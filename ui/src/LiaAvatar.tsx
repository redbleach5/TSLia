import {useEffect,useRef,useState} from 'react'
import * as THREE from 'three'
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js'
import {AvatarRig} from './avatarRig'
import type {State} from './types'

type Props={
  state:State
  analyser:React.RefObject<AnalyserNode|null>
  // Шина ARKit-кадров от сервера: undefined, пока бэкенд мимики не подключён
  // (Audio2Face-3D). Без неё лицом управляет процедурный риг.
  faceFrame?:React.RefObject<Record<string,number>|null>
}

// Пути к glTF-аватару, пробуются по очереди. Файл кладётся в ui/public/models/.
const MODEL_PATHS=['/models/Lia.gltf','/models/Lia.glb','/models/avatar.gltf','/models/avatar.glb']
// Ориентация: экспорт Lia_v2 «сырой» (без rotateVRM0), старый VRM-код ставил rotation.y=PI,
// поэтому модель разворачиваем к камере. 0 — если модель уже смотрит лицом.
const MODEL_ROTATION_Y=Math.PI
// Кадрирование: целевая высота аватара и позиция ног после вписывания в вид камеры.
const FRAME_HEIGHT=1.55
const FRAME_Y=0.15
// Релакс-поза: анимаций в glTF нет (экспорт в T-позе), поэтому руки опускаем процедурно.
// Кости экспортированы без поворотов (matrix = translation, локальные оси = оси модели),
// руки направлены вдоль X (L=-X, R=+X) — опускание это поворот вокруг Z.
// Итоговый наклон ~67° от горизонтали (руки ~23° от вертикали, A-pose без клипов в корпус).
const ARM_POSE:ReadonlyArray<readonly [string,number]>=[
  ['J_Bip_L_Shoulder',12],['J_Bip_L_UpperArm',55],
  ['J_Bip_R_Shoulder',-12],['J_Bip_R_UpperArm',-55],
]

