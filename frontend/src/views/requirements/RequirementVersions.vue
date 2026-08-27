<template>
  <section class="admin-page">
    <div class="page-head">
      <div class="page-title">
        <span class="eyebrow">需求用例中心</span>
        <h1>版本管理</h1>
        <p>创建待发布版本，绑定正式需求后发布；已发布版本仍可追加需求。</p>
      </div>
      <el-select v-model="selectedProject" placeholder="选择项目" class="project-select" @change="handleProjectChange">
        <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
      </el-select>
    </div>

    <section class="data-section">
      <div class="section-head">
        <div>
          <h2>版本列表</h2>
          <p>共 {{ pagination.total }} 个版本，只有已发布版本可用于用例生成和用例筛选。</p>
        </div>
        <div class="table-toolbar">
          <el-input v-model="keyword" placeholder="搜索版本名称、版本号" clearable @keyup.enter="resetPage" @clear="resetPage" />
          <el-button :icon="Search" @click="resetPage">搜索</el-button>
          <el-button type="primary" :icon="Plus" :disabled="!selectedProject" @click="openDialog">新建版本</el-button>
        </div>
      </div>

      <el-table :data="versions" v-loading="loading" class="dense-table">
        <el-table-column prop="version_no" label="版本号" width="150">
          <template #default="{ row }"><span class="mono-code">{{ row.version_no }}</span></template>
        </el-table-column>
        <el-table-column prop="name" label="版本名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="description" label="描述" min-width="240" show-overflow-tooltip />
        <el-table-column label="正式需求" width="110" align="right"><template #default="{ row }">{{ row.requirement_revisions_count || 0 }}</template></el-table-column>
        <el-table-column prop="status_label" label="状态" width="90">
          <template #default="{ row }"><span class="status-pill" :class="versionStatusClass(row.status)">{{ row.status_label }}</span></template>
        </el-table-column>
        <el-table-column prop="published_at" label="发布时间" width="180" />
        <el-table-column label="操作" width="128" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-cell">
              <el-tooltip :content="row.status === 'archived' ? '查看正式需求' : '管理正式需求'"><el-button text type="primary" :icon="Connection" @click="openRequirementDrawer(row)">管理正式需求</el-button></el-tooltip>
              <el-tooltip v-if="row.status === 'draft'" content="发布版本"><el-button text type="success" :icon="Promotion" :disabled="!row.requirement_revisions_count" @click="publishVersion(row)">发布版本</el-button></el-tooltip>
              <el-tooltip v-if="row.status === 'published'" content="归档版本"><el-button text type="danger" :icon="Delete" @click="archiveVersion(row)">归档版本</el-button></el-tooltip>
            </div>
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无版本" /></template>
      </el-table>

      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="loadVersions"
        />
      </div>
    </section>

    <el-dialog v-model="dialogVisible" title="新建版本" width="720px">
      <el-form :model="form" label-width="96px">
        <el-form-item label="版本号"><el-input v-model="form.version_no" placeholder="例如 v1.0.0" /></el-form-item>
        <el-form-item label="版本名称"><el-input v-model="form.name" placeholder="请输入版本名称" /></el-form-item>
        <el-alert type="info" :closable="false" title="版本将以待发布状态创建，请先绑定至少一条正式需求。" />
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="4" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveVersion">创建待发布版本</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="requirementDrawerVisible" size="min(980px, 96vw)" title="管理版本正式需求">
      <template v-if="activeVersion">
        <div class="drawer-summary">
          <div>
            <span class="mono-code">{{ activeVersion.version_no }}</span>
            <h2>{{ activeVersion.name }}</h2>
            <p>{{ versionPolicyText(activeVersion.status) }}</p>
          </div>
          <span class="status-pill" :class="versionStatusClass(activeVersion.status)">{{ activeVersion.status_label }}</span>
        </div>

        <section class="drawer-section">
          <div class="drawer-section-head">
            <div><h3>已绑定正式需求</h3><p>共 {{ boundRevisions.length }} 条</p></div>
          </div>
          <el-table :data="boundRevisions" v-loading="revisionLoading" class="dense-table" max-height="280">
            <el-table-column prop="family_no" label="需求族" width="150"><template #default="{ row }"><span class="mono-code">{{ row.family_no }}</span></template></el-table-column>
            <el-table-column prop="revision_no" label="修订" width="72"><template #default="{ row }">R{{ row.revision_no }}</template></el-table-column>
            <el-table-column label="正式模块" min-width="180" show-overflow-tooltip><template #default="{ row }">{{ modulePaths(row) }}</template></el-table-column>
            <el-table-column prop="title" label="正式需求" min-width="220" show-overflow-tooltip />
            <el-table-column v-if="activeVersion.status === 'draft'" label="操作" width="56" align="center">
              <template #default="{ row }"><div class="action-cell"><el-tooltip content="移除绑定"><el-button text type="danger" :icon="Remove" :loading="removingRevisionId === row.id" @click="removeRevision(row)">移除绑定</el-button></el-tooltip></div></template>
            </el-table-column>
            <template #empty><el-empty description="尚未绑定正式需求" :image-size="64" /></template>
          </el-table>
        </section>

        <section v-if="activeVersion.status !== 'archived'" class="drawer-section">
          <div class="drawer-section-head">
            <div><h3>{{ activeVersion.status === 'published' ? '追加正式需求' : '可绑定正式需求' }}</h3><p>仅显示当前项目尚未绑定的正式需求修订</p></div>
            <div class="revision-toolbar">
              <el-input v-model="revisionKeyword" clearable placeholder="搜索需求族、标题或模块" />
              <el-button type="primary" :disabled="!revisionSelection.length" :loading="binding" @click="bindSelectedRevisions">绑定所选（{{ revisionSelection.length }}）</el-button>
            </div>
          </div>
          <el-table v-loading="revisionLoading" :data="availableRevisions" class="dense-table" max-height="360" @selection-change="revisionSelection = $event">
            <el-table-column type="selection" width="44" />
            <el-table-column prop="family_no" label="需求族" width="150"><template #default="{ row }"><span class="mono-code">{{ row.family_no }}</span></template></el-table-column>
            <el-table-column prop="revision_no" label="修订" width="72"><template #default="{ row }">R{{ row.revision_no }}</template></el-table-column>
            <el-table-column label="正式模块" min-width="180" show-overflow-tooltip><template #default="{ row }">{{ modulePaths(row) }}</template></el-table-column>
            <el-table-column prop="title" label="正式需求" min-width="220" show-overflow-tooltip />
            <template #empty><el-empty description="暂无可绑定的正式需求" :image-size="64" /></template>
          </el-table>
        </section>

        <div v-if="activeVersion.status === 'draft'" class="drawer-actions">
          <span v-if="!boundRevisions.length">至少绑定一条正式需求后才能发布</span>
          <el-button type="success" :icon="Promotion" :disabled="!boundRevisions.length" :loading="publishing" @click="publishVersion(activeVersion)">发布版本</el-button>
        </div>
      </template>
    </el-drawer>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Connection, Delete, Plus, Promotion, Remove, Search } from '@element-plus/icons-vue'

