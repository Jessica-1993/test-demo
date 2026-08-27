import api from '@/utils/api'

export function getProjects(params = {}) {
  return api.get('/configuration/projects/', { params })
}

export function getProject(id) {
  return api.get(`/configuration/projects/${id}/`)
}

export function createProject(payload) {
  return api.post('/configuration/projects/', payload)
}

export function updateProject(id, payload) {
  return api.patch(`/configuration/projects/${id}/`, payload)
}

export function confirmProject(id) {
  return api.post(`/configuration/projects/${id}/confirm/`)
}

export function deleteProject(id) {
  return api.delete(`/configuration/projects/${id}/`)
}

export function setDefaultProject(id) {
  return api.post(`/configuration/projects/${id}/set_default/`)
}

export function getLLMModels(params = {}) {
  return api.get('/configuration/llm-models/', { params })
}

export function createLLMModel(payload) {
  return api.post('/configuration/llm-models/', payload)
}

export function updateLLMModel(id, payload) {
  return api.patch(`/configuration/llm-models/${id}/`, payload)
}

export function deleteLLMModel(id) {
  return api.delete(`/configuration/llm-models/${id}/`)
}

export function setDefaultLLMModel(id) {
  return api.post(`/configuration/llm-models/${id}/set_default/`)
}

export function testLLMConnection(id) {
  return api.post(`/configuration/llm-models/${id}/test_connection/`)
}

export function getProviderDefaults() {
  return api.get('/configuration/llm-models/provider-defaults/')
}

export function fetchRemoteModels(payload) {
  return api.post('/configuration/llm-models/fetch-models/', payload)
}

export function getPrompts(params = {}) {
  return api.get('/configuration/prompts/', { params })
}

export function getDefaultPrompt(roleType) {
  return api.get('/configuration/prompts/default-prompt/', { params: { role_type: roleType } })
}

export function createPrompt(payload) {
  return api.post('/configuration/prompts/', payload)
}

export function updatePrompt(id, payload) {
  return api.patch(`/configuration/prompts/${id}/`, payload)
}

export function deletePrompt(id) {
  return api.delete(`/configuration/prompts/${id}/`)
}
