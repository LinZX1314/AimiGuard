<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/index'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import {
  ClipboardList,
  Calendar,
  Clock,
  ExternalLink,
  Search,
  Trash2,
  FileText,
  Shield,
  MessageSquare
} from 'lucide-vue-next'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Input } from '@/components/ui/input'

interface Report {
  session_id: number
  title: string
  created_at: string
  updated_at: string
  report: string
  summary: string
  is_html: boolean
  original_input: string | null
}

const reports = ref<Report[]>([])
const loading = ref(true)
const searchTitle = ref('')
const selectedReport = ref<Report | null>(null)

async function loadReports() {
  loading.value = true
  try {
    const res = await api.get<any>('/api/v1/ai/reports')
    reports.value = res.data ?? res
    if (reports.value.length > 0) {
      selectedReport.value = reports.value[0]
    }
  } catch (e) {
    console.error('Failed to load reports:', e)
  } finally {
    loading.value = false
  }
}

const filteredReports = computed(() => {
  if (!searchTitle.value) return reports.value
  const lowSearch = searchTitle.value.toLowerCase()
  return reports.value.filter(r => 
    r.title.toLowerCase().includes(lowSearch) || 
    r.summary?.toLowerCase().includes(lowSearch)
  )
})

const renderedReport = computed(() => {
  if (!selectedReport.value) return ''
  const content = selectedReport.value.report
  if (selectedReport.value.is_html) {
    return DOMPurify.sanitize(content)
  }
  return DOMPurify.sanitize(marked.parse(content) as string)
})

function selectReport(report: Report) {
  selectedReport.value = report
}

