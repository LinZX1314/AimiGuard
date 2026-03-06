<template>
  <div class="p-6">
    <div class="mx-auto max-w-[1200px] space-y-6">
      <!-- Header -->
      <div class="space-y-1">
        <h1 class="text-2xl font-semibold">系统设置</h1>
        <p class="text-sm text-muted-foreground">系统级配置与管理入口</p>
      </div>

      <!-- 系统模式 -->
      <Card>
        <CardHeader class="pb-3 flex-row items-center justify-between">
          <div class="space-y-0.5">
            <CardTitle class="text-base flex items-center gap-2">
              <Shield class="size-4 text-primary" />
              系统运行模式
            </CardTitle>
            <p class="text-xs text-muted-foreground">控制防御策略的主动/被动策略切换</p>
          </div>
          <Badge
            :class="currentMode === 'ACTIVE'
              ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
              : 'bg-amber-500/15 text-amber-400 border-amber-500/30'"
          >
            {{ currentMode === 'ACTIVE' ? '主动防御' : '被动监控' }}
          </Badge>
        </CardHeader>
        <CardContent class="space-y-4">
          <div v-if="modeLoading" class="space-y-2">
            <Skeleton class="h-8 w-full rounded" />
          </div>
          <div v-else class="grid gap-3 sm:grid-cols-2">
            <!-- PASSIVE -->
            <button
              :class="[
                'rounded-lg border-2 p-4 text-left transition-all',
                currentMode === 'PASSIVE'
                  ? 'border-primary bg-primary/5'
                  : 'border-border hover:border-muted-foreground/40',
              ]"
              @click="setMode('PASSIVE')"
            >
              <div class="flex items-center gap-2 mb-1.5">
                <Eye class="size-4 text-amber-400" />
                <span class="font-semibold text-sm">被动监控（PASSIVE）</span>
              </div>
              <p class="text-xs text-muted-foreground">仅记录和告警，不自动执行封禁动作。适合初期部署或误报率高时使用。</p>
            </button>
            <!-- ACTIVE -->
            <button
              :class="[
                'rounded-lg border-2 p-4 text-left transition-all',
                currentMode === 'ACTIVE'
                  ? 'border-emerald-500 bg-emerald-500/5'
                  : 'border-border hover:border-muted-foreground/40',
              ]"
              @click="confirmSetMode('ACTIVE')"
            >
              <div class="flex items-center gap-2 mb-1.5">
                <ShieldCheck class="size-4 text-emerald-400" />
                <span class="font-semibold text-sm">主动防御（ACTIVE）</span>
              </div>
              <p class="text-xs text-muted-foreground">AI 评分达到阈值时自动触发封禁，高危 IP 立即阻断。需确认操作。</p>
            </button>
          </div>
          <div v-if="modeInfo" class="text-xs text-muted-foreground space-y-0.5 pt-1 border-t border-border">
            <p>最后操作：<span class="text-foreground">{{ modeInfo.operator }}</span></p>
            <p>时间：{{ formatTime(modeInfo.updated_at) }}</p>
            <p v-if="modeInfo.reason">原因：{{ modeInfo.reason }}</p>
          </div>
          <p v-if="modeMsg" class="text-xs" :class="modeMsgOk ? 'text-emerald-400' : 'text-destructive'">{{ modeMsg }}</p>
        </CardContent>
      </Card>

      <!-- 版本信息 -->
      <Card>
        <CardHeader class="pb-3">
          <CardTitle class="text-base flex items-center gap-2">
            <Info class="size-4 text-muted-foreground" />
            版本信息
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div v-if="versionLoading" class="space-y-2">
            <Skeleton v-for="i in 4" :key="i" class="h-6 w-full rounded" />
          </div>
          <div v-else class="grid gap-2 sm:grid-cols-2 text-sm">
            <div class="flex justify-between rounded-md border border-border px-3 py-2">
              <span class="text-muted-foreground">应用版本</span>
              <code class="font-semibold">{{ version.app_version }}</code>
            </div>
            <div class="flex justify-between rounded-md border border-border px-3 py-2">
              <span class="text-muted-foreground">Git Commit</span>
              <code class="font-semibold">{{ version.git_commit?.slice(0, 8) }}</code>
            </div>
            <div class="flex justify-between rounded-md border border-border px-3 py-2">
              <span class="text-muted-foreground">Schema 版本</span>
              <code class="font-semibold">{{ version.schema_version }}</code>
            </div>
            <div class="flex justify-between rounded-md border border-border px-3 py-2">
              <span class="text-muted-foreground">运行环境</span>
              <Badge variant="outline" class="text-xs h-5">{{ version.env }}</Badge>
            </div>
            <div class="sm:col-span-2 flex justify-between rounded-md border border-border px-3 py-2">
              <span class="text-muted-foreground">构建时间</span>
              <span>{{ formatTime(version.build_time) }}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- 当前用户信息 -->
      <Card>
        <CardHeader class="pb-3">
          <CardTitle class="text-base flex items-center gap-2">
            <UserCircle class="size-4 text-muted-foreground" />
            当前用户
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div v-if="profileLoading" class="space-y-2">
            <Skeleton v-for="i in 3" :key="i" class="h-6 w-full rounded" />
          </div>
          <div v-else class="space-y-2 text-sm">
            <div class="flex justify-between rounded-md border border-border px-3 py-2">
              <span class="text-muted-foreground">用户名</span>
              <span class="font-semibold">{{ profile.username }}</span>
            </div>
            <div class="flex justify-between rounded-md border border-border px-3 py-2">
              <span class="text-muted-foreground">角色</span>
              <Badge variant="outline" class="text-xs capitalize">{{ profile.role }}</Badge>
            </div>
            <div class="flex justify-between rounded-md border border-border px-3 py-2">
              <span class="text-muted-foreground">邮箱</span>
              <span>{{ profile.email || '—' }}</span>
            </div>
            <div class="rounded-md border border-border px-3 py-2">
              <p class="text-muted-foreground mb-1.5">权限点</p>
              <div class="flex flex-wrap gap-1">
                <Badge
                  v-for="perm in profile.permissions"
                  :key="perm"
                  variant="outline"
                  class="text-[10px] h-4 font-mono"
                >{{ perm }}</Badge>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- 确认切换 ACTIVE 弹窗 -->
      <div
        v-if="confirmOpen"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
        @click.self="confirmOpen = false"
      >
        <div class="mx-4 w-full max-w-sm rounded-xl border border-border bg-background p-6 shadow-2xl space-y-4">
          <div class="flex items-center gap-2 text-amber-400">
            <AlertTriangle class="size-5" />
            <span class="font-semibold">切换到主动防御模式</span>
          </div>
          <p class="text-sm text-muted-foreground">主动防御模式下，AI 评分 ≥ 80 分的事件将自动触发封禁，请确认操作。</p>
          <div class="space-y-1.5">
            <label class="text-xs font-medium">操作原因（必填）</label>
            <input
              v-model="modeReason"
              placeholder="请说明切换原因…"
              class="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <div class="flex gap-2 justify-end">
            <Button variant="outline" size="sm" class="cursor-pointer" @click="confirmOpen = false">取消</Button>
            <Button size="sm" class="cursor-pointer" :disabled="!modeReason.trim() || modeSaving" @click="setMode('ACTIVE')">
              {{ modeSaving ? '切换中…' : '确认切换' }}
            </Button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { apiClient } from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertTriangle, Eye, Info, Shield, ShieldCheck, UserCircle } from 'lucide-vue-next'

