<script lang="ts">
let hasTopologyLoadedOnce = false
</script>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import * as d3 from 'd3-force'
import { 
  Zap, Plus, Trash2, Save, X, MousePointer2, 
  ShieldCheck, Server, Database, Router, HardDrive, Cpu, 
  ArrowRight, MousePointerClick, Loader2 
} from 'lucide-vue-next'

import { api, apiCall } from '@/api'
import {
  createTopologyFixture,
  getTopologySummary,
  type TopologyNodeType,
} from '@/lib/topology-state'

const props = defineProps<{
  topology?: any
  recentAttacks?: any[]
  loading?: boolean
}>()

// --- 核心状态 ---
const nodes = ref<any[]>([])
const links = ref<any[]>([])
const isDataLoading = ref(!hasTopologyLoadedOnce)
const isSaving = ref(false)

// --- 编辑与交互状态 ---
const isEditMode = ref(false)
const selectedNodeId = ref<string | null>(null)
const mousePos = ref({ x: 0, y: 0 })
const isAddingNode = ref(false)
const newNodeName = ref('')
const newNodeType = ref<TopologyNodeType>('server')

const selectedNode = computed(() => nodes.value.find(n => n.id === selectedNodeId.value))

// --- 视图平移与缩放 ---
const pan = ref({ x: 0, y: 0 })
const panStart = ref({ x: 0, y: 0 })
const zoom = ref(1)
const isPanning = ref(false)
const draggingId = ref<string | null>(null)

// --- D3 仿真 ---
const simulation = ref<any>(null)
const boardRef = ref<HTMLElement | null>(null)

const nodeColors: Record<string, string> = {
  online: '#00ff88',
  offline: '#f43f5e', // 更鲜艳的红色
  warning: '#fbbf24', // 更亮的黄色
  attack: '#f43f5e',
}

const nodeIcons: Record<string, any> = {
  firewall: ShieldCheck,
  server: Server,
  honeypot: Database,
  router: Router,
  switch: HardDrive,
  edge: Cpu,
}

const summary = computed(() => getTopologySummary({ nodes: nodes.value, links: links.value }))

// --- API 交互 ---
const fetchTopology = async () => {
  const data = await apiCall(() => api.get<any>('/api/v1/topology'))
  if (data && data.nodes?.length > 0) {
    nodes.value = data.nodes
    links.value = data.links
  } else {
    // 首次使用或空数据时，使用预设
    const fixture = createTopologyFixture()
    nodes.value = fixture.nodes
    links.value = fixture.links
  }
  isDataLoading.value = false
  hasTopologyLoadedOnce = true
}

const handleSave = async () => {
  isSaving.value = true
  const res = await apiCall(() => api.post('/api/v1/topology', { nodes: nodes.value, links: links.value }))
  if (res) {
    isEditMode.value = false
    selectedNodeId.value = null
  }
  isSaving.value = false
}

// --- D3 仿真逻辑 ---
const initSimulation = () => {
  if (simulation.value) simulation.value.stop()
  
  const width = boardRef.value?.clientWidth || 920
  const height = boardRef.value?.clientHeight || 420

  simulation.value = d3.forceSimulation(nodes.value)
    .force('link', d3.forceLink(links.value).id((d: any) => d.id).distance(220)) // 增加间距
    .force('charge', d3.forceManyBody().strength(-1200))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(80))

  simulation.value.on('tick', () => {
    // 强制更新视图
    nodes.value = [...nodes.value]
    links.value = [...links.value]
  })
}

watch([nodes, links], () => {
  if (!simulation.value && nodes.value.length > 0) {
    initSimulation()
  }
}, { deep: false })

// --- 交互逻辑 ---
const handleMouseMove = (e: MouseEvent) => {
  if (!boardRef.value) return
  const rect = boardRef.value.getBoundingClientRect()
  
  // 考虑缩放坐标转换
  const rawX = e.clientX - rect.left - pan.value.x
  const rawY = e.clientY - rect.top - pan.value.y
  const x = rawX / zoom.value
  const y = rawY / zoom.value

  if (selectedNodeId.value && isEditMode.value) {
    mousePos.value = { x, y }
  }

  if (draggingId.value && simulation.value) {
    const node = nodes.value.find(n => n.id === draggingId.value)
    if (node) {
      node.fx = x
      node.fy = y
    }
  } else if (isPanning.value) {
    pan.value = {
      x: e.clientX - panStart.value.x,
      y: e.clientY - panStart.value.y
    }
  }
}

