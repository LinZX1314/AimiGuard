<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/index'

const iocs    = ref<any[]>([])
const loading = ref(false)
const search  = ref('')
const headers = [
  { title: '类型',   key: 'type',       width: '100px' },
  { title: '值',     key: 'value' },
  { title: '威胁分', key: 'score',      width: '90px'  },
  { title: '来源',   key: 'source' },
  { title: '标签',   key: 'tags' },
  { title: '最后看到', key: 'last_seen' },
]

async function load() {
  loading.value = true
  try {
    const d = await api.get<any>('/api/v1/threat-intel/iocs?limit=500')
    iocs.value = d.items ?? d.data?.items ?? d.data ?? []
  } catch(e) { console.error(e) }
  loading.value = false
}

onMounted(load)
</script>

<template>
  <v-container fluid class="pa-6">
    <v-card>
      <v-card-title class="d-flex align-center pa-4">
        威胁情报 IOC
        <v-spacer />
        <v-text-field v-model="search" label="搜索" prepend-inner-icon="mdi-magnify" clearable hide-details style="max-width:240px" />
        <v-btn icon variant="text" class="ml-2" @click="load"><v-icon>mdi-refresh</v-icon></v-btn>
      </v-card-title>
      <v-card-text class="pt-0">
        <v-data-table :headers="headers" :items="iocs" :loading="loading" :search="search" :items-per-page="50" density="compact">
          <template #item.score="{ item }">
            <v-chip :color="item.score >= 80 ? 'error' : item.score >= 50 ? 'warning' : 'success'" size="x-small">
              {{ item.score }}
            </v-chip>
          </template>
          <template #item.tags="{ item }">
            <v-chip v-for="t in (Array.isArray(item.tags) ? item.tags : [item.tags])" :key="t" size="x-small" class="mr-1">{{ t }}</v-chip>
          </template>
        </v-data-table>
      </v-card-text>
    </v-card>
  </v-container>
</template>
