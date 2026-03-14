<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api } from '@/api/index'

const saving  = ref(false)
const snack   = ref({ show: false, text: '', color: 'success' as string })
const status  = ref({ hfish_sync: false, nmap_scan: false, ai_analysis: false, acl_auto_ban: false })
let statusTimer: ReturnType<typeof setInterval>

const hfish   = ref({ host_port: '', api_key: '', sync_interval: 60,     sync_enabled: false })
const nmap    = ref({ ip_ranges: '', arguments: '-sS -O -T4', scan_interval: 604800, scan_enabled: false, vuln_scripts_text: '{}' })
const logging = ref({ api_request_log: true, sync_log: true, scan_log: true, ai_log: true, error_log: true })
const aiCfg   = ref({ enabled: false, model: '', api_key: '', base_url: '', auto_ban: false, ban_threshold: 80 })

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
      nmap.value.arguments        = sd.nmap.arguments   ?? '-sS -O -T4'
      nmap.value.scan_interval    = sd.nmap.scan_interval ?? 604800
      nmap.value.scan_enabled     = sd.nmap.scan_enabled  ?? false
      nmap.value.vuln_scripts_text = JSON.stringify(sd.nmap.vuln_scripts_by_tag ?? {}, null, 2)
    }
    if (sd.logging) Object.assign(logging.value, sd.logging)
    if (sd.status)  Object.assign(status.value,  sd.status)
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
      logging: logging.value,
    }
    await api.post('/api/v1/settings', payload)
    if (aiCfg.value.api_key) {
      await api.post('/api/v1/system/ai-config', aiCfg.value)
    } else {
      const a = { ...aiCfg.value }; delete (a as any).api_key
      await api.post('/api/v1/system/ai-config', a)
    }
    snack.value = { show: true, text: '保存成功', color: 'success' }
  } catch(e) {
    snack.value = { show: true, text: `保存失败: ${e instanceof Error ? e.message : ''}`, color: 'error' }
  }
  saving.value = false
}

async function testHfish() {
  try {
    await api.post('/api/v1/defense/hfish/test', hfish.value)
    snack.value = { show: true, text: 'HFish 连接测试成功', color: 'success' }
  } catch {
    snack.value = { show: true, text: '连接失败，请检查地址和 API Key', color: 'error' }
  }
}

