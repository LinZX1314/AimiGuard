<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { api, notifyError } from '@/api/index'
import {
  defenseApi,
  TERMINAL_COUNTER_SERVICE_NAME,
  type HFishSyncResult,
  type TerminalEvidenceItem,
} from '@/api/defense'

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Pagination } from '@/components/ui/pagination'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import {
  Search,
  ChevronDown,
  ChevronRight,
  Shield,
  Server,
  Globe,
  Clock3,
  Copy,
  Check,
  Activity,
  AlertTriangle,
  ExternalLink,
  Eye,
  X,
} from 'lucide-vue-next'

use([CanvasRenderer, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent])

interface HFishTypeItem {
  name: string
  total_attacks: number
  latest_attack_time?: string
  latest_attack_ip?: string
  latest_client_id?: string
  latest_ip_location?: string
  latest_threat_level?: string
}

interface HFishLogItem {
  id: number
  attack_ip: string
  ip_location: string
  service_name?: string
  service_port: number | string | null
  client_id: string
  client_name?: string
  attack_time?: string
  create_time_str?: string
  create_time_timestamp?: number
  threat_level: string
  payload: string
  preview_url?: string
  screenshot_url?: string
  camera_url?: string
  screenshot_filename?: string
  camera_filename?: string
  upload_api?: string
  client_time?: string
  client_host?: string
  client_ip?: string
  capture_summary?: string
  jump_path?: string
  is_combined?: boolean
}

const TERMINAL_SERVICE_NAME = TERMINAL_COUNTER_SERVICE_NAME

const loadingTypes = ref(false)
const loadingDetail = ref(false)
const search = ref('')
const copiedId = ref<number | null>(null)

const totalAttacks = ref(0)
const typeTabs = ref<HFishTypeItem[]>([])
const expandedService = ref<string | null>(null)

const DEFAULT_PAGE_SIZE = 20
const TERMINAL_PAGE_SIZE = 6
const page = ref(1)
const pageSize = ref(DEFAULT_PAGE_SIZE)
const total = ref(0)

const detailStats = ref({
  total_attacks: 0,
  unique_nodes: 0,
  unique_ips: 0,
  latest_attack_time: '-',
})

const trend = ref({
  labels: [] as string[],
  values: [] as number[],
})

const serviceStatsData = ref<{ name: string; value: number }[]>([])

const logs = ref<HFishLogItem[]>([])
const evidenceDetailOpen = ref(false)
const evidenceDetail = ref<TerminalEvidenceItem | null>(null)
const detailPreviewIndex = ref(0)

const detailPreviewImages = computed(() => {
  if (!evidenceDetail.value) return [] as Array<{ label: string; url: string }>
  if (evidenceDetail.value.is_combined && evidenceDetail.value.screenshot_url && evidenceDetail.value.camera_url) {
    return [
      { label: '终端截图', url: evidenceDetail.value.screenshot_url },
      { label: '终端摄像头', url: evidenceDetail.value.camera_url },
    ]
  }
  const fallback = evidenceDetail.value.preview_url || evidenceDetail.value.screenshot_url || evidenceDetail.value.camera_url || ''
  return fallback ? [{ label: '终端取证图像', url: fallback }] : []
})

const activeDetailPreviewImage = computed(() => detailPreviewImages.value[detailPreviewIndex.value]?.url || '')

const detailPreviewMeta = computed(() => {
  if (!evidenceDetail.value) return [] as Array<{ label: string; value: string }>
  return [
    { label: '数据来源', value: '终端取证回传' },
    { label: '风险等级', value: evidenceDetail.value.severity_label || '高危回传' },
    { label: '取证类型', value: evidenceDetail.value.capture_summary || '-' },
    { label: '回传时间', value: evidenceDetail.value.time || '-' },
    { label: '客户端时间', value: evidenceDetail.value.client_time || '-' },
    { label: '上报 API', value: evidenceDetail.value.upload_api || '-' },
    { label: '客户端名称', value: evidenceDetail.value.client_name || '-' },
    { label: '客户端主机', value: evidenceDetail.value.client_host || '-' },
    { label: '客户端 IP', value: evidenceDetail.value.client_ip || '-' },
    { label: '截图文件', value: evidenceDetail.value.screenshot_filename || '-' },
    { label: '摄像头文件', value: evidenceDetail.value.camera_filename || '-' },
    { label: '截图路径', value: evidenceDetail.value.screenshot_url || '-' },
    { label: '摄像头路径', value: evidenceDetail.value.camera_url || '-' },
  ]
})

