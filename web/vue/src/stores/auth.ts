import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../api/index'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<{ username: string; role: string } | null>(
    JSON.parse(localStorage.getItem('user') || 'null')
  )

  const isLoggedIn = computed(() => !!token.value)

  async function login(username: string, password: string) {
    const data = await api.post<{ access_token: string; user: { username: string; role: string } }>(
      '/api/v1/auth/login',
      { username, password },
      false
    )
    token.value = data.access_token
    user.value = data.user
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user', JSON.stringify(data.user))
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return { token, user, isLoggedIn, login, logout }
})
