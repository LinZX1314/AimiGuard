<script lang="ts">
let hasTopologyLoadedOnce = false
</script>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, withDefaults } from 'vue'

import {
  buildTopologyStageLinks,
  buildTopologyStageNodes,
  createTopologyFixture,
  getTopologySummary,
  type TopologyFixture,
  type TopologyLinkType,
  type TopologyNodeType,
  type TopologyStatus,
} from '@/lib/topology-state'

interface RecentAttack {
  attack_ip: string
  ip_location?: string
  service_name?: string
  threat_level?: string
  create_time_str?: string
}

interface RawTopologyNode {
  id: string
  label: string
  type: string
  status: string
}

interface RawTopologyLink {
  source: string
  target: string
  type: string
}

const props = withDefaults(defineProps<{
  topology?: {
    nodes: RawTopologyNode[]
    links: RawTopologyLink[]
  }
  recentAttacks?: RecentAttack[]
  loading?: boolean
}>(), {
  recentAttacks: () => [],
  loading: false,
})

const CANVAS_WIDTH = 920
const CANVAS_HEIGHT = 620

function normalizeNodeType(type?: string): TopologyNodeType {
  const value = (type || '').toLowerCase()
  if (value.includes('firewall') || value.includes('waf')) return 'firewall'
  if (value.includes('router') || value.includes('soc')) return 'router'
  if (value.includes('switch')) return 'switch'
  if (value.includes('honeypot') || value.includes('trap') || value.includes('botnet')) return 'honeypot'
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
  if (value.includes('uplink') || value.includes('backbone') || value.includes('core')) return 'uplink'
  return 'lan'
}

function stretchPoint(x: number, y: number) {
  return {
    x,
    y: Math.round(Math.max(52, Math.min(CANVAS_HEIGHT - 52, 48 + y * 1.35))),
  }
}

function createGeneratedPoint(index: number) {
  const columns = [84, 178, 300, 430, 560, 700, 820, 878]
  const rows = [88, 188, 288, 388, 488, 568]
  return {
    x: columns[index % columns.length],
    y: rows[Math.floor(index / columns.length) % rows.length],
  }
}

function createStageFixture(): TopologyFixture {
  const fixture = createTopologyFixture()
  return {
    ...fixture,
    nodes: fixture.nodes.map((node) =>
      node.id === 'core-switch'
        ? { ...node, label: '核心数据中心交换机 · SW-Core-01' }
        : node,
    ),
    positions: Object.fromEntries(
      Object.entries(fixture.positions).map(([id, point]) => [id, stretchPoint(point.x, point.y)]),
    ),
  }
}

function buildTopologyState(raw?: { nodes: RawTopologyNode[]; links: RawTopologyLink[] }): TopologyFixture {
  const fallback = createStageFixture()

  if (!raw?.nodes?.length) {
    return fallback
  }

  const nodes = raw.nodes.map((node, index) => ({
    id: node.id,
    label: node.id === 'core-switch' && !(node.label || '').includes('SW-Core')
      ? `${node.label || '核心数据中心交换机'} · SW-Core-01`
      : (node.label || `节点 ${index + 1}`),
    type: normalizeNodeType(node.type),
    status: normalizeStatus(node.status),
  }))

  const nodeIds = new Set(nodes.map((node) => node.id))
  const links = (raw.links || [])
    .filter((link) => nodeIds.has(link.source) && nodeIds.has(link.target))
    .map((link) => ({
      source: link.source,
      target: link.target,
      type: normalizeLinkType(link.type),
    }))

  return {
    nodes,
    links: links.length ? links : fallback.links.filter((link) => nodeIds.has(link.source) && nodeIds.has(link.target)),
    positions: Object.fromEntries(
      nodes.map((node, index) => [node.id, fallback.positions[node.id] || createGeneratedPoint(index)]),
    ),
  }
}

const topologyState = ref<TopologyFixture>(createStageFixture())
const selectedNodeId = ref<string | null>('core-switch')
const boardRef = ref<HTMLElement | null>(null)
const draggingNodeId = ref<string | null>(null)
const isPanningBoard = ref(false)
const panStartClient = ref({ x: 0, y: 0 })
const panStartScroll = ref({ left: 0, top: 0 })
const isDataLoading = ref(!hasTopologyLoadedOnce)
let loadingTimer = 0

