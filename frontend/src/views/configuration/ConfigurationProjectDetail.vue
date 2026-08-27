<template>
  <section class="detail-page" v-loading="pageLoading">
    <div class="page-header">
      <div class="header-content">
        <el-button text :icon="Back" class="back-button" @click="router.push('/configuration/projects')">返回项目列表</el-button>
        <div class="title-line">
          <h1>{{ project?.name || '项目详情' }}</h1>
          <span v-if="project" class="project-code mono-code">{{ project.code }}</span>
          <span v-if="project?.confirmation_status === 'pending'" class="status-pill is-warning">有待确认修改</span>
        </div>
      </div>
      <el-button :icon="Refresh" class="refresh-button" @click="loadAll">刷新</el-button>
    </div>

    <el-tabs v-if="project" v-model="activeTab" class="detail-tabs">
      <el-tab-pane label="项目概览" name="overview">
        <div class="section-panel">
          <div class="section-head"><div><h2>当前正式配置</h2><p>修订 v{{ project.current_revision_no }}，下游业务当前使用以下内容。</p></div><el-button type="primary" :icon="Edit" @click="openProjectDialog">编辑项目</el-button></div>
          <el-descriptions :column="2" border class="project-descriptions">
            <el-descriptions-item label="项目名称">{{ project.name }}</el-descriptions-item><el-descriptions-item label="项目编码"><span class="mono-code">{{ project.code }}</span></el-descriptions-item>
            <el-descriptions-item label="负责人">{{ project.owner || '-' }}</el-descriptions-item><el-descriptions-item label="状态">{{ project.status === 'active' ? '启用' : '停用' }}</el-descriptions-item>
            <el-descriptions-item label="默认项目">{{ project.is_default ? '是' : '否' }}</el-descriptions-item><el-descriptions-item label="更新时间">{{ formatDate(project.updated_at) }}</el-descriptions-item>
            <el-descriptions-item label="项目描述" :span="2">{{ project.description || '-' }}</el-descriptions-item>
          </el-descriptions>
        </div>
        <div v-if="project.pending_revision" class="section-panel pending-panel">
          <div class="section-head"><div><h2>待确认修改</h2><p>修订 v{{ project.pending_revision.revision_no }} 尚未影响当前正式配置。</p></div><div class="head-actions"><el-button :icon="Edit" @click="openProjectDialog">继续编辑</el-button><el-button type="primary" :icon="CircleCheck" :loading="confirmingProject" @click="confirmProjectChanges">再次确认</el-button></div></div>
          <el-descriptions :column="2" border><el-descriptions-item label="项目名称">{{ project.pending_revision.name }}</el-descriptions-item><el-descriptions-item label="项目编码"><span class="mono-code">{{ project.pending_revision.code }}</span></el-descriptions-item><el-descriptions-item label="负责人">{{ project.pending_revision.owner || '-' }}</el-descriptions-item><el-descriptions-item label="状态">{{ project.pending_revision.project_status_label }}</el-descriptions-item><el-descriptions-item label="项目描述" :span="2">{{ project.pending_revision.description || '-' }}</el-descriptions-item></el-descriptions>
        </div>
      </el-tab-pane>

      <el-tab-pane label="正式模块" name="modules">
        <div class="section-panel">
          <div class="section-head"><div><h2>正式模块组织树</h2><p>{{ moduleCount }} 个模块；编辑后需再次确认，确认前正式层级保持不变。</p></div><el-button type="primary" :icon="Plus" @click="openModuleDialog()">新增根模块</el-button></div>
          <el-tree v-if="moduleTree.length" :data="moduleTree" node-key="id" default-expand-all :expand-on-click-node="false" class="module-tree">
            <template #default="{ data }">
              <div class="module-node">
                <div class="module-main"><strong>{{ data.name }}</strong><span class="mono-code">{{ data.code }}</span><span class="status-pill" :class="data.status === 'active' ? 'is-success' : 'is-muted'">{{ data.status === 'active' ? '启用' : '停用' }}</span><span v-if="data.confirmation_status === 'pending'" class="status-pill is-warning">待再次确认</span><span class="module-description">{{ data.description || '暂无说明' }}</span></div>
                <div class="node-actions"><el-button text type="primary" :icon="Plus" @click.stop="openModuleDialog(null, data)">新增子模块</el-button><el-button text type="primary" :icon="Edit" @click.stop="openModuleDialog(data)">编辑</el-button><el-button v-if="data.confirmation_status === 'pending'" text type="success" :icon="CircleCheck" :loading="confirmingModuleId === data.id" @click.stop="confirmModuleChanges(data)">确认</el-button></div>
              </div>
            </template>
          </el-tree>
          <el-empty v-else description="暂无正式模块，可先新增根模块" />
        </div>
      </el-tab-pane>

      <el-tab-pane label="项目知识" name="knowledge">
        <div class="section-panel">
          <div class="section-head"><div><h2>项目知识</h2><p>{{ knowledgeItems.length }} 条知识项；候选修订确认后进入项目正式知识库。</p></div><el-button type="primary" :icon="Plus" @click="openKnowledgeDialog">新增知识</el-button></div>
          <el-table v-if="knowledgeItems.length" :data="knowledgeItems" class="dense-table knowledge-table">
            <el-table-column prop="code" label="编码" width="150"><template #default="{ row }"><span class="mono-code">{{ row.code }}</span></template></el-table-column>
            <el-table-column prop="category_label" label="类别" width="120" />
            <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
            <el-table-column prop="module_name" label="适用模块" min-width="140"><template #default="{ row }">{{ row.module_name || '全项目' }}</template></el-table-column>
            <el-table-column label="状态" width="110"><template #default="{ row }"><span class="status-pill" :class="knowledgeStatusClass(row)">{{ row.current_revision?.status_label || '-' }}</span></template></el-table-column>
            <el-table-column label="操作" width="128" fixed="right" align="center"><template #default="{ row }"><div class="knowledge-actions"><el-button text type="primary" @click="openKnowledgeDetail(row)">查看正文</el-button><el-button text type="success" :loading="confirmingKnowledgeId === row.current_revision?.id" :disabled="row.current_revision?.status !== 'candidate' || confirmingKnowledgeId !== null" @click="confirmKnowledge(row)">确认</el-button></div></template></el-table-column>
          </el-table>
          <div v-if="knowledgeItems.length" class="knowledge-cards">
            <article v-for="item in knowledgeItems" :key="item.id" class="knowledge-card">
              <div class="knowledge-card-head"><div><strong>{{ item.title }}</strong><div class="knowledge-meta"><span class="mono-code">{{ item.code }}</span><span>{{ item.category_label }}</span><span>{{ item.module_name || '全项目' }}</span></div></div><span class="status-pill" :class="knowledgeStatusClass(item)">{{ item.current_revision?.status_label || '-' }}</span></div>
              <div class="knowledge-content">{{ item.current_revision?.content || '暂无正文' }}</div>
              <div class="knowledge-card-actions"><el-button text type="primary" @click="openKnowledgeDetail(item)">查看详情</el-button><el-button v-if="item.current_revision?.status === 'candidate'" text type="success" :loading="confirmingKnowledgeId === item.current_revision?.id" :disabled="confirmingKnowledgeId !== null" @click="confirmKnowledge(item)">确认候选</el-button></div>
            </article>
          </div>
          <el-empty v-if="!knowledgeItems.length" description="暂无项目知识，可新增第一条候选知识" />
        </div>
      </el-tab-pane>

      <el-tab-pane label="需求版本" name="versions"><div class="section-panel"><div class="section-head"><div><h2>需求版本</h2><p>{{ projectVersions.length }} 个版本。</p></div></div><el-table :data="projectVersions" class="dense-table"><el-table-column prop="sequence" label="序号" width="80" /><el-table-column prop="version_no" label="版本号" width="160" /><el-table-column prop="name" label="名称" min-width="180" /><el-table-column prop="status_label" label="状态" width="100" /><el-table-column label="正式需求" width="110"><template #default="{ row }">{{ row.requirement_revisions?.length || 0 }}</template></el-table-column></el-table></div></el-tab-pane>
      <el-tab-pane label="索引状态" name="search"><div class="section-panel"><div class="section-head"><div><h2>项目索引</h2><p>检查 OpenSearch 连接或重建当前项目索引。</p></div></div><div class="health-panel"><strong>OpenSearch</strong><span :class="searchHealth.ok ? 'health-ok' : 'health-error'">{{ searchHealth.ok ? '连接正常' : (searchHealth.detail || '未检查') }}</span><el-button :icon="Refresh" @click="checkSearchHealth">检查</el-button><el-button type="primary" @click="rebuildIndex">重建项目索引</el-button></div></div></el-tab-pane>
    </el-tabs>

    <el-dialog v-model="projectDialogVisible" title="编辑项目" width="560px"><el-alert title="保存后生成待确认稿，不会立即替换当前正式项目配置。" type="info" :closable="false" show-icon /><el-form ref="projectFormRef" :model="projectForm" :rules="projectRules" label-width="96px" class="dialog-form"><el-form-item label="项目名称" prop="name"><el-input v-model="projectForm.name" /></el-form-item><el-form-item label="项目编码" prop="code"><el-input v-model="projectForm.code" /></el-form-item><el-form-item label="负责人"><el-input v-model="projectForm.owner" /></el-form-item><el-form-item label="状态" prop="status"><el-radio-group v-model="projectForm.status"><el-radio-button label="active">启用</el-radio-button><el-radio-button label="inactive">停用</el-radio-button></el-radio-group></el-form-item><el-form-item label="描述"><el-input v-model="projectForm.description" type="textarea" :rows="3" /></el-form-item></el-form><template #footer><el-button @click="projectDialogVisible = false">取消</el-button><el-button type="primary" :loading="savingProject" @click="saveProjectDraft">保存待确认稿</el-button></template></el-dialog>

    <el-dialog v-model="moduleDialogVisible" :title="moduleForm.id ? '编辑正式模块' : '新增正式模块'" width="620px"><el-alert v-if="moduleForm.id" title="编辑内容保存为待确认稿，确认前当前模块及其业务引用保持不变。" type="info" :closable="false" show-icon /><el-form ref="moduleFormRef" :model="moduleForm" :rules="moduleRules" label-width="100px" class="dialog-form"><el-form-item label="模块名称" prop="name"><el-input v-model="moduleForm.name" /></el-form-item><el-form-item label="模块编码" prop="code"><el-input v-model="moduleForm.code" /></el-form-item><el-form-item label="上级模块"><el-tree-select v-model="moduleForm.parent" :data="moduleSelectTree" node-key="id" :props="{ label: 'name', children: 'children', disabled: 'disabled' }" check-strictly clearable default-expand-all placeholder="不选择则为根模块" /></el-form-item><el-form-item label="排序号" prop="sort_order"><el-input-number v-model="moduleForm.sort_order" :min="0" :step="1" /></el-form-item><el-form-item label="状态" prop="status"><el-radio-group v-model="moduleForm.status"><el-radio-button label="active">启用</el-radio-button><el-radio-button label="inactive">停用</el-radio-button></el-radio-group></el-form-item><el-form-item label="模块说明"><el-input v-model="moduleForm.description" type="textarea" :rows="3" /></el-form-item></el-form><template #footer><el-button @click="moduleDialogVisible = false">取消</el-button><el-button type="primary" :loading="moduleSaving" @click="saveModule">{{ moduleForm.id ? '保存待确认稿' : '创建并生效' }}</el-button></template></el-dialog>

    <el-dialog v-model="knowledgeDialogVisible" title="新增项目知识" width="min(680px, 92vw)" class="knowledge-dialog" destroy-on-close :close-on-click-modal="false">
      <el-alert title="新建内容先保存为候选修订，人工确认后才成为正式项目知识。" type="info" :closable="false" show-icon />
      <el-form ref="knowledgeFormRef" :model="knowledgeForm" :rules="knowledgeRules" label-width="92px" class="dialog-form">
        <div class="knowledge-form-grid">
          <el-form-item label="知识类别" prop="category"><el-select v-model="knowledgeForm.category"><el-option label="业务规则" value="business_rule" /><el-option label="业务流程" value="business_flow" /><el-option label="角色权限" value="role_permission" /><el-option label="模块边界" value="module_boundary" /><el-option label="术语" value="term" /><el-option label="非功能约束" value="non_functional" /><el-option label="外部依赖" value="external_dependency" /></el-select></el-form-item>
          <el-form-item label="适用模块"><el-tree-select v-model="knowledgeForm.module" :data="moduleTree" node-key="id" :props="{ label: 'name', children: 'children' }" check-strictly clearable default-expand-all placeholder="不选择则适用于全项目" /></el-form-item>
        </div>
        <el-form-item label="知识标题" prop="title"><el-input v-model="knowledgeForm.title" maxlength="200" show-word-limit placeholder="用一句话概括这条知识" /></el-form-item>
        <el-form-item label="知识正文" prop="content"><el-input v-model="knowledgeForm.content" type="textarea" :rows="10" resize="vertical" placeholder="完整描述业务规则、流程、边界或约束。支持多段文本。" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="knowledgeDialogVisible = false">取消</el-button><el-button type="primary" :loading="knowledgeSaving" @click="addKnowledge">保存候选知识</el-button></template>
    </el-dialog>

    <el-dialog v-model="knowledgeDetailVisible" :title="selectedKnowledge?.title || '知识详情'" width="min(720px, 92vw)" class="knowledge-detail-dialog">
      <div v-if="selectedKnowledge" class="knowledge-detail">
        <div class="knowledge-detail-meta"><span class="mono-code">{{ selectedKnowledge.code }}</span><span>{{ selectedKnowledge.category_label }}</span><span>{{ selectedKnowledge.module_name || '全项目' }}</span><span class="status-pill" :class="knowledgeStatusClass(selectedKnowledge)">{{ selectedKnowledge.current_revision?.status_label || '-' }}</span></div>
        <div class="knowledge-detail-content">{{ selectedKnowledge.current_revision?.content || '暂无正文' }}</div>
      </div>
      <template #footer><el-button @click="knowledgeDetailVisible = false">关闭</el-button><el-button v-if="selectedKnowledge?.current_revision?.status === 'candidate'" type="primary" :loading="confirmingKnowledgeId === selectedKnowledge.current_revision.id" @click="confirmKnowledge(selectedKnowledge, true)">确认候选</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Back, CircleCheck, Edit, Plus, Refresh } from '@element-plus/icons-vue'
