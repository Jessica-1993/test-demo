import { reactive } from 'vue'
import { ElMessage } from 'element-plus'

const fallbackCatalog = {
  VALIDATION_ERROR: ['提交内容有误', '部分字段缺失或格式不符合要求', '请根据字段提示修改后重新提交'],
  AUTH_REQUIRED: ['登录状态已失效', '当前登录凭证不存在或已过期', '请重新登录后继续操作'],
  NETWORK_ERROR: ['网络连接失败', '浏览器无法连接后端服务', '请检查网络和后端服务后重试'],
  MODEL_TIMEOUT: ['模型调用超时', '模型服务未在限定时间内返回结果', '请稍后重新发起任务'],
  INTERNAL_ERROR: ['系统内部异常', '系统执行过程中发生了未预期错误', '请记录错误编号并联系管理员处理'],
}

export const errorState = reactive({
  visible: false,
  current: null,
  actionHandler: null,
})

function firstMessage(value) {
  if (Array.isArray(value)) return value.map(firstMessage).filter(Boolean).join('；')
  if (value && typeof value === 'object') return Object.values(value).map(firstMessage).filter(Boolean).join('；')
  return value ? String(value) : ''
}

function localError(code, message, fieldErrors = {}) {
  const fallback = fallbackCatalog[code] || fallbackCatalog.INTERNAL_ERROR
  return {
    code,
    message: message || fallback[0],
    reason: fallback[1],
    solution: fallback[2],
    retryable: code === 'NETWORK_ERROR' || code === 'MODEL_TIMEOUT',
    action: null,
    trace_id: '',
    details: {},
    field_errors: fieldErrors,
  }
}

export function normalizeApiError(error, fallback = '操作失败') {
  if (error?.errorInfo?.code) return { ...error.errorInfo, field_errors: error.errorInfo.field_errors || {} }
  if (error?.code && error?.message && error?.reason) return { ...error, field_errors: error.field_errors || {} }

  const data = error?.response?.data
  if (data?.error?.code) {
    const fieldErrors = data.field_errors || {}
    const fieldMessage = firstMessage(fieldErrors)
    return {
      ...data.error,
      message: data.error.code === 'VALIDATION_ERROR' && fieldMessage ? fieldMessage : data.error.message,
      field_errors: fieldErrors,
    }
  }
  if (!error?.response) {
    const isTimeout = error?.code === 'ECONNABORTED' || /timeout/i.test(error?.message || '')
    return localError(isTimeout ? 'MODEL_TIMEOUT' : 'NETWORK_ERROR', '')
  }
  const fieldErrors = data && typeof data === 'object'
    ? Object.fromEntries(Object.entries(data).filter(([key]) => !['detail', 'message', 'error'].includes(key)))
    : {}
  const message = data?.detail || data?.message || firstMessage(fieldErrors) || (typeof data === 'string' ? data : fallback)
  const status = error.response.status
  const code = status === 401 ? 'AUTH_REQUIRED'
    : status === 400 ? 'VALIDATION_ERROR'
      : status >= 500 ? 'INTERNAL_ERROR' : 'VALIDATION_ERROR'
  return localError(code, firstMessage(message) || fallback, fieldErrors)
}

export function showErrorInfo(errorInfo, options = {}) {
  const normalized = normalizeApiError(errorInfo, options.fallback)
  if (normalized.code === 'VALIDATION_ERROR' && !options.forceDialog) {
    ElMessage.error(normalized.message)
    return normalized
  }
  errorState.current = normalized
  errorState.actionHandler = options.actionHandler || null
  errorState.visible = true
  return normalized
}

export function presentApiError(error, options = {}) {
  const normalized = showErrorInfo(normalizeApiError(error, options.fallback), options)
  error.errorInfo = normalized
  return normalized
}

export function closeErrorDialog() {
  errorState.visible = false
  errorState.actionHandler = null
}
