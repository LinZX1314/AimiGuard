<script setup lang="ts">
import { computed } from 'vue'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Shield, Ban, Clock3, CheckCircle2, ShieldAlert } from 'lucide-vue-next'
import TechCard from './shared/TechCard.vue'

const props = defineProps<{
  defenseEvents: Array<{
    attack_ip: string
    ip_location?: string
    attack_count: number
    latest_time?: string
    ai_status?: string
    ai_decision?: string
  }>
  loading: boolean
}>()

const queueSummary = computed(() => {
  let block = 0
  let pending = 0
  let safe = 0

  for (const item of props.defenseEvents) {
    if (item.ai_decision === 'true') {
      block += 1
    } else if (item.ai_decision === 'pending') {
      pending += 1
    } else {
      safe += 1
    }
  }

  return { block, pending, safe }
})

function getDecisionIcon(decision?: string) {
  if (decision === 'true') return Ban
  if (decision === 'pending') return Clock3
  return CheckCircle2
}

function getDecisionColor(decision?: string) {
  if (decision === 'true') return 'text-rose-300 border-rose-400/35 bg-rose-500/15'
  if (decision === 'pending') return 'text-amber-300 border-amber-400/35 bg-amber-500/15'
  return 'text-emerald-300 border-emerald-400/35 bg-emerald-500/15'
}

function getDecisionText(decision?: string) {
  if (decision === 'true') return '建议封禁'
  if (decision === 'pending') return '分析中'
  return '安全'
}
</script>

<template>
    <TechCard title="防御处置队列" :icon="Shield" glow-color="green" class="tech-card-dashboard-clear">
    <div class="mb-3 grid grid-cols-3 gap-2">
      <div class="rounded-lg border border-red-500/30 bg-red-500/8 px-2 py-1.5 text-center dark:border-red-400/25 dark:bg-red-500/10">
        <p class="text-[10px] text-red-600 dark:text-red-300">建议封禁</p>
        <p class="text-sm font-semibold text-red-600 dark:text-red-300 tabular-nums">{{ queueSummary.block }}</p>
      </div>
      <div class="rounded-lg border border-amber-500/30 bg-amber-500/8 px-2 py-1.5 text-center dark:border-amber-400/25 dark:bg-amber-500/10">
        <p class="text-[10px] text-amber-600 dark:text-amber-300">分析中</p>
        <p class="text-sm font-semibold text-amber-600 dark:text-amber-300 tabular-nums">{{ queueSummary.pending }}</p>
      </div>
  <div class="rounded-lg border border-emerald-500/30 bg-emerald-500/8 px-2 py-1.5 text-center border-emerald-400/25 bg-emerald-500/10">
        <p class="text-[10px] text-emerald-600 dark:text-emerald-300">已放行</p>
        <p class="text-sm font-semibold text-emerald-600 dark:text-emerald-300 tabular-nums">{{ queueSummary.safe }}</p>
      </div>
    </div>

    <ScrollArea class="h-[calc(100%-88px)]">
      <div class="space-y-2 pr-2">
        <div
          v-for="item in defenseEvents"
          :key="item.attack_ip"
          class="group rounded-lg border border-border/45 bg-secondary/30 px-3 py-2.5 transition-all duration-300 hover:border-primary/35 hover:shadow-[0_0_14px_hsl(var(--primary)/0.08)] dark:bg-muted/20"
        >
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2 min-w-0">
              <component :is="getDecisionIcon(item.ai_decision)" class="h-3.5 w-3.5 shrink-0" :class="getDecisionColor(item.ai_decision).split(' ')[0]" />
              <p class="font-mono text-sm tracking-wide truncate">{{ item.attack_ip }}</p>
            </div>
  <Badge variant="outline" class="text-xs shrink-0 border-primary/30 bg-primary/8 text-primary">{{ item.attack_count }} 次</Badge>
          </div>
          <p class="mt-1 pl-6 text-[11px] text-muted-foreground/80">{{ item.ip_location || '未知地区' }} · {{ item.latest_time || '-' }}</p>
          <div class="mt-2 pl-6">
            <Badge
              variant="outline"
              class="text-xs"
              :class="getDecisionColor(item.ai_decision)"
            >
              AI 判定: {{ getDecisionText(item.ai_decision) }}
            </Badge>
          </div>
        </div>
        <div v-if="!defenseEvents.length && !loading" class="py-8 text-center text-sm text-muted-foreground">
  <div class="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-full border border-emerald-500/30 bg-emerald-500/8 border-emerald-400/25 bg-emerald-500/10">
    <ShieldAlert class="h-4 w-4 text-emerald-600 text-emerald-300" />
          </div>
          暂无待处置事件
        </div>
      </div>
    </ScrollArea>
</TechCard>
</template>
