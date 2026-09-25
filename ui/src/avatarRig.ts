import * as THREE from 'three'
import type {State} from './types'
import {faceCoverage,resolveArkitFrame,morphNames} from './faceMap'
import type {ArkitWeights} from './faceMap'

// Процедурная «жизнь» аватара. Анимационных клипов в glTF нет (экспорт в T-позе),
// поэтому дыхание, перенос веса, взгляд, моргание, мимика, артикуляция, расслабленная
// кисть и вторичная динамика волос считаются покадрово на костях и morph targets.
// Кости экспортированы без поворотов, оси модели: вперёд −Z, лево −X, верх +Y.
// Отсюда знаки: наклон головы вперёд — отрицательный rotation.x, поворот к «своей
// левой» — положительный rotation.y, наклон к левому плечу — положительный rotation.z.

const D=Math.PI/180
const clamp=(v:number,a:number,b:number)=>v<a?a:v>b?b:v
const rand=(a:number,b:number)=>a+Math.random()*(b-a)
// Экспоненциальное сглаживание: скорость задаётся в 1/с и не зависит от FPS.
const approach=(cur:number,to:number,rate:number,dt:number)=>cur+(to-cur)*(1-Math.exp(-rate*dt))
const smooth=(x:number)=>{const t=clamp(x,0,1);return t*t*(3-2*t)}
// Гладкий псевдослучайный шум на сумме несовпадающих по частоте синусоид:
// бесшовный и без рывков Math.random() на каждом кадре.
const noise=(t:number,ph:number,a=.11,b=.29,c=.63)=>
  Math.sin((t*a+ph)*6.283)*.55+Math.sin((t*b+ph*1.7)*6.283)*.3+Math.sin((t*c+ph*2.9)*6.283)*.15

// Сколько секунд после последнего ARKit-кадра риг держит губы/брови за внешним
// источником. Audio2Face-3D отдаёт 30 кадров/с, поэтому 0.4 с — запас на сетевой джиттер.
const EXT_HOLD=.4

type Slot={mesh:THREE.Mesh;index:number}
type Morphs=Map<string,Slot[]>
// Снимок базовой (T-поза/покой) трансформации кости: каждый кадр пишем base+offset.
type Handle={obj:THREE.Object3D;rx:number;ry:number;rz:number;px:number;py:number;pz:number}

// Алиасы morph targets: применяется первая группа с найденным morph. Имена VRoid-морфов
// сохранены как совместимые с историческим glTF-аватаром Лии.
const ALIASES:Record<string,ReadonlyArray<ReadonlyArray<string>>>={
  happy:[['happy'],['joy'],['smile'],['Fcl_ALL_Joy']],
  relaxed:[['relaxed'],['relief'],['calm'],['Fcl_ALL_Fun']],
  surprised:[['surprised'],['surprise'],['shocked'],['Fcl_ALL_Surprised']],
  thinking:[['thinking'],['pensive'],['Fcl_BRW_Sorrow']],
  eyes:[['eyesWide'],['spread'],['Fcl_EYE_Spread']],
  smile:[['mouthSmile'],['smileMouth'],['Fcl_MTH_Fun']],
  blink:[['blink'],['Fcl_EYE_Close'],['blinkLeft','blinkRight'],['blink_L','blink_R'],['Fcl_EYE_Close_L','Fcl_EYE_Close_R']],
  aa:[['aa'],['jawOpen'],['mouthOpen'],['viseme_aa'],['Fcl_MTH_A']],
  oh:[['oh'],['mouthO'],['viseme_oh'],['Fcl_MTH_O']],
  // Дополнительные виземы: нужны для внешних ARKit-кадров (MouthPucker/Funnel/Stretch)
  // и доступны в процедурной артикуляции, если её решат расширить.
  ou:[['ou'],['mouthU'],['viseme_ou'],['Fcl_MTH_U']],
  ih:[['ih'],['viseme_ih'],['Fcl_MTH_I']],
  ee:[['ee'],['viseme_ee'],['Fcl_MTH_E']],
  closeMouth:[['mouthClose'],['Fcl_MTH_Close'],['Fcl_MTH_Neutral']],
  mouthUp:[['mouthUp'],['Fcl_MTH_Up']],
  mouthDown:[['mouthDown'],['Fcl_MTH_Down']],
  mouthWide:[['mouthLarge'],['Fcl_MTH_Large']],
}

