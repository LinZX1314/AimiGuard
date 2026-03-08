<template>
  <div class="ai-center flex h-[calc(100vh-64px)] overflow-hidden">

    <!-- 鈹€鈹€ 宸︿晶锛氫細璇濆巻鍙?鈹€鈹€ -->
    <aside class="sessions-sidebar w-56 shrink-0 border-r border-border bg-sidebar flex flex-col">
      <div class="flex items-center justify-between px-3.5 py-3 border-b border-border/60">
        <div class="flex items-center gap-1.5">
          <MessagesSquare class="size-3.5 text-primary/70" />
          <span class="text-[11px] font-semibold text-muted-foreground uppercase tracking-widest">鍘嗗彶浼氳瘽</span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          class="size-6 cursor-pointer hover:bg-primary/10 hover:text-primary transition-colors"
          title="鏂板缓浼氳瘽"
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
          <p class="text-xs text-muted-foreground/60">鏆傛棤鍘嗗彶浼氳瘽</p>
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
                {{ s.context_type || 'AI 瀵硅瘽' }}
              </p>
              <p class="text-[10px] opacity-50 mt-0.5 tabular-nums">{{ formatTime(s.started_at) }}</p>
            </div>
            <div
              class="shrink-0 size-5 rounded flex items-center justify-center opacity-0 group-hover:opacity-100 hover:bg-destructive/15 hover:text-destructive transition-all cursor-pointer"
              title="鍒犻櫎浼氳瘽"
              @click.stop="deleteSession(s)"
            >
              <Trash2 class="size-3" />
            </div>
          </div>
        </button>
      </div>
    </aside>

    <!-- 鈹€鈹€ 涓細瀵硅瘽鍖?鈹€鈹€ -->
    <div class="flex flex-1 flex-col min-w-0 min-h-0">

      <!-- 瀵硅瘽椤堕儴 -->
      <div class="flex items-center justify-between border-b border-border/60 px-5 py-2.5 shrink-0 bg-background/80 backdrop-blur-sm">
        <div class="flex items-center gap-2.5">
          <div class="size-7 rounded-lg bg-primary/10 flex items-center justify-center ring-1 ring-primary/20">
            <BrainCircuit class="size-3.5 text-primary" />
          </div>
          <div>
            <span class="font-semibold text-sm leading-none">AI 鐮斿垽鍔╂墜</span>
            <div class="flex items-center gap-1.5 mt-0.5">
              <span class="inline-block size-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span class="text-[10px] text-muted-foreground">鍦ㄧ嚎</span>
              <span v-if="currentSessionId" class="text-[10px] text-muted-foreground/50">路 浼氳瘽 #{{ currentSessionId }}</span>
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
          鏂板缓瀵硅瘽
        </Button>
      </div>

      <!-- 娑堟伅鍒楄〃锛氫娇鐢?AI Elements Conversation 缁勪欢 -->
      <Conversation class="flex-1 min-h-0 px-5 py-4 [&>div]:!overflow-y-auto">
        <!-- 绌虹姸鎬侊細浣跨敤 AI Elements ConversationEmptyState -->
        <ConversationEmptyState
          v-if="messages.length === 0 && !aiThinking"
          title="寮€濮?AI 鐮斿垽瀵硅瘽"
          description="璇㈤棶鍛婅鍒嗘瀽銆佹紡娲炶В璇汇€佷慨澶嶅缓璁紝鎴栧紩鐢ㄤ簨浠?ID 杩涜娣卞害鍒嗘瀽"
        >
          <template #icon>
            <div class="size-14 rounded-2xl bg-primary/8 border border-primary/15 flex items-center justify-center mb-1">
              <BrainCircuit class="size-6 text-primary/60" />
            </div>
          </template>

          <!-- 蹇嵎鎻愮ず鎸夐挳 -->
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

        <!-- 娑堟伅娴侊細浣跨敤 AI Elements Message / MessageContent / MessageAvatar -->
        <div v-if="messages.length > 0 || aiThinking" class="space-y-5 py-2">
          <TransitionGroup name="msg" tag="div" class="space-y-5">
            <Message
              v-for="(msg, idx) in messages"
              :key="idx"
              :from="msg.role"
            >
              <!-- AI 鍔╂墜娑堟伅锛氬ご鍍忓湪宸?-->
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

              <!-- 鐢ㄦ埛娑堟伅锛氬ご鍍忓湪鍙?-->
              <MessageAvatar
                v-if="msg.role === 'user'"
                src=""
                name="Me"
                class="shrink-0 bg-muted ring-border/50 text-muted-foreground text-[10px]"
              />
            </Message>
          </TransitionGroup>

          <!-- AI 鎬濊€冧腑鎸囩ず鍣?-->
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

      <!-- 杈撳叆鍖猴細浣跨敤 AI Elements PromptInput 缁勪欢 -->
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
              Enter 鍙戦€?路 Shift+Enter 鎹㈣ 路 鍙紩鐢ㄤ簨浠?ID
            </span>
            <div class="flex items-center gap-1.5">
              <!-- TTS 楹﹀厠椋庢寜閽?+ 褰曢煶姘旀场 -->
              <div class="relative">
                <button
                  class="relative size-8 rounded-full flex items-center justify-center transition-all duration-200 cursor-pointer"
                  :class="[
                    ttsRecording
                      ? 'bg-red-500/15 text-red-400 ring-1 ring-red-500/30 hover:bg-red-500/25'
                      : 'bg-muted/60 text-muted-foreground hover:bg-primary/10 hover:text-primary',
                  ]"
                  :title="ttsRecording ? '鍋滄褰曢煶' : '璇煶杈撳叆'"
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
                <!-- 褰曢煶涓皬姘旀场鎻愮ず -->
                <Transition name="tts-bubble">
                  <div
                    v-if="ttsRecording"
                    class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2.5 rounded-xl bg-popover border border-border/60 shadow-lg px-3 py-2.5 flex flex-col items-center gap-2 z-50"
                    :class="sttText ? 'w-52' : 'w-36'"
                  >
                    <!-- 瀹炴椂娉㈠舰 -->
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
                    <p class="text-[9px] text-muted-foreground/40 leading-none">鐐瑰嚮鍋滄骞跺彂閫</p>
                    <!-- 灏忎笁瑙掔澶?-->
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

    <!-- 楹﹀厠椋庢潈闄愬脊绐?-->
    <Dialog :open="showMicPermissionDialog" @update:open="showMicPermissionDialog = $event">
      <DialogContent class="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2">
            <Mic class="size-4 text-primary" />
            闇€瑕侀害鍏嬮鏉冮檺
          </DialogTitle>
          <DialogDescription>
            璇煶杈撳叆鍔熻兘闇€瑕佽闂偍鐨勯害鍏嬮銆傝鍦ㄦ祻瑙堝櫒寮瑰嚭鐨勬潈闄愯姹備腑鐐瑰嚮銆屽厑璁搞€嶏紝鎴栧湪娴忚鍣ㄨ缃腑鎵嬪姩寮€鍚害鍏嬮鏉冮檺銆?          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" size="sm" class="cursor-pointer" @click="showMicPermissionDialog = false">
            鎴戠煡閬撲簡
          </Button>
          <Button size="sm" class="cursor-pointer" @click="retryMicPermission">
            閲嶆柊鎺堟潈
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- 鈹€鈹€ 鍙充晶锛氭姤鍛?鈹€鈹€ -->
    <aside class="w-64 shrink-0 border-l border-border/60 flex flex-col bg-sidebar">

      <!-- 鏍囬 -->
      <div class="flex items-center gap-1.5 px-3.5 py-3 border-b border-border/60">
        <FileText class="size-3.5 text-primary/70" />
        <span class="text-[11px] font-semibold text-muted-foreground uppercase tracking-widest">鎶ュ憡</span>
      </div>

      <!-- 鎶ュ憡闈㈡澘 -->
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
              <FileText class="size-3" /> 鏃ユ姤
            </Button>
            <Button
              variant="outline"
              size="sm"
              class="cursor-pointer text-[11px] gap-1 h-7 hover:border-primary/30 hover:text-primary"
              :disabled="reportGenerating"
              @click="generateReport('weekly')"
            >
              <FileText class="size-3" /> 鍛ㄦ姤
            </Button>
          </div>
          <Button
            variant="outline"
            size="sm"
            class="cursor-pointer text-[11px] gap-1 w-full h-7 hover:border-primary/30 hover:text-primary"
            :disabled="reportGenerating"
            @click="generateReport('scan')"
          >
            <ScanLine class="size-3" /> 鎵弿鎶ュ憡
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
              鐢熸垚涓€?            </p>
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
            <p class="text-[11px] text-muted-foreground/50">鏆傛棤鎶ュ憡</p>
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
              <span v-else>…</span>
              <Eye class="size-3 opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
          </div>
        </div>

        <!-- 鍒嗛〉 -->
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

    <!-- 鈹€鈹€ 鎶ュ憡棰勮寮圭獥 鈹€鈹€ -->
    <Dialog v-model:open="showReportPreview">
      <DialogContent class="max-w-3xl max-h-[85vh] flex flex-col gap-0 p-0 overflow-hidden">
        <DialogHeader class="shrink-0 px-6 pt-5 pb-3 border-b border-border/60">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <FileText class="size-4 text-primary" />
              <DialogTitle class="text-base">
                {{ previewReport?.report_type === 'daily' ? '鏃ユ姤' : previewReport?.report_type === 'weekly' ? '鍛ㄦ姤' : previewReport?.report_type === 'scan' ? '鎵弿鎶ュ憡' : '鎶ュ憡' }}
              </DialogTitle>
              <Badge variant="outline" class="text-[10px] h-5 capitalize">{{ previewReport?.report_type }}</Badge>
            </div>
            <div class="flex items-center gap-3 text-[11px] text-muted-foreground">
              <span v-if="previewFileSize != null">{{ formatFileSize(previewFileSize) }}</span>
              <span class="tabular-nums">{{ previewReport ? formatTime(previewReport.created_at) : '' }}</span>
            </div>
          </div>
          <DialogDescription class="sr-only">鎶ュ憡棰勮</DialogDescription>
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
            <Markdown :content="previewContent" :cdn-options="{ mermaid: false, beautifulMermaid: false }" />
          </div>
          <div v-else class="text-center text-muted-foreground py-12">
            <p class="text-sm">鏃犳硶鍔犺浇鎶ュ憡鍐呭</p>
          </div>
        </div>
        <div class="shrink-0 border-t border-border/60 px-6 py-3 flex items-center justify-end gap-2">
          <Button variant="outline" size="sm" class="cursor-pointer gap-1.5 text-xs" @click="exportReportPdf">
            <Download class="size-3.5" />
            瀵煎嚭 PDF
          </Button>
          <Button variant="outline" size="sm" class="cursor-pointer text-xs" @click="showReportPreview = false">
            鍏抽棴
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
  Trash2,
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
  '鍒嗘瀽鏈€杩戝憡璀?,
  '瑙ｈ鎵弿缁撴灉',
  '缁欏嚭淇寤鸿',
  '濞佽儊婧簮鍒嗘瀽',
]

