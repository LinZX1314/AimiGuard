<script lang="ts">
let hasTopologyLoadedOnce = false
</script>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

import {
  buildTopologyStageLinks,
  buildTopologyStageNodes,
  createTopologyFixture,
  getTopologySummary,
  type TopologyNodeType,
} from '@/lib/topology-state'

interface RecentAttack {
  attack_ip: string
  ip_location?: string
  service_name?: string
  threat_level?: string
  create_time_str?: string
}

defineProps<{
  topology?: {
    nodes: Array<{ id: string; label: string; type: string; status: string }>
    links: Array<{ source: string; target: string; type: string }>
  }
  recentAttacks?: RecentAttack[]
  loading?: boolean
}>()

const topologyState = ref(createTopologyFixture())
const selectedNodeId = ref<string | null>('core-switch')
const boardRef = ref<HTMLElement | null>(null)
const draggingNodeId = ref<string | null>(null)
const isPanningBoard = ref(false)
const panStartClient = ref({ x: 0, y: 0 })
const panStartScroll = ref({ left: 0, top: 0 })
const isDataLoading = ref(!hasTopologyLoadedOnce)

const nodeLabels: Record<TopologyNodeType, string> = {
  edge: 'ED',
  router: 'RT',
  firewall: 'FW',
  server: 'SV',
  switch: 'SW',
  honeypot: 'HP',
}

// 明确“核心数据中心节点”命名
const coreNode = topologyState.value.nodes.find((item) => item.id === 'core-switch')
if (coreNode) {
  coreNode.label = '核心数据中心交换机 - SW-Core-01'
}

const summary = computed(() => getTopologySummary(topologyState.value))

const stageLinks = computed(() => buildTopologyStageLinks(topologyState.value, selectedNodeId.value))
const stageNodes = computed(() =>
  buildTopologyStageNodes(topologyState.value, selectedNodeId.value).map((node) => ({
    ...node,
    labelToken: nodeLabels[node.type],
  })),
)

const statCards = computed(() => [
  { label: '节点总数', value: `${summary.value.nodeCount}` },
  { label: '在线节点', value: `${summary.value.onlineCount}` },
  { label: '告警节点', value: `${summary.value.warningCount + summary.value.attackCount}` },
  { label: '链路总数', value: `${summary.value.linkCount}` },
])

function selectNode(nodeId: string) {
  selectedNodeId.value = nodeId
}

function updateNodePosition(nodeId: string, clientX: number, clientY: number) {
  const board = boardRef.value
  if (!board) return
  const rect = board.getBoundingClientRect()
  const scaleX = 920 / rect.width
  const scaleY = 420 / rect.height

  const x = (clientX - rect.left) * scaleX
  const y = (clientY - rect.top) * scaleY

  const safeX = Math.max(42, Math.min(878, x))
  const safeY = Math.max(42, Math.min(378, y))

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
    setTimeout(() => {
      isDataLoading.value = false
      hasTopologyLoadedOnce = true
    }, 2000)
  }
})

onUnmounted(() => {
  window.removeEventListener('pointermove', handleGlobalPointerMove)
  window.removeEventListener('pointerup', handleGlobalPointerUp)
})
</script>

