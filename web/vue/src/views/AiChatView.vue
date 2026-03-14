<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue'
import { marked } from 'marked'
import { api } from '@/api/index'

interface ToolCall {
  id: string
  type?: string
  name: string
  arguments: Record<string, unknown>
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
const expandedBlocks = ref<Record<string, boolean>>({})

// ── STT ──────────────────────────────────────────────────────────────────
const listening = ref(false)
let recognition: any = null
const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
if (SpeechRecognition) {
  recognition = new SpeechRecognition()
  recognition.lang = 'zh-CN'
  recognition.continuous = false
  recognition.interimResults = false
  recognition.onresult = (e: any) => {
    const t = e.results[0][0].transcript
    input.value = (input.value + ' ' + t).trim()
  }
  recognition.onend = () => { listening.value = false }
}
function toggleListen() {
  if (!recognition) return
  if (listening.value) { recognition.stop(); listening.value = false }
  else { recognition.start(); listening.value = true }
}

// ── TTS ──────────────────────────────────────────────────────────────────
const ttsEnabled = ref(true)
function speak(text: string) {
  if (!ttsEnabled.value || !window.speechSynthesis) return
  const stripped = text.replace(/[#*`>~_\[\]()!]/g, ' ').replace(/\s+/g, ' ').trim()
  const utt = new SpeechSynthesisUtterance(stripped.slice(0, 400))
  utt.lang = 'zh-CN'
  utt.rate = 1.1
  window.speechSynthesis.speak(utt)
}

// ── Markdown ─────────────────────────────────────────────────────────────
function renderMd(text: string): string {
  const html = marked.parse(text, { breaks: true, gfm: true }) as string
  return html.replace(/<a /g, '<a target="_blank" rel="noopener noreferrer" ')
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
      let content = current.content || fallbackReply
      let createdAt = current.created_at
      let cursor = index + 1

      while (cursor < source.length) {
        const next = source[cursor]
        if (next.role === 'tool') {
          toolResults.push({
            content: next.content || '',
            created_at: next.created_at,
            name: next.name,
            tool_call_id: next.tool_call_id
          })
          cursor += 1
          continue
        }
        if (next.role === 'assistant' && !next.tool_calls?.length) {
          content = next.content || content
          createdAt = next.created_at || createdAt
          cursor += 1
        }
        break
      }

      normalized.push({
        role: 'assistant',
        content: content || fallbackReply,
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

function shouldCollapse(text: string): boolean {
  if (!text) return false
  const lineCount = (text.match(/\n/g)?.length ?? 0) + 1
  return text.length > 700 || lineCount > 12
}

function messageKey(message: Message, index: number): string {
  return `${message.role}-${message.created_at || 'no-ts'}-${index}`
}

function toolResultKey(parentKey: string, result: ToolResult, index: number): string {
  return `${parentKey}-tool-${result.tool_call_id || result.name || index}`
}

function isExpanded(key: string): boolean {
  return !!expandedBlocks.value[key]
}

function toggleExpanded(key: string) {
  expandedBlocks.value[key] = !expandedBlocks.value[key]
}

async function loadSessions() {
  try {
    const d = await api.get<any>('/api/v1/ai/sessions')
    sessions.value = d.data ?? d
  } catch(e) { console.error(e) }
}

async function loadMessages(sid: number) {
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
  messages.value.push(userMsg)
  sending.value = true

  // 使用 reactive 包装，确保闭包内的修改能触发 Vue 响应式更新
  const assistantMsg = reactive<Message>({ role: 'assistant', content: '' })
  messages.value.push(assistantMsg as any)
  await nextTick(); scrollBottom()

  try {
    const body: any = { message: text, ...extraParams }
    if (currentSession.value) body.session_id = currentSession.value

    const token = localStorage.getItem('token')
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`

    const response = await fetch('/api/v1/ai/chat/stream', {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      credentials: 'include'
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) {
      throw new Error('无法读取响应')
    }

    let isNewSession = !currentSession.value
    let sessionId = currentSession.value
    let buffer = '' // 添加缓冲区

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      
      // 保留最后一个可能不完整的行
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || !trimmed.startsWith('data: ')) continue
        
        const data = trimmed.slice(6)
        if (data === '[DONE]') continue
        
        try {
          const parsed = JSON.parse(data)
          if (parsed.content) {
            assistantMsg.content += parsed.content
            await nextTick(); scrollBottom()
          }
          // 工具调用：AI 正在调用工具
          if (parsed.tool_call) {
            if (!(assistantMsg as any).tool_calls) (assistantMsg as any).tool_calls = []
            ;(assistantMsg as any).tool_calls.push({
              id: parsed.tool_call.name + '_' + Date.now(),
              name: parsed.tool_call.name,
              arguments: parsed.tool_call.arguments,
            })
            await nextTick(); scrollBottom()
          }
          // 工具结果：扫描/执行完毕
          if (parsed.tool_result) {
            if (!(assistantMsg as any).tool_results) (assistantMsg as any).tool_results = []
            // 找到最后一个 tool_call，把结果关联过去
            const lastToolCall = (assistantMsg as any).tool_calls?.slice(-1)[0]
            ;(assistantMsg as any).tool_results.push({
              name: lastToolCall?.name || 'tool',
              content: parsed.tool_result,
            })
            await nextTick(); scrollBottom()
          }
          if (parsed.session_id && !sessionId) {
            sessionId = parsed.session_id
            currentSession.value = sessionId
          }
        } catch (e) {
          console.error('SSE JSON 解析失败:', e, data)
        }
      }
    }

    // 更新会话列表
    if (isNewSession && sessionId) {
      currentSession.value = sessionId
      await loadSessions()
    }

    // 语音播报
    speak(assistantMsg.content)
  } catch(e: unknown) {
    assistantMsg.content = `⚠️ ${e instanceof Error ? e.message : '请求失败'}`
  }
  sending.value = false
}

function newChat() {
  messages.value = []
  currentSession.value = null
}

function scrollBottom() {
  if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight
}

import { useRoute } from 'vue-router'
const route = useRoute()

async function onPageLoad() {
  await loadSessions()
  
  // 处理 URL传参上下文
  const { context_type, context_id } = route.query
  if (context_type && context_id) {
    // 自动发起一个分析请求
    input.value = `请帮我深度分析一下这个目标：${context_id}`
    await send({ 
      context_type: context_type as string, 
      context_id: context_id as string 
    })
  }
}

onMounted(onPageLoad)
</script>

<template>
  <v-container fluid class="pa-4" style="height:calc(100vh - 64px)">
    <v-row class="fill-height" style="height:100%">
      <!-- Session list -->
      <v-col cols="12" md="3" class="d-flex flex-column" style="height:100%">
        <v-card class="flex-grow-1 d-flex flex-column" style="height:100%; overflow:hidden">
          <v-card-title class="d-flex align-center pa-3 text-subtitle-1">
            会话列表
            <v-spacer />
            <v-btn icon variant="text" size="small" @click="newChat" title="新对话">
              <v-icon size="18">mdi-plus</v-icon>
            </v-btn>
          </v-card-title>
          <v-divider />
          <v-list density="compact" style="flex:1; overflow-y:auto">
            <v-list-item
              v-for="s in sessions"
              :key="s.id"
              :active="currentSession === s.id"
              active-color="primary"
              :title="s.title || `会话 #${s.id}`"
              :subtitle="s.created_at?.slice(0,16)"
              @click="loadMessages(s.id)"
            >
              <template #append>
                <v-btn icon variant="text" size="x-small" color="error" @click.stop="deleteSession(s.id)">
                  <v-icon size="14">mdi-close</v-icon>
                </v-btn>
              </template>
            </v-list-item>
            <v-list-item v-if="!sessions.length" class="text-medium-emphasis pa-4">
              暂无会话
            </v-list-item>
          </v-list>
        </v-card>
      </v-col>

      <!-- Chat window -->
      <v-col cols="12" md="9" class="d-flex flex-column" style="height:100%">
        <v-card class="flex-grow-1 d-flex flex-column" style="height:100%; overflow:hidden">
          <!-- Messages area -->
          <div ref="chatBox" style="flex:1; overflow-y:auto; padding:16px">
            <div v-if="loading" class="text-center py-8">
              <v-progress-circular indeterminate color="primary" />
            </div>
            <div v-else-if="!messages.length" class="d-flex flex-column align-center justify-center" style="height:100%; color:rgba(255,255,255,.3)">
              <v-icon size="64">mdi-robot-outline</v-icon>
              <div class="mt-4 text-subtitle-1">玄枢 AI 助手</div>
              <div class="text-caption mt-1">输入指令开始对话，支持自然语言触发扫描与分析</div>
            </div>
            <template v-else>
              <div
                v-for="(msg, i) in messages"
                :key="messageKey(msg, i)"
                :class="['d-flex', 'mb-4', msg.role === 'user' ? 'justify-end' : 'justify-start']"
              >
                <v-card
                  :color="msg.role === 'user' ? 'primary' : 'surface'"
                  :style="`max-width:${msg.role === 'user' ? '72%' : '78%'}; border:1px solid rgba(255,255,255,${msg.role==='user'?'0':'.08'})`"
                  class="pa-3"
                >
                  <div
                    v-if="msg.role === 'user'"
                    style="white-space:pre-wrap; font-size:.9rem; line-height:1.6"
                  >{{ msg.content }}</div>
                  <template v-else>
                    <div
                      v-if="msg.content"
                      class="md-body"
                      :class="{ 'collapsible-content': shouldCollapse(msg.content) && !isExpanded(messageKey(msg, i)) }"
                      style="font-size:.9rem; line-height:1.7"
                      v-html="renderMd(msg.content)"
                    />
                    <v-btn
                      v-if="msg.content && shouldCollapse(msg.content)"
                      variant="text"
                      size="small"
                      class="mt-2 px-0"
                      @click="toggleExpanded(messageKey(msg, i))"
                    >
                      {{ isExpanded(messageKey(msg, i)) ? '收起' : '展开全文' }}
                    </v-btn>
                    <div
                      v-if="msg.tool_calls?.length"
                      class="tool-call-block"
                      :class="{ 'mt-3': !!msg.content }"
                    >
                      <div class="text-caption text-medium-emphasis mb-2">工具调用</div>
                      <div
                        v-for="toolCall in msg.tool_calls"
                        :key="toolCall.id"
                        class="tool-call-item mb-2"
                      >
                        <div class="text-body-2 font-weight-medium mb-1">{{ toolCall.name }}</div>
                        <pre class="tool-pre">{{ formatJson(toolCall.arguments) }}</pre>
                      </div>
                    </div>
                    <div
                      v-if="msg.tool_results?.length"
                      class="tool-call-block mt-3"
                    >
                      <div class="text-caption text-medium-emphasis mb-2">工具结果</div>
                      <div
                        v-for="(toolResult, toolIndex) in msg.tool_results"
                        :key="toolResultKey(messageKey(msg, i), toolResult, toolIndex)"
                        class="tool-call-item mb-2"
                      >
                        <div class="text-body-2 font-weight-medium mb-1">
                          {{ toolResult.name || 'unknown_tool' }}
                        </div>
                        <pre
                          class="tool-pre"
                          :class="{ 'collapsible-pre': shouldCollapse(formatToolResult(toolResult.content)) && !isExpanded(toolResultKey(messageKey(msg, i), toolResult, toolIndex)) }"
                        >{{ formatToolResult(toolResult.content) }}</pre>
                        <v-btn
                          v-if="shouldCollapse(formatToolResult(toolResult.content))"
                          variant="text"
                          size="small"
                          class="mt-2 px-0"
                          @click="toggleExpanded(toolResultKey(messageKey(msg, i), toolResult, toolIndex))"
                        >
                          {{ isExpanded(toolResultKey(messageKey(msg, i), toolResult, toolIndex)) ? '收起' : '展开详情' }}
                        </v-btn>
                      </div>
                    </div>
                  </template>
                </v-card>
              </div>
            </template>
          </div>

          <!-- Input bar -->
          <v-divider />
          <div class="d-flex ga-2 pa-3 align-end">
            <!-- STT button -->
            <v-btn
              :icon="listening ? 'mdi-microphone-off' : 'mdi-microphone'"
              :color="listening ? 'error' : 'default'"
              variant="text"
              height="56"
              width="44"
              :title="recognition ? (listening ? '停止录音' : '语音输入') : '浏览器不支持语音识别'"
              :disabled="!recognition"
              @click="toggleListen"
            />
            <v-textarea
              v-model="input"
              placeholder="输入指令或问题，Enter 发送，Shift+Enter 换行"
              rows="2"
              auto-grow
              max-rows="5"
              hide-details
              no-resize
              style="flex:1"
              @keydown.enter.exact.prevent="send"
              @keydown.enter.shift="() => {}"
            />
            <!-- TTS toggle -->
            <v-btn
              :icon="ttsEnabled ? 'mdi-volume-high' : 'mdi-volume-off'"
              :color="ttsEnabled ? 'primary' : 'default'"
              variant="text"
              height="56"
              width="44"
              title="AI 语音播报"
              @click="ttsEnabled = !ttsEnabled"
            />
            <v-btn color="primary" height="56" :loading="sending" @click="send" icon>
              <v-icon>mdi-send</v-icon>
            </v-btn>
          </div>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<style scoped>
.md-body                  { overflow-wrap:anywhere; word-break:break-word; }
.md-body :deep(p)          { margin: 0.25rem 0; }
.md-body :deep(pre)        { background: rgba(0,0,0,.35); border-radius:6px; padding:.6em .8em; overflow-x:auto; font-size:.82rem; white-space:pre-wrap; word-break:break-word; overflow-wrap:anywhere; }
.md-body :deep(code)       { background: rgba(0,0,0,.3); border-radius:3px; padding:.1em .3em; font-size:.85rem; }
.md-body :deep(ul),
.md-body :deep(ol)         { padding-left:1.4em; margin:.25rem 0; }
.md-body :deep(blockquote) { border-left:3px solid rgba(0,229,255,.5); padding-left:.8em; opacity:.8; margin:.3rem 0; }
.md-body :deep(h1),
.md-body :deep(h2),
.md-body :deep(h3)         { margin:.4rem 0 .2rem; font-size:1rem; color:#00E5FF; }
.md-body :deep(table)      { border-collapse:collapse; width:100%; font-size:.82rem; }
.md-body :deep(th),
.md-body :deep(td)         { border:1px solid rgba(255,255,255,.1); padding:.3em .6em; }
.md-body :deep(th)         { background:rgba(0,229,255,.08); }
.md-body :deep(a)          { color:#7ad7ff; text-decoration:underline; overflow-wrap:anywhere; word-break:break-all; }
.collapsible-content       { position:relative; max-height:320px; overflow:hidden; }
.collapsible-content::after{ content:''; position:absolute; left:0; right:0; bottom:0; height:72px; background:linear-gradient(180deg, rgba(18,18,18,0) 0%, rgba(18,18,18,.95) 100%); pointer-events:none; }
.tool-call-block           { border-top:1px solid rgba(255,255,255,.08); padding-top:12px; }
.tool-call-item            { background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.08); border-radius:8px; padding:10px; }
.tool-pre                  { margin:0; white-space:pre-wrap; word-break:break-word; font-size:.8rem; line-height:1.55; background:rgba(0,0,0,.28); border-radius:6px; padding:.7em .8em; overflow-x:auto; }
.collapsible-pre           { max-height:220px; overflow:hidden; }
</style>
