<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/index'

const loading = ref(false)
const events  = ref<any[]>([])
const search  = ref('')
const page    = ref(1)
const total   = ref(0)
const pageSize = 50

const headers = [
  { title: '攻击 IP',   key: 'attack_ip',   width: '150px' },
  { title: '类型',      key: 'event_type',  width: '120px' },
  { title: '严重性',    key: 'severity',    width: '100px' },
  { title: 'AI 建议',  key: 'ai_decision', width: '120px' },
  { title: 'AI 分析',  key: 'ai_analysis' },
  { title: '状态',      key: 'status',      width: '100px' },
  { title: '时间',      key: 'created_at' },
  { title: '操作',      key: 'actions',     sortable: false, width: '140px' },
]
const SEV_COLOR: Record<string, string>  = { high: 'error', medium: 'warning', low: 'info', info: 'grey' }
const STA_COLOR: Record<string, string>  = { pending: 'warning', approved: 'success', rejected: 'grey', false_positive: 'info' }

function unwrap<T>(payload: any): T {
  return (payload?.data ?? payload) as T
}

async function load() {
  // 事件列表以分页查询为主，兼容后端返回 items 或 data.items 两种结构。
  loading.value = true
  try {
    const url = `/api/v1/defense/events?page=${page.value}&page_size=${pageSize}`
    const d   = await api.get<any>(url)
    const data = unwrap<any>(d)
    events.value = data.items ?? []
    total.value  = data.total ?? events.value.length
  } catch(e) { console.error(e) }
  loading.value = false
}

async function approve(id: number) {
  await api.post(`/api/v1/defense/events/${id}/approve`, {})
  load()
}
async function reject(id: number) {
  await api.post(`/api/v1/defense/events/${id}/reject`, {})
  load()
}
async function markFP(id: number) {
  await api.post(`/api/v1/defense/events/${id}/false-positive`, {})
  load()
}

onMounted(load)
</script>

<template>
  <v-container fluid class="pa-6">
    <v-card>
      <v-card-title class="d-flex align-center pa-4">
        防御事件
        <v-spacer />
        <v-text-field v-model="search" label="搜索" prepend-inner-icon="mdi-magnify" clearable hide-details style="max-width:240px" />
        <v-btn icon variant="text" class="ml-2" @click="load"><v-icon>mdi-refresh</v-icon></v-btn>
      </v-card-title>
      <v-card-text class="pt-0">
        <v-data-table
          :headers="headers"
          :items="events"
          :loading="loading"
          :search="search"
          :items-per-page="pageSize"
          density="compact"
        >
          <template #item.severity="{ item }">
            <v-chip :color="SEV_COLOR[item.severity] ?? 'grey'" size="x-small">{{ item.severity }}</v-chip>
          </template>
          <template #item.status="{ item }">
            <v-chip :color="STA_COLOR[item.status] ?? 'grey'" size="x-small">{{ item.status }}</v-chip>
          </template>
          <template #item.ai_decision="{ item }">
            <v-chip v-if="item.ai_decision" :color="item.ai_decision === 'ban' ? 'error' : 'success'" size="x-small">
              {{ item.ai_decision === 'ban' ? '封禁' : '放行' }}
            </v-chip>
          </template>
          <template #item.ai_analysis="{ item }">
            <div style="max-width:260px; white-space:normal; font-size:.8rem" class="text-medium-emphasis">
              {{ item.ai_analysis || '-' }}
            </div>
          </template>
          <template #item.actions="{ item }">
            <v-btn v-if="item.status === 'pending'" size="x-small" color="success" variant="text" @click="approve(item.id)">批准</v-btn>
            <v-btn v-if="item.status === 'pending'" size="x-small" color="grey"    variant="text" @click="reject(item.id)">拒绝</v-btn>
            <v-btn size="x-small" color="warning" variant="text" @click="markFP(item.id)">误报</v-btn>
          </template>
        </v-data-table>
      </v-card-text>
    </v-card>
  </v-container>
</template>
