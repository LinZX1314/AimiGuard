<template>
  <canvas ref="canvas" class="fixed inset-0 pointer-events-none" style="z-index: 0;" />
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const canvas = ref<HTMLCanvasElement>()
let ctx: CanvasRenderingContext2D | null = null
let particles: Particle[] = []
let animationId: number

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  radius: number
}

const config = {
  particleCount: 50,
  particleSpeed: 0.3,
  lineDistance: 120,
  particleRadius: 1.2
}

function initCanvas() {
  if (!canvas.value) return

  canvas.value.width = window.innerWidth
  canvas.value.height = window.innerHeight
  ctx = canvas.value.getContext('2d')

  particles = Array.from({ length: config.particleCount }, () => ({
    x: Math.random() * canvas.value!.width,
    y: Math.random() * canvas.value!.height,
    vx: (Math.random() - 0.5) * config.particleSpeed,
    vy: (Math.random() - 0.5) * config.particleSpeed,
    radius: config.particleRadius
  }))
}

function animate() {
  if (!ctx || !canvas.value) return

  ctx.clearRect(0, 0, canvas.value.width, canvas.value.height)

  // 动态判断当前主题模式
  const isDark = document.documentElement.classList.contains('dark')
  
  // 暗黑模式下用极客蓝/青，明亮模式下用清新蓝
const particleColor = 'hsl(var(--primary) / 0.6)'
const lineColor = 'hsl(var(--primary) / 0.2)'

  particles.forEach((p, i) => {
    p.x += p.vx
    p.y += p.vy

    if (p.x < 0 || p.x > canvas.value!.width) p.vx *= -1
    if (p.y < 0 || p.y > canvas.value!.height) p.vy *= -1

    ctx!.beginPath()
    ctx!.arc(p.x, p.y, p.radius, 0, Math.PI * 2)
    ctx!.fillStyle = particleColor
    ctx!.fill()

    for (let j = i + 1; j < particles.length; j++) {
      const p2 = particles[j]
      const dx = p.x - p2.x
      const dy = p.y - p2.y
      const distance = Math.sqrt(dx * dx + dy * dy)
      
      if (distance < config.lineDistance) {
        ctx!.beginPath()
        ctx!.moveTo(p.x, p.y)
        ctx!.lineTo(p2.x, p2.y)
        ctx!.strokeStyle = lineColor
        ctx!.lineWidth = 1
        ctx!.stroke()
      }
    }
  })

  animationId = requestAnimationFrame(animate)
}

function handleResize() {
  initCanvas()
}

onMounted(() => {
  initCanvas()
  animate()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  cancelAnimationFrame(animationId)
  window.removeEventListener('resize', handleResize)
})
</script>
