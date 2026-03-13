<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/index'

const config  = ref<any>({ enabled: false, mode: 'whitelist', whitelist: [], blacklist: [] })
const saving  = ref(false)
const snack   = ref({ show: false, text: '', color: 'success' })
const newIp   = ref('')
const listTab = ref<'white' | 'black'>('white')

async function load() {
  try {
    const d = await api.get<any>('/api/v1/firewall/config')
    config.value = d.data ?? d
  } catch(e) { console.error(e) }
}

async function save() {
  saving.value = true
  try {
    await api.post('/api/v1/firewall/config', config.value)
    snack.value = { show: true, text: '保存成功', color: 'success' }
  } catch(e) {
    snack.value = { show: true, text: '保存失败', color: 'error' }
  }
  saving.value = false
}

function addIp() {
  if (!newIp.value.trim()) return
  const ip = newIp.value.trim()
  if (listTab.value === 'white') {
    if (!config.value.whitelist.includes(ip)) config.value.whitelist.push(ip)
  } else {
    if (!config.value.blacklist.includes(ip)) config.value.blacklist.push(ip)
  }
  newIp.value = ''
}
function removeIp(ip: string) {
  if (listTab.value === 'white') config.value.whitelist = config.value.whitelist.filter((i: string) => i !== ip)
  else config.value.blacklist = config.value.blacklist.filter((i: string) => i !== ip)
}

onMounted(load)
</script>

<template>
  <v-container fluid class="pa-6" style="max-width:800px">
    <v-card class="mb-4">
      <v-card-title>防火墙配置</v-card-title>
      <v-card-text>
        <v-switch v-model="config.enabled" label="启用防火墙" color="primary" hide-details class="mb-4" />
        <v-select
          v-model="config.mode"
          :items="[{title:'白名单模式（仅允许列表内 IP）',value:'whitelist'},{title:'黑名单模式（封禁列表内 IP）',value:'blacklist'}]"
          item-title="title"
          item-value="value"
          label="工作模式"
          class="mb-2"
        />
      </v-card-text>
    </v-card>

    <v-card class="mb-4">
      <v-card-title class="d-flex align-center">
        IP 列表管理
        <v-btn-toggle v-model="listTab" mandatory density="compact" color="primary" class="ml-4">
          <v-btn value="white" size="small">白名单 ({{ config.whitelist?.length ?? 0 }})</v-btn>
          <v-btn value="black" size="small">黑名单 ({{ config.blacklist?.length ?? 0 }})</v-btn>
        </v-btn-toggle>
      </v-card-title>
      <v-card-text>
        <div class="d-flex ga-2 mb-3">
          <v-text-field v-model="newIp" label="输入 IP 地址" hide-details @keyup.enter="addIp" />
          <v-btn color="primary" @click="addIp">添加</v-btn>
        </div>
        <v-list density="compact" style="max-height:320px; overflow-y:auto">
          <v-list-item
            v-for="ip in (listTab === 'white' ? config.whitelist : config.blacklist)"
            :key="ip"
            :title="ip"
          >
            <template #append>
              <v-btn icon variant="text" size="x-small" color="error" @click="removeIp(ip)">
                <v-icon size="16">mdi-close</v-icon>
              </v-btn>
            </template>
          </v-list-item>
          <v-list-item v-if="!(listTab === 'white' ? config.whitelist : config.blacklist)?.length" class="text-medium-emphasis">
            暂无数据
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>

    <v-btn color="primary" :loading="saving" @click="save" prepend-icon="mdi-content-save-outline">
      保存配置
    </v-btn>

    <v-snackbar v-model="snack.show" :color="snack.color" timeout="2500">{{ snack.text }}</v-snackbar>
  </v-container>
</template>
