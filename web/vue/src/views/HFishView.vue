<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { use }    from 'echarts/core'
import { CanvasRenderer }  from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import {
  GridComponent, TitleComponent, TooltipComponent,
  LegendComponent, DataZoomComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import { api, apiCall } from '@/api/index'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { 
  RefreshCw, 
  RotateCw, 
  Search, 
  Earth, 
  PieChart as PieChartIcon, 
  LayoutGrid, 
  List, 
  Globe,
  Settings2,
  XCircle,
  AlertTriangle
} from 'lucide-vue-next'

use([CanvasRenderer, BarChart, PieChart, GridComponent, TitleComponent,
     TooltipComponent, LegendComponent, DataZoomComponent])

const loading   = ref(false)
const logs      = ref<any[]>([])
const pieLogs   = ref<any[]>([])
const stats     = ref({ total_attacks: 0 })
const services  = ref<string[]>([])
const search    = ref('')
const svcFilter = ref<string>("ALL")

// Nmap host dialog
const nmapDialog = ref(false)
const nmapIp     = ref('')
const nmapHost   = ref<any>(null)

const headers = ['攻击 IP', '归属地', '服务类型', '端口', '时间']

const filteredLogs = computed(() => {
  let result = logs.value
  if (search.value) {
    const s = search.value.toLowerCase()
    result = result.filter(l => 
      (l.attack_ip || '').toLowerCase().includes(s) || 
      (l.ip_location || '').toLowerCase().includes(s) ||
      (l.service_name || '').toLowerCase().includes(s)
    )
  }
  return result
})

function normalizeLogs(payload: unknown): any[] {
  if (Array.isArray(payload)) return payload
  if (payload && typeof payload === 'object') {
    const obj = payload as { items?: unknown }
    if (Array.isArray(obj.items)) return obj.items
  }
  return []
}

// ── ECharts options ──────────────────────────────────────────────────────
const CHART_THEME = {
  textStyle: { color: 'rgba(255,255,255,.7)', fontFamily: 'inherit' },
  backgroundColor: 'transparent',
}
const locationBarOption = computed(() => {
  const counter: Record<string, number> = {}
  for (const log of logs.value) {
    const ip = log.attack_ip || '未知'
    counter[ip] = (counter[ip] ?? 0) + (Number(log.attack_count) || 1)
  }
  const sorted = Object.entries(counter).sort((a, b) => b[1] - a[1]).slice(0, 15)
  return {
    ...CHART_THEME,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '8%', bottom: '3%', top: '5%', containLabel: true },
    xAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(255,255,255,.06)' } }, axisLabel: { color: '#64748b' } },
    yAxis: {
      type: 'category',
      data: sorted.map(x => x[0]).reverse(),
      axisLabel: { fontSize: 11, color: '#94a3b8' }
    },
    series: [{
      type: 'bar',
      data: sorted.map(x => x[1]).reverse(),
      itemStyle: {
        borderRadius: [0, 4, 4, 0],
        color: { type: 'linear', x: 0, y: 0, x2: 1, y2: 0,
          colorStops: [{ offset: 0, color: '#8B5CF6' }, { offset: 1, color: '#00E5FF' }] }
      },
      label: { show: true, position: 'right', fontSize: 10, color: '#94a3b8' }
    }]
  }
})

const servicePieOption = computed(() => {
  const counter: Record<string, number> = {}
  for (const log of pieLogs.value) {
    const svc = log.service_name || '未知'
    counter[svc] = (counter[svc] ?? 0) + (Number(log.attack_count) || 1)
  }
  const sorted = Object.entries(counter).sort((a, b) => b[1] - a[1]).slice(0, 8)
  const COLORS = ['#00E5FF','#8B5CF6','#F472B6','#10B981','#F59E0B','#3B82F6','#EF4444','#FCA5A5']
  return {
    ...CHART_THEME,
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'vertical', right: '0', top: 'center',
      textStyle: { color: '#94a3b8', fontSize: 10 } },
    series: [{
      type: 'pie',
      radius: ['50%', '80%'],
      center: ['35%', '50%'],
      data: sorted.map(([name, value], i) => ({
        name, value, itemStyle: { color: COLORS[i % COLORS.length] }
      })),
      label: { show: false },
      itemStyle: { borderRadius: 4, borderColor: '#0f172a', borderWidth: 2 }
    }]
  }
})

async function loadStats() {
  const d = await apiCall<any>(async () => await api.get<any>('/api/v1/defense/hfish/stats'))
  if (d) {
    const sd = d ?? {}
    stats.value.total_attacks = (sd.service_stats ?? []).reduce((a:number,s:any) => a + s.count, 0)
    services.value = (sd.service_stats ?? []).map((s:any) => s.name)
  }
}

