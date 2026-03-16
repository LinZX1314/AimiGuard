import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type Theme = 'cyberpunk' | 'indigo' | 'forest' | 'rose'

export const useUiStore = defineStore('ui', () => {
  const theme = ref<Theme>((localStorage.getItem('ag-theme') as Theme) || 'cyberpunk')

  function setTheme(t: Theme) {
    theme.value = t
  }

  watch(theme, (newTheme) => {
    localStorage.setItem('ag-theme', newTheme)
    document.documentElement.setAttribute('data-theme', newTheme)
    // Also toggle .dark class for compatibility with Shadcn components that might use it
    const darkThemes: Theme[] = ['cyberpunk', 'indigo', 'forest']
    if (darkThemes.includes(newTheme)) {
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
