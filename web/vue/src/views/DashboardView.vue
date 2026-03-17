<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { api } from '@/api/index'
import { Line, Doughnut, Bar } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, ArcElement, BarElement, Title, Tooltip, Legend, Filler
} from 'chart.js'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { 
  History, 
  ShieldAlert, 
  Server, 
  Bug, 
  Bot, 
  Ban, 
  CheckCircle2, 
  Circle,
  Activity,
  AlertTriangle,
  Flame
} from 'lucide-vue-next'

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
  { label: '攻击日志总数',  key: 'hfish_total',   color: 'text-blue-400',   bg: 'bg-blue-400/10', border: 'border-blue-400/20', icon: History },
  { label: '高危攻击',      key: 'hfish_high',    color: 'text-red-400',    bg: 'bg-red-400/10',  border: 'border-red-400/20',  icon: ShieldAlert },
  { label: '在线主机',      key: 'nmap_online',   color: 'text-emerald-400', bg: 'bg-emerald-400/10', border: 'border-emerald-400/20', icon: Server },
  { label: '待修漏洞',      key: 'vuln_open',     color: 'text-amber-400',  bg: 'bg-amber-400/10', border: 'border-amber-400/20', icon: Bug },
  { label: 'AI 封禁决策',   key: 'ai_decisions',  color: 'text-violet-400', bg: 'bg-violet-400/10', border: 'border-violet-400/20', icon: Bot },
  { label: '已封禁 IP',     key: 'blocked_ips',   color: 'text-slate-400',   bg: 'bg-slate-400/10',   border: 'border-slate-400/20',   icon: Ban },
]
const chainItems = [
  { label: 'HFish 同步',   key: 'hfish_sync'   },
  { label: 'Nmap 扫描',    key: 'nmap_scan'    },
  { label: 'AI 分析',      key: 'ai_analysis'  },
  { label: 'ACL 封禁',     key: 'acl_auto_ban' },
]

const trendOptions = {
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: { 
    x: { grid: { color: 'rgba(255,255,255,.05)' }, ticks: { color: '#94a3b8' } }, 
    y: { grid: { color: 'rgba(255,255,255,.05)' }, ticks: { color: '#94a3b8' } } 
  }
}

function unwrap<T>(payload: any): T {
  return (payload?.data ?? payload) as T
}

async function load() {
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
    loadError.value = '核心指标加载失败，请稍后刷新重试'
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
  } else {
    trends.value = { labels: [], counts: [] }
    hfishStats.value = { levels: [], counts: [], colors: [], services: {} }
    partialError.value.push('攻击统计图表加载失败')
  }

  loading.value = false
}

let refreshTimer: ReturnType<typeof setInterval>
onMounted(() => { load(); refreshTimer = setInterval(load, 30_000) })
onUnmounted(() => clearInterval(refreshTimer))
</script>

