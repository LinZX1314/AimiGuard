<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/index'

const honeypots = ref<any[]>([])
const loading   = ref(false)
const dlg       = ref(false)
const form      = ref({ name: '', type: '', ip: '', port: '', enabled: true })
const editId    = ref<number | null>(null)
const alertsDlg = ref(false)
const alerts    = ref<any[]>([])
const alertTitle = ref('')

const headers = [
  { title: '名称',  key: 'name' },
  { title: '类型',  key: 'type' },
  { title: 'IP',   key: 'ip',   width: '140px' },
  { title: '端口', key: 'port', width: '80px'  },
  { title: '状态', key: 'enabled', width: '80px' },
  { title: '告警', key: 'alert_count', width: '80px' },
  { title: '操作', key: 'actions', sortable: false, width: '120px' },
]

async function load() {
  loading.value = true
  try {
    const d = await api.get<any>('/api/v1/honeypots')
    honeypots.value = d.data ?? d
  } catch(e) { console.error(e) }
  loading.value = false
}

function openNew() {
  form.value = { name: '', type: '', ip: '', port: '', enabled: true }
  editId.value = null
  dlg.value = true
}

function openEdit(hp: any) {
  form.value = { ...hp }
  editId.value = hp.id
  dlg.value = true
}

async function save() {
  try {
    if (editId.value) await api.put(`/api/v1/honeypots/${editId.value}`, form.value)
    else await api.post('/api/v1/honeypots', form.value)
    dlg.value = false
    load()
  } catch(e) { console.error(e) }
}

async function viewAlerts(hp: any) {
  alertTitle.value = hp.name
  alertsDlg.value = true
  try {
    const d = await api.get<any>(`/api/v1/honeypots/${hp.id}/alerts`)
    alerts.value = d.data ?? d
  } catch { alerts.value = [] }
}

onMounted(load)
</script>

<template>
  <v-container fluid class="pa-6">
    <v-card>
      <v-card-title class="d-flex align-center pa-4">
        蜜罐实例
        <v-spacer />
        <v-btn color="primary" prepend-icon="mdi-plus" @click="openNew">新增蜜罐</v-btn>
        <v-btn icon variant="text" class="ml-2" @click="load"><v-icon>mdi-refresh</v-icon></v-btn>
      </v-card-title>
      <v-card-text class="pt-0">
        <v-data-table :headers="headers" :items="honeypots" :loading="loading" density="compact">
          <template #item.enabled="{ item }">
            <v-chip :color="item.enabled ? 'success' : 'grey'" size="x-small">
              {{ item.enabled ? '运行中' : '停止' }}
            </v-chip>
          </template>
          <template #item.actions="{ item }">
            <v-btn size="x-small" variant="text" @click="openEdit(item)">编辑</v-btn>
            <v-btn size="x-small" variant="text" color="warning" @click="viewAlerts(item)">告警</v-btn>
          </template>
        </v-data-table>
      </v-card-text>
    </v-card>

    <!-- Add/Edit dialog -->
    <v-dialog v-model="dlg" max-width="480">
      <v-card>
        <v-card-title>{{ editId ? '编辑蜜罐' : '新增蜜罐' }}</v-card-title>
        <v-card-text>
          <v-text-field v-model="form.name"  label="名称"    class="mb-2" />
          <v-text-field v-model="form.type"  label="类型"    class="mb-2" placeholder="ssh / http / ftp ..." />
          <v-text-field v-model="form.ip"    label="IP"      class="mb-2" />
          <v-text-field v-model="form.port"  label="端口"    class="mb-2" />
          <v-switch v-model="form.enabled" label="启用" color="primary" hide-details />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="dlg = false">取消</v-btn>
          <v-btn color="primary" @click="save">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Alerts dialog -->
    <v-dialog v-model="alertsDlg" max-width="700">
      <v-card>
        <v-card-title>告警记录 — {{ alertTitle }}</v-card-title>
        <v-card-text>
          <v-data-table
            :headers="[{title:'时间',key:'created_at'},{title:'来源 IP',key:'src_ip'},{title:'事件',key:'event_type'},{title:'详情',key:'detail'}]"
            :items="alerts"
            density="compact"
            :items-per-page="20"
          />
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn variant="text" @click="alertsDlg = false">关闭</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>
