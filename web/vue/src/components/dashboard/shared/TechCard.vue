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
  glowColor: 'cyan',
})

const uiStore = useUiStore()
const isDark = computed(() => uiStore.theme === 'dark')

const glowColors = computed(() => ({
  cyan: isDark.value ? 'before:from-primary/60' : 'before:from-primary/35',
  green: isDark.value ? 'before:from-green-500/70' : 'before:from-emerald-500/45',
  orange: isDark.value ? 'before:from-orange-500/70' : 'before:from-orange-500/45',
  red: isDark.value ? 'before:from-red-500/70' : 'before:from-red-500/45',
}))
</script>

<template>
  <div
    :class="[
      'relative overflow-hidden rounded-xl transition-all duration-300',
      isDark
        ? 'border border-border/15 bg-gradient-to-br from-card/20 to-card/10 backdrop-blur-md'
        : 'border border-border/65 bg-gradient-to-br from-card/80 via-secondary/38 to-muted/30 shadow-[0_8px_18px_hsl(var(--primary)/0.06)]',
      'before:absolute before:inset-[-1px] before:-z-10 before:rounded-xl before:bg-gradient-to-br before:to-transparent before:p-[1px] before:opacity-20 before:pointer-events-none',
      glowColors[glowColor],
      props.class,
    ]"
  >
    <div
      v-if="title"
      class="flex items-center gap-2 border-b px-3 py-2"
      :class="isDark ? 'border-border/10 bg-gradient-to-r from-transparent via-white/5 to-transparent' : 'border-border/45 bg-gradient-to-r from-primary/6 via-secondary/75 to-transparent'"
    >
      <component v-if="icon" :is="icon" class="h-3.5 w-3.5 text-primary" />
      <h3 class="text-xs font-semibold tracking-wide text-foreground">{{ title }}</h3>
    </div>

    <div class="p-2.5">
      <slot />
    </div>
  </div>
</template>
