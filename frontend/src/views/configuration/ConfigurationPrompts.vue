<template>
  <section class="config-page">
    <div class="page-header">
      <div>
        <p class="eyebrow">Configuration</p>
        <h1>系统角色配置</h1>
      </div>
      <div class="header-actions">
        <el-button :icon="Refresh" @click="fetchRoles">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openRoleDialog()">新增角色</el-button>
      </div>
    </div>

    <div class="content-panel">
      <div class="toolbar roles-toolbar">
        <el-input v-model="roleFilters.search" clearable placeholder="搜索角色名称、提示词或模型" :prefix-icon="Search" @keyup.enter="resetRolePage" @clear="resetRolePage" />
        <el-select v-model="roleFilters.role_type" clearable placeholder="角色类型" @change="resetRolePage">
          <el-option v-for="item in roleTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="roleFilters.is_active" clearable placeholder="状态" @change="resetRolePage">
          <el-option label="启用" :value="true" />
          <el-option label="停用" :value="false" />
        </el-select>
      </div>

      <el-table v-loading="roleLoading" :data="roles" class="dense-table">
        <el-table-column prop="name" label="角色名称" min-width="190" show-overflow-tooltip />
        <el-table-column label="角色类型" width="170">
          <template #default="{ row }">{{ labelOf(roleTypeOptions, row.role_type) }}</template>
        </el-table-column>
        <el-table-column label="绑定模型（配置名称 / 模型名称）" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">{{ formatBoundModel(row) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="95">
          <template #default="{ row }">
            <span class="status-pill" :class="row.is_active ? 'is-success' : 'is-muted'">{{ row.is_active ? '启用' : '停用' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="提示词摘要" min-width="320" show-overflow-tooltip>
          <template #default="{ row }">{{ summarizePrompt(row.prompt_content) }}</template>
        </el-table-column>
        <el-table-column label="更新时间" width="180">
          <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="92" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-cell">
              <el-button text type="primary" :icon="Edit" @click="openRoleDialog(row)">编辑</el-button>
              <el-button text type="danger" :icon="Delete" @click="removeRole(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="rolePagination.page"
          v-model:page-size="rolePagination.pageSize"
          :page-sizes="[10, 20, 50]"
          :total="rolePagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleRoleSizeChange"
          @current-change="fetchRoles"
        />
      </div>
    </div>

    <el-dialog v-model="roleDialogVisible" :title="roleForm.id ? '编辑系统角色' : '新增系统角色'" width="860px">
      <el-form ref="roleFormRef" :model="roleForm" :rules="roleRules" label-width="112px">
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12">
            <el-form-item label="角色名称" prop="name">
              <el-input v-model="roleForm.name" placeholder="例如：高覆盖率用例生成专家" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="角色类型" prop="role_type">
              <el-select v-model="roleForm.role_type" @change="handleRoleTypeChange">
                <el-option v-for="item in roleTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="绑定模型" prop="llm_model">
          <el-select v-model="roleForm.llm_model" filterable clearable placeholder="请选择：配置名称 / 模型名称">
            <el-option
              v-for="model in models"
              :key="model.id"
              :label="formatModelOption(model)"
              :value="model.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="启用状态">
          <el-switch v-model="roleForm.is_active" />
        </el-form-item>
        <el-form-item v-if="roleForm.role_type !== 'embedding'" label="提示词内容" prop="prompt_content">
          <div class="prompt-editor">
            <div class="prompt-tools">
              <span>可编辑角色提示词，也可使用系统内置模板。</span>
              <el-button size="small" :loading="loadingDefaultPrompt" @click="fillDefaultPrompt">填充默认提示词</el-button>
            </div>
            <el-input v-model="roleForm.prompt_content" type="textarea" :rows="18" resize="vertical" placeholder="请输入系统角色提示词" />
          </div>
        </el-form-item>
        <el-alert v-else title="文本向量角色只负责绑定向量模型，运行时不会发送系统提示词。" type="info" :closable="false" show-icon />
      </el-form>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingRole" @click="saveRole">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit, Plus, Refresh, Search } from '@element-plus/icons-vue'

import { createPrompt, deletePrompt, getDefaultPrompt, getLLMModels, getPrompts, updatePrompt } from '@/api/configuration'
import { cleanParams, formatDate, labelOf, normalizeListResponse, roleTypeOptions } from './configurationHelpers'

const roles = ref([])
const models = ref([])
const roleLoading = ref(false)
const savingRole = ref(false)
const loadingDefaultPrompt = ref(false)
const roleDialogVisible = ref(false)
const roleFormRef = ref()
const roleFilters = reactive({
  search: '',
  role_type: '',
  is_active: '',
})
const rolePagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
})
const roleForm = reactive(emptyRoleForm())

