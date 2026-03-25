<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, nextTick, computed } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/index'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import AiSessionSidebar from '@/components/ai/AiSessionSidebar.vue'
import AiMessageList from '@/components/ai/AiMessageList.vue'
import AiChatInput from '@/components/ai/AiChatInput.vue'
import {
  Terminal,
} from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'





interface ToolCall {


  id: string


  type?: string


  name?: string


  arguments?: Record<string, unknown>


  function?: {


    name?: string


    arguments?: string | Record<string, unknown>


  }


}





interface ApiMessage {


  role: 'user' | 'assistant' | 'tool'


  content?: string


  openai_content?: string | null


  ts?: string


  created_at?: string


  name?: string


  tool_call_id?: string


  tool_calls?: ToolCall[]


}





interface ToolResult {


  content: string


  created_at?: string


  name?: string


  tool_call_id?: string


}





interface Message {


  role: 'user' | 'assistant'


  content: string


  post_content?: string


  created_at?: string


  tool_calls?: ToolCall[]


  tool_results?: ToolResult[]


}





interface Session { id: number; title: string; created_at: string }





interface ChatAttachmentPayload {


  name: string


  type: string


  size: number


  isImage: boolean


  textContent?: string


}





// ─── 通用状态 ────────────────────────────────────────────────────────────────


const sessions = ref<Session[]>([])


const messages = ref<Message[]>([])


const loading = ref(false)


const sending = ref(false)


const currentSession = ref<number | null>(null)


const activeChatController = ref<AbortController | null>(null)


const ttsEnabled = ref(true)


const inFlightSessionId = ref<number | null>(null)


const pendingSessionMessages = reactive<Record<number, Message[]>>({})


const route = useRoute()


const TTS_STORAGE_KEY = 'aimiguard.ai.tts-enabled'





function cloneMessages(source: Message[]): Message[] {


  return source.map((msg) => ({


    ...msg,


    tool_calls: msg.tool_calls ? msg.tool_calls.map((tc) => ({ ...tc, function: tc.function ? { ...tc.function } : undefined })) : undefined,


    tool_results: msg.tool_results ? msg.tool_results.map((tr) => ({ ...tr })) : undefined,


  }))


}





function setPendingMessages(sessionId: number, source: Message[]) {


  Object.assign(pendingSessionMessages, { [sessionId]: source })


}





function getPendingMessages(sessionId: number): Message[] | null {


  const pending = pendingSessionMessages[sessionId]


  return pending ? cloneMessages(pending) : null


}





function mergeServerWithPending(sessionId: number, serverMessages: Message[]): Message[] {


  const pending = pendingSessionMessages[sessionId]


  if (!pending) return serverMessages





  if (inFlightSessionId.value === sessionId) {


    return cloneMessages(pending)


  }





  if (pending.length > serverMessages.length) {


    return cloneMessages(pending)


  }





  delete pendingSessionMessages[sessionId]


  return serverMessages


}





function loadTtsPreference() {


  if (typeof window === 'undefined') return true


  try {


    const saved = window.localStorage.getItem(TTS_STORAGE_KEY)


    if (saved === null) return true


    return saved === '1' || saved === 'true'


  } catch {


    return true


  }


}





function persistTtsPreference(enabled: boolean) {


  if (typeof window === 'undefined') return


  try {


    window.localStorage.setItem(TTS_STORAGE_KEY, enabled ? '1' : '0')


  } catch {


    // 本地存储不可用时静默降级


  }


}





// ─── 演练模式状态 ────────────────────────────────────────────────────────────


const drillMode = ref(false)


const drillLog = ref<Array<{


  id: number


  type: 'step' | 'thinking' | 'tool_call' | 'tool_result' | 'complete' | 'warning' | 'text'


  icon: string


  color: string


  label: string


  content: string


  timestamp: string


  expanded: boolean


  toolIcon: string


}>>([])


const drillStep = ref(0)


const drillMaxStep = ref(30)


const drillProgress = ref(0)


const drillReport = ref('')


const drillReportHtml = ref(false)


const drillSummary = ref('')


const drillFindingCount = ref(0)


const drillPanelOpen = ref(false)


const drillElapsed = ref(0)


const drillHostsFound = ref(0)


const drillScreenshotsTaken = ref(0)


let drillLogId = 0