const nodeLabels: Record<TopologyNodeType, string> = {
  edge: 'ED',
  router: 'RT',
  firewall: 'FW',
  server: 'SV',
  switch: 'SW',
  honeypot: 'HP',
}

const nodeTypeText: Record<TopologyNodeType, string> = {
  edge: '边界入口',
  router: '调度中枢',
  firewall: '边界防护',
  server: '业务节点',
  switch: '交换矩阵',
  honeypot: '诱捕节点',
}

const linkTypeText: Record<TopologyLinkType, string> = {
  uplink: '骨干上联',
  lan: '业务链路',
  blocked: '阻断联动',
  attack: '攻击路径',
}

watch(
  () => props.topology,
  (topology) => {
    topologyState.value = buildTopologyState(topology)
    if (!topologyState.value.nodes.some((node) => node.id === selectedNodeId.value)) {
      selectedNodeId.value = topologyState.value.nodes.find((node) => node.id === 'core-switch')?.id || topologyState.value.nodes[0]?.id || null
    }
  },
  { immediate: true, deep: true },
)

const summary = computed(() => getTopologySummary(topologyState.value))
const stageLinks = computed(() => buildTopologyStageLinks(topologyState.value, selectedNodeId.value))
const stageNodes = computed(() =>
  buildTopologyStageNodes(topologyState.value, selectedNodeId.value).map((node) => ({
    ...node,
    labelToken: nodeLabels[node.type],
  })),
)

const selectedNode = computed(() =>
  stageNodes.value.find((node) => node.id === selectedNodeId.value) || stageNodes.value[0] || null,
)

const selectedNodeLinks = computed(() => {
  if (!selectedNode.value) return []
  return stageLinks.value.filter((link) => link.sourceId === selectedNode.value?.id || link.targetId === selectedNode.value?.id)
})

const statCards = computed(() => [
  { label: '节点总数', value: `${summary.value.nodeCount}` },
  { label: '在线节点', value: `${summary.value.onlineCount}` },
  { label: '威胁节点', value: `${summary.value.warningCount + summary.value.attackCount}` },
  { label: '链路总数', value: `${summary.value.linkCount}` },
])

const relationCards = computed(() => {
  const visibleLinks = selectedNodeLinks.value.length ? selectedNodeLinks.value : stageLinks.value.slice(0, 5)
  const nodeMap = new Map(stageNodes.value.map((node) => [node.id, node]))

  return visibleLinks.slice(0, 5).map((link) => {
    const source = nodeMap.get(link.sourceId)
    const target = nodeMap.get(link.targetId)
    const relationNode = selectedNode.value?.id === link.sourceId ? target : source

    return {
      id: link.id,
      badge: linkTypeText[link.type],
      title: relationNode?.label || `${source?.label || link.sourceId} → ${target?.label || link.targetId}`,
      description: `${source?.label || link.sourceId} → ${target?.label || link.targetId}`,
      tone: `relation-${link.type}`,
    }
  })
})

const eventFeed = computed(() => {
  if (props.recentAttacks.length) {
    return props.recentAttacks.slice(0, 4).map((item, index) => ({
      id: `${item.attack_ip || 'attack'}-${item.create_time_str || index}`,
      level: (item.threat_level || 'medium').toLowerCase(),
      title: item.service_name || '异常访问行为',
      meta: `${item.attack_ip || '未知源'} · ${item.ip_location || '位置待解析'}`,
      time: item.create_time_str || '刚刚',
    }))
  }

  return relationCards.value.slice(0, 4).map((item, index) => ({
    id: `${item.id}-${index}`,
    level: index === 0 ? 'high' : index === 1 ? 'medium' : 'low',
    title: item.badge,
    meta: item.description,
    time: '实时同步',
  }))
})

const selectedNodeMeta = computed(() => {
  if (!selectedNode.value) {
    return [
      { label: '节点类型', value: '--' },
      { label: '关联链路', value: '--' },
      { label: '关系态势', value: '--' },
    ]
  }

  const riskCount = selectedNodeLinks.value.filter((link) => link.type === 'attack' || link.type === 'blocked').length

  return [
    { label: '节点类型', value: nodeTypeText[selectedNode.value.type] },
    { label: '关联链路', value: `${selectedNodeLinks.value.length} 条` },
    { label: '关系态势', value: riskCount > 0 ? `${riskCount} 条风险链路` : '链路稳定' },
  ]
})

