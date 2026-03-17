<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { api, apiCall } from '@/api/index'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import {
  Save,
  CheckCircle2,
  Circle,
  RotateCw,
  Trash2,
  Plus,
  Code,
  Link,
  Network,
  Bot,
  Activity,
  Bug,
  Flame,
  XCircle,
  Eye,
  EyeOff,
  Zap
} from 'lucide-vue-next'

const router = useRouter()
const route  = useRoute()

// 卡片引用
const hfishCardRef = ref<any>(null)
const switchCardRef = ref<any>(null)

const saving  = ref(false)
const status  = ref({ hfish_sync: false, nmap_scan: false, ai_analysis: false, acl_auto_ban: false })
let statusTimer: ReturnType<typeof setInterval>

const hfish   = ref({ host_port: '', api_key: '', sync_interval: 60, sync_enabled: false })
const nmap    = ref({ ip_ranges: '', arguments: '-sS -O -T5', scan_interval: 604800, scan_enabled: false, vuln_scripts_text: '{}' })
const aiCfg   = ref({ enabled: false, model: '', api_key: '', base_url: '', auto_ban: false })
const switches = ref<Array<{host: string, port: number, password: string, acl_number: number, enabled: boolean}>>([])
const switchStatusCfg = ref({ strict_mode: false })

// 新增交换机表单
const newSwitch = ref({ host: '', port: 23, password: '', acl_number: 30, enabled: true })

// 密码显示状态
const showSwitchPasswords = ref<Record<number, boolean>>({})
const testingSwitch = ref<number | null>(null)

// API Key 显示/隐藏状态
const showApiKey = ref(false)

// Feedback
const feedback = ref<{ show: boolean, text: string, type: 'success' | 'error' | 'none' }>({ show: false, text: '', type: 'none' })
function showFeedback(text: string, type: 'success' | 'error') {
  feedback.value = { show: true, text, type }
  setTimeout(() => { if (feedback.value.text === text) feedback.value.show = false }, 4000)
}

// Vuln rules UI
const newRuleTag     = ref('')
const newRuleScripts = ref('')
const osTagOptions   = ['windows', 'windows 10', 'windows 7', 'winserver', 'linux', 'macos', 'bsd']

const parsedVulnRules = computed<Record<string, string[]>>(() => {
  try { return JSON.parse(nmap.value.vuln_scripts_text) } catch { return {} }
})

function addVulnRule() {
  if (!newRuleTag.value || !newRuleScripts.value) return
  const rules = parsedVulnRules.value
  rules[newRuleTag.value] = newRuleScripts.value.split(',').map(s => s.trim()).filter(Boolean)
  nmap.value.vuln_scripts_text = JSON.stringify(rules, null, 2)
  newRuleTag.value = ''
  newRuleScripts.value = ''
}

function removeVulnRule(tag: string) {
  const rules = parsedVulnRules.value
  delete rules[tag]
  nmap.value.vuln_scripts_text = JSON.stringify(rules, null, 2)
}

// 交换机管理函数
function addSwitch() {
  if (!newSwitch.value.host) return
  switches.value.push({ ...newSwitch.value })
  newSwitch.value = { host: '', port: 23, password: '', acl_number: 30, enabled: true }
}

function removeSwitch(index: number) {
  switches.value.splice(index, 1)
}

async function testSwitch(sw: typeof switches.value[0], index: number) {
  testingSwitch.value = index
  try {
    const res: any = await api.post('/api/v1/defense/switch/test', {
      host: sw.host,
      port: sw.port,
      password: sw.password
    })
    if (res.reachable) {
      if (res.warning) {
        showFeedback(`交换机 ${sw.host}: ${res.warning}`, 'error')
      } else {
        showFeedback(`交换机 ${sw.host} 连接成功`, 'success')
      }
    } else {
      showFeedback(`交换机 ${sw.host} 连接失败`, 'error')
    }
  } catch (e: any) {
    showFeedback(e.message || '测试失败', 'error')
  } finally {
    testingSwitch.value = null
  }
}

