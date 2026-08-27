import api from '@/utils/api'

export function getRequirementDocuments(params = {}) {
  return api.get('/requirements/documents/', { params })
}

export function uploadRequirementDocument(payload) {
  return api.post('/requirements/documents/upload/', payload, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function deleteRequirementDocument(id) {
  return api.delete(`/requirements/documents/${id}/`)
}

export function parseRequirementDocument(id) {
  return api.post(`/requirements/documents/${id}/parse/`)
}

export function syncRequirementDocuments(payload) {
  return api.post('/requirements/documents/sync_qiniu/', payload)
}

export function getRequirementParseRuns(id) {
  return api.get(`/requirements/documents/${id}/parse_runs/`)
}

export function getRequirementDocumentContent(id) {
  return api.get(`/requirements/documents/${id}/content/`)
}

export function getRequirementItems(params = {}) {
  return api.get('/requirements/items/', { params })
}

export function createRequirementItem(payload) {
  return api.post('/requirements/items/', payload)
}

export function updateRequirementItem(id, payload) {
  return api.patch(`/requirements/items/${id}/`, payload)
}

export function deleteRequirementItem(id) {
  return api.delete(`/requirements/items/${id}/`)
}

export function confirmRequirementItems(ids) {
  return api.post('/requirements/items/confirm/', { ids })
}

export function mergeRequirementItems(payload) {
  return api.post('/requirements/items/merge/', payload)
}

export function reorderRequirementBlocks(id, blockIds) {
  return api.post(`/requirements/items/${id}/reorder_blocks/`, { block_ids: blockIds })
}

export function integrateRequirementItem(id) {
  return api.post(`/requirements/items/${id}/integrate/`)
}

export function integrateRequirementBatch(documentId, payload) {
  return api.post(`/requirements/documents/${documentId}/integrate_batch/`, payload)
}

export function getIntegrationBatches(params = {}) {
  return api.get('/requirements/integration-batches/', { params })
}

export function getRequirementIntegration(id) {
  return api.get(`/requirements/items/${id}/integration/`, { suppressStatuses: [404] })
}

export function updateRequirementIntegration(id, payload) {
  return api.patch(`/requirements/items/${id}/integration/`, payload)
}

export function confirmRequirementRelationship(id, payload) {
  return api.post(`/requirements/items/${id}/confirm_relationship/`, payload)
}

export function reviewRequirementIntegration(id, reviewStatus) {
  return api.post(`/requirements/items/${id}/review_integration/`, { review_status: reviewStatus })
}

export function confirmFormalRequirement(id) {
  return api.post(`/requirements/items/${id}/confirm_formal/`)
}

export function resolveRequirementConflict(id, payload) {
  return api.post(`/requirements/conflicts/${id}/resolve/`, payload)
}

export function handleRequirementQuestion(id, payload) {
  return api.post(`/requirements/open-questions/${id}/handle/`, payload)
}

export function updateRequirementContentBlock(id, payload) {
  return api.patch(`/requirements/content-blocks/${id}/`, payload)
}

export function deleteRequirementContentBlock(id) {
  return api.delete(`/requirements/content-blocks/${id}/`)
}

export function getRequirementVersions(params = {}) {
  return api.get('/requirements/versions/', { params })
}

export function getRequirementRevisions(params = {}) {
  return api.get('/requirements/revisions/', { params })
}

export function getRequirementFamilies(params = {}) {
  return api.get('/requirements/families/', { params })
}

export function createRequirementVersion(payload) {
  return api.post('/requirements/versions/', payload)
}

export function bindRequirementVersionRequirements(id, revisionIds) {
  return api.post(`/requirements/versions/${id}/bind_requirements/`, { revision_ids: revisionIds })
}

export function unbindRequirementVersionRequirements(id, revisionIds) {
  return api.post(`/requirements/versions/${id}/unbind_requirements/`, { revision_ids: revisionIds })
}

export function publishRequirementVersion(id) {
  return api.post(`/requirements/versions/${id}/publish/`)
}

export function archiveRequirementVersion(id) {
  return api.post(`/requirements/versions/${id}/archive/`)
}

export function getTestCases(params = {}) {
  return api.get('/requirements/test-cases/', { params })
}

export function getTestCase(id) {
  return api.get(`/requirements/test-cases/${id}/`)
}

export function generateTestCases(payload) {
  return api.post('/requirements/generation-tasks/generate/', payload)
}

export function getGenerationTasks(params = {}) {
  return api.get('/requirements/generation-tasks/', { params })
}

export function getGenerationTask(id) {
  return api.get(`/requirements/generation-tasks/${id}/`)
}

export function retryGenerationTask(id) {
  return api.post(`/requirements/generation-tasks/${id}/retry/`)
}

export function retryIntegrationBatch(id) {
  return api.post(`/requirements/integration-batches/${id}/retry/`)
}

export function createEnhancementTask(payload) {
  return api.post('/requirements/enhancement-tasks/generate/', payload)
}

export function getEnhancementTasks(params = {}) {
  return api.get('/requirements/enhancement-tasks/', { params })
}

export function getEnhancementTask(id) {
  return api.get(`/requirements/enhancement-tasks/${id}/`)
}

export function retryEnhancementTask(id) {
  return api.post(`/requirements/enhancement-tasks/${id}/retry/`)
}

export function getEnhancementSuggestions(params = {}) {
  return api.get('/requirements/enhancement-suggestions/', { params })
}

export function acceptEnhancementSuggestion(id, note = '') {
  return api.post(`/requirements/enhancement-suggestions/${id}/accept/`, { note })
}

export function rejectEnhancementSuggestion(id, note = '') {
  return api.post(`/requirements/enhancement-suggestions/${id}/reject/`, { note })
}

export function batchDecideEnhancementSuggestions(payload) {
  return api.post('/requirements/enhancement-suggestions/batch-decide/', payload)
}
