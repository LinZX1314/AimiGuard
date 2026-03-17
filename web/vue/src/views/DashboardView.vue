<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/index'
import { Line, Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Activity,
  Bot,
  Circle,
  Server,
  Sparkles,
  Globe,
  Radar,
  Router,
  ShieldAlert,
  Bug,
  ServerCog,
  Shield,
  Send,
  Loader2,
} from 'lucide-vue-next'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler,
)

interface TopMetrics {
  hfish_total: number
  hfish_high: number
  nmap_online: number
  vuln_open: number
  ai_decisions: number
  blocked_ips: number
}

interface ScreenPayload {
  top_metrics: TopMetrics
  chain_status: Record<string, boolean>
  trends: { labels: string[]; counts: number[] }
  threat_distribution: { levels: string[]; counts: number[] }
  hot_services: Array<{ name: string; count: number }>
  recent_attacks: Array<{ attack_ip: string; ip_location?: string; service_name?: string; threat_level?: string; create_time_str?: string }>
  defense_events: Array<{ attack_ip: string; ip_location?: string; attack_count: number; latest_time?: string; ai_status?: string; ai_decision?: string }>
}

const router = useRouter()
const loading = ref(true)
const loadError = ref('')

const aiMessages = ref<Array<{ role: 'user' | 'assistant'; content: string }>>([])
const aiInput = ref('')
const aiLoading = ref(false)
const aiError = ref('')
const aiSessionId = ref<number | null>(null)
const aiEndRef = ref<HTMLElement | null>(null)

const quickPrompts = [
  { label: '态势总览', prompt: '请输出当前态势总览和最高优先级风险。' },
  { label: '防御动作', prompt: '请基于当前攻击来源给出30分钟防御动作清单。' },
  { label: '链路体检', prompt: '请评估当前链路健康与潜在瓶颈。' },
]

const payload = ref<ScreenPayload>({
  top_metrics: { hfish_total: 0, hfish_high: 0, nmap_online: 0, vuln_open: 0, ai_decisions: 0, blocked_ips: 0 },
  chain_status: {},
  trends: { labels: [], counts: [] },
  threat_distribution: { levels: [], counts: [] },
  hot_services: [],
  recent_attacks: [],
  defense_events: [],
})

const metricCards = computed(() => [
  { key: 'hfish_total', label: '攻击日志总数', value: payload.value.top_metrics.hfish_total, color: 'text-cyan-400' },
  { key: 'hfish_high', label: '高危攻击', value: payload.value.top_metrics.hfish_high, color: 'text-red-400' },
  { key: 'nmap_online', label: '在线主机', value: payload.value.top_metrics.nmap_online, color: 'text-emerald-400' },
  { key: 'vuln_open', label: '待修漏洞', value: payload.value.top_metrics.vuln_open, color: 'text-amber-400' },
  { key: 'ai_decisions', label: 'AI 决策数', value: payload.value.top_metrics.ai_decisions, color: 'text-violet-400' },
  { key: 'blocked_ips', label: '已封禁 IP', value: payload.value.top_metrics.blocked_ips, color: 'text-slate-400' },
])

const chainItems = [
  { key: 'hfish_sync', label: 'HFish 同步' },
  { key: 'nmap_scan', label: 'Nmap 扫描' },
  { key: 'ai_analysis', label: 'AI 分析' },
  { key: 'acl_auto_ban', label: 'ACL 封禁' },
]

type BattlefieldNode = {
  id: string
  label: string
  type: 'edge' | 'firewall' | 'switch' | 'honeypot' | 'core' | 'soc'
  status: 'online' | 'warn' | 'danger'
  x: number
  y: number
  detail: string
}

