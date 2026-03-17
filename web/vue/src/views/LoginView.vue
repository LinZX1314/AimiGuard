<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Shield, User, Lock, Eye, EyeOff, LogIn, AlertTriangle, Scan, Sun, Moon } from 'lucide-vue-next'

const router = useRouter()
const auth   = useAuthStore()
const uiStore = useUiStore()
const loading  = ref(false)
const error    = ref('')
const username = ref('admin')
const password = ref('')
const showPwd  = ref(false)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const mounted  = ref(false)
const shakeError = ref(false)
const loginSuccess = ref(false)
const focusField = ref<'none' | 'user' | 'pass'>('none')
let animFrame: number
let cleanupResize: (() => void) | null = null

// ─── Typing subtitle ───────────────────────────────────────────────────────
const subtitleText = 'INTELLIGENT THREAT DEFENSE SYSTEM'
const typedLen = ref(0)
const typedSubtitle = computed(() => subtitleText.slice(0, typedLen.value))
const showCursor = ref(true)
const isDark = computed(() => uiStore.theme === 'dark')

function handleToggleTheme() {
  uiStore.setTheme(uiStore.theme === 'dark' ? 'light' : 'dark')
}

function startTyping() {
  let i = 0
  const iv = setInterval(() => {
    if (i >= subtitleText.length) { clearInterval(iv); return }
    typedLen.value = ++i
  }, 55)
  // blink cursor
  const blink = setInterval(() => { showCursor.value = !showCursor.value }, 530)
  onUnmounted(() => { clearInterval(iv); clearInterval(blink) })
}

