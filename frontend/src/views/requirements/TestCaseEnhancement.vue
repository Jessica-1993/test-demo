<template>
  <section class="enhancement-page">
    <header class="page-head">
      <div class="page-title">
        <span class="eyebrow">需求用例中心</span>
        <h1>用例增强</h1>
        <p>以当前正式需求和用例为基线，检索历史用例与缺陷，生成可审核的新增或优化建议。</p>
      </div>
      <el-select v-model="selectedProject" class="project-select" placeholder="选择项目" @change="handleProjectChange">
        <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
      </el-select>
    </header>

    <section class="workbench-panel">
      <div class="workflow-strip">
        <span>1. 选择正式需求</span><i>→</i><span>2. 检索历史资产</span><i>→</i><span>3. 生成并评审建议</span><i>→</i><span>4. 人工确认落库</span>
      </div>
      <div class="control-bar">
        <el-select v-model="selectedVersion" placeholder="选择已发布版本" class="version-select" @change="loadRevisionContext">
          <el-option v-for="version in versions" :key="version.id" :label="`${version.version_no} ${version.name}`" :value="version.id" />
        </el-select>
        <el-input v-model="revisionKeyword" clearable placeholder="筛选需求编号或标题" />
        <span class="selection-summary">已选 {{ selectedRevisions.length }} 条</span>
        <el-button type="primary" :icon="MagicStick" :disabled="!selectedRevisions.length" :loading="submitting" @click="submitEnhancement">创建增强任务</el-button>
      </div>

      <el-table ref="revisionTable" v-loading="loadingRevisions" :data="filteredRevisions" class="dense-table" @selection-change="selectedRevisions = $event">
        <el-table-column type="selection" width="46" />
        <el-table-column prop="family_no" label="需求族" width="130"><template #default="{ row }"><span class="mono-code">{{ row.family_no }} R{{ row.revision_no }}</span></template></el-table-column>
        <el-table-column prop="title" label="正式需求" min-width="280" show-overflow-tooltip />
        <el-table-column label="正式模块" min-width="220" show-overflow-tooltip><template #default="{ row }">{{ row.modules?.map(item => item.path).join('；') || '-' }}</template></el-table-column>
        <el-table-column label="当前用例" width="100" align="right"><template #default="{ row }"><span class="mono-code">{{ caseCounts[row.id] || 0 }}</span></template></el-table-column>
      </el-table>
    </section>

    <section class="data-section">
      <div class="section-head"><div><h2>增强任务</h2><p>共 {{ taskPagination.total }} 条；任务完成后进入建议审核。</p></div><el-button :icon="Refresh" @click="loadTasks">刷新</el-button></div>
      <el-table v-loading="loadingTasks" :data="tasks" class="dense-table">
        <el-table-column type="expand" width="44"><template #default="{ row }"><div class="task-log"><div v-for="(log, index) in row.task_log || []" :key="index" class="log-row"><span class="mono-code">{{ log.requirement }}</span><span :class="['status-pill', `status-${log.status}`]">{{ log.stage }}</span><span>{{ log.message || log.title }}</span></div><el-empty v-if="!row.task_log?.length" description="暂无日志" /></div></template></el-table-column>
        <el-table-column prop="task_no" label="任务编号" min-width="220"><template #default="{ row }"><span class="mono-code">{{ row.task_no }}</span></template></el-table-column>
        <el-table-column prop="version_name" label="版本" min-width="130" show-overflow-tooltip />
        <el-table-column prop="status_label" label="状态" width="110"><template #default="{ row }"><span :class="['status-pill', `status-${row.status}`]">{{ row.status_label }}</span></template></el-table-column>
        <el-table-column label="进度" width="170"><template #default="{ row }"><div class="progress-cell"><el-progress :percentage="row.progress" :show-text="false" :stroke-width="6" /><span>{{ row.progress }}%</span></div></template></el-table-column>
        <el-table-column prop="suggestion_count" label="建议" width="72" align="right" />
        <el-table-column prop="pending_count" label="待确认" width="82" align="right" />
        <el-table-column prop="error_message" label="错误摘要" min-width="180" show-overflow-tooltip />
        <el-table-column label="操作" width="128" fixed="right" align="center"><template #default="{ row }"><div class="action-cell"><el-tooltip content="审核建议"><el-button text type="primary" :icon="View" :disabled="!row.suggestion_count" @click="openReview(row)">审核</el-button></el-tooltip><el-tooltip content="错误详情"><el-button text type="danger" :icon="Warning" :disabled="!row.error_info?.code" @click="showTaskError(row)">错误详情</el-button></el-tooltip><el-tooltip content="重新发起"><el-button text type="primary" :icon="RefreshRight" :disabled="!['failed','partial_success'].includes(row.status)" @click="retryTask(row)">重新发起</el-button></el-tooltip></div></template></el-table-column>
      </el-table>
      <div class="pagination-bar"><el-pagination v-model:current-page="taskPagination.page" v-model:page-size="taskPagination.pageSize" :total="taskPagination.total" :page-sizes="[10,20,50]" layout="total, sizes, prev, pager, next" @size-change="resetTaskPage" @current-change="loadTasks" /></div>
    </section>

    <el-drawer v-model="reviewVisible" title="增强建议审核" size="min(1180px, 96vw)" destroy-on-close>
      <div class="review-toolbar"><div><strong class="mono-code">{{ activeTask?.task_no }}</strong><p>逐条核对当前内容、建议内容与历史证据后再确认。</p></div><div><el-button :disabled="!selectedSuggestions.length" @click="batchDecision('reject')">批量拒绝</el-button><el-button type="primary" :disabled="!selectedAcceptable.length" @click="batchDecision('accept')">批量接受</el-button></div></div>
      <el-table v-loading="loadingSuggestions" :data="suggestions" class="dense-table" @selection-change="selectedSuggestions = $event">
        <el-table-column type="selection" width="46" />
        <el-table-column type="expand" width="44">
          <template #default="{ row }">
            <div class="compare-workbench">
              <article class="compare-pane"><h3>当前用例</h3><template v-if="row.action === 'update'"><CaseContent :content="row.before_snapshot" /></template><el-empty v-else description="新增建议，无当前用例" /></article>
              <article class="compare-pane proposed"><h3>增强建议</h3><CaseContent :content="row.proposed_content" /></article>
            </div>
            <div class="evidence-panel"><h3>建议依据</h3><p class="rationale">{{ row.rationale || '-' }}</p><div v-if="row.evidence?.length" class="evidence-list"><article v-for="item in row.evidence" :key="item.id"><div><span class="text-badge">{{ item.usage_label }}</span><span class="mono-code">{{ item.identifier }}</span><strong>{{ item.title }}</strong></div><p>{{ item.excerpt }}</p></article></div><el-empty v-else description="由当前正式需求直接推导" /></div>
          </template>
        </el-table-column>
        <el-table-column prop="action_label" label="类型" width="92"><template #default="{ row }"><span class="text-badge">{{ row.action_label }}</span></template></el-table-column>
        <el-table-column prop="requirement_title" label="正式需求" min-width="220" show-overflow-tooltip />
        <el-table-column prop="target_case_no" label="目标用例" width="130"><template #default="{ row }"><span class="mono-code">{{ row.target_case_no || '新增' }}</span></template></el-table-column>
        <el-table-column label="建议标题" min-width="240" show-overflow-tooltip><template #default="{ row }">{{ row.proposed_content?.title }}</template></el-table-column>
        <el-table-column label="评审" width="90"><template #default="{ row }"><span :class="['status-pill', row.review_passed ? 'status-success' : 'status-failed']">{{ row.review_passed ? '通过' : '未通过' }}</span></template></el-table-column>
        <el-table-column prop="status_label" label="处理状态" width="100" />
        <el-table-column label="操作" width="92" fixed="right" align="center"><template #default="{ row }"><div class="action-cell"><el-button text type="primary" :icon="Check" :disabled="row.status !== 'pending' || !row.review_passed" @click="decide(row, 'accept')">接受</el-button><el-button text type="danger" :icon="Close" :disabled="!['pending','conflict'].includes(row.status)" @click="decide(row, 'reject')">拒绝</el-button></div></template></el-table-column>
      </el-table>
    </el-drawer>
  </section>
