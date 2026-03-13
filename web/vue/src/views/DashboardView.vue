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
const metrics   = ref<Metrics>({ hfish_total:0, hfish_high:0, nmap_online:0, vuln_open:0, ai_decisions:0, blocked_ips:0 })
const chainStatus = ref<Record<string, boolean>>({})
const trends    = ref<{ labels: string[], counts: number[] }>({ labels: [], counts: [] })
const hfishStats = ref<{ levels: string[], counts: number[], colors: string[], services: Record<string,number> }>({ levels:[], counts:[], colors:[], services:{} })
const loading   = ref(true)

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

async function load() {
  loading.value = true
  try {
    const [m, cs, st] = await Promise.all([
      api.get<any>('/api/v1/overview/metrics'),
      api.get<any>('/api/v1/overview/chain-status'),
      api.get<any>('/api/v1/defense/hfish/stats'),
    ])
    const d = m.data ?? m
    metrics.value = {
      hfish_total:  d.hfish_total   ?? d.total_attacks ?? 0,
      hfish_high:   d.hfish_high    ?? 0,
      nmap_online:  d.nmap_online   ?? 0,
      vuln_open:    d.vuln_open     ?? 0,
      ai_decisions: d.ai_decisions  ?? 0,
      blocked_ips:  d.blocked_ips   ?? 0,
    }
    chainStatus.value = cs.data ?? cs

    const sd = st.data ?? st
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
    trendChartData.labels = trends.value.labels
    trendChartData.datasets[0].data = trends.value.counts
  } catch(e) { console.error(e) }
  loading.value = false
}

let refreshTimer: ReturnType<typeof setInterval>
onMounted(() => { load(); refreshTimer = setInterval(load, 30_000) })
onUnmounted(() => clearInterval(refreshTimer))
</script>

<template>
  <v-container fluid class="pa-6">
    <!-- Stat Cards -->
    <v-row class="mb-4">
      <v-col v-for="s in statCards" :key="s.key" cols="12" sm="6" md="4" lg="2">
        <v-card :style="`border-left:4px solid ${s.color}`" class="pa-4" height="100">
          <div class="d-flex justify-space-between align-center">
            <div>
              <div class="text-caption text-medium-emphasis">{{ s.label }}</div>
              <div class="text-h4 font-weight-bold mt-1" :style="`color:${s.color}`">
                <v-progress-circular v-if="loading" indeterminate size="24" width="2" :color="s.color" />
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
            <v-skeleton-loader v-else type="image" height="200" />
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
            <v-skeleton-loader v-else type="image" height="180" />
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Chain status -->
    <v-row>
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title class="text-subtitle-1">防御链路状态</v-card-title>
          <v-card-text>
            <v-row dense>
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
            <v-skeleton-loader v-else type="image" height="130" />
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>
