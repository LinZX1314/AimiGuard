<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/index'

const workflows = ref<any[]>([])
const runs      = ref<any[]>([])
const loading   = ref(false)
const tab       = ref('workflows')

const wfHeaders = [
  { title: '名称',  key: 'name' },
  { title: '描述',  key: 'description' },
  { title: '状态',  key: 'status', width: '100px' },
  { title: '最后运行', key: 'last_run_at' },
]
const runHeaders = [
  { title: '工作流', key: 'workflow_name' },
  { title: '状态',   key: 'status',  width: '100px' },
  { title: '触发者', key: 'triggered_by' },
  { title: '开始时间', key: 'started_at' },
  { title: '结束时间', key: 'ended_at' },
]
const STA_COLOR: Record<string, string>  = { active: 'success', inactive: 'grey', running: 'primary', success: 'success', failed: 'error' }

async function loadWorkflows() {
  loading.value = true
  try {
    const d = await api.get<any>('/api/v1/workflows')
    workflows.value = d.items ?? d.data ?? []
  } catch {}
  loading.value = false
}

async function loadRuns() {
  loading.value = true
  try {
    const d = await api.get<any>('/api/v1/workflows/runs?limit=100')
    runs.value = d.items ?? d.data ?? []
  } catch {}
  loading.value = false
}

onMounted(() => { loadWorkflows(); loadRuns() })
</script>

<template>
  <v-container fluid class="pa-6">
    <v-tabs v-model="tab" color="primary" class="mb-4">
      <v-tab value="workflows">工作流定义</v-tab>
      <v-tab value="runs">运行记录</v-tab>
    </v-tabs>

    <v-window v-model="tab">
      <v-window-item value="workflows">
        <v-card>
          <v-card-text class="pt-2">
            <v-data-table :headers="wfHeaders" :items="workflows" :loading="loading" density="compact">
              <template #item.status="{ item }">
                <v-chip :color="STA_COLOR[item.status] ?? 'grey'" size="x-small">{{ item.status }}</v-chip>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-window-item>

      <v-window-item value="runs">
        <v-card>
          <v-card-text class="pt-2">
            <v-data-table :headers="runHeaders" :items="runs" :loading="loading" density="compact">
              <template #item.status="{ item }">
                <v-chip :color="STA_COLOR[item.status] ?? 'grey'" size="x-small">{{ item.status }}</v-chip>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-window-item>
    </v-window>
  </v-container>
</template>
