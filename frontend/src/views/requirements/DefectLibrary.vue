<template>
  <section class="defect-page">
    <header class="page-head">
      <div class="page-title">
        <span class="eyebrow">需求用例中心</span>
        <h1>缺陷库</h1>
        <p>维护可追溯的历史缺陷知识；只有已确认且未作废记录会进入用例增强检索。</p>
      </div>
      <el-select v-model="selectedProject" class="project-select" placeholder="选择项目" @change="handleProjectChange">
        <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
      </el-select>
    </header>

    <section class="data-section">
      <div class="section-head">
        <div>
          <h2>缺陷记录</h2>
          <p>共 {{ pagination.total }} 条，已选择 {{ selectedRows.length }} 条。</p>
        </div>
        <div class="toolbar">
          <el-input v-model="filters.search" clearable placeholder="编号、标题、根因" @keyup.enter="resetPage" @clear="resetPage" />
          <el-select v-model="filters.severity" clearable placeholder="严重程度" @change="resetPage">
            <el-option v-for="item in severityOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-select v-model="filters.knowledge_status" clearable placeholder="确认状态" @change="resetPage">
            <el-option v-for="item in knowledgeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-button :disabled="!confirmableIds.length" @click="confirmSelected">确认选中</el-button>
          <el-button :icon="Upload" @click="importVisible = true">导入</el-button>
          <el-button type="primary" :icon="Plus" @click="openDialog()">新增缺陷</el-button>
        </div>
      </div>

      <el-table v-loading="loading" :data="rows" class="dense-table" @selection-change="selectedRows = $event">
        <el-table-column type="selection" width="46" />
        <el-table-column prop="defect_no" label="缺陷编号" width="130">
          <template #default="{ row }"><span class="mono-code">{{ row.defect_no }}</span></template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="260" show-overflow-tooltip />
        <el-table-column prop="severity_label" label="严重程度" width="96">
          <template #default="{ row }"><span class="text-badge">{{ row.severity_label }}</span></template>
        </el-table-column>
        <el-table-column prop="lifecycle_status_label" label="缺陷状态" width="96" />
        <el-table-column prop="knowledge_status_label" label="确认状态" width="96">
          <template #default="{ row }"><span :class="['status-pill', `status-${row.knowledge_status}`]">{{ row.knowledge_status_label }}</span></template>
        </el-table-column>
        <el-table-column label="模块" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.module_paths?.map(item => item.path).join('；') || '-' }}</template>
        </el-table-column>
        <el-table-column prop="detected_version_name" label="发现版本" width="120" show-overflow-tooltip />
        <el-table-column prop="root_cause" label="根因" min-width="220" show-overflow-tooltip />
        <el-table-column label="操作" width="128" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-cell">
              <el-button text type="primary" :icon="Edit" @click="openDialog(row)">编辑</el-button>
              <el-button v-if="row.knowledge_status === 'confirmed'" text type="warning" :icon="CircleClose" @click="invalidateRow(row)">作废</el-button>
              <el-button text type="danger" :icon="Delete" @click="removeRow(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-bar">
        <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.pageSize" :page-sizes="[10, 20, 50]" :total="pagination.total" layout="total, sizes, prev, pager, next, jumper" @size-change="resetPage" @current-change="loadRows" />
      </div>
    </section>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑缺陷' : '新增缺陷'" width="min(860px, 94vw)" destroy-on-close>
      <el-form label-position="top" class="defect-form">
        <div class="form-grid">
          <el-form-item label="缺陷编号" required><el-input v-model="form.defect_no" /></el-form-item>
          <el-form-item label="缺陷标题" required><el-input v-model="form.title" /></el-form-item>
          <el-form-item label="严重程度"><el-select v-model="form.severity"><el-option v-for="item in severityOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
          <el-form-item label="缺陷状态"><el-select v-model="form.lifecycle_status"><el-option v-for="item in lifecycleOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
          <el-form-item label="发现版本"><el-select v-model="form.detected_version" clearable><el-option v-for="item in versions" :key="item.id" :label="`${item.version_no} ${item.name}`" :value="item.id" /></el-select></el-form-item>
          <el-form-item label="修复版本"><el-select v-model="form.fixed_version" clearable><el-option v-for="item in versions" :key="item.id" :label="`${item.version_no} ${item.name}`" :value="item.id" /></el-select></el-form-item>
          <el-form-item label="正式模块" class="span-2"><el-select v-model="form.modules" multiple filterable><el-option v-for="item in modules" :key="item.id" :label="item.path" :value="item.id" /></el-select></el-form-item>
          <el-form-item label="标签" class="span-2"><el-input v-model="tagText" placeholder="使用逗号分隔" /></el-form-item>
          <el-form-item label="缺陷描述" class="span-2"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
          <el-form-item label="复现步骤" class="span-2"><el-input v-model="form.reproduction_steps" type="textarea" :rows="4" /></el-form-item>
          <el-form-item label="实际结果"><el-input v-model="form.actual_result" type="textarea" :rows="3" /></el-form-item>
          <el-form-item label="预期结果"><el-input v-model="form.expected_result" type="textarea" :rows="3" /></el-form-item>
          <el-form-item label="根因"><el-input v-model="form.root_cause" type="textarea" :rows="3" /></el-form-item>
          <el-form-item label="解决方案"><el-input v-model="form.resolution" type="textarea" :rows="3" /></el-form-item>
        </div>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveRow">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="importVisible" title="导入历史缺陷" width="520px">
      <p class="import-help">支持 CSV/XLSX，列名可使用：缺陷编号、缺陷标题、描述、复现步骤、严重程度、状态、发现版本、模块编码、根因、解决方案、标签。导入后默认待确认。</p>
      <el-upload :auto-upload="false" :limit="1" accept=".csv,.xlsx" :on-change="file => importFile = file.raw" :on-remove="() => importFile = null"><el-button :icon="DocumentAdd">选择文件</el-button></el-upload>
      <template #footer><el-button @click="importVisible = false">取消</el-button><el-button type="primary" :disabled="!importFile" :loading="importing" @click="submitImport">开始导入</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CircleClose, Delete, DocumentAdd, Edit, Plus, Upload } from '@element-plus/icons-vue'

