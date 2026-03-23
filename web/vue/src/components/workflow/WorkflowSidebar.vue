<script setup lang="ts">
import { computed } from 'vue'
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

const totalCount = computed(() => props.workflows.length)
</script>

<template>
  <Card class="h-full min-h-0 border-border/60 bg-card/80">
    <CardHeader class="space-y-3 pb-3">
      <div class="flex items-center justify-between gap-3">
        <div class="space-y-1">
          <CardTitle>工作流</CardTitle>
          <div class="text-xs text-muted-foreground">共 {{ totalCount }} 条</div>
        </div>
        <Button size="sm" variant="outline" class="cursor-pointer" @click="emits('create')">新建</Button>
      </div>
    </CardHeader>

    <CardContent class="min-h-0 px-3 pb-3">
      <ScrollArea class="h-[620px] pr-2">
        <div class="space-y-2">
          <button
            v-for="workflow in props.workflows"
            :key="workflow.id"
            type="button"
            class="flex w-full cursor-pointer flex-col items-start gap-2 rounded-xl border px-3 py-3 text-left transition-colors hover:border-primary/40 hover:bg-primary/5"
            :class="workflow.id === props.selectedWorkflowId ? 'border-primary/50 bg-primary/10' : 'border-border/60 bg-background/60'"
            @click="emits('select', workflow)"
          >
            <div class="flex w-full items-start justify-between gap-2">
              <div class="min-w-0 space-y-1">
                <div class="line-clamp-1 font-medium text-foreground">{{ workflow.name }}</div>
                <div class="flex flex-wrap items-center gap-1.5">
                  <Badge variant="secondary">{{ workflow.status }}</Badge>
                  <Badge variant="outline">{{ workflow.trigger.type || 'manual' }}</Badge>
                </div>
              </div>
            </div>
            <p class="line-clamp-2 text-xs text-muted-foreground">{{ workflow.description || '暂无描述' }}</p>
          </button>
        </div>
      </ScrollArea>
    </CardContent>
  </Card>
</template>
