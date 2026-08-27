<template>
  <section class="config-page">
    <div class="page-header">
      <div>
        <p class="eyebrow">Configuration</p>
        <h1>大模型配置</h1>
      </div>
      <el-button type="primary" :icon="Connection" @click="openModelDialog()">新增模型</el-button>
    </div>

    <div class="content-panel">
      <div class="toolbar models-toolbar">
        <el-input v-model="modelFilters.search" clearable placeholder="搜索配置名、模型名或 Base URL" :prefix-icon="Search" @keyup.enter="resetModelPage" @clear="resetModelPage" />
        <el-select v-model="modelFilters.provider" clearable placeholder="供应商" @change="resetModelPage">
          <el-option v-for="item in providerOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="modelFilters.usage" clearable placeholder="用途" @change="resetModelPage">
          <el-option v-for="item in usageOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button :icon="Refresh" @click="fetchModels">刷新</el-button>
      </div>

      <el-table v-loading="modelLoading" :data="models" class="dense-table">
        <el-table-column prop="name" label="配置名称" min-width="170" show-overflow-tooltip />
        <el-table-column label="供应商" width="110">
          <template #default="{ row }">{{ labelOf(providerOptions, row.provider) }}</template>
        </el-table-column>
        <el-table-column label="用途" width="130">
          <template #default="{ row }">{{ labelOf(usageOptions, row.usage) }}</template>
        </el-table-column>
        <el-table-column prop="model_name" label="模型名" min-width="170">
          <template #default="{ row }"><span class="mono-code">{{ row.model_name }}</span></template>
        </el-table-column>
        <el-table-column prop="base_url" label="Base URL" min-width="220" show-overflow-tooltip />
        <el-table-column label="API Key" width="150">
          <template #default="{ row }">{{ row.api_key_masked || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="95">
          <template #default="{ row }">
            <span class="status-pill" :class="row.is_active ? 'is-success' : 'is-muted'">{{ row.is_active ? '启用' : '停用' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="默认" width="90">
          <template #default="{ row }">
            <span v-if="row.is_default" class="text-badge is-default">默认</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="参数" width="150">
          <template #default="{ row }">{{ row.max_tokens }} / {{ row.temperature }} / {{ row.top_p }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-cell">
              <el-button text type="primary" :icon="Edit" @click="openModelDialog(row)">编辑</el-button>
              <el-button text type="success" :disabled="row.is_default || !row.is_active" @click="makeModelDefault(row)">设默认</el-button>
              <el-button text :icon="Connection" :loading="testingId === row.id" @click="runConnectionTest(row)">测试</el-button>
              <el-button text type="danger" :icon="Delete" @click="removeModel(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="modelPagination.page"
          v-model:page-size="modelPagination.pageSize"
          :page-sizes="[10, 20, 50]"
          :total="modelPagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleModelSizeChange"
          @current-change="fetchModels"
        />
      </div>
    </div>

    <el-dialog v-model="modelDialogVisible" :title="modelForm.id ? '编辑大模型' : '新增大模型'" width="680px">
      <el-form ref="modelFormRef" :model="modelForm" :rules="modelRules" label-width="112px">
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12">
            <el-form-item label="配置名称" prop="name">
              <el-input v-model="modelForm.name" placeholder="例如：DeepSeek 用例生成" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="用途" prop="usage">
              <el-select v-model="modelForm.usage" @change="handleUsageChange">
                <el-option v-for="item in usageOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12">
            <el-form-item label="协议" prop="protocol">
              <el-select v-model="modelForm.protocol" @change="handleProtocolChange">
                <el-option v-for="item in availableProtocolOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="供应商" prop="provider">
              <el-select v-model="modelForm.provider" @change="handleProviderChange">
                <el-option v-for="item in availableProviderOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="Base URL" prop="base_url">
          <el-input v-model="modelForm.base_url" placeholder="供应商 API 根地址" />
        </el-form-item>
        <el-form-item label="API Key" prop="api_key">
          <el-input v-model="modelForm.api_key" type="password" show-password :placeholder="modelForm.id ? '不填写则保留原 API Key' : '请输入 API Key'" />
        </el-form-item>
        <el-form-item label="模型名称" prop="model_name">
          <div class="model-picker">
            <el-select v-model="modelForm.model_name" filterable allow-create default-first-option placeholder="请先获取模型列表，或手动输入模型名">
              <el-option v-for="model in remoteModels" :key="model" :label="model" :value="model" />
            </el-select>
            <el-button :icon="Refresh" :loading="fetchingRemoteModels" @click="fetchModelNames">获取模型</el-button>
          </div>
        </el-form-item>
        <el-form-item v-if="modelForm.usage === 'embedding'" label="向量维度" prop="embedding_dimension">
          <el-select v-model="modelForm.embedding_dimension"><el-option label="768（OpenSearch 当前索引）" :value="768" /><el-option label="1536" :value="1536" /><el-option label="3072" :value="3072" /></el-select>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :xs="24" :sm="8">
            <el-form-item label="最大 Token" prop="max_tokens">
              <el-input-number v-model="modelForm.max_tokens" :min="1" :max="200000" controls-position="right" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="8">
            <el-form-item label="温度" prop="temperature">
              <el-input-number v-model="modelForm.temperature" :min="0" :max="2" :step="0.1" controls-position="right" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="8">
            <el-form-item label="采样概率" prop="top_p">
              <el-input-number v-model="modelForm.top_p" :min="0" :max="1" :step="0.1" controls-position="right" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="启用状态">
          <el-switch v-model="modelForm.is_active" />
        </el-form-item>
        <el-form-item label="默认模型">
          <el-switch v-model="modelForm.is_default" :disabled="!modelForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="modelDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingModel" @click="saveModel">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Connection, Delete, Edit, Refresh, Search } from '@element-plus/icons-vue'

import {
  createLLMModel,
  deleteLLMModel,
  fetchRemoteModels,
  getLLMModels,
  getProviderDefaults,
  setDefaultLLMModel,
  testLLMConnection,
  updateLLMModel,
} from '@/api/configuration'
import { cleanParams, labelOf, normalizeListResponse, protocolOptions, providerOptions, usageOptions } from './configurationHelpers'

const models = ref([])
const modelLoading = ref(false)
const savingModel = ref(false)
const testingId = ref(null)
const fetchingRemoteModels = ref(false)
const modelDialogVisible = ref(false)
const modelFormRef = ref()
const providerDefaults = ref({})
const remoteModels = ref([])
const modelFilters = reactive({
  search: '',
  provider: '',
  usage: '',
})
const modelPagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
})
const modelForm = reactive(emptyModelForm())

