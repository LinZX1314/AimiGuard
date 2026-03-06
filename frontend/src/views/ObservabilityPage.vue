<template>
  <div class="space-y-6">
    <!-- 页头 -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold tracking-tight">系统可观测性</h1>
        <p class="text-sm text-muted-foreground mt-0.5">监控运行指标、告警阈值与系统健康状态</p>
      </div>
      <div class="flex items-center gap-2">
        <Badge v-if="alertSummary.has_alerts" class="bg-destructive/15 text-destructive border-destructive/30 text-xs">
          {{ alertSummary.alert_count }} 项告警
        </Badge>
        <Badge v-else class="bg-emerald-500/15 text-emerald-400 border-emerald-500/30 text-xs">正常</Badge>
        <Button size="sm" variant="outline" class="cursor-pointer text-xs gap-1" :disabled="loading" @click="refresh">
          <RefreshCw class="size-3" :class="loading ? 'animate-spin' : ''" />
          刷新
        </Button>
      </div>
    </div>

    <!-- 运行概览 -->
    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card v-for="s in statCards" :key="s.label">
        <CardContent class="pt-4 pb-3">
          <div class="flex items-center justify-between mb-1">
            <span class="text-xs text-muted-foreground">{{ s.label }}</span>
            <component :is="s.icon" class="size-4 text-muted-foreground" />
          </div>
          <div class="text-xl font-bold">{{ s.value }}</div>
          <p v-if="s.sub" class="text-[10px] text-muted-foreground mt-0.5">{{ s.sub }}</p>
        </CardContent>
      </Card>
    </div>

    <!-- 告警 -->
    <Card v-if="alertSummary.alerts && alertSummary.alerts.length > 0">
      <CardHeader class="pb-2">
        <CardTitle class="text-base flex items-center gap-2">
          <AlertTriangle class="size-4 text-destructive" />
          活跃告警
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div class="space-y-2">
          <div
            v-for="(a, i) in alertSummary.alerts"
            :key="i"
            class="flex items-center justify-between rounded-lg border p-3"
            :class="a.severity === 'HIGH' ? 'border-destructive/40 bg-destructive/5' : 'border-amber-500/40 bg-amber-500/5'"
          >
            <div>
              <p class="text-sm font-medium">{{ alertLabels[a.metric] || a.metric }}</p>
              <p class="text-xs text-muted-foreground">当前值 {{ a.value }}{{ a.metric.includes('rate') ? '%' : 'ms' }}，阈值 {{ a.threshold }}{{ a.metric.includes('rate') ? '%' : 'ms' }}</p>
            </div>
            <Badge :class="a.severity === 'HIGH' ? 'bg-destructive/15 text-destructive border-destructive/30' : 'bg-amber-500/15 text-amber-400 border-amber-500/30'" class="text-[10px]">
              {{ a.severity }}
            </Badge>
          </div>
        </div>
      </CardContent>
    </Card>

    <div class="grid gap-4 lg:grid-cols-2">
      <!-- 延迟统计 -->
      <Card>
        <CardHeader class="pb-2">
          <CardTitle class="text-base flex items-center gap-2">
            <Activity class="size-4 text-primary" /> 延迟统计（ms）
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div v-if="loading" class="space-y-2">
            <Skeleton v-for="i in 4" :key="i" class="h-8 w-full rounded" />
          </div>
          <table v-else class="w-full text-sm">
            <thead>
              <tr class="border-b border-border bg-muted/30">
                <th class="px-3 py-2 text-left text-xs font-medium text-muted-foreground">指标</th>
                <th class="px-3 py-2 text-right text-xs font-medium text-muted-foreground">次数</th>
                <th class="px-3 py-2 text-right text-xs font-medium text-muted-foreground">平均</th>
                <th class="px-3 py-2 text-right text-xs font-medium text-muted-foreground">P50</th>
                <th class="px-3 py-2 text-right text-xs font-medium text-muted-foreground">P95</th>
                <th class="px-3 py-2 text-right text-xs font-medium text-muted-foreground">最大</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(v, k) in metricsData.latencies" :key="k" class="border-b border-border/50">
                <td class="px-3 py-2 text-xs font-mono">{{ latencyLabels[k as string] || k }}</td>
                <td class="px-3 py-2 text-xs text-right">{{ v.count }}</td>
                <td class="px-3 py-2 text-xs text-right">{{ v.avg_ms }}</td>
                <td class="px-3 py-2 text-xs text-right">{{ v.p50_ms }}</td>
                <td class="px-3 py-2 text-xs text-right font-medium" :class="v.p95_ms > 2000 ? 'text-destructive' : ''">{{ v.p95_ms }}</td>
                <td class="px-3 py-2 text-xs text-right">{{ v.max_ms }}</td>
              </tr>
            </tbody>
          </table>
        </CardContent>
      </Card>

      <!-- 告警阈值配置 -->
      <Card>
        <CardHeader class="pb-2">
          <CardTitle class="text-base flex items-center gap-2">
            <Settings class="size-4 text-primary" /> 告警阈值配置
          </CardTitle>
        </CardHeader>
        <CardContent class="space-y-3">
          <div v-if="loading" class="space-y-2">
            <Skeleton v-for="i in 4" :key="i" class="h-8 w-full rounded" />
          </div>
          <template v-else>
            <div v-for="(val, key) in thresholds" :key="key" class="flex items-center gap-3">
              <label class="text-xs text-muted-foreground min-w-[140px]">{{ thresholdLabels[key as string] || key }}</label>
              <input
                type="number"
                :value="val"
                @change="(e: Event) => pendingThresholds[key as string] = parseFloat((e.target as HTMLInputElement).value)"
                class="h-7 w-24 rounded-md border border-input bg-background px-2 text-xs text-right focus:outline-none focus:ring-1 focus:ring-ring"
              />
              <span class="text-[10px] text-muted-foreground">{{ (key as string).includes('pct') ? '%' : 'ms' }}</span>
            </div>
          </template>
          <div class="pt-2 flex items-center gap-2">
            <Button size="sm" class="cursor-pointer text-xs" :disabled="Object.keys(pendingThresholds).length === 0 || savingThresholds" @click="saveThresholds">
              {{ savingThresholds ? '保存中…' : '保存阈值' }}
            </Button>
            <span v-if="thresholdMsg" class="text-xs" :class="thresholdMsgOk ? 'text-emerald-400' : 'text-destructive'">{{ thresholdMsg }}</span>
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- 数据库指标 -->
    <Card>
      <CardHeader class="pb-2">
        <CardTitle class="text-base flex items-center gap-2">
          <Database class="size-4 text-primary" /> 数据库指标
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div v-if="loading" class="space-y-2">
          <Skeleton class="h-8 w-full rounded" />
        </div>
        <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <div v-for="d in dbCards" :key="d.label" class="rounded-lg border border-border p-3">
            <p class="text-xs text-muted-foreground">{{ d.label }}</p>
            <p class="text-lg font-bold" :class="d.warn ? 'text-destructive' : ''">{{ d.value }}</p>
          </div>
        </div>
      </CardContent>
    </Card>

    <!-- 计数器 -->
    <Card>
      <CardHeader class="pb-2">
        <CardTitle class="text-base flex items-center gap-2">
          <BarChart3 class="size-4 text-primary" /> 运行计数器
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div v-if="loading" class="space-y-2">
          <Skeleton class="h-8 w-full rounded" />
        </div>
        <div v-else class="flex flex-wrap gap-3">
          <div v-for="(v, k) in metricsData.counters" :key="k" class="rounded-lg border border-border px-4 py-2.5 min-w-[120px]">
            <p class="text-[10px] text-muted-foreground">{{ counterLabels[k as string] || k }}</p>
            <p class="text-base font-bold font-mono">{{ v.toLocaleString() }}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { RefreshCw, Activity, AlertTriangle, Settings, Database, BarChart3, Clock, Zap, Server, ShieldAlert } from 'lucide-vue-next'