export function LiaAvatar({state,analyser,faceFrame}:Props){
  const host=useRef<HTMLDivElement>(null)
  const stateRef=useRef(state)
  // Актуальный проп держим в ref: цикл анимации создаётся один раз и не перезапускается.
  const faceRef=useRef(faceFrame)
  faceRef.current=faceFrame
  const [ready,setReady]=useState(false)
  const [error,setError]=useState(false)

  // Риг читает состояние покадрово сам: поза и мимика сглаживаются внутри,
  // поэтому здесь не нужно переписывать morph targets при каждом изменении state.
  useEffect(()=>{stateRef.current=state},[state])

  useEffect(()=>{
    if(!host.current)return
    let dead=false,frame=0
    let mixer:THREE.AnimationMixer|null=null
    let rig:AvatarRig|null=null
    const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(30,1,.1,100),renderer=new THREE.WebGLRenderer({alpha:true,antialias:true})
    // Кадр в полный рост под сцену (stage высотой 470, canvas 405): голова у верха canvas,
    // ноги — чуть выше подписи stage-caption (top:382px).
    camera.position.set(0,0.95,3.5)
    renderer.setPixelRatio(Math.min(devicePixelRatio,2))
    renderer.outputColorSpace=THREE.SRGBColorSpace
    // PBR-материалы (вместо MToon из VRM) пересвечиваются теми же интенсивностями света,
    // что и раньше — сглаживаем ACES-тонмаппингом.
    renderer.toneMapping=THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure=1
    host.current.appendChild(renderer.domElement)
    scene.add(new THREE.HemisphereLight(0xf5d6ff,0x171020,1.5))
    const key=new THREE.DirectionalLight(0xffe7ee,2.6)
    key.position.set(2,4,3)
    scene.add(key)
    const rim=new THREE.DirectionalLight(0x9b7cff,1.8)
    rim.position.set(-3,2,-2)
    scene.add(rim)
    const wrapper=new THREE.Group()
    scene.add(wrapper)

    const resize=()=>{if(!host.current)return;const {clientWidth:w,clientHeight:h}=host.current;camera.aspect=w/h;camera.updateProjectionMatrix();renderer.setSize(w,h)}
    resize()
    const ro=new ResizeObserver(resize)
    ro.observe(host.current)

    // Загрузка первой доступной модели, нормализация масштаба и центрирование по bbox.
    const loadModel=async():Promise<THREE.Object3D>=>{
      const loader=new GLTFLoader()
      for(const path of MODEL_PATHS){
        try{
          const g=await loader.loadAsync(path)
          const box=new THREE.Box3().setFromObject(g.scene)
          const size=box.getSize(new THREE.Vector3()),center=box.getCenter(new THREE.Vector3())
          const scale=size.y>0?FRAME_HEIGHT/size.y:1
          g.scene.scale.setScalar(scale)
          g.scene.position.set(-center.x*scale,FRAME_Y-box.min.y*scale,-center.z*scale)
          if(g.animations.length){
            const clip=g.animations.find(a=>/idle|breath/i.test(a.name))??g.animations[0]
            mixer=new THREE.AnimationMixer(g.scene)
            mixer.clipAction(clip).play()
          }
          // Снимаем T-позу: анимаций в файле нет, ставим руки вдоль тела.
          for(const [name,deg] of ARM_POSE){
            const bone=g.scene.getObjectByName(name)
            if(bone)bone.rotation.z+=THREE.MathUtils.degToRad(deg)
          }
          return g.scene
        }catch{/* пробуем следующий путь */}
      }
      throw new Error('model not found')
    }

    loadModel().then(root=>{
      if(dead)return
      // Риг создаётся после релакс-позы: он запоминает базовые повороты костей
      // и дальше двигает их только относительно базы (см. avatarRig.ts).
      rig=new AvatarRig(root,wrapper,MODEL_ROTATION_Y)
      wrapper.add(root)
      // Честный отчёт о мимике: сколько ARKit-шейпов эта модель принимает.
      // Модель VRoid (57 морфов Fcl_*) принимает не все 52 — см. ui/src/faceMap.ts.
      const cover=rig.coverage()
      console.info(`[мимика] ARKit: ${cover.mapped.length}/${cover.shapes} шейпов принимается, ${cover.lost.length} нет морфов`
        + (cover.missingTargets.length?`; в модели отсутствуют: ${cover.missingTargets.join(', ')}`:''))
      setReady(true)
    }).catch(()=>{if(!dead)setError(true)})

    const clock=new THREE.Clock()
    let time=new Uint8Array(1024)
    const animate=()=>{
      frame=requestAnimationFrame(animate)
      const dt=Math.min(clock.getDelta(),.1),t=clock.elapsedTime
      mixer?.update(dt)
      // Артикуляция: RMS тайм-домена вместо |x-128| по частотным бинам — в бинах
      // есть DC-сдвиг 128, из-за которого рот открывался даже в полной тишине.
      const st=stateRef.current
      let voice=0
      if(st==='speaking'){
        const node=analyser.current
        if(node){
          if(time.length!==node.fftSize)time=new Uint8Array(node.fftSize)
          node.getByteTimeDomainData(time)
          let sum=0
          for(let i=0;i<time.length;i++){const v=(time[i]-128)/128;sum+=v*v}
          voice=Math.max(0,Math.min(1,(Math.sqrt(sum/time.length)-.012)/.18))
        }else{
          // Речь ещё без analyser: грубая артикуляция, чтобы рот не стоял камнем.
          voice=.35+.3*Math.abs(Math.sin(t*7.3))*(.6+.4*Math.sin(t*2.1))
        }
      }
      rig?.update(dt,t,{state:st,voice})
      // Кадр ARKit от бэкенда мимики: применяется один раз на приход, дальше риг
      // держит морфы сам (EXT_HOLD) и плавно возвращает себе управление.
      const pendingFace=faceRef.current?.current
      if(pendingFace&&rig){
        rig.applyArkitFrame(pendingFace,t)
        if(faceRef.current)faceRef.current.current=null
      }
      renderer.render(scene,camera)
    }
    animate()
    return()=>{
      dead=true
      cancelAnimationFrame(frame)
      ro.disconnect()
      mixer?.stopAllAction()
      rig=null
      scene.clear()
      renderer.dispose()
      renderer.domElement.remove()
    }
  },[])

  return <div className="avatar-viewport" ref={host}>{!ready&&!error&&<div className="avatar-loading">Лия пробуждается…</div>}{error&&<div className="avatar-error">Не удалось загрузить модель: положите Lia.gltf в ui/public/models/</div>}<div className={`avatar-fallback ${ready?'hidden':''}`}><div className="simple-face"><i/><i/><b/></div><div className="simple-body"/></div></div>
}
