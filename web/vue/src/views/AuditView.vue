<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/index'

const logs    = ref<any[]>([])
const loading = ref(false)
const search  = ref('')
const headers = [
  { title: '操作者',  key: 'operator' },
  { title: '动作',    key: 'action' },
  { title: '资源',    key: 'resource' },
  { title: '结果',    key: 'result',  width: '100px' },
  { title: '来源 IP', key: 'ip',      width: '150px' },
  { title: '时间',    key: 'created_at' },
]

async function load() {
  loading.value = true
  try {
    const d = await api.get<any>('/api/v1/audit/logs?limit=500')
    logs.value = d.items ?? d.data?.items ?? d.data ?? []
  } catch(e) { console.error(e) }
  loading.value = false
}

onMounted(load)
</script>

<template>
  <v-container fluid class="pa-6">
    <v-card>
      <v-card-title class="d-flex align-center pa-4">
        审计日志
        <v-spacer />
        <v-text-field v-model="search" label="搜索" prepend-inner-icon="mdi-magnify" clearable hide-details style="max-width:240px" />
        <v-btn icon variant="text" class="ml-2" @click="load"><v-icon>mdi-refresh</v-icon></v-btn>
      </v-card-title>
      <v-card-text class="pt-0">
        <v-data-table
          :headers="headers"
          :items="logs"
          :loading="loading"
          :search="search"
          :items-per-page="50"
          density="compact"
        >
          <template #item.result="{ item }">
            <v-chip :color="item.result === 'success' ? 'success' : 'error'" size="x-small">{{ item.result }}</v-chip>
          </template>
        </v-data-table>
      </v-card-text>
    </v-card>
  </v-container>
</template>
