<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Settings, Shield, Network, Bot, Bell, Plus, Trash2 } from 'lucide-vue-next'
import { api } from '@/api/index'

const loading = ref(false)
const whitelistLoading = ref(false)
const whitelist = ref<string[]>([])
const newIp = ref('')
const whitelistMsg = ref('')

// 系统配置
const systemConfig = ref({
  hfish_url: '',
  hfish_token: '',
  switch_ip: '',
  switch_username: '',
  switch_password: '',
  ai_enabled: false,
  ai_url: '',
  ai_model: '',
})

// 加载配置
async function loadConfig() {
  loading.value = true
  try {
    const res = await api.get<Partial<typeof systemConfig.value>>('/api/system/config')
    const configData = res as Partial<typeof systemConfig.value>
    if (configData) {
      systemConfig.value = { ...systemConfig.value, ...configData }
    }
  } catch (err) {
    console.error('加载配置失败:', err)
  } finally {
    loading.value = false
  }
}

// 保存配置
async function saveConfig() {
  loading.value = true
  try {
    await api.post('/api/system/config', systemConfig.value)
    alert('配置保存成功')
  } catch (err) {
    console.error('保存配置失败:', err)
    alert('配置保存失败')
  } finally {
    loading.value = false
  }
}

async function loadWhitelist() {
  try {
    const res = await api.get<{ whitelist: string[] }>('/api/v1/system/ai-whitelist')
    whitelist.value = (res as any)?.whitelist ?? []
  } catch (e) {
    console.error('加载白名单失败:', e)
  }
}

async function addIp() {
  const ip = newIp.value.trim()
  if (!ip) return
  if (whitelist.value.includes(ip)) {
    whitelistMsg.value = `${ip} 已在白名单中`
    return
  }
  whitelist.value.push(ip)
  newIp.value = ''
  await saveWhitelist()
}

async function removeIp(ip: string) {
  whitelist.value = whitelist.value.filter(i => i !== ip)
  await saveWhitelist()
}

async function saveWhitelist() {
  whitelistLoading.value = true
  whitelistMsg.value = ''
  try {
    await api.post('/api/v1/system/ai-whitelist', { whitelist: whitelist.value })
    whitelistMsg.value = '白名单保存成功'
  } catch (e) {
    console.error('保存白名单失败:', e)
    whitelistMsg.value = '保存失败'
  } finally {
    whitelistLoading.value = false
    setTimeout(() => { whitelistMsg.value = '' }, 3000)
  }
}

onMounted(() => {
  loadConfig()
  loadWhitelist()
})
</script>

