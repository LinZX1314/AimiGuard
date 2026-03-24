<script setup lang="ts">
import type { TabsListProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { reactiveOmit } from "@vueuse/core"
import { TabsList } from "reka-ui"
import { cn } from "@/lib/utils"

const props = defineProps<TabsListProps & { class?: HTMLAttributes["class"] }>()

const delegatedProps = reactiveOmit(props, "class")
</script>

<template>
  <TabsList
    v-bind="delegatedProps"
    :class="cn(
      'inline-flex items-center justify-center gap-1 rounded-2xl border border-border/65 bg-gradient-to-r from-card/86 via-secondary/20 to-muted/18 p-1.5 text-muted-foreground shadow-[0_10px_24px_rgba(67,84,109,0.08)] backdrop-blur-sm dark:border-white/[0.06] dark:bg-background/35 dark:shadow-sm',
      props.class,
    )"
  >
    <slot />
  </TabsList>
</template>
