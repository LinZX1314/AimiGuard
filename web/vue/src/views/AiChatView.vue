<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { api } from '@/api/index'
import { useRoute } from 'vue-router'
import AiSessionSidebar from '@/components/ai/AiSessionSidebar.vue'
import AiMessageList from '@/components/ai/AiMessageList.vue'
import AiChatInput from '@/components/ai/AiChatInput.vue'

interface ToolCall {
  id: string
  type?: string
  name?: string
  arguments?: Record<string, unknown>
  function?: {
    name?: string
    arguments?: string | Record<string, unknown>
  }
}

interface ApiMessage {
  role: 'user' | 'assistant' | 'tool'
  content: string
  created_at?: string
  name?: string
  tool_call_id?: string
  tool_calls?: ToolCall[]
}

interface ToolResult {
  content: string
  created_at?: string
  name?: string
  tool_call_id?: string
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  post_content?: string
  created_at?: string
  tool_calls?: ToolCall[]
  tool_results?: ToolResult[]
}

interface Session { id: number; title: string; created_at: string }

const sessions = ref<Session[]>([])
const messages = ref<Message[]>([])
const loading = ref(false)
const sending = ref(false)
const currentSession = ref<number | null>(null)
const activeChatController = ref<AbortController | null>(null)
const ttsEnabled = ref(true)
const route = useRoute()

// TTS logic
function speak(text: string) {
  if (!ttsEnabled.value || !window.speechSynthesis) return
  const stripped = text.replace(/[#*`>~_\[\]()!]/g, ' ').replace(/\s+/g, ' ').trim()
  const utt = new SpeechSynthesisUtterance(stripped.slice(0, 400))
  utt.lang = 'zh-CN'
  utt.rate = 1.1
  window.speechSynthesis.speak(utt)
}

function toggleTts() {
  if (ttsEnabled.value && window.speechSynthesis) {
    window.speechSynthesis.cancel()
  }
  ttsEnabled.value = !ttsEnabled.value
}

function stopGenerating() {
  activeChatController.value?.abort()
}

// Session Management
async function loadSessions() {
  try {
    const d = await api.get<any>('/api/v1/ai/sessions')
    const list = d.data ?? d
    sessions.value = list
  } catch(e) { console.error(e) }
}

async function loadMessages(sid: number) {
  if (sid === -1) {
    currentSession.value = -1
    messages.value = []
    loading.value = false
    return
  }
  loading.value = true
  currentSession.value = sid
  try {
    const d = await api.get<any>(`/api/v1/ai/sessions/${sid}/messages`)
    messages.value = normalizeMessages((d.data ?? d) as ApiMessage[])
  } catch(e) { console.error(e) }
  loading.value = false
}

async function deleteSession(sid: number) {
  try {
    await api.delete(`/api/v1/ai/sessions/${sid}`)
    if (currentSession.value === sid) { messages.value = []; currentSession.value = null }
    await loadSessions()
  } catch {}
}

function normalizeMessages(source: ApiMessage[], fallbackReply = ''): Message[] {
  const normalized: Message[] = []
  let index = 0
  while (index < source.length) {
    const current = source[index]
    if (current.role === 'user') {
      normalized.push({ role: 'user', content: current.content || '', created_at: current.created_at })
      index += 1
      continue
    }
    if (current.role === 'assistant' && current.tool_calls?.length) {
      const toolResults: ToolResult[] = []
      let content = current.content || ''
      let postContent = ''
      let createdAt = current.created_at
      let cursor = index + 1
      let seqIndex = 0
      while (cursor < source.length) {
        const next = source[cursor]
        if (next.role === 'tool') {
          let matchedCall = current.tool_calls?.find(tc => tc.id === next.tool_call_id)
          if (!matchedCall && seqIndex < current.tool_calls.length) matchedCall = current.tool_calls[seqIndex]
          const toolName = next.name || matchedCall?.name || (matchedCall as any)?.function?.name || 'unknown_tool'
          toolResults.push({ content: next.content || '', created_at: next.created_at, name: toolName, tool_call_id: next.tool_call_id || matchedCall?.id })
          seqIndex++; cursor += 1; continue
        }
        if (next.role === 'assistant' && !next.tool_calls?.length) {
          postContent = next.content || ''; createdAt = next.created_at || createdAt; cursor += 1
        }
        break
      }
      normalized.push({ role: 'assistant', content, post_content: postContent, created_at: createdAt, tool_calls: current.tool_calls, tool_results: toolResults })
      index = cursor; continue
    }
    if (current.role === 'assistant') {
      normalized.push({ role: 'assistant', content: current.content || fallbackReply, created_at: current.created_at })
      index += 1; continue
    }
    normalized.push({
      role: 'assistant', content: '', created_at: current.created_at,
      tool_results: [{ content: current.content || '', created_at: current.created_at, name: current.name, tool_call_id: current.tool_call_id }]
    })
    index += 1
  }
  if (!normalized.length && fallbackReply) normalized.push({ role: 'assistant', content: fallbackReply })
  return normalized
}

// Sending logic
async function send(text: string, extraParams: any = {}) {
  if (!text || sending.value) return
  messages.value.push({ role: 'user', content: text })
  sending.value = true
  const assistantMsg = reactive<Message>({ role: 'assistant', content: '', post_content: '' })
  messages.value.push(assistantMsg as any)

  const controller = new AbortController()
  activeChatController.value = controller

  try {
    const body: any = { message: text, ...extraParams }
    if (currentSession.value && currentSession.value !== -1) body.session_id = currentSession.value

    const token = localStorage.getItem('token')
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`

    const response = await fetch('/api/v1/ai/chat/stream', {
      method: 'POST', headers, body: JSON.stringify(body), credentials: 'include', signal: controller.signal
    })
    if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`)

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let typeQueue = ''
    let typeInterval: any = null

    const startTypewriter = () => {
      if (typeInterval) return
      typeInterval = setInterval(() => {
        if (typeQueue.length > 0) {
          const popCount = Math.max(1, Math.ceil(typeQueue.length / 15))
          const hasTools = (assistantMsg as any).tool_calls?.length > 0 || (assistantMsg as any).tool_results?.length > 0
          if (hasTools) assistantMsg.post_content = (assistantMsg.post_content || '') + typeQueue.slice(0, popCount)
          else assistantMsg.content += typeQueue.slice(0, popCount)
          typeQueue = typeQueue.slice(popCount)
        } else {
          clearInterval(typeInterval); typeInterval = null
        }
      }, 30)
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data: ')) continue
        const data = trimmed.slice(6)
        if (data === '[DONE]') continue
        try {
          const parsed = JSON.parse(data)
          if (parsed.content) { typeQueue += parsed.content; startTypewriter() }
          if (parsed.tool_call) {
             if (typeQueue) {
               const hasTools = (assistantMsg as any).tool_calls?.length > 0
               if (hasTools) assistantMsg.post_content = (assistantMsg.post_content || '') + typeQueue
               else assistantMsg.content += typeQueue
               typeQueue = ''
             }
             if (!(assistantMsg as any).tool_calls) (assistantMsg as any).tool_calls = []
             ;(assistantMsg as any).tool_calls.push({ id: parsed.tool_call.name + '_' + Date.now(), name: parsed.tool_call.name, arguments: parsed.tool_call.arguments })
          }
          if (parsed.tool_result) {
            if (typeQueue) { assistantMsg.post_content = (assistantMsg.post_content || '') + typeQueue; typeQueue = '' }
            if (!(assistantMsg as any).tool_results) (assistantMsg as any).tool_results = []
            const matchedToolCall = parsed.tool_call_id ? (assistantMsg as any).tool_calls?.find((tc: any) => tc.id === parsed.tool_call_id) : (assistantMsg as any).tool_calls?.slice(-1)[0]
            ;(assistantMsg as any).tool_results.push({ name: matchedToolCall?.name || 'tool', tool_call_id: parsed.tool_call_id || matchedToolCall?.id, content: parsed.tool_result })
          }
          if (parsed.session_id && (!currentSession.value || currentSession.value === -1)) {
            currentSession.value = parsed.session_id
            await loadSessions()
          }
        } catch {}
      }
    }
    speak(assistantMsg.content)
  } catch(e: any) {
    if (e.name !== 'AbortError') assistantMsg.content = `错误：${e.message || '请求失败'}`
  } finally {
    sending.value = false; activeChatController.value = null
  }
}

