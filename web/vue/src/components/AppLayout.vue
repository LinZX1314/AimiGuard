<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route  = useRoute()
const auth   = useAuthStore()
const drawer = ref(true)
const logoUrl = new URL('@/assets/aimiguard-logo.png', import.meta.url).href

const navItems = [
  { title: '总览大屏',   icon: 'mdi-view-dashboard',        to: '/' },
  { title: 'HFish 蜜罐', icon: 'mdi-spider-web',            to: '/hfish' },
  { title: 'Nmap 扫描',  icon: 'mdi-radar',                 to: '/nmap' },
  { title: '漏洞管理',   icon: 'mdi-bug-outline',           to: '/vuln' },
  { title: '防御事件',   icon: 'mdi-shield-alert-outline',  to: '/defense' },
  { title: 'AI 助手',    icon: 'mdi-robot-outline',         to: '/ai' },
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
      permanent
      width="180"
      color="surface"
      style="border-right: 1px solid rgba(255,255,255,0.06);"
    >
      <!-- Logo 固定高度 64px 与顶部 App bar 完美对齐 -->
      <div
        style="height: 64px; width: 100%; border-bottom: 1px solid rgba(255,255,255,0.06); display: flex; align-items: center; overflow: hidden; white-space: nowrap;"
      >
        <div style="display: flex; align-items: center;">
          <v-avatar
            :image="logoUrl"
            size="30"
            class="ml-3 mr-2"
            style="min-width: 30px; filter: drop-shadow(0 0 4px rgba(0,229,255,0.3));"
          ></v-avatar>
        </div>
        <div style="display: flex; flex-direction: column; margin-inline-start: 5px; justify-content: center;">
          <div class="font-weight-black text-body-1" style="background: linear-gradient(120deg, #00E5FF 0%, #3B82F6 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: 1px; line-height: 1.2;">
            玄枢指挥官
          </div>
          <div class="text-caption font-weight-medium" style="color: #8A9CA5; line-height: 1.2; margin-top: 2px; margin-inline-start: 5px;">
                 AI攻防 <span style="color: #00E5FF; border: 1px solid rgba(0,229,255,0.3); border-radius: 4px; padding: 0 4px; font-size: 8px; margin-left: 2px;">PRO</span>
          </div>
        </div>
      </div>

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
      </template>
    </v-navigation-drawer>

    <!-- ─── App Bar ─── -->
    <v-app-bar
      flat
      color="surface"
      style="border-bottom: 1px solid rgba(255,255,255,0.06);"
    >
      <!-- 用于移动端显示隐藏侧边栏 -->
      <v-app-bar-nav-icon @click="drawer = !drawer" class="d-md-none" />
      <v-app-bar-title>
        <span class="text-subtitle-1 font-weight-medium">{{ currentTitle }}</span>
      </v-app-bar-title>
      <template #append>
        <v-menu location="bottom end" transition="slide-y-transition" offset="5">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              variant="text"
              height="48"
              class="px-2 mr-2 text-none"
              rounded="lg"
            >
              <v-avatar size="32" color="primary" variant="tonal" class="mr-2">
                <v-icon size="20">mdi-shield-account</v-icon>
              </v-avatar>
              <div class="d-none d-sm-flex flex-column align-start mr-2">
                <span class="text-body-2 font-weight-medium" style="line-height: 1.2;">{{ auth.user?.username ?? 'admin' }}</span>
                <span class="text-caption text-grey-darken-1" style="font-size: 10px; line-height: 1.2;">超级管理员</span>
              </div>
              <v-icon size="18" color="grey">mdi-chevron-down</v-icon>
            </v-btn>
          </template>
          
          <v-list density="compact" min-width="220" rounded="lg" elevation="8" class="py-2">
            <v-list-item class="mb-1">
              <template #prepend>
                 <v-avatar size="40" color="primary" variant="tonal" class="mr-3">
                   <v-icon>mdi-shield-account</v-icon>
                 </v-avatar>
              </template>
              <v-list-item-title class="font-weight-bold">{{ auth.user?.username ?? 'admin' }}</v-list-item-title>
              <v-list-item-subtitle class="text-caption" style="opacity: 0.7;">玄枢安全系统指挥官</v-list-item-subtitle>
            </v-list-item>
            
            <v-divider class="my-2" opacity="0.1" />
            
            <v-list-item prepend-icon="mdi-account-cog-outline" title="个人设置" to="/settings" rounded="md" class="mx-2 mb-1" />
            <v-list-item prepend-icon="mdi-history" title="最近登录" rounded="md" class="mx-2 mb-1" />
            
            <v-divider class="my-2" opacity="0.1" />
            
            <v-list-item prepend-icon="mdi-logout" title="退出系统" color="error" class="text-error mx-2" rounded="md" @click="handleLogout" />
          </v-list>
        </v-menu>
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
