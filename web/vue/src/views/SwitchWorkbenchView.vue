<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { apiCall } from '@/api/index'
import {
  type SwitchWorkbenchAiSuggestion,
  type SwitchWorkbenchAiTurn,
  type SwitchWorkbenchCommandRunResult,
  type SwitchWorkbenchDevice,
  type SwitchWorkbenchDeviceConfig,
  type SwitchWorkbenchHistoryRecord,
  type SwitchWorkbenchScript,
  switchWorkbenchApi,
} from '@/api/switchWorkbench'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  CircleCheck,
  Clock,
  Cpu,
  Network,
  Play,
  Plus,
  Radar,
  Save,
  Server,
  Settings2,
  Shield,
  Terminal,
  Trash2,
  Unplug,
  WandSparkles,
  Zap,
} from 'lucide-vue-next'

type DeviceStatus = 'online' | 'degraded' | 'offline'
type RiskLevel = '低风险' | '只读' | '谨慎'
type LogKind = 'meta' | 'command' | 'output' | 'ai' | 'warning'
type CommandSource = 'manual' | 'ai' | 'script'
type BackendMode = 'live' | 'demo'

type VendorTemplate = {
  vendor: string
  model: string
  paging_disable: string
}

interface DeviceGroup {
  id: string
  label: string
  description: string
}

interface DeviceRecord {
  id: number
  name: string
  host: string
  port: number
  vendor: string
  model: string
  groupId: string
  status: DeviceStatus
  lastSeen: string
  tags: string[]
  checked: boolean
  protocol: 'telnet'
  aclNumber: number
  enabled: boolean
  readonlyOnly: boolean
  notes: string
}

interface TerminalLog {
  id: number
  kind: LogKind
  title: string
  content: string
  timestamp: string
}

interface QuickScript {
  id: string
  title: string
  description: string
  scope: 'single' | 'batch'
  risk: RiskLevel
  commands: string[]
}

interface ExecutionRecord {
  id: number
  title: string
  source: CommandSource
  target: string
  status: '成功' | '待确认' | '失败'
  summary: string
  createdAt: string
  output?: string
}

interface WorkbenchAiMessage {
  role: 'user' | 'assistant'
  content: string
}

interface EditableDeviceConfig {
  id: number
  name: string
  host: string
  port: number
  vendor: string
  model: string
  group_id: string
  password: string
  secret: string
  acl_number: number
  enabled: boolean
  readonly_only: boolean
  notes: string
  paging_disable: string
  tagsText: string
}

const vendorTemplates: Record<string, VendorTemplate> = {
  H3C: { vendor: 'H3C', model: 'S6520X', paging_disable: 'screen-length disable' },
  Huawei: { vendor: 'Huawei', model: 'S5735-L24', paging_disable: 'screen-length 0 temporary' },
  Ruijie: { vendor: 'Ruijie', model: 'RG-S5750C', paging_disable: 'terminal length 0' },
  Cisco: { vendor: 'Cisco', model: 'Catalyst 2960', paging_disable: 'terminal length 0' },
}

const deviceGroups: DeviceGroup[] = [
  { id: 'all', label: '全部设备', description: '展示所有已纳入工作台的交换机。' },
  { id: 'core', label: '核心区', description: '核心交换与边界汇聚。' },
  { id: 'aggregation', label: '汇聚区', description: '业务与楼层汇聚设备。' },
  { id: 'access', label: '接入区', description: '终端接入与边缘端口。' },
]

const demoDevices: DeviceRecord[] = [
  {
    id: 1,
    name: 'SW-Core-01',
    host: '10.24.100.11',
    port: 23,
    vendor: 'H3C',
    model: 'S6520X',
    groupId: 'core',
    status: 'online',
    lastSeen: '1 分钟前',
    tags: ['Telnet', '核心', 'ACL'],
    checked: true,
    protocol: 'telnet',
    aclNumber: 3001,
    enabled: true,
    readonlyOnly: true,
    notes: '核心交换机，建议优先使用只读巡检。',
  },
  {
    id: 2,
    name: 'SW-Agg-03',
    host: '10.24.101.23',
    port: 23,
    vendor: 'Ruijie',
    model: 'RG-S5750C',
    groupId: 'aggregation',
    status: 'degraded',
    lastSeen: '5 分钟前',
    tags: ['Telnet', '汇聚', '链路抖动'],
    checked: true,
    protocol: 'telnet',
    aclNumber: 3008,
    enabled: true,
    readonlyOnly: true,
    notes: '近一小时存在端口抖动。',
  },
  {
    id: 3,
    name: 'SW-Access-19',
    host: '10.24.110.19',
    port: 23,
    vendor: 'Huawei',
    model: 'S5735-L24',
    groupId: 'access',
    status: 'online',
    lastSeen: '刚刚',
    tags: ['Telnet', '接入', 'PoE'],
    checked: false,
    protocol: 'telnet',
    aclNumber: 3020,
    enabled: true,
    readonlyOnly: true,
    notes: '接入交换机，适合做端口健康巡检。',
  },
  {
    id: 4,
    name: 'SW-Access-27',
    host: '10.24.110.27',
    port: 23,
    vendor: 'Cisco',
    model: 'Catalyst 2960',
    groupId: 'access',
    status: 'offline',
    lastSeen: '22 分钟前',
    tags: ['Telnet', '接入', '离线'],
    checked: false,
    protocol: 'telnet',
    aclNumber: 3022,
    enabled: false,
    readonlyOnly: true,
    notes: '当前设备离线，建议先做连通性测试。',
  },
]

const demoScripts: QuickScript[] = [
  {
    id: 'health-check',
    title: '批量接口巡检',
    description: '读取接口摘要、错误计数和波动状态，适合批量健康检查。',
    scope: 'batch',
    risk: '只读',
    commands: ['display interface brief', 'display interface counters'],
  },
  {
    id: 'acl-audit',
    title: 'ACL 快速核查',
    description: '抽取 ACL 与命中统计，交给 AI 判断是否有误封、漏拦截。',
    scope: 'single',
    risk: '谨慎',
    commands: ['display acl all', 'display current-configuration | include acl'],
  },
  {
    id: 'baseline',
    title: '配置基线采样',
    description: '抓取当前配置、版本与保存状态，用于生成配置基线快照。',
    scope: 'batch',
    risk: '低风险',
    commands: ['display version', 'display current-configuration'],
  },
]

const demoHistory: ExecutionRecord[] = [
  {
    id: 1,
    title: 'AI 自动诊断接口异常',
    source: 'ai',
    target: 'SW-Agg-03',
    status: '成功',
    summary: '发现 2 个端口 CRC 飙升，建议先核查光模块与链路质量。',
    createdAt: '09:42:18',
  },
  {
    id: 2,
    title: '批量接口巡检',
    source: 'script',
    target: '2 台交换机',
    status: '成功',
    summary: '完成 2/2 台设备检测，1 台存在高负载端口。',
    createdAt: '09:36:02',
  },
  {
    id: 3,
    title: '手动执行 ACL 查询',
    source: 'manual',
    target: 'SW-Core-01',
    status: '待确认',
    summary: 'AI 已生成策略建议，等待运维确认是否继续执行下一条命令。',
    createdAt: '09:31:44',
  },
]

const quickCommands = [
  'display interface brief',
  'display current-configuration',
  'display acl all',
  'display mac-address',
]

const backendMode = ref<BackendMode>('demo')
const devices = ref<DeviceRecord[]>([...demoDevices])
const quickScripts = ref<QuickScript[]>([...demoScripts])
const executionRecords = ref<ExecutionRecord[]>([...demoHistory])
const aiSuggestions = ref<SwitchWorkbenchAiSuggestion[]>([])
const aiConversation = ref<WorkbenchAiMessage[]>([])
const aiSummary = ref('')
const aiNextSteps = ref<string[]>([])
const terminalLogs = ref<TerminalLog[]>([
  {
    id: 1,
    kind: 'meta',
    title: '会话初始化',
    content: '已载入 AI交换机工作台，可通过 Telnet 建立会话并保留操作记录。',
    timestamp: '09:30:11',
  },
  {
    id: 2,
    kind: 'output',
    title: '设备摘要',
    content: 'SW-Core-01 在线，Telnet:23，可进入只读巡检模式。',
    timestamp: '09:30:12',
  },
  {
    id: 3,
    kind: 'ai',
    title: 'AI 提示',
    content: '建议先执行 display interface brief 与 display acl all，快速识别端口异常与策略漂移。',
    timestamp: '09:30:16',
  },
])