let drillTimer: ReturnType<typeof setInterval> | null = null





const parsedReportHtml = computed(() => {


  const raw = drillReport.value || drillSummary.value


  if (!raw) return ''


  return DOMPurify.sanitize(marked.parse(raw) as string)


})





const toolIconMap: Record<string, string> = {


  search: 'search',


  network_scan: 'search',


  scan: 'search',


  camera: 'camera',


  screenshot: 'camera',


  web: 'camera',


  bruteforce: 'lock',


  ssh: 'lock',


  rdp: 'lock',


  mysql: 'lock',


  honeypot: 'bug',


  audit: 'bug',


  stats: 'bug',


  ban: 'ban',


  report: 'file-text',


  generate: 'file-text',


  status: 'target',


  plan: 'target',


  analyze: 'eye',


  document: 'eye',


}





function getToolIcon(toolName: string): string {


  if (!toolName) return 'terminal'


  const lower = toolName.toLowerCase()


  for (const [key, icon] of Object.entries(toolIconMap)) {


    if (lower.includes(key)) return icon


  }


  return 'zap'


}





function drillAdd(type: 'step' | 'thinking' | 'tool_call' | 'tool_result' | 'complete' | 'warning' | 'text', label: string, content: string, icon: string, color: string, toolIcon = 'terminal') {


  if (drillLog.value.length >= 500) drillLog.value.shift()  // 限制最大长度，防止内存溢出


  drillLog.value.push({


    id: ++drillLogId,


    type,


    icon,


    color,


    label,


    content,


    timestamp: new Date().toLocaleTimeString('zh-CN', { hour12: false }),


    expanded: type === 'tool_result',


    toolIcon,


  })


  nextTick(() => {


    const el = document.querySelector('.drill-log-scroll')


    if (el) el.scrollTop = el.scrollHeight


  })


}





function drillToggleExpand(id: number) {


  const entry = drillLog.value.find(e => e.id === id)


  if (entry) entry.expanded = !entry.expanded


}





function formatToolResult(result: string): string {


  try {


    const parsed = JSON.parse(result)


    if (parsed.error) return `❌ ${parsed.error}`


    if (parsed.vulnerable) {


      const creds = parsed.vulnerable_creds || []


      if (creds.length > 0) {


        return `🔴 弱口令发现！\n${creds.map((c: any) => `  ${c.username} / ${c.password}`).join('\n')}`


      }


      return `✅ 检测完成，未发现常见弱口令`


    }


    if (parsed.发现主机 !== undefined) {


      drillHostsFound.value = Math.max(drillHostsFound.value, parsed.发现主机)


      return `✅ 发现 ${parsed.发现主机} 台主机`


    }


    if (parsed.total !== undefined) return `✅ 蜜罐记录 ${parsed.total} 次攻击`


    if (parsed.screenshot_url) { drillScreenshotsTaken.value++; return `✅ 截图已保存` }


    if (parsed.report) return `✅ 报告生成完毕，共 ${parsed.findings_count || 0} 项发现`


    if (parsed.plan) {


      // 行动计划：提取阶段数作为摘要，不显示完整 markdown


      const phases = (parsed.plan.match(/### /g) || []).length


      return `✅ ${parsed.message || '行动计划已生成'}（${phases} 个阶段）`


    }


    if (parsed.攻击记录 !== undefined) {


      // 蜜罐审计结果


      const count = parsed.总数 || (parsed.攻击记录 && parsed.攻击记录.length) || 0


      const service = parsed.service || '全部'


      return `✅ 蜜罐审计完成，服务 [${service}]，${count} 条攻击记录`


    }


    if (parsed.local_ip) {


      // 本机IP查询结果


      return `✅ 本机 IP: ${parsed.local_ip} | 主机名: ${parsed.hostname || 'unknown'}`


    }


    if (parsed.message) return parsed.message


    return JSON.stringify(parsed, null, 2)


  } catch { return result }


}





function toggleDrillPanel() {


  drillPanelOpen.value = !drillPanelOpen.value


  // 持久化面板开关状态（按会话区分），切换回来时恢复


  const sid = currentSession.value


  if (drillPanelOpen.value && sid && sid > 0) {


    sessionStorage.setItem('drill_panel_' + sid, 'true')


  } else if (sid && sid > 0) {


    sessionStorage.removeItem('drill_panel_' + sid)


  }


}





function startDrillTimer() {


  drillElapsed.value = 0


  if (drillTimer) clearInterval(drillTimer)


  drillTimer = setInterval(() => { drillElapsed.value++ }, 1000)


}





function stopDrillTimer() {


  if (drillTimer) { clearInterval(drillTimer); drillTimer = null }


}





function formatElapsed(seconds: number): string {


  const m = Math.floor(seconds / 60)


  const s = seconds % 60


  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`


}





function speak(text: string) {


  if (!ttsEnabled.value || !window.speechSynthesis) return


  const stripped = text.replace(/[#*`>~_\[\]()!]/g, ' ').replace(/\s+/g, ' ').trim()


  const utt = new SpeechSynthesisUtterance(stripped.slice(0, 400))


  utt.lang = 'zh-CN'; utt.rate = 1.1


  window.speechSynthesis.speak(utt)


}





