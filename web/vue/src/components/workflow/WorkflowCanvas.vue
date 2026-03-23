<script setup lang="ts">
import { computed } from 'vue'
import type { Connection, EdgeMouseEvent, NodeMouseEvent } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls as VueFlowControls } from '@vue-flow/controls'
import { MarkerType, VueFlow } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import type { WorkflowCatalogNode, WorkflowDefinition } from '@/api/workflow'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import WorkflowNode from '@/components/workflow/WorkflowNode.vue'
import { createWorkflowNode, defaultWorkflowCatalogNodes } from '@/lib/workflow/defaults'

const props = defineProps<{
  definition: WorkflowDefinition
  catalogNodes: WorkflowCatalogNode[]
  selectedNodeId?: string | null
}>()

const emit = defineEmits<{
  update: [definition: WorkflowDefinition]
  selectNode: [nodeId: string | null]
}>()

const availableCatalogNodes = computed(() => props.catalogNodes.length ? props.catalogNodes : defaultWorkflowCatalogNodes)
const flowNodes = computed(() => props.definition.nodes)
const flowEdges = computed(() =>
  props.definition.edges.map((edge) => ({
    ...edge,
    type: !edge.type || edge.type === 'animated' ? 'smoothstep' : edge.type,
    markerEnd: { type: MarkerType.ArrowClosed },
    label: edge.branch ? `分支: ${edge.branch}` : undefined,
  })),
)

function nextPosition() {
  const count = props.definition.nodes.length
  return { x: 120 + (count % 3) * 260, y: 80 + Math.floor(count / 3) * 180 }
}

function createNode(kind?: string) {
  const template = availableCatalogNodes.value.find((item) => item.kind === kind) || availableCatalogNodes.value[0]
  if (!template) {
    throw new Error('缺少可用节点模板')
  }
  return createWorkflowNode(template, nextPosition(), `${template.kind}-${Date.now()}`)
}

function emitDefinition(next: WorkflowDefinition) {
  emit('update', next)
}

function addNode(kind?: string) {
  const node = createNode(kind)
  emitDefinition({
    nodes: [...props.definition.nodes, node],
    edges: props.definition.edges,
  })
  emit('selectNode', node.id)
}

function deleteSelectedNode() {
  if (!props.selectedNodeId) return
  emitDefinition({
    nodes: props.definition.nodes.filter((node) => node.id !== props.selectedNodeId),
    edges: props.definition.edges.filter((edge) => edge.source !== props.selectedNodeId && edge.target !== props.selectedNodeId),
  })
  emit('selectNode', null)
}

function onConnect(connection: Connection) {
  if (!connection.source || !connection.target) return
  const sourceNode = props.definition.nodes.find((node) => node.id === connection.source)
  const branch = sourceNode?.data.kind === 'condition' ? String(connection.sourceHandle || 'true') : undefined
  emitDefinition({
    nodes: props.definition.nodes,
    edges: [
      ...props.definition.edges,
      {
        id: `edge-${connection.source}-${connection.target}-${Date.now()}`,
        source: connection.source,
        target: connection.target,
        type: 'smoothstep',
        ...(branch ? { branch } : {}),
      },
    ],
  })
}

function onNodeClick(event: NodeMouseEvent) {
  emit('selectNode', event.node.id)
}

function onPaneClick() {
  emit('selectNode', null)
}

function onEdgeDoubleClick(event: EdgeMouseEvent) {
  emitDefinition({
    nodes: props.definition.nodes,
    edges: props.definition.edges.filter((edge) => edge.id !== event.edge.id),
  })
}
</script>

<template>
  <Card class="h-full min-h-0 border-border/60 bg-card/80">
    <CardContent class="flex h-full min-h-0 flex-col gap-3 p-3">
      <div class="flex flex-wrap items-center gap-2">
        <Button type="button" variant="secondary" class="min-h-11 cursor-pointer" @click="addNode()">新增节点</Button>
        <Button type="button" variant="outline" class="min-h-11 cursor-pointer" :disabled="!selectedNodeId" @click="deleteSelectedNode">
          删除选中节点
        </Button>
        <span class="text-xs text-muted-foreground">条件节点连线时使用 source handle `true` / `false` 自动标记分支，双击边可删除。</span>
      </div>

      <div class="min-h-0 flex-1 overflow-hidden rounded-xl border border-border/60 bg-background/60">
        <VueFlow
          class="h-full w-full"
          :nodes="flowNodes"
          :edges="flowEdges"
          :default-viewport="{ zoom: 0.9, x: 0, y: 0 }"
          fit-view-on-init
          @connect="onConnect"
          @node-click="onNodeClick"
          @pane-click="onPaneClick"
          @edge-double-click="onEdgeDoubleClick"
        >
          <template #node-workflow="nodeProps">
            <WorkflowNode v-bind="nodeProps" />
          </template>
          <Background pattern-color="rgba(148, 163, 184, 0.15)" :gap="20" />
          <VueFlowControls />
        </VueFlow>
      </div>
    </CardContent>
  </Card>
</template>
