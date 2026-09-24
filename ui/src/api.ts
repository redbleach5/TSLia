import type {ServerEvent} from './types'

export class LiyaSocket {
  private socket?: WebSocket
  connect(){ if (this.socket?.readyState === WebSocket.OPEN) return; this.socket = new WebSocket('ws://127.0.0.1:8765'); }
  send(event: unknown){ if(this.socket?.readyState === WebSocket.OPEN) this.socket.send(JSON.stringify(event)) }
  onMessage(handler:(event:ServerEvent)=>void){ this.socket && (this.socket.onmessage = e => handler(JSON.parse(e.data))) }
  onOpen(handler:()=>void){ this.socket && (this.socket.onopen = handler) }
  close(){ this.socket?.close() }
}