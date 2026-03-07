<template>
  <div class="p-6">
    <div class="mx-auto max-w-[1440px] space-y-6">
      <div class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div class="space-y-1">
          <h1 class="text-2xl font-semibold tracking-tight">流程目录</h1>
          <p class="text-sm text-muted-foreground">查看工作流版本状态并进入只读图谱，支持 trace_id 一键跳转审计链路。</p>
        </div>
        <div class="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
          <input
            v-model="traceIdInput"
            type="text"
            placeholder="输入 trace_id 后跳到审计"
            class="h-9 w-full min-w-[220px] rounded-md border border-input bg-background px-3 text-sm shadow-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <Button
            variant="outline"
            size="sm"
            class="cursor-pointer"
            :disabled="!traceIdInput.trim()"
            @click="jumpToAudit"
          >
            trace 跳转
          </Button>
        </div>
      </div>

      <Card>
        <CardContent class="pt-5">
          <div class="grid gap-3 lg:grid-cols-[1fr_180px_160px]">
            <input
              v-model="filters.keyword"
              type="text"
              placeholder="按流程名 / workflow_key 检索"
              class="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              @keyup.enter="search"
            />
            <select
              v-model="filters.definition_state"
              class="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <option value="">全部状态</option>
              <option v-for="state in stateOptions" :key="state" :value="state">{{ state }}</option>
            </select>
            <div class="flex gap-2">
              <Button size="sm" class="cursor-pointer flex-1" :disabled="loading" @click="search">
                {{ loading ? '加载中...' : '查询' }}
              </Button>
              <Button variant="outline" size="sm" class="cursor-pointer" :disabled="loading" @click="resetFilters">
                重置
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader class="flex-row items-center justify-between">
          <CardTitle class="text-base">流程清单</CardTitle>
          <div class="flex items-center gap-2">
            <span class="text-xs text-muted-foreground">共 {{ total }} 条</span>
            <Button variant="outline" size="sm" class="h-8 cursor-pointer" :disabled="loading" @click="loadWorkflows">
              刷新
            </Button>
            <Button v-if="isAdmin" size="sm" class="h-8 cursor-pointer" @click="router.push('/workflow/new')">
              新建流程
            </Button>
          </div>
        </CardHeader>
        <CardContent class="p-0">
          <div v-if="errorText" class="px-4 py-3 text-xs text-destructive border-t border-border bg-destructive/5">
            {{ errorText }}
          </div>

          <div v-if="loading" class="space-y-2 p-4">
            <Skeleton v-for="index in 5" :key="index" class="h-12 w-full rounded-md" />
          </div>

          <div v-else-if="items.length === 0" class="px-4 py-16 text-center text-sm text-muted-foreground">
            没有符合条件的流程。
          </div>

          <div v-else class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-border bg-muted/20">
                  <th class="px-4 py-3 text-left text-xs font-medium text-muted-foreground">流程</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-muted-foreground">状态</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-muted-foreground">版本</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-muted-foreground">最近更新时间</th>
                  <th class="px-4 py-3 text-right text-xs font-medium text-muted-foreground">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in items" :key="item.id" class="border-b border-border/60 hover:bg-muted/20">
                  <td class="px-4 py-3 align-top">
                    <div class="space-y-1">
                      <p class="font-medium text-foreground">{{ item.name }}</p>
                      <p class="font-mono text-xs text-muted-foreground">{{ item.workflow_key }}</p>
                      <p v-if="item.description" class="text-xs text-muted-foreground line-clamp-2">{{ item.description }}</p>
                    </div>
                  </td>
                  <td class="px-4 py-3 align-top">
                    <Badge class="text-[10px]" :class="stateClass(item.definition_state)">
                      {{ item.definition_state }}
                    </Badge>
                  </td>
                  <td class="px-4 py-3 align-top">
                    <div class="space-y-1 text-xs text-muted-foreground">
                      <p>最新 v{{ item.latest_version }}</p>
                      <p>发布 {{ item.published_version ? `v${item.published_version}` : '--' }}</p>
                    </div>
                  </td>
                  <td class="px-4 py-3 align-top text-xs text-muted-foreground">
                    {{ formatDateTime(item.updated_at) }}
                  </td>
                  <td class="px-4 py-3 align-top text-right">
                    <div class="flex justify-end gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        class="h-8 cursor-pointer"
                        @click="goReadonlyGraph(item.id)"
                      >
                        查看图谱
                      </Button>
                      <Button
                        v-if="isAdmin"
                        variant="outline"
                        size="sm"
                        class="h-8 cursor-pointer"
                        @click="router.push(`/workflow/${item.id}/edit`)"
                      >
                        编辑
                      </Button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-if="totalPages > 1" class="flex items-center justify-between border-t border-border px-4 py-3">
            <span class="text-xs text-muted-foreground">第 {{ page }} / {{ totalPages }} 页</span>
            <div class="flex gap-2">
              <Button variant="outline" size="sm" class="h-8 cursor-pointer" :disabled="page <= 1 || loading" @click="changePage(page - 1)">
                上一页
              </Button>
              <Button variant="outline" size="sm" class="h-8 cursor-pointer" :disabled="page >= totalPages || loading" @click="changePage(page + 1)">
                下一页
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { workflowApi, type WorkflowDefinitionItem } from '@/api/workflow'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { getRequestErrorMessage } from '@/api/client'

