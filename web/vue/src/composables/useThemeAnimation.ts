import { onMounted } from 'vue'

export function useThemeAnimation() {
  const toggleTheme = (event: MouseEvent) => {
    const isDark = document.documentElement.classList.contains('dark')

    if (!document.startViewTransition) {
      document.documentElement.classList.toggle('dark')
      return
    }

    const target = event.currentTarget as HTMLElement
    // Get mouse click coordinates or button center
    const x = event.clientX
    const y = event.clientY
    
    // Set custom properties for the CSS animation
    document.documentElement.style.setProperty('--click-x', x + 'px')
    document.documentElement.style.setProperty('--click-y', y + 'px')
    document.documentElement.classList.add('view-transitioning')

    const transition = document.startViewTransition(() => {
      document.documentElement.classList.toggle('dark')
    })
    
    transition.finished.then(() => {
      document.documentElement.classList.remove('view-transitioning')
    })
  }

  return { toggleTheme }
}
