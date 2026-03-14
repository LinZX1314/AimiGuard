<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api } from '@/api/index'
import { useRouter } from 'vue-router'

const router = useRouter()
const loading  = ref(false)
const scanning = ref(false)
const hosts    = ref<any[]>([])
const scans    = ref<any[]>([])
const stats    = ref({ online: 0 })
const search   = ref('')
const vendorFlt= ref<string | null>(null)
const currentScanId = ref<number | null>(null)

// Host detail dialog
const detailDlg = ref(false)
const detailHost= ref<any>(null)

const headers = [
  { title: 'IP',          key: 'ip',           width: '140px' },
  { title: 'MAC',         key: 'mac_address',  width: '160px' },
  { title: '主机名',      key: 'hostname' },
  { title: '厂商',        key: 'vendor' },
  { title: '系统',        key: 'os_type' },
  { title: '状态',        key: 'state',        width: '80px'  },
  { title: '开放端口',    key: 'open_ports' },
  { title: '操作',        key: 'actions',      sortable: false, width: '80px' },
]

const scanItems = computed(() =>
  scans.value.map(s => ({ id: s.id, label: `#${s.id} – ${s.scan_time?.slice(0,16) ?? ''}` }))
)
const vendorOptions = computed(() =>
  [...new Set(hosts.value.map(h => h.vendor).filter(Boolean))]
)

async function loadScans() {
  try {
    const d = await api.get<any>('/api/nmap/scans')
    scans.value = Array.isArray(d) ? d : (d.data ?? [])
    if (scans.value.length) currentScanId.value = scans.value[0].id
  } catch(e) { console.error(e) }
}

async function loadHosts() {
  loading.value = true
  try {
    let url = '/api/nmap/hosts?limit=500'
    if (currentScanId.value) url += `&scan_id=${currentScanId.value}`
    const d = await api.get<any>(url)
    hosts.value = Array.isArray(d) ? d : (d.data ?? [])
    const online = hosts.value.filter(h => h.state === 'up')
    stats.value.online = online.length
  } catch(e) { console.error(e) }
  loading.value = false
}

const scanProgress = ref(0)
const scanStatus   = ref('')   // '' | 'pending' | 'running' | 'done' | 'error'
let progressTimer: ReturnType<typeof setInterval>

function startProgressPoll() {
  scanProgress.value = 0
  scanStatus.value   = 'pending'
  let pct = 0
  progressTimer = setInterval(async () => {
    pct = Math.min(pct + Math.random() * 8 + 3, 95)
    scanProgress.value = Math.round(pct)
    try {
      const d = await api.get<any>('/api/nmap/scans')
      const latest = (Array.isArray(d) ? d : (d.data ?? []))[0]
      if (latest && scans.value[0]?.id !== latest.id) {
        // new scan appeared — done
        stopProgressPoll(true)
        await loadScans(); await loadHosts()
      }
    } catch { /* ignore */ }
  }, 1200)
}

function stopProgressPoll(success = false) {
  clearInterval(progressTimer)
  scanProgress.value = success ? 100 : 0
  scanStatus.value   = success ? 'done' : ''
  scanning.value     = false
  if (success) setTimeout(() => { scanStatus.value = ''; scanProgress.value = 0 }, 2000)
}

async function startScan() {
  scanning.value = true
  try {
    await api.post('/api/nmap/scan', {})
    startProgressPoll()
  } catch(e) {
    console.error(e)
    scanStatus.value = 'error'
    scanning.value   = false
  }
}

async function openDetail(host: any) {
  detailHost.value = host
  detailDlg.value = true
}

function analyzeWithAi(host: any) {
  detailDlg.value = false
  router.push({
    path: '/ai',
    query: {
      context_type: 'host',
      context_id: host.ip
    }
  })
}

onUnmounted(() => clearInterval(progressTimer))
onMounted(async () => { await loadScans(); await loadHosts() })
</script>