const router = useRouter()

const isAdmin = computed(() => {
  try {
    const raw = localStorage.getItem('user_info')
    if (!raw) return false
    const info = JSON.parse(raw)
    return info?.role === 'admin'
  } catch { return false }
})

const stateOptions = ['DRAFT', 'VALIDATED', 'PUBLISHED', 'ARCHIVED']
const pageSize = 10

const loading = ref(false)
const errorText = ref('')
const page = ref(1)
const total = ref(0)
const items = ref<WorkflowDefinitionItem[]>([])
const traceIdInput = ref('')

const filters = reactive({
  keyword: '',
  definition_state: '',
})

const totalPages = computed(() => {
  const pages = Math.ceil(total.value / pageSize)
  return pages > 0 ? pages : 1
})

const stateClass = (state: string) => {
  if (state === 'PUBLISHED') return 'border-cyan-500/30 bg-cyan-500/12 text-cyan-300'
  if (state === 'VALIDATED') return 'border-emerald-500/30 bg-emerald-500/12 text-emerald-300'
  if (state === 'ARCHIVED') return 'border-slate-500/30 bg-slate-500/12 text-slate-300'
  return 'border-amber-500/30 bg-amber-500/12 text-amber-300'
}

const formatDateTime = (value: string | null) => {
  if (!value) return '--'
  return new Date(value).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const loadWorkflows = async () => {
  loading.value = true
  errorText.value = ''
  try {
    const data = await workflowApi.getWorkflows({
      page: page.value,
      page_size: pageSize,
      keyword: filters.keyword.trim() || undefined,
      definition_state: filters.definition_state || undefined,
    })
    items.value = data.items
    total.value = data.total
  } catch (error) {
    items.value = []
    total.value = 0
    errorText.value = getRequestErrorMessage(error, '加载流程列表失败')
  } finally {
    loading.value = false
  }
}

const search = () => {
  page.value = 1
  loadWorkflows()
}

const resetFilters = () => {
  filters.keyword = ''
  filters.definition_state = ''
  search()
}

const changePage = (nextPage: number) => {
  page.value = nextPage
  loadWorkflows()
}

const goReadonlyGraph = (workflowId: number) => {
  router.push(`/workflow/${workflowId}/graph`)
}

const jumpToAudit = () => {
  const traceId = traceIdInput.value.trim()
  if (!traceId) return
  router.push({ path: '/audit', query: { trace_id: traceId } })
}

onMounted(loadWorkflows)
</script>
