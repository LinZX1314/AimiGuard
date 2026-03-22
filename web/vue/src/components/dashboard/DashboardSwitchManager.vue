<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { applySwitchPortConfig, chunkPortsForDisplay, createDefaultSwitchPorts, type SwitchPort } from '@/lib/centerPanelState'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'

interface SwitchStatusItem {
  host: string
  port: number
  acl_number?: number
  enabled: boolean
  online: boolean
  error?: string
}

interface OverviewPayload {
  switches?: Array<{
    host?: string
    port?: number
    acl_number?: number
    enabled?: boolean
  }>
}

const ports = ref(createDefaultSwitchPorts())
const isLoading = ref(false)
const isSaving = ref(false)
const selectedPort = ref<SwitchPort | null>(null)
const editStatus = ref<'up' | 'admin-down'>('up')
const editVlan = ref(10)
const switchIdentity = ref({
  name: '核心数据中心节点 - SW-Core-01',
  brand: 'Ruijie (锐捷)',
  ip: '10.24.100.254',
  status: 'SSH Online',
})
const switchStatuses = ref<SwitchStatusItem[]>([])

const rows = computed(() => chunkPortsForDisplay(ports.value))
const activePortCount = computed(() => ports.value.filter((port) => port.status === 'up').length)
const adminDownCount = computed(() => ports.value.filter((port) => port.status === 'admin-down').length)
const onlineSwitchCount = computed(() => switchStatuses.value.filter((item) => item.online).length)

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('token')
  if (!token) return {}
  return { Authorization: `Bearer ${token}` }
}

function syncIdentityFromStatuses() {
  const primary = switchStatuses.value[0]
  if (!primary) {
    return
  }

  switchIdentity.value = {
    name: '核心数据中心节点 - SW-Core-01',
    brand: 'Ruijie (锐捷)',
    ip: primary.host,
    status: primary.online ? 'SSH Online' : (primary.error ? `OFFLINE · ${primary.error}` : 'OFFLINE'),
  }
}

async function loadRealSwitchData() {
  const headers = getAuthHeaders()
  if (!headers.Authorization) {
    return
  }

  const [statusesRes, overviewRes] = await Promise.all([
    fetch('/api/v1/defense/switch/statuses?strict=0', { credentials: 'include', headers }),
    fetch('/api/v1/overview/screen', { credentials: 'include', headers }),
  ])

  if (statusesRes.ok) {
    const payload = await statusesRes.json()
    switchStatuses.value = Array.isArray(payload?.data?.items)
      ? payload.data.items
      : Array.isArray(payload?.items)
        ? payload.items
        : []
  }

  if (overviewRes.ok) {
    const payload = await overviewRes.json() as { data?: OverviewPayload } | OverviewPayload
    const overview = (payload as { data?: OverviewPayload })?.data ?? (payload as OverviewPayload)
    const configured = Array.isArray(overview?.switches) ? overview.switches : []
    const primaryConfig = configured[0]
    if (primaryConfig?.host) {
      switchIdentity.value = {
        ...switchIdentity.value,
        ip: primaryConfig.host,
      }
    }
  }

  syncIdentityFromStatuses()
  if (switchStatuses.value.length > 0) {
    ports.value = createDefaultSwitchPorts().map((port, index) => {
      const relatedSwitch = switchStatuses.value[index % switchStatuses.value.length]
      const enabled = relatedSwitch?.enabled ?? true
      const online = relatedSwitch?.online ?? false
      return {
        ...port,
        status: !enabled ? 'admin-down' : online ? (port.status === 'admin-down' ? 'up' : port.status) : 'down',
      }
    })
  }
}

async function reloadPorts() {
  isLoading.value = true
  try {
    await loadRealSwitchData()
  } catch {
    ports.value = createDefaultSwitchPorts().map((port, index) => index % 5 === 0 ? { ...port, tx: port.tx + 7, rx: port.rx + 5 } : port)
  } finally {
    isLoading.value = false
  }
}

function openPort(port: SwitchPort) {
  selectedPort.value = port
  editStatus.value = port.status === 'admin-down' ? 'admin-down' : 'up'
  editVlan.value = port.vlan
}