function buildMotionPath(link: { sourcePoint: { x: number; y: number }; targetPoint: { x: number; y: number } }) {
  return `M ${link.sourcePoint.x} ${link.sourcePoint.y} L ${link.targetPoint.x} ${link.targetPoint.y}`
}

function selectNode(nodeId: string) {
  selectedNodeId.value = nodeId
}

function updateNodePosition(nodeId: string, clientX: number, clientY: number) {
  const board = boardRef.value
  if (!board) return

  const rect = board.getBoundingClientRect()
  const scaleX = CANVAS_WIDTH / rect.width
  const scaleY = CANVAS_HEIGHT / rect.height

  const x = (clientX - rect.left) * scaleX
  const y = (clientY - rect.top) * scaleY

  const safeX = Math.max(42, Math.min(CANVAS_WIDTH - 42, x))
  const safeY = Math.max(42, Math.min(CANVAS_HEIGHT - 42, y))

  topologyState.value.positions[nodeId] = { x: safeX, y: safeY }
}

function handleNodePointerDown(nodeId: string, event: PointerEvent) {
  draggingNodeId.value = nodeId
  selectNode(nodeId)
  isPanningBoard.value = false
  ;(event.currentTarget as HTMLElement | null)?.setPointerCapture?.(event.pointerId)
  updateNodePosition(nodeId, event.clientX, event.clientY)
}

function handleBoardPointerDown(event: PointerEvent) {
  const target = event.target as HTMLElement | null
  if (target?.closest('.topology-node')) {
    return
  }

  const board = boardRef.value
  if (!board) return

  isPanningBoard.value = true
  panStartClient.value = { x: event.clientX, y: event.clientY }
  panStartScroll.value = { left: board.scrollLeft, top: board.scrollTop }
  board.setPointerCapture?.(event.pointerId)
}

function handleGlobalPointerMove(event: PointerEvent) {
  if (draggingNodeId.value) {
    updateNodePosition(draggingNodeId.value, event.clientX, event.clientY)
    return
  }

  if (!isPanningBoard.value || !boardRef.value) return

  const dx = event.clientX - panStartClient.value.x
  const dy = event.clientY - panStartClient.value.y
  boardRef.value.scrollLeft = panStartScroll.value.left - dx
  boardRef.value.scrollTop = panStartScroll.value.top - dy
}

function handleGlobalPointerUp() {
  draggingNodeId.value = null
  isPanningBoard.value = false
}

onMounted(() => {
  window.addEventListener('pointermove', handleGlobalPointerMove)
  window.addEventListener('pointerup', handleGlobalPointerUp)

  if (!hasTopologyLoadedOnce) {
    loadingTimer = window.setTimeout(() => {
      isDataLoading.value = false
      hasTopologyLoadedOnce = true
    }, 1200)
  } else {
    isDataLoading.value = false
  }
})

onUnmounted(() => {
  window.removeEventListener('pointermove', handleGlobalPointerMove)
  window.removeEventListener('pointerup', handleGlobalPointerUp)

  if (loadingTimer) {
    window.clearTimeout(loadingTimer)
  }
})
</script>

