<script lang="ts">
let hasWorldMapLoadedOnce = false

function getComputedHue(): number {
  const isDark = document.documentElement.classList.contains('dark')
  return isDark ? 180 : 215 // Use 180 (Cyan) for dark mode
}
</script>
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
  attacks: number
  lastSeen: string
  threatLevel: 'low' | 'medium' | 'high' | 'critical'
  latitude: number
  longitude: number
}

interface AttackLine {
  id: string
  source: [number, number]
  target: [number, number]
  color: string
  opacity: number
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
const mapReady = ref(hasWorldMapLoadedOnce)

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
  { id: '1', ip: '185.220.101.45', country: '俄罗斯', countryCode: 'RU', attacks: 2847, lastSeen: '2分钟前', threatLevel: 'critical', latitude: 55.7558, longitude: 37.6173 },
  { id: '2', ip: '45.227.255.98', country: '巴西', countryCode: 'BR', attacks: 1892, lastSeen: '5分钟前', threatLevel: 'high', latitude: -23.5505, longitude: -46.6333 },
  { id: '3', ip: '198.51.100.78', country: '美国', countryCode: 'US', attacks: 987, lastSeen: '3分钟前', threatLevel: 'medium', latitude: 40.7128, longitude: -74.006 },
])

const activeLines = ref<AttackLine[]>([])
const geoHover = ref<{ x: number; y: number; name: string } | null>(null)
const tooltipInfo = ref<{ x: number; y: number; data: AttackSource } | null>(null)
const targetView = ref(createInitialWorldView())
const currentView = ref(createInitialWorldView())

// --- 拖拽交互状态 ---
const isDragging = ref(false)
const lastMousePos = ref({ x: 0, y: 0 })

let viewFrame = 0
let viewStartTime = 0
let mapLoaderTimer = 0
let attackAnimationTimer = 0

const threatColor = computed(() => {
  return '#00d4ff';
});

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

// --- 拖拽逻辑 ---
const handleMouseDown = (e: MouseEvent) => {
  if (e.button !== 0) return
  isDragging.value = true
  lastMousePos.value = { x: e.clientX, y: e.clientY }
}

const handleMouseMove = (e: MouseEvent) => {
  if (!isDragging.value) return
  
  const dx = e.clientX - lastMousePos.value.x
  const dy = e.clientY - lastMousePos.value.y
  
  // 按照缩放级别动态调整灵敏度
  const sensitivity = 0.5 / currentView.value.zoom
  const newLon = currentView.value.coordinates[0] - dx * sensitivity
  const newLat = currentView.value.coordinates[1] + dy * sensitivity
  
  // 限制纬度防止溢出
  const clampedLat = Math.max(-85, Math.min(85, newLat))
  
  currentView.value = {
    ...currentView.value,
    coordinates: [newLon, clampedLat]
  }
  targetView.value = { ...currentView.value } // 同步目标视图
  
  lastMousePos.value = { x: e.clientX, y: e.clientY }
}

const handleMouseUp = () => {
  isDragging.value = false
}

const handleWheel = (e: WheelEvent) => {
  e.preventDefault()
  const direction = e.deltaY > 0 ? 0.9 : 1.1
  const newZoom = Math.max(1, Math.min(10, targetView.value.zoom * direction))
  targetView.value = { ...targetView.value, zoom: newZoom }
}

const animateView = () => {
  if (isDragging.value) return // 拖拽时不进行平滑补间，保证灵敏度

  cancelAnimationFrame(viewFrame)
  viewStartTime = performance.now()

  const startView = { ...currentView.value }
  const target = { ...targetView.value }

  // 如果距离太近就不补间了
  const dist = Math.abs(startView.zoom - target.zoom) + 
               Math.abs(startView.coordinates[0] - target.coordinates[0]) + 
               Math.abs(startView.coordinates[1] - target.coordinates[1])
  if (dist < 0.01) return

  const step = (time: number) => {
    const progress = Math.min(1, (time - viewStartTime) / 400) // 加快补间速度
    currentView.value = nextAnimatedView(startView, target, progress)
    if (progress < 1 && !isDragging.value) {
      viewFrame = requestAnimationFrame(step)
    }
  }

  viewFrame = requestAnimationFrame(step)
}

