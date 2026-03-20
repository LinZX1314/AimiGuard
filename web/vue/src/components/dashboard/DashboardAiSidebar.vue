<script setup lang="ts">
import { ref, reactive, onBeforeUnmount } from 'vue'
import { api } from '@/api/index'
import AiMessageList from '@/components/ai/AiMessageList.vue'
import AiChatInput from '@/components/ai/AiChatInput.vue'
import { Bot } from 'lucide-vue-next'

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

const messages = ref<Message[]>([])
const sending = ref(false)
const ttsEnabled = ref(true)
const activeChatController = ref<AbortController | null>(null)

function speak(text: string) {
  if (!ttsEnabled.value || !window.speechSynthesis) return
  const stripped = text.replace(/[#*`>~_\[\]()!]/g, ' ').replace(/\s+/g, ' ').trim()
  const utt = new SpeechSynthesisUtterance(stripped.slice(0, 400))
  utt.lang = 'zh-CN'
  utt.rate = 1.1
  window.speechSynthesis.speak(utt)
}

function stopGenerating() {
  activeChatController.value?.abort()
}

function toggleTts() {
  if (ttsEnabled.value && window.speechSynthesis) {
    window.speechSynthesis.cancel()
  }
  ttsEnabled.value = !ttsEnabled.value
}

async function send(text: string) {
  if (!text || sending.value) return
  messages.value.push({ role: 'user', content: text })
  sending.value = true
  const assistantMsg = reactive<Message>({ role: 'assistant', content: '', post_content: '' })
  messages.value.push(assistantMsg as any)

  const controller = new AbortController()
  activeChatController.value = controller

  try {
    const token = localStorage.getItem('token')
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`

    const response = await fetch('/api/v1/ai/chat/stream', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        message: text,
        context_type: 'dashboard',
        context_id: 'map',
      }),
      signal: controller.signal,
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

onBeforeUnmount(() => {
  stopGenerating()
  if (window.speechSynthesis) window.speechSynthesis.cancel()
})
</script>

<template>
  <div class="h-full flex flex-col bg-card/30 border border-border/60 rounded-xl overflow-hidden relative backdrop-blur-2xl">
    <!-- Header -->
    <div class="flex items-center gap-2 px-4 py-3 border-b border-border/40">
      <Bot class="h-4 w-4 text-primary" />
      <span class="text-sm font-semibold">AI 指挥中心</span>
    </div>

    <!-- Message List -->
    <div class="flex-1 min-h-0 overflow-hidden">
      <AiMessageList :messages="messages" :loading="false" />
    </div>

    <!-- Input -->
    <AiChatInput
      :sending="sending"
      :tts-enabled="ttsEnabled"
      @send="send"
      @stop="stopGenerating"
      @toggle-tts="toggleTts"
    />
  </div>
</template>
