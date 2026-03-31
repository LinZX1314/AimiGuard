<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api, apiCall } from '@/api/index'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Pagination } from '@/components/ui/pagination'
import {
  ShieldAlert,
  Check,
  X,
  ShieldMinus,
  ShieldCheck,
  Shield,
  RotateCw,
  Bot,
  Globe,
  Clock,
  ExternalLink
} from 'lucide-vue-next'

const loading = ref(false)
const whitelist = ref<string[]>([])
const events  = ref<any[]>([])
const page    = ref(1)
const pageSize = ref(50)
const total   = ref(0)

const headers = ['来源资产', '次数', '威胁指纹', 'AI 深度研判', '状态', '操作']



const STA_STYLES: Record<string, string>  = { 
  pending: 'bg-orange-500/20 text-orange-400 border-orange-500/30 animate-pulse', 
  approved: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', 
  rejected: 'bg-slate-500/15 text-slate-300 border-slate-400/30', 
  false_positive: 'bg-sky-500/10 text-sky-400 border-sky-500/20',
  analyzed: 'bg-blue-500/10 text-blue-300 border-blue-500/25',
  error: 'bg-red-500/15 text-red-300 border-red-500/30',
  whitelisted: 'bg-teal-500/10 text-teal-300 border-teal-500/25',
}

// 后端状态值保持不变，前端展示中文
const STATUS_TEXT: Record<string, string> = {
  pending: '待处理',
  approved: '已封禁',
  rejected: '已拒绝',
  false_positive: '误报',
  analyzed: '已分析',
  error: '执行失败',
  whitelisted: '白名单已跳过',
}

const ACTION_BTN_CLASS = 'h-7 border-border/60 bg-background text-foreground hover:bg-muted transition-all text-[11px] px-3 font-bold'

function getStatusText(status: string | undefined) {
  if (!status) return '待处理'
  return STATUS_TEXT[status] || '未知状态'
}

function unwrap<T>(payload: any): T {
  return (payload?.data ?? payload) as T
}

async function load() {
  loading.value = true
  const d = await apiCall<any>(async () => {
    const url = `/api/v1/defense/events?page=${page.value}&page_size=${pageSize.value}`
    const res = await api.get<any>(url)
    return unwrap<any>(res)
  })
  if (d) {
    events.value = (d.items ?? []).filter((ev: any) => !whitelist.value.includes(ev.attack_ip))
    total.value = d.total ?? events.value.length
  }
  loading.value = false
}

async function approve(id: number) {
  const ok = await apiCall(async () => {
    await api.post(`/api/v1/defense/events/${id}/approve`, {})
    load()
  }, { errorMsg: '批准失败' })
  if (ok) load()
}
async function reject(id: number) {
  const ok = await apiCall(async () => {
    await api.post(`/api/v1/defense/events/${id}/reject`, {})
    load()
  }, { errorMsg: '拒绝失败' })
  if (ok) load()
}
async function markFP(id: number) {
  const ok = await apiCall(async () => {
    await api.post(`/api/v1/defense/events/${id}/false-positive`, {})
    load()
  }, { errorMsg: '标记误报失败' })
  if (ok) load()
}

async function loadWhitelist() {
  try {
    const res = await api.get<{ whitelist: string[] }>('/api/v1/system/ai-whitelist')
    whitelist.value = (res as any)?.whitelist ?? []
  } catch (e) {
    console.error('加载白名单失败:', e)
  }
}

async function addToWhitelist(ip: string) {
  if (whitelist.value.includes(ip)) return
  whitelist.value.push(ip)
  await api.post('/api/v1/system/ai-whitelist', { whitelist: whitelist.value })
}

async function unban(id: number) {
  await apiCall(async () => {
    await api.post(`/api/v1/defense/events/${id}/unban`, {})
    load()
  }, { errorMsg: '解封失败' })
  load()
}

onMounted(async () => {
  await loadWhitelist()
  load()
})
</script>

