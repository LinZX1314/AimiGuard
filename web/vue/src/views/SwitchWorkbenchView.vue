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
const healthTone = computed(() => onlineCount.value >= Math.max(1, devices.value.length - 1) ? '稳定' : degradedCount.value ? '波动' : '待校验')

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
  if (status === 'online') return 'status-dot status-dot--online'
  if (status === 'degraded') return 'status-dot status-dot--degraded'
  return 'status-dot status-dot--offline'
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
  try {
    const [liveDevices, liveScripts, liveHistory] = await Promise.all([
      switchWorkbenchApi.devices(true),
      switchWorkbenchApi.scripts(),
      switchWorkbenchApi.history(24),
    ])

    // If we get valid responses from the backend, we are in LIVE mode
    if (liveDevices && Array.isArray(liveDevices)) {
      backendMode.value = 'live'
      devices.value = liveDevices.map(mapApiDevice)
      if (devices.value.length > 0) {
        selectedDeviceId.value = devices.value[0]?.id ?? selectedDeviceId.value
      }
      pushLog('meta', '后端已接入', '已成功连接服务器控制中心，准备执行物理资产指令。')
    }

    if (liveScripts && Array.isArray(liveScripts)) {
      quickScripts.value = liveScripts.map(mapApiScript)
    }
    if (liveHistory && Array.isArray(liveHistory)) {
      executionRecords.value = liveHistory.map(mapApiHistory)
    }
  } catch (err) {
    console.error('Hydration failed:', err)
    backendMode.value = 'demo'
    pushLog('warning', '降级提醒', '无法连接后端服务器，当前仅展示模拟演示数据。')
  }
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
  <div class="switch-workbench-page h-full overflow-hidden">
    <div class="switch-grid-bg"></div>
    <div class="switch-orb switch-orb--cyan"></div>
    <div class="switch-orb switch-orb--violet"></div>

    <div class="relative z-10 mx-auto w-full max-w-[1720px] px-8 py-10 space-y-8">
      <section class="hero-panel">
        <div class="hero-copy">
          <div class="hero-badges">
            <div class="hero-chip hero-chip--brand"><Bot class="h-3.5 w-3.5" />AI Command</div>
            <div class="hero-chip" :class="backendMode === 'live' ? 'hero-chip--success' : 'hero-chip--warning'">
              <CircleCheck v-if="backendMode === 'live'" class="h-3.5 w-3.5" />
              <Radar v-else class="h-3.5 w-3.5" />
              {{ backendMode === 'live' ? 'Live Session' : 'Demo Mode' }}
            </div>
          </div>
          <p class="hero-kicker">Network Command Theater</p>
          <h1 class="hero-title">AimiGuard AI 运维矩阵</h1>
          <p class="hero-subtitle">深度集成物理资产、会话终端与 AI 诊断回路，构建多维一体的指挥视图。</p>
        </div>

        <div class="hero-metrics">
          <div class="metric-card">
            <span class="metric-label">Switches</span>
            <strong class="metric-value">{{ devices.length }}</strong>
          </div>
          <div class="metric-card metric-card--success">
            <span class="metric-label">Online</span>
            <strong class="metric-value">{{ onlineCount }}</strong>
          </div>
          <div class="metric-card metric-card--warning">
            <span class="metric-label">Unstable</span>
            <strong class="metric-value">{{ degradedCount }}</strong>
          </div>
          <div class="metric-card">
            <span class="metric-label">Batch</span>
            <strong class="metric-value">{{ checkedDevices.length }}</strong>
          </div>
        </div>
      </section>

      <div class="workbench-layout">
        <section class="panel-shell">
          <header class="panel-head">
            <div>
              <p class="panel-eyebrow">Asset Matrix</p>
              <h2 class="panel-title">资产矩阵</h2>
              <p class="panel-desc">快速筛选区域、切换目标、管理批量队列。</p>
            </div>
            <div class="mt-4 flex items-center justify-between">
              <Button size="sm" variant="outline" class="panel-btn h-9 px-4" @click="openConfigManager">
                <Settings2 class="mr-2 h-4 w-4" />管理
              </Button>
              <span class="mini-pill">{{ checkedDevices.length }} 已选</span>
            </div>
          </header>

          <div class="group-pills">
            <button
              v-for="group in availableGroupOptions"
              :key="group.id"
              class="group-pill"
              :class="{ 'group-pill--active': selectedGroup === group.id }"
              @click="selectGroup(group.id)"
            >
              <span class="group-pill__label">{{ group.label }}</span>
              <span class="group-pill__desc">{{ group.description }}</span>
            </button>
          </div>

          <ScrollArea class="asset-scroll">
            <div class="asset-list">
              <button
                v-for="device in visibleDevices"
                :key="device.id"
                class="asset-card"
                :class="{ 'asset-card--active': device.id === selectedDeviceId }"
                @click="setActiveDevice(device.id)"
              >
                <div class="flex items-start justify-between">
                  <div class="flex-1">
                    <div class="flex items-center gap-2 mb-1">
                      <strong class="asset-card__title">{{ device.name }}</strong>
                      <span :class="statusTone(device.status)"></span>
                    </div>
                    <p class="asset-card__subtitle">{{ device.vendor }} / {{ device.model }}</p>
                  </div>
                  <label class="flex items-center gap-1.5 cursor-pointer opacity-60 hover:opacity-100" @click.stop>
                    <input :checked="device.checked" type="checkbox" class="w-3.5 h-3.5 accent-cyan-400" @change="toggleDeviceSelection(device.id)" />
                    <span class="text-[10px] uppercase font-bold text-slate-500">Multiselect</span>
                  </label>
                </div>
              </button>
            </div>
          </ScrollArea>
        </section>

        <section class="center-column">
          <article class="device-spotlight" v-if="selectedDevice">
            <div class="flex-1 space-y-6">
              <div>
                <p class="panel-eyebrow">Current Focus</p>
                <div class="flex items-center gap-4 mt-2">
                  <h2 class="hero-title text-4xl mb-0">{{ selectedDevice.name }}</h2>
                  <span class="device-badge">Telnet 23</span>
                </div>
                <p class="text-slate-400 mt-2 text-sm">{{ selectedDevice.vendor }} {{ selectedDevice.model }} · {{ selectedDevice.host }}</p>
              </div>
              <div class="flex gap-3">
                <Button variant="outline" class="panel-btn" @click="detailOpen = true"><Cpu class="mr-2 h-4 w-4" />详情</Button>
                <Button variant="outline" class="panel-btn" :disabled="testingConnection" @click="testSelectedDeviceConnection">
                  <Activity class="mr-2 h-4 w-4" />{{ testingConnection ? '测试中...' : '测试连接' }}
                </Button>
                <Button variant="outline" class="panel-btn" @click="toggleSelectedDeviceChoice">
                  <CheckCircle2 class="mr-2 h-4 w-4" />{{ selectedDeviceSelected ? '移出批量' : '加入批量' }}
                </Button>
              </div>
            </div>

            <div class="space-y-3">
              <div class="status-box">
                <span class="status-box__label">Connection</span>
                <strong class="status-box__value" :class="connectionStatusTone === 'success' ? 'text-emerald-400' : 'text-slate-100'">{{ connectionStatus }}</strong>
              </div>
              <div class="status-box">
                <span class="status-box__label">History</span>
                <strong class="status-box__value">{{ selectedDeviceRecordCount }} 条记录</strong>
              </div>
            </div>
          </article>

          <article class="panel-shell flex-1">
            <header class="panel-head flex items-center justify-between">
              <div>
                <p class="panel-eyebrow">Interactive Shell</p>
                <h2 class="panel-title">会话终端</h2>
              </div>
              <div class="flex gap-2">
                <Button variant="outline" size="sm" class="panel-btn" @click="clearTerminal">清空</Button>
                <Button size="sm" class="panel-btn panel-btn--primary" :disabled="running" @click="submitManualCommand">
                  <Play class="mr-2 h-3.5 w-3.5" />{{ running ? '执行中' : '发送' }}
                </Button>
              </div>
            </header>

            <div class="flex-1 flex flex-col min-height-0 overflow-hidden">
              <ScrollArea class="flex-1 p-6">
                <div class="terminal-stream">
                  <div
                    v-for="entry in terminalLogs"
                    :key="entry.id"
                    class="terminal-entry"
                    :class="[
                      entry.kind === 'command' ? 'terminal-entry--command' : '',
                      entry.kind === 'ai' ? 'terminal-entry--ai' : '',
                      entry.kind === 'warning' ? 'terminal-entry--warning' : '',
                    ]"
                  >
                    <div class="terminal-entry__meta">
                      <span>{{ entry.title }}</span>
                      <span class="ml-4 opacity-50">{{ entry.timestamp }}</span>
                    </div>
                    <pre class="terminal-text whitespace-pre-wrap break-all">{{ entry.content }}</pre>
                  </div>
                </div>
              </ScrollArea>

              <div class="terminal-input-shell border-t border-white/5 mx-6 mb-6 pt-6">
                <div class="flex flex-wrap gap-2 mb-4">
                  <button v-for="command in quickCommands" :key="command" class="quick-command-chip" @click="applyQuickCommand(command)">{{ command }}</button>
                </div>
                <div class="flex gap-3">
                  <Input v-model="commandInput" class="h-12 bg-slate-950/50 border-white/10" placeholder="发送指令或通过 AI 助手自动生成..." />
                  <Button class="panel-btn panel-btn--primary h-12 px-8" :disabled="running" @click="submitManualCommand">执行</Button>
                </div>
              </div>
            </div>
          </article>
        </section>

        <section class="right-column">
          <article class="panel-shell p-8 space-y-8">
            <header>
              <p class="panel-eyebrow">AI Co-pilot</p>
              <h2 class="panel-title">智能诊断助理</h2>
              <p class="panel-desc">基于实时回显提供下一步操作建议。</p>
            </header>

            <div class="space-y-4">
              <Textarea v-model="aiPrompt" class="min-h-[100px] bg-slate-950/50 border-white/10 resize-none" placeholder="输入诊断需求，例如：检查此设备的接口报错统计..." />
              <div class="assistant-toggle">
                <div class="flex-1">
                  <p class="text-sm font-bold text-slate-200">自动执行安全建议</p>
                  <p class="text-[10px] text-slate-500">仅限只读检查指令</p>
                </div>
                <Switch v-model:checked="autoExecuteReadonly" />
              </div>
              <Button class="panel-btn panel-btn--primary w-full h-12" :disabled="running" @click="askAiAssistant">
                <WandSparkles class="mr-2 h-4 w-4" />{{ running ? '正在处理...' : '多轮协同诊断' }}
              </Button>
            </div>

            <div v-if="aiSummary" class="diagnosis-card diagnosis-card--summary">
              <p class="text-[10px] uppercase font-bold text-cyan-400 mb-2">CURRENT INSIGHT</p>
              <p class="text-sm text-slate-300 leading-relaxed">{{ aiSummary }}</p>
            </div>

            <div v-if="aiSuggestions.length" class="space-y-4">
              <div class="flex items-center justify-between">
                <p class="panel-eyebrow mb-0">AI Suggestions</p>
                <Button variant="ghost" size="sm" class="text-xs text-cyan-400 hover:text-cyan-300" @click="runAllSuggestions">全部串行执行</Button>
              </div>
              <div class="space-y-3">
                <div v-for="suggestion in aiSuggestions" :key="suggestion.id" class="suggestion-card">
                  <div class="flex items-start justify-between gap-4">
                    <div>
                      <h4 class="text-sm font-bold text-slate-200">{{ suggestion.title }}</h4>
                      <p class="text-[11px] text-slate-500 mt-1">{{ suggestion.reason }}</p>
                    </div>
                    <span class="text-[9px] uppercase font-black px-2 py-0.5 rounded bg-slate-800 text-slate-400">{{ suggestion.risk }}</span>
                  </div>
                  <div class="bg-black/40 rounded-lg p-3 mt-4 font-mono text-xs text-cyan-300 border border-white/5">{{ suggestion.command }}</div>
                  <div class="grid grid-cols-2 gap-2 mt-4">
                    <Button size="sm" class="panel-btn panel-btn--primary h-8" @click="runSuggestion(suggestion)">立即发送</Button>
                    <Button size="sm" variant="ghost" class="panel-btn h-8 text-xs" @click="commandInput = suggestion.command">引用</Button>
                  </div>
                </div>
              </div>
            </div>
          </article>

          <article class="panel-shell p-8 space-y-6">
            <header>
              <p class="panel-eyebrow">Script Rack</p>
              <h2 class="panel-title">快捷脚本</h2>
            </header>

            <div class="grid grid-cols-1 gap-3">
              <button v-for="script in quickScripts" :key="script.id" class="script-card" @click="runQuickScript(script)">
                <div class="flex items-start justify-between">
                  <div>
                    <h4 class="text-sm font-bold text-slate-200">{{ script.title }}</h4>
                    <p class="text-[11px] text-slate-500 mt-1 line-clamp-1">{{ script.description }}</p>
                  </div>
                  <span class="text-[9px] font-bold px-1.5 py-0.5 rounded bg-cyan-950/50 text-cyan-400 border border-cyan-500/20">{{ script.scope === 'batch' ? 'BATCH' : 'SINGLE' }}</span>
                </div>
                <div class="mt-4 flex items-center gap-3">
                  <span class="text-[10px] text-slate-400 font-mono">{{ script.commands.length }} Cmds</span>
                  <span class="text-[10px] px-2 py-0.5 rounded bg-white/5 text-slate-500">{{ script.risk }}</span>
                </div>
              </button>
            </div>
          </article>

          <article class="panel-shell flex-1">
             <header class="panel-head">
              <div>
                <p class="panel-eyebrow">History</p>
                <h2 class="panel-title">执行审计</h2>
              </div>
              <Select v-model="selectedRecordSource">
                <SelectTrigger class="w-32 bg-slate-950/50 border-white/10 h-8 text-[11px]"><SelectValue placeholder="All Sources" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部来源</SelectItem>
                  <SelectItem value="manual">手工</SelectItem>
                  <SelectItem value="ai">AI</SelectItem>
                  <SelectItem value="script">脚本</SelectItem>
                </SelectContent>
              </Select>
            </header>
            <ScrollArea class="flex-1 p-6">
              <div class="space-y-4">
                <div v-for="record in filteredExecutionRecords" :key="record.id" class="record-card">
                   <div class="flex items-start justify-between">
                    <h4 class="text-sm font-bold">{{ record.title }}</h4>
                    <span class="text-[10px] text-emerald-400">{{ record.status }}</span>
                  </div>
                  <p class="text-[11px] text-slate-500 mt-2 line-clamp-2">{{ record.summary }}</p>
                  <div class="flex items-center justify-between mt-4 text-[10px] text-slate-600 font-mono">
                    <span>Target: {{ record.target }}</span>
                    <span>{{ record.createdAt }}</span>
                  </div>
                </div>
              </div>
            </ScrollArea>
          </article>
        </section>
      </div>
    </div>

    <Sheet :open="detailOpen" @update:open="(value) => detailOpen = value">
      <SheetContent side="right" class="w-full overflow-y-auto border-white/10 bg-slate-950/96 text-slate-100 sm:max-w-xl">
        <SheetHeader>
          <SheetTitle class="flex items-center gap-2 text-slate-50"><Server class="h-4 w-4 text-primary" />设备详情</SheetTitle>
          <SheetDescription class="text-slate-400">展示交换机连接参数、执行边界和运维画像。</SheetDescription>
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
                <Button size="sm" class="panel-btn panel-btn--primary" @click="startCreateConfig"><Plus class="h-4 w-4" />新增</Button>
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
                <div class="space-y-2 md:col-span-2"><Label>厂商模板</Label><div class="flex flex-wrap gap-2"><Button type="button" size="sm" variant="outline" class="panel-btn panel-btn--ghost" @click="applyVendorTemplate('H3C')">H3C</Button><Button type="button" size="sm" variant="outline" class="panel-btn panel-btn--ghost" @click="applyVendorTemplate('Huawei')">Huawei</Button><Button type="button" size="sm" variant="outline" class="panel-btn panel-btn--ghost" @click="applyVendorTemplate('Ruijie')">Ruijie</Button><Button type="button" size="sm" variant="outline" class="panel-btn panel-btn--ghost" @click="applyVendorTemplate('Cisco')">Cisco</Button></div></div>
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
              <div class="flex gap-2"><Button variant="outline" class="panel-btn panel-btn--ghost" :disabled="configTesting" @click="testConfigConnection"><Activity class="h-4 w-4" />{{ configTesting ? '测试中...' : '测试连接' }}</Button><Button variant="outline" class="panel-btn panel-btn--danger" @click="removeSelectedConfig"><Trash2 class="h-4 w-4" />删除当前</Button></div>
              <div class="flex gap-2"><Button variant="outline" class="panel-btn panel-btn--ghost" @click="saveDraftConfig"><Save class="h-4 w-4" />保存草稿</Button><Button class="panel-btn panel-btn--primary" :disabled="configSaving" @click="commitConfigItems"><Settings2 class="h-4 w-4" />{{ configSaving ? '保存中...' : '写入系统' }}</Button></div>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>

    <Dialog :open="configDeleteConfirmOpen" @update:open="(value) => configDeleteConfirmOpen = value">
      <DialogContent class="max-w-md border-white/10 bg-slate-950/96 text-slate-100">
        <DialogHeader><DialogTitle>确认删除交换机</DialogTitle><DialogDescription class="text-slate-400">删除后将从工作台配置清单移除当前设备，保存写入后才会真正生效。</DialogDescription></DialogHeader>
        <DialogFooter><Button variant="outline" class="panel-btn panel-btn--ghost" @click="configDeleteConfirmOpen = false">取消</Button><Button class="panel-btn panel-btn--danger-solid" @click="confirmRemoveSelectedConfig">确认删除</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>