const battlefieldNodes = computed<BattlefieldNode[]>(() => {
  const online = payload.value.top_metrics.nmap_online
  const high = payload.value.top_metrics.hfish_high
  const total = payload.value.top_metrics.hfish_total

  return [
    { id: 'internet', label: '互联网边界', type: 'edge', status: 'warn', x: 90, y: 280, detail: `外部威胁流量 ${total}` },
    { id: 'fw', label: '主防火墙', type: 'firewall', status: high > 20 ? 'danger' : 'online', x: 265, y: 280, detail: `高危事件 ${high}` },
    { id: 'sw-core', label: '核心交换机 SW-Core', type: 'switch', status: 'online', x: 470, y: 190, detail: 'VLAN 聚合 / ACL 联动' },
    { id: 'sw-access', label: '接入交换机 SW-Access', type: 'switch', status: 'online', x: 470, y: 375, detail: '办公网接入与隔离' },
    { id: 'honeypot-a', label: '蜜罐节点 HP-Web', type: 'honeypot', status: high > 10 ? 'warn' : 'online', x: 690, y: 132, detail: 'HTTP/SSH 诱捕策略' },
    { id: 'honeypot-b', label: '蜜罐节点 HP-SSH', type: 'honeypot', status: high > 14 ? 'warn' : 'online', x: 690, y: 280, detail: '口令爆破诱捕' },
    { id: 'soc', label: 'AI/SOC 分析中心', type: 'soc', status: 'online', x: 690, y: 428, detail: `AI 决策 ${payload.value.top_metrics.ai_decisions}` },
    { id: 'core-assets', label: '核心资产区', type: 'core', status: online > 0 ? 'online' : 'warn', x: 900, y: 280, detail: `在线资产 ${online}` },
  ]
})

const battlefieldLinks = [
  ['internet', 'fw'],
  ['fw', 'sw-core'],
  ['fw', 'sw-access'],
  ['sw-core', 'honeypot-a'],
  ['sw-core', 'honeypot-b'],
  ['sw-access', 'soc'],
  ['honeypot-a', 'core-assets'],
  ['honeypot-b', 'core-assets'],
  ['soc', 'core-assets'],
]

const nodeMap = computed(() => {
  const map = new Map<string, BattlefieldNode>()
  battlefieldNodes.value.forEach((node) => map.set(node.id, node))
  return map
})

const battlefieldSvgLines = computed(() => {
  return battlefieldLinks
    .map(([fromId, toId]) => {
      const from = nodeMap.value.get(fromId)
      const to = nodeMap.value.get(toId)
      if (!from || !to) return null
      return {
        key: `${fromId}-${toId}`,
        x1: from.x,
        y1: from.y,
        x2: to.x,
        y2: to.y,
      }
    })
    .filter((line): line is { key: string; x1: number; y1: number; x2: number; y2: number } => Boolean(line))
})

function resolveNodeIcon(type: BattlefieldNode['type']) {
  if (type === 'edge') return Globe
  if (type === 'firewall') return ShieldAlert
  if (type === 'switch') return Router
  if (type === 'honeypot') return Bug
  if (type === 'soc') return ServerCog
  return Shield
}

function nodeTheme(type: BattlefieldNode['type']) {
  if (type === 'edge') return 'from-sky-500/30 to-cyan-400/10 border-cyan-300/30 text-cyan-100'
  if (type === 'firewall') return 'from-rose-500/35 to-red-500/10 border-red-300/30 text-rose-100'
  if (type === 'switch') return 'from-violet-500/35 to-indigo-500/10 border-violet-300/30 text-violet-100'
  if (type === 'honeypot') return 'from-amber-500/35 to-orange-500/10 border-amber-300/30 text-amber-100'
  if (type === 'soc') return 'from-emerald-500/35 to-teal-500/10 border-emerald-300/30 text-emerald-100'
  return 'from-slate-500/35 to-slate-500/10 border-slate-300/30 text-slate-100'
}

function statusTheme(status: BattlefieldNode['status']) {
  if (status === 'online') return 'bg-emerald-400'
  if (status === 'warn') return 'bg-amber-400'
  return 'bg-red-400'
}

