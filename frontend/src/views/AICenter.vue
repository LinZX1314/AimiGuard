<template>
  <div class="ai-center flex h-[calc(100vh-64px)] overflow-hidden">

    <!-- ── 左侧：会话历史 ── -->
    <aside class="sessions-sidebar w-56 shrink-0 border-r border-border bg-sidebar flex flex-col">
      <div class="flex items-center justify-between px-3.5 py-3 border-b border-border/60">
        <div class="flex items-center gap-1.5">
          <MessagesSquare class="size-3.5 text-primary/70" />
          <span class="text-[11px] font-semibold text-muted-foreground uppercase tracking-widest">历史会话</span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          class="size-6 cursor-pointer hover:bg-primary/10 hover:text-primary transition-colors"
          title="新建会话"
          @click="newSession"
        >
          <SquarePen class="size-3.5" />
        </Button>
      </div>

      <div class="flex-1 overflow-y-auto p-2 space-y-0.5">
        <div v-if="sessionsLoading" class="space-y-1.5 px-1 pt-1">
          <Skeleton v-for="i in 5" :key="i" class="h-10 w-full rounded-lg" />
        </div>
        <div v-else-if="sessions.length === 0" class="flex flex-col items-center justify-center py-12 text-center gap-2">
          <div class="size-8 rounded-full bg-muted/50 flex items-center justify-center">
            <MessageCircle class="size-4 text-muted-foreground/40" />
          </div>
          <p class="text-xs text-muted-foreground/60">暂无历史会话</p>
        </div>
        <button
          v-for="s in sessions"
          :key="s.id"
          :class="[
            'group w-full rounded-lg px-3 py-2.5 text-left transition-all duration-150',
            currentSessionId === s.id
              ? 'bg-primary/10 text-primary ring-1 ring-primary/20'
              : 'hover:bg-muted/60 text-muted-foreground hover:text-foreground',
          ]"
          @click="loadSession(s)"
        >
          <div class="flex items-start gap-2">
            <div
              class="mt-0.5 size-1.5 rounded-full shrink-0 transition-colors"
              :class="currentSessionId === s.id ? 'bg-primary' : 'bg-muted-foreground/30 group-hover:bg-muted-foreground/60'"
            />
            <div class="min-w-0 flex-1">
              <p class="truncate text-xs font-medium leading-snug">
                {{ s.context_type || 'AI 对话' }}
              </p>
              <p class="text-[10px] opacity-50 mt-0.5 tabular-nums">{{ formatTime(s.started_at) }}</p>
            </div>
          </div>
        </button>
      </div>
    </aside>

    <!-- ── 中：对话区 ── -->
    <div class="flex flex-1 flex-col min-w-0 min-h-0">

      <!-- 对话顶部 -->
      <div class="flex items-center justify-between border-b border-border/60 px-5 py-2.5 shrink-0 bg-background/80 backdrop-blur-sm">
        <div class="flex items-center gap-2.5">
          <div class="size-7 rounded-lg bg-primary/10 flex items-center justify-center ring-1 ring-primary/20">
            <BrainCircuit class="size-3.5 text-primary" />
          </div>
          <div>
            <span class="font-semibold text-sm leading-none">AI 研判助手</span>
            <div class="flex items-center gap-1.5 mt-0.5">
              <span class="inline-block size-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span class="text-[10px] text-muted-foreground">在线</span>
              <span v-if="currentSessionId" class="text-[10px] text-muted-foreground/50">· 会话 #{{ currentSessionId }}</span>
            </div>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          class="cursor-pointer text-xs gap-1.5 text-muted-foreground hover:text-foreground h-7"
          @click="newSession"
        >
          <SquarePen class="size-3" />
          新建对话
        </Button>
      </div>

      <!-- 消息列表：使用 AI Elements Conversation 组件 -->
      <Conversation class="flex-1 min-h-0 px-5 py-4">
        <!-- 空状态：使用 AI Elements ConversationEmptyState -->
        <ConversationEmptyState
          v-if="messages.length === 0 && !aiThinking"
          title="开始 AI 研判对话"
          description="询问告警分析、漏洞解读、修复建议，或引用事件 ID 进行深度分析"
        >
          <template #icon>
            <div class="size-14 rounded-2xl bg-primary/8 border border-primary/15 flex items-center justify-center mb-1">
              <BrainCircuit class="size-6 text-primary/60" />
            </div>
          </template>

          <!-- 快捷提示按钮 -->
          <div class="flex flex-wrap gap-2 justify-center mt-3">
            <button
              v-for="hint in quickHints"
              :key="hint"
              class="rounded-full border border-border/60 px-3 py-1 text-xs text-muted-foreground hover:border-primary/30 hover:text-primary hover:bg-primary/5 transition-all cursor-pointer"
              @click="fillHint(hint)"
            >
              {{ hint }}
            </button>
          </div>
        </ConversationEmptyState>

        <!-- 消息流：使用 AI Elements Message / MessageContent / MessageAvatar -->
        <div v-if="messages.length > 0 || aiThinking" class="space-y-5 pb-2">
          <TransitionGroup name="msg" tag="div" class="space-y-5">
            <Message
              v-for="(msg, idx) in messages"
              :key="idx"
              :from="msg.role"
            >
              <!-- AI 助手消息：头像在左 -->
              <MessageAvatar
                v-if="msg.role === 'assistant'"
                src=""
                name="AI"
                class="shrink-0 bg-primary/10 ring-primary/20 text-primary text-[10px]"
              />

              <div class="flex flex-col gap-1 min-w-0">
                <MessageContent
                  :class="[
                    msg.role === 'user'
                      ? 'group-[.is-user]:bg-primary group-[.is-user]:text-primary-foreground group-[.is-user]:shadow-sm'
                      : 'group-[.is-assistant]:bg-muted/50 group-[.is-assistant]:rounded-xl group-[.is-assistant]:px-4 group-[.is-assistant]:py-3 group-[.is-assistant]:border group-[.is-assistant]:border-border/50',
                  ]"
                >
                  <span class="leading-relaxed whitespace-pre-wrap">{{ msg.content }}</span>
                </MessageContent>
                <span class="text-[10px] text-muted-foreground/50 px-1 tabular-nums"
                  :class="msg.role === 'user' ? 'text-right' : 'text-left'"
                >
                  {{ formatTime(msg.created_at) }}
                </span>
              </div>

              <!-- 用户消息：头像在右 -->
              <MessageAvatar
                v-if="msg.role === 'user'"
                src=""
                name="Me"
                class="shrink-0 bg-muted ring-border/50 text-muted-foreground text-[10px]"
              />
            </Message>
          </TransitionGroup>

          <!-- AI 思考中指示器 -->
          <Transition name="thinking">
            <Message v-if="aiThinking" from="assistant">
              <MessageAvatar
                src=""
                name="AI"
                class="shrink-0 bg-primary/10 ring-primary/20 text-primary text-[10px]"
              />
              <MessageContent class="group-[.is-assistant]:bg-muted/50 group-[.is-assistant]:rounded-xl group-[.is-assistant]:px-4 group-[.is-assistant]:py-3 group-[.is-assistant]:border group-[.is-assistant]:border-border/50">
                <div class="flex items-center gap-2">
                  <BrainCircuit class="size-3.5 text-primary animate-pulse" />
                  <div class="flex gap-1">
                    <span class="size-1.5 rounded-full bg-primary/60 animate-bounce" style="animation-delay: 0ms" />
                    <span class="size-1.5 rounded-full bg-primary/60 animate-bounce" style="animation-delay: 150ms" />
                    <span class="size-1.5 rounded-full bg-primary/60 animate-bounce" style="animation-delay: 300ms" />
                  </div>
                  <span class="text-xs text-muted-foreground">AI 正在分析…</span>
                </div>
              </MessageContent>
            </Message>
          </Transition>
        </div>
      </Conversation>

      <!-- 输入区：使用 AI Elements PromptInput 组件 -->
      <div class="shrink-0 border-t border-border/60 px-4 py-3 bg-background/80 backdrop-blur-sm">
        <PromptInput
          class="rounded-xl border-border/60 shadow-sm"
          @submit="handlePromptSubmit"
        >
          <PromptInputTextarea
            placeholder="询问告警分析、漏洞解读、修复建议，或输入事件 ID…"
            :disabled="aiThinking"
            class="min-h-10 max-h-36 text-sm placeholder:text-muted-foreground/50"
          />
          <PromptInputFooter class="px-2 pb-2">
            <span class="text-[10px] text-muted-foreground/50 select-none">
              Enter 发送 · Shift+Enter 换行 · 可引用事件 ID
            </span>
            <div class="flex items-center gap-1.5">
              <!-- TTS 麦克风按钮 -->
              <button
                class="relative size-8 rounded-full flex items-center justify-center transition-all duration-200 cursor-pointer"
                :class="[
                  ttsRecording
                    ? 'bg-red-500/15 text-red-400 ring-1 ring-red-500/30 hover:bg-red-500/25'
                    : 'bg-muted/60 text-muted-foreground hover:bg-primary/10 hover:text-primary',
                ]"
                :title="ttsRecording ? '停止录音' : '语音输入'"
                @click="toggleTTSRecording"
              >
                <!-- 麦克风图标 -->
                <Mic v-if="!ttsRecording" class="size-3.5" />
                <!-- 录音中：声音波浪动画 -->
                <div v-else class="flex items-center gap-[2px]">
                  <span class="tts-wave" style="animation-delay: 0ms" />
                  <span class="tts-wave" style="animation-delay: 150ms" />
                  <span class="tts-wave" style="animation-delay: 300ms" />
                  <span class="tts-wave" style="animation-delay: 450ms" />
                </div>
                <!-- 录音脉冲光圈 -->
                <span
                  v-if="ttsRecording"
                  class="absolute inset-0 rounded-full border-2 border-red-400/40 animate-ping pointer-events-none"
                />
              </button>
              <PromptInputSubmit
                :status="aiThinking ? 'submitted' : undefined"
                :disabled="aiThinking"
                class="cursor-pointer"
              />
            </div>
          </PromptInputFooter>
        </PromptInput>
      </div>
    </div>

    <!-- 麦克风权限弹窗 -->
    <Dialog :open="showMicPermissionDialog" @update:open="showMicPermissionDialog = $event">
      <DialogContent class="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2">
            <Mic class="size-4 text-primary" />
            需要麦克风权限
          </DialogTitle>
          <DialogDescription>
            语音输入功能需要访问您的麦克风。请在浏览器弹出的权限请求中点击「允许」，或在浏览器设置中手动开启麦克风权限。
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" size="sm" class="cursor-pointer" @click="showMicPermissionDialog = false">
            我知道了
          </Button>
          <Button size="sm" class="cursor-pointer" @click="retryMicPermission">
            重新授权
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- ── 右侧：报告 + TTS ── -->
    <aside class="w-64 shrink-0 border-l border-border/60 flex flex-col bg-sidebar">

      <!-- 标签切换 -->
      <div class="flex border-b border-border/60 shrink-0">
        <button
          v-for="tab in rightTabs"
          :key="tab.key"
          :class="[
            'flex-1 py-2.5 text-xs font-medium text-center transition-all duration-150',
            rightTab === tab.key
              ? 'text-primary border-b-2 border-primary'
              : 'text-muted-foreground border-b-2 border-transparent hover:text-foreground hover:border-border',
          ]"
          @click="rightTab = tab.key"
        >
          <div class="flex items-center justify-center gap-1.5">
            <component :is="tab.icon" class="size-3" />
            {{ tab.label }}
          </div>
        </button>
      </div>

      <!-- 报告面板 -->
      <div v-show="rightTab === 'report'" class="flex flex-col flex-1 min-h-0">
        <div class="px-3 py-3 border-b border-border/60 space-y-2 shrink-0">
          <div class="grid grid-cols-2 gap-1.5">
            <Button
              variant="outline"
              size="sm"
              class="cursor-pointer text-[11px] gap-1 h-7 hover:border-primary/30 hover:text-primary"
              :disabled="reportGenerating"
              @click="generateReport('daily')"
            >
              <FileText class="size-3" /> 日报
            </Button>
            <Button
              variant="outline"
              size="sm"
              class="cursor-pointer text-[11px] gap-1 h-7 hover:border-primary/30 hover:text-primary"
              :disabled="reportGenerating"
              @click="generateReport('weekly')"
            >
              <FileText class="size-3" /> 周报
            </Button>
          </div>
          <Button
            variant="outline"
            size="sm"
            class="cursor-pointer text-[11px] gap-1 w-full h-7 hover:border-primary/30 hover:text-primary"
            :disabled="reportGenerating"
            @click="generateReport('scan')"
          >
            <ScanLine class="size-3" /> 扫描报告
          </Button>
          <Transition name="fade">
            <p
              v-if="reportMsg"
              class="text-[10px] text-center py-0.5 rounded"
              :class="reportMsgOk ? 'text-emerald-400' : 'text-destructive'"
            >
              {{ reportMsg }}
            </p>
            <p v-else-if="reportGenerating" class="text-[10px] text-muted-foreground text-center animate-pulse">
              生成中…
            </p>
          </Transition>
        </div>

        <div class="flex-1 overflow-y-auto p-2 space-y-1.5">
          <div v-if="reportsLoading" class="space-y-1.5">
            <Skeleton v-for="i in 3" :key="i" class="h-16 w-full rounded-lg" />
          </div>
          <div
            v-else-if="reports.length === 0"
            class="flex flex-col items-center justify-center py-10 gap-2"
          >
            <FileText class="size-6 text-muted-foreground/20" />
            <p class="text-[11px] text-muted-foreground/50">暂无报告</p>
          </div>
          <div
            v-for="r in reports"
            :key="r.id"
            class="rounded-lg border border-border/50 p-2.5 space-y-1.5 cursor-pointer hover:border-primary/30 hover:bg-muted/30 transition-all"
            @click="selectedReport = selectedReport?.id === r.id ? null : r"
          >
            <div class="flex items-center justify-between gap-1">
              <Badge variant="outline" class="text-[9px] h-4 capitalize px-1.5">{{ r.report_type }}</Badge>
              <span class="text-[10px] text-muted-foreground tabular-nums">{{ formatDate(r.created_at) }}</span>
            </div>
            <p class="text-[11px] text-muted-foreground/80 line-clamp-2 leading-relaxed">{{ r.summary }}</p>
            <Transition name="expand">
              <div
                v-if="selectedReport?.id === r.id"
                class="text-[10px] text-muted-foreground/60 pt-1.5 border-t border-border/50 space-y-1 font-mono"
              >
                <p>trace: {{ r.trace_id?.slice(0, 16) }}</p>
                <p class="truncate">path: {{ r.detail_path }}</p>
              </div>
            </Transition>
          </div>
        </div>
      </div>

      <!-- TTS 面板 -->
      <div v-show="rightTab === 'tts'" class="flex flex-col flex-1 min-h-0">
        <div class="px-3 py-3 border-b border-border/60 space-y-2 shrink-0">
          <textarea
            v-model="ttsText"
            rows="3"
            placeholder="输入文本，将其转为语音…"
            class="w-full rounded-lg border border-border/60 bg-background/50 px-3 py-2 text-xs placeholder:text-muted-foreground/50 resize-none focus:outline-none focus:ring-1 focus:ring-primary/40 focus:border-primary/30 transition-all"
          />
          <Button
            size="sm"
            class="cursor-pointer text-xs gap-1.5 w-full h-7"
            :disabled="!ttsText.trim() || ttsCreating"
            @click="createTTS"
          >
            <Volume2 class="size-3" />
            {{ ttsCreating ? '创建中…' : '创建 TTS 任务' }}
          </Button>
          <Transition name="fade">
            <p
              v-if="ttsMsg"
              class="text-[10px] text-center"
              :class="ttsMsgOk ? 'text-emerald-400' : 'text-destructive'"
            >
              {{ ttsMsg }}
            </p>
          </Transition>
        </div>

        <div class="flex-1 overflow-y-auto p-2 space-y-1.5">
          <div v-if="ttsLoading" class="space-y-1.5">
            <Skeleton v-for="i in 3" :key="i" class="h-12 w-full rounded-lg" />
          </div>
          <div
            v-else-if="ttsTasks.length === 0"
            class="flex flex-col items-center justify-center py-10 gap-2"
          >
            <Volume2 class="size-6 text-muted-foreground/20" />
            <p class="text-[11px] text-muted-foreground/50">暂无 TTS 任务</p>
          </div>
          <div
            v-for="t in ttsTasks"
            :key="t.id"
            class="rounded-lg border border-border/50 p-2.5 space-y-1.5"
          >
            <div class="flex items-center justify-between gap-1">
              <span class="text-[10px] text-muted-foreground/60 tabular-nums">#{{ t.id }}</span>
              <Badge class="text-[9px] h-4 px-1.5" :class="ttsStateColor(t.state)">
                {{ t.state }}
              </Badge>
            </div>
            <p class="text-[11px] text-muted-foreground/80 line-clamp-2">{{ t.text_preview }}</p>
            <div v-if="t.state === 'PENDING'" class="pt-0.5">
              <Button
                variant="outline"
                size="sm"
                class="cursor-pointer text-[10px] h-5 w-full gap-1 hover:border-primary/30 hover:text-primary"
                @click="processTTS(t.id)"
              >
                <Play class="size-2.5" /> 模拟处理
              </Button>
            </div>
            <div v-if="t.audio_path" class="text-[10px] text-emerald-400/80 truncate font-mono">
              {{ t.audio_path }}
            </div>
          </div>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { aiApi } from '@/api/ai'
