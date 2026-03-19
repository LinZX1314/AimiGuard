<script setup lang="ts">
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Activity } from 'lucide-vue-next'

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

function formatThreatLevel(level?: string) {
  if (!level) return '未分级'
  const lower = level.toLowerCase()
  if (level === '高危' || lower === 'high') return '高危'
  if (level === '中危' || lower === 'medium') return '中危'
  if (level === '安全' || lower === 'low') return '安全'
  return level
}
</script>

<template>
  <main class="min-h-0 flex flex-col gap-4 overflow-hidden">
    <Card class="flex-1 min-h-0 overflow-hidden">
      <CardHeader class="pb-2">
        <CardTitle class="text-sm flex items-center gap-2">
          <Activity class="h-4 w-4 text-primary" />
          最近攻击记录
        </CardTitle>
      </CardHeader>
      <CardContent class="h-[calc(100%-48px)] overflow-hidden p-0">
        <ScrollArea class="h-full px-6 pb-6">
          <div v-if="loadError" class="rounded-lg border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {{ loadError }}
          </div>

          <template v-else>
            <div class="space-y-2">
              <div v-for="(item, idx) in recentAttacks" :key="`${item.attack_ip}-${idx}`" class="rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
                <div class="flex items-center justify-between gap-3">
                  <div>
                    <p class="font-mono text-sm text-foreground">{{ item.attack_ip }}</p>
                    <p class="text-xs text-muted-foreground">{{ item.ip_location || '未知地区' }} · {{ item.service_name || '未知服务' }}</p>
                  </div>
                  <Badge variant="outline">{{ formatThreatLevel(item.threat_level) }}</Badge>
                </div>
                <p class="text-xs text-muted-foreground mt-1">{{ item.create_time_str || '-' }}</p>
              </div>
              <div v-if="!recentAttacks.length && !loading" class="text-sm text-muted-foreground text-center py-8">
                暂无攻击记录
              </div>
            </div>
          </template>
        </ScrollArea>
      </CardContent>
    </Card>
  </main>
</template>
