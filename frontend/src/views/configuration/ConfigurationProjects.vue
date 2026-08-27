<template>
  <section class="config-page">
    <div class="page-header">
      <div>
        <p class="eyebrow">Configuration</p>
        <h1>项目配置</h1>
        <p class="page-description">维护全局项目；进入项目详情可管理正式模块、项目知识、需求版本与索引。</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="openProjectDialog()">新增项目</el-button>
    </div>

    <div class="content-panel">
      <div class="toolbar projects-toolbar">
        <el-input v-model="projectFilters.search" clearable placeholder="搜索项目名称、编码或负责人" :prefix-icon="Search" @keyup.enter="resetProjectPage" @clear="resetProjectPage" />
        <el-select v-model="projectFilters.status" clearable placeholder="项目状态" @change="resetProjectPage">
          <el-option label="启用" value="active" />
          <el-option label="停用" value="inactive" />
        </el-select>
        <el-button :icon="Refresh" @click="fetchProjects">刷新</el-button>
      </div>

      <el-table v-loading="projectLoading" :data="projects" class="dense-table">
        <el-table-column prop="name" label="项目名称" min-width="170" show-overflow-tooltip />
        <el-table-column prop="code" label="项目编码" min-width="140"><template #default="{ row }"><span class="mono-code">{{ row.code }}</span></template></el-table-column>
        <el-table-column prop="owner" label="负责人" min-width="110"><template #default="{ row }">{{ row.owner || '-' }}</template></el-table-column>
        <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip><template #default="{ row }">{{ row.description || '-' }}</template></el-table-column>
        <el-table-column label="确认状态" width="110"><template #default="{ row }"><span class="status-pill" :class="row.confirmation_status === 'pending' ? 'is-warning' : 'is-success'">{{ row.confirmation_status === 'pending' ? '待再次确认' : '已确认' }}</span></template></el-table-column>
        <el-table-column label="状态" width="90"><template #default="{ row }"><span class="status-pill" :class="row.status === 'active' ? 'is-success' : 'is-muted'">{{ row.status === 'active' ? '启用' : '停用' }}</span></template></el-table-column>
        <el-table-column label="默认" width="76"><template #default="{ row }"><span v-if="row.is_default" class="text-badge is-default">默认</span><span v-else>-</span></template></el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="180"><template #default="{ row }">{{ formatDate(row.updated_at) }}</template></el-table-column>
        <el-table-column label="操作" width="160" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-cell">
              <el-button text type="primary" :icon="View" @click="openProjectDetail(row)">详情</el-button>
              <el-button text type="primary" :icon="Edit" @click="openProjectDialog(row)">编辑</el-button>
              <el-button text type="success" :icon="Star" :disabled="row.is_default || row.status !== 'active'" @click="makeProjectDefault(row)">设默认</el-button>
              <el-button text type="danger" :icon="Delete" @click="removeProject(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-bar"><el-pagination v-model:current-page="projectPagination.page" v-model:page-size="projectPagination.pageSize" :page-sizes="[10, 20, 50]" :total="projectPagination.total" layout="total, sizes, prev, pager, next, jumper" @size-change="handleProjectSizeChange" @current-change="fetchProjects" /></div>
    </div>

    <el-dialog v-model="projectDialogVisible" :title="projectForm.id ? '编辑项目' : '新增项目'" width="560px">
      <el-alert v-if="projectForm.id" title="编辑内容保存为待确认稿，确认前当前正式项目配置继续生效。" type="info" :closable="false" show-icon />
      <el-form ref="projectFormRef" :model="projectForm" :rules="projectRules" label-width="96px" class="project-form">
        <el-form-item label="项目名称" prop="name"><el-input v-model="projectForm.name" /></el-form-item>
        <el-form-item label="项目编码" prop="code"><el-input v-model="projectForm.code" /></el-form-item>
        <el-form-item label="负责人"><el-input v-model="projectForm.owner" /></el-form-item>
        <el-form-item label="状态" prop="status"><el-radio-group v-model="projectForm.status"><el-radio-button label="active">启用</el-radio-button><el-radio-button label="inactive">停用</el-radio-button></el-radio-group></el-form-item>
        <el-form-item label="默认项目"><el-switch v-model="projectForm.is_default" :disabled="projectForm.status !== 'active'" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="projectForm.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="projectDialogVisible = false">取消</el-button><el-button type="primary" :loading="savingProject" @click="saveProject">{{ projectForm.id ? '保存待确认稿' : '保存' }}</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit, Plus, Refresh, Search, Star, View } from '@element-plus/icons-vue'
import { createProject, deleteProject, getProjects, setDefaultProject, updateProject } from '@/api/configuration'
import { cleanParams, formatDate, normalizeListResponse } from './configurationHelpers'