<template>
  <div class="p-6 space-y-6">
    <Card class="border-border/50">
      <CardHeader class="pb-6 border-b flex flex-row items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="p-2 bg-red-500/10 rounded-lg">
            <ShieldAlert :size="20" class="text-red-500" />
          </div>
          <CardTitle class="text-xl font-bold">防御决策管理</CardTitle>
        </div>
        <Button variant="ghost" size="icon" @click="load" :disabled="loading">
          <RotateCw :size="16" :class="{ 'animate-spin': loading }" />
        </Button>
      </CardHeader>

      <CardContent class="p-0">
        <div class="overflow-x-auto text-foreground">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-muted/30 text-muted-foreground border-b text-[10px] uppercase tracking-widest font-bold">
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
                <tr v-for="ev in events" :key="ev.id" class="hover:bg-white/[0.02] border-b last:border-0 transition-colors">
                  <!-- 资产信息 -->
                  <td class="py-5 px-5 align-top">
                    <div class="space-y-1.5">
                      <div class="font-bold font-mono text-foreground text-sm leading-none flex items-center gap-2">
                        {{ ev.attack_ip }}
                        <ExternalLink :size="10" class="text-muted-foreground cursor-pointer hover:text-primary transition-colors" />
                      </div>
                      <div class="flex items-center gap-1.5 text-[10px] text-muted-foreground font-medium">
                        <Globe class="h-3 w-3 opacity-70" />
                        {{ ev.ip_location || '内部网络 / 未知' }}
                      </div>
                    </div>
                  </td>

                  <!-- 攻击次数 -->
                  <td class="py-5 px-5 align-top">
                    <div class="inline-flex flex-col items-center justify-center bg-blue-500/5 border border-blue-500/10 rounded-md w-12 py-1">
                      <span class="text-xs font-black text-blue-400 leading-none">{{ ev.attack_count }}</span>
                      <span class="text-[7px] uppercase tracking-tighter text-blue-600 font-bold mt-1">Hits</span>
                    </div>
                  </td>

                  <!-- 事件指纹 -->
                  <td class="py-5 px-5 align-top">
                    <div class="space-y-2">
                      <div class="flex flex-wrap gap-1 max-w-[180px]">
                        <Badge v-for="tag in (ev.event_type || '').split(',').slice(0, 3)" :key="tag" 
                               variant="secondary" class="text-[9px] px-1.5 py-0 h-4 bg-muted text-muted-foreground rounded">
                          {{ tag.trim() }}
                        </Badge>
                        <span v-if="(ev.event_type || '').split(',').length > 3" class="text-[9px] text-muted-foreground/60 font-bold">...</span>
                      </div>
                      <div class="flex items-center gap-1.5 text-[10px] text-muted-foreground font-mono">
                         <Clock :size="10" class="opacity-70" />
                         {{ ev.created_at?.slice(5, 16) }}
                      </div>
                    </div>
                  </td>

                  <!-- AI 研判 -->
                  <td class="py-5 px-5 align-top">
                    <div class="flex flex-col gap-2 max-w-[400px]">
                      <div class="flex items-center gap-2">
                        <Bot class="h-3.5 w-3.5 text-primary" />
                        <span class="text-[10px] font-bold uppercase tracking-wider" 
                              :class="(ev.ai_decision === 'ban' || ev.ai_decision === '封禁' || ev.ai_decision === '已封禁') ? 'text-destructive' : 'text-emerald-500'">
                          {{ (ev.ai_decision === 'ban' || ev.ai_decision === '封禁' || ev.ai_decision === '已封禁') ? '检出：建议阻断' : '检出：疑似误报' }}
                        </span>
                      </div>
                      <div class="text-[11px] text-foreground/80 leading-relaxed bg-muted/30 p-2.5 rounded-lg border relative group">
                        <div class="absolute -left-1 top-2 w-0.5 h-3 bg-primary/40 rounded-full"></div>
                        <span class="italic">"{{ ev.ai_analysis || 'AI 正在分析该 IP 的攻击指纹与威胁模型...' }}"</span>
                      </div>
                    </div>
                  </td>

                  <!-- 状态标签 -->
                  <td class="py-5 px-5 align-top">
                    <Badge :class="STA_STYLES[ev.status] || 'bg-slate-500/10'" class="uppercase text-[9px] tracking-widest px-2 h-5 flex items-center justify-center font-black">
                      {{ getStatusText(ev.status) }}
                    </Badge>
                  </td>

                  <!-- 操作 -->
                  <td class="py-5 px-5 align-top">
                    <div class="flex flex-col gap-1.5">
                      <template v-if="ev.status === 'approved'">
                        <Button
                          variant="ghost"
                          size="sm"
                          class="h-7 text-orange-500 hover:text-orange-600 hover:bg-orange-500/5 transition-all text-[10px] px-3"
                          @click="unban(ev.id)">
                          <X class="h-3 w-3 mr-1.5 opacity-70" /> 解封
                        </Button>
                      </template>
                      <Button
                        v-if="!whitelist.includes(ev.attack_ip)"
                        variant="ghost"
                        size="sm"
                        class="h-7 text-green-500 hover:text-green-600 hover:bg-green-500/5 transition-all text-[10px] px-3"
                        @click="addToWhitelist(ev.attack_ip)">
                        <Shield class="h-3 w-3 mr-1.5 opacity-70" /> 加入白名单
                      </Button>
                      <span v-else class="text-[10px] text-muted-foreground/60">已白名单</span>
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
        <Pagination v-model:page="page" v-model:page-size="pageSize" :total="total" @update:page="load" @update:page-size="load" />
      </CardContent>
    </Card>
  </div>
</template>
