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
  { key: 'hfish_total', label: '攻击日志总数', value: props.payload.top_metrics.hfish_total, color: 'text-cyan-400' },
  { key: 'hfish_high', label: '高危攻击', value: props.payload.top_metrics.hfish_high, color: 'text-red-400' },
  { key: 'nmap_online', label: '在线主机', value: props.payload.top_metrics.nmap_online, color: 'text-emerald-400' },
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

const cloudWords = computed(() => {
  const slots = [
    { left: '6%', top: '14%' },
    { left: '40%', top: '6%' },
    { left: '67%', top: '18%' },
    { left: '14%', top: '42%' },
    { left: '50%', top: '40%' },
    { left: '25%', top: '66%' },
    { left: '73%', top: '62%' },
    { left: '9%', top: '74%' },
    { left: '56%', top: '76%' },
    { left: '34%', top: '26%' },
  ]
  const max = Math.max(...attackTypeWords.value.map((item) => item[1]), 1)

  return attackTypeWords.value.map(([label, count], idx) => ({
    label,
    size: 12 + Math.round((count / max) * 12),
    weight: 520 + Math.round((count / max) * 260),
    left: slots[idx]?.left || `${10 + (idx * 7) % 80}%`,
    top: slots[idx]?.top || `${8 + (idx * 12) % 75}%`,
    rotate: idx % 3 === 0 ? -9 : idx % 3 === 1 ? 0 : 9,
  }))
})

function getChainStatus(key: string): boolean {
  return props.payload.chain_status[key] ?? false
}
</script>

<template>
  <aside class="min-h-0 overflow-hidden pr-1">
    <ScrollArea class="h-full">
      <div class="space-y-3 pr-2">
        <TechCard title="态势摘要" :icon="Activity" glow-color="cyan">
          <div class="space-y-1.5">
            <div class="grid grid-cols-2 gap-1.5">
              <div v-for="item in metricCards" :key="item.key" class="rounded-md border border-border/60 bg-muted/20 px-2 py-1.5">
                <p class="text-[10px] tracking-wide text-muted-foreground">{{ item.label }}</p>
                <p class="text-sm font-semibold leading-4" :class="item.color">{{ item.value || 0 }}</p>
              </div>
            </div>
          </div>
        </TechCard>

        <TechCard title="实时攻击趋势" glow-color="cyan">
          <div class="h-36">
            <Line v-if="payload.trends.labels.length" :data="trendData" :options="trendOptions" />
            <Skeleton v-else-if="loading" class="h-full w-full" />
            <div v-else class="h-full flex items-center justify-center text-sm text-muted-foreground">暂无趋势数据</div>
          </div>
        </TechCard>

        <TechCard title="热门攻击服务" glow-color="orange">
          <div class="h-36">
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

          <div class="attack-cloud mt-2" aria-label="攻击类型词云">
            <span
              v-for="word in cloudWords"
              :key="word.label"
              class="attack-cloud__item"
              :style="{
                left: word.left,
                top: word.top,
                fontSize: `${word.size}px`,
                fontWeight: `${word.weight}`,
                transform: `rotate(${word.rotate}deg)`,
              }"
            >
              {{ word.label }}
            </span>
          </div>
        </TechCard>

        <TechCard title="防御链路状态" glow-color="green">
          <div class="space-y-1.5">
            <div v-for="item in chainItems" :key="item.key" class="flex items-center justify-between">
              <span class="text-sm text-muted-foreground">{{ item.label }}</span>
              <span v-if="getChainStatus(item.key)" class="text-xs text-emerald-400">运行中</span>
              <span v-else class="text-xs text-slate-500">未启用</span>
            </div>
          </div>
        </TechCard>
      </div>
    </ScrollArea>
  </aside>
</template>

<style scoped>
.attack-cloud {
  position: relative;
  height: 130px;
  border-radius: 10px;
  border: 1px solid rgb(34 211 238 / 0.2);
  background: radial-gradient(circle at 45% 45%, rgb(8 145 178 / 0.2), transparent 62%);
  overflow: hidden;
}

.attack-cloud__item {
  position: absolute;
  color: rgb(125 211 252 / 0.95);
  text-shadow: 0 0 10px rgb(8 145 178 / 0.35);
  white-space: nowrap;
}
</style>