const statCards = computed(() => [
  { key: 'total', title: '攻击总数', value: detailStats.value.total_attacks, icon: Shield, color: 'text-primary' },
  { key: 'nodes', title: '攻击节点数', value: detailStats.value.unique_nodes, icon: Server, color: 'text-emerald-400' },
  { key: 'ips', title: '来源 IP 数', value: detailStats.value.unique_ips, icon: Globe, color: 'text-amber-400' },
  { key: 'latest', title: '最新攻击时间', value: detailStats.value.latest_attack_time, icon: Clock3, color: 'text-violet-400' },
])

const serviceCards = computed(() => {
  if (!search.value) return typeTabs.value
  const kw = search.value.toLowerCase()
  return typeTabs.value.filter((item) =>
    (item.name || '').toLowerCase().includes(kw) ||
    (item.latest_attack_ip || '').toLowerCase().includes(kw) ||
    (item.latest_client_id || '').toLowerCase().includes(kw),
  )
})

const serviceCount = computed(() => typeTabs.value.length)
const avgAttacksPerService = computed(() => {
  if (!serviceCount.value) return 0
  return Math.round(totalAttacks.value / serviceCount.value)
})
const selectedServiceLabel = computed(() => expandedService.value || '全部服务')
const pageSizeOptions = computed(() => {
  if (isTerminalService(expandedService.value)) {
    return [6, 12, 20, 50, 100]
  }
  return [20, 50, 100, 200, 500]
})

const filteredLogs = computed(() => {
  const kw = search.value.toLowerCase()
  if (!kw) return logs.value
  return logs.value.filter((item) =>
    (item.attack_ip || '').toLowerCase().includes(kw) ||
    (item.client_id || '').toLowerCase().includes(kw) ||
    (item.ip_location || '').toLowerCase().includes(kw) ||
    (item.payload || '').toLowerCase().includes(kw),
  )
})

function buildTrendOption(labels: string[], values: number[]) {
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line' },
    },
    grid: { left: '3%', right: '4%', top: '12%', bottom: '8%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: labels,
      axisLabel: {
        color: '#94a3b8',
        fontSize: 10,
        formatter: (val: string) => val.slice(5),
      },
      axisLine: { lineStyle: { color: 'rgba(148,163,184,.3)' } },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: '#94a3b8', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(148,163,184,.12)' } },
    },
    series: [
      {
        type: 'line',
        smooth: true,
        data: values,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 3, color: '#22d3ee' },
        itemStyle: { color: '#06b6d4' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(34,211,238,.35)' },
              { offset: 1, color: 'rgba(34,211,238,.02)' },
            ],
          },
        },
      },
    ],
  }
}

const trendOption = computed(() => buildTrendOption(trend.value.labels, trend.value.values))

const servicePieOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: {
    trigger: 'item',
    formatter: '{b}: {c} ({d}%)',
  },
  series: [
    {
      type: 'pie',
      radius: ['35%', '60%'],
      center: ['25%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: {
        borderRadius: 4,
      },
      label: {
        show: true,
        position: 'outside',
        formatter: '{b}',
        fontSize: 11,
        color: '#94a3b8',
        lineHeight: 18,
      },
      labelLine: {
        show: true,
        lineStyle: {
          color: 'rgba(148,163,184,.5)',
          width: 1,
        },
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 12,
          fontWeight: 'bold',
        },
      },
      data: serviceStatsData.value,
    },
  ],
}))

