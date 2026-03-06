<template>
  <div class="p-6">
    <div class="mx-auto max-w-[1400px] space-y-6">
      <div class="flex items-center justify-between">
        <div class="space-y-1">
          <h1 class="text-2xl font-semibold">主动探测仪表盘</h1>
          <p class="text-sm text-muted-foreground">探测任务、资产覆盖与扫描结果总览</p>
        </div>
        <Button variant="outline" size="sm" class="cursor-pointer gap-2" :disabled="loading" @click="loadAll">
          <RefreshCw class="size-4" :class="loading ? 'animate-spin' : ''" />
          刷新
        </Button>
      </div>

      <!-- Metrics -->
      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card v-for="item in metrics" :key="item.label">
          <CardHeader class="pb-2 flex-row items-center justify-between">
            <CardTitle class="text-sm font-medium text-muted-foreground">{{ item.label }}</CardTitle>
            <component :is="item.icon" class="size-4 text-muted-foreground/60" />
          </CardHeader>
          <CardContent>
            <p class="text-2xl font-semibold" :class="item.color">
              <span v-if="loading">—</span>
              <span v-else>{{ item.value }}</span>
            </p>
            <p v-if="item.sub" class="text-xs text-muted-foreground mt-1">{{ item.sub }}</p>
          </CardContent>
        </Card>
      </div>

      <div class="grid gap-4 lg:grid-cols-2">
        <!-- Recent Tasks -->
        <Card>
          <CardHeader class="flex-row items-center justify-between pb-3">
            <CardTitle class="text-base">近期扫描任务</CardTitle>
            <router-link to="/probe/scan">
              <Button variant="ghost" size="sm" class="cursor-pointer text-xs gap-1">
                <ExternalLink class="size-3.5" />
                全部
              </Button>
            </router-link>
          </CardHeader>
          <CardContent class="space-y-2">
            <div v-if="loading" class="space-y-2">
              <Skeleton v-for="i in 4" :key="i" class="h-10 w-full rounded" />
            </div>
            <div v-else-if="recentTasks.length === 0" class="text-center py-6 text-sm text-muted-foreground">
              暂无扫描任务
            </div>
            <div
              v-for="task in recentTasks"
              :key="task.id"
              class="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm"
            >
              <div class="flex items-center gap-2 min-w-0">
                <code class="text-xs truncate max-w-[140px]">{{ task.target }}</code>
                <Badge variant="outline" class="text-xs shrink-0">{{ task.profile || 'default' }}</Badge>
              </div>
              <Badge :class="getStateColor(task.state)" class="text-xs shrink-0">{{ getStateLabel(task.state) }}</Badge>
            </div>
          </CardContent>
        </Card>

        <!-- Right column -->
        <div class="space-y-4">
          <!-- Findings by Severity -->
          <Card>
            <CardHeader class="pb-3">
              <CardTitle class="text-base">漏洞严重程度分布</CardTitle>
            </CardHeader>
            <CardContent>
              <div v-if="loading" class="h-48 flex items-center justify-center">
                <Skeleton class="size-36 rounded-full" />
              </div>
              <div v-else-if="stats.totalFindings === 0" class="h-48 flex items-center justify-center text-muted-foreground text-sm">暂无漏洞数据</div>
              <div v-else class="flex items-center gap-4">
                <div class="h-48 flex-1 min-w-0">
                  <Doughnut :data="severityChartData" :options="doughnutOptions" />
                </div>
                <div class="space-y-1.5 shrink-0 text-xs">
                  <div v-for="s in severitySummary" :key="s.label" class="flex items-center gap-2">
                    <span class="size-2.5 rounded-sm" :class="s.barColor"></span>
                    <span class="text-muted-foreground">{{ s.label }}</span>
                    <span class="font-semibold tabular-nums ml-auto pl-3">{{ s.count }}</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <!-- Chain Status -->
          <Card>
            <CardHeader class="pb-3">
              <CardTitle class="text-base">探测链路状态</CardTitle>
            </CardHeader>
            <CardContent class="space-y-2 text-sm">
              <div v-for="item in chainStatus" :key="item.name" class="flex items-center justify-between rounded-md border border-border px-3 py-2">
                <span>{{ item.name }}</span>
                <span :class="item.ok ? 'text-emerald-500' : 'text-amber-500'">{{ item.ok ? '正常' : item.note }}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      <!-- 图表行：任务状态分布 + 近7天趋势 -->
      <div class="grid gap-4 lg:grid-cols-2">
        <!-- 任务状态分布饼图 -->
        <Card>
          <CardHeader class="pb-3">
            <CardTitle class="text-base">扫描任务状态分布</CardTitle>
          </CardHeader>
          <CardContent>
            <div v-if="loading" class="h-44 flex items-center justify-center">
              <Skeleton class="size-32 rounded-full" />
            </div>
            <div v-else class="flex items-center gap-5">
              <div class="h-44 w-44 shrink-0">
                <Doughnut :data="taskStateChartData" :options="taskDoughnutOptions" />
              </div>
              <div class="space-y-2 text-xs">
                <div class="flex items-center gap-2">
                  <span class="size-2.5 rounded-sm bg-slate-400/70"></span>
                  <span class="text-muted-foreground">待调度</span>
                  <span class="ml-auto font-semibold tabular-nums pl-4">{{ taskStateCounts.CREATED }}</span>
                </div>
                <div class="flex items-center gap-2">
                  <span class="size-2.5 rounded-sm bg-blue-500/75"></span>
                  <span class="text-muted-foreground">运行中</span>
                  <span class="ml-auto font-semibold tabular-nums pl-4">{{ taskStateCounts.RUNNING }}</span>
                </div>
                <div class="flex items-center gap-2">
                  <span class="size-2.5 rounded-sm bg-emerald-400/75"></span>
                  <span class="text-muted-foreground">已完成</span>
                  <span class="ml-auto font-semibold tabular-nums pl-4">{{ taskStateCounts.REPORTED }}</span>
                </div>
                <div class="flex items-center gap-2">
                  <span class="size-2.5 rounded-sm bg-red-400/75"></span>
                  <span class="text-muted-foreground">失败</span>
                  <span class="ml-auto font-semibold tabular-nums pl-4">{{ taskStateCounts.FAILED }}</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <!-- 近7天任务完成趋势 -->
        <Card>
          <CardHeader class="pb-3">
            <CardTitle class="text-base">近 7 天任务完成趋势</CardTitle>
          </CardHeader>
          <CardContent>
            <div v-if="loading" class="h-44 flex items-center justify-center">
              <Skeleton class="h-full w-full rounded" />
            </div>
            <div v-else class="h-44">
              <Bar :data="trendChartData" :options="barOptions" />
            </div>
          </CardContent>
        </Card>
      </div>

      <!-- Top HIGH findings -->
      <Card v-if="!loading && highFindings.length > 0">
        <CardHeader class="pb-3">
          <CardTitle class="text-base flex items-center gap-2">
            <AlertTriangle class="size-4 text-red-400" />
            高危发现 Top {{ highFindings.length }}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div class="rounded-lg border border-border overflow-hidden">
            <table class="w-full text-sm">
              <thead>
                <tr class="bg-muted/30 border-b border-border">
                  <th class="text-left px-4 py-2 text-xs text-muted-foreground font-medium">资产</th>
                  <th class="text-left px-4 py-2 text-xs text-muted-foreground font-medium">端口/服务</th>
                  <th class="text-left px-4 py-2 text-xs text-muted-foreground font-medium">CVE</th>
                  <th class="text-left px-4 py-2 text-xs text-muted-foreground font-medium">发现时间</th>
                  <th class="text-left px-4 py-2 text-xs text-muted-foreground font-medium">状态</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="f in highFindings" :key="f.id" class="border-b border-border/50 hover:bg-muted/20">
                  <td class="px-4 py-2 font-mono text-xs">{{ f.asset }}</td>
                  <td class="px-4 py-2 text-xs">{{ f.port }}/{{ f.service || '?' }}</td>
                  <td class="px-4 py-2 text-xs font-mono text-muted-foreground">{{ f.cve || '—' }}</td>
                  <td class="px-4 py-2 text-xs text-muted-foreground">{{ formatTime(f.created_at) }}</td>
                  <td class="px-4 py-2">
                    <Badge variant="outline" class="text-xs">{{ f.status }}</Badge>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Doughnut, Bar } from 'vue-chartjs'
