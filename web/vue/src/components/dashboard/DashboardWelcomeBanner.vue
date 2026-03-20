<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'

interface TopMetrics {
  hfish_total: number
  hfish_high: number
  nmap_online: number
  ai_decisions: number
  blocked_ips: number
}

const props = defineProps<{
  topMetrics: TopMetrics
  loading: boolean
}>()

const mounted = ref(false)
const animationStep = ref(0)

// 数字动画
const animatedMetrics = ref({
  hfish_total: 0,
  hfish_high: 0,
  nmap_online: 0,
  ai_decisions: 0,
  blocked_ips: 0,
})

// 格式化数字
const formatNumber = (num: number) => {
  if (num >= 10000) return (num / 10000).toFixed(1) + 'w'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'k'
  return num.toString()
}

// 计算威胁等级
const threatLevel = computed(() => {
  const ratio = props.topMetrics.hfish_high / Math.max(props.topMetrics.hfish_total, 1)
  if (ratio > 0.3) return { level: '高危', color: 'text-red-400', bgColor: 'bg-red-500/20' }
  if (ratio > 0.1) return { level: '警告', color: 'text-yellow-400', bgColor: 'bg-yellow-500/20' }
  return { level: '安全', color: 'text-green-400', bgColor: 'bg-green-500/20' }
})

onMounted(() => {
  // 入场动画
  setTimeout(() => { mounted.value = true }, 100)
  
  // 数字滚动动画
  const targetValues = { ...props.topMetrics }
  const duration = 1500
  const steps = 30
  const interval = duration / steps
  let step = 0
  
  const timer = setInterval(() => {
    step++
    const progress = step / steps
    const eased = 1 - Math.pow(1 - progress, 3) // easeOutCubic
    
    animatedMetrics.value = {
      hfish_total: Math.round(targetValues.hfish_total * eased),
      hfish_high: Math.round(targetValues.hfish_high * eased),
      nmap_online: Math.round(targetValues.nmap_online * eased),
      ai_decisions: Math.round(targetValues.ai_decisions * eased),
      blocked_ips: Math.round(targetValues.blocked_ips * eased),
    }
    
    if (step >= steps) {
      clearInterval(timer)
      animatedMetrics.value = { ...targetValues }
    }
  }, interval)

  // 脉冲动画循环
  const pulseTimer = setInterval(() => {
    animationStep.value = (animationStep.value + 1) % 3
  }, 2000)
  
  return () => {
    clearInterval(timer)
    clearInterval(pulseTimer)
  }
})
</script>