// ── 模式 ──
const currentMode = ref('PASSIVE')
const modeInfo = ref<{ operator: string; updated_at: string; reason: string | null } | null>(null)
const modeLoading = ref(false)
const modeSaving = ref(false)
const modeMsg = ref('')
const modeMsgOk = ref(true)
const confirmOpen = ref(false)
const modeReason = ref('')

// ── 版本 ──
const versionLoading = ref(false)
const version = ref({ app_version: '—', git_commit: '—', schema_version: '—', env: '—', build_time: '' })

// ── 用户 ──
const profileLoading = ref(false)
const profile = ref<{ username: string; role: string; email: string | null; permissions: string[] }>({
  username: '—', role: '—', email: null, permissions: [],
})

const loadMode = async () => {
  modeLoading.value = true
  try {
    const res: any = await apiClient.get('/system/mode')
    const data = res?.data ?? res
    currentMode.value = data?.mode ?? 'PASSIVE'
    modeInfo.value = {
      operator: data?.operator ?? '—',
      updated_at: data?.updated_at ?? '',
      reason: data?.reason ?? null,
    }
  } catch {
    currentMode.value = 'PASSIVE'
  } finally {
    modeLoading.value = false
  }
}

const confirmSetMode = (mode: string) => {
  if (mode === 'ACTIVE') {
    modeReason.value = ''
    confirmOpen.value = true
  } else {
    setMode(mode)
  }
}

const setMode = async (mode: string) => {
  modeSaving.value = true
  modeMsg.value = ''
  try {
    const res: any = await apiClient.post('/system/mode', {
      mode,
      reason: modeReason.value || `切换为 ${mode}`,
    })
    const data = res?.data ?? res
    currentMode.value = data?.mode ?? mode
    modeInfo.value = { operator: data?.operator ?? '—', updated_at: data?.updated_at ?? '', reason: data?.reason ?? null }
    modeMsgOk.value = true
    modeMsg.value = `已切换到 ${mode} 模式`
    confirmOpen.value = false
    modeReason.value = ''
  } catch (e: any) {
    modeMsgOk.value = false
    modeMsg.value = e?.response?.data?.detail || '切换失败'
  } finally {
    modeSaving.value = false
    setTimeout(() => { modeMsg.value = '' }, 3000)
  }
}

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

const loadProfile = async () => {
  profileLoading.value = true
  try {
    const res: any = await apiClient.get('/system/profile')
    const data = res?.data ?? res
    profile.value = {
      username: data?.username ?? '—',
      role: data?.role ?? '—',
      email: data?.email ?? null,
      permissions: data?.permissions ?? [],
    }
  } catch {
    // ignore
  } finally {
    profileLoading.value = false
  }
}

const formatTime = (t: string) =>
  t ? new Date(t).toLocaleString('zh-CN') : '—'

onMounted(() => {
  loadMode()
  loadVersion()
  loadProfile()
})
</script>
