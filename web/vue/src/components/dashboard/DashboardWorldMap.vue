<script setup lang="ts">
import type { FeatureCollection, Geometry } from 'geojson'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { geoMercator, geoPath, geoCentroid } from 'd3-geo'
import { feature } from 'topojson-client'

import { createInitialWorldView, nextAnimatedView } from '@/lib/worldMapState'
import worldTopology from '../../../public/countries-110m.json'

interface AttackSource {
  id: string
  ip: string
  country: string
  countryCode: string
  city: string
  attacks: number
  lastSeen: string
  threatLevel: 'low' | 'medium' | 'high' | 'critical'
  attackTypes: string[]
  latitude: number
  longitude: number
}

interface AttackLine {
  id: string
  source: [number, number]
  target: [number, number]
  sourceCountry: string
  attackType: string
  timestamp: string
}

interface WorldFeature {
  id?: string | number
  properties: {
    name?: string
  }
  geometry: Geometry
}

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

const mapShellRef = ref<HTMLElement>()
const mapReady = ref(false)

const COUNTRY_TRANSLATIONS: Record<string, string> = {
  China: '中国',
  'United States': '美国',
  'United States of America': '美国',
  Russia: '俄罗斯',
  'Russian Federation': '俄罗斯',
  Japan: '日本',
  'South Korea': '韩国',
  India: '印度',
  'United Kingdom': '英国',
  Germany: '德国',
  France: '法国',
  Brazil: '巴西',
  Canada: '加拿大',
  Australia: '澳大利亚',
  Italy: '意大利',
  Spain: '西班牙',
  Mexico: '墨西哥',
  Indonesia: '印度尼西亚',
  'Saudi Arabia': '沙特阿拉伯',
  Turkey: '土耳其',
  Iran: '伊朗',
  'South Africa': '南非',
  Egypt: '埃及',
  Vietnam: '越南',
  Thailand: '泰国',
  Malaysia: '马来西亚',
  Singapore: '新加坡',
  Philippines: '菲律宾',
  Pakistan: '巴基斯坦',
  Bangladesh: '孟加拉国',
  Nigeria: '尼日利亚',
  Argentina: '阿根廷',
  Colombia: '哥伦比亚',
  Chile: '智利',
  Peru: '秘鲁',
  Ukraine: '乌克兰',
  Poland: '波兰',
  Netherlands: '荷兰',
  Belgium: '比利时',
  Sweden: '瑞典',
  Switzerland: '瑞士',
  Austria: '奥地利',
  Norway: '挪威',
  Denmark: '丹麦',
  Finland: '芬兰',
  Greece: '希腊',
  Portugal: '葡萄牙',
  Ireland: '爱尔兰',
  'New Zealand': '新西兰',
  Israel: '以色列',
}

const TARGET_COORDS: [number, number] = [116.4074, 39.9042]
const worldView = { width: 960, height: 540 }

const attackSources = ref<AttackSource[]>([
  { id: '1', ip: '185.220.101.45', country: '俄罗斯', countryCode: 'RU', city: '莫斯科', attacks: 2847, lastSeen: '2分钟前', threatLevel: 'critical', attackTypes: ['SSH暴力破解', 'DDoS'], latitude: 55.7558, longitude: 37.6173 },
  { id: '2', ip: '45.227.255.98', country: '巴西', countryCode: 'BR', city: '圣保罗', attacks: 1892, lastSeen: '5分钟前', threatLevel: 'high', attackTypes: ['SQL注入', '端口扫描'], latitude: -23.5505, longitude: -46.6333 },
  { id: '3', ip: '103.152.118.24', country: '中国', countryCode: 'CN', city: '北京', attacks: 1456, lastSeen: '1分钟前', threatLevel: 'high', attackTypes: ['XSS攻击', 'Web扫描'], latitude: 39.9042, longitude: 116.4074 },
  { id: '4', ip: '91.134.203.156', country: '法国', countryCode: 'FR', city: '巴黎', attacks: 1234, lastSeen: '8分钟前', threatLevel: 'medium', attackTypes: ['目录遍历', 'CSRF'], latitude: 48.8566, longitude: 2.3522 },
  { id: '5', ip: '198.51.100.78', country: '美国', countryCode: 'US', city: '纽约', attacks: 987, lastSeen: '3分钟前', threatLevel: 'medium', attackTypes: ['API滥用', '爬虫'], latitude: 40.7128, longitude: -74.006 },
  { id: '6', ip: '203.0.113.41', country: '印度', countryCode: 'IN', city: '孟买', attacks: 761, lastSeen: '9分钟前', threatLevel: 'medium', attackTypes: ['端口扫描'], latitude: 19.076, longitude: 72.8777 },
])

