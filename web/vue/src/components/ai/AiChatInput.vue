<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Send,
  Square,
  X,
  History,
  Settings,
  FileUp,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

const props = defineProps<{
  sending: boolean
  ttsEnabled: boolean
}>()

const emit = defineEmits<{
  (e: 'send', text: string, extra?: any): void
  (e: 'stop'): void
  (e: 'toggleTts'): void
  (e: 'upload', file: File): void
}>()

const input = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)
const uploadedFileName = ref('')

// STT ------------------------------------------------------------------------
const listening = ref(false)
const voiceCardVisible = ref(false)
const voiceError = ref('')
const voiceDraft = ref('')
const voiceInterim = ref('')
const waveformBars = ref<number[]>(Array.from({ length: 20 }, (_, index) => 0.15 + (index % 4) * 0.02))

let recognition: any = null
let mediaStream: MediaStream | null = null
let audioContext: AudioContext | null = null
let analyser: AnalyserNode | null = null
let sourceNode: MediaStreamAudioSourceNode | null = null
let frequencyData: any = new Uint8Array(0)
let animationFrameId: number | null = null

const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
const voiceSupported = computed(() => Boolean(SpeechRecognition && navigator.mediaDevices?.getUserMedia))
const voiceTranscript = computed(() => [voiceDraft.value, voiceInterim.value].filter(Boolean).join(' ').trim())
const canApplyVoice = computed(() => Boolean(voiceTranscript.value))

function resetWaveform() {
  waveformBars.value = Array.from({ length: 20 }, (_, index) => 0.15 + (index % 4) * 0.02)
}

function stopWaveform() {
  if (animationFrameId !== null) {
    window.cancelAnimationFrame(animationFrameId)
    animationFrameId = null
  }
  if (sourceNode) {
    sourceNode.disconnect()
    sourceNode = null
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach(track => track.stop())
    mediaStream = null
  }
  if (audioContext) {
    void audioContext.close()
    audioContext = null
  }
  analyser = null
  frequencyData = new Uint8Array(0)
  resetWaveform()
}

function stopSpeechRecognition() {
  if (!recognition) return
  try {
    recognition.stop()
  } catch {}
  listening.value = false
}

function cleanupVoiceCapture() {
  stopSpeechRecognition()
  stopWaveform()
  voiceInterim.value = ''
}

function renderWaveformFrame() {
  if (!analyser || !frequencyData) return

  analyser.getByteFrequencyData(frequencyData)
  const bucketSize = Math.max(1, Math.floor(frequencyData.length / waveformBars.value.length))

  waveformBars.value = waveformBars.value.map((_, index) => {
    const start = index * bucketSize
    const end = index === waveformBars.value.length - 1 ? frequencyData.length : Math.min(frequencyData.length, start + bucketSize)
    let total = 0

    for (let i = start; i < end; i += 1) total += frequencyData[i]

    const average = total / Math.max(1, end - start)
    return Number((0.12 + Math.min(1, Math.max(0.04, average / 255)) * 1.18).toFixed(3))
  })

  animationFrameId = window.requestAnimationFrame(renderWaveformFrame)
}

async function startWaveform() {
  stopWaveform()
  const AudioContextClass = (window as any).AudioContext || (window as any).webkitAudioContext

  if (!AudioContextClass || !navigator.mediaDevices?.getUserMedia) {
    voiceError.value = '当前浏览器不支持麦克风实时波形。'
    return
  }

  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    })
    audioContext = new AudioContextClass()
    if (audioContext?.state === 'suspended') await audioContext.resume()
    if (!audioContext) return

    analyser = audioContext.createAnalyser()
    analyser.fftSize = 256
    analyser.smoothingTimeConstant = 0.82
    sourceNode = audioContext.createMediaStreamSource(mediaStream)
    if (sourceNode && analyser) {
      sourceNode.connect(analyser)
      frequencyData = new Uint8Array(analyser.frequencyBinCount)
      renderWaveformFrame()
    }
  } catch (error) {
    console.error('初始化麦克风波形失败:', error)
    voiceError.value = '无法访问麦克风，请确认浏览器权限已开启。'
    resetWaveform()
  }
}