import {
  archiveRequirementVersion,
  bindRequirementVersionRequirements,
  createRequirementVersion,
  getRequirementRevisions,
  getRequirementVersions,
  publishRequirementVersion,
  unbindRequirementVersionRequirements,
} from '@/api/requirements'
import { useRequirementProjects } from './useRequirementProjects'

const { projects, selectedProject, loadProjects } = useRequirementProjects()
const versions = ref([])
const keyword = ref('')
const loading = ref(false)
const saving = ref(false)
const binding = ref(false)
const publishing = ref(false)
const dialogVisible = ref(false)
const requirementDrawerVisible = ref(false)
const activeVersion = ref()
const allRevisions = ref([])
const revisionSelection = ref([])
const revisionKeyword = ref('')
const revisionLoading = ref(false)
const removingRevisionId = ref()
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })
const form = reactive(emptyForm())

const boundRevisionIds = computed(() => new Set(activeVersion.value?.requirement_revisions || []))
const boundRevisions = computed(() => allRevisions.value.filter(revision => boundRevisionIds.value.has(revision.id)))
const availableRevisions = computed(() => {
  const keywordValue = revisionKeyword.value.trim().toLowerCase()
  return allRevisions.value.filter((revision) => {
    if (boundRevisionIds.value.has(revision.id)) return false
    if (!keywordValue) return true
    return [revision.family_no, revision.title, modulePaths(revision), `r${revision.revision_no}`]
      .some(value => String(value || '').toLowerCase().includes(keywordValue))
  })
})

function emptyForm() {
  return { project: undefined, version_no: '', name: '', description: '' }
}