const configManagerOpen = ref(false)
const configDeleteConfirmOpen = ref(false)
const configItems = ref<EditableDeviceConfig[]>([])
const selectedConfigId = ref<number | null>(null)
const configSaving = ref(false)
const configLoading = ref(false)
const configTesting = ref(false)
const configValidationMessage = ref('')
const configForm = ref<EditableDeviceConfig>(createEmptyConfig(1))

const selectedGroup = ref('all')
const selectedDeviceId = ref(1)
const selectedRecordSource = ref<'all' | CommandSource>('all')
const commandInput = ref('display interface brief')
const aiPrompt = ref('帮我检查这台交换机是否存在 ACL 漂移和异常 down 口。')
const running = ref(false)
const detailOpen = ref(false)
const autoExecuteReadonly = ref(false)
const connectionStatus = ref('未测试')
const connectionStatusTone = ref<'default' | 'success' | 'warning'>('default')
const testingConnection = ref(false)
let logSeed = terminalLogs.value.length
let recordSeed = executionRecords.value.length

const selectedDevice = computed(() => devices.value.find((device) => device.id === selectedDeviceId.value) ?? null)
const checkedDevices = computed(() => devices.value.filter((device) => device.checked))
const onlineCount = computed(() => devices.value.filter((device) => device.status === 'online').length)
const degradedCount = computed(() => devices.value.filter((device) => device.status === 'degraded').length)
const availableGroupOptions = computed(() => deviceGroups.filter((group) => group.id === 'all' || devices.value.some((device) => device.groupId === group.id)))
const visibleDevices = computed(() => selectedGroup.value === 'all' ? devices.value : devices.value.filter((device) => device.groupId === selectedGroup.value))
const filteredExecutionRecords = computed(() => selectedRecordSource.value === 'all' ? executionRecords.value : executionRecords.value.filter((record) => record.source === selectedRecordSource.value))
const selectedDeviceRecordCount = computed(() => executionRecords.value.filter((record) => record.target === selectedDevice.value?.name).length)
const selectedDeviceSelected = computed(() => checkedDevices.value.some((device) => device.id === selectedDevice.value?.id))
const configPanelItems = computed(() => configItems.value)

function nowLabel() {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false })
}

function createEmptyConfig(id: number): EditableDeviceConfig {
  return {
    id,
    name: `SW-${String(id).padStart(2, '0')}`,
    host: '',
    port: 23,
    vendor: 'Generic',
    model: 'Telnet Switch',
    group_id: 'access',
    password: '',
    secret: '',
    acl_number: 30,
    enabled: true,
    readonly_only: true,
    notes: '',
    paging_disable: '',
    tagsText: 'Telnet',
  }
}

function nextConfigId() {
  return configItems.value.length ? Math.max(...configItems.value.map((item) => item.id)) + 1 : 1
}

function validateIpFormat(ip: string) {
  if (!/^\d{1,3}(\.\d{1,3}){3}$/.test(ip)) return false
  return ip.split('.').every((part) => Number(part) >= 0 && Number(part) <= 255)
}

function validateCurrentConfig() {
  const payload = editableToPayload(configForm.value)
  if (!payload.name) return '交换机名称不能为空'
  if (!payload.host) return 'IP 地址不能为空'
  if (!validateIpFormat(payload.host)) return 'IP 地址格式不正确'
  if (!payload.port || payload.port < 1 || payload.port > 65535) return '端口范围应为 1-65535'
  return ''
}

function applyVendorTemplate(vendorKey: string) {
  const template = vendorTemplates[vendorKey]
  if (!template) return
  configForm.value.vendor = template.vendor
  if (!configForm.value.model || configForm.value.model === 'Telnet Switch') {
    configForm.value.model = template.model
  }
  configForm.value.paging_disable = template.paging_disable
  configValidationMessage.value = ''
}

function pushLog(kind: LogKind, title: string, content: string) {
  terminalLogs.value.push({
    id: ++logSeed,
    kind,
    title,
    content,
    timestamp: nowLabel(),
  })
}

function syncAiTurn(turn: SwitchWorkbenchAiTurn, prompt: string) {
  aiConversation.value.push({ role: 'user', content: prompt })
  aiConversation.value.push({ role: 'assistant', content: turn.answer })
  aiConversation.value = aiConversation.value.slice(-8)
  aiSummary.value = turn.summary
  aiNextSteps.value = turn.next_steps
  aiSuggestions.value = turn.suggested_commands
}

function buildLocalAiTurn(prompt: string, device: DeviceRecord, commandOutput = '', command = ''): SwitchWorkbenchAiTurn {
  const suggested_commands = localAiSuggestions(commandOutput ? `${prompt}\n${commandOutput}` : prompt, device)
  const summary = command ? simulateAiInsight(command, device) : `AI 判断：已理解 ${device.name} 的诊断意图，建议先从只读命令建立上下文。`
  const answer = commandOutput
    ? `${summary}\n\n我已结合最新回显给出下一步建议，优先继续执行只读命令确认异常范围。`
    : `我已理解你的意图：${prompt}\n\n建议先执行 ${suggested_commands[0]?.command || 'display interface brief'} 建立诊断上下文，再根据回显继续细化分析。`
  return {
    answer,
    summary,
    next_steps: suggested_commands.slice(0, 3).map((item) => item.command),
    suggested_commands,
  }
}

async function requestAiTurn(prompt: string, device: DeviceRecord, commandOutput = '', command = '') {
  if (backendMode.value === 'live') {
    const result = await apiCall(() => switchWorkbenchApi.analyzeTurn({
      device_id: device.id,
      prompt,
      command_output: commandOutput,
      command,
      conversation: aiConversation.value,
    }), { silent: true })
    if (result) return result
  }
  return buildLocalAiTurn(prompt, device, commandOutput, command)
}

function recordStatusLabel(status: 'success' | 'pending' | 'failed' | '成功' | '待确认' | '失败') {
  if (status === 'success' || status === '成功') return '成功'
  if (status === 'failed' || status === '失败') return '失败'
  return '待确认'
}

function sourceLabel(source: CommandSource) {
  if (source === 'manual') return '手工'
  if (source === 'ai') return 'AI'
  return '脚本'
}

function statusTone(status: DeviceStatus) {
  if (status === 'online') return 'bg-emerald-400 shadow-[0_0_16px_rgba(74,222,128,0.6)]'
  if (status === 'degraded') return 'bg-amber-400 shadow-[0_0_16px_rgba(251,191,36,0.55)]'
  return 'bg-rose-400 shadow-[0_0_16px_rgba(251,113,133,0.55)]'
}

function statusLabel(status: DeviceStatus) {
  if (status === 'online') return '在线'
  if (status === 'degraded') return '不稳定'
  return '离线'
}

function mapApiDevice(device: SwitchWorkbenchDevice): DeviceRecord {
  return {
    id: device.id,
    name: device.name,
    host: device.host,
    port: device.port,
    vendor: device.vendor,
    model: device.model,
    groupId: device.group_id,
    status: device.status,
    lastSeen: device.last_seen,
    tags: device.tags,
    checked: device.enabled,
    protocol: 'telnet',
    aclNumber: device.acl_number,
    enabled: device.enabled,
    readonlyOnly: device.readonly_only,
    notes: device.notes,
  }
}

function mapApiScript(script: SwitchWorkbenchScript): QuickScript {
  return {
    id: script.id,
    title: script.title,
    description: script.description,
    scope: script.scope,
    risk: script.risk,
    commands: script.commands,
  }
}

function mapApiHistory(record: SwitchWorkbenchHistoryRecord): ExecutionRecord {
  return {
    id: record.id,
    title: `${sourceLabel(record.source)}执行 ${record.command_text}`,
    source: record.source,
    target: record.device_name,
    status: recordStatusLabel(record.status),
    summary: record.summary,
    createdAt: record.created_at,
    output: record.stdout,
  }
}

function mapApiConfig(item: SwitchWorkbenchDeviceConfig): EditableDeviceConfig {
  return {
    ...item,
    tagsText: item.tags.join(', '),
  }
}

function editableToPayload(item: EditableDeviceConfig) {
  return {
    id: item.id,
    name: item.name.trim(),
    host: item.host.trim(),
    port: Number(item.port || 23),
    vendor: item.vendor.trim() || 'Generic',
    model: item.model.trim() || 'Telnet Switch',
    group_id: item.group_id,
    password: item.password,
    secret: item.secret,
    acl_number: Number(item.acl_number || 30),
    enabled: item.enabled,
    readonly_only: item.readonly_only,
    notes: item.notes.trim(),
    paging_disable: item.paging_disable.trim(),
    tags: item.tagsText.split(',').map((tag) => tag.trim()).filter(Boolean),
  }
}

