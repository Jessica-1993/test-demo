import axios from 'axios'
import { presentApiError } from '@/utils/errors'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('testhub_demo_access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  response => response,
  error => {
    const suppressStatuses = error.config?.suppressStatuses || []
    const suppressed = error.config?.suppressError || suppressStatuses.includes(error.response?.status)
    if (error.response?.status === 401) {
      localStorage.removeItem('testhub_demo_access_token')
      localStorage.removeItem('testhub_demo_refresh_token')
      localStorage.removeItem('testhub_demo_user')

      if (window.location.pathname !== '/login') {
        const redirect = encodeURIComponent(window.location.pathname + window.location.search)
        window.location.href = `/login?redirect=${redirect}`
      }
    }
    if (!suppressed && error.response?.status !== 401) {
      const canReplay = ['get', 'head'].includes((error.config?.method || '').toLowerCase())
      presentApiError(error, {
        actionHandler: canReplay && error.response?.data?.error?.retryable
          ? () => api.request(error.config)
          : null,
      })
    }
    return Promise.reject(error)
  },
)

export default api