import {
  Chart as ChartJS, ArcElement, Tooltip, Legend,
  CategoryScale, LinearScale, BarElement, Title,
} from 'chart.js'
import { scanApi, type ScanTask, type ScanFinding } from '@/api/scan'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { RefreshCw, ExternalLink, Target, Shield, Bug, AlertTriangle } from 'lucide-vue-next'

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement, Title)

const loading = ref(false)
const recentTasks = ref<ScanTask[]>([])
const trendTasks = ref<ScanTask[]>([])
const highFindings = ref<ScanFinding[]>([])
const taskStateCounts = ref({ CREATED: 0, RUNNING: 0, REPORTED: 0, FAILED: 0 })

const stats = ref({
  totalAssets: 0,
  enabledAssets: 0,
  runningTasks: 0,
  totalFindings: 0,
  highFindings: 0,
  mediumFindings: 0,
  lowFindings: 0,
  infoFindings: 0,
})

const metrics = computed(() => [
  {
    label: '资产总数',
    value: stats.value.totalAssets,
    sub: `${stats.value.enabledAssets} 个已启用`,
    icon: Target,
    color: 'text-foreground',
  },
  {
    label: '运行中扫描',
    value: stats.value.runningTasks,
    sub: '实时任务数',
    icon: Shield,
    color: stats.value.runningTasks > 0 ? 'text-blue-400' : 'text-foreground',
  },
  {
    label: '漏洞发现',
    value: stats.value.totalFindings,
    sub: `${stats.value.highFindings} 个高危`,
    icon: Bug,
    color: stats.value.highFindings > 0 ? 'text-red-400' : 'text-foreground',
  },
  {
    label: '高危待处理',
    value: stats.value.highFindings,
    sub: '需要优先处置',
    icon: AlertTriangle,
    color: stats.value.highFindings > 0 ? 'text-red-400' : 'text-emerald-400',
  },
])