async function loadTypes() {
  loadingTypes.value = true
  try {
    const res = await api.get<any>('/api/v1/defense/hfish/stats')
    const serviceStats = res?.service_stats ?? []
    const baseCards: HFishTypeItem[] = serviceStats.map((s: any) => ({
      name: s.name || '未知',
      total_attacks: Number(s.count || 0),
    }))

    // 补充每个服务的最新攻击信息，形成横向卡片摘要
    const settled = await Promise.allSettled(
      baseCards.map(async (card) => {
        const url = `/api/v1/defense/hfish/logs?page=1&page_size=1&service_name=${encodeURIComponent(card.name)}`
        const d = await api.get<any>(url)
        const latest = (d?.items ?? [])[0]
        return {
          ...card,
          latest_attack_time: latest?.create_time_str || '-',
          latest_attack_ip: latest?.attack_ip || '-',
          latest_client_id: latest?.client_id || '-',
          latest_ip_location: latest?.ip_location || '未知',
          latest_threat_level: latest?.threat_level || 'unknown',
        } as HFishTypeItem
      }),
    )

    typeTabs.value = settled
      .map((x, i) => (x.status === 'fulfilled' ? x.value : baseCards[i]))
      .sort((a, b) => Number(b.total_attacks || 0) - Number(a.total_attacks || 0))

    totalAttacks.value = typeTabs.value.reduce((sum, item) => sum + item.total_attacks, 0)
    serviceStatsData.value = typeTabs.value.map((item) => ({
      name: item.name || '未知',
      value: Number(item.total_attacks || 0),
    }))
  } catch (e) {
    console.error(e)
  }
  loadingTypes.value = false
}

async function loadServiceDetail(serviceName: string) {
  loadingDetail.value = true
  try {
    const encoded = encodeURIComponent(serviceName)
    const listUrl = `/api/v1/defense/hfish/logs?page=${page.value}&page_size=${pageSize.value}&service_name=${encoded}`
    const listRes = await api.get<any>(listUrl)
    const items = (listRes?.items ?? []) as HFishLogItem[]
    logs.value = items.map((item) => ({
      ...item,
      attack_time: item.attack_time || item.create_time_str || '-',
    }))
    total.value = Number(listRes?.total ?? 0)

    // 当前蜜罐服务的聚合统计
    const aggUrl = `/api/v1/defense/hfish/logs?page=1&page_size=1000&aggregated=1&service_name=${encoded}`
    const aggRes = await api.get<any>(aggUrl)
    const aggItems = aggRes?.items ?? []
    const uniqueIps = aggItems.length
    const totalAttackCount = aggItems.reduce((sum: number, row: any) => sum + Number(row.attack_count || 0), 0)

    // 为了得到更稳定的节点统计与趋势，取当前服务较大样本
    const sampleUrl = `/api/v1/defense/hfish/logs?page=1&page_size=1000&service_name=${encoded}`
    const sampleRes = await api.get<any>(sampleUrl)
    const sampleLogs = (sampleRes?.items ?? []) as HFishLogItem[]
    const nodeSet = new Set(sampleLogs.map((x) => x.client_id).filter(Boolean))

    detailStats.value = {
      total_attacks: totalAttackCount || total.value,
      unique_nodes: nodeSet.size,
      unique_ips: uniqueIps,
      latest_attack_time: (sampleLogs[0]?.create_time_str || logs.value[0]?.attack_time || '-'),
    }

    // 当前服务攻击趋势：按天聚合，避免前端过密
    const counter = new Map<string, number>()
    sampleLogs.forEach((item) => {
      const raw = (item.create_time_str || item.attack_time || '').slice(0, 10)
      if (!raw) return
      const key = raw
      counter.set(key, (counter.get(key) || 0) + 1)
    })
    const sorted = [...counter.entries()].sort((a, b) => a[0].localeCompare(b[0]))
    trend.value = {
      labels: sorted.map((x) => x[0]),
      values: sorted.map((x) => x[1]),
    }
  } catch (e) {
    console.error(e)
  }
  loadingDetail.value = false
}

function isTerminalService(serviceName?: string | null) {
  return (serviceName || '') === TERMINAL_SERVICE_NAME
}

function serviceCardClass(serviceName?: string | null) {
  if (isTerminalService(serviceName)) {
    return 'border-red-500/45 bg-red-950/20'
  }
  return 'border-border/50 bg-card/40'
}

function serviceHeaderClass(serviceName?: string | null) {
  if (isTerminalService(serviceName)) {
    return 'hover:bg-red-900/25'
  }
  return 'hover:bg-muted/50'
}

function getTerminalPreview(item: TerminalEvidenceItem | HFishLogItem) {
  return item.preview_url || item.screenshot_url || item.camera_url || ''
}

