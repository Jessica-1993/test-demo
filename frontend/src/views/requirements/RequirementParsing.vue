<template>
  <div class="admin-page">
    <header class="page-head">
      <div>
        <span class="eyebrow">结构化处理</span>
        <h1>需求解析</h1>
        <p>按文档层级拆分需求，并整理文本、表格和图片。</p>
      </div>
      <el-select v-model="selectedProject" class="project-select" @change="projectChanged">
        <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
      </el-select>
    </header>

    <section class="control-band">
      <el-select v-model="selectedDocument" filterable placeholder="选择需求文档" @change="loadWorkspace">
        <el-option v-for="doc in documents" :key="doc.id" :label="doc.title" :value="doc.id">
          <span>{{ doc.title }}</span>
          <span class="option-meta">{{ doc.status_label }}</span>
        </el-option>
      </el-select>
      <el-button type="primary" :icon="MagicStick" :loading="parsing" :disabled="!selectedDocument" @click="parseDocument">开始解析</el-button>
      <div v-if="currentRun" class="run-summary">
        <span class="status-dot"></span>
        <strong>第 {{ currentRun.run_no }} 次</strong>
        <span>{{ currentRun.requirement_count }} 条需求</span>
        <span>{{ currentRun.table_count }} 表格</span>
        <span>{{ currentRun.image_count }} 图片</span>
        <span>{{ currentRun.filtered_count }} 已过滤</span>
      </div>
    </section>

    <el-tabs v-model="activeTab" class="workspace-tabs">
      <el-tab-pane label="当前解析结果" name="requirements">
        <section class="data-section">
          <div class="section-head">
            <div>
              <h2>解析结果</h2>
              <p>查看和整理文档解析出的候选需求，需求整合请在独立页签中完成。</p>
            </div>
            <div class="section-actions">
              <el-button :icon="Connection" :disabled="parseSelection.length < 2" @click="mergeSelected">合并所选</el-button>
            </div>
          </div>
          <el-table
            v-loading="loading"
            :data="requirements"
            row-key="id"
            class="dense-table"
            @selection-change="parseSelection = $event"
            @row-click="openDetail"
          >
            <el-table-column type="selection" width="44" />
            <el-table-column prop="requirement_no" label="编号" width="150"><template #default="{ row }"><span class="mono-code">{{ row.requirement_no }}</span></template></el-table-column>
            <el-table-column prop="module" label="模块" width="150" show-overflow-tooltip />
            <el-table-column prop="title" label="功能" min-width="220" show-overflow-tooltip />
            <el-table-column prop="confirm_status_label" label="确认状态" width="110">
              <template #default="{ row }"><span class="text-badge" :class="{ 'is-confirmed': row.confirm_status === 'confirmed' }">{{ row.confirm_status_label }}</span></template>
            </el-table-column>
            <el-table-column label="内容" width="150"><template #default="{ row }"><span>{{ blockCount(row, 'text') }} 文本</span> · <span>{{ blockCount(row, 'table') }} 表</span> · <span>{{ blockCount(row, 'image') }} 图</span></template></el-table-column>
            <el-table-column label="操作" width="92" fixed="right" align="center">
              <template #default="{ row }">
                <div class="action-cell">
                  <el-tooltip content="查看详情"><el-button :icon="View" @click.stop="openDetail(row)" /></el-tooltip>
                  <el-tooltip content="归档"><el-button type="danger" :icon="Delete" @click.stop="archive(row)" /></el-tooltip>
                </div>
              </template>
            </el-table-column>
            <template #empty><el-empty description="暂无解析结果" /></template>
          </el-table>
        </section>
      </el-tab-pane>

      <el-tab-pane :label="`需求整合 (${integrationRows.length})`" name="integration">
        <section class="data-section">
          <div class="section-head">
            <div>
              <h2>需求整合</h2>
              <p>结合项目知识、历史正式需求和用例覆盖提示生成可编辑整合稿。</p>
            </div>
            <div class="section-actions">
              <el-button :icon="Refresh" :loading="loading" @click="loadWorkspace">刷新</el-button>
              <el-button type="primary" :loading="integrating" :disabled="integrationSelection.length === 0" @click="integrateSelected">整合所选</el-button>
            </div>
          </div>
          <el-table ref="integrationTableRef" v-loading="loading" :data="integrationRows" row-key="id" class="dense-table" @selection-change="integrationSelection = $event">
            <el-table-column type="selection" width="44" />
            <el-table-column prop="requirement_no" label="编号" width="150"><template #default="{ row }"><span class="mono-code">{{ row.requirement_no }}</span></template></el-table-column>
            <el-table-column prop="module" label="原模块" width="140" show-overflow-tooltip />
            <el-table-column prop="title" label="需求" min-width="240" show-overflow-tooltip />
            <el-table-column label="整合状态" width="120"><template #default="{ row }"><span class="status-pill" :class="integrationStatusClass(row)">{{ integrationStatusLabel(row) }}</span></template></el-table-column>
            <el-table-column label="操作" width="92" fixed="right" align="center">
              <template #default="{ row }"><div class="action-cell"><el-tooltip :content="integrationActionLabel(row)"><el-button type="primary" :icon="MagicStick" @click="openIntegration(row)" /></el-tooltip></div></template>
            </el-table-column>
            <template #empty><el-empty description="暂无待整合需求" /></template>
          </el-table>
        </section>
        <section class="data-section integration-task-section">
          <div class="section-head">
            <div><h2>整合任务</h2><p>批量整合在后台执行；失败项可保留原记录后重新发起。</p></div>
            <el-button :icon="Refresh" @click="loadIntegrationBatches">刷新</el-button>
          </div>
          <el-table :data="integrationBatches" class="dense-table">
            <el-table-column prop="id" label="任务" width="90"><template #default="{ row }"><span class="mono-code">INT-{{ row.id }}</span></template></el-table-column>
            <el-table-column prop="status_label" label="状态" width="110"><template #default="{ row }"><span class="status-pill" :class="`is-${row.status}`">{{ row.status_label }}</span></template></el-table-column>
            <el-table-column prop="total_count" label="总数" width="70" align="right" />
            <el-table-column prop="success_count" label="成功" width="70" align="right" />
            <el-table-column prop="failed_count" label="失败" width="70" align="right" />
            <el-table-column prop="error_message" label="错误摘要" min-width="220" show-overflow-tooltip />
            <el-table-column label="操作" width="92" fixed="right" align="center">
              <template #default="{ row }"><div class="action-cell"><el-tooltip content="错误详情"><el-button :icon="Warning" type="danger" :disabled="!row.error_info?.code" @click="showBatchError(row)" /></el-tooltip><el-tooltip content="重新发起"><el-button :icon="RefreshRight" type="primary" :disabled="!['failed','partial_success'].includes(row.status)" @click="retryBatch(row)" /></el-tooltip></div></template>
            </el-table-column>
          </el-table>
        </section>
      </el-tab-pane>

      <el-tab-pane :label="`整合审核 (${reviewRows.length})`" name="review">
        <section class="data-section">
          <div class="section-head">
            <div>
              <h2>整合审核</h2>
              <p>审核整合稿、确认需求关系并处理冲突，最后形成正式需求修订。</p>
            </div>
            <div class="section-actions"><el-button :icon="Refresh" :loading="loading" @click="loadWorkspace">刷新</el-button></div>
          </div>
          <el-table v-loading="loading" :data="reviewRows" row-key="id" class="dense-table">
            <el-table-column prop="requirement_no" label="编号" width="150"><template #default="{ row }"><span class="mono-code">{{ row.requirement_no }}</span></template></el-table-column>
            <el-table-column prop="title" label="原始需求" min-width="220" show-overflow-tooltip />
            <el-table-column label="整合标题" min-width="220" show-overflow-tooltip><template #default="{ row }">{{ row.integration_draft?.title || '-' }}</template></el-table-column>
            <el-table-column label="关系" width="110"><template #default="{ row }">{{ relationshipLabel(row.integration_draft?.relationship_mode) }}</template></el-table-column>
            <el-table-column label="审核状态" width="120"><template #default="{ row }"><span class="status-pill" :class="reviewStatusClass(row)">{{ reviewStatusLabel(row) }}</span></template></el-table-column>
            <el-table-column label="操作" width="92" fixed="right" align="center">
              <template #default="{ row }"><div class="action-cell"><el-tooltip :content="row.confirm_status === 'confirmed' ? '查看审核结果' : '整合审核'"><el-button type="primary" :icon="row.confirm_status === 'confirmed' ? View : Check" @click="openReview(row)" /></el-tooltip></div></template>
            </el-table-column>
            <template #empty><el-empty description="暂无待审核整合稿，请先完成需求整合" /></template>
          </el-table>
        </section>
      </el-tab-pane>

      <el-tab-pane :label="`待整理区 (${orphanBlocks.length})`" name="orphans">
        <section class="data-section">
          <div class="section-head"><div><h2>未归属内容</h2><p>没有三级功能标题的内容不会自动生成需求，可手动分配。</p></div></div>
          <div v-if="!orphanBlocks.length" class="empty-state">暂无待整理内容</div>
          <div v-for="block in orphanBlocks" :key="block.id" class="orphan-row">
            <div class="orphan-content"><strong>{{ typeLabel(block.block_type) }}</strong><span>{{ block.text || '未命名内容' }}</span></div>
            <el-select v-model="orphanTargets[block.id]" placeholder="分配到需求"><el-option v-for="item in requirements" :key="item.id" :label="`${item.module} / ${item.title}`" :value="item.id" /></el-select>
            <el-button type="primary" plain @click="assignBlock(block)">确认</el-button>
          </div>
        </section>
      </el-tab-pane>

      <el-tab-pane label="解析历史" name="history">
        <section class="data-section">
          <el-table :data="runs" class="dense-table">
            <el-table-column prop="run_no" label="批次" width="90" />
            <el-table-column prop="status_label" label="状态" width="100" />
            <el-table-column prop="extraction_engine" label="引擎" width="130" />
            <el-table-column prop="message" label="结果" min-width="260" show-overflow-tooltip />
            <el-table-column prop="created_by_name" label="执行人" width="110" />
            <el-table-column prop="created_at" label="时间" width="180"><template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template></el-table-column>
            <el-table-column label="操作" width="92" fixed="right" align="center"><template #default="{ row }"><div class="action-cell"><el-tooltip content="错误详情"><el-button :icon="Warning" type="danger" :disabled="!row.error_info?.code" @click="showRunError(row)" /></el-tooltip><el-tooltip content="重新解析"><el-button :icon="RefreshRight" type="primary" :disabled="row.status !== 'failed'" @click="parseDocument" /></el-tooltip></div></template></el-table-column>
          </el-table>
        </section>
      </el-tab-pane>
    </el-tabs>

    <el-drawer v-model="detailVisible" size="min(1120px, 96vw)" title="需求详情">
      <template v-if="editingItem">
        <div class="review-layout detail-layout">
          <RequirementSourcePane :item="sourcePreviewItem" />
          <section class="review-pane detail-edit-pane">
            <div class="review-head">
              <div><h2>候选需求编辑</h2><p>左侧原始需求与需求整合阶段使用相同的展示口径。</p></div>
              <el-button type="primary" :icon="Check" @click="saveItem">保存修改</el-button>
            </div>
            <el-form label-position="top" class="edit-form">
              <div class="form-grid"><el-form-item label="所属模块"><el-input v-model="editForm.module" /></el-form-item><el-form-item label="功能标题"><el-input v-model="editForm.title" /></el-form-item></div>
              <el-form-item label="功能描述"><el-input v-model="editForm.description" type="textarea" :rows="4" /></el-form-item>
              <el-form-item label="补充描述"><el-input v-model="editForm.supplementary_description" type="textarea" :rows="3" /></el-form-item>
              <el-form-item label="验收标准"><el-input v-model="editForm.acceptance_criteria" type="textarea" :rows="3" /></el-form-item>
            </el-form>
            <el-divider />
            <div class="content-head"><div><h2>内容整理</h2><p>调整原文内容组顺序，或移除不属于当前需求的内容。</p></div><span>{{ contentGroups.length }} 组</span></div>
            <div v-for="(group, index) in contentGroups" :key="group.id" class="organize-row" :class="{ 'is-section': group.kind === 'section' }">
              <div class="group-title"><span v-if="group.kind === 'section'" class="level-mark">H{{ group.headingLevel }}</span><strong>{{ group.title }}</strong><span class="group-count">{{ group.blockIds.length }} 块</span></div>
              <div class="block-actions">
                <el-tooltip content="上移"><el-button :icon="ArrowUp" :disabled="index === 0" @click="moveGroup(index, -1)" /></el-tooltip>
                <el-tooltip content="下移"><el-button :icon="ArrowDown" :disabled="index === contentGroups.length - 1" @click="moveGroup(index, 1)" /></el-tooltip>
                <el-tooltip content="移除内容组"><el-button type="danger" :icon="Delete" @click="removeGroup(group)" /></el-tooltip>
              </div>
            </div>
            <el-empty v-if="!contentGroups.length" description="暂无原文内容块" :image-size="72" />
          </section>
        </div>
      </template>
    </el-drawer>

    <el-drawer v-model="integrationVisible" size="min(1120px, 96vw)" title="需求整合">
      <template v-if="integrationItem">
        <div class="review-layout">
          <RequirementSourcePane :item="integrationItem" />
          <section class="review-pane">
            <div class="review-head">
              <div><h2>整合稿</h2><p>整合完成后将自动进入整合审核列表。</p></div>
              <el-button v-if="!isFormalConfirmed" type="primary" :loading="integrating" @click="runIntegration(integrationItem)">{{ integrationDraft ? '重新整合' : '开始整合' }}</el-button>
            </div>
            <template v-if="integrationDraft">
              <el-alert v-if="integrationDraft.review_status === 'rejected'" type="warning" :closable="false" title="该整合稿已被驳回，请重新执行整合后再提交审核。" />
              <el-form label-position="top" :disabled="isFormalConfirmed">
                <el-form-item label="标题"><el-input v-model="integrationDraft.title" /></el-form-item>
                <el-alert v-if="integrationDraft.module_resolution_status === 'needs_review'" class="module-alert" type="warning" :closable="false" title="模型建议中存在未匹配路径，请人工选择正式模块后保存。" />
                <el-form-item label="正式模块（可多选）">
                  <el-tree-select v-model="integrationDraft.formal_module_ids" :data="modules" node-key="id" multiple show-checkbox check-strictly default-expand-all collapse-tags collapse-tags-tooltip :props="moduleTreeProps" placeholder="选择一个或多个父级/叶子模块" />
                  <div class="field-help">选择父节点表示直接归属父节点，不会自动绑定其后代。</div>
                </el-form-item>
                <div v-if="integrationDraft.suggested_module_paths?.length" class="module-suggestions"><span>模型建议</span><el-tag v-for="path in integrationDraft.suggested_module_paths" :key="path" size="small" effect="plain">{{ path }}</el-tag></div>
                <div v-if="integrationDraft.unresolved_module_paths?.length" class="module-suggestions is-unresolved"><span>未匹配</span><el-tag v-for="path in integrationDraft.unresolved_module_paths" :key="path" size="small" type="warning">{{ path }}</el-tag></div>
                <el-form-item label="整合描述"><el-input v-model="integrationDraft.description" type="textarea" :rows="7" /></el-form-item>
                <el-form-item label="验收标准"><el-input v-model="integrationDraft.acceptance_criteria" type="textarea" :rows="4" /></el-form-item>
                <el-form-item label="补充描述"><el-input v-model="integrationDraft.supplementary_description" type="textarea" :rows="3" /></el-form-item>
                <el-form-item label="来源摘要"><el-input v-model="integrationDraft.source_summary" type="textarea" :rows="3" /></el-form-item>
                <el-button v-if="!isFormalConfirmed && integrationDraft.review_status !== 'rejected'" @click="saveIntegration">保存整合稿</el-button>
              </el-form>
            </template>
            <el-empty v-else description="点击开始整合，生成可编辑整合稿" />
          </section>
        </div>
      </template>
    </el-drawer>

    <el-drawer v-model="reviewVisible" size="min(1120px, 96vw)" title="整合审核">
      <template v-if="integrationItem && integrationDraft">
        <div class="review-layout">
          <RequirementSourcePane :item="integrationItem" />
          <section class="review-pane">
            <div class="review-head"><div><h2>整合稿</h2><p>{{ currentReviewStatusLabel }}</p></div><span class="status-pill" :class="currentReviewStatusClass">{{ currentReviewStatusLabel }}</span></div>
            <el-form label-position="top" :disabled="!reviewDraftEditable">
              <el-form-item label="标题"><el-input v-model="integrationDraft.title" /></el-form-item>
              <el-alert v-if="integrationDraft.module_resolution_status === 'needs_review'" class="module-alert" type="warning" :closable="false" title="模块归属待人工处理，解决前不能审核通过。" />
              <el-form-item label="正式模块（可多选）">
                <el-tree-select v-model="integrationDraft.formal_module_ids" :data="modules" node-key="id" multiple show-checkbox check-strictly default-expand-all collapse-tags collapse-tags-tooltip :props="moduleTreeProps" placeholder="选择一个或多个父级/叶子模块" />
                <div class="field-help">完整路径随模块树实时更新；选择父节点不会自动写入后代。</div>
              </el-form-item>
              <div v-if="integrationDraft.unresolved_module_paths?.length" class="module-suggestions is-unresolved"><span>未匹配路径</span><el-tag v-for="path in integrationDraft.unresolved_module_paths" :key="path" size="small" type="warning">{{ path }}</el-tag></div>
              <el-form-item label="整合描述"><el-input v-model="integrationDraft.description" type="textarea" :rows="7" /></el-form-item>
              <el-form-item label="验收标准"><el-input v-model="integrationDraft.acceptance_criteria" type="textarea" :rows="4" /></el-form-item>
              <el-button v-if="reviewDraftEditable" @click="saveIntegration">保存整合稿</el-button>
            </el-form>

            <el-divider />
            <h3>需求关系</h3>
            <div class="inline-fields">
              <el-radio-group v-model="integrationDraft.relationship_mode" :disabled="isFormalConfirmed || integrationDraft.review_status === 'approved'">
                <el-radio-button value="new">新需求</el-radio-button>
                <el-radio-button value="existing">历史需求</el-radio-button>
              </el-radio-group>
              <el-select v-if="integrationDraft.relationship_mode === 'existing'" v-model="integrationDraft.selected_family" filterable placeholder="选择需求族" :disabled="isFormalConfirmed || integrationDraft.review_status === 'approved'">
                <el-option v-for="family in families" :key="family.id" :label="`${family.family_no} / ${family.title} / ${familyModulePaths(family)}`" :value="family.id" />
              </el-select>
              <el-button v-if="!isFormalConfirmed && integrationDraft.review_status !== 'approved'" @click="confirmRelationship">确认关系</el-button>
              <span v-if="integrationDraft.relationship_confirmed" class="status-pill is-success">关系已确认</span>
            </div>

            <el-divider />
            <h3>需求冲突</h3>
            <div v-if="integrationRun?.conflicts?.length" class="review-list">
              <div v-for="conflict in integrationRun.conflicts" :key="conflict.id" class="review-card">
                <div class="card-head"><strong>{{ conflict.title }}</strong><span class="status-pill" :class="conflict.status === 'resolved' ? 'is-success' : 'is-warning'">{{ conflict.status === 'resolved' ? '已处理' : '待处理' }}</span></div>
                <p>当前：{{ conflict.current_statement }}</p><p>历史：{{ conflict.historical_statement }}</p>
                <div class="conflict-fields">
                  <el-select v-model="conflict.resolution" placeholder="处理方式" :disabled="isFormalConfirmed || conflict.status === 'resolved'" @change="prepareConflictResolution(conflict)">
                    <el-option label="采用当前规则" value="current" /><el-option label="保留历史规则" value="historical" /><el-option label="手工规则" value="manual" />
                  </el-select>
                  <el-input v-model="conflict.final_statement" placeholder="最终规则" :disabled="isFormalConfirmed || conflict.status === 'resolved'" />
                  <el-button :disabled="isFormalConfirmed || conflict.status === 'resolved'" @click="resolveConflict(conflict)">确认处理</el-button>
                </div>
              </div>
            </div>
            <p v-else class="muted">无阻断冲突</p>

            <el-divider />
            <h3>待确认问题</h3>
            <div v-if="integrationRun?.open_questions?.length" class="review-list">
              <div v-for="question in integrationRun.open_questions" :key="question.id" class="review-card question-card">
                <div class="card-head"><strong>{{ question.category || '待确认' }}</strong><span class="status-pill" :class="question.status === 'open' ? 'is-warning' : 'is-success'">{{ questionStatusLabel(question.status) }}</span></div>
                <p>{{ question.question }}</p>
                <div class="question-fields">
                  <el-select v-model="question.status" :disabled="isFormalConfirmed"><el-option label="已回答" value="answered" /><el-option label="不适用" value="not_applicable" /><el-option label="接受警告" value="accepted_warning" /></el-select>
                  <el-input v-model="question.answer" placeholder="处理说明" :disabled="isFormalConfirmed" />
                  <el-button :disabled="isFormalConfirmed || question.status === 'open'" @click="handleQuestion(question)">保存处理</el-button>
                </div>
              </div>
            </div>
            <p v-else class="muted">无待确认问题</p>

            <div class="drawer-actions">
              <template v-if="!isFormalConfirmed">
                <el-button type="danger" plain @click="rejectIntegration">驳回整合稿</el-button>
                <el-button v-if="integrationDraft.review_status !== 'approved'" type="success" :disabled="!canApproveIntegration" @click="approveIntegration">审核通过</el-button>
                <el-button type="primary" :disabled="!canConfirmFormal" @click="confirmFormal">确认为正式需求</el-button>
              </template>
              <span v-else class="status-pill is-success">已正式确认</span>
            </div>
          </section>
        </div>
      </template>
    </el-drawer>

  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ArrowDown, ArrowUp, Check, Connection, Delete, MagicStick, Refresh, RefreshRight, View, Warning } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  confirmFormalRequirement,
  confirmRequirementRelationship,
  deleteRequirementContentBlock,
  deleteRequirementItem,
  getRequirementDocumentContent,
  getRequirementDocuments,
  getRequirementFamilies,
  getRequirementIntegration,
  getIntegrationBatches,
  getRequirementParseRuns,
  handleRequirementQuestion,
  integrateRequirementBatch,
  integrateRequirementItem,
  mergeRequirementItems,
  parseRequirementDocument,
  reorderRequirementBlocks,
  resolveRequirementConflict,
  reviewRequirementIntegration,
  retryIntegrationBatch,
  updateRequirementContentBlock,
  updateRequirementIntegration,
  updateRequirementItem,
} from '@/api/requirements'
import { getProjectModuleTree } from '@/api/projectKnowledge'
import { showErrorInfo } from '@/utils/errors'
import RequirementSourcePane from './RequirementSourcePane.vue'
import { useRequirementProjects } from './useRequirementProjects'