const handleGeographyClick = (featureItem: WorldFeature) => {
  const centroid = geoCentroid(featureItem as any) as [number, number]
  if (!Number.isFinite(centroid[0]) || !Number.isFinite(centroid[1])) return
  targetView.value = { coordinates: centroid, zoom: 2.2 }
}

const triggerAttack = () => {
  if (attackSources.value.length === 0) return
  const source = attackSources.value[Math.floor(Math.random() * attackSources.value.length)]
  const newLine: AttackLine = {
    id: Math.random().toString(36).substr(2, 9),
    source: [source.longitude, source.latitude],
    target: TARGET_COORDS,
    color:
      source.threatLevel === 'critical'
        ? '#ff4444'
        : source.threatLevel === 'high'
          ? '#ff7f24'
          : source.threatLevel === 'medium'
            ? '#ffd700'
            : '#00ff88',
    opacity: 1,
  }
  activeLines.value.push(newLine)
  if (activeLines.value.length > 8) activeLines.value.shift()
}

const handleSourceEnter = (event: MouseEvent | PointerEvent, source: AttackSource) => {
  tooltipInfo.value = {
    x: event.clientX,
    y: event.clientY,
    data: source,
  }
}

const resetView = () => {
  targetView.value = createInitialWorldView()
}

const zoomIn = () => {
  targetView.value = { ...targetView.value, zoom: Math.min(10, targetView.value.zoom * 1.5) }
}

const zoomOut = () => {
  targetView.value = { ...targetView.value, zoom: Math.max(1, targetView.value.zoom / 1.5) }
}

onMounted(() => {
  if (!hasWorldMapLoadedOnce) {
    mapLoaderTimer = window.setTimeout(() => {
      mapReady.value = true
      hasWorldMapLoadedOnce = true
    }, 1200)
  }
  attackAnimationTimer = window.setInterval(triggerAttack, 3000)
})

onBeforeUnmount(() => {
  clearTimeout(mapLoaderTimer)
  clearInterval(attackAnimationTimer)
  cancelAnimationFrame(viewFrame)
})

watch(targetView, animateView, { deep: true })
</script>