// 鈹€鈹€ 鐘舵€?鈹€鈹€
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

// 瀹炴椂闊抽娉㈠舰鐘舵€?const waveBars = reactive([0, 0, 0, 0, 0])
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
    // 浠庨璋变腑鍙?5 涓噰鏍风偣鏄犲皠鍒版尝褰㈡潯楂樺害 (0~1)
    const len = dataArr.length
    const step = Math.max(1, Math.floor(len / 5))
    for (let i = 0; i < 5; i++) {
      const val = dataArr[Math.min(i * step, len - 1)] / 255
      // 骞虫粦杩囨浮锛岄伩鍏嶈烦鍔?      waveBars[i] = waveBars[i] * 0.4 + val * 0.6
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
      // 褰曢煶缁撴潫鍚庤嚜鍔ㄥ彂閫佽浆鍐欐枃瀛?      const finalText = event.text
      setTimeout(() => {
        if (finalText.trim()) sendMessage(finalText.trim())
        sttText.value = ''
      }, 300)
    }
  })

  sttStream.connect().then(() => {
    // 鍚姩 MediaRecorder 娴佸紡鍙戦€侀煶棰戝潡
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
    mediaRecorder.start(250) // 姣?250ms 鍙戦€佷竴涓煶棰戝潡
  }).catch(() => {
    // WebSocket 杩炴帴澶辫触鏃朵粛鐒跺厑璁稿綍闊筹紙鍙槸娌℃湁杞啓锛?  })
}

onUnmounted(() => {
  stopAudioVisualizer()
  stopSTTStream()
})

// 鈹€鈹€ 蹇嵎鎻愮ず 鈹€鈹€
const fillHint = (hint: string) => {
  // PromptInput 鍐呴儴绠＄悊鏂囨湰鐘舵€侊紝鏃犳硶鐩存帴娉ㄥ叆
  // 闄嶇骇涓虹洿鎺ュ彂閫?  sendMessage(hint)
}

// 鈹€鈹€ 浼氳瘽绠＄悊 鈹€鈹€
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

const deleteSession = async (s: Session) => {
  try {
    await aiApi.deleteSession(s.id)
    sessions.value = sessions.value.filter(x => x.id !== s.id)
    if (currentSessionId.value === s.id) {
      currentSessionId.value = null
      messages.value = []
    }
  } catch { /* ignore */ }
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

// 鈹€鈹€ 鍙戦€佹秷鎭?鈹€鈹€
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
      content: '鎶辨瓑锛屾湇鍔℃殏鏃朵笉鍙敤锛岃绋嶅悗閲嶈瘯銆?,
      created_at: new Date().toISOString(),
    })
  } finally {
    aiThinking.value = false
  }
}