function toggleTts() {


  if (ttsEnabled.value && window.speechSynthesis) window.speechSynthesis.cancel()


  ttsEnabled.value = !ttsEnabled.value


  persistTtsPreference(ttsEnabled.value)


}





function stopGenerating() { activeChatController.value?.abort() }





// Session Management


async function loadSessions() {


  try {


    const d = await api.get<any>('/api/v1/ai/sessions')


    sessions.value = (d.data ?? d) as Session[]


  } catch(e) { console.error(e) }


}





async function loadMessages(sid: number) {


  if (sid === -1) { currentSession.value = -1; messages.value = []; loading.value = false; return }


  loading.value = true; currentSession.value = sid





  const pending = getPendingMessages(sid)


  if (inFlightSessionId.value === sid && pending) {


    messages.value = pending


    loading.value = false


    return


  }





  try {


    const d = await api.get<any>(`/api/v1/ai/sessions/${sid}/messages`)


    const rawMessages = (d.data ?? d) as ApiMessage[]


    


    // 自动判定是否为 Drill 会话，实现切页后视图状态恢复


    const isDrill = rawMessages.some(m => 


      (m.role === 'user' && m.content?.includes('【演练文档】')) || 


      (m.role === 'assistant' && m.tool_calls?.some(tc => tc.function?.name?.startsWith('drill_') || (tc as any).name?.startsWith('drill_')))


    )





    if (isDrill) {


      drillMode.value = true


      // 恢复该会话上次的面板开关状态（sessionStorage 中保存的值）


      if (sessionStorage.getItem('drill_panel_' + sid) === 'true') {


        drillPanelOpen.value = true


      }


      drillLog.value = []


      drillStep.value = 0


      drillFindingCount.value = 0


      drillHostsFound.value = 0


      drillScreenshotsTaken.value = 0


      drillElapsed.value = 0


      drillReport.value = ''


      


      rawMessages.forEach((msg, idx) => {


        if (msg.role === 'user') {


          // drillAdd('text', '👤 指挥官', msg.content || '', 'user', 'text-green-400', 'user')


        } else if (msg.role === 'assistant') {


          // if (msg.content) drillAdd('text', '🧠 协同思考', msg.content, 'cpu', 'text-blue-400', 'cpu')


          if (msg.tool_calls?.length) {


            msg.tool_calls.forEach(tc => {


              drillStep.value++


              const tName = tc.function?.name || (tc as any).name || ''


              if (!tName) return


              const toolArgs = typeof tc.function?.arguments === 'string' ? tc.function.arguments : JSON.stringify(tc.function?.arguments || (tc as any).arguments || {})


              const tIcon = getToolIcon(tName)


              const toolLabel = tName.replace('drill_', '').replace(/_/g, ' ').toUpperCase()


              drillAdd('tool_call', `🔧 ${toolLabel}`, toolArgs, 'terminal', 'text-purple-400', tIcon)


            })


          }


        } else if (msg.role === 'tool') {


            const raw = typeof msg.content === 'object' ? JSON.stringify(msg.content) : (msg.content || '')


            // 追加为独立的 tool_result 行，让 UI 可以折叠呈现，避免覆盖工具参数


            drillAdd('tool_result', `↪ 结果反馈`, formatToolResult(raw), 'check-square', 'text-emerald-400')


            try {


              const r = JSON.parse(raw)


              if (r.vulnerable && r.vulnerable_creds?.length > 0) drillFindingCount.value++


              if (r.发现主机 !== undefined) drillHostsFound.value = Math.max(drillHostsFound.value, r.发现主机)


              if (r.screenshot_url) drillScreenshotsTaken.value++


              if (r.report) {


                drillReport.value = r.report


                drillReportHtml.value = !!r.is_html


              }


            } catch (e) {}


        }


      })


      if (drillReport.value) drillAdd('complete', '✅ 演练完成', `共发现 ${drillFindingCount.value} 个安全问题`, 'check-circle', 'text-emerald-400')


    } else {


      drillMode.value = false


      drillPanelOpen.value = false


    }





    const normalized = normalizeMessages(rawMessages)


    messages.value = mergeServerWithPending(sid, normalized)


  } catch(e) { console.error(e) }


  loading.value = false


}





