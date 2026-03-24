<script lang="ts">
let hasTopologyLoadedOnce = false
</script>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, withDefaults } from 'vue'
import {
  ArrowRight,
  Cpu,
  Database,
  HardDrive,
  Loader2,
  MousePointer2,
  MousePointerClick,
  Plus,
  Router,
  Save,
  Server,
  ShieldCheck,
  Trash2,
  X,
  Zap,
} from 'lucide-vue-next'

import { api, apiCall } from '@/api'
import {
  createTopologyFixture,
  type TopologyLinkType,
  type TopologyNodeType,
  type TopologyStatus,
} from '@/lib/topology-state'

interface RawTopologyNode {
  id: string
  label: string
  type?: string
  status?: string
  x?: number
  y?: number
}

interface RawTopologyLink {
  source: string | { id: string }
  target: string | { id: string }
  type?: string
}

interface StageNode {
  id: string
  label: string
  type: TopologyNodeType
  status: TopologyStatus
  x: number
  y: number
}

interface StageLink {
  source: string
  target: string
  type: TopologyLinkType
}

const props = withDefaults(defineProps<{
  topology?: {
    nodes?: RawTopologyNode[]
    links?: RawTopologyLink[]
  }
  recentAttacks?: Array<{ threat_level?: string }>
  loading?: boolean
}>(), {
  recentAttacks: () => [],
  loading: false,
})

const FIXTURE = createTopologyFixture()
const nodes = ref<StageNode[]>([])
const links = ref<StageLink[]>([])
const isDataLoading = ref(!hasTopologyLoadedOnce)
const isSaving = ref(false)
const isEditMode = ref(false)
const selectedNodeId = ref<string | null>(null)
const isAddingNode = ref(false)
const newNodeName = ref('')
const newNodeType = ref<TopologyNodeType>('server')
const mousePos = ref({ x: 0, y: 0 })
const pan = ref({ x: 0, y: 0 })
const panStart = ref({ x: 0, y: 0 })
const zoom = ref(1)
const isPanning = ref(false)
const draggingId = ref<string | null>(null)
const boardRef = ref<HTMLElement | null>(null)

const nodeColors: Record<TopologyStatus, string> = {
  online: '#00ff88',
  offline: '#ff6b6b',
  warning: '#fbbf24',
  attack: '#f43f5e',
}

const nodeIcons: Record<TopologyNodeType, unknown> = {
  firewall: ShieldCheck,
  server: Server,
  honeypot: Database,
  router: Router,
  switch: HardDrive,
  edge: Cpu,
}

const selectedNode = computed(() => nodes.value.find((node) => node.id === selectedNodeId.value) || null)
const nodeMap = computed(() => new Map(nodes.value.map((node) => [node.id, node])))
const resolvedLinks = computed(() =>
  links.value
    .map((link) => {
      const sourceNode = nodeMap.value.get(link.source)
      const targetNode = nodeMap.value.get(link.target)
      if (!sourceNode || !targetNode) return null
      return { ...link, sourceNode, targetNode }
    })
    .filter((link): link is StageLink & { sourceNode: StageNode; targetNode: StageNode } => Boolean(link)),
)
const summary = computed(() => ({
  nodeCount: nodes.value.length,
  onlineCount: nodes.value.filter((node) => node.status === 'online').length,
  warningCount: nodes.value.filter((node) => node.status === 'warning').length,
  attackCount: nodes.value.filter((node) => node.status === 'attack').length,
  linkCount: links.value.length,
}))

function normalizeNodeType(type?: string): TopologyNodeType {
  const value = (type || '').toLowerCase()
  if (value.includes('firewall') || value.includes('waf')) return 'firewall'
  if (value.includes('router') || value.includes('soc')) return 'router'
  if (value.includes('switch')) return 'switch'
  if (value.includes('honeypot') || value.includes('botnet') || value.includes('trap')) return 'honeypot'
  if (value.includes('edge') || value.includes('internet') || value.includes('gateway') || value.includes('出口')) return 'edge'
  return 'server'
}

