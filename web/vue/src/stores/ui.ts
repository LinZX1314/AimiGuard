import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type Theme = 'light' | 'dark'

export const useUiStore = defineStore('ui', () => {
  const storedTheme = localStorage.getItem('ag-theme') as Theme | null
  const theme = ref<Theme>(storedTheme === 'light' || storedTheme === 'dark' ? storedTheme : 'dark')

  function setTheme(t: Theme) {
    theme.value = t
  }

  window.addEventListener('storage', (event) => {
    if (event.key !== 'ag-theme') {
      return
    }
    const nextTheme = event.newValue
    if (nextTheme === 'light' || nextTheme === 'dark') {
      theme.value = nextTheme
    }
  })

  watch(theme, (newTheme) => {
    localStorage.setItem('ag-theme', newTheme)
    // 同步 .dark 类，确保 shadcn / tailwind dark: 样式一致生效
    if (newTheme === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, { immediate: true })

  return {
    theme,
    setTheme
  }
})
