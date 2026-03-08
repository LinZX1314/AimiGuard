<template>
  <div class="p-6">
    <div class="mx-auto max-w-[1400px] space-y-6">
      <!-- Header -->
      <div class="flex items-center justify-between">
        <div class="space-y-1">
          <h1 class="text-2xl font-semibold flex items-center gap-2">
            <span
              class="inline-flex size-2.5 rounded-full"
              :class="polling ? 'bg-orange-500 animate-pulse' : 'bg-muted-foreground'"
            />
            实时检测
          </h1>
          <p class="text-sm text-muted-foreground">主动探测模式下的实时扫描监控大屏 · WebSocket 实时推送</p>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-xs text-muted-foreground">{{ lastUpdated }}</span>
          <Button variant="outline" size="sm" class="cursor-pointer gap-1.5" @click="refresh">
            <RefreshCw class="size-3.5" :class="loading ? 'animate-spin' : ''" />
            立即刷新
          </Button>
        </div>
      </div>

      <!-- Metrics -->
      <div class="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent class="pt-5 pb-4 flex items-center gap-4">
            <div class="size-10 rounded-lg flex items-center justify-center bg-blue-500/10 shrink-0">
              <Radar class="size-5 text-blue-400" />
            </div>
            <div>
              <p class="text-2xl font-bold tabular-nums" :class="metrics.running > 0 ? 'text-blue-400' : 'text-foreground'">
                {{ loading ? '—' : metrics.running }}
              </p>
              <p class="text-xs text-muted-foreground mt-0.5">运行中任务</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent class="pt-5 pb-4 flex items-center gap-4">
            <div class="size-10 rounded-lg flex items-center justify-center bg-orange-500/10 shrink-0">
              <Target class="size-5 text-orange-400" />
            </div>
            <div>
              <p class="text-2xl font-bold tabular-nums">{{ loading ? '—' : metrics.todayTasks }}</p>
              <p class="text-xs text-muted-foreground mt-0.5">今日扫描任务</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent class="pt-5 pb-4 flex items-center gap-4">
            <div class="size-10 rounded-lg flex items-center justify-center bg-red-500/10 shrink-0">
              <Bug class="size-5 text-red-400" />
            </div>
            <div>
              <p class="text-2xl font-bold tabular-nums" :class="metrics.highFindings > 0 ? 'text-red-400' : 'text-emerald-400'">
                {{ loading ? '—' : metrics.highFindings }}
              </p>
              <p class="text-xs text-muted-foreground mt-0.5">高危漏洞命中</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <div class="grid gap-4 lg:grid-cols-2">
        <!-- 运行中任务流 -->
        <Card>
          <CardHeader class="pb-3 flex-row items-center justify-between">
            <CardTitle class="text-base flex items-center gap-2">
              <span class="inline-flex size-1.5 rounded-full bg-orange-500 animate-pulse" />
              实时探测流
            </CardTitle>
            <router-link to="/probe/scan">
              <Button variant="ghost" size="sm" class="cursor-pointer text-xs gap-1 h-7">
                <ExternalLink class="size-3" />
                扫描管理
              </Button>
            </router-link>
          </CardHeader>
          <CardContent class="space-y-1.5 max-h-[340px] overflow-y-auto pr-1">
            <div v-if="loading && taskStream.length === 0" class="space-y-1.5">
              <Skeleton v-for="i in 5" :key="i" class="h-10 w-full rounded" />
            </div>
            <div v-else-if="taskStream.length === 0" class="py-8 text-center text-sm text-muted-foreground">
              暂无运行中任务，持续监控中…
            </div>
            <div
              v-for="t in taskStream"
              :key="t.id"
              class="flex items-center justify-between rounded-md border border-border px-3 py-2 text-xs gap-2"
              :class="t.state === 'RUNNING' ? 'border-blue-500/30 bg-blue-500/5' : ''"
            >
              <div class="flex items-center gap-2 min-w-0">
                <code class="shrink-0 text-muted-foreground/70">{{ t.time }}</code>
                <code class="font-mono text-muted-foreground truncate max-w-[140px]">{{ t.target }}</code>
                <Badge variant="outline" class="text-[10px] h-4 shrink-0">{{ t.profile }}</Badge>
              </div>
              <Badge :class="stateColor(t.state)" class="text-[10px] h-4 shrink-0">{{ stateLabel(t.state) }}</Badge>
            </div>
          </CardContent>
        </Card>

        <!-- 右列 -->
        <div class="space-y-4">
          <!-- 最新高危发现 -->
          <Card>
            <CardHeader class="pb-3">
              <CardTitle class="text-base flex items-center gap-2">
                <AlertTriangle class="size-4 text-red-400" />
                最新高危发现
              </CardTitle>
            </CardHeader>
            <CardContent class="space-y-1.5">
              <div v-if="loading" class="space-y-1.5">
                <Skeleton v-for="i in 3" :key="i" class="h-8 w-full rounded" />
              </div>
              <div v-else-if="highFindings.length === 0" class="py-4 text-center text-xs text-muted-foreground">
                暂无高危发现
              </div>
              <div
                v-for="f in highFindings"
                :key="f.id"
                class="flex items-center justify-between rounded-md border border-red-500/20 bg-red-500/5 px-3 py-1.5 text-xs gap-2"
              >
                <div class="flex items-center gap-2 min-w-0">
                  <code class="font-mono text-red-300 shrink-0">{{ f.asset }}</code>
                  <span class="text-muted-foreground truncate">{{ f.port ? f.port + '/' : '' }}{{ f.service || 'unknown' }}</span>
                  <span v-if="f.cve" class="text-muted-foreground/60 shrink-0">{{ f.cve }}</span>
                </div>
                <Badge class="bg-red-500/20 text-red-400 border-red-500/30 text-[10px] h-4 shrink-0">HIGH</Badge>
              </div>
            </CardContent>
          </Card>

          <!-- 任务状态汇总 -->
          <Card>
            <CardHeader class="pb-3">
              <CardTitle class="text-base">任务状态分布</CardTitle>
            </CardHeader>
            <CardContent class="space-y-2">
              <div v-if="loading" class="space-y-1.5">
                <Skeleton v-for="i in 4" :key="i" class="h-7 w-full rounded" />
              </div>
              <div v-for="s in stateSummary" v-else :key="s.state" class="flex items-center justify-between rounded-md border border-border px-3 py-1.5 text-xs">
                <div class="flex items-center gap-2">
                  <Badge :class="stateColor(s.state)" class="text-[10px] h-4 w-16 justify-center">{{ stateLabel(s.state) }}</Badge>
                  <div class="h-1.5 rounded-full bg-muted overflow-hidden w-24">
                    <div :class="stateBarColor(s.state)" class="h-full rounded-full transition-all" :style="{ width: s.pct + '%' }" />
                  </div>
                </div>
                <span class="font-semibold tabular-nums">{{ s.count }}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { scanApi, type ScanFinding, type ScanTask } from '@/api/scan'