const trendData = computed(() => ({
  labels: payload.value.trends.labels,
  datasets: [{
    label: '攻击次数',
    data: payload.value.trends.counts,
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
  labels: payload.value.hot_services.slice(0, 6).map((x) => x.name),
  datasets: [{
    label: '攻击次数',
    data: payload.value.hot_services.slice(0, 6).map((x) => x.count),
    backgroundColor: '#8b5cf6',
    borderRadius: 6,
  }],
}))

function formatThreatLevel(level?: string) {
  if (!level) return '未分级'
  const lower = level.toLowerCase()
  if (level === '高危' || lower === 'high') return '高危'
  if (level === '中危' || lower === 'medium') return '中危'
  if (level === '低危' || lower === 'low') return '低危'
  return level
}

async function loadScreen() {
  if (!payload.value.recent_attacks.length) {
    loading.value = true
  }
  loadError.value = ''
  try {
    const res = await api.get<any>('/api/v1/overview/screen')
    payload.value = (res?.data ?? res) as ScreenPayload
  } catch (e: any) {
    loadError.value = e?.message || '大屏数据加载失败'
  } finally {
    loading.value = false
  }
}

async function scrollAiToBottom() {
  await nextTick()
  aiEndRef.value?.scrollIntoView({ behavior: 'smooth', block: 'end' })
}

async function sendAiMessage(prompt?: string) {
  const text = (prompt ?? aiInput.value).trim()
  if (!text || aiLoading.value) return

  aiError.value = ''
  aiMessages.value.push({ role: 'user', content: text })
  aiMessages.value.push({ role: 'assistant', content: '' })
  if (!prompt) aiInput.value = ''
  aiLoading.value = true
  await scrollAiToBottom()

  try {
    const token = localStorage.getItem('token') || ''
    const resp = await fetch('/api/v1/ai/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: token ? `Bearer ${token}` : '',
      },
      body: JSON.stringify({
        message: text,
        session_id: aiSessionId.value ?? undefined,
        context_type: 'dashboard',
        context_id: 'map',
      }),
    })

    if (!resp.ok || !resp.body) {
      throw new Error('AI 服务暂不可用')
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const events = buffer.split('\n\n')
      buffer = events.pop() || ''

      for (const event of events) {
        const line = event.split('\n').find((x) => x.startsWith('data: '))
        if (!line) continue

        try {
          const parsed = JSON.parse(line.slice(6))
          if (parsed.session_id) {
            aiSessionId.value = Number(parsed.session_id)
          }
          if (parsed.error) {
            aiError.value = String(parsed.error)
            continue
          }
          if (parsed.content) {
            const lastIndex = aiMessages.value.length - 1
            const last = aiMessages.value[lastIndex]
            if (last && last.role === 'assistant') {
              aiMessages.value[lastIndex] = { ...last, content: `${last.content}${String(parsed.content)}` }
            }
            await scrollAiToBottom()
          }
        } catch {
          // 忽略无法解析的 SSE 帧
        }
      }
    }
  } catch (e: any) {
    aiError.value = e?.message || 'AI 响应异常'
    const lastIndex = aiMessages.value.length - 1
    if (lastIndex >= 0 && aiMessages.value[lastIndex].role === 'assistant' && !aiMessages.value[lastIndex].content) {
      aiMessages.value[lastIndex].content = '抱歉，当前 AI 服务不可用，请稍后重试。'
    }
  } finally {
    aiLoading.value = false
  }
}

let timer: ReturnType<typeof setInterval>
onMounted(() => {
  loadScreen()
  timer = setInterval(loadScreen, 15_000)
})
onUnmounted(() => {
  clearInterval(timer)
})
</script>