<template>
  <div class="topology-stage-shell" aria-label="网络拓扑视图">
    <div v-if="isDataLoading" class="topology-loading-view">
      <div class="topology-loading-spinner"></div>
      <p class="topology-loading-text">正在扫描网络拓扑图并同步链路关系...</p>
    </div>

    <template v-else>
      <div class="topology-stage-grid">
        <section class="topology-stage-main">
          <div class="topology-stage-toolbar">
            <div class="topology-stage-toolbar__copy">
              <span class="topology-stage-toolbar__eyebrow">TOPOLOGY MATRIX</span>
              <strong>首页链路拓扑与关系图谱</strong>
              <p>围绕核心交换、边界防护、业务分区与蜜罐联动，展示资产间的实时连接、风险流向与阻断路径。</p>
            </div>

            <div class="topology-stage-stats">
              <article v-for="card in statCards" :key="card.label" class="topology-stage-stat">
                <span>{{ card.label }}</span>
                <strong>{{ card.value }}</strong>
              </article>
            </div>
          </div>

          <div
            ref="boardRef"
            class="topology-stage-board"
            :class="{ 'topology-stage-board--panning': isPanningBoard }"
            aria-label="内网信任链路与告警链路拓扑图"
            @pointerdown="handleBoardPointerDown"
          >
            <div class="topology-stage-board__aurora" aria-hidden="true"></div>
            <div class="topology-stage-board__canvas">
              <div class="topology-stage-board__grid" aria-hidden="true"></div>
              <div class="topology-stage-board__radar" aria-hidden="true"></div>

              <svg class="topology-stage-board__svg" :viewBox="`0 0 ${CANVAS_WIDTH} ${CANVAS_HEIGHT}`" preserveAspectRatio="none">
                <defs>
                  <filter id="topologyGlow" x="-25%" y="-25%" width="150%" height="150%">
                    <feGaussianBlur stdDeviation="4" result="blur" />
                    <feMerge>
                      <feMergeNode in="blur" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                </defs>

                <g v-for="link in stageLinks" :key="link.id">
                  <line
                    class="topology-link topology-link--shadow"
                    :x1="link.sourcePoint.x"
                    :y1="link.sourcePoint.y"
                    :x2="link.targetPoint.x"
                    :y2="link.targetPoint.y"
                  />

                  <line
                    class="topology-link"
                    :class="`topology-link--${link.type}`"
                    :x1="link.sourcePoint.x"
                    :y1="link.sourcePoint.y"
                    :x2="link.targetPoint.x"
                    :y2="link.targetPoint.y"
                    :stroke="link.color"
                    :stroke-width="link.active ? 3.2 : 2"
                    :stroke-dasharray="link.type === 'attack' ? '8 8' : link.type === 'blocked' ? '4 7' : undefined"
                    :opacity="link.active ? 1 : 0.84"
                    :filter="link.active ? 'url(#topologyGlow)' : undefined"
                  />

                  <circle
                    v-if="link.type !== 'lan'"
                    class="topology-link__pulse"
                    :r="link.type === 'attack' ? 3.6 : 3"
                    :fill="link.color"
                  >
                    <animateMotion
                      :dur="link.type === 'attack' ? '2.4s' : link.type === 'blocked' ? '3s' : '3.6s'"
                      repeatCount="indefinite"
                      :path="buildMotionPath(link)"
                    />
                  </circle>
                </g>
              </svg>

              <button
                v-for="node in stageNodes"
                :key="node.id"
                type="button"
                class="topology-node"
                :class="{ 'topology-node--selected': node.selected }"
                :style="{
                  left: `${node.point.x}px`,
                  top: `${node.point.y}px`,
                  '--topology-node-tone': node.tone,
                }"
                :aria-label="`${node.label} ${node.status}`"
                :aria-pressed="node.selected"
                @pointerdown="handleNodePointerDown(node.id, $event)"
                @click="selectNode(node.id)"
              >
                <span class="topology-node__halo" aria-hidden="true"></span>
                <span class="topology-node__icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" class="topology-node__icon-svg">
                    <path v-if="node.type === 'edge'" d="M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16Zm0 2.2a5.8 5.8 0 0 1 4.73 2.44h-2.1c-.32-.92-.79-1.75-1.38-2.44H12Zm-2.2.43c-.6.66-1.07 1.47-1.4 2.36H6.33A5.8 5.8 0 0 1 9.8 6.63ZM6.2 12c0-.38.04-.74.11-1.1h2.11A12.4 12.4 0 0 0 8.3 12c0 .37.04.73.1 1.08H6.3A5.7 5.7 0 0 1 6.2 12Zm.13 2.98h2.08c.33.88.8 1.69 1.39 2.35a5.8 5.8 0 0 1-3.47-2.35ZM12 17.8h-.03c-.86-.73-1.5-1.73-1.9-2.82h3.84c-.4 1.1-1.05 2.1-1.91 2.82Zm2.56-.47c.58-.66 1.05-1.46 1.38-2.35h2.06a5.8 5.8 0 0 1-3.44 2.35ZM18.8 12c0 .37-.03.73-.1 1.08h-2.1c.07-.35.1-.71.1-1.08s-.03-.74-.1-1.1h2.1c.07.36.1.72.1 1.1Z" />
                    <path v-else-if="node.type === 'firewall'" d="M12 3 18 6v5c0 4.2-2.55 7.45-6 9-3.45-1.55-6-4.8-6-9V6l6-3Z" />
                    <path v-else-if="node.type === 'router'" d="M12 4l7 4v8l-7 4-7-4V8l7-4Z" />
                    <path v-else-if="node.type === 'honeypot'" d="M12 4c3.8 0 6.5 2.35 6.5 5.3 0 3.86-3.17 7.7-6.5 10.7-3.33-3-6.5-6.84-6.5-10.7C5.5 6.35 8.2 4 12 4Z" />
                    <rect v-else x="5" y="5" width="14" height="14" rx="3" />
                  </svg>
                </span>

                <span class="topology-node__token">{{ node.labelToken }}</span>
                <span class="topology-node__label">{{ node.label }}</span>
                <span class="topology-node__status">{{ node.status }}</span>
              </button>
            </div>

            <div class="topology-stage-board__legend">
              <span><i style="background: hsl(var(--primary));"></i>骨干上联</span>
              <span><i style="background: rgba(0, 255, 136, 0.58)"></i>内网链路</span>
              <span><i style="background: rgba(0, 255, 136, 0.8)"></i>阻断联动</span>
              <span><i style="background: rgba(255, 68, 68, 0.82)"></i>攻击链路</span>
            </div>
          </div>
        </section>

        <aside class="topology-stage-sidepanel">
          <section class="topology-panel">
            <span class="topology-panel__eyebrow">FOCUS NODE</span>
            <strong>{{ selectedNode?.label || '未选择节点' }}</strong>
            <p>{{ selectedNode ? nodeTypeText[selectedNode.type] : '节点信息待加载' }}</p>

            <div class="topology-panel__metrics">
              <div v-for="item in selectedNodeMeta" :key="item.label" class="topology-panel__metric">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>
          </section>

          <section class="topology-panel">
            <div class="topology-panel__heading">
              <span class="topology-panel__eyebrow">RELATIONS</span>
              <strong>关联关系</strong>
            </div>

            <ul class="topology-relation-list">
              <li v-for="item in relationCards" :key="item.id" class="topology-relation-item" :class="item.tone">
                <span class="topology-relation-item__badge">{{ item.badge }}</span>
                <div class="topology-relation-item__body">
                  <strong>{{ item.title }}</strong>
                  <p>{{ item.description }}</p>
                </div>
              </li>
            </ul>
          </section>

          <section class="topology-panel">
            <div class="topology-panel__heading">
              <span class="topology-panel__eyebrow">EVENT STREAM</span>
              <strong>联动事件流</strong>
            </div>

            <ul class="topology-event-list">
              <li v-for="item in eventFeed" :key="item.id" class="topology-event-item">
                <span class="topology-event-item__level" :class="`level-${item.level}`">{{ item.level }}</span>
                <div class="topology-event-item__body">
                  <strong>{{ item.title }}</strong>
                  <p>{{ item.meta }}</p>
                </div>
                <time>{{ item.time }}</time>
              </li>
            </ul>
          </section>
        </aside>
      </div>
    </template>
  </div>
