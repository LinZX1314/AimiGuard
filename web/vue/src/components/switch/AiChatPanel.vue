<script setup lang="ts">
import { ref, nextTick, computed } from 'vue'
import { Bot, Send, Loader2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import AiCommandCard from './AiCommandCard.vue'
import { useSwitchWorkbenchStore } from '@/stores/switchWorkbench'
import { switchWorkbenchApi } from '@/api/switchWorkbench'

const emit = defineEmits<{
  (e: 'send-to-terminal', command: string): void
}>()

const store = useSwitchWorkbenchStore()
const inputText = ref('')
const sending = ref(false)
const messagesContainer = ref<HTMLDivElement | null>(null)

// 配置 marked
marked.setOptions({
  breaks: true,
  gfm: true,
})

// 构建对话历史
const conversationHistory = computed(() => {
  return store.aiMessages.map(msg => ({
    role: msg.role as 'user' | 'assistant',
    content: msg.content,
  }))
})

// 渲染 Markdown
function renderMarkdown(text: string): string {
  const html = marked.parse(text) as string
  return DOMPurify.sanitize(html)
}

// 获取最新的终端命令和回显
function getLatestTerminalInfo(): { command: string; output: string } {
  const messages = store.terminalMessages
  if (messages.length === 0) {
    return { command: '', output: '' }
  }

  // 找到最后一条发送的命令和对应的回显
  let lastCommand = ''
  let lastOutput = ''

  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i]
    if (msg.type === 'sent' && !lastCommand) {
      lastCommand = msg.content.trim()
    }
    if (msg.type === 'received' && !lastOutput) {
      lastOutput = msg.content
    }
    if (lastCommand && lastOutput) break
  }

  return { command: lastCommand, output: lastOutput }
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || sending.value) return

  sending.value = true
  inputText.value = ''

  // 添加用户消息
  store.appendAiMessage({
    role: 'user',
    content: text,
  })

  await scrollToBottom()

  // 获取终端上下文
  const terminalInfo = getLatestTerminalInfo()

  try {
    // 调用 AI 接口（使用真正的 AI 分析）
    const result = await switchWorkbenchApi.analyzeTurn({
      device_id: store.selectedDeviceId || undefined,
      prompt: text,
      command: terminalInfo.command,
      command_output: terminalInfo.output,
      conversation: conversationHistory.value.slice(-6), // 最多传最近6条对话
    })

    // 添加 AI 响应
    store.appendAiMessage({
      role: 'assistant',
      content: result.answer || result.summary || 'AI 已分析完成',
      commands: result.suggested_commands?.map((item: any) => item.command) || result.next_steps || [],
    })
  } catch (e: any) {
    store.appendAiMessage({
      role: 'assistant',
      content: `错误: ${e.message || 'AI 分析失败'}`,
    })
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

function handleSendCommand(command: string) {
  emit('send-to-terminal', command)
}

async function scrollToBottom() {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}
</script>

<template>
  <div class="flex flex-col h-full bg-card">
    <!-- 头部 -->
    <div class="shrink-0 flex items-center gap-2 px-4 py-3 border-b">
      <Bot :size="16" class="text-primary" />
      <span class="font-medium text-sm">AI 助手</span>
      <span class="text-xs text-muted-foreground">交换机命令生成</span>
    </div>

    <!-- 消息列表 -->
    <ScrollArea class="flex-1 min-h-0" ref="messagesContainer">
      <div class="p-4 space-y-4">
        <!-- 欢迎消息 -->
        <div v-if="store.aiMessages.length === 0" class="text-center py-8">
          <Bot :size="32" class="mx-auto text-muted-foreground/50 mb-2" />
          <p class="text-sm text-muted-foreground">
            描述您的需求，AI 将生成相应的交换机命令
          </p>
          <div class="mt-4 text-xs text-muted-foreground/70 space-y-1">
            <p>例如：</p>
            <p class="italic">"查看当前端口状态"</p>
            <p class="italic">"查看 VLAN 配置"</p>
            <p class="italic">"查看设备版本信息"</p>
          </div>
        </div>

        <!-- 消息列表 -->
        <div v-for="msg in store.aiMessages" :key="msg.id">
          <!-- 用户消息 -->
          <div v-if="msg.role === 'user'" class="flex justify-end">
            <div class="bg-primary text-primary-foreground rounded-lg px-3 py-2 max-w-[80%]">
              <p class="text-sm">{{ msg.content }}</p>
            </div>
          </div>

          <!-- AI 消息 -->
          <div v-else class="space-y-3">
            <div class="flex items-start gap-2">
              <Bot :size="16" class="text-primary mt-1 shrink-0" />
              <div class="bg-muted rounded-lg px-3 py-2 max-w-[85%]">
                <!-- 使用 v-html 渲染 Markdown -->
                <div class="text-sm markdown-content" v-html="renderMarkdown(msg.content)"></div>
              </div>
            </div>

            <!-- 命令卡片 -->
            <div v-if="msg.commands?.length" class="ml-6 space-y-2">
              <AiCommandCard
                v-for="(cmd, idx) in msg.commands"
                :key="idx"
                :command="cmd"
                @send="handleSendCommand"
              />
            </div>
          </div>
        </div>

        <!-- 加载指示器 -->
        <div v-if="sending" class="flex items-center gap-2 text-muted-foreground">
          <Loader2 :size="16" class="animate-spin" />
          <span class="text-sm">AI 正在分析...</span>
        </div>
      </div>
    </ScrollArea>

    <!-- 输入框 -->
    <div class="shrink-0 p-3 border-t">
      <form @submit.prevent="handleSend" class="flex gap-2">
        <Textarea
          v-model="inputText"
          placeholder="描述您的需求，例如：查看端口状态"
          rows="4"
          class="min-h-[88px] max-h-[150px] resize-none"
          @keydown.enter.prevent="handleSend"
        />
        <Button
          type="submit"
          size="icon"
          class="h-[48px] w-[48px] shrink-0"
          :disabled="!inputText.trim() || sending"
        >
          <Send :size="18" />
        </Button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3) {
  font-weight: 600;
  margin-top: 0.5em;
  margin-bottom: 0.25em;
}

.markdown-content :deep(code) {
  background-color: hsl(var(--muted));
  padding: 0.125em 0.375em;
  border-radius: 0.25em;
  font-family: monospace;
  font-size: 0.9em;
}

.markdown-content :deep(pre) {
  background-color: hsl(var(--muted));
  padding: 0.75em;
  border-radius: 0.375em;
  overflow-x: auto;
  margin: 0.5em 0;
}

.markdown-content :deep(pre code) {
  background: none;
  padding: 0;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  padding-left: 1.5em;
  margin: 0.5em 0;
}

.markdown-content :deep(li) {
  margin: 0.25em 0;
}

.markdown-content :deep(p) {
  margin: 0.5em 0;
}

.markdown-content :deep(p:first-child) {
  margin-top: 0;
}

.markdown-content :deep(p:last-child) {
  margin-bottom: 0;
}
</style>