function toggleSwitchPassword(index: number) {
  showSwitchPasswords.value[index] = !showSwitchPasswords.value[index]
}

async function loadStatus() {
  try {
    const d = await api.get<any>('/api/status')
    status.value = d
  } catch {}
}

async function loadSettings() {
  const d = await apiCall<any>(async () => await api.get<any>('/api/v1/settings'), { silent: true })
  if (d) {
    const sd = d.data ?? d
    if (sd.hfish) { Object.assign(hfish.value, sd.hfish); hfish.value.api_key = '' }
    if (sd.nmap)  {
      nmap.value.ip_ranges = Array.isArray(sd.nmap.ip_ranges) ? sd.nmap.ip_ranges.join(', ') : (sd.nmap.ip_ranges ?? '')
      nmap.value.arguments = sd.nmap.arguments ?? '-sS -O -T5'
      nmap.value.scan_interval = sd.nmap.scan_interval ?? 604800
      nmap.value.scan_enabled = sd.nmap.scan_enabled ?? false
      nmap.value.vuln_scripts_text = JSON.stringify(sd.nmap.vuln_scripts_by_tag ?? {}, null, 2)
    }
    if (sd.switches) {
      // 确保每个交换机都有enabled字段
      switches.value = sd.switches.map((sw: any) => ({
        host: sw.host || '',
        port: sw.port || 23,
        password: sw.password || '',
        acl_number: sw.acl_number || 30,
        enabled: sw.enabled !== undefined ? sw.enabled : true
      }))
    }
    if (sd.switch_status) {
      switchStatusCfg.value.strict_mode = !!sd.switch_status.strict_mode
    }
  }

  const ai = await apiCall<any>(async () => await api.get<any>('/api/v1/system/ai-config'), { silent: true })
  if (ai) {
    Object.assign(aiCfg.value, ai.data ?? ai)
    aiCfg.value.api_key = ''
  }
}

async function saveSettings() {
  saving.value = true
  try {
    const payload = {
      hfish: { ...hfish.value },
      nmap: {
        ...nmap.value,
        ip_ranges: nmap.value.ip_ranges.split(',').map(s => s.trim()).filter(Boolean),
        vuln_scripts_by_tag: parsedVulnRules.value,
      },
      switches: switches.value,
      switch_status: { ...switchStatusCfg.value },
    }
    await api.post('/api/v1/settings', payload)
    if (aiCfg.value.api_key) {
      await api.post('/api/v1/system/ai-config', aiCfg.value)
    } else {
      const a = { ...aiCfg.value }
      delete (a as any).api_key
      await api.post('/api/v1/system/ai-config', a)
    }
    showFeedback('系统设置已成功更新', 'success')
  } catch (e) {
    showFeedback(`更新失败: ${e instanceof Error ? e.message : '未知错误'}`, 'error')
  }
  saving.value = false
}

async function testHfish() {
  try {
    await api.post('/api/v1/defense/hfish/test', hfish.value)
    showFeedback('HFish 蜜罐服务连接测试成功', 'success')
  } catch {
    showFeedback('无法连接到 HFish 服务，请核对地址和密钥', 'error')
  }
}

onMounted(async () => {
  await loadSettings()
  loadStatus()
  statusTimer = setInterval(loadStatus, 15000)

  // 首次进入页面时处理聚焦参数
  await handleFocusByQuery()
})

onUnmounted(() => clearInterval(statusTimer))