import { confirmDefects, createDefect, deleteDefect, getDefects, importDefects, invalidateDefect, updateDefect } from '@/api/defects'
import { getProjectModules } from '@/api/projectKnowledge'
import { getRequirementVersions } from '@/api/requirements'
import { useRequirementProjects } from './useRequirementProjects'

const { projects, selectedProject, loadProjects } = useRequirementProjects()
const rows = ref([])
const versions = ref([])
const modules = ref([])
const selectedRows = ref([])
const loading = ref(false)
const saving = ref(false)
const importing = ref(false)
const dialogVisible = ref(false)
const importVisible = ref(false)
const importFile = ref(null)
const editingId = ref(null)
const tagText = ref('')
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })
const filters = reactive({ search: '', severity: '', knowledge_status: '' })
const severityOptions = [{ label: '致命', value: 'critical' }, { label: '严重', value: 'high' }, { label: '一般', value: 'medium' }, { label: '轻微', value: 'low' }]
const lifecycleOptions = [{ label: '待处理', value: 'open' }, { label: '已解决', value: 'resolved' }, { label: '已关闭', value: 'closed' }, { label: '已拒绝', value: 'rejected' }]
const knowledgeOptions = [{ label: '待确认', value: 'draft' }, { label: '已确认', value: 'confirmed' }, { label: '已作废', value: 'invalid' }]
const emptyForm = () => ({ defect_no: '', title: '', description: '', reproduction_steps: '', actual_result: '', expected_result: '', root_cause: '', resolution: '', severity: 'medium', lifecycle_status: 'open', detected_version: null, fixed_version: null, modules: [], tags: [] })
const form = reactive(emptyForm())
const confirmableIds = computed(() => selectedRows.value.filter(row => row.knowledge_status !== 'confirmed').map(row => row.id))