// ─── Particle Background ───────────────────────────────────────────────────
function initParticles(canvas: HTMLCanvasElement) {
  const ctx = canvas.getContext('2d')!
  let w = 0, h = 0
  const resize = () => { w = canvas.width = window.innerWidth; h = canvas.height = window.innerHeight }
  resize()
  window.addEventListener('resize', resize)

  type Particle = { x: number; y: number; vx: number; vy: number; r: number; alpha: number; pulse: number; speed: number }
  const N = 100
  const particles: Particle[] = Array.from({ length: N }, () => ({
    x: Math.random() * w,
    y: Math.random() * h,
    vx: (Math.random() - 0.5) * 0.35,
    vy: (Math.random() - 0.5) * 0.35,
    r: Math.random() * 2 + 0.3,
    alpha: Math.random() * 0.6 + 0.15,
    pulse: Math.random() * Math.PI * 2,
    speed: Math.random() * 0.02 + 0.01,
  }))

  // mouse interaction
  let mx = -1000, my = -1000
  const onMouse = (e: MouseEvent) => { mx = e.clientX; my = e.clientY }
  window.addEventListener('mousemove', onMouse)

  const draw = () => {
    ctx.clearRect(0, 0, w, h)
    for (let i = 0; i < N; i++) {
      const p = particles[i]
      p.pulse += p.speed
      const breathe = Math.sin(p.pulse) * 0.15 + 1

      // mouse repulsion
      const dmx = p.x - mx, dmy = p.y - my
      const dmDist = Math.sqrt(dmx * dmx + dmy * dmy)
      if (dmDist < 150) {
        const force = (150 - dmDist) / 150 * 0.5
        p.x += (dmx / dmDist) * force
        p.y += (dmy / dmDist) * force
      }

      p.x += p.vx; p.y += p.vy
      if (p.x < 0 || p.x > w) p.vx *= -1
      if (p.y < 0 || p.y > h) p.vy *= -1

      const a = p.alpha * breathe
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.r * breathe, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(0,229,255,${a})`
      ctx.fill()

      // connections
      for (let j = i + 1; j < N; j++) {
        const q = particles[j]
        const dx = p.x - q.x, dy = p.y - q.y
        const d = Math.sqrt(dx * dx + dy * dy)
        if (d < 130) {
          ctx.beginPath()
          ctx.moveTo(p.x, p.y)
          ctx.lineTo(q.x, q.y)
          ctx.strokeStyle = `rgba(0,229,255,${(1 - d / 130) * 0.12})`
          ctx.lineWidth = 0.5
          ctx.stroke()
        }
      }
    }
    animFrame = requestAnimationFrame(draw)
  }
  draw()
  cleanupResize = () => {
    window.removeEventListener('resize', resize)
    window.removeEventListener('mousemove', onMouse)
  }
}

onMounted(async () => {
  if (canvasRef.value) initParticles(canvasRef.value)
  await nextTick()
  // stagger entrance
  setTimeout(() => { mounted.value = true }, 100)
  setTimeout(() => startTyping(), 800)
})

onUnmounted(() => {
  if (animFrame) cancelAnimationFrame(animFrame)
  cleanupResize?.()
})

// ─── Auth ──────────────────────────────────────────────────────────────────
async function handleLogin() {
  if (!username.value || !password.value) { 
    error.value = '请输入用户名和密码'
    triggerShake()
    return 
  }
  loading.value = true
  error.value = ''
  try {
    await auth.login(username.value, password.value)
    loginSuccess.value = true
    // wait for success animation before navigating
    setTimeout(() => router.replace('/'), 600)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '登录失败，请检查账号密码'
    triggerShake()
  } finally { 
    loading.value = false 
  }
}

function triggerShake() {
  shakeError.value = true
  setTimeout(() => { shakeError.value = false }, 500)
}
</script>

<template>
  <div class="login-page min-h-screen flex items-center justify-center relative overflow-hidden bg-background text-foreground">
    <Button
      variant="outline"
      size="sm"
      class="absolute top-5 right-5 z-20 rounded-full border-white/15 bg-black/20 backdrop-blur-md hover:bg-black/30"
      @click="handleToggleTheme"
    >
      <Sun v-if="isDark" class="h-4 w-4 mr-1.5" />
      <Moon v-else class="h-4 w-4 mr-1.5" />
      {{ isDark ? '切换为亮色' : '切换为暗色' }}
    </Button>

    <!-- Ambient glow orbs -->
    <div class="absolute inset-0 overflow-hidden pointer-events-none">
      <div class="absolute w-[600px] h-[600px] -top-40 -left-40 rounded-full bg-cyan-500/[0.04] blur-[120px] animate-[drift_12s_ease-in-out_infinite_alternate]"></div>
      <div class="absolute w-[500px] h-[500px] -bottom-32 -right-32 rounded-full bg-blue-600/[0.05] blur-[100px] animate-[drift_15s_ease-in-out_infinite_alternate-reverse]"></div>
      <div class="absolute w-[300px] h-[300px] top-1/2 left-1/3 rounded-full bg-indigo-500/[0.03] blur-[80px] animate-[drift_10s_ease-in-out_infinite_alternate]"></div>
    </div>

    <!-- Grid overlay -->
    <div class="absolute inset-0 pointer-events-none opacity-[0.04]" style="background-image: linear-gradient(rgba(0,229,255,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(0,229,255,0.3) 1px, transparent 1px); background-size: 60px 60px;"></div>

    <!-- Particle canvas -->
    <canvas ref="canvasRef" class="fixed inset-0 z-0 pointer-events-none" />

    <!-- Scan lines effect -->
    <div class="absolute inset-0 pointer-events-none z-[1] opacity-[0.03]" style="background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,229,255,0.1) 2px, rgba(0,229,255,0.1) 4px);"></div>

    <!-- Main content -->
    <div 
      class="relative z-10 w-full max-w-[420px] px-6 transition-all duration-1000"
      :class="[
        mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8',
        loginSuccess ? 'scale-95 opacity-0' : ''
      ]"
      :style="{ transitionTimingFunction: 'cubic-bezier(0.16, 1, 0.3, 1)' }"
    >
      <!-- Logo Section -->
      <div class="text-center mb-10">
        <!-- Shield icon with glowing ring -->
        <div 
          class="relative inline-flex items-center justify-center transition-all duration-700 delay-200"
          :class="mounted ? 'opacity-100 scale-100' : 'opacity-0 scale-50'"
        >
          <div class="absolute w-24 h-24 rounded-full border border-cyan-400/20 animate-[ping_3s_ease-in-out_infinite]"></div>
          <div class="absolute w-20 h-20 rounded-full border border-cyan-400/10"></div>
          <div class="relative w-16 h-16 rounded-full bg-gradient-to-br from-cyan-500/20 to-blue-600/10 border border-cyan-400/30 flex items-center justify-center backdrop-blur-sm shadow-[0_0_40px_rgba(0,229,255,0.15)]">
            <Shield class="h-8 w-8 text-cyan-400 drop-shadow-[0_0_8px_rgba(0,229,255,0.5)]" />
          </div>
        </div>

        <h1 
          class="text-[28px] font-black mt-6 tracking-wider transition-all duration-700 delay-300"
          :class="mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'"
        >
          <span class="bg-gradient-to-r from-cyan-300 via-cyan-400 to-blue-400 bg-clip-text text-transparent drop-shadow-[0_0_20px_rgba(0,229,255,0.3)]">
            玄枢·AI攻防指挥官
          </span>
        </h1>

        <!-- Typing subtitle -->
        <div 
          class="h-5 mt-2.5 transition-all duration-700 delay-500"
          :class="mounted ? 'opacity-100' : 'opacity-0'"
        >
          <span class="text-[10px] tracking-[0.25em] font-mono text-cyan-600/80">
            {{ typedSubtitle }}<span class="inline-block w-[1px] h-3 bg-cyan-400 ml-[1px] align-middle" :class="showCursor ? 'opacity-100' : 'opacity-0'"></span>
          </span>
        </div>
      </div>

      <!-- Login Card -->
      <div 
        class="relative group transition-all duration-700 delay-500"
        :class="[
          mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6',
          shakeError ? 'animate-[headShake_0.5s_ease-in-out]' : ''
        ]"
      >
        <!-- Card glow border -->
        <div class="absolute -inset-[1px] rounded-xl bg-gradient-to-b from-cyan-400/30 via-cyan-400/5 to-blue-500/20 opacity-60 group-hover:opacity-100 transition-opacity duration-500 blur-[0.5px]"></div>
        
        <div
          class="relative rounded-xl backdrop-blur-2xl overflow-hidden border transition-colors duration-300"
          :class="isDark
            ? 'bg-[#0c1222]/88 border-white/[0.05] shadow-[0_20px_60px_rgba(0,0,0,0.5)]'
            : 'bg-white/78 border-slate-200/80 shadow-[0_14px_45px_rgba(15,23,42,0.14)]'"
        >
          <!-- Top accent line -->
          <div class="h-[1px] w-full bg-gradient-to-r from-transparent via-cyan-400/50 to-transparent"></div>

          <div class="px-8 pt-8 pb-9 space-y-5">
            <!-- Status indicator -->
            <div class="flex items-center justify-between text-[10px] font-mono text-muted-foreground mb-1">
              <span class="flex items-center gap-1.5">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)] animate-pulse"></span>
                安全连接
              </span>
              <span>实时防护</span>
            </div>

            <!-- Error alert -->
            <Transition
              enter-active-class="transition-all duration-300 ease-out"
              enter-from-class="opacity-0 -translate-y-2 scale-95"
              enter-to-class="opacity-100 translate-y-0 scale-100"
              leave-active-class="transition-all duration-200 ease-in"
              leave-from-class="opacity-100 translate-y-0 scale-100"
              leave-to-class="opacity-0 -translate-y-2 scale-95"
            >
              <div v-if="error" class="flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs">
                <AlertTriangle class="w-3.5 h-3.5 shrink-0" />
                {{ error }}
              </div>
            </Transition>

            <!-- Input fields -->
            <div class="space-y-3.5">
              <div 
                class="relative rounded-lg transition-all duration-300"
                :class="focusField === 'user' ? 'shadow-[0_0_0_1px_rgba(0,229,255,0.3),0_0_15px_rgba(0,229,255,0.08)]' : ''"
              >
                <User class="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 transition-colors duration-200" :class="focusField === 'user' ? 'text-cyan-400' : 'text-slate-500'" />
                <Input 
                  v-model="username" 
                  placeholder="用户名"
                  autocomplete="username"
                  class="pl-10 h-11 rounded-lg border-border bg-background/70 text-foreground placeholder:text-muted-foreground focus:border-cyan-400/30 focus:bg-background transition-all duration-300"
                  @focus="focusField = 'user'"
                  @blur="focusField = 'none'"
                  @keyup.enter="handleLogin"
                />
              </div>
              
              <div 
                class="relative rounded-lg transition-all duration-300"
                :class="focusField === 'pass' ? 'shadow-[0_0_0_1px_rgba(0,229,255,0.3),0_0_15px_rgba(0,229,255,0.08)]' : ''"
              >
                <Lock class="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 transition-colors duration-200" :class="focusField === 'pass' ? 'text-cyan-400' : 'text-slate-500'" />
                <Input 
                  v-model="password" 
                  :type="showPwd ? 'text' : 'password'"
                  placeholder="密码"
                  autocomplete="current-password"
                  class="pl-10 pr-10 h-11 rounded-lg border-border bg-background/70 text-foreground placeholder:text-muted-foreground focus:border-cyan-400/30 focus:bg-background transition-all duration-300"
                  @focus="focusField = 'pass'"
                  @blur="focusField = 'none'"
                  @keyup.enter="handleLogin"
                />
                <button 
                  type="button" 
                  @click="showPwd = !showPwd"
                  class="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors duration-200"
                  tabindex="-1"
                >
                  <EyeOff v-if="showPwd" class="h-4 w-4" />
                  <Eye v-else class="h-4 w-4" />
                </button>
              </div>
            </div>

            <!-- Login Button -->
            <Button 
              class="login-btn w-full h-11 text-sm font-bold tracking-[0.15em] uppercase relative overflow-hidden rounded-lg border-0 transition-all duration-300"
              :class="[
                loading 
                  ? 'bg-cyan-500/20 text-cyan-300 cursor-wait' 
                  : 'bg-gradient-to-r from-cyan-500 to-blue-500 text-white hover:shadow-[0_0_30px_rgba(0,229,255,0.25)] hover:scale-[1.01] active:scale-[0.99]'
              ]"
              :disabled="loading"
              @click="handleLogin"
            >
              <!-- Shimmer effect -->
              <div v-if="!loading" class="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full animate-[shimmer_3s_ease-in-out_infinite]"></div>
              
              <template v-if="loading">
                <Scan class="mr-2 h-4 w-4 animate-spin" />
                验证中...
              </template>
              <template v-else>
                <LogIn class="mr-2 h-4 w-4" />
                安全登录
              </template>
            </Button>

            <!-- Bottom decorative line -->
            <div class="flex items-center gap-3 pt-1">
              <div class="flex-1 h-[1px] bg-gradient-to-r from-transparent to-border"></div>
              <span class="text-[9px] font-mono text-muted-foreground tracking-widest">AIMIGUARD v2.0</span>
              <div class="flex-1 h-[1px] bg-gradient-to-l from-transparent to-border"></div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Footer -->
      <div 
        class="text-center mt-8 transition-all duration-700 delay-700"
        :class="mounted ? 'opacity-100' : 'opacity-0'"
      >
        <p class="text-slate-600/80 text-[10px] tracking-wider font-mono">&copy; 2026 玄枢安全实验室</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes drift {
  0% { transform: translate(0, 0) scale(1); }
  100% { transform: translate(30px, -20px) scale(1.1); }
}

@keyframes shimmer {
  0% { transform: translateX(-100%); }
  50%, 100% { transform: translateX(100%); }
}

@keyframes headShake {
  0% { transform: translateX(0); }
  6.5% { transform: translateX(-6px) rotateY(-9deg); }
  18.5% { transform: translateX(5px) rotateY(7deg); }
  31.5% { transform: translateX(-3px) rotateY(-5deg); }
  43.5% { transform: translateX(2px) rotateY(3deg); }
  50% { transform: translateX(0); }
}

.login-page {
  /* Subtle vignette */
  background-image: radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,0.4) 100%);
  background-color: hsl(var(--background));
}
</style>
