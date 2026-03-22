<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { api } from '@/api/index'
import DashboardMetricSidebar from '@/components/dashboard/DashboardMetricSidebar.vue'
import DashboardAiSidebar from '@/components/dashboard/DashboardAiSidebar.vue'
import DashboardCenterPanel from '@/components/dashboard/DashboardCenterPanel.vue'

interface TopMetrics {
  hfish_total: number
  hfish_high: number
  nmap_online: number
  ai_decisions: number
  blocked_ips: number
}

interface TopologyNode {
  id: string
  label: string
  type: string
  status: string
}

interface TopologyLink {
  source: string
  target: string
  type: string
}

interface ScreenPayload {
  top_metrics: TopMetrics
  chain_status: Record<string, boolean>
  trends: { labels: string[]; counts: number[] }
  threat_distribution: { levels: string[]; counts: number[] }
  hot_services: Array<{ name: string; count: number }>
  recent_attacks: Array<{ attack_ip: string; ip_location?: string; service_name?: string; threat_level?: string; create_time_str?: string }>
  defense_events: Array<{ attack_ip: string; ip_location?: string; attack_count: number; latest_time?: string; ai_status?: string; ai_decision?: string }>
  topology: {
    nodes: TopologyNode[]
    links: TopologyLink[]
  }
}

const loading = ref(true)
const loadError = ref('')

const payload = ref<ScreenPayload>({
  top_metrics: { hfish_total: 0, hfish_high: 0, nmap_online: 0, ai_decisions: 0, blocked_ips: 0 },
  chain_status: {},
  trends: { labels: [], counts: [] },
  threat_distribution: { levels: [], counts: [] },
  hot_services: [],
  recent_attacks: [],
  defense_events: [],
  topology: { nodes: [], links: [] },
})

async function loadScreen() {
  if (!payload.value.recent_attacks.length) {
    loading.value = true
  }
  loadError.value = ''
  try {
    const res = await api.get<any>('/api/v1/overview/screen')
    payload.value = (res?.data ?? res) as ScreenPayload
  } catch (e: any) {
    loadError.value = e?.message || '大屏数据加载失败'
  } finally {
    loading.value = false
  }
}

let timer: ReturnType<typeof setInterval>
onMounted(() => {
  loadScreen()
  timer = setInterval(loadScreen, 15_000)
})
onUnmounted(() => {
  clearInterval(timer)
})
</script>

<template>
  <div class="dashboard-screen h-full w-full overflow-hidden p-2 md:p-3">
    <div class="dashboard-screen__grid grid h-full grid-cols-1 gap-3 xl:grid-cols-[280px_minmax(0,1fr)_330px]">
      <!-- 左栏：态势摘要 -->
      <DashboardMetricSidebar :payload="payload" :loading="loading" />

      <!-- 中栏：主显示区域 -->
      <DashboardCenterPanel :payload="payload" :loading="loading" :load-error="loadError" />

      <!-- 右栏：AI 指挥侧边栏 -->
      <DashboardAiSidebar />
    </div>
  </div>
</template>

<style scoped>
.dashboard-screen :deep(.tech-card-dashboard-clear) {
  background: linear-gradient(180deg, hsl(var(--card) / 0.92), hsl(var(--card) / 0.84));
  backdrop-filter: blur(10px);
  box-shadow: 0 12px 28px hsl(var(--primary) / 0.08);
}

.dashboard-screen :deep(.tech-card-dashboard-clear)::before {
  opacity: 0.16;
}

.dashboard-screen :deep(.dashboard-kpi-shell),
.dashboard-screen :deep(.world-map-shell),
.dashboard-screen :deep(.topology-stage-board),
.dashboard-screen :deep(.device-panel-card),
.dashboard-screen :deep(.topology-detail-card),
.dashboard-screen :deep(.device-detail-strip) {
  background: linear-gradient(180deg, hsl(var(--card) / 0.96), hsl(var(--secondary) / 0.38));
  backdrop-filter: blur(10px);
  box-shadow: 0 14px 32px hsl(var(--primary) / 0.08);
}

.dashboard-screen :deep(.dashboard-kpi-shell::before) {
  opacity: 0.12;
}

.dashboard-screen :deep(.kpi-chip),
.dashboard-screen :deep(.topology-stage-board__legend),
.dashboard-screen :deep(.world-map-shell__status),
.dashboard-screen :deep(.device-panel-card__eyebrow),
.dashboard-screen :deep(.device-detail-strip__eyebrow),
.dashboard-screen :deep(.topology-stage-board__grid),
.dashboard-screen :deep(.world-map-shell__loading) {
  background: hsl(var(--secondary) / 0.4);
  backdrop-filter: blur(8px);
  box-shadow: none;
}

.dashboard-screen :deep(.map-card),
.dashboard-screen :deep(.view-main-card) {
  border-color: hsl(var(--border) / 0.5);
}

.dashboard-screen {
  position: relative;
}

.dashboard-screen::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 20px;
  background:
    radial-gradient(circle at top left, hsl(var(--primary) / 0.12), transparent 30%),
    radial-gradient(circle at top right, hsl(var(--primary) / 0.08), transparent 28%),
    linear-gradient(180deg, hsl(var(--background) / 0.88), hsl(var(--secondary) / 0.22));
  pointer-events: none;
}

.dashboard-screen__grid {
  position: relative;
  z-index: 1;
}

.dashboard-screen__grid > * {
  min-height: 0;
}

@media (max-width: 1279px) {
  .dashboard-screen {
    height: auto;
    min-height: 100%;
    overflow: hidden;
  }

  .dashboard-screen__grid {
    height: auto;
    align-content: start;
  }
}
</style>