<style scoped>
.switch-workbench-page {
  position: relative;
  min-height: 100vh;
  background: #020617;
  color: #f8fafc;
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
}

.switch-grid-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image: radial-gradient(circle at 2px 2px, rgba(255, 255, 255, 0.05) 1px, transparent 0);
  background-size: 24px 24px;
  mask-image: radial-gradient(ellipse at top, black 40%, transparent 90%);
}

.switch-orb {
  position: absolute;
  border-radius: 9999px;
  filter: blur(120px);
  opacity: 0.15;
  pointer-events: none;
}

.switch-orb--cyan {
  top: -100px;
  left: 10%;
  width: 500px;
  height: 500px;
  background: #22d3ee;
}

.switch-orb--violet {
  top: 20%;
  right: 5%;
  width: 400px;
  height: 400px;
  background: #8b5cf6;
}

.hero-panel {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px 40px;
  border-radius: 28px;
  background: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(32px);
  border: 1px solid rgba(255, 255, 255, 0.06);
  box-shadow: 0 4px 24px -1px rgba(0, 0, 0, 0.2);
  overflow: hidden;
}

.hero-panel::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at top left, rgba(34, 211, 238, 0.08), transparent 40%);
  pointer-events: none;
}

.hero-copy {
  z-index: 1;
  max-width: 65%;
}