// Поза корпуса/взгляда по состояниям (градусы). Сменяется медленно (~2.2/с),
// чтобы переход «слушает → думает» читался как движение человека, а не как телепорт.
type Pose={
  spineX:number;chestX:number;headX:number;headY:number;headZ:number
  gazeX:number;gazeY:number;blink:number
}
const STATE_POSE:Record<State,Pose>={
  // idle — лёгкая сутулость покоя, взгляд блуждает вокруг камеры.
  idle:{spineX:-.6,chestX:-.4,headX:-1,headY:0,headZ:0,gazeX:0,gazeY:-1,blink:1},
  // listening — податься вперёд, раскрыть грудь, смотреть «в уши», плечи выше.
  listening:{spineX:-2.6,chestX:-1.2,headX:-1.2,headY:0,headZ:1.2,gazeX:0,gazeY:0,blink:1.2},
  // thinking — откинуться, отвести взгляд в сторону и вниз, хмурить брови.
  thinking:{spineX:.4,chestX:.8,headX:-4.5,headY:7,headZ:-3,gazeX:6,gazeY:-4,blink:.75},
  // speaking — прямо на слушателя, микропокачивание головой в ритме речи.
  speaking:{spineX:-1.2,chestX:-.6,headX:-.6,headY:0,headZ:0,gazeX:0,gazeY:0,blink:1},
  error:{spineX:.6,chestX:.4,headX:2,headY:-4,headZ:-5,gazeX:-3,gazeY:-3,blink:1.25},
}

// Целевые значения мимики по состояниям. Суммы держим умеренными: полные морфы
// лица (ALL_*) складываются и быстро выглядят гримасой, если их много.
const STATE_FACE:Record<State,Record<string,number>>={
  idle:{happy:0,relaxed:.5,surprised:0,thinking:0,eyes:.06,smile:.22},
  listening:{happy:.08,relaxed:.3,surprised:.16,thinking:0,eyes:.3,smile:.3},
  thinking:{happy:0,relaxed:.16,surprised:0,thinking:.55,eyes:.1,smile:.06},
  speaking:{happy:.22,relaxed:.3,surprised:.03,thinking:0,eyes:.16,smile:.3},
  error:{happy:0,relaxed:.12,surprised:.2,thinking:.5,eyes:.24,smile:0},
}
// Длительность одного цикла дыхания, с. Ускоряется на речи и в внимании.
const STATE_BREATH:Record<State,number>={idle:4.6,listening:3.8,thinking:4.4,speaking:3.1,error:3.6}

// Расслабленная кисть: пальцы полу-сжаты (прямые пальцы в покое выглядят как у куклы).
// [Index, Middle, Ring, Little] × [проксимальный, средний, дистальный] суставы.
const FINGERS=['Index','Middle','Ring','Little'] as const
const CURL=[17,19,21,23]
const JOINT=[1,.7,.4]

function collectMorphs(root:THREE.Object3D):Morphs{
  const map:Morphs=new Map()
  root.traverse(o=>{
    if(!(o as THREE.Mesh).isMesh)return
    const mesh=o as THREE.Mesh
    const dict=mesh.morphTargetDictionary
    if(!dict||!mesh.morphTargetInfluences)return
    for(const [name,index] of Object.entries(dict)){
      const list=map.get(name)??[]
      list.push({mesh,index})
      map.set(name,list)
    }
  })
  return map
}

function setMorph(map:Morphs,name:string,value:number){
  for(const slot of map.get(name)??[])slot.mesh.morphTargetInfluences![slot.index]=value
}

