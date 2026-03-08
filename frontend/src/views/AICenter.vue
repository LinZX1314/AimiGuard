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
              <!-- TTS 麦克风按钮 + 录音气泡 -->
              <div class="relative">
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
                  <Mic v-if="!ttsRecording" class="size-3.5" />
                  <div v-else class="flex items-center gap-[2px] h-4">
                    <span
                      v-for="(v, i) in waveBars"
                      :key="i"
                      class="tts-wave-bar"
                      :style="{ height: Math.max(3, v * 16) + 'px' }"
                    />
                  </div>
                  <span
                    v-if="ttsRecording"
                    class="absolute inset-0 rounded-full border-2 border-red-400/40 animate-ping pointer-events-none"
                  />
                </button>
                <!-- 录音中小气泡提示 -->
                <Transition name="tts-bubble">
                  <div
                    v-if="ttsRecording"
                    class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2.5 rounded-xl bg-popover border border-border/60 shadow-lg px-3 py-2.5 flex flex-col items-center gap-2 z-50"
                    :class="sttText ? 'w-52' : 'w-36'"
                  >
                    <!-- 实时波形 -->
                    <div class="flex items-center gap-[3px] h-6">
                      <span
                        v-for="(v, i) in waveBars"
                        :key="i"
                        class="tts-wave-bar-pop"
                        :style="{ height: Math.max(4, v * 24) + 'px' }"
                      />
                    </div>
                    <p v-if="sttText" class="text-[10px] text-foreground leading-tight text-center max-w-full truncate">{{ sttText }}</p>
                    <p v-else class="text-[10px] text-muted-foreground leading-none">正在聆听…</p>
                    <p class="text-[9px] text-muted-foreground/40 leading-none">点击停止并发送</p>
                    <!-- 小三角箭头 -->
                    <div class="absolute -bottom-1 left-1/2 -translate-x-1/2 size-2 rotate-45 bg-popover border-r border-b border-border/60" />
                  </div>
                </Transition>
              </div>
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

    <!-- ── 右侧：报告 ── -->
    <aside class="w-64 shrink-0 border-l border-border/60 flex flex-col bg-sidebar">

      <!-- 标题 -->
      <div class="flex items-center gap-1.5 px-3.5 py-3 border-b border-border/60">
        <FileText class="size-3.5 text-primary/70" />
        <span class="text-[11px] font-semibold text-muted-foreground uppercase tracking-widest">报告</span>
      </div>

      <!-- 报告面板 -->
      <div class="flex flex-col flex-1 min-h-0">
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
            @click="openReportPreview(r)"
          >
            <div class="flex items-center justify-between gap-1">
              <Badge variant="outline" class="text-[9px] h-4 capitalize px-1.5">{{ r.report_type }}</Badge>
              <span class="text-[10px] text-muted-foreground tabular-nums">{{ formatDate(r.created_at) }}</span>
            </div>
            <p class="text-[11px] text-muted-foreground/80 line-clamp-2 leading-relaxed">{{ r.summary }}</p>
            <div class="flex items-center justify-between text-[10px] text-muted-foreground/50">
              <span v-if="r.file_size != null">{{ formatFileSize(r.file_size) }}</span>
              <span v-else>—</span>
              <Eye class="size-3 opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
          </div>
        </div>

        <!-- 分页 -->
        <div v-if="reportTotal > reportPageSize" class="shrink-0 border-t border-border/60 px-2 py-2 flex items-center justify-between">
          <Button
            variant="ghost"
            size="icon"
            class="size-6 cursor-pointer"
            :disabled="reportPage <= 1"
            @click="reportPage--; loadReports()"
          >
            <ChevronLeft class="size-3.5" />
          </Button>
          <span class="text-[10px] text-muted-foreground tabular-nums">{{ reportPage }} / {{ Math.ceil(reportTotal / reportPageSize) }}</span>
          <Button
            variant="ghost"
            size="icon"
            class="size-6 cursor-pointer"
            :disabled="reportPage >= Math.ceil(reportTotal / reportPageSize)"
            @click="reportPage++; loadReports()"
          >
            <ChevronRight class="size-3.5" />
          </Button>
        </div>
      </div>
    </aside>

    <!-- ── 报告预览弹窗 ── -->
    <Dialog v-model:open="showReportPreview">
      <DialogContent class="max-w-3xl max-h-[85vh] flex flex-col gap-0 p-0 overflow-hidden">
        <DialogHeader class="shrink-0 px-6 pt-5 pb-3 border-b border-border/60">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <FileText class="size-4 text-primary" />
              <DialogTitle class="text-base">
                {{ previewReport?.report_type === 'daily' ? '日报' : previewReport?.report_type === 'weekly' ? '周报' : previewReport?.report_type === 'scan' ? '扫描报告' : '报告' }}
              </DialogTitle>
              <Badge variant="outline" class="text-[10px] h-5 capitalize">{{ previewReport?.report_type }}</Badge>
            </div>
            <div class="flex items-center gap-3 text-[11px] text-muted-foreground">
              <span v-if="previewFileSize != null">{{ formatFileSize(previewFileSize) }}</span>
              <span class="tabular-nums">{{ previewReport ? formatTime(previewReport.created_at) : '' }}</span>
            </div>
          </div>
          <DialogDescription class="sr-only">报告预览</DialogDescription>
        </DialogHeader>
        <div class="flex-1 overflow-y-auto px-6 py-5 min-h-0">
          <div v-if="previewLoading" class="space-y-3 py-8">
            <Skeleton class="h-6 w-3/4" />
            <Skeleton class="h-4 w-full" />
            <Skeleton class="h-4 w-5/6" />
            <Skeleton class="h-4 w-full" />
            <Skeleton class="h-4 w-2/3" />
          </div>
          <div v-else-if="previewContent" ref="previewContentRef" class="report-markdown prose prose-sm dark:prose-invert max-w-none">
            <Markdown :content="previewContent" />
          </div>
          <div v-else class="text-center text-muted-foreground py-12">
            <p class="text-sm">无法加载报告内容</p>
          </div>
        </div>
        <div class="shrink-0 border-t border-border/60 px-6 py-3 flex items-center justify-end gap-2">
          <Button variant="outline" size="sm" class="cursor-pointer gap-1.5 text-xs" @click="exportReportPdf">
            <Download class="size-3.5" />
            导出 PDF
          </Button>
          <Button variant="outline" size="sm" class="cursor-pointer text-xs" @click="showReportPreview = false">
            关闭
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, reactive } from 'vue'
import { aiApi } from '@/api/ai'
import { reportApi } from '@/api/report'
import type { ReportItem } from '@/api/report'
import { STTStream } from '@/api/stt'
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
import { Markdown } from 'vue-stream-markdown'
import 'vue-stream-markdown/index.css'
import {
  BrainCircuit,
  ChevronLeft,
  ChevronRight,
  Download,
  Eye,
  FileText,
  MessageCircle,
  MessagesSquare,
  Mic,
  ScanLine,
  SquarePen,
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

type Report = ReportItem

const quickHints = [
  '分析最近告警',
  '解读扫描结果',
  '给出修复建议',
  '威胁溯源分析',
]

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
const reportPage = ref(1)
const reportPageSize = 10
const reportTotal = ref(0)

const showReportPreview = ref(false)
const previewReport = ref<Report | null>(null)
const previewContent = ref('')
const previewFileSize = ref<number | null>(null)
const previewLoading = ref(false)
const previewContentRef = ref<HTMLElement | null>(null)

const ttsRecording = ref(false)
const showMicPermissionDialog = ref(false)
const sttText = ref('')

// 实时音频波形状态
const waveBars = reactive([0, 0, 0, 0, 0])
let audioCtx: AudioContext | null = null
let analyser: AnalyserNode | null = null
let micStream: MediaStream | null = null
let animFrameId: number | null = null
let sttStream: STTStream | null = null
let mediaRecorder: MediaRecorder | null = null

const startAudioVisualizer = (stream: MediaStream) => {
  audioCtx = new AudioContext()
  analyser = audioCtx.createAnalyser()
  analyser.fftSize = 64
  const source = audioCtx.createMediaStreamSource(stream)
  source.connect(analyser)
  const dataArr = new Uint8Array(analyser.frequencyBinCount)

  const tick = () => {
    if (!analyser || !ttsRecording.value) return
    analyser.getByteFrequencyData(dataArr)
    // 从频谱中取 5 个采样点映射到波形条高度 (0~1)
    const len = dataArr.length
    const step = Math.max(1, Math.floor(len / 5))
    for (let i = 0; i < 5; i++) {
      const val = dataArr[Math.min(i * step, len - 1)] / 255
      // 平滑过渡，避免跳动
      waveBars[i] = waveBars[i] * 0.4 + val * 0.6
    }
    animFrameId = requestAnimationFrame(tick)
  }
  tick()
}

const stopAudioVisualizer = () => {
  if (animFrameId) { cancelAnimationFrame(animFrameId); animFrameId = null }
  if (audioCtx) { audioCtx.close(); audioCtx = null; analyser = null }
  if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null }
  for (let i = 0; i < 5; i++) waveBars[i] = 0
}