<template>
  <div class="h-full w-full overflow-hidden p-4 md:p-6">
    <div class="grid h-full grid-cols-1 gap-4 xl:grid-cols-[300px_minmax(0,1fr)_360px]">
      <!-- 左栏：态势摘要 -->
      <aside class="min-h-0 overflow-hidden pr-1">
        <ScrollArea class="h-full">
        <div class="space-y-4 pr-2">
        <Card>
          <CardHeader class="pb-3">
            <CardTitle class="text-sm flex items-center gap-2"><Activity class="h-4 w-4 text-primary" /> 态势摘要</CardTitle>
          </CardHeader>
          <CardContent class="space-y-2">
            <div class="grid grid-cols-2 gap-2">
              <div v-for="item in metricCards" :key="item.key" class="rounded-lg border border-border/60 bg-muted/20 px-2.5 py-2">
                <p class="text-[10px] tracking-wide text-muted-foreground">{{ item.label }}</p>
                <p class="text-base font-semibold leading-5" :class="item.color">{{ item.value }}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">实时攻击趋势与来源</CardTitle>
          </CardHeader>
          <CardContent>
            <div class="h-44">
              <Line v-if="payload.trends.labels.length" :data="trendData" :options="trendOptions" />
              <Skeleton v-else-if="loading" class="h-full w-full" />
              <div v-else class="h-full flex items-center justify-center text-sm text-muted-foreground">暂无趋势数据</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">热门攻击服务</CardTitle>
          </CardHeader>
          <CardContent>
            <div class="h-44">
              <Bar v-if="payload.hot_services.length" :data="serviceData" :options="{ responsive: true, maintainAspectRatio: false, indexAxis: 'y', plugins: { legend: { display: false } }, scales: { x: { grid: { display: false }, ticks: { color: '#94a3b8' } }, y: { grid: { display: false }, ticks: { color: '#94a3b8' } } } }" />
              <Skeleton v-else-if="loading" class="h-full w-full" />
              <div v-else class="h-full flex items-center justify-center text-sm text-muted-foreground">暂无服务统计</div>
            </div>
          </CardContent>
        </Card>
        </div>
        </ScrollArea>
      </aside>

      <!-- 中栏：主战场 -->
      <main class="min-h-0 flex flex-col gap-4 overflow-hidden">
        <Card class="shrink-0">
          <CardContent class="p-3">
            <div class="flex items-center gap-2">
              <Globe class="h-4 w-4 text-primary" />
              <span class="text-sm font-medium">攻击地图</span>
            </div>
          </CardContent>
        </Card>

        <Card class="flex-1 min-h-0 overflow-hidden">
          <CardHeader class="pb-2">
            <CardTitle class="text-sm flex items-center gap-2">
              <Radar class="h-4 w-4 text-primary" />
              攻击地图面板
            </CardTitle>
          </CardHeader>
          <CardContent class="h-[calc(100%-48px)] overflow-hidden p-0">
            <ScrollArea class="h-full px-6 pb-6">
            <div v-if="loadError" class="rounded-lg border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">{{ loadError }}</div>

            <template v-else>
              <div class="h-[30rem] xl:h-[34rem] rounded-xl border border-cyan-400/25 bg-[radial-gradient(circle_at_15%_16%,rgba(34,211,238,0.2),transparent_45%),radial-gradient(circle_at_86%_4%,rgba(56,189,248,0.22),transparent_38%),radial-gradient(circle_at_50%_110%,rgba(15,118,110,0.2),transparent_45%),linear-gradient(180deg,rgba(15,23,42,0.62),rgba(2,6,23,0.92))] p-2 shadow-[0_0_0_1px_rgba(34,211,238,0.1),0_20px_50px_rgba(2,132,199,0.22)]">
                <div class="relative h-full w-full overflow-hidden rounded-lg border border-cyan-500/20 bg-slate-950/45">
                  <svg class="absolute inset-0 h-full w-full" viewBox="0 0 1000 560" preserveAspectRatio="xMidYMid meet">
                    <defs>
                      <linearGradient id="topoLine" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stop-color="rgba(34,211,238,0.15)" />
                        <stop offset="50%" stop-color="rgba(34,211,238,0.9)" />
                        <stop offset="100%" stop-color="rgba(59,130,246,0.2)" />
                      </linearGradient>
                    </defs>
                    <g>
                      <line
                        v-for="line in battlefieldSvgLines"
                        :key="line.key"
                        :x1="line.x1"
                        :y1="line.y1"
                        :x2="line.x2"
                        :y2="line.y2"
                        stroke="url(#topoLine)"
                        stroke-width="2"
                        stroke-dasharray="7 6"
                        opacity="0.85"
                      />
                    </g>
                  </svg>

                  <div
                    v-for="node in battlefieldNodes"
                    :key="node.id"
                    class="group absolute w-[184px] -translate-x-1/2 -translate-y-1/2"
                    :style="{ left: `${node.x / 10}%`, top: `${node.y / 5.6}%` }"
                  >
                    <div class="rounded-xl border bg-gradient-to-b p-3 backdrop-blur-sm transition duration-300 group-hover:-translate-y-1 group-hover:shadow-[0_16px_26px_rgba(8,145,178,0.35)]" :class="nodeTheme(node.type)">
                      <div class="mb-1 flex items-center justify-between gap-2">
                        <div class="flex items-center gap-1.5 text-xs font-semibold">
                          <component :is="resolveNodeIcon(node.type)" class="h-3.5 w-3.5" />
                          <span>{{ node.label }}</span>
                        </div>
                        <span class="h-2.5 w-2.5 rounded-full shadow-[0_0_10px_rgba(255,255,255,0.55)]" :class="statusTheme(node.status)" />
                      </div>
                      <p class="text-[11px] text-slate-200/90">{{ node.detail }}</p>
                    </div>
                    <div class="mx-auto h-2 w-[78%] rounded-b-xl bg-black/35 blur-[1px]" />
                  </div>
                </div>
              </div>
              <div class="mt-4 space-y-2">
                <div v-for="(item, idx) in payload.recent_attacks" :key="`${item.attack_ip}-${idx}`" class="rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
                  <div class="flex items-center justify-between gap-3">
                    <div>
                      <p class="font-mono text-sm text-foreground">{{ item.attack_ip }}</p>
                      <p class="text-xs text-muted-foreground">{{ item.ip_location || '未知地区' }} · {{ item.service_name || '未知服务' }}</p>
                    </div>
                    <Badge variant="outline">{{ formatThreatLevel(item.threat_level) }}</Badge>
                  </div>
                </div>
              </div>
            </template>
            </ScrollArea>
          </CardContent>
        </Card>
      </main>

      <!-- 右栏：AI 侧边栏 + 防御队列 -->
      <aside class="min-h-0 overflow-hidden space-y-4 pl-1 flex flex-col">
        <Card class="flex-1 min-h-0 overflow-hidden">
          <CardHeader class="pb-2">
            <CardTitle class="text-sm flex items-center gap-2"><Bot class="h-4 w-4 text-primary" /> AI 指挥侧边栏</CardTitle>
          </CardHeader>
          <CardContent class="h-[calc(100%-52px)] p-3 flex flex-col gap-3 min-h-0">
            <ScrollArea class="w-full">
              <div class="flex items-center gap-1.5 pb-1">
              <Button
                v-for="item in quickPrompts"
                :key="item.label"
                variant="outline"
                size="sm"
                :disabled="aiLoading"
                @click="sendAiMessage(item.prompt)"
                class="h-7 px-2.5 text-[11px] whitespace-nowrap rounded-full"
              >
                <Sparkles class="h-3 w-3 mr-1" /> {{ item.label }}
              </Button>
              </div>
            </ScrollArea>

            <ScrollArea class="flex-1 rounded-lg border border-border/60 bg-muted/20 p-3">
              <div class="space-y-3">
                <div v-if="!aiMessages.length" class="text-xs text-muted-foreground">输入问题，AI 会基于当前大屏状态给出防御建议。</div>
                <div
                  v-for="(msg, idx) in aiMessages"
                  :key="idx"
                  class="rounded-lg border px-2.5 py-2 text-xs leading-relaxed"
                  :class="msg.role === 'assistant' ? 'bg-primary/5 border-primary/20 text-foreground' : 'bg-background border-border/60 text-muted-foreground'"
                >
                  <p class="mb-1 font-semibold opacity-80">{{ msg.role === 'assistant' ? 'AI' : '你' }}</p>
                  <p class="whitespace-pre-wrap break-words">{{ msg.content }}</p>
                </div>
                <div ref="aiEndRef" />
              </div>
            </ScrollArea>

            <div class="space-y-2">
              <p v-if="aiError" class="text-[11px] text-destructive">{{ aiError }}</p>
              <Textarea v-model="aiInput" :disabled="aiLoading" rows="3" placeholder="例如：请给出当前最高风险攻击源及封禁优先级" />
              <div class="flex items-center gap-2">
                <Button class="flex-1" :disabled="aiLoading || !aiInput.trim()" @click="sendAiMessage()">
                  <Loader2 v-if="aiLoading" class="h-4 w-4 mr-2 animate-spin" />
                  <Send v-else class="h-4 w-4 mr-2" />
                  {{ aiLoading ? '分析中...' : '发送' }}
                </Button>
                <Button variant="outline" :disabled="aiLoading" @click="router.push('/ai')">全屏</Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">防御处置队列</CardTitle>
          </CardHeader>
          <CardContent class="p-0">
            <ScrollArea class="h-56 px-6 py-3">
            <div class="space-y-2">
            <div v-for="item in payload.defense_events" :key="item.attack_ip" class="rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
              <div class="flex items-center justify-between">
                <p class="font-mono text-sm">{{ item.attack_ip }}</p>
                <Badge variant="outline">{{ item.attack_count }} 次</Badge>
              </div>
              <p class="text-xs text-muted-foreground mt-1">{{ item.ip_location || '未知地区' }} · {{ item.latest_time || '-' }}</p>
              <p class="text-xs mt-1" :class="item.ai_decision === 'true' ? 'text-red-400' : 'text-muted-foreground'">AI 决策: {{ item.ai_decision === 'true' ? '建议封禁' : '待分析' }}</p>
            </div>
            <div v-if="!payload.defense_events.length && !loading" class="text-sm text-muted-foreground">暂无待处置事件</div>
            </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </aside>
    </div>
  </div>
</template>
