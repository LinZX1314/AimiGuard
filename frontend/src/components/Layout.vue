<template>
  <Transition name="route-progress">
    <div v-if="isRouteChanging" class="route-progress" :style="{ transform: `scaleX(${routeProgress})` }" />
  </Transition>
  <div ref="shellRef" class="flex h-screen flex-col bg-background/50 text-foreground">
    <header class="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div class="relative flex h-14 items-center px-4 sm:px-6">
        <div class="flex items-center gap-3">
          <Sheet>
            <SheetTrigger as-child>
              <Button variant="ghost" size="icon" class="cursor-pointer md:hidden">
                <PanelLeft class="size-4" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" class="w-[18rem] border-r border-border bg-sidebar p-0">
              <SheetHeader class="sr-only">
                <SheetTitle>Mobile Navigation</SheetTitle>
                <SheetDescription>Mobile navigation menu for current mode.</SheetDescription>
              </SheetHeader>
              <div class="border-b border-sidebar-border px-4 py-3">
                <p class="text-sm font-medium text-sidebar-foreground">{{ activeModeLabel }}</p>
              </div>
              <nav class="space-y-1 p-3">
                <router-link
                  v-for="item in currentSidebarItems"
                  :key="item.to"
                  :to="item.to"
                  class="flex items-center gap-2 rounded-md border bg-background/25 px-3 py-2 text-sm text-sidebar-foreground cursor-pointer"
                  :class="activeMode === 'defense' ? 'sidebar-action sidebar-action-defense' : 'sidebar-action sidebar-action-probe'"
                  :active-class="activeMode === 'defense' ? 'sidebar-action-active-defense' : 'sidebar-action-active-probe'"
                >
                  <component :is="item.icon" class="size-4" />
                  <span>{{ item.label }}</span>
                </router-link>
              </nav>
            </SheetContent>
          </Sheet>

          <div class="flex items-center gap-2">
            <ShieldCheck class="size-5 text-primary" />
            <span class="hidden text-sm font-semibold tracking-tight text-foreground sm:inline">玄枢·AI攻防指挥官</span>
          </div>
        </div>

        <!-- 模式切换：绝对居中于整个页面 -->
        <div class="absolute left-1/2 -translate-x-1/2 hidden md:flex">
          <Tabs
            :model-value="activeMode"
            @update:model-value="onModeChange"
          >
            <TabsList class="relative h-10 w-[180px] bg-muted/50 p-1 rounded-full grid grid-cols-2 items-center overflow-hidden border border-border/20 z-0">
              <!-- 滑动高亮底块 -->
              <div class="absolute inset-y-1 left-1 right-1 pointer-events-none z-0">
                <div 
                  class="h-full w-[calc(50%-2px)] rounded-full transition-transform duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]"
                  :class="activeMode === 'defense' ? 'translate-x-0 bg-[#3B82F6] shadow-[0_2px_8px_rgba(59,130,246,0.3)]' : 'translate-x-[calc(100%+4px)] bg-[#F97316] shadow-[0_2px_8px_rgba(249,115,22,0.3)]'"
                ></div>
              </div>
              <TabsTrigger 
                value="defense" 
                class="relative z-10 w-full h-full cursor-pointer rounded-full px-0 text-xs sm:text-sm transition-colors duration-300 border-none bg-transparent hover:bg-transparent shadow-none data-[state=active]:!bg-transparent data-[state=active]:!text-white data-[state=active]:shadow-none"
                :class="activeMode !== 'defense' ? 'text-muted-foreground hover:text-foreground' : 'text-white'"
              >
                防御坚守
              </TabsTrigger>
              <TabsTrigger 
                value="probe" 
                class="relative z-10 w-full h-full cursor-pointer rounded-full px-0 text-xs sm:text-sm transition-colors duration-300 border-none bg-transparent hover:bg-transparent shadow-none data-[state=active]:!bg-transparent data-[state=active]:!text-white data-[state=active]:shadow-none"
                :class="activeMode !== 'probe' ? 'text-muted-foreground hover:text-foreground' : 'text-white'"
              >
                主动探测
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        <div class="flex-1" />

        <div class="flex items-center gap-2">
          <!-- 蜜罐状态指示器 -->
          <div class="hidden items-center gap-2 mr-1 lg:flex">
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
              <PopoverContent align="end" class="w-64 p-3 space-y-3">
                <div class="flex items-center justify-between">
                  <span class="text-sm font-medium">HFish 蜜罐</span>
                  <Badge
                    :class="hfishConnected ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-red-500/15 text-red-400 border-red-500/30'"
                    class="text-[10px] h-5"
                  >
                    {{ hfishConnected ? '已连接' : '未连接' }}
                  </Badge>
                </div>
                <p v-if="hfishTestMsg" :class="hfishTestOk ? 'text-emerald-400' : 'text-red-400'" class="text-xs">{{ hfishTestMsg }}</p>
                <div class="flex gap-2">
                  <Button variant="outline" size="sm" class="cursor-pointer flex-1 h-7 text-xs gap-1" :disabled="hfishTesting" @click="testHFish">
                    <Zap class="size-3" :class="hfishTesting ? 'animate-pulse' : ''" />
                    {{ hfishTesting ? '测试中…' : '测试连接' }}
                  </Button>
                  <Button variant="ghost" size="sm" class="cursor-pointer h-7 text-xs gap-1" @click="router.push('/integrations?tab=hfish')">
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
                  交换机 <span class="font-semibold text-foreground tabular-nums">{{ deviceCount }}</span>
                </button>
              </PopoverTrigger>
              <PopoverContent align="end" class="w-72 p-3 space-y-3">
                <div class="flex items-center justify-between">
                  <span class="text-sm font-medium">交换机设备</span>
                  <Badge variant="outline" class="text-[10px] h-5">{{ deviceCount }} 台</Badge>
                </div>
                <div v-if="deviceList.length === 0" class="text-xs text-muted-foreground text-center py-2">暂无设备</div>
                <div v-else class="space-y-1.5 max-h-40 overflow-y-auto">
                  <div
                    v-for="d in deviceList"
                    :key="d.id"
                    class="flex items-center justify-between rounded-md border border-border/50 px-2.5 py-1.5 text-xs"
                  >
                    <div class="flex items-center gap-2 min-w-0">
                      <span
                        class="inline-flex size-1.5 rounded-full shrink-0"
                        :class="deviceTestResults[d.id] === true ? 'bg-emerald-500' : deviceTestResults[d.id] === false ? 'bg-red-400' : 'bg-muted-foreground/40'"
                      />
                      <span class="font-medium truncate">{{ d.name }}</span>
                      <span class="text-muted-foreground font-mono">{{ d.ip }}</span>
                    </div>
                    <Button variant="ghost" size="sm" class="cursor-pointer h-5 px-1.5 text-[10px]" :disabled="deviceTesting === d.id" @click="testDevice(d.id)">
                      {{ deviceTesting === d.id ? '…' : '测试' }}
                    </Button>
                  </div>
                </div>
                <Button variant="ghost" size="sm" class="cursor-pointer w-full h-7 text-xs gap-1" @click="router.push('/integrations?tab=device')">
                  <ExternalLink class="size-3" />
                  设备管理
                </Button>
              </PopoverContent>
            </Popover>
          </div>

          <Sheet>
            <SheetTrigger as-child>
              <Button
                variant="ghost"
                size="icon"
                class="relative cursor-pointer text-muted-foreground"
              >
                <Bell class="size-4" />
                <span
                  v-if="unreadNotifications > 0"
                  class="absolute -top-0.5 -right-0.5 inline-flex h-2 w-2 rounded-full bg-red-500"
                />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" class="w-[22rem] border-l border-border p-0 gap-0">
              <!-- 通知面板 -->
              <div class="border-b border-border px-4 py-3 shrink-0">
                <SheetTitle class="text-sm font-semibold">Notifications</SheetTitle>
                <SheetDescription class="sr-only">View realtime notifications and mark all as read.</SheetDescription>
              </div>
              <!-- 通知面板 -->
              <div class="flex-1 overflow-y-auto px-4 py-3 space-y-2 min-h-0">
                <div
                  v-for="item in pagedNotifications"
                  :key="item.id"
                  class="rounded-md border border-border bg-card px-3 py-2 cursor-pointer transition-colors hover:bg-accent/40"
                  :class="!item.read ? 'border-l-2 border-l-blue-500' : ''"
                  @click="markNotificationRead(item)"
                >
                  <div class="flex items-center justify-between gap-2">
                    <div class="flex items-center gap-1.5 min-w-0">
                      <span
                        v-if="item.severity === 'critical' || item.severity === 'high'"
                        class="inline-flex size-1.5 rounded-full bg-red-500 shrink-0"
                      />
                      <span
                        v-else-if="item.severity === 'medium'"
                        class="inline-flex size-1.5 rounded-full bg-yellow-500 shrink-0"
                      />
                      <p class="text-sm font-medium truncate">{{ item.title }}</p>
                    </div>
                    <span
                      v-if="!item.read"
                      class="inline-flex h-1.5 w-1.5 rounded-full bg-blue-500 shrink-0"
                    />
                  </div>
                  <p class="mt-1 text-xs text-muted-foreground line-clamp-2">{{ item.content }}</p>
                  <p class="mt-2 text-[11px] text-muted-foreground/80">{{ item.time }}</p>
                </div>
                <p v-if="notifications.length === 0" class="py-8 text-center text-xs text-muted-foreground">暂无通知</p>
              </div>
              <!-- 通知面板 -->
              <div class="border-t border-border px-3 py-2 shrink-0 flex items-center justify-between">
                <Button
                  variant="ghost"
                  size="sm"
                  class="h-7 cursor-pointer text-xs"
                  @click="markAllNotificationsRead"
                >
                  全部已读
                </Button>
                <div v-if="notifTotalPages > 1" class="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    class="h-6 w-6 cursor-pointer"
                    :disabled="notifPage === 1"
                    @click="notifPage--"
                  >
                    <ChevronLeftIcon class="size-3" />
                  </Button>
                  <span class="text-xs text-muted-foreground tabular-nums">{{ notifPage }} / {{ notifTotalPages }}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="h-6 w-6 cursor-pointer"
                    :disabled="notifPage === notifTotalPages"
                    @click="notifPage++"
                  >
                    <ChevronRight class="size-3" />
                  </Button>
                </div>
                <span v-else class="text-xs text-muted-foreground tabular-nums">{{ notifications.length }} items</span>
              </div>
            </SheetContent>
          </Sheet>

          <Button
            variant="ghost"
            size="icon"
            class="cursor-pointer text-muted-foreground"
            @click="goToSettings"
          >
            <Settings class="size-4" />
          </Button>

          <Button
            variant="ghost"
            size="icon"
            class="cursor-pointer text-muted-foreground"
            @click="toggleTheme"
          >
            <Moon v-if="isDarkMode" class="size-4" />
            <Sun v-else class="size-4" />
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger as-child>
              <Button variant="ghost" size="icon" class="relative cursor-pointer text-muted-foreground">
                <Avatar class="size-8">
                  <AvatarFallback class="bg-primary/10 text-xs text-primary">
                    {{ username.charAt(0).toUpperCase() }}
                  </AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" class="w-56">
              <DropdownMenuLabel>
                <div class="flex items-center justify-between">
                  <span class="text-sm text-foreground">{{ username }}</span>
                  <Badge :variant="roleBadgeVariant">{{ roleText }}</Badge>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem class="cursor-pointer" @click="goToProfile">
                <UserRound class="mr-2 size-4" />
                用户中心
              </DropdownMenuItem>
              <DropdownMenuItem class="cursor-pointer" @click="goToSettings">
                <Settings class="mr-2 size-4" />
                系统设置
              </DropdownMenuItem>
              <DropdownMenuItem class="cursor-pointer" @click="goToSecuritySettings">
                <ShieldAlert class="mr-2 size-4" />
                安全设置
              </DropdownMenuItem>
              <DropdownMenuItem v-if="role === 'admin' || role === 'operator'" class="cursor-pointer" @click="router.push('/integrations')">
                <Blocks class="mr-2 size-4" />
                集成管理
              </DropdownMenuItem>
              <DropdownMenuItem v-if="role === 'admin'" class="cursor-pointer" @click="router.push('/observability')">
                <Activity class="mr-2 size-4" />
                可观测性
              </DropdownMenuItem>
              <DropdownMenuItem v-if="role === 'admin' || role === 'operator'" class="cursor-pointer" @click="router.push('/audit')">
                <FileSearch class="mr-2 size-4" />
                审计日志
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem class="cursor-pointer text-destructive focus:text-destructive" @click="handleLogout">
                <LogOut class="mr-2 size-4" />
                退出登录
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <div class="border-t border-border px-4 py-2 md:hidden">
        <Tabs :model-value="activeMode" @update:model-value="onModeChange">
          <TabsList class="relative w-full h-10 bg-muted/50 p-1 rounded-xl grid grid-cols-2 items-center overflow-hidden border border-border/20 z-0">
            <!-- 移动端滑动高亮底块 -->
            <div class="absolute inset-y-1 left-1 right-1 pointer-events-none z-0">
              <div 
                class="h-full w-[calc(50%-2px)] rounded-lg transition-transform duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]"
                :class="activeMode === 'defense' ? 'translate-x-0 bg-[#3B82F6] shadow-[0_2px_8px_rgba(59,130,246,0.3)]' : 'translate-x-[calc(100%+4px)] bg-[#F97316] shadow-[0_2px_8px_rgba(249,115,22,0.3)]'"
              ></div>
            </div>
            <TabsTrigger 
              value="defense" 
              class="relative z-10 w-full h-full cursor-pointer rounded-lg border-none bg-transparent transition-colors duration-300 hover:bg-transparent shadow-none data-[state=active]:!bg-transparent data-[state=active]:!text-white data-[state=active]:shadow-none"
              :class="activeMode !== 'defense' ? 'text-muted-foreground hover:text-foreground' : 'text-white'"
            >
              防御坚守
            </TabsTrigger>
            <TabsTrigger 
              value="probe" 
              class="relative z-10 w-full h-full cursor-pointer rounded-lg border-none bg-transparent transition-colors duration-300 hover:bg-transparent shadow-none data-[state=active]:!bg-transparent data-[state=active]:!text-white data-[state=active]:shadow-none"
              :class="activeMode !== 'probe' ? 'text-muted-foreground hover:text-foreground' : 'text-white'"
            >
              主动探测
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
    </header>

    <div class="relative flex min-h-0 flex-1 overflow-hidden">
      <div ref="maskWrapRef" class="pointer-events-none fixed inset-0 z-[100] hidden flex w-full h-full">
        <div ref="impactPulseRef" class="absolute top-1/2 left-1/2 size-20 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-primary opacity-0" />
        <div
          v-for="panelIndex in maskPanels"
          :key="`mask-panel-${panelIndex}`"
          :ref="setMaskPanelRef"
          class="h-full flex-1 bg-background/50 border-r border-border/50 last:border-r-0 origin-top"
        />
        <div ref="inkTopRef" class="absolute top-[30%] left-0 h-0.5 w-full bg-primary shadow-[0_0_15px_var(--primary)] opacity-0" />
        <div ref="inkBottomRef" class="absolute bottom-[30%] left-0 h-0.5 w-full bg-primary shadow-[0_0_15px_var(--primary)] opacity-0" />
        <div 
          ref="transitionTitleRef" 
          class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-6xl md:text-8xl font-black tracking-[0.5em] text-transparent bg-clip-text bg-gradient-to-b from-white via-white to-white/10 opacity-0 whitespace-nowrap z-50 select-none pointer-events-none"
          style="text-shadow: 0 0 40px var(--primary);"
        >
          {{ transitionTitleText }}
        </div>
      </div>

      <aside
        ref="sidebarRef"
        class="relative hidden shrink-0 border-r border-sidebar-border bg-sidebar transition-[transform,opacity] duration-260 ease-[cubic-bezier(0.4,0,0.2,1)] md:flex md:flex-col"
        :class="sidebarCollapsed ? 'px-2 py-3' : 'p-3'"
        :style="{ width: `${sidebarCurrentWidth}px` }"
      >
        <div
          class="mb-3 min-h-8 rounded-md border transition-[transform,opacity] duration-260 ease-[cubic-bezier(0.4,0,0.2,1)] backdrop-blur-sm bg-background/60 flex items-center justify-center overflow-hidden"
          :class="[
            sidebarCollapsed ? 'px-2 py-2 text-center' : 'px-3 py-2',
            activeMode === 'defense' 
              ? 'border-blue-500 text-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.1)]' 
              : 'border-orange-500 text-orange-500 shadow-[0_0_15px_rgba(249,115,22,0.1)]'
          ]"
        >
          <p class="font-medium tracking-wide leading-none flex items-center justify-center" :class="sidebarCollapsed ? 'text-[11px]' : 'text-xs'">
            <span
              class="sidebar-mode-label"
              :class="sidebarCollapsed ? 'sidebar-mode-label-collapsed' : 'sidebar-mode-label-expanded'"
            >
              {{ sidebarCollapsed ? (activeMode === 'defense' ? '防御' : '探测') : activeModeLabel }}
            </span>
          </p>
        </div>

        <nav class="flex-1 space-y-1 overflow-hidden">
          <router-link
            v-for="item in currentSidebarItems"
            :key="item.to"
            :to="item.to"
            data-sidebar-item="true"
            :title="sidebarCollapsed ? item.label : undefined"
            class="flex items-center rounded-md border bg-background/25 py-2 text-sm text-sidebar-foreground cursor-pointer"
            :class="[
              sidebarCollapsed ? 'justify-center px-2' : 'gap-2 px-3',
              activeMode === 'defense' ? 'sidebar-action sidebar-action-defense' : 'sidebar-action sidebar-action-probe'
            ]"
            :active-class="activeMode === 'defense' ? 'sidebar-action-active-defense' : 'sidebar-action-active-probe'"
          >
            <component :is="item.icon" class="size-4" />
            <span
              class="sidebar-item-label"
              :class="sidebarCollapsed ? 'sidebar-item-label-collapsed' : 'sidebar-item-label-expanded'"
            >
              {{ item.label }}
            </span>
          </router-link>
        </nav>

        <div class="mt-2 border-t border-sidebar-border/70 pt-2">
          <button
            type="button"
            class="flex h-11 w-full items-center rounded-md border bg-background/25 text-sidebar-foreground focus:outline-none focus:ring-2 focus:ring-ring cursor-pointer"
            :class="[
              sidebarCollapsed ? 'justify-center px-2' : 'gap-2 px-3',
              activeMode === 'defense' ? 'sidebar-action sidebar-action-defense' : 'sidebar-action sidebar-action-probe'
            ]"
            :title="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
            :aria-label="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
            @click="toggleSidebarCollapsed"
          >
            <ChevronRight
              class="size-4 transition-transform duration-220 ease-out"
              :class="sidebarCollapsed ? 'rotate-0' : 'rotate-180'"
            />
            <span
              class="sidebar-item-label text-sm"
              :class="sidebarCollapsed ? 'sidebar-item-label-collapsed' : 'sidebar-item-label-expanded'"
            >
              收起侧边栏
            </span>
          </button>
        </div>

        <div
          class="absolute top-0 -right-1 z-20 h-full w-2 cursor-col-resize"
          role="separator"
          aria-orientation="vertical"
          @mousedown="startSidebarResize"
        >
          <div
            class="mx-auto h-full w-px bg-transparent transition-opacity duration-180 hover:opacity-80 hover:bg-border"
            :class="isSidebarResizing ? 'bg-primary/60' : ''"
          />
        </div>
      </aside>

      <main
        ref="contentRef"
        class="min-w-0 flex-1 overflow-y-auto bg-background/50"
      >
        <div class="relative h-full">
          <router-view v-slot="{ Component, route: childRoute }">
            <Transition name="fade-slide" mode="out-in" appear>
              <div :key="childRoute.fullPath" class="route-page h-full">
                <component :is="Component" />
              </div>
            </Transition>
          </router-view>
        </div>
      </main>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUpdate, onMounted, onUnmounted, ref, watch } from 'vue'
