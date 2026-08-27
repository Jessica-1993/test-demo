<template>
  <section class="testcase-page">
    <header class="page-head">
      <div class="page-title">
        <span class="eyebrow">需求用例中心</span>
        <h1>用例生成</h1>
        <p>选择版本下的详细需求创建生成任务，并追踪后台执行结果。</p>
      </div>
      <el-select v-model="selectedProject" placeholder="选择项目" class="project-select" @change="handleProjectChange">
        <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
      </el-select>
    </header>

    <section class="workbench-panel">
      <el-tabs v-model="activeTab" class="generation-tabs">
        <el-tab-pane label="选择需求" name="requirements">
          <div class="workflow-strip" aria-label="生成链路">
            <div class="workflow-step active">
              <span>1</span>
              <strong>选择版本</strong>
            </div>
            <div class="workflow-step">
              <span>2</span>
              <strong>勾选需求</strong>
            </div>
            <div class="workflow-step">
              <span>3</span>
              <strong>创建任务</strong>
            </div>
          </div>

          <div class="control-bar">
            <el-select v-model="selectedVersion" placeholder="选择版本" class="version-select" @change="handleVersionChange">
              <el-option v-for="version in versions" :key="version.id" :label="`${version.version_no} ${version.name}`" :value="version.id" />
            </el-select>
            <el-input
              v-model="requirementKeyword"
              placeholder="搜索待生成详细需求"
              clearable
              class="requirement-search"
              @keyup.enter="resetRequirementPage"
              @clear="resetRequirementPage"
            />
            <el-button :icon="Search" @click="resetRequirementPage">搜索</el-button>
            <span class="selection-count" :class="{ active: selectedRows.length }">已选 {{ selectedRows.length }} 项</span>
            <el-button type="primary" :icon="MagicStick" :loading="generating" :disabled="!selectedRows.length" @click="startGeneration">
              一键生成
            </el-button>
          </div>

          <el-table
            ref="requirementTableRef"
            :data="requirementItems"
            v-loading="loadingRequirements"
            class="dense-table generation-table"
            @row-click="openRequirementDetail"
            @selection-change="selectedRows = $event"
          >
            <el-table-column type="selection" width="44" />
            <el-table-column prop="requirement_no" label="编号" width="120">
              <template #default="{ row }">
                <span class="mono-code">{{ row.requirement_no }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="需求标题" min-width="260" show-overflow-tooltip />
            <el-table-column prop="module" label="模块" width="140" show-overflow-tooltip />
            <el-table-column label="内容" width="150">
              <template #default="{ row }">
                <span>{{ blockCount(row, 'text') }} 文本</span> · <span>{{ blockCount(row, 'table') }} 表</span> · <span>{{ blockCount(row, 'image') }} 图</span>
              </template>
            </el-table-column>
            <el-table-column prop="priority_label" label="优先级" width="90">
              <template #default="{ row }">
                <span class="text-badge">{{ row.priority_label || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="整合稿" width="96">
              <template #default="{ row }">
                <span class="status-pill" :class="integrationStatusClass(row.integration_draft?.status)">
                  {{ row.integration_draft?.status_label || '未整合' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="92" fixed="right" align="center">
              <template #default="{ row }">
                <div class="action-cell">
                  <el-tooltip content="查看 / 整合">
                    <el-button text type="primary" :icon="View" @click.stop="openRequirementDetail(row)">查看</el-button>
                  </el-tooltip>
                </div>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-bar">
            <el-pagination
              v-model:current-page="requirementPagination.page"
              v-model:page-size="requirementPagination.pageSize"
              :page-sizes="[10, 20, 50]"
              :total="requirementPagination.total"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="handleRequirementSizeChange"
              @current-change="loadRequirementItems"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane label="生成任务" name="tasks">
          <div class="section-head">
            <div>
              <h2>生成任务</h2>
              <p>共 {{ taskPagination.total }} 条任务，展开可查看每条需求的执行日志。</p>
            </div>
            <el-button :icon="Refresh" @click="loadTasks">刷新</el-button>
          </div>

          <el-table :data="tasks" v-loading="loadingTasks" class="dense-table task-table">
            <el-table-column type="expand" width="44">
              <template #default="{ row }">
                <div class="task-log">
                  <el-empty v-if="!row.generation_log?.length" description="暂无执行日志" />
                  <el-timeline v-else>
                    <el-timeline-item
                      v-for="(log, index) in row.generation_log"
                      :key="`${row.id}-${log.requirement_item || index}-${index}`"
                      :type="logStatusType(log.status)"
                      :hollow="log.status === 'running'"
                    >
                      <div class="log-title">
                        <span class="mono-code">{{ log.requirement_no || `步骤 ${index + 1}` }}</span>
                        <span class="status-pill" :class="statusClass(log.status)">{{ logStatusLabel(log.status) }}</span>
                        <span v-if="log.stage" class="text-badge">{{ log.stage }}</span>
                      </div>
                      <p class="log-message">{{ log.message || '-' }}</p>
                      <div class="log-meta">
                        <span v-if="log.case_count">用例数：{{ log.case_count }}</span>
                        <span v-if="log.writer_role">生成角色：{{ log.writer_role }}</span>
                        <span v-if="log.writer_model">生成模型：{{ log.writer_model }}</span>
                        <span v-if="log.reviewer_role">评审角色：{{ log.reviewer_role }}</span>
                        <span v-if="log.reviewer_model">评审模型：{{ log.reviewer_model }}</span>
                        <span v-if="log.retried">已重试</span>
                      </div>
                    </el-timeline-item>
                  </el-timeline>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="task_no" label="任务编号" min-width="210">
              <template #default="{ row }">
                <span class="mono-code">{{ row.task_no }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="version_name" label="版本" min-width="130" show-overflow-tooltip />
            <el-table-column prop="status_label" label="状态" width="110">
              <template #default="{ row }">
                <span class="status-pill" :class="statusClass(row.status)">{{ row.status_label }}</span>
              </template>
            </el-table-column>
            <el-table-column label="进度" width="220">
              <template #default="{ row }">
                <div class="progress-cell">
                  <el-progress :percentage="row.progress" :stroke-width="6" :show-text="false" />
                  <span>{{ row.progress }}%</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="total_count" label="需求数" width="82" align="right" />
            <el-table-column prop="success_count" label="成功" width="74" align="right" />
            <el-table-column prop="failed_count" label="失败" width="74" align="right">
              <template #default="{ row }">
                <span :class="{ 'error-count': row.failed_count }">{{ row.failed_count }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="error_message" label="错误摘要" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="error-summary">{{ row.error_message || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="92" fixed="right" align="center">
              <template #default="{ row }">
                <div class="action-cell">
                  <el-tooltip content="错误详情"><el-button text type="danger" :icon="Warning" :disabled="!row.error_info?.code" @click="showTaskError(row)">错误详情</el-button></el-tooltip>
                  <el-tooltip content="重新发起"><el-button text type="primary" :icon="RefreshRight" :disabled="!['failed','partial_success'].includes(row.status)" @click="retryTask(row)">重新发起</el-button></el-tooltip>
                </div>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-bar">
            <el-pagination
              v-model:current-page="taskPagination.page"
              v-model:page-size="taskPagination.pageSize"
              :page-sizes="[8, 10, 20, 50]"
              :total="taskPagination.total"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="handleTaskSizeChange"
              @current-change="loadTasks"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </section>

    <el-drawer v-model="detailVisible" size="min(1180px, 96vw)" title="需求详情 / 整合稿">
      <template v-if="detailItem">
        <div class="detail-meta">
          <div><span>编号</span><strong class="mono-code">{{ detailItem.requirement_no }}</strong></div>
          <div><span>正式模块</span><strong>{{ formalModulePaths(detailItem) }}</strong></div>
          <div><span>优先级</span><strong>{{ detailItem.priority_label || '-' }}</strong></div>
          <div><span>来源</span><strong>{{ detailItem.document_title || '-' }}</strong></div>
        </div>

        <div class="compare-workbench">
          <section class="compare-pane source-pane">
            <div class="pane-head">
              <div>
                <h2>需求原稿</h2>
                <p>原始字段和来源内容块，只读核对。</p>
              </div>
            </div>
            <div class="pane-body">
              <section class="source-section">
                <h3>{{ detailItem.title || '暂无需求标题' }}</h3>
                <div class="source-kv">
                  <span>模块</span><strong>{{ detailItem.module || '-' }}</strong>
                  <span>优先级</span><strong>{{ detailItem.priority_label || '-' }}</strong>
                </div>
                <p class="full-text">{{ detailItem.description || '暂无需求描述' }}</p>
                <p v-if="detailItem.acceptance_criteria" class="full-text"><strong>验收标准：</strong>{{ detailItem.acceptance_criteria }}</p>
                <p v-if="detailItem.supplementary_description" class="full-text"><strong>补充描述：</strong>{{ detailItem.supplementary_description }}</p>
              </section>

              <div class="content-head source-block-head"><h2>来源内容块</h2><span>{{ detailItem.content_blocks?.length || 0 }} 个来源内容</span></div>
              <div v-if="!detailContentGroups.length" class="empty-content">暂无来源内容块</div>
              <div v-for="group in detailContentGroups" :key="group.id" class="content-block" :class="{ 'is-section': group.kind === 'section' }">
                <div class="block-head">
                  <div class="group-title"><span v-if="group.kind === 'section'" class="level-mark">H{{ group.headingLevel }}</span><strong>{{ group.title }}</strong></div>
                </div>
                <div class="group-body">
                  <template v-for="block in group.blocks" :key="block.id">
                    <p v-if="block.block_type === 'text'" class="block-text">{{ block.text }}</p>
                    <div v-else-if="block.block_type === 'table'" class="table-scroll">
                      <div v-if="block.table_data?.html" class="source-table" v-html="block.table_data.html"></div>
                      <table v-else>
                        <tbody>
                          <tr v-for="(row, rowIndex) in block.table_data?.rows || []" :key="rowIndex">
                            <component :is="rowIndex === 0 ? 'th' : 'td'" v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell }}</component>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <el-image v-else-if="block.block_type === 'image'" class="document-image" :src="block.image_url" :preview-src-list="[block.image_url]" fit="contain" preview-teleported />
                  </template>
                </div>
              </div>
            </div>
          </section>

          <section class="compare-pane draft-pane">
            <div class="pane-head">
              <div>
                <h2>整合稿</h2>
                <p>该版本已发布，正式需求上下文只读。</p>
              </div>
              <el-tag type="success" effect="plain">已通过整合审核</el-tag>
            </div>
            <div class="pane-body">
              <el-alert v-if="integrationForm.status === 'failed'" type="error" :closable="false" :title="integrationForm.error_message || '整合失败'" />
              <el-empty v-if="!integrationForm.id" description="暂无整合稿，可先解析整合" />
              <el-form v-else label-position="top" class="integration-form">
                <div class="form-grid">
                  <el-form-item label="正式模块"><el-input v-model="integrationForm.module_paths" readonly /></el-form-item>
                  <el-form-item label="整合标题"><el-input v-model="integrationForm.title" readonly /></el-form-item>
                </div>
                <el-form-item label="整合描述"><el-input v-model="integrationForm.description" type="textarea" :rows="7" readonly /></el-form-item>
                <el-form-item label="验收标准"><el-input v-model="integrationForm.acceptance_criteria" type="textarea" :rows="4" readonly /></el-form-item>
                <el-form-item label="补充描述"><el-input v-model="integrationForm.supplementary_description" type="textarea" :rows="4" readonly /></el-form-item>
                <el-form-item label="来源摘要"><el-input v-model="integrationForm.source_summary" type="textarea" :rows="4" readonly /></el-form-item>
              </el-form>
            </div>
          </section>
        </div>
      </template>
    </el-drawer>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, RefreshRight, Search, View, Warning } from '@element-plus/icons-vue'

import {
  generateTestCases,
  getGenerationTasks,
  getRequirementItems,
  getRequirementVersions,
  retryGenerationTask,
} from '@/api/requirements'
import { showErrorInfo } from '@/utils/errors'
import { useRequirementProjects } from './useRequirementProjects'

const { projects, selectedProject, loadProjects } = useRequirementProjects()
const activeTab = ref('requirements')
const versions = ref([])
const selectedVersion = ref()
const requirementItems = ref([])
const selectedRows = ref([])
const tasks = ref([])
const requirementKeyword = ref('')
const loadingRequirements = ref(false)
const loadingTasks = ref(false)
const generating = ref(false)
const detailVisible = ref(false)
const detailItem = ref(null)
const requirementTableRef = ref()
const requirementPagination = reactive({ page: 1, pageSize: 10, total: 0 })
const taskPagination = reactive({ page: 1, pageSize: 8, total: 0 })
const integrationForm = reactive(emptyIntegrationForm())
const detailContentGroups = computed(() => groupContentBlocks(detailItem.value?.content_blocks || []))
let pollTimer

function emptyIntegrationForm() {
  return {
    id: undefined,
    status: '',
    title: '',
    module: '',
    module_paths: '',
    description: '',
    acceptance_criteria: '',
    supplementary_description: '',
    source_summary: '',
    error_message: '',
  }
}

function resetIntegrationForm(data = emptyIntegrationForm()) {
  Object.assign(integrationForm, emptyIntegrationForm(), data, {
    module_paths: data.formal_modules?.map(module => module.path).join('；') || '',
  })
}

function formalModulePaths(item) {
  return item?.formal_modules?.map(module => module.path).join('；') || '-'
}

function normalizeListResponse(data) {
  if (Array.isArray(data)) return { results: data, total: data.length }
  return { results: data.results || [], total: data.count || 0 }
}

function clearRequirementSelection() {
  selectedRows.value = []
  nextTick(() => requirementTableRef.value?.clearSelection())
}

async function loadVersions() {
  versions.value = []
  selectedVersion.value = undefined
  if (!selectedProject.value) return
  const { data } = await getRequirementVersions({ project: selectedProject.value, status: 'published', page_size: 100 })
  versions.value = normalizeListResponse(data).results
  selectedVersion.value = versions.value[0]?.id
}

async function loadRequirementItems() {
  requirementItems.value = []
  clearRequirementSelection()
  if (!selectedProject.value || !selectedVersion.value) {
    requirementPagination.total = 0
    return
  }
  loadingRequirements.value = true
  try {
    const params = {
      project: selectedProject.value,
      version: selectedVersion.value,
      page: requirementPagination.page,
      page_size: requirementPagination.pageSize,
    }
    if (requirementKeyword.value) params.search = requirementKeyword.value
    const { data } = await getRequirementItems(params)
    const payload = normalizeListResponse(data)
    requirementItems.value = payload.results
    requirementPagination.total = payload.total
  } finally {
    loadingRequirements.value = false
  }
}

async function loadTasks() {
  tasks.value = []
  if (!selectedProject.value) {
    taskPagination.total = 0
    return
  }
  loadingTasks.value = true
  try {
    const params = {
      project: selectedProject.value,
      page: taskPagination.page,
      page_size: taskPagination.pageSize,
    }
    if (selectedVersion.value) params.version = selectedVersion.value
    const { data } = await getGenerationTasks(params)
    const payload = normalizeListResponse(data)
    tasks.value = payload.results
    taskPagination.total = payload.total
  } finally {
    loadingTasks.value = false
  }
}

async function handleProjectChange() {
  requirementPagination.page = 1
  taskPagination.page = 1
  await loadVersions()
  await Promise.all([loadRequirementItems(), loadTasks()])
}

async function handleVersionChange() {
  requirementPagination.page = 1
  taskPagination.page = 1
  await Promise.all([loadRequirementItems(), loadTasks()])
}

async function resetRequirementPage() {
  requirementPagination.page = 1
  await loadRequirementItems()
}

async function handleRequirementSizeChange() {
  requirementPagination.page = 1
  await loadRequirementItems()
}

async function handleTaskSizeChange() {
  taskPagination.page = 1
  await loadTasks()
}

async function startGeneration() {
  if (generating.value) return
  generating.value = true
  try {
    await generateTestCases({
      project: selectedProject.value,
      version: selectedVersion.value,
      requirement_items: selectedRows.value.map((item) => item.id),
    })
    ElMessage.success('已创建用例生成任务')
    activeTab.value = 'tasks'
    taskPagination.page = 1
    await loadTasks()
    startPolling()
  } catch (_error) {
    // API 错误由统一错误中心展示。
  } finally {
    generating.value = false
  }
}

function showTaskError(row) {
  showErrorInfo(row.error_info, {
    forceDialog: true,
    actionHandler: ['failed', 'partial_success'].includes(row.status) ? () => retryTask(row) : null,
  })
}

async function retryTask(row) {
  try {
    await ElMessageBox.confirm(`将复制 ${row.task_no} 的失败项创建新任务，原记录会保留。`, '重新发起生成任务', { type: 'warning' })
    await retryGenerationTask(row.id)
    ElMessage.success('已创建重试任务')
    await loadTasks()
    startPolling()
  } catch (_error) {
    // 取消操作或 API 错误由统一错误中心处理。
  }
}

function openRequirementDetail(row) {
  detailItem.value = row
  resetIntegrationForm(row.integration_draft || {})
  detailVisible.value = true
}

function blockCount(row, type) {
  return row.content_blocks?.filter((block) => block.block_type === type).length || 0
}

function typeLabel(type) {
  return { text: '文本', table: '表格', image: '图片' }[type] || type
}

function groupContentBlocks(blocks) {
  const groups = []
  let section = null
  for (const block of blocks) {
    if (block.block_type === 'text' && block.heading_level >= 4) {
      section = {
        id: `section-${block.id}`,
        kind: 'section',
        title: block.text,
        headingLevel: block.heading_level,
        blocks: [],
      }
      groups.push(section)
      continue
    }
    if (section) {
      section.blocks.push(block)
    } else {
      groups.push({ id: `block-${block.id}`, kind: 'standalone', title: typeLabel(block.block_type), blocks: [block] })
    }
  }
  return groups
}

function integrationStatusClass(status) {
  if (status === 'completed') return 'is-success'
  if (status === 'failed') return 'is-danger'
  if (status === 'pending') return 'is-running'
  return 'is-muted'
}

function startPolling() {
  if (pollTimer) return
  pollTimer = window.setInterval(async () => {
    await loadTasks()
    if (!tasks.value.some((task) => ['pending', 'running'].includes(task.status))) {
      window.clearInterval(pollTimer)
      pollTimer = undefined
    }
  }, 4000)
}

function logStatusType(status) {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running') return 'primary'
  return 'info'
}

function logStatusLabel(status) {
  if (status === 'success') return '成功'
  if (status === 'failed') return '失败'
  if (status === 'running') return '执行中'
  return '记录'
}

function statusClass(status) {
  if (status === 'success' || status === 'completed') return 'is-success'
  if (status === 'failed') return 'is-danger'
  if (status === 'running') return 'is-running'
  return 'is-muted'
}

onMounted(async () => {
  await loadProjects()
  await handleProjectChange()
  if (tasks.value.some((task) => ['pending', 'running'].includes(task.status))) startPolling()
})

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer)
})
</script>

<style scoped>
.testcase-page {
  width: min(1440px, 100%);
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 16px;
}

.page-title {
  min-width: 0;
}

.eyebrow {
  display: block;
  margin-bottom: 6px;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.2;
}

h1,
h2,
p {
  margin: 0;
}

h1 {
  margin-bottom: 6px;
  color: #172033;
  font-size: 24px;
  font-weight: 650;
  line-height: 1.25;
}

h2 {
  color: #172033;
  font-size: 17px;
  font-weight: 650;
  line-height: 1.35;
}

h3 {
  margin: 0 0 8px;
  color: #172033;
  font-size: 15px;
  font-weight: 650;
  line-height: 1.45;
}

p {
  color: #64748b;
  font-size: 14px;
  line-height: 1.6;
}

.project-select {
  flex: 0 0 240px;
}

.workbench-panel {
  border: 1px solid #e6ebf2;
  border-radius: 8px;
  background: #ffffff;
}

.generation-tabs :deep(.el-tabs__header) {
  margin: 0;
  padding: 0 14px;
  border-bottom: 1px solid #edf1f6;
}

.generation-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.workflow-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border-bottom: 1px solid #edf1f6;
  background: #fbfcfe;
}

.workflow-step {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  padding: 0 14px;
  color: #64748b;
  border-right: 1px solid #edf1f6;
  font-size: 13px;
}

.workflow-step:last-child {
  border-right: 0;
}

.workflow-step span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  color: #64748b;
  background: #eef2f7;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.workflow-step.active {
  color: #2563eb;
}

.workflow-step.active span {
  color: #ffffff;
  background: #2563eb;
}

.control-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  border-bottom: 1px solid #edf1f6;
}

