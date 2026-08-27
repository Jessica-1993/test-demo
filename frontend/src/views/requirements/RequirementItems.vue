<template>
  <section class="admin-page">
    <div class="page-head">
      <div class="page-title">
        <span class="eyebrow">需求用例中心</span>
        <h1>详细需求</h1>
        <p>维护从需求文档拆分出的详细需求，支持按标题、描述和来源内容搜索。</p>
      </div>
      <el-select v-model="selectedProject" placeholder="选择项目" class="project-select" @change="handleProjectChange">
        <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
      </el-select>
    </div>

    <section class="data-section">
    <div class="section-head">
      <div>
        <h2>需求列表</h2>
        <p>共 {{ itemPagination.total }} 条详细需求，支持维护来源定位与优先级。</p>
      </div>
      <div class="table-toolbar">
      <el-input v-model="itemKeyword" placeholder="搜索标题、描述、来源" clearable @keyup.enter="resetItemPage" @clear="resetItemPage" />
      <el-button :icon="Search" @click="resetItemPage">搜索</el-button>
      <el-button type="primary" :icon="Plus" :disabled="!documents.length" @click="openItemDialog()">新增需求</el-button>
      </div>
    </div>

    <el-table :data="items" v-loading="loadingItems" class="dense-table" @row-click="openDetailDrawer">
      <el-table-column prop="requirement_no" label="编号" width="120">
        <template #default="{ row }"><span class="mono-code">{{ row.requirement_no }}</span></template>
      </el-table-column>
      <el-table-column prop="title" label="需求标题" min-width="220" show-overflow-tooltip />
      <el-table-column prop="module" label="功能模块" width="130" />
      <el-table-column prop="document_title" label="来源文档" min-width="170" show-overflow-tooltip />
      <el-table-column label="内容" width="150">
        <template #default="{ row }">
          <span>{{ blockCount(row, 'text') }} 文本</span> · <span>{{ blockCount(row, 'table') }} 表</span> · <span>{{ blockCount(row, 'image') }} 图</span>
        </template>
      </el-table-column>
      <el-table-column prop="priority_label" label="优先级" width="90">
        <template #default="{ row }"><span class="text-badge">{{ row.priority_label || '-' }}</span></template>
      </el-table-column>
      <el-table-column label="操作" width="128" fixed="right" align="center">
        <template #default="{ row }">
          <div class="action-cell">
            <el-tooltip content="查看详情">
              <el-button text :icon="View" @click.stop="openDetailDrawer(row)">查看</el-button>
            </el-tooltip>
            <el-tooltip content="编辑">
              <el-button text type="primary" :icon="Edit" @click.stop="openItemDialog(row)">编辑</el-button>
            </el-tooltip>
            <el-tooltip content="删除">
              <el-button text type="danger" :icon="Delete" @click.stop="removeItem(row)">删除</el-button>
            </el-tooltip>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-bar">
      <el-pagination
        v-model:current-page="itemPagination.page"
        v-model:page-size="itemPagination.pageSize"
        :page-sizes="[10, 20, 50]"
        :total="itemPagination.total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleItemSizeChange"
        @current-change="loadItems"
      />
    </div>
    </section>

    <el-dialog v-model="itemDialogVisible" :title="editingItem?.id ? '编辑详细需求' : '新增详细需求'" width="min(860px, 92vw)">
      <el-form :model="itemForm" label-width="96px">
        <el-form-item label="来源文档">
          <el-select v-model="itemForm.document" placeholder="选择文档" :disabled="Boolean(editingItem?.id)">
            <el-option v-for="document in documents" :key="document.id" :label="document.title" :value="document.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="需求编号"><el-input v-model="itemForm.requirement_no" /></el-form-item>
        <el-form-item label="需求标题"><el-input v-model="itemForm.title" /></el-form-item>
        <el-form-item label="功能模块"><el-input v-model="itemForm.module" /></el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="itemForm.priority">
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item label="需求描述"><el-input v-model="itemForm.description" type="textarea" :rows="4" /></el-form-item>
        <el-form-item label="验收标准"><el-input v-model="itemForm.acceptance_criteria" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template v-if="editingItem?.id">
        <el-divider />
        <div class="content-head"><h2>内容块</h2><span>{{ editingItem.content_blocks?.length || 0 }} 个来源内容</span></div>
        <div v-if="!contentGroups.length" class="empty-content">暂无来源内容块</div>
        <div v-for="group in contentGroups" :key="group.id" class="content-block" :class="{ 'is-section': group.kind === 'section' }">
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
      </template>
      <template #footer>
        <el-button @click="itemDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingItem" @click="saveItem">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailDrawerVisible" size="min(820px, 92vw)" title="需求详情">
      <template v-if="detailItem">
        <div class="detail-meta">
          <div><span>编号</span><strong class="mono-code">{{ detailItem.requirement_no }}</strong></div>
          <div><span>模块</span><strong>{{ detailItem.module || '-' }}</strong></div>
          <div><span>优先级</span><strong>{{ detailItem.priority_label || '-' }}</strong></div>
          <div><span>来源</span><strong>{{ detailItem.document_title || '-' }}</strong></div>
        </div>
        <section class="detail-section">
          <h2>{{ detailItem.title }}</h2>
          <p class="full-text">{{ detailItem.description || '暂无需求描述' }}</p>
        </section>
        <section class="detail-section">
          <h2>验收标准</h2>
          <p class="full-text">{{ detailItem.acceptance_criteria || '暂无验收标准' }}</p>
        </section>
        <section v-if="detailItem.supplementary_description" class="detail-section">
          <h2>补充描述</h2>
          <p class="full-text">{{ detailItem.supplementary_description }}</p>
        </section>
        <el-divider />
        <div class="content-head"><h2>内容块</h2><span>{{ detailItem.content_blocks?.length || 0 }} 个来源内容</span></div>
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
      </template>
    </el-drawer>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit, Plus, Search, View } from '@element-plus/icons-vue'

