<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { api } from '@/api/index'
import { Line, Doughnut, Bar } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, ArcElement, BarElement, Title, Tooltip, Legend, Filler
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement,
  ArcElement, BarElement, Title, Tooltip, Legend, Filler)

interface Metrics {
  hfish_total: number; hfish_high: number; nmap_online: number;
  vuln_open: number; ai_decisions: number; blocked_ips: number
}
const EMPTY_METRICS: Metrics = {
  hfish_total: 0,
  hfish_high: 0,
  nmap_online: 0,
  vuln_open: 0,
  ai_decisions: 0,
  blocked_ips: 0,
}
const metrics = ref<Metrics>({ ...EMPTY_METRICS })
const chainStatus = ref<Record<string, boolean>>({})
const trends = ref<{ labels: string[], counts: number[] }>({ labels: [], counts: [] })
const hfishStats = ref<{ levels: string[], counts: number[], colors: string[], services: Record<string, number> }>({ levels: [], counts: [], colors: [], services: {} })
const loading = ref(true)
const loadError = ref('')
const partialError = ref<string[]>([])

const THREAT_COLORS: Record<string, string> = {
  '高危': '#EF4444', '中危': '#F59E0B', '低危': '#3B82F6', '信息': '#9CA3AF'
}
const statCards = [
  { label: '攻击日志总数',  key: 'hfish_total',   color: '#3B82F6', icon: 'mdi-history' },
  { label: '高危攻击',      key: 'hfish_high',    color: '#EF4444', icon: 'mdi-shield-alert-outline' },
  { label: '在线主机',      key: 'nmap_online',   color: '#10B981', icon: 'mdi-server-network' },
  { label: '待修漏洞',      key: 'vuln_open',     color: '#F59E0B', icon: 'mdi-bug-outline' },
  { label: 'AI 封禁决策',   key: 'ai_decisions',  color: '#8B5CF6', icon: 'mdi-robot-outline' },
  { label: '已封禁 IP',     key: 'blocked_ips',   color: '#F472B6', icon: 'mdi-cancel' },
]
const chainItems = [
  { label: 'HFish 同步',   key: 'hfish_sync'   },
  { label: 'Nmap 扫描',    key: 'nmap_scan'    },
  { label: 'AI 分析',      key: 'ai_analysis'  },
  { label: 'ACL 封禁',     key: 'acl_auto_ban' },
]

const trendChartData = {
  labels: trends.value.labels,
  datasets: [{
    label: '攻击次数',
    data: trends.value.counts,
    borderColor: '#00E5FF',
    backgroundColor: 'rgba(0,229,255,0.12)',
    fill: true,
    tension: 0.4
  }]
}
const trendOptions = {
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: { x: { grid: { color: 'rgba(255,255,255,.05)' } }, y: { grid: { color: 'rgba(255,255,255,.05)' } } }
}

function unwrap<T>(payload: any): T {
  // 兼容 api.ts 已解包和历史接口未解包两种返回。
  return (payload?.data ?? payload) as T
}

function resetCharts() {
  trends.value = { labels: [], counts: [] }
  hfishStats.value = { levels: [], counts: [], colors: [], services: {} }
  trendChartData.labels = []
  trendChartData.datasets[0].data = []
}

function syncTrendChart() {
  trendChartData.labels = trends.value.labels
  trendChartData.datasets[0].data = trends.value.counts
}

async function load() {
  // 仪表盘加载时并发拉取核心统计，减少首屏等待。
  loading.value = true
  loadError.value = ''
  partialError.value = []

  const [m, cs, st] = await Promise.allSettled([
    api.get<any>('/api/v1/overview/metrics'),
    api.get<any>('/api/v1/overview/chain-status'),
    api.get<any>('/api/v1/defense/hfish/stats'),
  ])

  if (m.status === 'fulfilled') {
    const d = unwrap<any>(m.value)
    metrics.value = {
      hfish_total: d.hfish_total ?? d.total_attacks ?? 0,
      hfish_high: d.hfish_high ?? 0,
      nmap_online: d.nmap_online ?? 0,
      vuln_open: d.vuln_open ?? 0,
      ai_decisions: d.ai_decisions ?? 0,
      blocked_ips: d.blocked_ips ?? 0,
    }
  } else {
    metrics.value = { ...EMPTY_METRICS }
    loadError.value = '核心指标加载失败，请稍后刷新重试。'
  }

  if (cs.status === 'fulfilled') {
    chainStatus.value = unwrap<Record<string, boolean>>(cs.value)
  } else {
    chainStatus.value = {}
    partialError.value.push('防御链路状态加载失败')
  }

  if (st.status === 'fulfilled') {
    const sd = unwrap<any>(st.value)
    const threat = sd.threat_stats ?? []
    hfishStats.value = {
      levels: threat.map((t: any) => t.level),
      counts: threat.map((t: any) => t.count),
      colors: threat.map((t: any) => THREAT_COLORS[t.level] ?? '#9E9E9E'),
      services: Object.fromEntries((sd.service_stats ?? []).map((s: any) => [s.name, s.count]))
    }
    const ts = sd.time_stats ?? []
    trends.value = {
      labels: ts.map((t: any) => t.date),
      counts: ts.map((t: any) => t.count)
    }
    syncTrendChart()
  } else {
    resetCharts()
    partialError.value.push('攻击统计图表加载失败')
  }

  if (!loadError.value && partialError.value.length === 3) {
    loadError.value = '首页数据暂时无法加载，请检查后端服务后重试。'
  }

  loading.value = false
}

