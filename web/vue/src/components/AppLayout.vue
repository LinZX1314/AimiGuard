<script setup lang="ts">
import { computed } from 'vue'
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
  Moon
} from 'lucide-vue-next'

import { useThemeAnimation } from '@/composables/useThemeAnimation'
import { ref } from 'vue'

const router = useRouter()
const route  = useRoute()
const auth   = useAuthStore()
const { toggleTheme } = useThemeAnimation()
const isDark = ref(document.documentElement.classList.contains('dark'))

function handleToggleTheme(e: MouseEvent) {
  toggleTheme(e)
  isDark.value = !isDark.value
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
              class="flex items-center px-3 py-2.5 rounded-md text-sm transition-colors group"
              :class="[
                isExactActive || (item.to !== '/' && route.path.startsWith(item.to))
                   ? 'bg-primary/10 text-primary font-bold shadow-[0_0_15px_rgba(0,229,255,0.1)]'
                  : 'text-slate-400 hover:bg-white/5 hover:text-foreground'
              ]"
            >
              <div class="mr-3 transition-transform group-hover:scale-110">
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
          <!-- Theme Toggle Button -->
          <Button variant="ghost" size="icon" @click="handleToggleTheme" class="rounded-full mr-2">
            <Sun v-if="!isDark" class="h-[1.2rem] w-[1.2rem] transition-all" />
            <Moon v-else class="h-[1.2rem] w-[1.2rem] transition-all" />
            <span class="sr-only">Toggle theme</span>
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
        <router-view v-slot="{ Component }">
          <transition name="fade-slide" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>