const availableProtocolOptions = computed(() => {
  const allowed = providerDefaults.value.usage_protocols?.[modelForm.usage] || []
  return protocolOptions.filter(item => allowed.includes(item.value))
})

const availableProviderOptions = computed(() => {
  const allowed = providerDefaults.value.protocol_providers?.[modelForm.protocol] || []
  return providerOptions.filter(item => allowed.includes(item.value))
})

const modelRules = {
  name: [{ required: true, message: '请输入配置名称', trigger: 'blur' }],
  provider: [{ required: true, message: '请选择供应商', trigger: 'change' }],
  protocol: [{ required: true, message: '请选择协议', trigger: 'change' }],
  usage: [{ required: true, message: '请选择用途', trigger: 'change' }],
  model_name: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
  base_url: [{ required: true, message: '请输入 Base URL', trigger: 'blur' }],
  api_key: [
    {
      validator: (_rule, value, callback) => {
        if (!modelForm.id && !value) {
          callback(new Error('请输入 API Key'))
          return
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
}

function emptyModelForm() {
  return {
    id: null,
    name: '',
    provider: 'chatgpt',
    protocol: 'openai_compatible',
    usage: 'general_chat',
    model_name: '',
    base_url: 'https://api.openai.com',
    api_key: '',
    max_tokens: 4096,
    temperature: 0.7,
    top_p: 1,
    embedding_dimension: 768,
    is_active: true,
    is_default: false,
  }
}

function resetReactive(target, source) {
  Object.keys(target).forEach(key => delete target[key])
  Object.assign(target, source)
}

async function fetchProviderDefaults() {
  const response = await getProviderDefaults()
  providerDefaults.value = response.data
}

async function fetchModels() {
  modelLoading.value = true
  try {
    const response = await getLLMModels(cleanParams({
      ...modelFilters,
      page: modelPagination.page,
      page_size: modelPagination.pageSize,
    }))
    const payload = normalizeListResponse(response.data)
    models.value = payload.results
    modelPagination.total = payload.total
  } finally {
    modelLoading.value = false
  }
}

async function resetModelPage() {
  modelPagination.page = 1
  await fetchModels()
}

async function handleModelSizeChange() {
  modelPagination.page = 1
  await fetchModels()
}

function openModelDialog(row = null) {
  resetReactive(modelForm, row ? { ...emptyModelForm(), ...row, api_key: '' } : emptyModelForm())
  remoteModels.value = row?.model_name ? [row.model_name] : []
  modelDialogVisible.value = true
}

function handleProtocolChange(protocol) {
  const allowed = providerDefaults.value.protocol_providers?.[protocol] || []
  if (!allowed.includes(modelForm.provider)) {
    modelForm.provider = allowed[0] || ''
  }
  const defaults = providerDefaults.value.providers?.[modelForm.provider]
  if (defaults) {
    modelForm.base_url = defaults.base_url
  }
  modelForm.model_name = ''
  remoteModels.value = []
}

function handleProviderChange(provider) {
  const defaults = providerDefaults.value.providers?.[provider]
  if (!defaults) return
  modelForm.base_url = defaults.base_url
  modelForm.model_name = ''
  remoteModels.value = []
}

function handleUsageChange() {
  const allowedProtocols = providerDefaults.value.usage_protocols?.[modelForm.usage] || []
  if (!allowedProtocols.includes(modelForm.protocol)) {
    modelForm.protocol = allowedProtocols[0] || ''
  }
  const allowedProviders = providerDefaults.value.protocol_providers?.[modelForm.protocol] || []
  if (!allowedProviders.includes(modelForm.provider)) {
    modelForm.provider = allowedProviders[0] || ''
  }
  const defaults = providerDefaults.value.providers?.[modelForm.provider]
  if (defaults) modelForm.base_url = defaults.base_url
  modelForm.model_name = ''
  if (modelForm.usage === 'embedding') {
    modelForm.base_url = 'https://generativelanguage.googleapis.com/v1beta'
    modelForm.model_name = 'gemini-embedding-2'
    modelForm.embedding_dimension = 768
  } else if (modelForm.usage === 'vision_analyzer' && modelForm.protocol === 'openai_responses') {
    modelForm.model_name = 'gpt-5-mini'
    modelForm.temperature = 0.1
  }
  remoteModels.value = []
}

async function fetchModelNames() {
  if (!modelForm.api_key) {
    ElMessage.warning('请先填写 API Key')
    return
  }
  if (!modelForm.base_url || !modelForm.provider || !modelForm.protocol) {
    ElMessage.warning('请先选择协议、供应商并填写 Base URL')
    return
  }
  fetchingRemoteModels.value = true
  try {
    const response = await fetchRemoteModels({
      protocol: modelForm.protocol,
      provider: modelForm.provider,
      base_url: modelForm.base_url,
      api_key: modelForm.api_key,
      usage: modelForm.usage,
    })
    remoteModels.value = response.data.models || []
    if (remoteModels.value.length === 1) {
      modelForm.model_name = remoteModels.value[0]
    }
    ElMessage.success(response.data.message || '模型列表已获取')
  } catch (_error) {
    // API 错误由统一错误中心展示。
  } finally {
    fetchingRemoteModels.value = false
  }
}

async function saveModel() {
  await modelFormRef.value.validate()
  savingModel.value = true
  try {
    const payload = { ...modelForm }
    if (!payload.api_key) {
      delete payload.api_key
    }
    if (!payload.is_active) {
      payload.is_default = false
    }
    if (payload.id) {
      await updateLLMModel(payload.id, payload)
    } else {
      await createLLMModel(payload)
    }
    ElMessage.success('大模型配置已保存')
    modelDialogVisible.value = false
    await fetchModels()
  } finally {
    savingModel.value = false
  }
}

async function makeModelDefault(row) {
  await setDefaultLLMModel(row.id)
  ElMessage.success('默认模型已更新')
  await fetchModels()
}

async function removeModel(row) {
  await ElMessageBox.confirm(`确认删除模型配置「${row.name}」？`, '删除模型配置', { type: 'warning' })
  await deleteLLMModel(row.id)
  ElMessage.success('模型配置已删除')
  await fetchModels()
}

async function runConnectionTest(row) {
  testingId.value = row.id
  try {
    const response = await testLLMConnection(row.id)
    ElMessage.success(response.data.message || '连接测试成功')
  } catch (_error) {
    // API 错误由统一错误中心展示。
  } finally {
    testingId.value = null
  }
}

onMounted(async () => {
  await Promise.all([fetchProviderDefaults(), fetchModels()])
})
</script>

<style scoped>
.config-page {
  width: min(1440px, 100%);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.eyebrow,
h1 {
  margin: 0;
}

.eyebrow {
  margin-bottom: 6px;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
}

h1 {
  color: #172033;
  font-size: 24px;
  font-weight: 650;
  line-height: 1.25;
}

.content-panel {
  border: 1px solid #e6ebf2;
  border-radius: 8px;
  background: #ffffff;
}

.toolbar {
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid #edf1f6;
}

.models-toolbar {
  grid-template-columns: minmax(240px, 1fr) 160px 160px auto;
}

.model-picker {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  width: 100%;
}

:deep(.el-select),
:deep(.el-input-number) {
  width: 100%;
}

.dense-table {
  --el-table-border-color: #edf1f6;
  --el-table-header-bg-color: #fbfcfe;
  --el-table-header-text-color: #6b7280;
  --el-table-row-hover-bg-color: #f8fbff;
  font-size: 14px;
}

.dense-table :deep(.el-table__header th) {
  height: 42px;
  padding: 0;
  font-weight: 650;
}

.dense-table :deep(.el-table__cell) {
  padding: 8px 0;
}

.mono-code {
  color: #374151;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 13px;
}

.status-pill,
.text-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
}

.status-pill.is-success { color: #047857; background: #ecfdf5; border: 1px solid #bbf7d0; }
.status-pill.is-muted { color: #64748b; background: #f8fafc; border: 1px solid #e2e8f0; }
.text-badge.is-default { color: #92400e; background: #fffbeb; border: 1px solid #fde68a; }
.action-cell { display: inline-flex; align-items: center; justify-content: center; gap: 4px; white-space: nowrap; }
.action-cell :deep(.el-button) { width: 28px; height: 28px; margin-left: 0; padding: 0; border-radius: 6px; font-weight: 600; }
.action-cell :deep(.el-button span) { display: none; }
.action-cell :deep(.el-icon + span) { margin-left: 0; }

.pagination-bar {
  display: flex;
  justify-content: flex-end;
  padding: 12px 14px;
  border-top: 1px solid #edf1f6;
}

@media (max-width: 900px) {
  .toolbar,
  .models-toolbar,
  .model-picker {
    grid-template-columns: 1fr;
  }

  .page-header {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
