<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useUiStore } from '@/stores/ui'







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











const uiStore = useUiStore()
const isDark = computed(() => uiStore.theme === 'dark')

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





  <section class="switch-shell" :class="{ 'switch-shell--dark': isDark }" aria-label="设备面板">





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





      <div class="switch-chassis" :class="{ 'switch-chassis--dark': isDark }">





        <div class="switch-chassis__lights"><span></span><span></span></div>





        <div class="switch-chassis__brand">RUIJIE</div>





        <div class="switch-port-grid" :class="{ 'switch-port-grid--dark': isDark }">





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





<DialogContent class="sm:max-w-[425px] border-border/80 bg-slate-200/82 backdrop-blur-xl text-slate-800 dark:border-white/10 dark:bg-[#0b1220]/96 dark:text-slate-100">





        <DialogHeader>





          <DialogTitle>{{ selectedPort?.name }} 配置</DialogTitle>





          <DialogDescription class="text-primary/70">





            修改当前物理端口的状态和 VLAN 划分。





          </DialogDescription>





        </DialogHeader>











        <div class="grid gap-6 py-4" v-if="selectedPort">





          <label class="grid gap-2">





            <span class="text-sm font-medium text-primary/70">Port Status (Admin)</span>





            <div class="flex gap-2">





              <button





                type="button"





                class="flex-1 py-2 px-3 rounded-md transition-all duration-200 text-sm font-medium border"





:class="editStatus === 'up' ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-600' : 'bg-slate-200/80 border-slate-400/35 text-slate-600'"





                @click="editStatus = 'up'"





              >





                UP (Enable)





              </button>





              <button





                type="button"





                class="flex-1 py-2 px-3 rounded-md transition-all duration-200 text-sm font-medium border"





:class="editStatus === 'admin-down' ? 'bg-red-500/20 border-red-500/50 text-red-600' : 'bg-slate-100 border-slate-200 text-slate-500'"





                @click="editStatus = 'admin-down'"





              >





                DOWN (Shutdown)





              </button>





            </div>





          </label>











          <label class="grid gap-2">





            <span class="text-sm font-medium text-primary/70">Access VLAN</span>





            <input





              v-model.number="editVlan"





              type="number"





              min="1"





              max="4094"





class="w-full rounded-md border border-primary/25 bg-slate-200/76 px-3 py-2 text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all font-mono"





            />





          </label>











<div class="grid grid-cols-2 gap-3 p-3 rounded-lg border border-primary/20 bg-primary/5">





            <div class="flex flex-col gap-1">





              <span class="text-[10px] text-primary/70/60 uppercase tracking-wider">Speed</span>





<strong class="text-sm text-primary font-mono">{{ selectedPort.speed }}</strong>





            </div>





            <div class="flex flex-col gap-1">





              <span class="text-[10px] text-primary/70/60 uppercase tracking-wider">Inbound / Outbound</span>





<strong class="text-sm text-primary font-mono">{{ selectedPort.tx }} M / {{ selectedPort.rx }} M</strong>





            </div>





          </div>





        </div>











        <DialogFooter>





          <button





            type="button"





            class="w-full justify-center rounded-md bg-primary/10 px-4 py-2 text-sm font-medium text-primary border border-primary/30   transition-all focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-slate-900 disabled:opacity-50 disabled:cursor-not-allowed"





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
.switch-shell {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  border-radius: 20px;
  overflow: hidden;

  --switch-bg: linear-gradient(180deg, hsl(var(--card)), hsl(var(--secondary)));
  --switch-border: rgba(0, 0, 0, 0.08);
  --switch-text-muted: rgba(0, 0, 0, 0.5);
  --switch-heading: #0f172a;
  --chassis-bg: #dbe2ea;
  --chassis-border: #c9d2dd;
  --chassis-shadow: rgba(0, 0, 0, 0.1);
  --brand-color: rgba(0, 0, 0, 0.08);
  --port-bg: rgba(255, 255, 255, 0.5);
  --port-border: rgba(0, 0, 0, 0.1);
  --jack-bg: #334155;
  --jack-border: #475569;

  background: var(--switch-bg);
  border: 1px solid var(--switch-border);
}

:global(html.dark) .switch-shell,
.switch-shell--dark {
  --switch-bg: linear-gradient(180deg, rgba(3, 8, 20, .98), rgba(8, 12, 22, .99));
  --switch-border: rgba(0, 0, 0, .65);
  --switch-text-muted: #cbd5e1 !important;
  --switch-heading: #f1f5f9 !important;
  --chassis-bg: linear-gradient(180deg, #0b0f17, #121821);
  --chassis-border: #05070c;
  --chassis-shadow: rgba(0, 0, 0, .55);
  --brand-color: rgba(255, 255, 255, .12);
  --port-bg: rgba(2, 6, 23, .82);
  --port-border: rgba(148, 163, 184, .12);
  --jack-bg: #0b0f14;
  --jack-border: #2b3442;

  background: var(--switch-bg) !important;
  border-color: var(--switch-border) !important;
}

.switch-head,
.switch-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px;
  border-bottom: 1px solid var(--switch-border);
}

