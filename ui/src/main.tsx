import {useEffect,useRef,useState} from 'react'
import {createRoot} from 'react-dom/client'
import {LiyaSocket} from './api'
import type {Message,ServerEvent,State} from './types'
import {LiaAvatar} from './LiaAvatar'
import './styles.css'

const labels:Record<State,string>={idle:'Лия рядом',listening:'Слушаю тебя',thinking:'Думаю о твоём запросе',speaking:'Отвечаю тебе',error:'Нужна помощь'}
const quick=['Что ты умеешь?','Расскажи о себе','Составь план на день','Запомни это']

function App(){
 const [state,setState]=useState<State>('idle');const [input,setInput]=useState('');const [messages,setMessages]=useState<Message[]>([{id:'hi',role:'assistant',text:'Привет. Я Лия. Рада, что ты здесь.',time:'сейчас'}]);const [panel,setPanel]=useState(false);const [connected,setConnected]=useState(false);const socket=useRef(new LiyaSocket())
 const send=(event:unknown)=>{socket.current.connect();setTimeout(()=>socket.current.send(event),50)}
 useEffect(()=>{const s=socket.current;s.onOpen(()=>setConnected(true));s.onClose(()=>setConnected(false));s.onMessage((e:ServerEvent)=>{if(e.type==='state')setState(e.state);if(e.type==='transcript'&&e.text)setMessages(m=>[...m,{id:crypto.randomUUID(),role:'user',text:e.text,time:'сейчас'}]);if(e.type==='assistant_text')setMessages(m=>[...m,{id:crypto.randomUUID(),role:'assistant',text:e.text,time:'сейчас'}]);if(e.type==='error')setState('error')});s.connect();return()=>s.close()},[])
 const submit=(value=input)=>{const text=value.trim();if(!text)return;setMessages(m=>[...m,{id:crypto.randomUUID(),role:'user',text,time:'сейчас'}]);send({type:'text',text});setInput('')}
 return <main className={`companion ${state}`}>
  <header className="topbar"><div className="wordmark"><span className="wordmark-dot"/>ли<span>я</span></div><div className="top-center">{connected?'● локальная связь':'○ ожидает runtime'}</div><div className="top-actions"><button onClick={()=>setPanel(!panel)}>☰</button><button>⚙</button><div className="avatar">Я</div></div></header>
  <section className="stage"><div className="stage-glow"/><LiaAvatar state={state}/><div className="character-shadow"/><div className="stage-caption"><div className="caption-kicker">ЛИЯ</div><h1>{labels[state]}</h1><p>{state==='listening'?'Говори свободно — я пойму тебя':state==='thinking'?'Собираю мысли в слова':'Я всегда готова выслушать'}</p></div></section>
  <section className="conversation"><div className="conversation-line"><span>Ваш разговор</span><button onClick={()=>setMessages(m=>m.slice(-1))}>Очистить</button></div><div className="message-stack">{messages.slice(-4).map(m=><article className={`message ${m.role}`} key={m.id}><span className="speaker">{m.role==='user'?'вы':'лия'}</span><p>{m.text}</p><time>{m.time}</time></article>)}</div><div className="quick-row">{quick.map(q=><button key={q} onClick={()=>submit(q)}>{q}<span>↗</span></button>)}</div><form onSubmit={e=>{e.preventDefault();submit()}}><button type="button" onMouseDown={()=>send({type:'start_listening'})} onMouseUp={()=>send({type:'stop_listening'})} className="voice-button">◉</button><input value={input} onChange={e=>setInput(e.target.value)} placeholder="Скажи что-нибудь или напиши…"/><button className="send" type="submit">↑</button></form></section>
  {panel&&<aside className="drawer"><div className="drawer-head"><b>Лия</b><button onClick={()=>setPanel(false)}>×</button></div><p>Твой локальный компаньон. Всё, что ты говоришь, остаётся на этом устройстве.</p><div className="drawer-item"><span>Настроение</span><b>Спокойная и внимательная</b></div><div className="drawer-item"><span>Память</span><b>Только то, что разрешишь</b></div><div className="drawer-item"><span>Голос</span><b>Локальный · готов к подключению</b></div><div className="drawer-foot">Esc · закрыть</div></aside>}
  <footer className="footer"><span>⌘ K быстрые команды</span><span>Лия v0.1 · локальный режим</span><span>Ничего лишнего</span></footer>
 </main>
}
createRoot(document.getElementById('root')!).render(<App/>)