function normalizeListResponse(data) {
  if (Array.isArray(data)) return { results: data, total: data.length }
  return { results: data.results || [], total: data.count || 0 }
}

function modulePaths(revision) {
  return revision.modules?.map(module => module.path).join('；') || '未设置模块'
}

async function loadVersions() {
  versions.value = []
  if (!selectedProject.value) {
    pagination.total = 0
    return
  }
  loading.value = true
  try {
    const params = { project: selectedProject.value, page: pagination.page, page_size: pagination.pageSize }
    if (keyword.value) params.search = keyword.value
    const { data } = await getRequirementVersions(params)
    const payload = normalizeListResponse(data)
    versions.value = payload.results
    pagination.total = payload.total
  } finally {
    loading.value = false
  }
}

async function handleProjectChange() {
  pagination.page = 1
  await loadVersions()
}

async function resetPage() {
  pagination.page = 1
  await loadVersions()
}

async function handleSizeChange() {
  pagination.page = 1
  await loadVersions()
}

function openDialog() {
  Object.assign(form, emptyForm(), { project: selectedProject.value })
  dialogVisible.value = true
}

async function saveVersion() {
  if (!form.version_no.trim()) return ElMessage.warning('请输入版本号')
  if (!form.name.trim()) return ElMessage.warning('请输入版本名称')
  saving.value = true
  try {
    await createRequirementVersion({
      project: selectedProject.value,
      version_no: form.version_no.trim(),
      name: form.name.trim(),
      description: form.description,
    })
    ElMessage.success('待发布版本已创建')
    dialogVisible.value = false
    await loadVersions()
  } catch (_error) {
    // API 错误由统一错误中心展示。
  } finally {
    saving.value = false
  }
}

function versionStatusClass(status) {
  return { draft: 'is-warning', published: 'is-success', archived: 'is-muted' }[status] || 'is-muted'
}

function versionPolicyText(status) {
  if (status === 'draft') return '可绑定或移除正式需求，绑定完成后发布。'
  if (status === 'published') return '可继续追加正式需求，已有绑定不可移除。'
  return '归档版本仅供查看，不再接受需求调整。'
}

function replaceVersion(updated) {
  const index = versions.value.findIndex(version => version.id === updated.id)
  if (index >= 0) versions.value[index] = updated
  if (activeVersion.value?.id === updated.id) activeVersion.value = updated
}

async function loadAllRevisions() {
  allRevisions.value = []
  if (!selectedProject.value) return
  revisionLoading.value = true
  try {
    let page = 1
    let hasNext = true
    while (hasNext) {
      const { data } = await getRequirementRevisions({ project: selectedProject.value, page, page_size: 100 })
      const payload = normalizeListResponse(data)
      allRevisions.value.push(...payload.results)
      hasNext = Boolean(data.next)
      page += 1
    }
  } finally {
    revisionLoading.value = false
  }
}

async function openRequirementDrawer(row) {
  activeVersion.value = row
  revisionSelection.value = []
  revisionKeyword.value = ''
  requirementDrawerVisible.value = true
  await loadAllRevisions()
}

async function bindSelectedRevisions() {
  binding.value = true
  try {
    const { data } = await bindRequirementVersionRequirements(activeVersion.value.id, revisionSelection.value.map(revision => revision.id))
    replaceVersion(data)
    revisionSelection.value = []
    ElMessage.success(activeVersion.value.status === 'published' ? '正式需求已追加' : '正式需求已绑定')
  } catch (_error) {
    // API 错误由统一错误中心展示。
  } finally {
    binding.value = false
  }
}

async function removeRevision(row) {
  await ElMessageBox.confirm(`确认从当前待发布版本移除「${row.title}」？`, '移除绑定', { type: 'warning' })
  removingRevisionId.value = row.id
  try {
    const { data } = await unbindRequirementVersionRequirements(activeVersion.value.id, [row.id])
    replaceVersion(data)
    ElMessage.success('正式需求已移除')
  } catch (_error) {
    // API 错误由统一错误中心展示。
  } finally {
    removingRevisionId.value = undefined
  }
}

