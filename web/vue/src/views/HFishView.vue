<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { api, apiCall } from '@/api/index'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Pagination } from '@/components/ui/pagination'
import {
  RefreshCw,
  RotateCw,
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
} from 'lucide-vue-next'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent])

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
}

const loadingTypes = ref(false)
const loadingDetail = ref(false)
const search = ref('')
const copiedId = ref<number | null>(null)

const totalAttacks = ref(0)
const typeTabs = ref<HFishTypeItem[]>([])
const expandedService = ref<string | null>(null)

const page = ref(1)
const pageSize = ref(20)
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

const logs = ref<HFishLogItem[]>([])

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

const trendOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'line' },
  },
  grid: { left: '3%', right: '4%', top: '12%', bottom: '8%', containLabel: true },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: trend.value.labels,
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
      data: trend.value.values,
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

    typeTabs.value = settled.map((x, i) => (x.status === 'fulfilled' ? x.value : baseCards[i]))
    totalAttacks.value = typeTabs.value.reduce((sum, item) => sum + item.total_attacks, 0)
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

async function switchType(name: string) {
  if (expandedService.value === name) {
    expandedService.value = null
    return
  }
  expandedService.value = name
  page.value = 1
  await loadServiceDetail(name)
}

async function manualSync() {
  loadingDetail.value = true
  const ok = await apiCall(async () => {
    await api.post('/api/v1/defense/hfish/sync', {})
  }, { errorMsg: '同步失败' })
  if (ok) {
    await loadTypes()
    if (expandedService.value) {
      await loadServiceDetail(expandedService.value)
    }
  }
  loadingDetail.value = false
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
          <div class="flex items-center justify-between gap-4">
            <div>
              <p class="text-xs font-semibold tracking-[0.12em] text-primary uppercase">HFish 攻击总量</p>
              <h2 class="text-4xl font-bold text-primary mt-1">{{ totalAttacks }}</h2>
              <p class="text-xs text-muted-foreground mt-1">展示最近同步到本地的攻击聚合统计</p>
            </div>
            <Button
              variant="outline"
              size="sm"
              @click="manualSync"
              :disabled="loadingDetail"
              class="border-primary/30 bg-primary/10 text-primary hover:bg-primary/20"
            >
              <RotateCw v-if="loadingDetail" class="h-4 w-4 mr-2 animate-spin" />
              <RefreshCw v-else class="h-4 w-4 mr-2" />
              手动同步
            </Button>
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
            class="rounded-xl border border-border/50 bg-card/40 overflow-hidden"
          >
            <button
              type="button"
              class="w-full px-4 py-3 hover:hover:bg-muted/50 transition-colors"
              @click="switchType(item.name)"
            >
              <div class="grid grid-cols-1 md:grid-cols-12 gap-2 items-center text-left">
                <div class="md:col-span-2 font-semibold text-foreground flex items-center gap-2">
                  <ChevronDown v-if="expandedService === item.name" class="h-4 w-4 text-primary" />
                  <ChevronRight v-else class="h-4 w-4 text-muted-foreground" />
                  <span>{{ item.name }}</span>
                </div>
                <div class="md:col-span-2 text-primary font-bold">{{ item.total_attacks }}</div>
                <div class="md:col-span-3 text-muted-foreground">{{ item.latest_attack_ip || '-' }}</div>
                <div class="md:col-span-3 text-muted-foreground text-xs">{{ item.latest_attack_time || '-' }}</div>
                <div class="md:col-span-2 flex md:justify-end">
                  <Badge variant="outline" :class="threatClass(item.latest_threat_level || '')">
                    {{ expandedService === item.name ? '收起' : '展开' }}
                  </Badge>
                </div>
              </div>
            </button>

            <div v-if="expandedService === item.name" class="border-t border-border/50 bg-muted/40 p-4 space-y-4">
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
                :page-sizes="[20, 50, 100, 200, 500]"
                @update:page="onPageChange"
                @update:page-size="onPageSizeChange"
              />
            </div>
          </div>
        </template>

        <div v-else class="py-10 text-center text-muted-foreground">没有匹配的蜜罐服务</div>
      </CardContent>
    </Card>
  </div>
</template>
