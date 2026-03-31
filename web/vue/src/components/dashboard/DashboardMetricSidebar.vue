<script setup lang="ts">
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
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
} from 'chart.js'
import { Skeleton } from '@/components/ui/skeleton'
import { Activity } from 'lucide-vue-next'
import TechCard from './shared/TechCard.vue'

ChartJS.register(
  Title,
  Tooltip,
  Legend,
  LineElement,
  LinearScale,
  CategoryScale,
  PointElement,
  Filler,
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

const trendData = computed(() => {
  const formattedLabels = props.payload.trends.labels.map((label: string) => {
    if (!label) return ''
    const parts = label.split(' ')
    let datePart = parts[0]
    let timePart = parts[1] || ''

    const dParts = datePart.split('-')
    if (dParts.length === 3) {
      datePart = `${dParts[1]}/${dParts[2]}`
    }

    if (timePart) {
      const tParts = timePart.split(':')
      if (tParts.length >= 2) {
        timePart = `${tParts[0]}:${tParts[1]}`
      }
      return `${datePart} ${timePart}`
    }
    return datePart
  })

  return {
    labels: formattedLabels,
    datasets: [{
    label: '攻击次数',
    data: props.payload.trends.counts,
    borderColor: '#34d399',
    backgroundColor: (context: any) => {
      const chart = context.chart
      const { ctx, chartArea } = chart
      if (!chartArea) {
        return 'rgba(52, 211, 153, 0.1)'
      }
      const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom)
      gradient.addColorStop(0, 'rgba(52, 211, 153, 0.4)')
      gradient.addColorStop(1, 'rgba(52, 211, 153, 0.0)')
      return gradient
    },
    fill: true,
    tension: 0.5, // 平滑曲线
    pointRadius: 0, // 不显示折点
    pointBackgroundColor: '#ffffff',
    pointBorderColor: '#34d399',
    pointBorderWidth: 2,
    pointHoverRadius: 0, // 也不要悬浮点
    borderWidth: 2,
  }],
  }
})

const trendOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { 
    legend: { display: false },
    tooltip: {
      mode: 'index' as const,
      intersect: false,
    }
  },
  scales: {
    x: { 
      grid: { display: false }, 
      ticks: { 
        color: '#94a3b8', 
        font: { size: 10 },
        maxRotation: 0,
        maxTicksLimit: 6
      },
      border: { display: false }
    },
    y: { 
      display: false,
      beginAtZero: true
    },
  },
  interaction: {
    mode: 'nearest' as const,
    axis: 'x' as const,
    intersect: false
  },
  layout: {
    padding: {
      top: 10,
      bottom: 5,
      left: 10,
      right: 15
    }
  }
}

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
      <div class="h-full min-h-0 overflow-y-auto space-y-1.5 px-1">
        <template v-if="payload.hot_services.length">
          <div
            v-for="(service, index) in payload.hot_services"
            :key="service.name"
            class="flex items-center justify-between rounded-md border border-border/60 bg-secondary/30 px-3 py-2 dark:bg-muted/20"
          >
            <div class="flex items-center gap-2 min-w-0 flex-1">
              <span class="text-xs font-semibold text-primary w-5">{{ index + 1 }}</span>
              <span class="text-sm truncate text-foreground">{{ service.name }}</span>
            </div>
            <span class="text-sm font-bold text-primary ml-2 flex-shrink-0">{{ service.count }}</span>
          </div>
        </template>
        <Skeleton v-else-if="loading" class="h-full w-full" />
        <div v-else class="h-full flex items-center justify-center text-sm text-muted-foreground">暂无服务统计</div>
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