import { apiClient } from '@/api/client'

const loading = ref(true)
const savingThresholds = ref(false)
const thresholdMsg = ref('')
const thresholdMsgOk = ref(true)

interface LatencyStats {
  count: number
  avg_ms: number
  p50_ms: number
  p95_ms: number
  max_ms: number
}

const metricsData = ref<{
  uptime_seconds: number
  boot_time: string
  counters: Record<string, number>
  latencies: Record<string, LatencyStats>
  database: Record<string, number>
}>({
  uptime_seconds: 0,
  boot_time: '',
  counters: {},
  latencies: {},
  database: {},
})

const thresholds = ref<Record<string, number>>({})
const pendingThresholds = ref<Record<string, number>>({})

interface Alert {
  metric: string
  value: number
  threshold: number
  severity: string
}
const alertSummary = ref<{
  has_alerts: boolean
  alert_count: number
  alerts: Alert[]
}>({ has_alerts: false, alert_count: 0, alerts: [] })

const alertLabels: Record<string, string> = {
  scan_fail_rate: '扫描失败率',
  firewall_fail_rate: '防火墙回执失败率',
  api_p95_latency: 'API P95 延迟',
}

const latencyLabels: Record<string, string> = {
  api_request: 'HTTP 请求',
  ai_chat: 'AI 对话',
  firewall_sync: '防火墙同步',
  scan_dispatch: '扫描调度',
}

