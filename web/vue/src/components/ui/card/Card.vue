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
        'rounded-xl border backdrop-blur-2xl transition-all duration-500 text-card-foreground relative',
        
        /* Light mode base */
        'bg-gradient-to-br from-white/90 to-white/40 border-white/60 shadow-[0_8px_32px_rgba(0,0,0,0.04)]',
        /* Light mode hover */
        'hover:shadow-[0_12px_40px_rgba(0,0,0,0.08)] hover:border-white hover:from-white/95 hover:to-white/60',
        
        /* Dark mode base */
        'dark:bg-gradient-to-br dark:from-slate-900/60 dark:to-slate-900/20 dark:border-white/[0.08] dark:shadow-[0_8px_32px_rgba(0,0,0,0.4)]',
        /* Dark mode hover */
'dark:hover:from-slate-800/80 dark:hover:to-slate-900/40 dark:hover:border-primary/40 dark:hover:shadow-[0_0_30px_rgba(59,130,246,0.15)]',
        
        /* Inner 3D rim lighting */
        'after:pointer-events-none after:absolute after:inset-0 after:rounded-xl after:border after:border-white/20 dark:after:border-white/5 after:mix-blend-overlay',
        
        props.class,
      )
    "
  >
    <slot />
  </div>
</template>
