<script setup lang="ts">
import { computed } from 'vue'
import { Line, Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  LineElement,
  LinearScale,
  CategoryScale,
  PointElement,
  Filler,
  BarElement,
} from 'chart.js'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Activity } from 'lucide-vue-next'

ChartJS.register(
  Title,
  Tooltip,
  Legend,
  LineElement,
  LinearScale,
  CategoryScale,
  PointElement,
  Filler,
  BarElement
)

const props = defineProps<{
  payload: {
    top_metrics: {
      hfish_total: number
      hfish_high: number
      nmap_online: number
      vuln_open: number
      ai_decisions: number
      blocked_ips: number
    }
    chain_status: Record<string, boolean>
    trends: { labels: string[]; counts: number[] }
    hot_services: Array<{ name: string; count: number }>
  }
  loading: boolean
}>()

const metricCards = computed(() => [
  { key: 'hfish_total', label: '攻击日志总数', value: props.payload.top_metrics.hfish_total, color: 'text-cyan-400' },
  { key: 'hfish_high', label: '高危攻击', value: props.payload.top_metrics.hfish_high, color: 'text-red-400' },
  { key: 'nmap_online', label: '在线主机', value: props.payload.top_metrics.nmap_online, color: 'text-emerald-400' },
  { key: 'vuln_open', label: '待修漏洞', value: props.payload.top_metrics.vuln_open, color: 'text-amber-400' },
  { key: 'ai_decisions', label: 'AI 决策数', value: props.payload.top_metrics.ai_decisions, color: 'text-violet-400' },
  { key: 'blocked_ips', label: '已封禁 IP', value: props.payload.top_metrics.blocked_ips, color: 'text-slate-400' },
])

const chainItems = [
  { key: 'hfish_sync', label: 'HFish 同步' },
  { key: 'nmap_scan', label: 'Nmap 扫描' },
  { key: 'ai_analysis', label: 'AI 分析' },
  { key: 'acl_auto_ban', label: 'ACL 封禁' },
]

const trendData = computed(() => ({
  labels: props.payload.trends.labels,
  datasets: [{
    label: '攻击次数',
    data: props.payload.trends.counts,
    borderColor: '#06b6d4',
    backgroundColor: 'rgba(6, 182, 212, 0.12)',
    fill: true,
    tension: 0.35,
    pointRadius: 2,
    borderWidth: 2,
  }],
}))

const trendOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { grid: { color: 'rgba(148,163,184,.12)' }, ticks: { color: '#94a3b8' } },
    y: { grid: { color: 'rgba(148,163,184,.12)' }, ticks: { color: '#94a3b8' } },
  },
}

const serviceData = computed(() => ({
  labels: props.payload.hot_services.slice(0, 6).map((x) => x.name),
  datasets: [{
    label: '攻击次数',
    data: props.payload.hot_services.slice(0, 6).map((x) => x.count),
    backgroundColor: '#8b5cf6',
    borderRadius: 6,
  }],
}))

function getChainStatus(key: string): boolean {
  return props.payload.chain_status[key] ?? false
}
</script>

<template>
  <aside class="min-h-0 overflow-hidden pr-1">
    <ScrollArea class="h-full">
      <div class="space-y-4 pr-2">
        <Card>
          <CardHeader class="pb-3">
            <CardTitle class="text-sm flex items-center gap-2">
              <Activity class="h-4 w-4 text-primary" /> 态势摘要
            </CardTitle>
          </CardHeader>
          <CardContent class="space-y-2">
            <div class="grid grid-cols-2 gap-2">
              <div v-for="item in metricCards" :key="item.key" class="rounded-lg border border-border/60 bg-muted/20 px-2.5 py-2">
                <p class="text-[10px] tracking-wide text-muted-foreground">{{ item.label }}</p>
                <p class="text-base font-semibold leading-5" :class="item.color">{{ item.value || 0 }}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">实时攻击趋势</CardTitle>
          </CardHeader>
          <CardContent>
            <div class="h-44">
              <Line v-if="payload.trends.labels.length" :data="trendData" :options="trendOptions" />
              <Skeleton v-else-if="loading" class="h-full w-full" />
              <div v-else class="h-full flex items-center justify-center text-sm text-muted-foreground">暂无趋势数据</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">热门攻击服务</CardTitle>
          </CardHeader>
          <CardContent>
            <div class="h-44">
              <Bar
                v-if="payload.hot_services.length"
                :data="serviceData"
                :options="{
                  responsive: true,
                  maintainAspectRatio: false,
                  indexAxis: 'y',
                  plugins: { legend: { display: false } },
                  scales: {
                    x: { grid: { display: false }, ticks: { color: '#94a3b8' } },
                    y: { grid: { display: false }, ticks: { color: '#94a3b8' } }
                  }
                }"
              />
              <Skeleton v-else-if="loading" class="h-full w-full" />
              <div v-else class="h-full flex items-center justify-center text-sm text-muted-foreground">暂无服务统计</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">防御链路状态</CardTitle>
          </CardHeader>
          <CardContent class="space-y-2">
            <div v-for="item in chainItems" :key="item.key" class="flex items-center justify-between">
              <span class="text-sm text-muted-foreground">{{ item.label }}</span>
              <span v-if="getChainStatus(item.key)" class="text-xs text-emerald-400">运行中</span>
              <span v-else class="text-xs text-slate-500">未启用</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </ScrollArea>
  </aside>
</template>
