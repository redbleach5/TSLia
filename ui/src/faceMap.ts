// Мост ARKit-52 → морфы текущей glTF-модели. Audio2Face-3D выдаёт ARKit-подобные
// blendshapes (52 веса на кадр, 30 кадров/с), а Lia.gltf содержит VRoid-совместимые
// имена Fcl_*: каждый ARKit-шейп приходится либо на один Fcl_-морф (с гейном), либо честно
// признаётся немаппируемым. Полное соответствие ARKit-52 возможно только на аватаре,
// у которого эти морфы есть; здесь совпадение частичное, и это видно в отчёте покрытия.
//
// Проверено на реальном файле: ui/public/models/Lia.gltf → 57 морфов Fcl_*
// (6 ALL, 5 BRW, 14 EYE, 19 MTH, 13 HA), см. scripts/model_capabilities.py.

// Канонические 52 ARKit-шейпа в порядке Apple/NVIDIA. Сервис отдаёт эти имена
// в animation data; осмысленность и наличие каждого канала проверяются на выбранной модели.
export const ARKIT_SHAPES:ReadonlyArray<string>=[
  'BrowDownLeft','BrowDownRight','BrowInnerUp','BrowOuterUpLeft','BrowOuterUpRight',
  'CheekPuff','CheekSquintLeft','CheekSquintRight',
  'EyeBlinkLeft','EyeBlinkRight','EyeLookDownLeft','EyeLookDownRight',
  'EyeLookInLeft','EyeLookInRight','EyeLookOutLeft','EyeLookOutRight',
  'EyeLookUpLeft','EyeLookUpRight','EyeSquintLeft','EyeSquintRight','EyeWideLeft','EyeWideRight',
  'JawForward','JawLeft','JawOpen','JawRight',
  'MouthClose','MouthDimpleLeft','MouthDimpleRight','MouthFrownLeft','MouthFrownRight','MouthFunnel',
  'MouthLeft','MouthLowerDownLeft','MouthLowerDownRight','MouthPressLeft','MouthPressRight',
  'MouthPucker','MouthRight','MouthRollLower','MouthRollUpper','MouthShrugLower','MouthShrugUpper',
  'MouthSmileLeft','MouthSmileRight','MouthStretchLeft','MouthStretchRight',
  'MouthUpperUpLeft','MouthUpperUpRight','NoseSneerLeft','NoseSneerRight','TongueOut',
]

// Таблица маппинга: [ARKit-шейп, морф модели, гейн, почему так].
// Гейн — не косметика: у VRoid многие группы симметричны (L/R шейпы идут в один морф)
// и включают мимику целиком, поэтому вес снижается, чтобы лицо не «складывалось» в гримасу.
export const ARKIT_TO_FCL:ReadonlyArray<readonly [string,string,number,string]>=[
  ['BrowDownLeft','Fcl_BRW_Angry',.55,'левая и правая бровь у VRoid — одна симметричная группа'],
  ['BrowDownRight','Fcl_BRW_Angry',.55,'симметрично, из пары берётся максимум'],
  ['BrowInnerUp','Fcl_BRW_Sorrow',.6,'внутренний край бровей вверх ≈ печаль'],
  ['BrowOuterUpLeft','Fcl_BRW_Surprised',.45,'наружный край вверх ≈ удивление'],
  ['BrowOuterUpRight','Fcl_BRW_Surprised',.45,'симметрично'],
  ['CheekSquintLeft','Fcl_EYE_Joy_L',.3,'щёчный прищур приближён улыбкой с прищуром'],
  ['CheekSquintRight','Fcl_EYE_Joy_R',.3,'симметрично'],
  ['EyeBlinkLeft','Fcl_EYE_Close_L',1,'точное соответствие: веко левого глаза'],
  ['EyeBlinkRight','Fcl_EYE_Close_R',1,'точное соответствие'],
  ['EyeSquintLeft','Fcl_EYE_Joy_L',.35,'прищур приближён группой улыбки с прищуром'],
  ['EyeSquintRight','Fcl_EYE_Joy_R',.35,'симметрично'],
  ['EyeWideLeft','Fcl_EYE_Spread',.6,'раскрытие глаз: точного L/R нет, берём общий морф'],
  ['EyeWideRight','Fcl_EYE_Spread',.6,'симметрично'],
  ['JawOpen','Fcl_MTH_A',1,'визем A: челюсть вниз — основная артикуляция'],
  ['MouthClose','Fcl_MTH_Close',.8,'у Audio2Face MouthClose включает открытие челюсти, поэтому гейн ниже'],
  ['MouthDimpleLeft','Fcl_MTH_Joy',.25,'ямочки приближены улыбкой рта'],
  ['MouthDimpleRight','Fcl_MTH_Joy',.25,'симметрично'],
  ['MouthFrownLeft','Fcl_MTH_Sorrow',.5,'уголки вниз ≈ печаль рта'],
  ['MouthFrownRight','Fcl_MTH_Sorrow',.5,'симметрично'],
  ['MouthFunnel','Fcl_MTH_O',.75,'воронка губ ≈ визем O'],
  ['MouthLowerDownLeft','Fcl_MTH_Down',.45,'нижняя губа вниз: только симметричный морф'],
  ['MouthLowerDownRight','Fcl_MTH_Down',.45,'симметрично'],
  ['MouthPressLeft','Fcl_MTH_Close',.35,'сжатые губы ≈ закрытие губ'],
  ['MouthPressRight','Fcl_MTH_Close',.35,'симметрично'],
  ['MouthPucker','Fcl_MTH_U',.85,'собранные губы ≈ визем U'],
  ['MouthSmileLeft','Fcl_MTH_Joy',.55,'улыбка рта: симметричный морф'],
  ['MouthSmileRight','Fcl_MTH_Joy',.55,'симметрично'],
  ['MouthStretchLeft','Fcl_MTH_Large',.35,'растянутый рот приближён широким виземом'],
  ['MouthStretchRight','Fcl_MTH_Large',.35,'симметрично'],
  ['MouthUpperUpLeft','Fcl_MTH_Up',.4,'верхняя губа вверх: только симметричный морф'],
  ['MouthUpperUpRight','Fcl_MTH_Up',.4,'симметрично'],
]

