import type {ServerEvent} from './types'

type Handler<T> = (value: T) => void

export class LiyaSocket {
  private socket?: WebSocket
  private messageHandler?: Handler<ServerEvent>
  private openHandler?: Handler<void>
  private closeHandler?: Handler<void>

  connect() {
    if (this.socket?.readyState === WebSocket.OPEN || this.socket?.readyState === WebSocket.CONNECTING) return
    this.socket = new WebSocket('ws://127.0.0.1:8765')
    this.socket.onopen = () => this.openHandler?.()
    this.socket.onmessage = event => {
      try { this.messageHandler?.(JSON.parse(event.data) as ServerEvent) } catch { /* ignore malformed runtime event */ }
    }
    this.socket.onclose = () => this.closeHandler?.()
  }

  send(event: unknown) {
    if (this.socket?.readyState === WebSocket.OPEN) this.socket.send(JSON.stringify(event))
  }

  onMessage(handler: Handler<ServerEvent>) { this.messageHandler = handler; if (this.socket) this.socket.onmessage = event => { try { handler(JSON.parse(event.data) as ServerEvent) } catch { /* ignore */ } } }
  onOpen(handler: Handler<void>) { this.openHandler = handler; if (this.socket) this.socket.onopen = () => handler() }
  onClose(handler: Handler<void>) { this.closeHandler = handler; if (this.socket) this.socket.onclose = () => handler() }
  close() { this.socket?.close() }
}