.version-select {
  flex: 0 0 240px;
}

.requirement-search {
  flex: 1 1 320px;
  max-width: 420px;
}

.selection-count {
  display: inline-flex;
  align-items: center;
  height: 32px;
  padding: 0 10px;
  color: #64748b;
  background: #f6f8fb;
  border: 1px solid #e6ebf2;
  border-radius: 6px;
  font-size: 13px;
  white-space: nowrap;
}

.selection-count.active {
  color: #1d4ed8;
  border-color: #bfdbfe;
  background: #eff6ff;
}

.section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  min-height: 58px;
  padding: 12px 14px;
  border-bottom: 1px solid #edf1f6;
}

.dense-table {
  --el-table-border-color: #edf1f6;
  --el-table-header-bg-color: #fbfcfe;
  --el-table-header-text-color: #6b7280;
  --el-table-row-hover-bg-color: #f8fbff;
  width: 100%;
  color: #2f3a4c;
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

.dense-table :deep(.cell) {
  line-height: 1.45;
}

.generation-table,
.task-table {
  border-radius: 0 0 8px 8px;
}

.mono-code {
  color: #374151;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.text-badge,
.status-pill {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
}

.text-badge {
  color: #475569;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
}

.status-pill.is-success {
  color: #047857;
  background: #ecfdf5;
  border: 1px solid #bbf7d0;
}

.status-pill.is-danger {
  color: #b91c1c;
  background: #fef2f2;
  border: 1px solid #fecaca;
}

.status-pill.is-running {
  color: #1d4ed8;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
}

.status-pill.is-muted {
  color: #64748b;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.progress-cell {
  display: grid;
  grid-template-columns: minmax(80px, 1fr) 44px;
  gap: 8px;
  align-items: center;
}

.progress-cell span {
  color: #64748b;
  font-size: 13px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.error-count,
.error-summary {
  color: #b91c1c;
}

.task-log {
  padding: 10px 18px 6px;
  background: #fbfcfe;
}

.log-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 650;
}

.log-message {
  margin: 6px 0;
  color: #374151;
}

.log-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  color: #64748b;
  font-size: 12px;
}

.action-cell,
.content-head,
.detail-actions,
.group-title {
  display: flex;
  align-items: center;
}

.action-cell {
  justify-content: center;
  gap: 4px;
  white-space: nowrap;
}

.action-cell :deep(.el-button) {
  width: 28px;
  height: 28px;
  margin-left: 0;
  padding: 0;
  border-radius: 6px;
}

.action-cell :deep(.el-button span) {
  display: none;
}

.detail-meta {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 14px;
}

.detail-meta div {
  min-width: 0;
  padding: 10px;
  border: 1px solid #e6ebf2;
  border-radius: 6px;
  background: #fbfcfe;
}

.detail-meta span {
  display: block;
  margin-bottom: 4px;
  color: #64748b;
  font-size: 12px;
}

.detail-meta strong {
  color: #172033;
  font-size: 13px;
}

.compare-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
  min-height: 0;
}

