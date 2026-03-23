<script setup lang="ts">
import { ref } from 'vue'
import { Send, Copy, Check } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'

const props = defineProps<{
  command: string
}>()

const emit = defineEmits<{
  (e: 'send', command: string): void
}>()

const copied = ref(false)

function handleSend() {
  emit('send', props.command)
}

async function handleCopy() {
  try {
    await navigator.clipboard.writeText(props.command)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (e) {
    console.error('Failed to copy:', e)
  }
}
</script>

<template>
  <div class="bg-muted/50 border rounded-lg px-3 py-2 flex items-center justify-between gap-2 hover:bg-muted/70 transition-colors">
    <code class="text-sm font-mono text-foreground flex-1 truncate">{{ command }}</code>
    <div class="flex items-center gap-1 shrink-0">
      <Button
        variant="ghost"
        size="icon"
        class="h-7 w-7"
        @click="handleCopy"
        :title="copied ? '已复制' : '复制命令'"
      >
        <component :is="copied ? Check : Copy" :size="14" :class="copied ? 'text-green-500' : ''" />
      </Button>
      <Button
        size="sm"
        variant="default"
        class="h-7 text-xs"
        @click="handleSend"
      >
        <Send :size="12" class="mr-1" />
        发送
      </Button>
    </div>
  </div>
</template>
