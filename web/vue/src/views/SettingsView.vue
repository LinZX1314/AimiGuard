<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api } from '@/api/index'
import { useUiStore } from '@/stores/ui'
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
  Info, 
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
  Key
} from 'lucide-vue-next'

const uiStore = useUiStore()
const saving  = ref(false)
const status  = ref({ hfish_sync: false, nmap_scan: false, ai_analysis: false, acl_auto_ban: false })
let statusTimer: ReturnType<typeof setInterval>

const hfish   = ref({ host_port: '', api_key: '', sync_interval: 60,     sync_enabled: false })
const nmap    = ref({ ip_ranges: '', arguments: '-sS -O -T5', scan_interval: 604800, scan_enabled: false, vuln_scripts_text: '{}' })
const aiCfg   = ref({ enabled: false, model: '', api_key: '', base_url: '', auto_ban: false, ban_threshold: 80 })

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

async function loadStatus() {
  try {
    const d = await api.get<any>('/api/status')
    status.value = d
  } catch {}
}

async function loadSettings() {
  try {
    const d = await api.get<any>('/api/v1/settings')
    const sd = d.data ?? d
    if (sd.hfish) { Object.assign(hfish.value, sd.hfish); hfish.value.api_key = '' }
    if (sd.nmap)  {
      nmap.value.ip_ranges        = Array.isArray(sd.nmap.ip_ranges) ? sd.nmap.ip_ranges.join(', ') : (sd.nmap.ip_ranges ?? '')
      nmap.value.arguments        = sd.nmap.arguments   ?? '-sS -O -T5'
      nmap.value.scan_interval    = sd.nmap.scan_interval ?? 604800
      nmap.value.scan_enabled     = sd.nmap.scan_enabled  ?? false
      nmap.value.vuln_scripts_text = JSON.stringify(sd.nmap.vuln_scripts_by_tag ?? {}, null, 2)
    }
  } catch(e) { console.error(e) }

  try {
    const ai = await api.get<any>('/api/v1/system/ai-config')
    Object.assign(aiCfg.value, ai.data ?? ai)
    aiCfg.value.api_key = ''
  } catch {}
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
    }
    await api.post('/api/v1/settings', payload)
    if (aiCfg.value.api_key) {
      await api.post('/api/v1/system/ai-config', aiCfg.value)
    } else {
      const a = { ...aiCfg.value }; delete (a as any).api_key
      await api.post('/api/v1/system/ai-config', a)
    }
    showFeedback('系统设置已成功更新', 'success')
  } catch(e) {
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

onMounted(() => {
  loadSettings()
  loadStatus()
  statusTimer = setInterval(loadStatus, 15000)
})
onUnmounted(() => clearInterval(statusTimer))

const chainItems = [
  { label: 'HFish 同步',  key: 'hfish_sync'   },
  { label: 'Nmap 扫描',   key: 'nmap_scan'    },
  { label: 'AI 分析',     key: 'ai_analysis'  },
  { label: 'ACL 封禁',    key: 'acl_auto_ban' },
]
</script>

<template>
  <div class="p-6 max-w-4xl mx-auto space-y-6">
    <!-- Theme selection -->
    <Card class="bg-card/40 border border-border/50 overflow-hidden">
      <CardHeader class="pb-4">
        <CardTitle class="text-[15px] font-bold flex items-center gap-2">
          <Activity :size="16" class="text-primary" />
          后台引擎运行状态
        </CardTitle>
        <Badge variant="outline" class="text-[10px] animate-pulse border-primary/20 text-primary">LIVE</Badge>
      </CardHeader>
      <CardContent>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div v-for="ci in chainItems" :key="ci.key" 
               class="flex items-center gap-2 p-3 rounded-lg border border-border/20 bg-muted/5 transition-all"
               :class="(status as any)[ci.key] ? 'border-emerald-500/20 bg-emerald-500/5' : 'border-slate-500/20'">
            <CheckCircle2 v-if="(status as any)[ci.key]" :size="16" class="text-emerald-500 shrink-0" />
            <Circle v-else :size="16" class="text-slate-600 shrink-0" />
            <span class="text-xs font-medium" :class="(status as any)[ci.key] ? 'text-emerald-400' : 'text-slate-500'">{{ ci.label }}</span>
          </div>
        </div>
      </CardContent>
    </Card>

    <Card class="bg-card/40 border border-border/50">
      <CardHeader>
        <CardTitle class="text-base font-bold flex items-center gap-2">
          <Settings :size="16" class="text-primary" />
          界面主题定制
        </CardTitle>
        <CardDescription class="text-xs">选择适合您工作环境的视觉风格</CardDescription>
      </CardHeader>
      <CardContent>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div 
            v-for="t in ['cyberpunk', 'indigo', 'forest', 'rose']" 
            :key="t"
            class="group cursor-pointer p-4 rounded-xl border-2 transition-all flex flex-col items-center gap-3"
            :class="[uiStore.theme === t ? 'border-primary bg-primary/10' : 'border-border/50 bg-muted/5 hover:border-border']"
            @click="uiStore.setTheme(t as any)"
          >
            <div class="w-full h-20 rounded-lg flex items-center justify-center relative overflow-hidden" 
                 :class="[
                   t === 'cyberpunk' ? 'bg-black shadow-[inset_0_0_20px_rgba(0,255,255,0.2)]' : 
                   t === 'indigo' ? 'bg-slate-900 border-indigo-500/20 shadow-[inset_0_0_20px_rgba(79,70,229,0.2)]' : 
                   t === 'forest' ? 'bg-[#051005] border-emerald-500/10 shadow-[inset_0_0_20px_rgba(16,185,129,0.1)]' : 
                   'bg-white border-slate-200 shadow-[0_0_15px_rgba(0,0,0,0.05)]'
                 ]"
            >
              <div class="flex flex-col gap-1 w-1/2">
                <div class="h-1.5 w-full rounded-full" :class="[
                   t === 'cyberpunk' ? 'bg-cyan-400' : 
                   t === 'indigo' ? 'bg-indigo-400' : 
                   t === 'forest' ? 'bg-emerald-400' : 'bg-slate-900'
                ]"></div>
                <div class="h-1 w-3/4 rounded-full" :class="t === 'rose' ? 'bg-slate-200' : 'bg-white/20'"></div>
              </div>
            </div>
            <span class="text-xs font-bold uppercase tracking-wider">
              {{ t === 'rose' ? 'Pure Monochrome' : t }}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>

    <!-- HFish Config -->
    <Card class="bg-card/40 border border-border/50">
      <CardHeader>
        <CardTitle class="text-base font-bold flex items-center gap-2">
          <Flame :size="16" class="text-orange-500" />
          HFish 蜜罐集成
        </CardTitle>
        <CardDescription class="text-xs">配置 AimiGuard 与控制台集群的同步链路</CardDescription>
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

    <!-- Nmap Config -->
    <Card class="bg-card/40 border border-border/50">
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
          <div class="flex items-center gap-3 h-10 px-4 bg-muted/10 rounded-lg border border-border/30 mt-auto">
            <Switch v-model="nmap.scan_enabled" id="nmap-scan" />
            <Label for="nmap-scan" class="text-xs font-medium cursor-pointer">开启周期性重扫</Label>
          </div>
        </div>

        <!-- Vuln scripts -->
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
            <div v-for="(scripts, tag) in parsedVulnRules" :key="tag" 
                 class="flex items-center justify-between p-2 pl-3 bg-white/5 rounded-lg border border-white/5">
              <div class="flex items-center gap-3 overflow-hidden">
                <Badge variant="secondary" class="bg-primary/20 text-primary border-primary/10">{{ tag }}</Badge>
                <span class="text-[11px] text-slate-400 truncate">{{ scripts.join(', ') }}</span>
              </div>
              <Button variant="ghost" size="icon" @click="removeVulnRule(String(tag))" class="h-7 w-7 text-slate-500 hover:text-red-400">
                <Trash2 class="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>

          <Accordion type="single" collapsible class="border rounded-lg border-border/30 overflow-hidden">
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

    <!-- AI Config -->
    <Card class="bg-card/40 border border-border/50">
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
            <Label for="ai-enabled" class="text-xs font-bold font-mono">ENABELD</Label>
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
            <Input v-model="aiCfg.api_key" type="password" placeholder="••••••••••••" class="bg-black/20" />
          </div>
          <div class="space-y-2">
            <Label class="text-xs font-semibold text-slate-400">自定义接口代理 (Base URL)</Label>
            <Input v-model="aiCfg.base_url" placeholder="https://api.openai.com/v1" class="bg-black/20" />
          </div>
          <div class="space-y-2">
            <Label class="text-xs font-semibold text-slate-400">自动化判定置信度阈值 (%)</Label>
            <div class="flex items-center gap-3">
              <Input v-model.number="aiCfg.ban_threshold" type="number" class="bg-black/20" />
              <div class="text-[10px] text-slate-500 italic max-w-[120px] leading-tight">高于此数值将不经由人类批准直接触发 ACL 封禁。</div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>

    <!-- Global Save Action -->
    <div class="sticky bottom-6 flex justify-center py-2 z-50 pointer-events-none">
      <div class="pointer-events-auto flex items-center gap-4 animate-in slide-in-from-bottom-2 duration-500">
        <Button size="lg" @click="saveSettings" :disabled="saving" 
                class="px-10 h-14 rounded-full bg-primary hover:bg-primary/90 text-primary-foreground font-bold shadow-[0_10px_30px_rgba(0,229,255,0.3)] group">
          <Save v-if="!saving" class="mr-2 h-5 w-5 group-hover:scale-110 transition-transform" />
          <RotateCw v-else class="mr-2 h-5 w-5 animate-spin" />
          保 存 全 局 设 置
        </Button>
      </div>
    </div>

    <!-- Custom Feedback Banner -->
    <div v-if="feedback.show" 
         class="fixed top-20 right-6 z-[100] p-4 rounded-xl border-l-[6px] shadow-2xl animate-in slide-in-from-right-4 duration-300 transform"
         :class="feedback.type === 'success' ? 'bg-emerald-500/10 border-l-emerald-500 text-emerald-300 border border-white/5' : 'bg-red-500/10 border-l-red-500 text-red-300 border border-white/5'">
      <div class="flex items-center gap-3">
        <CheckCircle2 v-if="feedback.type === 'success'" class="h-5 w-5" />
        <XCircle v-else class="h-5 w-5" />
        <span class="text-sm font-bold tracking-wide">{{ feedback.text }}</span>
      </div>
    </div>
  </div>
</template>
