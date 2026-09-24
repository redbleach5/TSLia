import type {ServerEvent} from './types'

type Handler<T> = (value: T) => void

export class LiyaSocket {
  private socket?: WebSocket
  private messageHandler?: Handler<ServerEvent>
  private openHandler?: Handler<void>
  private closeHandler?: Handler<void>
  private queue: string[] = []

  connect() {
    if (this.socket?.readyState === WebSocket.OPEN || this.socket?.readyState === WebSocket.CONNECTING) return
    this.socket = new WebSocket('ws://127.0.0.1:8765')
    this.socket.onopen = () => { this.openHandler?.(); while (this.queue.length) this.socket?.send(this.queue.shift()!) }
    this.socket.onmessage = event => {
      try { this.messageHandler?.(JSON.parse(event.data) as ServerEvent) } catch { /* ignore malformed runtime event */ }
    }
    this.socket.onclose = () => this.closeHandler?.()
  }

  send(event: unknown) {
    const payload = JSON.stringify(event)
    if (this.socket?.readyState === WebSocket.OPEN) this.socket.send(payload)
    else { this.queue.push(payload); this.connect() }
  }

  onMessage(handler: Handler<ServerEvent>) { this.messageHandler = handler; if (this.socket) this.socket.onmessage = event => { try { handler(JSON.parse(event.data) as ServerEvent) } catch { /* ignore */ } } }
  onOpen(handler: Handler<void>) { this.openHandler = handler; if (this.socket) this.socket.onopen = () => handler() }
  onClose(handler: Handler<void>) { this.closeHandler = handler; if (this.socket) this.socket.onclose = () => handler() }
  close() { this.socket?.close() }
}