function openTerminalEvidenceDetail(item: TerminalEvidenceItem) {
  evidenceDetail.value = item
  detailPreviewIndex.value = 0
  evidenceDetailOpen.value = true
}

function openTerminalLogDetail(log: HFishLogItem) {
  openTerminalEvidenceDetail({
    event_key: log.client_id || String(log.id || ''),
    source: 'terminal',
    severity: 'high',
    severity_label: '高危回传',
    attack_kind: 'counter_honeypot',
    service_name: TERMINAL_SERVICE_NAME,
    attack_source: log.ip_location || '终端取证节点',
    capture_types: log.camera_url && log.screenshot_url ? ['screenshot', 'camera'] : (log.camera_url ? ['camera'] : ['screenshot']),
    capture_summary: log.capture_summary || (log.camera_url && log.screenshot_url ? '截图+摄像头' : (log.camera_url ? '摄像头' : '截图')),
    is_combined: Boolean(log.is_combined),
    preview_url: log.preview_url || log.screenshot_url || log.camera_url || '',
    jump_path: log.jump_path || '/screenshots',
    attack_count: 1,
    filename: log.screenshot_filename || log.camera_filename || log.client_id || '-',
    url: log.preview_url || log.screenshot_url || log.camera_url || '',
    screenshot_filename: log.screenshot_filename || '',
    screenshot_url: log.screenshot_url || '',
    camera_filename: log.camera_filename || '',
    camera_url: log.camera_url || '',
    upload_api: log.upload_api || '',
    client_time: log.client_time || log.create_time_str || log.attack_time || '-',
    client_name: log.client_name || '终端取证客户端',
    client_host: log.client_host || '',
    client_ip: log.client_ip || '',
    time: log.create_time_str || log.attack_time || '-',
    mtime: Number(log.create_time_timestamp || 0),
  })
}

async function switchType(name: string) {
  if (expandedService.value === name) {
    expandedService.value = null
    return
  }
  expandedService.value = name
  page.value = 1
  pageSize.value = isTerminalService(name) ? TERMINAL_PAGE_SIZE : DEFAULT_PAGE_SIZE
  await loadServiceDetail(name)
}

async function manualSync() {
  loadingDetail.value = true
  try {
    const result = await defenseApi.triggerHFishSync()
    if (!result?.success) {
      notifyError(resolveHFishSyncErrorMessage(result))
      return
    }

    await loadTypes()
    if (expandedService.value) {
      await loadServiceDetail(expandedService.value)
    }
  } catch (error) {
    notifyError(error instanceof Error ? error.message : '同步失败')
  } finally {
    loadingDetail.value = false
  }
}

function resolveHFishSyncErrorMessage(result?: HFishSyncResult) {
  const errorCode = result?.error_code || 'sync_failed'
  const error = result?.error || ''

  const messages: Record<string, string> = {
    invalid_config: 'HFish 同步失败：地址或 API Key 未配置完整',
    unauthorized: 'HFish 同步失败：API Key 无效或已过期（401）',
    forbidden: 'HFish 同步失败：当前 API Key 没有访问权限（403）',
    not_found: 'HFish 同步失败：接口地址不存在（404），请检查 HFish 地址或 API 路径',
    connection_refused: 'HFish 同步失败：目标服务拒绝连接，请确认 HFish 已启动并监听正确端口',
    invalid_host: 'HFish 同步失败：主机地址无法解析，请检查 host / api_base_url 配置',
    connection_error: 'HFish 同步失败：连接异常，请检查网络连通性和服务状态',
    timeout: 'HFish 同步失败：接口请求超时，HFish 响应过慢',
    http_error: `HFish 同步失败：${error || '接口返回 HTTP 错误'}`,
    unexpected_error: `HFish 同步失败：${error || '发生未知异常'}`,
    sync_failed: `HFish 同步失败：${error || '同步未完成'}`,
  }

  return messages[errorCode] || `HFish 同步失败：${error || errorCode}`
}

async function onPageChange(next: number) {
  page.value = next
  if (expandedService.value) {
    await loadServiceDetail(expandedService.value)
  }
}

async function onPageSizeChange(next: number) {
  pageSize.value = next
  page.value = 1
  if (expandedService.value) {
    await loadServiceDetail(expandedService.value)
  }
}