function normalizeStatus(status?: string): TopologyStatus {
  const value = (status || '').toLowerCase()
  if (value.includes('offline') || value.includes('down')) return 'offline'
  if (value.includes('warning') || value.includes('alert') || value.includes('risk')) return 'warning'
  if (value.includes('attack') || value.includes('critical') || value.includes('danger')) return 'attack'
  return 'online'
}

function normalizeLinkType(type?: string): TopologyLinkType {
  const value = (type || '').toLowerCase()
  if (value.includes('attack') || value.includes('threat')) return 'attack'
  if (value.includes('block') || value.includes('defense') || value.includes('intercept')) return 'blocked'
  if (value.includes('uplink') || value.includes('core') || value.includes('backbone')) return 'uplink'
  return 'lan'
}

function createGridPosition(index: number) {
  const columns = [120, 260, 410, 560, 710, 860]
  const rows = [90, 210, 330, 450]
  return {
    x: columns[index % columns.length],
    y: rows[Math.floor(index / columns.length) % rows.length],
  }
}

function buildFixtureState() {
  return {
    nodes: FIXTURE.nodes.map((node, index) => {
      const point = FIXTURE.positions[node.id] || createGridPosition(index)
      return {
        ...node,
        x: point.x,
        y: point.y,
      } satisfies StageNode
    }),
    links: FIXTURE.links.map((link) => ({ ...link })),
  }
}

function buildStageState(raw?: { nodes?: RawTopologyNode[]; links?: RawTopologyLink[] }) {
  if (!raw?.nodes?.length) {
    return buildFixtureState()
  }

  const fallback = buildFixtureState()
  const fallbackPositions = new Map(fallback.nodes.map((node) => [node.id, { x: node.x, y: node.y }]))
  const nodeIds = new Set<string>()

  const nextNodes = raw.nodes.map((node, index) => {
    const point = fallbackPositions.get(node.id) || createGridPosition(index)
    const safeX = Number.isFinite(node.x) ? Number(node.x) : point.x
    const safeY = Number.isFinite(node.y) ? Number(node.y) : point.y
    nodeIds.add(node.id)

    return {
      id: node.id,
      label: node.label || `节点 ${index + 1}`,
      type: normalizeNodeType(node.type),
      status: normalizeStatus(node.status),
      x: safeX,
      y: safeY,
    } satisfies StageNode
  })

  const nextLinks: StageLink[] = []
  for (const link of raw.links || []) {
    const source = typeof link.source === 'string' ? link.source : link.source?.id
    const target = typeof link.target === 'string' ? link.target : link.target?.id
    if (!source || !target || !nodeIds.has(source) || !nodeIds.has(target)) continue
    nextLinks.push({
      source,
      target,
      type: normalizeLinkType(link.type),
    })
  }

  return {
    nodes: nextNodes,
    links: nextLinks.length ? nextLinks : fallback.links,
  }
}

function replaceTopology(raw?: { nodes?: RawTopologyNode[]; links?: RawTopologyLink[] }) {
  const state = buildStageState(raw)
  nodes.value = state.nodes
  links.value = state.links
  selectedNodeId.value = state.nodes[0]?.id || null
  zoom.value = 1
  pan.value = { x: 0, y: 0 }
  isDataLoading.value = false
  hasTopologyLoadedOnce = true
}

function sanitizeForSave() {
  return {
    nodes: nodes.value.map((node) => ({
      id: node.id,
      label: node.label,
      type: node.type,
      status: node.status,
      x: Number(node.x.toFixed(2)),
      y: Number(node.y.toFixed(2)),
    })),
    links: links.value.map((link) => ({
      source: link.source,
      target: link.target,
      type: link.type,
    })),
  }
}

async function fetchTopology() {
  const data = await apiCall(() => api.get<{ nodes?: RawTopologyNode[]; links?: RawTopologyLink[] }>('/api/v1/topology'), {
    errorMsg: '加载拓扑数据失败',
  })

  replaceTopology(data && data.nodes?.length ? data : props.topology)
}

