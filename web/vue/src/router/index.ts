import type { RouteRecordRaw } from 'vue-router'

const ROUTE_LOADING_MIN_MS = 250

// 统一封装异步路由：保证每次切换时 loading 至少展示一小段时间，避免闪烁。
function lazyWithMinDelay(loader: () => Promise<unknown>) {
  return () =>
    Promise.all([
      loader(),
      new Promise((resolve) => setTimeout(resolve, ROUTE_LOADING_MIN_MS)),
    ]).then(([component]) => component)
}

export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: lazyWithMinDelay(() => import('../views/LoginView.vue')),
    meta: { public: true }
  },
  {
    path: '/',
    component: lazyWithMinDelay(() => import('../components/AppLayout.vue')),
    meta: { requiresAuth: true },
    children: [
      { path: '',          name: 'Dashboard',    component: lazyWithMinDelay(() => import('../views/DashboardView.vue')) },
      { path: 'hfish',     name: 'HFish',        component: lazyWithMinDelay(() => import('../views/HFishView.vue')) },
      { path: 'nmap',      name: 'Nmap',         component: lazyWithMinDelay(() => import('../views/NmapView.vue')) },
      { path: 'screenshots', name: 'NmapScreenshots', component: lazyWithMinDelay(() => import('../views/NmapScreenshotsView.vue')) },
      { path: 'defense',   name: 'Defense',      component: lazyWithMinDelay(() => import('../views/DefenseView.vue')) },
      { path: 'ai',        name: 'AiChat',       component: lazyWithMinDelay(() => import('../views/AiChatView.vue')) },
      { path: 'settings',  name: 'Settings',     component: lazyWithMinDelay(() => import('../views/SettingsView.vue')) },
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]