const attackLines = ref<AttackLine[]>([
  { id: 'line1', source: [37.6173, 55.7558], target: TARGET_COORDS, sourceCountry: '俄罗斯', attackType: 'SSH暴力破解', timestamp: '2分钟前' },
  { id: 'line2', source: [-46.6333, -23.5505], target: TARGET_COORDS, sourceCountry: '巴西', attackType: 'SQL注入', timestamp: '5分钟前' },
  { id: 'line3', source: [-74.006, 40.7128], target: TARGET_COORDS, sourceCountry: '美国', attackType: 'DDoS', timestamp: '1分钟前' },
  { id: 'line4', source: [2.3522, 48.8566], target: TARGET_COORDS, sourceCountry: '法国', attackType: '目录遍历', timestamp: '8分钟前' },
])

const geoHover = ref<{ x: number; y: number; name: string } | null>(null)
const tooltipInfo = ref<{ x: number; y: number; data: AttackSource } | null>(null)
const targetView = ref(createInitialWorldView())
const currentView = ref(createInitialWorldView())

let viewFrame = 0
let viewStartTime = 0
let mapLoaderTimer = 0

const worldFeatures = computed<WorldFeature[]>(() => {
  const countriesObject = (worldTopology as any).objects.countries
  const collection = feature(worldTopology as any, countriesObject) as unknown as FeatureCollection
  return collection.features as WorldFeature[]
})

const projection = computed(() =>
  geoMercator()
    .scale(152 * currentView.value.zoom)
    .translate([worldView.width / 2, worldView.height / 2])
    .center(currentView.value.coordinates),
)

const pathGenerator = computed(() => geoPath(projection.value))
const projectedTarget = computed(() => projection.value(TARGET_COORDS) ?? [worldView.width / 2, worldView.height / 2])

const renderedCountries = computed(() =>
  worldFeatures.value.map((item) => ({
    ...item,
    svgPath: pathGenerator.value(item as any) ?? '',
  })),
)

const renderedSources = computed(() =>
  attackSources.value
    .map((source) => {
      const point = projection.value([source.longitude, source.latitude])
      if (!point) return null
      return {
        ...source,
        x: point[0],
        y: point[1],
        color:
          source.threatLevel === 'critical'
            ? '#ff4444'
            : source.threatLevel === 'high'
              ? '#ff7f24'
              : source.threatLevel === 'medium'
                ? '#ffd700'
                : '#00ff88',
      }
    })
    .filter(Boolean) as Array<AttackSource & { x: number; y: number; color: string }>,
)

const renderedMainLine = computed(() => {
  const mainLine = attackLines.value[0]
  if (!mainLine) return null
  const source = projection.value(mainLine.source)
  const target = projection.value(mainLine.target)
  if (!source || !target) return null
  return {
    ...mainLine,
    d: `M ${source[0]} ${source[1]} Q ${(source[0] + target[0]) / 2} ${Math.min(source[1], target[1]) - 70} ${target[0]} ${target[1]}`,
  }
})

const animateView = () => {
  cancelAnimationFrame(viewFrame)
  viewStartTime = performance.now()

  const startView = { ...currentView.value }
  const target = { ...targetView.value }

  const step = (time: number) => {
    const progress = Math.min(1, (time - viewStartTime) / 1000)
    currentView.value = nextAnimatedView(startView, target, progress)
    if (progress < 1) {
      viewFrame = requestAnimationFrame(step)
    }
  }

  viewFrame = requestAnimationFrame(step)
}

const handleGeographyClick = (featureItem: WorldFeature) => {
  const centroid = geoCentroid(featureItem as any) as [number, number]
  if (!Number.isFinite(centroid[0]) || !Number.isFinite(centroid[1])) return
  targetView.value = { coordinates: centroid, zoom: 2.2 }
  animateView()
}

const handleOceanClick = () => {
  targetView.value = createInitialWorldView()
  animateView()
}

const handleSourceEnter = (event: MouseEvent, source: AttackSource) => {
  const rect = mapShellRef.value?.getBoundingClientRect()
  if (!rect) return
  const x = Math.min(Math.max(12, event.clientX - rect.left + 10), rect.width - 250)
  const y = Math.min(Math.max(12, event.clientY - rect.top + 8), rect.height - 140)
  tooltipInfo.value = { x, y, data: source }
}