</template>

<style scoped>
.topology-loading-view {
  display: flex;
  flex: 1;
  min-height: 620px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
}

.topology-loading-spinner {
  width: 50px;
  height: 50px;
  border: 4px solid rgba(6, 182, 212, 0.16);
  border-top-color: rgb(34, 211, 238);
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}

.topology-loading-text {
  font-size: 14px;
  color: rgb(103 232 249 / 0.92);
  letter-spacing: 0.04em;
  animation: pulse 1.8s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }

  50% {
    opacity: 0.55;
  }
}

.topology-stage-shell {
  display: flex;
  flex: 1;
  min-height: 0;
  height: 100%;
}

.topology-stage-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 14px;
  flex: 1;
  min-height: 0;
  width: 100%;
}

.topology-stage-main,
.topology-stage-sidepanel {
  min-height: 0;
}

.topology-stage-main {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 12px;
}

.topology-stage-toolbar {
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 12px;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid rgb(56 189 248 / 0.16);
  background:
    radial-gradient(circle at top left, rgb(34 211 238 / 0.12), transparent 40%),
    linear-gradient(155deg, rgb(8 47 73 / 0.5), rgb(2 6 23 / 0.78));
}

.topology-stage-toolbar__copy {
  display: grid;
  gap: 6px;
  max-width: 380px;
}

