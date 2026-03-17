<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import {
  LayoutDashboard,
  Bug,
  Radar,
  ShieldAlert,
  Bot,
  Settings,
  LogOut,
  ChevronDown,
  User,
  Menu,
  Siren,
  Sun,
  Moon,
  Network,
  Zap,
  ExternalLink
} from 'lucide-vue-next'

import { useThemeAnimation } from '@/composables/useThemeAnimation'
import { useUiStore } from '@/stores/ui'
import { defenseApi } from '@/api/defense'
import { api } from '@/api/index'
import RouteLoading from '@/components/RouteLoading.vue'

const router = useRouter()
const route  = useRoute()
const auth   = useAuthStore()
const uiStore = useUiStore()
const { toggleTheme } = useThemeAnimation()
const isDark = computed(() => uiStore.theme === 'dark')

// 蜜罐和交换机状态
const hfishConnected = ref(false)
const hfishTesting = ref(false)
const hfishTestMsg = ref('')
const switchCount = ref(0)
const switchEnabledCount = ref(0)
const switchOnlineCount = ref(0)
const switchStatusItems = ref<Array<{ host: string; port: number; aclNumber: number; enabled: boolean; online: boolean }>>([])
let statusPollTimer: ReturnType<typeof setInterval> | null = null

const loadTopbarStatus = async () => {
  try {
    // 获取蜜罐状态
    const status: any = await api.get('/api/status')
    hfishConnected.value = status?.hfish_sync ?? false
    
    // 获取交换机配置数量（优先新接口，兼容旧接口）
    let cfg: any = null
    try {
      cfg = await api.get('/api/v1/settings')
    } catch {
      cfg = await api.get('/api/settings')
    }

    const cfgData = cfg?.data ?? cfg
    const switches = cfgData?.switches || []
    switchCount.value = Array.isArray(switches) ? switches.length : 1

    // 先用配置做兜底，避免状态接口失败时出现“0/0 + 暂无配置”
    const normalized = Array.isArray(switches)
      ? switches
          .filter((sw: any) => sw && sw.host)
          .map((sw: any) => ({
            host: String(sw.host),
            port: Number(sw.port || 23),
            aclNumber: Number(sw.acl_number || 30),
            enabled: sw.enabled !== false,
            online: false,
          }))
      : []
    switchStatusItems.value = normalized
    switchEnabledCount.value = normalized.filter((item) => item.enabled).length
    switchOnlineCount.value = 0

    // 获取交换机在线状态
    const strictMode = !!cfgData?.switch_status?.strict_mode
    try {
      const statuses = await defenseApi.getSwitchStatuses(strictMode)
      switchEnabledCount.value = statuses?.enabled ?? switchEnabledCount.value
      switchOnlineCount.value = statuses?.online ?? switchOnlineCount.value
      const items = (statuses?.items ?? []).map((item) => ({
        host: item.host,
        port: item.port,
        aclNumber: Number(item.acl_number || 30),
        enabled: item.enabled,
        online: item.online,
      }))
      if (items.length > 0) {
        switchStatusItems.value = items
      }
    } catch (e) {
      console.warn('Load switch statuses failed, fallback to config list:', e)
    }
  } catch (e) {
    console.error('Failed to load status:', e)
  }
}

const testHFish = async () => {
  hfishTesting.value = true
  hfishTestMsg.value = ''
  try {
    const res = await defenseApi.testHFish()
    if (res.reachable) {
      hfishTestMsg.value = '连接成功'
      hfishConnected.value = true
    } else {
      hfishTestMsg.value = '连接失败'
      hfishConnected.value = false
    }
  } catch (e: any) {
    hfishTestMsg.value = e.message || '连接失败'
    hfishConnected.value = false
  } finally {
    hfishTesting.value = false
  }
}

function openSettingsWithFocus(target: 'hfish' | 'switch') {
  router.push({
    path: '/settings',
    query: {
      focus: target,
      t: String(Date.now()),
    },
  })
}