const { projects, selectedProject, loadProjects } = useRequirementProjects()
const documents = ref([])
const selectedDocument = ref()
const requirements = ref([])
const orphanBlocks = ref([])
const runs = ref([])
const currentRun = ref()
const loading = ref(false)
const parsing = ref(false)
const integrating = ref(false)
const integrationBatches = ref([])
const activeTab = ref('requirements')
const parseSelection = ref([])
const integrationSelection = ref([])
const integrationTableRef = ref()
const detailVisible = ref(false)
const editingItem = ref()
const orphanTargets = reactive({})
const editForm = reactive({})
const modules = ref([])
const families = ref([])
const integrationVisible = ref(false)
const reviewVisible = ref(false)
const integrationItem = ref()
const integrationDraft = ref()
const integrationRun = ref()
const moduleTreeProps = { label: 'path', children: 'children', disabled: data => data.status !== 'active' }
let batchPollTimer

const contentGroups = computed(() => groupContentBlocks(editingItem.value?.content_blocks || []))
const sourcePreviewItem = computed(() => ({
  ...editingItem.value,
  ...editForm,
}))
const integrationRows = computed(() => requirements.value.filter(row => (
  row.confirm_status !== 'confirmed'
  && (!row.integration_draft || row.integration_draft.status !== 'completed' || row.integration_draft.review_status === 'rejected')
)))
const reviewRows = computed(() => requirements.value.filter(row => (
  row.integration_draft?.status === 'completed' && row.integration_draft.review_status !== 'rejected'
)))
const isFormalConfirmed = computed(() => integrationItem.value?.confirm_status === 'confirmed')
const reviewDraftEditable = computed(() => !isFormalConfirmed.value && integrationDraft.value?.review_status === 'pending')
const hasPendingConflicts = computed(() => integrationRun.value?.conflicts?.some(conflict => conflict.status !== 'resolved') || false)
const hasResolvedModules = computed(() => (
  integrationDraft.value?.module_resolution_status === 'resolved'
  && (integrationDraft.value?.formal_module_ids?.length || 0) > 0
  && !(integrationDraft.value?.unresolved_module_paths?.length)
))
const canApproveIntegration = computed(() => (
  hasResolvedModules.value
  && integrationDraft.value?.relationship_confirmed
  && !hasPendingConflicts.value
))
const canConfirmFormal = computed(() => (
  integrationDraft.value?.review_status === 'approved'
  && integrationDraft.value?.relationship_confirmed
  && !hasPendingConflicts.value
  && hasResolvedModules.value
  && !isFormalConfirmed.value
))
const currentReviewStatusLabel = computed(() => {
  if (isFormalConfirmed.value) return '已正式确认'
  return { pending: '待审核', approved: '已通过', rejected: '已驳回' }[integrationDraft.value?.review_status] || '未整合'
})
const currentReviewStatusClass = computed(() => {
  if (isFormalConfirmed.value || integrationDraft.value?.review_status === 'approved') return 'is-success'
  if (integrationDraft.value?.review_status === 'rejected') return 'is-danger'
  return 'is-warning'
})

