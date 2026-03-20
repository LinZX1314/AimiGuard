<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  title?: string
  icon?: any
  glowColor?: 'cyan' | 'green' | 'orange' | 'red'
  class?: string
}

const props = withDefaults(defineProps<Props>(), {
  glowColor: 'cyan'
})

const glowColors = computed(() => ({
  cyan: 'before:from-cyan-500',
  green: 'before:from-green-500', 
  orange: 'before:from-orange-500',
  red: 'before:from-red-500'
}))
</script>

<template>
  <div
    :class="[
      'relative rounded-md overflow-hidden',
      'bg-gradient-to-br from-card/20 to-card/10',
      'border border-border/15 backdrop-blur-md',
      // 发光边框效果
      'before:absolute before:inset-[-1px] before:rounded-md before:p-[1px]',
      'before:bg-gradient-to-br before:to-transparent before:opacity-20',
      'before:pointer-events-none before:-z-10',
      glowColors[glowColor],
      props.class
    ]"
  >
    <div v-if="title" class="flex items-center gap-2 px-2.5 py-1.5 border-b border-border/10 bg-gradient-to-r from-transparent via-white/5 to-transparent">
      <component v-if="icon" :is="icon" class="w-3.5 h-3.5 text-cyan-400" />
      <h3 class="text-xs font-medium text-foreground">{{ title }}</h3>
    </div>

    <div class="p-2.5">
      <slot />
    </div>
  </div>
</template>