function configToDeviceRecord(item: EditableDeviceConfig, index: number): DeviceRecord {
  const payload = editableToPayload(item)
  return {
    id: index + 1,
    name: payload.name,
    host: payload.host,
    port: payload.port,
    vendor: payload.vendor,
    model: payload.model,
    groupId: payload.group_id,
    status: payload.enabled ? 'online' : 'offline',
    lastSeen: payload.enabled ? '配置已更新' : '已禁用',
    tags: payload.tags.length ? payload.tags : ['Telnet'],
    checked: payload.enabled,
    protocol: 'telnet',
    aclNumber: payload.acl_number,
    enabled: payload.enabled,
    readonlyOnly: payload.readonly_only,
    notes: payload.notes,
  }
}

function simulateOutput(command: string, device: DeviceRecord) {
  const lowered = command.toLowerCase()

  if (lowered.includes('interface brief')) {
    return `Interface            Status    Protocol  InUti OutUti\nGE1/0/1              UP        UP        12%   10%\nGE1/0/8              DOWN      DOWN      0%    0%\nGE1/0/21             UP        UP        76%   81%\nGE1/0/24             UP        UP        38%   35%\n\n设备 ${device.name} 检测到 1 个 down 口，1 个高利用率口。`
  }

  if (lowered.includes('acl')) {
    return `ACL 3001 inbound matched 1283 packets\nACL 3012 inbound matched 0 packets\nACL 3999 deny ip any any matched 17 packets\n\n发现 1 条长时间无命中 ACL，建议核对策略漂移或业务下线情况。`
  }

  if (lowered.includes('current-configuration')) {
    return `sysname ${device.name}\ninterface GigabitEthernet1/0/21\n port link-type access\n port default vlan 210\n qos trust dscp\n\nacl number 3001\n rule 5 deny ip source 10.24.8.0 0.0.0.255 destination any\n\n本次输出已截断，仅展示关键片段。`
  }

  if (lowered.includes('version')) {
    return `${device.vendor} ${device.model}\nSoftware Version 7.1.070\nBootRom Version 2.3.1\n\n设备版本信息已采集完成。`
  }

  return `命令 ${command} 已在 ${device.name} 上执行完成。\nTelnet 会话稳定，回显可继续交给 AI 助手解析。`
}

function simulateAiInsight(command: string, device: DeviceRecord) {
  const lowered = command.toLowerCase()

  if (lowered.includes('interface brief')) {
    return `AI 判断：${device.name} 当前存在接口波动与局部高利用率，建议进一步执行 display interface counters 查看 CRC / error 增长趋势。`
  }

  if (lowered.includes('acl')) {
    return 'AI 判断：ACL 命中分布不均，存在“配置仍在但业务已迁移”的可能，建议联动基线快照做差异比对。'
  }

  if (lowered.includes('current-configuration')) {
    return 'AI 判断：已识别接入口 VLAN 与 ACL 片段，建议将当前输出归档为配置快照，并继续查询保存状态。'
  }

  if (lowered.includes('version')) {
    return 'AI 判断：版本信息已采集，可进一步核查型号、镜像版本与变更基线。'
  }

  return 'AI 判断：当前输出未发现明显危险动作，可继续追加只读命令进行下一轮诊断。'
}

function localAiSuggestions(prompt: string, device: DeviceRecord | null): SwitchWorkbenchAiSuggestion[] {
  const lowered = prompt.toLowerCase()
  const suggestions: SwitchWorkbenchAiSuggestion[] = []

  const add = (command: string, title: string, risk: RiskLevel, reason: string) => {
    suggestions.push({
      id: `local-${suggestions.length + 1}`,
      command,
      title,
      risk,
      reason,
      auto_runnable: risk !== '谨慎',
    })
  }

  if (lowered.includes('acl') || prompt.includes('策略')) {
    add('display acl all', '查看 ACL 列表', '只读', '先确认 ACL 内容、命中与空规则。')
    add('display current-configuration | include acl', '抓取 ACL 配置片段', '谨慎', '便于与基线做差异对比。')
  }
  if (prompt.includes('接口') || prompt.includes('端口') || lowered.includes('down')) {
    add('display interface brief', '查看接口状态', '只读', '先定位 down 口与高利用率端口。')
    add('display interface counters', '查看接口计数器', '只读', '进一步确认 CRC / error 是否增长。')
  }
  if (prompt.includes('配置') || prompt.includes('基线') || prompt.includes('版本')) {
    add('display version', '查看版本信息', '低风险', '建立设备画像，便于后续排障。')
  }

  if (!suggestions.length) {
    add('display interface brief', `${device?.name ?? '当前设备'} 接口总览`, '只读', '默认先读取接口摘要，快速建立问题上下文。')
    add('display current-configuration', '配置快照采样', '只读', '采样当前配置，供 AI 进一步分析。')
  }

  return suggestions.slice(0, 4)
}

function upsertExecutionRecord(record: ExecutionRecord) {
  executionRecords.value = [record, ...executionRecords.value.filter((item) => item.id !== record.id)]
}

function pushExecutionRecordFromRun(result: SwitchWorkbenchCommandRunResult) {
  const record: ExecutionRecord = {
    id: result.run_id ?? ++recordSeed,
    title: `${sourceLabel(result.source)}执行 ${result.command}`,
    source: result.source,
    target: result.device.name,
    status: recordStatusLabel(result.status),
    summary: result.analysis,
    createdAt: result.created_at,
    output: result.output,
  }
  upsertExecutionRecord(record)
}

function selectGroup(groupId: string) {
  selectedGroup.value = groupId
  const firstVisible = (groupId === 'all' ? devices.value : devices.value.filter((device) => device.groupId === groupId))[0]
  if (firstVisible) selectedDeviceId.value = firstVisible.id
}

function setActiveDevice(id: number) {
  selectedDeviceId.value = id
  const device = devices.value.find((item) => item.id === id)
  if (!device) return
  connectionStatus.value = '未测试'
  connectionStatusTone.value = 'default'
  aiConversation.value = []
  aiSummary.value = ''
  aiNextSteps.value = []
  aiSuggestions.value = []
  pushLog('meta', '切换设备', `当前激活设备已切换为 ${device.name}（${device.host}:${device.port}）。`)
}

function toggleDeviceSelection(id: number) {
  devices.value = devices.value.map((device) => (
    device.id === id
      ? { ...device, checked: !device.checked }
      : device
  ))
}

function toggleSelectedDeviceChoice() {
  const device = selectedDevice.value
  if (!device) return
  toggleDeviceSelection(device.id)
}

function clearTerminal() {
  terminalLogs.value = [{
    id: ++logSeed,
    kind: 'meta',
    title: '日志已清空',
    content: '已保留设备选择状态，新的命令与分析结果将从此处继续记录。',
    timestamp: nowLabel(),
  }]
}

function applyConfigToForm(item: EditableDeviceConfig) {
  configForm.value = { ...item }
  selectedConfigId.value = item.id
  configValidationMessage.value = ''
}

function startCreateConfig() {
  const item = createEmptyConfig(nextConfigId())
  configItems.value = [item, ...configItems.value]
  applyConfigToForm(item)
}

function removeSelectedConfig() {
  if (!selectedConfigId.value) return
  configDeleteConfirmOpen.value = true
}

function confirmRemoveSelectedConfig() {
  if (!selectedConfigId.value) return
  configItems.value = configItems.value.filter((item) => item.id !== selectedConfigId.value)
  const next = configItems.value[0] ?? createEmptyConfig(nextConfigId())
  if (!configItems.value.length) configItems.value = [next]
  applyConfigToForm(next)
  configDeleteConfirmOpen.value = false
}

function saveDraftConfig() {
  const normalized = editableToPayload(configForm.value)
  const validation = validateCurrentConfig()
  configValidationMessage.value = validation
  if (validation) {
    pushLog('warning', '配置未保存', validation)
    return
  }

  configItems.value = configItems.value.map((item) => item.id === configForm.value.id ? { ...configForm.value } : item)
  if (!configItems.value.some((item) => item.id === configForm.value.id)) {
    configItems.value.unshift({ ...configForm.value })
  }
  selectedConfigId.value = configForm.value.id
  pushLog('meta', '配置草稿已更新', `${normalized.name} 的交换机配置已写入本地草稿。`)
}