import { confirmProject, getProject, updateProject } from '@/api/configuration'
import { confirmProjectKnowledgeRevision, confirmProjectModule, createProjectKnowledgeItem, createProjectModule, getProjectKnowledgeItems, getProjectModuleTree, getSearchHealth, reindexProject, updateProjectModule } from '@/api/projectKnowledge'
import { getRequirementVersions } from '@/api/requirements'
import { formatDate, normalizeListResponse } from './configurationHelpers'

const route = useRoute(); const router = useRouter(); const projectId = Number(route.params.id)
const project = ref(); const pageLoading = ref(false); const activeTab = ref('overview'); const moduleTree = ref([]); const knowledgeItems = ref([]); const projectVersions = ref([])
const projectDialogVisible = ref(false); const savingProject = ref(false); const confirmingProject = ref(false); const projectFormRef = ref(); const projectForm = reactive({ name: '', code: '', owner: '', description: '', status: 'active' })
const moduleDialogVisible = ref(false); const moduleSaving = ref(false); const confirmingModuleId = ref(null); const moduleFormRef = ref(); const moduleForm = reactive(emptyModuleForm())
const knowledgeDialogVisible = ref(false); const knowledgeDetailVisible = ref(false); const selectedKnowledge = ref(); const knowledgeSaving = ref(false); const knowledgeFormRef = ref(); const confirmingKnowledgeId = ref(null); const knowledgeForm = reactive(emptyKnowledgeForm()); const searchHealth = reactive({ ok: false, detail: '未检查' })
const projectRules = { name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }], code: [{ required: true, message: '请输入项目编码', trigger: 'blur' }], status: [{ required: true, message: '请选择状态', trigger: 'change' }] }
const moduleRules = { name: [{ required: true, message: '请输入模块名称', trigger: 'blur' }], code: [{ required: true, message: '请输入模块编码', trigger: 'blur' }], sort_order: [{ required: true, message: '请输入排序号', trigger: 'change' }], status: [{ required: true, message: '请选择状态', trigger: 'change' }] }
const knowledgeRules = { category: [{ required: true, message: '请选择知识类别', trigger: 'change' }], title: [{ required: true, message: '请输入知识标题', trigger: 'blur' }], content: [{ required: true, message: '请输入知识正文', trigger: 'blur' }] }
const moduleCount = computed(() => countNodes(moduleTree.value))
const moduleSelectTree = computed(() => {
  const disabledIds = new Set(moduleForm.id ? collectNodeIds(findNode(moduleTree.value, moduleForm.id)) : [])
  const clone = nodes => nodes.map(node => ({ ...node, disabled: disabledIds.has(node.id), children: clone(node.children || []) }))
  return clone(moduleTree.value)
})

