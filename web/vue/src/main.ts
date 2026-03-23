import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHashHistory } from 'vue-router'
import './assets/index.css'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

import App from './App.vue'
import { routes } from './router/index'
import { useErrorStore } from './stores/error'
import { useAuthStore } from './stores/auth'
import { setErrorStoreRef } from './api/index'

function clearClientAuthArtifacts() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  sessionStorage.clear()

  // 尽可能清理前端可访问cookie（HttpOnly由后端控制）
  document.cookie.split(';').forEach((entry) => {
    const cookie = entry.trim()
    if (!cookie) return
    const eqIdx = cookie.indexOf('=')
    const name = eqIdx >= 0 ? cookie.slice(0, eqIdx) : cookie
    document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/`
  })
}

function installUnauthorizedGuard() {
  const rawFetch = window.fetch.bind(window)
  let handlingUnauthorized = false

  window.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const response = await rawFetch(input, init)
    if (response.status !== 401) {
      return response
    }

    const url = typeof input === 'string'
      ? input
      : input instanceof Request
        ? input.url
        : String(input)

    // 登录接口本身401不触发全局登出
    if (url.includes('/api/v1/auth/login')) {
      return response
    }

    if (!handlingUnauthorized) {
      handlingUnauthorized = true
      const auth = useAuthStore(pinia)
      auth.logout()
      clearClientAuthArtifacts()
      if (router.currentRoute.value.path !== '/login') {
        router.replace('/login')
      }
      window.setTimeout(() => {
        handlingUnauthorized = false
      }, 300)
    }

    return response
  }) as typeof window.fetch
}

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

const pinia = createPinia()
const app = createApp(App)

// 初始化错误store引用
const errorStore = useErrorStore(pinia)
setErrorStoreRef(errorStore)
installUnauthorizedGuard()

// 路由守卫：未登录用户重定向到登录页
router.beforeEach((to, _from, next) => {
  const auth = useAuthStore(pinia)
  if (!to.meta.public && !auth.isLoggedIn) {
    next('/login')
  } else if (to.path === '/login' && auth.isLoggedIn) {
    next('/')
  } else {
    next()
  }
})

app.use(pinia)
app.use(router)
app.mount('#app')