async function loadLogs() {
  loading.value = true
  try {
    const url = `/api/v1/defense/hfish/logs?limit=5000${svcFilter.value !== 'ALL' ? '&service_name=' + encodeURIComponent(svcFilter.value) : ''}`
    const d = await api.get<any>(url)
    logs.value = normalizeLogs(d)
    pieLogs.value = logs.value
  } catch(e) { console.error(e) }
  loading.value = false
}

async function showNmap(ip: string) {
  nmapIp.value = ip
  nmapHost.value = null
  nmapDialog.value = true
  const d = await apiCall<any>(async () => await api.get<any>(`/api/nmap/host/${ip}`))
  nmapHost.value = d ?? null
}

async function manualSync() {
  loading.value = true
  const ok = await apiCall(async () => {
    await api.post('/api/v1/defense/hfish/sync', {})
    loadStats()
    loadLogs()
  }, { errorMsg: '同步失败' })
  if (ok) {
    await loadStats()
    await loadLogs()
  }
  loading.value = false
}

watch([svcFilter], loadLogs)
onMounted(() => { loadStats(); loadLogs() })
</script>

<template>
  <div class="p-6 space-y-6">
    <!-- Stats Bar -->
    <Card class="bg-blue-500/5 border-blue-500/10 border-l-[4px] border-l-blue-500">
      <CardContent class="p-5 flex justify-between items-center">
        <div>
          <p class="text-xs font-medium text-blue-400 uppercase tracking-wider mb-1">攻击日志总数</p>
          <h2 class="text-4xl font-bold tracking-tight text-blue-500">{{ stats.total_attacks }}</h2>
        </div>
        <Button variant="outline" size="sm" @click="manualSync" :disabled="loading" class="bg-blue-500/10 border-blue-500/20 text-blue-400 hover:bg-blue-500 hover:text-white transition-all">
          <RotateCw v-if="loading" class="mr-2 h-4 w-4 animate-spin" />
          <RefreshCw v-else class="mr-2 h-4 w-4" />
          手动同步
        </Button>
      </CardContent>
    </Card>

    <!-- Charts row -->
    <div class="grid grid-cols-1 md:grid-cols-12 gap-6" v-if="logs.length">
      <Card class="md:col-span-7 bg-card/40 border border-border/50">
        <CardHeader class="pb-2">
          <CardTitle class="text-[15px] font-semibold flex items-center gap-2">
            <Globe class="h-4 w-4 text-primary" />
            攻击来源 Top 15（IP）
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div class="h-[300px]">
            <VChart :option="locationBarOption" autoresize />
          </div>
        </CardContent>
      </Card>
      <Card class="md:col-span-5 bg-card/40 border border-border/50">
        <CardHeader class="pb-2">
          <CardTitle class="text-[15px] font-semibold flex items-center gap-2">
            <PieChartIcon class="h-4 w-4 text-primary" />
            攻击服务分布
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div class="h-[300px]">
            <VChart :option="servicePieOption" autoresize />
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- Table Card -->
    <Card class="bg-card/40 border border-border/50">
      <CardHeader class="pb-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div class="flex items-center gap-4">
          <CardTitle class="text-lg font-bold">攻击记录明细</CardTitle>
        </div>
        <div class="flex items-center gap-3">
          <div class="relative w-64">
            <Search class="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input v-model="search" placeholder="搜索攻击 IP 或服务" class="pl-9 h-9 bg-black/20" />
          </div>
          <Select v-model="svcFilter">
            <SelectTrigger class="w-40 h-9 bg-black/20">
              <SelectValue placeholder="服务类型" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">全部服务</SelectItem>
              <SelectItem v-for="s in services" :key="s" :value="s">{{ s }}</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="ghost" size="icon" @click="loadLogs" :disabled="loading">
            <RefreshCw class="h-4 w-4" :class="{ 'animate-spin': loading }" />
          </Button>
        </div>
      </CardHeader>
      <CardContent class="p-0">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-muted/20 border-b border-border/50 text-muted-foreground">
                <th v-for="h in headers" :key="h" class="text-left py-3 px-4 font-semibold uppercase text-[11px] tracking-wider">{{ h }}</th>
              </tr>
            </thead>
            <tbody>
              <template v-if="loading">
                <tr v-for="i in 5" :key="i" class="border-b border-border/20 last:border-0">
                  <td v-for="j in headers.length" :key="j" class="py-4 px-4"><Skeleton class="h-4 w-full" /></td>
                </tr>
              </template>
              <template v-else-if="filteredLogs.length">
                <tr v-for="(item, idx) in filteredLogs" :key="idx" class="border-b border-border/10 last:border-0 hover:bg-white/5 transition-colors">
                  <td class="py-3 px-4">
                    <button @click="showNmap(item.attack_ip)" class="text-primary hover:underline font-medium">{{ item.attack_ip || '-' }}</button>
                  </td>
                  <td class="py-3 px-4 text-slate-400 font-medium">{{ item.ip_location || '未知' }}</td>
                  <td class="py-3 px-4">
                    <Badge variant="outline" class="border-primary/20 text-primary">{{ item.service_name || '-' }}</Badge>
                  </td>
                  <td class="py-3 px-4 text-slate-400 font-mono">{{ item.service_port || '-' }}</td>
                  <td class="py-3 px-4 text-slate-500 text-xs">{{ item.create_time_str }}</td>
                </tr>
              </template>
              <tr v-else>
                <td :colspan="headers.length" class="py-20 text-center text-muted-foreground italic">暂无满足条件的攻击记录</td>
              </tr>
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>

    <!-- Nmap Dialog -->
    <Dialog v-model:open="nmapDialog">
      <DialogContent class="sm:max-w-[560px] bg-slate-900 border-white/10 text-slate-100">
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2 text-xl">
            <Settings2 class="h-5 w-5 text-primary" />
            扫描信息 - {{ nmapIp }}
          </DialogTitle>
        </DialogHeader>
        
        <div v-if="nmapHost" class="space-y-6 pt-4">
          <div class="grid grid-cols-2 gap-4">
            <div class="space-y-1">
              <p class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">当前状态</p>
              <Badge :variant="nmapHost.state === 'up' ? 'default' : 'secondary'" 
                     :class="nmapHost.state === 'up' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : ''">
                {{ nmapHost.state === 'up' ? '在线' : '离线' }}
              </Badge>
            </div>
            <div class="space-y-1 text-right">
              <p class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">主机名</p>
              <p class="font-medium">{{ nmapHost.hostname || '-' }}</p>
            </div>
          </div>

          <div class="p-4 bg-black/30 rounded-xl border border-white/5 grid grid-cols-1 gap-4">
            <div class="flex justify-between items-center text-sm">
              <span class="text-slate-400">MAC 地址</span>
              <span class="font-mono">{{ nmapHost.mac_address || '-' }}</span>
            </div>
            <div class="border-t border-white/5 pt-2 flex justify-between items-center text-sm">
              <span class="text-slate-400">厂商信息</span>
              <span>{{ nmapHost.vendor || '-' }}</span>
            </div>
            <div class="border-t border-white/5 pt-2 flex justify-between items-center text-sm">
              <span class="text-slate-400">操作系统</span>
              <span class="flex items-center gap-1.5 font-medium"><Globe class="h-3.5 w-3.5 text-primary" /> {{ nmapHost.os_type || '-' }}</span>
            </div>
          </div>

          <div v-if="nmapHost.services?.length" class="space-y-3">
            <h4 class="text-sm font-semibold flex items-center gap-2">
              <LayoutGrid class="h-4 w-4 text-primary" />
              开放端口
            </h4>
            <div class="rounded-xl border border-white/5 overflow-hidden">
              <table class="w-full text-xs">
                <thead class="bg-white/5">
                  <tr class="text-slate-500">
                    <th class="py-2.5 px-4 text-left font-medium">端口</th>
                    <th class="py-2.5 px-4 text-left font-medium">协议</th>
                    <th class="py-2.5 px-4 text-left font-medium text-right">服务名称</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-white/5">
                  <tr v-for="s in nmapHost.services" :key="s.port" class="hover:bg-white/5 px-4">
                    <td class="py-2.5 px-4 font-bold text-primary">{{ s.port }}</td>
                    <td class="py-2.5 px-4 uppercase text-slate-500">TCP</td>
                    <td class="py-2.5 px-4 text-right">
                      <Badge variant="outline" class="border-white/10 text-slate-300 font-normal">{{ s.service }}</Badge>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <div v-else class="py-12 flex flex-col items-center justify-center gap-3 text-slate-500 italic">
          <XCircle class="h-10 w-10 opacity-20" />
          未找到该 IP 的扫描记录
        </div>

        <div class="flex justify-end pt-4">
          <Button variant="secondary" @click="nmapDialog = false">关闭窗口</Button>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>

<style scoped>
.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
