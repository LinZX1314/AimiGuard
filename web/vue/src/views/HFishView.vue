<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { use }    from 'echarts/core'
import { CanvasRenderer }  from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import {
  GridComponent, TitleComponent, TooltipComponent,
  LegendComponent, DataZoomComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import { api } from '@/api/index'

use([CanvasRenderer, BarChart, PieChart, GridComponent, TitleComponent,
     TooltipComponent, LegendComponent, DataZoomComponent])

const loading   = ref(false)
const viewMode  = ref<'detail' | 'aggregated'>('detail')
const logs      = ref<any[]>([])
const stats     = ref({ total_attacks: 0 })
const services  = ref<string[]>([])
const search    = ref('')
const svcFilter = ref<string | null>(null)

// Nmap host dialog
const nmapDialog = ref(false)
const nmapIp     = ref('')
const nmapHost   = ref<any>(null)

const detailHeaders = [
  { title: '攻击 IP',   key: 'attack_ip',       width: '160px' },
  { title: '归属地',    key: 'ip_location' },
  { title: '服务类型',  key: 'service_name' },
  { title: '端口',      key: 'service_port',    width: '90px' },
  { title: '时间',      key: 'create_time_str' },
]
const aggHeaders = [
  { title: '攻击 IP',     key: 'attack_ip',    width: '160px' },
  { title: '归属地',      key: 'ip_location' },
  { title: '攻击次数',    key: 'attack_count', width: '100px' },
  { title: '服务分类',    key: 'service_name' },
  { title: '最后活跃',    key: 'latest_time' },
  { title: 'AI 封禁判定', key: 'decision',     width: '120px' },
  { title: 'AI 分析',     key: 'ai_analysis' },
]
const headers = computed(() => viewMode.value === 'aggregated' ? aggHeaders : detailHeaders)

// ── ECharts options ──────────────────────────────────────────────────────
const CHART_THEME = {
  textStyle: { color: 'rgba(255,255,255,.7)', fontFamily: 'inherit' },
  backgroundColor: 'transparent',
}
const locationBarOption = computed(() => {
  const counter: Record<string, number> = {}
  for (const log of logs.value) {
    const loc = log.ip_location || log.location || '未知'
    // take first segment (e.g. "中国 广东")
    const key = loc.split(' ')[0] || loc
    counter[key] = (counter[key] ?? 0) + (Number(log.attack_count) || 1)
  }
  const sorted = Object.entries(counter).sort((a, b) => b[1] - a[1]).slice(0, 15)
  return {
    ...CHART_THEME,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '8%', containLabel: true },
    xAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(255,255,255,.06)' } } },
    yAxis: {
      type: 'category',
      data: sorted.map(x => x[0]).reverse(),
      axisLabel: { fontSize: 11 }
    },
    series: [{
      type: 'bar',
      data: sorted.map(x => x[1]).reverse(),
      itemStyle: {
        color: { type: 'linear', x: 0, y: 0, x2: 1, y2: 0,
          colorStops: [{ offset: 0, color: '#8B5CF6' }, { offset: 1, color: '#00E5FF' }] }
      },
      label: { show: true, position: 'right', fontSize: 11, color: 'rgba(255,255,255,.6)' }
    }]
  }
})

const servicePieOption = computed(() => {
  const counter: Record<string, number> = {}
  for (const log of logs.value) {
    const svc = log.service_name || '未知'
    counter[svc] = (counter[svc] ?? 0) + (Number(log.attack_count) || 1)
  }
  const sorted = Object.entries(counter).sort((a, b) => b[1] - a[1]).slice(0, 10)
  const COLORS = ['#00E5FF','#8B5CF6','#F472B6','#10B981','#F59E0B','#3B82F6','#EF4444','#6EE7B7','#A78BFA','#FCA5A5']
  return {
    ...CHART_THEME,
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'vertical', right: '2%', top: 'center',
      textStyle: { color: 'rgba(255,255,255,.7)', fontSize: 11 } },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['40%', '55%'],
      data: sorted.map(([name, value], i) => ({
        name, value, itemStyle: { color: COLORS[i % COLORS.length] }
      })),
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 12 } }
    }]
  }
})

async function loadStats() {
  try {
    const d = await api.get<any>('/api/v1/defense/hfish/stats')
    const sd = d.data ?? d
    stats.value.total_attacks = (sd.service_stats ?? []).reduce((a:number,s:any) => a + s.count, 0)
    services.value = (sd.service_stats ?? []).map((s:any) => s.name)
  } catch(e) { console.error(e) }
}

async function loadLogs() {
  loading.value = true
  try {
    let url = viewMode.value === 'aggregated'
      ? '/api/v1/defense/hfish/logs?limit=500&aggregated=1'
      : '/api/v1/defense/hfish/logs?limit=500'
    if (svcFilter.value) url += `&service_name=${encodeURIComponent(svcFilter.value)}`
    const d = await api.get<any>(url)
    logs.value = d.data?.items ?? d.data ?? d
  } catch(e) { console.error(e) }
  loading.value = false
}

async function showNmap(ip: string) {
  nmapIp.value = ip
  nmapHost.value = null
  nmapDialog.value = true
  try {
    const d = await api.get<any>(`/api/nmap/host/${ip}`)
    nmapHost.value = d
  } catch { nmapHost.value = null }
}

async function manualSync() {
  try {
    await api.post('/api/v1/defense/hfish/sync', {})
    await loadStats()
    await loadLogs()
  } catch(e) { console.error(e) }
}