const thresholdLabels: Record<string, string> = {
  scan_fail_rate_pct: '扫描失败率',
  firewall_fail_rate_pct: '防火墙失败率',
  api_p95_ms: 'API P95 延迟',
  scan_timeout_rate_pct: '扫描超时率',
}

const counterLabels: Record<string, string> = {
  http_requests_total: 'HTTP 请求总数',
  http_errors_total: 'HTTP 错误总数',
  ai_chat_requests: 'AI 对话请求',
  firewall_sync_total: '防火墙同步',
}

function formatUptime(s: number) {
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d}天${h}小时`
  if (h > 0) return `${h}小时${m}分`
  return `${m}分${Math.floor(s % 60)}秒`
}

const statCards = computed(() => {
  const m = metricsData.value
  const counters = m.counters || {}
  const total = counters.http_requests_total || 0
  const errors = counters.http_errors_total || 0
  return [
    {
      label: '运行时间',
      value: formatUptime(m.uptime_seconds || 0),
      icon: Clock,
      sub: `启动: ${m.boot_time ? m.boot_time.slice(0, 19).replace('T', ' ') : '-'}`,
    },
    {
      label: 'HTTP 请求总量',
      value: total.toLocaleString(),
      icon: Zap,
      sub: `错误 ${errors}`,
    },
    {
      label: '威胁事件数',
      value: (m.database?.threat_events || 0).toLocaleString(),
      icon: ShieldAlert,
    },
    {
      label: '扫描任务数',
      value: (m.database?.scan_tasks || 0).toLocaleString(),
      icon: Server,
      sub: `失败率 ${m.database?.scan_fail_rate || 0}%`,
    },
  ]
})

const dbCards = computed(() => {
  const d = metricsData.value.database || {}
  return [
    { label: '威胁事件', value: d.threat_events || 0 },
    { label: '扫描任务', value: d.scan_tasks || 0 },
    { label: '扫描失败率', value: `${d.scan_fail_rate || 0}%`, warn: (d.scan_fail_rate || 0) > 20 },
    { label: '防火墙任务', value: d.firewall_tasks || 0 },
    { label: '防火墙失败率', value: `${d.firewall_fail_rate || 0}%`, warn: (d.firewall_fail_rate || 0) > 10 },
  ]
})

async function refresh() {
  loading.value = true
  try {
    const [mRes, tRes, aRes] = await Promise.all([
      apiClient.get('/system/metrics'),
      apiClient.get('/system/alert-thresholds'),
      apiClient.get('/system/alert-check'),
    ])
    metricsData.value = mRes as any
    thresholds.value = tRes as any
    pendingThresholds.value = {}
    alertSummary.value = aRes as any
  } catch (e: any) {
    console.error('metrics fetch error', e)
  } finally {
    loading.value = false
  }
}

async function saveThresholds() {
  if (Object.keys(pendingThresholds.value).length === 0) return
  savingThresholds.value = true
  thresholdMsg.value = ''
  try {
    const res: any = await apiClient.put('/system/alert-thresholds', pendingThresholds.value)
    thresholds.value = res
    pendingThresholds.value = {}
    thresholdMsg.value = '已保存'
    thresholdMsgOk.value = true
    const aRes: any = await apiClient.get('/system/alert-check')
    alertSummary.value = aRes
  } catch (e: any) {
    thresholdMsg.value = e?.message || '保存失败'
    thresholdMsgOk.value = false
  } finally {
    savingThresholds.value = false
  }
}

onMounted(refresh)
</script>