function handleNewChat() {
  messages.value = []
  currentSession.value = -1
  sessions.value = [{ id: -1, title: '新对话', created_at: new Date().toLocaleString() }, ...sessions.value.filter(s => s.id !== -1)]
}

onMounted(async () => {
  await loadSessions()
  const { context_type, context_id, prompt } = route.query
  if (prompt) {
    await send(String(prompt), { context_type, context_id })
  } else if (context_type && context_id) {
    await send(`请帮我分析这个目标：${context_id}`, { context_type, context_id })
  }
})

onBeforeUnmount(() => {
  stopGenerating()
  if (window.speechSynthesis) window.speechSynthesis.cancel()
})
</script>

<template>
  <div class="flex h-[calc(100vh-64px)] bg-background/60 backdrop-blur-sm text-foreground overflow-hidden">
    <AiSessionSidebar
      :sessions="sessions"
      :current-session="currentSession"
      @new-chat="handleNewChat"
      @load-messages="loadMessages"
      @delete-session="deleteSession"
    />
    <main class="flex-1 bg-transparent flex flex-col relative w-full overflow-hidden">
      <AiMessageList :messages="messages" :loading="loading" />
      <AiChatInput
        :sending="sending"
        :tts-enabled="ttsEnabled"
        @send="send"
        @stop="stopGenerating"
        @toggle-tts="toggleTts"
      />
    </main>
  </div>
</template>