function resetSelections() {
  parseSelection.value = []
  integrationSelection.value = []
  integrationTableRef.value?.clearSelection()
}

async function loadDocuments() {
  if (!selectedProject.value) return
  const [{ data: docData }, { data: moduleData }, { data: familyData }] = await Promise.all([
    getRequirementDocuments({ project: selectedProject.value, page_size: 100 }),
    getProjectModuleTree(selectedProject.value),
    getRequirementFamilies({ project: selectedProject.value, page_size: 100 }),
  ])
  documents.value = docData.results || docData
  modules.value = moduleData
  families.value = familyData.results || familyData
  if (!documents.value.some(document => document.id === selectedDocument.value)) selectedDocument.value = documents.value[0]?.id
  if (selectedDocument.value) await loadWorkspace()
}

async function projectChanged() {
  selectedDocument.value = undefined
  resetSelections()
  await loadDocuments()
}

async function loadWorkspace() {
  if (!selectedDocument.value) return
  resetSelections()
  loading.value = true
  try {
    const [{ data: content }, { data: history }] = await Promise.all([
      getRequirementDocumentContent(selectedDocument.value),
      getRequirementParseRuns(selectedDocument.value),
    ])
    requirements.value = content.requirements || []
    orphanBlocks.value = content.orphan_blocks || []
    currentRun.value = content.parse_run
    runs.value = history
    await loadIntegrationBatches()
  } catch (_error) {
    // API 错误由统一错误中心展示。
  } finally {
    loading.value = false
  }
}