<template>
  <div class="p-6 space-y-6">
    <!-- Notifications -->
    <div v-if="loadError || partialError.length" class="space-y-3">
      <Alert v-if="loadError" variant="destructive" class="bg-red-500/10 border-red-500/20">
        <AlertTriangle class="h-4 w-4" />
        <AlertDescription>{{ loadError }}</AlertDescription>
      </Alert>
      <Alert v-if="partialError.length" variant="default" class="bg-amber-500/10 border-amber-500/20 text-amber-500">
        <ShieldAlert class="h-4 w-4" />
        <AlertDescription>{{ partialError.join('；') }}</AlertDescription>
      </Alert>
    </div>

    <!-- Stat Cards -->
    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      <Card 
        v-for="s in statCards" 
        :key="s.key" 
        class="bg-card/40 border relative overflow-hidden group hover:border-border transition-all"
      >
        <div class="absolute top-0 right-0 p-3 opacity-20 group-hover:opacity-40 transition-opacity">
          <Bug v-if="s.icon === Bug" :size="48" :stroke-width="1.5" :class="s.color" />
          <ShieldAlert v-else-if="s.icon === ShieldAlert" :size="48" :stroke-width="1.5" :class="s.color" />
          <History v-else-if="s.icon === History" :size="48" :stroke-width="1.5" :class="s.color" />
          <Server v-else-if="s.icon === Server" :size="48" :stroke-width="1.5" :class="s.color" />
          <Bot v-else-if="s.icon === Bot" :size="48" :stroke-width="1.5" :class="s.color" />
          <Ban v-else-if="s.icon === Ban" :size="48" :stroke-width="1.5" :class="s.color" />
          <Activity v-else :size="48" :stroke-width="1.5" :class="s.color" />
        </div>
        <CardContent class="p-5 relative z-10">
          <p class="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">{{ s.label }}</p>
          <div class="flex items-center">
            <h2 v-if="!loading" class="text-3xl font-bold tracking-tight" :class="s.color">
              {{ (metrics as any)[s.key] }}
            </h2>
            <Skeleton v-else class="h-8 w-20 bg-muted" />
          </div>
          <div class="mt-2 h-1 w-12 rounded-full" :class="s.bg"></div>
        </CardContent>
      </Card>
    </div>

    <!-- Charts Row -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <!-- Line Chart -->
      <Card class="lg:col-span-8 border border-border/50">
        <CardHeader class="pb-2">
          <CardTitle class="text-[15px] font-semibold flex items-center gap-2">
            <History class="h-4 w-4 text-primary" />
            攻击趋势（近 7 天）
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div class="h-[240px] w-full">
            <Line 
              v-if="trends.labels.length" 
              :data="{ 
                labels: trends.labels, 
                datasets: [{ 
                  label: '攻击次数', 
                  data: trends.counts, 
                  borderColor: '#00E5FF', 
                  backgroundColor: 'rgba(0,229,255,.08)', 
                  fill: true, 
                  tension: 0.4,
                  pointRadius: 4,
                  pointBackgroundColor: '#00E5FF',
                  borderWidth: 2
                }] 
              }" 
              :options="trendOptions" 
            />
            <Skeleton v-else-if="loading" class="h-full w-full rounded-lg" />
            <div v-else class="h-full flex items-center justify-center text-muted-foreground text-sm italic">
              {{ partialError.includes('攻击统计图表加载失败') ? '数据加载异常' : '暂无统计数据' }}
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- Doughnut Chart -->
      <Card class="lg:col-span-4 border border-border/50">
        <CardHeader class="pb-2">
          <CardTitle class="text-[15px] font-semibold flex items-center gap-2">
            <ShieldAlert class="h-4 w-4 text-primary" />
            威胁等级分布
          </CardTitle>
        </CardHeader>
        <CardContent class="flex items-center justify-center pt-2">
          <div class="h-[240px] w-full flex items-center justify-center">
            <Doughnut
              v-if="hfishStats.levels.length"
              :data="{ 
                labels: hfishStats.levels, 
                datasets: [{ 
                  data: hfishStats.counts, 
                  backgroundColor: hfishStats.colors,
                  borderWidth: 0,
                  hoverOffset: 8
                }] 
              }"
              :options="{ 
                responsive: true, 
                maintainAspectRatio: false,
                plugins: {
                  legend: {
                    position: 'bottom',
                    labels: { color: '#94a3b8', boxWidth: 10, padding: 20, font: { size: 10 } }
                  }
                }
              }"
            />
            <Skeleton v-else-if="loading" class="h-48 w-48 rounded-full" />
            <div v-else class="text-muted-foreground text-sm italic">
              暂无等级统计
            </div>
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- Defense Status & Popular Services -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <Card class="border-border/50">
        <CardHeader class="pb-2">
          <CardTitle class="text-[15px] font-semibold flex items-center gap-2">
            <Bot class="h-4 w-4 text-primary" />
            防御链路状态
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div v-if="Object.keys(chainStatus).length" class="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3 py-2">
            <div 
              v-for="ci in chainItems" 
              :key="ci.key" 
              class="flex items-center gap-3 p-2.5 rounded-lg border border-transparent transition-all"
              :class="[chainStatus[ci.key] ? 'bg-emerald-500/5 text-emerald-400 border-emerald-500/10' : 'bg-muted/10 text-slate-500 border-dashed border-border/50']"
            >
              <CheckCircle2 v-if="chainStatus[ci.key]" class="h-4 w-4 shrink-0" />
              <Circle v-else class="h-4 w-4 shrink-0" />
              <span class="text-sm font-medium">{{ ci.label }}</span>
            </div>
          </div>
          <div v-else-if="loading" class="space-y-3 py-2">
            <Skeleton v-for="i in 4" :key="i" class="h-10 w-full" />
          </div>
          <div v-else class="py-10 text-center text-muted-foreground text-sm italic">
            链路数据暂时不可用
          </div>
        </CardContent>
      </Card>

      <Card class="border-border/50">
        <CardHeader class="pb-2">
          <CardTitle class="text-[15px] font-semibold flex items-center gap-2">
            <Flame class="h-4 w-4 text-primary" />
            热门攻击服务
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div class="h-[160px] w-full overflow-hidden">
            <Bar
              v-if="Object.keys(hfishStats.services).length"
              :data="{
                labels: Object.keys(hfishStats.services).slice(0,6),
                datasets: [{ 
                  label: '攻击次数', 
                  data: Object.values(hfishStats.services).slice(0,6), 
                  backgroundColor: '#8B5CF6', 
                  borderRadius: 6 
                }]
              }"
              :options="{ 
                responsive: true, 
                maintainAspectRatio: false, 
                indexAxis: 'y', 
                plugins: { legend: { display: false } },
                scales: {
                  x: { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 10 } } },
                  y: { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 10 } } }
                }
              }"
            />
            <Skeleton v-else-if="loading" class="h-full w-full rounded-lg" />
            <div v-else class="h-full flex items-center justify-center text-muted-foreground text-sm italic">
              暂无服务统计数据
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>
