import type { RouteRecordRaw } from 'vue-router'

export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    component: () => import('../components/AppLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '',          name: 'Dashboard',    component: () => import('../views/DashboardView.vue') },
      { path: 'hfish',     name: 'HFish',        component: () => import('../views/HFishView.vue') },
      { path: 'nmap',      name: 'Nmap',         component: () => import('../views/NmapView.vue') },
      { path: 'vuln',      name: 'Vuln',         component: () => import('../views/VulnView.vue') },
      { path: 'defense',   name: 'Defense',      component: () => import('../views/DefenseView.vue') },
      { path: 'honeypots', name: 'Honeypots',    component: () => import('../views/HoneypotsView.vue') },
      { path: 'ai',        name: 'AiChat',       component: () => import('../views/AiChatView.vue') },
      { path: 'audit',     name: 'Audit',        component: () => import('../views/AuditView.vue') },
      { path: 'threat',    name: 'ThreatIntel',  component: () => import('../views/ThreatIntelView.vue') },
      { path: 'settings',  name: 'Settings',     component: () => import('../views/SettingsView.vue') },
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]
