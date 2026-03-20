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
  <div class="h-full w-full overflow-hidden p-4 md:p-6">
    <div class="grid h-full grid-cols-1 gap-4 xl:grid-cols-[300px_minmax(0,1fr)_360px]">
      <!-- 左栏：态势摘要 -->
      <DashboardMetricSidebar :payload="payload" :loading="loading" />

      <!-- 中栏：主显示区域 -->
      <DashboardCenterPanel :payload="payload" :loading="loading" :load-error="loadError" />

      <!-- 右栏：AI 指挥侧边栏 -->
      <DashboardAiSidebar />
    </div>
  </div>
</template>
