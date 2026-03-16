<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent } from '@/components/ui/card'
import { Shield, User, Lock, Eye, EyeOff, LogIn } from 'lucide-vue-next'

const router = useRouter()
const auth   = useAuthStore()
const loading  = ref(false)
const error    = ref('')
const username = ref('admin')
const password = ref('')
const showPwd  = ref(false)
const canvasRef = ref<HTMLCanvasElement | null>(null)
let animFrame: number

// ─── Particle Background ───────────────────────────────────────────────────
function initParticles(canvas: HTMLCanvasElement) {
  const ctx = canvas.getContext('2d')!
  const resize = () => { canvas.width = window.innerWidth; canvas.height = window.innerHeight }
  resize()
  window.addEventListener('resize', resize)

  type Particle = { x: number; y: number; vx: number; vy: number; r: number; alpha: number }
  const N = 90
  const particles: Particle[] = Array.from({ length: N }, () => ({
    x: Math.random() * canvas.width,
    y: Math.random() * canvas.height,
    vx: (Math.random() - 0.5) * 0.4,
    vy: (Math.random() - 0.5) * 0.4,
    r: Math.random() * 1.8 + 0.4,
    alpha: Math.random() * 0.5 + 0.2,
  }))

  const draw = () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    for (let i = 0; i < N; i++) {
      const p = particles[i]
      p.x += p.vx; p.y += p.vy
      if (p.x < 0 || p.x > canvas.width)  p.vx *= -1
      if (p.y < 0 || p.y > canvas.height) p.vy *= -1
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(0,229,255,${p.alpha})`
      ctx.fill()
      for (let j = i + 1; j < N; j++) {
        const q = particles[j]
        const d = Math.hypot(p.x - q.x, p.y - q.y)
        if (d < 120) {
          ctx.beginPath()
          ctx.moveTo(p.x, p.y)
          ctx.lineTo(q.x, q.y)
          ctx.strokeStyle = `rgba(0,229,255,${(1 - d / 120) * 0.15})`
          ctx.lineWidth = 0.6
          ctx.stroke()
        }
      }
    }
    animFrame = requestAnimationFrame(draw)
  }
  draw()
  return () => { window.removeEventListener('resize', resize) }
}

onMounted(() => {
  if (canvasRef.value) initParticles(canvasRef.value)
})
onUnmounted(() => {
  if (animFrame) cancelAnimationFrame(animFrame)
})

// ─── Auth ──────────────────────────────────────────────────────────────────
async function handleLogin() {
  if (!username.value || !password.value) { 
    error.value = '请输入用户名和密码'
    return 
  }
  loading.value = true
  error.value = ''
  try {
    await auth.login(username.value, password.value)
    router.replace('/')
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '登录失败，请检查账号密码'
  } finally { 
    loading.value = false 
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center relative overflow-hidden bg-[#0B0F19]">
    <!-- Particle canvas -->
    <canvas ref="canvasRef" class="fixed inset-0 z-0 pointer-events-none" />

    <div class="relative z-10 w-full max-w-md px-6 animate-in fade-in duration-1000">
      <!-- Logo Section -->
      <div class="text-center mb-10">
        <div class="relative inline-block">
          <Shield class="h-16 w-16 text-primary drop-shadow-[0_0_15px_rgba(0,229,255,0.4)]" />
          <div class="absolute inset-0 rounded-full blur-2xl bg-primary/20 -z-10"></div>
        </div>
        <h1 class="text-3xl font-bold mt-4 tracking-wider bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
          玄枢·AI攻防指挥官
        </h1>
        <p class="text-[10px] sm:text-xs mt-2 text-slate-500 tracking-[0.2em] font-medium uppercase">
          AIMIGUARD SECURITY PLATFORM
        </p>
      </div>

      <!-- Login Card -->
      <Card class="bg-slate-900/80 backdrop-blur-xl border border-cyan-400/20 shadow-[0_0_40px_rgba(0,229,255,0.08)]">
        <CardContent class="pt-8 px-8 pb-10 space-y-5">
          <Alert v-if="error" variant="destructive" class="mb-2 bg-destructive/10 border-destructive/20 py-3">
            <AlertDescription>{{ error }}</AlertDescription>
          </Alert>

          <div class="space-y-4">
            <div class="relative">
              <User class="absolute left-3 top-3 h-4 w-4 text-slate-400" />
              <Input 
                v-model="username" 
                placeholder="用户名" 
                class="pl-10 bg-black/40 border-slate-700/50 h-11 text-slate-100 placeholder:text-slate-500 focus:border-primary/50"
                @keyup.enter="handleLogin"
              />
            </div>
            
            <div class="relative">
              <Lock class="absolute left-3 top-3 h-4 w-4 text-slate-400" />
              <Input 
                v-model="password" 
                :type="showPwd ? 'text' : 'password'"
                placeholder="密码" 
                class="pl-10 pr-10 bg-black/40 border-slate-700/50 h-11 text-slate-100 placeholder:text-slate-500 focus:border-primary/50"
                @keyup.enter="handleLogin"
              />
              <button 
                type="button" 
                @click="showPwd = !showPwd"
                class="absolute right-3 top-3 text-slate-400 hover:text-slate-200"
              >
                <EyeOff v-if="showPwd" class="h-4 w-4" />
                <Eye v-else class="h-4 w-4" />
              </button>
            </div>
          </div>

          <Button 
            class="w-full h-11 text-[15px] font-semibold tracking-widest bg-primary hover:bg-primary/90 text-primary-foreground shadow-lg shadow-primary/10"
            :disabled="loading"
            @click="handleLogin"
          >
            <template v-if="loading">
              <div class="animate-spin h-5 w-5 border-2 border-primary-foreground border-t-transparent rounded-full mr-2"></div>
              处理中...
            </template>
            <template v-else>
              <LogIn class="mr-2 h-4 w-4" />
              登 录
            </template>
          </Button>
        </CardContent>
      </Card>
      
      <div class="text-center mt-8 text-slate-600 text-xs">
        &copy; 2026 玄枢安全实验室 · 安全可靠的AI保障系统
      </div>
    </div>
  </div>
</template>
