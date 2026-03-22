<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { useErrorStore } from '@/stores/error'
import { AlertTriangle, X } from 'lucide-vue-next'
import RouteLoading from '@/components/RouteLoading.vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const ui = useUiStore()
const errorStore = useErrorStore()
const routeChanging = ref(false)
const isDashboardRoute = computed(() => route.path === '/')
const isAiRoute = computed(() => route.path.startsWith('/ai'))
const showPerspectiveGrid = computed(() => !route.meta.public)

const ROUTE_PROGRESS_MIN_MS = 220
let routeChangeStartedAt = 0

const hideProgress = () => {
  const elapsed = Date.now() - routeChangeStartedAt
  const remain = Math.max(0, ROUTE_PROGRESS_MIN_MS - elapsed)
  window.setTimeout(() => {
    routeChanging.value = false
  }, remain)
}

const removeBeforeGuard = router.beforeEach((to, from, next) => {
  if (to.fullPath !== from.fullPath) {
    routeChangeStartedAt = Date.now()
    routeChanging.value = true
  }
  next()
})

const removeAfterGuard = router.afterEach(() => {
  hideProgress()
})

const removeErrorHandler = router.onError(() => {
  routeChanging.value = false
})

// Guard: redirect to login if not authenticated
watch(() => auth.isLoggedIn, (v) => {
  if (!v) router.replace('/login')
}, { immediate: true })

watch(
  isDashboardRoute,
  (active) => {
    document.documentElement.classList.toggle('dashboard-route-active', active)
  },
  { immediate: true },
)

watch(
  isAiRoute,
  (active) => {
    document.documentElement.classList.toggle('ai-chat-background-disabled', active)
  },
  { immediate: true },
)

onUnmounted(() => {
  removeBeforeGuard()
  removeAfterGuard()
  removeErrorHandler()
  document.documentElement.classList.remove('dashboard-route-active')
  document.documentElement.classList.remove('ai-chat-background-disabled')
})
</script>

<template>
  <!-- 3D 透视网格地板 -->
  <div v-if="showPerspectiveGrid" class="perspective-floor">
    <div class="perspective-floor__grid"></div>
  </div>

  <transition name="route-progress-fade">
    <div v-if="routeChanging" class="route-progress" aria-hidden="true">
      <span class="route-progress__line route-progress__line--primary" />
      <span class="route-progress__line route-progress__line--secondary" />
    </div>
  </transition>

  <router-view v-slot="{ Component, route }">
    <Suspense>
      <transition
        :name="route.meta.public ? 'login-fade' : 'page-fade'"
        mode="out-in"
        appear
      >
        <component :is="Component" :key="route.meta.public ? route.fullPath : 'private-layout'" />
      </transition>
      <template #fallback>
        <RouteLoading />
      </template>
    </Suspense>
  </router-view>
  <!-- Global Error Toast -->
  <Transition
    enter-active-class="transition-all duration-300 ease-out"
    enter-from-class="opacity-0 translate-y-2"
    enter-to-class="opacity-100 translate-y-0"
    leave-active-class="transition-all duration-200 ease-in"
    leave-from-class="opacity-100 translate-y-0"
    leave-to-class="opacity-0 translate-y-2"
  >
    <div
      v-if="errorStore.message"
      class="fixed bottom-4 right-4 z-50 max-w-sm"
    >
      <div
        class="flex items-start gap-3 p-4 rounded-lg border shadow-lg"
        :class="errorStore.type === 'error'
          ? 'bg-red-950/90 border-red-500/50 text-red-200'
          : 'bg-amber-950/90 border-amber-500/50 text-amber-200'"
      >
        <AlertTriangle class="h-5 w-5 shrink-0 mt-0.5" />
        <p class="flex-1 text-sm">{{ errorStore.message }}</p>
        <button @click="errorStore.clear()" class="shrink-0 hover:opacity-70">
          <X class="h-4 w-4" />
        </button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.route-progress {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 4px;
  overflow: hidden;
  z-index: 120;
  pointer-events: none;
  background: var(--route-progress-track);
  backdrop-filter: blur(2px);
}

.route-progress__line {
  position: absolute;
  top: 0;
  left: 0;
  display: block;
  width: 46%;
  height: 100%;
  border-radius: 9999px;
  background: linear-gradient(
    90deg,
    transparent 0%,
    var(--route-progress-color-soft) 18%,
    var(--route-progress-color) 55%,
    transparent 100%
  );
}

:global(html) .route-progress {
  --route-progress-color: #0b0b0b;
  --route-progress-color-soft: rgba(0, 0, 0, 0.45);
  --route-progress-track: rgba(0, 0, 0, 0.08);
}

:global(html.dark) .route-progress {
  --route-progress-color: #ffffff;
  --route-progress-color-soft: rgba(255, 255, 255, 0.45);
  --route-progress-track: rgba(255, 255, 255, 0.12);
}

.route-progress__line--primary {
  box-shadow: 0 0 14px var(--route-progress-color-soft);
  animation: route-progress-sweep 1.08s cubic-bezier(0.22, 0.61, 0.36, 1) infinite;
}

.route-progress__line--secondary {
  width: 26%;
  opacity: 0.75;
  filter: blur(0.4px);
  animation: route-progress-sweep 1.08s cubic-bezier(0.22, 0.61, 0.36, 1) infinite;
  animation-delay: 0.28s;
}

.route-progress-fade-enter-active,
.route-progress-fade-leave-active {
  transition: opacity 0.2s ease;
}

.route-progress-fade-enter-from,
.route-progress-fade-leave-to {
  opacity: 0;
}

@keyframes route-progress-sweep {
  0% {
    transform: translateX(-130%);
  }

  45% {
    transform: translateX(105%);
  }

  100% {
    transform: translateX(240%);
  }
}
</style>