onMounted(() => {
  loadSettings()
  loadStatus()
  statusTimer = setInterval(loadStatus, 10000)
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
  <v-container fluid class="pa-6" style="max-width:860px">
    <!-- Status -->
    <v-card class="mb-4">
      <v-card-title class="d-flex align-center">
        <v-icon start>mdi-information-outline</v-icon>
        模块状态
        <v-chip size="x-small" color="primary" class="ml-2">实时</v-chip>
      </v-card-title>
      <v-card-text>
        <v-row dense>
          <v-col cols="6" sm="3" v-for="ci in chainItems" :key="ci.key">
            <div class="d-flex align-center ga-2">
              <v-icon :color="(status as any)[ci.key] ? 'success' : 'grey'" size="16">
                {{ (status as any)[ci.key] ? 'mdi-check-circle' : 'mdi-circle-outline' }}
              </v-icon>
              <span class="text-body-2">{{ ci.label }}</span>
            </div>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- HFish -->
    <v-card class="mb-4">
      <v-card-title>HFish 蜜罐同步</v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="12" md="6">
            <v-text-field v-model="hfish.host_port" label="HFish 地址" placeholder="127.0.0.1:4433" class="mb-2" />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field v-model="hfish.api_key" label="API 密钥" type="password" placeholder="留空不修改" class="mb-2" />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field v-model.number="hfish.sync_interval" label="同步间隔（秒）" type="number" hint="默认 60 秒" persistent-hint />
          </v-col>
          <v-col cols="12" md="3" class="d-flex align-center">
            <v-switch v-model="hfish.sync_enabled" label="启用自动同步" color="primary" hide-details />
          </v-col>
          <v-col cols="12" md="3" class="d-flex align-center">
            <v-btn color="info" variant="tonal" @click="testHfish" prepend-icon="mdi-connection">测试连接</v-btn>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Nmap -->
    <v-card class="mb-4">
      <v-card-title>Nmap 网络扫描</v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="12" md="6">
            <v-text-field v-model="nmap.ip_ranges" label="扫描网段" placeholder="192.168.1.0/24" hint="多个用逗号分隔" persistent-hint class="mb-2" />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field v-model="nmap.arguments" label="扫描参数" placeholder="-sS -O -T4" class="mb-2" />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field v-model.number="nmap.scan_interval" label="扫描间隔（秒）" type="number" hint="默认 604800 秒（一周）" persistent-hint />
          </v-col>
          <v-col cols="12" md="6" class="d-flex align-center">
            <v-switch v-model="nmap.scan_enabled" label="启用自动扫描" color="primary" hide-details />
          </v-col>

          <!-- Vuln rules -->
          <v-col cols="12">
            <div class="text-subtitle-2 mb-2" style="color:#00E5FF">漏洞扫描规则</div>
            <v-row dense class="mb-3 align-center">
              <v-col cols="12" md="3">
                <v-select v-model="newRuleTag" :items="osTagOptions" label="OS 标签" hide-details />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field v-model="newRuleScripts" label="漏洞脚本（逗号分隔）" placeholder="smb-vuln-ms17-010, ftp-anon" hide-details />
              </v-col>
              <v-col cols="12" md="3">
                <v-btn color="primary" variant="tonal" block @click="addVulnRule" prepend-icon="mdi-plus">添加规则</v-btn>
              </v-col>
            </v-row>
            <div
              v-for="(scripts, tag) in parsedVulnRules"
              :key="tag"
              class="d-flex align-center ga-2 pa-2 mb-2"
              style="border:1px solid rgba(255,255,255,.08); border-radius:8px"
            >
              <v-chip color="primary" size="small">{{ tag }}</v-chip>
              <span class="text-medium-emphasis text-body-2 flex-grow-1">{{ scripts.join(', ') }}</span>
              <v-btn icon variant="text" size="x-small" color="error" @click="removeVulnRule(String(tag))">
                <v-icon size="14">mdi-delete-outline</v-icon>
              </v-btn>
            </div>
            <div v-if="!Object.keys(parsedVulnRules).length" class="text-medium-emphasis text-body-2 mb-2">暂无规则</div>

            <v-expansion-panels variant="accordion">
              <v-expansion-panel>
                <v-expansion-panel-title class="text-body-2">
                  <v-icon start size="small">mdi-code-json</v-icon>高级：直接编辑 JSON
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <v-textarea v-model="nmap.vuln_scripts_text" rows="6" hide-details style="font-family:monospace" />
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- AI Config -->
    <v-card class="mb-4">
      <v-card-title>AI 分析配置</v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="12" md="4">
            <v-switch v-model="aiCfg.enabled" label="启用 AI 分析" color="primary" hide-details />
          </v-col>
          <v-col cols="12" md="4">
            <v-switch v-model="aiCfg.auto_ban" label="AI 自动封禁" color="error" hide-details />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field v-model="aiCfg.model" label="模型名称" placeholder="gpt-4o-mini" class="mb-2" />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field v-model="aiCfg.api_key" label="API Key" type="password" placeholder="留空不修改" class="mb-2" />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field v-model="aiCfg.base_url" label="Base URL（可选）" placeholder="https://api.openai.com/v1" class="mb-2" />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model.number="aiCfg.ban_threshold"
              label="封禁置信度阈值 (%)"
              type="number"
              hint="AI 置信度超过此值时自动封禁"
              persistent-hint
            />
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Logging -->
    <v-card class="mb-4">
      <v-card-title><v-icon start>mdi-file-document-outline</v-icon>日志开关</v-card-title>
      <v-card-text>
        <v-row dense>
          <v-col cols="12" md="4">
            <v-switch v-model="logging.api_request_log" label="API 请求日志" color="primary" hide-details />
          </v-col>
          <v-col cols="12" md="4">
            <v-switch v-model="logging.sync_log"         label="同步日志"     color="primary" hide-details />
          </v-col>
          <v-col cols="12" md="4">
            <v-switch v-model="logging.scan_log"         label="扫描日志"     color="primary" hide-details />
          </v-col>
          <v-col cols="12" md="4">
            <v-switch v-model="logging.ai_log"           label="AI 日志"      color="primary" hide-details />
          </v-col>
          <v-col cols="12" md="4">
            <v-switch v-model="logging.error_log"        label="错误日志"     color="primary" hide-details />
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <v-btn color="primary" size="large" :loading="saving" @click="saveSettings" prepend-icon="mdi-content-save">
      保存设置
    </v-btn>

    <v-snackbar v-model="snack.show" :color="snack.color" timeout="3000">{{ snack.text }}</v-snackbar>
  </v-container>
</template>