function scrollToCard(target: string) {
  const normalizeEl = (raw: any): HTMLElement | null => {
    if (!raw) return null
    if (raw instanceof HTMLElement) return raw
    if (raw.$el instanceof HTMLElement) return raw.$el
    return null
  }

  let element: HTMLElement | null = null

  if (target === 'hfish') {
    element = normalizeEl(hfishCardRef.value) || document.getElementById('settings-hfish-card')
  } else if (target === 'switch') {
    element = normalizeEl(switchCardRef.value) || document.getElementById('settings-switch-card')
  }
  
  if (element) {
    const scrollContainer = document.querySelector('main.overflow-auto') as HTMLElement | null
    if (scrollContainer) {
      const containerRect = scrollContainer.getBoundingClientRect()
      const elementRect = element.getBoundingClientRect()
      const scrollTop = scrollContainer.scrollTop + (elementRect.top - containerRect.top) - 96
      scrollContainer.scrollTo({ top: Math.max(0, scrollTop), behavior: 'smooth' })
    } else {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }

    // 添加高亮效果
    element.classList.add('ring-2', 'ring-primary', 'ring-offset-2', 'ring-offset-background')
    setTimeout(() => {
      element?.classList.remove('ring-2', 'ring-primary', 'ring-offset-2', 'ring-offset-background')
    }, 3000)
  }
}

async function handleFocusByQuery() {
  const focusTarget = route.query.focus as string | undefined
  if (!focusTarget) return

  await nextTick()

  // 过渡动画和异步渲染期间，做多次尝试，避免偶发不聚焦
  const retryDelays = [0, 120, 280, 520]
  retryDelays.forEach((delay) => {
    setTimeout(() => {
      scrollToCard(focusTarget)
    }, delay)
  })
}

watch(
  () => [route.query.focus, route.query.t],
  async () => {
    await handleFocusByQuery()
  }
)

const chainItems = [
  { label: 'HFish 同步', key: 'hfish_sync' },
  { label: 'Nmap 扫描', key: 'nmap_scan' },
  { label: 'AI 分析', key: 'ai_analysis' },
  { label: 'ACL 封禁', key: 'acl_auto_ban' },
]
</script>

