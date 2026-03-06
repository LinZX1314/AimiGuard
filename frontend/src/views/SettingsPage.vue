<template>
  <div>
    <!-- 页头 + Tab 导航（统一 padding） -->
    <div class="px-6 pt-6">
      <div class="mx-auto max-w-[1200px]">
        <div class="mb-5 space-y-1">
          <h1 class="text-2xl font-semibold">系统设置</h1>
          <p class="text-sm text-muted-foreground">系统级配置与管理入口</p>
        </div>

        <Tabs v-model="activeTab">
          <TabsList class="mb-0 w-full justify-start h-auto p-1 gap-1">
            <TabsTrigger value="overview" class="flex items-center gap-1.5 px-4 py-2">
              <LayoutDashboard class="size-3.5" />
              系统概览
            </TabsTrigger>
            <TabsTrigger value="integrations" class="flex items-center gap-1.5 px-4 py-2">
              <Puzzle class="size-3.5" />
              插件与联动
            </TabsTrigger>
            <TabsTrigger value="audit" class="flex items-center gap-1.5 px-4 py-2">
              <FileText class="size-3.5" />
              审计日志
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
    </div>

    <!-- Tab 内容区（各自管理布局） -->
    <div v-show="activeTab === 'overview'" class="p-6 pt-4">
      <div class="mx-auto max-w-[1200px] space-y-5">
        <!-- 运行架构 -->
        <div>
          <div class="flex items-center justify-between mb-3">
            <div>
              <h2 class="text-sm font-semibold flex items-center gap-2">
                <Shield class="size-4 text-primary" />
                系统运行架构
              </h2>
              <p class="text-xs text-muted-foreground mt-0.5">防御坚守与主动探测的运行机制说明</p>
            </div>
            <Badge class="bg-blue-500/15 text-blue-400 border-blue-500/30 shrink-0">
              防御坚守持续运行中
            </Badge>
          </div>
          <div class="grid gap-3 sm:grid-cols-2">
            <div class="rounded-lg border-2 border-blue-500/40 bg-blue-500/5 p-4 space-y-2">
              <div class="flex items-center gap-2">
                <Shield class="size-4 text-blue-400" />
                <span class="font-semibold text-sm text-blue-400">防御坚守（始终运行）</span>
              </div>
              <p class="text-xs text-muted-foreground leading-relaxed">
                后台持续采集 HFish 蜜罐告警、AI 评分、审批执行封禁，全程自动运行，无需手动开启。
                这是系统的<span class="text-foreground font-medium">默认且唯一持续状态</span>。
              </p>
            </div>
            <div class="rounded-lg border-2 border-orange-500/40 bg-orange-500/5 p-4 space-y-2">
              <div class="flex items-center gap-2">
                <ScanSearch class="size-4 text-orange-400" />
                <span class="font-semibold text-sm text-orange-400">主动探测（手动触发）</span>
              </div>
              <p class="text-xs text-muted-foreground leading-relaxed">
                主动探测任务需在顶栏切换到<span class="text-foreground font-medium">「主动探测」面板</span>后，
                手动添加扫描任务来触发。不存在系统级"主动模式"开关，避免资源持续消耗。
              </p>
            </div>
          </div>
          <div class="mt-3 rounded-md bg-muted/30 border border-border px-4 py-3 text-xs text-muted-foreground space-y-1.5">
            <p class="flex items-start gap-2">
              <span class="inline-block size-1.5 rounded-full bg-blue-400 shrink-0 mt-1"></span>
              顶栏「防御坚守 / 主动探测」切换的是<strong class="text-foreground">展示面板</strong>，不影响后端任何运行状态。
            </p>
            <p class="flex items-start gap-2">
              <span class="inline-block size-1.5 rounded-full bg-orange-400 shrink-0 mt-1"></span>
              如需执行主动探测，请切换到主动探测面板 → 扫描管理 → 新建扫描任务。
            </p>
          </div>
        </div>

        <!-- 版本信息 -->
        <div class="border-t border-border pt-5">
          <h2 class="text-sm font-semibold flex items-center gap-2 mb-3">
            <Package class="size-4 text-muted-foreground" />
            版本信息
          </h2>
          <div v-if="versionLoading" class="space-y-2">
            <Skeleton v-for="i in 5" :key="i" class="h-9 w-full rounded-md" />
          </div>
          <div v-else class="grid gap-2 sm:grid-cols-2 text-sm">
            <div class="flex justify-between items-center rounded-md border border-border px-4 py-2.5">
              <span class="text-muted-foreground">应用版本</span>
              <code class="font-semibold bg-muted/50 px-2 py-0.5 rounded text-xs">{{ version.app_version }}</code>
            </div>
            <div class="flex justify-between items-center rounded-md border border-border px-4 py-2.5">
              <span class="text-muted-foreground">Git Commit</span>
              <code class="font-semibold bg-muted/50 px-2 py-0.5 rounded text-xs font-mono">{{ version.git_commit?.slice(0, 8) }}</code>
            </div>
            <div class="flex justify-between items-center rounded-md border border-border px-4 py-2.5">
              <span class="text-muted-foreground">Schema 版本</span>
              <code class="font-semibold bg-muted/50 px-2 py-0.5 rounded text-xs">{{ version.schema_version }}</code>
            </div>
            <div class="flex justify-between items-center rounded-md border border-border px-4 py-2.5">
              <span class="text-muted-foreground">运行环境</span>
              <Badge variant="outline" class="text-xs h-5">{{ version.env }}</Badge>
            </div>
            <div class="sm:col-span-2 flex justify-between items-center rounded-md border border-border px-4 py-2.5">
              <span class="text-muted-foreground">构建时间</span>
              <span class="text-xs">{{ formatTime(version.build_time) }}</span>
            </div>
          </div>
        </div>

        <!-- 可观测性（系统的一部分） -->
        <div class="border-t border-border pt-5">
          <h2 class="text-sm font-semibold flex items-center gap-2 mb-4">
            <Activity class="size-4 text-muted-foreground" />
            系统可观测性
          </h2>
          <ObservabilityPage />
        </div>
      </div>
    </div>

    <!-- 插件与联动（有内部双层 tab） -->
    <div v-show="activeTab === 'integrations'">
      <IntegrationsPage />
    </div>

    <!-- 审计日志 -->
    <div v-show="activeTab === 'audit'">
      <AuditPage />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { apiClient } from '@/api/client'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Activity, FileText, LayoutDashboard, Package, Puzzle, ScanSearch, Shield } from 'lucide-vue-next'
import ObservabilityPage from '@/views/ObservabilityPage.vue'
import IntegrationsPage from '@/views/IntegrationsPage.vue'
import AuditPage from '@/views/AuditPage.vue'

const activeTab = ref('overview')

// ── 版本 ──
const versionLoading = ref(false)
const version = ref({ app_version: '—', git_commit: '—', schema_version: '—', env: '—', build_time: '' })

const loadVersion = async () => {
  versionLoading.value = true
  try {
    const res: any = await apiClient.get('/system/version')
    const data = res?.data ?? res
    version.value = {
      app_version: data?.app_version ?? '—',
      git_commit: data?.git_commit ?? '—',
      schema_version: data?.schema_version ?? '—',
      env: data?.env ?? '—',
      build_time: data?.build_time ?? '',
    }
  } catch {
    // ignore
  } finally {
    versionLoading.value = false
  }
}

const formatTime = (t: string) =>
  t ? new Date(t).toLocaleString('zh-CN') : '—'

onMounted(() => {
  loadVersion()
})
</script>