async function handleSave() {
  isSaving.value = true
  const result = await apiCall(() => api.post('/api/v1/topology', sanitizeForSave()), {
    errorMsg: '拓扑保存失败',
  })
  if (result) {
    isEditMode.value = false
    selectedNodeId.value = null
  }
  isSaving.value = false
}

function toggleLink(sourceId: string, targetId: string) {
  const existingIndex = links.value.findIndex((link) =>
    (link.source === sourceId && link.target === targetId) ||
    (link.source === targetId && link.target === sourceId),
  )

  if (existingIndex > -1) {
    links.value.splice(existingIndex, 1)
  } else {
    links.value.push({ source: sourceId, target: targetId, type: 'lan' })
  }
}

function getLocalPoint(event: MouseEvent) {
  if (!boardRef.value) return { x: 0, y: 0 }
  const rect = boardRef.value.getBoundingClientRect()
  return {
    x: (event.clientX - rect.left - pan.value.x) / zoom.value,
    y: (event.clientY - rect.top - pan.value.y) / zoom.value,
  }
}

function clampPosition(x: number, y: number) {
  const width = boardRef.value?.clientWidth || 980
  const height = boardRef.value?.clientHeight || 560
  return {
    x: Math.max(48, Math.min(width / zoom.value - 48, x)),
    y: Math.max(64, Math.min(height / zoom.value - 64, y)),
  }
}

function addNode() {
  const label = newNodeName.value.trim()
  if (!label) return

  const width = boardRef.value?.clientWidth || 980
  const height = boardRef.value?.clientHeight || 560
  const center = clampPosition(width / 2 / zoom.value - pan.value.x / zoom.value, height / 2 / zoom.value - pan.value.y / zoom.value)
  const id = `node-${Date.now()}`

  nodes.value.push({
    id,
    label,
    type: newNodeType.value,
    status: 'online',
    x: center.x,
    y: center.y,
  })

  newNodeName.value = ''
  isAddingNode.value = false
  selectedNodeId.value = id
}

function deleteSelectedNode() {
  if (!selectedNodeId.value) return
  nodes.value = nodes.value.filter((node) => node.id !== selectedNodeId.value)
  links.value = links.value.filter((link) => link.source !== selectedNodeId.value && link.target !== selectedNodeId.value)
  selectedNodeId.value = nodes.value[0]?.id || null
}

function handleNodeClick(nodeId: string, event: MouseEvent) {
  event.stopPropagation()

  if (!isEditMode.value) {
    selectedNodeId.value = nodeId
    return
  }

  if (!selectedNodeId.value) {
    selectedNodeId.value = nodeId
  } else if (selectedNodeId.value === nodeId) {
    selectedNodeId.value = null
  } else {
    toggleLink(selectedNodeId.value, nodeId)
    selectedNodeId.value = nodeId
  }
}

function handleMouseMove(event: MouseEvent) {
  const point = getLocalPoint(event)
  mousePos.value = point

  if (draggingId.value) {
    const node = nodes.value.find((item) => item.id === draggingId.value)
    if (node) {
      const next = clampPosition(point.x, point.y)
      node.x = next.x
      node.y = next.y
    }
    return
  }

  if (isPanning.value) {
    pan.value = {
      x: event.clientX - panStart.value.x,
      y: event.clientY - panStart.value.y,
    }
  }
}

function handleMouseUp() {
  draggingId.value = null
  isPanning.value = false
}

function handleWheel(event: WheelEvent) {
  event.preventDefault()
  const board = boardRef.value
  if (!board) return

  const rect = board.getBoundingClientRect()
  const mouseX = event.clientX - rect.left
  const mouseY = event.clientY - rect.top

  const factor = event.deltaY > 0 ? 0.92 : 1.08
  const newZoom = Math.max(0.45, Math.min(2.2, zoom.value * factor))

  // 以鼠标位置为中心缩放
  pan.value = {
    x: mouseX - (mouseX - pan.value.x) * (newZoom / zoom.value),
    y: mouseY - (mouseY - pan.value.y) * (newZoom / zoom.value),
  }
  zoom.value = newZoom
}

