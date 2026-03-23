<script setup lang="ts">
import { computed } from 'vue'
import type { WorkflowRunRecord } from '@/api/workflow'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

const props = defineProps<{
  runs: WorkflowRunRecord[]
  loading?: boolean
}>()

const emit = defineEmits<{
  selectRun: [runId: number]
}>()

const recentRuns = computed(() => props.runs.slice(0, 8))

function statusVariant(status: string) {
  if (status === 'success' || status === 'success_with_skips') return 'default'
  if (status === 'running') return 'secondary'
  return 'destructive'
}

function statusLabel(status: string) {
  if (status === 'success_with_skips') return '成功(含跳过)'
  if (status === 'success') return '成功'
  if (status === 'running') return '运行中'
  return '失败'
}
</script>

<template>
  <Card class="border-border/60 bg-card/80">
    <CardHeader class="pb-4">
      <CardTitle>最近运行</CardTitle>
      <CardDescription>查看最近执行结果，点击查看详情。</CardDescription>
    </CardHeader>
    <CardContent class="space-y-3">
      <div v-if="loading" class="rounded-xl border border-dashed border-border/60 p-5 text-sm text-muted-foreground">
        正在加载运行历史...
      </div>
      <div v-else-if="!recentRuns.length" class="rounded-xl border border-dashed border-border/60 p-5 text-sm text-muted-foreground">
        暂无运行记录。
      </div>
      <div v-else class="space-y-2">
        <div v-for="run in recentRuns" :key="run.id" class="rounded-xl border border-border/60 bg-background/60 p-3">
          <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div class="min-w-0 space-y-1.5">
              <div class="flex flex-wrap items-center gap-2">
                <Badge :variant="statusVariant(run.status)">{{ statusLabel(run.status) }}</Badge>
                <span class="text-xs text-muted-foreground">{{ run.trigger_type }}</span>
              </div>
              <div class="line-clamp-1 text-sm font-medium text-foreground">#{{ run.id }} · {{ run.summary || '暂无摘要' }}</div>
              <div class="text-xs text-muted-foreground">
                {{ run.started_at || '—' }} · {{ run.steps_count ?? run.steps?.length ?? 0 }} 步
              </div>
            </div>
            <Button type="button" size="sm" variant="outline" class="cursor-pointer" @click="emit('selectRun', run.id)">详情</Button>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>
