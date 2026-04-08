<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api, apiCall, getToken } from '@/api/index'
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
  Trash2,
  Bot,
  CheckCircle2,
  Monitor,
  Cpu,
  Network,
  Activity,
  History,
  Server,
  PackageSearch,
  Camera,
  X,
  ExternalLink,
} from 'lucide-vue-next'

const router = useRouter()
const currentTab = ref<'hosts' | 'screenshots'>('hosts')
const loading  = ref(false)
const scanning = ref(false)
const hosts    = ref<any[]>([])
const scans    = ref<any[]>([])
const stats    = ref({ online: 0 })
const search   = ref('')
const vendorFlt= ref<string>("ALL")
const currentScanId = ref<string>("NONE")

// 探测地址配置
const probeIps = ref<string[]>([])
const probeIpPorts = ref<Record<string, number[]>>({})
const probeIpHostnames = ref<Record<string, string>>({})

// Pagination
const page     = ref(1)
const pageSize = ref(50)
const total    = ref(0)

// Host detail dialog
const detailDlg = ref(false)
const detailHost= ref<any>(null)
const detailScreenshots = ref<any[]>([])
const screenshotDlg = ref(false)
const screenshotImg = ref('')
const screenshotTitle = ref('')
const takingScreenshot = ref(false)

// Screenshot gallery state
const galleryScreenshots = ref<any[]>([])
const galleryLoading = ref(false)
const gallerySearch = ref('')
const galleryPreviewDlg = ref(false)
const galleryPreviewImg = ref('')
const galleryPreviewTitle = ref('')

// 探测地址配置弹窗
const probeIpDlg = ref(false)
const probeIpInput = ref('')
const probeIpPortsInput = ref('')

const filteredGalleryScreenshots = computed(() => {
  if (!gallerySearch.value) return galleryScreenshots.value
  const s = gallerySearch.value.toLowerCase()
  return galleryScreenshots.value.filter(sh =>
    (sh.ip || '').toLowerCase().includes(s) ||
    (sh.url || '').toLowerCase().includes(s) ||
    String(sh.port).includes(s)
  )
})

const headers = ['IP 地址', '主机名', '开放端口', '操作']

