<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { apiCall } from '@/api/index'
import {
  workflowApi,
  type WorkflowCatalogNode,
  type WorkflowRecord,
  type WorkflowRunDetail,
  type WorkflowRunRecord,
  type WorkflowTemplate,
  type WorkflowTriggerType,
} from '@/api/workflow'
import WorkflowCanvas from '@/components/workflow/WorkflowCanvas.vue'
import WorkflowInspector from '@/components/workflow/WorkflowInspector.vue'
import WorkflowRunDialog from '@/components/workflow/WorkflowRunDialog.vue'
import WorkflowRunDetailDrawer from '@/components/workflow/WorkflowRunDetailDrawer.vue'
import WorkflowRunPanel from '@/components/workflow/WorkflowRunPanel.vue'
import WorkflowSidebar from '@/components/workflow/WorkflowSidebar.vue'
import WorkflowTemplateCenter from '@/components/workflow/WorkflowTemplateCenter.vue'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  createDefaultWorkflowDefinition,
  createWorkflowNode,
  defaultWorkflowCatalogNodes,
  normalizeWorkflowDefinition,
  toPersistedWorkflowDefinition,
} from '@/lib/workflow/defaults'

const workflows = ref<WorkflowRecord[]>([])
const runs = ref<WorkflowRunRecord[]>([])
const templates = ref<WorkflowTemplate[]>([])
const catalogNodes = ref<WorkflowCatalogNode[]>([...defaultWorkflowCatalogNodes])
const selectedWorkflowId = ref<number | null>(null)
const selectedNodeId = ref<string | null>(null)
const selectedRunDetail = ref<WorkflowRunDetail | null>(null)
const runDialogOpen = ref(false)
const runDetailOpen = ref(false)
const templateCenterOpen = ref(false)
const templateLoading = ref(false)
const loading = ref(false)
const saving = ref(false)
const running = ref(false)
const loadingRunDetail = ref(false)

const selectedWorkflow = computed(() => {
  return workflows.value.find((item) => item.id === selectedWorkflowId.value) ?? null
})

function normalizeWorkflowRecord(workflow: WorkflowRecord): WorkflowRecord {
  return {
    ...workflow,
    definition: normalizeWorkflowDefinition(workflow.definition),
  }
}

function triggerLabel(kind: WorkflowTriggerType) {
  if (kind === 'schedule') return '定时触发'
  if (kind === 'webhook') return 'Webhook 触发'
  return '手动触发'
}

function buildWorkflowPayload(kind: WorkflowTriggerType = 'manual') {
  const definition = createDefaultWorkflowDefinition()
  definition.nodes[0] = createWorkflowNode({ kind, type: 'trigger', label: triggerLabel(kind) }, { x: 0, y: 0 }, 'trigger-1')

  return {
    name: `AI工作流 ${workflows.value.length + 1}`,
    description: '基于 AI 工作流画布编排系统能力',
    category: 'ai',
    status: 'draft',
    trigger: {
      type: kind,
      enabled: true,
      ...(kind === 'schedule' ? { interval_seconds: 60 } : {}),
    },
    definition: toPersistedWorkflowDefinition(definition),
  }
}

function upsertWorkflow(workflow: WorkflowRecord) {
  const normalized = normalizeWorkflowRecord(workflow)
  workflows.value = [normalized, ...workflows.value.filter((item) => item.id !== normalized.id)]
  selectedWorkflowId.value = normalized.id
  selectedNodeId.value = null
  return normalized
}

async function loadWorkflows() {
  loading.value = true
  const [catalog, data] = await Promise.all([
    apiCall(() => workflowApi.catalog(), { silent: true }),
    apiCall(() => workflowApi.list()),
  ])
  loading.value = false

  catalogNodes.value = catalog?.nodes?.length ? catalog.nodes : [...defaultWorkflowCatalogNodes]
  workflows.value = (data ?? []).map(normalizeWorkflowRecord)

  if (!selectedWorkflowId.value && workflows.value.length > 0) {
    selectedWorkflowId.value = workflows.value[0].id
  }

  if (selectedWorkflowId.value) {
    await loadRuns(selectedWorkflowId.value)
  } else {
    runs.value = []
  }
}

