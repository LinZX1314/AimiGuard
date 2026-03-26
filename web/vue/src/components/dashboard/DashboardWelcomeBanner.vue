<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed, watch } from 'vue'

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
let pulseTimer = 0
let rollTimer = 0

const animatedMetrics = ref({
  hfish_total: 0,
  hfish_high: 0,
  nmap_online: 0,
  ai_decisions: 0,
  blocked_ips: 0,
})

const formatNumber = (num: number) => {
  if (num >= 10000) return (num / 10000).toFixed(1) + 'w'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'k'
  return num.toString()
}

const threatLevel = computed(() => {
  const ratio = props.topMetrics.hfish_high / Math.max(props.topMetrics.hfish_total, 1)
  if (ratio > 0.3) return { level: '高危', color: 'text-red-400', bgColor: 'bg-red-500/20' }
  if (ratio > 0.1) return { level: '警告', color: 'text-yellow-400', bgColor: 'bg-yellow-500/20' }
  return { level: '安全', color: 'text-green-400', bgColor: 'bg-green-500/20' }
})

function startRollAnimation(targetValues: TopMetrics) {
  if (rollTimer) clearInterval(rollTimer)
  
  const duration = 1500
  const steps = 30
  const interval = duration / steps
  let step = 0

  rollTimer = window.setInterval(() => {
    step++
    const progress = step / steps
    const eased = 1 - Math.pow(1 - progress, 3)

    animatedMetrics.value = {
      hfish_total: Math.round(targetValues.hfish_total * eased),
      hfish_high: Math.round(targetValues.hfish_high * eased),
      nmap_online: Math.round(targetValues.nmap_online * eased),
      ai_decisions: Math.round(targetValues.ai_decisions * eased),
      blocked_ips: Math.round(targetValues.blocked_ips * eased),
    }

    if (step >= steps) {
      clearInterval(rollTimer)
      rollTimer = 0
      animatedMetrics.value = { ...targetValues }
    }
  }, interval)
}

watch(() => props.topMetrics, (newVal, oldVal) => {
  if (oldVal && (newVal.hfish_total !== oldVal.hfish_total || 
                  newVal.hfish_high !== oldVal.hfish_high ||
                  newVal.nmap_online !== oldVal.nmap_online ||
                  newVal.ai_decisions !== oldVal.ai_decisions ||
                  newVal.blocked_ips !== oldVal.blocked_ips)) {
    startRollAnimation(newVal)
  }
}, { deep: true })

onMounted(() => {
  setTimeout(() => { mounted.value = true }, 100)

  pulseTimer = window.setInterval(() => {
    animationStep.value = (animationStep.value + 1) % 3
  }, 2000)

  startRollAnimation(props.topMetrics)
})

onUnmounted(() => {
  if (rollTimer) clearInterval(rollTimer)
  if (pulseTimer) clearInterval(pulseTimer)
})
</script>

<template>
  <div class="relative z-10 transition-all duration-700" :class="mounted ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-4'">
    <div class="dashboard-kpi-shell">
      <div class="dashboard-kpi-head">
        <div class="dashboard-kpi-title">态势摘要</div>
        <div class="dashboard-kpi-status" :class="threatLevel.bgColor">
          <span class="status-dot" />
          <span :class="threatLevel.color">{{ threatLevel.level }}</span>
        </div>
      </div>

      <div class="dashboard-kpi-strip">
        <article class="kpi-chip" :class="{ 'kpi-chip--active': animationStep === 0 }">
          <span>总攻击</span>
<strong class="text-primary">{{ loading ? 0 : formatNumber(animatedMetrics.hfish_total) }}</strong>
        </article>
        <article class="kpi-chip" :class="{ 'kpi-chip--active': animationStep === 2 }">
          <span>在线主机</span>
          <strong class="text-emerald-400">{{ loading ? 0 : formatNumber(animatedMetrics.nmap_online) }}</strong>
        </article>
        <article class="kpi-chip" :class="{ 'kpi-chip--active': animationStep === 0 }">
          <span>AI决策</span>
          <strong class="text-sky-500 dark:text-sky-300">{{ loading ? 0 : formatNumber(animatedMetrics.ai_decisions) }}</strong>
        </article>
        <article class="kpi-chip" :class="{ 'kpi-chip--active': animationStep === 1 }">
          <span>已封禁</span>
          <strong class="text-slate-600 dark:text-slate-300">{{ loading ? 0 : formatNumber(animatedMetrics.blocked_ips) }}</strong>
        </article>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard-kpi-shell {
  position: relative;
  border-radius: 10px;
  border: 1px solid hsl(var(--border) / 0.45);
  background: linear-gradient(170deg, hsl(var(--card) / 0.78), hsl(var(--card) / 0.52));
  padding: 10px 12px;
  overflow: hidden;
}

:global(html.dark) .dashboard-kpi-shell {
  background: linear-gradient(170deg, rgb(15 23 42 / 0.84), rgb(2 10 23 / 0.76));
}

.dashboard-kpi-shell::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(120deg, transparent 0%, rgb(56 189 248 / 0.1) 40%, transparent 90%);
  animation: shell-scan 4.5s linear infinite;
  pointer-events: none;
}

.dashboard-kpi-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.dashboard-kpi-title {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.4px;
}

.dashboard-kpi-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 11px;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: rgb(34 197 94);
  box-shadow: 0 0 8px rgb(34 197 94 / 0.8);
}

.dashboard-kpi-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.kpi-chip {
  position: relative;
  border-radius: 8px;
  border: 1px solid hsl(var(--border) / 0.42);
  background: hsl(var(--background) / 0.5);
  padding: 7px 8px;
  min-height: 56px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 3px;
}

:global(html.dark) .kpi-chip {
  background: rgb(15 23 42 / 0.46);
}

.kpi-chip span {
  font-size: 10px;
  color: hsl(var(--muted-foreground));
}

.kpi-chip strong {
  font-size: 18px;
  line-height: 1;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.kpi-chip--active {
  border-color: rgb(14 165 233 / 0.45);
  box-shadow: 0 0 0 1px rgb(56 189 248 / 0.25) inset;
}

@keyframes shell-scan {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

@media (max-width: 1100px) {
  .dashboard-kpi-strip {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .dashboard-kpi-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
