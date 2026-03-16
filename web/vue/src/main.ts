import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHashHistory } from 'vue-router'
import './assets/index.css'

import App from './App.vue'
import { routes } from './router/index'
import { useErrorStore } from './stores/error'
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

app.use(pinia)
app.use(router)
app.mount('#app')