const handleGeoEnter = (event: MouseEvent, name?: string) => {
  if (!name) return
  const rect = mapShellRef.value?.getBoundingClientRect()
  if (!rect) return
  const x = Math.min(Math.max(12, event.clientX - rect.left + 10), rect.width - 130)
  const y = Math.min(Math.max(12, event.clientY - rect.top + 8), rect.height - 70)
  geoHover.value = { x, y, name }
}

onMounted(() => {
  mapLoaderTimer = window.setTimeout(() => {
    mapReady.value = true
  }, 900)

  if (props.recentAttacks.length > 0) {
    const first = props.recentAttacks[0]
    const ipSeed = first.attack_ip.split('.').reduce((sum, seg) => sum + Number(seg || 0), 0)
    const lon = ((ipSeed * 37) % 360) - 180
    const lat = (((ipSeed * 23) % 140) - 70)
    attackLines.value = [{
      id: 'line-main',
      source: [Number(lon.toFixed(3)), Number(lat.toFixed(3))],
      target: TARGET_COORDS,
      sourceCountry: first.ip_location || '未知区域',
      attackType: first.service_name || '异常流量',
      timestamp: first.create_time_str || '刚刚',
    }]
  }
})

watch(
  () => props.loading,
  (isLoading) => {
    if (mapLoaderTimer) {
      window.clearTimeout(mapLoaderTimer)
    }
    if (isLoading) {
      mapReady.value = false
      return
    }
    mapLoaderTimer = window.setTimeout(() => {
      mapReady.value = true
    }, 700)
  },
)

onBeforeUnmount(() => {
  cancelAnimationFrame(viewFrame)
  if (mapLoaderTimer) {
    window.clearTimeout(mapLoaderTimer)
  }
})
</script>

