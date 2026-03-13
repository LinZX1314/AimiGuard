<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

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
      // draw lines to close particles
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
onUnmounted(() => cancelAnimationFrame(animFrame))

// ─── Auth ──────────────────────────────────────────────────────────────────
async function handleLogin() {
  if (!username.value || !password.value) { error.value = '请输入用户名和密码'; return }
  loading.value = true; error.value = ''
  try {
    await auth.login(username.value, password.value)
    router.replace('/')
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '登录失败，请检查账号密码'
  } finally { loading.value = false }
}
</script>

<template>
  <v-app>
    <v-main>
      <!-- Particle canvas -->
      <canvas ref="canvasRef" style="position:fixed; inset:0; z-index:0; background:#0B0F19;" />

      <v-container class="fill-height" fluid style="position:relative; z-index:1">
        <v-row align="center" justify="center" class="fill-height">
          <v-col cols="12" sm="8" md="5" lg="4">
            <!-- Logo -->
            <div class="text-center mb-8">
              <div style="position:relative; display:inline-block">
                <v-icon size="72" color="primary">mdi-shield-sword-outline</v-icon>
                <span style="position:absolute; inset:0; border-radius:50%; box-shadow:0 0 32px 8px rgba(0,229,255,.25); pointer-events:none" />
              </div>
              <div
                class="text-h5 font-weight-bold mt-3"
                style="color:#00E5FF; letter-spacing:.1em; text-shadow:0 0 20px rgba(0,229,255,.5)"
              >
                玄枢·AI攻防指挥官
              </div>
              <div class="text-caption mt-1" style="color:rgba(255,255,255,.4); letter-spacing:.2em">
                AIMIGUARD SECURITY PLATFORM
              </div>
            </div>

            <v-card
              style="
                background: rgba(26,34,53,0.85);
                backdrop-filter: blur(16px);
                border: 1px solid rgba(0,229,255,0.18);
                box-shadow: 0 0 40px rgba(0,229,255,0.08);
              "
            >
              <v-card-text class="pa-8">
                <v-alert v-if="error" type="error" density="compact" class="mb-4" :text="error" />

                <v-text-field
                  v-model="username"
                  label="用户名"
                  prepend-inner-icon="mdi-account-outline"
                  class="mb-3"
                  @keyup.enter="handleLogin"
                />
                <v-text-field
                  v-model="password"
                  label="密码"
                  prepend-inner-icon="mdi-lock-outline"
                  :append-inner-icon="showPwd ? 'mdi-eye-off' : 'mdi-eye'"
                  :type="showPwd ? 'text' : 'password'"
                  class="mb-5"
                  @click:append-inner="showPwd = !showPwd"
                  @keyup.enter="handleLogin"
                />

                <v-btn
                  color="primary"
                  block
                  size="large"
                  :loading="loading"
                  style="letter-spacing:.1em"
                  @click="handleLogin"
                >
                  <v-icon start>mdi-login</v-icon>
                  登 录
                </v-btn>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
    </v-main>
  </v-app>
</template>