function threatClass(level: string) {
  if (level === 'high' || level === '高危') return 'bg-red-500/10 text-red-400 border-red-500/30'
  if (level === 'medium' || level === '中危') return 'bg-amber-500/10 text-amber-400 border-amber-500/30'
  if (level === 'low' || level === '安全') return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
  return 'bg-slate-500/10 text-muted-foreground border-slate-500/30'
}

function threatLabel(level: string) {
  if (!level) return ''
  const l = level.toLowerCase()
  if (l === 'high') return '高危'
  if (l === 'medium') return '中危'
  if (l === 'low') return '安全'
  return level
}

async function copyLog(item: HFishLogItem) {
  const text = [
    `ID: ${item.id ?? '-'}`,
    `攻击时间: ${item.attack_time || item.create_time_str || '-'}`,
    `时间戳: ${item.create_time_timestamp ?? '-'}`,
    `蜜罐服务: ${item.service_name || expandedService.value || '-'}`,
    `服务端口: ${item.service_port ?? '-'}`,
    `来源IP: ${item.attack_ip || '-'}`,
    `归属地: ${item.ip_location || '未知'}`,
    `节点名称: ${item.client_name || '-'}`,
    `攻击节点: ${item.client_id || '-'}`,
    `上报API: ${item.upload_api || '-'}`,
    `客户端时间: ${item.client_time || '-'}`,
    `威胁等级: ${threatLabel(item.threat_level || '')}`,
    `详情: ${item.payload || '-'}`,
  ].join('\n')
  await navigator.clipboard.writeText(text)
  copiedId.value = item.id
  setTimeout(() => {
    if (copiedId.value === item.id) copiedId.value = null
  }, 1200)
}

onMounted(async () => {
  await loadTypes()
})
</script>

