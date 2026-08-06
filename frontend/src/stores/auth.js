import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authAPI } from '../api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.is_admin || false)
  const username = computed(() => user.value?.username || '')

  async function login(username, password) {
    const res = await authAPI.login({ username, password })
    token.value = res.data.access_token
    user.value = {
      username: res.data.username,
      is_admin: res.data.is_admin,
    }
    localStorage.setItem('token', token.value)
    localStorage.setItem('user', JSON.stringify(user.value))
  }

  async function register(username, password, email = '') {
    const res = await authAPI.register({ username, password, email })
    token.value = res.data.access_token
    user.value = {
      username: res.data.username,
      is_admin: res.data.is_admin,
    }
    localStorage.setItem('token', token.value)
    localStorage.setItem('user', JSON.stringify(user.value))
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return { token, user, isLoggedIn, isAdmin, username, login, register, logout }
})