.compare-pane {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: min(680px, calc(100vh - 170px));
  overflow: hidden;
  border: 1px solid #e6ebf2;
  border-radius: 8px;
  background: #ffffff;
}

.pane-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  min-height: 58px;
  padding: 12px 14px;
  border-bottom: 1px solid #edf1f6;
  background: #fbfcfe;
}

.pane-body {
  min-height: 0;
  overflow: auto;
  padding: 14px;
}

.source-section {
  margin-bottom: 14px;
  padding-bottom: 14px;
  border-bottom: 1px solid #edf1f6;
}

.source-kv {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto minmax(0, 1fr);
  gap: 6px 8px;
  margin-bottom: 8px;
  color: #475569;
  font-size: 13px;
}

.source-kv span {
  color: #64748b;
}

.content-head {
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.source-block-head {
  margin-top: 2px;
}

.content-head span {
  color: #64748b;
  font-size: 12px;
}

.detail-actions {
  gap: 8px;
}

.integration-form {
  margin-top: 12px;
}

.form-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
  gap: 12px;
}

.full-text,
.block-text {
  color: #334155;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.full-text {
  margin-top: 8px;
}

.empty-content {
  padding: 28px;
  color: #94a3b8;
  text-align: center;
}

.content-block {
  margin-bottom: 12px;
  overflow: hidden;
  border: 1px solid #dce4ee;
  border-radius: 6px;
}