function handleToggleTheme(e: MouseEvent) {
  toggleTheme(e, () => {
    uiStore.setTheme(uiStore.theme === 'dark' ? 'light' : 'dark')
  })
}

const logoUrl = new URL('@/assets/aimiguard-logo.png', import.meta.url).href

const navItems = [
  { title: '总览大屏',   icon: LayoutDashboard, to: '/' },
  { title: 'HFish 蜜罐', icon: Bug,             to: '/hfish' },
  { title: 'Nmap 扫描',  icon: Radar,           to: '/nmap' },
  { title: '漏洞管理',   icon: Siren,           to: '/vuln' },
  { title: '防御事件',   icon: ShieldAlert,     to: '/defense' },
  { title: 'AI 助手',    icon: Bot,             to: '/ai' },
  { title: '系统设置',   icon: Settings,        to: '/settings' },
]

const currentNavItem = computed(() => {
  return navItems.find(item => {
    if (item.to === '/') {
      return route.path === '/'
    }

    return route.path === item.to || route.path.startsWith(`${item.to}/`)
  }) ?? null
})

const currentTitle = computed(() => currentNavItem.value?.title ?? '玄枢·AI攻防指挥官')

function handleLogout() {
  auth.logout()
  router.replace('/login')
}

onMounted(() => {
  loadTopbarStatus()
  statusPollTimer = setInterval(loadTopbarStatus, 30000)
})

onUnmounted(() => {
  if (statusPollTimer) {
    clearInterval(statusPollTimer)
    statusPollTimer = null
  }
})
</script>