function openInNewTab(report: Report) {
  const win = window.open('', '_blank')
  if (win) {
    const content = report.is_html ? report.report : marked.parse(report.report)
    win.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <title>${report.title} - 演练报告</title>
        <style>
          body { font-family: sans-serif; line-height: 1.6; max-width: 900px; margin: 40px auto; padding: 0 20px; color: #333; }
          img { max-width: 100%; border-radius: 8px; }
          pre { background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }
          code { font-family: monospace; }
          table { width: 100%; border-collapse: collapse; margin: 20px 0; }
          th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
          th { background: #f8f9fa; }
          h1, h2, h3 { color: #2563eb; }
        </style>
      </head>
      <body>
        ${content}
      </body>
      </html>
    `)
    win.document.close()
  }
}

const router = useRouter()
function goToChat(sessionId: number) {
  router.push({ path: '/ai', query: { session_id: sessionId } })
}

onMounted(() => {
  loadReports()
})
</script>

<template>
  <div class="flex h-full bg-transparent overflow-hidden">
    <!-- Left: Report List -->
    <div class="w-80 border-r border-border/50 flex flex-col bg-secondary/20 shrink-0">
      <div class="p-4 border-b border-border/50 bg-background/50 backdrop-blur-sm">
        <div class="flex items-center gap-2 mb-4">
          <div class="p-2 bg-primary/10 rounded-lg">
            <ClipboardList class="h-5 w-5 text-primary" />
          </div>
          <h2 class="text-lg font-bold">演练报告库</h2>
        </div>
        <div class="relative">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input 
            v-model="searchTitle" 
            placeholder="搜索报告..." 
            class="pl-9 h-9 bg-background/50" 
          />
        </div>
      </div>

      <ScrollArea class="flex-1">
        <div class="p-2 space-y-2">
          <div v-if="loading" class="flex flex-col gap-3 p-4">
            <div v-for="i in 5" :key="i" class="h-20 bg-muted/40 animate-pulse rounded-xl"></div>
          </div>
          <div v-else-if="filteredReports.length === 0" class="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <FileText class="h-12 w-12 mb-2 opacity-20" />
            <p class="text-sm">暂无报告数据</p>
          </div>
          <button
            v-for="report in filteredReports"
            :key="report.session_id"
            @click="selectReport(report)"
            class="w-full text-left p-4 rounded-xl transition-all border border-transparent group relative overflow-hidden"
            :class="[
              selectedReport?.session_id === report.session_id 
                ? 'bg-primary/10 border-primary/20 shadow-[0_4px_12px_hsl(var(--primary)/0.08)]' 
                : 'hover:bg-muted/50 text-muted-foreground hover:text-foreground'
            ]"
          >
            <div 
              class="absolute left-0 top-1/2 -translate-y-1/2 w-1 rounded-r-full bg-primary transition-all"
              :class="selectedReport?.session_id === report.session_id ? 'h-8 opacity-100' : 'h-0 opacity-0'"
            ></div>
            <div class="flex flex-col gap-1.5">
              <div class="flex items-center justify-between">
                <span class="text-xs font-mono text-muted-foreground">{{ report.session_id }}</span>
                <Badge variant="outline" class="text-[10px] px-1.5 h-4 bg-background/50 border-primary/20 text-primary">
                  演练模式
                </Badge>
              </div>
              <h3 class="font-bold text-sm line-clamp-1" :class="selectedReport?.session_id === report.session_id ? 'text-primary' : ''">
                {{ report.title }}
              </h3>
              <p class="text-[11px] line-clamp-2 leading-relaxed opacity-70">
                {{ report.summary || '暂无摘要描述' }}
              </p>
              <div class="flex items-center gap-3 mt-1 text-[10px] opacity-60 font-medium">
                <span class="flex items-center gap-1">
                  <Calendar class="h-3 w-3" />
                  {{ report.created_at.split(' ')[0] }}
                </span>
                <span class="flex items-center gap-1">
                  <Clock class="h-3 w-3" />
                  {{ report.created_at.split(' ')[1] }}
                </span>
              </div>
            </div>
          </button>
        </div>
      </ScrollArea>
    </div>

    <!-- Right: Report Detail -->
    <div class="flex-1 flex flex-col bg-background/40 relative">
      <div v-if="selectedReport" class="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        <!-- Detail Header -->
        <header class="h-16 border-b border-border/50 px-6 flex items-center justify-between bg-background/50 backdrop-blur-md shrink-0">
          <div class="flex items-center gap-4 min-w-0">
            <div class="p-2.5 bg-primary/10 rounded-xl border border-primary/20">
              <Shield class="h-5 w-5 text-primary" />
            </div>
            <div class="flex flex-col min-w-0">
              <h1 class="text-base font-bold truncate">{{ selectedReport.title }}</h1>
              <div class="flex items-center gap-2 text-[11px] text-muted-foreground font-medium">
                <span>会话 ID: #{{ selectedReport.session_id }}</span>
                <span class="opacity-30">|</span>
                <span>生成于 {{ selectedReport.created_at }}</span>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <Button variant="outline" size="sm" class="h-9 gap-2" @click="goToChat(selectedReport.session_id)">
              <MessageSquare class="h-4 w-4" />
              <span>跳转原始会话</span>
            </Button>
            <Button variant="default" size="sm" class="h-9 gap-2" @click="openInNewTab(selectedReport)">
              <ExternalLink class="h-4 w-4" />
              <span>新窗口查看</span>
            </Button>
          </div>
        </header>

        <!-- Report Content -->
        <div class="flex-1 overflow-auto relative">
          <!-- 装饰背景 -->
          <div class="absolute inset-0 pointer-events-none opacity-[0.03]">
             <div class="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,hsl(var(--primary)),transparent)]"></div>
          </div>
          
          <div class="max-w-[1000px] mx-auto p-8 md:p-12">
            <Card class="border-border/50 shadow-2xl bg-background/60 backdrop-blur-xl relative overflow-hidden">
              <!-- 顶部装饰排版 -->
              <div class="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-primary/10 via-primary to-primary/10"></div>
              
              <CardContent class="p-8 md:p-12">
                <div 
                  id="report-container"
                  class="prose prose-sm dark:prose-invert max-w-none report-content"
                  v-html="renderedReport"
                ></div>
              </CardContent>
            </Card>

            <!-- 底部版权说明 -->
            <div class="mt-8 mb-12 flex flex-col items-center justify-center gap-2 opacity-30 select-none">
              <div class="flex items-center gap-2 text-[10px] font-mono tracking-widest uppercase">
                <Shield class="h-3 w-3" />
                AimiGuard Security Analytics Report
              </div>
              <div class="text-[9px] font-medium">
                © 2026 玄枢指挥官 · AI 安全攻防实验室
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="flex-1 flex flex-col items-center justify-center text-muted-foreground p-12">
        <div class="relative mb-6">
          <div class="absolute inset-0 bg-primary/10 blur-2xl rounded-full scale-150 animate-pulse"></div>
          <ClipboardList class="h-20 w-20 relative opacity-20" />
        </div>
        <h3 class="text-xl font-bold mb-2">欢迎查阅演练报告库</h3>
        <p class="text-sm max-w-md text-center opacity-60">
          这里记录了所有 AI 攻防指挥官执行的安全演练成果，请从左侧列表中选择查看详细的分析报告。
        </p>
      </div>
    </div>
  </div>
</template>

<style>
/* 报告内容专属样式 */
.report-content {
  line-height: 1.8;
  font-size: 0.95rem;
}

.report-content h1 {
  @apply text-3xl font-black mb-8 pb-4 border-b border-primary/20 text-foreground flex items-center gap-3;
}

.report-content h2 {
  @apply text-xl font-bold mt-10 mb-5 text-primary flex items-center gap-2;
}

.report-content h2::before {
  content: '◈';
  @apply text-primary/40 font-normal;
}

.report-content h3 {
  @apply text-lg font-bold mt-8 mb-4 text-foreground/90;
}

.report-content p {
  @apply mb-4 text-muted-foreground leading-relaxed;
}

.report-content ul, .report-content ol {
  @apply mb-6 ml-4 space-y-2;
}

.report-content li {
  @apply text-muted-foreground relative;
}

.report-content table {
  @apply w-full border-collapse my-8 rounded-xl overflow-hidden border border-border/50;
}

.report-content th {
  @apply bg-muted/80 p-4 text-sm font-bold text-foreground text-left;
}

.report-content td {
  @apply p-4 text-sm border-t border-border/50 text-muted-foreground;
}

.report-content blockquote {
  @apply border-l-4 border-primary/30 bg-primary/5 p-6 my-6 rounded-r-xl italic;
}

.report-content img {
  @apply rounded-xl border border-border/50 shadow-lg my-8 max-w-full;
}

.report-content hr {
  @apply my-10 border-border/50;
}

.report-content pre {
  @apply bg-zinc-950/80 p-6 rounded-xl my-6 border border-white/5 font-mono text-xs leading-relaxed overflow-x-auto;
}

.report-content code {
  @apply font-mono px-1.5 py-0.5 rounded bg-muted text-primary text-[0.85em];
}
</style>
