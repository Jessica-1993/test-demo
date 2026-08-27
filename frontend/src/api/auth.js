import api from '@/utils/api'

export function login(payload) {
  return api.post('/auth/login/', payload)
}

export function logout() {
  return api.post('/auth/logout/')
}

export function getCurrentUser() {
  return api.get('/auth/me/')
}
