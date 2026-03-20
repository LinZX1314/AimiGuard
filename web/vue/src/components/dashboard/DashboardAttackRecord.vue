<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from 'vue'
import { Badge } from '@/components/ui/badge'
import { MapPin, ShieldAlert } from 'lucide-vue-next'
import TechCard from './shared/TechCard.vue'

const props = defineProps<{
  recentAttacks: Array<{
    attack_ip: string
    ip_location?: string
    service_name?: string
    threat_level?: string
    create_time_str?: string
  }>
  loading: boolean
  loadError?: string
}>()

type AttackItem = {
  attack_ip: string
  ip_location?: string
  service_name?: string
  threat_level?: string
  create_time_str?: string
}

const normalizedAttacks = computed(() => props.recentAttacks.slice(0, 20))
const showErrorOnly = computed(() => Boolean(props.loadError) && normalizedAttacks.value.length === 0)

const queueItems = ref<AttackItem[]>([])
const popupItem = ref<AttackItem | null>(null)
const popupVisible = ref(false)
const latestKey = ref('')
let popupTimer: ReturnType<typeof setTimeout> | null = null

function attackKey(item?: AttackItem) {
  if (!item) return ''
  return `${item.attack_ip}-${item.create_time_str || ''}-${item.service_name || ''}`
}

function enqueue(item: AttackItem) {
  queueItems.value = [item, ...queueItems.value.filter((x) => attackKey(x) !== attackKey(item))].slice(0, 16)
}

function popupAndEnqueue(item: AttackItem) {
  popupItem.value = item
  popupVisible.value = true
  if (popupTimer) clearTimeout(popupTimer)
  popupTimer = setTimeout(() => {
    popupVisible.value = false
    enqueue(item)
  }, 1700)
}

watch(
  () => props.recentAttacks,
  (list) => {
    if (!list.length) return

    if (!queueItems.value.length) {
      queueItems.value = list.slice(0, 10)
    }

    const newest = list[0]
    const key = attackKey(newest)
    if (key && key !== latestKey.value) {
      latestKey.value = key
      popupAndEnqueue(newest)
    }
  },
  { immediate: true, deep: true },
)

onUnmounted(() => {
  if (popupTimer) clearTimeout(popupTimer)
})

const tickerItems = computed(() => {
  if (!queueItems.value.length) return []
  return [...queueItems.value, ...queueItems.value]
})

function formatThreatLevel(level?: string) {
  if (!level) return '未分级'
  const lower = level.toLowerCase()
  if (level === '高危' || lower === 'high' || lower === 'critical' || level === '严重') return '高危'
  if (level === '中危' || lower === 'medium') return '中危'
  if (level === '低危' || lower === 'low') return '低危'
  return level
}

function getThreatLevelColor(level?: string) {
  const lower = level?.toLowerCase() || ''
  if (lower === 'high' || lower === 'critical' || level === '高危' || level === '严重') {
    return 'text-red-300 border-red-400/35 bg-red-500/15'
  }
  if (lower === 'medium' || level === '中危') {
    return 'text-orange-300 border-orange-400/35 bg-orange-500/15'
  }
  if (lower === 'low' || level === '低危') {
    return 'text-emerald-300 border-emerald-400/35 bg-emerald-500/15'
  }
  return 'text-slate-300 border-slate-400/30 bg-slate-500/15'
}
</script>

<template>
  <TechCard glow-color="orange" class="flex-1 min-h-0 bg-slate-900/30">

    <div v-if="showErrorOnly" class="rounded-lg border border-orange-400/25 bg-gradient-to-r from-orange-500/15 to-red-500/10 px-3 py-3 text-sm text-orange-100">
      <div class="flex items-center gap-2">
        <ShieldAlert class="h-4 w-4 text-orange-300" />
        <span class="font-medium">攻击日志服务暂时不可用</span>
      </div>
      <p class="mt-1 text-xs text-orange-100/70">系统已进入回退展示模式，正在等待数据恢复。</p>
    </div>

    <template v-else>
      <div v-if="loadError" class="mb-2 rounded-md border border-amber-400/20 bg-amber-500/10 px-2 py-1 text-xs text-amber-200">
        实时刷新失败，当前展示最近一次成功获取的数据
      </div>

      <div class="mb-2 rounded-lg border border-cyan-400/20 bg-slate-950/40 p-2">
        <transition name="popup">
          <div
            v-if="popupItem && popupVisible"
            class="rounded-md border border-cyan-400/30 bg-cyan-500/12 px-2 py-1.5 shadow-[0_0_18px_rgba(34,211,238,0.15)]"
          >
            <div class="flex items-center justify-between gap-2">
              <div class="min-w-0">
                <p class="truncate font-mono text-sm text-cyan-100">{{ popupItem.attack_ip }}</p>
                <p class="truncate text-xs text-cyan-100/80">{{ popupItem.ip_location || '未知地区' }} / {{ popupItem.service_name || '未知服务' }}</p>
              </div>
              <Badge variant="outline" class="text-xs" :class="getThreatLevelColor(popupItem.threat_level)">
                {{ formatThreatLevel(popupItem.threat_level) }}
              </Badge>
            </div>
          </div>
        </transition>
      </div>

      <div class="relative h-[88px] overflow-hidden rounded-lg border border-border/40 bg-slate-950/45">
        <div class="pointer-events-none absolute inset-y-0 left-0 z-10 w-10 bg-gradient-to-r from-slate-950 to-transparent" />
        <div class="pointer-events-none absolute inset-y-0 right-0 z-10 w-10 bg-gradient-to-l from-slate-950 to-transparent" />

        <div v-if="tickerItems.length" class="attack-ticker-track flex h-full w-max items-center gap-2 px-2">
          <div
            v-for="(item, idx) in tickerItems"
            :key="`${item.attack_ip}-${item.create_time_str || ''}-${idx}`"
            class="attack-chip flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-xs"
            :class="getThreatLevelColor(item.threat_level)"
            :style="{ animationDelay: `${(idx % 10) * 0.12}s` }"
          >
            <MapPin class="h-3 w-3" />
            <span class="font-mono">{{ item.attack_ip }}</span>
            <span class="opacity-85">{{ item.ip_location || '未知地区' }}</span>
            <span class="opacity-70">{{ item.service_name || '未知服务' }}</span>
          </div>
        </div>

        <div v-else-if="!loading" class="flex h-full items-center justify-center text-sm text-muted-foreground">
          暂无攻击记录
        </div>
      </div>
    </template>
  </TechCard>
</template>

<style scoped>
@keyframes attack-ticker-scroll {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}

@keyframes attack-chip-pop {
  0%, 100% { transform: translateY(0) scale(1); }
  40% { transform: translateY(-2px) scale(1.02); }
  70% { transform: translateY(0) scale(1); }
}

.attack-ticker-track {
  animation: attack-ticker-scroll 28s linear infinite;
}

.attack-chip {
  animation: attack-chip-pop 2.8s ease-in-out infinite;
}

.popup-enter-active,
.popup-leave-active {
  transition: all 0.35s ease;
}

.popup-enter-from,
.popup-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.98);
}
</style>
