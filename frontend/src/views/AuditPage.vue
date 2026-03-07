<template>
  <div class="p-6">
    <div class="mx-auto max-w-[1400px] space-y-6">
      <div class="flex items-center justify-between">
        <div class="space-y-1">
          <h1 class="text-2xl font-semibold">Audit Center</h1>
          <p class="text-sm text-muted-foreground">Query key operations and trace by trace_id.</p>
        </div>
        <Button variant="outline" size="sm" class="cursor-pointer gap-1.5" :disabled="loading" @click="loadLogs">
          <RefreshCw class="size-3.5" :class="loading ? 'animate-spin' : ''" />
          Refresh
        </Button>
      </div>

      <Card>
        <CardContent class="pt-4 pb-3">
          <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <input
              v-model="query.trace_id"
              placeholder="trace_id"
              class="h-8 w-full rounded-md border border-input bg-background px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            />
            <input
              v-model="query.actor"
              placeholder="actor"
              class="h-8 w-full rounded-md border border-input bg-background px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            />
            <input
              v-model="query.action"
              placeholder="action"
              class="h-8 w-full rounded-md border border-input bg-background px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            />
            <select
              v-model="query.result"
              class="h-8 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <option value="">all results</option>
              <option value="success">success</option>
              <option value="failed">failed</option>
            </select>
            <Button size="sm" class="cursor-pointer h-8" @click="search">Search</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader class="pb-2 flex-row items-center justify-between">
          <CardTitle class="text-base">Audit Logs</CardTitle>
          <span class="text-xs text-muted-foreground">total {{ total }}</span>
        </CardHeader>
        <CardContent class="p-0">
          <div v-if="loading" class="p-4 space-y-2">
            <Skeleton v-for="i in 6" :key="i" class="h-10 w-full rounded" />
          </div>

          <div v-else-if="logs.length === 0" class="py-12 text-center text-sm text-muted-foreground">
            No audit logs.
          </div>

          <div v-else class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-border bg-muted/30">
                  <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground w-36">time</th>
                  <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground w-24">actor</th>
                  <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">action</th>
                  <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground w-32">target</th>
                  <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground w-16">result</th>
                  <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground w-36">trace_id</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in logs"
                  :key="row.id"
                  class="border-b border-border/50 hover:bg-muted/20 transition-colors cursor-pointer"
                  @click="selectedRow = selectedRow?.id === row.id ? null : row"
                >
                  <td class="px-4 py-2 text-xs text-muted-foreground whitespace-nowrap">{{ formatTime(row.created_at) }}</td>
                  <td class="px-4 py-2 text-xs font-medium">{{ row.actor }}</td>
                  <td class="px-4 py-2 text-xs font-mono">{{ row.action }}</td>
                  <td class="px-4 py-2 text-xs text-muted-foreground truncate max-w-[128px]">{{ row.target }}</td>
                  <td class="px-4 py-2">
                    <Badge
                      :class="row.result === 'success'
                        ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                        : 'bg-destructive/15 text-destructive border-destructive/30'"
                      class="text-[10px] h-4"
                    >
                      {{ row.result }}
                    </Badge>
                  </td>
                  <td class="px-4 py-2">
                    <code class="text-[10px] text-muted-foreground">{{ row.trace_id?.slice(0, 16) }}…</code>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-if="selectedRow" class="border-t border-border bg-muted/10 p-4 space-y-2">
            <p class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">details</p>
            <div class="grid gap-2 sm:grid-cols-2 text-xs">
              <div><span class="text-muted-foreground">trace_id: </span><code>{{ selectedRow.trace_id }}</code></div>
              <div><span class="text-muted-foreground">target_type: </span>{{ selectedRow.target_type || '-' }}</div>
              <div><span class="text-muted-foreground">target_ip: </span>{{ selectedRow.target_ip || '-' }}</div>
              <div><span class="text-muted-foreground">error: </span>{{ selectedRow.error_message || '-' }}</div>
              <div class="sm:col-span-2"><span class="text-muted-foreground">reason: </span>{{ selectedRow.reason || '-' }}</div>
            </div>
          </div>

          <div v-if="totalPages > 1" class="flex items-center justify-between px-4 py-3 border-t border-border">
            <span class="text-xs text-muted-foreground">page {{ page }} / {{ totalPages }}</span>
            <div class="flex gap-1">
              <Button variant="outline" size="sm" class="h-7 text-xs cursor-pointer" :disabled="page <= 1" @click="changePage(page - 1)">Prev</Button>
              <Button variant="outline" size="sm" class="h-7 text-xs cursor-pointer" :disabled="page >= totalPages" @click="changePage(page + 1)">Next</Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { apiClient } from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { RefreshCw } from 'lucide-vue-next'

interface AuditLog {
  id: number
  actor: string
  action: string
  target: string
  target_type: string | null
  target_ip: string | null
  result: string
  reason: string | null
  error_message: string | null
  trace_id: string
  created_at: string
}

const route = useRoute()
const logs = ref<AuditLog[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = 50
const totalPages = ref(0)
const selectedRow = ref<AuditLog | null>(null)

const query = reactive({
  trace_id: '',
  actor: '',
  action: '',
  result: '',
})

const syncQueryFromRoute = () => {
  const traceFromRoute = route.query.trace_id
  query.trace_id = typeof traceFromRoute === 'string' ? traceFromRoute : ''
}

const loadLogs = async () => {
  loading.value = true
  selectedRow.value = null
  try {
    const params: Record<string, string | number> = { page: page.value, page_size: pageSize }
    if (query.trace_id) params.trace_id = query.trace_id
    if (query.actor) params.actor = query.actor
    if (query.action) params.action = query.action
    if (query.result) params.result = query.result

    const res: any = await apiClient.get('/system/audit/logs', { params })
    const data = res?.data ?? res
    logs.value = data?.items ?? []
    total.value = data?.total ?? 0
    totalPages.value = data?.total_pages ?? 0
  } catch {
    logs.value = []
  } finally {
    loading.value = false
  }
}

const search = () => {
  page.value = 1
  loadLogs()
}

const changePage = (p: number) => {
  page.value = p
  loadLogs()
}

const formatTime = (t: string) =>
  t
    ? new Date(t).toLocaleString('zh-CN', {
      month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    })
    : '-'

watch(() => route.query.trace_id, () => {
  syncQueryFromRoute()
})

onMounted(() => {
  syncQueryFromRoute()
  loadLogs()
})
</script>