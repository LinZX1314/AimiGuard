<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { useErrorStore } from '@/stores/error'
import { watch } from 'vue'
import { AlertTriangle, X } from 'lucide-vue-next'

const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()
const errorStore = useErrorStore()

// Guard: redirect to login if not authenticated
watch(() => auth.isLoggedIn, (v) => {
  if (!v) router.replace('/login')
}, { immediate: true })
</script>

<template>
  <router-view />
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
