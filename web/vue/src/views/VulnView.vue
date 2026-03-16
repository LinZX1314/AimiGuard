<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
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
import { Skeleton } from '@/components/ui/skeleton'
import { 
  Bug, 
  ShieldAlert, 
  ShieldCheck, 
  Search, 
  RefreshCw, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle,
  Flame,
  Filter,
  MoreHorizontal,
  Eraser
} from 'lucide-vue-next'

const loading  = ref(false)
const scanning = ref(false)
const vulns    = ref<any[]>([])
const search   = ref('')
const sevFlt   = ref<string>("ALL")
const statusFlt= ref<string>("ALL")
const stats    = ref({ total: 0, critical: 0, high: 0, fixed: 0 })

const headers = ['漏洞名称', '主机 IP', '严重性', '状态 / 发现时间', '操作']

const severities = ['严重', '高危', '中危', '低危', '信息']
const statuses   = ['open', 'fixed', 'ignored', 'false_positive']

const SEV_STYLES: Record<string, string> = {
  '严重': 'bg-red-500/10 text-red-500 border-red-500/20',
  '高危': 'bg-orange-500/10 text-orange-500 border-orange-500/20',
  '中危': 'bg-amber-500/10 text-amber-500 border-amber-500/20',
  '低危': 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20',
  '信息': 'bg-slate-500/10 text-slate-500 border-slate-500/20'
}

const STA_STYLES: Record<string, string> = {
  open: 'bg-red-500/20 text-red-400 border-red-500/30 font-bold',
  fixed: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  ignored: 'bg-slate-800 text-slate-500 border-white/5',
  false_positive: 'bg-amber-500/20 text-amber-400 border-amber-500/30'
}

const filteredVulns = computed(() => {
  let result = vulns.value
  if (search.value) {
    const s = search.value.toLowerCase()
    result = result.filter(v => 
      (v.vuln_name || '').toLowerCase().includes(s) || 
      (v.ip || '').toLowerCase().includes(s)
    )
  }
  return result
})

async function load() {
  loading.value = true
  const d = await apiCall<any>(async () => {
    let url = '/api/v1/scan/findings?limit=500'
    if (sevFlt.value !== "ALL")    url += `&severity=${sevFlt.value}`
    if (statusFlt.value !== "ALL") url += `&status=${statusFlt.value}`
    return await api.get<any>(url)
  })
  if (d) {
    vulns.value = d.items ?? d.data?.items ?? d.data ?? []
    stats.value.total    = vulns.value.length
    stats.value.critical = vulns.value.filter(v => v.severity === '严重').length
    stats.value.high     = vulns.value.filter(v => v.severity === '高危').length
    stats.value.fixed    = vulns.value.filter(v => v.status === 'fixed').length
  }
  loading.value = false
}

async function startVulnScan() {
  scanning.value = true
  await apiCall(async () => await api.post('/api/nmap/vuln/scan', {}), { errorMsg: '漏洞扫描启动失败' })
  scanning.value = false
}

async function markStatus(id: number, status: string) {
  const ok = await apiCall(async () => {
    await api.put(`/api/v1/scan/findings/${id}/status`, { status })
    load()
  }, { errorMsg: '状态更新失败' })
  if (ok) load()
}

const statSummaries = computed(() => [
  { label: '漏洞总数', val: stats.value.total, icon: Bug, color: 'text-primary' },
  { label: '严重威胁', val: stats.value.critical, icon: Flame, color: 'text-red-500 shadow-[0_0_10px_rgba(239,68,68,0.3)]' },
  { label: '高危漏洞', val: stats.value.high, icon: AlertTriangle, color: 'text-orange-400' },
  { label: '已修复', val: stats.value.fixed, icon: ShieldCheck, color: 'text-emerald-400' }
])

onMounted(load)
</script>