async function parseDocument() {
  if (currentRun.value) await ElMessageBox.confirm('重新解析成功后，当前需求将归档并由新结果替换。', '重新解析', { type: 'warning' })
  parsing.value = true
  try {
    await parseRequirementDocument(selectedDocument.value)
    ElMessage.success('解析完成')
    resetSelections()
    await loadDocuments()
  } catch (_error) {
    await loadWorkspace()
  } finally {
    parsing.value = false
  }
}

function openDetail(row) {
  editingItem.value = JSON.parse(JSON.stringify(row))
  Object.assign(editForm, {
    module: row.module,
    title: row.title,
    description: row.description,
    supplementary_description: row.supplementary_description,
    acceptance_criteria: row.acceptance_criteria,
  })
  detailVisible.value = true
}

async function saveItem() {
  const { data } = await updateRequirementItem(editingItem.value.id, editForm)
  ElMessage.success('需求已更新')
  const index = requirements.value.findIndex(item => item.id === data.id)
  requirements.value[index] = data
  openDetail(data)
}

async function archive(row) {
  await ElMessageBox.confirm(`确认归档「${row.title}」？`, '归档需求', { type: 'warning' })
  await deleteRequirementItem(row.id)
  ElMessage.success('需求已归档')
  await loadWorkspace()
}