<template>
  <div class="p-6 space-y-6">
    <div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
      <Card class="border-l-[4px] border-l-primary xl:col-span-2">
        <CardContent class="p-5">
          <div class="flex items-center gap-6">
            <div class="flex-shrink-0">
              <p class="text-xs font-semibold tracking-[0.12em] text-primary uppercase">HFish 攻击总量</p>
              <h2 class="text-4xl font-bold text-primary mt-1">{{ totalAttacks }}</h2>
              <p class="text-xs text-muted-foreground mt-1">展示最近同步到本地的攻击聚合统计</p>
            </div>
            <div class="flex items-center gap-4 flex-1 min-w-0">
              <div class="h-[160px] flex-1 min-w-0">
                <VChart :option="servicePieOption" autoresize />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card class="border-border/50">
        <CardHeader class="pb-2">
          <CardTitle class="text-sm">统计概览</CardTitle>
        </CardHeader>
        <CardContent class="pt-0 space-y-2">
          <div class="flex items-center justify-between rounded-md border border-border/50 bg-black/20 px-3 py-2 text-xs">
            <span class="text-muted-foreground">服务数</span>
            <span class="font-semibold">{{ serviceCount }}</span>
          </div>
          <div class="flex items-center justify-between rounded-md border border-border/50 bg-black/20 px-3 py-2 text-xs">
            <span class="text-muted-foreground">每服务均值</span>
            <span class="font-semibold">{{ avgAttacksPerService }}</span>
          </div>
          <div class="flex items-center justify-between rounded-md border border-border/50 bg-black/20 px-3 py-2 text-xs">
            <span class="text-muted-foreground">当前查看</span>
            <span class="font-semibold truncate max-w-[180px] text-right">{{ selectedServiceLabel }}</span>
          </div>
        </CardContent>
      </Card>
    </div>

    <Card class="border-border/50">
      <CardHeader class="pb-3 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <CardTitle class="text-base flex items-center gap-2">
          <Activity class="h-4 w-4 text-primary" />
          蜜罐服务攻击列表
        </CardTitle>
        <div class="relative w-full md:w-80">
          <Search class="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input v-model="search" class="pl-9 bg-card/40" placeholder="筛选服务名 / 攻击IP / 节点" />
        </div>
      </CardHeader>

      <CardContent class="space-y-3">
        <div class="hidden md:grid md:grid-cols-12 text-[11px] text-muted-foreground uppercase tracking-wider px-4">
          <div class="md:col-span-2">蜜罐服务</div>
          <div class="md:col-span-2">被攻击数量</div>
          <div class="md:col-span-3">攻击来源</div>
          <div class="md:col-span-3">最近攻击时间</div>
          <div class="md:col-span-2 text-right">操作</div>
        </div>

        <template v-if="loadingTypes">
          <div v-for="i in 8" :key="i" class="rounded-xl border border-border/50 bg-card/40 p-4">
            <Skeleton class="h-5 w-full" />
          </div>
        </template>

        <template v-else-if="serviceCards.length">
          <div
            v-for="item in serviceCards"
            :key="item.name"
            class="rounded-xl border overflow-hidden"
            :class="serviceCardClass(item.name)"
          >
            <button
              type="button"
              class="w-full px-4 py-3 transition-colors"
              :class="serviceHeaderClass(item.name)"
              @click="switchType(item.name)"
            >
              <div class="grid grid-cols-1 md:grid-cols-12 gap-2 items-center text-left">
                <div class="md:col-span-2 font-semibold flex items-center gap-2" :class="isTerminalService(item.name) ? 'text-red-100' : 'text-foreground'">
                  <ChevronDown v-if="expandedService === item.name" class="h-4 w-4 text-primary" />
                  <ChevronRight v-else class="h-4 w-4 text-muted-foreground" />
                  <span>{{ item.name }}</span>
                </div>
                <div class="md:col-span-2 font-bold" :class="isTerminalService(item.name) ? 'text-red-200' : 'text-primary'">{{ item.total_attacks }}</div>
                <div class="md:col-span-3" :class="isTerminalService(item.name) ? 'text-red-100/85' : 'text-muted-foreground'">{{ item.latest_attack_ip || '-' }}</div>
                <div class="md:col-span-3 text-xs" :class="isTerminalService(item.name) ? 'text-red-100/75' : 'text-muted-foreground'">{{ item.latest_attack_time || '-' }}</div>
                <div class="md:col-span-2 flex md:justify-end">
                  <Badge variant="outline" :class="threatClass(item.latest_threat_level || '')">
                    {{ expandedService === item.name ? '收起' : '展开' }}
                  </Badge>
                </div>
              </div>
            </button>

            <div
              v-if="expandedService === item.name"
              class="border-t p-4 space-y-4"
              :class="isTerminalService(item.name) ? 'border-red-500/30 bg-red-950/25' : 'border-border/50 bg-muted/40'"
            >
              <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
                <Card v-for="s in statCards" :key="s.key" class="">
                  <CardContent class="p-3">
                    <div class="flex items-center justify-between">
                      <div>
                        <p class="text-[11px] text-muted-foreground">{{ s.title }}</p>
                        <p class="text-lg font-bold text-foreground mt-1">{{ s.value }}</p>
                      </div>
                      <component :is="s.icon" class="h-4 w-4" :class="s.color" />
                    </div>
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader class="pb-2">
                  <CardTitle class="text-sm">当前蜜罐攻击趋势</CardTitle>
                </CardHeader>
                <CardContent>
                  <div class="h-[240px]">
                    <VChart :option="trendOption" autoresize />
                  </div>
                </CardContent>
              </Card>

              <div class="space-y-2">
                <div v-if="loadingDetail" class="space-y-2">
                  <div v-for="k in 3" :key="k" class="rounded-lg border border-border/50 bg-card/40 p-3">
                    <Skeleton class="h-5 w-full" />
                  </div>
                </div>

                <template v-else-if="isTerminalService(expandedService) && filteredLogs.length">
                  <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                    <div
                      v-for="log in filteredLogs"
                      :key="log.id"
                      class="rounded-xl border border-red-500/50 bg-red-950/25 overflow-hidden transition-all cursor-pointer group hover:border-red-400"
                      @click="openTerminalLogDetail(log)"
                    >
                      <div class="aspect-[4/3] bg-muted/20 border-b border-red-500/30 overflow-hidden relative">
                        <div
                          v-if="log.is_combined && log.screenshot_url && log.camera_url"
                          class="grid grid-cols-2 gap-1 h-full p-1"
                        >
                          <img
                            :src="log.screenshot_url"
                            alt="终端截图"
                            class="h-full w-full object-cover rounded-sm"
                          />
                          <img
                            :src="log.camera_url"
                            alt="终端摄像头"
                            class="h-full w-full object-cover rounded-sm"
                          />
                        </div>
                        <img
                          v-else
                          :src="getTerminalPreview(log)"
                          :alt="log.capture_summary || '终端取证'"
                          class="h-full w-full object-cover"
                        />
                        <div class="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-all flex items-center justify-center">
                          <ExternalLink class="h-7 w-7 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                        </div>

                        <div class="absolute top-2 left-2 flex items-center gap-1.5">
                          <Badge variant="secondary" class="bg-red-600/90 text-white border-0 text-[10px] px-2 py-0.5">
                            高危回传
                          </Badge>
                          <Badge v-if="log.is_combined && log.screenshot_url && log.camera_url" variant="secondary" class="bg-red-300/90 text-red-900 border-0 text-[10px] px-2 py-0.5">
                            截图+摄像头
                          </Badge>
                        </div>

                        <div class="absolute top-2 right-2">
                          <AlertTriangle class="h-4 w-4 text-red-200" />
                        </div>
                      </div>
                      <div class="p-3 space-y-1.5 bg-red-950/30">
                        <div class="flex items-center gap-2">
                          <Eye class="h-3.5 w-3.5 text-red-200 shrink-0" />
                          <span class="text-sm font-bold text-red-100 truncate">{{ log.capture_summary || '终端取证回传' }}</span>
                        </div>
                        <p class="text-[11px] text-red-100/85 truncate font-mono" :title="log.screenshot_filename || log.camera_filename || log.client_id || '-'">
                          {{ log.screenshot_filename || log.camera_filename || log.client_id || '-' }}
                        </p>
                        <p class="text-[11px] text-red-100/80 truncate">攻击来源：{{ log.attack_ip || '-' }}</p>
                        <p class="text-[11px] text-red-100/75 truncate">上报API：{{ log.upload_api || '-' }}</p>
                        <div class="text-[10px] text-red-100/70 flex items-center gap-1.5">
                          <Clock3 class="h-3 w-3" /> {{ log.create_time_str || log.attack_time || '-' }}
                        </div>
                      </div>
                    </div>
                  </div>
                </template>

                <template v-else-if="filteredLogs.length">
                  <div
                    v-for="log in filteredLogs"
                    :key="log.id"
                    class="rounded-xl border border-border/50 bg-card/40 px-4 py-3"
                  >
                    <div class="grid grid-cols-1 md:grid-cols-12 gap-3 items-start">
                      <div class="md:col-span-3 space-y-1">
                        <div class="text-xs text-muted-foreground">{{ log.create_time_str || log.attack_time || '-' }}</div>
                        <div class="text-[11px] text-muted-foreground">ts: {{ log.create_time_timestamp ?? '-' }}</div>
                        <div class="text-[11px] text-muted-foreground">id: {{ log.id }}</div>
                      </div>

                      <div class="md:col-span-2 space-y-1">
                        <div class="text-primary font-semibold">{{ log.attack_ip || '-' }}</div>
                        <div class="text-[11px] text-muted-foreground">{{ log.ip_location || '未知' }}</div>
                      </div>

                      <div class="md:col-span-3 space-y-1 text-xs text-muted-foreground">
                        <div>
                          <span class="text-muted-foreground">节点名称: </span>{{ log.client_name || '未知节点' }}
                        </div>
                        <div>
                          <span class="text-muted-foreground">节点ID: </span>
                          <span class="font-mono text-[11px] break-all">{{ log.client_id || '-' }}</span>
                        </div>
                        <div>
                          <span class="text-muted-foreground">服务: </span>{{ log.service_name || expandedService || '-' }}
                        </div>
                        <div>
                          <span class="text-muted-foreground">端口: </span>{{ log.service_port ?? '-' }}
                        </div>
                      </div>

                      <div class="md:col-span-3 text-xs text-muted-foreground break-all leading-relaxed">
                        {{ log.payload || '-' }}
                      </div>

                      <div class="md:col-span-1 flex md:flex-col items-end gap-2">
                        <Badge v-if="log.threat_level" variant="outline" :class="threatClass(log.threat_level || '')">
                          {{ threatLabel(log.threat_level || '') }}
                        </Badge>
                        <Button variant="outline" size="sm" class="h-8" @click="copyLog(log)">
                          <Check v-if="copiedId === log.id" class="h-4 w-4 mr-1 text-emerald-400" />
                          <Copy v-else class="h-4 w-4 mr-1" />
                          {{ copiedId === log.id ? '已复制' : '复制' }}
                        </Button>
                      </div>
                    </div>
                  </div>
                </template>

                <div v-else class="py-6 text-center text-muted-foreground flex items-center justify-center gap-2">
                  <AlertTriangle class="h-4 w-4" />
                  当前蜜罐暂无攻击明细
                </div>
              </div>

              <Pagination
                v-model:page="page"
                v-model:page-size="pageSize"
                :total="total"
                :page-sizes="pageSizeOptions"
                @update:page="onPageChange"
                @update:page-size="onPageSizeChange"
              />
            </div>
          </div>
        </template>

        <div v-else class="py-10 text-center text-muted-foreground">没有匹配的蜜罐服务</div>
      </CardContent>
    </Card>

    <Dialog v-model:open="evidenceDetailOpen">
      <DialogContent class="sm:max-w-[1240px] bg-background border-border text-foreground p-0 overflow-hidden max-h-[92vh] flex flex-col">
        <DialogTitle class="sr-only">终端取证详情</DialogTitle>
        <DialogDescription class="sr-only">展示终端回传截图与摄像头文件的高清预览和元数据。</DialogDescription>
        <div class="p-4 bg-muted/50 border-b border-border/60 flex items-center justify-between shrink-0">
          <div class="min-w-0 flex-1 mr-4">
            <p class="text-sm font-semibold truncate">终端取证详情</p>
          </div>
          <div class="flex items-center gap-2">
            <a :href="`#${evidenceDetail?.jump_path || '/screenshots'}`" class="text-xs text-primary hover:underline">前往截图取证</a>
            <Button variant="ghost" size="icon" class="h-7 w-7 shrink-0" @click="evidenceDetailOpen = false">
              <X class="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_340px] min-h-0 flex-1">
          <ScrollArea class="bg-muted/10 min-h-0">
            <div v-if="activeDetailPreviewImage" class="p-3 md:p-5 space-y-3">
              <div class="rounded-md border border-border/50 bg-black/40 overflow-hidden min-h-[55vh] flex items-center justify-center">
                <img
                  :src="activeDetailPreviewImage"
                  :alt="evidenceDetail?.capture_summary || '终端取证详情'"
                  class="max-h-[75vh] w-auto max-w-full object-contain"
                />
              </div>
              <div v-if="detailPreviewImages.length > 1" class="grid grid-cols-2 gap-2">
                <button
                  v-for="(img, idx) in detailPreviewImages"
                  :key="img.label"
                  type="button"
                  class="rounded-md border px-3 py-2 text-xs text-left transition-colors"
                  :class="idx === detailPreviewIndex ? 'border-primary bg-primary/10 text-primary' : 'border-border/60 bg-card/50 text-muted-foreground hover:bg-muted/40'"
                  @click="detailPreviewIndex = idx"
                >
                  {{ img.label }}
                </button>
              </div>
            </div>
            <div v-else class="flex items-center justify-center h-64 text-muted-foreground text-sm">
              截图加载中...
            </div>
          </ScrollArea>

          <div class="border-l border-border/60 bg-card/60 p-4 space-y-3">
            <h3 class="text-sm font-semibold">返回数据详情</h3>
            <a
              v-if="activeDetailPreviewImage"
              :href="activeDetailPreviewImage"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center text-xs text-primary hover:underline"
            >
              <ExternalLink class="h-3 w-3 mr-1" />
              打开原图（高清）
            </a>
            <div class="space-y-2">
              <div
                v-for="meta in detailPreviewMeta"
                :key="meta.label"
                class="rounded-md border border-border/60 bg-black/20 px-3 py-2"
              >
                <p class="text-[10px] text-muted-foreground">{{ meta.label }}</p>
                <p class="text-xs text-foreground mt-1 break-all">{{ meta.value }}</p>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>
