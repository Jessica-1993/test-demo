import api from '@/utils/api'

export const getDefects = (params = {}) => api.get('/defects/', { params })
export const createDefect = payload => api.post('/defects/', payload)
export const updateDefect = (id, payload) => api.patch(`/defects/${id}/`, payload)
export const deleteDefect = id => api.delete(`/defects/${id}/`)
export const confirmDefects = ids => api.post('/defects/confirm/', { ids })
export const invalidateDefect = id => api.post(`/defects/${id}/invalidate/`)
export const importDefects = payload => api.post('/defects/import/', payload, {
  headers: { 'Content-Type': 'multipart/form-data' },
})
export const getDefectImportBatches = (params = {}) => api.get('/defects/import-batches/', { params })
