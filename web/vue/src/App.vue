<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { watch } from 'vue'

const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()

// Guard: redirect to login if not authenticated
watch(() => auth.isLoggedIn, (v) => {
  if (!v) router.replace('/login')
}, { immediate: true })
</script>

<template>
  <router-view />
</template>
