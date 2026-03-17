<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { api } from '@/api/index'
import {
  MessageSquare,
  Plus,
  Trash2,
  Bot,
  Wrench,
  CheckCircle2,
  ChevronDown,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Send,
  Square,
  User,
  History,
  Settings,
  X
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { Textarea } from '@/components/ui/textarea'

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
const input    = ref('')
const loading  = ref(false)
const sending  = ref(false)
const currentSession = ref<number | null>(null)
const chatBox  = ref<HTMLElement | null>(null)
const chatEnd = ref<HTMLElement | null>(null)
const activeChatController = ref<AbortController | null>(null)

// STT ------------------------------------------------------------------------
const listening = ref(false)
const voiceDialog = ref(false)
const voiceError = ref('')
const voiceDraft = ref('')
const voiceInterim = ref('')
const waveformBars = ref<number[]>(Array.from({ length: 28 }, (_, index) => 0.12 + (index % 5) * 0.018))

let recognition: any = null
let mediaStream: MediaStream | null = null
let audioContext: AudioContext | null = null
let analyser: AnalyserNode | null = null
let sourceNode: MediaStreamAudioSourceNode | null = null
let frequencyData: Uint8Array<ArrayBuffer> = new Uint8Array(0)
let animationFrameId: number | null = null

const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
const voiceSupported = computed(() => Boolean(SpeechRecognition && navigator.mediaDevices?.getUserMedia))
const voiceTranscript = computed(() => [voiceDraft.value, voiceInterim.value].filter(Boolean).join(' ').trim())
const canApplyVoice = computed(() => Boolean(voiceTranscript.value))

function resetWaveform() {
  waveformBars.value = Array.from({ length: 28 }, (_, index) => 0.12 + (index % 5) * 0.018)
}

function stopWaveform() {
  if (animationFrameId !== null) {
    window.cancelAnimationFrame(animationFrameId)
    animationFrameId = null
  }
  if (sourceNode) {
    sourceNode.disconnect()
    sourceNode = null
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach(track => track.stop())
    mediaStream = null
  }
  if (audioContext) {
    void audioContext.close()
    audioContext = null
  }
  analyser = null
  frequencyData = new Uint8Array(0)
  resetWaveform()
}

function stopSpeechRecognition() {
  if (!recognition) return
  try {
    recognition.stop()
  } catch {}
  listening.value = false
}

function cleanupVoiceCapture() {
  stopSpeechRecognition()
  stopWaveform()
  voiceInterim.value = ''
}

function renderWaveformFrame() {
  if (!analyser || !frequencyData) return

  if (frequencyData) analyser.getByteFrequencyData(frequencyData as any)
  const bucketSize = Math.max(1, Math.floor(frequencyData.length / waveformBars.value.length))

  waveformBars.value = waveformBars.value.map((_, index) => {
    const start = index * bucketSize
    const end = index === waveformBars.value.length - 1 ? frequencyData!.length : Math.min(frequencyData!.length, start + bucketSize)
    let total = 0

    for (let i = start; i < end; i += 1) total += frequencyData![i]

    const average = total / Math.max(1, end - start)
    return Number((0.12 + Math.min(1, Math.max(0.04, average / 255)) * 1.18).toFixed(3))
  })

  animationFrameId = window.requestAnimationFrame(renderWaveformFrame)
}

async function startWaveform() {
  stopWaveform()
  const AudioContextClass = (window as any).AudioContext || (window as any).webkitAudioContext

  if (!AudioContextClass || !navigator.mediaDevices?.getUserMedia) {
    voiceError.value = '当前浏览器不支持麦克风实时波形。'
    return
  }

  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    })
    audioContext = new AudioContextClass()
    if (audioContext?.state === 'suspended') await audioContext.resume()
    if (!audioContext) return

    analyser = audioContext.createAnalyser()
    analyser.fftSize = 256
    analyser.smoothingTimeConstant = 0.82
    sourceNode = audioContext.createMediaStreamSource(mediaStream)
    if (sourceNode && analyser) {
      sourceNode.connect(analyser)
      frequencyData = new Uint8Array(analyser.frequencyBinCount)
      renderWaveformFrame()
    }
  } catch (error) {
    console.error('初始化麦克风波形失败:', error)
    voiceError.value = '无法访问麦克风，请确认浏览器权限已开启。'
    resetWaveform()
  }
}

