<script setup lang="ts">
import { ref, reactive, onBeforeUnmount, computed } from 'vue'
import { api } from '@/api/index'
import AiMessageList from '@/components/ai/AiMessageList.vue'
import AiChatInput from '@/components/ai/AiChatInput.vue'
import { Bot, Zap, Shield, Search, AlertTriangle, X } from 'lucide-vue-next'

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

interface Session {
  id: number
  title: string
  created_at: string
}

interface ChatAttachmentPayload {
  name: string
  type: string
  size: number
  isImage: boolean
  textContent?: string
}

// 快捷输入选项
const quickPrompts = [
  { icon: Shield, label: '安全态势分析', text: '分析当前整体安全态势' },
  { icon: Search, label: '威胁情报查询', text: '查询最新威胁情报' },
  { icon: AlertTriangle, label: '高危IP处置', text: '列出需要处置的高危IP' },
  { icon: Zap, label: '一键应急响应', text: '启动应急响应流程' },
]

const messages = ref<Message[]>([])
const sessions = ref<Session[]>([])
const sending = ref(false)
const ttsEnabled = ref(true)
const activeChatController = ref<AbortController | null>(null)
const showHistory = ref(false)
const showSettings = ref(false)
const showQuickPrompts = ref(true)

// TTS设置
const settings = reactive({
  ttsEnabled: true,
  voiceSpeed: 1.0,
  autoAnalysis: false,
})

