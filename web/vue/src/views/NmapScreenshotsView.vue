<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api, apiCall, getToken } from '@/api/index'
import { defenseApi, type TerminalEvidenceItem } from '@/api/defense'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { Search, Camera, X, Monitor, ExternalLink, RefreshCw, Clock, AlertTriangle } from 'lucide-vue-next'

type MixedEvidence = {
  id: string
  channel: 'nmap' | 'terminal'
  level: 'normal' | 'high'
  title: string
  subtitle: string
  time: string
  mtime: number
  imageUrl: string
  raw: Record<string, any>
}

const loading = ref(false)
const screenshots = ref<any[]>([])
const terminalEvidence = ref<TerminalEvidenceItem[]>([])
const keyword = ref('')

const previewDlg = ref(false)
const previewImages = ref<Array<{ label: string; url: string }>>([])
const activePreviewIndex = ref(0)
const previewTitle = ref('')
const previewMeta = ref<Array<{ label: string; value: string }>>([])

const activePreviewImage = computed(() => previewImages.value[activePreviewIndex.value]?.url || '')

function parseTimeToMtime(raw: string | undefined): number {
  if (!raw) return 0
  const ts = Date.parse(raw.replace(' ', 'T'))
  return Number.isNaN(ts) ? 0 : Math.floor(ts / 1000)
}

function getScreenshotUrl(ip: string, port: number, fresh = false) {
  const token = getToken() || ''
  const base = `/api/nmap/screenshot/${encodeURIComponent(ip)}/${port}?token=${encodeURIComponent(token)}`
  return fresh ? `${base}&t=${Date.now()}` : base
}

const mergedEvidence = computed<MixedEvidence[]>(() => {
  const nmapItems: MixedEvidence[] = screenshots.value.map((sh: any) => ({
    id: `nmap-${sh.ip}-${sh.port}-${sh.scan_time || ''}`,
    channel: 'nmap',
    level: 'normal',
    title: `${sh.ip}:${sh.port}`,
    subtitle: sh.url || 'Web 扫描截图',
    time: sh.scan_time || '-',
    mtime: parseTimeToMtime(sh.scan_time),
    imageUrl: getScreenshotUrl(sh.ip, sh.port),
    raw: sh,
  }))

  const terminalItems: MixedEvidence[] = terminalEvidence.value.map((item) => ({
    id: `terminal-${item.event_key}`,
    channel: 'terminal',
    level: 'high',
    title: item.is_combined ? '终端取证回传（截图+摄像头）' : `终端${item.capture_summary}回传`,
    subtitle: [item.screenshot_filename, item.camera_filename].filter(Boolean).join(' | ') || item.filename,
    time: item.time,
    mtime: item.mtime,
    imageUrl: item.preview_url || item.url,
    raw: item as unknown as Record<string, any>,
  }))

  return [...nmapItems, ...terminalItems].sort((a, b) => b.mtime - a.mtime)
})

const filteredEvidence = computed(() => {
  if (!keyword.value) return mergedEvidence.value
  const s = keyword.value.toLowerCase()
  return mergedEvidence.value.filter((item) =>
    item.title.toLowerCase().includes(s) ||
    item.subtitle.toLowerCase().includes(s) ||
    item.time.toLowerCase().includes(s) ||
    item.channel.toLowerCase().includes(s),
  )
})

async function loadScreenshots() {
  const d = await apiCall<any[]>(async () => api.get<any>('/api/nmap/screenshots/all'))
  if (d) {
    screenshots.value = Array.isArray(d) ? d : (d as any)?.data ?? []
  }
}

async function loadTerminalEvidence() {
  const d = await apiCall(async () => defenseApi.getTerminalEvidence(500))
  if (d) {
    terminalEvidence.value = Array.isArray(d.items) ? d.items : []
  }
}

async function refreshAll() {
  loading.value = true
  try {
    await Promise.all([loadScreenshots(), loadTerminalEvidence()])
  } finally {
    loading.value = false
  }
}

