import { apiClient } from './client'

export interface ChatResponse {
  session_id: number
  message: string
  context?: { type: string | null; id: string | null }
}

export interface SessionMessage {
  role: string
  content: string
  created_at: string
}

export interface ChatSession {
  id: number
  context_type: string | null
  context_id: number | null
  operator: string
  started_at: string
  expires_at: string | null
}

export const aiApi = {
  async chat(
    message: string,
    sessionId?: number | null,
    context?: { type: string; id: string },
  ): Promise<ChatResponse> {
    const res = await apiClient.post('/ai/chat', {
      message,
      session_id: sessionId ?? undefined,
      context_type: context?.type,
      context_id: context?.id,
    })
    // interceptor 解包后 res = data 字段内容
    return res as unknown as ChatResponse
  },

  async getSessions(): Promise<ChatSession[]> {
    const res = await apiClient.get('/ai/sessions')
    return (Array.isArray(res) ? res : (res as any)?.data ?? []) as ChatSession[]
  },

  async getSessionMessages(sessionId: number): Promise<SessionMessage[]> {
    const res = await apiClient.get(`/ai/sessions/${sessionId}/messages`)
    return (Array.isArray(res) ? res : (res as any) ?? []) as SessionMessage[]
  },

  async deleteSession(sessionId: number): Promise<void> {
    await apiClient.delete(`/ai/sessions/${sessionId}`)
  },
}
