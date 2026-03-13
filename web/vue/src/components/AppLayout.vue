<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route  = useRoute()
const auth   = useAuthStore()
const drawer = ref(true)
const rail   = ref(false)

const navItems = [
  { title: '总览大屏',   icon: 'mdi-view-dashboard',        to: '/' },
  { title: 'HFish 蜜罐', icon: 'mdi-spider-web',            to: '/hfish' },
  { title: 'Nmap 扫描',  icon: 'mdi-radar',                 to: '/nmap' },
  { title: '漏洞管理',   icon: 'mdi-bug-outline',           to: '/vuln' },
  { title: '防御事件',   icon: 'mdi-shield-alert-outline',  to: '/defense' },
  { title: '防火墙',     icon: 'mdi-shield-lock-outline',   to: '/firewall' },
  { title: '蜜罐管理',   icon: 'mdi-pot-mix-outline',       to: '/honeypots' },
  { title: 'AI 助手',    icon: 'mdi-robot-outline',         to: '/ai' },
  { title: '审计日志',   icon: 'mdi-clipboard-text-clock',  to: '/audit' },
  { title: '威胁情报',   icon: 'mdi-earth',                 to: '/threat' },
  { title: '工作流',     icon: 'mdi-sitemap-outline',       to: '/workflow' },
  { title: '系统设置',   icon: 'mdi-cog-outline',           to: '/settings' },
]

const currentTitle = computed(() => {
  const match = navItems.find(n => n.to === route.path) 
  return match?.title ?? '玄枢·AI攻防指挥官'
})

function handleLogout() {
  auth.logout()
  router.replace('/login')
}
</script>

<template>
  <v-app>
    <!-- ─── Navigation Drawer ─── -->
    <v-navigation-drawer
      v-model="drawer"
      :rail="rail"
      permanent
      color="surface"
      style="border-right: 1px solid rgba(255,255,255,0.06);"
    >
      <!-- Logo -->
      <v-list-item
        :prepend-avatar="new URL('@/assets/aimiguard-logo.png', import.meta.url).href"
        title="玄枢·AI攻防指挥官"
        nav
        class="py-4"
        style="color: #00E5FF;"
      >
        <template #append>
          <v-btn
            :icon="rail ? 'mdi-chevron-right' : 'mdi-chevron-left'"
            variant="text"
            density="compact"
            @click="rail = !rail"
          />
        </template>
      </v-list-item>

      <v-divider />

      <v-list density="compact" nav class="mt-1">
        <v-list-item
          v-for="item in navItems"
          :key="item.to"
          :prepend-icon="item.icon"
          :title="item.title"
          :to="item.to"
          :exact="item.to === '/'"
          active-color="primary"
          rounded="lg"
          class="mb-1"
        />
      </v-list>

      <template #append>
        <v-divider />
        <v-list density="compact" nav class="my-1">
          <v-list-item
            prepend-icon="mdi-logout"
            title="退出登录"
            rounded="lg"
            @click="handleLogout"
          />
        </v-list>
      </template>
    </v-navigation-drawer>

    <!-- ─── App Bar ─── -->
    <v-app-bar
      flat
      color="surface"
      style="border-bottom: 1px solid rgba(255,255,255,0.06);"
    >
      <v-app-bar-nav-icon @click="drawer = !drawer" />
      <v-app-bar-title>
        <span class="text-subtitle-1 font-weight-medium">{{ currentTitle }}</span>
      </v-app-bar-title>
      <template #append>
        <v-chip size="small" color="primary" variant="tonal" class="mr-3">
          <v-icon start size="16">mdi-account-circle</v-icon>
          {{ auth.user?.username ?? 'admin' }}
        </v-chip>
      </template>
    </v-app-bar>

    <!-- ─── Main Content ─── -->
    <v-main>
      <router-view />
    </v-main>
  </v-app>
</template>

<style scoped>
:deep(.v-list-item--active) {
  background: rgba(0, 229, 255, 0.08) !important;
}
</style>
