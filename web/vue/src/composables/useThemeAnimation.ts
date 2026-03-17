import { onMounted } from 'vue'

export function useThemeAnimation() {
  const toggleTheme = (event: MouseEvent, toggleFn: () => void) => {
    if (!document.startViewTransition) {
      toggleFn()
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
      toggleFn()
    })

    transition.finished.then(() => {
      document.documentElement.classList.remove('view-transitioning')
    })
  }

  return { toggleTheme }
}
