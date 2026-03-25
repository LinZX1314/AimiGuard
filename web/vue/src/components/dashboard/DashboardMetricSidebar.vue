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
import { PieChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import 'echarts-wordcloud'
import VChart from 'vue-echarts'

use([CanvasRenderer, PieChart, TooltipComponent])

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
  // 现代渐变色彩方案 - 使用实际HSL值而非CSS变量
  const colors = [
    '#6366f1', '#8b5cf6', '#ec4899', '#f97316',
    '#10b981', '#06b6d4', '#3b82f6', '#a855f7',
  ]
  return {
    tooltip: {
      show: true,
      backgroundColor: 'hsl(var(--card))',
      borderColor: 'hsl(var(--border))',
      textStyle: { color: 'hsl(var(--foreground))' },
      formatter: (params: any) => `${params.name}: ${params.value}次`
    },
    series: [
      {
        type: 'wordCloud',
        shape: 'circle',
        keepAspect: true,
        left: 'center',
        top: 'center',
        width: '90%',
        height: '90%',
        sizeRange: [14, 36],
        rotationRange: [-30, 30],
        rotationStep: 15,
        gridSize: 10,
        drawOutOfBound: false,
        layoutAnimation: true,
        shrinkToFit: true,
        textStyle: {
          fontWeight: '600',
          fontFamily: 'system-ui, -apple-system, sans-serif',
          color: function () {
            return colors[Math.floor(Math.random() * colors.length)]
          }
        },
        emphasis: {
          textStyle: {
            shadowBlur: 12,
            shadowColor: 'rgba(99, 102, 241, 0.5)'
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
      center: ['30%', '50%'],
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
      data: props.payload.hot_services.map((s) => ({ name: s.name, value: s.count })),
    },
  ],
}))

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

    <TechCard title="热门攻击服务" glow-color="orange" class="tech-card-dashboard-clear flex-adaptive-card flex-1 shrink-0">
      <div class="flex flex-col gap-2 h-full min-h-0">
        <div class="basis-[45%] min-h-[70px]">
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

        <div class="flex-1 min-h-[100px] relative rounded-lg border border-border/60 bg-secondary/30 dark:bg-muted/20 backdrop-blur overflow-hidden" aria-label="攻击类型词云">
          <v-chart
            v-if="attackTypeWords.length"
            class="h-full w-full absolute inset-0"
            :option="wordCloudOption"
            autoresize
          />
          <div v-else class="h-full flex items-center justify-center text-xs text-muted-foreground">暂无攻击数据</div>
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
  height: 100%;
}
</style>