<template>
  <div class="relative z-10 transition-all duration-700" :class="mounted ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-4'">
    <!-- 背景光效 -->
    <div class="absolute inset-0 -mx-4 -my-2 bg-gradient-to-r from-cyan-500/5 via-transparent to-cyan-500/5 rounded-xl blur-xl animate-pulse" />
    
    <!-- 主内容 -->
    <div class="relative bg-gradient-to-b from-card/60 to-card/30 backdrop-blur-md rounded-xl border border-cyan-500/20 p-5 overflow-hidden">
      <!-- 动态扫描线 -->
      <div class="absolute inset-0 overflow-hidden pointer-events-none">
        <div class="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-cyan-500/50 to-transparent animate-[scan_3s_linear_infinite]" />
      </div>

      <!-- 角落装饰 -->
      <div class="absolute top-0 left-0 w-16 h-16">
        <div class="absolute top-0 left-0 w-4 h-[1px] bg-cyan-500/50" />
        <div class="absolute top-0 left-0 w-[1px] h-4 bg-cyan-500/50" />
      </div>
      <div class="absolute top-0 right-0 w-16 h-16">
        <div class="absolute top-0 right-0 w-4 h-[1px] bg-cyan-500/50" />
        <div class="absolute top-0 right-0 w-[1px] h-4 bg-cyan-500/50" />
      </div>
      <div class="absolute bottom-0 left-0 w-16 h-16">
        <div class="absolute bottom-0 left-0 w-4 h-[1px] bg-cyan-500/50" />
        <div class="absolute bottom-0 left-0 w-[1px] h-4 bg-cyan-500/50" />
      </div>
      <div class="absolute bottom-0 right-0 w-16 h-16">
        <div class="absolute bottom-0 right-0 w-4 h-[1px] bg-cyan-500/50" />
        <div class="absolute bottom-0 right-0 w-[1px] h-4 bg-cyan-500/50" />
      </div>

      <!-- 系统状态指示 -->
      <div class="absolute top-2 right-8 flex items-center gap-2">
        <div class="relative flex items-center gap-1.5 px-2 py-1 rounded-full bg-card/80 border border-border/40">
          <span class="relative flex h-2 w-2">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
          </span>
          <span class="text-[10px] text-muted-foreground font-medium">{{ threatLevel.level }}</span>
        </div>
      </div>

      <!-- 核心指标 -->
      <div class="grid grid-cols-5 gap-3">
        <!-- 总攻击 -->
        <div class="group relative text-center p-3 rounded-lg bg-muted/20 border border-border/40 hover:border-cyan-500/50 hover:bg-cyan-500/5 transition-all duration-300 cursor-default">
          <div class="absolute inset-0 bg-gradient-to-t from-cyan-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity rounded-lg" />
          <div class="relative">
            <div class="text-[11px] text-muted-foreground mb-1">总攻击</div>
            <div class="text-xl font-bold text-cyan-400 tabular-nums" :class="{ 'animate-[glow_1s_ease-in-out_infinite]': animationStep === 0 }">
              {{ loading ? 0 : formatNumber(animatedMetrics.hfish_total) }}
            </div>
            <div class="absolute -bottom-0.5 left-1/2 -translate-x-1/2 w-0 h-[2px] bg-cyan-500/50 group-hover:w-full transition-all duration-300" />
          </div>
        </div>

        <!-- 高危 -->
        <div class="group relative text-center p-3 rounded-lg bg-muted/20 border border-border/40 hover:border-red-500/50 hover:bg-red-500/5 transition-all duration-300 cursor-default">
          <div class="absolute inset-0 bg-gradient-to-t from-red-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity rounded-lg" />
          <div class="relative">
            <div class="text-[11px] text-muted-foreground mb-1">高危</div>
            <div class="text-xl font-bold text-red-400 tabular-nums" :class="{ 'animate-[glow-red_1s_ease-in-out_infinite]': animationStep === 1 }">
              {{ loading ? 0 : formatNumber(animatedMetrics.hfish_high) }}
            </div>
            <div class="absolute -bottom-0.5 left-1/2 -translate-x-1/2 w-0 h-[2px] bg-red-500/50 group-hover:w-full transition-all duration-300" />
          </div>
        </div>

        <!-- 在线主机 -->
        <div class="group relative text-center p-3 rounded-lg bg-muted/20 border border-border/40 hover:border-green-500/50 hover:bg-green-500/5 transition-all duration-300 cursor-default">
          <div class="absolute inset-0 bg-gradient-to-t from-green-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity rounded-lg" />
          <div class="relative">
            <div class="text-[11px] text-muted-foreground mb-1">在线主机</div>
            <div class="text-xl font-bold text-green-400 tabular-nums" :class="{ 'animate-[glow-green_1s_ease-in-out_infinite]': animationStep === 2 }">
              {{ loading ? 0 : formatNumber(animatedMetrics.nmap_online) }}
            </div>
            <div class="absolute -bottom-0.5 left-1/2 -translate-x-1/2 w-0 h-[2px] bg-green-500/50 group-hover:w-full transition-all duration-300" />
          </div>
        </div>

        <!-- AI决策 -->
        <div class="group relative text-center p-3 rounded-lg bg-muted/20 border border-border/40 hover:border-purple-500/50 hover:bg-purple-500/5 transition-all duration-300 cursor-default">
          <div class="absolute inset-0 bg-gradient-to-t from-purple-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity rounded-lg" />
          <div class="relative">
            <div class="text-[11px] text-muted-foreground mb-1">AI决策</div>
            <div class="text-xl font-bold text-purple-400 tabular-nums" :class="{ 'animate-[glow-purple_1s_ease-in-out_infinite]': animationStep === 0 }">
              {{ loading ? 0 : formatNumber(animatedMetrics.ai_decisions) }}
            </div>
            <div class="absolute -bottom-0.5 left-1/2 -translate-x-1/2 w-0 h-[2px] bg-purple-500/50 group-hover:w-full transition-all duration-300" />
          </div>
        </div>

        <!-- 已封禁 -->
        <div class="group relative text-center p-3 rounded-lg bg-muted/20 border border-border/40 hover:border-slate-500/50 hover:bg-slate-500/5 transition-all duration-300 cursor-default">
          <div class="absolute inset-0 bg-gradient-to-t from-slate-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity rounded-lg" />
          <div class="relative">
            <div class="text-[11px] text-muted-foreground mb-1">已封禁</div>
            <div class="text-xl font-bold text-slate-400 tabular-nums" :class="{ 'animate-[glow-slate_1s_ease-in-out_infinite]': animationStep === 1 }">
              {{ loading ? 0 : formatNumber(animatedMetrics.blocked_ips) }}
            </div>
            <div class="absolute -bottom-0.5 left-1/2 -translate-x-1/2 w-0 h-[2px] bg-slate-500/50 group-hover:w-full transition-all duration-300" />
          </div>
        </div>
      </div>

      <!-- 底部数据流动画 -->
      <div class="absolute bottom-0 left-0 right-0 h-[2px] overflow-hidden">
        <div class="h-full flex gap-8 animate-[data-flow_2s_linear_infinite]">
          <div class="flex gap-8 whitespace-nowrap">
            <span class="text-[8px] text-cyan-500/30 font-mono">SYS.STATUS: OK</span>
            <span class="text-[8px] text-cyan-500/30 font-mono">│</span>
            <span class="text-[8px] text-cyan-500/30 font-mono">DEFENSE: ACTIVE</span>
            <span class="text-[8px] text-cyan-500/30 font-mono">│</span>
            <span class="text-[8px] text-cyan-500/30 font-mono">AI.MODE: INTELLIGENT</span>
            <span class="text-[8px] text-cyan-500/30 font-mono">│</span>
            <span class="text-[8px] text-cyan-500/30 font-mono">SCAN.INTERVAL: 15S</span>
          </div>
          <div class="flex gap-8 whitespace-nowrap">
            <span class="text-[8px] text-cyan-500/30 font-mono">SYS.STATUS: OK</span>
            <span class="text-[8px] text-cyan-500/30 font-mono">│</span>
            <span class="text-[8px] text-cyan-500/30 font-mono">DEFENSE: ACTIVE</span>
            <span class="text-[8px] text-cyan-500/30 font-mono">│</span>
            <span class="text-[8px] text-cyan-500/30 font-mono">AI.MODE: INTELLIGENT</span>
            <span class="text-[8px] text-cyan-500/30 font-mono">│</span>
            <span class="text-[8px] text-cyan-500/30 font-mono">SCAN.INTERVAL: 15S</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes scan {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

@keyframes data-flow {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}

@keyframes glow {
  0%, 100% { text-shadow: 0 0 5px rgba(34, 211, 238, 0.5); }
  50% { text-shadow: 0 0 15px rgba(34, 211, 238, 0.8), 0 0 25px rgba(34, 211, 238, 0.4); }
}

@keyframes glow-red {
  0%, 100% { text-shadow: 0 0 5px rgba(248, 113, 113, 0.5); }
  50% { text-shadow: 0 0 15px rgba(248, 113, 113, 0.8), 0 0 25px rgba(248, 113, 113, 0.4); }
}

@keyframes glow-green {
  0%, 100% { text-shadow: 0 0 5px rgba(74, 222, 128, 0.5); }
  50% { text-shadow: 0 0 15px rgba(74, 222, 128, 0.8), 0 0 25px rgba(74, 222, 128, 0.4); }
}

@keyframes glow-purple {
  0%, 100% { text-shadow: 0 0 5px rgba(192, 132, 252, 0.5); }
  50% { text-shadow: 0 0 15px rgba(192, 132, 252, 0.8), 0 0 25px rgba(192, 132, 252, 0.4); }
}

@keyframes glow-slate {
  0%, 100% { text-shadow: 0 0 5px rgba(148, 163, 184, 0.5); }
  50% { text-shadow: 0 0 15px rgba(148, 163, 184, 0.8), 0 0 25px rgba(148, 163, 184, 0.4); }
}

.animate-\[glow {
  animation: glow 1s ease-in-out infinite;
}
</style>
