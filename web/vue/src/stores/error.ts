import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useErrorStore = defineStore('error', () => {
  const message = ref('')
  const type = ref<'error' | 'warning' | 'info'>('error')
  let timeoutId: ReturnType<typeof setTimeout> | null = null

  function show(msg: string, t: 'error' | 'warning' | 'info' = 'error', duration = 5000) {
    message.value = msg
    type.value = t
    if (timeoutId) clearTimeout(timeoutId)
    timeoutId = setTimeout(() => {
      message.value = ''
    }, duration)
  }

  function error(msg: string, duration?: number) {
    show(msg, 'error', duration)
  }

  function warning(msg: string, duration?: number) {
    show(msg, 'warning', duration)
  }

  function clear() {
    message.value = ''
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
  }

  return { message, type, show, error, warning, clear }
})