async function mergeSelected() {
  const title = parseSelection.value[0].title
  await mergeRequirementItems({ ids: parseSelection.value.map(item => item.id), title })
  ElMessage.success('需求已合并，原需求已归档')
  await loadWorkspace()
}

async function integrateSelected() {
  integrating.value = true
  try {
    await integrateRequirementBatch(selectedDocument.value, {
      ids: integrationSelection.value.map(row => row.id),
    })
    ElMessage.success('已提交批量整合任务，可点击刷新查看结果')
    await loadIntegrationBatches()
    await loadWorkspace()
  } catch (_error) {
    // API 错误由统一错误中心展示。
  } finally {
    integrating.value = false
  }
}

async function loadIntegrationBatches() {
  if (!selectedDocument.value) { integrationBatches.value = []; return }
  const { data } = await getIntegrationBatches({ document: selectedDocument.value, page_size: 50 })
  integrationBatches.value = data.results || data
}

function showBatchError(row) {
  showErrorInfo(row.error_info, {
    forceDialog: true,
    actionHandler: ['failed', 'partial_success'].includes(row.status) ? () => retryBatch(row) : null,
  })
}

function showRunError(row) {
  showErrorInfo(row.error_info, {
    forceDialog: true,
    actionHandler: row.status === 'failed' ? () => parseDocument() : null,
  })
}