import { reportApi } from '@/api/report'
import { ttsApi, type TTSTask } from '@/api/tts'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { Conversation, ConversationEmptyState } from '@/components/ai-elements/conversation'
import { Message, MessageContent, MessageAvatar } from '@/components/ai-elements/message'
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputSubmit,
  PromptInputFooter,
  type PromptInputMessage,
} from '@/components/ai-elements/prompt-input'
import {
  BrainCircuit,
  FileText,
  MessageCircle,
  MessagesSquare,
  Mic,
  Play,
  ScanLine,
  SquarePen,
  Volume2,
} from 'lucide-vue-next'

interface Message_ {
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

interface Session {
  id: number
  context_type: string | null
  started_at: string
  expires_at: string | null
}

interface Report {
  id: number
  report_type: string
  summary: string
  detail_path: string | null
  trace_id: string | null
  created_at: string
}

const quickHints = [
  '分析最近告警',
  '解读扫描结果',
  '给出修复建议',
  '威胁溯源分析',
]

const rightTabs = [
  { key: 'report', label: '报告', icon: FileText },
  { key: 'tts', label: 'TTS', icon: Volume2 },
]
const rightTab = ref('report')

// ── 状态 ──
const messages = ref<Message_[]>([])
const aiThinking = ref(false)
const currentSessionId = ref<number | null>(null)

const sessions = ref<Session[]>([])
const sessionsLoading = ref(false)

const reports = ref<Report[]>([])
const reportsLoading = ref(false)
const reportGenerating = ref(false)
const reportMsg = ref('')
const reportMsgOk = ref(true)
const selectedReport = ref<Report | null>(null)

const ttsText = ref('')
const ttsCreating = ref(false)
const ttsMsg = ref('')
const ttsMsgOk = ref(true)
const ttsTasks = ref<TTSTask[]>([])
const ttsLoading = ref(false)
const ttsRecording = ref(false)
const showMicPermissionDialog = ref(false)

// ── 快捷提示 ──
const fillHint = (hint: string) => {
  // PromptInput 内部管理文本状态，无法直接注入
  // 降级为直接发送
  sendMessage(hint)
}

// ── 会话管理 ──
const newSession = () => {
  currentSessionId.value = null
  messages.value = []
}

const loadSessions = async () => {
  sessionsLoading.value = true
  try {
    const data: any = await aiApi.getSessions()
    sessions.value = Array.isArray(data) ? data : (data?.data ?? [])
  } catch {
    sessions.value = []
  } finally {
    sessionsLoading.value = false
  }
}

const loadSession = async (s: Session) => {
  currentSessionId.value = s.id
  messages.value = []
  try {
    const msgs: any = await aiApi.getSessionMessages(s.id)
    const list = Array.isArray(msgs) ? msgs : (msgs?.data ?? [])
    messages.value = list.map((m: any) => ({
      role: m.role,
      content: m.content,
      created_at: m.created_at,
    }))
  } catch {
    messages.value = []
  }
}

// ── 发送消息 ──
const sendMessage = async (text: string) => {
  if (!text.trim() || aiThinking.value) return

  const now = new Date().toISOString()
  messages.value.push({ role: 'user', content: text, created_at: now })
  aiThinking.value = true

  try {
    const res: any = await aiApi.chat(text, currentSessionId.value ?? undefined)
    const data = res?.data ?? res
    const sessionId = data?.session_id ?? res?.session_id
    const reply = data?.message ?? res?.message ?? '（无响应）'

    if (sessionId && !currentSessionId.value) {
      currentSessionId.value = sessionId
      await loadSessions()
    }

    messages.value.push({ role: 'assistant', content: reply, created_at: new Date().toISOString() })
  } catch {
    messages.value.push({
      role: 'assistant',
      content: '抱歉，服务暂时不可用，请稍后重试。',
      created_at: new Date().toISOString(),
    })
  } finally {
    aiThinking.value = false
  }
}

// PromptInput submit 事件处理
const handlePromptSubmit = (payload: PromptInputMessage) => {
  sendMessage(payload.text)
}

// ── 报告 ──
const loadReports = async () => {
  reportsLoading.value = true
  try {
    const data: any = await reportApi.getReports()
    const list = data?.items ?? (Array.isArray(data) ? data : (data?.data ?? []))
    reports.value = Array.isArray(list) ? list : []
  } catch {
    reports.value = []
  } finally {
    reportsLoading.value = false
  }
}

const generateReport = async (type: string) => {
  reportGenerating.value = true
  reportMsg.value = ''
  try {
    await reportApi.generate(type)
    reportMsg.value = '报告已生成'
    reportMsgOk.value = true
    await loadReports()
  } catch {
    reportMsg.value = '生成失败'
    reportMsgOk.value = false
  } finally {
    reportGenerating.value = false
    setTimeout(() => { reportMsg.value = '' }, 3000)
  }
}

// ── TTS ──
const loadTTS = async () => {
  ttsLoading.value = true
  try {
    const data = await ttsApi.listTasks({ page: 1, page_size: 20 })
    ttsTasks.value = data?.items ?? []
  } catch {
    ttsTasks.value = []
  } finally {
    ttsLoading.value = false
  }
}

const createTTS = async () => {
  const text = ttsText.value.trim()
  if (!text) return
  ttsCreating.value = true
  ttsMsg.value = ''
  try {
    await ttsApi.createTask(text)
    ttsText.value = ''
    ttsMsgOk.value = true
    ttsMsg.value = 'TTS 任务已创建'
    await loadTTS()
  } catch {
    ttsMsgOk.value = false
    ttsMsg.value = '创建失败'
  } finally {
    ttsCreating.value = false
    setTimeout(() => { ttsMsg.value = '' }, 3000)
  }
}

const processTTS = async (taskId: number) => {
  try {
    await ttsApi.processTask(taskId)
    await loadTTS()
  } catch { /* ignore */ }
}

// ── TTS 录音按钮 ──
const toggleTTSRecording = async () => {
  if (ttsRecording.value) {
    ttsRecording.value = false
    return
  }
  // 检查麦克风权限
  try {
    const permStatus = await navigator.permissions.query({ name: 'microphone' as PermissionName })
    if (permStatus.state === 'denied') {
      showMicPermissionDialog.value = true
      return
    }
  } catch {
    // permissions API 不支持时直接尝试获取
  }
  try {
    await navigator.mediaDevices.getUserMedia({ audio: true })
    ttsRecording.value = true
  } catch {
    showMicPermissionDialog.value = true
  }
}

const retryMicPermission = async () => {
  showMicPermissionDialog.value = false
  try {
    await navigator.mediaDevices.getUserMedia({ audio: true })
    ttsRecording.value = true
  } catch {
    showMicPermissionDialog.value = true
  }
}

const ttsStateColor = (s: string) => {
  const m: Record<string, string> = {
    PENDING: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    PROCESSING: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    SUCCESS: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    FAILED: 'bg-destructive/15 text-destructive border-destructive/30',
  }
  return m[s] || 'bg-muted text-muted-foreground'
}

// ── 格式化 ──
const formatTime = (t: string) =>
  t ? new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''

const formatDate = (t: string) =>
  t ? new Date(t).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }) : ''

onMounted(() => {
  loadSessions()
  loadReports()
  loadTTS()
})
</script>

<style scoped>
/* 消息入场动画 */
.msg-enter-active {
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.msg-enter-from {
  opacity: 0;
  transform: translateY(12px) scale(0.97);
}

/* AI 思考状态入场 */
.thinking-enter-active {
  transition: all 0.25s ease-out;
}
.thinking-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.thinking-leave-active {
  transition: all 0.2s ease-in;
}
.thinking-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* 淡入淡出 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 展开收起 */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
}
.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 4rem;
}

/* TTS 声音波浪动画 */
.tts-wave {
  display: inline-block;
  width: 2.5px;
  border-radius: 9999px;
  background: currentColor;
  animation: tts-wave-bounce 0.8s ease-in-out infinite alternate;
}
.tts-wave:nth-child(1) { height: 8px; }
.tts-wave:nth-child(2) { height: 14px; }
.tts-wave:nth-child(3) { height: 10px; }
.tts-wave:nth-child(4) { height: 6px; }

@keyframes tts-wave-bounce {
  0% { transform: scaleY(0.4); opacity: 0.6; }
  100% { transform: scaleY(1); opacity: 1; }
}
</style>