const roleRules = {
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }],
  role_type: [{ required: true, message: '请选择角色类型', trigger: 'change' }],
  llm_model: [{ validator: (_rule, value, callback) => roleForm.is_active && !value ? callback(new Error('启用角色必须绑定模型')) : callback(), trigger: 'change' }],
  prompt_content: [{ validator: (_rule, value, callback) => roleForm.role_type !== 'embedding' && !value?.trim() ? callback(new Error('请输入提示词内容')) : callback(), trigger: 'blur' }],
}

function emptyRoleForm() {
  return {
    id: null,
    name: '',
    role_type: '',
    prompt_content: '',
    llm_model: null,
    is_active: true,
  }
}

function resetReactive(target, source) {
  Object.keys(target).forEach(key => delete target[key])
  Object.assign(target, source)
}

function summarizePrompt(content) {
  if (!content) return '-'
  const normalized = content.replace(/\s+/g, ' ').trim()
  return normalized.length > 120 ? `${normalized.slice(0, 120)}...` : normalized
}

function formatModelOption(model) {
  return `${model.name} / ${model.model_name}`
}

function formatBoundModel(role) {
  return role.llm_model_display || '-'
}

async function fetchRoles() {
  roleLoading.value = true
  try {
    const response = await getPrompts(cleanParams({
      ...roleFilters,
      page: rolePagination.page,
      page_size: rolePagination.pageSize,
    }))
    const payload = normalizeListResponse(response.data)
    roles.value = payload.results
    rolePagination.total = payload.total
  } finally {
    roleLoading.value = false
  }
}

async function fetchModels(roleType) {
  if (!roleType) {
    models.value = []
    return
  }
  const response = await getLLMModels({ usage: roleType, is_active: true, page_size: 100 })
  models.value = normalizeListResponse(response.data).results
}

function resetRolePage() {
  rolePagination.page = 1
  fetchRoles()
}

function handleRoleSizeChange(size) {
  rolePagination.pageSize = size
  resetRolePage()
}

async function openRoleDialog(row) {
  resetReactive(roleForm, row ? {
    id: row.id,
    name: row.name,
    role_type: row.role_type,
    prompt_content: row.prompt_content,
    llm_model: row.llm_model,
    is_active: row.is_active,
  } : emptyRoleForm())
  await fetchModels(roleForm.role_type)
  roleDialogVisible.value = true
}

async function handleRoleTypeChange(roleType) {
  roleForm.llm_model = null
  if (roleType === 'embedding') roleForm.prompt_content = ''
  await fetchModels(roleType)
}

async function fillDefaultPrompt() {
  if (!roleForm.role_type) {
    ElMessage.warning('请先选择角色类型')
    return
  }
  if (roleForm.prompt_content.trim()) {
    await ElMessageBox.confirm('当前提示词将被默认模板覆盖，是否继续？', '填充默认提示词', {
      type: 'warning',
      confirmButtonText: '覆盖',
      cancelButtonText: '取消',
    })
  }
  loadingDefaultPrompt.value = true
  try {
    const response = await getDefaultPrompt(roleForm.role_type)
    roleForm.prompt_content = response.data.prompt_content || ''
    ElMessage.success('默认提示词已填充')
  } finally {
    loadingDefaultPrompt.value = false
  }
}

async function saveRole() {
  await roleFormRef.value?.validate()
  savingRole.value = true
  try {
    const payload = {
      name: roleForm.name,
      role_type: roleForm.role_type,
      prompt_content: roleForm.prompt_content,
      llm_model: roleForm.llm_model,
      is_active: roleForm.is_active,
    }
    if (roleForm.id) {
      await updatePrompt(roleForm.id, payload)
    } else {
      await createPrompt(payload)
    }
    ElMessage.success('系统角色配置已保存')
    roleDialogVisible.value = false
    fetchRoles()
  } finally {
    savingRole.value = false
  }
}

async function removeRole(row) {
  await ElMessageBox.confirm(`确认删除系统角色「${row.name}」？`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  await deletePrompt(row.id)
  ElMessage.success('系统角色配置已删除')
  fetchRoles()
}

onMounted(() => {
  fetchRoles()
})
</script>

<style scoped>
.config-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: min(1440px, 100%);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.eyebrow {
  margin: 0 0 4px;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.page-header h1 {
  margin: 0;
  color: #111827;
  font-size: 24px;
}

.content-panel {
  border: 1px solid #e6ebf2;
  border-radius: 8px;
  background: #ffffff;
}

.toolbar {
  display: flex;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid #edf1f6;
}

.roles-toolbar .el-input {
  max-width: 360px;
}

.roles-toolbar .el-select {
  width: 180px;
}

.prompt-editor {
  width: 100%;
}

.prompt-tools {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  color: #64748b;
  font-size: 13px;
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

.status-pill {
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

@media (max-width: 760px) {
  .page-header,
  .toolbar,
  .header-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .roles-toolbar .el-input,
  .roles-toolbar .el-select {
    max-width: none;
    width: 100%;
  }

  .prompt-tools {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
