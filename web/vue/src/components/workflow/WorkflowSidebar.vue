<script setup lang="ts">
import type { WorkflowRecord } from '@/api/workflow'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'

const props = defineProps<{
  workflows: WorkflowRecord[]
  selectedWorkflowId: number | null
}>()

const emits = defineEmits<{
  create: []
  select: [workflow: WorkflowRecord]
}>()
</script>

<template>
  <Card class="h-full min-h-0 border-border/60 bg-card/80">
    <CardHeader class="space-y-3">
      <div class="flex items-center justify-between gap-3">
        <CardTitle>工作流</CardTitle>
        <Button size="sm" class="cursor-pointer" @click="emits('create')">新建</Button>
      </div>
    </CardHeader>

    <CardContent class="min-h-0 px-3 pb-3">
      <ScrollArea class="h-[640px] pr-2">
        <div class="space-y-2">
          <button
            v-for="workflow in props.workflows"
            :key="workflow.id"
            type="button"
            class="flex w-full cursor-pointer flex-col items-start gap-2 rounded-lg border px-3 py-3 text-left transition-colors hover:border-primary/40 hover:bg-primary/5"
            :class="workflow.id === props.selectedWorkflowId ? 'border-primary/50 bg-primary/10' : 'border-border/60 bg-background/60'"
            @click="emits('select', workflow)"
          >
            <div class="flex w-full items-center justify-between gap-2">
              <span class="line-clamp-1 font-medium text-foreground">{{ workflow.name }}</span>
              <Badge variant="secondary">{{ workflow.status }}</Badge>
            </div>
            <p class="line-clamp-2 text-xs text-muted-foreground">{{ workflow.description || '暂无描述' }}</p>
          </button>
        </div>
      </ScrollArea>
    </CardContent>
  </Card>
</template>
