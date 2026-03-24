<script setup lang="ts">
import { MessageSquare, Plus, Trash2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'

interface Session {
  id: number
  title: string
  created_at: string
}

const props = defineProps<{
  sessions: Session[]
  currentSession: number | null
}>()

const emit = defineEmits<{
  (e: 'newChat'): void
  (e: 'loadMessages', id: number): void
  (e: 'deleteSession', id: number): void
}>()

function getSessionTitle(session: Session) {
  const title = session.title?.trim()
  return title || `会话 #${session.id}`
}

function formatSessionTime(value?: string) {
  if (!value) return '刚刚创建'

  const normalized = value.includes('T') ? value : value.replace(' ', 'T')
  const date = new Date(normalized)

  if (Number.isNaN(date.getTime())) {
    return value.slice(0, 16)
  }

  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

function handleSessionKeydown(event: KeyboardEvent, id: number) {
  if (event.key !== 'Enter' && event.key !== ' ') return
  event.preventDefault()
  emit('loadMessages', id)
}
</script>

<template>
  <aside class="z-10 flex h-full w-[272px] shrink-0 flex-col overflow-hidden border-r border-border/55 bg-gradient-to-b from-card/35 via-background/15 to-transparent backdrop-blur-xl transition-all">
    <div class="flex items-center justify-between border-b border-border/45 px-4 py-3.5">
      <div class="flex min-w-0 items-center gap-2.5">
        <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-border/60 bg-gradient-to-br from-card/85 to-secondary/35 shadow-sm">
          <MessageSquare :size="17" class="text-primary" />
        </div>
        <div class="min-w-0">
          <h2 class="truncate text-sm font-semibold tracking-[0.08em] text-foreground/90">会话记录</h2>
          <p class="mt-0.5 text-[11px] text-muted-foreground">最近的 AI 对话历史</p>
        </div>
      </div>

      <Button
        variant="ghost"
        size="icon"
        title="新对话"
        class="h-9 w-9 shrink-0 rounded-xl border border-border/60 bg-card/55 shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:bg-primary hover:text-primary-foreground"
        @click="emit('newChat')"
      >
        <Plus :size="18" />
      </Button>
    </div>

    <ScrollArea class="min-w-0 flex-1 px-2 py-3">
      <div class="w-full max-w-full overflow-x-hidden">
        <div
          v-if="!props.sessions.length"
          class="mx-1 flex flex-col items-center justify-center rounded-xl border border-dashed border-border/55 bg-card/30 px-4 py-10 text-center"
        >
          <div class="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl border border-border/50 bg-gradient-to-br from-card/80 to-secondary/25 text-muted-foreground shadow-sm">
            <MessageSquare :size="20" />
          </div>
          <div class="text-sm font-medium text-foreground/85">暂无历史会话</div>
          <div class="mt-1 max-w-[180px] text-xs leading-5 text-muted-foreground">发起新的对话后，记录会按时间顺序展示在这里。</div>
        </div>

        <div v-else class="space-y-1 px-1">
          <div
            v-for="s in props.sessions"
            :key="s.id"
            role="button"
            tabindex="0"
            class="group relative flex min-w-0 max-w-full items-start gap-2 overflow-hidden rounded-lg px-2.5 py-2.5 outline-none transition-all duration-200"
            :class="[
              props.currentSession === s.id
                ? 'bg-primary/10 shadow-[0_6px_16px_hsl(var(--primary)/0.08)] ring-1 ring-primary/15'
                : 'bg-transparent hover:bg-background/45'
            ]"
            @click="emit('loadMessages', s.id)"
            @keydown="handleSessionKeydown($event, s.id)"
          >
            <div
              class="absolute inset-y-2 left-0 w-0.5 rounded-r-full bg-primary transition-all duration-200"
              :class="props.currentSession === s.id ? 'opacity-100' : 'opacity-0 group-hover:opacity-60'"
            ></div>

            <div class="mt-[7px] h-2 w-2 shrink-0 rounded-full transition-colors"
              :class="props.currentSession === s.id ? 'bg-primary shadow-[0_0_10px_hsl(var(--primary)/0.55)]' : 'bg-border/80 group-hover:bg-primary/55'"
              aria-hidden="true"
            ></div>

            <div class="min-w-0 max-w-full flex-1 pr-1">
              <div
                class="truncate text-sm font-semibold leading-5 transition-colors"
                :class="props.currentSession === s.id ? 'text-primary' : 'text-foreground/90'"
                :title="getSessionTitle(s)"
              >
                {{ getSessionTitle(s) }}
              </div>

              <div class="mt-1 flex min-w-0 items-center gap-2 text-[11px] text-muted-foreground">
                <span class="truncate">{{ formatSessionTime(s.created_at) }}</span>
                <span class="h-1 w-1 shrink-0 rounded-full bg-border/80" aria-hidden="true"></span>
                <span class="shrink-0 rounded-full border border-border/55 bg-background/55 px-1.5 py-0.5 leading-none text-[10px] text-foreground/70">
                  #{{ s.id }}
                </span>
                <span
                  v-if="props.currentSession === s.id"
                  class="shrink-0 rounded-full border border-primary/20 bg-primary/10 px-1.5 py-0.5 leading-none text-[10px] font-medium text-primary"
                >
                  当前
                </span>
              </div>
            </div>

            <Button
              variant="ghost"
              size="icon"
              class="mt-0.5 h-7 w-7 shrink-0 rounded-md border border-border/35 bg-background/30 text-muted-foreground/90 shadow-none transition-all duration-200 hover:border-destructive/20 hover:bg-destructive/10 hover:text-destructive"
              :class="props.currentSession === s.id ? 'text-foreground/80' : ''"
              :title="`删除 ${getSessionTitle(s)}`"
              @click.stop="emit('deleteSession', s.id)"
            >
              <Trash2 :size="13" />
            </Button>
          </div>
        </div>
      </div>
    </ScrollArea>
  </aside>
</template>