function openEvidence(item: MixedEvidence) {
  if (item.channel === 'terminal' && item.raw.is_combined) {
    previewImages.value = [
      { label: '终端截图', url: item.raw.screenshot_url || item.imageUrl },
      { label: '终端摄像头', url: item.raw.camera_url || item.imageUrl },
    ].filter((x) => Boolean(x.url))
  } else {
    previewImages.value = [{
      label: item.channel === 'terminal' ? '终端取证图像' : '扫描截图',
      url: item.channel === 'nmap' ? getScreenshotUrl(item.raw.ip, item.raw.port, true) : item.imageUrl,
    }]
  }
  activePreviewIndex.value = 0
  previewTitle.value = item.title

  if (item.channel === 'terminal') {
    previewMeta.value = [
      { label: '数据来源', value: '终端取证回传' },
      { label: '风险等级', value: '高危' },
      { label: '取证类型', value: item.raw.capture_summary || '-' },
      { label: '截图文件', value: item.raw.screenshot_filename || '-' },
      { label: '摄像头文件', value: item.raw.camera_filename || '-' },
      { label: '回传时间', value: item.raw.time || '-' },
      { label: '截图路径', value: item.raw.screenshot_url || '-' },
      { label: '摄像头路径', value: item.raw.camera_url || '-' },
    ]
  } else {
    previewMeta.value = [
      { label: '数据来源', value: '网络扫描' },
      { label: '风险等级', value: '常规' },
      { label: '目标地址', value: item.raw.ip || '-' },
      { label: '目标端口', value: String(item.raw.port ?? '-') },
      { label: '目标 URL', value: item.raw.url || '-' },
      { label: '扫描时间', value: item.raw.scan_time || '-' },
    ]
  }

  previewDlg.value = true
}

onMounted(async () => {
  await refreshAll()
})
</script>