.hero-badges {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.hero-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-radius: 99px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #94a3b8;
}

.hero-chip--brand {
  background: rgba(34, 211, 238, 0.1);
  border-color: rgba(34, 211, 238, 0.2);
  color: #22d3ee;
}

.hero-kicker {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.3em;
  color: #22d3ee;
  text-transform: uppercase;
  margin-bottom: 12px;
  opacity: 0.8;
}

.hero-title {
  font-size: 2.25rem;
  font-weight: 850;
  line-height: 1.1;
  letter-spacing: -0.02em;
  margin-bottom: 12px;
  background: linear-gradient(to bottom right, #fff, #94a3b8);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.hero-subtitle {
  font-size: 14px;
  line-height: 1.6;
  color: #94a3b8;
  max-width: 520px;
}

.hero-metrics {
  display: grid;
  grid-template-columns: repeat(4, 130px);
  gap: 12px;
  z-index: 1;
}

.metric-card {
  padding: 16px 20px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  transition: transform 0.3s ease, background 0.3s ease;
}

.metric-card:hover {
  background: rgba(255, 255, 255, 0.05);
  transform: translateY(-2px);
}

.metric-label {
  font-size: 10px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 8px;
}

.metric-value {
  font-size: 1.75rem;
  font-weight: 800;
  color: #94a3b8;
}

.metric-card--success .metric-value { color: #10b981; }
.metric-card--warning .metric-value { color: #f59e0b; }

.workbench-layout {
  display: grid;
  grid-template-columns: 340px minmax(0, 1fr) 420px;
  gap: 20px;
  padding-bottom: 40px;
  height: calc(100vh - 280px); /* Fill remaining height */
}

.center-column {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-height: 0;
}

.right-column {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-height: 0;
}

.panel-shell {
  background: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(24px);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 32px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-head {
  padding: 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.panel-eyebrow {
  color: #22d3ee;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  margin-bottom: 8px;
  opacity: 0.8;
}

.panel-title {
  font-size: 1.15rem;
  font-weight: 700;
  color: #f1f5f9;
}

.panel-desc {
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}

.group-pills {
  padding: 20px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.group-pill {
  padding: 12px 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  text-align: left;
  transition: all 0.2s ease;
}

.group-pill--active {
  background: rgba(34, 211, 238, 0.08);
  border-color: rgba(34, 211, 238, 0.3);
}

.group-pill__label {
  font-size: 13px;
  font-weight: 600;
  color: #e2e8f0;
}

.group-pill__desc {
  font-size: 10px;
  color: #64748b;
  margin-top: 2px;
}

.asset-scroll {
  padding: 0 20px 20px;
  flex: 1;
}

.asset-list {
  display: grid;
  gap: 12px;
}

.asset-card {
  padding: 20px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.04);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.asset-card:hover, .asset-card--active {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(34, 211, 238, 0.2);
  transform: scale(1.01);
}

.asset-card__title {
  font-size: 15px;
  font-weight: 700;
  color: #f8fafc;
}

.asset-card__subtitle {
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot--online { background: #10b981; box-shadow: 0 0 12px #10b981; }
.status-dot--degraded { background: #f59e0b; box-shadow: 0 0 12px #f59e0b; }
.status-dot--offline { background: #ef4444; box-shadow: 0 0 12px #ef4444; }

.device-spotlight {
  padding: 24px 32px;
  background: linear-gradient(to right, rgba(15, 23, 42, 0.5), transparent);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 28px;
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 32px;
}

.device-title-row h2 {
  font-size: 1.75rem;
  font-weight: 800;
  letter-spacing: -0.01em;
}

.device-badge {
  padding: 4px 12px;
  border-radius: 99px;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  background: rgba(34, 211, 238, 0.1);
  color: #22d3ee;
  border: 1px solid rgba(34, 211, 238, 0.2);
}

.status-box {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.status-box__label {
  font-size: 10px;
  text-transform: uppercase;
  font-weight: 700;
  color: #64748b;
  letter-spacing: 0.1em;
}

.status-box__value {
  font-size: 1.25rem;
  font-weight: 700;
}

.status-box {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.status-box__label {
  font-size: 10px;
  text-transform: uppercase;
  font-weight: 700;
  color: #64748b;
  letter-spacing: 0.1em;
}

.status-box__value {
  font-size: 1.15rem;
  font-weight: 700;
  color: #f1f5f9;
}

.terminal-stream {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.terminal-entry {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.terminal-entry__meta {
  color: #64748b;
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
}

.terminal-text {
  background: rgba(15, 23, 42, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.04);
  padding: 14px 18px;
  border-radius: 14px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #e2e8f0;
  border-left: 3px solid rgba(255, 255, 255, 0.1);
}

.terminal-entry--command .terminal-text { border-left-color: #22d3ee; color: #22d3ee; }
.terminal-entry--ai .terminal-text { border-left-color: #8b5cf6; color: #a78bfa; }
.terminal-entry--warning .terminal-text { border-left-color: #ef4444; color: #fca5a5; }

.terminal-input-shell {
  margin-top: 0;
  padding: 24px;
  background: rgba(15, 23, 42, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 20px;
}

.quick-command-chip {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
  padding: 6px 14px;
  border-radius: 99px;
  font-size: 11px;
  color: #94a3b8;
  transition: all 0.2s ease;
}

.quick-command-chip:hover {
  background: rgba(34, 211, 238, 0.1);
  border-color: rgba(34, 211, 238, 0.2);
  color: #22d3ee;
}

.assistant-toggle {
  background: rgba(255, 255, 255, 0.03);
  padding: 16px 20px;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.diagnosis-card {
  padding: 24px;
  border-radius: 24px;
  background: rgba(15, 23, 42, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.diagnosis-card--summary {
  background: linear-gradient(to bottom right, rgba(34, 211, 238, 0.05), transparent);
  border-color: rgba(34, 211, 238, 0.15);
}

.suggestion-card, .script-card, .record-card {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 20px;
  padding: 20px;
  transition: all 0.25s ease;
}

.suggestion-card:hover, .script-card:hover {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.1);
}

.panel-btn--primary {
  background: linear-gradient(135deg, #22d3ee, #0ea5e9);
  color: #020617;
  font-weight: 700;
  border-radius: 12px;
  box-shadow: 0 4px 14px -2px rgba(34, 211, 238, 0.3);
}

.panel-btn {
  border-radius: 12px;
  font-weight: 600;
  transition: all 0.2s ease;
}

.mini-pill {
  background: rgba(34, 211, 238, 0.08);
  border: 1px solid rgba(34, 211, 238, 0.15);
  padding: 4px 10px;
  border-radius: 99px;
  font-size: 10px;
  font-weight: 700;
  color: #22d3ee;
}

@media (max-width: 1600px) {
  .workbench-layout {
    grid-template-columns: 300px minmax(0, 1fr) 360px;
  }
}

@media (max-width: 1280px) {
  .workbench-layout {
    grid-template-columns: 1fr;
  }
  .hero-panel {
    flex-direction: column;
    align-items: flex-start;
    gap: 32px;
  }
}
</style>