function syncDevicesFromConfigs(items: EditableDeviceConfig[]) {
  devices.value = items.map((item, index) => configToDeviceRecord(item, index))
  if (!devices.value.some((device) => device.id === selectedDeviceId.value)) {
    selectedDeviceId.value = devices.value[0]?.id ?? 1
  }
}

async function loadConfigManagerData(preferredId?: number) {
  configLoading.value = true
  let items: EditableDeviceConfig[] = []

  if (backendMode.value === 'live') {
    const result = await apiCall(() => switchWorkbenchApi.deviceConfigs(), { silent: true, errorMsg: '加载交换机配置失败' })
    if (result) {
      items = result.map(mapApiConfig)
    }
  }

  if (!items.length) {
    items = devices.value.map((device, index) => ({
      id: index + 1,
      name: device.name,
      host: device.host,
      port: device.port,
      vendor: device.vendor,
      model: device.model,
      group_id: device.groupId,
      password: '',
      secret: '',
      acl_number: device.aclNumber,
      enabled: device.enabled,
      readonly_only: device.readonlyOnly,
      notes: device.notes,
      paging_disable: '',
      tagsText: device.tags.join(', '),
    }))
  }

  if (!items.length) items = [createEmptyConfig(1)]
  configItems.value = items
  const initial = items.find((item) => item.id === preferredId) ?? items[0]
  applyConfigToForm(initial)
  configLoading.value = false
}

async function openConfigManager() {
  await loadConfigManagerData(selectedDevice.value?.id)
  configManagerOpen.value = true
}

async function testConfigConnection() {
  const validation = validateCurrentConfig()
  configValidationMessage.value = validation
  if (validation) return

  const payload = editableToPayload(configForm.value)
  configTesting.value = true

  if (backendMode.value === 'live') {
    const result = await apiCall(() => switchWorkbenchApi.testDevice({
      host: payload.host,
      port: payload.port,
      password: payload.password,
    }), { errorMsg: '测试交换机连接失败' })

    if (result) {
      configValidationMessage.value = result.warning ? `测试结果：${result.warning}` : `测试结果：${result.host}:${result.port} 连接正常`
    }
  } else {
    await new Promise((resolve) => window.setTimeout(resolve, 420))
    configValidationMessage.value = '演示模式下模拟测试通过'
  }

  configTesting.value = false
}

async function commitConfigItems() {
  const payload = configItems.value.map(editableToPayload)
  const validation = validateCurrentConfig()
  configValidationMessage.value = validation
  if (validation || !payload.every((item) => item.name && item.host)) {
    pushLog('warning', '保存被阻止', validation || '请先补齐所有交换机的名称与 IP 地址。')
    return
  }

  configSaving.value = true

  if (backendMode.value === 'live') {
    const result = await apiCall(() => switchWorkbenchApi.saveDeviceConfigs({ devices: payload }), { errorMsg: '保存交换机配置失败' })
    if (result?.items) {
      configItems.value = result.items.map(mapApiConfig)
      await hydrateWorkbench()
      pushLog('meta', '交换机配置已保存', `已将 ${result.items.length} 台交换机写入系统配置。`)
      configManagerOpen.value = false
    }
  } else {
    syncDevicesFromConfigs(configItems.value)
    pushLog('meta', '演示模式配置已应用', `已在演示模式中更新 ${configItems.value.length} 台交换机。`)
    configManagerOpen.value = false
  }

  configSaving.value = false
}

async function hydrateWorkbench() {
  const [liveDevices, liveScripts, liveHistory] = await Promise.all([
    apiCall(() => switchWorkbenchApi.devices(true), { silent: true }),
    apiCall(() => switchWorkbenchApi.scripts(), { silent: true }),
    apiCall(() => switchWorkbenchApi.history(24), { silent: true }),
  ])

  if (liveDevices && liveDevices.length) {
    backendMode.value = 'live'
    devices.value = liveDevices.map(mapApiDevice)
    selectedDeviceId.value = devices.value[0]?.id ?? selectedDeviceId.value
    pushLog('meta', '后端已接入', '已从真实接口加载交换机列表与执行记录。')
  }

  if (liveScripts?.length) quickScripts.value = liveScripts.map(mapApiScript)
  if (liveHistory?.length) executionRecords.value = liveHistory.map(mapApiHistory)
}

async function testSelectedDeviceConnection() {
  const device = selectedDevice.value
  if (!device || testingConnection.value) return

  testingConnection.value = true
  connectionStatus.value = '测试中...'
  connectionStatusTone.value = 'default'
  pushLog('meta', '连通性测试', `正在测试 ${device.host}:${device.port} 的 Telnet 可达性。`)

  if (backendMode.value === 'live') {
    const result = await apiCall(() => switchWorkbenchApi.testDevice({ device_id: device.id }), { silent: true })
    if (result) {
      connectionStatus.value = result.warning ? '可达但需确认' : '连接正常'
      connectionStatusTone.value = result.warning ? 'warning' : 'success'
      pushLog(result.warning ? 'warning' : 'meta', '测试结果', result.warning ?? `Telnet 到 ${result.host}:${result.port} 握手正常。`)
      testingConnection.value = false
      return
    }
  }

  await new Promise((resolve) => window.setTimeout(resolve, 500))
  connectionStatus.value = device.status === 'offline' ? '设备离线' : '连接正常'
  connectionStatusTone.value = device.status === 'offline' ? 'warning' : 'success'
  pushLog(device.status === 'offline' ? 'warning' : 'meta', '测试结果', device.status === 'offline' ? '设备当前离线，建议核查网络路径。' : '演示模式下模拟连通性测试通过。')
  testingConnection.value = false
}

async function runCommand(command: string, source: CommandSource) {
  const device = selectedDevice.value
  const normalized = command.trim()
  if (!normalized || !device || running.value) return

  running.value = true
  pushLog('command', source === 'manual' ? '手动命令' : source === 'ai' ? 'AI 建议命令' : '脚本命令', `${device.name}> ${normalized}`)

  if (backendMode.value === 'live') {
    const result = await apiCall(() => switchWorkbenchApi.runCommand({
      device_id: device.id,
      command: normalized,
      source,
    }), { silent: true })

    if (result) {
      pushLog(result.status === 'failed' ? 'warning' : 'output', '设备回显', result.output)
      pushLog(result.status === 'failed' ? 'warning' : 'ai', 'AI 分析', result.analysis)
      pushExecutionRecordFromRun(result)
      const turn = await requestAiTurn(aiPrompt.value.trim() || '请分析刚刚的设备回显并给下一步建议', device, result.output, normalized)
      syncAiTurn(turn, `已执行命令：${normalized}`)
      running.value = false
      return
    }
  }

  await new Promise((resolve) => window.setTimeout(resolve, 520))
  const output = simulateOutput(normalized, device)
  const aiInsight = simulateAiInsight(normalized, device)
  pushLog('output', '设备回显', output)
  pushLog('ai', 'AI 分析', aiInsight)
  upsertExecutionRecord({
    id: ++recordSeed,
    title: source === 'manual' ? `手动执行 ${normalized}` : source === 'ai' ? 'AI 自动诊断接口异常' : `脚本执行 · ${normalized}`,
    source,
    target: device.name,
    status: source === 'manual' ? '待确认' : '成功',
    summary: aiInsight,
    createdAt: nowLabel(),
    output,
  })
  const turn = await requestAiTurn(aiPrompt.value.trim() || '请分析刚刚的设备回显并给下一步建议', device, output, normalized)
  syncAiTurn(turn, `已执行命令：${normalized}`)
  running.value = false
}

async function runSuggestion(suggestion: SwitchWorkbenchAiSuggestion) {
  commandInput.value = suggestion.command
  await runCommand(suggestion.command, 'ai')
}

async function runAllSuggestions() {
  for (const suggestion of aiSuggestions.value) {
    await runSuggestion(suggestion)
  }
}

