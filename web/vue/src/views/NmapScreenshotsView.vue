<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api, apiCall } from '@/api/index'
import { getToken } from '@/api/index'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
} from '@/components/ui/dialog'
import {
  Search,
  Camera,
  X,
  Monitor,
  ExternalLink,
  RefreshCw,
} from 'lucide-vue-next'

const loading = ref(false)
const screenshots = ref<any[]>([])
const search = ref('')
const previewDlg = ref(false)
const previewImg = ref('')
const previewTitle = ref('')

const filteredScreenshots = computed(() => {
  if (!search.value) return screenshots.value
  const s = search.value.toLowerCase()
  return screenshots.value.filter(sh =>
    (sh.ip || '').toLowerCase().includes(s) ||
    (sh.url || '').toLowerCase().includes(s) ||
    String(sh.port).includes(s)
  )
})

async function loadScreenshots() {
  loading.value = true
  const d = await apiCall<any[]>(async () =>
    api.get<any>('/api/nmap/screenshots/all')
  )
  if (d) {
    screenshots.value = Array.isArray(d) ? d : (d as any)?.data ?? []
  }
  loading.value = false
}

function getScreenshotUrl(ip: string, port: number) {
  const token = getToken() || ''
  return `/api/nmap/screenshot/${encodeURIComponent(ip)}/${port}?token=${encodeURIComponent(token)}&t=${Date.now()}`
}

function viewScreenshot(sh: any) {
  previewImg.value = getScreenshotUrl(sh.ip, sh.port)
  previewTitle.value = `${sh.ip}:${sh.port} — ${sh.url || ''}`
  previewDlg.value = true
}

onMounted(loadScreenshots)
</script>

<template>
  <div class="p-6 space-y-6">
    <!-- Header Card -->
    <Card class="border-border/50">
      <CardContent class="p-5 flex flex-col gap-4">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div class="flex items-center gap-3">
            <div class="bg-primary/10 p-2 rounded-lg">
              <Camera :size="20" class="text-primary" />
            </div>
            <div>
              <h2 class="text-lg font-semibold">Web 截图画廊</h2>
              <p class="text-xs text-muted-foreground mt-0.5">共 {{ screenshots.length }} 张截图</p>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <div class="relative w-64">
              <Search :size="16" class="absolute left-2.5 top-2.5 text-muted-foreground" />
              <Input
                v-model="search"
                placeholder="搜索 IP、端口、URL..."
                class="pl-9 h-9 bg-black/20"
              />
            </div>
            <Button variant="ghost" size="icon" @click="loadScreenshots" :disabled="loading">
              <RefreshCw :size="16" :class="{ 'animate-spin': loading }" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>

    <!-- Screenshot Grid -->
    <div v-if="loading && screenshots.length === 0" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      <div v-for="i in 8" :key="i" class="rounded-xl border border-border/50 overflow-hidden">
        <div class="aspect-[4/3] bg-muted/40 animate-pulse"></div>
        <div class="p-3 space-y-2">
          <div class="h-4 bg-muted/40 rounded animate-pulse w-3/4"></div>
          <div class="h-3 bg-muted/40 rounded animate-pulse w-1/2"></div>
        </div>
      </div>
    </div>

    <div v-else-if="filteredScreenshots.length > 0" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      <div
        v-for="sh in filteredScreenshots"
        :key="`${sh.ip}-${sh.port}`"
        class="rounded-xl border border-border/50 overflow-hidden bg-card hover:border-primary/40 transition-all cursor-pointer group"
        @click="viewScreenshot(sh)"
      >
        <!-- Thumbnail -->
        <div class="aspect-[4/3] bg-muted/20 relative overflow-hidden">
          <img
            :src="getScreenshotUrl(sh.ip, sh.port)"
            :alt="`${sh.ip}:${sh.port}`"
            class="w-full h-full object-cover object-top"
            @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }"
          />
          <!-- Overlay on hover -->
          <div class="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-all flex items-center justify-center">
            <ExternalLink :size="28" class="text-white opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
          <!-- Port badge -->
          <div class="absolute top-2 right-2">
            <Badge variant="secondary" class="bg-black/60 text-white border-0 text-xs px-2 py-0.5 font-mono">
              :{{ sh.port }}
            </Badge>
          </div>
        </div>

        <!-- Info -->
        <div class="p-3 space-y-1.5">
          <div class="flex items-center gap-2">
            <Monitor :size="12" class="text-muted-foreground shrink-0" />
            <span class="text-sm font-bold text-foreground truncate">{{ sh.ip }}</span>
          </div>
          <div class="text-[11px] text-muted-foreground truncate font-mono" :title="sh.url || ''">
            {{ sh.url || '—' }}
          </div>
          <div v-if="sh.scan_time" class="text-[10px] text-muted-foreground/60">
            {{ sh.scan_time?.slice(0, 16) }}
          </div>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else class="flex flex-col items-center justify-center py-24 text-muted-foreground">
      <Camera :size="48" class="mb-4 opacity-30" />
      <p class="text-sm font-medium">暂无截图记录</p>
      <p class="text-xs mt-1">网络扫描时将对 Web 服务自动截图</p>
    </div>

    <!-- Preview Dialog -->
    <Dialog v-model:open="previewDlg">
      <DialogContent class="sm:max-w-[1000px] bg-background border-border text-foreground p-0 overflow-hidden max-h-[90vh] flex flex-col">
        <div class="p-4 bg-muted/50 border-b border-border/60 flex items-center justify-between shrink-0">
          <div class="min-w-0 flex-1 mr-4">
            <p class="text-sm font-semibold truncate">{{ previewTitle }}</p>
          </div>
          <Button variant="ghost" size="icon" class="h-7 w-7 shrink-0" @click="previewDlg = false">
            <X class="h-4 w-4" />
          </Button>
        </div>
        <ScrollArea class="flex-1 bg-muted/10">
          <img
            v-if="previewImg"
            :src="previewImg"
            :alt="previewTitle"
            class="w-full h-auto"
          />
          <div v-else class="flex items-center justify-center h-64 text-muted-foreground text-sm">
            截图加载中...
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  </div>
</template>
