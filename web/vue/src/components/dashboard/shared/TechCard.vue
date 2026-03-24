<script setup lang="ts">
import { computed } from 'vue'
import { useUiStore } from '@/stores/ui'

interface Props {
  title?: string
  icon?: any
  glowColor?: 'cyan' | 'green' | 'orange' | 'red'
  class?: string
}

const props = withDefaults(defineProps<Props>(), {
  glowColor: 'cyan'
})

const uiStore = useUiStore()
const isDark = computed(() => uiStore.theme === 'dark')

const glowColors = computed(() => ({
cyan: isDark.value ? 'before:from-primary/60' : 'before:from-primary/40',
  green: isDark.value ? 'before:from-green-500/70' : 'before:from-emerald-500/55',
  orange: isDark.value ? 'before:from-orange-500/70' : 'before:from-orange-500/55',
  red: isDark.value ? 'before:from-red-500/70' : 'before:from-red-500/55'
}))
</script>

<template>
  <div
    :class="[
      'relative rounded-xl overflow-hidden transition-all duration-300',
      isDark
        ? 'bg-card/20 border border-border/15'
        : 'bg-gradient-to-br from-card/96 to-secondary/35 border border-border/55 shadow-[0_12px_28px_hsl(var(--primary)/0.08)]',
      'before:absolute before:inset-[-1px] before:rounded-xl before:p-[1px]',
      'before:bg-gradient-to-br before:to-transparent before:opacity-20',
      'before:pointer-events-none before:-z-10',
      glowColors[glowColor],
      props.class
    ]"
  >
    <div v-if="title" class="flex items-center gap-2 px-3 py-2 border-b" :class="isDark ? 'border-border/10 bg-gradient-to-r from-transparent via-white/5 to-transparent' : 'border-border/50 bg-gradient-to-r from-primary/5 via-white/80 to-transparent'">
<component v-if="icon" :is="icon" class="w-3.5 h-3.5" :class="isDark ? 'text-primary' : 'text-primary'" />
      <h3 class="text-xs font-semibold text-foreground tracking-wide">{{ title }}</h3>
    </div>

    <div class="p-2.5">
      <slot />
    </div>
  </div>
</template>
