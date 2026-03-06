<template>
  <div class="p-6">
    <div class="mx-auto max-w-[860px] space-y-6">
      <!-- Header -->
      <div class="space-y-1">
        <h1 class="text-2xl font-semibold">用户中心</h1>
        <p class="text-sm text-muted-foreground">当前用户信息与安全设置</p>
      </div>

      <!-- 账户卡 -->
      <Card>
        <CardContent class="pt-5 pb-5">
          <div class="flex items-center gap-5">
            <!-- 头像 -->
            <div class="size-16 rounded-full bg-primary/15 flex items-center justify-center text-2xl font-bold text-primary shrink-0">
              {{ profile.username.charAt(0).toUpperCase() }}
            </div>
            <div class="space-y-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <p class="text-xl font-semibold">{{ profile.username }}</p>
                <Badge :class="roleColor" class="capitalize">{{ roleText }}</Badge>
                <Badge variant="outline" class="text-xs text-emerald-400 border-emerald-500/30 bg-emerald-500/10">正常</Badge>
              </div>
              <p class="text-sm text-muted-foreground">{{ profile.email || '未设置邮箱' }}</p>
              <p v-if="profile.full_name" class="text-sm text-muted-foreground">{{ profile.full_name }}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div class="grid gap-6 md:grid-cols-2">
        <!-- 账户信息 -->
        <Card>
          <CardHeader class="pb-3">
            <CardTitle class="text-base flex items-center gap-2">
              <UserCircle class="size-4 text-muted-foreground" />
              账户信息
            </CardTitle>
          </CardHeader>
          <CardContent class="space-y-2">
            <div v-if="loading" class="space-y-2">
              <Skeleton v-for="i in 3" :key="i" class="h-10 w-full rounded" />
            </div>
            <template v-else>
              <div class="flex justify-between rounded-md border border-border px-3 py-2.5 text-sm">
                <span class="text-muted-foreground">用户名</span>
                <span class="font-medium">{{ profile.username }}</span>
              </div>
              <div class="flex justify-between rounded-md border border-border px-3 py-2.5 text-sm">
                <span class="text-muted-foreground">邮箱</span>
                <span>{{ profile.email || '—' }}</span>
              </div>
              <div class="flex justify-between rounded-md border border-border px-3 py-2.5 text-sm">
                <span class="text-muted-foreground">姓名</span>
                <span>{{ profile.full_name || '—' }}</span>
              </div>
              <div class="flex justify-between rounded-md border border-border px-3 py-2.5 text-sm">
                <span class="text-muted-foreground">角色</span>
                <Badge :class="roleColor" class="text-xs capitalize">{{ roleText }}</Badge>
              </div>
              <div class="flex justify-between rounded-md border border-border px-3 py-2.5 text-sm">
                <span class="text-muted-foreground">最近登录</span>
                <span>{{ lastLogin }}</span>
              </div>
              <div class="flex justify-between rounded-md border border-border px-3 py-2.5 text-sm">
                <span class="text-muted-foreground">账户状态</span>
                <span class="text-emerald-400">正常</span>
              </div>
            </template>
          </CardContent>
        </Card>

        <!-- 权限点 -->
        <Card>
          <CardHeader class="pb-3">
            <CardTitle class="text-base flex items-center gap-2">
              <ShieldCheck class="size-4 text-muted-foreground" />
              权限点
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div v-if="loading" class="space-y-2">
              <Skeleton class="h-24 w-full rounded" />
            </div>
            <div v-else-if="profile.permissions.length === 0" class="py-6 text-center text-xs text-muted-foreground">
              暂无权限记录
            </div>
            <div v-else class="flex flex-wrap gap-1.5">
              <Badge
                v-for="perm in profile.permissions"
                :key="perm"
                variant="outline"
                class="text-[10px] h-5 font-mono cursor-default"
              >{{ perm }}</Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      <!-- 安全设置（占位，提示管理员配置） -->
      <Card>
        <CardHeader class="pb-3">
          <CardTitle class="text-base flex items-center gap-2">
            <Lock class="size-4 text-muted-foreground" />
            安全设置
          </CardTitle>
        </CardHeader>
        <CardContent class="space-y-3">
          <div class="flex items-center justify-between rounded-md border border-border px-4 py-3">
            <div class="space-y-0.5">
              <p class="text-sm font-medium">修改密码</p>
              <p class="text-xs text-muted-foreground">定期更换密码可降低账户风险</p>
            </div>
            <Button variant="outline" size="sm" class="cursor-pointer" disabled>
              即将支持
            </Button>
          </div>
          <div class="flex items-center justify-between rounded-md border border-border px-4 py-3">
            <div class="space-y-0.5">
              <p class="text-sm font-medium">登录审计</p>
              <p class="text-xs text-muted-foreground">在审计中心查看本账号的所有操作日志</p>
            </div>
            <router-link to="/audit">
              <Button variant="outline" size="sm" class="cursor-pointer gap-1.5">
                <ExternalLink class="size-3.5" />
                查看审计
              </Button>
            </router-link>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { apiClient } from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ExternalLink, Lock, ShieldCheck, UserCircle } from 'lucide-vue-next'

const loading = ref(false)
const profile = ref({
  username: '—',
  email: null as string | null,
  full_name: null as string | null,
  role: 'viewer',
  permissions: [] as string[],
})

const lastLogin = new Date().toLocaleString('zh-CN')

const roleText = computed(() => {
  const map: Record<string, string> = { admin: '管理员', operator: '操作员', viewer: '查看者' }
  return map[profile.value.role] || profile.value.role
})

const roleColor = computed(() => {
  const map: Record<string, string> = {
    admin: 'bg-primary/15 text-primary border-primary/30',
    operator: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    viewer: 'bg-muted text-muted-foreground',
  }
  return map[profile.value.role] || 'bg-muted text-muted-foreground'
})

const loadProfile = async () => {
  loading.value = true
  try {
    const res: any = await apiClient.get('/system/profile')
    const data = res?.data ?? res
    profile.value = {
      username: data?.username ?? '—',
      email: data?.email ?? null,
      full_name: data?.full_name ?? null,
      role: data?.role ?? 'viewer',
      permissions: data?.permissions ?? [],
    }
    // Sync to localStorage so Layout.vue shows correct name
    const existing = JSON.parse(localStorage.getItem('user_info') || '{}')
    localStorage.setItem('user_info', JSON.stringify({
      ...existing,
      username: data?.username,
      role: data?.role,
    }))
  } catch {
    // fallback to localStorage
    const raw = localStorage.getItem('user_info')
    if (raw) {
      const u = JSON.parse(raw)
      profile.value.username = u.username || '—'
      profile.value.role = u.role || 'viewer'
    }
  } finally {
    loading.value = false
  }
}

onMounted(loadProfile)
</script>
