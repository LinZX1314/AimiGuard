<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import DashboardWelcomeBanner from './DashboardWelcomeBanner.vue'
import DashboardWorldMap from './DashboardWorldMap.vue'
import DashboardTopology from './DashboardTopology.vue'
import DashboardDevicePanel from './DashboardDevicePanel.vue'
import { Activity, Wifi, Server } from 'lucide-vue-next'

interface TopMetrics {
  hfish_total: number
  hfish_high: number
  nmap_online: number
  ai_decisions: number
  blocked_ips: number
}

interface RecentAttack {
  attack_ip: string
  ip_location?: string
  service_name?: string
  threat_level?: string
  create_time_str?: string
}

interface ScreenPayload {
  top_metrics: TopMetrics
  chain_status: Record<string, boolean>
  trends: { labels: string[]; counts: number[] }
  threat_distribution: { levels: string[]; counts: number[] }
  hot_services: Array<{ name: string; count: number }>
  recent_attacks: RecentAttack[]
  topology: {
    nodes: Array<{ id: string; label: string; type: string; status: string }>
    links: Array<{ source: string; target: string; type: string }>
  }
}

const props = defineProps<{
  payload: ScreenPayload
  loading: boolean
  loadError: string
}>()

const containerRef = ref<HTMLElement>()

// 入场动画状态
const animationState = ref({
  welcome: false,
  overviewMap: false,
})

const dashboardViews = [
  { key: 'overview', label: '总览', icon: Activity },
  { key: 'topology', label: '拓扑', icon: Wifi },
  { key: 'device', label: '设备面板', icon: Server },
] as const

const activeView = ref<(typeof dashboardViews)[number]['key']>('overview')
const mockFeedRows = ref<HoneypotFeedItem[]>([])
let mockFeedTimer = 0

interface HoneypotFeedItem {
  id: string
  ip: string
  location: string
  service: string
  level: string
  time: string
}

const honeypotFeedItems = computed<HoneypotFeedItem[]>(() => {
  const realRows = props.payload.recent_attacks.map((item, idx) => ({
    id: `${item.attack_ip}-${item.create_time_str || idx}-${item.service_name || 'unknown'}`,
    ip: item.attack_ip || '未知IP',
    location: item.ip_location || '未知区域',
    service: item.service_name || '未知服务',
    level: item.threat_level || 'medium',
    time: item.create_time_str || '刚刚',
  }))

  // 按时间倒序排列，解析失败时保持原有顺序
  const withTs = realRows.map((item, index) => ({
    ...item,
    index,
    ts: Number.isNaN(Date.parse(item.time)) ? -1 : Date.parse(item.time),
  }))

  const sortedRealRows = withTs
    .sort((a, b) => {
      if (a.ts === -1 && b.ts === -1) return a.index - b.index
      if (a.ts === -1) return 1
      if (b.ts === -1) return -1
      return b.ts - a.ts
    })
    .slice(0, 8)
    .map(({ index, ts, ...item }) => item)

  if (sortedRealRows.length > 0) {
    return sortedRealRows
  }

  return mockFeedRows.value.slice(0, 8)
})

const honeypotLevelText = (level: string) => {
  const lv = level.toLowerCase()
  if (lv === 'critical') return '严重'
  if (lv === 'high') return '高危'
  if (lv === 'medium') return '中危'
  return '低危'
}

const topologySummaryCards = computed(() => {
  const nodes = props.payload.topology?.nodes || []
  const links = props.payload.topology?.links || []
  const onlineStatuses = new Set(['online', 'normal', 'active'])
  const warningStatuses = new Set(['warning', 'alert', 'attack', 'offline'])

  const onlineCount = nodes.filter((n) => onlineStatuses.has((n.status || '').toLowerCase())).length
  const warningCount = nodes.filter((n) => warningStatuses.has((n.status || '').toLowerCase())).length

  return [
    { label: '节点总数', value: nodes.length || 0 },
    { label: '在线节点', value: onlineCount },
    { label: '告警节点', value: warningCount },
    { label: '链路总数', value: links.length || 0 },
  ]
})

