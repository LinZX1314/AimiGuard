<script setup lang="ts">
import { MessageSquare, Plus, Trash2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'

interface Session { id: number; title: string; created_at: string }

const props = defineProps<{
  sessions: Session[]
  currentSession: number | null
}>()

const emit = defineEmits<{
  (e: 'newChat'): void
  (e: 'loadMessages', id: number): void
  (e: 'deleteSession', id: number): void
}>()
</script>

<template>
  <aside class="w-72 shrink-0 bg-muted/30 border-r border-border flex flex-col backdrop-blur-xl z-10 transition-all">
    <div class="px-4 py-3.5 flex justify-between items-center border-b border-border/50">
      <h2 class="text-base font-semibold flex items-center m-0 opacity-90">
        <MessageSquare :size="20" class="mr-2" />
        会话记录
      </h2>
      <Button variant="ghost" size="icon" @click="emit('newChat')" title="新对话" class="h-9 w-9 rounded-full bg-background/5 border border-border hover:bg-foreground hover:text-background transition-all">
        <Plus :size="20" />
      </Button>
    </div>

    <ScrollArea class="flex-1 px-2 py-2">
      <div v-if="!sessions.length" class="text-center py-8 text-muted-foreground text-sm">
        暂无历史会话
      </div>
      <div class="flex flex-col rounded-lg border border-border/40 overflow-hidden divide-y divide-border/30 bg-background/10">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="group flex items-center justify-between py-2.5 px-3 cursor-pointer bg-transparent transition-all hover:bg-background/35"
          :class="[currentSession === s.id ? 'bg-primary/10' : '']"
          @click="emit('loadMessages', s.id)"
        >
          <div class="overflow-hidden flex-1">
            <div class="font-medium text-sm whitespace-nowrap overflow-hidden text-ellipsis" :class="[currentSession === s.id ? 'text-primary' : '']">
              {{ s.title || `会话 #${s.id}` }}
            </div>
            <div class="text-[11px] text-muted-foreground mt-0.5">{{ s.created_at?.slice(0,16) }}</div>
          </div>
          <Button variant="ghost" size="icon" class="h-7 w-7 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-opacity" @click.stop="emit('deleteSession', s.id)">
            <Trash2 :size="14" />
          </Button>
        </div>
      </div>
    </ScrollArea>
  </aside>
</template>
