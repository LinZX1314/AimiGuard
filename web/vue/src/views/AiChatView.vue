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










          if (parsed.content) { typeQueue += parsed.content; startTypewriter() }





          if (parsed.tool_call) {


            if (typeQueue) {


              assistantMsg.content += typeQueue


              typeQueue = ''


            }


            if (!(assistantMsg as any).tool_calls) (assistantMsg as any).tool_calls = []


            const tcId = parsed.tool_call.id || 'tc_' + Date.now()


            ;(assistantMsg as any).tool_calls.push({ id: tcId, name: parsed.tool_call.name, arguments: parsed.tool_call.arguments })




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







          }





          if (parsed.session_id && !resolvedSessionId) {


            resolvedSessionId = Number(parsed.session_id)


            inFlightSessionId.value = resolvedSessionId


            setPendingMessages(resolvedSessionId, requestMessages)


            await loadSessions()


            if (!currentSession.value || currentSession.value === -1) {


              currentSession.value = resolvedSessionId


            }




          }


        } catch (e) { console.error('SSE解析错误:', e) }


      }


    }


    speak(assistantMsg.content)


  } catch(e: any) {


    if (e.name !== 'AbortError') assistantMsg.content = `错误：${e.message || '请求失败'}`


  } finally {


    sending.value = false; activeChatController.value = null


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


  messages.value = []; currentSession.value = -1


  sessions.value = [{ id: -1, title: '新对话', created_at: new Date().toLocaleString() }, ...sessions.value.filter(s => s.id !== -1)]


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


  if (window.speechSynthesis) window.speechSynthesis.cancel()


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