async function loadTemplates() {
  templateLoading.value = true
  const data = await apiCall(() => workflowApi.templates(), { silent: true })
  templateLoading.value = false
  templates.value = data ?? []
}

async function loadRuns(workflowId: number) {
  const data = await apiCall(() => workflowApi.runs(workflowId), { silent: true })
  runs.value = data ?? []
}

async function handleCreateWorkflow(kind: WorkflowTriggerType = 'manual') {
  const created = await apiCall(() => workflowApi.create(buildWorkflowPayload(kind)))
  if (!created) return

  upsertWorkflow(created)
  runs.value = []
}

async function handleOpenTemplateCenter() {
  templateCenterOpen.value = true
  if (!templates.value.length) {
    await loadTemplates()
  }
}

function handleTemplateCenterOpenChange(value: boolean) {
  templateCenterOpen.value = value
}

async function handleInstantiateTemplate(templateId: string) {
  const created = await apiCall(() => workflowApi.instantiateTemplate(templateId, {}))
  if (!created) return

  upsertWorkflow(created)
  runs.value = []
  templateCenterOpen.value = false
}

function handleSelectWorkflow(workflow: WorkflowRecord) {
  selectedWorkflowId.value = workflow.id
  selectedNodeId.value = null
  selectedRunDetail.value = null
  runDetailOpen.value = false
  void loadRuns(workflow.id)
}

function handleUpdateDefinition(definition: WorkflowRecord['definition']) {
  if (!selectedWorkflow.value) return
  const normalizedDefinition = normalizeWorkflowDefinition(definition)
  workflows.value = workflows.value.map((item) => (item.id === selectedWorkflow.value?.id ? { ...item, definition: normalizedDefinition } : item))
}

async function handleSaveWorkflow() {
  const workflow = selectedWorkflow.value
  if (!workflow) return

  saving.value = true
  const saved = await apiCall(() =>
    workflowApi.update(workflow.id, {
      name: workflow.name,
      description: workflow.description,
      category: workflow.category,
      status: workflow.status,
      definition: toPersistedWorkflowDefinition(workflow.definition),
      trigger: workflow.trigger,
    }),
  )
  saving.value = false

  if (!saved) return
  upsertWorkflow(saved)
}

async function handlePublishWorkflow() {
  const workflow = selectedWorkflow.value
  if (!workflow) return

  const saved = await apiCall(() => workflowApi.publish(workflow.id))
  if (!saved) return
  upsertWorkflow(saved)
}

function handleOpenRunDialog() {
  if (!selectedWorkflow.value) return
  runDialogOpen.value = true
}

function handleRunDialogOpenChange(value: boolean) {
  runDialogOpen.value = value
}

function handleRunDetailOpenChange(value: boolean) {
  runDetailOpen.value = value
}

async function openRunDetail(runId: number) {
  loadingRunDetail.value = true
  runDetailOpen.value = true
  const detail = await apiCall(() => workflowApi.runDetail(runId), { silent: true })
  loadingRunDetail.value = false
  selectedRunDetail.value = detail ?? null
}

async function handleRunWorkflow(payload: Record<string, unknown>) {
  const workflow = selectedWorkflow.value
  if (!workflow) return

  running.value = true
  const result = await apiCall(() => workflowApi.run(workflow.id, { payload }))
  running.value = false

  if (!result) return

  runDialogOpen.value = false
  await loadRuns(workflow.id)
  await openRunDetail(result.id)
}

onMounted(async () => {
  await loadWorkflows()
})
</script>