const handleWheel = (e: WheelEvent) => {
  e.preventDefault()
  const direction = e.deltaY > 0 ? 0.9 : 1.1
  const newZoom = Math.max(0.3, Math.min(3, zoom.value * direction))
  
  // 以鼠标位置为中心缩放（可选增强，这里先做简单的比例缩放）
  zoom.value = newZoom
}

const handleMouseUp = () => {
  if (draggingId.value && simulation.value) {
    simulation.value.alphaTarget(0)
    const node = nodes.value.find(n => n.id === draggingId.value)
    if (node) {
      node.fx = null
      node.fy = null
    }
  }
  draggingId.value = null
  isPanning.value = false
}

const handleNodeClick = (nodeId: string, e: MouseEvent) => {
  e.stopPropagation()
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
  }
}

const toggleLink = (sourceId: string, targetId: string) => {
  const existingIndex = links.value.findIndex(l => {
    const s = typeof l.source === 'string' ? l.source : l.source.id
    const t = typeof l.target === 'string' ? l.target : l.target.id
    return (s === sourceId && t === targetId) || (s === targetId && t === sourceId)
  })

  if (existingIndex > -1) {
    links.value.splice(existingIndex, 1)
  } else {
    links.value.push({ source: sourceId, target: targetId, type: 'lan' })
  }
  if (simulation.value) {
    simulation.value.force('link').links(links.value)
    simulation.value.alpha(0.3).restart()
  }
}

const addNode = () => {
  if (!newNodeName.value.trim()) return
  const id = `node-${Date.now()}`
  nodes.value.push({
    id,
    label: newNodeName.value,
    type: newNodeType.value,
    status: 'online'
  })
  newNodeName.value = ''
  isAddingNode.value = false
  selectedNodeId.value = id
  if (simulation.value) {
    simulation.value.nodes(nodes.value)
    simulation.value.alpha(0.3).restart()
  }
}

const deleteSelectedNode = () => {
  if (!selectedNodeId.value) return
  nodes.value = nodes.value.filter(n => n.id !== selectedNodeId.value)
  links.value = links.value.filter(l => {
    const s = typeof l.source === 'string' ? l.source : l.source.id
    const t = typeof l.target === 'string' ? l.target : l.target.id
    return s !== selectedNodeId.value && t !== selectedNodeId.value
  })
  selectedNodeId.value = null
  if (simulation.value) {
    simulation.value.nodes(nodes.value)
    simulation.value.force('link').links(links.value)
    simulation.value.alpha(0.3).restart()
  }
}

onMounted(() => {
  fetchTopology()
})

onUnmounted(() => {
  if (simulation.value) simulation.value.stop()
})
</script>