function setExpr(map:Morphs,key:string,value:number,skip?:ReadonlySet<string>){
  for(const group of ALIASES[key]??[]){
    // Морфы, которыми сейчас владеет внешний ARKit-кадр, не перезаписываем: иначе
    // процедурная мимика и данные Audio2Face будут драться за один и тот же морф.
    // Если вся группа заблокирована — возвращаемся, не переходя к менее точной группе.
    let hit=false,blocked=false
    for(const alias of group){
      if(!map.has(alias))continue
      if(skip?.has(alias)){blocked=true;continue}
      setMorph(map,alias,value);hit=true
    }
    if(hit||blocked)return
  }
}

const track=(root:THREE.Object3D,name:string):Handle|null=>{
  const obj=name?root.getObjectByName(name):root
  if(!obj)return null
  return {obj,rx:obj.rotation.x,ry:obj.rotation.y,rz:obj.rotation.z,px:obj.position.x,py:obj.position.y,pz:obj.position.z}
}

// Вдох занимает 35% цикла, дальше короткая пауза и спокойный выдох:
// дыхание человека не синусоида, и это заметно при сравнении кадров.
const breathCurve=(p:number)=>{
  if(p<.35)return smooth(p/.35)
  if(p<.45)return 1
  return 1-smooth((p-.45)/.55)
}

// Пружина для вторичной динамики (волосы): почти критическое затухание.
type Spring={x:number;v:number}
const springStep=(s:Spring,to:number,dt:number,k:number,c:number)=>{
  const v=s.v+(to-s.x)*k*dt-c*s.v*dt
  s.x+=v*dt
  s.v=v
}

export type RigInput={state:State;voice:number}

export class AvatarRig{
  private stage:THREE.Object3D|null
  private baseYaw:number
  private morphs:Morphs

  private hips:Handle|null=null
  private spine:Handle|null=null
  private chest:Handle|null=null
  private upper:Handle|null=null
  private neck:Handle|null=null
  private head:Handle|null=null
  private eyeL:Handle|null=null
  private eyeR:Handle|null=null
  private shL:Handle|null=null
  private shR:Handle|null=null
  private uaL:Handle|null=null
  private uaR:Handle|null=null
  private laL:Handle|null=null
  private laR:Handle|null=null
  private hdL:Handle|null=null
  private hdR:Handle|null=null
  private fingers:{h:Handle;sign:number;amount:number}[]=[]
  private hair:{h:Handle;rate:number;lag:Spring[];off:Spring[];ph:number}[]=[]

  // сглаженные внутренние состояния
  private pose:Pose={...STATE_POSE.idle}
  private face:Record<string,number>={happy:0,relaxed:0,surprised:0,thinking:0,eyes:0,smile:0}
  private breathPhase=Math.random()*.6
  private armAmp=1
  private perk=0
  private shift=0
  private shiftTarget=0
  private nextShift=5
  private mouth=0
  private gazeX=0
  private gazeY=0
  private gazeTX=0
  private gazeTY=0
  private nextSaccade=1
  private blinkStart=-1
  private blinkDur=.15
  private nextBlink=1.6
  private doubleBlink=false
  private slowBlink=false
  private nodP=-1
  private nodDur=.6
  private nodAmp=0
  private nodT=3
  // Внешняя мимика (ARKit-кадры сервера): пока кадры идут, риг уступает им губы,
  // брови и моргание, а после паузы плавно возвращает управление себе.
  private extTargets:Record<string,number>={}
  private extSkip=new Set<string>()
  private extUntil=-1
  private extBlend=0
  private extLost:string[]=[]
  private firstQ=true
  private prevQ=new THREE.Quaternion()
  private q=new THREE.Quaternion()
  private invQ=new THREE.Quaternion()
  private dq=new THREE.Quaternion()
  private av=new THREE.Vector3()