const stopSTTStream = () => {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop()
  }
  mediaRecorder = null
  if (sttStream) {
    sttStream.stop()
    setTimeout(() => { sttStream?.close(); sttStream = null }, 500)
  }
}

const startSTTStream = (stream: MediaStream) => {
  sttText.value = ''
  sttStream = new STTStream((event) => {
    if (event.type === 'partial' || event.type === 'final') {
      sttText.value = event.text || ''
    }
    if (event.type === 'final' && event.text) {
      // 录音结束后自动发送转写文字
      const finalText = event.text
      setTimeout(() => {
        if (finalText.trim()) sendMessage(finalText.trim())
        sttText.value = ''
      }, 300)
    }
  })

  sttStream.connect().then(() => {
    // 启动 MediaRecorder 流式发送音频块
    try {
      mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : 'audio/webm',
      })
    } catch {
      mediaRecorder = new MediaRecorder(stream)
    }
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0 && sttStream?.connected) {
        e.data.arrayBuffer().then((buf) => sttStream?.sendAudio(buf))
      }
    }
    mediaRecorder.start(250) // 每 250ms 发送一个音频块
  }).catch(() => {
    // WebSocket 连接失败时仍然允许录音（只是没有转写）
  })
}

onUnmounted(() => {
  stopAudioVisualizer()
  stopSTTStream()
})

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
    const data: any = await reportApi.getReports(reportPage.value, reportPageSize)
    const list = data?.items ?? (Array.isArray(data) ? data : (data?.data ?? []))
    reports.value = Array.isArray(list) ? list : []
    reportTotal.value = typeof data?.total === 'number' ? data.total : reports.value.length
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
    reportPage.value = 1
    await loadReports()
  } catch {
    reportMsg.value = '生成失败'
    reportMsgOk.value = false
  } finally {
    reportGenerating.value = false
    setTimeout(() => { reportMsg.value = '' }, 3000)
  }
}