<template>
  <div class="p-6 space-y-6 text-slate-100">
    <!-- Quick Stats Row -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <Card v-for="s in statSummaries" :key="s.label" class="bg-card/40 border border-border/50 transition-all hover:bg-card/60">
        <CardContent class="p-5 flex flex-col justify-center items-center text-center">
          <div class="p-2 rounded-full mb-2 bg-white/5">
            <Bug v-if="s.icon === Bug" :size="20" :class="s.color" />
            <Flame v-else-if="s.icon === Flame" :size="20" :class="s.color" />
            <AlertTriangle v-else-if="s.icon === AlertTriangle" :size="20" :class="s.color" />
            <ShieldCheck v-else-if="s.icon === ShieldCheck" :size="20" :class="s.color" />
          </div>
          <h2 class="text-3xl font-black tracking-tighter" :class="s.color">{{ s.val }}</h2>
          <p class="text-[10px] uppercase tracking-[0.2em] font-bold text-slate-500 mt-1">{{ s.label }}</p>
        </CardContent>
      </Card>
    </div>

    <!-- Main List Card -->
    <Card class="bg-card/40 border border-border/50">
      <CardHeader class="pb-4 border-b border-border/20 flex flex-row items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="p-2 bg-orange-500/10 rounded-lg">
            <AlertTriangle :size="20" class="text-orange-500" />
          </div>
          <CardTitle class="text-lg font-bold">漏洞监测概况</CardTitle>
        </div>
        <div class="flex gap-2">
          <Button variant="outline" size="sm" @click="startVulnScan" :disabled="scanning" 
                  class="bg-orange-500/10 border-orange-500/20 text-orange-400 hover:bg-orange-500 hover:text-white transition-all px-4">
            <Bug v-if="!scanning" :size="16" class="mr-2" />
            <RefreshCw v-else :size="16" class="mr-2 animate-spin" />
            开启漏洞扫描
          </Button>
          <Button variant="ghost" size="icon" @click="load" :disabled="loading">
            <RefreshCw :size="16" class="text-primary" :class="{ 'animate-spin': loading }" />
          </Button>
        </div>
      </CardHeader>
      
      <CardContent class="p-0">
        <!-- Filter Bar -->
        <div class="p-4 bg-muted/5 border-b border-border/10 flex flex-wrap items-center gap-4">
          <div class="relative w-72">
            <Search :size="16" class="absolute left-3 top-3 text-muted-foreground" />
            <Input v-model="search" placeholder="搜索漏洞名称/资产 IP..." class="pl-10 h-10 bg-black/20" />
          </div>
          
          <div class="flex items-center gap-2">
            <Filter :size="16" class="text-slate-500" />
            <Select v-model="sevFlt" @update:model-value="load">
              <SelectTrigger class="w-36 h-10 bg-black/20 border-border/40">
                <SelectValue placeholder="严重性" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">全部等级</SelectItem>
                <SelectItem v-for="s in severities" :key="s" :value="s">{{ s }}</SelectItem>
              </SelectContent>
            </Select>
            <Select v-model="statusFlt" @update:model-value="load">
              <SelectTrigger class="w-36 h-10 bg-black/20 border-border/40">
                <SelectValue placeholder="修复状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">全部状态</SelectItem>
                <SelectItem v-for="s in statuses" :key="s" :value="s">{{ s }}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <!-- Table -->
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-muted-foreground bg-muted/10 border-b border-border/20 uppercase text-[10px] tracking-widest font-bold">
                <th v-for="h in headers" :key="h" class="text-left py-3 px-5">{{ h }}</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border/5">
              <template v-if="loading">
                <tr v-for="i in 5" :key="i">
                  <td v-for="j in headers.length" :key="j" class="py-4 px-5"><Skeleton class="h-4 w-full" /></td>
                </tr>
              </template>
              <template v-else-if="filteredVulns.length">
                <tr v-for="v in filteredVulns" :key="v.id" class="hover:bg-white/5 transition-colors">
                  <td class="py-4 px-5">
                    <div class="flex flex-col gap-1 max-w-[280px]">
                      <span class="font-bold text-slate-200 leading-tight">{{ v.vuln_name }}</span>
                      <span class="text-[10px] font-mono text-slate-500 overflow-hidden truncate">CVE-ID: {{ v.cve_id || 'UNKNOWN' }}</span>
                    </div>
                  </td>
                  <td class="py-4 px-5">
                    <div class="flex items-center gap-2">
                      <span class="text-xs font-mono bg-indigo-500/10 text-indigo-300 px-2 py-0.5 rounded border border-indigo-500/20">
                        {{ v.ip }}
                      </span>
                      <span v-if="v.port" class="text-[10px] text-slate-500 text-bold">:{{ v.port }}</span>
                    </div>
                  </td>
                  <td class="py-4 px-5">
                    <Badge :class="SEV_STYLES[v.severity] || 'bg-slate-500/10'">
                      {{ v.severity }}
                    </Badge>
                  </td>
                  <td class="py-4 px-5">
                    <div class="flex flex-col gap-1">
                      <Badge :class="STA_STYLES[v.status] || 'bg-slate-500/10'" class="w-fit text-[10px] px-2 h-5">
                        {{ v.status.toUpperCase() }}
                      </Badge>
                      <span class="text-[10px] text-slate-500">{{ v.created_at?.slice(0,16) }}</span>
                    </div>
                  </td>
                  <td class="py-4 px-5">
                    <div class="flex items-center gap-1">
                      <Button v-if="v.status === 'open'" variant="ghost" size="sm" class="h-8 text-emerald-400 hover:bg-emerald-500/10 hover:text-emerald-300" 
                              @click="markStatus(v.id, 'fixed')">
                        <CheckCircle2 class="mr-1.5 h-3.5 w-3.5" /> 已修
                      </Button>
                      <Button v-if="v.status === 'open'" variant="ghost" size="sm" class="h-8 text-slate-500 hover:bg-white/5 hover:text-slate-300"
                              @click="markStatus(v.id, 'ignored')">
                        <XCircle class="mr-1.5 h-3.5 w-3.5" /> 忽略
                      </Button>
                      <Button v-else variant="ghost" size="icon" class="h-8 w-8 text-slate-600">
                        <MoreHorizontal class="h-4 w-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              </template>
              <tr v-else>
                <td :colspan="headers.length" class="py-24 text-center bg-muted/5">
                  <div class="flex flex-col items-center gap-2 text-slate-600 italic">
                    <Eraser class="h-8 w-8 opacity-20" />
                    <span>未发现满足筛选条件的漏洞记录</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
