import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createVuetify } from 'vuetify'
import { createRouter, createWebHashHistory } from 'vue-router'
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'

import App from './App.vue'
import { routes } from './router/index'

const vuetify = createVuetify({
  theme: {
    defaultTheme: 'dark',
    themes: {
      dark: {
        colors: {
          primary:    '#00E5FF',
          secondary:  '#8B5CF6',
          accent:     '#F472B6',
          error:      '#EF4444',
          warning:    '#F59E0B',
          info:       '#3B82F6',
          success:    '#10B981',
          background: '#0B0F19',
          surface:    '#1A2235',
        }
      }
    }
  },
  defaults: {
    VCard:    { rounded: 'lg' },
    VBtn:     { rounded: 'lg' },
    VTextField: { variant: 'outlined', density: 'compact' },
    VSelect:    { variant: 'outlined', density: 'compact' },
  }
})

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)
app.use(vuetify)
app.use(router)
app.mount('#app')
