import {useEffect,useRef,useState} from 'react'
import {LiyaSocket} from './api'
import {useAudioPlaybackQueue} from './audioQueue'
import type {Message,ServerEvent,State} from './types'

type Fact = Extract<ServerEvent,{type:'memory'}>['facts'] extends (infer T)[]|undefined ? T : never
type Metrics = Extract<ServerEvent,{type:'pipeline_metrics'}>
type Latency = Extract<ServerEvent,{type:'latency_stats'}>['stats']

export type LiaRuntime = ReturnType<typeof useLiaRuntime>

export function useLiaRuntime(){
  const socket=useRef<LiyaSocket|null>(null)
  if(!socket.current) socket.current=new LiyaSocket()
  const analyser=useRef<AnalyserNode|null>(null)
  const playback=useAudioPlaybackQueue(a=>{analyser.current=a})
  const faceFrame=useRef<Record<string,number>|null>(null)
  const requestId=useRef(0)
  const stream=useRef<MediaStream|null>(null)
  const node=useRef<AudioWorkletNode|null>(null)
  const capture=useRef<AudioContext|null>(null)
  const [state,setState]=useState<State>('idle')
  const [metrics,setMetrics]=useState<Metrics|null>(null)
  const [latency,setLatency]=useState<Latency|null>(null)
  const [facts,setFacts]=useState<Fact[]>([])
  const [input,setInput]=useState('')
  const [panel,setPanel]=useState(false)
  const [connected,setConnected]=useState(false)
  const [messages,setMessages]=useState<Message[]>([{id:'hi',role:'assistant',text:'Привет. Я Лия. Рада, что ты здесь.',time:'сейчас'}])

  const send=(event:unknown)=>socket.current?.send(event)
  const stopCapture=()=>{node.current?.disconnect();capture.current?.close();stream.current?.getTracks().forEach(track=>track.stop());node.current=null;capture.current=null;stream.current=null}
  const start=async()=>{if(node.current)return;try{stream.current=await navigator.mediaDevices.getUserMedia({audio:true});const context=new AudioContext({sampleRate:32000});capture.current=context;await context.audioWorklet.addModule('/worklets/pcm-processor.js');const source=context.createMediaStreamSource(stream.current),audioNode=new AudioWorkletNode(context,'pcm-processor');audioNode.port.onmessage=event=>{const raw=event.data as Float32Array,pcm=new Int16Array(raw.length);for(let i=0;i<raw.length;i++){const value=Math.max(-1,Math.min(1,raw[i]));pcm[i]=value<0?value*0x8000:value*0x7fff}let binary='';for(const value of pcm)binary+=String.fromCharCode(value);send({type:'audio_pcm_chunk',request_id:requestId.current,data:btoa(binary)})};source.connect(audioNode);audioNode.connect(context.destination);node.current=audioNode;requestId.current=Date.now();send({type:'start_listening',request_id:requestId.current})}catch{setState('error')}}
  const stop=()=>{if(!node.current)return;stopCapture();send({type:'finish_listening',request_id:requestId.current,format:'pcm_s16le'})}
  const submit=(text?:string)=>{const value=(text??input).trim();if(value){setInput('');send({type:'text',text:value})}}
  const cancel=()=>{playback.clear();send({type:'cancel'})}

  useEffect(()=>{const currentSocket=socket.current!;currentSocket.onOpen(()=>setConnected(true));let retry=0;currentSocket.onClose(()=>{setConnected(false);retry=window.setTimeout(()=>currentSocket.connect(),2000)});currentSocket.onMessage((event:ServerEvent)=>{if(event.type==='state')setState(event.state);if(event.type==='pipeline_metrics')setMetrics(event);if(event.type==='latency_stats')setLatency(event.stats);if(event.type==='face_frame'&&event.weights)faceFrame.current=event.weights;if(event.type==='memory'&&event.facts)setFacts(event.facts);if(event.type==='interim_transcript'){setState('thinking');setMessages(current=>{const last=current[current.length-1];return last?.id==='interim'?current.map(message=>message.id==='interim'?{...message,text:event.text}:message):[...current,{id:'interim',role:'user',text:event.text,time:'сейчас'}]})}if(event.type==='transcript'&&event.text)setMessages(current=>{const last=current[current.length-1];return last?.id==='interim'?current.map(message=>message.id==='interim'?{...message,id:crypto.randomUUID(),text:event.text}:message):[...current,{id:crypto.randomUUID(),role:'user',text:event.text,time:'сейчас'}]});if(event.type==='assistant_chunk')setMessages(current=>{const last=current[current.length-1];return last?.id==='streaming'?current.map(message=>message.id==='streaming'?{...message,text:event.text}:message):[...current,{id:'streaming',role:'assistant',text:event.text,time:'сейчас'}]});if(event.type==='assistant_text')setMessages(current=>{const last=current[current.length-1];return last?.id==='streaming'?current.map(message=>message.id==='streaming'?{...message,id:crypto.randomUUID(),text:event.text}:message):[...current,{id:crypto.randomUUID(),role:'assistant',text:event.text,time:'сейчас'}]});if(event.type==='audio')void playback.enqueue({data:event.data,mime:event.mime,sampleRate:event.sampleRate,replyId:event.reply_id,index:event.index});if(event.type==='cancelled'){playback.clear();setMessages(current=>current.filter(message=>message.id!=='interim'))}});currentSocket.connect();return()=>{window.clearTimeout(retry);stopCapture()}},[])

  return {state,metrics,latency,facts,input,setInput,panel,setPanel,connected,messages,analyser,faceFrame,send,start,stop,submit,cancel}
}
