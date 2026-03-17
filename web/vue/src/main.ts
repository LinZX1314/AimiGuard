import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHashHistory } from 'vue-router'
import './assets/index.css'

import App from './App.vue'
import { routes } from './router/index'
import { useErrorStore } from './stores/error'
import { useAuthStore } from './stores/auth'
import { setErrorStoreRef } from './api/index'

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

const pinia = createPinia()
const app = createApp(App)

// 初始化错误store引用
const errorStore = useErrorStore(pinia)
setErrorStoreRef(errorStore)

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