function emptyModuleForm() { return { id: null, parent: null, code: '', name: '', description: '', status: 'active', sort_order: 0 } }
function emptyKnowledgeForm() { return { category: 'business_rule', module: null, title: '', content: '' } }
function countNodes(nodes) { return nodes.reduce((total, node) => total + 1 + countNodes(node.children || []), 0) }
function findNode(nodes, id) { for (const node of nodes) { if (node.id === id) return node; const found = findNode(node.children || [], id); if (found) return found } return null }
function collectNodeIds(node) { return node ? [node.id, ...(node.children || []).flatMap(collectNodeIds)] : [] }
function resetForm(target, values) { Object.keys(target).forEach(key => delete target[key]); Object.assign(target, values) }
function knowledgeStatusClass(row) { return row.current_revision?.status === 'confirmed' ? 'is-success' : row.current_revision?.status === 'candidate' ? 'is-warning' : 'is-muted' }

async function loadAll() { pageLoading.value = true; try { await Promise.all([loadProject(), loadModules(), loadKnowledge(), loadVersions()]) } finally { pageLoading.value = false } }
async function loadProject() { const { data } = await getProject(projectId); project.value = data }
async function loadModules() { const { data } = await getProjectModuleTree(projectId); moduleTree.value = data }
async function loadKnowledge() { const { data } = await getProjectKnowledgeItems({ project: projectId, page_size: 100 }); knowledgeItems.value = normalizeListResponse(data).results }
async function loadVersions() { const { data } = await getRequirementVersions({ project: projectId, page_size: 100 }); projectVersions.value = normalizeListResponse(data).results }
function openProjectDialog() { const source = project.value.pending_revision ? { ...project.value.pending_revision, status: project.value.pending_revision.project_status } : project.value; Object.assign(projectForm, { name: source.name, code: source.code, owner: source.owner || '', description: source.description || '', status: source.status }); projectDialogVisible.value = true }
async function saveProjectDraft() { await projectFormRef.value.validate(); savingProject.value = true; try { await updateProject(projectId, { ...projectForm }); ElMessage.success('项目待确认稿已保存'); projectDialogVisible.value = false; await loadProject() } finally { savingProject.value = false } }
async function confirmProjectChanges() { confirmingProject.value = true; try { await confirmProject(projectId); ElMessage.success('项目修改已确认并生效'); await loadProject() } finally { confirmingProject.value = false } }
function openModuleDialog(row = null, parent = null) { const source = row?.pending_revision ? { ...row.pending_revision, status: row.pending_revision.module_status } : row; resetForm(moduleForm, source ? { ...emptyModuleForm(), ...source, id: row.id, parent: source.parent } : { ...emptyModuleForm(), parent: parent?.id || null }); moduleDialogVisible.value = true }
async function saveModule() { await moduleFormRef.value.validate(); moduleSaving.value = true; try { const payload = { project: projectId, parent: moduleForm.parent || null, code: moduleForm.code, name: moduleForm.name, description: moduleForm.description, status: moduleForm.status, sort_order: moduleForm.sort_order }; if (moduleForm.id) await updateProjectModule(moduleForm.id, payload); else await createProjectModule(payload); ElMessage.success(moduleForm.id ? '模块待确认稿已保存' : '模块已创建并生效'); moduleDialogVisible.value = false; await loadModules() } finally { moduleSaving.value = false } }
async function confirmModuleChanges(row) { confirmingModuleId.value = row.id; try { await confirmProjectModule(row.id); ElMessage.success(`模块「${row.name}」修改已确认`); await loadModules() } finally { confirmingModuleId.value = null } }
async function openKnowledgeDialog() { resetForm(knowledgeForm, emptyKnowledgeForm()); knowledgeDialogVisible.value = true; await nextTick(); knowledgeFormRef.value?.clearValidate() }
function openKnowledgeDetail(row) { selectedKnowledge.value = row; knowledgeDetailVisible.value = true }
async function addKnowledge() { await knowledgeFormRef.value.validate(); knowledgeSaving.value = true; try { await createProjectKnowledgeItem({ project: projectId, code: `KN-${Date.now()}`, ...knowledgeForm, module: knowledgeForm.module || null }); resetForm(knowledgeForm, emptyKnowledgeForm()); knowledgeDialogVisible.value = false; ElMessage.success('知识候选已新增'); await loadKnowledge() } finally { knowledgeSaving.value = false } }
async function confirmKnowledge(row, closeDetail = false) { confirmingKnowledgeId.value = row.current_revision.id; try { await confirmProjectKnowledgeRevision(row.current_revision.id); ElMessage.success('知识修订已确认，正在进入索引队列'); if (closeDetail) knowledgeDetailVisible.value = false; await loadKnowledge() } finally { confirmingKnowledgeId.value = null } }
async function checkSearchHealth() { try { const { data } = await getSearchHealth(); Object.assign(searchHealth, data) } catch (error) { Object.assign(searchHealth, { ok: false, detail: error.response?.data?.detail || '连接失败' }) } }
async function rebuildIndex() { await reindexProject(projectId); ElMessage.success('项目索引重建任务已提交') }
onMounted(loadAll)
</script>