// PromptInput submit 浜嬩欢澶勭悊
const handlePromptSubmit = (payload: PromptInputMessage) => {
  sendMessage(payload.text)
}

// 鈹€鈹€ 鎶ュ憡 鈹€鈹€
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
    reportMsg.value = '鐢熸垚澶辫触'
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
    previewContent.value = r.summary ? `> ${r.summary}\n\n*鎶ュ憡鍘熷鏂囦欢涓嶅彲鐢?` : ''
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
  const reportType = previewReport.value?.report_type ?? 'report'
  const title = reportType === 'daily' ? '姣忔棩瀹夊叏鎶ュ憡'
    : reportType === 'weekly' ? '姣忓懆瀹夊叏鎶ュ憡'
    : reportType === 'scan' ? '瀹夊叏鎵弿鎶ュ憡' : '瀹夊叏鎶ュ憡'
  const titleEn = reportType === 'daily' ? 'Daily Security Report'
    : reportType === 'weekly' ? 'Weekly Security Report'
    : reportType === 'scan' ? 'Scan Report' : 'Security Report'
  const dateStr = previewReport.value?.created_at
    ? new Date(previewReport.value.created_at).toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
    : new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
  const timeStr = previewReport.value?.created_at
    ? new Date(previewReport.value.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : ''
  const fileSize = previewFileSize.value != null ? formatFileSize(previewFileSize.value) : ''
  const printWin = window.open('', '_blank')
  if (!printWin) return
  printWin.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"/>
<title>${title} - ${dateStr}</title>
<style>
  @page {
    size: A4;
    margin: 14mm 12mm 16mm 12mm;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    background: #fff;
  }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
    color: #111111;
    line-height: 1.75;
    font-size: 13px;
    background: #fff;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }

  /* 鈹€鈹€ 灏侀潰澶撮儴 鈹€鈹€ */
  .cover-header {
    position: relative;
    z-index: 1;
    background: #ffffff;
    color: #111111;
    padding: 22px 24px 18px;
    border: 1px solid #111111;
    border-top-width: 4px;
    page-break-after: avoid;
  }
  .cover-header .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 16px;
  }
  .cover-header .brand-icon {
    width: 28px; height: 28px;
    border-radius: 6px;
    border: 1px solid #111111;
    background: #ffffff;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px;
    color: #111111;
  }
  .cover-header .brand-text {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1.4px;
    text-transform: uppercase;
    opacity: 1;
    color: #444444;
  }
  .cover-header .report-title {
    font-size: 28px;
    font-weight: 800;
    letter-spacing: 0.5px;
    margin-bottom: 6px;
    color: #111111;
  }
  .cover-header .report-title-en {
    font-size: 11px;
    font-weight: 500;
    opacity: 1;
    color: #666666;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 14px;
  }
  .cover-header .meta-row {
    display: flex;
    gap: 10px 18px;
    flex-wrap: wrap;
    padding-top: 12px;
    border-top: 1px solid #d1d5db;
  }
  .cover-header .meta-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    opacity: 1;
    color: #444444;
  }
  .cover-header .meta-label {
    font-weight: 700;
    opacity: 1;
    color: #111111;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    font-size: 10px;
  }
  .cover-header .accent-bar {
    margin-top: 14px;
    height: 0;
    border-top: 2px solid #111111;
    background: none;
  }

  /* 鈹€鈹€ 姝ｆ枃瀹瑰櫒 鈹€鈹€ */
  .content-wrap {
    position: relative;
    z-index: 1;
    max-width: 100%;
    margin-top: 12px;
    padding: 20px 24px 24px;
    border: 1px solid #d1d5db;
    background: #ffffff;
    overflow: hidden;
  }

  /* 鈹€鈹€ 鍒嗙被鏍囩 鈹€鈹€ */
  .report-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #ffffff;
    color: #111111;
    font-size: 10px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 20px;
    border: 1px solid #111111;
    margin-bottom: 18px;
    text-transform: uppercase;
    letter-spacing: 1.2px;
  }

  /* 鈹€鈹€ Markdown 鍐呭鏍峰紡 鈹€鈹€ */
  .content-wrap h1 {
    font-size: 20px;
    font-weight: 800;
    color: #111111;
    border-bottom: 1px solid #111111;
    padding-bottom: 8px;
    margin: 0 0 14px;
  }
  .content-wrap h1:not(:first-child) { margin-top: 26px; }
  .content-wrap h2 {
    font-size: 16px;
    font-weight: 700;
    color: #111111;
    margin: 22px 0 10px;
    padding-left: 10px;
    border-left: 3px solid #111111;
  }
  .content-wrap h3 {
    font-size: 14px;
    font-weight: 700;
    color: #111111;
    margin: 18px 0 8px;
  }
  .content-wrap p {
    margin: 8px 0;
    color: #111111;
  }
  .content-wrap ul, .content-wrap ol {
    padding-left: 22px;
    margin: 8px 0;
  }
  .content-wrap li {
    margin: 5px 0;
    color: #111111;
  }
  .content-wrap li::marker {
    color: #111111;
  }
  .content-wrap code {
    background: #ffffff;
    color: #111111;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 12px;
    font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
    border: 1px solid #d1d5db;
  }
  .content-wrap pre {
    background: #ffffff;
    border: 1px solid #d1d5db;
    padding: 14px 16px;
    border-radius: 8px;
    overflow-x: auto;
    margin: 12px 0;
    font-size: 12px;
  }
  .content-wrap pre code {
    background: transparent;
    padding: 0;
    border: none;
    color: #111111;
  }
  .content-wrap table {
    border-collapse: collapse;
    width: 100%;
    margin: 14px 0;
    font-size: 12px;
    border-radius: 0;
    overflow: visible;
    border: 1px solid #d1d5db;
  }
  .content-wrap th {
    background: #ffffff;
    font-weight: 700;
    color: #111111;
    padding: 8px 10px;
    text-align: left;
    border-bottom: 1px solid #d1d5db;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .content-wrap td {
    padding: 8px 10px;
    border-bottom: 1px solid #d1d5db;
    color: #111111;
    background: #ffffff;
  }
  .content-wrap tr:nth-child(even) td {
    background: #ffffff;
  }
  .content-wrap blockquote {
    border-left: 3px solid #111111;
    margin: 14px 0;
    padding: 10px 14px;
    background: #ffffff;
    border-radius: 0;
    color: #333333;
    font-size: 12.5px;
  }
  .content-wrap hr {
    border: none;
    border-top: 1px solid #d1d5db;
    margin: 20px 0;
  }
  .content-wrap strong {
    color: #111111;
  }

  /* 鈹€鈹€ 椤佃剼 鈹€鈹€ */
  .page-footer {
    border-top: 1px solid #d1d5db;
    padding: 14px 0 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    font-size: 10px;
    color: #444444;
    margin-top: 14px;
  }
  .page-footer .confidential {
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
    color: #111111;
    text-transform: uppercase;
    letter-spacing: 1px;
  }
  .page-footer .gen-info {
    text-align: right;
    color: #444444;
  }

  /* 鈹€鈹€ 姘村嵃 (SVG background, 鎵撳嵃鍏煎) 鈹€鈹€ */
  .watermark-bg {
    position: relative;
  }
  .watermark-bg::before {
    content: 'AIMIGUAN INTERNAL REPORT';
    position: absolute;
    top: 52%;
    left: 50%;
    pointer-events: none;
    z-index: 0;
    transform: translate(-50%, -50%) rotate(-28deg);
    transform-origin: center center;
    color: rgba(17, 17, 17, 0.06);
    font-size: 42px;
    font-weight: 700;
    letter-spacing: 4px;
    white-space: nowrap;
  }
  .watermark-bg > * { position: relative; z-index: 1; }

  /* 鈹€鈹€ 鎵撳嵃浼樺寲 鈹€鈹€ */
  @media print {
    html, body { background: #fff; }
    .cover-header,
    .content-wrap,
    .report-badge,
    .page-footer,
    .watermark-bg::before {
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
  }
</style>
</head><body>

<!-- 灏侀潰澶撮儴 -->
<div class="cover-header">
  <div class="brand">
    <div class="brand-icon">AI</div>
    <div class="brand-text">AiMiGuan \u00B7 瀹夊叏鎬佸娍鎰熺煡骞冲彴</div>
  </div>
  <div class="report-title">${title}</div>
  <div class="report-title-en">${titleEn}</div>
  <div class="meta-row">
    <div class="meta-item">
      <span class="meta-label">鏃ユ湡</span>
      <span>${dateStr}</span>
    </div>
    ${timeStr ? `<div class="meta-item"><span class="meta-label">鏃堕棿</span><span>${timeStr}</span></div>` : ''}
    ${fileSize ? `<div class="meta-item"><span class="meta-label">澶у皬</span><span>${fileSize}</span></div>` : ''}
    <div class="meta-item">
      <span class="meta-label">绫诲瀷</span>
      <span>${reportType.toUpperCase()}</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">瀵嗙骇</span>
      <span>鍐呴儴</span>
    </div>
  </div>
  <div class="accent-bar"></div>
</div>

<!-- 姝ｆ枃鍐呭 (甯︽按鍗拌儗鏅? -->
<div class="content-wrap watermark-bg">
  <div class="report-badge">${reportType} report</div>
  ${el.innerHTML}
</div>

<!-- 椤佃剼 -->
<div class="page-footer">
  <div class="confidential">鍐呴儴璧勬枡 \u00B7 璇峰嬁澶栦紶</div>
  <div class="gen-info">
    Generated by AiMiGuan &middot; ${dateStr} ${timeStr}
  </div>
</div>

</body></html>`)
  printWin.document.close()
  setTimeout(() => { printWin.focus(); printWin.print() }, 400)
}

// 鈹€鈹€ TTS 褰曢煶鎸夐挳 鈹€鈹€
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
  // 妫€鏌ラ害鍏嬮鏉冮檺
  try {
    const permStatus = await navigator.permissions.query({ name: 'microphone' as PermissionName })
    if (permStatus.state === 'denied') {
      showMicPermissionDialog.value = true
      return
    }
  } catch {
    // permissions API 涓嶆敮鎸佹椂鐩存帴灏濊瘯鑾峰彇
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

// 鈹€鈹€ 鏍煎紡鍖?鈹€鈹€
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
/* 娑堟伅鍏ュ満鍔ㄧ敾 */
.msg-enter-active {
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.msg-enter-from {
  opacity: 0;
  transform: translateY(12px) scale(0.97);
}

/* AI 鎬濊€冪姸鎬佸叆鍦?*/
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

/* 娣″叆娣″嚭 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 灞曞紑鏀惰捣 */
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

/* 瑙ｉ櫎 InputGroup overflow-hidden 瑁佸壀锛岃姘旀场鍙互婧㈠嚭 */
:deep([data-slot="input-group"]) {
  overflow: visible !important;
}

/* TTS 鎸夐挳鍐呭皬娉㈠舰鏉?*/
.tts-wave-bar {
  display: inline-block;
  width: 2.5px;
  min-height: 3px;
  border-radius: 9999px;
  background: currentColor;
  transition: height 0.08s ease-out;
}

/* TTS 姘旀场涓尝褰㈡潯 */
.tts-wave-bar-pop {
  display: inline-block;
  width: 3px;
  min-height: 4px;
  border-radius: 9999px;
  background: #f87171;
  transition: height 0.08s ease-out;
}

/* 姘旀场寮瑰嚭鍔ㄧ敾 */
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

/* 鎶ュ憡棰勮 Markdown 缇庡寲 */
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

