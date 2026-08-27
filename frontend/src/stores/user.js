import { defineStore } from 'pinia'

import { getCurrentUser, login as loginApi, logout as logoutApi } from '@/api/auth'

const ACCESS_TOKEN_KEY = 'testhub_demo_access_token'
const REFRESH_TOKEN_KEY = 'testhub_demo_refresh_token'
const USER_KEY = 'testhub_demo_user'

function readJson(key) {
  try {
    const value = localStorage.getItem(key)
    return value ? JSON.parse(value) : null
  } catch {
    return null
  }
}

export const useUserStore = defineStore('user', {
  state: () => ({
    accessToken: localStorage.getItem(ACCESS_TOKEN_KEY) || '',
    refreshToken: localStorage.getItem(REFRESH_TOKEN_KEY) || '',
    user: readJson(USER_KEY),
    initialized: false,
  }),

  getters: {
    isAuthenticated: state => Boolean(state.accessToken),
    displayName: state => state.user?.display_name || state.user?.username || '未登录',
  },

  actions: {
    persistAuth(payload) {
      this.accessToken = payload.access
      this.refreshToken = payload.refresh
      this.user = payload.user

      localStorage.setItem(ACCESS_TOKEN_KEY, payload.access)
      localStorage.setItem(REFRESH_TOKEN_KEY, payload.refresh)
      localStorage.setItem(USER_KEY, JSON.stringify(payload.user))
    },

    clearAuth() {
      this.accessToken = ''
      this.refreshToken = ''
      this.user = null
      localStorage.removeItem(ACCESS_TOKEN_KEY)
      localStorage.removeItem(REFRESH_TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
    },

    async login(credentials) {
      const response = await loginApi(credentials)
      this.persistAuth(response.data)
      return response.data
    },

    async initAuth() {
      if (!this.accessToken) {
        this.initialized = true
        return
      }

      try {
        const response = await getCurrentUser()
        this.user = response.data
        localStorage.setItem(USER_KEY, JSON.stringify(response.data))
      } catch {
        this.clearAuth()
      } finally {
        this.initialized = true
      }
    },

    async logout() {
      try {
        await logoutApi()
      } finally {
        this.clearAuth()
      }
    },
  },
})