.topology-stage-toolbar__eyebrow,
.topology-panel__eyebrow {
  display: inline-flex;
  width: fit-content;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid rgb(56 189 248 / 0.28);
  background: rgb(14 116 144 / 0.18);
  color: rgb(125 211 252 / 0.95);
  font-size: 10px;
  letter-spacing: 0.16em;
}

.topology-stage-toolbar__copy strong {
  color: rgb(224 242 254);
  font-size: 16px;
}

.topology-stage-toolbar__copy p {
  color: rgb(148 163 184);
  font-size: 12px;
  line-height: 1.55;
}

.topology-stage-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  flex: 1;
}

.topology-stage-stat {
  display: grid;
  align-content: center;
  gap: 6px;
  min-height: 80px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid rgb(125 211 252 / 0.14);
  background: linear-gradient(180deg, rgb(15 23 42 / 0.72), rgb(15 23 42 / 0.34));
}

.topology-stage-stat span {
  font-size: 11px;
  color: rgb(186 230 253);
}

.topology-stage-stat strong {
  font-size: 20px;
  color: rgb(240 249 255);
}

.topology-stage-board {
  position: relative;
  overflow: auto;
  min-height: 620px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: linear-gradient(180deg, rgba(10, 18, 36, 0.9), rgba(7, 13, 29, 0.96));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04), 0 0 24px hsl(var(--primary) / 0.1);
  cursor: grab;
}

.topology-stage-board--panning {
  cursor: grabbing;
}

.topology-stage-board__aurora {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 16% 18%, rgb(56 189 248 / 0.18), transparent 24%),
    radial-gradient(circle at 82% 16%, rgb(34 197 94 / 0.12), transparent 22%),
    radial-gradient(circle at 74% 82%, rgb(14 165 233 / 0.12), transparent 28%);
  pointer-events: none;
}

.topology-stage-board__canvas {
  position: relative;
  width: 920px;
  height: 620px;
}

.topology-stage-board__grid,
.topology-stage-board__radar,
.topology-stage-board__svg {
  position: absolute;
  inset: 0;
}

.topology-stage-board__grid {
  background-image:
    linear-gradient(hsl(var(--primary) / 0.08) 1px, transparent 1px),
    linear-gradient(90deg, hsl(var(--primary) / 0.08) 1px, transparent 1px);
  background-size: 36px 36px;
  mask-image: radial-gradient(circle at center, black 58%, transparent 96%);
}

.topology-stage-board__radar {
  background:
    radial-gradient(circle at center, rgb(34 211 238 / 0.12), transparent 36%),
    radial-gradient(circle at center, transparent 52%, rgb(34 211 238 / 0.08) 53%, transparent 54%),
    radial-gradient(circle at center, transparent 68%, rgb(34 211 238 / 0.06) 69%, transparent 70%);
  opacity: 0.72;
  pointer-events: none;
}

.topology-stage-board__svg {
  width: 920px;
  height: 620px;
}

.topology-link--shadow {
  stroke: rgb(14 165 233 / 0.18);
  stroke-width: 7;
  opacity: 0.18;
  filter: blur(6px);
}

.topology-link {
  transition: opacity 180ms ease, stroke-width 180ms ease;
}

.topology-link__pulse {
  filter: drop-shadow(0 0 6px currentColor);
}

.topology-node {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 96px;
  min-height: 92px;
  padding: 0;
  border: 0;
  background: transparent;
  color: rgba(232, 234, 246, 0.94);
  transform: translate(-50%, -50%);
  cursor: grab;
  transition: transform 160ms ease, filter 160ms ease;
  user-select: none;
}

.topology-node:active {
  cursor: grabbing;
}

.topology-node:hover,
.topology-node--selected {
  transform: translate(-50%, -50%) scale(1.05);
  filter: drop-shadow(0 0 16px color-mix(in srgb, var(--topology-node-tone) 28%, transparent));
}

.topology-node__halo,
.topology-node__icon {
  position: absolute;
  top: 2px;
  left: 50%;
  transform: translateX(-50%);
  border-radius: 999px;
}

.topology-node__halo {
  width: 74px;
  height: 74px;
  border: 1px solid color-mix(in srgb, var(--topology-node-tone) 60%, transparent);
  background: radial-gradient(circle, color-mix(in srgb, var(--topology-node-tone) 22%, transparent), transparent 72%);
  box-shadow: 0 0 28px color-mix(in srgb, var(--topology-node-tone) 16%, transparent);
}

