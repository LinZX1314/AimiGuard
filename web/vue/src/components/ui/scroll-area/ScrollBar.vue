<script setup lang="ts">
import type { ScrollAreaScrollbarProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { reactiveOmit } from "@vueuse/core"
import { ScrollAreaScrollbar, ScrollAreaThumb } from "reka-ui"
import { cn } from "@/lib/utils"

const props = withDefaults(defineProps<ScrollAreaScrollbarProps & { class?: HTMLAttributes["class"] }>(), {
  orientation: "vertical",
})

const delegatedProps = reactiveOmit(props, "class")
</script>

<template>
  <ScrollAreaScrollbar
    v-bind="delegatedProps"
    :class="
      cn(
        'flex touch-none select-none rounded-full bg-muted/28 backdrop-blur-sm transition-all duration-200 hover:bg-muted/40 dark:bg-white/[0.05] dark:hover:bg-white/[0.08]',
        orientation === 'vertical' && 'h-full w-3 p-[3px]',
        orientation === 'horizontal' && 'h-3 flex-col p-[3px]',
        props.class,
      )
    "
  >
    <ScrollAreaThumb
      class="relative flex-1 rounded-full border border-white/35 bg-gradient-to-b from-secondary/90 to-muted/70 shadow-[0_1px_6px_rgba(67,84,109,0.18)] before:absolute before:inset-[1px] before:rounded-full before:bg-white/20 before:opacity-70 dark:border-primary/20 dark:bg-gradient-to-b dark:from-primary/45 dark:to-primary/25 dark:shadow-[0_0_12px_hsl(var(--primary)/0.16)] dark:before:bg-white/10"
    />
  </ScrollAreaScrollbar>
</template>
