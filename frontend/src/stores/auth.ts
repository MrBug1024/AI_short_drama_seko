// src/stores/auth.ts
// 用户认证 Pinia store：持有 token 与 user 信息，持久化到 localStorage。
// 使用方式：
//   import { useAuthStore } from '@/stores/auth'
//   const auth = useAuthStore()
//   auth.user   // {id, email, display_name, role, status}
//   auth.isLoggedIn
//   auth.login(email, password)  /  auth.register(email, password, display_name)
//   auth.logout()
//   auth.fetchMe()  // 用 token 拉取最新 user 信息

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api'

const TOKEN_KEY = 'lbp_m_token'

export interface UserInfo {
  id: number
  email: string
  display_name: string
  role: 'user' | 'admin'
  status: 'active' | 'disabled'
  created_at?: string
}

export const useAuthStore = defineStore('auth', () => {
  // token：启动时尝试从 localStorage 恢复
  const token = ref<string>(localStorage.getItem(TOKEN_KEY) || '')

  // user：登录态下保存当前用户
  const user = ref<UserInfo | null>(null)

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  function setToken(t: string) {
    token.value = t
    if (t) {
      localStorage.setItem(TOKEN_KEY, t)
    } else {
      localStorage.removeItem(TOKEN_KEY)
    }
  }

  async function login(email: string, password: string) {
    const data = await authApi.login({ email, password })
    setToken(data.access_token)
    user.value = data.user
    return data.user
  }

  async function register(email: string, password: string, display_name: string) {
    const data = await authApi.register({ email, password, display_name })
    setToken(data.access_token)
    user.value = data.user
    return data.user
  }

  function logout() {
    setToken('')
    user.value = null
  }

  async function fetchMe() {
    if (!token.value) return null
    try {
      const u = await authApi.me()
      user.value = u
      return u
    } catch (e) {
      // token 失效（401 等）：清空
      logout()
      return null
    }
  }

  // 应用启动时：如果有 token 但 user 为空，异步拉一次
  if (token.value && !user.value) {
    // 不 await，fire-and-forget；Layout 会通过 user 显示
    fetchMe().catch(() => {})
  }

  return {
    token,
    user,
    isLoggedIn,
    isAdmin,
    login,
    register,
    logout,
    fetchMe,
    setToken,
  }
})