const scanItems = computed(() =>
  scans.value.map(s => ({ id: String(s.id), label: `#${s.id} 扫描 ${s.scan_time?.slice(0,16) ?? ''}` }))
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
    let realHosts = d.items ?? (Array.isArray(d) ? d : (d.data ?? []))
    total.value = d.total ?? realHosts.length

    // 合并探测地址到主机列表
    if (probeIps.value.length > 0) {
      const probeHosts = probeIps.value.map(ip => ({
        id: `probe_${ip}`,
        ip: ip,
        hostname: probeIpHostnames.value[ip] || '',
        state: 'up',
        vendor: '',
        open_ports: probeIpPorts.value[ip] || [80, 443],
        mac_address: '',
        os_type: 'Unknown',
        os_accuracy: 0,
        os_tags: 'unknown'
      }))
      realHosts = [...realHosts, ...probeHosts]
      total.value += probeHosts.length
    }

    hosts.value = realHosts
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

async function clearScanHistory() {
  if (!window.confirm('确认清理全部扫描历史吗？该操作不可恢复。')) {
    return
  }

  const done = await apiCall(async () => api.post('/api/nmap/scans/clear', {}))
  if (!done) {
    return
  }

  scans.value = []
  currentScanId.value = 'NONE'
  hosts.value = []
  total.value = 0
  page.value = 1
  stats.value.online = 0
}

function buildServicesFallback(host: any) {
  const services = Array.isArray(host?.services) ? host.services : []
  if (services.length > 0) {
    return services
  }
  const openPorts = Array.isArray(host?.open_ports) ? host.open_ports : []
  return openPorts.map((port: any) => ({
    port,
    service: 'unknown',
    product: '-',
    version: '',
  }))
}

async function openDetail(host: any) {
  detailHost.value = {
    ...host,
    services: buildServicesFallback(host),
  }
  detailDlg.value = true
  detailScreenshots.value = []

  const ip = host?.ip
  if (!ip) return

  const detail = await apiCall<any>(async () =>
    api.get<any>(`/api/nmap/host/${encodeURIComponent(ip)}?scan_id=${encodeURIComponent(currentScanId.value)}`)
  , { silent: true })

  if (detail) {
    detailHost.value = {
      ...detail,
      services: buildServicesFallback(detail),
    }
  }

  // 加载截图
  const shots = await apiCall<any[]>(async () =>
    api.get<any[]>(`/api/nmap/screenshots/${encodeURIComponent(ip)}`)
  , { silent: true })
  if (shots && Array.isArray(shots)) {
    detailScreenshots.value = shots
  }
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

function getScreenshotUrl(ip: string, port: number, fresh = false) {
  const token = getToken() || ''
  const base = `/api/nmap/screenshot/${encodeURIComponent(ip)}/${port}?token=${encodeURIComponent(token)}`
  return fresh ? `${base}&t=${Date.now()}` : base
}

function viewScreenshot(ip: string, port: number, title?: string) {
  screenshotImg.value = getScreenshotUrl(ip, port, true)
  screenshotTitle.value = title || `${ip}:${port}`
  screenshotDlg.value = true
}

async function takeScreenshot(ip: string, port: number, url: string) {
  takingScreenshot.value = true
  try {
    // 直接调用截图 API，传递当前扫描编号
    await api.post('/api/nmap/screenshot', { ip, port, url, scan_id: currentScanId.value })
    // 刷新截图列表
    const shots = await apiCall<any[]>(async () =>
      api.get<any[]>(`/api/nmap/screenshots/${encodeURIComponent(ip)}`)
    , { silent: true })
    if (shots && Array.isArray(shots)) {
      detailScreenshots.value = shots
    }
  } catch (e) {
    console.error('截图失败', e)
  } finally {
    takingScreenshot.value = false
  }
}

// Screenshot gallery functions
async function loadGalleryScreenshots() {
  galleryLoading.value = true
  const d = await apiCall<any>(async () =>
    api.get<any>('/api/nmap/screenshots/all')
  )
  if (d) {
    galleryScreenshots.value = Array.isArray(d) ? d : (d?.data ?? [])
  }
  galleryLoading.value = false
}

function viewGalleryScreenshot(sh: any) {
  galleryPreviewImg.value = getScreenshotUrl(sh.ip, sh.port)
  galleryPreviewTitle.value = `${sh.ip}:${sh.port} — ${sh.url || ''}`
  galleryPreviewDlg.value = true
}

// 探测地址配置函数
function loadProbeIpConfig() {
  try {
    const saved = localStorage.getItem('nmap_probe_ips')
    if (saved) {
      const data = JSON.parse(saved)
      probeIps.value = data.ips || []
      probeIpPorts.value = data.ports || {}
      probeIpHostnames.value = data.hostnames || {}
    }
  } catch {}
}

function openProbeIpDlg() {
  probeIpInput.value = probeIps.value.join(',')
  probeIpPortsInput.value = Object.entries(probeIpPorts.value)
    .map(([ip, ports]) => `${ip}:${(ports as number[]).join(',')}`)
    .join(';')
  probeIpDlg.value = true
}

function saveProbeIpConfig() {
  // 解析IP列表
  const ips = probeIpInput.value.split(',').map(s => s.trim()).filter(s => s)
  probeIps.value = ips

  // 解析端口配置
  const ports: Record<string, number[]> = {}
  const hostnames: Record<string, string> = {}
  const portLines = probeIpPortsInput.value.split(';')
  for (const line of portLines) {
    const parts = line.split(':').map(s => s.trim())
    const ip = parts[0]
    if (ip && parts[1]) {
      ports[ip] = parts[1].split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n))
    }
    if (ip && parts[2]) {
      hostnames[ip] = parts[2]
    }
  }
  probeIpPorts.value = ports
  probeIpHostnames.value = hostnames

  // 保存到 localStorage
  localStorage.setItem('nmap_probe_ips', JSON.stringify({
    ips: probeIps.value,
    ports: probeIpPorts.value,
    hostnames: probeIpHostnames.value
  }))

  probeIpDlg.value = false
  loadHosts()
}

onUnmounted(() => clearInterval(progressTimer))
onMounted(async () => {
  loadProbeIpConfig()
  await loadScans()
  if (currentScanId.value !== "NONE") await loadHosts()
})
</script>