  constructor(root:THREE.Object3D,stage?:THREE.Object3D|null,baseYaw=0){
    this.stage=stage??null
    this.baseYaw=baseYaw
    this.morphs=collectMorphs(root)
    this.hips=track(root,'J_Bip_C_Hips')
    this.spine=track(root,'J_Bip_C_Spine')
    this.chest=track(root,'J_Bip_C_Chest')
    this.upper=track(root,'J_Bip_C_UpperChest')
    this.neck=track(root,'J_Bip_C_Neck')
    this.head=track(root,'J_Bip_C_Head')
    this.eyeL=track(root,'J_Adj_L_FaceEye')
    this.eyeR=track(root,'J_Adj_R_FaceEye')
    this.shL=track(root,'J_Bip_L_Shoulder')
    this.shR=track(root,'J_Bip_R_Shoulder')
    this.uaL=track(root,'J_Bip_L_UpperArm')
    this.uaR=track(root,'J_Bip_R_UpperArm')
    this.laL=track(root,'J_Bip_L_LowerArm')
    this.laR=track(root,'J_Bip_R_LowerArm')
    this.hdL=track(root,'J_Bip_L_Hand')
    this.hdR=track(root,'J_Bip_R_Hand')
    // Кисть: изгиб пальцев вокруг Z, знак зеркален для левой (палец идёт к ладони −Y).
    for(const side of ['L','R'] as const){
      const sign=side==='L'?1:-1
      FINGERS.forEach((f,i)=>{
        JOINT.forEach((share,j)=>{
          const h=track(root,`J_Bip_${side}_${f}${j+1}`)
          if(h)this.fingers.push({h,sign,amount:CURL[i]*share})
        })
      })
    }
    // Волосы: цепочки J_Sec_Hair*. Глубина считается по предкам — наружные косточки
    // реагируют сильнее и с запаздыванием, отсюда «догоняющая» прядь.
    root.traverse(o=>{
      if(!/^J_Sec_Hair\d_/.test(o.name))return
      const h=track(o,'')
      if(!h)return
      let depth=0,p=o.parent
      while(p){if(/^J_Sec_Hair\d_/.test(p.name))depth++;p=p.parent}
      this.hair.push({
        h,
        rate:16/(1+depth*.85),
        lag:[{x:0,v:0},{x:0,v:0},{x:0,v:0}],
        off:[{x:0,v:0},{x:0,v:0},{x:0,v:0}],
        ph:Math.random()*9,
      })
    })
  }

  /** Кадр ARKit-весов от бэкенда мимики: 52 веса → морфы Fcl_* этой модели. */
  applyArkitFrame(frame:ArkitWeights,t:number){
    const resolved=resolveArkitFrame(frame,this.morphs.keys())
    this.extTargets=resolved.targets
    this.extLost=resolved.lost
    this.extSkip=new Set(Object.keys(resolved.targets))
    this.extUntil=t+EXT_HOLD
  }

  /** Отчёт о мимике: сколько ARKit-шейпов модель реально принимает, а сколько теряется. */
  coverage(){return faceCoverage(morphNames(this.morphs))}

  /** Шейпы из последнего кадра, для которых в модели нет морфа. */
  get lostShapes():ReadonlyArray<string>{return this.extLost}

  /** Запись мимики с учётом владения морфами со стороны внешнего кадра. */
  private paint(m:Morphs,key:string,value:number){
    setExpr(m,key,value,this.extBlend>.01?this.extSkip:undefined)
  }