.topology-node__icon {
  display: grid;
  place-items: center;
  width: 52px;
  height: 52px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.98), rgba(10, 17, 33, 0.96));
  border: 2px solid color-mix(in srgb, var(--topology-node-tone) 72%, rgba(255, 255, 255, 0.1));
  color: var(--topology-node-tone);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08), 0 12px 30px rgba(15, 23, 42, 0.4);
}

.topology-node__icon-svg {
  width: 22px;
  height: 22px;
  fill: currentColor;
}

.topology-node__token,
.topology-node__label,
.topology-node__status {
  position: relative;
  z-index: 1;
}

.topology-node__token {
  margin-top: 62px;
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.72);
  font-size: 10px;
  letter-spacing: 0.16em;
  color: var(--topology-node-tone);
}

.topology-node__label {
  max-width: 140px;
  text-align: center;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.35;
}

.topology-node__status {
  color: rgba(191, 219, 254, 0.72);
  font-size: 10px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.topology-stage-board__legend {
  position: absolute;
  left: 16px;
  bottom: 16px;
  display: grid;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid hsl(var(--primary) / 0.18);
  background: rgba(5, 10, 24, 0.72);
  backdrop-filter: blur(14px);
}

.topology-stage-board__legend span {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: rgb(203 213 225 / 0.88);
  font-size: 11px;
}

.topology-stage-board__legend i {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  display: inline-block;
  box-shadow: 0 0 12px currentColor;
}

.topology-stage-sidepanel {
  display: grid;
  grid-template-rows: auto auto 1fr;
  gap: 12px;
}

.topology-panel {
  display: grid;
  gap: 12px;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid rgb(56 189 248 / 0.14);
  background:
    radial-gradient(circle at top right, rgb(56 189 248 / 0.08), transparent 34%),
    linear-gradient(180deg, rgb(15 23 42 / 0.86), rgb(2 6 23 / 0.82));
}

.topology-panel strong {
  color: rgb(226 232 240);
  font-size: 15px;
  line-height: 1.4;
}

.topology-panel p {
  color: rgb(148 163 184 / 0.92);
  font-size: 12px;
  line-height: 1.5;
}

.topology-panel__heading {
  display: grid;
  gap: 8px;
}

.topology-panel__metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.topology-panel__metric {
  display: grid;
  gap: 6px;
  padding: 10px;
  border-radius: 12px;
  border: 1px solid rgb(125 211 252 / 0.1);
  background: rgb(15 23 42 / 0.6);
}

.topology-panel__metric span {
  color: rgb(125 211 252 / 0.78);
  font-size: 10px;
}

.topology-panel__metric strong {
  color: rgb(240 249 255);
  font-size: 12px;
}

.topology-relation-list,
.topology-event-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.topology-relation-item,
.topology-event-item {
  display: grid;
  gap: 10px;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid rgb(148 163 184 / 0.12);
  background: rgb(15 23 42 / 0.56);
}

.topology-relation-item {
  grid-template-columns: auto minmax(0, 1fr);
}

.topology-relation-item__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 72px;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgb(14 116 144 / 0.16);
  color: rgb(125 211 252);
  font-size: 10px;
}

