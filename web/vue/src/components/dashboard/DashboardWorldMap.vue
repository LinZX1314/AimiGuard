<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { use } from 'echarts/core'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { MapChart, EffectScatterChart, LinesChart } from 'echarts/charts'
import { GeoComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { feature } from 'topojson-client'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Globe, Activity } from 'lucide-vue-next'

use([CanvasRenderer, MapChart, EffectScatterChart, LinesChart, GeoComponent, TooltipComponent])

interface AttackSource {
  attack_ip: string
  ip_location?: string
  service_name?: string
  threat_level?: string
  create_time_str?: string
}

const props = defineProps<{
  recentAttacks: AttackSource[]
  loading: boolean
  loadError?: string
}>()

const mapReady = ref(false)
const mapLoadFailed = ref(false)
const targetCoord: [number, number] = [104.1954, 35.8617]

const geoMap: Record<string, [number, number]> = {
  中国: [104.1954, 35.8617],
  北京: [116.4074, 39.9042],
  上海: [121.4737, 31.2304],
  广州: [113.2644, 23.1291],
  深圳: [114.0579, 22.5431],
  香港: [114.1694, 22.3193],
  日本: [138.2529, 36.2048],
  韩国: [127.7669, 35.9078],
  新加坡: [103.8198, 1.3521],
  美国: [-95.7129, 37.0902],
  俄罗斯: [105.3188, 61.524],
  德国: [10.4515, 51.1657],
  英国: [-3.436, 55.3781],
  法国: [2.2137, 46.2276],
  巴西: [-51.9253, -14.235],
  印度: [78.9629, 20.5937],
  澳大利亚: [133.7751, -25.2744],
}

function hashToCoord(seed: string): [number, number] {
  let hash = 0
  for (let i = 0; i < seed.length; i += 1) {
    hash = (hash << 5) - hash + seed.charCodeAt(i)
    hash |= 0
  }
  const lng = ((hash % 360) + 360) % 360 - 180
  const lat = ((((hash >> 4) % 140) + 140) % 140) - 70
  return [Number(lng.toFixed(3)), Number(lat.toFixed(3))]
}

function resolveCoord(location: string | undefined, ip: string): [number, number] {
  const text = location || ''
  for (const key of Object.keys(geoMap)) {
    if (text.includes(key)) return geoMap[key]
  }
  return hashToCoord(`${text}-${ip}`)
}

function levelValue(level?: string): number {
  const lower = (level || '').toLowerCase()
  if (lower === 'critical' || lower === 'high' || level === '严重' || level === '高危') return 3
  if (lower === 'medium' || level === '中危') return 2
  return 1
}

const mapPoints = computed(() => {
  return props.recentAttacks.slice(0, 120).map((item) => {
    const [lng, lat] = resolveCoord(item.ip_location, item.attack_ip)
    const severity = levelValue(item.threat_level)
    return {
      name: item.ip_location || '未知地区',
      value: [lng, lat, severity],
      ip: item.attack_ip,
      service: item.service_name || '未知服务',
      level: item.threat_level || '未分级',
      time: item.create_time_str || '-',
    }
  })
})

const mapLines = computed(() => {
  return mapPoints.value.slice(0, 80).map((point) => ({
    fromName: point.name,
    toName: '中国',
    coords: [[point.value[0], point.value[1]], targetCoord],
    value: point.value[2],
  }))
})

const attackTickerItems = computed(() => {
  const rows = props.recentAttacks.slice(0, 12)
  if (!rows.length) return []
  return [...rows, ...rows]
})

const threatSummary = computed(() => {
  let high = 0
  let medium = 0
  let low = 0
  for (const item of props.recentAttacks) {
    const val = levelValue(item.threat_level)
    if (val === 3) high += 1
    else if (val === 2) medium += 1
    else low += 1
  }
  return { high, medium, low }
})

const mapOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: {
    trigger: 'item',
    backgroundColor: 'rgba(15, 23, 42, 0.92)',
    borderColor: 'rgba(34, 211, 238, 0.35)',
    borderWidth: 1,
    textStyle: { color: '#e2e8f0', fontSize: 11 },
    formatter: (params: any) => {
      const data = params?.data
      if (!data) return ''
      return [
        `<div><strong>${data.ip}</strong></div>`,
        `<div>位置：${data.name}</div>`,
        `<div>服务：${data.service}</div>`,
        `<div>等级：${data.level}</div>`,
        `<div>时间：${data.time}</div>`,
      ].join('')
    },
  },
  geo: {
    map: 'world',
    roam: true,
    zoom: 1.22,
    scaleLimit: { min: 1, max: 5 },
    itemStyle: {
      areaColor: 'rgba(8, 16, 31, 0.9)',
      borderColor: 'rgba(56, 189, 248, 0.35)',
      borderWidth: 1,
      shadowBlur: 18,
      shadowColor: 'rgba(14, 116, 144, 0.35)',
    },
    emphasis: {
      itemStyle: {
        areaColor: 'rgba(34, 211, 238, 0.24)',
      },
      label: { show: false },
    },
  },
  series: [
    {
      name: 'attack-lines',
      type: 'lines',
      coordinateSystem: 'geo',
      data: mapLines.value,
      zlevel: 1,
      effect: {
        show: true,
        period: 5,
        trailLength: 0.2,
        symbol: 'arrow',
        symbolSize: 6,
        color: '#67e8f9',
      },
      lineStyle: {
        width: 1.2,
        opacity: 0.45,
        curveness: 0.2,
        color: 'rgba(56, 189, 248, 0.65)',
      },
    },
    {
      name: 'attack-points',
      type: 'effectScatter',
      coordinateSystem: 'geo',
      data: mapPoints.value,
      symbolSize: (val: number[]) => 6 + val[2] * 2,
      showEffectOn: 'render',
      rippleEffect: {
        brushType: 'stroke',
        scale: 3,
      },
      itemStyle: {
        color: (params: any) => {
          const sev = params?.data?.value?.[2] || 1
          if (sev >= 3) return '#fb7185'
          if (sev >= 2) return '#fbbf24'
          return '#34d399'
        },
        shadowBlur: 14,
        shadowColor: 'rgba(56, 189, 248, 0.65)',
      },
      zlevel: 2,
    },
  ],
}))

