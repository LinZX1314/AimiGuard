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
import { Skeleton } from '@/components/ui/skeleton'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Activity } from 'lucide-vue-next'
import TechCard from './shared/TechCard.vue'

import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { TooltipComponent } from 'echarts/components'
import 'echarts-wordcloud'
import VChart from 'vue-echarts'

use([CanvasRenderer, TooltipComponent])

ChartJS.register(
  Title,
  Tooltip,
  Legend,
  LineElement,
  LinearScale,
  CategoryScale,
  PointElement,
  Filler,
  BarElement,
)

const props = defineProps<{
  payload: {
    top_metrics: {
      hfish_total: number
      hfish_high: number
      nmap_online: number
      ai_decisions: number
      blocked_ips: number
    }
    chain_status: Record<string, boolean>
    trends: { labels: string[]; counts: number[] }
    hot_services: Array<{ name: string; count: number }>
    recent_attacks: Array<{ attack_ip: string; ip_location?: string; service_name?: string; threat_level?: string; create_time_str?: string }>
  }
  loading: boolean
}>()

const metricCards = computed(() => [
  { key: 'hfish_total', label: '攻击日志总数', value: props.payload.top_metrics.hfish_total, color: 'text-primary' },
  { key: 'hfish_high', label: '高危攻击', value: props.payload.top_metrics.hfish_high, color: 'text-red-500' },
  { key: 'nmap_online', label: '在线主机', value: props.payload.top_metrics.nmap_online, color: 'text-emerald-500' },
  { key: 'ai_decisions', label: 'AI 决策数', value: props.payload.top_metrics.ai_decisions, color: 'text-violet-500' },
  { key: 'blocked_ips', label: '已封禁 IP', value: props.payload.top_metrics.blocked_ips, color: 'text-slate-500 dark:text-slate-400' },
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
    borderColor: 'hsl(var(--primary))',
    backgroundColor: 'hsl(var(--primary) / 0.12)',
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
    backgroundColor: 'hsl(var(--primary) / 0.65)',
    borderRadius: 6,
  }],
}))

const attackTypeWords = computed(() => {
  const counter = new Map<string, number>()
  props.payload.recent_attacks.forEach((item) => {
    const key = item.service_name?.trim() || '未知攻击'
    counter.set(key, (counter.get(key) || 0) + 1)
  })

  const result = Array.from(counter.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)

  if (result.length > 0) {
    return result
  }

  return [
    ['SSH暴力破解', 9],
    ['SQL注入', 7],
    ['端口扫描', 6],
    ['XSS攻击', 5],
    ['目录遍历', 4],
    ['DDoS', 4],
  ] as Array<[string, number]>
})

const wordCloudOption = computed(() => {
  // 主题感知色板：暗色用彩虹，亮色用蓝色系
  const colors = [
    'hsl(var(--primary))', 'hsl(260 60% 55%)', 'hsl(340 65% 55%)',
    'hsl(25 95% 55%)', 'hsl(158 80% 45%)', 'hsl(185 80% 45%)',
  ]
  return {
    tooltip: { show: true },
    series: [
      {
        type: 'wordCloud',
        shape: 'circle',
        keepAspect: false,
        left: 'center',
        top: 'center',
        width: '100%',
        height: '100%',
        right: null,
        bottom: null,
        sizeRange: [12, 32],
        rotationRange: [0, 0],
        rotationStep: 45,
        gridSize: 8,
        drawOutOfBound: false,
        layoutAnimation: true,
        textStyle: {
          fontWeight: 'bold',
          color: function () {
            return colors[Math.floor(Math.random() * colors.length)]
          }
        },
        data: attackTypeWords.value.map(([name, value]) => ({
          name,
          value,
        }))
      }
    ]
  }
})

function getChainStatus(key: string): boolean {
  return props.payload.chain_status[key] ?? false
}
</script>

<template>
  <aside class="h-full flex flex-col gap-3 min-h-0 overflow-hidden pr-2">
    <TechCard title="态势摘要" :icon="Activity" glow-color="cyan" class="tech-card-dashboard-clear shrink-0">
      <div class="space-y-1.5">
        <div class="grid grid-cols-2 gap-1.5">
          <div v-for="item in metricCards" :key="item.key" class="rounded-md border border-border/60 bg-secondary/30 px-2 py-1.5 dark:bg-muted/20">
            <p class="text-[10px] tracking-wide text-muted-foreground">{{ item.label }}</p>
            <p class="text-sm font-semibold leading-4" :class="item.color">{{ item.value || 0 }}</p>
          </div>
        </div>
      </div>
    </TechCard>

    <TechCard title="实时攻击趋势" glow-color="cyan" class="tech-card-dashboard-clear flex-adaptive-card flex-[0.9] shrink-0 min-h-0">
      <div class="flex-1 min-h-0 relative w-full h-full">
        <Line v-if="payload.trends.labels.length" :data="trendData" :options="trendOptions" />
        <Skeleton v-else-if="loading" class="h-full w-full" />
        <div v-else class="h-full flex items-center justify-center text-sm text-muted-foreground">暂无趋势数据</div>
      </div>
    </TechCard>

    <TechCard title="热门攻击服务" glow-color="orange" class="tech-card-dashboard-clear flex-adaptive-card flex-[1.4] min-h-0">
      <div class="flex flex-col gap-2 flex-1 min-h-0 h-full">
        <div class="flex-1 min-h-0 relative w-full h-full">
          <Bar
            v-if="payload.hot_services.length"
            :data="serviceData"
            :options="{
              responsive: true,
              maintainAspectRatio: false,
              indexAxis: 'y',
              plugins: { legend: { display: false } },
              scales: {
                x: { grid: { display: false }, ticks: { color: 'hsl(var(--muted-foreground))' } },
                y: { grid: { display: false }, ticks: { color: 'hsl(var(--muted-foreground))' } }
              }
            }"
          />
          <Skeleton v-else-if="loading" class="h-full w-full" />
          <div v-else class="h-full flex items-center justify-center text-sm text-muted-foreground">暂无服务统计</div>
        </div>

        <div class="flex-[1.2] min-h-0 relative rounded-lg border border-border/60 bg-secondary/30 dark:bg-muted/20 backdrop-blur" aria-label="攻击类型词云">
          <v-chart class="h-full w-full absolute inset-0" :option="wordCloudOption" autoresize />
        </div>
      </div>
    </TechCard>

    <TechCard title="防御链路状态" glow-color="green" class="tech-card-dashboard-clear shrink-0">
      <div class="space-y-1.5">
        <div v-for="item in chainItems" :key="item.key" class="flex items-center justify-between">
          <span class="text-sm text-muted-foreground">{{ item.label }}</span>
          <span v-if="getChainStatus(item.key)" class="text-xs text-emerald-500 font-medium">运行中</span>
          <span v-else class="text-xs text-muted-foreground">未启用</span>
        </div>
      </div>
    </TechCard>
  </aside>
</template>

<style scoped>
.flex-adaptive-card {
  display: flex;
  flex-direction: column;
}
.flex-adaptive-card :deep(> div.p-2\.5) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
</style>
