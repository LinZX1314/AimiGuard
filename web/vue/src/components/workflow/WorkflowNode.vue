<script setup lang="ts">
import { computed } from 'vue'
import type { NodeProps } from '@vue-flow/core'
import { Badge } from '@/components/ui/badge'
import { Node, NodeContent, NodeDescription, NodeFooter, NodeHeader, NodeTitle } from '@/components/ai-elements/node'
import { summarizeNodeConfig, workflowCategoryMeta } from '@/lib/workflow/defaults'

const props = defineProps<NodeProps>()
const data = computed(() => (props.data ?? {}) as Record<string, any>)
const kind = computed(() => String(data.value.kind || 'system'))
const categoryKey = computed(() => String(data.value.category || 'system'))
const category = computed(() => workflowCategoryMeta[categoryKey.value] ?? workflowCategoryMeta.system)
const configSummary = computed(() => summarizeNodeConfig(kind.value, (data.value.config ?? {}) as Record<string, unknown>))
</script>

<template>
  <Node :handles="data.handles ?? { target: true, source: true }">
    <NodeHeader>
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0 space-y-1">
          <NodeTitle>{{ data.label || '未命名节点' }}</NodeTitle>
          <NodeDescription>{{ data.description || '暂无描述' }}</NodeDescription>
        </div>
        <Badge variant="secondary" :class="category.color">{{ category.label }}</Badge>
      </div>
    </NodeHeader>

    <NodeContent>
      <div class="space-y-3 text-sm text-muted-foreground">
        <div class="font-medium text-foreground">节点类型：{{ kind }}</div>
        <div v-if="configSummary.length" class="flex flex-wrap gap-2">
          <span
            v-for="item in configSummary"
            :key="item"
            class="rounded-full border border-border/60 bg-background/70 px-2.5 py-1 text-[11px] leading-none text-foreground/85"
          >
            {{ item }}
          </span>
        </div>
      </div>
    </NodeContent>

    <NodeFooter>
      <div class="flex w-full items-center justify-between text-xs text-muted-foreground">
        <span>ID: {{ props.id }}</span>
        <span>{{ category.label }}</span>
      </div>
    </NodeFooter>
  </Node>
</template>
