<script setup lang="ts">
import type { TabsTriggerProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { reactiveOmit } from "@vueuse/core"
import { TabsTrigger, useForwardProps } from "reka-ui"
import { cn } from "@/lib/utils"

const props = defineProps<TabsTriggerProps & { class?: HTMLAttributes["class"] }>()

const delegatedProps = reactiveOmit(props, "class")

const forwardedProps = useForwardProps(delegatedProps)
</script>

<template>
  <TabsTrigger
    v-bind="forwardedProps"
    :class="cn(
      'inline-flex items-center justify-center whitespace-nowrap rounded-xl px-3.5 py-1.5 text-sm font-medium text-foreground/74 ring-offset-background transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/18 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 data-[state=active]:border data-[state=active]:border-border/70 data-[state=active]:bg-gradient-to-br data-[state=active]:from-card/96 data-[state=active]:via-secondary/24 data-[state=active]:to-muted/22 data-[state=active]:text-foreground data-[state=active]:shadow-[0_8px_20px_rgba(67,84,109,0.10)] dark:text-foreground/70 dark:data-[state=active]:border-white/[0.06] dark:data-[state=active]:bg-background/50 dark:data-[state=active]:shadow-sm',
      props.class,
    )"
  >
    <span class="truncate">
      <slot />
    </span>
  </TabsTrigger>
</template>