if (SpeechRecognition) {
  recognition = new SpeechRecognition()
  recognition.lang = 'zh-CN'
  recognition.continuous = true
  recognition.interimResults = true
  recognition.maxAlternatives = 1

  recognition.onresult = (event: any) => {
    let finalText = ''
    let interimText = ''

    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const result = event.results[index]
      const transcript = result?.[0]?.transcript?.trim() || ''
      if (!transcript) continue

      if (result.isFinal) finalText += ` ${transcript}`
      else interimText += ` ${transcript}`
    }

    if (finalText.trim()) {
      voiceDraft.value = [voiceDraft.value, finalText.trim()].filter(Boolean).join(' ').trim()
    }
    voiceInterim.value = interimText.trim()
  }

  recognition.onerror = (event: any) => {
    console.error('语音识别失败:', event)
    listening.value = false
    stopWaveform()
    voiceError.value = event?.error === 'not-allowed' || event?.error === 'service-not-allowed'
      ? '麦克风权限被拒绝，请在浏览器设置中允许访问。'
      : `语音识别不可用：${event?.error || '未知错误'}`
  }

  recognition.onend = () => {
    listening.value = false
    stopWaveform()
  }
}

async function toggleVoiceCard() {
  if (!voiceSupported.value) return
  if (voiceCardVisible.value) {
    voiceCardVisible.value = false
    cleanupVoiceCapture()
  } else {
    voiceCardVisible.value = true
    voiceError.value = ''
    voiceDraft.value = ''
    voiceInterim.value = ''
    resetWaveform()
    await startWaveform()
    if (recognition) {
       try {
         recognition.start()
         listening.value = true
       } catch (error) {
         console.error('启动语音识别失败:', error)
         voiceError.value = '启动语音识别失败，请稍后重试。'
         listening.value = false
       }
    } else {
       voiceError.value = '当前浏览器不支持语音识别'
    }
  }
}

function applyVoiceTranscript() {
  if (!voiceTranscript.value) return
  input.value = [input.value, voiceTranscript.value].filter(Boolean).join(' ').trim()
  voiceCardVisible.value = false
  cleanupVoiceCapture()
}

watch(voiceCardVisible, (visible) => {
  if (!visible) cleanupVoiceCapture()
})

onBeforeUnmount(() => {
  cleanupVoiceCapture()
})

function handleSend() {
  const text = input.value.trim()
  if (!text || props.sending) return
  emit('send', text)
  input.value = ''
}

async function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  emit('upload', file)
  uploadedFileName.value = file.name
  target.value = ''
}

defineExpose({
    setInput: (text: string) => { input.value = text }
})
</script>