const deviceHeaderData = computed(() => {
  const nodes = props.payload.topology?.nodes || []
  const links = props.payload.topology?.links || []
  const coreNode = nodes.find((node) => node.id === 'core-switch') || nodes.find((node) => node.type === 'switch')
  const honeypotNode = nodes.find((node) => node.type === 'honeypot')
  const warningStatuses = new Set(['warning', 'alert', 'attack', 'offline'])
  const warningCount = nodes.filter((n) => warningStatuses.has((n.status || '').toLowerCase())).length

  return {
    title: coreNode?.label || '核心数据中心交换机',
    status: `switch · ${(coreNode?.status || 'online').toLowerCase()}`,
    linkCount: `${links.length || 0} 条链路`,
    honeypot: honeypotNode?.label || '境外攻击源 (Botnet)',
    warningCount: `${warningCount} 项`,
  }
})

onMounted(() => {
  // 启动入场动画序列
  setTimeout(() => { animationState.value.welcome = true }, 200)
  setTimeout(() => { animationState.value.overviewMap = true }, 400)

  // 无真实数据时，模拟“加载后逐条新增”的历史告警效果
  if (!props.payload.recent_attacks.length) {
    const now = Date.now()
    const mockSeeds: HoneypotFeedItem[] = [
      { id: 'sim-1', ip: '185.220.101.45', location: '俄罗斯-莫斯科', service: 'SSH暴力破解', level: 'critical', time: new Date(now - 15_000).toISOString() },
      { id: 'sim-2', ip: '45.227.255.98', location: '巴西-圣保罗', service: 'SQL注入', level: 'high', time: new Date(now - 11_000).toISOString() },
      { id: 'sim-3', ip: '198.51.100.78', location: '美国-纽约', service: 'API滥用', level: 'medium', time: new Date(now - 7_000).toISOString() },
      { id: 'sim-4', ip: '203.0.113.41', location: '印度-孟买', service: '端口扫描', level: 'medium', time: new Date(now - 3_000).toISOString() },
    ]

    let cursor = 0
    mockFeedTimer = window.setInterval(() => {
      const row = mockSeeds[cursor % mockSeeds.length]

      // 新数据插入头部，形成倒序时间列表和自然位移动画
      mockFeedRows.value = [{
        ...row,
        id: `${row.id}-${Date.now()}`,
        time: new Date().toISOString(),
      }, ...mockFeedRows.value].slice(0, 8)

      cursor += 1
    }, 1800)
  }
})

onUnmounted(() => {
  if (mockFeedTimer) {
    window.clearInterval(mockFeedTimer)
  }
})
</script>