if (SpeechRecognition) {
  recognition = new SpeechRecognition()
  recognition.lang = 'zh-CN'
  recognition.continuous = true
  recognition.interimResults = true
  recognition.maxAlternatives = 1

  recognition.onresult = (event: any) => {
    let finalText = ''
    let interimText = ''

    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const result = event.results[index]
      const transcript = result?.[0]?.transcript?.trim() || ''
      if (!transcript) continue

      if (result.isFinal) finalText += ` ${transcript}`
      else interimText += ` ${transcript}`
    }

    if (finalText.trim()) {
      voiceDraft.value = [voiceDraft.value, finalText.trim()].filter(Boolean).join(' ').trim()
    }
    voiceInterim.value = interimText.trim()
  }

  recognition.onerror = (event: any) => {
    console.error('语音识别失败:', event)
    listening.value = false
    stopWaveform()
    voiceError.value = event?.error === 'not-allowed' || event?.error === 'service-not-allowed'
      ? '麦克风权限被拒绝，请在浏览器设置中允许访问。'
      : `语音识别不可用：${event?.error || '未知错误'}`
  }

  recognition.onend = () => {
    listening.value = false
    stopWaveform()
  }
}

function startSpeechRecognition() {
  if (!recognition) {
    voiceError.value = '当前浏览器不支持语音识别'
    return
  }

  voiceError.value = ''
  voiceInterim.value = ''

  try {
    recognition.start()
    listening.value = true
  } catch (error) {
    console.error('启动语音识别失败:', error)
    voiceError.value = '启动语音识别失败，请稍后重试。'
    listening.value = false
  }
}

async function openVoiceDialog() {
  if (!voiceSupported.value) return
  voiceDialog.value = true
  voiceError.value = ''
  voiceDraft.value = ''
  voiceInterim.value = ''
  resetWaveform()
  await startWaveform()
  startSpeechRecognition()
}

async function restartVoiceInput() {
  voiceError.value = ''
  voiceDraft.value = ''
  voiceInterim.value = ''
  stopSpeechRecognition()
  await startWaveform()
  startSpeechRecognition()
}

function closeVoiceDialog() {
  voiceDialog.value = false
}

function stopVoiceInput() {
  cleanupVoiceCapture()
}

function applyVoiceTranscript() {
  if (!voiceTranscript.value) return
  input.value = [input.value, voiceTranscript.value].filter(Boolean).join(' ').trim()
  voiceDialog.value = false
}

watch(voiceDialog, (open) => {
  if (!open) cleanupVoiceCapture()
})

function toggleListen() {
  if (!recognition) return
  if (listening.value) {
    stopVoiceInput()
  } else {
    startSpeechRecognition()
  }
}


// TTS ------------------------------------------------------------------------
const ttsEnabled = ref(true)
function speak(text: string) {
  if (!ttsEnabled.value || !window.speechSynthesis) return
  const stripped = text.replace(/[#*`>~_\[\]()!]/g, ' ').replace(/\s+/g, ' ').trim()
  const utt = new SpeechSynthesisUtterance(stripped.slice(0, 400))
  utt.lang = 'zh-CN'
  utt.rate = 1.1
  window.speechSynthesis.speak(utt)
}


function toggleTts() {
  // 切换 TTS 状态时，停止当前正在播放的语音
  if (ttsEnabled.value && window.speechSynthesis) {
    window.speechSynthesis.cancel()
  }
  ttsEnabled.value = !ttsEnabled.value
}

function stopGenerating() {
  activeChatController.value?.abort()
}

// Markdown -------------------------------------------------------------------
function renderMd(text: string): string {
  const rawHtml = marked.parse(text, { breaks: true, gfm: true }) as string
  // 对 marked 渲染结果进行清洗，防止 XSS 注入
  const safeHtml = DOMPurify.sanitize(rawHtml, {
    ADD_ATTR: ['target'],
    ADD_TAGS: ['details', 'summary']
  })
  return safeHtml.replace(/<a /g, '<a target="_blank" rel="noopener noreferrer" ')
}

function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value ?? '')
  }
}

function formatToolResult(content: string): string {
  if (!content) return ''
  try {
    return JSON.stringify(JSON.parse(content), null, 2)
  } catch {
    return content
  }
}

