<script setup lang="ts">
import type { NodeProps } from '@vue-flow/core'
import { Badge } from '@/components/ui/badge'
import { Node, NodeContent, NodeDescription, NodeFooter, NodeHeader, NodeTitle } from '@/components/ai-elements/node'
import { workflowCategoryMeta } from '@/lib/workflow/defaults'

const props = defineProps<NodeProps>()
const data = (props.data ?? {}) as Record<string, any>
const kind = String(data.kind || props.type || 'system')
const category = workflowCategoryMeta[props.type || 'system'] ?? workflowCategoryMeta.system
</script>

<template>
  <Node :handles="data.handles ?? { target: true, source: true }">
    <NodeHeader>
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <NodeTitle>{{ data.label || '未命名节点' }}</NodeTitle>
          <NodeDescription>{{ data.description || '暂无描述' }}</NodeDescription>
        </div>
        <Badge variant="secondary" :class="category.color">{{ category.label }}</Badge>
      </div>
    </NodeHeader>

    <NodeContent>
      <div class="space-y-2 text-sm text-muted-foreground">
        <div class="font-medium text-foreground">节点类型：{{ kind }}</div>
        <div v-if="data.config" class="rounded-md border border-border/60 bg-background/60 px-2 py-2 text-xs leading-relaxed break-all">
          {{ JSON.stringify(data.config, null, 2) }}
        </div>
      </div>
    </NodeContent>

    <NodeFooter>
      <div class="flex w-full items-center justify-between text-xs text-muted-foreground">
        <span>ID: {{ props.id }}</span>
        <span>Workflow</span>
      </div>
    </NodeFooter>
  </Node>
</template>