<template>
  <div class="p-6 max-w-4xl mx-auto space-y-6">
    <Card class="bg-card/40 border overflow-hidden">
      <CardHeader class="pb-4">
        <CardTitle class="text-[15px] font-bold flex items-center gap-2">
          <Activity :size="16" class="text-primary" />
          后台引擎运行状态
        </CardTitle>
        <Badge variant="outline" class="text-[10px] animate-pulse border-primary/20 text-primary">LIVE</Badge>
      </CardHeader>
      <CardContent>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div
            v-for="ci in chainItems"
            :key="ci.key"
            class="flex items-center gap-2 p-3 rounded-lg border bg-muted/5 transition-all"
            :class="(status as any)[ci.key] ? 'border-emerald-500/20 bg-emerald-500/5' : 'border-slate-500/20'"
          >
            <CheckCircle2 v-if="(status as any)[ci.key]" :size="16" class="text-emerald-500 shrink-0" />
            <Circle v-else :size="16" class="text-slate-600 shrink-0" />
            <span class="text-xs font-medium" :class="(status as any)[ci.key] ? 'text-emerald-400' : 'text-slate-500'">{{ ci.label }}</span>
          </div>
        </div>
      </CardContent>
    </Card>

    <Card id="settings-hfish-card" ref="hfishCardRef" class="border-border/50">
      <CardHeader>
        <CardTitle class="text-base font-bold flex items-center gap-2">
          <Flame :size="16" class="text-orange-500" />
          HFish 蜜罐集成
        </CardTitle>
        <CardDescription class="text-xs">配置 AimiGuard 与控制台集群的同步链接</CardDescription>
      </CardHeader>
      <CardContent class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="space-y-2">
            <Label class="text-xs font-semibold text-slate-400">控制台 API 地址</Label>
            <Input v-model="hfish.host_port" placeholder="10.0.0.5:4433" class="bg-black/20" />
          </div>
          <div class="space-y-2">
            <Label class="text-xs font-semibold text-slate-400">API 安全密钥</Label>
            <Input v-model="hfish.api_key" type="password" placeholder="••••••••••••" class="bg-black/20" />
          </div>
        </div>
        <div class="flex flex-wrap items-end gap-6 pt-2">
          <div class="space-y-2 flex-1 min-w-[200px]">
            <Label class="text-xs font-semibold text-slate-400">日志拉取频率 (秒)</Label>
            <Input v-model.number="hfish.sync_interval" type="number" class="bg-black/20" />
          </div>
          <div class="flex items-center gap-3 h-10 px-4 bg-muted/10 rounded-lg border border-border/30">
            <Switch v-model="hfish.sync_enabled" id="hfish-sync" />
            <Label for="hfish-sync" class="text-xs font-medium cursor-pointer">全自动实时同步</Label>
          </div>
          <Button variant="secondary" size="sm" @click="testHfish" class="h-10 bg-blue-500/10 text-blue-400 hover:bg-blue-500 hover:text-white border-blue-500/20">
            <Link :size="16" class="mr-2" /> 测试连接
          </Button>
        </div>
      </CardContent>
    </Card>

    <Card class="border-border/50">
      <CardHeader>
        <CardTitle class="text-base font-bold flex items-center gap-2">
          <Network :size="16" class="text-emerald-500" />
          Nmap 自动资产发现
        </CardTitle>
        <CardDescription class="text-xs">主动探测内部网络环境下的存活资产</CardDescription>
      </CardHeader>
      <CardContent class="space-y-6">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="space-y-2">
            <Label class="text-xs font-semibold text-slate-400">扫描目标地址段</Label>
            <Input v-model="nmap.ip_ranges" placeholder="192.168.1.0/24, 172.16.0.0/16" class="bg-black/20" />
          </div>
          <div class="space-y-2">
            <Label class="text-xs font-semibold text-slate-400">扫描策略参数</Label>
            <Input v-model="nmap.arguments" placeholder="-sS -O -T4" class="bg-black/20" />
          </div>
          <div class="space-y-2">
            <Label class="text-xs font-semibold text-slate-400">全网重扫周期 (秒)</Label>
            <Input v-model.number="nmap.scan_interval" type="number" class="bg-black/20" />
          </div>
          <div class="flex items-center gap-3 h-10 px-4 bg-muted/10 rounded-lg border mt-auto">
            <Switch v-model="nmap.scan_enabled" id="nmap-scan" />
            <Label for="nmap-scan" class="text-xs font-medium cursor-pointer">开启周期性重扫</Label>
          </div>
        </div>

        <div class="space-y-4 pt-2">
          <div class="flex items-center gap-2">
            <Bug class="h-4 w-4 text-amber-500" />
            <span class="text-sm font-bold">按资产标签分配漏洞扫描脚本</span>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-12 gap-3">
            <div class="md:col-span-3">
              <Select v-model="newRuleTag">
                <SelectTrigger class="bg-black/20 text-xs">
                  <SelectValue placeholder="操作系统标签" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="os in osTagOptions" :key="os" :value="os">{{ os }}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="md:col-span-6">
              <Input v-model="newRuleScripts" placeholder="smb-vuln-ms17-010, ftp-anon, ..." class="bg-black/20 h-10 text-xs" />
            </div>
            <div class="md:col-span-3">
              <Button @click="addVulnRule" variant="outline" class="w-full border-primary/20 text-primary hover:bg-primary/10">
                <Plus class="h-4 w-4 mr-2" /> 添加规则
              </Button>
            </div>
          </div>

          <div class="space-y-2">
            <div
              v-for="(scripts, tag) in parsedVulnRules"
              :key="tag"
              class="flex items-center justify-between p-2 pl-3 bg-white/5 rounded-lg border border-white/5"
            >
              <div class="flex items-center gap-3 overflow-hidden">
                <Badge variant="secondary" class="bg-primary/20 text-primary border-primary/10">{{ tag }}</Badge>
                <span class="text-[11px] text-slate-400 truncate">{{ scripts.join(', ') }}</span>
              </div>
              <Button variant="ghost" size="icon" @click="removeVulnRule(String(tag))" class="h-7 w-7 text-slate-500 hover:text-red-400">
                <Trash2 class="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>

          <Accordion type="single" collapsible class="border rounded-lg overflow-hidden">
            <AccordionItem value="json" class="border-0">
              <AccordionTrigger class="px-4 py-2 hover:no-underline hover:bg-white/5 text-xs text-slate-500">
                <div class="flex items-center gap-2"><Code class="h-3.5 w-3.5" /> 导出/编辑原生规则 JSON</div>
              </AccordionTrigger>
              <AccordionContent class="px-4 pb-4">
                <Textarea v-model="nmap.vuln_scripts_text" rows="5" class="bg-black/40 font-mono text-[11px] mt-2" />
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>
      </CardContent>
    </Card>

    <Card id="settings-switch-card" ref="switchCardRef" class="border-border/50">
      <CardHeader>
        <CardTitle class="text-base font-bold flex items-center gap-2">
          <Network :size="16" class="text-emerald-500" />
          交换机设备管理
        </CardTitle>
        <CardDescription class="text-xs">配置交换机设备用于ACL自动封禁</CardDescription>
      </CardHeader>
      <CardContent class="space-y-4">
        <!-- 添加新交换机 -->
        <div class="p-4 bg-gradient-to-r from-primary/5 to-transparent rounded-xl border border-primary/20">
          <div class="flex items-center gap-2 mb-3">
            <Plus class="h-4 w-4 text-primary" />
            <span class="text-sm font-bold">添加新设备</span>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-5 gap-3">
            <div class="md:col-span-2">
              <Label class="text-xs font-semibold text-slate-400 mb-1.5 block">IP 地址 *</Label>
              <Input v-model="newSwitch.host" placeholder="192.168.0.2" class="bg-black/30 h-10 border-white/10 focus:border-primary/50" />
            </div>
            <div>
              <Label class="text-xs font-semibold text-slate-400 mb-1.5 block">端口</Label>
              <Input v-model.number="newSwitch.port" type="number" class="bg-black/30 h-10 border-white/10 focus:border-primary/50" />
            </div>
            <div>
              <Label class="text-xs font-semibold text-slate-400 mb-1.5 block">密码</Label>
              <Input v-model="newSwitch.password" type="password" placeholder="••••••" class="bg-black/30 h-10 border-white/10 focus:border-primary/50" />
            </div>
            <div>
              <Label class="text-xs font-semibold text-slate-400 mb-1.5 block">ACL 编号</Label>
              <Input v-model.number="newSwitch.acl_number" type="number" class="bg-black/30 h-10 border-white/10 focus:border-primary/50" />
            </div>
          </div>
          <div class="flex justify-end mt-3">
            <Button @click="addSwitch" variant="default" size="sm" class="h-9 px-6 bg-primary hover:bg-primary/90 text-primary-foreground">
              <Plus class="h-4 w-4 mr-1.5" /> 
              添加设备
            </Button>
          </div>
        </div>

        <!-- 交换机列表 -->
        <div class="space-y-3">
          <div
            v-for="(sw, idx) in switches"
            :key="idx"
            class="group relative p-4 bg-gradient-to-r from-white/[0.02] to-transparent rounded-xl border border-white/10 hover:border-primary/30 transition-all duration-300"
            :class="!sw.enabled ? 'opacity-60' : ''"
          >
            <div class="flex items-start justify-between gap-4">
              <!-- 左侧：开关和基本信息 -->
              <div class="flex items-start gap-4 flex-1">
                <!-- 开关区域 -->
                <div class="flex flex-col items-center gap-1 pt-1">
                  <Switch 
                    :model-value="sw.enabled" 
                    @update:model-value="sw.enabled = $event"
                    class="data-[state=checked]:bg-emerald-500 data-[state=unchecked]:bg-slate-600 border-2 data-[state=unchecked]:border-slate-500"
                  />
                  <span class="text-[10px] text-muted-foreground">{{ sw.enabled ? '启用' : '禁用' }}</span>
                </div>

                <!-- 设备信息 -->
                <div class="flex-1 space-y-2">
                  <!-- 第一行：IP和状态 -->
                  <div class="flex items-center gap-3">
                    <div class="flex items-center gap-2">
                      <Network class="h-4 w-4 text-primary" />
                      <span class="text-base font-mono font-bold">{{ sw.host }}</span>
                    </div>
                    <Badge 
                      v-if="!sw.enabled" 
                      variant="outline" 
                      class="text-[10px] h-5 border-orange-500/50 text-orange-400 bg-orange-500/10"
                    >
                      已禁用
                    </Badge>
                    <Badge 
                      v-else
                      variant="outline"
                      class="text-[10px] h-5 border-emerald-500/50 text-emerald-400 bg-emerald-500/10"
                    >
                      已启用
                    </Badge>
                  </div>

                  <!-- 第二行：详细信息 -->
                  <div class="flex items-center gap-6 text-xs text-muted-foreground">
                    <div class="flex items-center gap-1.5">
                      <span class="text-slate-500">端口:</span>
                      <span class="font-mono font-medium text-foreground">{{ sw.port }}</span>
                    </div>
                    <div class="flex items-center gap-1.5">
                      <span class="text-slate-500">ACL:</span>
                      <Badge variant="secondary" class="text-[10px] h-5 px-2">{{ sw.acl_number }}</Badge>
                    </div>
                    <div class="flex items-center gap-1.5">
                      <span class="text-slate-500">密码:</span>
                      <div class="flex items-center gap-1">
                        <span v-if="showSwitchPasswords[idx]" class="font-mono text-foreground">{{ sw.password || '未设置' }}</span>
                        <span v-else class="font-mono text-slate-400">••••••</span>
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          @click="toggleSwitchPassword(idx)" 
                          class="h-6 w-6 text-muted-foreground hover:text-primary hover:bg-primary/10"
                        >
                          <Eye v-if="!showSwitchPasswords[idx]" :size="14" />
                          <EyeOff v-else :size="14" />
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 右侧：操作按钮 -->
              <div class="flex items-center gap-2">
                <Button 
                  variant="outline" 
                  size="sm" 
                  @click="testSwitch(sw, idx)" 
                  :disabled="testingSwitch === idx"
                  class="h-8 px-3 text-xs border-blue-500/30 text-blue-400 hover:bg-blue-500/10 hover:text-blue-300 hover:border-blue-500/50"
                >
                  <Zap v-if="testingSwitch === idx" class="h-3.5 w-3.5 mr-1.5 animate-pulse" />
                  <Link v-else class="h-3.5 w-3.5 mr-1.5" />
                  {{ testingSwitch === idx ? '测试中...' : '测试连接' }}
                </Button>
                <Button 
                  variant="ghost" 
                  size="sm"
                  @click="removeSwitch(idx)" 
                  class="h-8 w-8 text-slate-500 hover:text-red-400 hover:bg-red-500/10 border border-transparent hover:border-red-500/30"
                >
                  <Trash2 class="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          </div>

          <div v-if="switches.length === 0" class="text-center py-12 text-muted-foreground">
            <Network class="h-12 w-12 mx-auto mb-3 opacity-20" />
            <p class="text-sm font-medium">暂无交换机配置</p>
            <p class="text-xs mt-1">请在上方添加设备</p>
          </div>
        </div>

        <div class="text-xs space-y-2 mt-3 p-3 bg-amber-500/5 border border-amber-500/20 rounded-lg">
          <div class="flex items-center justify-between rounded-lg border border-border/40 bg-background/40 px-3 py-2 mb-2">
            <div>
              <p class="text-xs font-semibold">在线判定严格模式</p>
              <p class="text-[11px] text-muted-foreground mt-0.5">开启后需 Telnet 登录成功才判定为在线</p>
            </div>
            <Switch v-model="switchStatusCfg.strict_mode" id="switch-strict-mode" />
          </div>
          <div class="flex items-start gap-2">
            <span class="text-amber-400 mt-0.5">💡</span>
            <div class="flex-1">
              <p class="font-semibold text-amber-400 mb-1">配置说明</p>
              <p class="text-muted-foreground leading-relaxed">
                交换机配置用于 ACL 自动封禁功能。请确保交换机已开启 <span class="text-foreground font-medium">Telnet 服务</span>，并具有配置 ACL 的权限。禁用的交换机将不会参与自动封禁流程。
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>

    <Card class="border-border/50">
      <CardHeader>
        <CardTitle class="text-base font-bold flex items-center gap-2">
          <Bot class="h-4 w-4 text-primary" />
          AI 攻防决策大脑
        </CardTitle>
        <CardDescription class="text-xs">集成大语言模型以提供安全分析和自动化封禁处理</CardDescription>
      </CardHeader>
      <CardContent class="space-y-6">
        <div class="flex flex-wrap gap-4 p-4 bg-muted/10 rounded-xl border border-white/5">
          <div class="flex items-center gap-3">
            <Switch v-model="aiCfg.enabled" id="ai-enabled" />
            <Label for="ai-enabled" class="text-xs font-bold font-mono">ENABLED</Label>
          </div>
          <div class="w-px h-6 bg-white/10 mx-2 hidden sm:block"></div>
          <div class="flex items-center gap-3">
            <Switch v-model="aiCfg.auto_ban" id="auto-ban" />
            <Label for="auto-ban" class="text-xs font-bold text-red-500 font-mono">AUTO-BAN</Label>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
          <div class="space-y-2">
            <Label class="text-xs font-semibold text-slate-400">大模型型号 (Model)</Label>
            <Input v-model="aiCfg.model" placeholder="gpt-4o-mini" class="bg-black/20" />
          </div>
          <div class="space-y-2">
            <Label class="text-xs font-semibold text-slate-400">API 访问令牌 (Key)</Label>
            <div class="relative">
              <Input
                v-model="aiCfg.api_key"
                :type="showApiKey ? 'text' : 'password'"
                placeholder="••••••••••••"
                class="bg-black/20 pr-10"
              />
              <Button
                variant="ghost"
                size="icon"
                class="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 text-muted-foreground hover:text-foreground"
                @click="showApiKey = !showApiKey"
                type="button"
              >
                <Eye v-if="!showApiKey" :size="16" />
                <EyeOff v-else :size="16" />
              </Button>
            </div>
          </div>
          <div class="space-y-2">
            <Label class="text-xs font-semibold text-slate-400">自定义接口代理 (Base URL)</Label>
            <Input v-model="aiCfg.base_url" placeholder="https://api.openai.com/v1" class="bg-black/20" />
          </div>
        </div>
      </CardContent>
    </Card>

    <div class="sticky bottom-6 flex justify-center py-2 z-50 pointer-events-none">
      <div class="pointer-events-auto flex items-center gap-4 animate-in slide-in-from-bottom-2 duration-500">
        <Button
          size="lg"
          @click="saveSettings"
          :disabled="saving"
          class="px-10 h-14 rounded-full bg-primary hover:bg-primary/90 text-primary-foreground font-bold shadow-[0_10px_30px_rgba(0,229,255,0.3)] group"
        >
          <Save v-if="!saving" class="mr-2 h-5 w-5 group-hover:scale-110 transition-transform" />
          <RotateCw v-else class="mr-2 h-5 w-5 animate-spin" />
          保存全局配置
        </Button>
      </div>
    </div>

    <div
      v-if="feedback.show"
      class="fixed top-20 right-6 z-[100] p-4 rounded-xl border-l-[6px] shadow-2xl animate-in slide-in-from-right-4 duration-300 transform"
      :class="feedback.type === 'success' ? 'bg-emerald-500/10 border-l-emerald-500 text-emerald-300 border border-white/5' : 'bg-red-500/10 border-l-red-500 text-red-300 border border-white/5'"
    >
      <div class="flex items-center gap-3">
        <CheckCircle2 v-if="feedback.type === 'success'" class="h-5 w-5" />
        <XCircle v-else class="h-5 w-5" />
        <span class="text-sm font-bold tracking-wide">{{ feedback.text }}</span>
      </div>
    </div>
  </div>
</template>


