import {useEffect,useRef,useState} from 'react'
import {createRoot} from 'react-dom/client'
import {LiyaSocket} from './api'
import type {Message,ServerEvent,State} from './types'
import './styles.css'

const stateLabels:Record<State,string>={idle:'Готова к разговору',listening:'Слушаю',thinking:'Думаю',speaking:'Говорю',error:'Нужна помощь'}
function App(){
 const [state,setState]=useState<State>('idle'); const [input,setInput]=useState(''); const [messages,setMessages]=useState<Message[]>([{id:'welcome',role:'assistant',text:'Привет. Я Лия. Что будем делать?',time:'сейчас'}]); const [connected,setConnected]=useState(false); const socket=useRef(new LiyaSocket())
 const send=(event:unknown)=>{socket.current.connect(); socket.current.send(event)}
 useEffect(()=>{const s=socket.current; s.onOpen(()=>setConnected(true)); s.onMessage((e:ServerEvent)=>{if(e.type==='state')setState(e.state); if(e.type==='transcript'&&e.text)setMessages(m=>[...m,{id:crypto.randomUUID(),role:'user',text:e.text,time:'сейчас'}]); if(e.type==='assistant_text'||e.type==='message'&&e.role==='assistant')setMessages(m=>[...m,{id:crypto.randomUUID(),role:'assistant',text:e.type==='assistant_text'?e.text:e.text,time:'сейчас'}]); if(e.type==='error')setState('error')}); s.connect(); return ()=>s.close()},[])
 const submit=()=>{const text=input.trim();if(!text)return;setMessages(m=>[...m,{id:crypto.randomUUID(),role:'user',text,time:'сейчас'}]);send({type:'text',text});setInput('')}
 return <main className="shell"><header><div className="brand"><div className="orb"><span /></div><div><b>Лия</b><small>локальный компаньон</small></div></div><div className="status"><i className={connected?'dot online':'dot'} />{connected?'runtime подключён':'runtime не подключён'}</div></header><section className="hero"><div className="halo"/><div className="voice-core"><div className="ring"/><div className="face">✦</div></div><h1>{stateLabels[state]}</h1><p>Нажмите и говорите, или напишите сообщение</p><button className="talk" onMouseDown={()=>send({type:'start_listening'})} onMouseUp={()=>send({type:'stop_listening'})}><span>●</span>{state==='listening'?'Слушаю…':'Говорить'}</button></section><section className="messages">{messages.map(m=><article className={m.role} key={m.id}><small>{m.role==='user'?'Вы':'Лия'} · {m.time}</small><p>{m.text}</p></article>)}</section><form onSubmit={e=>{e.preventDefault();submit()}}><input value={input} onChange={e=>setInput(e.target.value)} placeholder="Напишите Лии…" /><button type="submit">Отправить</button></form></main>
}
createRoot(document.getElementById('root')!).render(<App/>)