</template>

<script setup>
import { computed, defineComponent, h, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Close, MagicStick, Refresh, RefreshRight, View, Warning } from '@element-plus/icons-vue'
import { acceptEnhancementSuggestion, batchDecideEnhancementSuggestions, createEnhancementTask, getEnhancementSuggestions, getEnhancementTasks, getRequirementRevisions, getRequirementVersions, getTestCases, rejectEnhancementSuggestion, retryEnhancementTask } from '@/api/requirements'
import { showErrorInfo } from '@/utils/errors'
import { useRequirementProjects } from './useRequirementProjects'

const CaseContent = defineComponent({ props: { content: { type: Object, default: () => ({}) } }, setup(props) { const fields = [['case_no','编号'],['title','标题'],['preconditions','前置条件'],['steps','操作步骤'],['expected_result','预期结果'],['priority','优先级'],['test_type','类型']]; return () => h('dl', { class:'case-content' }, fields.flatMap(([key,label]) => [h('dt', label), h('dd', props.content?.[key] || '-')])) } })
const { projects, selectedProject, loadProjects } = useRequirementProjects()
const versions = ref([]), selectedVersion = ref(), revisions = ref([]), revisionKeyword = ref(''), selectedRevisions = ref([]), caseCounts = reactive({})
const tasks = ref([]), suggestions = ref([]), selectedSuggestions = ref([]), activeTask = ref(null)
const loadingRevisions = ref(false), loadingTasks = ref(false), loadingSuggestions = ref(false), submitting = ref(false), reviewVisible = ref(false)
const taskPagination = reactive({ page:1, pageSize:10, total:0 })
let pollTimer
const filteredRevisions = computed(() => { const keyword = revisionKeyword.value.trim().toLowerCase(); return keyword ? revisions.value.filter(item => `${item.family_no} ${item.title}`.toLowerCase().includes(keyword)) : revisions.value })
const selectedAcceptable = computed(() => selectedSuggestions.value.filter(item => item.status === 'pending' && item.review_passed))
function normalize(data) { return Array.isArray(data) ? { results:data, count:data.length } : { results:data.results || [], count:data.count || 0 } }
async function loadVersions() { const { data } = await getRequirementVersions({ project:selectedProject.value, status:'published', page_size:100 }); versions.value = normalize(data).results; selectedVersion.value = versions.value[0]?.id; await loadRevisionContext() }
async function loadRevisionContext() {
  revisions.value=[]; selectedRevisions.value=[]; Object.keys(caseCounts).forEach(key => delete caseCounts[key]); if (!selectedVersion.value) return
  loadingRevisions.value=true
  try { const [revisionResponse, caseResponse] = await Promise.all([getRequirementRevisions({ project:selectedProject.value, versions:selectedVersion.value, page_size:500 }), getTestCases({ project:selectedProject.value, version:selectedVersion.value, page_size:500 })]); revisions.value=normalize(revisionResponse.data).results; normalize(caseResponse.data).results.forEach(item => { if (item.requirement_revision) caseCounts[item.requirement_revision]=(caseCounts[item.requirement_revision] || 0)+1 }) } finally { loadingRevisions.value=false }
}
async function loadTasks() { if (!selectedProject.value) return; loadingTasks.value=true; try { const { data }=await getEnhancementTasks({ project:selectedProject.value, page:taskPagination.page, page_size:taskPagination.pageSize }); const payload=normalize(data); tasks.value=payload.results; taskPagination.total=payload.count } finally { loadingTasks.value=false } }
async function handleProjectChange() { await loadVersions(); taskPagination.page=1; await loadTasks() }
async function submitEnhancement() { submitting.value=true; try { await createEnhancementTask({ project:selectedProject.value, version:selectedVersion.value, requirement_revisions:selectedRevisions.value.map(item => item.id) }); ElMessage.success('已创建用例增强任务'); await loadTasks() } catch(_error) { /* 统一错误中心已展示 */ } finally { submitting.value=false } }
async function openReview(task) { activeTask.value=task; reviewVisible.value=true; await loadSuggestions() }
async function loadSuggestions() { if (!activeTask.value) return; loadingSuggestions.value=true; try { const { data }=await getEnhancementSuggestions({ task:activeTask.value.id, page_size:500 }); suggestions.value=normalize(data).results } finally { loadingSuggestions.value=false } }
async function decide(row, decision) { try { await ElMessageBox.confirm(`确认${decision === 'accept' ? '接受并应用' : '拒绝'}该建议？`, '处理增强建议', { type:'warning' }); decision === 'accept' ? await acceptEnhancementSuggestion(row.id) : await rejectEnhancementSuggestion(row.id); ElMessage.success('建议已处理'); await Promise.all([loadSuggestions(), loadTasks()]) } catch(_error) { /* 取消操作或统一错误中心已处理 */ } }
function showTaskError(row) { showErrorInfo(row.error_info, { forceDialog:true, actionHandler:['failed','partial_success'].includes(row.status) ? () => retryTask(row) : null }) }
async function retryTask(row) { try { await ElMessageBox.confirm(`将复制 ${row.task_no} 的失败项创建新任务，原记录会保留。`, '重新发起增强任务', { type:'warning' }); await retryEnhancementTask(row.id); ElMessage.success('已创建重试任务'); await loadTasks() } catch (_error) { /* 取消操作或统一错误中心已处理 */ } }
async function batchDecision(decision) { const source=decision === 'accept' ? selectedAcceptable.value : selectedSuggestions.value; const { data }=await batchDecideEnhancementSuggestions({ ids:source.map(item=>item.id), decision }); ElMessage.success(`处理完成：成功 ${data.success_count}，失败 ${data.failed_count}`); await Promise.all([loadSuggestions(), loadTasks()]) }
async function resetTaskPage() { taskPagination.page=1; await loadTasks() }
onMounted(async()=>{ await loadProjects(); await handleProjectChange(); pollTimer=window.setInterval(()=>{ if(tasks.value.some(item=>['pending','running'].includes(item.status))) loadTasks() },5000) })
onBeforeUnmount(()=>window.clearInterval(pollTimer))
</script>