<template>
  <div class="flex h-screen w-full bg-transparent text-foreground overflow-hidden font-sans relative">
    <!-- Sidebar -->
    <aside class="w-48 flex-shrink-0 border-r border-[hsl(var(--border))] flex flex-col hidden md:flex relative z-10 bg-background/80 backdrop-blur-md">
      <!-- Logo -->
      <div class="h-16 flex items-center px-4 border-b border-[hsl(var(--border))]">
        <Avatar class="h-8 w-8 mr-3 drop-shadow-[0_0_4px_rgba(0,229,255,0.3)] bg-transparent">
          <AvatarImage :src="logoUrl" />
          <AvatarFallback class="bg-primary/20 text-primary uppercase text-xs">AG</AvatarFallback>
        </Avatar>
        <div class="flex flex-col justify-center">
          <div class="text-[15px] font-black tracking-wide bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent leading-tight">
            玄枢指挥官
          </div>
          <div class="text-[10px] font-medium text-muted-foreground mt-0.5 flex items-center">
            AI攻防
            <span class="ml-1 px-1 border border-cyan-400/30 text-cyan-400 rounded text-[8px] uppercase">Pro</span>
          </div>
        </div>
      </div>

      <!-- Navigation -->
      <ScrollArea class="flex-1 py-4">
        <nav class="flex flex-col gap-1 px-2">
          <router-link
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            custom
            v-slot="{ isExactActive, href, navigate }"
          >
            <a
              :href="href"
              @click="navigate"
              class="flex items-center px-3 py-2.5 rounded-md text-sm group relative overflow-hidden transition-all duration-300 ease-out"
              :class="[
                isExactActive || (item.to !== '/' && route.path.startsWith(item.to))
                   ? 'bg-primary/10 text-primary font-bold shadow-[0_0_15px_rgba(0,229,255,0.1)]'
                  : 'text-slate-400 hover:bg-white/5 hover:text-foreground'
              ]"
            >
              <!-- Active indicator bar -->
              <div
                class="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] rounded-r-full bg-primary transition-all duration-300 ease-out"
                :class="isExactActive || (item.to !== '/' && route.path.startsWith(item.to)) ? 'h-5 opacity-100' : 'h-0 opacity-0'"
              ></div>
              <div class="mr-3 transition-transform duration-200 group-hover:scale-110">
                <component :is="item.icon" :size="18" :stroke-width="2" />
              </div>
              {{ item.title }}
            </a>
          </router-link>
        </nav>
      </ScrollArea>
    </aside>

    <!-- Main Content -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- Top Header -->
      <header class="h-16 flex-shrink-0 border-b border-[hsl(var(--border))] bg-background/60 backdrop-blur-md flex items-center justify-between px-4 sm:px-6 relative z-10">
        <div class="flex items-center">
          <!-- Mobile Menu Toggle (can add sheet later if needed) -->
          <Button variant="ghost" size="icon" class="md:hidden mr-2">
            <Menu class="h-5 w-5" />
          </Button>
          <component :is="currentNavItem?.icon ?? ShieldAlert" class="h-5 w-5 text-primary mr-2" />
          <h1 class="text-base font-semibold">{{ currentTitle }}</h1>
        </div>

        <div class="flex items-center gap-2">
          <!-- 蜜罐状态指示器 -->
          <div class="hidden lg:flex items-center gap-2 mr-1">
            <Popover>
              <PopoverTrigger as-child>
                <button
                  class="flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] cursor-pointer transition-colors hover:opacity-80"
                  :class="hfishConnected ? 'border-emerald-500/30 text-emerald-500 bg-emerald-500/5' : 'border-red-500/30 text-red-400 bg-red-500/5'"
                >
                  <span class="relative flex size-1.5">
                    <span
                      v-if="hfishConnected"
                      class="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-75"
                    />
                    <span
                      class="relative inline-flex size-1.5 rounded-full"
                      :class="hfishConnected ? 'bg-emerald-500' : 'bg-red-400'"
                    />
                  </span>
                  蜜罐{{ hfishConnected ? '在线' : '离线' }}
                </button>
              </PopoverTrigger>
              <PopoverContent align="end" class="w-56 p-3 space-y-3">
                <div class="flex items-center justify-between">
                  <span class="text-sm font-medium">HFish 蜜罐</span>
                  <Badge
                    :class="hfishConnected ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-red-500/15 text-red-400 border-red-500/30'"
                    class="text-[10px] h-5"
                  >
                    {{ hfishConnected ? '已连接' : '未连接' }}
                  </Badge>
                </div>
                <p v-if="hfishTestMsg" :class="hfishConnected ? 'text-emerald-400' : 'text-red-400'" class="text-xs">{{ hfishTestMsg }}</p>
                <div class="flex gap-2">
                  <Button variant="outline" size="sm" class="cursor-pointer flex-1 h-7 text-xs gap-1" :disabled="hfishTesting" @click="testHFish">
                    <Zap class="size-3" :class="hfishTesting ? 'animate-pulse' : ''" />
                    {{ hfishTesting ? '测试中…' : '测试连接' }}
                  </Button>
                  <Button variant="ghost" size="sm" class="cursor-pointer h-7 text-xs gap-1" @click="openSettingsWithFocus('hfish')">
                    <ExternalLink class="size-3" />
                    配置
                  </Button>
                </div>
              </PopoverContent>
            </Popover>

            <!-- 交换机状态指示器 -->
            <Popover>
              <PopoverTrigger as-child>
                <button
                  class="flex items-center gap-1.5 rounded-full border border-border/60 px-2.5 py-1 text-[11px] text-muted-foreground cursor-pointer transition-colors hover:opacity-80 hover:border-border"
                >
                  <Network class="size-3" />
                  交换机 <span class="font-semibold text-foreground tabular-nums">{{ switchCount }}</span>
                </button>
              </PopoverTrigger>
              <PopoverContent align="end" class="w-56 p-3 space-y-3">
                <div class="flex items-center justify-between">
                  <span class="text-sm font-medium">交换机设备</span>
                  <Badge
                    variant="outline"
                    class="text-[10px] h-5"
                    :class="switchEnabledCount > 0 && switchOnlineCount === switchEnabledCount
                      ? 'border-emerald-500/40 text-emerald-400 bg-emerald-500/10'
                      : 'border-amber-500/40 text-amber-400 bg-amber-500/10'"
                  >
                    在线 {{ switchOnlineCount }}/{{ switchEnabledCount }}
                  </Badge>
                </div>
                <p class="text-xs text-muted-foreground">
                  已配置 {{ switchCount }} 台交换机设备用于 ACL 封禁
                </p>
                <div v-if="switchStatusItems.length" class="max-h-36 overflow-y-auto rounded-lg border border-border/50 p-1.5 space-y-1.5 bg-muted/10">
                  <div
                    v-for="item in switchStatusItems"
                    :key="`${item.host}:${item.port}`"
                    class="rounded-md border border-border/60 px-2 py-1.5 bg-background/70 flex items-center justify-between gap-2"
                  >
                    <div class="min-w-0">
                      <div class="text-[11px] font-medium text-foreground truncate">{{ item.host }}</div>
                      <div class="text-[10px] text-muted-foreground">编号：{{ item.aclNumber }}</div>
                    </div>
                    <Badge
                      variant="outline"
                      class="h-5 px-1.5 shrink-0"
                      :class="item.enabled
                        ? (item.online
                          ? 'border-emerald-500/40 text-emerald-400 bg-emerald-500/10'
                          : 'border-red-500/40 text-red-400 bg-red-500/10')
                        : 'border-slate-500/40 text-slate-400 bg-slate-500/10'"
                    >
                      {{ item.enabled ? (item.online ? '在线' : '离线') : '禁用' }}
                    </Badge>
                  </div>
                </div>
                <div v-else class="rounded border border-border/50 p-2 text-[11px] text-muted-foreground text-center">
                  暂无交换机配置
                </div>
                <Button variant="ghost" size="sm" class="cursor-pointer w-full h-7 text-xs gap-1" @click="openSettingsWithFocus('switch')">
                  <ExternalLink class="size-3" />
                  设备管理
                </Button>
              </PopoverContent>
            </Popover>
          </div>

          <!-- Theme Toggle Button -->
          <Button variant="ghost" size="icon" @click="handleToggleTheme" class="rounded-full mr-2">
            <Sun v-if="!isDark" class="h-[1.2rem] w-[1.2rem] transition-all" />
            <Moon v-else class="h-[1.2rem] w-[1.2rem] transition-all" />
            <span class="sr-only">切换主题</span>
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger as-child>
              <Button variant="ghost" class="h-10 pl-2 pr-2 sm:pr-4 rounded-full flex items-center hover:bg-muted">
                <Avatar class="h-8 w-8 bg-primary/20 text-primary border border-primary/20 mr-0 sm:mr-3">
                  <AvatarFallback><User class="h-4 w-4" /></AvatarFallback>
                </Avatar>
                <div class="hidden sm:flex flex-col items-start mr-2">
                  <span class="text-sm font-medium leading-none">{{ auth.user?.username ?? 'admin' }}</span>
                  <span class="text-[11px] text-muted-foreground mt-1 leading-none">超级管理员</span>
                </div>
                <ChevronDown class="h-4 w-4 text-muted-foreground hidden sm:block" />
              </Button>
            </DropdownMenuTrigger>
            
            <DropdownMenuContent align="end" class="w-56 mt-1">
              <DropdownMenuLabel class="font-normal">
                <div class="flex flex-col space-y-1">
                  <p class="text-sm font-medium leading-none">{{ auth.user?.username ?? 'admin' }}</p>
                  <p class="text-xs leading-none text-muted-foreground">玄枢安全系统指挥官</p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem @click="router.push('/settings')">
                <Settings class="mr-2 h-4 w-4" />
                <span>个人设置</span>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem @click="handleLogout" class="text-destructive focus:bg-destructive focus:text-destructive-foreground">
                <LogOut class="mr-2 h-4 w-4" />
                <span>退出系统</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      <!-- Main Router View -->
      <main class="flex-1 overflow-auto bg-transparent relative z-10">
        <router-view v-slot="{ Component, route }">
          <transition name="fade-slide" mode="out-in">
            <Suspense>
              <component :is="Component" :key="route.fullPath" />
              <template #fallback>
                <RouteLoading />
              </template>
            </Suspense>
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>
