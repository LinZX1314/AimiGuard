<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { WorkflowDefinition, WorkflowNodeConfig } from '@/api/workflow'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

const props = defineProps<{
  definition: WorkflowDefinition
  selectedNodeId?: string | null
}>()

const emit = defineEmits<{
  update: [definition: WorkflowDefinition]
}>()

const selectedNode = computed<WorkflowNodeConfig | null>(() => props.definition.nodes.find((node) => node.id === props.selectedNodeId) ?? null)

const labelValue = ref('')
const descriptionValue = ref('')
const scheduleInterval = ref('60')
const hfishLimit = ref('10')
const hfishServiceName = ref('')
const aiPrompt = ref('')
const sourceValue = ref('trigger_payload')
const pathValue = ref('severity')
const operatorValue = ref('eq')
const expectedValue = ref('high')
const logLevel = ref('INFO')
const logMessage = ref('')
const notifyTitle = ref('')
const notifyMessage = ref('')
const apiEndpoint = ref('/api/v1/overview/chain-status')
const apiMethod = ref('GET')

watch(
  selectedNode,
  (node) => {
    const config = (node?.data.config ?? {}) as Record<string, unknown>
    labelValue.value = node?.data.label ?? ''
    descriptionValue.value = node?.data.description ?? ''
    scheduleInterval.value = String(config.interval_seconds ?? 60)
    hfishLimit.value = String(config.limit ?? 10)
    hfishServiceName.value = String(config.service_name ?? '')
    aiPrompt.value = String(config.prompt ?? '')
    sourceValue.value = String(config.source ?? 'trigger_payload')
    pathValue.value = String(config.path ?? 'severity')
    operatorValue.value = String(config.operator ?? 'eq')
    expectedValue.value = String(config.expected ?? 'high')
    logLevel.value = String(config.level ?? 'INFO')
    logMessage.value = String(config.message ?? '')
    notifyTitle.value = String(config.title ?? '')
    notifyMessage.value = String(config.message ?? '')
    apiEndpoint.value = String(config.endpoint ?? '/api/v1/overview/chain-status')
    apiMethod.value = String(config.method ?? 'GET').toUpperCase()
  },
  { immediate: true },
)

function updateNode(patch: Partial<WorkflowNodeConfig['data']>) {
  if (!selectedNode.value) return
  emit('update', {
    nodes: props.definition.nodes.map((node) =>
      node.id === selectedNode.value?.id
        ? {
            ...node,
            data: {
              ...node.data,
              ...patch,
            },
          }
        : node,
    ),
    edges: props.definition.edges,
  })
}

function buildConfigForKind(kind: string) {
  if (kind === 'schedule') {
    return { interval_seconds: Number(scheduleInterval.value) || 60 }
  }
  if (kind === 'query_hfish_logs') {
    return {
      limit: Number(hfishLimit.value) || 10,
      ...(hfishServiceName.value ? { service_name: hfishServiceName.value } : {}),
    }
  }
  if (kind === 'generate_ai_summary') {
    return {
      ...(aiPrompt.value ? { prompt: aiPrompt.value } : {}),
    }
  }
  if (kind === 'condition') {
    return {
      source: sourceValue.value,
      path: pathValue.value,
      operator: operatorValue.value,
      expected: expectedValue.value,
    }
  }
  if (kind === 'write_log') {
    return {
      level: logLevel.value,
      ...(logMessage.value ? { message: logMessage.value } : {}),
    }
  }
  if (kind === 'notify_in_app') {
    return {
      ...(notifyTitle.value ? { title: notifyTitle.value } : {}),
      ...(notifyMessage.value ? { message: notifyMessage.value } : {}),
    }
  }
  if (kind === 'call_internal_api') {
    return {
      endpoint: apiEndpoint.value || '/api/v1/overview/chain-status',
      method: apiMethod.value || 'GET',
    }
  }
  return {}
}

function applyMetadata() {
  const kind = String(selectedNode.value?.data.kind || '')
  updateNode({
    label: labelValue.value,
    description: descriptionValue.value,
    config: buildConfigForKind(kind),
  })
}
</script>

