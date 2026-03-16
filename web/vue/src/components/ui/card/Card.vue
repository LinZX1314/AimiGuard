<script setup lang="ts">
import type { HTMLAttributes } from "vue"
import { cn } from "@/lib/utils"

const props = defineProps<{
  class?: HTMLAttributes["class"]
}>()
</script>

<template>
  <div
    :class="
      cn(
        'rounded-xl border bg-card text-card-foreground backdrop-blur-2xl transition-all duration-500',
        'light:border-slate-200/50 light:bg-white/70 shadow-md hover:shadow-2xl hover:border-slate-300 drop-shadow-sm',
        'dark:bg-slate-900/40 dark:border-white/[0.08] dark:shadow-[0_4px_24px_rgba(0,0,0,0.6)] dark:hover:bg-slate-800/40 dark:hover:border-primary/50 dark:hover:shadow-[0_0_30px_rgba(0,229,255,0.2)]',
        props.class,
      )
    "
  >
    <slot />
  </div>
</template>