<template>
  <div ref="containerRef" class="flex-1 relative overflow-hidden rounded-lg border border-border/20">
    <!-- 主内容区域 -->
    <div class="h-full p-3 md:p-3.5">
      <!-- Topbar: 仅保留当前页面视图切换 -->
      <div class="mb-2.5 flex items-start justify-start">
        <div class="flex items-center gap-1 rounded-lg bg-card/75 p-1 backdrop-blur-sm border border-cyan-500/20 shadow-lg shadow-cyan-500/5">
          <button
            v-for="view in dashboardViews"
            :key="view.key"
            @click="activeView = view.key"
            class="group relative flex items-center gap-2 overflow-hidden rounded-md px-3 py-1.5 text-xs font-medium transition-all duration-300"
            :class="activeView === view.key
              ? 'text-cyan-400 bg-cyan-400/10 border border-cyan-400/30 shadow-inner'
              : 'text-muted-foreground hover:text-foreground'"
          >
            <span v-if="activeView === view.key" class="absolute inset-0 bg-gradient-to-r from-cyan-500/10 to-transparent animate-pulse" />
            <component :is="view.icon" class="h-3.5 w-3.5 transition-transform duration-300 group-hover:scale-110" />
            <span class="relative">{{ view.label }}</span>
          </button>
        </div>
      </div>

      <!-- 主内容区域切换 -->
      <transition name="view-fade" mode="out-in">
        <div class="h-full space-y-3">
          <!-- 三个标签统一动画，但顶部信息按各自页面内容显示 -->
          <div
            class="transition-all duration-700 ease-out"
            :class="animationState.welcome ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'"
          >
            <DashboardWelcomeBanner v-if="activeView === 'overview'" :top-metrics="payload.top_metrics" :loading="loading" />

            <div v-else-if="activeView === 'topology'" class="topology-detail-cards" aria-label="拓扑统计卡片">
              <article v-for="card in topologySummaryCards" :key="card.label" class="topology-detail-card">
                <span>{{ card.label }}</span>
                <strong>{{ card.value }}</strong>
              </article>
            </div>

            <div v-else class="device-detail-strip" aria-label="设备面板详情卡片">
              <div class="device-detail-strip__main">
                <span class="device-detail-strip__eyebrow">SELECTED NODE</span>
                <strong>{{ deviceHeaderData.title }}</strong>
                <p>{{ deviceHeaderData.status }}</p>
              </div>

              <ul class="device-detail-strip__list">
                <li><span>核心骨干</span><strong>{{ deviceHeaderData.linkCount }}</strong></li>
                <li><span>边界隔离</span><strong>1 条阻断</strong></li>
                <li><span>蜜罐联动</span><strong>{{ deviceHeaderData.honeypot }}</strong></li>
                <li><span>异常侦测</span><strong>{{ deviceHeaderData.warningCount }}</strong></li>
              </ul>
            </div>
          </div>

          <div
            class="view-stage-shell transition-all duration-700 ease-out"
            :class="animationState.overviewMap ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6'"
          >
            <!-- 总览视图 -->
            <template v-if="activeView === 'overview'">
              <div class="map-card view-main-card">
                <DashboardWorldMap
                  :recent-attacks="payload.recent_attacks"
                  :loading="loading"
                  :load-error="loadError"
                />
              </div>

              <div class="honeypot-feed-card">
                <div class="honeypot-feed__title">最新蜜罐捕获</div>
                <TransitionGroup name="honeypot-list" tag="div" class="honeypot-feed__list">
                  <div
                    class="honeypot-feed__item"
                    v-for="(item, idx) in honeypotFeedItems"
                    :key="item.id"
                    :style="{ animationDelay: `${idx * 120}ms` }"
                  >
                    <span class="honeypot-feed__level" :class="`level-${item.level.toLowerCase()}`">
                      {{ honeypotLevelText(item.level) }}
                    </span>
                    <span class="honeypot-feed__ip">{{ item.ip }}</span>
                    <span class="honeypot-feed__service">{{ item.service }}</span>
                    <span class="honeypot-feed__location">{{ item.location }}</span>
                    <span class="honeypot-feed__time">{{ item.time }}</span>
                  </div>
                </TransitionGroup>
                <!-- 无数据时的占位 -->
                <div v-if="!honeypotFeedItems.length" class="honeypot-feed__empty">
                  等待捕获数据…
                </div>
              </div>
            </template>

            <!-- 拓扑视图：与总览保持相同主体高度，下方无内容时保留空白区 -->
            <template v-else-if="activeView === 'topology'">
              <div class="map-card view-main-card">
                <DashboardTopology :topology="payload.topology" :recent-attacks="payload.recent_attacks" :loading="loading" />
              </div>
              <div class="view-empty-pad" aria-hidden="true"></div>
            </template>

            <!-- 设备视图：与总览保持相同主体高度，下方无内容时保留空白区 -->
            <template v-else>
              <div class="map-card view-main-card">
                <DashboardDevicePanel :hide-summary-card="true" />
              </div>
              <div class="view-empty-pad" aria-hidden="true"></div>
            </template>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<style scoped>
.map-card {
  border-radius: 12px;
  border: 1px solid hsl(var(--border) / 0.45);
  background: transparent;
  padding: 8px;
}

.view-stage-shell {
  height: calc(100% - 132px);
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.view-main-card {
  height: 520px;
  flex-shrink: 0;
}

.view-empty-pad {
  flex: 1;
  min-height: 0;
}

.topology-detail-cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.topology-detail-card {
  border-radius: 12px;
  border: 1px solid rgb(56 189 248 / 0.25);
  background: linear-gradient(155deg, rgb(8 47 73 / 0.5), rgb(2 6 23 / 0.75));
  padding: 10px 12px;
  display: grid;
  gap: 5px;
}

.topology-detail-card span {
  font-size: 11px;
  color: rgb(125 211 252 / 0.86);
}

.topology-detail-card strong {
  font-size: 18px;
  color: rgb(103 232 249);
}

.device-detail-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  border-radius: 12px;
  border: 1px solid rgb(56 189 248 / 0.22);
  background: linear-gradient(160deg, rgb(8 47 73 / 0.5), rgb(2 6 23 / 0.7));
  padding: 10px 12px;
}

.device-detail-strip__main {
  display: grid;
  gap: 4px;
  min-width: 220px;
}

.device-detail-strip__eyebrow {
  display: inline-flex;
  width: fit-content;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgb(56 189 248 / 0.3);
  background: rgb(14 116 144 / 0.22);
  color: rgb(125 211 252);
  font-size: 10px;
  letter-spacing: 0.12em;
}

