<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import {
  Bot,
  User,
  Wrench,
  CheckCircle2,
} from 'lucide-vue-next'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { ScrollArea } from '@/components/ui/scroll-area'

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

const props = defineProps<{
  messages: Message[]
  loading: boolean
}>()

const chatEnd = ref<HTMLElement | null>(null)
const scrollAreaRef = ref<any>(null)

function scrollBottom() {
  if (chatEnd.value) {
    chatEnd.value.scrollIntoView({ block: 'end', behavior: 'smooth' })
  }
}

watch(() => props.messages, async () => {
  await nextTick()
  scrollBottom()
}, { deep: true })

onMounted(() => {
  scrollBottom()
})

function renderMd(text: string): string {
  if (!text) return ''
  const rawHtml = marked.parse(text, { breaks: true, gfm: true }) as string
  const safeHtml = DOMPurify.sanitize(rawHtml, {
    ADD_ATTR: ['target'],
    ADD_TAGS: ['details', 'summary']
  })
  return safeHtml.replace(/<a /g, '<a target="_blank" rel="noopener noreferrer" ')
}

function formatToolResult(content: string): string {
  if (!content) return ''
  try {
    return JSON.stringify(JSON.parse(content), null, 2)
  } catch {
    return content
  }
}

function messageKey(message: Message, index: number): string {
  return `${message.role}-${message.created_at || 'no-ts'}-${index}`
}
</script>

<template>
  <ScrollArea ref="scrollAreaRef" class="flex-1 w-full pb-36 h-full">
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
      <div v-else class="space-y-8">
        <div
          v-for="(msg, idx) in messages"
          :key="messageKey(msg, idx)"
          class="flex gap-4 animate-in slide-in-from-bottom-2 duration-300"
          :class="[msg.role === 'user' ? 'flex-row-reverse' : '']"
        >
          <Avatar class="mt-1 shadow-md border border-border/50 shrink-0">
            <template v-if="msg.role === 'assistant'">
              <AvatarImage src="" />
              <AvatarFallback class="bg-primary/10 text-primary">
                <Bot :size="18" />
              </AvatarFallback>
            </template>
            <template v-else>
              <AvatarImage src="" />
              <AvatarFallback class="bg-muted text-muted-foreground">
                <User :size="18" />
              </AvatarFallback>
            </template>
          </Avatar>

          <div
            class="flex flex-col gap-2 max-w-[85%]"
            :class="[msg.role === 'user' ? 'items-end' : 'items-start']"
          >
            <!-- User Message -->
            <div
              v-if="msg.role === 'user'"
              class="px-5 py-3 rounded-2xl bg-primary text-primary-foreground shadow-sm text-[15px] leading-relaxed"
            >
              {{ msg.content }}
            </div>

            <!-- Assistant Message -->
            <template v-else>
              <!-- Content Part 1: Before Tools -->
              <div
                v-if="msg.content"
                class="px-5 py-3 rounded-2xl bg-muted/40 border border-border/50 text-foreground shadow-sm text-[15px] leading-relaxed prose prose-sm dark:prose-invert max-w-none"
                v-html="renderMd(msg.content)"
              ></div>

              <!-- Tool Calls & Results (Combined & Collapsible) -->
              <div v-if="msg.tool_calls?.length || msg.tool_results?.length" class="w-full my-3">
                <details class="group rounded-xl border border-border/60 bg-muted/20 overflow-hidden shadow-sm transition-all text-xs">
                  <summary class="px-4 py-2.5 cursor-pointer hover:bg-muted/40 flex items-center justify-between list-none">
                    <div class="flex items-center gap-2 font-semibold text-muted-foreground group-open:text-primary transition-colors">
                      <Wrench :size="14" class="group-open:rotate-12 transition-transform" />
                      <span>系统已执行 {{ msg.tool_calls?.length || 0 }} 项指令</span>
                      <span v-if="msg.tool_results?.length === msg.tool_calls?.length" class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">已完成</span>
                      <span v-else class="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-500 border border-amber-500/20 animate-pulse">执行中</span>
                    </div>
                    <div class="text-[10px] text-muted-foreground opacity-60 group-open:rotate-180 transition-transform">▼</div>
                  </summary>
                  
                  <div class="p-3 space-y-4 bg-background/40 border-t border-border/40 animate-in slide-in-from-top-1 duration-200">
                    <!-- Tool Calls -->
                    <div v-for="tc in msg.tool_calls" :key="tc.id" class="space-y-1.5">
                      <div class="flex items-center text-[11px] font-bold text-primary/80">
                        <Wrench :size="12" class="mr-1.5" />
                        调用工具: {{ tc.name || tc.function?.name }}
                      </div>
                      <pre class="p-2.5 rounded-lg bg-muted/40 font-mono text-[10px] text-muted-foreground/90 overflow-x-auto border border-border/20 whitespace-pre-wrap">{{ tc.arguments || tc.function?.arguments }}</pre>
                    </div>

                    <!-- Tool Results -->
                    <div v-for="(tr, tri) in msg.tool_results" :key="tri" class="space-y-1.5 border-t border-border/20 pt-3">
                      <div class="flex items-center text-[11px] font-bold text-emerald-600 dark:text-emerald-400">
                        <CheckCircle2 :size="12" class="mr-1.5" />
                        执行结果: {{ tr.name }}
                      </div>
                      <pre class="p-2.5 rounded-lg bg-emerald-500/5 font-mono text-[10px] text-emerald-700 dark:text-emerald-300 overflow-x-auto border border-emerald-500/10 whitespace-pre-wrap">{{ formatToolResult(tr.content) }}</pre>
                    </div>
                  </div>
                </details>
              </div>

              <!-- Content Part 2: After Tools -->
              <div
                v-if="msg.post_content"
                class="px-5 py-3 rounded-2xl bg-muted/40 border border-border/50 text-foreground shadow-sm text-[15px] leading-relaxed prose prose-sm dark:prose-invert max-w-none"
                v-html="renderMd(msg.post_content)"
              ></div>
            </template>
          </div>
        </div>
        <div ref="chatEnd" class="h-1" />
      </div>
    </div>
  </ScrollArea>
</template>