function startDragging(nodeId: string, event: MouseEvent) {
  event.stopPropagation()
  draggingId.value = nodeId
  selectedNodeId.value = nodeId
}

function handleExitEdit() {
  isEditMode.value = false
  isAddingNode.value = false
  selectedNodeId.value = null
  fetchTopology()
}

function handleBoardPointerDown(event: MouseEvent) {
  isPanning.value = true
  panStart.value = {
    x: event.clientX - pan.value.x,
    y: event.clientY - pan.value.y,
  }
  if (!isEditMode.value) {
    selectedNodeId.value = null
  }
}

watch(
  () => props.topology,
  (topology) => {
    if (topology?.nodes?.length) {
      replaceTopology(topology)
    }
  },
  { immediate: true, deep: true },
)

onMounted(() => {
  if (!props.topology?.nodes?.length) {
    fetchTopology()
  }
  window.addEventListener('mouseup', handleMouseUp)
})

onUnmounted(() => {
  window.removeEventListener('mouseup', handleMouseUp)
})
</script>

<template>
  <div class="topology-stage-shell" aria-label="网络拓扑视图">
    <div v-if="isDataLoading || props.loading" class="topology-loading-view">
      <div class="topology-loading-spinner"></div>
      <p class="topology-loading-text">正在同步旧分支首页拓扑大屏...</p>
    </div>

    <template v-else>
      <div class="topology-toolbar">
        <div v-if="isEditMode" class="toolbar-edit">
          <div class="edit-guide">
            <template v-if="!selectedNodeId">
              <MousePointerClick class="h-4 w-4 text-cyan" />
              第一步：选中起始设备
            </template>
            <template v-else>
              <Zap class="h-4 w-4 text-cyan" />
              第二步：点击另一台设备完成连线
            </template>
          </div>

          <div class="v-divider"></div>

          <button class="btn-ghost" @click="isAddingNode = true">
            <Plus class="h-4 w-4" />
            放置新设备
          </button>

          <button v-if="selectedNodeId" class="btn-danger" @click="deleteSelectedNode">
            <Trash2 class="h-4 w-4" />
            删除选中设备
          </button>

          <div class="v-divider"></div>

          <div class="action-group">
            <button class="btn-primary btn-sm" :disabled="isSaving" @click="handleSave">
              <Loader2 v-if="isSaving" class="h-3.5 w-3.5 animate-spin" />
              <Save v-else class="h-3.5 w-3.5" />
              确认发布
            </button>
            <button class="btn-ghost btn-sm" @click="handleExitEdit">
              退出
            </button>
          </div>
        </div>

        <button v-else class="topology-edit-entry" @click="isEditMode = true">
          <Zap class="h-4 w-4" />
          编辑拓扑
        </button>
      </div>

      <div
        ref="boardRef"
        class="topology-stage-board"
        @mousemove="handleMouseMove"
        @mouseleave="handleMouseUp"
        @mouseup="handleMouseUp"
        @wheel="handleWheel"
      >
        <div class="topology-stage-board__grid" aria-hidden="true"></div>

        <svg
          class="topology-stage-board__svg"
          @mousedown.self="handleBoardPointerDown"
        >
          <g :transform="`translate(${pan.x}, ${pan.y}) scale(${zoom})`">
            <line
              v-if="isEditMode && selectedNode"
              :x1="selectedNode.x"
              :y1="selectedNode.y"
              :x2="mousePos.x"
              :y2="mousePos.y"
              class="guide-link"
            />

            <line
              v-for="(link, index) in resolvedLinks"
              :key="`link-${index}`"
              :x1="link.sourceNode.x"
              :y1="link.sourceNode.y"
              :x2="link.targetNode.x"
              :y2="link.targetNode.y"
              class="topology-link"
              :class="`topology-link--${link.type}`"
            />

            <g v-for="node in nodes" :key="node.id" :transform="`translate(${node.x}, ${node.y})`">
              <circle v-if="node.id === selectedNodeId" r="48" class="node-highlight-ring" />

              <circle
                r="38"
                class="node-circle"
                :class="{ 'node-circle--selected': node.id === selectedNodeId }"
                :stroke="nodeColors[node.status]"
                @mousedown="startDragging(node.id, $event)"
                @click="handleNodeClick(node.id, $event)"
              />

              <foreignObject x="-22" y="-22" width="44" height="44" class="pointer-events-none">
                <div class="node-icon-wrapper">
                  <component
                    :is="nodeIcons[node.type] || Server"
                    class="h-full w-full"
                    :style="{ color: node.id === selectedNodeId ? '#00d4ff' : (node.status === 'online' ? '#ffffff' : nodeColors[node.status]) }"
                  />
                </div>
              </foreignObject>

              <text y="58" text-anchor="middle" class="node-label">{{ node.label }}</text>
            </g>
          </g>
        </svg>

        <div class="topology-hint">
          <span><MousePointer2 class="h-3 w-3" /> 拖拽空白区域平移</span>
          <span><ArrowRight class="h-3 w-3" /> 滚轮缩放视图</span>
          <span v-if="isEditMode" class="text-cyan"><ArrowRight class="h-3 w-3" /> 先点 A 再点 B 建链</span>
        </div>

        <div class="topology-legend">
          <div class="legend-item"><i class="legend-dot online"></i>在线</div>
          <div class="legend-item"><i class="legend-dot warning"></i>告警</div>
          <div class="legend-item"><i class="legend-dot attack"></i>攻击链路</div>
          <div class="legend-item"><i class="legend-dot lan"></i>常规链路</div>
        </div>
      </div>

      <transition name="slide-right">
        <div v-if="isAddingNode" class="node-addition-panel">
          <div class="panel-header">
            <h3>
              <Plus class="h-5 w-5 text-cyan" />
              资产入场
            </h3>
            <button class="btn-icon" @click="isAddingNode = false">
              <X class="h-4 w-4" />
            </button>
          </div>

          <div class="panel-body">
            <div class="form-item">
              <label>设备命名</label>
              <input v-model="newNodeName" placeholder="例如: WebServer-01" @keyup.enter="addNode" />
            </div>

            <div class="form-item">
              <label>选择设备类型</label>
              <div class="type-grid">
                <button
                  v-for="(icon, type) in nodeIcons"
                  :key="type"
                  class="type-btn"
                  :class="{ active: newNodeType === type }"
                  @click="newNodeType = type"
                >
                  <component :is="icon" class="h-6 w-6" />
                  <span>{{ type }}</span>
                </button>
              </div>
            </div>

            <button class="btn-primary btn-primary--wide" @click="addNode">执行部署</button>
          </div>
        </div>
      </transition>
    </template>
  </div>