<style scoped>
.detail-page { width: min(1440px, 100%); }.page-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 14px; }.header-content { min-width: 0; }.back-button { height: 28px; margin: 0 0 6px -8px; padding: 0 8px; color: #64748b; }.back-button:hover { color: var(--el-color-primary); background: #f3f7fc; }.title-line { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; min-width: 0; }h1, h2, .section-head p { margin: 0; }h1 { min-width: 0; color: #172033; font-size: 24px; font-weight: 650; line-height: 1.25; overflow-wrap: anywhere; }.project-code { display: inline-flex; align-items: center; height: 24px; padding: 0 8px; border: 1px solid #e2e8f0; border-radius: 5px; background: #f8fafc; }.refresh-button { flex: 0 0 auto; }.detail-tabs { padding: 0 14px 14px; border: 1px solid #e6ebf2; border-radius: 8px; background: #fff; }.section-panel { margin-top: 4px; border: 1px solid #e6ebf2; border-radius: 8px; background: #fff; overflow: hidden; }.section-panel + .section-panel { margin-top: 12px; }.pending-panel { border-color: #fde68a; }.section-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 14px; border-bottom: 1px solid #edf1f6; }.section-head h2 { color: #273248; font-size: 17px; font-weight: 650; }.section-head p { margin-top: 4px; color: #64748b; font-size: 13px; }.head-actions { display: flex; gap: 8px; }.project-descriptions, .pending-panel :deep(.el-descriptions) { padding: 14px; }.module-tree { padding: 6px 14px 14px; }.module-tree :deep(.el-tree-node__content) { height: 44px; border-bottom: 1px solid #f1f4f8; }.module-node { display: flex; align-items: center; justify-content: space-between; gap: 12px; width: calc(100% - 8px); min-width: 0; }.module-main { display: flex; align-items: center; gap: 8px; min-width: 0; }.module-description { color: #8490a3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.node-actions { display: flex; flex: 0 0 auto; }.knowledge-actions { display: inline-flex; gap: 4px; white-space: nowrap; }.knowledge-actions .el-button { margin-left: 0; }.knowledge-cards { display: none; }.knowledge-card { padding: 14px; border-bottom: 1px solid #edf1f6; }.knowledge-card:last-child { border-bottom: 0; }.knowledge-card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }.knowledge-card-head strong { color: #273248; font-size: 15px; line-height: 1.45; }.knowledge-meta { display: flex; flex-wrap: wrap; gap: 6px 10px; margin-top: 5px; color: #64748b; font-size: 12px; }.knowledge-content, .knowledge-detail-content { color: #334155; font-size: 14px; line-height: 1.75; white-space: pre-wrap; overflow-wrap: anywhere; }.knowledge-content { margin-top: 12px; padding: 12px; border: 1px solid #edf1f6; border-radius: 6px; background: #f8fafc; }.knowledge-card-actions { display: flex; justify-content: flex-end; gap: 4px; margin-top: 8px; }.knowledge-card-actions .el-button { margin-left: 0; }.knowledge-form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }.knowledge-detail-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; padding-bottom: 14px; border-bottom: 1px solid #edf1f6; color: #64748b; font-size: 13px; }.knowledge-detail-content { min-height: 180px; margin-top: 14px; padding: 16px; border: 1px solid #e6ebf2; border-radius: 8px; background: #fbfcfe; }.health-panel { display: flex; align-items: center; gap: 12px; padding: 18px; background: #f8fafc; }.health-ok { color: #047857; }.health-error { color: #b91c1c; }.dialog-form { margin-top: 18px; }:deep(.el-select), :deep(.el-input-number) { width: 100%; }.dense-table { --el-table-border-color: #edf1f6; --el-table-header-bg-color: #fbfcfe; --el-table-header-text-color: #6b7280; font-size: 14px; }.dense-table :deep(.el-table__header th) { height: 42px; padding: 0; font-weight: 650; }.dense-table :deep(.el-table__cell) { padding: 8px 0; }.mono-code { color: #475569; font-family: "SFMono-Regular", Consolas, monospace; font-size: 13px; }.status-pill { display: inline-flex; align-items: center; height: 22px; padding: 0 8px; border-radius: 999px; font-size: 12px; white-space: nowrap; }.is-success { color: #047857; background: #ecfdf5; border: 1px solid #bbf7d0; }.is-muted { color: #64748b; background: #f8fafc; border: 1px solid #e2e8f0; }.is-warning { color: #9a6700; background: #fffbeb; border: 1px solid #fde68a; }
@media (max-width: 900px) { .page-header { align-items: center; }.page-header .refresh-button { width: 32px; height: 32px; padding: 0; }.page-header .refresh-button :deep(span) { display: none; }.section-head, .module-node { align-items: stretch; flex-direction: column; }.section-head > .el-button { width: 100%; }.module-node { padding: 7px 0; }.module-main { flex-wrap: wrap; }.module-tree :deep(.el-tree-node__content) { height: auto; min-height: 52px; }.node-actions { justify-content: flex-end; } }
@media (max-width: 760px) { .knowledge-table { display: none; }.knowledge-cards { display: block; }.knowledge-form-grid { grid-template-columns: 1fr; gap: 0; } }
@media (max-width: 560px) { .page-header { gap: 8px; }.back-button { margin-bottom: 4px; }.title-line { gap: 6px; }h1 { font-size: 21px; }.project-code { max-width: 100%; overflow: hidden; text-overflow: ellipsis; }.head-actions { width: 100%; }.head-actions .el-button { flex: 1; margin-left: 0; }.knowledge-card-head { flex-direction: column; }.knowledge-detail-content { min-height: 120px; padding: 12px; } }
</style>
