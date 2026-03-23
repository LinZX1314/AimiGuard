<script setup lang="ts">
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

function statusVariant(status: string) {
  if (status === 'success') return 'default'
  if (status === 'running') return 'secondary'
  return 'destructive'
}
</script>

<template>
  <Card class="border-border/60 bg-card/80">
    <CardHeader>
      <CardTitle>运行历史</CardTitle>
      <CardDescription>查看最近执行结果，点击详情查看步骤级输入输出。</CardDescription>
    </CardHeader>
    <CardContent class="space-y-3">
      <div v-if="loading" class="rounded-xl border border-dashed border-border/60 p-6 text-sm text-muted-foreground">
        正在加载运行历史...
      </div>
      <div v-else-if="!runs.length" class="rounded-xl border border-dashed border-border/60 p-6 text-sm text-muted-foreground">
        暂无运行记录。
      </div>
      <div v-else class="space-y-3">
        <div v-for="run in runs" :key="run.id" class="rounded-xl border border-border/60 bg-background/60 p-4">
          <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div class="space-y-2">
              <div class="flex flex-wrap items-center gap-2">
                <Badge :variant="statusVariant(run.status)">{{ run.status }}</Badge>
                <span class="text-xs text-muted-foreground">{{ run.trigger_type }}</span>
              </div>
              <div class="text-sm font-medium text-foreground">#{{ run.id }} · {{ run.summary || '暂无摘要' }}</div>
              <div class="text-xs text-muted-foreground">
                {{ run.started_at || '—' }} → {{ run.ended_at || '进行中' }} · steps: {{ run.steps_count ?? run.steps?.length ?? 0 }}
              </div>
            </div>
            <Button type="button" variant="outline" class="min-h-11 cursor-pointer" @click="emit('selectRun', run.id)">查看详情</Button>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>
