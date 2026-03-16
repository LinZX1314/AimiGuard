<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api, apiCall } from '@/api/index'
import { useRouter } from 'vue-router'
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
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Progress } from '@/components/ui/progress'
import { Separator } from '@/components/ui/separator'
import { Pagination } from '@/components/ui/pagination'
import {
  Radar,
  RefreshCw,
  Search,
  Info,
  Bot,
  ShieldCheck,
  CheckCircle2,
  Monitor,
  Cpu,
  Network,
  Activity,
  History,
  Server,
  XCircle,
  PackageSearch
} from 'lucide-vue-next'

const router = useRouter()
const loading  = ref(false)
const scanning = ref(false)
const hosts    = ref<any[]>([])
const scans    = ref<any[]>([])
const stats    = ref({ online: 0 })
const search   = ref('')
const vendorFlt= ref<string>("ALL")
const currentScanId = ref<string>("NONE")

// Pagination
const page     = ref(1)
const pageSize = ref(50)
const total    = ref(0)

// Host detail dialog
const detailDlg = ref(false)
const detailHost= ref<any>(null)

const headers = ['IP 地址', 'MAC / 状态', '主机名', '厂商 / 系统', '开放端口', '操作']

const scanItems = computed(() =>
  scans.value.map(s => ({ id: String(s.id), label: `#${s.id} – ${s.scan_time?.slice(0,16) ?? ''}` }))
)

const vendorOptions = computed(() =>
  [...new Set(hosts.value.map(h => h.vendor).filter(Boolean))]
)

const filteredHosts = computed(() => {
  let result = hosts.value
  if (search.value) {
    const s = search.value.toLowerCase()
    result = result.filter(h => 
      (h.ip || '').toLowerCase().includes(s) || 
      (h.hostname || '').toLowerCase().includes(s) ||
      (h.vendor || '').toLowerCase().includes(s)
    )
  }
  if (vendorFlt.value !== "ALL") {
    result = result.filter(h => h.vendor === vendorFlt.value)
  }
  return result
})

async function loadScans() {
  const d = await apiCall<any>(async () => await api.get<any>('/api/nmap/scans'))
  if (d) {
    scans.value = Array.isArray(d) ? d : (d.data ?? [])
    if (scans.value.length) currentScanId.value = String(scans.value[0].id)
  }
}

async function loadHosts() {
  if (currentScanId.value === "NONE") return
  loading.value = true
  const d = await apiCall<any>(async () => {
    let url = `/api/nmap/hosts?page=${page.value}&page_size=${pageSize.value}&scan_id=${currentScanId.value}`
    return await api.get<any>(url)
  })
  if (d) {
    hosts.value = d.items ?? (Array.isArray(d) ? d : (d.data ?? []))
    total.value = d.total ?? hosts.value.length
    const online = hosts.value.filter(h => h.state === 'up')
    stats.value.online = online.length
  }
  loading.value = false
}

const scanProgress = ref(0)
const scanStatus   = ref('')   // '' | 'pending' | 'running' | 'done' | 'error'
let progressTimer: ReturnType<typeof setInterval>

function startProgressPoll() {
  scanProgress.value = 0
  scanStatus.value   = 'pending'
  let pct = 0
  progressTimer = setInterval(async () => {
    pct = Math.min(pct + Math.random() * 8 + 3, 95)
    scanProgress.value = Math.round(pct)
    try {
      const d = await api.get<any>('/api/nmap/scans')
      const latest = (Array.isArray(d) ? d : (d.data ?? []))[0]
      if (latest && String(scans.value[0]?.id) !== String(latest.id)) {
        stopProgressPoll(true)
        await loadScans(); await loadHosts()
      }
    } catch { /* ignore */ }
  }, 1200)
}

function stopProgressPoll(success = false) {
  clearInterval(progressTimer)
  scanProgress.value = success ? 100 : 0
  scanStatus.value   = success ? 'done' : ''
  scanning.value     = false
  if (success) setTimeout(() => { scanStatus.value = ''; scanProgress.value = 0 }, 2000)
}