// Шейпы без цели в этой модели. Список явный, чтобы покрытие считалось честно.
// Это ограничение Lia.gltf, а не заявленный лимит Audio2Face-3D.
export const ARKIT_UNMAPPED:ReadonlyArray<string>=[
  'CheekPuff','EyeLookDownLeft','EyeLookDownRight','EyeLookInLeft','EyeLookInRight',
  'EyeLookOutLeft','EyeLookOutRight','EyeLookUpLeft','EyeLookUpRight',
  'JawForward','JawLeft','JawRight','MouthLeft','MouthRight',
  'MouthRollLower','MouthRollUpper','MouthShrugLower','MouthShrugUpper',
  'NoseSneerLeft','NoseSneerRight','TongueOut',
]

// Разбор входящих имён нечувствителен к регистру: заголовок от сервиса — внешние данные.
const TABLE=new Map<string,{target:string;gain:number}>(
  ARKIT_TO_FCL.map(([shape,target,gain])=>[shape.toLowerCase(),{target,gain}]),
)

export type ArkitWeights=Record<string,number>

export type ResolvedFrame={
  targets:Record<string,number>
  mapped:string[]
  lost:string[]
  missingTargets:string[]
}

export type FaceCoverage={
  shapes:number
  mapped:string[]
  lost:string[]
  missingTargets:string[]
  targets:string[]
}

const limit=(value:number)=>value<0?0:value>1?1:value

/** Приводит кадр ARKit-весов к морфам модели: неизвестное и лишнее отбрасывается. */
export function resolveArkitFrame(frame:ArkitWeights,have:Iterable<string>):ResolvedFrame{
  const available=have instanceof Set?have:new Set(have)
  const lowered=new Map(Object.entries(frame).map(([name,value])=>[name.trim().toLowerCase(),value]))
  const targets:Record<string,number>={}
  const mapped:string[]=[]
  const missing=new Set<string>()
  for(const [name,raw] of lowered){
    const entry=TABLE.get(name)
    if(!entry||!(raw>0))continue
    if(!available.has(entry.target)){missing.add(entry.target);continue}
    const value=limit(raw)*entry.gain
    targets[entry.target]=Math.max(targets[entry.target]??0,value)
    mapped.push(name)
  }
  const lost=ARKIT_UNMAPPED.filter(shape=>(lowered.get(shape.toLowerCase())??0)>0)
  return {targets,mapped,lost,missingTargets:[...missing]}
}

/** Отчёт о возможностях мимики: сколько ARKit-шейпов эта модель способна принять. */
export function faceCoverage(have:Iterable<string>):FaceCoverage{
  const available=have instanceof Set?have:new Set(have)
  const mapped:string[]=[]
  const missing=new Set<string>()
  const targets=new Set<string>()
  for(const [shape,target] of ARKIT_TO_FCL){
    targets.add(target)
    if(available.has(target))mapped.push(shape)
    else missing.add(target)
  }
  const inTable=new Set(ARKIT_TO_FCL.map(([shape])=>shape))
  const lost=[...ARKIT_UNMAPPED,...ARKIT_SHAPES.filter(shape=>!inTable.has(shape))]
  return {shapes:ARKIT_SHAPES.length,mapped,lost,missingTargets:[...missing],targets:[...targets]}
}

/** Имена морфов модели: нужны и ригу, и отчёту покрытия. */
export function morphNames(map:Map<string,unknown>):string[]{return [...map.keys()]}