<template>
  <div class="p-6 space-y-6">
    <!-- Controls Card -->
    <Card class="border-border/50">
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

          <Button
            variant="outline"
            @click="clearScanHistory"
            :disabled="scanning"
            class="border-destructive/40 text-destructive hover:bg-destructive/10"
          >
            <Trash2 :size="15" class="mr-2" />
            清理扫描历史
          </Button>

          <Button
            variant="outline"
            @click="openProbeIpDlg"
            class="border-primary/40 text-primary hover:bg-primary/10"
          >
            <Monitor :size="15" class="mr-2" />
            探测地址
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
                {{ scanStatus === 'done' ? '全网段扫描完成' : '正在探测活跃主机...' }}
              </span>
              <span class="font-mono">{{ scanProgress }}%</span>
            </div>
            <Progress :model-value="scanProgress" class="h-2 bg-muted/30" />
          </div>
        </div>
      </CardContent>
    </Card>

    <!-- Results Table Card -->
    <Card class="border-border/50">
      <CardHeader class="pb-4 flex flex-row items-center justify-between border-b border-border/20">
        <div class="flex items-center gap-3">
          <div class="bg-primary/10 p-2 rounded-lg">
            <Network :size="20" class="text-primary" />
          </div>
          <div class="flex items-center gap-2">
            <span class="px-3 py-1.5 text-sm font-medium rounded-md bg-primary/10 text-primary">网络探测结果</span>
          </div>
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
                      <span
                        class="font-bold text-foreground cursor-pointer hover:text-primary transition-colors"
                        @click="openDetail(h)"
                      >{{ h.ip }}</span>
                    </div>
                  </td>
                  <td class="py-3 px-4 text-foreground font-medium">{{ h.hostname || '-' }}</td>
                  <td class="py-3 px-4">
                    <div class="max-w-[200px] truncate text-xs text-muted-foreground font-mono" :title="h.open_ports?.join(', ')">
                      {{ Array.isArray(h.open_ports) ? h.open_ports.join(', ') : h.open_ports || '-' }}
                    </div>
                  </td>
                  <td class="py-3 px-4">
                    <Button variant="ghost" size="icon" @click="openDetail(h)" class="h-8 w-8 text-muted-foreground hover:text-primary hover:bg-primary/10">
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

    <!-- Gallery Preview Dialog -->
    <Dialog v-model:open="detailDlg">
      <DialogContent class="sm:max-w-[600px] bg-background border-border text-foreground p-0 overflow-hidden">
        <div class="p-6 bg-gradient-to-r from-muted/70 to-primary/10 border-b border-border/60">
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
                  <div class="flex items-center gap-2 text-muted-foreground text-[10px] uppercase tracking-wider font-bold">
                    <Activity class="h-3 w-3" /> 网络状态
                  </div>
                  <Badge :variant="detailHost.state === 'up' ? 'default' : 'secondary'" class="bg-emerald-500/20 text-emerald-400 border-emerald-500/10">
                    {{ detailHost.state === 'up' ? '在线' : '离线' }}
                  </Badge>
                </div>
                <div class="space-y-1 text-xs">
                  <div class="flex items-center gap-2 text-muted-foreground text-[10px] uppercase tracking-wider font-bold">
                    <History class="h-3 w-3" /> 厂商信息
                  </div>
                  <p class="font-medium text-foreground">{{ detailHost.vendor || '-' }}</p>
                </div>
              </div>
              <div class="space-y-4">
                <div class="space-y-1 text-right">
                  <div class="flex items-center justify-end gap-2 text-muted-foreground text-[10px] uppercase tracking-wider font-bold">
                    主机名 <Monitor class="h-3 w-3" />
                  </div>
                  <p class="font-medium text-foreground">{{ detailHost.hostname || '-' }}</p>
                </div>
                <div class="space-y-1 text-right text-xs">
                  <div class="flex items-center justify-end gap-2 text-muted-foreground text-[10px] uppercase tracking-wider font-bold">
                    操作系统 <Cpu class="h-3 w-3" />
                  </div>
                  <p class="font-medium text-foreground">{{ detailHost.os_type || '-' }} ({{ detailHost.os_accuracy }}%)</p>
                </div>
              </div>
            </div>

            <div class="p-4 bg-muted/40 rounded-xl border border-border/60 space-y-3 font-mono text-[13px]">
              <div class="flex justify-between">
                <span class="text-muted-foreground">MAC 地址:</span>
                <span class="text-foreground">{{ detailHost.mac_address || '未知 MAC' }}</span>
              </div>
              <div class="flex justify-between border-t border-border/60 pt-2">
                <span class="text-muted-foreground">OS 标签:</span>
                <span class="text-foreground text-xs">{{ detailHost.os_tags || '-' }}</span>
              </div>
            </div>

            <div v-if="detailHost.services?.length" class="space-y-3">
              <h4 class="text-sm font-semibold flex items-center gap-2 text-primary">
                <PackageSearch class="h-4 w-4" /> 开放服务与版本
              </h4>
              <div class="rounded-xl border border-border/60 overflow-hidden">
                <table class="w-full text-xs">
                  <thead class="bg-muted/40">
                    <tr class="text-muted-foreground">
                      <th class="py-2 px-4 text-left font-medium">端口/协议</th>
                      <th class="py-2 px-4 text-left font-medium">服务</th>
                      <th class="py-2 px-4 text-right font-medium">应用版本</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-border/60">
                    <tr v-for="s in detailHost.services" :key="s.port" class="hover:bg-muted/40">
                      <td class="py-2.5 px-4"><span class="font-bold text-primary">{{ s.port }}</span> <span class="text-muted-foreground ml-1">TCP</span></td>
                      <td class="py-2.5 px-4 font-medium">{{ s.service }}</td>
                      <td class="py-2.5 px-4 text-right">
                        <Badge variant="outline" class="border-border text-muted-foreground font-normal py-0">
                          {{ s.product || '-' }} {{ s.version }}
                        </Badge>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Web 截图区域 -->
            <div class="space-y-3">
              <div class="flex items-center justify-between">
                <h4 class="text-sm font-semibold flex items-center gap-2 text-primary">
                  <Camera class="h-4 w-4" /> Web 截图
                </h4>
              </div>

              <!-- 已有截图 -->
              <div v-if="detailScreenshots.length > 0" class="grid grid-cols-2 gap-3">
                <div
                  v-for="shot in detailScreenshots"
                  :key="shot.port"
                  class="relative rounded-xl border border-border/60 overflow-hidden cursor-pointer hover:border-primary/50 transition-colors group"
                  @click="viewScreenshot(detailHost.ip, shot.port, `${shot.url}`)"
                >
                  <img
                    :src="getScreenshotUrl(detailHost.ip, shot.port)"
                    :alt="`${detailHost.ip}:${shot.port}`"
                    class="w-full h-28 object-cover object-top bg-muted"
                    @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }"
                  />
                  <div class="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-2">
                    <div class="text-white text-[10px] font-medium truncate">{{ shot.port }}/{{ shot.url }}</div>
                  </div>
                  <div class="absolute top-1 left-1">
                    <Badge v-if="shot.scan_id" variant="secondary" class="bg-primary/70 text-white border-0 text-[10px] px-1.5 py-0">
                      #{{ shot.scan_id }}
                    </Badge>
                  </div>
                  <div class="absolute top-1 right-1">
                    <Badge variant="secondary" class="bg-black/50 text-white border-0 text-[10px] px-1.5 py-0">
                      :{{ shot.port }}
                    </Badge>
                  </div>
                </div>
              </div>

              <!-- 无截图时的提示 -->
              <div v-else class="rounded-xl border border-dashed border-border/60 p-6 text-center text-xs text-muted-foreground">
                暂无截图记录，扫描时将自动对 Web 服务进行截图
              </div>

              <!-- Web 服务截图入口 -->
              <div v-if="detailHost.services?.length" class="flex flex-wrap gap-2">
                <Button
                  v-for="svc in detailHost.services.filter((s: any) => [80, 443, 8080, 8443, 81, 8000, 8888].includes(Number(s.port)))"
                  :key="svc.port"
                  variant="outline"
                  size="sm"
                  class="h-7 text-xs gap-1"
                  :disabled="takingScreenshot"
                  @click="takeScreenshot(detailHost.ip, Number(svc.port), `${Number(svc.port) === 443 ? 'https' : 'http'}://${detailHost.ip}:${svc.port}`)"
                >
                  <Camera :size="12" :class="{ 'animate-pulse': takingScreenshot }" />
                  截图 {{ svc.port }}
                </Button>
              </div>
            </div>
          </div>
        </ScrollArea>

        <div class="p-6 bg-muted/30 border-t border-border/60 flex flex-wrap justify-between gap-3">
          <Button variant="secondary" @click="detailDlg = false" class="bg-muted border-border hover:bg-muted/70">关闭</Button>
          <Button @click="analyzeWithAi(detailHost)" class="bg-primary hover:bg-primary/90 text-primary-foreground font-semibold">
            <Bot class="mr-2 h-4 w-4" /> AI 深度安全性分析
          </Button>
        </div>
      </DialogContent>
    </Dialog>

    <!-- Screenshot Preview Dialog -->
    <Dialog v-model:open="screenshotDlg">
      <DialogContent class="sm:max-w-[900px] bg-background border-border text-foreground p-0 overflow-hidden max-h-[90vh] flex flex-col">
        <div class="p-4 bg-muted/50 border-b border-border/60 flex items-center justify-between">
          <DialogTitle class="text-sm font-semibold text-muted-foreground truncate flex-1 mr-4">{{ screenshotTitle }}</DialogTitle>
          <Button variant="ghost" size="icon" class="h-7 w-7 shrink-0" @click="screenshotDlg = false">
            <X class="h-4 w-4" />
          </Button>
        </div>
        <ScrollArea class="flex-1 bg-muted/10">
          <img
            v-if="screenshotImg"
            :src="screenshotImg"
            :alt="screenshotTitle"
            class="w-full h-auto"
          />
          <div v-else class="flex items-center justify-center h-64 text-muted-foreground text-sm">
            截图加载中...
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>

    <!-- Gallery Preview Dialog -->
    <Dialog v-model:open="galleryPreviewDlg">
      <DialogContent class="sm:max-w-[1000px] bg-background border-border text-foreground p-0 overflow-hidden max-h-[90vh] flex flex-col">
        <div class="p-4 bg-muted/50 border-b border-border/60 flex items-center justify-between shrink-0">
          <div class="min-w-0 flex-1 mr-4">
            <p class="text-sm font-semibold truncate">{{ galleryPreviewTitle }}</p>
          </div>
          <Button variant="ghost" size="icon" class="h-7 w-7 shrink-0" @click="galleryPreviewDlg = false">
            <X class="h-4 w-4" />
          </Button>
        </div>
        <ScrollArea class="flex-1 bg-muted/10">
          <img
            v-if="galleryPreviewImg"
            :src="galleryPreviewImg"
            :alt="galleryPreviewTitle"
            class="w-full h-auto"
          />
          <div v-else class="flex items-center justify-center h-64 text-muted-foreground text-sm">
            截图加载中...
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>

    <!-- 探测地址配置弹窗 -->
    <Dialog v-model:open="probeIpDlg">
      <DialogContent class="sm:max-w-[500px] bg-background border-border text-foreground p-0 overflow-hidden">
        <div class="p-6 bg-gradient-to-r from-muted/70 to-primary/10 border-b border-border/60">
          <DialogTitle class="flex items-center gap-3 text-xl">
            <div class="h-10 w-10 flex items-center justify-center bg-primary/20 rounded-xl">
              <Monitor class="h-6 w-6 text-primary" />
            </div>
            <div>
              <p class="text-[10px] uppercase tracking-widest text-primary/70 font-bold mb-0.5">网络探测</p>
              <h2 class="font-bold">配置探测地址</h2>
            </div>
          </DialogTitle>
        </div>

        <div class="p-6 space-y-6">
          <div class="space-y-2">
            <label class="text-sm font-medium text-muted-foreground">IP地址（逗号分隔）</label>
            <Input
              v-model="probeIpInput"
              placeholder="例如: 192.168.1.0/24"
              class="bg-black/20 border-border/40"
            />
            <p class="text-xs text-muted-foreground/60">支持单个IP或IP段</p>
          </div>

          <div class="space-y-2">
            <label class="text-sm font-medium text-muted-foreground">端口配置（可选）</label>
            <Input
              v-model="probeIpPortsInput"
              placeholder="80,443,8080"
              class="bg-black/20 border-border/40"
            />
            <p class="text-xs text-muted-foreground/60">格式: 端口1,端口2</p>
          </div>

          <div v-if="probeIps.length > 0" class="p-3 bg-muted/30 rounded-lg border border-border/40">
            <p class="text-xs font-medium text-muted-foreground mb-2">当前探测地址:</p>
            <div class="flex flex-wrap gap-2">
              <Badge v-for="ip in probeIps" :key="ip" variant="outline" class="bg-primary/10 text-primary border-primary/20">
                {{ ip }}
              </Badge>
            </div>
          </div>
        </div>

        <div class="p-6 bg-muted/30 border-t border-border/60 flex justify-end gap-3">
          <Button variant="secondary" @click="probeIpDlg = false" class="bg-muted border-border hover:bg-muted/70">取消</Button>
          <Button @click="saveProbeIpConfig" class="bg-primary hover:bg-primary/90 text-primary-foreground font-semibold">保存配置</Button>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>