.content-block.is-section {
  border-left: 3px solid #409eff;
}

.block-head {
  min-height: 42px;
  padding: 0 10px;
  background: #f8fafc;
}

.group-title {
  gap: 8px;
  color: #25324a;
  font-size: 14px;
}

.level-mark {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 7px;
  color: #2563eb;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
}

.group-body > :not(:last-child) {
  border-bottom: 1px solid #edf1f6;
}

.block-text {
  padding: 14px 16px;
}

.table-scroll {
  overflow: auto;
  padding: 12px 16px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th,
td {
  padding: 8px;
  border: 1px solid #dbe3ec;
  text-align: left;
}

th {
  background: #f1f5f9;
}

.source-table :deep(table) {
  width: 100%;
  border-collapse: collapse;
}

.source-table :deep(th),
.source-table :deep(td) {
  padding: 8px;
  border: 1px solid #dbe3ec;
  text-align: left;
}

.source-table :deep(th) {
  background: #f1f5f9;
}

.document-image {
  width: 100%;
  height: 360px;
  background: #f8fafc;
}

.pagination-bar {
  display: flex;
  justify-content: flex-end;
  padding: 12px 14px;
  border-top: 1px solid #edf1f6;
}

@media (max-width: 980px) {
  .page-head,
  .section-head,
  .control-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .project-select,
  .version-select,
  .requirement-search {
    width: 100%;
    max-width: none;
    flex-basis: auto;
  }

  .workflow-strip {
    grid-template-columns: 1fr;
  }

  .detail-meta,
  .form-grid,
  .compare-workbench,
  .source-kv {
    grid-template-columns: 1fr;
  }

  .compare-pane {
    min-height: auto;
  }

  .source-pane {
    order: 2;
  }

  .draft-pane {
    order: 1;
  }

  .pane-head {
    align-items: stretch;
    flex-direction: column;
  }

  .content-head {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