import type { ComponentPublicInstance } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useActiveMode } from '@/composables/useActiveMode'
import { hasAnyPermission, parseStoredUserInfo } from '@/composables/useAuthz'
import { apiClient } from '@/api/client'
import { authApi } from '../api/auth'
import { overviewApi } from '@/api/overview'
import { deviceApi, type DeviceInfo } from '@/api/device'
import { defenseApi } from '@/api/defense'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import gsap from 'gsap'
import {
  Activity,
  Bell,
  Blocks,
  BrainCircuit,
  ChevronLeft as ChevronLeftIcon,
  ChevronRight,
  ExternalLink,
  FileSearch,
  LogOut,
  Moon,
  Network,
  PanelLeft,
  Radar,
  ScanSearch,
  Settings,
  ShieldAlert,
  ShieldCheck,
  Sun,
  UserRound,
  Zap,
} from 'lucide-vue-next'

type ModeKey = 'defense' | 'probe'

const router = useRouter()
const route = useRoute()
const { activeMode } = useActiveMode()

const username = ref('user')
const role = ref('viewer')

const hfishConnected = ref(false)
const hfishTesting = ref(false)
const hfishTestMsg = ref('')
const hfishTestOk = ref(false)
const deviceCount = ref(0)
const deviceList = ref<DeviceInfo[]>([])
const deviceTesting = ref<number | null>(null)
const deviceTestResults = ref<Record<number, boolean>>({})
let statusPollTimer: ReturnType<typeof setInterval> | null = null