  // Один кадр жизни: поза → дыхание → корпус → руки → взгляд → мимика → волосы.
  update(dt:number,t:number,input:RigInput){
    dt=clamp(dt,0,.1)
    const dtSafe=dt>0?dt:1/60
    const st=input.state,m=this.morphs,ps=this.pose,goal=STATE_POSE[st]

    // --- сглаженная поза состояния (~2.2/с): переход читается как движение человека
    ps.spineX=approach(ps.spineX,goal.spineX,2.2,dt)
    ps.chestX=approach(ps.chestX,goal.chestX,2.2,dt)
    ps.headX=approach(ps.headX,goal.headX,2.2,dt)
    ps.headY=approach(ps.headY,goal.headY,2.2,dt)
    ps.headZ=approach(ps.headZ,goal.headZ,2.2,dt)
    ps.gazeX=approach(ps.gazeX,goal.gazeX,3,dt)
    ps.gazeY=approach(ps.gazeY,goal.gazeY,3,dt)
    ps.blink=approach(ps.blink,goal.blink,1.5,dt)
    // активность рук и «настороженность» плеч тоже сглаживаем: иначе смена state
    // даёт мгновенный рывок конечности на несколько градусов за один кадр.
    this.armAmp=approach(this.armAmp,st==='speaking'?1.8:st==='listening'?.6:1,2.5,dt)
    this.perk=approach(this.perk,st==='listening'?1:0,2.5,dt)

    // --- артикуляция: огибающая с быстрой атакой и медленным спадом —
    // рот открывается на звуке и закрывается с инерцией, а не дребезжит по RMS.
    const voice=clamp(input.voice,0,1)
    this.mouth=approach(this.mouth,voice,voice>this.mouth?17:9,dt)

    // --- дыхание: несимметричный цикл, длина зависит от состояния
    const period=STATE_BREATH[st]*(1+noise(t,1.7,.05,.13,.29)*.06)
    this.breathPhase=(this.breathPhase+dt/period)%1
    const br=breathCurve(this.breathPhase)

    // --- медленный перенос веса с ноги на ногу + постоянное микрокачание
    if(t>this.nextShift){this.shiftTarget=rand(-1,1)*.026;this.nextShift=t+rand(6,14)}
    this.shift=approach(this.shift,this.shiftTarget,.5,dt)
    const swayY=noise(t,.7)
    const swayR=noise(t,2.3,.09,.27,.51)
    const drift=noise(t,4.1,.13,.31,.67)

    // --- сцена: корпус дышит и покачивается, а не болтается на синусе
    if(this.stage){
      this.stage.position.set(swayR*.003,br*.006+drift*.002,swayY*.002)
      this.stage.rotation.set(noise(t,5.3,.07,.19,.41)*.5*D,this.baseYaw+swayY*1.5*D,swayR*.5*D)
    }

    // --- таз: перенос веса и микроповороты; корпус контрповоротом держит баланс
    const hipsYaw=(swayY*1.1+this.shift*22)*D
    const hipsRoll=(swayR*.9-this.shift*26)*D
    if(this.hips){
      const h=this.hips
      h.obj.position.set(h.px+this.shift+swayR*.003,h.py,h.pz+swayY*.002)
      h.obj.rotation.set(h.rx,h.ry+hipsYaw,h.rz+hipsRoll)
    }
    if(this.spine){
      const v=this.spine
      // контрсдвиг позвоночника, чтобы голова оставалась над центром кадра
      v.obj.position.set(v.px-this.shift*.45,v.py,v.pz)
      v.obj.rotation.set(v.rx+(ps.spineX+br*.5)*D,v.ry-hipsYaw*.5,v.rz)
    }
    if(this.chest)this.chest.obj.rotation.set(this.chest.rx+(ps.chestX+br*1)*D,this.chest.ry-hipsYaw*.35,this.chest.rz)
    if(this.upper)this.upper.obj.rotation.set(this.upper.rx+br*.75*D,this.upper.ry,this.upper.rz)

    // --- плечи: на вдохе поднимаются (элевация ключицы трансляцией), в «слушании» — выше
    const shr=br*.006+this.perk*.002
    const shrRot=(br*1.9+this.perk*1.2)*D
    if(this.shL&&this.shR){
      this.shL.obj.position.set(this.shL.px,this.shL.py+shr,this.shL.pz)
      this.shL.obj.rotation.set(this.shL.rx,this.shL.ry,this.shL.rz-shrRot)
      this.shR.obj.position.set(this.shR.px,this.shR.py+shr,this.shR.pz)
      this.shR.obj.rotation.set(this.shR.rx,this.shR.ry,this.shR.rz+shrRot)
    }

    // --- руки: отстают от корпуса по инерции; в речи амплитуда жеста выше
    const armAmp=this.armAmp
    const lag=noise(t-.3,1.1,.1,.25,.55)
    const roll=noise(t,3.1,.12,.3,.66)
    const elbow=(4+noise(t,2.7,.14,.33,.7)*2.5+this.mouth*3)*armAmp
    if(this.uaL&&this.uaR){
      this.uaL.obj.rotation.set(this.uaL.rx+roll*1.2*D,this.uaL.ry-lag*1.3*armAmp*D,this.uaL.rz+lag*.7*armAmp*D)
      this.uaR.obj.rotation.set(this.uaR.rx+roll*1.2*D,this.uaR.ry+lag*1.3*armAmp*D,this.uaR.rz-lag*.7*armAmp*D)
    }
    if(this.laL)this.laL.obj.rotation.set(this.laL.rx+elbow*D,this.laL.ry,this.laL.rz)
    if(this.laR)this.laR.obj.rotation.set(this.laR.rx+elbow*D,this.laR.ry,this.laR.rz)
    const wrist=noise(t,6.1,.16,.37,.8)*2.5*armAmp
    if(this.hdL)this.hdL.obj.rotation.set(this.hdL.rx,this.hdL.ry+wrist*D,this.hdL.rz-wrist*.5*D)
    if(this.hdR)this.hdR.obj.rotation.set(this.hdR.rx,this.hdR.ry+wrist*D,this.hdR.rz+wrist*.5*D)

    // --- кисть: пальцы полу-сжаты и слегка «дышат», в речи подрабатывают жестом
    const flex=noise(t,7.7,.19,.41,.9)*2.5+Math.max(0,this.armAmp-1)*2.5
    for(const f of this.fingers){
      f.h.obj.rotation.set(f.h.rx,f.h.ry,f.h.rz+f.sign*(f.amount+flex*(f.amount/20))*D)
    }

    // --- микро-кивок: вживляется в «слушание» и речь, редко — в покое
    if(this.nodP<0){
      this.nodT-=dt
      if(this.nodT<=0){
        this.nodP=0
        this.nodDur=rand(.5,.8)
        this.nodAmp=st==='listening'?rand(1.8,3):st==='speaking'?rand(1,2):rand(1,1.8)
        this.nodT=st==='listening'?rand(2.6,5):st==='speaking'?rand(3,6):rand(6,12)
      }
    }else{
      this.nodP+=dt/this.nodDur
      if(this.nodP>=1)this.nodP=-1
    }
    const nod=this.nodP<0?0:Math.sin(this.nodP*Math.PI*1.7)*Math.exp(-this.nodP*2.4)*this.nodAmp

    // --- саккады: глаза дёргаются к точке и держат её, между ними микродрейф
    if(t>this.nextSaccade){
      this.gazeTX=clamp(goal.gazeX+rand(-5,5),-11,11)
      this.gazeTY=clamp(goal.gazeY+rand(-4,4),-7,7)
      this.nextSaccade=t+rand(1.1,st==='speaking'?1.7:3.4)
    }
    this.gazeX=approach(this.gazeX,this.gazeTX,16,dt)
    this.gazeY=approach(this.gazeY,this.gazeTY,16,dt)
    const gx=clamp(this.gazeX+noise(t,8.7,.5,1.1,2.3)*.3,-11,11)
    const gy=clamp(this.gazeY+noise(t,9.3,.45,1.3,2.7)*.25,-7,7)
    if(this.eyeL)this.eyeL.obj.rotation.set(this.eyeL.rx+gy*D,this.eyeL.ry+gx*D,this.eyeL.rz)
    if(this.eyeR)this.eyeR.obj.rotation.set(this.eyeR.rx+gy*D,this.eyeR.ry+gx*D,this.eyeR.rz)

    // --- моргание: случайные интервалы, редкие двойные и очень редкие «сонные»
    let blink=0
    if(this.blinkStart>=0){
      const q=(t-this.blinkStart)/this.blinkDur
      if(q>=1)this.blinkStart=-1
      else blink=q<.38?smooth(q/.38):q<.5?1:1-smooth((q-.5)/.5)
    }
    if(this.blinkStart<0&&t>=this.nextBlink){
      this.blinkStart=t
      this.blinkDur=this.slowBlink?.4:rand(.13,.17)
      this.slowBlink=Math.random()<.05
      const rate=Math.max(ps.blink,.3)
      if(this.doubleBlink){this.doubleBlink=false;this.nextBlink=t+rand(2.4,6)/rate}
      else{
        this.nextBlink=t+rand(1.8,5)/rate
        if(Math.random()<.18){this.doubleBlink=true;this.nextBlink=t+rand(.24,.42)}
      }
    }

    // --- шея и голова: поза состояния + микрошум + следование за взглядом + кивок
    const hnX=noise(t,1.3,.12,.31,.66)*1.1
    const hnY=noise(t,2.9,.1,.27,.58)*1.6
    const hnZ=noise(t,4.7,.09,.23,.51)*1.3
    const mouthLean=this.mouth*.9
    if(this.head){
      const h=this.head
      h.obj.rotation.set(
        h.rx+(ps.headX*.62+hnX*.55+gx*.22+nod*.62-mouthLean)*D,
        h.ry+(ps.headY*.62+hnY*.55+gx*.22)*D,
        h.rz+(ps.headZ*.62+hnZ*.55)*D,
      )
    }
    if(this.neck){
      const n=this.neck
      n.obj.rotation.set(
        n.rx+(ps.headX*.38+hnX*.45+nod*.38+gx*.08)*D,
        n.ry+(ps.headY*.38+hnY*.45+gx*.08)*D,
        n.rz+(ps.headZ*.38+hnZ*.45)*D,
      )
    }

    // --- мимика: плавно едет к цели состояния, поверх — микромимика ±4%
    const targets=STATE_FACE[st]
    Object.keys(this.face).forEach((key,i)=>{
      const want=(targets[key]??0)*(1+noise(t,i*1.7)*.04)
      this.face[key]=approach(this.face[key],want,2.1,dt)
      this.paint(m,key,this.face[key])
    })
    this.paint(m,'aa',Math.pow(this.mouth,.85))
    this.paint(m,'oh',clamp((this.mouth-.5)*.9,0,.55))
    this.paint(m,'blink',blink)

    // --- внешняя мимика: пока приходят ARKit-кадры, они владеют губами/бровями/веками.
    // Смешивание идёт по extBlend, поэтому вход и выход из режима не «щёлкают» лицом.
    const extAlive=t<this.extUntil
    this.extBlend=approach(this.extBlend,extAlive?1:0,extAlive?18:6,dt)
    if(this.extBlend>.005){
      for(const [name,value] of Object.entries(this.extTargets))setMorph(m,name,value*this.extBlend)
    }

    // --- вторичная динамика волос: пряди отстают от поворота головы и качаются сами
    if(this.head){
      this.head.obj.getWorldQuaternion(this.q)
      if(this.firstQ){this.prevQ.copy(this.q);this.firstQ=false}
      else{
        // угловая скорость кадра, переведённая в систему координат головы
        this.invQ.copy(this.prevQ).invert()
        this.dq.copy(this.q).multiply(this.invQ)
        const w=clamp(this.dq.w,-1,1)
        const s=Math.sqrt(Math.max(1-w*w,0))
        if(s>1e-6){
          const angle=2*Math.acos(w)
          this.av.set(this.dq.x/s,this.dq.y/s,this.dq.z/s)
            .multiplyScalar((angle>Math.PI?angle-2*Math.PI:angle)/dtSafe)
          if(this.av.lengthSq()>36)this.av.setLength(6)
          this.invQ.copy(this.q).invert()
          this.av.applyQuaternion(this.invQ)
        }else this.av.set(0,0,0)
        this.prevQ.copy(this.q)
      }
      for(const b of this.hair){
        for(let a=0;a<3;a++){
          b.lag[a].x=approach(b.lag[a].x,this.av.getComponent(a),b.rate,dt)
          const to=clamp(-.06*b.lag[a].x,-.055,.055)+noise(t,b.ph+a*1.3,.17,.4,.9)*1.2*D
          springStep(b.off[a],to,dt,110,16)
        }
        b.h.obj.rotation.set(b.h.rx+b.off[0].x,b.h.ry+b.off[1].x,b.h.rz+b.off[2].x)
      }
    }
  }
}
