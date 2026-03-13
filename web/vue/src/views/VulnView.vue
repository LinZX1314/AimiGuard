<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/index'

const loading  = ref(false)
const scanning = ref(false)
const vulns    = ref<any[]>([])
const search   = ref('')
const sevFlt   = ref<string | null>(null)
const statusFlt= ref<string | null>(null)
const stats    = ref({ total: 0, critical: 0, high: 0, fixed: 0 })

const headers = [
  { title: '漏洞名称',  key: 'vuln_name' },
  { title: '主机 IP',  key: 'ip',         width: '140px' },
  { title: '端口',     key: 'port',        width: '80px' },
  { title: '严重性',   key: 'severity',    width: '100px' },
  { title: '状态',     key: 'status',      width: '100px' },
  { title: '发现时间', key: 'created_at' },
  { title: '操作',     key: 'actions',     sortable: false, width: '120px' },
]

const severities = ['严重', '高危', '中危', '低危', '信息']
const statuses   = ['open', 'fixed', 'ignored', 'false_positive']
const SEV_COLOR: Record<string, string> = {
  '严重': 'error', '高危': 'warning', '中危': 'info', '低危': 'success', '信息': 'grey'
}
const STA_COLOR: Record<string, string> = {
  open: 'error', fixed: 'success', ignored: 'grey', false_positive: 'warning'
}

async function load() {
  loading.value = true
  try {
    let url = '/api/v1/scan/findings?limit=500'
    if (sevFlt.value)    url += `&severity=${sevFlt.value}`
    if (statusFlt.value) url += `&status=${statusFlt.value}`
    const d = await api.get<any>(url)
    vulns.value = d.items ?? d.data?.items ?? d.data ?? []
    stats.value.total    = vulns.value.length
    stats.value.critical = vulns.value.filter(v => v.severity === '严重').length
    stats.value.high     = vulns.value.filter(v => v.severity === '高危').length
    stats.value.fixed    = vulns.value.filter(v => v.status === 'fixed').length
  } catch(e) { console.error(e) }
  loading.value = false
}

async function startVulnScan() {
  scanning.value = true
  try { await api.post('/api/nmap/vuln/scan', {}) } catch {}
  scanning.value = false
}

async function markStatus(id: number, status: string) {
  try {
    await api.put(`/api/v1/scan/findings/${id}/status`, { status })
    await load()
  } catch(e) { console.error(e) }
}

onMounted(load)
</script>

<template>
  <v-container fluid class="pa-6">
    <!-- Stats -->
    <v-row class="mb-4">
      <v-col cols="6" md="3" v-for="[label, val, color] in [['漏洞总数', stats.total, '#3B82F6'], ['严重', stats.critical, '#EF4444'], ['高危', stats.high, '#F59E0B'], ['已修复', stats.fixed, '#10B981']]" :key="String(label)">
        <v-card :style="`border-left:4px solid ${color}`" class="pa-4">
          <div class="text-h4 font-weight-bold" :style="`color:${color}`">{{ val }}</div>
          <div class="text-caption text-medium-emphasis">{{ label }}</div>
        </v-card>
      </v-col>
    </v-row>

    <!-- Table -->
    <v-card>
      <v-card-title class="d-flex flex-wrap align-center ga-2 pa-4">
        漏洞列表
        <v-spacer />
        <v-btn color="warning" variant="tonal" :loading="scanning" @click="startVulnScan" prepend-icon="mdi-bug-check-outline">
          漏洞扫描
        </v-btn>
        <v-btn icon variant="text" @click="load"><v-icon>mdi-refresh</v-icon></v-btn>
      </v-card-title>
      <v-card-text class="pt-0">
        <v-row dense class="mb-3">
          <v-col cols="12" md="3">
            <v-text-field v-model="search" label="搜索" prepend-inner-icon="mdi-magnify" clearable hide-details />
          </v-col>
          <v-col cols="12" md="2">
            <v-select v-model="sevFlt" :items="severities" label="严重性" clearable hide-details @update:model-value="load" />
          </v-col>
          <v-col cols="12" md="2">
            <v-select v-model="statusFlt" :items="statuses" label="状态" clearable hide-details @update:model-value="load" />
          </v-col>
        </v-row>
        <v-data-table
          :headers="headers"
          :items="vulns"
          :loading="loading"
          :search="search"
          :items-per-page="50"
          density="compact"
        >
          <template #item.severity="{ item }">
            <v-chip :color="SEV_COLOR[item.severity] ?? 'grey'" size="x-small">{{ item.severity }}</v-chip>
          </template>
          <template #item.status="{ item }">
            <v-chip :color="STA_COLOR[item.status] ?? 'grey'" size="x-small">{{ item.status }}</v-chip>
          </template>
          <template #item.actions="{ item }">
            <v-btn size="x-small" variant="text" color="success"   @click="markStatus(item.id, 'fixed')">已修</v-btn>
            <v-btn size="x-small" variant="text" color="grey"      @click="markStatus(item.id, 'ignored')">忽略</v-btn>
          </template>
        </v-data-table>
      </v-card-text>
    </v-card>
  </v-container>
</template>
