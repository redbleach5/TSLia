import {useEffect,useRef} from 'react'

type AudioChunk = {data:string; mime:string; sampleRate?:number; replyId?:string; index?:number}

export class AudioPlaybackQueue {
  private context?: AudioContext
  private analyser?: AnalyserNode
  private nextAt = 0
  private generation = 0
  private sources = new Set<AudioBufferSourceNode>()
  private buffers: AudioBuffer[] = []
  private replyId?: string

  constructor(private readonly onAnalyser?: (analyser: AnalyserNode) => void) {}

  private ensureContext() {
    if (!this.context) {
      this.context = new AudioContext()
      this.analyser = this.context.createAnalyser()
      this.analyser.fftSize = 256
      this.analyser.connect(this.context.destination)
      this.onAnalyser?.(this.analyser)
    }
    return this.context
  }

  get analyserNode() { this.ensureContext(); return this.analyser }

  async enqueue(chunk: AudioChunk) {
    const context = this.ensureContext()
    if (context.state === 'suspended') await context.resume()
    if (chunk.replyId && chunk.replyId !== this.replyId) this.clear()
    if (chunk.replyId) this.replyId = chunk.replyId
    const index = chunk.index ?? this.buffers.length
    while (this.buffers.length < index) this.buffers.push(undefined as never)
    const bytes = Uint8Array.from(atob(chunk.data), c => c.charCodeAt(0))
    const buffer = await context.decodeAudioData(bytes.buffer)
    this.buffers[index] = buffer
    if (this.nextAt < context.currentTime) this.nextAt = context.currentTime
    if (index === 0) this.schedule(index)
  }

  private schedule(index: number) {
    const context = this.ensureContext()
    if (!this.context || !this.buffers[index]) return
    if (this.sources.size && index !== 0 && !this.buffers[index - 1]) return
    const source = context.createBufferSource()
    source.buffer = this.buffers[index]
    source.connect(this.analyser!)
    source.onended = () => {
      this.sources.delete(source)
      this.buffers[index] = undefined as never
      this.schedule(index + 1)
    }
    source.start(this.nextAt)
    this.nextAt += source.buffer.duration
    this.sources.add(source)
  }

  clear() {
    this.generation += 1
    for (const source of this.sources) { try { source.stop() } catch {} }
    this.sources.clear()
    this.buffers = []
    this.nextAt = this.context?.currentTime ?? 0
  }

  close() { this.clear(); void this.context?.close(); this.context = undefined }
}

export function useAudioPlaybackQueue(onAnalyser?: (analyser: AnalyserNode) => void) {
  const queue = useRef<AudioPlaybackQueue | null>(null)
  if (!queue.current) queue.current = new AudioPlaybackQueue(onAnalyser)
  useEffect(() => () => queue.current?.close(), [])
  return queue.current
}