function speak(text: string) {
  if (!settings.ttsEnabled || !window.speechSynthesis) return
  const stripped = text.replace(/[#*`>~_\[\]()!]/g, ' ').replace(/\s+/g, ' ').trim()
  const utt = new SpeechSynthesisUtterance(stripped.slice(0, 400))
  utt.lang = 'zh-CN'
  utt.rate = settings.voiceSpeed
  window.speechSynthesis.speak(utt)
}

function stopGenerating() {
  activeChatController.value?.abort()
}

function toggleTts() {
  if (settings.ttsEnabled && window.speechSynthesis) {
    window.speechSynthesis.cancel()
  }
  settings.ttsEnabled = !settings.ttsEnabled
  ttsEnabled.value = settings.ttsEnabled
}

// 快捷输入选择
function selectQuickPrompt(text: string) {
  showQuickPrompts.value = false
  send(text)
}

// 历史记录
async function loadSessions() {
  try {
    const d = await api.get<any>('/api/v1/ai/sessions')
    sessions.value = d.data ?? d
  } catch (e) { console.error(e) }
}

async function loadHistorySession(sid: number) {
  if (sid < 0) {
    messages.value = []
    showHistory.value = false
    return
  }
  try {
    const d = await api.get<any>(`/api/v1/ai/sessions/${sid}/messages`)
    messages.value = (d.data ?? d).map((m: any) => ({
      role: m.role === 'tool' ? 'assistant' : m.role,
      content: m.content || '',
      created_at: m.created_at,
    }))
    showHistory.value = false
  } catch (e) { console.error(e) }
}

async function clearHistory() {
  messages.value = []
}

function composeTextWithAttachments(text: string, attachments: ChatAttachmentPayload[] = []): string {
  if (!attachments.length) return text

  const header = attachments
    .map((item, index) => `${index + 1}. ${item.name} (${item.type || 'unknown'}, ${Math.max(1, Math.ceil(item.size / 1024))}KB)`)
    .join('\n')

  const textParts = attachments
    .filter((item) => !item.isImage && item.textContent)
    .map((item) => `【文件内容：${item.name}】\n${item.textContent}`)
    .join('\n\n')

  const imageTips = attachments
    .filter((item) => item.isImage)
    .map((item) => `- ${item.name}`)
    .join('\n')

  const blocks = [
    text,
    `\n\n[已附加文件]\n${header}`,
  ]

  if (textParts) blocks.push(`\n\n${textParts}`)
  if (imageTips) blocks.push(`\n\n[已附加图片]\n${imageTips}\n请基于对话上下文给出处理建议。`)

  return blocks.join('')
}

async function send(text: string, extra: any = {}) {
  const attachmentFiles = (extra?.files || []) as File[]
  const attachments = (extra?.attachments || []) as ChatAttachmentPayload[]
  const baseText = (text || '').trim() || (attachmentFiles.length ? '请分析我上传的文件/图片。' : '')
  const composedText = composeTextWithAttachments(baseText, attachments)
  if (!composedText || sending.value) return
  messages.value.push({ role: 'user', content: composedText })
  sending.value = true
  const assistantMsg = reactive<Message>({ role: 'assistant', content: '', post_content: '' })
  messages.value.push(assistantMsg as any)

  const controller = new AbortController()
  activeChatController.value = controller

  try {
    const token = localStorage.getItem('token')
    const headers: Record<string, string> = {}
    if (token) headers['Authorization'] = `Bearer ${token}`

    let response: Response
    if (attachmentFiles.length) {
      const form = new FormData()
      form.append('message', baseText)
      form.append('context_type', 'dashboard')
      form.append('context_id', 'map')
      attachmentFiles.forEach((file) => form.append('files', file))
      response = await fetch('/api/v1/ai/chat/stream', {
        method: 'POST',
        headers,
        body: form,
        signal: controller.signal,
      })
    } else {
      headers['Content-Type'] = 'application/json'
      response = await fetch('/api/v1/ai/chat/stream', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          message: baseText,
          context_type: 'dashboard',
          context_id: 'map',
        }),
        signal: controller.signal,
      })
    }
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
  <div class="h-full flex flex-col bg-card/30 border border-border/60 rounded-lg overflow-hidden relative backdrop-blur-2xl">
    <!-- Header - 科技风设计 + 历史记录/设置按钮 -->
    <div class="flex items-center gap-3 px-3 py-2.5 border-b border-cyan-500/20 bg-gradient-to-r from-cyan-500/5 via-transparent to-cyan-500/5">
      <div class="relative">
        <div class="w-8 h-8 rounded bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center">
          <Bot class="h-4 w-4 text-cyan-400" />
        </div>
        <div class="absolute -bottom-0.5 -right-0.5 w-2 h-2 bg-green-500 rounded-full border border-background animate-pulse" />
      </div>
      <div class="flex-1 min-w-0">
        <h3 class="text-sm font-semibold text-foreground">AI 指挥中心</h3>
        <p class="text-[10px] text-cyan-400/70 font-mono">STATUS: ONLINE</p>
      </div>
    </div>

    <!-- 快捷输入选项 -->
    <div v-if="showQuickPrompts && messages.length === 0" class="px-3 py-2.5 border-b border-border/20 bg-gradient-to-r from-cyan-500/5 to-transparent">
      <p class="text-xs text-muted-foreground mb-2 font-medium">💡 快捷指令</p>
      <div class="grid grid-cols-2 gap-2">
        <button
          v-for="prompt in quickPrompts"
          :key="prompt.label"
          @click="selectQuickPrompt(prompt.text)"
          class="flex items-center gap-2 px-2.5 py-1.5 rounded-md bg-card/60 border border-border/40 hover:border-cyan-500/50 hover:bg-cyan-500/10 transition-all duration-200 text-left group"
        >
          <component :is="prompt.icon" class="w-4 h-4 text-cyan-400 group-hover:scale-110 transition-transform" />
          <span class="text-xs text-muted-foreground group-hover:text-foreground transition-colors">{{ prompt.label }}</span>
        </button>
      </div>
    </div>

    <!-- 历史记录面板 -->
    <div v-if="showHistory" class="absolute inset-0 z-20 bg-background/95 backdrop-blur-xl flex flex-col animate-in slide-in-from-right duration-300">
      <div class="flex items-center justify-between px-4 py-3 border-b border-cyan-500/20">
        <h3 class="text-sm font-semibold text-foreground">历史记录</h3>
        <button @click="showHistory = false" class="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-muted transition-colors">
          <X class="w-4 h-4 text-muted-foreground" />
        </button>
      </div>
      <div class="flex-1 overflow-y-auto p-3 space-y-2">
        <button
          @click="loadHistorySession(-1)"
          class="w-full px-3 py-2 rounded-lg text-left text-sm bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/20 transition-colors"
        >
          + 新对话
        </button>
        <button
          v-for="session in sessions"
          :key="session.id"
          @click="loadHistorySession(session.id)"
          class="w-full px-3 py-2 rounded-lg text-left text-sm bg-muted/30 border border-border/40 hover:bg-muted/50 hover:border-cyan-500/30 transition-colors"
        >
          <p class="text-foreground truncate">{{ session.title || '新对话' }}</p>
          <p class="text-[10px] text-muted-foreground mt-0.5">{{ session.created_at }}</p>
        </button>
      </div>
    </div>

    <!-- 设置面板 -->
    <div v-if="showSettings" class="absolute inset-0 z-20 bg-background/95 backdrop-blur-xl flex flex-col animate-in slide-in-from-right duration-300">
      <div class="flex items-center justify-between px-4 py-3 border-b border-cyan-500/20">
        <h3 class="text-sm font-semibold text-foreground">设置</h3>
        <button @click="showSettings = false" class="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-muted transition-colors">
          <X class="w-4 h-4 text-muted-foreground" />
        </button>
      </div>
      <div class="flex-1 overflow-y-auto p-4 space-y-4">
        <!-- TTS开关 -->
        <div class="flex items-center justify-between py-2 border-b border-border/40">
          <div>
            <p class="text-sm font-medium">语音播报 (TTS)</p>
            <p class="text-xs text-muted-foreground">自动朗读AI回复</p>
          </div>
          <button
            @click="settings.ttsEnabled = !settings.ttsEnabled; ttsEnabled = settings.ttsEnabled"
            class="relative w-12 h-6 rounded-full transition-colors duration-200"
            :class="settings.ttsEnabled ? 'bg-cyan-500' : 'bg-muted'"
          >
            <span
              class="absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200"
              :class="settings.ttsEnabled ? 'translate-x-7' : 'translate-x-1'"
            />
          </button>
        </div>
        <!-- 语速 -->
        <div class="py-2 border-b border-border/40">
          <div class="flex items-center justify-between mb-2">
            <p class="text-sm font-medium">语速</p>
            <span class="text-xs text-cyan-400">{{ settings.voiceSpeed.toFixed(1) }}x</span>
          </div>
          <input
            type="range"
            v-model.number="settings.voiceSpeed"
            min="0.5"
            max="2"
            step="0.1"
            class="w-full h-2 rounded-lg appearance-none cursor-pointer accent-cyan-500"
          />
        </div>
        <!-- 清空对话 -->
        <div class="pt-2">
          <button
            @click="clearHistory"
            class="w-full px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 transition-colors text-sm"
          >
            清空当前对话
          </button>
        </div>
      </div>
    </div>

    <!-- Message List -->
    <div class="flex-1 min-h-0 overflow-hidden">
      <AiMessageList :messages="messages" :loading="false" :sending="sending" />
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

<style scoped>
@keyframes animate-in {
  from { opacity: 0; transform: translateX(20px); }
  to { opacity: 1; transform: translateX(0); }
}
.animate-in {
  animation: animate-in 0.3s ease-out;
}
</style>