let refreshTimer: ReturnType<typeof setInterval>
onMounted(() => { load(); refreshTimer = setInterval(load, 30_000) })
onUnmounted(() => clearInterval(refreshTimer))
</script>

<template>
  <v-container fluid class="pa-6">
    <v-alert
      v-if="loadError"
      type="error"
      variant="tonal"
      class="mb-4"
      density="comfortable"
      border="start"
    >
      {{ loadError }}
    </v-alert>

    <v-alert
      v-if="partialError.length"
      type="warning"
      variant="tonal"
      class="mb-4"
      density="comfortable"
      border="start"
    >
      {{ partialError.join('；') }}。
    </v-alert>

    <!-- Stat Cards -->
    <v-row class="mb-4">
      <v-col v-for="s in statCards" :key="s.key" cols="12" sm="6" md="4" lg="2">
        <v-card :style="`border-left:4px solid ${s.color}`" class="pa-4" height="100">
          <div class="d-flex justify-space-between align-center">
            <div>
              <div class="text-caption text-medium-emphasis">{{ s.label }}</div>
              <div class="text-h4 font-weight-bold mt-1" :style="`color:${s.color}`">
                <v-progress-circular v-if="loading" indeterminate size="24" width="2" :color="s.color" />
                <span v-else-if="loadError">--</span>
                <span v-else>{{ (metrics as any)[s.key] }}</span>
              </div>
            </div>
            <v-icon size="40" :color="s.color" style="opacity:.7">{{ s.icon }}</v-icon>
          </div>
        </v-card>
      </v-col>
    </v-row>

    <!-- Charts row -->
    <v-row class="mb-4">
      <v-col cols="12" md="8">
        <v-card height="280">
          <v-card-title class="text-subtitle-1">攻击趋势（近 7 天）</v-card-title>
          <v-card-text style="height:220px">
            <Line v-if="trends.labels.length" :data="{ labels: trends.labels, datasets: [{ label:'攻击次数', data: trends.counts, borderColor:'#00E5FF', backgroundColor:'rgba(0,229,255,.12)', fill:true, tension:.4 }] }" :options="trendOptions" />
            <v-skeleton-loader v-else-if="loading" type="image" height="200" />
            <div v-else class="d-flex align-center justify-center text-medium-emphasis h-100">
              {{ partialError.includes('攻击统计图表加载失败') ? '攻击趋势加载失败' : '暂无趋势数据' }}
            </div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="4">
        <v-card height="280">
          <v-card-title class="text-subtitle-1">威胁等级分布</v-card-title>
          <v-card-text style="height:220px; display:flex; align-items:center; justify-content:center">
            <Doughnut
              v-if="hfishStats.levels.length"
              :data="{ labels: hfishStats.levels, datasets: [{ data: hfishStats.counts, backgroundColor: hfishStats.colors }] }"
              :options="{ responsive:true, maintainAspectRatio:false }"
            />
            <v-skeleton-loader v-else-if="loading" type="image" height="180" />
            <div v-else class="text-medium-emphasis text-body-2">
              {{ partialError.includes('攻击统计图表加载失败') ? '威胁分布加载失败' : '暂无威胁分布数据' }}
            </div>
          </v-card-text>
        </v-card>
      </v-col>


    <!-- Chain status -->
    <v-row>
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title class="text-subtitle-1">防御链路状态</v-card-title>
          <v-card-text>
            <v-row v-if="Object.keys(chainStatus).length" dense>
              <v-col v-for="ci in chainItems" :key="ci.key" cols="6">
                <div class="d-flex align-center ga-2 py-2">
                  <v-icon
                    :color="chainStatus[ci.key] ? 'success' : 'grey'"
                    size="18"
                  >{{ chainStatus[ci.key] ? 'mdi-check-circle' : 'mdi-circle-outline' }}</v-icon>
                  <span class="text-body-2">{{ ci.label }}</span>
                </div>
              </v-col>
            </v-row>
            <div v-else-if="loading" class="py-6">
              <v-skeleton-loader type="list-item-two-line" />
            </div>
            <div v-else class="text-medium-emphasis text-body-2 py-4">
              {{ partialError.includes('防御链路状态加载失败') ? '防御链路状态加载失败' : '暂无链路状态数据' }}
            </div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title class="text-subtitle-1 d-flex align-center">
            热门攻击服务
          </v-card-title>
          <v-card-text style="height:150px">
            <Bar
              v-if="Object.keys(hfishStats.services).length"
              :data="{
                labels: Object.keys(hfishStats.services).slice(0,6),
                datasets: [{ label:'次数', data: Object.values(hfishStats.services).slice(0,6), backgroundColor:'#8B5CF6', borderRadius:4 }]
              }"
              :options="{ responsive:true, maintainAspectRatio:false, indexAxis:'y', plugins:{ legend:{ display:false } } }"
            />
            <v-skeleton-loader v-else-if="loading" type="image" height="130" />
            <div v-else class="d-flex align-center justify-center text-medium-emphasis h-100">
              {{ partialError.includes('攻击统计图表加载失败') ? '热门攻击服务加载失败' : '暂无热门攻击服务数据' }}
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>