async function deleteSession(sid: number) {


  try {


    await api.delete(`/api/v1/ai/sessions/${sid}`)


    delete pendingSessionMessages[sid]


    if (currentSession.value === sid) { messages.value = []; currentSession.value = null }


    await loadSessions()


  } catch (e) { console.error('删除会话失败:', e) }


}





function normalizeMessages(source: ApiMessage[], fallbackReply = ''): Message[] {


  const resolveContent = (msg: ApiMessage) => {


    return (msg.content ?? msg.openai_content ?? '').toString()


  }


  const resolveTime = (msg: ApiMessage) => {


    return msg.created_at || msg.ts


  }





  const normalized: Message[] = []


  let index = 0


  while (index < source.length) {


    const current = source[index]


    if (current.role === 'user') {


      normalized.push({ role: 'user', content: resolveContent(current), created_at: resolveTime(current) })


      index += 1; continue


    }


    if (current.role === 'assistant' && current.tool_calls?.length) {


      const toolResults: ToolResult[] = []


      let content = resolveContent(current)


      let postContent = ''


      let createdAt = resolveTime(current)


      let cursor = index + 1


      let seqIndex = 0


      while (cursor < source.length) {


        const next = source[cursor]


        if (next.role === 'tool') {


          let matchedCall = current.tool_calls?.find(tc => tc.id === next.tool_call_id)


          if (!matchedCall && seqIndex < current.tool_calls.length) matchedCall = current.tool_calls[seqIndex]


          const toolName = next.name || matchedCall?.name || (matchedCall as any)?.function?.name || 'unknown_tool'


          toolResults.push({ content: resolveContent(next), created_at: resolveTime(next), name: toolName, tool_call_id: next.tool_call_id || matchedCall?.id })


          seqIndex++; cursor += 1; continue


        }


        break


      }


      normalized.push({ role: 'assistant', content, created_at: createdAt, tool_calls: current.tool_calls, tool_results: toolResults })


      index = cursor; continue


    }


    if (current.role === 'assistant') {


      const assistantContent = resolveContent(current)


      normalized.push({ role: 'assistant', content: assistantContent || fallbackReply, created_at: resolveTime(current) })


      index += 1; continue


    }


    normalized.push({ role: 'assistant', content: '', created_at: resolveTime(current), tool_results: [{ content: resolveContent(current), created_at: resolveTime(current), name: current.name, tool_call_id: current.tool_call_id }] })


    index += 1


  }


  if (!normalized.length && fallbackReply) normalized.push({ role: 'assistant', content: fallbackReply })


  return normalized


}





function composeTextWithAttachments(text: string, attachments: ChatAttachmentPayload[] = []): string {


  if (!attachments.length) return text





  const header = attachments


    .map((item, index) => `${index + 1}. ${item.name} (${item.type || 'unknown'}, ${Math.max(1, Math.ceil(item.size / 1024))}KB)`)


    .join('\n')





  const textParts = attachments


    .filter((item) => !item.isImage && item.textContent)


    .map((item) => `【文件内容：${item.name}】\n${item.textContent}`)


    .join('\n\n')





  const imageTips = attachments


    .filter((item) => item.isImage)


    .map((item) => `- ${item.name}`)


    .join('\n')





  const blocks = [


    text,


    `\n\n[已附加文件]\n${header}`,


  ]





  if (textParts) {


    blocks.push(`\n\n${textParts}`)


  }





  if (imageTips) {


    blocks.push(`\n\n[已附加图片]\n${imageTips}\n请基于对话上下文给出处理建议。`)


  }





  return blocks.join('')


}