import { apiClient } from '@/api/client'
import { RealtimeChannel } from '@/api/realtime'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertTriangle, Bug, ExternalLink, Radar, RefreshCw, Target } from 'lucide-vue-next'

let realtimeChannel: RealtimeChannel | null = null
let refreshTimer: ReturnType<typeof setTimeout> | null = null

interface StreamTask {
  id: number
  target: string
  state: string
  profile: string
  time: string
}

const loading = ref(false)
const polling = ref(false)
const lastUpdated = ref('')

const metrics = ref({ running: 0, todayTasks: 0, highFindings: 0 })
const taskStream = ref<StreamTask[]>([])
const highFindings = ref<ScanFinding[]>([])

const scheduleRefresh = () => {
  if (refreshTimer) return
  refreshTimer = setTimeout(() => {
    refreshTimer = null
    void refresh()
  }, 150)
}

const loadAll = async () => {
  try {
    const [overview, recentTasks, hFindings] = await Promise.all([
      apiClient.get('/overview/metrics').catch(() => null),
      scanApi.getTasks({ page: 1, page_size: 20 }),
      scanApi.getFindings({ severity: 'HIGH', page_size: 6 }),
    ])

    // Metrics
    const ov: any = overview
    const ovData = ov?.data ?? ov
    metrics.value.running = ovData?.probe?.running_tasks ?? 0
    metrics.value.todayTasks = ovData?.probe?.today_tasks ?? 0
    metrics.value.highFindings = hFindings.total

    // Task stream (running first)
    const tasks: ScanTask[] = recentTasks.items
    tasks.sort((a, b) => {
      const order = ['RUNNING', 'DISPATCHED', 'CREATED', 'PARSED', 'REPORTED', 'FAILED']
      return order.indexOf(a.state) - order.indexOf(b.state)
    })
    taskStream.value = tasks.slice(0, 20).map((t) => ({
      id: t.id,
      target: t.target,
      state: t.state,
      profile: t.profile || 'default',
      time: t.created_at
        ? new Date(t.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
        : '—',
    }))

    // High findings
    highFindings.value = hFindings.items
  } catch { /* ignore */ }
}

const stateSummary = computed(() => {
  const counts: Record<string, number> = {}
  for (const t of taskStream.value) {
    counts[t.state] = (counts[t.state] || 0) + 1
  }
  const total = taskStream.value.length || 1
  return Object.entries(counts).map(([state, count]) => ({
    state,
    count,
    pct: Math.round((count / total) * 100),
  }))
})

const refresh = async () => {
  loading.value = true
  try {
    await loadAll()
    lastUpdated.value = new Date().toLocaleTimeString('zh-CN')
  } finally {
    loading.value = false
  }
}

const stateColor = (s: string) => {
  const m: Record<string, string> = {
    RUNNING: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    REPORTED: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    FAILED: 'bg-destructive/15 text-destructive border-destructive/30',
    DISPATCHED: 'bg-blue-500/15 text-blue-300 border-blue-500/20',
    PARSED: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
    CREATED: 'bg-muted text-muted-foreground',
  }
  return m[s] || 'bg-muted text-muted-foreground'
}

const stateLabel = (s: string) => {
  const m: Record<string, string> = {
    CREATED: '待调度', DISPATCHED: '已分发', RUNNING: '运行中',
    PARSED: '解析中', REPORTED: '已完成', FAILED: '失败',
  }
  return m[s] || s
}

const stateBarColor = (s: string) => {
  const m: Record<string, string> = {
    RUNNING: 'bg-blue-500', REPORTED: 'bg-emerald-500',
    FAILED: 'bg-red-500', PARSED: 'bg-purple-500',
    DISPATCHED: 'bg-blue-400', CREATED: 'bg-muted-foreground',
  }
  return m[s] || 'bg-muted-foreground'
}

onMounted(async () => {
  await refresh()
  realtimeChannel = new RealtimeChannel('/ws/scan/tasks', {
    onConnectionChange: (connected) => {
      polling.value = connected
    },
    onEvent: (event) => {
      if (event.type === 'ready') return
      scheduleRefresh()
    },
  })
  realtimeChannel.connect()
})

onUnmounted(() => {
  polling.value = false
  if (refreshTimer) {
    clearTimeout(refreshTimer)
    refreshTimer = null
  }
  realtimeChannel?.close()
  realtimeChannel = null
})
</script>
