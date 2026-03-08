import { buildApiUrl } from './client'

export interface RealtimeEvent<T = Record<string, unknown>> {
  type: string
  channel?: string
  reason?: string
  trace_id?: string
  timestamp?: string
  data?: T
}

interface RealtimeChannelOptions {
  onEvent?: (event: RealtimeEvent) => void
  onConnectionChange?: (connected: boolean) => void
  autoReconnect?: boolean
  reconnectDelayMs?: number
}

const toWebSocketUrl = (path: string): string => {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const url = new URL(buildApiUrl(normalizedPath), window.location.origin)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'

  const token = window.localStorage.getItem('access_token') || ''
  if (token) {
    url.searchParams.set('token', token)
  }

  return url.toString()
}

export class RealtimeChannel {
  private readonly path: string
  private readonly onEvent?: (event: RealtimeEvent) => void
  private readonly onConnectionChange?: (connected: boolean) => void
  private readonly autoReconnect: boolean
  private readonly reconnectDelayMs: number
  private reconnectTimer: number | null = null
  private closedManually = false
  private ws: WebSocket | null = null

  constructor(path: string, options: RealtimeChannelOptions = {}) {
    this.path = path
    this.onEvent = options.onEvent
    this.onConnectionChange = options.onConnectionChange
    this.autoReconnect = options.autoReconnect ?? true
    this.reconnectDelayMs = options.reconnectDelayMs ?? 2000
  }

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return
    }

    this.closedManually = false
    const socket = new WebSocket(toWebSocketUrl(this.path))
    this.ws = socket

    socket.onopen = () => {
      if (this.ws !== socket) return
      this.onConnectionChange?.(true)
    }

    socket.onmessage = (message) => {
      if (this.ws !== socket) return
      try {
        const event = JSON.parse(message.data) as RealtimeEvent
        this.onEvent?.(event)
      } catch {
        return
      }
    }

    socket.onclose = () => {
      if (this.ws === socket) {
        this.ws = null
      }
      this.onConnectionChange?.(false)
      if (!this.closedManually && this.autoReconnect) {
        this.scheduleReconnect()
      }
    }

    socket.onerror = () => {
      this.onConnectionChange?.(false)
    }
  }

  close() {
    this.closedManually = true
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      try {
        this.ws.close()
      } catch {
        return
      } finally {
        this.ws = null
      }
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer)
    }
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null
      this.connect()
    }, this.reconnectDelayMs)
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}