onMounted(async () => {
  try {
    const topo = await fetch('/countries-110m.json').then((r) => r.json())
    const worldGeoJson = feature(topo as any, (topo as any).objects.countries) as any
    echarts.registerMap('world', worldGeoJson)
    mapReady.value = true
    mapLoadFailed.value = false
  } catch (error) {
    console.error('加载世界地图数据失败', error)
    mapReady.value = false
    mapLoadFailed.value = true
  }
})
</script>

<template>
  <div class="h-full">
    <Card class="h-full overflow-hidden bg-card/40 backdrop-blur-sm border-border/20">
      <CardContent class="h-full p-4">
        <div class="mb-3 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <Globe class="h-4 w-4 text-cyan-400" />
            <h3 class="text-sm font-semibold text-foreground">全球攻击态势</h3>
          </div>
          <div class="flex items-center gap-2">
            <Badge variant="outline" class="border-red-400/30 bg-red-500/10 text-red-300">高危 {{ threatSummary.high }}</Badge>
            <Badge variant="outline" class="border-amber-400/30 bg-amber-500/10 text-amber-300">中危 {{ threatSummary.medium }}</Badge>
            <Badge variant="outline" class="border-emerald-400/30 bg-emerald-500/10 text-emerald-300">低危 {{ threatSummary.low }}</Badge>
          </div>
        </div>

        <div class="h-[calc(100%-34px)] rounded-lg border border-border/30 bg-slate-950/55">
          <div class="h-[calc(100%-76px)] overflow-hidden rounded-t-lg border-b border-cyan-500/10 bg-[radial-gradient(circle_at_50%_0%,rgba(8,145,178,0.18),transparent_45%)]">
            <VChart v-if="mapReady" class="h-full w-full" :option="mapOption" autoresize />
            <div v-else class="flex h-full flex-col items-center justify-center text-muted-foreground">
              <Globe class="mb-2 h-10 w-10 text-cyan-400/70" />
              <p v-if="mapLoadFailed" class="text-sm text-rose-300">地图资源加载失败，请检查 countries-110m.json</p>
              <p v-else class="text-sm">地图资源加载中...</p>
              <p v-if="loadError && !recentAttacks.length" class="mt-2 text-xs text-orange-300/90">{{ loadError }}</p>
            </div>
          </div>

          <div class="relative h-[76px] overflow-hidden bg-gradient-to-r from-slate-950/90 via-slate-900/70 to-slate-950/90">
            <div class="absolute left-3 top-2 flex items-center gap-1 text-[11px] text-cyan-200/90">
              <Activity class="h-3 w-3 animate-pulse" />
              <span>实时攻击轮播</span>
            </div>

            <div class="pointer-events-none absolute inset-y-0 left-0 z-10 w-12 bg-gradient-to-r from-slate-950 to-transparent" />
            <div class="pointer-events-none absolute inset-y-0 right-0 z-10 w-12 bg-gradient-to-l from-slate-950 to-transparent" />

            <div v-if="attackTickerItems.length" class="map-ticker-track flex h-full w-max items-center gap-2 px-2 pt-5">
              <div
                v-for="(item, idx) in attackTickerItems"
                :key="`${item.attack_ip}-${item.create_time_str || ''}-${idx}`"
                class="map-chip flex items-center gap-2 rounded-lg border border-cyan-400/25 bg-cyan-500/10 px-2.5 py-1 text-xs text-cyan-100"
                :style="{ animationDelay: `${(idx % 10) * 0.1}s` }"
              >
                <span class="h-1.5 w-1.5 rounded-full bg-cyan-300" />
                <span class="font-mono">{{ item.attack_ip }}</span>
                <span class="opacity-85">{{ item.ip_location || '未知地区' }}</span>
                <span class="opacity-75">{{ item.service_name || '未知服务' }}</span>
              </div>
            </div>

            <div v-else-if="!loading" class="flex h-full items-center justify-center text-sm text-muted-foreground">
              暂无攻击记录
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  </div>
</template>

<style scoped>
@keyframes map-ticker-scroll {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}

@keyframes map-chip-pop {
  0%, 100% { transform: translateY(0) scale(1); }
  40% { transform: translateY(-1px) scale(1.02); }
  70% { transform: translateY(0) scale(1); }
}

.map-ticker-track {
  animation: map-ticker-scroll 26s linear infinite;
}

.map-chip {
  animation: map-chip-pop 2.8s ease-in-out infinite;
}
</style>