async function retryBatch(row) {
  try {
    await ElMessageBox.confirm(`将复制 INT-${row.id} 的失败项创建新任务，原记录会保留。`, '重新发起整合任务', { type: 'warning' })
    await retryIntegrationBatch(row.id)
    ElMessage.success('已创建重试任务')
    await loadIntegrationBatches()
  } catch (_error) {
    // 取消操作或 API 错误由统一错误中心处理。
  }
}

async function loadIntegration(row) {
  integrationItem.value = row
  integrationDraft.value = null
  integrationRun.value = null
  try {
    const { data } = await getRequirementIntegration(row.id)
    integrationDraft.value = normalizeIntegrationDraft(data.draft || data)
    integrationRun.value = data.run || null
  } catch (_error) {
    // 404 表示尚未生成整合稿，其余错误由统一错误中心展示。
  }
}

async function openIntegration(row) {
  activeTab.value = 'integration'
  integrationVisible.value = true
  await loadIntegration(row)
}

async function openReview(row) {
  activeTab.value = 'review'
  reviewVisible.value = true
  await loadIntegration(row)
}

async function runIntegration(row) {
  if (row.confirm_status === 'confirmed') return ElMessage.warning('已正式确认的需求不可重新整合')
  integrating.value = true
  try {
    await integrateRequirementItem(row.id)
    await loadIntegration(row)
    await loadWorkspace()
    ElMessage.success('需求整合完成，已进入整合审核')
  } catch (_error) {
    // API 错误由统一错误中心展示。
  } finally {
    integrating.value = false
  }
}

async function saveIntegration() {
  const payload = {
    title: integrationDraft.value.title,
    formal_module_ids: integrationDraft.value.formal_module_ids,
    description: integrationDraft.value.description,
    acceptance_criteria: integrationDraft.value.acceptance_criteria,
    supplementary_description: integrationDraft.value.supplementary_description,
    source_summary: integrationDraft.value.source_summary,
  }
  const { data } = await updateRequirementIntegration(integrationItem.value.id, payload)
  integrationDraft.value = normalizeIntegrationDraft(data)
  ElMessage.success('整合稿已保存')
  await loadWorkspace()
}

async function confirmRelationship() {
  const { data } = await confirmRequirementRelationship(integrationItem.value.id, {
    relationship_mode: integrationDraft.value.relationship_mode,
    selected_family: integrationDraft.value.selected_family,
    change_type: integrationDraft.value.change_type,
  })
  integrationDraft.value = normalizeIntegrationDraft(data)
  ElMessage.success('需求关系已确认')
  await loadWorkspace()
}

function prepareConflictResolution(conflict) {
  if (conflict.resolution === 'current') conflict.final_statement = conflict.current_statement
  if (conflict.resolution === 'historical') conflict.final_statement = conflict.historical_statement
}

async function resolveConflict(conflict) {
  if (!conflict.resolution) return ElMessage.warning('请选择冲突处理方式')
  if (!conflict.final_statement) return ElMessage.warning('请填写最终规则')
  const { data } = await resolveRequirementConflict(conflict.id, {
    resolution: conflict.resolution,
    final_statement: conflict.final_statement,
  })
  Object.assign(conflict, data)
  ElMessage.success('冲突已处理')
}

async function handleQuestion(question) {
  const { data } = await handleRequirementQuestion(question.id, { status: question.status, answer: question.answer })
  Object.assign(question, data)
  ElMessage.success('待确认问题已处理')
}

async function rejectIntegration() {
  await ElMessageBox.confirm('驳回后，该需求将返回需求整合阶段并需要重新整合。', '驳回整合稿', { type: 'warning' })
  await reviewRequirementIntegration(integrationItem.value.id, 'rejected')
  ElMessage.success('整合稿已驳回')
  reviewVisible.value = false
  activeTab.value = 'integration'
  await loadWorkspace()
}

async function approveIntegration() {
  const { data } = await reviewRequirementIntegration(integrationItem.value.id, 'approved')
  integrationDraft.value = normalizeIntegrationDraft(data)
  ElMessage.success('整合稿已审核通过')
  await loadWorkspace()
}