<template>
  <div class="topology-stage-shell" aria-label="网络拓扑视图">
    <div v-if="isDataLoading" class="topology-loading-view">
      <div class="topology-loading-spinner"></div>
      <p class="topology-loading-text">正在扫描全息网络拓扑...</p>
    </div>

    <template v-else>
      <!-- 顶部编辑工具栏 -->
      <div class="topology-toolbar">
        <div v-if="!isEditMode" class="toolbar-main">
          <button @click="isEditMode = true" class="btn-primary">
            <Zap class="w-4 h-4" /> 进入拓扑编辑工作台
          </button>
        </div>
        <div v-else class="toolbar-edit">
          <div class="edit-guide">
            <template v-if="!selectedNodeId">
              <MousePointerClick class="w-4 h-4 animate-bounce text-cyan" /> 第一步：点击选中【起始设备】
            </template>
            <template v-else>
              <Zap class="w-4 h-4 text-cyan" /> 第二步：点击【另一个设备】完成连线
            </template>
          </div>
          <div class="v-divider"></div>
          <button @click="isAddingNode = true" class="btn-ghost">
            <Plus class="w-4 h-4" /> 放置新设备
          </button>
          <button v-if="selectedNodeId" @click="deleteSelectedNode" class="btn-danger">
            <Trash2 class="w-4 h-4" /> 销毁选中设备
          </button>
          <div class="v-divider"></div>
          <div class="action-group">
            <button @click="handleSave" :disabled="isSaving" class="btn-primary btn-sm">
              <template v-if="isSaving"><Loader2 class="w-3.5 h-3.5 animate-spin" /></template>
              <template v-else><Save class="w-3.5 h-3.5" /></template>
              确认发布
            </button>
            <button @click="isEditMode = false; selectedNodeId = null; fetchTopology()" class="btn-ghost btn-sm">退出</button>
          </div>
        </div>
      </div>

      <div 
        ref="boardRef" 
        class="topology-stage-board"
        @mousemove="handleMouseMove"
        @mouseup="handleMouseUp"
        @mouseleave="handleMouseUp"
        @wheel="handleWheel"
      >
        <svg 
          class="topology-stage-board__svg" 
          @mousedown.self="isPanning = true; panStart = { x: $event.clientX - pan.x, y: $event.clientY - pan.y }; selectedNodeId = null"
        >
          <g :transform="`translate(${pan.x}, ${pan.y}) scale(${zoom})`">
            <!-- 实时牵引线 -->
            <line 
              v-if="isEditMode && selectedNode"
              :x1="selectedNode.x"
              :y1="selectedNode.y"
              :x2="mousePos.x"
              :y2="mousePos.y"
              stroke="rgba(0, 212, 255, 0.4)"
              stroke-width="2"
              stroke-dasharray="6,6"
            />

            <!-- 连线层 -->
            <line
              v-for="(link, i) in links"
              :key="i"
              :x1="link.source?.x || 0"
              :y1="link.source?.y || 0"
              :x2="link.target?.x || 0"
              :y2="link.target?.y || 0"
              :stroke="link.type === 'attack' ? '#f43f5e' : 'rgba(0, 212, 255, 0.25)'"
              :stroke-width="link.type === 'attack' ? 3 : 1.5"
              :stroke-dasharray="link.type === 'attack' ? '5 5' : '0'"
              style="transition: stroke 0.3s"
            />

            <!-- 节点层 -->
            <g v-for="node in nodes" :key="node.id" :transform="`translate(${node.x},${node.y})`">
              <!-- 选中光环 -->
              <circle 
                v-if="node.id === selectedNodeId" 
                r="48" 
                class="node-highlight-ring"
              />
              
              <circle 
                r="38" 
                class="node-circle"
                :class="{ 'node-circle--selected': node.id === selectedNodeId }"
                :stroke="nodeColors[node.status] || '#94a3b8'"
                @mousedown="draggingId = node.id; simulation.alphaTarget(0.3).restart(); $event.stopPropagation()"
                @click="handleNodeClick(node.id, $event)"
              />
              
              <foreignObject x="-22" y="-22" width="44" height="44" class="pointer-events-none">
                <div class="node-icon-wrapper">
                  <component 
                    :is="nodeIcons[node.type] || Server" 
                    class="w-full h-full"
                    :style="{ color: node.id === selectedNodeId ? '#00d4ff' : (node.status === 'online' ? '#fff' : nodeColors[node.status]) }"
                  />
                </div>
              </foreignObject>

              <text y="58" text-anchor="middle" class="node-label">{{ node.label }}</text>
            </g>
          </g>
        </svg>

        <!-- 底部说明 -->
        <div class="topology-hint">
          <span><MousePointer2 class="w-3 h-3" /> 拖拽空白处平移</span>
          <span v-if="isEditMode" class="text-cyan"><ArrowRight class="w-3 h-3" /> 先点设备 A，再点设备 B 连线</span>
        </div>

        <div class="topology-legend">
          <div class="legend-item"><i style="background: #00ff88"></i>在线</div>
          <div class="legend-item"><i style="background: #ff4444"></i>告警/攻击</div>
          <div class="legend-item"><i style="background: rgba(0, 212, 255, 0.4)"></i>常规链路</div>
        </div>
      </div>

      <!-- 新增节点侧边面板 -->
      <transition name="slide-right">
        <div v-if="isAddingNode" class="node-addition-panel">
          <div class="panel-header">
            <h3><Plus class="text-cyan w-5 h-5" /> 资产入场</h3>
            <button @click="isAddingNode = false" class="btn-icon"><X /></button>
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
                  @click="newNodeType = type as TopologyNodeType"
                  :class="{ active: newNodeType === type }"
                  class="type-btn"
                >
                  <component :is="icon" class="w-6 h-6" />
                  <span>{{ type }}</span>
                </button>
              </div>
            </div>
            <button @click="addNode" class="btn-primary w-full mt-6 py-3">执行部署</button>
          </div>
        </div>
      </transition>
    </template>
  </div>
</template>

<style scoped>
.topology-stage-shell {
  height: 100%;
  background: #050b15;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(0, 212, 255, 0.1);
  position: relative;
}

/* 工具栏 */
.topology-toolbar {
  position: absolute;
  top: 40px; /* 下移一点 */
  left: 50%;
  transform: translateX(-50%);
  z-index: 50;
  pointer-events: auto;
}

.toolbar-main, .toolbar-edit {
  background: rgba(15, 23, 42, 0.98); /* 提高不透明度 */
  border: 1px solid rgba(0, 212, 255, 0.4);
  padding: 8px 16px;
  border-radius: 99px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.6);
}

