<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { marked } from 'marked'
import { api } from '@/api/index'

interface ToolCall {
  id: string
  type?: string
  name: string
  arguments: Record<string, unknown>
}

interface Message {
  role: 'user' | 'assistant' | 'tool'
  content: string
  created_at?: string
  name?: string
  tool_call_id?: string
  tool_calls?: ToolCall[]
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

// ── Markdown ─────────────────────────────────────────────────────────────
function renderMd(text: string): string {
  return marked.parse(text) as string
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
    messages.value = d.data ?? d
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

async function send() {
  const text = input.value.trim()
  if (!text || sending.value) return
  input.value = ''
  messages.value.push({ role: 'user', content: text })
  await nextTick(); scrollBottom()
  sending.value = true
  try {
    const body: any = { message: text }
    if (currentSession.value) body.session_id = currentSession.value
    const d = await api.post<any>('/api/v1/ai/chat', body)
    const res = d.data ?? d
    const reply = res.reply ?? res.message ?? JSON.stringify(res)
    const turnMessages = Array.isArray(res.messages) ? res.messages : [{ role: 'assistant', content: reply }]
    messages.value.push(...turnMessages)
    if (res.session_id && !currentSession.value) {
      currentSession.value = res.session_id
      await loadSessions()
    }
    speak(reply)
    await nextTick(); scrollBottom()
  } catch(e: unknown) {
    messages.value.push({ role: 'assistant', content: `⚠️ ${e instanceof Error ? e.message : '请求失败'}` })
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

onMounted(loadSessions)
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
                :key="i"
                :class="['d-flex', 'mb-4', msg.role === 'user' ? 'justify-end' : 'justify-start']"
              >
                <v-card
                  :color="msg.role === 'user' ? 'primary' : msg.role === 'tool' ? 'rgba(0,229,255,.06)' : 'surface'"
                  :style="`max-width:${msg.role === 'tool' ? '78%' : '72%'}; border:1px solid rgba(255,255,255,${msg.role==='user'?'0':'.08'})`"
                  class="pa-3"
                >
                  <div
                    v-if="msg.role === 'user'"
                    style="white-space:pre-wrap; font-size:.9rem; line-height:1.6"
                  >{{ msg.content }}</div>
                  <div
                    v-else-if="msg.role === 'assistant'"
                    class="md-body"
                    style="font-size:.9rem; line-height:1.7"
                    v-html="renderMd(msg.content)"
                  />
                  <div v-else class="tool-body">
                    <div class="text-caption text-medium-emphasis mb-2">
                      工具结果 · {{ msg.name || 'unknown_tool' }}
                    </div>
                    <pre class="tool-pre">{{ formatToolResult(msg.content) }}</pre>
                  </div>
                  <div
                    v-if="msg.role === 'assistant' && msg.tool_calls?.length"
                    class="tool-call-block mt-3"
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
                </v-card>
              </div>
              <div v-if="sending" class="d-flex justify-start mb-4">
                <v-card color="surface" class="pa-3" style="border:1px solid rgba(255,255,255,.08)">
                  <v-progress-circular indeterminate size="16" width="2" color="primary" />
                  <span class="ml-2 text-caption text-medium-emphasis">AI 正在分析中…</span>
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
              placeholder="输入指令或问题，Ctrl+Enter 发送…"
              rows="2"
              auto-grow
              max-rows="5"
              hide-details
              no-resize
              style="flex:1"
              @keydown.ctrl.enter="send"
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
.md-body :deep(p)          { margin: 0.25rem 0; }
.md-body :deep(pre)        { background: rgba(0,0,0,.35); border-radius:6px; padding:.6em .8em; overflow-x:auto; font-size:.82rem; }
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
.tool-call-block           { border-top:1px solid rgba(255,255,255,.08); padding-top:12px; }
.tool-call-item            { background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.08); border-radius:8px; padding:10px; }
.tool-pre                  { margin:0; white-space:pre-wrap; word-break:break-word; font-size:.8rem; line-height:1.55; background:rgba(0,0,0,.28); border-radius:6px; padding:.7em .8em; overflow-x:auto; }
</style>