async function runQuickScript(script: QuickScript) {
  if (running.value) return
  const targets = script.scope === 'batch' ? checkedDevices.value : (selectedDevice.value ? [selectedDevice.value] : [])
  if (!targets.length) {
    pushLog('warning', '执行阻断', '当前没有可用目标设备，请至少勾选一台交换机。')
    return
  }

  pushLog('meta', '批量脚本启动', `${script.title} 已发往 ${targets.length} 台设备，脚本包含 ${script.commands.length} 条只读命令。`)

  if (backendMode.value === 'live') {
    const result = await apiCall(() => switchWorkbenchApi.runScript({
      script_id: script.id,
      device_ids: targets.map((device) => device.id),
    }), { silent: true })

    if (result) {
      pushLog('meta', '批量脚本结果', result.summary)
      result.items.forEach((item) => {
        pushLog(item.status === 'failed' ? 'warning' : 'output', `${item.device.name} · ${item.command}`, item.output)
        pushLog(item.status === 'failed' ? 'warning' : 'ai', 'AI 汇总', item.analysis)
        pushExecutionRecordFromRun(item)
      })
      return
    }
  }

  for (const command of script.commands) {
    await runCommand(command, 'script')
  }
}

function applyQuickCommand(command: string) {
  commandInput.value = command
}

async function submitManualCommand() {
  await runCommand(commandInput.value, 'manual')
}

async function askAiAssistant() {
  const device = selectedDevice.value
  const prompt = aiPrompt.value.trim()
  if (!prompt || !device || running.value) return

  pushLog('meta', 'AI 意图', prompt)
  const turn = await requestAiTurn(prompt, device)
  syncAiTurn(turn, prompt)
  pushLog('ai', 'AI 策略', turn.answer)
  if (turn.suggested_commands[0]) {
    commandInput.value = turn.suggested_commands[0].command
  }
  if (autoExecuteReadonly.value && turn.suggested_commands.every((item) => item.auto_runnable)) {
    await runAllSuggestions()
  }
}

onMounted(async () => {
  await hydrateWorkbench()
})
</script>