<template>
  <div class="absolute bottom-0 left-0 right-0 p-6 pointer-events-none">
    <div class="max-w-4xl mx-auto flex flex-col gap-4 pointer-events-auto">
      <!-- Voice Capture Card -->
      <Transition
        enter-active-class="transition duration-300 ease-out"
        enter-from-class="transform translate-y-4 opacity-0"
        enter-to-class="transform translate-y-0 opacity-100"
        leave-active-class="transition duration-200 ease-in"
        leave-from-class="transform translate-y-0 opacity-100"
        leave-to-class="transform translate-y-4 opacity-0"
      >
        <div v-if="voiceCardVisible" class="bg-card/95 border border-border/80 p-4 rounded-2xl shadow-2xl backdrop-blur-2xl">
          <div class="flex items-center justify-between mb-3 px-1">
            <div class="flex items-center gap-2">
              <div class="relative flex items-center justify-center">
                <div v-if="listening" class="absolute inset-0 bg-primary/20 rounded-full animate-ping"></div>
                <div class="w-2 h-2 rounded-full" :class="listening ? 'bg-primary' : 'bg-muted-foreground/40'"></div>
              </div>
              <span class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{{ listening ? '正在倾听...' : '已暂停' }}</span>
            </div>
            <Button variant="ghost" size="icon" class="h-6 w-6 rounded-full" @click="toggleVoiceCard"><X :size="14" /></Button>
          </div>

          <div class="bg-muted/30 rounded-xl p-4 min-h-[80px] border border-border/40 relative group transition-all hover:bg-muted/40 overflow-hidden">
            <p v-if="!voiceTranscript && !voiceError" class="text-sm text-muted-foreground/60 italic animate-pulse">说出你的安全需求，例如：分析最近一小时的异常 IP...</p>
            <p v-if="voiceError" class="text-sm text-destructive font-medium">{{ voiceError }}</p>
            <p v-else class="text-[15px] leading-relaxed text-foreground/90 whitespace-pre-wrap font-medium">
              {{ voiceTranscript }}
            </p>
          </div>

          <div class="mt-4 flex items-center gap-4">
            <!-- Waveform Animation -->
            <div class="flex-1 flex items-center justify-start h-8 px-2 overflow-hidden gap-[3px]">
              <div
                v-for="(scale, index) in waveformBars"
                :key="index"
                class="w-[3px] bg-primary/40 rounded-full transition-all duration-75"
                :style="{ height: `${scale * 100}%`, backgroundColor: listening ? 'hsl(var(--primary))' : 'hsl(var(--muted-foreground)/0.3)' }"
              ></div>
            </div>

            <div class="flex items-center gap-2">
              <Button variant="outline" size="sm" class="rounded-full text-xs h-9 px-4 hover:border-border" @click="voiceDraft = ''; voiceInterim = ''">重置</Button>
              <Button :disabled="!canApplyVoice" variant="default" size="sm" class="rounded-full text-xs h-9 px-5 bg-primary shadow-lg shadow-primary/20" @click="applyVoiceTranscript">应用文本</Button>
            </div>
          </div>
        </div>
      </Transition>

      <!-- Main Input Bar -->
      <div class="bg-card/85 backdrop-blur-2xl border border-border/60 p-3 rounded-2xl shadow-2xl flex flex-col gap-2 relative">
        <Textarea
          v-model="input"
          placeholder="给 AimiGuard AI 发送消息..."
          class="border-none bg-transparent focus-visible:ring-0 min-h-[48px] max-h-48 resize-none text-[15px] p-2 placeholder:text-muted-foreground/50 transition-all font-medium"
          @keydown.enter.prevent="handleSend"
          :disabled="sending"
        />

        <div class="flex items-center justify-between border-t border-border/40 pt-2 px-1">
          <div class="flex items-center gap-1">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger as-child>
                  <Button
                    v-if="voiceSupported"
                    variant="ghost"
                    size="icon"
                    class="h-9 w-9 rounded-full transition-all"
                    :class="[voiceCardVisible ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-muted']"
                    @click="toggleVoiceCard"
                  >
                    <Mic :size="18" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>语音输入</TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger as-child>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="h-9 w-9 rounded-full transition-all"
                    :class="[ttsEnabled ? 'text-primary bg-primary/5' : 'text-muted-foreground']"
                    @click="emit('toggleTts')"
                  >
                    <component :is="ttsEnabled ? Volume2 : VolumeX" :size="18" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>{{ ttsEnabled ? '关闭语音播报' : '开启语音播报' }}</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger as-child>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="h-9 w-9 rounded-full transition-all"
                    :class="uploadedFileName ? 'text-primary bg-primary/10' : 'text-muted-foreground hover:bg-muted'"
                    @click="fileInputRef?.click()"
                  >
                    <FileUp :size="18" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>上传演练文档</TooltipContent>
              </Tooltip>
              <input ref="fileInputRef" type="file" accept=".txt,.md,.doc,.docx,.pdf" class="hidden" @change="handleFileChange" />
              <Button variant="ghost" size="icon" class="h-9 w-9 rounded-full text-muted-foreground"><History :size="18" /></Button>
              <Button variant="ghost" size="icon" class="h-9 w-9 rounded-full text-muted-foreground"><Settings :size="18" /></Button>
            </TooltipProvider>
          </div>

          <Button
            size="icon"
            class="h-9 w-9 rounded-full shadow-lg transition-all hover:scale-105 active:scale-95"
            :class="input.trim() || sending
              ? 'bg-primary/95 text-primary-foreground shadow-primary/20 disabled:shadow-none'
              : 'bg-muted/80 text-muted-foreground shadow-none'"
            :disabled="!input.trim() && !sending"
            @click="sending ? emit('stop') : handleSend()"
          >
            <component :is="sending ? Square : Send" :size="18" :class="sending ? 'fill-current' : ''" />
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