.device-detail-strip__main strong {
  color: rgb(224 242 254);
  font-size: 14px;
}

.device-detail-strip__main p {
  color: rgb(148 163 184);
  font-size: 12px;
}

.device-detail-strip__list {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  width: 100%;
  margin: 0;
  padding: 0;
  list-style: none;
}

.device-detail-strip__list li {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.device-detail-strip__list span {
  color: rgb(148 163 184);
  font-size: 11px;
}

.device-detail-strip__list strong {
  color: rgb(165 243 252);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 1200px) {
  .topology-detail-cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .device-detail-strip {
    flex-direction: column;
    align-items: flex-start;
  }

  .device-detail-strip__list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.honeypot-feed-card {
  border-radius: 12px;
  border: 1px solid rgb(34 211 238 / 0.2);
  background: linear-gradient(145deg, rgb(8 47 73 / 0.5), rgb(2 6 23 / 0.45));
  padding: 8px 10px 8px;
}

.honeypot-feed__title {
  display: inline-flex;
  margin-bottom: 5px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 10px;
  letter-spacing: 0.5px;
  color: rgb(165 243 252 / 0.95);
  border: 1px solid rgb(34 211 238 / 0.32);
  background: rgb(8 47 73 / 0.68);
}

.honeypot-feed__list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 176px;
  overflow-y: auto;
  padding-right: 4px;
}

.honeypot-feed__list::-webkit-scrollbar {
  width: 6px;
}

.honeypot-feed__list::-webkit-scrollbar-track {
  background: rgb(15 23 42 / 0.45);
  border-radius: 999px;
}

.honeypot-feed__list::-webkit-scrollbar-thumb {
  background: rgb(34 211 238 / 0.45);
  border-radius: 999px;
}

.honeypot-feed__item {
  display: grid;
  grid-template-columns: 54px 1.2fr 1fr 1fr 78px;
  align-items: center;
  gap: 10px;
  font-size: 11px;
  border-radius: 10px;
  border: 1px solid rgb(34 211 238 / 0.2);
  background: linear-gradient(135deg, rgb(4 47 74 / 0.84), rgb(2 6 23 / 0.8));
  color: rgb(224 242 254);
  padding: 7px 10px;
  box-shadow: 0 10px 28px rgb(2 6 23 / 0.45);
  /* 逐条弹入动画 */
  animation: honeypot-item-pop 0.4s ease both;
}

@keyframes honeypot-item-pop {
  from {
    opacity: 0;
    transform: translateY(-12px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.honeypot-feed__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60px;
  font-size: 11px;
  color: rgb(125 211 252 / 0.5);
  letter-spacing: 1px;
}

.honeypot-feed__level {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  border-radius: 999px;
  padding: 2px 6px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.honeypot-feed__level.level-critical {
  color: rgb(254 226 226);
  background: rgb(220 38 38 / 0.65);
}

.honeypot-feed__level.level-high {
  color: rgb(255 237 213);
  background: rgb(234 88 12 / 0.62);
}

.honeypot-feed__level.level-medium {
  color: rgb(254 249 195);
  background: rgb(202 138 4 / 0.62);
}

.honeypot-feed__level.level-low {
  color: rgb(220 252 231);
  background: rgb(22 163 74 / 0.58);
}

.honeypot-feed__ip,
.honeypot-feed__service,
.honeypot-feed__location,
.honeypot-feed__time {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.honeypot-feed__service {
  color: rgb(165 243 252 / 0.95);
}

.honeypot-feed__time {
  text-align: right;
  color: rgb(125 211 252 / 0.88);
}

.honeypot-list-enter-active,
.honeypot-list-leave-active {
  transition: all 0.38s ease;
}

.honeypot-list-move {
  transition: transform 0.42s ease;
}

.honeypot-list-enter-from {
  opacity: 0;
  transform: translateY(-14px) scale(0.98);
}

.honeypot-list-enter-to {
  opacity: 1;
  transform: translateY(0) scale(1);
}

.honeypot-list-leave-from {
  opacity: 1;
}

.honeypot-list-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(0.98);
}

@media (max-width: 1024px) {
  .honeypot-feed__item {
    grid-template-columns: 50px 1fr 1fr;
    row-gap: 5px;
  }

  .honeypot-feed__location,
  .honeypot-feed__time {
    display: none;
  }
}

.view-fade-enter-active,
.view-fade-leave-active {
  transition: opacity 0.35s ease, transform 0.35s ease;
}
.view-fade-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.view-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