<template>
  <v-container fluid class="pa-6">
    <!-- Controls -->
    <v-card class="mb-4">
      <v-card-text class="d-flex flex-wrap align-center ga-3">
        <v-select
          v-model="currentScanId"
          :items="scanItems"
          item-title="label"
          item-value="id"
          label="选择扫描记录"
          style="max-width:320px"
          hide-details
          @update:model-value="loadHosts"
        />
        <v-btn color="primary" :loading="scanning" @click="startScan" prepend-icon="mdi-radar">
          手动扫描
        </v-btn>
        <v-spacer />
        <div class="text-medium-emphasis text-body-2">在线主机</div>
        <v-chip color="success" size="small">{{ stats.online }}</v-chip>
      </v-card-text>
      <!-- scan progress -->
      <template v-if="scanStatus === 'pending' || scanStatus === 'running' || scanStatus === 'done'">
        <v-divider />
        <div class="px-4 pb-3 pt-1">
          <div class="d-flex justify-space-between text-caption text-medium-emphasis mb-1">
            <span>{{ scanStatus === 'done' ? '扫描完成' : '正在扫描网络…' }}</span>
            <span>{{ scanProgress }}%</span>
          </div>
          <v-progress-linear
            :model-value="scanProgress"
            :color="scanStatus === 'done' ? 'success' : 'primary'"
            :indeterminate="scanStatus === 'pending' && scanProgress < 5"
            rounded height="6"
            bg-color="rgba(255,255,255,.08)"
          />
        </div>
      </template>
    </v-card>

    <!-- Table -->
    <v-card>
      <v-card-title class="d-flex align-center pa-4">
        扫描结果
        <v-spacer />
        <v-btn icon variant="text" @click="loadHosts"><v-icon>mdi-refresh</v-icon></v-btn>
      </v-card-title>
      <v-card-text class="pt-0">
        <v-row dense class="mb-3">
          <v-col cols="12" md="3">
            <v-text-field v-model="search" label="搜索" prepend-inner-icon="mdi-magnify" clearable hide-details />
          </v-col>
          <v-col cols="12" md="2">
            <v-select v-model="vendorFlt" :items="vendorOptions" label="厂商" clearable hide-details />
          </v-col>
        </v-row>
        <v-data-table
          :headers="headers"
          :items="hosts"
          :loading="loading"
          :search="search"
          :items-per-page="50"
          density="compact"
        >
          <template #item.state="{ item }">
            <v-chip :color="item.state === 'up' ? 'success' : 'grey'" size="x-small">
              {{ item.state === 'up' ? '在线' : '离线' }}
            </v-chip>
          </template>
          <template #item.open_ports="{ item }">
            <div style="max-width:260px; white-space:normal; word-break:break-all; font-size:.8rem">
              {{ Array.isArray(item.open_ports) ? item.open_ports.join(', ') : item.open_ports || '-' }}
            </div>
          </template>
          <template #item.actions="{ item }">
            <v-btn icon variant="text" size="x-small" @click="openDetail(item)">
              <v-icon size="16">mdi-information-outline</v-icon>
            </v-btn>
          </template>
        </v-data-table>
      </v-card-text>
    </v-card>

    <!-- Detail dialog -->
    <v-dialog v-model="detailDlg" max-width="600">
      <v-card v-if="detailHost">
        <v-card-title>主机详情 — {{ detailHost.ip }}</v-card-title>
        <v-card-text>
          <v-list density="compact">
            <v-list-item title="状态">
              <template #append>
                <v-chip :color="detailHost.state === 'up' ? 'success' : 'grey'" size="x-small">
                  {{ detailHost.state === 'up' ? '在线' : '离线' }}
                </v-chip>
              </template>
            </v-list-item>
            <v-list-item title="MAC 地址"   :subtitle="detailHost.mac_address || '-'" />
            <v-list-item title="厂商"        :subtitle="detailHost.vendor    || '-'" />
            <v-list-item title="主机名"      :subtitle="detailHost.hostname  || '-'" />
            <v-list-item title="操作系统"    :subtitle="detailHost.os_type   || '-'" />
            <v-list-item title="OS 精度"     :subtitle="String(detailHost.os_accuracy || '-')" />
            <v-list-item title="OS 标签"     :subtitle="detailHost.os_tags   || '-'" />
          </v-list>
          <div v-if="detailHost.services?.length" class="mt-2">
            <div class="text-subtitle-2 mb-1">服务列表</div>
            <v-table density="compact">
              <thead><tr><th>端口</th><th>服务</th><th>产品/版本</th></tr></thead>
              <tbody>
                <tr v-for="s in detailHost.services" :key="s.port">
                  <td>{{ s.port }}</td>
                  <td>{{ s.service }}</td>
                  <td>{{ s.product }} {{ s.version }}</td>
                </tr>
              </tbody>
            </v-table>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn color="secondary" variant="outlined" prepend-icon="mdi-robot" @click="analyzeWithAi(detailHost)">
            AI 深度分析
          </v-btn>
          <v-btn color="primary" variant="text" @click="detailDlg = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>