function isEmptyAssistantMessage(msg?: Message): boolean {


  if (!msg || msg.role !== 'assistant') return false


  return !(


    msg.content?.trim() ||


    msg.post_content?.trim() ||


    msg.tool_calls?.length ||


    msg.tool_results?.length


  )


}





// Send


async function send(text: string, extraParams: any = {}, documentContent?: string) {


  if (!text && !documentContent) return


  if (sending.value) return





  const wasDrillSession = currentSession.value && currentSession.value > 0 && sessionStorage.getItem('drill_session') === String(currentSession.value)


  const attachmentFiles = (extraParams?.files || []) as File[]
  const hasImageUpload = attachmentFiles.some(f => f.type.startsWith('image/'))
  const isDrill = hasImageUpload || wasDrillSession || !!documentContent || extraParams?.context_type === 'drill' || extraParams?.is_drill


  if (isDrill) {


    drillLog.value = []; drillReport.value = ''; drillMode.value = true; drillPanelOpen.value = true


    drillStep.value = 0; drillFindingCount.value = 0; drillElapsed.value = 0


    drillHostsFound.value = 0; drillScreenshotsTaken.value = 0


    startDrillTimer()


  }





  const attachments = (extraParams?.attachments || []) as ChatAttachmentPayload[]


  const baseText = (text || '').trim() || (attachmentFiles.length ? '请分析我上传的文件/图片。' : '')


  const composedText = isDrill ? text : composeTextWithAttachments(baseText, attachments)


  const displayText = isDrill ? `【演练文档】\n${documentContent}` : composedText


  messages.value.push({ role: 'user', content: displayText })


  sending.value = true


  const requestMessages = messages.value


  const requestSessionId = currentSession.value && currentSession.value > 0 ? currentSession.value : null


  let resolvedSessionId: number | null = requestSessionId





  if (requestSessionId) {


    inFlightSessionId.value = requestSessionId


    setPendingMessages(requestSessionId, requestMessages)


  } else {


    inFlightSessionId.value = null


  }





  let assistantMsg = reactive<Message>({ role: 'assistant', content: '' })


  requestMessages.push(assistantMsg as any)





  const controller = new AbortController()


  activeChatController.value = controller





  try {


    const requestText = isDrill ? `【演练文档】${documentContent}` : baseText


    const token = localStorage.getItem('token')


    const headers: Record<string, string> = {}


    if (token) headers['Authorization'] = `Bearer ${token}`





    let response: Response


    if (attachmentFiles.length) {


      const form = new FormData()


      form.append('message', requestText)


      form.append('drill_mode', isDrill ? 'true' : 'false')


      if (currentSession.value && currentSession.value !== -1) {


        form.append('session_id', String(currentSession.value))


      }


      if (extraParams?.context_type) form.append('context_type', String(extraParams.context_type))


      if (extraParams?.context_id) form.append('context_id', String(extraParams.context_id))


      attachmentFiles.forEach((file) => form.append('files', file))





      response = await fetch('/api/v1/ai/chat/stream', {


        method: 'POST',


        headers,


        body: form,


        credentials: 'include',


        signal: controller.signal,


      })


    } else {


      headers['Content-Type'] = 'application/json'


      const body: any = { message: requestText, drill_mode: isDrill, ...extraParams }


      delete body.attachments


      delete body.files


      if (currentSession.value && currentSession.value !== -1) body.session_id = currentSession.value


      response = await fetch('/api/v1/ai/chat/stream', {


        method: 'POST', headers, body: JSON.stringify(body), credentials: 'include', signal: controller.signal


      })


    }


    if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`)





    const reader = response.body.getReader()


    const decoder = new TextDecoder()


    let buffer = ''


    let typeQueue = ''


    let typeInterval: any = null





    const startTypewriter = () => {


      if (typeInterval) return


      typeInterval = setInterval(() => {


        if (typeQueue.length > 0) {


          const popCount = Math.max(1, Math.ceil(typeQueue.length / 15))


          const hasTools = (assistantMsg as any).tool_calls?.length > 0 || (assistantMsg as any).tool_results?.length > 0


          if (hasTools) {


            assistantMsg = reactive({ role: 'assistant', content: '', created_at: new Date().toISOString() }) as any


            requestMessages.push(assistantMsg as any)


          }


          assistantMsg.content += typeQueue.slice(0, popCount)


          typeQueue = typeQueue.slice(popCount)


        } else { clearInterval(typeInterval); typeInterval = null }


      }, 30)


    }





    while (true) {


      const { done, value } = await reader.read()


      if (done) break


      buffer += decoder.decode(value, { stream: true })


      const lines = buffer.split('\n')


      buffer = lines.pop() || ''


      for (const line of lines) {


        const trimmed = line.trim()


        if (!trimmed.startsWith('data: ')) continue


        const data = trimmed.slice(6)


        if (data === '[DONE]') continue


        try {


          const parsed = JSON.parse(data)





          if (parsed.drill_mode) {


            drillMode.value = true; drillLog.value = []; drillReport.value = ''


            drillFindingCount.value = 0; drillHostsFound.value = 0; drillScreenshotsTaken.value = 0


            startDrillTimer()


            // 标记该会话为演练模式，后续发消息自动进入演练


            if (currentSession.value && currentSession.value > 0) {


              sessionStorage.setItem('drill_session', String(currentSession.value))


            }


            typeQueue += '\n🚀 演练启动：AI 正在分析演练文档，制定行动计划...\n'
            startTypewriter()


            continue


          }





          if (parsed.drill_step) {


            drillStep.value = parsed.drill_step.step || 0


            drillMaxStep.value = parsed.drill_step.max_steps || 30


            drillProgress.value = Math.round((drillStep.value / drillMaxStep.value) * 100)


            if (parsed.drill_step.status === 'thinking') {


              typeQueue += '\n🤔 ' + (parsed.drill_step.message || '') + '\n'
              startTypewriter()


            }


          }





          if (parsed.drill_complete) {


            drillReport.value = parsed.drill_complete.report || ''


            drillReportHtml.value = !!parsed.drill_complete.is_html


            drillSummary.value = parsed.drill_complete.summary || ''


            drillFindingCount.value = parsed.drill_complete.findings_count || 0


            stopDrillTimer()


            const autoTag = parsed.drill_complete.auto_generated ? ' [自动生成]' : ''


            const htmlTag = parsed.drill_complete.is_html ? ' 📊' : ''


            typeQueue += '\n✅ 演练完成：共发现 ' + drillFindingCount.value + ' 个安全问题，演练结束' + autoTag + htmlTag + '\n'
            startTypewriter()


          }





          if (parsed.drill_warning) {


            typeQueue += '\n⚠️ 演练警告：' + parsed.drill_warning + '\n'
            startTypewriter()


          }





          if (parsed.drill_final) {


            typeQueue += '\n📋 最终状态：' + parsed.drill_final.exec_summary + '\n'
            startTypewriter()


          }





          if (parsed.content) { typeQueue += parsed.content; startTypewriter() }





          if (parsed.tool_call) {


            if (typeQueue) {


              assistantMsg.content += typeQueue


              typeQueue = ''


            }


            if (!(assistantMsg as any).tool_calls) (assistantMsg as any).tool_calls = []


            const tcId = 'tc_' + Date.now()


            ;(assistantMsg as any).tool_calls.push({ id: tcId, name: parsed.tool_call.name, arguments: parsed.tool_call.arguments })


            if (drillMode.value) {


              const tIcon = getToolIcon(parsed.tool_call.name)


              const toolLabel = parsed.tool_call.name.replace('drill_', '').replace(/_/g, ' ').toUpperCase()


              drillAdd('tool_call', `🔧 ${toolLabel}`, JSON.stringify(parsed.tool_call.arguments || {}, null, 2), 'terminal', 'text-purple-400', tIcon)


            }


          }





          if (parsed.tool_result) {


            if (typeQueue) { assistantMsg.content += typeQueue; typeQueue = '' }


            if (!(assistantMsg as any).tool_results) (assistantMsg as any).tool_results = []


            


            // 后端返回的是: { id: "...", result: "{\"ok\":true,...}", ... }


            // 提取真正的内层工具执行结果


            const innerResult = (typeof parsed.tool_result === 'object' && parsed.tool_result.result !== undefined)


              ? parsed.tool_result.result


              : parsed.tool_result





            const tcId = (typeof parsed.tool_result === 'object' && (parsed.tool_result.tool_call_id || parsed.tool_result.id)) 


              || parsed.tool_call_id 


              || (assistantMsg as any).tool_calls?.slice(-1)[0]?.id 


              || ''





            const resultStr = typeof innerResult === 'string' ? innerResult : JSON.stringify(innerResult, null, 2)


            ;(assistantMsg as any).tool_results.push({ name: (assistantMsg as any).tool_calls?.find((tc: any) => tc.id === tcId)?.name || 'tool', tool_call_id: tcId, content: resultStr })





            if (drillMode.value) {


              drillAdd('tool_result', `↪ 结果反馈`, formatToolResult(resultStr), 'check-square', 'text-emerald-400')


              try {


                const r = JSON.parse(resultStr)


                if (r.vulnerable && r.vulnerable_creds?.length > 0) drillFindingCount.value++


              } catch (e) { console.warn('工具结果解析异常:', e) }


            }


          }





          if (parsed.session_id && !resolvedSessionId) {


            resolvedSessionId = Number(parsed.session_id)


            inFlightSessionId.value = resolvedSessionId


            setPendingMessages(resolvedSessionId, requestMessages)


            await loadSessions()


            if (!currentSession.value || currentSession.value === -1) {


              currentSession.value = resolvedSessionId


            }


            // 若已进入演练模式，补上 sessionStorage 标记（新会话场景 drill_mode 帧先于 session_id 帧到达）


            if (drillMode.value) {


              sessionStorage.setItem('drill_session', String(resolvedSessionId))


            }


          }


        } catch (e) { console.error('SSE解析错误:', e) }


      }


    }


    if (!drillMode.value) speak(assistantMsg.content)


  } catch(e: any) {


    stopDrillTimer()


    if (e.name !== 'AbortError') assistantMsg.content = `错误：${e.message || '请求失败'}`


    if (drillMode.value) drillAdd('warning', '❌ 请求失败', e.message || '', 'alert-triangle', 'text-red-400')


  } finally {


    stopDrillTimer(); sending.value = false; activeChatController.value = null


    const lastMsg = requestMessages[requestMessages.length - 1]


    if (isEmptyAssistantMessage(lastMsg)) {


      requestMessages.pop()


    }





    if (resolvedSessionId) {


      setPendingMessages(resolvedSessionId, requestMessages)


    }





    inFlightSessionId.value = null


  }


}





function handleNewChat() {


  messages.value = []; currentSession.value = -1; drillMode.value = false


  drillLog.value = []; drillReport.value = ''; stopDrillTimer()


  sessions.value = [{ id: -1, title: '新对话', created_at: new Date().toLocaleString() }, ...sessions.value.filter(s => s.id !== -1)]


}





function openReportWindow() {


  if (!drillReport.value) return


  const win = window.open('', '_blank')


  if (win) {


    win.document.write(drillReport.value)


    win.document.close()


  }


}





onMounted(async () => {


  ttsEnabled.value = loadTtsPreference()


  await loadSessions()


  const { context_type, context_id, prompt, session_id } = route.query as any


  if (session_id) {


    await loadMessages(Number(session_id))


  } else if (prompt) {


    await send(String(prompt), { context_type, context_id })


  } else if (context_type && context_id) {


    await send(`请帮我分析这个目标：${context_id}`, { context_type, context_id })


  }


})





onBeforeUnmount(() => {


  // 切换页面时不主动中断请求，允许后台继续执行并在会话历史中恢复结果


  stopDrillTimer(); if (window.speechSynthesis) window.speechSynthesis.cancel()


})


</script>





<template>


  <div class="flex h-[calc(100vh-64px)] min-w-0 bg-transparent text-foreground overflow-hidden">


    <AiSessionSidebar


      :sessions="sessions"


      :current-session="currentSession"


      @new-chat="handleNewChat"


      @load-messages="loadMessages"


      @delete-session="deleteSession"


    />


    <main class="relative flex min-w-0 flex-1 flex-col overflow-hidden bg-transparent">


      <AiMessageList :messages="messages" :loading="loading" :sending="sending" />


      <AiChatInput


        :sending="sending"


        :tts-enabled="ttsEnabled"


        @send="send"


        @stop="stopGenerating"


        @toggle-tts="toggleTts"


      />


    </main>


  </div>


</template>