function closeModal() {
  selectedPort.value = null
  isSaving.value = false
}

function saveConfig() {
  if (!selectedPort.value) {
    return
  }

  isSaving.value = true
  window.setTimeout(() => {
    ports.value = applySwitchPortConfig(ports.value, selectedPort.value!.id, editStatus.value, editVlan.value)
    closeModal()
  }, 760)
}

onMounted(() => {
  reloadPorts()
})
</script>

<template>
  <section class="switch-shell" aria-label="设备面板">
    <header class="switch-head">
      <div class="switch-head__identity">
        <div class="switch-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" focusable="false">
            <path d="M4 7h16M6 12h3m2 0h2m2 0h3M7 17h10" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.8" />
          </svg>
        </div>
        <div>
          <h3>{{ switchIdentity.name }}</h3>
          <p>
            <span>{{ switchIdentity.brand }}</span>
            <span>IP: {{ switchIdentity.ip }}</span>
            <strong>{{ switchIdentity.status }}</strong>
          </p>
        </div>
      </div>
      <button type="button" class="switch-head__reload" :disabled="isLoading" @click="reloadPorts">
        <svg viewBox="0 0 24 24" focusable="false" :class="{ 'switch-spin': isLoading }">
          <path d="M20 12a8 8 0 1 1-2.34-5.66M20 4v6h-6" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" />
        </svg>
        <span>{{ isLoading ? 'Config Parsing...' : 'Reload' }}</span>
      </button>
    </header>

    <div class="switch-summary">
      <span>活跃端口 <strong>{{ activePortCount }}</strong></span>
      <span>Shutdown <strong>{{ adminDownCount }}</strong></span>
      <span>在线交换机 <strong>{{ onlineSwitchCount }}</strong></span>
    </div>

    <div class="switch-stage">
      <div class="switch-chassis">
        <div class="switch-chassis__lights"><span></span><span></span></div>
        <div class="switch-chassis__brand">RUIJIE</div>
        <div class="switch-port-grid">
          <div class="switch-port-row">
            <button v-for="port in rows.topRow" :key="port.id" type="button" class="switch-port" :data-status="port.status" :title="`${port.name} - VLAN ${port.vlan}`" @click="openPort(port)">
              <span class="switch-port__id">{{ port.id }}</span>
              <span class="switch-port__jack"></span>
              <span class="switch-port__led"></span>
            </button>
          </div>
          <div class="switch-port-row">
            <button v-for="port in rows.bottomRow" :key="port.id" type="button" class="switch-port" :data-status="port.status" :title="`${port.name} - VLAN ${port.vlan}`" @click="openPort(port)">
              <span class="switch-port__id">{{ port.id }}</span>
              <span class="switch-port__jack"></span>
              <span class="switch-port__led"></span>
            </button>
          </div>
        </div>
        <div class="switch-chassis__range">GigabitEthernet 0/1 - 0/24</div>
      </div>
    </div>

    <!-- replace switch-modal with Dialog from UI -->
    <Dialog :open="!!selectedPort" @update:open="(val) => { if (!val) closeModal() }">
      <DialogContent class="sm:max-w-[425px] border-cyan-500/30 bg-slate-950/95 backdrop-blur-xl text-cyan-50">
        <DialogHeader>
          <DialogTitle>{{ selectedPort?.name }} 配置</DialogTitle>
          <DialogDescription class="text-cyan-200/60">
            修改当前物理端口的状态和 VLAN 划分。
          </DialogDescription>
        </DialogHeader>

        <div class="grid gap-6 py-4" v-if="selectedPort">
          <label class="grid gap-2">
            <span class="text-sm font-medium text-cyan-200">Port Status (Admin)</span>
            <div class="flex gap-2">
              <button
                type="button"
                class="flex-1 py-2 px-3 rounded-md transition-all duration-200 text-sm font-medium border"
                :class="editStatus === 'up' ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400' : 'bg-slate-800/50 border-slate-700 text-slate-400'"
                @click="editStatus = 'up'"
              >
                UP (Enable)
              </button>
              <button
                type="button"
                class="flex-1 py-2 px-3 rounded-md transition-all duration-200 text-sm font-medium border"
                :class="editStatus === 'admin-down' ? 'bg-red-500/20 border-red-500/50 text-red-400' : 'bg-slate-800/50 border-slate-700 text-slate-400'"
                @click="editStatus = 'admin-down'"
              >
                DOWN (Shutdown)
              </button>
            </div>
          </label>

          <label class="grid gap-2">
            <span class="text-sm font-medium text-cyan-200">Access VLAN</span>
            <input
              v-model.number="editVlan"
              type="number"
              min="1"
              max="4094"
              class="w-full rounded-md border border-cyan-500/30 bg-slate-900/80 px-3 py-2 text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 transition-all font-mono"
            />
          </label>

          <div class="grid grid-cols-2 gap-3 p-3 rounded-lg border border-cyan-500/20 bg-cyan-950/20">
            <div class="flex flex-col gap-1">
              <span class="text-[10px] text-cyan-200/60 uppercase tracking-wider">Speed</span>
              <strong class="text-sm text-cyan-400 font-mono">{{ selectedPort.speed }}</strong>
            </div>
            <div class="flex flex-col gap-1">
              <span class="text-[10px] text-cyan-200/60 uppercase tracking-wider">Inbound / Outbound</span>
              <strong class="text-sm text-cyan-400 font-mono">{{ selectedPort.tx }} M / {{ selectedPort.rx }} M</strong>
            </div>
          </div>
        </div>

        <DialogFooter>
          <button
            type="button"
            class="w-full justify-center rounded-md bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/20 hover:text-cyan-300 transition-all focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-slate-900 disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="isSaving"
            @click="saveConfig"
          >
            {{ isSaving ? '正在写入 Running-Config...' : '应用并保存配置' }}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </section>