function normalizeMessages(source: ApiMessage[], fallbackReply = ''): Message[] {
  const normalized: Message[] = []
  let index = 0

  while (index < source.length) {
    const current = source[index]

    if (current.role === 'user') {
      normalized.push({
        role: 'user',
        content: current.content || '',
        created_at: current.created_at
      })
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
          // 优先按 tool_call_id 匹配，缺失时按顺序回退
          let matchedCall = current.tool_calls?.find(tc => tc.id === next.tool_call_id)
          if (!matchedCall && seqIndex < current.tool_calls.length) {
            matchedCall = current.tool_calls[seqIndex]
          }
          const toolName = next.name || matchedCall?.name || (matchedCall as any)?.function?.name || 'unknown_tool'
          const toolId = next.tool_call_id || matchedCall?.id
          
          toolResults.push({
            content: next.content || '',
            created_at: next.created_at,
            name: toolName,
            tool_call_id: toolId
          })
          seqIndex++
          cursor += 1
          continue
        }
        if (next.role === 'assistant' && !next.tool_calls?.length) {
          postContent = next.content || ''
          createdAt = next.created_at || createdAt
          cursor += 1
        }
        break
      }

      normalized.push({
        role: 'assistant',
        content: content,
        post_content: postContent,
        created_at: createdAt,
        tool_calls: current.tool_calls,
        tool_results: toolResults
      })
      index = cursor
      continue
    }

    if (current.role === 'assistant') {
      normalized.push({
        role: 'assistant',
        content: current.content || fallbackReply,
        created_at: current.created_at
      })
      index += 1
      continue
    }

    normalized.push({
      role: 'assistant',
      content: '',
      created_at: current.created_at,
      tool_results: [{
        content: current.content || '',
        created_at: current.created_at,
        name: current.name,
        tool_call_id: current.tool_call_id
      }]
    })
    index += 1
  }

  if (!normalized.length && fallbackReply) {
    normalized.push({ role: 'assistant', content: fallbackReply })
  }

  return normalized
}

function messageKey(message: Message, index: number): string {
  return `${message.role}-${message.created_at || 'no-ts'}-${index}`
}

function toolResultKey(parentKey: string, result: ToolResult, index: number): string {
  return `${parentKey}-tool-${result.tool_call_id || result.name || index}`
}

watch(messages, async () => {
  await nextTick()
  scrollBottom()
}, { deep: true })