<template>
  <div ref="mapShellRef" class="world-map-shell" @mouseleave="geoHover = null">
    <Transition name="map-loader-fade">
      <div v-if="loading || !mapReady" class="world-map-shell__loading" aria-label="地图载入动画">
        <div class="world-map-shell__loading-core">
          <span class="world-map-shell__loading-ring ring-1"></span>
          <span class="world-map-shell__loading-ring ring-2"></span>
          <span class="world-map-shell__loading-ring ring-3"></span>
          <span class="world-map-shell__loading-dot"></span>
        </div>
        <div class="world-map-shell__loading-text">正在构建全球威胁态势图...</div>
      </div>
    </Transition>

    <div class="world-map-shell__toolbar">
      <span v-if="loadError && !recentAttacks.length" class="world-map-shell__error">{{ loadError }}</span>
    </div>

    <svg v-show="mapReady" class="world-map-shell__svg" viewBox="0 0 960 540" role="img" aria-label="全球攻击地图" @click="handleOceanClick">
      <defs>
        <linearGradient id="worldMapCountryGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="rgba(0, 212, 255, 0.16)" />
          <stop offset="100%" stop-color="rgba(0, 255, 136, 0.06)" />
        </linearGradient>
        <radialGradient id="worldMapTargetGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#00d4ff" stop-opacity="0.45" />
          <stop offset="100%" stop-color="#00d4ff" stop-opacity="0" />
        </radialGradient>
      </defs>

      <path
        v-for="country in renderedCountries"
        :key="country.id ?? country.properties.name"
        :d="country.svgPath"
        class="world-map-shell__country"
        fill="url(#worldMapCountryGradient)"
        @click.stop="handleGeographyClick(country)"
        @mouseenter="handleGeoEnter($event, country.properties.name)"
        @mousemove="handleGeoEnter($event, country.properties.name)"
        @mouseleave="geoHover = null"
      />

      <path v-if="renderedMainLine" :d="renderedMainLine.d" stroke="#ff3b30" class="world-map-shell__line" />

      <g
        v-for="source in renderedSources"
        :key="source.id"
        class="world-map-shell__marker"
        @mouseenter="handleSourceEnter($event, source)"
        @mousemove="handleSourceEnter($event, source)"
        @mouseleave="tooltipInfo = null"
      >
        <circle :cx="source.x" :cy="source.y" r="7" fill="none" :stroke="source.color" opacity="0.52" />
        <circle :cx="source.x" :cy="source.y" r="4" :fill="source.color" />
      </g>

      <g>
        <circle :cx="projectedTarget[0]" :cy="projectedTarget[1]" r="18" fill="url(#worldMapTargetGlow)" />
        <circle :cx="projectedTarget[0]" :cy="projectedTarget[1]" r="3" fill="#00d4ff" />
        <text :x="projectedTarget[0]" :y="projectedTarget[1] + 24" text-anchor="middle" class="world-map-shell__target-label">TARGET</text>
      </g>
    </svg>

    <div class="world-map-shell__legend">
      <span><i style="background:#ff4444"></i>严重</span>
      <span><i style="background:#ff7f24"></i>高危</span>
      <span><i style="background:#ffd700"></i>中危</span>
      <span><i style="background:#00d4ff"></i>目标</span>
    </div>

    <div class="world-map-shell__status"><span class="status-indicator status-indicator--online"></span><span>{{ loading ? '载入中' : '实时监控' }}</span></div>

    <div v-if="geoHover" class="world-map-shell__geo-hover" :style="{ left: `${geoHover.x}px`, top: `${geoHover.y}px` }">
      <span>国家地区</span>
      <strong>{{ COUNTRY_TRANSLATIONS[geoHover.name] || geoHover.name }}</strong>
    </div>

    <div v-if="tooltipInfo" class="world-map-shell__source-hover" :style="{ left: `${tooltipInfo.x}px`, top: `${tooltipInfo.y}px` }">
      <div class="world-map-shell__source-head">
        <strong>攻击源侦测</strong>
        <span>{{ tooltipInfo.data.threatLevel.toUpperCase() }}</span>
      </div>
      <div class="world-map-shell__source-grid">
        <span>追踪定位:</span><span>{{ tooltipInfo.data.country }} ({{ tooltipInfo.data.countryCode }})</span>
        <span>公网IP:</span><span>{{ tooltipInfo.data.ip }}</span>
        <span>拦截频次:</span><span>{{ tooltipInfo.data.attacks.toLocaleString() }} 次</span>
        <span>最后活动:</span><span>{{ tooltipInfo.data.lastSeen }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.world-map-shell {
  position: relative;
  height: 100%;
  border-radius: 12px;
  border: 1px solid hsl(var(--border) / 0.48);
  background: radial-gradient(circle at 20% 15%, rgb(14 116 144 / 0.18), transparent 45%),
    linear-gradient(160deg, hsl(var(--card) / 0.75), hsl(var(--card) / 0.5));
  overflow: hidden;
}

:global(html.dark) .world-map-shell {
  background: radial-gradient(circle at 20% 15%, rgb(6 182 212 / 0.22), transparent 45%),
    linear-gradient(160deg, rgb(7 18 34 / 0.96), rgb(2 10 23 / 0.86));
}

.world-map-shell__toolbar {
  position: absolute;
  top: 6px;
  left: 10px;
  right: 10px;
  z-index: 6;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.world-map-shell__button {
  border: 1px solid hsl(var(--border) / 0.7);
  background: hsl(var(--background) / 0.66);
  color: hsl(var(--foreground));
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 999px;
}

:global(html.dark) .world-map-shell__button {
  background: rgb(2 132 199 / 0.2);
  border-color: rgb(6 182 212 / 0.3);
  color: rgb(165 243 252);
}

.world-map-shell__error {
  font-size: 11px;
  color: rgb(251 113 133);
}

.world-map-shell__svg {
  width: 100%;
  height: calc(100% - 4px);
}

.world-map-shell__country {
  stroke: rgb(8 145 178 / 0.45);
  stroke-width: 0.8;
  transition: fill 0.2s ease;
  cursor: pointer;
}

.world-map-shell__country:hover {
  fill: rgb(34 211 238 / 0.28);
}

.world-map-shell__line {
  fill: none;
  stroke-width: 2.2;
  opacity: 0.88;
  stroke-linecap: round;
  filter: drop-shadow(0 0 8px rgb(255 59 48 / 0.45));
}

.world-map-shell__target-label {
  font-size: 10px;
  fill: rgb(34 211 238 / 0.9);
  letter-spacing: 1px;
}

.world-map-shell__legend {
  position: absolute;
  left: 12px;
  bottom: 10px;
  display: flex;
  gap: 10px;
  font-size: 11px;
  color: hsl(var(--foreground) / 0.85);
}

.world-map-shell__legend i {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  display: inline-block;
  margin-right: 5px;
}

.world-map-shell__status {
  position: absolute;
  right: 12px;
  bottom: 10px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: hsl(var(--foreground) / 0.82);
  background: hsl(var(--card) / 0.7);
  border: 1px solid hsl(var(--border) / 0.5);
  border-radius: 999px;
  padding: 3px 9px;
}


:global(html.dark) .world-map-shell__status {
  color: rgb(186 230 253);
  background: rgb(15 23 42 / 0.65);
  border-color: rgb(56 189 248 / 0.28);
}

.status-indicator {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  display: inline-block;
}

.status-indicator--online {
  background: rgb(34 197 94);
  box-shadow: 0 0 8px rgb(34 197 94 / 0.8);
}

.world-map-shell__geo-hover,
.world-map-shell__source-hover {
  position: absolute;
  z-index: 80;
  pointer-events: none;
  background: rgb(10 26 47 / 0.96);
  border: 1px solid rgb(34 211 238 / 0.35);
  border-radius: 10px;
  color: rgb(224 242 254);
  font-size: 11px;
  box-shadow: 0 14px 36px rgb(2 6 23 / 0.45);
}

.world-map-shell__geo-hover {
  display: inline-flex;
  flex-direction: column;
  gap: 2px;
  min-width: 92px;
  padding: 7px 10px;
}

.world-map-shell__geo-hover span {
  font-size: 10px;
  letter-spacing: 0.5px;
  color: rgb(125 211 252 / 0.85);
  text-transform: uppercase;
}

.world-map-shell__geo-hover strong {
  font-size: 14px;
  line-height: 1.1;
  color: rgb(103 232 249);
  text-shadow: 0 0 16px rgb(34 211 238 / 0.45);
}

.world-map-shell__source-hover {
  min-width: 230px;
  padding: 9px 10px;
}

.world-map-shell__source-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  font-size: 10px;
  letter-spacing: 0.4px;
  text-transform: uppercase;
  color: rgb(34 211 238);
}

.world-map-shell__source-grid {
  display: grid;
  grid-template-columns: 70px 1fr;
  row-gap: 4px;
  column-gap: 8px;
}

.world-map-shell__source-grid span:nth-child(odd) {
  color: rgb(125 211 252 / 0.85);
}

.world-map-shell__loading {
  position: absolute;
  inset: 0;
  z-index: 12;
  display: grid;
  place-items: center;
  background:
    radial-gradient(circle at 50% 38%, rgb(6 182 212 / 0.12), transparent 42%),
    linear-gradient(160deg, rgb(2 6 23 / 0.9), rgb(8 47 73 / 0.72));
  backdrop-filter: blur(3px);
}

.world-map-shell__loading-core {
  position: relative;
  width: 132px;
  height: 132px;
  display: grid;
  place-items: center;
}

.world-map-shell__loading-ring {
  position: absolute;
  border-radius: 999px;
  border: 1px solid rgb(34 211 238 / 0.3);
}

.world-map-shell__loading-ring.ring-1 {
  width: 60px;
  height: 60px;
  border-top-color: rgb(34 211 238 / 0.9);
  animation: map-spin 1.5s linear infinite;
}

.world-map-shell__loading-ring.ring-2 {
  width: 92px;
  height: 92px;
  border-right-color: rgb(125 211 252 / 0.8);
  animation: map-spin-reverse 2.1s linear infinite;
}

.world-map-shell__loading-ring.ring-3 {
  width: 124px;
  height: 124px;
  border-bottom-color: rgb(103 232 249 / 0.7);
  animation: map-breathe 1.9s ease-in-out infinite;
}

.world-map-shell__loading-dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  background: rgb(34 211 238);
  box-shadow: 0 0 24px rgb(34 211 238 / 0.8);
  animation: map-dot-pulse 1s ease-in-out infinite;
}

.world-map-shell__loading-text {
  margin-top: 10px;
  font-size: 12px;
  letter-spacing: 0.08em;
  color: rgb(165 243 252 / 0.95);
}

.map-loader-fade-enter-active,
.map-loader-fade-leave-active {
  transition: opacity 0.4s ease;
}

.map-loader-fade-enter-from,
.map-loader-fade-leave-to {
  opacity: 0;
}

@keyframes map-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes map-spin-reverse {
  to {
    transform: rotate(-360deg);
  }
}

@keyframes map-breathe {
  0%,
  100% {
    transform: scale(0.97);
    opacity: 0.6;
  }
  50% {
    transform: scale(1.03);
    opacity: 1;
  }
}

@keyframes map-dot-pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 0.85;
  }
  50% {
    transform: scale(1.22);
    opacity: 1;
  }
}

@media (max-width: 1024px) {
  .world-map-shell__legend {
    flex-wrap: wrap;
    row-gap: 5px;
    max-width: 72%;
  }
}
</style>
