/**
 * Streaming Speech-to-Text API via WebSocket.
 *
 * Connects to backend WS endpoint, sends binary audio frames,
 * and receives partial/final transcription events.
 */

export interface STTEvent {
  type: 'ready' | 'partial' | 'final' | 'error'
  text?: string
  is_final?: boolean
  session_id?: string
  detail?: string
}

export type STTEventHandler = (event: STTEvent) => void

export class STTStream {
  private ws: WebSocket | null = null
  private onEvent: STTEventHandler

  constructor(onEvent: STTEventHandler) {
    this.onEvent = onEvent
  }

  /** Open WebSocket connection to STT streaming endpoint. */
  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const token = localStorage.getItem('access_token') || ''
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      const url = `${protocol}//${host}/api/v1/stt/stream?token=${encodeURIComponent(token)}`

      this.ws = new WebSocket(url)
      this.ws.binaryType = 'arraybuffer'

      this.ws.onopen = () => resolve()

      this.ws.onmessage = (msg) => {
        try {
          const event: STTEvent = JSON.parse(msg.data)
          this.onEvent(event)
        } catch { /* ignore non-json */ }
      }

      this.ws.onerror = () => {
        this.onEvent({ type: 'error', detail: 'ws_connection_error' })
        reject(new Error('WebSocket connection failed'))
      }

      this.ws.onclose = () => {
        this.ws = null
      }
    })
  }

  /** Send an audio chunk (binary) to the server. */
  sendAudio(data: ArrayBuffer | Uint8Array) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(data)
    }
  }

  /** Signal stop recording and request final transcription. */
  stop() {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send('stop')
    }
  }

  /** Close the WebSocket connection. */
  close() {
    if (this.ws) {
      try { this.ws.close() } catch { /* ignore */ }
      this.ws = null
    }
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}
