<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue'
import { marked } from 'marked'
import { api } from '@/api/index'

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
function toggleTts() {
  // 切换 TTS 开关时，停止当前正在播放的语音
  if (ttsEnabled.value && window.speechSynthesis) {
    window.speechSynthesis.cancel()
  }
  ttsEnabled.value = !ttsEnabled.value
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
      let content = current.content || ''
      let postContent = ''
      let createdAt = current.created_at
      let cursor = index + 1
      let seqIndex = 0

      while (cursor < source.length) {
        const next = source[cursor]
        if (next.role === 'tool') {
          // 尝试匹配对应的 tool_call，如果后端没存 id，则按顺序绑定
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

async function loadSessions() {
  try {
    const d = await api.get<any>('/api/v1/ai/sessions')
    const list = d.data ?? d
    // 如果存在未发消息的新建会话占位副产品，保留在列表里
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
  messages.value.push(userMsg)
  sending.value = true

  // 使用 reactive 包装，确保闭包内的修改能触发 Vue 响应式更新
  const assistantMsg = reactive<Message>({ role: 'assistant', content: '', post_content: '' })
  messages.value.push(assistantMsg as any)
  await nextTick(); scrollBottom()

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

    let isNewSession = !currentSession.value || currentSession.value === -1
    let sessionId = currentSession.value === -1 ? null : currentSession.value
    let buffer = '' // 添加缓冲区
    
    // 用于打字机效果的队列
    let typeQueue = ''
    let typeInterval: any = null

    const startTypewriter = () => {
      if (typeInterval) return
      typeInterval = setInterval(() => {
        if (typeQueue.length > 0) {
          // 根据队列长度动态输出，防止积压导致过长延迟
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
      }, 30) // 30ms 刷新频率体验最佳
    }

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
            typeQueue += parsed.content
            startTypewriter()
          }
          // 工具调用：AI 正在调用工具
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
          // 工具结果：扫描/执行完毕
          if (parsed.tool_result) {
            if (typeQueue) {
              assistantMsg.post_content = (assistantMsg.post_content || '') + typeQueue
              typeQueue = ''
            }
            if (!(assistantMsg as any).tool_results) (assistantMsg as any).tool_results = []
            // 找到最后一个 tool_call，把结果关联过去
            const lastToolCall = (assistantMsg as any).tool_calls?.slice(-1)[0]
            ;(assistantMsg as any).tool_results.push({
              name: lastToolCall?.name || 'tool',
              tool_call_id: lastToolCall?.id,
              content: parsed.tool_result,
            })
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

    // 语音播报
    speak(assistantMsg.content)
  } catch(e: unknown) {
    assistantMsg.content = `⚠️ ${e instanceof Error ? e.message : '请求失败'}`
  }
  sending.value = false
}

function newChat() {
  messages.value = []
  currentSession.value = -1
  // 移除旧的未发消息的占位对话，避免堆积
  sessions.value = sessions.value.filter(s => s.id !== -1)
  sessions.value.unshift({
    id: -1,
    title: '新对话',
    created_at: new Date().toLocaleString()
  })
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
  <div class="ai-chat-layout premium-theme">
    <!-- Sidebar -->
    <aside class="ai-sidebar">
      <div class="sidebar-header">
        <h2 class="sidebar-title">
          <v-icon size="20" class="mr-2">mdi-forum</v-icon>
          会话记录
        </h2>
        <button class="new-chat-btn" @click="newChat" title="新对话">
          <v-icon size="20">mdi-plus</v-icon>
        </button>
      </div>
      
      <div class="session-list">
        <div v-if="!sessions.length" class="empty-sessions">
          暂无历史会话
        </div>
        <div
          v-for="s in sessions"
          :key="s.id"
          class="session-item"
          :class="{ 'session-active': currentSession === s.id }"
          @click="loadMessages(s.id)"
        >
          <div class="session-info">
            <div class="session-title">{{ s.title || `会话 #${s.id}` }}</div>
            <div class="session-time">{{ s.created_at?.slice(0,16) }}</div>
          </div>
          <button class="delete-btn" @click.stop="deleteSession(s.id)">
            <v-icon size="16">mdi-trash-can-outline</v-icon>
          </button>
        </div>
      </div>
    </aside>

    <!-- Main Chat Window -->
    <main class="ai-main">
      <div ref="chatBox" class="messages-area">
        <div class="chat-container">
          <!-- Loading State -->
          <div v-if="loading" class="loading-state">
            <div class="spinner"></div>
            <span>加载对话中...</span>
          </div>

          <!-- Empty State -->
          <div v-else-if="!messages.length" class="empty-state">
            <div class="empty-icon-wrap">
              <v-icon size="48" class="empty-icon">mdi-robot-outline</v-icon>
            </div>
            <h3 class="empty-title">玄枢 AI 助手</h3>
            <p class="empty-desc">输入指令开始对话，支持自然语言触发扫描与分析</p>
          </div>

          <!-- Message List -->
          <div v-else class="message-list">
            <div
              v-for="(msg, i) in messages"
              :key="messageKey(msg, i)"
              class="message-wrapper"
              :class="msg.role === 'user' ? 'is-user' : 'is-assistant'"
            >
              <div class="message-avatar" v-if="msg.role === 'assistant'">
                <v-icon size="22">mdi-robot-outline</v-icon>
              </div>

              <div class="message-content-wrapper">
                <div class="message-bubble">
                  <!-- User Message -->
                  <div v-if="msg.role === 'user'" class="user-text">
                    {{ msg.content }}
                  </div>
                  
                  <!-- Assistant Message -->
                  <template v-else>
                    <div
                      v-if="!msg.content && !msg.post_content && !msg.tool_calls?.length && !msg.tool_results?.length && sending"
                      class="assistant-loading"
                      aria-live="polite"
                    >
                      <span class="assistant-loading-text">思考中...</span>
                      <span class="assistant-loading-dots" aria-hidden="true">
                        <i></i><i></i><i></i>
                      </span>
                    </div>

                    <div
                      v-else-if="msg.content"
                      class="md-body"
                      v-html="renderMd(msg.content)"
                    />
                    
                    <!-- Merged Tool Calls and Results -->
                    <details v-if="msg.tool_calls?.length || msg.tool_results?.length" class="tool-section my-3">
                      <summary class="tool-header" :class="{ success: msg.tool_results?.length && msg.tool_results.length >= (msg.tool_calls?.length || 0) }">
                        <div class="d-flex align-center" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                          <v-icon size="14" class="mr-1">
                            {{ (msg.tool_calls?.length && !msg.tool_results?.length) ? 'mdi-wrench-outline' : 'mdi-check-circle-outline' }}
                          </v-icon>
                          <span class="tool-title" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 400px;">
                            工具: {{ (msg.tool_calls || msg.tool_results || []).map((t: any) => t.name || t.function?.name || 'unknown_tool').join(', ') }}
                          </span>
                        </div>
                        <v-icon size="16" class="expand-icon">mdi-chevron-down</v-icon>
                      </summary>
                      <div class="tool-content">
                        <!-- When we have Tool Calls -->
                        <template v-if="msg.tool_calls?.length">
                          <div
                            v-for="toolCall in msg.tool_calls"
                            :key="toolCall.id"
                            class="tool-card"
                          >
                            <div class="tool-name d-flex align-center justify-space-between">
                              <span><v-icon size="14" class="mr-1">mdi-api</v-icon> {{ toolCall.name || toolCall.function?.name }}</span>
                              <v-icon size="14" v-if="msg.tool_results?.find(r => (r.tool_call_id && r.tool_call_id === toolCall.id) || r.name === (toolCall.name || toolCall.function?.name))" color="#10b981">mdi-check</v-icon>
                              <v-progress-circular v-else indeterminate size="12" width="2" color="#c4b5fd" />
                            </div>
                            
                            <div class="code-label">输入参数</div>
                            <pre class="tool-code">{{ formatJson(toolCall.arguments || toolCall.function?.arguments) }}</pre>

                            <!-- Corresponding Result -->
                            <template v-if="msg.tool_results?.find(r => (r.tool_call_id && r.tool_call_id === toolCall.id) || r.name === (toolCall.name || toolCall.function?.name))">
                              <div class="code-label result-label mt-2">返回结果</div>
                              <pre class="tool-code result-code">{{ formatToolResult(msg.tool_results.find(r => (r.tool_call_id && r.tool_call_id === toolCall.id) || r.name === (toolCall.name || toolCall.function?.name))!.content) }}</pre>
                            </template>
                          </div>
                        </template>

                        <!-- Fallback: Only Tool Results -->
                        <template v-else-if="msg.tool_results?.length">
                          <div
                            v-for="(toolResult, toolIndex) in msg.tool_results"
                            :key="toolResultKey(messageKey(msg, i), toolResult, toolIndex)"
                            class="tool-card result-card"
                          >
                            <div class="tool-name"><v-icon size="14" class="mr-1">mdi-api</v-icon> {{ toolResult.name || 'unknown_tool' }}</div>
                            <div class="code-label result-label">返回结果</div>
                            <pre class="tool-code result-code">{{ formatToolResult(toolResult.content) }}</pre>
                          </div>
                        </template>
                      </div>
                    </details>
                    
                    <!-- Post Tool Message Content -->
                    <div
                      v-if="msg.post_content"
                      class="md-body mt-2"
                      v-html="renderMd(msg.post_content)"
                    />
                  </template>
                </div>
              </div>

              <div class="message-avatar" v-if="msg.role === 'user'">
                <v-icon size="22">mdi-account</v-icon>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Input Area (Prompt Input) -->
      <div class="input-area-wrapper">
        <div class="chat-container">
          <div class="prompt-input-container">
            <button 
              class="action-btn stt-btn"
              :class="{ 'is-listening': listening }"
              :title="recognition ? (listening ? '停止录音' : '语音输入') : '浏览器不支持语音识别'"
              :disabled="!recognition"
              @click="toggleListen"
            >
              <v-icon size="22">{{ listening ? 'mdi-microphone' : 'mdi-microphone-off' }}</v-icon>
              <div v-if="listening" class="pulse-ring"></div>
            </button>
            
            <textarea
              v-model="input"
              class="prompt-textarea"
              placeholder="何事相询？ (Enter 发送，Shift+Enter 换行)"
              rows="1"
              :disabled="sending"
              @keydown.enter.exact.prevent="send"
              @keydown.enter.shift.stop
            ></textarea>

            <div class="action-group">
              <button 
                class="action-btn tts-btn" 
                :class="{ 'active': ttsEnabled }"
                @click="toggleTts"
                title="AI 语音播报"
              >
                <v-icon size="20">{{ ttsEnabled ? 'mdi-volume-high' : 'mdi-volume-off' }}</v-icon>
              </button>
              
              <button 
                class="action-btn send-btn" 
                :class="{ 'sending': sending, 'disabled': !input.trim() }"
                @click="send" 
                :disabled="sending || !input.trim()"
              >
                <v-icon v-if="!sending" size="20">mdi-send</v-icon>
                <v-progress-circular v-else indeterminate size="20" width="2" color="white" />
              </button>
            </div>
          </div>
          <div class="input-footer">AI 生成的内容仅供参考，请谨慎验证。</div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
/* ───────────── PREMIUM THEME TOKENS ───────────── */
.premium-theme {
  --bg-app: #0f1115;
  --bg-sidebar: rgba(22, 24, 29, 0.7);
  --bg-chat: #0a0c10;
  --bg-bubble-user: linear-gradient(135deg, #2563eb, #0ea5e9);
  --bg-bubble-ai: rgba(30, 33, 40, 0.85);
  --bg-input: rgba(30, 33, 40, 0.6);
  --border-color: rgba(255, 255, 255, 0.08);
  --border-light: rgba(255, 255, 255, 0.05);
  --text-main: #f8fafc;
  --text-muted: #94a3b8;
  --accent: #38bdf8;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-xl: 24px;
}

/* ───────────── LAYOUT ───────────── */
.ai-chat-layout {
  display: flex;
  height: calc(100vh - 64px);
  background-color: var(--bg-app);
  color: var(--text-main);
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  overflow: hidden;
}

/* ───────────── SIDEBAR ───────────── */
.ai-sidebar {
  width: 280px;
  flex-shrink: 0;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  z-index: 10;
}

.sidebar-header {
  padding: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border-light);
}

.sidebar-title {
  font-size: 1rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  margin: 0;
  opacity: 0.9;
}

.new-chat-btn {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-color);
  color: var(--text-main);
  height: 36px;
  width: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.new-chat-btn:hover {
  background: var(--text-main);
  color: #000;
  transform: scale(1.05);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.session-list::-webkit-scrollbar { width: 4px; }
.session-list::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 4px; }

.empty-sessions {
  text-align: center;
  padding: 30px 0;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  cursor: pointer;
  background: transparent;
  transition: all 0.2s ease;
  border: 1px solid transparent;
}

.session-item:hover {
  background: rgba(255, 255, 255, 0.03);
}

.session-active {
  background: rgba(56, 189, 248, 0.1);
  border-color: rgba(56, 189, 248, 0.2);
}

.session-info {
  overflow: hidden;
}

.session-title {
  font-weight: 500;
  font-size: 0.9rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.session-active .session-title { color: var(--accent); }

.session-time {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.delete-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  opacity: 0;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s;
}

.session-item:hover .delete-btn { opacity: 1; }
.delete-btn:hover { color: #f43f5e; background: rgba(244, 63, 94, 0.1); }

/* ───────────── MAIN DEFAULT ───────────── */
.ai-main {
  flex: 1;
  background: var(--bg-chat);
  display: flex;
  flex-direction: column;
  position: relative;
}

.chat-container {
  max-width: 1040px;
  width: 100%;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  width: 100%;
  padding-bottom: 140px; /* Space for absolute input area */
  scroll-behavior: smooth;
}

.messages-area .chat-container {
  padding: 24px 14px 20px;
}

.messages-area::-webkit-scrollbar { width: 6px; }
.messages-area::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.15); border-radius: 4px; }

/* ───────────── EMPTY STATE ───────────── */
.empty-state {
  margin: auto;
  text-align: center;
  animation: fade-in 0.8s ease-out;
}

.empty-icon-wrap {
  width: 80px;
  height: 80px;
  margin: 0 auto 20px;
  background: linear-gradient(135deg, rgba(255,255,255,0.05), rgba(255,255,255,0));
  border: 1px solid var(--border-light);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  box-shadow: 0 8px 32px rgba(0,0,0,0.2);
}

.empty-title {
  font-size: 1.5rem;
  font-weight: 600;
  margin-bottom: 8px;
  letter-spacing: 0.5px;
}

.empty-desc {
  color: var(--text-muted);
  font-size: 0.95rem;
  max-width: 300px;
  margin: 0 auto;
  line-height: 1.5;
}

/* ───────────── MESSAGE LIST ───────────── */
.message-list {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.message-wrapper {
  display: flex;
  gap: 16px;
  animation: slide-up 0.4s ease-out backwards;
}

.message-wrapper.is-user { justify-content: flex-end; }

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--bg-sidebar);
  border: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--text-muted);
}

.is-user .message-avatar {
  background: linear-gradient(135deg, #475569, #334155);
  color: #fff;
}

.message-content-wrapper {
  max-width: 86%;
}

.message-bubble {
  padding: 16px 20px;
  border-radius: var(--radius-lg);
  font-size: 0.95rem;
  line-height: 1.6;
  box-shadow: 0 4px 20px rgba(0,0,0,0.1);
}

.is-user .message-bubble {
  background: var(--bg-bubble-user);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.is-assistant .message-bubble {
  background: var(--bg-bubble-ai);
  border: 1px solid var(--border-color);
  border-bottom-left-radius: 4px;
}

.user-text {
  white-space: pre-wrap;
}

/* ───────────── TOOLS ───────────── */
details.tool-section {
  background: rgba(0,0,0,0.25);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
  overflow: hidden;
  margin-top: 12px;
  transition: all 0.3s ease;
}

.tool-header {
  padding: 10px 14px;
  background: rgba(255,255,255,0.02);
  border-bottom: 1px solid transparent;
  font-size: 0.8rem;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  user-select: none;
  list-style: none; /* Hide default arrow */
  transition: background 0.2s;
}

.tool-header::-webkit-details-marker {
  display: none;
}

.tool-header:hover {
  background: rgba(255,255,255,0.05);
}

details[open] .tool-header {
  border-bottom-color: var(--border-light);
}

.tool-header .expand-icon {
  transition: transform 0.3s ease;
}

details[open] .tool-header .expand-icon {
  transform: rotate(180deg);
}

.tool-header.success { color: #10b981; }

.tool-content {
  animation: slide-down 0.3s ease-out;
}

.tool-card {
  padding: 12px 14px;
  border-bottom: 1px solid rgba(255,255,255,0.03);
}

.tool-card:last-child { border-bottom: none; }

.tool-name {
  font-family: monospace;
  font-size: 0.85rem;
  font-weight: 600;
  color: #c4b5fd;
  margin-bottom: 8px;
}

.code-label {
  font-size: 0.7rem;
  color: #94a3b8;
  margin-bottom: 4px;
  margin-left: 2px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.result-label { color: #34d399; }

.tool-code {
  margin: 0;
  padding: 12px;
  background: rgba(0,0,0,0.4);
  border-radius: 6px;
  font-size: 0.8rem;
  overflow-x: auto;
  color: #f8fafc;
  border-left: 2px solid #6366f1;
}

.result-code {
  color: #a7f3d0;
  border-left-color: #10b981;
}

/* ───────────── INPUT AREA ───────────── */
.input-area-wrapper {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding-bottom: 12px;
  background: linear-gradient(to top, var(--bg-chat) 75%, transparent);
  pointer-events: none;
  display: flex;
  justify-content: center;
}

.input-area-wrapper .chat-container {
  padding: 24px 14px 0;
}

.prompt-input-container {
  pointer-events: auto;
  background: var(--bg-input);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl);
  padding: 8px;
  display: flex;
  align-items: flex-end;
  gap: 12px;
  box-shadow: 0 12px 40px rgba(0,0,0,0.4);
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}

.prompt-input-container:focus-within {
  border-color: rgba(56, 189, 248, 0.4);
  box-shadow: 0 12px 40px rgba(0,0,0,0.4), 0 0 0 2px rgba(56, 189, 248, 0.1);
}

.prompt-textarea {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--text-main);
  font-family: inherit;
  font-size: 0.95rem;
  line-height: 1.5;
  padding: 12px 0;
  resize: none;
  max-height: 150px;
  outline: none;
}

.prompt-textarea::placeholder {
  color: rgba(255, 255, 255, 0.3);
}

.action-group {
  display: flex;
  gap: 6px;
  padding: 6px 4px;
}

.action-btn {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  position: relative;
}

.action-btn:hover:not(.disabled) {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-main);
}

.action-btn.active {
  color: var(--accent);
}

.send-btn {
  background: var(--text-main);
  color: #000;
}

.send-btn:hover:not(.disabled) {
  background: #fff;
  color: #000;
  transform: scale(1.05);
}

.send-btn.disabled {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.3);
  cursor: not-allowed;
}

.stt-btn { margin-bottom: 6px; margin-left: 6px; }

.is-listening { color: #f43f5e; }
.pulse-ring {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  border-radius: 50%;
  border: 2px solid #f43f5e;
  animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;
}

.input-footer {
  text-align: center;
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.2);
  margin-top: 12px;
  pointer-events: auto;
}

/* ───────────── ANIMATIONS ───────────── */
@keyframes slide-up {
  from { opacity: 0; transform: translateY(15px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes ping {
  75%, 100% { transform: scale(1.5); opacity: 0; }
}

@keyframes slide-down {
  from { opacity: 0; transform: translateY(-5px); }
  to { opacity: 1; transform: translateY(0); }
}

 .loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-muted);
  font-size: 0.9rem;
  gap: 16px;
}

.assistant-loading {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 28px;
  color: var(--text-muted);
}

.assistant-loading-text {
  font-size: 0.92rem;
  line-height: 1.5;
}

.assistant-loading-dots {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.assistant-loading-dots i {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: rgba(196, 181, 253, 0.95);
  display: block;
  animation: dot-bounce 1s ease-in-out infinite;
}

.assistant-loading-dots i:nth-child(2) {
  animation-delay: 0.15s;
}

.assistant-loading-dots i:nth-child(3) {
  animation-delay: 0.3s;
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid rgba(255,255,255,0.1);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes dot-bounce {
  0%, 80%, 100% {
    transform: translateY(0);
    opacity: 0.45;
  }
  40% {
    transform: translateY(-4px);
    opacity: 1;
  }
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ───────────── MARKDOWN FIXES ───────────── */
.md-body { overflow-wrap: anywhere; word-break: break-word; }
.md-body :deep(p) { margin: 0.5rem 0; }
.md-body :deep(pre) { background: rgba(0,0,0,0.4); border: 1px solid var(--border-light); border-radius: 8px; padding: 12px; overflow-x: auto; font-size: 0.85rem; margin: 12px 0; }
.md-body :deep(code) { background: rgba(0,0,0,0.3); border-radius: 4px; padding: 2px 6px; font-size: 0.85rem; color: #e2e8f0; }
.md-body :deep(ul), .md-body :deep(ol) { padding-left: 1.5em; margin: 0.5rem 0; }
.md-body :deep(blockquote) { border-left: 3px solid var(--accent); padding-left: 1em; opacity: 0.8; margin: 0.5rem 0; background: rgba(56, 189, 248, 0.05); padding: 8px 12px; border-radius: 0 6px 6px 0; }
.md-body :deep(h1), .md-body :deep(h2), .md-body :deep(h3) { margin: 1rem 0 0.5rem; font-size: 1.1rem; color: #fff; font-weight: 600; }
.md-body :deep(table) { border-collapse: collapse; width: 100%; font-size: 0.85rem; margin: 12px 0; border: 1px solid var(--border-light); border-radius: 8px; overflow: hidden; display: block; }
.md-body :deep(th), .md-body :deep(td) { border: 1px solid var(--border-light); padding: 8px 12px; }
.md-body :deep(th) { background: rgba(255,255,255,0.03); font-weight: 600; text-align: left; }
.md-body :deep(a) { color: var(--accent); text-decoration: none; transition: opacity 0.2s; }
.md-body :deep(a:hover) { text-decoration: underline; opacity: 0.8; }
</style>