const loadTopbarStatus = async () => {
  try {
    const [chain, devices] = await Promise.allSettled([
      overviewApi.getChainStatus(),
      deviceApi.list(),
    ])
    if (chain.status === 'fulfilled') {
      const hfish = chain.value.defense?.find((c: any) => c.key === 'hfish_ingest')
      hfishConnected.value = hfish?.ok ?? false
    }
    if (devices.status === 'fulfilled') {
      const list = Array.isArray(devices.value) ? devices.value : []
      deviceList.value = list
      deviceCount.value = list.length
    }
  } catch { /* ignore */ }
}

const testHFish = async () => {
  hfishTesting.value = true
  hfishTestMsg.value = ''
  try {
    const res = await defenseApi.testHFishConnection()
    hfishTestOk.value = res.ok
    hfishTestMsg.value = res.message
    if (res.ok) hfishConnected.value = true
  } catch {
    hfishTestOk.value = false
    hfishTestMsg.value = '请求失败'
  } finally {
    hfishTesting.value = false
  }
}

const testDevice = async (deviceId: number) => {
  deviceTesting.value = deviceId
  try {
    const res = await deviceApi.testConnection(deviceId)
    deviceTestResults.value = { ...deviceTestResults.value, [deviceId]: res.ok }
  } catch {
    deviceTestResults.value = { ...deviceTestResults.value, [deviceId]: false }
  } finally {
    deviceTesting.value = null
  }
}
interface NotifItem {
  id: number | string
  title: string
  content: string
  time: string
  read: boolean
  category?: string
  severity?: string
  link?: string
}
const notifications = ref<NotifItem[]>([])
const unreadCount = ref(0)
const NOTIF_PAGE_SIZE = 5
const notifPage = ref(1)
const notifTotalPages = computed(() => Math.max(1, Math.ceil(notifications.value.length / NOTIF_PAGE_SIZE)))
const pagedNotifications = computed(() => {
  const start = (notifPage.value - 1) * NOTIF_PAGE_SIZE
  return notifications.value.slice(start, start + NOTIF_PAGE_SIZE)
})

