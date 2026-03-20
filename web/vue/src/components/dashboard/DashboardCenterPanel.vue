<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import DashboardWelcomeBanner from './DashboardWelcomeBanner.vue'
import DashboardWorldMap from './DashboardWorldMap.vue'
import DashboardTopology from './DashboardTopology.vue'
import { Button } from '@/components/ui/button'
import { Maximize2, Minimize2, Activity, Globe, Wifi } from 'lucide-vue-next'

interface TopMetrics {
  hfish_total: number
  hfish_high: number
  nmap_online: number
  ai_decisions: number
  blocked_ips: number
}

interface RecentAttack {
  attack_ip: string
  ip_location?: string
  service_name?: string
  threat_level?: string
  create_time_str?: string
}

interface ScreenPayload {
  top_metrics: TopMetrics
  chain_status: Record<string, boolean>
  trends: { labels: string[]; counts: number[] }
  threat_distribution: { levels: string[]; counts: number[] }
  hot_services: Array<{ name: string; count: number }>
  recent_attacks: RecentAttack[]
  topology: {
    nodes: Array<{ id: string; label: string; type: string; status: string }>
    links: Array<{ source: string; target: string; type: string }>
  }
}

const props = defineProps<{
  payload: ScreenPayload
  loading: boolean
  loadError: string
}>()

const isFullscreen = ref(false)
const containerRef = ref<HTMLElement>()

// 入场动画状态
const animationState = ref({
  welcome: false,
  overviewMap: false,
})

const dashboardViews = [
  { key: 'overview', label: '总览', icon: Activity },
  { key: 'map', label: '地图', icon: Globe },
  { key: 'topology', label: '拓扑', icon: Wifi },
] as const

const activeView = ref<(typeof dashboardViews)[number]['key']>('overview')

const toggleFullscreen = async () => {
  if (!document.fullscreenElement) {
    await containerRef.value?.requestFullscreen()
    isFullscreen.value = true
  } else {
    await document.exitFullscreen()
    isFullscreen.value = false
  }
}

onMounted(() => {
  const handleFullscreenChange = () => {
    isFullscreen.value = !!document.fullscreenElement
  }
  document.addEventListener('fullscreenchange', handleFullscreenChange)
  
  // 启动入场动画序列
  setTimeout(() => { animationState.value.welcome = true }, 200)
  setTimeout(() => { animationState.value.overviewMap = true }, 400)

  onUnmounted(() => {
    document.removeEventListener('fullscreenchange', handleFullscreenChange)
  })
})
</script>

<template>
  <div ref="containerRef" class="flex-1 relative overflow-hidden bg-gradient-to-br from-slate-900/50 to-slate-800/30 backdrop-blur-sm rounded-xl border border-border/20">
    <!-- 背景粒子动画 -->
    <div class="absolute inset-0 overflow-hidden pointer-events-none">
      <div class="absolute w-2 h-2 bg-cyan-500/20 rounded-full animate-float-1" style="top: 10%; left: 20%;" />
      <div class="absolute w-3 h-3 bg-purple-500/20 rounded-full animate-float-2" style="top: 60%; left: 80%;" />
      <div class="absolute w-2 h-2 bg-green-500/20 rounded-full animate-float-3" style="top: 80%; left: 15%;" />
      <div class="absolute w-4 h-4 bg-cyan-500/10 rounded-full animate-float-4" style="top: 30%; left: 70%;" />
      <div class="absolute w-2 h-2 bg-red-500/10 rounded-full animate-float-5" style="top: 50%; left: 40%;" />
    </div>

    <!-- 主内容区域 -->
    <div class="h-full p-4 md:p-5">
      <!-- Topbar: 视图切换 + 全屏控制 -->
      <div class="mb-3 flex items-center justify-between">
        <div class="w-10" />
        <div class="flex items-center gap-1 rounded-lg bg-card/60 p-1 backdrop-blur-sm border border-cyan-500/20 shadow-lg shadow-cyan-500/5">
          <button
            v-for="(view, index) in dashboardViews"
            :key="view.key"
            @click="activeView = view.key"
            class="group relative flex items-center gap-2 overflow-hidden rounded-md px-3 py-1.5 text-xs font-medium transition-all duration-300"
            :class="activeView === view.key
              ? 'text-cyan-400 bg-cyan-400/10 border border-cyan-400/30 shadow-inner'
              : 'text-muted-foreground hover:text-foreground'"
          >
            <span v-if="activeView === view.key" class="absolute inset-0 bg-gradient-to-r from-cyan-500/10 to-transparent animate-pulse" />
            <component :is="view.icon" class="h-3.5 w-3.5 transition-transform duration-300 group-hover:scale-110" />
            <span class="relative">{{ view.label }}</span>
          </button>
        </div>

        <Button
          variant="ghost"
          size="sm"
          @click="toggleFullscreen"
          class="bg-card/60 backdrop-blur-sm border border-border/40 hover:bg-card/80 transition-all duration-300 hover:border-cyan-500/50"
        >
          <Maximize2 v-if="!isFullscreen" class="w-4 h-4" />
          <Minimize2 v-else class="w-4 h-4" />
        </Button>
      </div>

      <!-- 总览视图 -->
      <div v-if="activeView === 'overview'" class="h-full space-y-4">
        <!-- 欢迎横幅 -->
        <div
          class="transition-all duration-700 ease-out"
          :class="animationState.welcome ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'"
        >
          <DashboardWelcomeBanner :top-metrics="payload.top_metrics" :loading="loading" />
        </div>

        <!-- 总览主视图（地图 + 攻击记录） -->
        <div
          class="h-[calc(100%-165px)] flex flex-col gap-4 transition-all duration-700 ease-out"
          :class="animationState.overviewMap ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6'"
        >
          <div class="flex-1 min-h-0">
            <DashboardWorldMap
              :recent-attacks="payload.recent_attacks"
              :loading="loading"
              :load-error="loadError"
            />
          </div>
        </div>
      </div>

      <!-- 地图视图 -->
      <div v-else-if="activeView === 'map'" class="h-full">
        <DashboardWorldMap
          :recent-attacks="payload.recent_attacks"
          :loading="loading"
          :load-error="loadError"
        />
      </div>

      <!-- 拓扑视图 -->
      <div v-else-if="activeView === 'topology'" class="h-full">
        <DashboardTopology :topology="payload.topology" :loading="loading" />
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 浮动动画 */
@keyframes float-1 {
  0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.3; }
  50% { transform: translate(20px, -30px) scale(1.2); opacity: 0.6; }
}

@keyframes float-2 {
  0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.2; }
  50% { transform: translate(-15px, 25px) scale(1.1); opacity: 0.5; }
}

@keyframes float-3 {
  0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.25; }
  50% { transform: translate(25px, 15px) scale(1.3); opacity: 0.4; }
}

@keyframes float-4 {
  0%, 100% { transform: translate(0, 0); opacity: 0.15; }
  50% { transform: translate(-20px, -20px); opacity: 0.3; }
}

@keyframes float-5 {
  0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.1; }
  50% { transform: translate(10px, -15px) scale(0.8); opacity: 0.25; }
}

.animate-float-1 { animation: float-1 6s ease-in-out infinite; }
.animate-float-2 { animation: float-2 8s ease-in-out infinite; }
.animate-float-3 { animation: float-3 7s ease-in-out infinite; }
.animate-float-4 { animation: float-4 9s ease-in-out infinite; }
.animate-float-5 { animation: float-5 5s ease-in-out infinite; }
</style>