async function confirmFormal() {
  await confirmFormalRequirement(integrationItem.value.id)
  ElMessage.success('已形成正式需求')
  reviewVisible.value = false
  await loadWorkspace()
}

function integrationStatusLabel(row) {
  if (row.integration_draft?.review_status === 'rejected') return '审核驳回'
  return row.integration_draft?.status_label || '未整合'
}

function integrationStatusClass(row) {
  if (row.integration_draft?.review_status === 'rejected' || row.integration_draft?.status === 'failed') return 'is-danger'
  if (row.integration_draft?.status === 'pending') return 'is-running'
  return 'is-muted'
}

function integrationActionLabel(row) {
  return row.integration_draft ? '重新整合' : '开始整合'
}

function relationshipLabel(value) {
  return { new: '新需求', existing: '历史需求' }[value] || '待判定'
}

function reviewStatusLabel(row) {
  if (row.confirm_status === 'confirmed') return '已正式确认'
  return { pending: '待审核', approved: '已通过', rejected: '已驳回' }[row.integration_draft?.review_status] || '未整合'
}

function reviewStatusClass(row) {
  if (row.confirm_status === 'confirmed' || row.integration_draft?.review_status === 'approved') return 'is-success'
  if (row.integration_draft?.review_status === 'rejected') return 'is-danger'
  return 'is-warning'
}

function questionStatusLabel(status) {
  return { open: '待处理', answered: '已回答', not_applicable: '不适用', accepted_warning: '接受警告' }[status] || status
}

function normalizeIntegrationDraft(draft) {
  return {
    ...draft,
    formal_module_ids: draft?.formal_module_ids || (draft?.formal_modules || []).map(module => module.id),
  }
}

function familyModulePaths(family) {
  const modules = family.latest_revision?.modules?.length ? family.latest_revision.modules : family.modules
  return modules?.map(module => module.path).join('；') || '未设置模块'
}

async function assignBlock(block) {
  if (!orphanTargets[block.id]) return ElMessage.warning('请先选择目标需求')
  await updateRequirementContentBlock(block.id, { requirement: orphanTargets[block.id] })
  ElMessage.success('内容已分配')
  await loadWorkspace()
}

function groupContentBlocks(blocks) {
  const groups = []
  let section = null
  for (const block of blocks) {
    if (block.block_type === 'text' && block.heading_level >= 4) {
      section = { id: `section-${block.id}`, kind: 'section', title: block.text, headingLevel: block.heading_level, headingBlock: block, blocks: [], blockIds: [block.id] }
      groups.push(section)
      continue
    }
    if (section) {
      section.blocks.push(block)
      section.blockIds.push(block.id)
    } else {
      groups.push({ id: `block-${block.id}`, kind: 'standalone', title: typeLabel(block.block_type), blocks: [block], blockIds: [block.id] })
    }
  }
  return groups
}

async function moveGroup(index, delta) {
  const groups = [...contentGroups.value]
  ;[groups[index], groups[index + delta]] = [groups[index + delta], groups[index]]
  const { data } = await reorderRequirementBlocks(editingItem.value.id, groups.flatMap(group => group.blockIds))
  editingItem.value = data
  await loadWorkspace()
}

async function removeGroup(group) {
  await ElMessageBox.confirm(`确认移除「${group.title}」及其全部内容？`, '移除内容组', { type: 'warning' })
  await Promise.all(group.blockIds.map(id => deleteRequirementContentBlock(id)))
  const removed = new Set(group.blockIds)
  editingItem.value.content_blocks = editingItem.value.content_blocks.filter(item => !removed.has(item.id))
  await loadWorkspace()
}

function blockCount(row, type) {
  return row.content_blocks?.filter(block => block.block_type === type).length || 0
}

function typeLabel(type) {
  return { text: '文本', table: '表格', image: '图片' }[type] || type
}

onMounted(async () => {
  await loadProjects()
  await loadDocuments()
  batchPollTimer = window.setInterval(async () => {
    if (integrationBatches.value.some(item => ['pending', 'running'].includes(item.status))) {
      await loadWorkspace()
    }
  }, 5000)
})
onBeforeUnmount(() => window.clearInterval(batchPollTimer))
</script>