<template>
  <div class="p-6 space-y-6">
    <Card class="border-border/50">
      <CardContent class="p-5 flex flex-col gap-4">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div class="flex items-center gap-3">
            <div class="bg-primary/10 p-2 rounded-lg">
              <Camera :size="20" class="text-primary" />
            </div>
            <div>
              <h2 class="text-lg font-semibold">截图取证</h2>
              <p class="text-xs text-muted-foreground mt-0.5">统一时间流展示，终端回传会以红色高危卡片突出显示</p>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <Button variant="ghost" size="icon" @click="refreshAll" :disabled="loading">
              <RefreshCw :size="16" :class="{ 'animate-spin': loading }" />
            </Button>
          </div>
        </div>

        <div class="relative w-full max-w-md">
          <Search :size="16" class="absolute left-2.5 top-2.5 text-muted-foreground" />
          <Input
            v-model="keyword"
            placeholder="搜索 IP、端口、URL、文件名、时间..."
            class="pl-9 h-9 bg-black/20"
          />
        </div>
      </CardContent>
    </Card>

    <div v-if="loading && mergedEvidence.length === 0" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      <div v-for="i in 8" :key="i" class="rounded-xl border border-border/50 overflow-hidden">
        <div class="aspect-[4/3] bg-muted/40 animate-pulse"></div>
        <div class="p-3 space-y-2">
          <div class="h-4 bg-muted/40 rounded animate-pulse w-3/4"></div>
          <div class="h-3 bg-muted/40 rounded animate-pulse w-1/2"></div>
        </div>
      </div>
    </div>

    <div v-else-if="filteredEvidence.length > 0" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      <div
        v-for="item in filteredEvidence"
        :key="item.id"
        class="rounded-xl border overflow-hidden transition-all cursor-pointer group"
        :class="item.channel === 'terminal'
          ? 'border-red-500/50 bg-red-950/25 hover:border-red-400'
          : 'border-border/50 bg-card hover:border-primary/40'"
        @click="openEvidence(item)"
      >
        <div class="aspect-[4/3] bg-muted/20 relative overflow-hidden">
          <div
            v-if="item.channel === 'terminal' && item.raw.is_combined && item.raw.screenshot_url && item.raw.camera_url"
            class="grid grid-cols-2 gap-1 h-full p-1"
          >
            <div class="relative overflow-hidden rounded-sm bg-black/50">
              <img
                :src="item.raw.screenshot_url"
                alt="终端截图"
                class="w-full h-full object-cover object-top"
                @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }"
              />
            </div>
            <div class="relative overflow-hidden rounded-sm bg-black/50">
              <img
                :src="item.raw.camera_url"
                alt="终端摄像头"
                class="w-full h-full object-cover object-top"
                @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }"
              />
            </div>
          </div>
          <img
            v-else
            :src="item.imageUrl"
            :alt="item.title"
            class="w-full h-full object-cover object-top"
            @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }"
          />
          <div class="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-all flex items-center justify-center">
            <ExternalLink :size="28" class="text-white opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>

          <div class="absolute top-2 left-2">
            <Badge
              variant="secondary"
              :class="item.channel === 'terminal'
                ? 'bg-red-600/90 text-white border-0'
                : 'bg-black/60 text-white border-0'"
              class="text-[10px] px-2 py-0.5"
            >
              {{ item.channel === 'terminal' ? '高危回传' : '扫描截图' }}
            </Badge>
          </div>

          <div v-if="item.channel === 'terminal' && item.raw.is_combined" class="absolute top-8 left-2">
            <Badge variant="secondary" class="bg-red-300/90 text-red-900 border-0 text-[10px] px-2 py-0.5">
              截图+摄像头
            </Badge>
          </div>

          <div v-if="item.channel === 'nmap'" class="absolute top-2 right-2">
            <Badge variant="secondary" class="bg-black/60 text-white border-0 text-xs px-2 py-0.5 font-mono">
              :{{ item.raw.port }}
            </Badge>
          </div>

          <div v-else class="absolute top-2 right-2">
            <AlertTriangle :size="16" class="text-red-200" />
          </div>
        </div>

        <div class="p-3 space-y-1.5" :class="item.channel === 'terminal' ? 'bg-red-950/30' : ''">
          <div class="flex items-center gap-2">
            <Monitor :size="12" class="text-muted-foreground shrink-0" />
            <span class="text-sm font-bold text-foreground truncate">{{ item.title }}</span>
          </div>
          <div class="text-[11px] text-muted-foreground truncate font-mono" :title="item.subtitle">
            {{ item.subtitle }}
          </div>
          <div class="text-[10px] text-muted-foreground/80 flex items-center gap-1.5">
            <Clock :size="10" /> {{ item.time || '-' }}
          </div>
        </div>
      </div>
    </div>

    <div v-else class="flex flex-col items-center justify-center py-24 text-muted-foreground">
      <Camera :size="48" class="mb-4 opacity-30" />
      <p class="text-sm font-medium">暂无截图取证记录</p>
      <p class="text-xs mt-1">当扫描或终端回传发生后，这里会按时间统一展示</p>
    </div>

    <Dialog v-model:open="previewDlg">
      <DialogContent class="sm:max-w-[1240px] bg-background border-border text-foreground p-0 overflow-hidden max-h-[92vh] flex flex-col">
        <DialogTitle class="sr-only">截图取证详情预览</DialogTitle>
        <DialogDescription class="sr-only">提供原始高清图像预览和对应元数据，可在终端截图与摄像头图像间切换。</DialogDescription>
        <div class="p-4 bg-muted/50 border-b border-border/60 flex items-center justify-between shrink-0">
          <div class="min-w-0 flex-1 mr-4">
            <p class="text-sm font-semibold truncate">{{ previewTitle }}</p>
          </div>
          <Button variant="ghost" size="icon" class="h-7 w-7 shrink-0" @click="previewDlg = false">
            <X class="h-4 w-4" />
          </Button>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_340px] min-h-0 flex-1">
          <ScrollArea class="bg-muted/10 min-h-0">
            <div v-if="activePreviewImage" class="p-3 md:p-5 space-y-3">
              <div class="rounded-md border border-border/50 bg-black/40 overflow-hidden min-h-[55vh] flex items-center justify-center">
                <img
                  :src="activePreviewImage"
                  :alt="previewTitle"
                  class="max-h-[75vh] w-auto max-w-full object-contain"
                />
              </div>
              <div v-if="previewImages.length > 1" class="grid grid-cols-2 gap-2">
                <button
                  v-for="(img, idx) in previewImages"
                  :key="img.label"
                  type="button"
                  class="rounded-md border px-3 py-2 text-xs text-left transition-colors"
                  :class="idx === activePreviewIndex ? 'border-primary bg-primary/10 text-primary' : 'border-border/60 bg-card/50 text-muted-foreground hover:bg-muted/40'"
                  @click="activePreviewIndex = idx"
                >
                  {{ img.label }}
                </button>
              </div>
            </div>
            <div v-else class="flex items-center justify-center h-64 text-muted-foreground text-sm">
              截图加载中...
            </div>
          </ScrollArea>

          <div class="border-l border-border/60 bg-card/60 p-4 space-y-3">
            <h3 class="text-sm font-semibold">返回数据详情</h3>
            <a
              v-if="activePreviewImage"
              :href="activePreviewImage"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center text-xs text-primary hover:underline"
            >
              <ExternalLink :size="12" class="mr-1" />
              打开原图（高清）
            </a>
            <div class="space-y-2">
              <div
                v-for="meta in previewMeta"
                :key="meta.label"
                class="rounded-md border border-border/60 bg-black/20 px-3 py-2"
              >
                <p class="text-[10px] text-muted-foreground">{{ meta.label }}</p>
                <p class="text-xs text-foreground mt-1 break-all">{{ meta.value }}</p>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>