import {
  createRequirementItem,
  deleteRequirementItem,
  getRequirementDocuments,
  getRequirementItems,
  updateRequirementItem,
} from '@/api/requirements'
import { useRequirementProjects } from './useRequirementProjects'

const { projects, selectedProject, loadProjects } = useRequirementProjects()
const documents = ref([])
const items = ref([])
const itemKeyword = ref('')
const loadingItems = ref(false)
const savingItem = ref(false)
const itemDialogVisible = ref(false)
const detailDrawerVisible = ref(false)
const editingItem = ref(null)
const detailItem = ref(null)
const itemForm = reactive(emptyItemForm())
const itemPagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
})
const contentGroups = computed(() => groupContentBlocks(editingItem.value?.content_blocks || []))
const detailContentGroups = computed(() => groupContentBlocks(detailItem.value?.content_blocks || []))

function emptyItemForm() {
  return {
    document: undefined,
    requirement_no: '',
    title: '',
    module: '',
    priority: 'medium',
    description: '',
    acceptance_criteria: '',
  }
}

function resetItemForm(data = emptyItemForm()) {
  Object.assign(itemForm, emptyItemForm(), data)
}

async function loadDocuments() {
  if (!selectedProject.value) return
  const { data } = await getRequirementDocuments({
    project: selectedProject.value,
    page_size: 100,
  })
  documents.value = Array.isArray(data) ? data : data.results || []
}

async function loadItems() {
  if (!selectedProject.value) return
  loadingItems.value = true
  try {
    const params = {
      project: selectedProject.value,
      page: itemPagination.page,
      page_size: itemPagination.pageSize,
    }
    if (itemKeyword.value) params.search = itemKeyword.value
    const { data } = await getRequirementItems(params)
    const payload = normalizeListResponse(data)
    items.value = payload.results
    itemPagination.total = payload.total
  } finally {
    loadingItems.value = false
  }
}

function normalizeListResponse(data) {
  if (Array.isArray(data)) {
    return { results: data, total: data.length }
  }
  return { results: data.results || [], total: data.count || 0 }
}

async function handleProjectChange() {
  itemPagination.page = 1
  await Promise.all([loadDocuments(), loadItems()])
}

async function resetItemPage() {
  itemPagination.page = 1
  await loadItems()
}

async function handleItemSizeChange() {
  itemPagination.page = 1
  await loadItems()
}

function openItemDialog(row) {
  editingItem.value = row || null
  resetItemForm(row ? { ...row } : { document: documents.value[0]?.id })
  itemDialogVisible.value = true
}

function openDetailDrawer(row) {
  detailItem.value = row
  detailDrawerVisible.value = true
}

async function saveItem() {
  savingItem.value = true
  try {
    if (editingItem.value?.id) {
      await updateRequirementItem(editingItem.value.id, itemForm)
    } else {
      await createRequirementItem(itemForm)
    }
    ElMessage.success('已保存需求')
    itemDialogVisible.value = false
    await loadItems()
  } finally {
    savingItem.value = false
  }
}