.edit-guide {
  font-size: 14px;
  color: #fff;
  font-weight: bold;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
}

.text-cyan { color: #00d4ff; }
.v-divider { width: 1px; height: 16px; background: rgba(255,255,255,0.2); }

/* 画板 */
.topology-stage-board {
  height: 100%;
  position: relative;
  cursor: grab;
  background: #050b15; /* 使用纯色背景，去掉径向渐变（蒙版感） */
}

.topology-stage-board:active { cursor: grabbing; }

.topology-stage-board__svg {
  width: 100%;
  height: 100%;
  shape-rendering: geometricPrecision;
}

/* 节点 */
.node-circle {
  fill: #0f172a;
  stroke-width: 3;
  cursor: pointer;
  transition: r 0.3s, stroke-width 0.3s, stroke 0.3s;
}

.node-circle--selected {
  stroke: #00d4ff !important;
  stroke-width: 5;
}

.node-highlight-ring {
  fill: none;
  stroke: #00d4ff;
  stroke-width: 2;
  opacity: 0.5;
  animation: pulse 2s infinite ease-out;
}

.node-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.node-label {
  font-size: 14px;
  fill: #fff;
  font-weight: 600;
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  pointer-events: none;
  /* 移除 text-shadow 以减少模糊感，改用背景反衬或加粗 */
}

/* 引导信息 */
.topology-hint {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 24px;
  font-size: 12px;
  color: rgba(0, 212, 255, 0.5);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  pointer-events: none;
  background: rgba(10, 25, 47, 0.8);
  padding: 4px 16px;
  border-radius: 99px;
}

.topology-legend {
  position: absolute;
  left: 20px;
  bottom: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: rgba(15, 23, 42, 0.95);
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid rgba(0, 212, 255, 0.2);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
}

.legend-item i {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

/* 侧边面板 */
.node-addition-panel {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 320px;
  background: rgba(5, 11, 21, 0.98);
  border-left: 1px solid rgba(0, 212, 255, 0.1);
  padding: 30px;
  z-index: 100;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
}

.panel-header h3 { color: #fff; font-size: 18px; display: flex; align-items: center; gap: 8px; }

.form-item { margin-bottom: 24px; }
.form-item label { display: block; font-size: 11px; color: rgba(255,255,255,0.4); text-transform: uppercase; margin-bottom: 8px; font-weight: bold; }
.form-item input { width: 100%; background: rgba(255,255,255,0.05); border: none; border-bottom: 2px solid rgba(255,255,255,0.1); padding: 10px 0; color: #fff; outline: none; transition: border-color 0.3s; }
.form-item input:focus { border-color: #00d4ff; }

.type-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.type-btn { background: rgba(255,255,255,0.03); border: 2px solid transparent; border-radius: 12px; padding: 15px; display: flex; flex-direction: column; align-items: center; gap: 8px; color: rgba(255,255,255,0.3); transition: all 0.3s; }
.type-btn.active { background: rgba(0, 212, 255, 0.1); border-color: #00d4ff; color: #00d4ff; }
.type-btn span { font-size: 10px; text-transform: uppercase; font-weight: bold; }

/* 按钮通用 */
.btn-primary { background: #00d4ff; color: #000; border: none; border-radius: 99px; padding: 8px 16px; font-weight: bold; display: flex; align-items: center; gap: 6px; cursor: pointer; transition: transform 0.2s; font-size: 13px; }
.btn-primary:hover { transform: scale(1.05); }
.btn-ghost { background: transparent; border: none; color: rgba(255,255,255,0.6); padding: 8px 16px; font-size: 13px; font-weight: bold; display: flex; align-items: center; gap: 6px; cursor: pointer; border-radius: 99px; }
.btn-ghost:hover { background: rgba(255,255,255,0.05); color: #fff; }
.btn-danger { color: #ff4444; background: rgba(255, 68, 68, 0.1); border: none; padding: 8px 16px; border-radius: 99px; font-size: 13px; font-weight: bold; display: flex; align-items: center; gap: 6px; cursor: pointer; }
.btn-sm { padding: 4px 12px; font-size: 12px; }

@keyframes pulse {
  0% { transform: scale(0.8); opacity: 0.5; }
  100% { transform: scale(1.2); opacity: 0; }
}

.slide-right-enter-active, .slide-right-leave-active { transition: transform 0.3s; }
.slide-right-enter-from, .slide-right-leave-to { transform: translateX(100%); }
</style>
