<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Bot,
  Sparkles,
  Send,
  Loader2,
  Clock,
} from 'lucide-vue-next'

const router = useRouter()
const aiMessages = ref<Array<{ role: 'user' | 'assistant'; content: string }>>([])

function renderMd(text: string): string {
  if (!text) return ''
  const rawHtml = marked.parse(text, { breaks: true, gfm: true }) as string
  return DOMPurify.sanitize(rawHtml)
}
const aiInput = ref('')
const aiLoading = ref(false)
const aiError = ref('')
const aiSessionId = ref<number | null>(null)
const aiEndRef = ref<HTMLElement | null>(null)

const quickPrompts = [
  { label: '态势总览', prompt: '请输出当前态势总览和最高优先级风险。' },
  { label: '防御动作', prompt: '请基于当前攻击来源给出30分钟防御动作清单。' },
  { label: '链路体检', prompt: '请评估当前链路健康与潜在瓶颈。' },
]

async function scrollAiToBottom() {
  await nextTick()
  aiEndRef.value?.scrollIntoView({ behavior: 'smooth', block: 'end' })
}

async function sendAiMessage(prompt?: string) {
  const text = (prompt ?? aiInput.value).trim()
  if (!text || aiLoading.value) return

  aiError.value = ''
  aiMessages.value.push({ role: 'user', content: text })
  aiMessages.value.push({ role: 'assistant', content: '' })
  if (!prompt) aiInput.value = ''
  aiLoading.value = true
  await scrollAiToBottom()

  try {
    const token = localStorage.getItem('token') || ''
    const resp = await fetch('/api/v1/ai/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: token ? `Bearer ${token}` : '',
      },
      body: JSON.stringify({
        message: text,
        session_id: aiSessionId.value ?? undefined,
        context_type: 'dashboard',
        context_id: 'map',
      }),
    })

    if (!resp.ok || !resp.body) {
      throw new Error('AI 服务暂不可用')
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const events = buffer.split('\n\n')
      buffer = events.pop() || ''

      for (const event of events) {
        const line = event.split('\n').find((x) => x.startsWith('data: '))
        if (!line) continue

        try {
          const parsed = JSON.parse(line.slice(6))
          if (parsed.session_id) {
            aiSessionId.value = Number(parsed.session_id)
          }
          if (parsed.error) {
            aiError.value = String(parsed.error)
            continue
          }
          if (parsed.content) {
            const lastIndex = aiMessages.value.length - 1
            const last = aiMessages.value[lastIndex]
            if (last && last.role === 'assistant') {
              aiMessages.value[lastIndex] = { ...last, content: `${last.content}${String(parsed.content)}` }
            }
            await scrollAiToBottom()
          }
        } catch {
          // 忽略
        }
      }
    }
  } catch (e: any) {
    aiError.value = e?.message || 'AI 响应异常'
    const lastIndex = aiMessages.value.length - 1
    if (lastIndex >= 0 && aiMessages.value[lastIndex].role === 'assistant' && !aiMessages.value[lastIndex].content) {
      aiMessages.value[lastIndex].content = '抱歉，当前 AI 服务不可用，请稍后重试。'
    }
  } finally {
    aiLoading.value = false
  }
}
</script>

<template>
  <Card class="flex-1 min-h-0 overflow-hidden">
    <CardHeader class="pb-2">
      <CardTitle class="text-sm flex items-center gap-2">
        <Bot class="h-4 w-4 text-primary" /> AI 指挥侧边栏
      </CardTitle>
    </CardHeader>
    <CardContent class="h-[calc(100%-52px)] p-3 flex flex-col gap-3 min-h-0">
      <ScrollArea class="w-full">
        <div class="flex items-center gap-1.5 pb-1">
          <Button
            v-for="item in quickPrompts"
            :key="item.label"
            variant="outline"
            size="sm"
            :disabled="aiLoading"
            @click="sendAiMessage(item.prompt)"
            class="h-7 px-2.5 text-[11px] whitespace-nowrap rounded-full"
          >
            <Sparkles class="h-3 w-3 mr-1" /> {{ item.label }}
          </Button>
        </div>
      </ScrollArea>

      <ScrollArea class="flex-1 rounded-lg border border-border/60 bg-muted/20 p-3">
        <div class="space-y-3">
          <div v-if="!aiMessages.length" class="text-xs text-muted-foreground">
            输入问题，AI 会基于当前大屏状态给出防御建议。
          </div>
          <div
            v-for="(msg, idx) in aiMessages"
            :key="idx"
            class="rounded-lg border px-2.5 py-2 text-xs leading-relaxed max-w-full"
            :class="msg.role === 'assistant' ? 'bg-primary/5 border-primary/20 text-foreground' : 'bg-background border-border/60 text-muted-foreground'"
          >
            <p class="mb-1 font-semibold opacity-80">{{ msg.role === 'assistant' ? 'AI' : '你' }}</p>
            <div v-if="msg.role === 'assistant'" class="prose prose-sm dark:prose-invert prose-p:leading-relaxed prose-pre:bg-muted/50 max-w-none" v-html="renderMd(msg.content)"></div>
            <p v-else class="whitespace-pre-wrap break-words">{{ msg.content }}</p>
          </div>
          <div ref="aiEndRef" />
        </div>
      </ScrollArea>

      <div class="space-y-2">
        <p v-if="aiError" class="text-[11px] text-destructive">{{ aiError }}</p>
        <Textarea v-model="aiInput" :disabled="aiLoading" rows="3" placeholder="例如：请给出当前最高风险攻击源及封禁优先级" />
        <div class="flex items-center gap-2">
          <Button class="flex-1" :disabled="aiLoading || !aiInput.trim()" @click="sendAiMessage()">
            <Loader2 v-if="aiLoading" class="h-4 w-4 mr-2 animate-spin" />
            <Send v-else class="h-4 w-4 mr-2" />
            {{ aiLoading ? '分析中...' : '发送' }}
          </Button>
          <Button variant="outline" :disabled="aiLoading" @click="router.push('/ai')">
            <Clock class="h-4 w-4" />
          </Button>
        </div>
      </div>
    </CardContent>
  </Card>
</template>
