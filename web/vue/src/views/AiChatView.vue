<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/index'
import AiSessionSidebar from '@/components/ai/AiSessionSidebar.vue'
import AiMessageList from '@/components/ai/AiMessageList.vue'
import AiChatInput from '@/components/ai/AiChatInput.vue'
import {
  Terminal,
  FileText,
  Shield,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Camera,
  Server,
  Clock,
} from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'

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
  content?: string
  openai_content?: string | null
  ts?: string
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

interface ChatAttachmentPayload {
  name: string
  type: string
  size: number
  isImage: boolean
  textContent?: string
}

// ─── 通用状态 ────────────────────────────────────────────────────────────────
const sessions = ref<Session[]>([])
const messages = ref<Message[]>([])
const loading = ref(false)
const sending = ref(false)
const currentSession = ref<number | null>(null)
const activeChatController = ref<AbortController | null>(null)
const ttsEnabled = ref(true)
const inFlightSessionId = ref<number | null>(null)
const pendingSessionMessages = reactive<Record<number, Message[]>>({})
const route = useRoute()
const TTS_STORAGE_KEY = 'aimiguard.ai.tts-enabled'

function cloneMessages(source: Message[]): Message[] {
  return source.map((msg) => ({
    ...msg,
    tool_calls: msg.tool_calls ? msg.tool_calls.map((tc) => ({ ...tc, function: tc.function ? { ...tc.function } : undefined })) : undefined,
    tool_results: msg.tool_results ? msg.tool_results.map((tr) => ({ ...tr })) : undefined,
  }))
}

function setPendingMessages(sessionId: number, source: Message[]) {
  pendingSessionMessages[sessionId] = source
}

function getPendingMessages(sessionId: number): Message[] | null {
  const pending = pendingSessionMessages[sessionId]
  return pending ? cloneMessages(pending) : null
}

function mergeServerWithPending(sessionId: number, serverMessages: Message[]): Message[] {
  const pending = pendingSessionMessages[sessionId]
  if (!pending) return serverMessages

  if (inFlightSessionId.value === sessionId) {
    return cloneMessages(pending)
  }

  if (pending.length > serverMessages.length) {
    return cloneMessages(pending)
  }

  delete pendingSessionMessages[sessionId]
  return serverMessages
}

function loadTtsPreference() {
  if (typeof window === 'undefined') return true
  try {
    const saved = window.localStorage.getItem(TTS_STORAGE_KEY)
    if (saved === null) return true
    return saved === '1' || saved === 'true'
  } catch {
    return true
  }
}

function persistTtsPreference(enabled: boolean) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(TTS_STORAGE_KEY, enabled ? '1' : '0')
  } catch {
    // 本地存储不可用时静默降级
  }
}

// ─── 演练模式状态 ────────────────────────────────────────────────────────────
const drillMode = ref(false)
const drillLog = ref<Array<{
  id: number
  type: 'step' | 'thinking' | 'tool_call' | 'tool_result' | 'complete' | 'warning' | 'text'
  icon: string
  color: string
  label: string
  content: string
  timestamp: string
  expanded: boolean
  toolIcon: string
}>>([])
const drillStep = ref(0)
const drillMaxStep = ref(30)
const drillProgress = ref(0)
const drillReport = ref('')
const drillReportHtml = ref(false)
const drillSummary = ref('')
const drillFindingCount = ref(0)
const drillPanelOpen = ref(false)
const drillElapsed = ref(0)
const drillHostsFound = ref(0)
const drillScreenshotsTaken = ref(0)
let drillLogId = 0
let drillTimer: ReturnType<typeof setInterval> | null = null

const toolIconMap: Record<string, string> = {
  search: 'search',
  network_scan: 'search',
  scan: 'search',
  camera: 'camera',
  screenshot: 'camera',
  web: 'camera',
  bruteforce: 'lock',
  ssh: 'lock',
  rdp: 'lock',
  mysql: 'lock',
  honeypot: 'bug',
  audit: 'bug',
  stats: 'bug',
  ban: 'ban',
  report: 'file-text',
  generate: 'file-text',
  status: 'target',
  plan: 'target',
  analyze: 'eye',
  document: 'eye',
}

function getToolIcon(toolName: string): string {
  if (!toolName) return 'terminal'
  const lower = toolName.toLowerCase()
  for (const [key, icon] of Object.entries(toolIconMap)) {
    if (lower.includes(key)) return icon
  }
  return 'zap'
}

function drillAdd(type: 'step' | 'thinking' | 'tool_call' | 'tool_result' | 'complete' | 'warning' | 'text', label: string, content: string, icon: string, color: string, toolIcon = 'terminal') {
  if (drillLog.value.length >= 500) drillLog.value.shift()  // 限制最大长度，防止内存溢出
  drillLog.value.push({
    id: ++drillLogId,
    type,
    icon,
    color,
    label,
    content,
    timestamp: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
    expanded: type === 'tool_result',
    toolIcon,
  })
  nextTick(() => {
    const el = document.querySelector('.drill-log-scroll')
    if (el) el.scrollTop = el.scrollHeight
  })
}

