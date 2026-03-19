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
    <div class="p-5 flex justify-between items-center border-b border-border/50">
      <h2 class="text-base font-semibold flex items-center m-0 opacity-90">
        <MessageSquare :size="20" class="mr-2" />
        会话记录
      </h2>
      <Button variant="ghost" size="icon" @click="emit('newChat')" title="新对话" class="h-9 w-9 rounded-full bg-background/5 border border-border hover:bg-foreground hover:text-background transition-all">
        <Plus :size="20" />
      </Button>
    </div>

    <ScrollArea class="flex-1 p-3">
      <div v-if="!sessions.length" class="text-center py-8 text-muted-foreground text-sm">
        暂无历史会话
      </div>
      <div class="flex flex-col gap-2">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="group flex items-center justify-between py-3 px-4 rounded-xl cursor-pointer bg-transparent transition-all border border-transparent hover:bg-background/40"
          :class="[currentSession === s.id ? 'bg-primary/10 border-primary/20' : '']"
          @click="emit('loadMessages', s.id)"
        >
          <div class="overflow-hidden flex-1">
            <div class="font-medium text-sm whitespace-nowrap overflow-hidden text-ellipsis mb-1" :class="[currentSession === s.id ? 'text-primary' : '']">
              {{ s.title || `会话 #${s.id}` }}
            </div>
            <div class="text-xs text-muted-foreground">{{ s.created_at?.slice(0,16) }}</div>
          </div>
          <Button variant="ghost" size="icon" class="h-8 w-8 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-opacity" @click.stop="emit('deleteSession', s.id)">
            <Trash2 :size="16" />
          </Button>
        </div>
      </div>
    </ScrollArea>
  </aside>
</template>