.switch-head__identity,
.switch-head p,
.switch-head__reload,
.switch-summary,
.switch-port,
.switch-modal__head,
.switch-toggle-group,
.switch-modal__stats div {
  display: flex;
  align-items: center;
}

.switch-head__identity {
  gap: 14px;
}

.switch-icon {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border-radius: 14px;
  color: var(--primary);
  border: 1px solid hsl(var(--primary) / 0.2);
  background: hsl(var(--primary) / 0.08);
}

.switch-icon svg,
.switch-head__reload svg {
  width: 22px;
  height: 22px;
}

.switch-head h3,
.switch-modal__head h4 {
  margin: 0;
  color: var(--switch-heading);
}

.switch-head p,
.switch-modal__stats span {
  margin: 0;
  font: 11px/1.4 'JetBrains Mono', monospace;
  color: var(--switch-text-muted);
}

.switch-head p {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.switch-head p strong {
  color: hsl(var(--primary));
}

.switch-head__reload,
.switch-modal__close,
.switch-toggle,
.switch-modal__save {
  min-height: 44px;
  border-radius: 12px;
  border: 1px solid transparent;
  transition: background-color .18s ease, border-color .18s ease, opacity .18s ease;
}

.switch-head__reload,
.switch-modal__save {
  padding: 0 14px;
  font-weight: 600;
}

.switch-head__reload {
  border-color: var(--switch-border);
  background: rgba(125, 125, 125, 0.05);
  color: var(--foreground);
  gap: 10px;
}

.switch-summary span,
.switch-chassis__range,
.switch-port__id,
.switch-modal__field span,
.switch-modal__stats strong {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
}

.switch-summary strong,
.switch-modal__stats strong {
  color: hsl(var(--primary));
}

.switch-stage {
  flex: 1;
  min-height: 0;
  display: grid;
  place-items: center;
  padding: 16px;
  overflow: hidden;
}

.switch-chassis {
  position: relative;
  width: min(100%, 860px);
  max-width: 100%;
  padding: 20px;
  border-radius: 12px;
  border: 2px solid var(--chassis-border);
  background: var(--chassis-bg);
  box-shadow: 0 16px 40px var(--chassis-shadow);
}

.switch-chassis--dark {
  background: linear-gradient(180deg, #0b0f17, #121821) !important;
  border-color: #05070c !important;
}

.switch-chassis__lights {
  position: absolute;
  top: 12px;
  left: 18px;
  display: flex;
  gap: 6px;
}

.switch-chassis__lights span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
}

.switch-chassis__lights span:first-child {
  background: #22c55e;
  box-shadow: 0 0 12px #22c55e;
}

.switch-chassis__lights span:last-child {
  background: #3b82f6;
}

.switch-chassis__brand {
  position: absolute;
  right: 26px;
  top: 24px;
  font-size: 34px;
  font-weight: 900;
  font-style: italic;
  letter-spacing: -.06em;
  color: var(--brand-color);
}

.switch-port-grid {
  margin-top: 44px;
  padding: 16px;
  background: var(--port-bg);
  border: 1px solid var(--port-border);
  border-radius: 8px;
  display: grid;
  gap: 8px;
}

.switch-port-grid--dark {
  background: rgba(2, 6, 23, .82) !important;
  border-color: rgba(148, 163, 184, .12) !important;
}

.switch-port-row {
  display: flex;
  justify-content: center;
  gap: 8px;
}

.switch-port {
  position: relative;
  flex-direction: column;
  gap: 6px;
  padding: 0;
  background: none;
  border: 0;
  color: var(--foreground);
}

.switch-port__jack {
  width: 34px;
  height: 34px;
  border-radius: 4px;
  border: 2px solid var(--jack-border);
  border-top: 0;
  background: var(--jack-bg);
  position: relative;
}

.switch-port[data-status='admin-down'] .switch-port__jack {
  background: #333;
  border-color: #555;
}

.switch-port__jack::before {
  content: '';
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 12px;
  height: 6px;
  background: #222;
}

.switch-port__jack::after {
  content: '';
  position: absolute;
  left: 4px;
  right: 4px;
  bottom: 4px;
  height: 4px;
  background: linear-gradient(90deg, #b8860b, #ffd700, #b8860b);
  opacity: .55;
}

.switch-port__led {
  width: 10px;
  height: 5px;
  border-radius: 999px;
  background: rgba(125, 125, 125, 0.4);
  box-shadow: 0 0 10px rgba(0, 0, 0, .05);
}

:global(html.dark) .switch-port__led {
  background: rgba(255, 255, 255, .16);
  box-shadow: 0 0 10px rgba(255, 255, 255, .12);
}

:global(html.dark) .switch-head h3 {
  color: #f1f5f9 !important;
}

:global(html.dark) .switch-head p {
  color: #cbd5e1 !important;
}

:global(html.dark) .switch-head p span {
  color: #cbd5e1 !important;
}

:global(html.dark) .switch-head p strong {
  color: #67e8f9 !important;
}

:global(html.dark) .switch-summary strong {
  color: #67e8f9 !important;
}

:global(html.dark) .switch-shell .switch-head h3 {
  color: #f1f5f9 !important;
}

:global(html.dark) .switch-shell .switch-head p {
  color: #cbd5e1 !important;
}

:global(html.dark) .switch-shell .switch-head p span {
  color: #cbd5e1 !important;
}

:global(html.dark) .switch-shell .switch-head p strong {
  color: #67e8f9 !important;
}

:global(html.dark) section.switch-shell .switch-head__identity h3 {
  color: #f1f5f9 !important;
}

:global(html.dark) section.switch-shell .switch-head__identity p {
  color: #cbd5e1 !important;
}

:global(html.dark) section.switch-shell .switch-head__identity p span {
  color: #cbd5e1 !important;
}

:global(html.dark) section.switch-shell .switch-head__identity p strong {
  color: #67e8f9 !important;
}

:global(html.dark) .switch-chassis {
  background: #121316 !important;
  border-color: #000000 !important;
}

:global(html.dark) .switch-summary span {
  color: #94a3b8 !important;
}

:global(html.dark) .switch-head__reload {
  color: #cbd5e1 !important;
}

:global(html.dark) .switch-head__reload span {
  color: #cbd5e1 !important;
}

:global(html.dark) .switch-chassis__range {
  color: #94a3b8 !important;
}

:global(html.dark) .switch-port__id {
  color: #cbd5e1 !important;
}

.switch-port[data-status='up'] .switch-port__led {
  background: #22c55e;
  box-shadow: 0 0 10px rgba(34, 197, 94, .65);
}

.switch-port[data-status='admin-down'] .switch-port__led {
  background: #ef4444;
  box-shadow: 0 0 10px rgba(239, 68, 68, .55);
}

.switch-chassis__range {
  margin-top: 16px;
  text-align: center;
  color: var(--switch-text-muted);
  letter-spacing: .3em;
  text-transform: uppercase;
}

.switch-modal {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(0, 0, 0, .72);
  backdrop-filter: blur(8px);
}

.switch-modal__dialog {
  width: min(100%, 420px);
  padding: 22px;
  border-radius: 18px;
  border: 1px solid hsl(var(--primary) / 0.3);
  background: var(--card);
  box-shadow: 0 24px 60px rgba(0, 0, 0, .45);
}

.switch-modal__body,
.switch-modal__field {
  display: grid;
  gap: 12px;
}

.switch-modal__body {
  margin-top: 16px;
}

.switch-modal__close {
  padding: 0 10px;
  border-color: var(--border);
  background: transparent;
  color: var(--muted-foreground);
}

.switch-toggle-group {
  gap: 10px;
}

.switch-toggle {
  flex: 1;
  justify-content: center;
  padding: 0 12px;
  border-color: var(--border);
  background: var(--muted);
  color: var(--muted-foreground);
}

.switch-toggle--danger.switch-toggle--active {
  border-color: rgba(255, 68, 68, .4);
  background: rgba(255, 68, 68, .16);
  color: #ff9c9c;
}

.switch-toggle--active {
  border-color: hsl(var(--primary) / 0.4);
  background: hsl(var(--primary) / 0.1);
  color: hsl(var(--primary));
}

.switch-modal__field input {
  min-height: 44px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--input);
  color: var(--foreground);
  padding: 0 14px;
}

.switch-modal__stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--muted);
}

.switch-modal__stats div {
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.switch-modal__save {
  justify-content: center;
  border-color: hsl(var(--primary) / 0.3);
  background: hsl(var(--primary) / 0.1);
  color: hsl(var(--primary));
}

.switch-head__reload:focus-visible,
.switch-port:focus-visible,
.switch-modal__close:focus-visible,
.switch-toggle:focus-visible,
.switch-modal__field input:focus-visible,
.switch-modal__save:focus-visible {
  outline: 2px solid hsl(var(--primary) / 0.7);
  outline-offset: 2px;
}

.switch-spin {
  animation: switch-spin 1s linear infinite;
}

@keyframes switch-spin {
  to {
    transform: rotate(360deg)
  }
}
</style>