async function startScan() {
  scanning.value = true
  try {
    await api.post('/api/nmap/scan', {})
    startProgressPoll()
  } catch(e) {
    console.error(e)
    scanStatus.value = 'error'
    scanning.value   = false
  }
}

async function openDetail(host: any) {
  detailHost.value = host
  detailDlg.value = true
}

function analyzeWithAi(host: any) {
  detailDlg.value = false
  router.push({
    path: '/ai',
    query: {
      context_type: 'host',
      context_id: host.ip
    }
  })
}

onUnmounted(() => clearInterval(progressTimer))
onMounted(async () => { await loadScans(); if (currentScanId.value !== "NONE") await loadHosts() })
</script>

<template>
  <div class="p-6 space-y-6">
    <!-- Controls Card -->
    <Card class="bg-card/40 border border-border/50">
      <CardContent class="p-5 flex flex-col gap-4">
        <div class="flex flex-wrap items-center gap-4">
          <div class="flex items-center gap-2">
            <span class="text-xs font-semibold text-muted-foreground uppercase tracking-widest">扫描历史:</span>
            <Select v-model="currentScanId" @update:model-value="loadHosts">
              <SelectTrigger class="w-64 bg-black/20 h-10 border-border/40">
                <SelectValue placeholder="选择扫描记录" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem v-for="s in scanItems" :key="s.id" :value="s.id">{{ s.label }}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Button @click="startScan" :disabled="scanning" class="bg-primary hover:bg-primary/90 shadow-lg shadow-primary/10">
            <Radar :size="16" class="mr-2" :class="{ 'animate-pulse': scanning }" />
            手动扫描
          </Button>

          <div class="flex-1"></div>

          <div class="flex items-center gap-4 bg-emerald-500/5 px-4 py-1.5 rounded-full border border-emerald-500/10">
            <span class="text-xs font-medium text-emerald-400">在线主机</span>
            <span class="text-sm font-bold text-emerald-500">{{ stats.online }}</span>
          </div>
        </div>

        <!-- Progress bar -->
        <div v-if="scanning || scanStatus === 'done'" class="animate-in slide-in-from-top-2">
          <Separator class="bg-border/30 mb-4" />
          <div class="space-y-2">
            <div class="flex justify-between items-center text-xs">
              <span class="text-muted-foreground font-medium flex items-center gap-2">
                <Activity :size="14" class="animate-spin" v-if="scanning" />
                <CheckCircle2 :size="14" class="text-emerald-500" v-else />
                {{ scanStatus === 'done' ? '全网段扫描完成' : '正在探测活跃主机中...' }}
              </span>
              <span class="font-mono">{{ scanProgress }}%</span>
            </div>
            <Progress :model-value="scanProgress" class="h-2 bg-muted/30" />
          </div>
        </div>
      </CardContent>
    </Card>

    <!-- Results Table Card -->
    <Card class="bg-card/40 border border-border/50">
      <CardHeader class="pb-4 flex flex-row items-center justify-between border-b border-border/20">
        <div class="flex items-center gap-3">
          <div class="bg-primary/10 p-2 rounded-lg">
            <Network :size="20" class="text-primary" />
          </div>
          <CardTitle class="text-lg">网络探测结果</CardTitle>
        </div>
        <Button variant="ghost" size="icon" @click="loadHosts" :disabled="loading">
          <RefreshCw :size="16" :class="{ 'animate-spin': loading }" />
        </Button>
      </CardHeader>
      
      <CardContent class="p-0">
        <div class="p-4 flex flex-wrap gap-4 border-b border-border/10">
          <div class="relative w-64">
            <Search :size="16" class="absolute left-2.5 top-2.5 text-muted-foreground" />
            <Input v-model="search" placeholder="搜索 IP、主机名..." class="pl-9 h-9 bg-black/20" />
          </div>
          <Select v-model="vendorFlt">
            <SelectTrigger class="w-48 h-9 bg-black/20 text-xs">
              <SelectValue placeholder="厂商过滤" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">全部厂商</SelectItem>
              <SelectItem v-for="v in vendorOptions" :key="v" :value="v">{{ v }}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-muted/10 text-muted-foreground border-b border-border/20">
              <tr>
                <th v-for="h in headers" :key="h" class="text-left py-3 px-4 font-semibold text-[11px] tracking-widest uppercase">{{ h }}</th>
              </tr>
            </thead>
            <tbody>
              <template v-if="loading">
                <tr v-for="i in 5" :key="i" class="border-b border-border/10">
                  <td v-for="j in headers.length" :key="j" class="py-4 px-4"><div class="h-4 w-full bg-muted/40 animate-pulse rounded"></div></td>
                </tr>
              </template>
              <template v-else-if="filteredHosts.length">
                <tr v-for="h in filteredHosts" :key="h.id" class="border-b hover:bg-white/5 transition-colors">
                  <td class="py-3 px-4">
                    <div class="flex items-center gap-2">
                      <div class="h-2 w-2 rounded-full" :class="h.state === 'up' ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.4)]' : 'bg-slate-600'"></div>
                      <span class="font-bold text-slate-200">{{ h.ip }}</span>
                    </div>
                  </td>
                  <td class="py-3 px-4">
                    <div class="flex flex-col gap-0.5">
                      <span class="text-xs font-mono text-slate-400">{{ h.mac_address || '未知 MAC' }}</span>
                      <Badge variant="outline" class="w-fit text-[10px] h-4 px-1 py-0 bg-black/20">
                        {{ h.state === 'up' ? 'ONLINE' : 'OFFLINE' }}
                      </Badge>
                    </div>
                  </td>
                  <td class="py-3 px-4 text-slate-300 font-medium">{{ h.hostname || '-' }}</td>
                  <td class="py-3 px-4">
                    <div class="flex flex-col gap-0.5">
                      <span class="text-xs text-primary/80 font-medium">{{ h.vendor || '-' }}</span>
                      <span class="text-[11px] text-slate-500 uppercase tracking-tighter">{{ h.os_type || '-' }}</span>
                    </div>
                  </td>
                  <td class="py-3 px-4">
                    <div class="max-w-[200px] truncate text-xs text-slate-400 font-mono" :title="h.open_ports?.join(', ')">
                      {{ Array.isArray(h.open_ports) ? h.open_ports.join(', ') : h.open_ports || '-' }}
                    </div>
                  </td>
                  <td class="py-3 px-4">
                    <Button variant="ghost" size="icon" @click="openDetail(h)" class="h-8 w-8 text-slate-400 hover:text-primary hover:bg-primary/10">
                      <Info class="h-4 w-4" />
                    </Button>
                  </td>
                </tr>
              </template>
              <tr v-else>
                <td :colspan="headers.length" class="py-20 text-center text-muted-foreground italic bg-muted/5">暂无探测到的主机记录</td>
              </tr>
            </tbody>
          </table>
        </div>
        <Pagination v-model:page="page" v-model:page-size="pageSize" :total="total" @update:page="loadHosts" @update:page-size="loadHosts" />
      </CardContent>
    </Card>

    <!-- Detail Dialog -->
    <Dialog v-model:open="detailDlg">
      <DialogContent class="sm:max-w-[600px] bg-slate-900 border-white/10 text-slate-100 p-0 overflow-hidden">
        <div class="p-6 bg-gradient-to-r from-slate-900 to-indigo-900/20 border-b border-white/5">
          <DialogTitle class="flex items-center gap-3 text-2xl">
            <div class="h-10 w-10 flex items-center justify-center bg-primary/20 rounded-xl">
              <Server class="h-6 w-6 text-primary" />
            </div>
            <div>
              <p class="text-[10px] uppercase tracking-widest text-primary/70 font-bold mb-0.5">主机资产详情</p>
              <h2 class="font-bold">{{ detailHost?.ip }}</h2>
            </div>
          </DialogTitle>
        </div>
        
        <ScrollArea class="max-h-[60vh]">
          <div v-if="detailHost" class="p-6 space-y-6">
            <div class="grid grid-cols-2 gap-4">
              <div class="space-y-4">
                <div class="space-y-1">
                  <div class="flex items-center gap-2 text-slate-500 text-[10px] uppercase tracking-wider font-bold">
                    <Activity class="h-3 w-3" /> 网络状态
                  </div>
                  <Badge :variant="detailHost.state === 'up' ? 'default' : 'secondary'" class="bg-emerald-500/20 text-emerald-400 border-emerald-500/10">
                    {{ detailHost.state === 'up' ? '在线' : '离线' }}
                  </Badge>
                </div>
                <div class="space-y-1 text-xs">
                  <div class="flex items-center gap-2 text-slate-500 text-[10px] uppercase tracking-wider font-bold">
                    <History class="h-3 w-3" /> 厂商信息
                  </div>
                  <p class="font-medium text-slate-200">{{ detailHost.vendor || '-' }}</p>
                </div>
              </div>
              <div class="space-y-4">
                <div class="space-y-1 text-right">
                  <div class="flex items-center justify-end gap-2 text-slate-500 text-[10px] uppercase tracking-wider font-bold">
                    主机名 <Monitor class="h-3 w-3" />
                  </div>
                  <p class="font-medium text-slate-200">{{ detailHost.hostname || '-' }}</p>
                </div>
                <div class="space-y-1 text-right text-xs">
                  <div class="flex items-center justify-end gap-2 text-slate-500 text-[10px] uppercase tracking-wider font-bold">
                    操作系统 <Cpu class="h-3 w-3" />
                  </div>
                  <p class="font-medium text-slate-200">{{ detailHost.os_type || '-' }} ({{ detailHost.os_accuracy }}%)</p>
                </div>
              </div>
            </div>

            <div class="p-4 bg-black/40 rounded-xl border border-white/5 space-y-3 font-mono text-[13px]">
              <div class="flex justify-between">
                <span class="text-slate-500">MAC 地址:</span>
                <span class="text-slate-200">{{ detailHost.mac_address || '-' }}</span>
              </div>
              <div class="flex justify-between border-t border-white/5 pt-2">
                <span class="text-slate-500">OS 标签:</span>
                <span class="text-slate-200 text-xs">{{ detailHost.os_tags || '-' }}</span>
              </div>
            </div>

            <div v-if="detailHost.services?.length" class="space-y-3">
              <h4 class="text-sm font-semibold flex items-center gap-2 text-primary">
                <PackageSearch class="h-4 w-4" /> 开放服务与版本
              </h4>
              <div class="rounded-xl border border-white/5 overflow-hidden">
                <table class="w-full text-xs">
                  <thead class="bg-white/5">
                    <tr class="text-slate-500">
                      <th class="py-2 px-4 text-left font-medium">端口/协议</th>
                      <th class="py-2 px-4 text-left font-medium">服务</th>
                      <th class="py-2 px-4 text-right font-medium">应用版本</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-white/5">
                    <tr v-for="s in detailHost.services" :key="s.port" class="hover:bg-white/5">
                      <td class="py-2.5 px-4"><span class="font-bold text-primary">{{ s.port }}</span> <span class="text-slate-600 ml-1">TCP</span></td>
                      <td class="py-2.5 px-4 font-medium">{{ s.service }}</td>
                      <td class="py-2.5 px-4 text-right">
                        <Badge variant="outline" class="border-white/10 text-slate-400 font-normal py-0">
                          {{ s.product || '-' }} {{ s.version }}
                        </Badge>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </ScrollArea>

        <div class="p-6 bg-slate-900/50 border-t border-white/5 flex flex-wrap justify-between gap-3">
          <Button variant="secondary" @click="detailDlg = false" class="bg-white/5 border-white/10 hover:bg-white/10">关闭</Button>
          <Button @click="analyzeWithAi(detailHost)" class="bg-primary hover:bg-primary/90 text-primary-foreground font-semibold">
            <Bot class="mr-2 h-4 w-4" /> AI 深度安全性分析
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>