<template>
  <div class="switch-workbench-page h-full overflow-hidden px-6 py-6">
    <div class="mb-6 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
      <div class="space-y-3">
        <div class="flex flex-wrap items-center gap-2">
          <div class="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <Zap class="h-3.5 w-3.5" />
            AI交换机工作台
          </div>
          <div
            class="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium"
            :class="backendMode === 'live' ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300' : 'border-amber-400/30 bg-amber-400/10 text-amber-200'"
          >
            <CircleCheck v-if="backendMode === 'live'" class="h-3.5 w-3.5" />
            <Radar v-else class="h-3.5 w-3.5" />
            {{ backendMode === 'live' ? '真实接口模式' : '演示回退模式' }}
          </div>
        </div>
        <div>
          <h1 class="text-3xl font-black tracking-tight text-foreground md:text-[2.1rem]">Telnet 联动 · 多交换机 AI 运维工作台</h1>
          <p class="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">
            左侧管理交换机资产与批量目标，中间承载 Telnet 会话与人工命令，右侧由 AI 生成建议命令、快捷脚本与留痕记录。现在已补上交换机配置管理入口，可以直接维护设备清单。
          </p>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Card class="border-primary/15 bg-card/70 backdrop-blur-xl"><CardContent class="px-4 py-3"><div class="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">交换机</div><div class="mt-2 text-2xl font-black">{{ devices.length }}</div></CardContent></Card>
        <Card class="border-emerald-400/20 bg-card/70 backdrop-blur-xl"><CardContent class="px-4 py-3"><div class="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">在线</div><div class="mt-2 text-2xl font-black text-emerald-400">{{ onlineCount }}</div></CardContent></Card>
        <Card class="border-amber-400/20 bg-card/70 backdrop-blur-xl"><CardContent class="px-4 py-3"><div class="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">不稳定</div><div class="mt-2 text-2xl font-black text-amber-400">{{ degradedCount }}</div></CardContent></Card>
        <Card class="border-primary/15 bg-card/70 backdrop-blur-xl"><CardContent class="px-4 py-3"><div class="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">批量目标</div><div class="mt-2 text-2xl font-black">{{ checkedDevices.length }}</div></CardContent></Card>
      </div>
    </div>

    <div class="grid h-[calc(100vh-13rem)] grid-cols-1 gap-4 xl:grid-cols-[320px_minmax(0,1fr)_390px]">
      <Card class="flex min-h-0 flex-col overflow-hidden border-white/10 bg-slate-950/65 text-slate-100 shadow-[0_24px_80px_rgba(2,8,23,0.45)] backdrop-blur-2xl">
        <CardHeader class="border-b border-white/10 pb-4">
          <div class="flex items-center justify-between gap-3">
            <div>
              <CardTitle class="flex items-center gap-2 text-base text-slate-50"><Server class="h-4 w-4 text-primary" />多交换机资产</CardTitle>
              <CardDescription class="mt-1 text-slate-400">分组查看、批量勾选、切换工作会话。</CardDescription>
            </div>
            <div class="flex items-center gap-2">
              <Button size="sm" variant="outline" class="border-white/10 bg-white/5 text-slate-100 hover:bg-white/10" @click="openConfigManager"><Settings2 class="h-4 w-4" />管理交换机</Button>
              <Badge variant="outline" class="border-primary/30 bg-primary/10 text-primary">{{ checkedDevices.length }} 已选</Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent class="flex min-h-0 flex-1 flex-col gap-4 p-4">
          <div class="grid grid-cols-2 gap-2">
            <button v-for="group in availableGroupOptions" :key="group.id" type="button" class="rounded-2xl border px-3 py-3 text-left transition-all duration-300" :class="selectedGroup === group.id ? 'border-primary/40 bg-primary/12 shadow-[0_0_0_1px_rgba(0,255,255,0.14)]' : 'border-white/8 bg-white/[0.04] hover:border-white/15 hover:bg-white/[0.07]'" @click="selectGroup(group.id)">
              <div class="text-sm font-semibold text-slate-100">{{ group.label }}</div>
              <div class="mt-1 text-[11px] leading-5 text-slate-400">{{ group.description }}</div>
            </button>
          </div>
          <ScrollArea class="min-h-0 flex-1 pr-3">
            <div class="space-y-3">
              <button v-for="device in visibleDevices" :key="device.id" type="button" class="group w-full rounded-[22px] border p-4 text-left transition-all duration-300" :class="device.id === selectedDeviceId ? 'border-primary/40 bg-primary/12 shadow-[0_0_0_1px_rgba(0,255,255,0.14)]' : 'border-white/10 bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.06]'" @click="setActiveDevice(device.id)">
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <div class="flex items-center gap-2"><span class="text-sm font-semibold text-slate-50">{{ device.name }}</span><span class="h-2.5 w-2.5 rounded-full" :class="statusTone(device.status)"></span></div>
                    <div class="mt-1 text-xs text-slate-400">{{ device.vendor }} · {{ device.model }}</div>
                  </div>
                  <label class="flex items-center gap-2 text-[11px] text-slate-400" @click.stop>
                    <input :checked="device.checked" type="checkbox" class="h-3.5 w-3.5 rounded border-white/20 bg-transparent" @change="toggleDeviceSelection(device.id)" />
                    批量
                  </label>
                </div>
                <div class="mt-4 flex flex-wrap gap-2">
                  <Badge variant="outline" class="border-white/10 bg-black/20 text-slate-200">{{ device.host }}:{{ device.port }}</Badge>
                  <Badge variant="outline" class="border-primary/25 bg-primary/10 text-primary">{{ device.protocol }}</Badge>
                  <Badge variant="outline" class="border-white/10 bg-white/5 text-slate-300">{{ statusLabel(device.status) }}</Badge>
                </div>
                <div class="mt-4 flex flex-wrap gap-2"><span v-for="tag in device.tags" :key="tag" class="rounded-full border border-white/8 bg-white/[0.05] px-2 py-1 text-[11px] text-slate-300">{{ tag }}</span></div>
                <div class="mt-4 flex items-center justify-between text-[11px] text-slate-500"><span>{{ device.lastSeen }}</span><span>ACL {{ device.aclNumber }}</span></div>
              </button>
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      <div class="flex min-h-0 flex-col gap-4">
        <Card class="overflow-hidden border-primary/15 bg-card/65 backdrop-blur-xl">
          <CardContent class="p-0">
            <div v-if="selectedDevice" class="grid gap-0 lg:grid-cols-[1.55fr_1fr]">
              <div class="border-b border-border/60 p-5 lg:border-b-0 lg:border-r">
                <div class="flex items-center gap-2 text-xs uppercase tracking-[0.28em] text-primary/80"><Network class="h-3.5 w-3.5" />当前激活设备</div>
                <div class="mt-4 flex flex-wrap items-center gap-3"><h2 class="text-2xl font-black tracking-tight">{{ selectedDevice.name }}</h2><Badge variant="outline" class="border-primary/20 bg-primary/10 text-primary">Telnet 会话</Badge><Badge variant="outline" class="border-border bg-background/50">{{ selectedDevice.vendor }}</Badge></div>
                <div class="mt-3 flex flex-wrap gap-2 text-sm text-muted-foreground"><span>{{ selectedDevice.host }}:{{ selectedDevice.port }}</span><span>·</span><span>{{ selectedDevice.model }}</span><span>·</span><span>ACL {{ selectedDevice.aclNumber }}</span></div>
                <div class="mt-4 flex flex-wrap items-center gap-2">
                  <Button variant="outline" class="border-border/70 bg-background/60" @click="detailOpen = true"><Cpu class="h-4 w-4" />设备详情</Button>
                  <Button variant="outline" class="border-border/70 bg-background/60" :disabled="testingConnection" @click="testSelectedDeviceConnection"><Activity class="h-4 w-4" />{{ testingConnection ? '测试中...' : '测试连接' }}</Button>
                  <Button variant="outline" class="border-border/70 bg-background/60" @click="toggleSelectedDeviceChoice"><CheckCircle2 class="h-4 w-4" />{{ selectedDeviceSelected ? '移出批量' : '加入批量' }}</Button>
                </div>
              </div>
              <div class="p-5">
                <div class="flex items-center gap-2 text-xs uppercase tracking-[0.28em] text-muted-foreground"><Shield class="h-3.5 w-3.5 text-primary" />工作台状态</div>
                <div class="mt-4 space-y-3">
                  <div class="rounded-2xl border border-border/60 bg-background/45 p-3"><div class="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">连接状态</div><div class="mt-2 text-sm font-semibold" :class="connectionStatusTone === 'success' ? 'text-emerald-400' : connectionStatusTone === 'warning' ? 'text-amber-300' : 'text-foreground'">{{ connectionStatus }}</div></div>
                  <div class="rounded-2xl border border-border/60 bg-background/45 p-3"><div class="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">历史留痕</div><div class="mt-2 text-sm font-semibold">{{ selectedDeviceRecordCount }} 条记录</div></div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card class="flex min-h-0 flex-1 flex-col overflow-hidden border-white/10 bg-[#06101f]/90 text-slate-100 shadow-[0_24px_80px_rgba(2,8,23,0.55)]">
          <CardHeader class="border-b border-white/10 pb-4">
            <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div><CardTitle class="flex items-center gap-2 text-base text-slate-50"><Terminal class="h-4 w-4 text-primary" />Telnet 会话终端</CardTitle><CardDescription class="mt-1 text-slate-400">AI 与人工共用一条操作链路，所有回显保留到记录中心。</CardDescription></div>
              <div class="flex flex-wrap items-center gap-2"><Button variant="outline" class="border-white/10 bg-white/5 text-slate-100 hover:bg-white/10" @click="clearTerminal">清空回显</Button><Button class="bg-primary/90 text-primary-foreground hover:bg-primary" :disabled="running" @click="submitManualCommand"><Play class="h-4 w-4" />{{ running ? '执行中...' : '执行命令' }}</Button></div>
            </div>
          </CardHeader>
          <CardContent class="grid min-h-0 flex-1 gap-4 p-4 lg:grid-rows-[minmax(0,1fr)_auto]">
            <ScrollArea class="terminal-screen min-h-0 rounded-[24px] border border-cyan-400/15 bg-[#020817]/80 p-4 pr-6">
              <div class="space-y-3">
                <div v-for="entry in terminalLogs" :key="entry.id" class="rounded-2xl border px-4 py-3" :class="entry.kind === 'command' ? 'border-cyan-400/20 bg-cyan-400/6' : entry.kind === 'ai' ? 'border-violet-400/20 bg-violet-400/8' : entry.kind === 'warning' ? 'border-amber-400/20 bg-amber-400/8' : 'border-white/8 bg-white/[0.03]'">
                  <div class="mb-2 flex items-center justify-between gap-3 text-[11px] uppercase tracking-[0.25em]"><span class="text-slate-300">{{ entry.title }}</span><span class="text-slate-500">{{ entry.timestamp }}</span></div>
                  <pre class="terminal-text whitespace-pre-wrap break-all text-[13px] leading-6 text-slate-100">{{ entry.content }}</pre>
                </div>
              </div>
            </ScrollArea>
            <div class="space-y-3 rounded-[24px] border border-white/10 bg-white/[0.03] p-4">
              <div class="flex flex-wrap gap-2"><button v-for="command in quickCommands" :key="command" type="button" class="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs text-slate-300 transition hover:border-primary/30 hover:text-primary" @click="applyQuickCommand(command)">{{ command }}</button></div>
              <div class="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]"><Input v-model="commandInput" class="border-white/10 bg-black/25 text-slate-100 placeholder:text-slate-500" placeholder="输入命令，如 display interface brief" /><Button class="min-w-[132px] bg-primary/90 text-primary-foreground hover:bg-primary" :disabled="running" @click="submitManualCommand">手动执行</Button></div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div class="flex min-h-0 flex-col gap-4">
        <Card class="overflow-hidden border-white/10 bg-slate-950/65 text-slate-100 shadow-[0_24px_80px_rgba(2,8,23,0.45)] backdrop-blur-2xl">
          <CardHeader class="border-b border-white/10 pb-4">
            <CardTitle class="flex items-center gap-2 text-base text-slate-50"><Bot class="h-4 w-4 text-primary" />AI 协同助手</CardTitle>
            <CardDescription class="text-slate-400">生成命令建议、人机共审，并把最新回显持续回流给 AI 做多轮诊断。</CardDescription>
          </CardHeader>
          <CardContent class="space-y-4 p-4">
            <Textarea v-model="aiPrompt" class="min-h-[120px] border-white/10 bg-black/20 text-slate-100 placeholder:text-slate-500" placeholder="例如：帮我批量检查这些交换机的接口健康和 ACL 命中情况。" />
            <div class="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-3">
              <div>
                <div class="text-sm font-medium text-slate-100">只读建议自动执行</div>
                <div class="text-xs text-slate-400">仅对 AI 标记为安全的只读命令自动串行执行。</div>
              </div>
              <Switch v-model:checked="autoExecuteReadonly" />
            </div>
            <Button class="w-full bg-primary/90 text-primary-foreground hover:bg-primary" :disabled="running" @click="askAiAssistant"><WandSparkles class="h-4 w-4" />{{ running ? 'AI 正在诊断...' : '开始多轮诊断' }}</Button>

            <div v-if="aiSummary" class="rounded-[22px] border border-cyan-400/20 bg-cyan-400/10 p-4">
              <div class="text-sm font-semibold text-cyan-100">当前诊断结论</div>
              <p class="mt-2 text-xs leading-6 text-cyan-50/90">{{ aiSummary }}</p>
              <div v-if="aiNextSteps.length" class="mt-3 flex flex-wrap gap-2">
                <Badge v-for="step in aiNextSteps" :key="step" variant="outline" class="border-cyan-300/20 bg-cyan-300/10 text-cyan-100">{{ step }}</Badge>
              </div>
            </div>

            <div v-if="aiConversation.length" class="space-y-3 rounded-[22px] border border-white/10 bg-white/[0.03] p-4">
              <div class="text-sm font-semibold text-slate-100">AI 诊断对话</div>
              <div class="space-y-2">
                <div v-for="(message, index) in aiConversation" :key="`${message.role}-${index}`" class="rounded-2xl border px-3 py-3" :class="message.role === 'assistant' ? 'border-violet-400/20 bg-violet-400/8' : 'border-white/10 bg-black/15'">
                  <div class="mb-1 text-[11px] uppercase tracking-[0.24em]" :class="message.role === 'assistant' ? 'text-violet-200' : 'text-slate-400'">{{ message.role === 'assistant' ? 'AI' : '你' }}</div>
                  <div class="text-sm leading-6 text-slate-100 whitespace-pre-wrap">{{ message.content }}</div>
                </div>
              </div>
            </div>

            <div v-if="aiSuggestions.length" class="space-y-3 rounded-[22px] border border-violet-400/20 bg-violet-400/8 p-4">
              <div class="flex items-center justify-between gap-3">
                <div class="text-sm font-semibold text-violet-100">AI 建议命令</div>
                <Button variant="outline" class="border-violet-300/20 bg-violet-300/10 text-violet-50 hover:bg-violet-300/20" @click="runAllSuggestions">全部执行</Button>
              </div>
              <div class="space-y-2">
                <div v-for="suggestion in aiSuggestions" :key="suggestion.id" class="rounded-2xl border border-white/10 bg-black/15 p-3">
                  <div class="flex items-start justify-between gap-3">
                    <div>
                      <div class="text-sm font-semibold text-slate-100">{{ suggestion.title }}</div>
                      <div class="mt-1 text-[11px] text-slate-400">{{ suggestion.reason }}</div>
                    </div>
                    <Badge variant="outline" class="border-white/10 bg-white/5 text-slate-100">{{ suggestion.risk }}</Badge>
                  </div>
                  <div class="mt-3 rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 font-mono text-[12px] text-cyan-200">{{ suggestion.command }}</div>
                  <div class="mt-3 flex gap-2">
                    <Button size="sm" class="bg-primary/90 text-primary-foreground hover:bg-primary" @click="runSuggestion(suggestion)">执行</Button>
                    <Button size="sm" variant="outline" class="border-white/10 bg-transparent text-slate-100 hover:bg-white/5" @click="commandInput = suggestion.command">写入输入框</Button>
                  </div>
                </div>
              </div>
            </div>

            <div class="rounded-[22px] border border-violet-400/20 bg-violet-400/8 p-4"><div class="flex items-center gap-2 text-sm font-semibold text-violet-100"><AlertTriangle class="h-4 w-4" />安全执行边界</div><p class="mt-2 text-xs leading-6 text-violet-100/80">当前工作台对后端真实执行默认启用只读命令门禁，先支持 display / show / dis / ping 这类巡检命令，为后续审批流与命令白名单预留扩展点。</p></div>
          </CardContent>
        </Card>

        <Card class="overflow-hidden border-white/10 bg-slate-950/65 text-slate-100 shadow-[0_24px_80px_rgba(2,8,23,0.45)] backdrop-blur-2xl">
          <CardHeader class="border-b border-white/10 pb-4"><div class="flex items-center justify-between gap-3"><div><CardTitle class="flex items-center gap-2 text-base text-slate-50"><Shield class="h-4 w-4 text-primary" />快捷脚本</CardTitle><CardDescription class="text-slate-400">一键发起单台或多台交换机的标准化检测。</CardDescription></div><Badge variant="outline" class="border-primary/30 bg-primary/10 text-primary">先 A 后 B</Badge></div></CardHeader>
          <CardContent class="space-y-3 p-4">
            <button v-for="script in quickScripts" :key="script.id" type="button" class="w-full rounded-[20px] border border-white/10 bg-white/[0.03] p-4 text-left transition hover:border-primary/30 hover:bg-primary/8" @click="runQuickScript(script)">
              <div class="flex items-start justify-between gap-3"><div><div class="text-sm font-semibold text-slate-50">{{ script.title }}</div><div class="mt-1 text-xs leading-5 text-slate-400">{{ script.description }}</div></div><Badge variant="outline" class="border-white/10 bg-black/20 text-slate-200">{{ script.scope === 'batch' ? '批量' : '单台' }}</Badge></div>
              <div class="mt-3 flex flex-wrap gap-2"><Badge variant="outline" class="border-primary/25 bg-primary/10 text-primary">{{ script.risk }}</Badge><Badge variant="outline" class="border-white/10 bg-black/20 text-slate-300">{{ script.commands.length }} 条命令</Badge></div>
            </button>
          </CardContent>
        </Card>

        <Card class="flex min-h-0 flex-1 flex-col overflow-hidden border-white/10 bg-slate-950/65 text-slate-100 shadow-[0_24px_80px_rgba(2,8,23,0.45)] backdrop-blur-2xl">
          <CardHeader class="border-b border-white/10 pb-4"><div class="flex items-center justify-between gap-3"><div><CardTitle class="flex items-center gap-2 text-base text-slate-50"><Clock class="h-4 w-4 text-primary" />执行记录</CardTitle><CardDescription class="text-slate-400">记录 AI / 人工 / 脚本链路的所有执行摘要。</CardDescription></div><div class="w-32"><Select v-model="selectedRecordSource"><SelectTrigger class="border-white/10 bg-black/20 text-xs text-slate-100"><SelectValue placeholder="来源过滤" /></SelectTrigger><SelectContent><SelectItem value="all">全部来源</SelectItem><SelectItem value="manual">手工</SelectItem><SelectItem value="ai">AI</SelectItem><SelectItem value="script">脚本</SelectItem></SelectContent></Select></div></div></CardHeader>
          <CardContent class="min-h-0 flex-1 p-4"><ScrollArea class="h-full pr-3"><div class="space-y-3"><div v-for="record in filteredExecutionRecords" :key="record.id" class="rounded-[20px] border border-white/10 bg-white/[0.03] p-4"><div class="flex items-start justify-between gap-3"><div><div class="text-sm font-semibold text-slate-50">{{ record.title }}</div><div class="mt-1 text-xs text-slate-400">目标：{{ record.target }}</div></div><Badge variant="outline" class="border-white/10 bg-black/20 text-slate-200">{{ record.status }}</Badge></div><div class="mt-3 text-xs leading-5 text-slate-300">{{ record.summary }}</div><div class="mt-3 flex items-center gap-2 text-[11px] text-slate-500"><span>{{ sourceLabel(record.source) }}</span><span>·</span><span>{{ record.createdAt }}</span></div></div></div></ScrollArea></CardContent>
        </Card>
      </div>
    </div>

    <Sheet :open="detailOpen" @update:open="(value) => detailOpen = value">
      <SheetContent side="right" class="w-full overflow-y-auto border-white/10 bg-slate-950/96 text-slate-100 sm:max-w-xl">
        <SheetHeader>
          <SheetTitle class="flex items-center gap-2 text-slate-50"><Server class="h-4 w-4 text-primary" />设备详情</SheetTitle>
          <SheetDescription class="text-slate-400">展示交换机连接参数、执行边界和运维画像，便于后续接入设备编辑能力。</SheetDescription>
        </SheetHeader>
        <div v-if="selectedDevice" class="mt-6 space-y-4">
          <div class="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
            <div class="flex items-center justify-between gap-3"><div><div class="text-lg font-semibold text-slate-50">{{ selectedDevice.name }}</div><div class="mt-1 text-sm text-slate-400">{{ selectedDevice.vendor }} · {{ selectedDevice.model }}</div></div><span class="rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs text-slate-200">{{ statusLabel(selectedDevice.status) }}</span></div>
            <div class="mt-4 grid gap-3 sm:grid-cols-2">
              <div class="rounded-2xl border border-white/8 bg-black/20 p-3"><div class="text-[11px] uppercase tracking-[0.24em] text-slate-500">连接地址</div><div class="mt-2 font-mono text-sm text-slate-100">{{ selectedDevice.host }}:{{ selectedDevice.port }}</div></div>
              <div class="rounded-2xl border border-white/8 bg-black/20 p-3"><div class="text-[11px] uppercase tracking-[0.24em] text-slate-500">ACL 编号</div><div class="mt-2 font-mono text-sm text-slate-100">{{ selectedDevice.aclNumber }}</div></div>
              <div class="rounded-2xl border border-white/8 bg-black/20 p-3"><div class="text-[11px] uppercase tracking-[0.24em] text-slate-500">协议</div><div class="mt-2 text-sm text-slate-100">{{ selectedDevice.protocol.toUpperCase() }}</div></div>
              <div class="rounded-2xl border border-white/8 bg-black/20 p-3"><div class="text-[11px] uppercase tracking-[0.24em] text-slate-500">执行模式</div><div class="mt-2 text-sm text-slate-100">{{ selectedDevice.readonlyOnly ? '只读巡检' : '开放执行' }}</div></div>
            </div>
          </div>
          <div class="rounded-[24px] border border-white/10 bg-white/[0.03] p-5"><div class="flex items-center gap-2 text-sm font-semibold text-slate-50"><Unplug class="h-4 w-4 text-primary" />运维备注</div><p class="mt-3 text-sm leading-7 text-slate-300">{{ selectedDevice.notes || '暂未填写设备备注。' }}</p></div>
        </div>
      </SheetContent>
    </Sheet>

    <Dialog :open="configManagerOpen" @update:open="(value) => configManagerOpen = value">
      <DialogContent class="max-h-[90vh] max-w-6xl overflow-hidden border-white/10 bg-slate-950/96 p-0 text-slate-100">
        <div class="flex h-full max-h-[90vh] flex-col overflow-hidden">
          <DialogHeader class="border-b border-white/10 px-6 py-4">
            <DialogTitle class="flex items-center gap-2 text-slate-50"><Settings2 class="h-4 w-4 text-primary" />交换机配置管理</DialogTitle>
            <DialogDescription class="text-slate-400">维护工作台纳管的交换机清单、Telnet 凭据、分组与只读执行边界。</DialogDescription>
          </DialogHeader>
          <div class="grid min-h-0 flex-1 gap-0 lg:grid-cols-[320px_minmax(0,1fr)]">
            <div class="border-b border-white/10 p-4 lg:border-b-0 lg:border-r">
              <div class="mb-4 flex items-center justify-between gap-2">
                <div class="text-sm font-semibold text-slate-100">设备列表</div>
                <Button size="sm" class="bg-primary/90 text-primary-foreground hover:bg-primary" @click="startCreateConfig"><Plus class="h-4 w-4" />新增</Button>
              </div>
              <ScrollArea class="h-[56vh] pr-3">
                <div v-if="configLoading" class="text-sm text-slate-400">正在加载配置...</div>
                <div v-else class="space-y-2">
                  <button v-for="item in configPanelItems" :key="item.id" type="button" class="w-full rounded-2xl border p-3 text-left transition" :class="selectedConfigId === item.id ? 'border-primary/40 bg-primary/10' : 'border-white/10 bg-white/[0.03] hover:bg-white/[0.06]'" @click="applyConfigToForm(item)">
                    <div class="flex items-center justify-between gap-3"><div class="text-sm font-semibold text-slate-100">{{ item.name }}</div><Badge variant="outline" class="border-white/10 bg-black/20 text-slate-200">{{ item.enabled ? '启用' : '禁用' }}</Badge></div>
                    <div class="mt-1 text-xs text-slate-400">{{ item.host }}:{{ item.port }}</div>
                    <div class="mt-2 text-[11px] text-slate-500">{{ item.vendor }} · {{ item.group_id }}</div>
                  </button>
                </div>
              </ScrollArea>
            </div>
            <div class="min-h-0 overflow-y-auto p-6">
              <div class="grid gap-5 md:grid-cols-2">
                <div class="space-y-2 md:col-span-2"><Label>厂商模板</Label><div class="flex flex-wrap gap-2"><Button type="button" size="sm" variant="outline" class="border-white/10 bg-white/5 text-slate-100" @click="applyVendorTemplate('H3C')">H3C</Button><Button type="button" size="sm" variant="outline" class="border-white/10 bg-white/5 text-slate-100" @click="applyVendorTemplate('Huawei')">Huawei</Button><Button type="button" size="sm" variant="outline" class="border-white/10 bg-white/5 text-slate-100" @click="applyVendorTemplate('Ruijie')">Ruijie</Button><Button type="button" size="sm" variant="outline" class="border-white/10 bg-white/5 text-slate-100" @click="applyVendorTemplate('Cisco')">Cisco</Button></div></div>
                <div class="space-y-2"><Label>交换机名称</Label><Input v-model="configForm.name" class="bg-black/20" /></div>
                <div class="space-y-2"><Label>IP 地址</Label><Input v-model="configForm.host" class="bg-black/20" placeholder="192.168.0.2" /></div>
                <div class="space-y-2"><Label>端口</Label><Input v-model.number="configForm.port" type="number" class="bg-black/20" /></div>
                <div class="space-y-2"><Label>ACL 编号</Label><Input v-model.number="configForm.acl_number" type="number" class="bg-black/20" /></div>
                <div class="space-y-2"><Label>厂商</Label><Input v-model="configForm.vendor" class="bg-black/20" /></div>
                <div class="space-y-2"><Label>型号</Label><Input v-model="configForm.model" class="bg-black/20" /></div>
                <div class="space-y-2"><Label>分组</Label><Select v-model="configForm.group_id"><SelectTrigger class="bg-black/20"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="core">core</SelectItem><SelectItem value="aggregation">aggregation</SelectItem><SelectItem value="access">access</SelectItem></SelectContent></Select></div>
                <div class="space-y-2"><Label>标签</Label><Input v-model="configForm.tagsText" class="bg-black/20" placeholder="Telnet, 核心, ACL" /></div>
                <div class="space-y-2"><Label>Telnet 密码</Label><Input v-model="configForm.password" type="password" class="bg-black/20" /></div>
                <div class="space-y-2"><Label>Enable Secret</Label><Input v-model="configForm.secret" type="password" class="bg-black/20" /></div>
                <div class="space-y-2 md:col-span-2"><Label>分页关闭命令</Label><Input v-model="configForm.paging_disable" class="bg-black/20" placeholder="如 screen-length disable / terminal length 0" /></div>
                <div class="space-y-2 md:col-span-2"><Label>备注</Label><Textarea v-model="configForm.notes" class="min-h-[110px] bg-black/20" /></div>
              </div>
              <div class="mt-6 grid gap-4 rounded-2xl border border-white/10 bg-white/[0.03] p-4 md:grid-cols-2">
                <div class="flex items-center justify-between"><div><div class="text-sm text-slate-100">启用设备</div><div class="text-xs text-slate-400">禁用后不参与探测与批量执行。</div></div><Switch v-model:checked="configForm.enabled" /></div>
                <div class="flex items-center justify-between"><div><div class="text-sm text-slate-100">只读执行门禁</div><div class="text-xs text-slate-400">限制命令仅允许巡检类读取操作。</div></div><Switch v-model:checked="configForm.readonly_only" /></div>
              </div>
              <div v-if="configValidationMessage" class="mt-4 rounded-2xl border border-amber-400/20 bg-amber-400/10 px-4 py-3 text-sm text-amber-100">{{ configValidationMessage }}</div>
            </div>
          </div>
          <DialogFooter class="border-t border-white/10 px-6 py-4">
            <div class="flex w-full flex-col gap-2 sm:flex-row sm:justify-between">
              <div class="flex gap-2"><Button variant="outline" class="border-white/10 bg-white/5 text-slate-100 hover:bg-white/10" :disabled="configTesting" @click="testConfigConnection"><Activity class="h-4 w-4" />{{ configTesting ? '测试中...' : '测试连接' }}</Button><Button variant="outline" class="border-red-500/20 bg-red-500/10 text-red-300 hover:bg-red-500/20" @click="removeSelectedConfig"><Trash2 class="h-4 w-4" />删除当前</Button></div>
              <div class="flex gap-2"><Button variant="outline" class="border-white/10 bg-white/5 text-slate-100 hover:bg-white/10" @click="saveDraftConfig"><Save class="h-4 w-4" />保存草稿</Button><Button class="bg-primary/90 text-primary-foreground hover:bg-primary" :disabled="configSaving" @click="commitConfigItems"><Settings2 class="h-4 w-4" />{{ configSaving ? '保存中...' : '写入系统' }}</Button></div>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>

    <Dialog :open="configDeleteConfirmOpen" @update:open="(value) => configDeleteConfirmOpen = value">
      <DialogContent class="max-w-md border-white/10 bg-slate-950/96 text-slate-100">
        <DialogHeader><DialogTitle>确认删除交换机</DialogTitle><DialogDescription class="text-slate-400">删除后将从工作台配置清单移除当前设备，保存写入后才会真正生效。</DialogDescription></DialogHeader>
        <DialogFooter><Button variant="outline" class="border-white/10 bg-white/5 text-slate-100" @click="configDeleteConfirmOpen = false">取消</Button><Button class="bg-red-500 text-white hover:bg-red-500/90" @click="confirmRemoveSelectedConfig">确认删除</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>

<style scoped>
.switch-workbench-page {
  position: relative;
}

.switch-workbench-page::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(circle at 12% 18%, rgba(0, 255, 255, 0.08), transparent 28%),
    radial-gradient(circle at 88% 12%, rgba(124, 58, 237, 0.12), transparent 22%),
    linear-gradient(135deg, rgba(15, 23, 42, 0.1), transparent 45%);
  mix-blend-mode: screen;
}

.terminal-screen {
  position: relative;
  box-shadow: inset 0 0 0 1px rgba(0, 255, 255, 0.04), inset 0 24px 60px rgba(0, 0, 0, 0.35);
}

.terminal-screen::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(to bottom, rgba(255, 255, 255, 0.03), transparent 16%, transparent 84%, rgba(0, 255, 255, 0.03));
}

.terminal-text {
  font-family: 'Cascadia Code', 'JetBrains Mono', 'Fira Code', monospace;
}
</style>