watch([viewMode, svcFilter], loadLogs)
onMounted(() => { loadStats(); loadLogs() })
</script>

<template>
  <v-container fluid class="pa-6">
    <!-- Stats bar -->
    <v-row class="mb-4">
      <v-col cols="12">
        <v-card style="border-left:4px solid #3B82F6" class="pa-4">
          <div class="d-flex justify-space-between align-center">
            <div>
              <div class="text-caption text-medium-emphasis">攻击日志总数</div>
              <div class="text-h4 font-weight-bold" style="color:#3B82F6">{{ stats.total_attacks }}</div>
            </div>
            <v-btn color="primary" variant="tonal" @click="manualSync" prepend-icon="mdi-sync">
              手动同步
            </v-btn>
          </div>
        </v-card>
      </v-col>
    </v-row>

    <!-- ECharts Attack Origin Charts -->
    <v-row class="mb-4" v-if="logs.length">
      <v-col cols="12" md="7">
        <v-card>
          <v-card-title class="text-subtitle-1 pa-3">
            <v-icon start color="primary" size="18">mdi-earth</v-icon>
            攻击来源 Top 15（地区）
          </v-card-title>
          <v-card-text class="pa-2" style="height:300px">
            <v-chart :option="locationBarOption" autoresize style="width:100%;height:100%" />
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="5">
        <v-card>
          <v-card-title class="text-subtitle-1 pa-3">
            <v-icon start color="secondary" size="18">mdi-chart-donut</v-icon>
            攻击服务分布
          </v-card-title>
          <v-card-text class="pa-2" style="height:300px">
            <v-chart :option="servicePieOption" autoresize style="width:100%;height:100%" />
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Table card -->
    <v-card>
      <v-card-title class="d-flex flex-wrap align-center ga-2 pa-4">
        <span>攻击记录</span>
        <v-btn-toggle v-model="viewMode" mandatory density="compact" color="primary">
          <v-btn value="detail" size="small">
            <v-icon start size="16">mdi-format-list-bulleted</v-icon>明细
          </v-btn>
          <v-btn value="aggregated" size="small">
            <v-icon start size="16">mdi-folder-network</v-icon>折叠
          </v-btn>
        </v-btn-toggle>
        <v-spacer />
        <v-btn icon variant="text" @click="loadLogs"><v-icon>mdi-refresh</v-icon></v-btn>
      </v-card-title>

      <v-card-text class="pt-0">
        <v-row dense class="mb-3">
          <v-col cols="12" md="3">
            <v-text-field v-model="search" label="搜索" prepend-inner-icon="mdi-magnify" clearable hide-details />
          </v-col>
          <v-col cols="12" md="2">
            <v-select v-model="svcFilter" :items="services" label="服务类型" clearable hide-details />
          </v-col>
        </v-row>

        <v-data-table
          :headers="headers"
          :items="logs"
          :loading="loading"
          :search="search"
          :items-per-page="50"
          density="compact"
        >
          <template #item.attack_ip="{ item }">
            <a href="#" @click.prevent="showNmap(item.attack_ip)" class="text-primary">
              {{ item.attack_ip || '-' }}
            </a>
          </template>
          <template #item.decision="{ item }">
            <v-chip
              v-if="item.decision"
              :color="item.decision === 'true' ? 'error' : 'success'"
              size="x-small"
            >{{ item.decision === 'true' ? '建议封禁' : '无需封禁' }}</v-chip>
            <span v-else class="text-medium-emphasis">-</span>
          </template>
          <template #item.ai_analysis="{ item }">
            <div
              v-if="item.ai_analysis"
              style="max-width:280px; white-space:normal; word-break:break-all; font-size:.8rem"
              class="text-medium-emphasis"
            >{{ item.ai_analysis }}</div>
            <span v-else class="text-medium-emphasis">暂无分析</span>
          </template>
        </v-data-table>
      </v-card-text>
    </v-card>

    <!-- Nmap dialog -->
    <v-dialog v-model="nmapDialog" max-width="560">
      <v-card>
        <v-card-title>扫描信息 - {{ nmapIp }}</v-card-title>
        <v-card-text v-if="nmapHost">
          <v-list density="compact">
            <v-list-item title="状态">
              <template #append>
                <v-chip :color="nmapHost.state === 'up' ? 'success' : 'grey'" size="x-small">
                  {{ nmapHost.state === 'up' ? '在线' : '离线' }}
                </v-chip>
              </template>
            </v-list-item>
            <v-list-item title="MAC 地址"   :subtitle="nmapHost.mac_address || '-'" />
            <v-list-item title="厂商"        :subtitle="nmapHost.vendor    || '-'" />
            <v-list-item title="主机名"      :subtitle="nmapHost.hostname  || '-'" />
            <v-list-item title="操作系统"    :subtitle="nmapHost.os_type   || '-'" />
          </v-list>
          <div v-if="nmapHost.services?.length" class="mt-2">
            <div class="text-subtitle-2 mb-1">开放端口</div>
            <v-table density="compact">
              <thead><tr><th>端口</th><th>服务</th></tr></thead>
              <tbody>
                <tr v-for="s in nmapHost.services" :key="s.port">
                  <td>{{ s.port }}</td><td>{{ s.service }}</td>
                </tr>
              </tbody>
            </v-table>
          </div>
        </v-card-text>
        <v-card-text v-else class="text-medium-emphasis">未找到该 IP 的扫描记录</v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn color="primary" variant="text" @click="nmapDialog = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>