<template>
  <div class="h-full overflow-auto p-6 space-y-6">
    <div class="flex items-center gap-3 mb-6">
      <Settings class="h-8 w-8 text-primary" />
      <h1 class="text-3xl font-bold">系统设置</h1>
    </div>

    <Tabs default-value="honeypot" class="w-full">
      <TabsList class="grid w-full grid-cols-4">
        <TabsTrigger value="honeypot">
          <Shield class="h-4 w-4 mr-2" />
          蜜罐配置
        </TabsTrigger>
        <TabsTrigger value="switch">
          <Network class="h-4 w-4 mr-2" />
          交换机配置
        </TabsTrigger>
        <TabsTrigger value="ai">
          <Bot class="h-4 w-4 mr-2" />
          AI 配置
        </TabsTrigger>
        <TabsTrigger value="notification">
          <Bell class="h-4 w-4 mr-2" />
          通知配置
        </TabsTrigger>
      </TabsList>

      <!-- 蜜罐配置 -->
      <TabsContent value="honeypot">
        <Card>
          <CardHeader>
            <CardTitle>HFish 蜜罐配置</CardTitle>
          </CardHeader>
          <CardContent class="space-y-4">
            <form @submit.prevent="saveConfig" class="space-y-4">
              <div class="space-y-2">
                <Label for="hfish_url">HFish API 地址</Label>
                <Input
                  id="hfish_url"
                  v-model="systemConfig.hfish_url"
                  placeholder="http://192.168.1.100:4433/api/v1"
                />
              </div>
              <div class="space-y-2">
                <Label for="hfish_token">API Token</Label>
                <Input
                  id="hfish_token"
                  v-model="systemConfig.hfish_token"
                  type="password"
                  placeholder="请输入 HFish API Token"
                />
              </div>
              <Button type="submit" :disabled="loading">
                保存配置
              </Button>
            </form>
          </CardContent>
        </Card>
      </TabsContent>

      <!-- 交换机配置 -->
      <TabsContent value="switch">
        <Card>
          <CardHeader>
            <CardTitle>交换机配置</CardTitle>
          </CardHeader>
          <CardContent class="space-y-4">
            <form @submit.prevent="saveConfig" class="space-y-4">
              <div class="space-y-2">
                <Label for="switch_ip">交换机 IP</Label>
                <Input
                  id="switch_ip"
                  v-model="systemConfig.switch_ip"
                  placeholder="192.168.1.1"
                />
              </div>
              <div class="space-y-2">
                <Label for="switch_username">用户名</Label>
                <Input
                  id="switch_username"
                  v-model="systemConfig.switch_username"
                  placeholder="admin"
                />
              </div>
              <div class="space-y-2">
                <Label for="switch_password">密码</Label>
                <Input
                  id="switch_password"
                  v-model="systemConfig.switch_password"
                  type="password"
                  placeholder="请输入交换机密码"
                />
              </div>
              <Button type="submit" :disabled="loading">
                保存配置
              </Button>
            </form>
          </CardContent>
        </Card>
      </TabsContent>

      <!-- AI 配置 -->
      <TabsContent value="ai">
        <div class="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>AI 配置</CardTitle>
            </CardHeader>
            <CardContent class="space-y-4">
              <form @submit.prevent="saveConfig" class="space-y-4">
                <div class="flex items-center space-x-2">
                  <Switch
                    id="ai_enabled"
                    v-model:checked="systemConfig.ai_enabled"
                  />
                  <Label for="ai_enabled">启用 AI 功能</Label>
                </div>
                <div class="space-y-2">
                  <Label for="ai_url">AI API 地址</Label>
                <Input
                  id="ai_url"
                  v-model="systemConfig.ai_url"
                  placeholder="https://api.openai.com/v1"
                  :disabled="!systemConfig.ai_enabled"
                />
              </div>
              <div class="space-y-2">
                <Label for="ai_model">AI 模型</Label>
                <Input
                  id="ai_model"
                  v-model="systemConfig.ai_model"
                  placeholder="gpt-4"
                  :disabled="!systemConfig.ai_enabled"
                />
              </div>
              <Button type="submit" :disabled="loading">
                保存配置
              </Button>
            </form>
            </CardContent>
          </Card>

          <!-- AI 封禁白名单 -->
          <Card>
            <CardHeader>
              <CardTitle class="flex items-center gap-2">
                <Shield class="h-5 w-5 text-green-500" />
                AI 分析封禁白名单
              </CardTitle>
            </CardHeader>
            <CardContent class="space-y-4">
              <p class="text-sm text-muted-foreground">白名单中的 IP 不会被 AI 自动封禁。</p>

              <!-- 现有白名单 -->
              <div v-if="whitelist.length > 0" class="space-y-2">
                <div
                  v-for="ip in whitelist"
                  :key="ip"
                  class="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                >
                  <span class="font-mono">{{ ip }}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    class="h-6 w-6 p-0 text-destructive hover:text-destructive"
                    @click="removeIp(ip)"
                    :disabled="whitelistLoading"
                  >
                    <Trash2 class="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <p v-else class="text-sm text-muted-foreground">暂无白名单 IP</p>

              <!-- 添加新 IP -->
              <div class="flex gap-2">
                <Input
                  v-model="newIp"
                  placeholder="输入 IP 地址，如 192.168.0.4"
                  class="flex-1 font-mono"
                  @keyup.enter="addIp"
                />
                <Button @click="addIp" :disabled="whitelistLoading || !newIp.trim()">
                  <Plus class="h-4 w-4 mr-1" />
                  添加
                </Button>
              </div>

              <p v-if="whitelistMsg" class="text-sm" :class="whitelistMsg.includes('成功') ? 'text-green-600' : 'text-red-500'">
                {{ whitelistMsg }}
              </p>
            </CardContent>
          </Card>
        </div>
      </TabsContent>

      <!-- 通知配置 -->
      <TabsContent value="notification">
        <Card>
          <CardHeader>
            <CardTitle>通知配置</CardTitle>
          </CardHeader>
          <CardContent class="space-y-4">
            <p class="text-sm text-muted-foreground">通知配置功能即将上线</p>
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>
  </div>
</template>