function drillToggleExpand(id: number) {
  const entry = drillLog.value.find(e => e.id === id)
  if (entry) entry.expanded = !entry.expanded
}

function formatToolResult(result: string): string {
  try {
    const parsed = JSON.parse(result)
    if (parsed.error) return `❌ ${parsed.error}`
    if (parsed.vulnerable) {
      const creds = parsed.vulnerable_creds || []
      if (creds.length > 0) {
        return `🔴 弱口令发现！\n${creds.map((c: any) => `  ${c.username} / ${c.password}`).join('\n')}`
      }
      return `✅ 检测完成，未发现常见弱口令`
    }
    if (parsed.发现主机 !== undefined) {
      drillHostsFound.value = Math.max(drillHostsFound.value, parsed.发现主机)
      return `✅ 发现 ${parsed.发现主机} 台主机`
    }
    if (parsed.total !== undefined) return `✅ 蜜罐记录 ${parsed.total} 次攻击`
    if (parsed.screenshot_url) { drillScreenshotsTaken.value++; return `✅ 截图已保存` }
    if (parsed.report) return `✅ 报告生成完毕，共 ${parsed.findings_count || 0} 项发现`
    if (parsed.plan) {
      // 行动计划：提取阶段数作为摘要，不显示完整 markdown
      const phases = (parsed.plan.match(/### /g) || []).length
      return `✅ ${parsed.message || '行动计划已生成'}（${phases} 个阶段）`
    }
    if (parsed.攻击记录 !== undefined) {
      // 蜜罐审计结果
      const count = parsed.总数 || (parsed.攻击记录 && parsed.攻击记录.length) || 0
      const service = parsed.service || '全部'
      return `✅ 蜜罐审计完成，服务 [${service}]，${count} 条攻击记录`
    }
    if (parsed.local_ip) {
      // 本机IP查询结果
      return `✅ 本机 IP: ${parsed.local_ip} | 主机名: ${parsed.hostname || 'unknown'}`
    }
    if (parsed.message) return parsed.message
    return JSON.stringify(parsed, null, 2)
  } catch { return result }
}

function toggleDrillPanel() { drillPanelOpen.value = !drillPanelOpen.value }

function startDrillTimer() {
  drillElapsed.value = 0
  if (drillTimer) clearInterval(drillTimer)
  drillTimer = setInterval(() => { drillElapsed.value++ }, 1000)
}

function stopDrillTimer() {
  if (drillTimer) { clearInterval(drillTimer); drillTimer = null }
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function speak(text: string) {
  if (!ttsEnabled.value || !window.speechSynthesis) return
  const stripped = text.replace(/[#*`>~_\[\]()!]/g, ' ').replace(/\s+/g, ' ').trim()
  const utt = new SpeechSynthesisUtterance(stripped.slice(0, 400))
  utt.lang = 'zh-CN'; utt.rate = 1.1
  window.speechSynthesis.speak(utt)
}

function toggleTts() {
  if (ttsEnabled.value && window.speechSynthesis) window.speechSynthesis.cancel()
  ttsEnabled.value = !ttsEnabled.value
  persistTtsPreference(ttsEnabled.value)
}

function stopGenerating() { activeChatController.value?.abort() }

// Session Management
async function loadSessions() {
  try {
    const d = await api.get<any>('/api/v1/ai/sessions')
    sessions.value = (d.data ?? d) as Session[]
  } catch(e) { console.error(e) }
}

async function loadMessages(sid: number) {
  if (sid === -1) { currentSession.value = -1; messages.value = []; loading.value = false; return }
  loading.value = true; currentSession.value = sid

  const pending = getPendingMessages(sid)
  if (inFlightSessionId.value === sid && pending) {
    messages.value = pending
    loading.value = false
    return
  }

  try {
    const d = await api.get<any>(`/api/v1/ai/sessions/${sid}/messages`)
    const normalized = normalizeMessages((d.data ?? d) as ApiMessage[])
    messages.value = mergeServerWithPending(sid, normalized)
  } catch(e) { console.error(e) }
  loading.value = false
}

async function deleteSession(sid: number) {
  try {
    await api.delete(`/api/v1/ai/sessions/${sid}`)
    delete pendingSessionMessages[sid]
    if (currentSession.value === sid) { messages.value = []; currentSession.value = null }
    await loadSessions()
  } catch (e) { console.error('删除会话失败:', e) }
}

function normalizeMessages(source: ApiMessage[], fallbackReply = ''): Message[] {
  const resolveContent = (msg: ApiMessage) => {
    return (msg.content ?? msg.openai_content ?? '').toString()
  }
  const resolveTime = (msg: ApiMessage) => {
    return msg.created_at || msg.ts
  }

  const normalized: Message[] = []
  let index = 0
  while (index < source.length) {
    const current = source[index]
    if (current.role === 'user') {
      normalized.push({ role: 'user', content: resolveContent(current), created_at: resolveTime(current) })
      index += 1; continue
    }
    if (current.role === 'assistant' && current.tool_calls?.length) {
      const toolResults: ToolResult[] = []
      let content = resolveContent(current)
      let postContent = ''
      let createdAt = resolveTime(current)
      let cursor = index + 1
      let seqIndex = 0
      while (cursor < source.length) {
        const next = source[cursor]
        if (next.role === 'tool') {
          let matchedCall = current.tool_calls?.find(tc => tc.id === next.tool_call_id)
          if (!matchedCall && seqIndex < current.tool_calls.length) matchedCall = current.tool_calls[seqIndex]
          const toolName = next.name || matchedCall?.name || (matchedCall as any)?.function?.name || 'unknown_tool'
          toolResults.push({ content: resolveContent(next), created_at: resolveTime(next), name: toolName, tool_call_id: next.tool_call_id || matchedCall?.id })
          seqIndex++; cursor += 1; continue
        }
        break
      }
      normalized.push({ role: 'assistant', content, created_at: createdAt, tool_calls: current.tool_calls, tool_results: toolResults })
      index = cursor; continue
    }
    if (current.role === 'assistant') {
      const assistantContent = resolveContent(current)
      normalized.push({ role: 'assistant', content: assistantContent || fallbackReply, created_at: resolveTime(current) })
      index += 1; continue
    }
    normalized.push({ role: 'assistant', content: '', created_at: resolveTime(current), tool_results: [{ content: resolveContent(current), created_at: resolveTime(current), name: current.name, tool_call_id: current.tool_call_id }] })
    index += 1
  }
  if (!normalized.length && fallbackReply) normalized.push({ role: 'assistant', content: fallbackReply })
  return normalized
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

  if (textParts) {
    blocks.push(`\n\n${textParts}`)
  }

  if (imageTips) {
    blocks.push(`\n\n[已附加图片]\n${imageTips}\n请基于对话上下文给出处理建议。`)
  }

  return blocks.join('')
}

function isEmptyAssistantMessage(msg?: Message): boolean {
  if (!msg || msg.role !== 'assistant') return false
  return !(
    msg.content?.trim() ||
    msg.post_content?.trim() ||
    msg.tool_calls?.length ||
    msg.tool_results?.length
  )
}

// Send
async function send(text: string, extraParams: any = {}, documentContent?: string) {
  if (!text && !documentContent) return
  if (sending.value) return

  const isDrill = !!documentContent
  const attachmentFiles = (extraParams?.files || []) as File[]
  if (isDrill) {
    drillLog.value = []; drillReport.value = ''; drillMode.value = true; drillPanelOpen.value = true
    drillStep.value = 0; drillFindingCount.value = 0; drillElapsed.value = 0
    drillHostsFound.value = 0; drillScreenshotsTaken.value = 0
    startDrillTimer()
  }

  const attachments = (extraParams?.attachments || []) as ChatAttachmentPayload[]
  const baseText = (text || '').trim() || (attachmentFiles.length ? '请分析我上传的文件/图片。' : '')
  const composedText = isDrill ? text : composeTextWithAttachments(baseText, attachments)
  const displayText = isDrill ? `【演练文档】\n${documentContent}` : composedText
  messages.value.push({ role: 'user', content: displayText })
  sending.value = true
  const requestMessages = messages.value
  const requestSessionId = currentSession.value && currentSession.value > 0 ? currentSession.value : null
  let resolvedSessionId: number | null = requestSessionId

  if (requestSessionId) {
    inFlightSessionId.value = requestSessionId
    setPendingMessages(requestSessionId, requestMessages)
  } else {
    inFlightSessionId.value = null
  }

  let assistantMsg = reactive<Message>({ role: 'assistant', content: '' })
  requestMessages.push(assistantMsg as any)

  const controller = new AbortController()
  activeChatController.value = controller

  try {
    const requestText = isDrill ? `【演练文档】${documentContent}` : baseText
    const token = localStorage.getItem('token')
    const headers: Record<string, string> = {}
    if (token) headers['Authorization'] = `Bearer ${token}`

    let response: Response
    if (attachmentFiles.length) {
      const form = new FormData()
      form.append('message', requestText)
      form.append('drill_mode', isDrill ? 'true' : 'false')
      if (currentSession.value && currentSession.value !== -1) {
        form.append('session_id', String(currentSession.value))
      }
      if (extraParams?.context_type) form.append('context_type', String(extraParams.context_type))
      if (extraParams?.context_id) form.append('context_id', String(extraParams.context_id))
      attachmentFiles.forEach((file) => form.append('files', file))

      response = await fetch('/api/v1/ai/chat/stream', {
        method: 'POST',
        headers,
        body: form,
        credentials: 'include',
        signal: controller.signal,
      })
    } else {
      headers['Content-Type'] = 'application/json'
      const body: any = { message: requestText, drill_mode: isDrill, ...extraParams }
      delete body.attachments
      delete body.files
      if (currentSession.value && currentSession.value !== -1) body.session_id = currentSession.value
      response = await fetch('/api/v1/ai/chat/stream', {
        method: 'POST', headers, body: JSON.stringify(body), credentials: 'include', signal: controller.signal
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
          if (hasTools) {
            assistantMsg = reactive({ role: 'assistant', content: '', created_at: new Date().toISOString() }) as any
            requestMessages.push(assistantMsg as any)
          }
          assistantMsg.content += typeQueue.slice(0, popCount)
          typeQueue = typeQueue.slice(popCount)
        } else { clearInterval(typeInterval); typeInterval = null }
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

          if (parsed.drill_mode) {
            drillMode.value = true; drillLog.value = []; drillReport.value = ''
            drillFindingCount.value = 0; drillHostsFound.value = 0; drillScreenshotsTaken.value = 0
            startDrillTimer()
drillAdd('text', '🚀 演练启动', 'AI 正在分析演练文档，制定行动计划...', 'zap', 'text-primary')
            continue
          }

          if (parsed.drill_step) {
            drillStep.value = parsed.drill_step.step || 0
            drillMaxStep.value = parsed.drill_step.max_steps || 30
            drillProgress.value = Math.round((drillStep.value / drillMaxStep.value) * 100)
            if (parsed.drill_step.status === 'thinking') {
              drillAdd('thinking', '🤔 AI 决策中', parsed.drill_step.message || '', 'loader', 'text-yellow-400')
            }
          }

          if (parsed.drill_complete) {
            drillReport.value = parsed.drill_complete.report || ''
            drillReportHtml.value = !!parsed.drill_complete.is_html
            drillSummary.value = parsed.drill_complete.summary || ''
            drillFindingCount.value = parsed.drill_complete.findings_count || 0
            stopDrillTimer()
            const autoTag = parsed.drill_complete.auto_generated ? ' [自动生成]' : ''
            const htmlTag = parsed.drill_complete.is_html ? ' 📊' : ''
            drillAdd('complete', '✅ 演练完成', `共发现 ${drillFindingCount.value} 个安全问题，演练结束${autoTag}${htmlTag}`, 'check-circle', 'text-emerald-400')
          }

          if (parsed.drill_warning) {
            drillAdd('warning', '⚠️ 演练警告', parsed.drill_warning, 'alert-triangle', 'text-orange-400')
          }

          if (parsed.drill_final) {
            drillAdd('complete', '📋 最终状态', parsed.drill_final.exec_summary || '', 'shield', 'text-blue-400')
          }

          if (parsed.content) { typeQueue += parsed.content; startTypewriter() }

          if (parsed.tool_call) {
            if (typeQueue) {
              assistantMsg.content += typeQueue
              typeQueue = ''
            }
            if (!(assistantMsg as any).tool_calls) (assistantMsg as any).tool_calls = []
            const tcId = 'tc_' + Date.now()
            ;(assistantMsg as any).tool_calls.push({ id: tcId, name: parsed.tool_call.name, arguments: parsed.tool_call.arguments })
            if (drillMode.value) {
              const tIcon = getToolIcon(parsed.tool_call.name)
              const toolLabel = parsed.tool_call.name.replace('drill_', '').replace(/_/g, ' ').toUpperCase()
              drillAdd('tool_call', `🔧 ${toolLabel}`, JSON.stringify(parsed.tool_call.arguments || {}, null, 2), 'terminal', 'text-purple-400', tIcon)
            }
          }

          if (parsed.tool_result) {
            if (typeQueue) { assistantMsg.content += typeQueue; typeQueue = '' }
            if (!(assistantMsg as any).tool_results) (assistantMsg as any).tool_results = []
            const tcId = parsed.tool_call_id || (assistantMsg as any).tool_calls?.slice(-1)[0]?.id || ''
            const result = typeof parsed.tool_result === 'string' ? parsed.tool_result : JSON.stringify(parsed.tool_result, null, 2)
            ;(assistantMsg as any).tool_results.push({ name: (assistantMsg as any).tool_calls?.find((tc: any) => tc.id === tcId)?.name || 'tool', tool_call_id: tcId, content: result })
            if (drillMode.value) {
              const lastLog = (() => { for (let i = drillLog.value.length - 1; i >= 0; i--) { if (drillLog.value[i].type === 'tool_call') return drillLog.value[i] } return null })()
              if (lastLog) {
                lastLog.content = formatToolResult(result)
                try {
                  const r = JSON.parse(result)
                  if (r.vulnerable && r.vulnerable_creds?.length > 0) drillFindingCount.value++
                } catch (e) { console.warn('工具结果解析异常:', e) }
              }
            }
          }

          if (parsed.session_id && !resolvedSessionId) {
            resolvedSessionId = Number(parsed.session_id)
            inFlightSessionId.value = resolvedSessionId
            setPendingMessages(resolvedSessionId, requestMessages)
            await loadSessions()
            if (!currentSession.value || currentSession.value === -1) {
              currentSession.value = resolvedSessionId
            }
          }
        } catch (e) { console.error('SSE解析错误:', e) }
      }
    }
    if (!drillMode.value) speak(assistantMsg.content)
  } catch(e: any) {
    stopDrillTimer()
    if (e.name !== 'AbortError') assistantMsg.content = `错误：${e.message || '请求失败'}`
    if (drillMode.value) drillAdd('warning', '❌ 请求失败', e.message || '', 'alert-triangle', 'text-red-400')
  } finally {
    stopDrillTimer(); sending.value = false; activeChatController.value = null
    const lastMsg = requestMessages[requestMessages.length - 1]
    if (isEmptyAssistantMessage(lastMsg)) {
      requestMessages.pop()
    }

    if (resolvedSessionId) {
      setPendingMessages(resolvedSessionId, requestMessages)
    }

    inFlightSessionId.value = null
  }
}

function handleNewChat() {
  messages.value = []; currentSession.value = -1; drillMode.value = false
  drillLog.value = []; drillReport.value = ''; stopDrillTimer()
  sessions.value = [{ id: -1, title: '新对话', created_at: new Date().toLocaleString() }, ...sessions.value.filter(s => s.id !== -1)]
}

function openReportWindow() {
  if (!drillReport.value) return
  const win = window.open('', '_blank')
  if (win) {
    win.document.write(drillReport.value)
    win.document.close()
  }
}

onMounted(async () => {
  ttsEnabled.value = loadTtsPreference()
  await loadSessions()
  const { context_type, context_id, prompt } = route.query as any
  if (prompt) await send(String(prompt), { context_type, context_id })
  else if (context_type && context_id) await send(`请帮我分析这个目标：${context_id}`, { context_type, context_id })
})

onBeforeUnmount(() => {
  // 切换页面时不主动中断请求，允许后台继续执行并在会话历史中恢复结果
  stopDrillTimer(); if (window.speechSynthesis) window.speechSynthesis.cancel()
})
</script>

<template>
  <div class="flex h-[calc(100vh-64px)] bg-transparent text-foreground overflow-hidden">
    <AiSessionSidebar
      :sessions="sessions"
      :current-session="currentSession"
      @new-chat="handleNewChat"
      @load-messages="loadMessages"
      @delete-session="deleteSession"
    />
    <main class="flex-1 bg-transparent flex flex-col relative w-full overflow-hidden">

      <!-- ═══════════════════════════════════════════════════════════════ -->
      <!-- 演练执行面板（Agent 循环可视化 - 军事指挥中心风格）           -->
      <!-- ═══════════════════════════════════════════════════════════════ -->
      <Transition name="slide-up">
        <div v-if="drillPanelOpen" class="absolute inset-0 z-50 flex flex-col bg-background/98 backdrop-blur-2xl border-t border-primary/30">

          <!-- ── 顶部状态栏 ── -->
          <div class="flex items-center justify-between px-6 py-3 border-b border-border/60 bg-gradient-to-r from-background via-background to-muted/20 shrink-0 relative overflow-hidden">
            <!-- 扫描线动画 -->
            <div class="absolute inset-0 overflow-hidden pointer-events-none">
              <div class="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent animate-scanline"></div>
            </div>

            <div class="flex items-center gap-4 relative z-10">
              <!-- Logo区域 -->
              <div class="flex items-center gap-2.5">
                <div class="relative">
                  <div class="absolute inset-0 bg-primary/20 rounded-lg blur-md animate-pulse"></div>
                  <div class="relative bg-primary/10 p-2 rounded-lg border border-primary/30">
                    <Shield :size="20" class="text-primary" />
                  </div>
                </div>
                <div>
                  <h2 class="text-sm font-bold tracking-wide text-foreground flex items-center gap-1.5">
                    <span class="text-primary">⬡</span> 玄枢·AI 攻防指挥官
                  </h2>
                  <p class="text-[10px] text-muted-foreground/60 font-mono tracking-widest uppercase">
                    Security Drill Executor v2.0
                  </p>
                </div>
              </div>

              <!-- 状态指示器 -->
              <div class="h-8 w-px bg-border/40 mx-2"></div>

              <!-- 统计数据 -->
              <div class="flex items-center gap-4">
                <div class="flex items-center gap-1.5" title="已用时">
<Clock :size="12" class="text-primary/70" />
                  <span class="text-xs font-mono text-primary/80 tabular-nums">{{ formatElapsed(drillElapsed) }}</span>
                </div>
                <div class="flex items-center gap-1.5" title="发现主机">
                  <Server :size="12" class="text-emerald-400/70" />
                  <span class="text-xs font-mono text-emerald-400/90 tabular-nums">{{ drillHostsFound }}</span>
                </div>
                <div class="flex items-center gap-1.5" title="截图数量">
                  <Camera :size="12" class="text-blue-400/70" />
                  <span class="text-xs font-mono text-blue-400/90 tabular-nums">{{ drillScreenshotsTaken }}</span>
                </div>
                <div class="flex items-center gap-1.5" title="安全问题">
                  <AlertTriangle :size="12" class="text-orange-400/70" />
                  <span class="text-xs font-mono text-orange-400/90 tabular-nums">{{ drillFindingCount }}</span>
                </div>
              </div>
            </div>

            <!-- 右侧: 进度 + 控制 -->
            <div class="flex items-center gap-4 relative z-10">
              <!-- 进度条 -->
              <div class="flex items-center gap-3">
                <div class="text-xs text-muted-foreground/60 font-mono">
                  STEP {{ drillStep }}/{{ drillMaxStep }}
                </div>
                <div class="w-40 h-1.5 bg-muted/40 rounded-full overflow-hidden border border-border/20">
                  <div
                    class="h-full transition-all duration-500 ease-out rounded-full"
                    :class="drillProgress > 80 ? 'bg-gradient-to-r from-blue-500 to-primary' : drillProgress > 40 ? 'bg-gradient-to-r from-primary to-blue-500' : 'bg-gradient-to-r from-primary to-blue-400'"
                    :style="{ width: drillProgress + '%' }"
                  ></div>
                </div>
                <div class="text-xs font-mono text-primary tabular-nums w-8">{{ drillProgress }}%</div>
              </div>

              <Badge v-if="drillFindingCount > 0" variant="outline" class="text-xs border-orange-500/40 text-orange-400 bg-orange-500/10 font-mono">
                ⚠ {{ drillFindingCount }} 发现
              </Badge>

              <Button variant="ghost" size="sm" class="h-7 text-xs gap-1 hover:bg-muted/30" @click="toggleDrillPanel">
                <ChevronDown :size="14" />收起
              </Button>
            </div>
          </div>

          <!-- ── 主内容区 ── -->
          <div class="flex-1 flex overflow-hidden">

            <!-- Agent 执行日志（终端风格） -->
            <div class="flex-1 flex flex-col overflow-hidden">
              <!-- 终端头部 -->
              <div class="flex items-center gap-2 px-4 py-2 bg-muted/30 border-b border-border/40 shrink-0">
                <div class="flex gap-1.5">
                  <div class="w-2.5 h-2.5 rounded-full bg-red-500/60"></div>
                  <div class="w-2.5 h-2.5 rounded-full bg-yellow-500/60"></div>
                  <div class="w-2.5 h-2.5 rounded-full bg-emerald-500/60"></div>
                </div>
                <div class="text-[10px] text-muted-foreground/60 font-mono tracking-wider">
                  XUANSHU-DRILL :: AGENT-LOOP-TERMINAL
                </div>
                <div class="ml-auto flex items-center gap-1.5">
                  <div v-if="sending && drillMode" class="flex items-center gap-1 text-[10px] text-emerald-400/70 font-mono">
                    <div class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></div>
                    EXECUTING
                  </div>
                </div>
              </div>

              <!-- 终端内容 -->
              <ScrollArea class="drill-log-scroll flex-1 p-3 space-y-1.5 bg-[#0a0e14]">
                <!-- 欢迎信息 -->
                <div class="text-[11px] font-mono text-primary/40 mb-3 leading-relaxed">
                  <div>╔══════════════════════════════════════════════════════════════════╗</div>
                  <div>║  玄枢·AI 攻防指挥官 Security Drill Executor                    ║</div>
                  <div>║  Copyright (c) 2026 XuanShu Security Systems                 ║</div>
                  <div>╚══════════════════════════════════════════════════════════════════╝</div>
                </div>

                <div
                  v-for="entry in drillLog"
                  :key="entry.id"
                  class="rounded overflow-hidden border transition-all duration-200"
                  :class="{
                    'bg-yellow-500/5 border-yellow-500/20': entry.type === 'thinking',
                    'bg-purple-500/5 border-purple-500/25': entry.type === 'tool_call',
                    'bg-emerald-500/5 border-emerald-500/20': entry.type === 'tool_result',
                    'bg-emerald-500/8 border-emerald-500/40': entry.type === 'complete',
                    'bg-orange-500/5 border-orange-500/20': entry.type === 'warning',
                    'bg-primary/5 border-primary/20': entry.type === 'text',
                  }"
                >
                  <!-- 日志行头部 -->
                  <div
                    class="flex items-center gap-2 px-3 py-1.5 cursor-pointer hover:opacity-80 transition-opacity"
                    :class="{ 'cursor-default': entry.type !== 'tool_result' }"
                    @click="entry.type === 'tool_result' ? drillToggleExpand(entry.id) : null"
                  >
                    <span class="text-[9px] text-muted-foreground/30 shrink-0 font-mono">{{ entry.timestamp }}</span>
                    <span class="text-[10px] font-mono font-bold tracking-wider shrink-0"
                      :class="{
                        'text-yellow-400': entry.type === 'thinking',
                        'text-purple-400': entry.type === 'tool_call',
                        'text-emerald-400': entry.type === 'tool_result' || entry.type === 'complete',
                        'text-orange-400': entry.type === 'warning',
                        'text-primary': entry.type === 'text',
                      }"
                    >[{{ entry.label }}]</span>
                    <span v-if="entry.type === 'tool_call'" class="text-[10px] text-muted-foreground/60 font-mono">
                      {{ entry.content.split('\n')[0].slice(0, 80) }}{{ entry.content.length > 80 ? '...' : '' }}
                    </span>
                    <span v-if="entry.type === 'tool_result'" class="ml-auto flex items-center gap-1">
                      <ChevronUp v-if="entry.expanded" :size="10" class="text-muted-foreground/50" />
                      <ChevronDown v-else :size="10" class="text-muted-foreground/50" />
                    </span>
                    <!-- 执行中动画 -->
                    <div v-if="sending && entry.id === drillLog[drillLog.length - 1]?.id" class="ml-auto flex items-center gap-1">
                      <span class="text-[9px] text-primary/60 font-mono animate-pulse">●</span>
                    </div>
                  </div>

                  <!-- 日志行内容 -->
                  <div v-if="entry.type !== 'tool_result' || entry.expanded" class="px-3 pb-2">
                    <pre
                      v-if="entry.type === 'tool_result'"
                      class="text-[11px] font-mono text-emerald-300/80 whitespace-pre-wrap break-all max-h-48 overflow-auto leading-relaxed"
                      :class="entry.content.startsWith('🔴') ? 'text-red-400' : entry.content.startsWith('❌') ? 'text-red-400' : 'text-emerald-300/80'"
                    >{{ entry.content }}</pre>
                    <p v-else class="text-[11px] text-muted-foreground/70 font-mono leading-relaxed">{{ entry.content }}</p>
                  </div>
                </div>

                <!-- 执行中占位 -->
                <div v-if="sending && drillMode" class="flex items-center gap-2 text-[11px] font-mono text-muted-foreground/40 py-2">
                  <span class="animate-pulse">▶</span>
                  <span>AI 正在执行中...</span>
                </div>
              </ScrollArea>
            </div>

            <!-- 报告预览侧边栏 -->
            <div v-if="drillReport || drillSummary" class="w-[440px] border-l border-border/50 flex flex-col shrink-0 bg-muted/5">
              <div class="px-4 py-2.5 border-b border-border/40 bg-muted/20 flex items-center gap-2 shrink-0">
                <FileText :size="12" class="text-primary" />
                <span class="text-xs font-bold text-foreground tracking-wide">演练报告预览</span>
                <div class="ml-auto flex items-center gap-1.5">
                  <Badge v-if="drillFindingCount > 0" variant="outline" class="h-5 text-[10px] border-orange-500/30 text-orange-400 bg-orange-500/5">
                    {{ drillFindingCount }} 项
                  </Badge>
                  <button
                    v-if="drillReportHtml"
                    @click="openReportWindow"
                    class="ml-1 px-2 py-0.5 text-[10px] rounded border border-primary/30 text-primary/70 hover:text-primary hover:border-primary/60 transition-colors cursor-pointer bg-transparent"
                  >新窗口</button>
                </div>
              </div>
              <ScrollArea class="flex-1">
                <!-- HTML 报告：使用 iframe 渲染 -->
                <iframe
                  v-if="drillReportHtml && drillReport"
                  :srcdoc="drillReport"
                  class="w-full h-full border-0"
                  sandbox="allow-scripts"
                ></iframe>
                <!-- Markdown 报告：纯文本展示 -->
                <div v-else-if="drillReport || drillSummary" class="p-4 prose prose-invert prose-sm max-w-none text-foreground/70 whitespace-pre-wrap text-xs font-mono leading-relaxed">
                  {{ drillReport || drillSummary }}
                </div>
              </ScrollArea>
            </div>

            <!-- 空的侧边栏（无报告时显示统计） -->
            <div v-else class="w-[300px] border-l border-border/50 flex flex-col shrink-0 bg-muted/5">
              <div class="px-4 py-2.5 border-b border-border/40 bg-muted/20 shrink-0">
                <span class="text-xs font-bold text-foreground tracking-wide">实时统计</span>
              </div>
              <div class="flex-1 p-4 space-y-3">
                <div class="bg-muted/30 rounded-lg p-3 border border-border/30">
                  <div class="text-[10px] text-muted-foreground/50 uppercase tracking-wider mb-1">执行步骤</div>
                  <div class="text-2xl font-mono font-bold text-primary">{{ drillStep }}</div>
                  <div class="text-[10px] text-muted-foreground/50">/ {{ drillMaxStep }} 最大步数</div>
                </div>
                <div class="bg-muted/30 rounded-lg p-3 border border-border/30">
                  <div class="text-[10px] text-muted-foreground/50 uppercase tracking-wider mb-1">发现主机</div>
                  <div class="text-2xl font-mono font-bold text-emerald-400">{{ drillHostsFound }}</div>
                  <div class="text-[10px] text-muted-foreground/50">台存活主机</div>
                </div>
                <div class="bg-muted/30 rounded-lg p-3 border border-border/30">
                  <div class="text-[10px] text-muted-foreground/50 uppercase tracking-wider mb-1">截图采集</div>
                  <div class="text-2xl font-mono font-bold text-blue-400">{{ drillScreenshotsTaken }}</div>
                  <div class="text-[10px] text-muted-foreground/50">张 Web 截图</div>
                </div>
                <div class="bg-orange-500/5 rounded-lg p-3 border border-orange-500/20">
                  <div class="text-[10px] text-orange-400/60 uppercase tracking-wider mb-1">安全问题</div>
                  <div class="text-2xl font-mono font-bold text-orange-400">{{ drillFindingCount }}</div>
                  <div class="text-[10px] text-orange-400/50">项发现</div>
                </div>
                <div class="bg-muted/30 rounded-lg p-3 border border-border/30">
                  <div class="text-[10px] text-muted-foreground/50 uppercase tracking-wider mb-1">已用时间</div>
                  <div class="text-xl font-mono font-bold text-primary">{{ formatElapsed(drillElapsed) }}</div>
                </div>

                <!-- 工具调用历史 -->
                <div class="space-y-1">
                  <div class="text-[10px] text-muted-foreground/50 uppercase tracking-wider mb-2">工具调用记录</div>
                  <div v-for="entry in [...drillLog].reverse().filter(e => e.type === 'tool_result').slice(0, 8)" :key="entry.id"
                    class="flex items-center gap-2 text-[10px] font-mono text-muted-foreground/60 bg-muted/20 rounded px-2 py-1">
                    <span class="text-emerald-400/60">✓</span>
                    <span>{{ entry.label }}</span>
                  </div>
                  <div v-if="drillLog.filter(e => e.type === 'tool_result').length === 0" class="text-[10px] text-muted-foreground/30 font-mono italic">
                    尚未调用工具...
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Transition>

      <!-- ═══════════════════════════════════════════════════════════════ -->
      <!-- 迷你演练进度条（非展开时）                                      -->
      <!-- ═══════════════════════════════════════════════════════════════ -->
      <div v-if="drillMode && !drillPanelOpen" class="absolute top-0 left-0 right-0 z-40">
        <div class="h-0.5 bg-muted">
          <div class="h-full bg-gradient-to-r from-primary to-blue-500 transition-all duration-500" :style="{ width: drillProgress + '%' }"></div>
        </div>
        <div class="bg-muted/90 border-b border-border/40 px-4 py-1.5 flex items-center justify-between backdrop-blur">
          <div class="flex items-center gap-3 text-xs">
            <Shield :size="12" class="text-primary animate-pulse" />
            <span class="text-muted-foreground font-mono">演练执行中... 第 {{ drillStep }} 步</span>
            <span class="text-muted-foreground/40 font-mono text-[10px]">{{ formatElapsed(drillElapsed) }}</span>
          </div>
          <div class="flex items-center gap-2">
            <Badge v-if="drillFindingCount > 0" variant="outline" class="h-5 text-[10px] border-orange-500/30 text-orange-400 bg-orange-500/5">
              {{ drillFindingCount }} 发现
            </Badge>
            <Button variant="ghost" size="sm" class="h-5 text-[10px] gap-1" @click="toggleDrillPanel">
              <Terminal :size="12" />查看详情
            </Button>
          </div>
        </div>
      </div>

      <AiMessageList :messages="messages" :loading="loading" :sending="sending" />
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

<style scoped>
.slide-up-enter-active, .slide-up-leave-active { transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1); }
.slide-up-enter-from, .slide-up-leave-to { transform: translateY(100%); opacity: 0; }

@keyframes scanline {
  0% { transform: translateY(0); opacity: 1; }
  100% { transform: translateY(100vh); opacity: 0; }
}
.animate-scanline {
  animation: scanline 4s linear infinite;
background: linear-gradient(to bottom, transparent, hsl(var(--primary) / 0.12), transparent);
}
</style>