async function loadSessions() {
  try {
    const d = await api.get<any>('/api/v1/ai/sessions')
    const list = d.data ?? d

    if (currentSession.value === -1) {
      sessions.value = [
        { id: -1, title: '新对话', created_at: new Date().toLocaleString() },
        ...list 
      ]
    } else {
      sessions.value = list
    }
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
    await nextTick(); scrollBottom()
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

async function send(extraParams: any = {}) {
  const text = input.value.trim()
  if (!text || sending.value) return
  input.value = ''
  const userMsg = { role: 'user' as const, content: text }
  messages.value.push(userMsg as any)
  await nextTick()
  scrollBottom()

  sending.value = true

  // 使用 reactive 包装，确保深层字段改动能触发响应式更新
  const assistantMsg = reactive<Message>({ role: 'assistant', content: '', post_content: '' })
  messages.value.push(assistantMsg as any)
  await nextTick(); scrollBottom()

  const controller = new AbortController()
  activeChatController.value = controller

  try {
    const body: any = { message: text, ...extraParams }
    if (currentSession.value && currentSession.value !== -1) {
      body.session_id = currentSession.value
    }

    const token = localStorage.getItem('token')
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`

    const response = await fetch('/api/v1/ai/chat/stream', {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      credentials: 'include',
      signal: controller.signal
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) {
      throw new Error('无法读取响应')
    }

    let isNewSession = !currentSession.value || currentSession.value === -1
    let sessionId = currentSession.value === -1 ? null : currentSession.value
    let buffer = '' // 分块缓冲区
    
    // 打字机效果队列
    let typeQueue = ''
    let typeInterval: any = null

    const startTypewriter = () => {
      if (typeInterval) return
      typeInterval = setInterval(() => {
        if (typeQueue.length > 0) {
          // 根据队列长度动态提速，避免长文本明显滞后
          const popCount = Math.max(1, Math.ceil(typeQueue.length / 15))
          const hasTools = (assistantMsg as any).tool_calls?.length > 0 || (assistantMsg as any).tool_results?.length > 0
          if (hasTools) {
            assistantMsg.post_content = (assistantMsg.post_content || '') + typeQueue.slice(0, popCount)
          } else {
            assistantMsg.content += typeQueue.slice(0, popCount)
          }
          typeQueue = typeQueue.slice(popCount)
          nextTick(() => scrollBottom())
        }
      }, 30) // 30ms 刷新频率，兼顾流畅与性能
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      
      // 最后一行可能是不完整数据，留待下轮拼接
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || !trimmed.startsWith('data: ')) continue
        
        const data = trimmed.slice(6)
        if (data === '[DONE]') continue
        
        try {
          const parsed = JSON.parse(data)
          if (parsed.content) {
            typeQueue += parsed.content
            startTypewriter()
          }
          // 工具调用事件
          if (parsed.tool_call) {
            if (typeQueue) {
              const hasTools = (assistantMsg as any).tool_calls?.length > 0
              if (hasTools) {
                assistantMsg.post_content = (assistantMsg.post_content || '') + typeQueue
              } else {
                assistantMsg.content += typeQueue
              }
              typeQueue = ''
            }
            if (!(assistantMsg as any).tool_calls) (assistantMsg as any).tool_calls = []
            ;(assistantMsg as any).tool_calls.push({
              id: parsed.tool_call.name + '_' + Date.now(),
              name: parsed.tool_call.name,
              arguments: parsed.tool_call.arguments,
            })
            nextTick(() => scrollBottom())
          }
          // 工具执行结果事件
          if (parsed.tool_result) {
            if (typeQueue) {
              assistantMsg.post_content = (assistantMsg.post_content || '') + typeQueue
              typeQueue = ''
            }
            if (!(assistantMsg as any).tool_results) (assistantMsg as any).tool_results = []
            // 优先用后端返回的 tool_call_id 匹配，否则回退到最后一个 tool_call
            const matchedToolCall = parsed.tool_call_id
              ? (assistantMsg as any).tool_calls?.find((tc: any) => tc.id === parsed.tool_call_id)
              : (assistantMsg as any).tool_calls?.slice(-1)[0]
            ;(assistantMsg as any).tool_results.push({
              name: matchedToolCall?.name || 'tool',
              tool_call_id: parsed.tool_call_id || matchedToolCall?.id,
              content: parsed.tool_result,
            })
            nextTick(() => scrollBottom())
          }
          // 后端返回错误事件
          if (parsed.error) {
            if (typeQueue) {
              const hasTools = (assistantMsg as any).tool_calls?.length > 0
              if (hasTools) {
                assistantMsg.post_content = (assistantMsg.post_content || '') + typeQueue
              } else {
                assistantMsg.content += typeQueue
              }
              typeQueue = ''
            }
            // 如果界面还没有任何内容，直接显示错误
            const errorContent = assistantMsg.content || assistantMsg.post_content
            if (!errorContent) {
              assistantMsg.content = `错误：${parsed.error}`
            }
            nextTick(() => scrollBottom())
          }
          if (parsed.session_id && !sessionId) {
            sessionId = parsed.session_id
            currentSession.value = sessionId
            if (isNewSession) {
              await loadSessions()
            }
          }
        } catch (e) {
          console.error('SSE JSON 解析失败:', e, data)
        }
      }
    }

    // 触发语音播报
    speak(assistantMsg.content)
  } catch(e: unknown) {
    const isAbort = e instanceof DOMException
      ? e.name === 'AbortError'
      : e instanceof Error && e.name === 'AbortError'

    if (isAbort) {
      const hasContent = Boolean(assistantMsg.content || assistantMsg.post_content || assistantMsg.tool_calls?.length || assistantMsg.tool_results?.length)
      if (!hasContent) {
        assistantMsg.content = '已停止生成'
      }
    } else {
      assistantMsg.content = `错误：${e instanceof Error ? e.message : '请求失败'}`
    }
  } finally {
    if (activeChatController.value === controller) {
      activeChatController.value = null
    }
    sending.value = false
  }
}

function newChat() {
  messages.value = []
  currentSession.value = -1
  // 移除旧的占位会话，避免重复
  sessions.value = sessions.value.filter(s => s.id !== -1)
  sessions.value.unshift({
    id: -1,
    title: '新对话',
    created_at: new Date().toLocaleString()
  })
}

function scrollBottom() {
  if (chatEnd.value) {
    chatEnd.value.scrollIntoView({ block: 'end', behavior: 'smooth' })
    return
  }

  if (chatBox.value) {
    chatBox.value.scrollTop = chatBox.value.scrollHeight
  }
}

import { useRoute } from 'vue-router'
const route = useRoute()

async function onPageLoad() {
  await loadSessions()

  // 处理 URL 上下文参数
  const { context_type, context_id, prompt } = route.query
  if (prompt) {
    input.value = String(prompt)
    await send({
      ...(context_type ? { context_type: String(context_type) } : {}),
      ...(context_id ? { context_id: String(context_id) } : {}),
    })
    return
  }

  if (context_type && context_id) {
    // 自动注入上下文提问
    input.value = `请帮我分析这个目标：${context_id}`
    await send({
      context_type: context_type as string,
      context_id: context_id as string
    })
  }
}

onMounted(onPageLoad)
onBeforeUnmount(() => {
  cleanupVoiceCapture()
  stopGenerating()
  if (window.speechSynthesis) {
    window.speechSynthesis.cancel()
  }
})
</script>
<template>
  <div class="flex h-[calc(100vh-64px)] bg-background text-foreground font-sans overflow-hidden">
    <!-- Sidebar -->
    <aside class="w-72 shrink-0 bg-muted/30 border-r border-border flex flex-col backdrop-blur-xl z-10 transition-all">
      <div class="p-5 flex justify-between items-center border-b border-border/50">
        <h2 class="text-base font-semibold flex items-center m-0 opacity-90">
          <MessageSquare :size="20" class="mr-2" />
          会话记录
        </h2>
        <Button variant="ghost" size="icon" @click="newChat" title="新对话" class="h-9 w-9 rounded-full bg-background/5 border border-border hover:bg-foreground hover:text-background transition-all">
          <Plus :size="20" />
        </Button>
      </div>

      <ScrollArea class="flex-1 p-3">
        <div v-if="!sessions.length" class="text-center py-8 text-muted-foreground text-sm">
          暂无历史会话
        </div>
        <div class="flex flex-col gap-2">
          <div
            v-for="s in sessions"
            :key="s.id"
            class="group flex items-center justify-between py-3 px-4 rounded-xl cursor-pointer bg-transparent transition-all border border-transparent hover:bg-background/40"
            :class="[currentSession === s.id ? 'bg-primary/10 border-primary/20' : '']"
            @click="loadMessages(s.id)"
          >
            <div class="overflow-hidden flex-1">
              <div class="font-medium text-sm whitespace-nowrap overflow-hidden text-ellipsis mb-1" :class="[currentSession === s.id ? 'text-primary' : '']">
                {{ s.title || `会话 #${s.id}` }}
              </div>
              <div class="text-xs text-muted-foreground">{{ s.created_at?.slice(0,16) }}</div>
            </div>
            <Button variant="ghost" size="icon" class="h-8 w-8 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-opacity" @click.stop="deleteSession(s.id)">
              <Trash2 :size="16" />
            </Button>
          </div>
        </div>
      </ScrollArea>
    </aside>

    <!-- Main Chat Window -->
    <main class="flex-1 bg-background/80 flex flex-col relative w-full">
      <ScrollArea ref="chatBox" class="flex-1 w-full pb-36 h-full">
        <div class="max-w-4xl w-full mx-auto flex flex-col px-4 pt-6 pb-5">
          <!-- Loading State -->
          <div v-if="loading" class="flex flex-col items-center justify-center h-full text-muted-foreground text-sm gap-4 py-20">
            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            <span>加载对话中...</span>
          </div>

          <!-- Empty State -->
          <div v-else-if="!messages.length" class="m-auto text-center animate-in fade-in py-32">
            <div class="w-20 h-20 mx-auto mb-5 bg-gradient-to-br from-white/5 to-transparent border border-white/5 rounded-full flex items-center justify-center text-muted-foreground shadow-2xl">
              <Bot :size="40" class="text-primary/80" />
            </div>
            <h3 class="text-2xl font-semibold mb-2 tracking-wide text-foreground">AimiGuard AI 助手</h3>
            <p class="text-muted-foreground text-[15px] max-w-sm mx-auto leading-relaxed">输入你的问题开始对话，支持自然语言安全分析与排查。</p>
          </div>

          <!-- Message List -->
          <div v-else class="flex flex-col gap-8">
            <div
              v-for="(msg, i) in messages"
              :key="messageKey(msg, i)"
              class="flex gap-4 animate-in slide-in-from-bottom-2 fade-in duration-300"
              :class="[msg.role === 'user' ? 'justify-end' : 'justify-start']"
            >
              <Avatar v-if="msg.role === 'assistant'" class="w-9 h-9 border border-border bg-muted shrink-0 text-muted-foreground">
                <AvatarFallback><Bot :size="20" /></AvatarFallback>
              </Avatar>

              <div class="max-w-[86%]">
                <div class="p-4 rounded-2xl text-[15px] leading-relaxed shadow-sm"
                  :class="[msg.role === 'user' ? 'bg-primary text-primary-foreground rounded-br-sm' : 'bg-muted/50 border rounded-bl-sm text-foreground']"
                >
                  <!-- User Message -->
                  <div v-if="msg.role === 'user'" class="whitespace-pre-wrap">
                    {{ msg.content }}
                  </div>
                  
                  <!-- Assistant Message -->
                  <template v-else>
                    <div
                      v-if="!msg.content && !msg.post_content && !msg.tool_calls?.length && !msg.tool_results?.length && sending"
                      class="inline-flex items-center gap-2.5 min-h-[28px] text-muted-foreground"
                    >
                      <span class="text-[15px]">思考中...</span>
                      <span class="flex items-center gap-1.5 align-middle">
                        <i class="w-1.5 h-1.5 rounded-full bg-primary/80 animate-bounce"></i>
                        <i class="w-1.5 h-1.5 rounded-full bg-primary/80 animate-bounce delay-150"></i>
                        <i class="w-1.5 h-1.5 rounded-full bg-primary/80 animate-bounce delay-300"></i>
                      </span>
                    </div>

                    <div
                      v-else-if="msg.content"
                      class="md-body text-foreground/90 markdown-content"
                      v-html="renderMd(msg.content)"
                    />
                    
                    <!-- Tools -->
                    <details v-if="msg.tool_calls?.length || msg.tool_results?.length" class="bg-black/20 rounded-xl border overflow-hidden mt-3 transition-all group">
                      <summary class="px-3.5 py-2.5 bg-white/5 border-b border-transparent text-xs text-muted-foreground flex items-center justify-between cursor-pointer select-none list-none group-hover:bg-white/10 group-open:border-border/50 w-full outline-none [&::-webkit-details-marker]:hidden"
                        :class="[msg.tool_results?.length && msg.tool_results.length >= (msg.tool_calls?.length || 0) ? 'text-emerald-500' : '']"
                      >
                        <div class="flex items-center overflow-hidden text-ellipsis whitespace-nowrap">
                          <Wrench v-if="msg.tool_calls?.length && !msg.tool_results?.length" class="w-3.5 h-3.5 mr-1" />
                          <CheckCircle2 v-else class="w-3.5 h-3.5 mr-1" />
                          <span class="whitespace-nowrap overflow-hidden text-ellipsis max-w-[400px]">
                            工具: {{ (msg.tool_calls || msg.tool_results || []).map((t: any) => t.name || t.function?.name || 'unknown_tool').join(', ') }}
                          </span>
                        </div>
                        <ChevronDown class="w-4 h-4 transition-transform duration-300 group-open:rotate-180" />
                      </summary>

                      <div class="animate-in slide-in-from-top-1">
                        <template v-if="msg.tool_calls?.length">
                          <div
                            v-for="toolCall in msg.tool_calls"
                            :key="toolCall.id"
                            class="p-3.5 border-b border-white/5 last:border-0"
                          >
                            <div class="font-mono text-[13px] font-semibold text-primary/80 mb-2 flex items-center justify-between">
                              <span class="flex items-center gap-1"><Wrench class="w-3.5 h-3.5" /> {{ toolCall.name || toolCall.function?.name }}</span>
                              <CheckCircle2 v-if="msg.tool_results?.find(r => (r.tool_call_id && r.tool_call_id === toolCall.id) || r.name === (toolCall.name || toolCall.function?.name))" class="w-3.5 h-3.5 text-emerald-500" />
                              <div v-else class="animate-spin h-3 w-3 border-2 border-primary border-t-transparent rounded-full"></div>
                            </div>
                            
                            <div class="text-[11px] text-slate-400 mb-1 ml-0.5 uppercase tracking-wider">参数输入</div>
                            <pre class="m-0 p-3 bg-black/40 rounded-md text-xs overflow-x-auto text-slate-50 border-l-2 border-primary font-mono">{{ formatJson(toolCall.arguments || toolCall.function?.arguments) }}</pre>

                            <template v-if="msg.tool_results?.find(r => (r.tool_call_id && r.tool_call_id === toolCall.id) || r.name === (toolCall.name || toolCall.function?.name))">
                              <div class="text-[11px] text-emerald-400 mt-2 mb-1 ml-0.5 uppercase tracking-wider">返回结果</div>
                              <pre class="m-0 p-3 bg-black/40 rounded-md text-xs overflow-x-auto text-emerald-100 border-l-2 border-emerald-500 font-mono">{{ formatToolResult(msg.tool_results.find(r => (r.tool_call_id && r.tool_call_id === toolCall.id) || r.name === (toolCall.name || toolCall.function?.name))!.content) }}</pre>
                            </template>
                          </div>
                        </template>

                        <template v-else-if="msg.tool_results?.length">
                          <div
                            v-for="(toolResult, toolIndex) in msg.tool_results"
                            :key="toolResultKey(messageKey(msg, i), toolResult, toolIndex)"
                            class="p-3.5 border-b border-white/5 last:border-0"
                          >
                            <div class="font-mono text-[13px] font-semibold text-primary/80 mb-2 flex items-center gap-1"><Wrench class="w-3.5 h-3.5" /> {{ toolResult.name || 'unknown_tool' }}</div>
                            <div class="text-[11px] text-emerald-400 mb-1 ml-0.5 uppercase tracking-wider">返回结果</div>
                            <pre class="m-0 p-3 bg-black/40 rounded-md text-xs overflow-x-auto text-emerald-100 border-l-2 border-emerald-500 font-mono">{{ formatToolResult(toolResult.content) }}</pre>
                          </div>
                        </template>
                      </div>
                    </details>
                    
                    <div
                      v-if="msg.post_content"
                      class="md-body text-foreground/90 markdown-content mt-2"
                      v-html="renderMd(msg.post_content)"
                    />
                  </template>
                </div>
              </div>

              <Avatar v-if="msg.role === 'user'" class="w-9 h-9 bg-primary/20 shrink-0 text-primary border border-primary/30">
                <AvatarFallback><User class="w-5 h-5" /></AvatarFallback>
              </Avatar>
            </div>
          </div>
        </div>
      </ScrollArea>
      <div ref="chatEnd" class="h-px w-full" aria-hidden="true"></div>

      <!-- Input Area -->
      <div class="absolute bottom-0 left-0 right-0 pb-3 bg-gradient-to-t from-background/95 from-75% to-transparent pointer-events-none flex justify-center z-10 w-full">
        <div class="max-w-4xl w-full px-4 pt-6">
          <div class="pointer-events-auto backdrop-blur-xl border rounded-[24px] p-2 flex items-end gap-3 shadow-2xl transition-all focus-within:border-primary/40 focus-within:ring-2 focus-within:ring-primary/10">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="h-[38px] w-[38px] rounded-full shrink-0 mb-1.5 ml-1.5 relative cursor-pointer"
                    :class="[listening ? 'text-destructive hover:text-destructive hover:bg-destructive/10' : 'text-muted-foreground hover:text-foreground hover:bg-white/10']"
                    :disabled="!recognition"
                    @click="toggleListen"
                  >
                    <Mic v-if="listening" :size="20" class="z-10" />
                    <MicOff v-else :size="20" />
                    <div v-if="listening" class="absolute inset-0 rounded-full border-2 border-destructive animate-ping"></div>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {{ recognition ? (listening ? '停止录音' : '开始语音输入') : '当前浏览器不支持语音识别' }}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <Textarea
              v-model="input"
              class="flex-1 bg-transparent border-0 text-foreground font-sans text-[15px] leading-relaxed py-2.5 resize-none max-h-[150px] min-h-[44px] focus-visible:ring-0 focus-visible:ring-offset-0 shadow-none scrollbar-hide"
              placeholder="请输入你的问题（Enter 发送，Shift+Enter 换行）"
              :rows="1"
              @keydown.enter.exact.prevent="send"
              @keydown.enter.shift.stop
            />

            <div class="flex gap-1.5 p-1 shrink-0">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      class="h-[38px] w-[38px] rounded-full cursor-pointer"
                      :class="[ttsEnabled ? 'text-primary' : 'text-muted-foreground']"
                      @click="toggleTts"
                    >
                      <Volume2 v-if="ttsEnabled" :size="20" />
                      <VolumeX v-else :size="20" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>AI 语音播报</TooltipContent>
                </Tooltip>
              </TooltipProvider>

              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      v-if="sending"
                      size="icon"
                      class="h-[38px] w-[38px] rounded-full cursor-pointer border border-destructive/30 bg-destructive/10 text-destructive hover:bg-destructive/15 hover:text-destructive shadow-sm transition-all"
                      @click="stopGenerating"
                    >
                      <Square :size="16" fill="currentColor" />
                    </Button>
                    <Button
                      v-else
                      class="h-[38px] w-[38px] rounded-full transition-all cursor-pointer"
                      :class="!input.trim() ? 'opacity-50 cursor-not-allowed bg-muted text-muted-foreground hover:bg-muted' : 'bg-primary text-primary-foreground hover:scale-105 shadow-md shadow-primary/20'"
                      :disabled="!input.trim()"
                      size="icon"
                      @click="send"
                    >
                      <Send :size="18" class="ml-0.5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{{ sending ? '停止生成' : '发送消息' }}</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>
          <div class="text-center text-[11px] text-muted-foreground/60 mt-3 pointer-events-auto">AI 生成内容仅供参考，请结合实际进行核验。</div>
        </div>
      </div>
    </main>
  </div>
</template>


<style>
/* Markdown Content Overrides */
.markdown-content { overflow-wrap: anywhere; word-break: break-word; }
.markdown-content p { margin: 0.5rem 0; }
.markdown-content pre { background: rgba(0,0,0,0.4); border: 1px solid theme('colors.border'); border-radius: 0.5rem; padding: 0.75rem; overflow-x: auto; font-size: 0.85rem; margin: 0.75rem 0; }
.markdown-content code { background: rgba(0,0,0,0.3); border-radius: 0.25rem; padding: 0.125rem 0.375rem; font-size: 0.85rem; color: theme('colors.slate.200'); font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
.markdown-content pre code { background: transparent; padding: 0; color: inherit; }
.markdown-content ul, .markdown-content ol { padding-left: 1.5em; margin: 0.5rem 0; }
.markdown-content ul { list-style-type: disc; }
.markdown-content ol { list-style-type: decimal; }
.markdown-content blockquote { border-left: 3px solid theme('colors.primary.DEFAULT'); padding: 0.5rem 0.75rem; opacity: 0.8; margin: 0.5rem 0; background: theme('colors.primary.DEFAULT' / 5%); border-radius: 0 0.375rem 0.375rem 0; }
.markdown-content h1, .markdown-content h2, .markdown-content h3 { margin: 1rem 0 0.5rem; color: theme('colors.foreground'); font-weight: 600; line-height: 1.25; }
.markdown-content h1 { font-size: 1.5rem; }
.markdown-content h2 { font-size: 1.25rem; }
.markdown-content h3 { font-size: 1.125rem; }
.markdown-content table { border-collapse: collapse; width: 100%; font-size: 0.85rem; margin: 0.75rem 0; border: 1px solid theme('colors.border'); border-radius: 0.5rem; overflow: hidden; display: block; }
.markdown-content th, .markdown-content td { border: 1px solid theme('colors.border'); padding: 0.5rem 0.75rem; }
.markdown-content th { background: theme('colors.white' / 3%); font-weight: 600; text-align: left; }
.markdown-content a { color: theme('colors.primary.DEFAULT'); text-decoration: none; transition: opacity 0.2s; }
.markdown-content a:hover { text-decoration: underline; opacity: 0.8; }
.scrollbar-hide::-webkit-scrollbar { display: none; }
.scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
</style>