async function removeItem(row) {
  await ElMessageBox.confirm(`确认删除需求「${row.title}」？`, '删除需求', { type: 'warning' })
  await deleteRequirementItem(row.id)
  ElMessage.success('已删除需求')
  await loadItems()
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

onMounted(async () => {
  await loadProjects()
  await Promise.all([loadDocuments(), loadItems()])
})
</script>

<style scoped>
.admin-page {
  width: min(1440px, 100%);
}

.page-head,
.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

h1,
h2,
p {
  margin: 0;
}

.eyebrow {
  display: block;
  margin-bottom: 6px;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
}

h1 {
  margin-bottom: 6px;
  color: #172033;
  font-size: 24px;
  font-weight: 650;
}

h2 {
  color: #172033;
  font-size: 17px;
  font-weight: 650;
}

p {
  color: #64748b;
  font-size: 14px;
  line-height: 1.6;
}

.page-head {
  margin-bottom: 16px;
}

.project-select {
  width: 240px;
}

.data-section {
  border: 1px solid #e6ebf2;
  border-radius: 8px;
  background: #ffffff;
}

.section-head {
  min-height: 58px;
  padding: 12px 14px;
  border-bottom: 1px solid #edf1f6;
}

.table-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.table-toolbar .el-input {
  max-width: 360px;
}

.dense-table { --el-table-border-color: #edf1f6; --el-table-header-bg-color: #fbfcfe; --el-table-header-text-color: #6b7280; --el-table-row-hover-bg-color: #f8fbff; font-size: 14px; }
.dense-table :deep(.el-table__header th) { height: 42px; padding: 0; font-weight: 650; }
.dense-table :deep(.el-table__cell) { padding: 8px 0; }
.mono-code { color: #374151; font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace; font-size: 13px; font-variant-numeric: tabular-nums; }
.text-badge { display: inline-flex; align-items: center; height: 22px; padding: 0 8px; border: 1px solid #e2e8f0; border-radius: 999px; color: #475569; background: #f1f5f9; font-size: 12px; white-space: nowrap; }
.action-cell { display: inline-flex; align-items: center; justify-content: center; gap: 4px; white-space: nowrap; }
.action-cell :deep(.el-button) { width: 28px; height: 28px; margin-left: 0; padding: 0; border-radius: 6px; font-weight: 600; }
.action-cell :deep(.el-button span) { display: none; }
.action-cell :deep(.el-icon + span) { margin-left: 0; }
.pagination-bar { display: flex; justify-content: flex-end; padding: 12px 14px; border-top: 1px solid #edf1f6; }
.detail-meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-bottom: 16px; }
.detail-meta div { min-width: 0; padding: 10px 12px; border: 1px solid #e6ebf2; border-radius: 6px; background: #fbfcfe; }
.detail-meta span { display: block; margin-bottom: 4px; color: #64748b; font-size: 12px; }
.detail-meta strong { display: block; overflow: hidden; color: #172033; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.detail-section { margin-bottom: 16px; }
.detail-section h2 { margin-bottom: 8px; }
.full-text { padding: 12px 14px; border: 1px solid #e6ebf2; border-radius: 6px; background: #fff; color: #334155; font-size: 14px; line-height: 1.7; white-space: pre-wrap; }
.content-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.content-head span { color: #64748b; font-size: 12px; }
.empty-content { padding: 28px; border: 1px dashed #dbe3ec; border-radius: 6px; color: #94a3b8; text-align: center; }
.content-block { margin-bottom: 12px; border: 1px solid #dce4ee; border-radius: 6px; overflow: hidden; }
.content-block.is-section { border-left: 3px solid #409eff; }
.block-head { display: flex; align-items: center; min-height: 42px; gap: 8px; padding: 0 10px; background: #f8fafc; }
.group-title { display: flex; align-items: center; gap: 8px; color: #25324a; font-size: 14px; }
.level-mark { display: inline-flex; align-items: center; height: 22px; padding: 0 7px; border: 1px solid #bfdbfe; border-radius: 4px; background: #eff6ff; color: #2563eb; font-size: 11px; font-weight: 700; }
.group-body > :not(:last-child) { border-bottom: 1px solid #edf1f6; }
.block-text { padding: 14px 16px; color: #334155; font-size: 14px; line-height: 1.7; white-space: pre-wrap; }
.table-scroll { overflow: auto; padding: 12px 16px; }
.table-scroll table { width: 100%; border-collapse: collapse; font-size: 13px; }
.table-scroll th,
.table-scroll td { padding: 8px; border: 1px solid #dbe3ec; text-align: left; }
.table-scroll th { background: #f1f5f9; }
.source-table :deep(table) { width: 100%; border-collapse: collapse; }
.source-table :deep(th),
.source-table :deep(td) { padding: 8px; border: 1px solid #dbe3ec; text-align: left; }
.source-table :deep(th) { background: #f1f5f9; }
.document-image { width: 100%; height: 360px; background: #f8fafc; }

@media (max-width: 760px) {
  .page-head,
  .section-head,
  .table-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .detail-meta {
    grid-template-columns: 1fr;
  }

  .project-select,
  .table-toolbar .el-input {
    width: 100%;
    max-width: none;
  }
}
</style>