</template>

<style scoped>
.switch-shell{position:relative;display:flex;flex-direction:column;height:100%;min-height:420px;border:1px solid rgba(255,255,255,.08);border-radius:20px;background:linear-gradient(180deg,rgba(5,10,24,.96),rgba(12,12,18,.98));overflow:hidden}.switch-head,.switch-summary{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:18px;border-bottom:1px solid rgba(255,255,255,.08)}.switch-head__identity,.switch-head p,.switch-head__reload,.switch-summary,.switch-port,.switch-modal__head,.switch-toggle-group,.switch-modal__stats div{display:flex;align-items:center}.switch-head__identity{gap:14px}.switch-icon{display:grid;place-items:center;width:48px;height:48px;border-radius:14px;color:var(--cyber-cyan);border:1px solid rgba(0,212,255,.2);background:rgba(0,212,255,.08)}.switch-icon svg,.switch-head__reload svg{width:22px;height:22px}.switch-head h3,.switch-modal__head h4{margin:0}.switch-head p,.switch-modal__stats span{margin:0;font:11px/1.4 'JetBrains Mono',monospace;color:var(--muted-foreground)}.switch-head p{display:flex;flex-wrap:wrap;gap:10px}.switch-head p strong{color:var(--cyber-green)}.switch-head__reload,.switch-modal__close,.switch-toggle,.switch-modal__save{min-height:44px;border-radius:12px;border:1px solid transparent;transition:background-color .18s ease,border-color .18s ease,opacity .18s ease}.switch-head__reload,.switch-modal__save{padding:0 14px;font-weight:600}.switch-head__reload{border-color:rgba(255,255,255,.1);background:rgba(255,255,255,.04);color:var(--foreground);gap:10px}.switch-summary span,.switch-chassis__range,.switch-port__id,.switch-modal__field span,.switch-modal__stats strong{font-family:'JetBrains Mono',monospace;font-size:11px}.switch-summary strong,.switch-modal__stats strong{color:var(--cyber-cyan)}.switch-stage{flex:1;display:grid;place-items:center;padding:24px}.switch-chassis{position:relative;width:min(100%,860px);padding:20px;border-radius:12px;border:2px solid #2a2d36;background:#1a1c23;box-shadow:0 16px 40px rgba(0,0,0,.35)}.switch-chassis__lights{position:absolute;top:12px;left:18px;display:flex;gap:6px}.switch-chassis__lights span{width:8px;height:8px;border-radius:999px}.switch-chassis__lights span:first-child{background:#22c55e;box-shadow:0 0 12px #22c55e}.switch-chassis__lights span:last-child{background:#3b82f6}.switch-chassis__brand{position:absolute;right:26px;top:24px;font-size:34px;font-weight:900;font-style:italic;letter-spacing:-.06em;color:rgba(255,255,255,.12)}.switch-port-grid{margin-top:44px;padding:16px;background:rgba(0,0,0,.58);border:1px solid rgba(255,255,255,.06);border-radius:8px;display:grid;gap:8px}.switch-port-row{display:flex;justify-content:center;gap:8px}.switch-port{position:relative;flex-direction:column;gap:6px;padding:0;background:none;border:0;color:var(--foreground)}.switch-port__jack{width:34px;height:34px;border-radius:4px;border:2px solid #333;border-top:0;background:#111;position:relative}.switch-port[data-status='admin-down'] .switch-port__jack{background:#333;border-color:#555}.switch-port__jack::before{content:'';position:absolute;top:0;left:50%;transform:translateX(-50%);width:12px;height:6px;background:#222}.switch-port__jack::after{content:'';position:absolute;left:4px;right:4px;bottom:4px;height:4px;background:linear-gradient(90deg,#b8860b,#ffd700,#b8860b);opacity:.55}.switch-port__led{width:10px;height:5px;border-radius:999px;background:rgba(255,255,255,.16);box-shadow:0 0 10px rgba(255,255,255,.12)}.switch-port[data-status='up'] .switch-port__led{background:#22c55e;box-shadow:0 0 10px rgba(34,197,94,.65)}.switch-port[data-status='admin-down'] .switch-port__led{background:#ef4444;box-shadow:0 0 10px rgba(239,68,68,.55)}.switch-chassis__range{margin-top:16px;text-align:center;color:rgba(255,255,255,.3);letter-spacing:.3em;text-transform:uppercase}.switch-modal{position:absolute;inset:0;display:grid;place-items:center;padding:20px;background:rgba(0,0,0,.72);backdrop-filter:blur(8px)}.switch-modal__dialog{width:min(100%,420px);padding:22px;border-radius:18px;border:1px solid rgba(0,212,255,.28);background:linear-gradient(180deg,rgba(10,15,24,.96),rgba(5,9,16,.98));box-shadow:0 24px 60px rgba(0,0,0,.45)}.switch-modal__body,.switch-modal__field{display:grid;gap:12px}.switch-modal__body{margin-top:16px}.switch-modal__close{padding:0 10px;border-color:rgba(255,255,255,.12);background:transparent;color:rgba(255,255,255,.7)}.switch-toggle-group{gap:10px}.switch-toggle{flex:1;justify-content:center;padding:0 12px;border-color:rgba(255,255,255,.12);background:rgba(255,255,255,.04);color:rgba(255,255,255,.7)}.switch-toggle--danger.switch-toggle--active{border-color:rgba(255,68,68,.4);background:rgba(255,68,68,.16);color:#ff9c9c}.switch-toggle--active{border-color:rgba(34,197,94,.42);background:rgba(34,197,94,.12);color:#6ee7b7}.switch-modal__field input{min-height:44px;border-radius:12px;border:1px solid rgba(255,255,255,.12);background:rgba(0,0,0,.36);color:var(--foreground);padding:0 14px}.switch-modal__stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;padding:12px;border-radius:12px;border:1px solid rgba(255,255,255,.06);background:rgba(255,255,255,.04)}.switch-modal__stats div{flex-direction:column;align-items:flex-start;gap:4px}.switch-modal__save{justify-content:center;border-color:rgba(0,212,255,.35);background:rgba(0,212,255,.12);color:var(--cyber-cyan)}.switch-head__reload:focus-visible,.switch-port:focus-visible,.switch-modal__close:focus-visible,.switch-toggle:focus-visible,.switch-modal__field input:focus-visible,.switch-modal__save:focus-visible{outline:2px solid rgba(0,212,255,.7);outline-offset:2px}.switch-spin{animation:switch-spin 1s linear infinite}@keyframes switch-spin{to{transform:rotate(360deg)}}
</style>