.topology-relation-item__body,
.topology-event-item__body {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.topology-relation-item__body strong,
.topology-event-item__body strong {
  font-size: 13px;
}

.topology-relation-item__body p,
.topology-event-item__body p {
  font-size: 11px;
  color: rgb(148 163 184 / 0.92);
}

.topology-relation-item.relation-attack {
  border-color: rgb(248 113 113 / 0.18);
}

.topology-relation-item.relation-blocked {
  border-color: rgb(74 222 128 / 0.18);
}

.topology-event-item {
  grid-template-columns: auto minmax(0, 1fr) auto;
}

.topology-event-item__level {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 52px;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.topology-event-item__level.level-critical,
.topology-event-item__level.level-high {
  background: rgb(127 29 29 / 0.34);
  color: rgb(252 165 165);
}

.topology-event-item__level.level-medium {
  background: rgb(120 53 15 / 0.32);
  color: rgb(253 186 116);
}

.topology-event-item__level.level-low {
  background: rgb(22 101 52 / 0.28);
  color: rgb(134 239 172);
}

.topology-event-item time {
  color: rgb(125 211 252 / 0.76);
  font-size: 10px;
  white-space: nowrap;
}

:global(html:not(.dark)) .topology-stage-toolbar,
:global(html:not(.dark)) .topology-panel,
:global(html:not(.dark)) .topology-stage-stat,
:global(html:not(.dark)) .topology-panel__metric {
  border-color: hsl(var(--border) / 0.72);
  background: linear-gradient(180deg, hsl(var(--card) / 0.98), hsl(var(--secondary) / 0.68));
  box-shadow: 0 10px 22px hsl(var(--primary) / 0.04);
}

:global(html:not(.dark)) .topology-stage-toolbar__eyebrow,
:global(html:not(.dark)) .topology-panel__eyebrow,
:global(html:not(.dark)) .topology-relation-item__badge {
  border-color: hsl(var(--border) / 0.72);
  background: hsl(var(--secondary) / 0.92);
  color: hsl(var(--foreground));
}

:global(html:not(.dark)) .topology-stage-toolbar__copy strong,
:global(html:not(.dark)) .topology-stage-stat strong,
:global(html:not(.dark)) .topology-panel strong,
:global(html:not(.dark)) .topology-panel__metric strong,
:global(html:not(.dark)) .topology-relation-item__body strong,
:global(html:not(.dark)) .topology-event-item__body strong,
:global(html:not(.dark)) .topology-node__label {
  color: hsl(var(--foreground));
}

:global(html:not(.dark)) .topology-stage-toolbar__copy p,
:global(html:not(.dark)) .topology-stage-stat span,
:global(html:not(.dark)) .topology-panel p,
:global(html:not(.dark)) .topology-panel__metric span,
:global(html:not(.dark)) .topology-relation-item__body p,
:global(html:not(.dark)) .topology-event-item__body p,
:global(html:not(.dark)) .topology-node__status,
:global(html:not(.dark)) .topology-stage-board__legend span,
:global(html:not(.dark)) .topology-event-item time {
  color: hsl(var(--muted-foreground));
}

:global(html:not(.dark)) .topology-stage-board {
  border-color: hsl(var(--border) / 0.72);
  background: linear-gradient(180deg, hsl(var(--card) / 0.98), hsl(var(--secondary) / 0.7));
  box-shadow: inset 0 1px 0 hsl(var(--background)), 0 14px 30px hsl(var(--primary) / 0.05);
}

:global(html:not(.dark)) .topology-stage-board__grid {
  background-image:
    linear-gradient(hsl(var(--border) / 0.5) 1px, transparent 1px),
    linear-gradient(90deg, hsl(var(--border) / 0.5) 1px, transparent 1px);
}

:global(html:not(.dark)) .topology-stage-board__radar {
  background:
    radial-gradient(circle at center, hsl(var(--primary) / 0.08), transparent 36%),
    radial-gradient(circle at center, transparent 52%, hsl(var(--primary) / 0.05) 53%, transparent 54%),
    radial-gradient(circle at center, transparent 68%, hsl(var(--primary) / 0.04) 69%, transparent 70%);
}

:global(html:not(.dark)) .topology-stage-board__legend {
  border-color: hsl(var(--border) / 0.75);
  background: hsl(var(--background) / 0.88);
}

:global(html:not(.dark)) .topology-node__icon {
  background: linear-gradient(180deg, hsl(var(--card) / 0.98), hsl(var(--secondary) / 0.88));
  box-shadow: inset 0 1px 0 hsl(var(--background)), 0 10px 20px hsl(var(--primary) / 0.08);
}

:global(html:not(.dark)) .topology-node__token {
  background: hsl(var(--secondary) / 0.92);
}

@media (max-width: 1280px) {
  .topology-stage-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .topology-stage-sidepanel {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    grid-template-rows: none;
  }
}

@media (max-width: 960px) {
  .topology-stage-toolbar {
    flex-direction: column;
  }

  .topology-stage-stats,
  .topology-panel__metrics,
  .topology-stage-sidepanel {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .topology-stage-stats,
  .topology-panel__metrics,
  .topology-stage-sidepanel {
    grid-template-columns: minmax(0, 1fr);
  }

  .topology-event-item {
    grid-template-columns: minmax(0, 1fr);
  }

  .topology-event-item time {
    justify-self: start;
  }
}
</style>
