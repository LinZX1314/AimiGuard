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

const selectedNode = computed<WorkflowNodeConfig | null>(() =>
  props.definition.nodes.find((node) => node.id === props.selectedNodeId) ?? null,
)

const labelValue = ref('')
const descriptionValue = ref('')
const configText = ref('{}')
const sourceValue = ref('trigger_payload')
const pathValue = ref('severity')
const operatorValue = ref('eq')
const expectedValue = ref('high')

watch(
  selectedNode,
  (node) => {
    labelValue.value = node?.data.label ?? ''
    descriptionValue.value = node?.data.description ?? ''
    configText.value = JSON.stringify(node?.data.config ?? {}, null, 2)
    sourceValue.value = String(node?.data.config?.source ?? 'trigger_payload')
    pathValue.value = String(node?.data.config?.path ?? 'severity')
    operatorValue.value = String(node?.data.config?.operator ?? 'eq')
    expectedValue.value = String(node?.data.config?.expected ?? 'high')
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

function applyMetadata() {
  let parsedConfig: Record<string, unknown> = {}
  try {
    parsedConfig = JSON.parse(configText.value || '{}')
  } catch {
    parsedConfig = { raw: configText.value }
  }
  updateNode({
    label: labelValue.value,
    description: descriptionValue.value,
    config: parsedConfig,
  })
}

function applyCondition() {
  updateNode({
    config: {
      ...(selectedNode.value?.data.config ?? {}),
      source: sourceValue.value,
      path: pathValue.value,
      operator: operatorValue.value,
      expected: expectedValue.value,
    },
  })
}
</script>

<template>
  <Card class="border-border/60 bg-card/80">
    <CardHeader>
      <CardTitle>属性检查器</CardTitle>
      <CardDescription>编辑选中节点的标签、描述和配置。条件节点支持单独配置分支判断。</CardDescription>
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
        <div class="space-y-2">
          <Label for="workflow-node-config">节点配置 JSON</Label>
          <Textarea id="workflow-node-config" v-model="configText" class="min-h-40 font-mono text-xs" />
        </div>
        <Button type="button" class="min-h-11 w-full cursor-pointer" @click="applyMetadata">保存节点配置</Button>

        <div v-if="selectedNode.data.kind === 'condition'" class="space-y-3 rounded-xl border border-border/60 bg-background/60 p-4">
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
          <Button type="button" variant="secondary" class="min-h-11 w-full cursor-pointer" @click="applyCondition">保存条件配置</Button>
        </div>
      </template>
      <div v-else class="rounded-xl border border-dashed border-border/60 p-6 text-sm text-muted-foreground">
        请选择一个节点查看或编辑配置。
      </div>
    </CardContent>
  </Card>
</template>