<template>
  <div ref="mapShellRef" class="world-map-shell" aria-label="全球威胁实时观测站">
    <div v-if="!mapReady" class="world-map-shell__loader">
      <div class="world-map-shell__loader-spinner"></div>
      <p class="world-map-shell__loader-text">正在校准全球地理坐标系...</p>
    </div>

    <div v-else class="world-map-shell__content">
      <div class="world-map-shell__toolbar">
        <button class="world-map-shell__toolbar-btn" title="放大" @click="zoomIn">+</button>
        <button class="world-map-shell__toolbar-btn" title="缩小" @click="zoomOut">-</button>
        <button class="world-map-shell__toolbar-btn" title="重置" @click="resetView">⟲</button>
      </div>

      <div class="world-map-shell__legend">
        <div class="world-map-shell__legend-item">
          <span class="world-map-shell__legend-dot" style="background: #ff4444"></span>
          <span>高危威胁</span>
        </div>
        <div class="world-map-shell__legend-item">
          <span class="world-map-shell__legend-dot" style="background: #ffd700"></span>
          <span>异常流量</span>
        </div>
        <div class="world-map-shell__legend-item">
          <span class="world-map-shell__legend-dot" style="background: #00ff88"></span>
          <span>正常同步</span>
        </div>
      </div>

      <svg 
        :viewBox="`0 0 ${worldView.width} ${worldView.height}`" 
        class="world-map-shell__svg"
        :class="{ 'world-map-shell__svg--dragging': isDragging }"
        @mousedown="handleMouseDown"
        @mousemove="handleMouseMove"
        @mouseup="handleMouseUp"
        @mouseleave="handleMouseUp"
        @wheel="handleWheel"
        style="shape-rendering: geometricPrecision;"
      >
        <defs>
          <linearGradient id="worldMapLineGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#ff4444" stop-opacity="0.2" />
            <stop offset="100%" stop-color="#00d4ff" stop-opacity="1" />
          </linearGradient>

          <!-- 科技感背景网格定义 -->
          <pattern id="world-grid" width="30" height="30" patternUnits="userSpaceOnUse">
            <path d="M 30 0 L 0 0 0 30" fill="none" stroke="rgba(0, 212, 255, 0.05)" stroke-width="0.5" />
          </pattern>
        </defs>

        <!-- 背景网格层 -->
        <rect width="100%" height="100%" fill="url(#world-grid)" />

        <g class="world-map-shell__countries">
          <path
            v-for="country in renderedCountries"
            :key="country.id || country.properties.name"
            :d="country.svgPath"
            class="world-map-shell__country"
            :class="{ 'world-map-shell__country--active': geoHover?.name === country.properties.name }"
            @mouseenter="geoHover = { x: 0, y: 0, name: country.properties.name || '' }"
            @mouseleave="geoHover = null"
            @click.stop="handleGeographyClick(country)"
          >
            <title>{{ COUNTRY_TRANSLATIONS[country.properties.name || ''] || country.properties.name }}</title>
          </path>
        </g>

        <g v-for="line in activeLines" :key="line.id">
          <path
            :d="`M ${projection(line.source)?.[0] || 0} ${projection(line.source)?.[1] || 0} Q ${( (projection(line.source)?.[0] || 0) + (projection(line.target)?.[0] || 0) ) / 2} ${Math.min(projection(line.source)?.[1] || 0, projection(line.target)?.[1] || 0) - 80} ${projection(line.target)?.[0] || 0} ${projection(line.target)?.[1] || 0}`"
            stroke-width="1.5"
            class="world-map-shell__attack-arc"
            stroke="url(#worldMapLineGradient)"
            fill="none"
          />
          <circle r="3" :fill="line.color" class="attack-pulse">
             <animateMotion 
               :dur="'2.5s'" 
               repeatCount="indefinite" 
               :path="`M ${projection(line.source)?.[0] || 0} ${projection(line.source)?.[1] || 0} Q ${( (projection(line.source)?.[0] || 0) + (projection(line.target)?.[0] || 0) ) / 2} ${Math.min(projection(line.source)?.[1] || 0, projection(line.target)?.[1] || 0) - 80} ${projection(line.target)?.[0] || 0} ${projection(line.target)?.[1] || 0}`" 
             />
          </circle>
        </g>

        <g v-for="source in renderedSources" :key="source.id" class="world-map-shell__marker" @mouseenter="handleSourceEnter($event, source)" @mousemove="handleSourceEnter($event, source)" @mouseleave="tooltipInfo = null">
          <circle :cx="source.x" :cy="source.y" r="6" fill="none" :stroke="source.color" opacity="0.4" />
          <circle :cx="source.x" :cy="source.y" r="3" :fill="source.color" />
        </g>

        <g>
          <circle :cx="projectedTarget[0]" :cy="projectedTarget[1]" r="4.5" stroke-width="1.5" fill="transparent" stroke="#00d4ff" class="world-map-shell__pulse-ring" />
          <circle :cx="projectedTarget[0]" :cy="projectedTarget[1]" r="2.8" fill="#00d4ff" />
        </g>
      </svg>

      <div v-if="tooltipInfo" class="world-map-shell__tooltip" :style="{ left: tooltipInfo.x + 15 + 'px', top: tooltipInfo.y - 40 + 'px' }">
        <div class="world-map-shell__tooltip-header">
          <span class="world-map-shell__tooltip-country">{{ tooltipInfo.data.country }}</span>
          <span :style="{ color: threatColor }">{{ tooltipInfo.data.threatLevel.toUpperCase() }}</span>
        </div>
        <div class="world-map-shell__tooltip-ip">{{ tooltipInfo.data.ip }}</div>
        <div class="world-map-shell__tooltip-stat">
          <span>攻击频次:</span>
          <span class="world-map-shell__tooltip-val">{{ tooltipInfo.data.attacks }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.world-map-shell {
  position: relative;
  height: 100%;
  background: #020617;
  border-radius: 8px;
  border: 1px solid rgba(0, 212, 255, 0.2);
  overflow: hidden;
  user-select: none;
}
.world-map-shell__loader {
  display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 15px;
}
.world-map-shell__loader-spinner {
  width: 40px; height: 40px; border: 3px solid rgba(0, 212, 255, 0.1); border-top-color: #00d4ff; border-radius: 50%; animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.world-map-shell__loader-text { color: #00d4ff; font-size: 13px; }
.world-map-shell__content { height: 100%; position: relative; }
.world-map-shell__svg { width: 100%; height: 100%; cursor: grab; }
.world-map-shell__svg--dragging { cursor: grabbing; }
.world-map-shell__country { fill: rgba(0, 212, 255, 0.05); stroke: rgba(0, 212, 255, 0.2); stroke-width: 0.5; transition: fill 0.3s; }
.world-map-shell__country:hover { fill: rgba(0, 212, 255, 0.15); stroke: rgba(0, 212, 255, 0.5); }
.world-map-shell__country--active { fill: rgba(0, 212, 255, 0.2) !important; stroke: rgba(0, 212, 255, 0.8) !important; }
.world-map-shell__attack-arc { stroke: #00d4ff; opacity: 0.6; filter: drop-shadow(0 0 2px #00d4ff); }
.world-map-shell__pulse-ring { transform-origin: center; animation: pulse 2s infinite; }
@keyframes pulse { 0% { r: 4.5; opacity: 0.8; } 100% { r: 12; opacity: 0; } }

.world-map-shell__toolbar {
  position: absolute; top: 15px; right: 15px; display: flex; flex-direction: column; gap: 8px; z-index: 10;
}
.world-map-shell__toolbar-btn {
  width: 32px; height: 32px; background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(0, 212, 255, 0.3); color: #00d4ff; border-radius: 4px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s;
}
.world-map-shell__toolbar-btn:hover { background: rgba(0, 212, 255, 0.2); border-color: #00d4ff; }

.world-map-shell__legend {
  position: absolute; bottom: 15px; left: 15px; display: flex; flex-direction: column; gap: 6px; z-index: 10; background: rgba(15, 23, 42, 0.9); padding: 8px 12px; border-radius: 6px; border: 1px solid rgba(0, 212, 255, 0.1);
}
.world-map-shell__legend-item { display: flex; align-items: center; gap: 8px; color: rgba(255, 255, 255, 0.7); font-size: 11px; }
.world-map-shell__legend-dot { width: 8px; height: 8px; border-radius: 50%; }

.world-map-shell__tooltip {
  position: fixed; background: rgba(15, 23, 42, 0.98); border: 1px solid #00d4ff; border-radius: 6px; padding: 10px; min-width: 140px; pointer-events: none; z-index: 100; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
}
.world-map-shell__tooltip-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; font-size: 11px; border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding-bottom: 4px; }
.world-map-shell__tooltip-country { color: #fff; font-weight: bold; }
.world-map-shell__tooltip-ip { font-family: monospace; color: #00d4ff; font-size: 13px; margin-bottom: 4px; }
.world-map-shell__tooltip-stat { display: flex; justify-content: space-between; font-size: 11px; color: rgba(255, 255, 255, 0.6); }
.world-map-shell__tooltip-val { color: #fff; }
</style>