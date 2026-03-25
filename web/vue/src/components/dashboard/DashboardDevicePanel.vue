<script setup lang="ts">
import { computed, ref } from 'vue'
import DashboardSwitchManager from './DashboardSwitchManager.vue'
import { createTopologyFixture, getTopologySummary } from '@/lib/topology-state'

const props = withDefaults(defineProps<{
  hideSummaryCard?: boolean
}>(), {
  hideSummaryCard: false,
})

const topologyState = ref(createTopologyFixture())
const summary = computed(() => getTopologySummary(topologyState.value))
const coreNode = computed(() => topologyState.value.nodes.find((node) => node.id === 'core-switch'))
const honeypotNode = computed(() => topologyState.value.nodes.find((node) => node.type === 'honeypot'))
</script>

<template>
  <div class="device-panel-shell" aria-label="设备面板视图">
    <div class="device-panel-grid" :class="{ 'device-panel-grid--single': props.hideSummaryCard }">
      <div v-if="!props.hideSummaryCard" class="device-panel-card">
        <span class="device-panel-card__eyebrow">SELECTED NODE</span>
        <strong>{{ coreNode?.label || '核心数据中心节点' }}</strong>
        <p>switch · {{ coreNode?.status || 'online' }}</p>

        <ul class="device-panel-card__list">
          <li><span>核心骨干</span><strong>{{ summary.linkCount }} 条链路</strong></li>
          <li><span>边界隔离</span><strong>1 条阻断</strong></li>
          <li><span>蜜罐联动</span><strong>{{ honeypotNode?.label || '诱捕蜜罐' }}</strong></li>
          <li><span>异常侦测</span><strong>{{ summary.warningCount + summary.attackCount }} 项</strong></li>
        </ul>
      </div>

      <DashboardSwitchManager />
    </div>
  </div>
</template>

<style scoped>
.device-panel-shell {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.device-panel-grid {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 12px;
  width: 100%;
  min-height: 0;
}

.device-panel-grid--single {
  grid-template-columns: minmax(0, 1fr);
}

.device-panel-card {
  border-radius: 16px;
  border: 1px solid var(--border);
  background: var(--secondary);
  box-shadow: var(--shadow);
  padding: 12px;
  height: fit-content;
}

.device-panel-card__eyebrow {
  display: inline-flex;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid hsl(var(--primary) / 0.3);
  background: hsl(var(--primary) / 0.1);
  color: hsl(var(--primary) / 0.9);
  font-size: 10px;
  letter-spacing: 0.14em;
}

.device-panel-card strong {
  display: block;
  margin-top: 8px;
  font-size: 14px;
  color: var(--foreground);
}

.device-panel-card p {
  margin: 8px 0 0;
  color: var(--muted-foreground);
  font-size: 12px;
  text-transform: lowercase;
}

.device-panel-card__list {
  list-style: none;
  padding: 0;
  margin: 10px 0 0;
}

.device-panel-card__list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
}

.device-panel-card__list li + li {
  margin-top: 6px;
}

.device-panel-card__list span {
  color: var(--muted-foreground);
}

.device-panel-card__list strong {
  margin: 0;
  color: rgb(165 243 252);
  font-size: 11px;
}

@media (max-width: 1200px) {
  .device-panel-grid {
    grid-template-columns: 1fr;
  }
}
</style>