const formatNotifTime = (iso: string) => {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr} 小时前`
  return d.toLocaleDateString('zh-CN')
}

const loadNotifications = async () => {
  try {
    const res: any = await apiClient.get('/notifications', { params: { limit: 50 } })
    const data = res?.data ?? res
    const items = data?.items ?? []
    notifications.value = items.map((n: any) => ({
      id: n.id,
      title: n.title || '',
      content: n.content || '',
      time: formatNotifTime(n.created_at || ''),
      read: !!n.read,
      category: n.category,
      severity: n.severity,
      link: n.link,
    }))
    unreadCount.value = data?.unread ?? notifications.value.filter((n: NotifItem) => !n.read).length
  } catch {
    // keep existing
  }
}

let notifPollTimer: ReturnType<typeof setInterval> | null = null
const shellRef = ref<HTMLElement | null>(null)
const sidebarRef = ref<HTMLElement | null>(null)

// 侧边栏状态与动画配置
const isRouteChanging = ref(false)
const routeProgress = ref(0)
const isDarkMode = ref(false)
const THEME_KEY = 'theme'
const SIDEBAR_COLLAPSED_KEY = 'layout_sidebar_collapsed'
const SIDEBAR_WIDTH_STEP_KEY = 'layout_sidebar_width_step'
const sidebarWidthPresets = [160, 180, 200] as const
const minSidebarWidthStep = 0
const defaultSidebarWidthStep = 1
const maxSidebarWidthStep = sidebarWidthPresets.length - 1

const sidebarCollapsed = ref(false)
const sidebarWidthStep = ref(defaultSidebarWidthStep)
const isSidebarResizing = ref(false)
let sidebarResizeMoveHandler: ((event: MouseEvent) => void) | null = null
let sidebarResizeUpHandler: (() => void) | null = null

const normalizeSidebarWidthStep = (value: number) => {
  return Math.min(maxSidebarWidthStep, Math.max(minSidebarWidthStep, value))
}

const widthToStep = (width: number) => {
  let nearestStep = defaultSidebarWidthStep
  let nearestDiff = Number.POSITIVE_INFINITY

  sidebarWidthPresets.forEach((presetWidth, step) => {
    const diff = Math.abs(presetWidth - width)
    if (diff < nearestDiff) {
      nearestDiff = diff
      nearestStep = step
    }
  })

  return nearestStep
}

const getSidebarTargetWidth = () => {
  if (sidebarCollapsed.value) return 72
  return sidebarWidthPresets[sidebarWidthStep.value]
}

const sidebarAnimatedWidth = ref(getSidebarTargetWidth())
let sidebarWidthAnimationFrame: number | null = null

const stopSidebarWidthAnimation = () => {
  if (sidebarWidthAnimationFrame !== null) {
    cancelAnimationFrame(sidebarWidthAnimationFrame)
    sidebarWidthAnimationFrame = null
  }
}

const runSidebarWidthAnimation = () => {
  stopSidebarWidthAnimation()

  const animate = () => {
    const target = getSidebarTargetWidth()
    const current = sidebarAnimatedWidth.value
    const diff = target - current

    if (Math.abs(diff) < 0.5) {
      sidebarAnimatedWidth.value = target
      sidebarWidthAnimationFrame = null
      return
    }

    sidebarAnimatedWidth.value = current + diff * 0.18
    sidebarWidthAnimationFrame = requestAnimationFrame(animate)
  }

  sidebarWidthAnimationFrame = requestAnimationFrame(animate)
}

const sidebarCurrentWidth = computed(() => Math.round(sidebarAnimatedWidth.value))

const toggleSidebarCollapsed = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const loadSidebarPreference = () => {
  const savedCollapsed = localStorage.getItem(SIDEBAR_COLLAPSED_KEY)
  if (savedCollapsed !== null) {
    sidebarCollapsed.value = savedCollapsed === '1' || savedCollapsed === 'true'
  }

  const savedStep = localStorage.getItem(SIDEBAR_WIDTH_STEP_KEY)
  if (savedStep !== null) {
    const parsedStep = Number.parseInt(savedStep, 10)
    if (!Number.isNaN(parsedStep)) {
      sidebarWidthStep.value = normalizeSidebarWidthStep(parsedStep)
    }
  }
}

const updateSidebarWidthByClientX = (clientX: number) => {
  const shellEl = shellRef.value
  if (!shellEl) return

  const shellLeft = shellEl.getBoundingClientRect().left
  const nextWidth = clientX - shellLeft
  const clampedWidth = Math.min(sidebarWidthPresets[maxSidebarWidthStep], Math.max(sidebarWidthPresets[minSidebarWidthStep], nextWidth))
  stopSidebarWidthAnimation()
  sidebarAnimatedWidth.value = clampedWidth
  sidebarWidthStep.value = widthToStep(clampedWidth)
}

const stopSidebarResize = () => {
  isSidebarResizing.value = false

  if (sidebarResizeMoveHandler) {
    window.removeEventListener('mousemove', sidebarResizeMoveHandler)
    sidebarResizeMoveHandler = null
  }

  if (sidebarResizeUpHandler) {
    window.removeEventListener('mouseup', sidebarResizeUpHandler)
    sidebarResizeUpHandler = null
  }

  if (!sidebarCollapsed.value) {
    runSidebarWidthAnimation()
  }
}

const startSidebarResize = (event: MouseEvent) => {
  if (sidebarCollapsed.value || event.button !== 0) return

  event.preventDefault()
  isSidebarResizing.value = true

  sidebarResizeMoveHandler = (moveEvent: MouseEvent) => {
    updateSidebarWidthByClientX(moveEvent.clientX)
  }

  sidebarResizeUpHandler = () => {
    stopSidebarResize()
  }

  window.addEventListener('mousemove', sidebarResizeMoveHandler)
  window.addEventListener('mouseup', sidebarResizeUpHandler)
}

watch(sidebarCollapsed, (collapsed) => {
  localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? '1' : '0')
})

watch([sidebarCollapsed, sidebarWidthStep], () => {
  if (isSidebarResizing.value) return
  runSidebarWidthAnimation()
})

watch(sidebarWidthStep, (step) => {
  localStorage.setItem(SIDEBAR_WIDTH_STEP_KEY, String(normalizeSidebarWidthStep(step)))
})

const applyTheme = (mode: 'light' | 'dark') => {
  const root = document.documentElement
  root.classList.toggle('dark', mode === 'dark')
  isDarkMode.value = mode === 'dark'
  localStorage.setItem(THEME_KEY, mode)
}

const initTheme = () => {
  const savedTheme = localStorage.getItem(THEME_KEY)
  if (savedTheme === 'light' || savedTheme === 'dark') {
    applyTheme(savedTheme)
    return
  }

  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  applyTheme(prefersDark ? 'dark' : 'light')
}

const toggleTheme = async (event?: MouseEvent) => {
  const newMode = isDarkMode.value ? 'light' : 'dark'
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

  if (reducedMotion) {
    applyTheme(newMode)
    return
  }

  const triggerElement = event?.currentTarget
  if (!(triggerElement instanceof HTMLElement)) {
    applyTheme(newMode)
    return
  }

  const rect = triggerElement.getBoundingClientRect()
  const x = rect.left + rect.width / 2
  const y = rect.top + rect.height / 2

  // 主题切换圆形扩散动画
  const { executeThemeAnimation, getAnimationConfig } = await import('@/composables/useThemeAnimation')
  const config = getAnimationConfig()
  
  // View Transitions API 支持检测
  if (config.type === 'view') {
    const root = document.documentElement
    root.classList.add('view-transitioning')
    isDarkMode.value = newMode === 'dark'
    localStorage.setItem(THEME_KEY, newMode)
    try {
      await executeThemeAnimation({ x, y, reducedMotion })
    } finally {
      root.classList.remove('view-transitioning')
    }
  } else {
    // 降级方案：使用 GSAP 动画
    const animationPromise = executeThemeAnimation({ x, y, reducedMotion })
    setTimeout(() => {
      applyTheme(newMode)
    }, config.duration / 2)
    await animationPromise
  }
}

const contentRef = ref<HTMLElement | null>(null)
const maskWrapRef = ref<HTMLElement | null>(null)
const maskPanelRefs = ref<HTMLElement[]>([])
const impactPulseRef = ref<HTMLElement | null>(null)
const inkTopRef = ref<HTMLElement | null>(null)
const inkBottomRef = ref<HTMLElement | null>(null)
const transitionTitleRef = ref<HTMLElement | null>(null)
const transitionTitleText = ref('')
const isModeSwitching = ref(false)
let modeTimeline: gsap.core.Timeline | null = null

const setMaskPanelRef = (el: Element | ComponentPublicInstance | null) => {
  const maybeElement = el instanceof HTMLElement
    ? el
    : (el && '$el' in el && el.$el instanceof HTMLElement ? el.$el : null)

  if (maybeElement) {
    maskPanelRefs.value.push(maybeElement)
  }
}

const maskPanels = Array.from({ length: 12 }, (_, i) => i)

onBeforeUpdate(() => {
  maskPanelRefs.value = []
})


type SidebarRole = 'admin' | 'operator' | 'viewer'

interface SidebarItem {
  to: string
  label: string
  icon: unknown
  roles?: SidebarRole[]
  permissions?: string[]
}

const sidebarMap: Record<ModeKey, SidebarItem[]> = {
  defense: [
    { to: '/defense/dashboard', label: '仪表盘', icon: Activity },
    { to: '/defense/realtime', label: '实时监测', icon: Activity },
    { to: '/defense/events', label: '威胁处置', icon: ShieldAlert },
    { to: '/defense/ai', label: 'AI 研判', icon: BrainCircuit },
    { to: '/workflow/catalog', label: '工作流', icon: Blocks, permissions: ['workflow_view'] },
    { to: '/workflow/runs', label: '流程执行', icon: Activity, permissions: ['workflow_view'] },
  ],
  probe: [
    { to: '/probe/dashboard', label: '仪表盘', icon: Activity },
    { to: '/probe/realtime', label: '实时监测', icon: Radar },
    { to: '/probe/scan', label: '扫描管理', icon: ScanSearch },
    { to: '/probe/ai', label: 'AI 分析', icon: BrainCircuit },
  ],
}

const modeDefaultRoute: Record<ModeKey, string> = {
  defense: '/defense/dashboard',
  probe: '/probe/dashboard',
}

const activeModeLabel = computed(() => {
  return activeMode.value === 'defense' ? '防御模式' : '探测模式'
})

const currentSidebarItems = computed(() => {
  const roleValue = role.value === 'admin' || role.value === 'operator' || role.value === 'viewer'
    ? role.value
    : 'viewer'
  return sidebarMap[activeMode.value].filter((item) => {
    if (item.roles && !item.roles.includes(roleValue)) return false
    if (item.permissions && !hasAnyPermission(item.permissions)) return false
    return true
  })
})

const roleText = computed(() => {
  const map: Record<string, string> = { admin: 'Admin', operator: 'Operator', viewer: 'Viewer' }
  return map[role.value] || role.value
})

const roleBadgeVariant = computed(() => {
  return role.value === 'admin' ? ('default' as const) : ('secondary' as const)
})

const unreadNotifications = computed(() => unreadCount.value)

// function removed

const resetAnimatedState = () => {
  if (shellRef.value) gsap.set(shellRef.value, { clearProps: 'all' })
  if (sidebarRef.value) gsap.set(sidebarRef.value, { clearProps: 'transform,opacity,filter' })
  if (contentRef.value) gsap.set(contentRef.value, { clearProps: 'all' })
  if (maskWrapRef.value) gsap.set(maskWrapRef.value, { autoAlpha: 0, display: 'none' })
  if (maskPanelRefs.value.length > 0) gsap.set(maskPanelRefs.value, { clearProps: 'all' })
  if (impactPulseRef.value) gsap.set(impactPulseRef.value, { autoAlpha: 0, scale: 0.4, clearProps: 'all' })
  if (inkTopRef.value) gsap.set(inkTopRef.value, { autoAlpha: 0, scaleX: 0, clearProps: 'all' })
  if (inkBottomRef.value) gsap.set(inkBottomRef.value, { autoAlpha: 0, scaleX: 0, clearProps: 'all' })
  if (transitionTitleRef.value) gsap.set(transitionTitleRef.value, { autoAlpha: 0, scale: 1, letterSpacing: '0.5em', clearProps: 'all' })
}

const runModeTransition = async (targetMode: ModeKey) => {
  // 模式切换动画序列 — 检查必要 DOM 元素
  // 模式切换动画序列 — 初始化状态
  const sidebarEl = sidebarRef.value
  const contentEl = contentRef.value
  const shellEl = shellRef.value
  const maskWrapEl = maskWrapRef.value
  const pulseEl = impactPulseRef.value
  const topLineEl = inkTopRef.value
  const bottomLineEl = inkBottomRef.value
  const panels = maskPanelRefs.value
  const titleEl = transitionTitleRef.value

  const isProbe = targetMode === 'probe'
  const accentColor = isProbe ? '#f97316' : '#3b82f6' // Orange for Probe, Blue for Defense
  transitionTitleText.value = isProbe ? '主动探测' : '防御坚守'

  if (modeTimeline) {
    modeTimeline.kill()
  }

  isModeSwitching.value = true

  // Fallback
  if (!contentEl || !shellEl || !maskWrapEl) {
    void router.push(modeDefaultRoute[targetMode]).then(() => {
      isModeSwitching.value = false
    })
    return
  }

  // Ensure the new title text is rendered before GSAP snapshots transforms.
  await nextTick()
  if (titleEl) {
    // Force layout so translate(-50%, -50%) is calculated with real glyph metrics.
    void titleEl.offsetWidth
  }

  // Initial States
  gsap.set(maskWrapEl, { display: 'flex', autoAlpha: 1 })
  gsap.set(panels, { 
    scaleY: 0, 
    transformOrigin: 'top', 
    backgroundColor: isProbe ? '#0c0a09' : '#0f172a', 
    borderColor: isProbe ? 'rgba(249, 115, 22, 0.2)' : 'rgba(59, 130, 246, 0.2)'
  })
  
  if (pulseEl) {
    gsap.set(pulseEl, { 
      autoAlpha: 0, 
      scale: 0,
      borderColor: accentColor,
      boxShadow: `0 0 30px ${accentColor}`
    })
  }

  if (topLineEl && bottomLineEl) {
    gsap.set([topLineEl, bottomLineEl], { 
      scaleX: 0, 
      autoAlpha: 0,
      backgroundColor: accentColor,
      boxShadow: `0 0 20px ${accentColor}`
    })
  }

  if (titleEl) {
    gsap.set(titleEl, {
      autoAlpha: 0,
      scale: 0.8,
      x: 0,
      y: 0,
      xPercent: -50,
      yPercent: -50,
      transformOrigin: '50% 50%',
      letterSpacing: '1em',
      textShadow: `0 0 0px ${accentColor}`
    })
  }

  modeTimeline = gsap.timeline({
    onComplete: () => {
      isModeSwitching.value = false
      modeTimeline = null
      resetAnimatedState()
    }
  })

  // --- Animation Sequence (Slower & Cinematic) ---
  
  // 1. Initiate: Content scales down
  modeTimeline
    .to(contentEl, {
      filter: 'blur(4px) grayscale(80%)',
      opacity: 0.6,
      duration: 0.6,
      ease: 'power2.inOut'
    }, 0)
    .to(shellEl, {
      backgroundColor: '#000',
      duration: 0.6
    }, 0)

  if (sidebarEl) {
    modeTimeline.to(sidebarEl, {
      scaleX: 1,
      filter: 'blur(4px) grayscale(80%)',
      opacity: 0.6,
      transformOrigin: 'center center',
      duration: 0.6,
      ease: 'power2.inOut'
    }, 0)
  }

  // 2. Tech Wipe: Panels slam down (Full Cover)
  modeTimeline.to(panels, {
    scaleY: 1,
    duration: 0.7,
    stagger: {
      amount: 0.3,
      from: isProbe ? 'start' : 'end',
      grid: [1, 12]
    },
    ease: 'expo.inOut'
  }, 0.2)

  // 3. Scan Lines: Zip across during close
  if (topLineEl && bottomLineEl) {
    modeTimeline.to([topLineEl, bottomLineEl], {
      autoAlpha: 1,
      scaleX: 1,
      duration: 0.5,
      ease: 'power2.inOut'
    }, 0.3)
  }

  // 4. TITLE REVEAL (The "Middle" Moment)
  // Starts when panels are mostly down (around 0.8s)
  if (titleEl) {
    modeTimeline
      .to(titleEl, {
        autoAlpha: 1,
        scale: 1,
        letterSpacing: '0.2em', // Compress tracking
        textShadow: `0 0 30px ${accentColor}`,
        duration: 0.8,
        ease: 'power4.out'
      }, 0.7) // Start appearing as panels finish closing
      
      // Glitch shake effect
      .to(titleEl, {
        x: 2,
        y: -2,
        duration: 0.05,
        repeat: 5,
        yoyo: true,
        ease: 'steps(1)'
      }, 0.8)
      
      // Hold for a moment (0.5s pause implicit in duration)
      .to(titleEl, {
        autoAlpha: 0,
        scale: 1.5,
        x: 0,
        y: 0,
        filter: 'blur(10px)',
        letterSpacing: '0.5em',
        duration: 0.4,
        ease: 'power2.in'
      }, 1.6) // Fade out after hold
  }

  // 5. Switch Router (Hidden behind panels)
  modeTimeline.add(() => {
    void router.push(modeDefaultRoute[targetMode]).then(() => {
      gsap.set(contentEl, {
        filter: 'blur(10px) brightness(1.5)',
        opacity: 0
      })

      if (sidebarEl) {
        gsap.set(sidebarEl, {
          filter: 'blur(10px) brightness(1.5)',
          scaleX: 1,
          opacity: 0,
          transformOrigin: 'center center'
        })
      }
    })
  }, 1.2) // Switch happens while text is visible

  // 6. Reveal: Panels retract (Starts after title fades out)
  const revealStart = 1.8 // Delayed start
  
  modeTimeline.to(panels, {
    scaleY: 0,
    transformOrigin: 'bottom',
    duration: 0.7,
    stagger: {
      amount: 0.2,
      from: isProbe ? 'end' : 'start'
    },
    ease: 'expo.inOut'
  }, revealStart)

  // 7. Lines fade out
  if (topLineEl && bottomLineEl) {
    modeTimeline.to([topLineEl, bottomLineEl], {
      scaleX: 0,
      autoAlpha: 0,
      transformOrigin: isProbe ? 'right' : 'left',
      duration: 0.4
    }, revealStart + 0.1)
  }

  // 8. Energy Burst (Sync with reveal)
  if (pulseEl) {
    modeTimeline
      .set(pulseEl, { autoAlpha: 1, scale: 0.1 }, revealStart)
      .to(pulseEl, {
        scale: 4,
        autoAlpha: 0,
        duration: 0.6,
        ease: 'power2.out'
      }, revealStart)
  }

  // 9. Content Returns
  modeTimeline.to(contentEl, {
    filter: 'blur(0px) brightness(1)',
    opacity: 1,
    duration: 0.8,
    ease: 'power3.out'
  }, revealStart + 0.2)

  if (sidebarEl) {
    modeTimeline.to(sidebarEl, {
      scaleX: 1,
      scaleY: 1,
      filter: 'blur(0px) brightness(1)',
      opacity: 1,
      duration: 0.8,
      ease: 'power3.out'
    }, revealStart + 0.2)
  }
  
  // 10. Restore Shell
  modeTimeline.to(shellEl, {
    backgroundColor: '',
    clearProps: 'backgroundColor',
    duration: 0.5
  }, revealStart + 0.3)
}

const switchMode = (mode: ModeKey) => {
  if (mode === activeMode.value) return
  if (isModeSwitching.value) return
  void runModeTransition(mode)
}

const onModeChange = (nextMode: string | number) => {
  if (nextMode === 'defense' || nextMode === 'probe') {
    switchMode(nextMode)
  }
}

const goToSettings = () => {
  router.push('/settings')
}

const goToSecuritySettings = () => {
  router.push('/settings?tab=security')
}

const markNotificationRead = async (item: NotifItem) => {
  if (item.read) return
  try {
    await apiClient.post(`/notifications/${item.id}/read`)
    item.read = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
  } catch { /* ignore */ }
}

const markAllNotificationsRead = async () => {
  try {
    await apiClient.post('/notifications/read-all')
    notifications.value = notifications.value.map((item) => ({ ...item, read: true }))
    unreadCount.value = 0
    notifPage.value = 1
  } catch { /* ignore */ }
}

const goToProfile = () => {
  router.push('/profile')
}

// 路由切换进度与页面过渡动画
let progressTimer: ReturnType<typeof setTimeout> | null = null

watch(() => route.fullPath, () => {
  isRouteChanging.value = true
  routeProgress.value = 0.25
  
  if (progressTimer) clearTimeout(progressTimer)
  
  progressTimer = setTimeout(() => {
    routeProgress.value = 0.68
  }, 180)
  
  nextTick(() => {
    setTimeout(() => {
      routeProgress.value = 1
      setTimeout(() => {
        isRouteChanging.value = false
        routeProgress.value = 0
      }, 220)
    }, 120)
  })
})

onMounted(() => {
  initTheme()
  loadSidebarPreference()
  sidebarAnimatedWidth.value = getSidebarTargetWidth()

  const user = parseStoredUserInfo()
  if (user) {
    username.value = user.username || 'user'
    role.value = user.role || 'viewer'
  }

  resetAnimatedState()

  loadTopbarStatus()
  statusPollTimer = setInterval(loadTopbarStatus, 30000)

  loadNotifications()
  notifPollTimer = setInterval(loadNotifications, 30000)
})

onUnmounted(() => {
  if (modeTimeline) {
    modeTimeline.kill()
    modeTimeline = null
  }
  if (progressTimer) {
    clearTimeout(progressTimer)
    progressTimer = null
  }
  stopSidebarResize()
  stopSidebarWidthAnimation()
  if (statusPollTimer) {
    clearInterval(statusPollTimer)
    statusPollTimer = null
  }
  if (notifPollTimer) {
    clearInterval(notifPollTimer)
    notifPollTimer = null
  }
})

const handleLogout = async () => {
  try {
    await authApi.logout()
  } catch (err) {
    console.error('Logout failed:', err)
  } finally {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_info')
    router.push('/login')
  }
}
</script>

<style scoped>
.sidebar-item-label {
  display: inline-block;
  overflow: hidden;
  white-space: nowrap;
  transform-origin: left center;
  transition: opacity 220ms ease, transform 220ms ease;
}

.sidebar-item-label-expanded {
  max-width: 9rem;
  opacity: 1;
  transform: translateX(0);
}

.sidebar-item-label-collapsed {
  max-width: 0;
  opacity: 0;
  transform: translateX(-6px);
}

.sidebar-mode-label {
  display: inline-block;
  overflow: hidden;
  white-space: nowrap;
  transition: opacity 220ms ease, transform 220ms ease;
}

.sidebar-mode-label-expanded {
  max-width: 10rem;
  opacity: 1;
}

.sidebar-mode-label-collapsed {
  max-width: 2.5rem;
  opacity: 0.95;
}

.sidebar-action {
  transition: border-color 220ms ease, background-color 220ms ease, box-shadow 220ms ease, color 220ms ease;
}

.sidebar-action-defense {
  border-color: rgba(59, 130, 246, 0.25);
}

.sidebar-action-defense:hover {
  border-color: rgba(59, 130, 246, 0.4);
  background: rgba(59, 130, 246, 0.08);
  color: #3b82f6;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.08);
}

.sidebar-action-defense:active {
  border-color: rgba(59, 130, 246, 0.5);
  background: rgba(59, 130, 246, 0.12);
  color: #3b82f6;
  box-shadow: none;
}

.sidebar-action-active-defense {
  border-color: rgba(59, 130, 246, 0.5);
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(59, 130, 246, 0.1);
}

.sidebar-action-probe {
  border-color: rgba(249, 115, 22, 0.25);
}

.sidebar-action-probe:hover {
  border-color: rgba(249, 115, 22, 0.4);
  background: rgba(249, 115, 22, 0.08);
  color: #f97316;
  box-shadow: 0 2px 8px rgba(249, 115, 22, 0.08);
}

.sidebar-action-probe:active {
  border-color: rgba(249, 115, 22, 0.5);
  background: rgba(249, 115, 22, 0.12);
  color: #f97316;
  box-shadow: none;
}

.sidebar-action-active-probe {
  border-color: rgba(249, 115, 22, 0.5);
  background: rgba(249, 115, 22, 0.1);
  color: #f97316;
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(249, 115, 22, 0.1);
}

@media (prefers-reduced-motion: reduce) {
  .sidebar-item-label,
  .sidebar-mode-label {
    transition: none;
  }
}
</style>


