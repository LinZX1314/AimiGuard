<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { X } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { switchWorkbenchApi } from '@/api/switchWorkbench'
import type { SwitchWorkbenchDevice, SwitchWorkbenchDeviceConfig } from '@/api/switchWorkbench'

const props = defineProps<{
  device?: SwitchWorkbenchDevice | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved'): void
}>()

const isEdit = !!props.device
const loading = ref(false)
const error = ref('')

const form = reactive({
  name: '',
  host: '',
  port: 23,
  vendor: 'Generic',
  model: 'Telnet Switch',
  group_id: 'access',
  password: '',
  secret: '',
  acl_number: 30,
  enabled: true,
  readonly_only: false,
  notes: '',
  paging_disable: '',
  tags: [] as string[],
})

onMounted(() => {
  if (props.device) {
    form.name = props.device.name
    form.host = props.device.host
    form.port = props.device.port
    form.vendor = props.device.vendor
    form.model = props.device.model
    form.group_id = props.device.group_id
    form.enabled = props.device.enabled
    form.readonly_only = props.device.readonly_only
    form.tags = props.device.tags || []
  }
})

async function handleSubmit() {
  if (!form.name.trim()) {
    error.value = '请输入设备名称'
    return
  }
  if (!form.host.trim()) {
    error.value = '请输入 IP 地址'
    return
  }

  loading.value = true
  error.value = ''

  try {
    const payload = {
      name: form.name.trim(),
      host: form.host.trim(),
      port: form.port,
      vendor: form.vendor,
      model: form.model,
      group_id: form.group_id,
      password: form.password,
      secret: form.secret,
      acl_number: form.acl_number,
      enabled: form.enabled,
      readonly_only: form.readonly_only,
      notes: form.notes,
      paging_disable: form.paging_disable,
      tags: form.tags,
    }

    // 获取现有设备配置
    const configs = await switchWorkbenchApi.deviceConfigs()
    let newConfigs: any[] = []

    if (isEdit && props.device) {
      // 更新现有设备
      newConfigs = configs.map((c: any) =>
        c.host === props.device?.host ? { ...c, ...payload } : c
      )
    } else {
      // 添加新设备
      newConfigs = [...configs, { ...payload, id: Date.now() }]
    }

    await switchWorkbenchApi.saveDeviceConfigs({ devices: newConfigs })
    emit('saved')
  } catch (e: any) {
    error.value = e.message || '保存失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
    <div class="bg-background rounded-lg shadow-xl w-full max-w-md mx-4">
      <!-- 头部 -->
      <div class="flex items-center justify-between px-4 py-3 border-b">
        <h3 class="font-medium">{{ isEdit ? '编辑设备' : '添加设备' }}</h3>
        <button class="p-1 rounded hover:bg-muted" @click="emit('close')">
          <X :size="18" />
        </button>
      </div>

      <!-- 表单 -->
      <form @submit.prevent="handleSubmit" class="p-4 space-y-4">
        <div v-if="error" class="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded">
          {{ error }}
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="space-y-2">
            <Label for="name">设备名称</Label>
            <Input id="name" v-model="form.name" placeholder="交换机-A" />
          </div>
          <div class="space-y-2">
            <Label for="host">IP 地址</Label>
            <Input id="host" v-model="form.host" placeholder="192.168.1.1" />
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="space-y-2">
            <Label for="port">端口</Label>
            <Input id="port" v-model.number="form.port" type="number" placeholder="23" />
          </div>
          <div class="space-y-2">
            <Label for="vendor">厂商</Label>
            <Select v-model="form.vendor">
              <SelectTrigger id="vendor">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Generic">通用</SelectItem>
                <SelectItem value="Huawei">华为</SelectItem>
                <SelectItem value="H3C">H3C</SelectItem>
                <SelectItem value="Ruijie">锐捷</SelectItem>
                <SelectItem value="Cisco">思科</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="space-y-2">
            <Label for="password">密码</Label>
            <Input id="password" v-model="form.password" type="password" placeholder="可选" />
          </div>
          <div class="space-y-2">
            <Label for="secret">特权密码</Label>
            <Input id="secret" v-model="form.secret" type="password" placeholder="可选" />
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="space-y-2">
            <Label for="group_id">设备组</Label>
            <Select v-model="form.group_id">
              <SelectTrigger id="group_id">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="core">核心</SelectItem>
                <SelectItem value="aggregation">汇聚</SelectItem>
                <SelectItem value="access">接入</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div class="space-y-2">
            <Label for="model">型号</Label>
            <Input id="model" v-model="form.model" placeholder="Telnet Switch" />
          </div>
        </div>

        <div class="flex justify-end gap-2 pt-2">
          <Button type="button" variant="outline" @click="emit('close')">
            取消
          </Button>
          <Button type="submit" :disabled="loading">
            {{ loading ? '保存中...' : '保存' }}
          </Button>
        </div>
      </form>
    </div>
  </div>
</template>
