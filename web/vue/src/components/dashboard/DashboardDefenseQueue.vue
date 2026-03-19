<script setup lang="ts">
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'

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
</script>

<template>
  <Card>
    <CardHeader class="pb-2">
      <CardTitle class="text-sm">防御处置队列</CardTitle>
    </CardHeader>
    <CardContent class="p-0">
      <ScrollArea class="h-56 px-6 py-3">
        <div class="space-y-2">
          <div v-for="item in defenseEvents" :key="item.attack_ip" class="rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
            <div class="flex items-center justify-between">
              <p class="font-mono text-sm">{{ item.attack_ip }}</p>
              <Badge variant="outline">{{ item.attack_count }} 次</Badge>
            </div>
            <p class="text-xs text-muted-foreground mt-1">{{ item.ip_location || '未知地区' }} · {{ item.latest_time || '-' }}</p>
            <p class="text-xs mt-1" :class="item.ai_decision === 'true' ? 'text-red-400' : 'text-muted-foreground'">
              AI 决策: {{ item.ai_decision === 'true' ? '建议封禁' : '待分析' }}
            </p>
          </div>
          <div v-if="!defenseEvents.length && !loading" class="text-sm text-muted-foreground">
            暂无待处置事件
          </div>
        </div>
      </ScrollArea>
    </CardContent>
  </Card>
</template>