function normalize(data) { return Array.isArray(data) ? { results: data, count: data.length } : { results: data.results || [], count: data.count || 0 } }
async function loadContext() {
  if (!selectedProject.value) return
  const [versionResponse, moduleResponse] = await Promise.all([
    getRequirementVersions({ project: selectedProject.value, page_size: 200 }),
    getProjectModules({ project: selectedProject.value, status: 'active', page_size: 500 }),
  ])
  versions.value = normalize(versionResponse.data).results
  modules.value = normalize(moduleResponse.data).results
}
async function loadRows() {
  if (!selectedProject.value) return
  loading.value = true
  try {
    const params = { project: selectedProject.value, page: pagination.page, page_size: pagination.pageSize }
    Object.entries(filters).forEach(([key, value]) => { if (value) params[key] = value })
    const { data } = await getDefects(params)
    const payload = normalize(data)
    rows.value = payload.results
    pagination.total = payload.count
  } finally { loading.value = false }
}
async function handleProjectChange() { pagination.page = 1; await loadContext(); await loadRows() }
async function resetPage() { pagination.page = 1; await loadRows() }
function openDialog(row = null) {
  editingId.value = row?.id || null
  Object.assign(form, emptyForm(), row ? { ...row, modules: row.modules || [] } : {})
  tagText.value = (row?.tags || []).join(', ')
  dialogVisible.value = true
}
async function saveRow() {
  if (!form.defect_no.trim() || !form.title.trim()) return ElMessage.warning('请填写缺陷编号和标题')
  saving.value = true
  try {
    const payload = { ...form, project: selectedProject.value, tags: tagText.value.split(/[,，]/).map(item => item.trim()).filter(Boolean) }
    editingId.value ? await updateDefect(editingId.value, payload) : await createDefect(payload)
    ElMessage.success('缺陷已保存')
    dialogVisible.value = false
    await loadRows()
  } catch (_error) { /* 统一错误中心已展示 */ } finally { saving.value = false }
}
async function removeRow(row) {
  try { await ElMessageBox.confirm(`确认删除缺陷 ${row.defect_no}？`, '删除缺陷', { type: 'warning' }); await deleteDefect(row.id); ElMessage.success('已删除'); await loadRows() } catch (_error) { /* 取消操作或统一错误中心已处理 */ }
}
async function invalidateRow(row) {
  try { await ElMessageBox.confirm(`确认作废缺陷 ${row.defect_no}？作废后将从增强检索中移除。`, '作废缺陷', { type:'warning' }); await invalidateDefect(row.id); ElMessage.success('缺陷已作废'); await loadRows() } catch (_error) { /* 取消操作或统一错误中心已处理 */ }
}
async function confirmSelected() { await confirmDefects(confirmableIds.value); ElMessage.success('已确认并提交检索索引'); await loadRows() }
async function submitImport() {
  importing.value = true
  try {
    const payload = new FormData(); payload.append('project', selectedProject.value); payload.append('file', importFile.value)
    const { data } = await importDefects(payload)
    ElMessage.success(`导入完成：成功 ${data.success_count}，失败 ${data.failed_count}`)
    importVisible.value = false; importFile.value = null; await loadRows()
  } catch (_error) { /* 统一错误中心已展示 */ } finally { importing.value = false }
}
onMounted(async () => { await loadProjects(); await handleProjectChange() })
</script>

<style scoped>
.defect-page { width: min(1440px, 100%); }
.page-head,.section-head { display:flex; align-items:flex-start; justify-content:space-between; gap:24px; }
.page-head { margin-bottom:16px; } .page-title { min-width:0; }
.eyebrow { display:block; margin-bottom:6px; color:#64748b; font-size:12px; font-weight:600; }
h1,h2,p { margin:0; } h1 { margin-bottom:6px; color:#172033; font-size:24px; font-weight:650; } h2 { color:#172033; font-size:17px; font-weight:650; } p { color:#64748b; font-size:14px; line-height:1.6; }
.project-select { flex:0 0 240px; } .data-section { border:1px solid #e6ebf2; border-radius:8px; background:#fff; }
.section-head { align-items:flex-end; min-height:58px; padding:12px 14px; border-bottom:1px solid #edf1f6; }
.toolbar { display:flex; align-items:center; gap:8px; flex-wrap:wrap; justify-content:flex-end; } .toolbar .el-input { width:220px; } .toolbar .el-select { width:130px; }
.dense-table { --el-table-border-color:#edf1f6; --el-table-header-bg-color:#fbfcfe; --el-table-header-text-color:#6b7280; --el-table-row-hover-bg-color:#f8fbff; font-size:14px; }
.dense-table :deep(.el-table__header th) { height:42px; padding:0; font-weight:650; } .dense-table :deep(.el-table__cell) { padding:8px 0; }
.mono-code { color:#374151; font-family:"SFMono-Regular",Consolas,monospace; font-size:13px; }
.status-pill,.text-badge { display:inline-flex; align-items:center; height:22px; padding:0 8px; border-radius:999px; font-size:12px; white-space:nowrap; }
.text-badge { color:#475569; background:#f1f5f9; } .status-confirmed { color:#15803d; background:#f0fdf4; } .status-draft { color:#b45309; background:#fffbeb; } .status-invalid { color:#64748b; background:#f1f5f9; }
.action-cell { display:inline-flex; gap:4px; } .action-cell :deep(.el-button) { width:28px; height:28px; margin:0; padding:0; border-radius:6px; } .action-cell :deep(.el-button span) { display:none; }
.pagination-bar { display:flex; justify-content:flex-end; padding:12px 14px; border-top:1px solid #edf1f6; }
.form-grid { display:grid; grid-template-columns:1fr 1fr; gap:0 16px; } .span-2 { grid-column:1 / -1; } .defect-form .el-select { width:100%; }
.import-help { margin-bottom:16px; }
@media (max-width:900px) { .page-head,.section-head { flex-direction:column; align-items:stretch; gap:12px; } .project-select { flex-basis:auto; width:100%; } .toolbar { justify-content:flex-start; } .form-grid { grid-template-columns:1fr; } .span-2 { grid-column:auto; } }
</style>
