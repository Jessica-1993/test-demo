<template>
  <section class="testcase-page">
    <header class="page-head">
      <div class="page-title">
        <span class="eyebrow">需求用例中心</span>
        <h1>用例库</h1>
        <p>按项目和版本查看已入库测试用例，支持按编号、标题或步骤检索。</p>
      </div>
      <el-select v-model="selectedProject" placeholder="选择项目" class="project-select" @change="handleProjectChange">
        <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
      </el-select>
    </header>

    <section class="data-section">
      <div class="section-head">
        <div>
          <h2>用例列表</h2>
          <p>共 {{ casePagination.total }} 条入库用例。</p>
        </div>
        <div class="case-tools">
          <el-select v-model="selectedVersion" placeholder="全部版本" clearable class="version-select" @change="handleVersionChange">
            <el-option v-for="version in versions" :key="version.id" :label="`${version.version_no} ${version.name}`" :value="version.id" />
          </el-select>
          <el-input
            v-model="caseKeyword"
            placeholder="搜索用例编号、标题、步骤"
            clearable
            @keyup.enter="resetCasePage"
            @clear="resetCasePage"
          />
          <el-button :icon="Search" @click="resetCasePage">搜索</el-button>
        </div>
      </div>

      <el-table :data="testCases" v-loading="loadingCases" class="dense-table case-table">
        <el-table-column prop="case_no" label="用例编号" width="120">
          <template #default="{ row }">
            <span class="mono-code">{{ row.case_no }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="用例标题" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" class="case-title-link" @click="goToCaseDetail(row)">
              {{ row.title }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="version_name" label="版本" min-width="130" show-overflow-tooltip />
        <el-table-column prop="requirement_no" label="关联需求" width="120">
          <template #default="{ row }">
            <span class="mono-code">{{ row.requirement_no }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="priority_label" label="优先级" width="86">
          <template #default="{ row }">
            <span class="text-badge">{{ row.priority_label || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="test_type_label" label="类型" width="110" show-overflow-tooltip />
        <el-table-column prop="steps" label="操作步骤" min-width="260" show-overflow-tooltip />
        <el-table-column prop="expected_result" label="预期结果" min-width="240" show-overflow-tooltip />
      </el-table>

      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="casePagination.page"
          v-model:page-size="casePagination.pageSize"
          :page-sizes="[10, 20, 50]"
          :total="casePagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleCaseSizeChange"
          @current-change="loadTestCases"
        />
      </div>
    </section>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'

import {
  getRequirementVersions,
  getTestCases,
} from '@/api/requirements'
import { useRequirementProjects } from './useRequirementProjects'

const { projects, selectedProject, loadProjects } = useRequirementProjects()
const router = useRouter()
const versions = ref([])
const selectedVersion = ref()
const testCases = ref([])
const caseKeyword = ref('')
const loadingCases = ref(false)
const casePagination = reactive({ page: 1, pageSize: 10, total: 0 })

function normalizeListResponse(data) {
  if (Array.isArray(data)) return { results: data, total: data.length }
  return { results: data.results || [], total: data.count || 0 }
}

async function loadVersions() {
  versions.value = []
  selectedVersion.value = undefined
  if (!selectedProject.value) return
  const { data } = await getRequirementVersions({ project: selectedProject.value, status: 'published', page_size: 100 })
  versions.value = normalizeListResponse(data).results
}

async function loadTestCases() {
  testCases.value = []
  if (!selectedProject.value) {
    casePagination.total = 0
    return
  }
  loadingCases.value = true
  try {
    const params = {
      project: selectedProject.value,
      page: casePagination.page,
      page_size: casePagination.pageSize,
    }
    if (selectedVersion.value) params.version = selectedVersion.value
    if (caseKeyword.value) params.search = caseKeyword.value
    const { data } = await getTestCases(params)
    const payload = normalizeListResponse(data)
    testCases.value = payload.results
    casePagination.total = payload.total
  } finally {
    loadingCases.value = false
  }
}

async function handleProjectChange() {
  casePagination.page = 1
  await loadVersions()
  await loadTestCases()
}

async function handleVersionChange() {
  casePagination.page = 1
  await loadTestCases()
}

async function resetCasePage() {
  casePagination.page = 1
  await loadTestCases()
}

async function handleCaseSizeChange() {
  casePagination.page = 1
  await loadTestCases()
}

function goToCaseDetail(row) {
  router.push(`/requirements/test-cases/${row.id}`)
}

onMounted(async () => {
  await loadProjects()
  await handleProjectChange()
})
</script>

<style scoped>
.testcase-page {
  width: min(1440px, 100%);
}

.page-head,
.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

.page-head {
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

p {
  color: #64748b;
  font-size: 14px;
  line-height: 1.6;
}

.project-select {
  flex: 0 0 240px;
}

.data-section {
  border: 1px solid #e6ebf2;
  border-radius: 8px;
  background: #ffffff;
}

.section-head {
  align-items: flex-end;
  min-height: 58px;
  padding: 12px 14px;
  border-bottom: 1px solid #edf1f6;
}

.case-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}

.case-tools .el-input {
  width: 320px;
}

.version-select {
  width: 240px;
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

.case-table {
  border-radius: 0 0 8px 8px;
}

.case-title-link {
  max-width: 100%;
  font-weight: 600;
  vertical-align: middle;
}

.case-title-link :deep(.el-link__inner) {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mono-code {
  color: #374151;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.text-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  color: #475569;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
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
  .case-tools {
    align-items: stretch;
    flex-direction: column;
  }

  .project-select,
  .version-select,
  .case-tools .el-input {
    width: 100%;
    max-width: none;
    flex-basis: auto;
  }
}
</style>
