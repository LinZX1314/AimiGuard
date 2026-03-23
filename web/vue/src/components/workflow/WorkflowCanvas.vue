<script setup lang="ts">
import { computed, ref } from 'vue'
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
import { createWorkflowNode, defaultWorkflowCatalogNodes, workflowCategoryMeta } from '@/lib/workflow/defaults'

const props = defineProps<{
  definition: WorkflowDefinition
  catalogNodes: WorkflowCatalogNode[]
  selectedNodeId?: string | null
}>()

const emit = defineEmits<{
  update: [definition: WorkflowDefinition]
  selectNode: [nodeId: string | null]
}>()

const availableCatalogNodes = computed(() => (props.catalogNodes.length ? props.catalogNodes : defaultWorkflowCatalogNodes))
const flowNodes = computed(() => props.definition.nodes)
const flowEdges = computed(() =>
  props.definition.edges.map((edge) => ({
    ...edge,
    type: !edge.type || edge.type === 'animated' ? 'smoothstep' : edge.type,
    markerEnd: { type: MarkerType.ArrowClosed },
    label: edge.branch ? `分支: ${edge.branch}` : undefined,
  })),
)
const contextMenu = ref<{ visible: boolean; x: number; y: number; flowX: number; flowY: number }>({
  visible: false,
  x: 0,
  y: 0,
  flowX: 0,
  flowY: 0,
})

function nextPosition() {
  const count = props.definition.nodes.length
  return { x: 120 + (count % 3) * 260, y: 80 + Math.floor(count / 3) * 180 }
}

function computeFlowPosition(clientX: number, clientY: number) {
  const pane = document.querySelector('.vue-flow__pane') as HTMLElement | null
  if (!pane) return nextPosition()
  const rect = pane.getBoundingClientRect()
  return {
    x: Math.max(clientX - rect.left - 90, 24),
    y: Math.max(clientY - rect.top - 30, 24),
  }
}

function createNode(kind?: string, position?: { x: number; y: number }) {
  const template = availableCatalogNodes.value.find((item) => item.kind === kind) || availableCatalogNodes.value[0]
  if (!template) {
    throw new Error('缺少可用节点模板')
  }
  return createWorkflowNode(template, position ?? nextPosition(), `${template.kind}-${Date.now()}`)
}

function emitDefinition(next: WorkflowDefinition) {
  emit('update', next)
}

function addNode(kind?: string, position?: { x: number; y: number }) {
  const node = createNode(kind, position)
  emitDefinition({
    nodes: [...props.definition.nodes, node],
    edges: props.definition.edges,
  })
  emit('selectNode', node.id)
}

function addNodeFromContextMenu(kind?: string) {
  addNode(kind, { x: contextMenu.value.flowX, y: contextMenu.value.flowY })
  closeContextMenu()
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
  closeContextMenu()
}

function onPaneClick() {
  emit('selectNode', null)
  closeContextMenu()
}

function onEdgeDoubleClick(event: EdgeMouseEvent) {
  emitDefinition({
    nodes: props.definition.nodes,
    edges: props.definition.edges.filter((edge) => edge.id !== event.edge.id),
  })
}

function openContextMenu(event: MouseEvent) {
  event.preventDefault()
  const position = computeFlowPosition(event.clientX, event.clientY)
  contextMenu.value = {
    visible: true,
    x: event.clientX,
    y: event.clientY,
    flowX: position.x,
    flowY: position.y,
  }
}

function closeContextMenu() {
  contextMenu.value.visible = false
}

function categoryLabel(type: string) {
  return workflowCategoryMeta[type]?.label ?? '节点'
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
        <span class="text-xs text-muted-foreground">右键画布可在鼠标位置创建节点；条件节点连线时使用 source handle `true` / `false` 自动标记分支，双击边可删除。</span>
      </div>

      <div class="relative min-h-0 flex-1 overflow-hidden rounded-xl border border-border/60 bg-background/60" @contextmenu="openContextMenu">
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

        <div
          v-if="contextMenu.visible"
          class="absolute z-20 w-80 rounded-2xl border border-border/70 bg-popover/95 p-3 shadow-2xl backdrop-blur"
          :style="{
            left: `${Math.max(contextMenu.x - 36, 16)}px`,
            top: `${Math.max(contextMenu.y - 120, 16)}px`,
          }"
          @click.stop
        >
          <div class="mb-2 flex items-center justify-between">
            <div>
              <div class="text-sm font-semibold text-foreground">创建节点</div>
              <div class="text-xs text-muted-foreground">在当前右键位置插入工作流功能模块</div>
            </div>
            <Button type="button" variant="ghost" size="sm" class="cursor-pointer" @click="closeContextMenu">关闭</Button>
          </div>

          <div class="grid max-h-80 gap-2 overflow-y-auto">
            <button
              v-for="item in availableCatalogNodes"
              :key="item.kind"
              type="button"
              class="flex cursor-pointer items-start justify-between rounded-xl border border-border/60 bg-background/70 px-3 py-3 text-left transition hover:border-primary/40 hover:bg-primary/5"
              @click="addNodeFromContextMenu(item.kind)"
            >
              <div>
                <div class="text-sm font-medium text-foreground">{{ item.label }}</div>
                <div class="text-xs text-muted-foreground">{{ categoryLabel(item.type) }} · {{ item.kind }}</div>
              </div>
              <span class="text-xs text-primary">创建</span>
            </button>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>