<template>
  <div class="topology-stage-shell" aria-label="网络拓扑视图">
    <div v-if="isDataLoading" class="topology-loading-view">
      <div class="topology-loading-spinner"></div>
      <p class="topology-loading-text">正在扫描网络拓扑图并获取节点状态...</p>
    </div>

    <template v-else>
      <div class="topology-stage-grid">
        <div
          ref="boardRef"
          class="topology-stage-board"
          :class="{ 'topology-stage-board--panning': isPanningBoard }"
          aria-label="内网信任链路与告警链路拓扑图"
          @pointerdown="handleBoardPointerDown"
        >
        <div class="topology-stage-board__canvas">
          <div class="topology-stage-board__grid" aria-hidden="true"></div>
          <svg class="topology-stage-board__svg" viewBox="0 0 920 420" preserveAspectRatio="none">
            <defs>
              <filter id="topologyGlow" x="-25%" y="-25%" width="150%" height="150%">
                <feGaussianBlur stdDeviation="4" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            <line
              v-for="link in stageLinks"
              :key="link.id"
              :x1="link.sourcePoint.x"
              :y1="link.sourcePoint.y"
              :x2="link.targetPoint.x"
              :y2="link.targetPoint.y"
              :stroke="link.color"
              :stroke-width="link.active ? 3 : 1.9"
              :stroke-dasharray="link.type === 'attack' ? '8 8' : link.type === 'blocked' ? '4 6' : undefined"
              :opacity="link.active ? 1 : 0.86"
              :filter="link.active ? 'url(#topologyGlow)' : undefined"
            />
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
          <span><i style="background: rgba(0, 212, 255, 0.82)"></i>骨干上联</span>
          <span><i style="background: rgba(0, 255, 136, 0.58)"></i>内网链路</span>
          <span><i style="background: rgba(0, 255, 136, 0.8)"></i>阻断联动</span>
          <span><i style="background: rgba(255, 68, 68, 0.82)"></i>攻击链路</span>
        </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.topology-loading-view {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  height: 100%;
  gap: 20px;
}
.topology-loading-spinner {
  width: 48px;
  height: 48px;
  border: 4px solid rgba(6, 182, 212, 0.2);
  border-top-color: rgb(6, 182, 212);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
.topology-loading-text {
  font-size: 14px;
  color: rgb(6, 182, 212);
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.topology-stage-shell {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  height: 100%;
}

.topology-stage-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
  min-height: 0;
  flex: 1;
}

.topology-stage-board {
  position: relative;
  overflow: hidden;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: linear-gradient(180deg, rgba(10, 18, 36, 0.82), rgba(7, 13, 29, 0.92));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04), 0 0 18px rgba(0, 212, 255, 0.08);
}

.topology-stage-board {
  min-height: 320px;
  overflow: auto;
  cursor: grab;
}

.topology-stage-board--panning {
  cursor: grabbing;
}

.topology-stage-board__canvas {
  position: relative;
  width: 920px;
  height: 420px;
}

.topology-stage-board__grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(0, 212, 255, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 212, 255, 0.08) 1px, transparent 1px);
  background-size: 34px 34px;
  mask-image: radial-gradient(circle at center, black, transparent 92%);
}

.topology-stage-board__svg {
  position: absolute;
  inset: 0;
  width: 920px;
  height: 420px;
}

.topology-node {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 72px;
  min-height: 72px;
  padding: 0;
  border: 0;
  background: transparent;
  color: rgba(232, 234, 246, 0.92);
  transform: translate(-50%, -50%);
  cursor: grab;
  transition: transform 160ms ease;
  user-select: none;
}

.topology-node:active {
  cursor: grabbing;
}

.topology-node:hover,
.topology-node--selected {
  transform: translate(-50%, -50%) scale(1.04);
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
  width: 64px;
  height: 64px;
  border: 1px solid color-mix(in srgb, var(--topology-node-tone) 55%, transparent);
  background: radial-gradient(circle, color-mix(in srgb, var(--topology-node-tone) 18%, transparent), transparent 70%);
}

.topology-node__icon {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  background: rgba(13, 27, 42, 0.96);
  border: 2px solid color-mix(in srgb, var(--topology-node-tone) 72%, rgba(255, 255, 255, 0.1));
  color: var(--topology-node-tone);
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
  margin-top: 54px;
  font-size: 10px;
  letter-spacing: 0.12em;
  color: var(--topology-node-tone);
}

.topology-node__label {
  font-size: 12px;
  font-weight: 700;
}

.topology-node__status {
  color: rgba(255, 255, 255, 0.52);
  font-size: 10px;
  text-transform: uppercase;
}

.topology-stage-board__legend {
  display: grid;
  gap: 10px;
}

.topology-stage-board__legend {
  position: absolute;
  left: 12px;
  bottom: 12px;
  padding: 8px 10px;
  border-radius: 12px;
  border: 1px solid rgba(0, 212, 255, 0.16);
  background: rgba(5, 5, 16, 0.78);
  backdrop-filter: blur(12px);
}

.topology-stage-board__legend span {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--muted-foreground);
  font-size: 11px;
}

.topology-stage-board__legend i {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  display: inline-block;
}

</style>