<template>
  <Card class="border-border/60 bg-card/80">
    <CardHeader>
      <CardTitle>属性检查器</CardTitle>
      <CardDescription>编辑选中节点的标题、说明和业务配置，不再直接显示原始 JSON。</CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">
      <template v-if="selectedNode">
        <div class="space-y-2">
          <Label for="workflow-node-label">节点标题</Label>
          <Input id="workflow-node-label" v-model="labelValue" class="min-h-11" />
        </div>
        <div class="space-y-2">
          <Label for="workflow-node-description">节点说明</Label>
          <Textarea id="workflow-node-description" v-model="descriptionValue" class="min-h-24" />
        </div>

        <div v-if="selectedNode.data.kind === 'schedule'" class="space-y-2 rounded-xl border border-border/60 bg-background/60 p-4">
          <Label>执行间隔（秒）</Label>
          <Input v-model="scheduleInterval" class="min-h-11" type="number" min="1" />
        </div>

        <div v-else-if="selectedNode.data.kind === 'query_hfish_logs'" class="grid gap-3 rounded-xl border border-border/60 bg-background/60 p-4 md:grid-cols-2">
          <div class="space-y-2">
            <Label>最大读取条数</Label>
            <Input v-model="hfishLimit" class="min-h-11" type="number" min="1" />
          </div>
          <div class="space-y-2">
            <Label>服务名过滤</Label>
            <Input v-model="hfishServiceName" class="min-h-11" placeholder="可选，如 ssh / http" />
          </div>
        </div>

        <div v-else-if="selectedNode.data.kind === 'generate_ai_summary'" class="space-y-2 rounded-xl border border-border/60 bg-background/60 p-4">
          <Label>AI 提示词</Label>
          <Textarea v-model="aiPrompt" class="min-h-28" placeholder="可选，自定义摘要提示词" />
        </div>

        <div v-else-if="selectedNode.data.kind === 'condition'" class="space-y-3 rounded-xl border border-border/60 bg-background/60 p-4">
          <div class="text-sm font-medium text-foreground">条件分支设置</div>
          <div class="grid gap-3 md:grid-cols-2">
            <div class="space-y-2">
              <Label>数据来源</Label>
              <Input v-model="sourceValue" class="min-h-11" />
            </div>
            <div class="space-y-2">
              <Label>路径</Label>
              <Input v-model="pathValue" class="min-h-11" />
            </div>
            <div class="space-y-2">
              <Label>操作符</Label>
              <Input v-model="operatorValue" class="min-h-11" />
            </div>
            <div class="space-y-2">
              <Label>期望值</Label>
              <Input v-model="expectedValue" class="min-h-11" />
            </div>
          </div>
        </div>

        <div v-else-if="selectedNode.data.kind === 'write_log'" class="grid gap-3 rounded-xl border border-border/60 bg-background/60 p-4 md:grid-cols-2">
          <div class="space-y-2">
            <Label>日志级别</Label>
            <Input v-model="logLevel" class="min-h-11" placeholder="INFO / WARN / ERROR" />
          </div>
          <div class="space-y-2 md:col-span-2">
            <Label>日志消息</Label>
            <Textarea v-model="logMessage" class="min-h-24" placeholder="可选，不填则自动使用上一步输出" />
          </div>
        </div>

        <div v-else-if="selectedNode.data.kind === 'notify_in_app'" class="grid gap-3 rounded-xl border border-border/60 bg-background/60 p-4 md:grid-cols-2">
          <div class="space-y-2">
            <Label>通知标题</Label>
            <Input v-model="notifyTitle" class="min-h-11" />
          </div>
          <div class="space-y-2 md:col-span-2">
            <Label>通知内容</Label>
            <Textarea v-model="notifyMessage" class="min-h-24" placeholder="可选，不填则自动使用上一步输出" />
          </div>
        </div>

        <div v-else-if="selectedNode.data.kind === 'call_internal_api'" class="grid gap-3 rounded-xl border border-border/60 bg-background/60 p-4 md:grid-cols-2">
          <div class="space-y-2 md:col-span-2">
            <Label>API 路径</Label>
            <Input v-model="apiEndpoint" class="min-h-11" placeholder="/api/v1/overview/chain-status" />
          </div>
          <div class="space-y-2">
            <Label>请求方法</Label>
            <Input v-model="apiMethod" class="min-h-11" placeholder="GET / POST" />
          </div>
        </div>

        <Button type="button" class="min-h-11 w-full cursor-pointer" @click="applyMetadata">保存节点配置</Button>
      </template>
      <div v-else class="rounded-xl border border-dashed border-border/60 p-6 text-sm text-muted-foreground">
        请选择一个节点查看或编辑配置。
      </div>
    </CardContent>
  </Card>
</template>