const openReportPreview = async (r: Report) => {
  previewReport.value = r
  previewContent.value = ''
  previewFileSize.value = r.file_size ?? null
  previewLoading.value = true
  showReportPreview.value = true
  try {
    const data: any = await reportApi.getReportContent(r.id)
    previewContent.value = data?.content ?? ''
    previewFileSize.value = data?.file_size ?? r.file_size ?? null
  } catch {
    previewContent.value = ''
  } finally {
    previewLoading.value = false
  }
}

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

const exportReportPdf = () => {
  const el = previewContentRef.value
  if (!el) return
  const title = previewReport.value?.report_type === 'daily' ? '日报'
    : previewReport.value?.report_type === 'weekly' ? '周报'
    : previewReport.value?.report_type === 'scan' ? '扫描报告' : '报告'
  const dateStr = previewReport.value?.created_at
    ? new Date(previewReport.value.created_at).toLocaleDateString('zh-CN')
    : ''
  const printWin = window.open('', '_blank')
  if (!printWin) return
  printWin.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"/>
<title>${title} - ${dateStr}</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 40px; color: #1a1a1a; line-height: 1.7; max-width: 800px; margin: 0 auto; }
  h1 { font-size: 22px; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px; margin-bottom: 16px; }
  h2 { font-size: 18px; margin-top: 24px; color: #374151; }
  h3 { font-size: 15px; margin-top: 20px; color: #4b5563; }
  p { margin: 8px 0; }
  ul, ol { padding-left: 24px; }
  li { margin: 4px 0; }
  code { background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
  pre { background: #f3f4f6; padding: 16px; border-radius: 8px; overflow-x: auto; font-size: 13px; }
  pre code { background: none; padding: 0; }
  table { border-collapse: collapse; width: 100%; margin: 12px 0; }
  th, td { border: 1px solid #d1d5db; padding: 8px 12px; text-align: left; font-size: 13px; }
  th { background: #f9fafb; font-weight: 600; }
  blockquote { border-left: 3px solid #d1d5db; margin: 12px 0; padding: 8px 16px; color: #6b7280; }
  @media print { body { padding: 20px; } }
</style>
</head><body>`)
  printWin.document.write(el.innerHTML)
  printWin.document.write('</body></html>')
  printWin.document.close()
  setTimeout(() => { printWin.print() }, 300)
}

// ── TTS 录音按钮 ──
const startRecording = (stream: MediaStream) => {
  micStream = stream
  ttsRecording.value = true
  startAudioVisualizer(stream)
  startSTTStream(stream)
}

const toggleTTSRecording = async () => {
  if (ttsRecording.value) {
    stopSTTStream()
    ttsRecording.value = false
    stopAudioVisualizer()
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
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    startRecording(stream)
  } catch {
    showMicPermissionDialog.value = true
  }
}

const retryMicPermission = async () => {
  showMicPermissionDialog.value = false
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    startRecording(stream)
  } catch {
    showMicPermissionDialog.value = true
  }
}

// ── 格式化 ──
const formatTime = (t: string) =>
  t ? new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''

const formatDate = (t: string) =>
  t ? new Date(t).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }) : ''

onMounted(() => {
  loadSessions()
  loadReports()
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

/* 解除 InputGroup overflow-hidden 裁剪，让气泡可以溢出 */
:deep([data-slot="input-group"]) {
  overflow: visible !important;
}

/* TTS 按钮内小波形条 */
.tts-wave-bar {
  display: inline-block;
  width: 2.5px;
  min-height: 3px;
  border-radius: 9999px;
  background: currentColor;
  transition: height 0.08s ease-out;
}

/* TTS 气泡中波形条 */
.tts-wave-bar-pop {
  display: inline-block;
  width: 3px;
  min-height: 4px;
  border-radius: 9999px;
  background: #f87171;
  transition: height 0.08s ease-out;
}

/* 气泡弹出动画 */
.tts-bubble-enter-active {
  transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.tts-bubble-leave-active {
  transition: all 0.15s ease-in;
}
.tts-bubble-enter-from {
  opacity: 0;
  transform: translate(-50%, 4px) scale(0.9);
}
.tts-bubble-leave-to {
  opacity: 0;
  transform: translate(-50%, 4px) scale(0.9);
}

/* 报告预览 Markdown 美化 */
.report-markdown :deep(h1) {
  font-size: 1.35rem;
  font-weight: 700;
  border-bottom: 2px solid var(--border);
  padding-bottom: 0.5rem;
  margin-bottom: 1rem;
  margin-top: 0;
}
.report-markdown :deep(h2) {
  font-size: 1.15rem;
  font-weight: 600;
  margin-top: 1.5rem;
  margin-bottom: 0.5rem;
  color: var(--foreground);
}
.report-markdown :deep(h3) {
  font-size: 1rem;
  font-weight: 600;
  margin-top: 1.25rem;
  margin-bottom: 0.4rem;
}
.report-markdown :deep(p) {
  margin: 0.5rem 0;
  line-height: 1.75;
}
.report-markdown :deep(ul),
.report-markdown :deep(ol) {
  padding-left: 1.5rem;
  margin: 0.5rem 0;
}
.report-markdown :deep(li) {
  margin: 0.25rem 0;
  line-height: 1.7;
}
.report-markdown :deep(code) {
  background: var(--muted);
  padding: 0.15em 0.4em;
  border-radius: 4px;
  font-size: 0.85em;
}
.report-markdown :deep(pre) {
  background: var(--muted);
  padding: 1rem;
  border-radius: 8px;
  overflow-x: auto;
  margin: 0.75rem 0;
}
.report-markdown :deep(pre code) {
  background: none;
  padding: 0;
}
.report-markdown :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 0.75rem 0;
  font-size: 0.85rem;
}
.report-markdown :deep(th),
.report-markdown :deep(td) {
  border: 1px solid var(--border);
  padding: 0.5rem 0.75rem;
  text-align: left;
}
.report-markdown :deep(th) {
  background: var(--muted);
  font-weight: 600;
}
.report-markdown :deep(blockquote) {
  border-left: 3px solid var(--primary);
  margin: 0.75rem 0;
  padding: 0.5rem 1rem;
  color: var(--muted-foreground);
  background: var(--muted);
  border-radius: 0 6px 6px 0;
}
.report-markdown :deep(hr) {
  border: none;
  border-top: 1px solid var(--border);
  margin: 1.25rem 0;
}
</style>