</template>

<style scoped>
.topology-stage-shell {
  position: relative;
  height: 100%;
  overflow: hidden;
  border-radius: 12px;
  border: 1px solid rgba(0, 212, 255, 0.12);
  background:
    radial-gradient(circle at top left, rgba(0, 212, 255, 0.12), transparent 30%),
    linear-gradient(180deg, rgba(5, 11, 21, 0.98), rgba(7, 15, 30, 0.98));
}

.topology-loading-view {
  display: flex;
  height: 100%;
  min-height: 420px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 18px;
}

.topology-loading-spinner {
  width: 46px;
  height: 46px;
  border: 4px solid rgba(0, 212, 255, 0.12);
  border-top-color: rgba(0, 212, 255, 0.92);
  border-radius: 999px;
  animation: spin 0.9s linear infinite;
}

.topology-loading-text {
  color: rgba(165, 243, 252, 0.88);
  font-size: 13px;
  letter-spacing: 0.08em;
}

.topology-toolbar {
  position: absolute;
  top: 18px;
  left: 18px;
  right: 18px;
  z-index: 20;
  pointer-events: none;
}

.toolbar-edit {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 16px;
  border-radius: 18px;
  border: 1px solid rgba(0, 212, 255, 0.18);
  background: rgba(8, 15, 29, 0.88);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.34);
  backdrop-filter: blur(16px);
  pointer-events: auto;
}

