<template>
  <section class="testcase-detail-page">
    <header class="page-head">
      <div class="page-title">
        <span class="eyebrow">需求用例中心</span>
        <h1>用例详情</h1>
        <p>查看用例基础信息、需求来源、执行设计和模型审核记录。</p>
      </div>
      <el-button :icon="ArrowLeft" @click="goBack">返回</el-button>
    </header>

    <section v-loading="loading" class="detail-layout">
      <template v-if="testCase">
        <section class="summary-panel">
          <div class="case-heading">
            <span class="mono-code">{{ testCase.case_no }}</span>
            <h2>{{ testCase.title }}</h2>
          </div>
          <div class="summary-tags">
            <span class="status-pill status-active">{{ testCase.status_label || '-' }}</span>
            <span class="text-badge">{{ testCase.priority_label || '-' }}</span>
            <span class="text-badge">{{ testCase.test_type_label || '-' }}</span>
          </div>
        </section>

        <section class="data-section">
          <div class="section-head">
            <h2>基础信息</h2>
          </div>
          <el-descriptions :column="2" border class="case-descriptions">
            <el-descriptions-item label="所属项目">{{ testCase.project_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="需求版本">{{ testCase.version_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="关联需求">
              <span class="mono-code">{{ testCase.requirement_no || '-' }}</span>
              <span v-if="testCase.requirement_title" class="inline-title">{{ testCase.requirement_title }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="创建人">{{ testCase.created_by_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatDate(testCase.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ formatDate(testCase.updated_at) }}</el-descriptions-item>
          </el-descriptions>
        </section>

        <section class="data-section">
          <div class="section-head">
            <h2>用例功能</h2>
            <p>前置条件、操作步骤和预期结果用于后续执行、评审和报告追踪。</p>
          </div>
          <div class="content-grid">
            <article class="content-block">
              <h3>前置条件</h3>
              <p>{{ testCase.preconditions || '无' }}</p>
            </article>
            <article class="content-block">
              <h3>操作步骤</h3>
              <p>{{ testCase.steps || '无' }}</p>
            </article>
            <article class="content-block">
              <h3>预期结果</h3>
              <p>{{ testCase.expected_result || '无' }}</p>
            </article>
          </div>
        </section>

        <section class="data-section">
          <div class="section-head">
            <div>
              <h2>增强记录</h2>
              <p>查看历史用例或缺陷驱动的增强建议、覆盖前快照和人工处理结果。</p>
            </div>
            <span class="text-badge">{{ testCase.enhancement_history?.length || 0 }} 条</span>
          </div>
          <el-collapse v-if="testCase.enhancement_history?.length" class="history-list">
            <el-collapse-item v-for="item in testCase.enhancement_history" :key="item.id" :name="item.id">
              <template #title>
                <div class="history-title">
                  <span class="mono-code">{{ item.task_no }}</span>
                  <span class="text-badge">{{ item.action_label }}</span>
                  <span class="status-pill" :class="`status-${item.status}`">{{ item.status_label }}</span>
                  <span>{{ item.rationale || '增强建议' }}</span>
                </div>
              </template>
              <div class="history-content">
                <article><h3>修改前</h3><pre>{{ formatSnapshot(item.before_snapshot) }}</pre></article>
                <article><h3>建议内容</h3><pre>{{ formatSnapshot(item.proposed_content) }}</pre></article>
              </div>
              <div class="history-meta">
                <p>评审：{{ item.review_feedback || '-' }}</p>
                <p>处理：{{ item.decided_by_name || '-' }} · {{ formatDate(item.decided_at) }} · {{ item.decision_note || '无备注' }}</p>
                <p>证据：{{ item.evidence?.map(evidence => `${evidence.identifier} ${evidence.title}`).join('；') || '当前需求推导' }}</p>
              </div>
            </el-collapse-item>
          </el-collapse>
          <el-empty v-else description="暂无增强记录" />
        </section>

      </template>

      <el-empty v-else-if="!loading" description="未找到用例" />
    </section>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'

import { getTestCase } from '@/api/requirements'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const testCase = ref(null)

function formatDate(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function formatSnapshot(value) {
  if (!value || !Object.keys(value).length) return '无'
  const labels = { case_no: '用例编号', title: '标题', preconditions: '前置条件', steps: '操作步骤', expected_result: '预期结果', priority: '优先级', test_type: '测试类型' }
  return Object.entries(value).map(([key, content]) => `${labels[key] || key}：${content || '-'}`).join('\n')
}

function goBack() {
  router.back()
}

async function loadTestCase() {
  loading.value = true
  try {
    const { data } = await getTestCase(route.params.id)
    testCase.value = data
  } catch (_error) {
    // API 错误由统一错误中心展示。
    testCase.value = null
  } finally {
    loading.value = false
  }
}

onMounted(loadTestCase)
</script>

<style scoped>
.testcase-detail-page {
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
h3,
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
  color: #334155;
  font-size: 14px;
  font-weight: 650;
  line-height: 1.4;
}

p {
  color: #64748b;
  font-size: 14px;
  line-height: 1.6;
}

.detail-layout {
  display: grid;
  gap: 12px;
  min-height: 240px;
}

.summary-panel,
.data-section {
  border: 1px solid #e6ebf2;
  border-radius: 8px;
  background: #ffffff;
}

.summary-panel {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 14px;
}

.case-heading {
  min-width: 0;
}

.case-heading h2 {
  margin-top: 6px;
  overflow-wrap: anywhere;
}

.summary-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  min-height: 50px;
  padding: 12px 14px;
  border-bottom: 1px solid #edf1f6;
}

.case-descriptions {
  padding: 14px;
}

.case-descriptions :deep(.el-descriptions__label) {
  width: 112px;
  color: #64748b;
  font-weight: 650;
}

.inline-title {
  margin-left: 8px;
  color: #475569;
}

.content-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  padding: 14px;
}

.content-block {
  min-height: 160px;
  padding: 12px;
  border: 1px solid #edf1f6;
  border-radius: 8px;
  background: #fbfcfe;
}

.text-badge,
.status-pill {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
}

.text-badge { color: #475569; background: #f1f5f9; }
.status-accepted { color: #15803d; background: #f0fdf4; }
.status-rejected { color: #64748b; background: #f1f5f9; }
.status-conflict { color: #b91c1c; background: #fef2f2; }
.status-pending { color: #1d4ed8; background: #eff6ff; }
.history-list { padding: 0 14px 14px; }
.history-title { display: flex; align-items: center; gap: 8px; min-width: 0; }
.history-title > span:last-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.history-content { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.history-content article { padding: 12px; border: 1px solid #e6ebf2; border-radius: 8px; }
.history-content pre { margin: 8px 0 0; color: #475569; font: inherit; line-height: 1.6; white-space: pre-wrap; }
.history-meta { margin-top: 10px; padding: 10px 12px; border-radius: 8px; background: #f8fafc; }
@media (max-width: 760px) { .history-content { grid-template-columns: 1fr; } }

.content-block h3 {
  margin-bottom: 8px;
}

.content-block p {
  color: #334155;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.mono-code {
  color: #374151;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.status-pill,
.text-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
}

.status-active {
  color: #047857;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
}

.text-badge {
  color: #475569;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
}

@media (max-width: 980px) {
  .page-head,
  .summary-panel,
  .section-head {
    align-items: stretch;
    flex-direction: column;
  }

  .summary-tags {
    justify-content: flex-start;
  }

  .content-grid {
    grid-template-columns: 1fr;
  }
}
</style>