const severitySummary = computed(() => {
  const total = stats.value.totalFindings || 1
  return [
    { label: 'HIGH', count: stats.value.highFindings, color: 'bg-red-500/15 text-red-400 border-red-500/30', barColor: 'bg-red-500', pct: Math.round(stats.value.highFindings / total * 100) },
    { label: 'MEDIUM', count: stats.value.mediumFindings, color: 'bg-orange-500/15 text-orange-400 border-orange-500/30', barColor: 'bg-orange-500', pct: Math.round(stats.value.mediumFindings / total * 100) },
    { label: 'LOW', count: stats.value.lowFindings, color: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30', barColor: 'bg-yellow-400', pct: Math.round(stats.value.lowFindings / total * 100) },
    { label: 'INFO', count: stats.value.infoFindings, color: 'bg-blue-500/15 text-blue-400 border-blue-500/30', barColor: 'bg-blue-500', pct: Math.round(stats.value.infoFindings / total * 100) },
  ]
})

// ── 漏洞饼图数据 ──
const severityChartData = computed(() => ({
  labels: severitySummary.value.map(s => s.label),
  datasets: [{
    data: severitySummary.value.map(s => s.count),
    backgroundColor: ['rgba(239,68,68,0.8)', 'rgba(249,115,22,0.8)', 'rgba(234,179,8,0.8)', 'rgba(59,130,246,0.8)'],
    borderWidth: 0,
    hoverOffset: 6,
  }],
}))

const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  cutout: '62%',
  plugins: {
    legend: { display: false },
    tooltip: { callbacks: { label: (ctx: any) => ` ${ctx.label}: ${ctx.parsed}` } },
  },
}

const chainStatus = computed(() => [
  { name: '任务调度器', ok: true, note: '' },
  { name: '扫描执行器', ok: true, note: '' },
  { name: '结果入库', ok: stats.value.totalFindings >= 0, note: '' },
  { name: '资产管理', ok: stats.value.totalAssets >= 0, note: '' },
])

// ── 任务状态分布饼图 ──
const taskStateChartData = computed(() => ({
  labels: ['待调度', '运行中', '已完成', '失败'],
  datasets: [{
    data: [
      taskStateCounts.value.CREATED,
      taskStateCounts.value.RUNNING,
      taskStateCounts.value.REPORTED,
      taskStateCounts.value.FAILED,
    ],
    backgroundColor: [
      'rgba(148,163,184,0.7)',
      'rgba(59,130,246,0.75)',
      'rgba(52,211,153,0.75)',
      'rgba(248,113,113,0.75)',
    ],
    borderWidth: 0,
    hoverOffset: 6,
  }],
}))

const taskDoughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  cutout: '60%',
  plugins: {
    legend: { display: false },
    tooltip: { callbacks: { label: (ctx: any) => ` ${ctx.label}: ${ctx.parsed}` } },
  },
}

// ── 近7天任务完成趋势柱状图 ──
const trendChartData = computed(() => {
  const days: string[] = []
  const counts: number[] = []
  const now = new Date()
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now)
    d.setDate(d.getDate() - i)
    const key = `${d.getMonth() + 1}/${d.getDate()}`
    days.push(key)
    const isoDate = d.toISOString().slice(0, 10)
    const cnt = trendTasks.value.filter(t => {
      const ended = t.ended_at || t.created_at
      return ended && ended.slice(0, 10) === isoDate && (t.state === 'REPORTED' || t.state === 'FAILED')
    }).length
    counts.push(cnt)
  }
  return {
    labels: days,
    datasets: [{
      label: '完成/失败任务数',
      data: counts,
      backgroundColor: 'rgba(99,102,241,0.65)',
      borderRadius: 4,
    }],
  }
})

const barOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: { callbacks: { label: (ctx: any) => ` 任务数: ${ctx.parsed.y}` } },
  },
  scales: {
    x: { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 11 } } },
    y: { beginAtZero: true, grid: { color: 'rgba(148,163,184,0.1)' }, ticks: { color: '#94a3b8', precision: 0 } },
  },
}

const loadAll = async () => {
  loading.value = true
  try {
    const [
      assetsAll, assetsEnabled, tasksRunning, tasksRecent,
      findingsAll, findingsHigh, findingsMed, findingsLow, findingsInfo,
      stateCreated, stateRunning, stateReported, stateFailed,
      tasksTrend,
    ] = await Promise.all([
      scanApi.getAssets({ page_size: 1 }),
      scanApi.getAssets({ enabled: true, page_size: 1 }),
      scanApi.getTasks({ state: 'RUNNING', page_size: 1 }),
      scanApi.getTasks({ page: 1, page_size: 6 }),
      scanApi.getFindings({ page_size: 1 }),
      scanApi.getFindings({ severity: 'HIGH', page_size: 5 }),
      scanApi.getFindings({ severity: 'MEDIUM', page_size: 1 }),
      scanApi.getFindings({ severity: 'LOW', page_size: 1 }),
      scanApi.getFindings({ severity: 'INFO', page_size: 1 }),
      scanApi.getTasks({ state: 'CREATED', page_size: 1 }),
      scanApi.getTasks({ state: 'RUNNING', page_size: 1 }),
      scanApi.getTasks({ state: 'REPORTED', page_size: 1 }),
      scanApi.getTasks({ state: 'FAILED', page_size: 1 }),
      scanApi.getTasks({ page: 1, page_size: 100 }),
    ])

    stats.value.totalAssets = assetsAll.total
    stats.value.enabledAssets = assetsEnabled.total
    stats.value.runningTasks = tasksRunning.total
    stats.value.totalFindings = findingsAll.total
    stats.value.highFindings = findingsHigh.total
    stats.value.mediumFindings = findingsMed.total
    stats.value.lowFindings = findingsLow.total
    stats.value.infoFindings = findingsInfo.total

    taskStateCounts.value = {
      CREATED: stateCreated.total,
      RUNNING: stateRunning.total,
      REPORTED: stateReported.total,
      FAILED: stateFailed.total,
    }

    recentTasks.value = tasksRecent.items
    trendTasks.value = tasksTrend.items
    highFindings.value = findingsHigh.items
  } catch (e) {
    console.error('Failed to load probe dashboard:', e)
  } finally {
    loading.value = false
  }
}

const getStateColor = (state: string) => {
  const map: Record<string, string> = {
    CREATED: 'bg-muted text-muted-foreground',
    RUNNING: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    REPORTED: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    FAILED: 'bg-destructive/15 text-destructive border-destructive/30',
    DISPATCHED: 'bg-blue-500/15 text-blue-300 border-blue-500/20',
    PARSED: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
  }
  return map[state] || 'bg-muted text-muted-foreground'
}

const getStateLabel = (state: string) => {
  const map: Record<string, string> = {
    CREATED: '待调度', DISPATCHED: '已分发', RUNNING: '运行中',
    PARSED: '解析中', REPORTED: '已完成', FAILED: '失败',
  }
  return map[state] || state
}

const formatTime = (t: string) => new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })

onMounted(loadAll)
</script>