.toolbar-edit {
  justify-content: flex-start;
  flex-wrap: wrap;
}

.topology-edit-entry {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-left: auto;
  padding: 10px 14px;
  border: 1px solid rgba(34, 211, 238, 0.2);
  border-radius: 999px;
  background: rgba(8, 15, 29, 0.86);
  color: rgba(226, 232, 240, 0.92);
  box-shadow: 0 14px 32px rgba(0, 0, 0, 0.24);
  backdrop-filter: blur(14px);
  pointer-events: auto;
  cursor: pointer;
  transition: transform 0.2s ease, background 0.2s ease, border-color 0.2s ease;
}

.topology-edit-entry:hover {
  transform: translateY(-1px);
  background: rgba(12, 22, 40, 0.92);
  border-color: rgba(34, 211, 238, 0.35);
}

.edit-guide {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px 0 2px;
  color: #f8fafc;
  font-size: 13px;
  font-weight: 600;
}

.text-cyan {
  color: #00d4ff;
}

.v-divider {
  width: 1px;
  height: 18px;
  background: rgba(148, 163, 184, 0.28);
}

.action-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.topology-stage-board {
  position: relative;
  height: 100%;
  min-height: 420px;
  cursor: grab;
}

.topology-stage-board:active {
  cursor: grabbing;
}

.topology-stage-board__grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(34, 211, 238, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(34, 211, 238, 0.08) 1px, transparent 1px);
  background-size: 42px 42px;
  mask-image: radial-gradient(circle at center, black 60%, transparent 96%);
  pointer-events: none;
}

.topology-stage-board__svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.guide-link {
  stroke: rgba(0, 212, 255, 0.44);
  stroke-width: 2;
  stroke-dasharray: 6 6;
}

.topology-link {
  transition: stroke 0.24s ease, opacity 0.24s ease;
}

.topology-link--uplink {
  stroke: rgba(56, 189, 248, 0.78);
  stroke-width: 2.4;
}

.topology-link--lan {
  stroke: rgba(0, 212, 255, 0.34);
  stroke-width: 1.7;
}

.topology-link--blocked {
  stroke: rgba(0, 255, 136, 0.72);
  stroke-width: 2.3;
  stroke-dasharray: 8 7;
}

.topology-link--attack {
  stroke: rgba(244, 63, 94, 0.92);
  stroke-width: 2.8;
  stroke-dasharray: 6 6;
}

.node-circle {
  fill: rgba(10, 17, 33, 0.96);
  stroke-width: 3;
  cursor: pointer;
  transition: stroke-width 0.24s ease, transform 0.24s ease;
}

.node-circle--selected {
  stroke: #00d4ff !important;
  stroke-width: 4.5;
}

.node-highlight-ring {
  fill: none;
  stroke: rgba(0, 212, 255, 0.9);
  stroke-width: 2;
  opacity: 0.52;
  animation: pulse 2s ease-out infinite;
}

.node-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.node-label {
  fill: #f8fafc;
  font-size: 13px;
  font-weight: 700;
  paint-order: stroke;
  stroke: rgba(5, 11, 21, 0.92);
  stroke-width: 4px;
}

.topology-hint {
  position: absolute;
  left: 50%;
  bottom: 18px;
  display: flex;
  gap: 18px;
  transform: translateX(-50%);
  padding: 7px 14px;
  border-radius: 999px;
  background: rgba(8, 15, 29, 0.84);
  color: rgba(125, 211, 252, 0.76);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  pointer-events: none;
}