<template>
  <div class="h-full overflow-auto p-6">
    <div class="mb-6 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div class="space-y-2">
        <h1 class="text-3xl font-bold tracking-tight">AI工作流</h1>
        <p class="max-w-prose text-sm leading-relaxed text-muted-foreground">
          将 AI、HFish、主机探测与防御动作编排成可执行工作流，支持手动触发、定时触发和 Webhook 触发。
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <Button variant="outline" class="cursor-pointer" @click="handleCreateWorkflow('manual')">新建工作流</Button>
        <Button variant="outline" class="cursor-pointer" @click="handleOpenTemplateCenter">模板中心</Button>
        <Button variant="outline" class="cursor-pointer" @click="handleCreateWorkflow('schedule')">快速定时流</Button>
        <Button variant="outline" class="cursor-pointer" @click="handleCreateWorkflow('webhook')">快速Webhook流</Button>
        <Button variant="outline" class="cursor-pointer" :disabled="!selectedWorkflow" @click="handlePublishWorkflow">发布</Button>
        <Button class="cursor-pointer" :disabled="!selectedWorkflow || running" @click="handleOpenRunDialog">
          {{ running ? '运行中...' : '立即运行' }}
        </Button>
      </div>
    </div>

    <div v-if="loading" class="rounded-xl border border-dashed border-border/60 px-6 py-10 text-center text-muted-foreground">
      正在加载工作流...
    </div>

    <div v-else class="grid grid-cols-1 gap-4 xl:grid-cols-[280px_minmax(0,1fr)_340px]">
      <WorkflowSidebar
        :workflows="workflows"
        :selected-workflow-id="selectedWorkflowId"
        @create="() => handleCreateWorkflow('manual')"
        @select="handleSelectWorkflow"
      />

      <div class="min-w-0 space-y-4">
        <Card v-if="selectedWorkflow" class="border-border/60 bg-card/80">
          <CardHeader class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div class="space-y-1">
              <CardTitle>{{ selectedWorkflow.name }}</CardTitle>
              <CardDescription>{{ selectedWorkflow.description || '未设置描述，可在右侧属性检查器中继续完善。' }}</CardDescription>
            </div>
            <Button variant="outline" class="cursor-pointer" :disabled="saving" @click="handleSaveWorkflow">
              {{ saving ? '保存中...' : '保存工作流' }}
            </Button>
          </CardHeader>
        </Card>

        <template v-if="selectedWorkflow">
          <WorkflowCanvas
            :definition="selectedWorkflow.definition"
            :catalog-nodes="catalogNodes"
            :selected-node-id="selectedNodeId"
            @update="handleUpdateDefinition"
            @select-node="(nodeId) => { selectedNodeId = nodeId }"
          />

          <WorkflowRunPanel :runs="runs" :loading="loadingRunDetail && !selectedRunDetail" @select-run="openRunDetail" />
        </template>

        <Card v-else class="border-border/60 bg-card/80">
          <CardContent class="py-12 text-center text-sm text-muted-foreground">
            还没有工作流，点击左上角按钮开始创建第一条 AI 工作流。
          </CardContent>
        </Card>
      </div>

      <div>
        <WorkflowInspector
          v-if="selectedWorkflow"
          :definition="selectedWorkflow.definition"
          :selected-node-id="selectedNodeId"
          @update="handleUpdateDefinition"
        />

        <Card v-else class="border-border/60 bg-card/80">
          <CardContent class="py-12 text-center text-sm text-muted-foreground">
            选择工作流后可在这里编辑节点属性。
          </CardContent>
        </Card>
      </div>
    </div>

    <WorkflowRunDialog :open="runDialogOpen" :running="running" @update:open="handleRunDialogOpenChange" @confirm="handleRunWorkflow" />
    <WorkflowRunDetailDrawer :open="runDetailOpen" :run="selectedRunDetail" @update:open="handleRunDetailOpenChange" />
    <WorkflowTemplateCenter
      :open="templateCenterOpen"
      :loading="templateLoading"
      :templates="templates"
      @update:open="handleTemplateCenterOpenChange"
      @instantiate="handleInstantiateTemplate"
    />
  </div>
</template>
