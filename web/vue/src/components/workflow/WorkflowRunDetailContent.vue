<script setup lang="ts">
import type { WorkflowRunRecord } from '@/api/workflow'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

defineProps<{
  run: WorkflowRunRecord | null
}>()

function formatJson(value: unknown) {
  return JSON.stringify(value ?? null, null, 2)
}
</script>

<template>
  <div v-if="run" class="space-y-4">
    <Card class="border-border/60 bg-card/80">
      <CardHeader>
        <div class="flex flex-wrap items-center gap-2">
          <CardTitle>运行 #{{ run.id }}</CardTitle>
          <Badge :variant="run.status === 'success' ? 'default' : run.status === 'running' ? 'secondary' : 'destructive'">
            {{ run.status }}
          </Badge>
          <Badge variant="outline">{{ run.trigger_type }}</Badge>
        </div>
        <CardDescription>{{ run.summary || '暂无摘要' }}</CardDescription>
      </CardHeader>
      <CardContent class="grid gap-3 text-sm md:grid-cols-2">
        <div>
          <div class="text-xs uppercase tracking-wide text-muted-foreground">开始时间</div>
          <div>{{ run.started_at || '—' }}</div>
        </div>
        <div>
          <div class="text-xs uppercase tracking-wide text-muted-foreground">结束时间</div>
          <div>{{ run.ended_at || '进行中' }}</div>
        </div>
        <div class="md:col-span-2">
          <div class="text-xs uppercase tracking-wide text-muted-foreground">触发 payload</div>
          <pre class="mt-2 overflow-auto rounded-xl bg-background p-3 text-xs">{{ formatJson(run.trigger_payload) }}</pre>
        </div>
      </CardContent>
    </Card>

    <Card class="border-border/60 bg-card/80">
      <CardHeader>
        <CardTitle>步骤详情</CardTitle>
        <CardDescription>逐步查看节点执行输入、输出与错误信息。</CardDescription>
      </CardHeader>
      <CardContent>
        <Accordion type="multiple" class="space-y-3">
          <AccordionItem v-for="step in run.steps || []" :key="step.id" :value="String(step.id)" class="rounded-xl border border-border/60 px-4">
            <AccordionTrigger class="cursor-pointer text-left">
              <div class="flex flex-col gap-1">
                <span class="font-medium">{{ step.node_name || step.node_id }} · {{ step.status }}</span>
                <span class="text-xs text-muted-foreground">{{ step.started_at || '—' }} → {{ step.ended_at || '—' }}</span>
              </div>
            </AccordionTrigger>
            <AccordionContent class="space-y-3 pb-4">
              <div>
                <div class="mb-1 text-xs uppercase tracking-wide text-muted-foreground">输入</div>
                <pre class="overflow-auto rounded-xl bg-background p-3 text-xs">{{ formatJson(step.input) }}</pre>
              </div>
              <div>
                <div class="mb-1 text-xs uppercase tracking-wide text-muted-foreground">输出</div>
                <pre class="overflow-auto rounded-xl bg-background p-3 text-xs">{{ formatJson(step.output) }}</pre>
              </div>
              <div v-if="step.error_message">
                <div class="mb-1 text-xs uppercase tracking-wide text-muted-foreground">错误</div>
                <pre class="overflow-auto rounded-xl bg-background p-3 text-xs text-red-400">{{ step.error_message }}</pre>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </CardContent>
    </Card>
  </div>
  <div v-else class="rounded-xl border border-dashed border-border/60 p-8 text-sm text-muted-foreground">
    请选择一条运行记录查看详情。
  </div>
</template>