.topology-hint span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.topology-legend {
  position: absolute;
  left: 18px;
  bottom: 18px;
  display: grid;
  gap: 9px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(34, 211, 238, 0.18);
  background: rgba(8, 15, 29, 0.84);
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  color: rgba(226, 232, 240, 0.82);
  font-size: 11px;
}

.legend-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  box-shadow: 0 0 12px currentColor;
}

.legend-dot.online {
  color: #00ff88;
  background: #00ff88;
}

.legend-dot.warning {
  color: #fbbf24;
  background: #fbbf24;
}

.legend-dot.attack {
  color: #f43f5e;
  background: #f43f5e;
}

.legend-dot.lan {
  color: #00d4ff;
  background: rgba(0, 212, 255, 0.72);
}

.node-addition-panel {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 320px;
  padding: 26px;
  border-left: 1px solid rgba(34, 211, 238, 0.12);
  background: rgba(5, 11, 21, 0.98);
  z-index: 30;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.panel-header h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #f8fafc;
  font-size: 17px;
}

.panel-body {
  display: grid;
  gap: 20px;
}

.form-item {
  display: grid;
  gap: 8px;
}

.form-item label {
  color: rgba(148, 163, 184, 0.88);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.form-item input {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.72);
  padding: 12px 14px;
  color: #f8fafc;
  outline: none;
}

.form-item input:focus {
  border-color: rgba(34, 211, 238, 0.48);
}

.type-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.type-btn {
  display: grid;
  place-items: center;
  gap: 8px;
  padding: 14px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.58);
  color: rgba(203, 213, 225, 0.74);
  transition: border-color 0.2s ease, color 0.2s ease, background 0.2s ease;
}

.type-btn.active {
  border-color: rgba(34, 211, 238, 0.42);
  background: rgba(8, 47, 73, 0.72);
  color: #67e8f9;
}

.type-btn span {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.btn-primary,
.btn-ghost,
.btn-danger,
.btn-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 0;
  cursor: pointer;
  transition: transform 0.2s ease, opacity 0.2s ease, background 0.2s ease;
}

.btn-primary {
  padding: 10px 16px;
  border-radius: 999px;
  background: linear-gradient(135deg, #00d4ff, #67e8f9);
  color: #082f49;
  font-size: 13px;
  font-weight: 800;
}

.btn-primary:hover,
.btn-ghost:hover,
.btn-danger:hover,
.btn-icon:hover {
  transform: translateY(-1px);
}

.btn-primary:disabled {
  opacity: 0.72;
  cursor: not-allowed;
}

.btn-primary--wide {
  width: 100%;
  justify-content: center;
}

.btn-ghost {
  padding: 9px 14px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.72);
  color: rgba(226, 232, 240, 0.82);
  font-size: 13px;
  font-weight: 700;
}

.btn-danger {
  padding: 9px 14px;
  border-radius: 999px;
  background: rgba(127, 29, 29, 0.2);
  color: rgba(252, 165, 165, 0.96);
  font-size: 13px;
  font-weight: 700;
}

.btn-icon {
  width: 34px;
  height: 34px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.72);
  color: rgba(226, 232, 240, 0.82);
}

.btn-sm {
  padding: 8px 12px;
  font-size: 12px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes pulse {
  0% {
    transform: scale(0.8);
    opacity: 0.56;
  }

  100% {
    transform: scale(1.24);
    opacity: 0;
  }
}

.slide-right-enter-active,
.slide-right-leave-active {
  transition: transform 0.24s ease;
}

.slide-right-enter-from,
.slide-right-leave-to {
  transform: translateX(100%);
}

@media (max-width: 1024px) {
  .toolbar-edit {
    flex-direction: column;
    align-items: flex-start;
  }

  .topology-hint {
    width: calc(100% - 36px);
    justify-content: center;
    flex-wrap: wrap;
  }
}

@media (max-width: 720px) {
  .topology-toolbar {
    top: 12px;
    left: 12px;
    right: 12px;
  }

  .topology-legend {
    left: 12px;
    bottom: 12px;
  }

  .node-addition-panel {
    width: 100%;
  }
}
</style>