<style scoped>
.enhancement-page{width:min(1440px,100%)}.page-head,.section-head{display:flex;align-items:flex-start;justify-content:space-between;gap:24px}.page-head{margin-bottom:16px}.eyebrow{display:block;margin-bottom:6px;color:#64748b;font-size:12px;font-weight:600}h1,h2,h3,p{margin:0}h1{margin-bottom:6px;color:#172033;font-size:24px;font-weight:650}h2{color:#172033;font-size:17px;font-weight:650}h3{color:#334155;font-size:14px;font-weight:650}p{color:#64748b;font-size:14px;line-height:1.6}.project-select{flex:0 0 240px}.workbench-panel,.data-section{margin-bottom:14px;border:1px solid #e6ebf2;border-radius:8px;background:#fff}.workflow-strip{display:flex;align-items:center;gap:12px;padding:10px 14px;color:#475569;font-size:13px;border-bottom:1px solid #edf1f6;background:#fbfcfe}.workflow-strip i{color:#94a3b8;font-style:normal}.control-bar{display:flex;align-items:center;gap:8px;padding:12px 14px}.control-bar .el-input{width:280px}.version-select{width:260px}.selection-summary{margin-left:auto;color:#64748b;font-size:13px}.section-head{align-items:flex-end;padding:12px 14px;border-bottom:1px solid #edf1f6}.dense-table{--el-table-border-color:#edf1f6;--el-table-header-bg-color:#fbfcfe;--el-table-header-text-color:#6b7280;--el-table-row-hover-bg-color:#f8fbff;font-size:14px}.dense-table :deep(.el-table__header th){height:42px;padding:0;font-weight:650}.dense-table :deep(.el-table__cell){padding:8px 0}.mono-code{color:#374151;font-family:"SFMono-Regular",Consolas,monospace;font-size:13px}.status-pill,.text-badge{display:inline-flex;align-items:center;height:22px;padding:0 8px;border-radius:999px;font-size:12px;white-space:nowrap}.text-badge{color:#475569;background:#f1f5f9}.status-success,.status-completed{color:#15803d;background:#f0fdf4}.status-running,.status-pending{color:#1d4ed8;background:#eff6ff}.status-failed{color:#b91c1c;background:#fef2f2}.status-partial_success{color:#b45309;background:#fffbeb}.progress-cell{display:grid;grid-template-columns:1fr 38px;align-items:center;gap:8px}.pagination-bar{display:flex;justify-content:flex-end;padding:12px 14px;border-top:1px solid #edf1f6}.task-log{padding:10px 54px}.log-row{display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid #edf1f6}.review-toolbar{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:12px;padding:12px 14px;border:1px solid #e6ebf2;border-radius:8px}.compare-workbench{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:8px 48px}.compare-pane,.evidence-panel{padding:14px;border:1px solid #e6ebf2;border-radius:8px;background:#fff}.compare-pane.proposed{border-color:#bfdbfe;background:#f8fbff}.compare-pane h3,.evidence-panel h3{margin-bottom:10px}.case-content{display:grid;grid-template-columns:92px 1fr;margin:0;font-size:13px}.case-content :deep(dt),.case-content :deep(dd){margin:0;padding:7px 0;border-bottom:1px solid #edf1f6;white-space:pre-wrap}.case-content :deep(dt){color:#64748b;font-weight:650}.evidence-panel{margin:4px 48px 12px}.rationale{margin-bottom:10px}.evidence-list article{padding:10px 0;border-top:1px solid #edf1f6}.evidence-list article>div{display:flex;align-items:center;gap:8px;margin-bottom:5px}.evidence-list article p{white-space:pre-wrap}.action-cell{display:inline-flex;gap:4px}.action-cell :deep(.el-button){width:28px;height:28px;margin:0;padding:0}.action-cell :deep(.el-button span){display:none}@media(max-width:900px){.page-head,.section-head,.review-toolbar{flex-direction:column;align-items:stretch}.project-select{flex-basis:auto;width:100%}.workflow-strip{overflow-x:auto}.control-bar{flex-wrap:wrap}.selection-summary{margin-left:0}.compare-workbench{grid-template-columns:1fr;padding:8px}.evidence-panel{margin:4px 8px 12px}}
</style>