const router = useRouter()
const projects = ref([])
const projectLoading = ref(false)
const savingProject = ref(false)
const projectDialogVisible = ref(false)
const projectFormRef = ref()
const projectFilters = reactive({ search: '', status: '' })
const projectPagination = reactive({ page: 1, pageSize: 10, total: 0 })
const projectForm = reactive(emptyProjectForm())
const projectRules = { name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }], code: [{ required: true, message: '请输入项目编码', trigger: 'blur' }], status: [{ required: true, message: '请选择状态', trigger: 'change' }] }

function emptyProjectForm() { return { id: null, name: '', code: '', description: '', owner: '', status: 'active', is_default: false } }
function resetReactive(target, source) { Object.keys(target).forEach(key => delete target[key]); Object.assign(target, source) }

async function fetchProjects() {
  projectLoading.value = true
  try {
    const { data } = await getProjects(cleanParams({ ...projectFilters, page: projectPagination.page, page_size: projectPagination.pageSize }))
    const payload = normalizeListResponse(data)
    projects.value = payload.results
    projectPagination.total = payload.total
  } finally { projectLoading.value = false }
}
async function resetProjectPage() { projectPagination.page = 1; await fetchProjects() }
async function handleProjectSizeChange() { projectPagination.page = 1; await fetchProjects() }
function openProjectDialog(row = null) {
  const values = row?.pending_revision ? { ...row, ...row.pending_revision, status: row.pending_revision.project_status, is_default: row.is_default } : row
  resetReactive(projectForm, values ? { ...emptyProjectForm(), ...values, id: row.id } : emptyProjectForm())
  projectDialogVisible.value = true
}
function openProjectDetail(row) { router.push(`/configuration/projects/${row.id}`) }
async function saveProject() {
  await projectFormRef.value.validate()
  savingProject.value = true
  try {
    const payload = { ...projectForm }
    if (payload.status !== 'active') payload.is_default = false
    if (payload.id) await updateProject(payload.id, payload)
    else await createProject(payload)
    ElMessage.success(payload.id ? '项目待确认稿已保存' : '项目已创建并生效')
    projectDialogVisible.value = false
    await fetchProjects()
  } finally { savingProject.value = false }
}
async function makeProjectDefault(row) { await setDefaultProject(row.id); ElMessage.success('默认项目已更新'); await fetchProjects() }
async function removeProject(row) { await ElMessageBox.confirm(`确认删除项目「${row.name}」？`, '删除项目', { type: 'warning' }); await deleteProject(row.id); ElMessage.success('项目已删除'); await fetchProjects() }
onMounted(fetchProjects)
</script>

<style scoped>
.config-page { width: min(1440px, 100%); }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.eyebrow, h1, .page-description { margin: 0; }.eyebrow { margin-bottom: 6px; color: #64748b; font-size: 12px; font-weight: 600; } h1 { color: #172033; font-size: 24px; font-weight: 650; }.page-description { margin-top: 7px; color: #64748b; font-size: 14px; }
.content-panel { border: 1px solid #e6ebf2; border-radius: 8px; background: #fff; }.toolbar { display: grid; gap: 8px; padding: 12px 14px; border-bottom: 1px solid #edf1f6; }.projects-toolbar { grid-template-columns: minmax(240px, 1fr) 160px auto; }
:deep(.el-select) { width: 100%; }.dense-table { --el-table-border-color: #edf1f6; --el-table-header-bg-color: #fbfcfe; --el-table-header-text-color: #6b7280; --el-table-row-hover-bg-color: #f8fbff; font-size: 14px; }.dense-table :deep(.el-table__header th) { height: 42px; padding: 0; font-weight: 650; }.dense-table :deep(.el-table__cell) { padding: 8px 0; }
.mono-code { color: #374151; font-family: "SFMono-Regular", Consolas, monospace; font-size: 13px; }.status-pill, .text-badge { display: inline-flex; align-items: center; height: 22px; padding: 0 8px; border-radius: 999px; font-size: 12px; white-space: nowrap; }.is-success { color: #047857; background: #ecfdf5; border: 1px solid #bbf7d0; }.is-muted { color: #64748b; background: #f8fafc; border: 1px solid #e2e8f0; }.is-warning { color: #9a6700; background: #fffbeb; border: 1px solid #fde68a; }.is-default { color: #92400e; background: #fffbeb; border: 1px solid #fde68a; }
.action-cell { display: inline-flex; align-items: center; justify-content: center; gap: 4px; white-space: nowrap; }.action-cell :deep(.el-button) { width: 28px; height: 28px; margin-left: 0; padding: 0; border-radius: 6px; }.action-cell :deep(.el-button span) { display: none; }.action-cell :deep(.el-icon + span) { margin-left: 0; }.pagination-bar { display: flex; justify-content: flex-end; padding: 12px 14px; border-top: 1px solid #edf1f6; }.project-form { margin-top: 18px; }
@media (max-width: 900px) { .projects-toolbar { grid-template-columns: 1fr; }.page-header { align-items: stretch; flex-direction: column; } }
</style>