async function publishVersion(row) {
  if (!row.requirement_revisions_count) return ElMessage.warning('请至少绑定一条正式需求')
  await ElMessageBox.confirm('发布后已有正式需求不可移除，只能继续追加。确认发布？', '发布版本', { type: 'warning' })
  publishing.value = true
  try {
    const { data } = await publishRequirementVersion(row.id)
    replaceVersion(data)
    ElMessage.success('版本已发布')
  } catch (_error) {
    // API 错误由统一错误中心展示。
  } finally {
    publishing.value = false
  }
}

async function archiveVersion(row) {
  await ElMessageBox.confirm(`归档后该版本不再用于新任务，确认归档「${row.name}」？`, '归档版本', { type: 'warning' })
  await archiveRequirementVersion(row.id)
  ElMessage.success('版本已归档')
  await loadVersions()
}

onMounted(async () => {
  await loadProjects()
  await loadVersions()
})
</script>

<style scoped>
.admin-page { width: min(1440px, 100%); }
.page-head, .section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }
.page-head { margin-bottom: 16px; }
h1, h2, p { margin: 0; }
.eyebrow { display: block; margin-bottom: 6px; color: #64748b; font-size: 12px; font-weight: 600; }
h1 { margin-bottom: 6px; color: #172033; font-size: 24px; font-weight: 650; }
h2 { color: #172033; font-size: 17px; font-weight: 650; }
p { color: #64748b; font-size: 14px; line-height: 1.6; }
.project-select { width: 240px; }
.data-section { border: 1px solid #e6ebf2; border-radius: 8px; background: #ffffff; }
.section-head { min-height: 58px; padding: 12px 14px; border-bottom: 1px solid #edf1f6; }
.table-toolbar { display: flex; align-items: center; gap: 8px; }
.table-toolbar .el-input { max-width: 360px; }
.dense-table { --el-table-border-color: #edf1f6; --el-table-header-bg-color: #fbfcfe; --el-table-header-text-color: #6b7280; --el-table-row-hover-bg-color: #f8fbff; font-size: 14px; }
.dense-table :deep(.el-table__header th) { height: 42px; padding: 0; font-weight: 650; }
.dense-table :deep(.el-table__cell) { padding: 8px 0; }
.mono-code { color: #374151; font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace; font-size: 13px; font-variant-numeric: tabular-nums; }
.status-pill { display: inline-flex; align-items: center; height: 22px; padding: 0 8px; border-radius: 999px; font-size: 12px; white-space: nowrap; }
.status-pill.is-success { color: #047857; background: #ecfdf5; border: 1px solid #bbf7d0; }
.status-pill.is-warning { color: #a16207; background: #fffbeb; border: 1px solid #fde68a; }
.status-pill.is-muted { color: #64748b; background: #f8fafc; border: 1px solid #e2e8f0; }
.action-cell { display: inline-flex; align-items: center; justify-content: center; gap: 4px; white-space: nowrap; }
.action-cell :deep(.el-button) { width: 28px; height: 28px; margin-left: 0; padding: 0; border-radius: 6px; }
.action-cell :deep(.el-button span) { display: none; }
.action-cell :deep(.el-icon + span) { margin-left: 0; }
.pagination-bar { display: flex; justify-content: flex-end; padding: 12px 14px; border-top: 1px solid #edf1f6; }
.drawer-summary,.drawer-section-head,.drawer-actions,.revision-toolbar{display:flex;align-items:center}
.drawer-summary,.drawer-section-head{justify-content:space-between;gap:20px}
.drawer-summary{padding:0 0 14px;border-bottom:1px solid #e6ebf2}
.drawer-summary h2{margin-top:4px}
.drawer-summary p{margin-top:4px}
.drawer-section{margin-top:16px;border:1px solid #e6ebf2;border-radius:8px;overflow:hidden}
.drawer-section-head{min-height:58px;padding:12px 14px;border-bottom:1px solid #edf1f6}
.drawer-section-head h3{margin:0;color:#172033;font-size:15px}
.revision-toolbar{gap:8px}
.revision-toolbar .el-input{width:280px}
.drawer-actions{position:sticky;bottom:0;justify-content:flex-end;gap:12px;margin-top:18px;padding:12px 0;background:#fff}
.drawer-actions span{color:#a16207;font-size:13px}
@media (max-width: 760px) {
  .page-head, .section-head, .table-toolbar, .drawer-summary, .drawer-section-head, .revision-toolbar { align-items: stretch; flex-direction: column; }
  .project-select, .table-toolbar .el-input, .revision-toolbar .el-input { width: 100%; max-width: none; }
}
</style>