<style scoped>
.admin-page{width:min(1440px,100%)}
.integration-task-section{margin-top:14px}
.page-head,.control-band,.section-head,.section-actions,.run-summary,.block-head,.block-actions,.orphan-row,.orphan-content,.content-head,.action-cell,.group-title,.review-head,.inline-fields,.drawer-actions,.card-head,.conflict-fields,.question-fields{display:flex;align-items:center}
.page-head,.section-head,.review-head,.card-head{justify-content:space-between;gap:24px}
.page-head{align-items:flex-start;margin-bottom:16px}
h1,h2,p{margin:0}
h1{font-size:24px;color:#172033}
h2{font-size:17px;color:#172033}
.eyebrow,p,.option-meta,.block-head,.content-head span,.muted{color:#64748b;font-size:12px}
.project-select{width:240px}
.control-band{gap:10px;padding:14px;border:1px solid #e6ebf2;border-radius:8px;background:#fff}
.control-band>.el-select{width:360px}
.option-meta{float:right;margin-left:24px}
.section-actions,.run-summary,.inline-fields,.drawer-actions,.conflict-fields,.question-fields{gap:8px}
.section-actions .el-select{width:230px}
.run-summary{margin-left:auto;color:#475569;font-size:13px}
.status-dot{width:8px;height:8px;border-radius:50%;background:#16a34a}
.workspace-tabs{margin-top:14px}
.data-section{border:1px solid #e6ebf2;border-radius:8px;background:#fff;overflow:hidden}
.section-head{min-height:58px;padding:12px 14px;border-bottom:1px solid #edf1f6}
.dense-table{--el-table-border-color:#edf1f6;--el-table-header-bg-color:#fbfcfe;--el-table-header-text-color:#6b7280;--el-table-row-hover-bg-color:#f8fbff;font-size:14px}
.dense-table :deep(.el-table__header th){height:42px;padding:0;font-weight:650}
.dense-table :deep(.el-table__cell){padding:8px 0}
.mono-code{color:#374151;font-family:"SFMono-Regular",Consolas,"Liberation Mono",monospace;font-size:13px;font-variant-numeric:tabular-nums}
.text-badge,.status-pill{display:inline-flex;align-items:center;height:22px;padding:0 8px;border:1px solid #dbe3ec;border-radius:999px;background:#f8fafc;color:#64748b;font-size:12px;white-space:nowrap}
.text-badge{border-color:#fed7aa;background:#fff7ed;color:#9a3412}
.text-badge.is-confirmed,.status-pill.is-success{border-color:#bbf7d0;background:#f0fdf4;color:#15803d}
.status-pill.is-warning{border-color:#fde68a;background:#fffbeb;color:#a16207}
.status-pill.is-danger{border-color:#fecaca;background:#fef2f2;color:#b91c1c}
.status-pill.is-running{border-color:#bfdbfe;background:#eff6ff;color:#2563eb}
.status-pill.is-muted{border-color:#e2e8f0;background:#f8fafc;color:#64748b}
.action-cell,.block-actions{gap:4px;justify-content:center;white-space:nowrap}
.action-cell .el-button,.block-actions .el-button{width:28px;height:28px;margin:0;padding:0}
.empty-state{padding:48px;text-align:center;color:#94a3b8}
.orphan-row{gap:12px;padding:12px 14px;border-bottom:1px solid #edf1f6}
.orphan-content{min-width:0;flex:1;gap:12px}
.orphan-content span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.orphan-row .el-select{width:280px}
.edit-form{padding-right:8px}
.form-grid{display:grid;grid-template-columns:1fr 2fr;gap:12px}
.content-head{align-items:flex-start;justify-content:space-between;margin-bottom:10px}
.content-head p{margin-top:4px}
.content-block{margin-bottom:12px;border:1px solid #dce4ee;border-radius:6px;overflow:hidden}
.content-block.is-section{border-left:3px solid #409eff}
.block-head{min-height:42px;gap:8px;padding:0 10px;background:#f8fafc}
.block-actions{margin-left:auto}
.group-title{gap:8px;color:#25324a;font-size:14px}
.level-mark{display:inline-flex;align-items:center;height:22px;padding:0 7px;border:1px solid #bfdbfe;border-radius:4px;background:#eff6ff;color:#2563eb;font-size:11px;font-weight:700}
.organize-row{display:flex;align-items:center;gap:10px;min-height:46px;margin-bottom:8px;padding:7px 9px;border:1px solid #dce4ee;border-radius:6px;background:#fbfcfe}
.organize-row.is-section{border-left:3px solid #409eff}
.organize-row .group-title{min-width:0;flex:1}
.organize-row .group-title strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.group-count{color:#94a3b8;font-size:12px;white-space:nowrap}
.group-body>:not(:last-child){border-bottom:1px solid #edf1f6}
.block-text{padding:14px 16px;color:#334155;font-size:14px;line-height:1.7;white-space:pre-wrap}
.table-scroll{overflow:auto;padding:12px 16px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:8px;border:1px solid #dbe3ec;text-align:left}
th{background:#f1f5f9}
.source-table :deep(table){width:100%;border-collapse:collapse}
.source-table :deep(th),.source-table :deep(td){padding:8px;border:1px solid #dbe3ec;text-align:left}
.source-table :deep(th){background:#f1f5f9}
.document-image{width:100%;height:360px;background:#f8fafc}
.review-layout{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px;height:calc(100vh - 130px)}
.review-pane{overflow:auto;padding:16px;border:1px solid #e3e8ef;border-radius:8px}
.detail-edit-pane{background:#fff}
.review-pane h3{margin:18px 0 8px;color:#334155}
.review-pane>p{font-size:14px;line-height:1.75;white-space:pre-wrap}
.review-head{align-items:flex-start;margin-bottom:14px}
.review-head p{margin-top:4px}
.inline-fields{align-items:flex-start;flex-wrap:wrap}
.inline-fields .el-select{width:300px}
.review-list{display:grid;gap:10px}
.review-card{padding:12px;border:1px solid #dce4ee;border-radius:6px;background:#fbfcfe}
.review-card p{margin:6px 0;line-height:1.5}
.conflict-fields,.question-fields{margin-top:10px}
.conflict-fields .el-select,.question-fields .el-select{width:150px;flex:none}
.conflict-fields .el-input,.question-fields .el-input{min-width:200px;flex:1}
.drawer-actions{position:sticky;bottom:0;justify-content:flex-end;margin-top:20px;padding:12px 0;background:#fff}
.module-alert{margin-bottom:14px}
.review-pane :deep(.el-tree-select){width:100%}
.field-help{width:100%;margin-top:6px;color:#64748b;font-size:12px;line-height:1.5}
.module-suggestions{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin:-4px 0 14px;color:#64748b;font-size:12px}
.module-suggestions>span:first-child{margin-right:2px;font-weight:600}
.module-suggestions.is-unresolved{padding:8px;border:1px solid #fde68a;border-radius:6px;background:#fffbeb}
@media(max-width:980px){
  .page-head,.control-band,.section-head,.section-actions,.run-summary,.orphan-row,.inline-fields,.conflict-fields,.question-fields{align-items:stretch;flex-direction:column}
  .project-select,.control-band>.el-select,.orphan-row .el-select,.section-actions .el-select,.inline-fields .el-select,.conflict-fields .el-select,.question-fields .el-select{width:100%}
  .run-summary{margin-left:0}
  .form-grid,.review-layout{grid-template-columns:1fr}
  .review-layout{height:auto}
}
</style>
