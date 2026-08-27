export const providerOptions = [
  { label: 'ChatGPT', value: 'chatgpt' },
  { label: 'DeepSeek', value: 'deepseek' },
  { label: 'Gemini', value: 'gemini' },
  { label: '千问', value: 'qwen' },
]

export const usageOptions = [
  { label: '通用对话', value: 'general_chat' },
  { label: '需求整合', value: 'requirement_integrator' },
  { label: '用例生成', value: 'testcase_writer' },
  { label: '用例增强', value: 'testcase_enhancer' },
  { label: '用例评审', value: 'testcase_reviewer' },
  { label: '图片理解', value: 'vision_analyzer' },
  { label: '文本向量', value: 'embedding' },
  { label: '自动化 Agent', value: 'automation_agent' },
]

export const protocolOptions = [
  { label: 'OpenAI Compatible', value: 'openai_compatible' },
  { label: 'OpenAI Responses', value: 'openai_responses' },
  { label: 'Gemini', value: 'gemini' },
]

export const roleTypeOptions = [
  { label: '通用对话助手', value: 'general_chat' },
  { label: '需求整合专家', value: 'requirement_integrator' },
  { label: '测试用例生成专家', value: 'testcase_writer' },
  { label: '测试用例增强专家', value: 'testcase_enhancer' },
  { label: '测试用例评审专家', value: 'testcase_reviewer' },
  { label: '图片理解专家', value: 'vision_analyzer' },
  { label: '文本向量角色', value: 'embedding' },
  { label: '自动化执行 Agent', value: 'automation_agent' },
]

export function cleanParams(params) {
  return Object.fromEntries(Object.entries(params).filter(([, value]) => value !== '' && value !== null && value !== undefined))
}

export function normalizeListResponse(data) {
  if (Array.isArray(data)) {
    return { results: data, total: data.length }
  }
  return { results: data.results || [], total: data.count || 0 }
}

export function formatDate(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

export function labelOf(options, value) {
  return options.find(item => item.value === value)?.label || value
}
