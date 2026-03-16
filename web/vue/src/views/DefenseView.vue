<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/index'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { 
  ShieldAlert, 
  RefreshCw, 
  Search, 
  Check, 
  X, 
  ShieldMinus, 
  ShieldCheck,
  RotateCw,
  AlertTriangle,
  Bot
} from 'lucide-vue-next'

const loading = ref(false)
const events  = ref<any[]>([])
const search  = ref('')
const page    = ref(1)
const total   = ref(0)
const pageSize = 50

const headers = ['攻击 IP', '事件类型 / 时间', '严重性', 'AI 判定与建议', '状态', '操作']

const SEV_STYLES: Record<string, string>  = { 
  high: 'bg-red-500/10 text-red-400 border-red-500/20', 
  medium: 'bg-orange-500/10 text-orange-400 border-orange-500/20', 
  low: 'bg-blue-500/10 text-blue-400 border-blue-500/20', 
  info: 'bg-slate-500/10 text-slate-500 border-slate-500/20' 
}

const STA_STYLES: Record<string, string>  = { 
  pending: 'bg-orange-500/20 text-orange-400 border-orange-500/30 animate-pulse', 
  approved: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', 
  rejected: 'bg-slate-800 text-slate-500 border-white/5', 
  false_positive: 'bg-sky-500/10 text-sky-400 border-sky-500/20' 
}

function unwrap<T>(payload: any): T {
  return (payload?.data ?? payload) as T
}

async function load() {
  loading.value = true
  try {
    const url = `/api/v1/defense/events?page=${page.value}&page_size=${pageSize}`
    const d   = await api.get<any>(url)
    const data = unwrap<any>(d)
    events.value = data.items ?? []
    total.value  = data.total ?? events.value.length
  } catch(e) { console.error(e) }
  loading.value = false
}

async function approve(id: number) {
  try {
    await api.post(`/api/v1/defense/events/${id}/approve`, {})
    load()
  } catch(e) { console.error(e) }
}
async function reject(id: number) {
  try {
    await api.post(`/api/v1/defense/events/${id}/reject`, {})
    load()
  } catch(e) { console.error(e) }
}
async function markFP(id: number) {
  try {
    await api.post(`/api/v1/defense/events/${id}/false-positive`, {})
    load()
  } catch(e) { console.error(e) }
}

onMounted(load)
</script>

<template>
  <div class="p-6 space-y-6">
    <Card class="bg-card/40 border border-border/50">
      <CardHeader class="pb-6 border-b border-border/20 flex flex-row items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="p-2 bg-red-500/10 rounded-lg">
            <ShieldAlert :size="20" class="text-red-500" />
          </div>
          <CardTitle class="text-xl font-bold">防御决策管理</CardTitle>
        </div>
        <div class="flex items-center gap-4">
          <div class="relative w-64">
            <Search :size="16" class="absolute left-2.5 top-2.5 text-muted-foreground" />
            <Input v-model="search" placeholder="过滤 IP 或类型..." class="pl-9 h-9 bg-black/20" />
          </div>
          <Button variant="ghost" size="icon" @click="load" :disabled="loading">
            <RotateCw :size="16" :class="{ 'animate-spin': loading }" />
          </Button>
        </div>
      </CardHeader>

      <CardContent class="p-0">
        <div class="overflow-x-auto text-slate-100">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-muted/10 text-muted-foreground border-b border-border/20 text-[10px] uppercase tracking-widest font-bold">
                <th v-for="h in headers" :key="h" class="text-left py-4 px-5">{{ h }}</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border/5">
              <template v-if="loading">
                <tr v-for="i in 6" :key="i">
                  <td v-for="j in headers.length" :key="j" class="py-4 px-5"><Skeleton class="h-4 w-full" /></td>
                </tr>
              </template>
              <template v-else-if="events.length">
                <tr v-for="ev in events" :key="ev.id" class="hover:bg-white/5 transition-colors">
                  <td class="py-4 px-5 font-bold font-mono text-slate-200">
                    {{ ev.attack_ip }}
                  </td>
                  <td class="py-4 px-5">
                    <div class="flex flex-col">
                      <span class="font-medium text-slate-300 font-sans text-xs">{{ ev.event_type }}</span>
                      <span class="text-[10px] text-slate-500 mt-1">{{ ev.created_at?.slice(0,19) }}</span>
                    </div>
                  </td>
                  <td class="py-4 px-5">
                    <Badge :class="SEV_STYLES[ev.severity] || 'bg-slate-500/10'">
                      {{ ev.severity?.toUpperCase() }}
                    </Badge>
                  </td>
                  <td class="py-4 px-5">
                    <div class="flex flex-col gap-2 max-w-[320px]">
                      <div class="flex items-center gap-2">
                        <Bot class="h-4 w-4 text-primary" />
                        <Badge :variant="ev.ai_decision === 'ban' ? 'destructive' : 'default'" class="h-5 text-[10px] px-2 font-bold uppercase tracking-tighter">
                          AI {{ ev.ai_decision === 'ban' ? '建议封禁' : '放行' }}
                        </Badge>
                      </div>
                      <p class="text-[11px] text-slate-400 italic leading-relaxed">{{ ev.ai_analysis || 'AI 分析生成中...' }}</p>
                    </div>
                  </td>
                  <td class="py-4 px-5">
                    <Badge :class="STA_STYLES[ev.status] || 'bg-slate-500/10'" class="uppercase text-[10px] tracking-tighter px-2">
                      {{ ev.status }}
                    </Badge>
                  </td>
                  <td class="py-4 px-5">
                    <div class="flex items-center gap-1">
                      <template v-if="ev.status === 'pending'">
                        <Button variant="ghost" size="sm" class="h-8 text-emerald-400 hover:bg-emerald-500/10 px-2" @click="approve(ev.id)">
                          <Check class="h-3.5 w-3.5 mr-1" /> 批准
                        </Button>
                        <Button variant="ghost" size="sm" class="h-8 text-slate-400 hover:bg-white/5 px-2" @click="reject(ev.id)">
                          <X class="h-3.5 w-3.5 mr-1" /> 拒绝
                        </Button>
                      </template>
                      <Button variant="ghost" size="sm" class="h-8 text-sky-400 hover:bg-sky-500/10 px-2" @click="markFP(ev.id)">
                        <ShieldMinus class="h-3.5 w-3.5 mr-1" /> 误报
                      </Button>
                    </div>
                  </td>
                </tr>
              </template>
              <tr v-else>
                <td :colspan="headers.length" class="py-24 text-center bg-muted/5">
                  <div class="flex flex-col items-center gap-3 text-slate-600">
                    <ShieldCheck class="h-10 w-10 opacity-10" />
                    <span class="italic text-sm font-medium">当前无待处理的防御事件</span>
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
