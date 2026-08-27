<template>
  <div class="admin-page">
    <header class="page-head">
      <div><span class="eyebrow">需求资产</span><h1>需求文档</h1><p>管理七牛云中的原始需求文件，解析操作在需求解析工作台中进行。</p></div>
      <el-select v-model="selectedProject" class="project-select" @change="loadDocuments">
        <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
      </el-select>
    </header>

    <section class="upload-band">
      <el-upload ref="uploadRef" drag :auto-upload="false" :limit="1" :on-change="onFileChange" :on-remove="onFileRemove" accept=".pdf,.docx,.txt,.md">
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div>拖放需求文档，或点击选择</div>
      </el-upload>
      <div class="upload-actions">
        <el-input v-model="title" placeholder="文档标题（默认使用文件名）" />
        <el-button type="primary" :icon="Upload" :loading="uploading" :disabled="!selectedFile" @click="submitUpload">上传文档</el-button>
      </div>
    </section>

    <section class="data-section">
      <div class="section-head">
        <div><h2>文档列表</h2><p>数据库索引与七牛文档对象保持同步。</p></div>
        <div class="toolbar">
          <el-input v-model="keyword" clearable placeholder="搜索文件名" :prefix-icon="Search" @keyup.enter="loadDocuments" />
          <el-button :icon="Refresh" :loading="syncing" @click="syncQiniu">同步七牛</el-button>
        </div>
      </div>
      <el-table v-loading="loading" :data="documents" class="dense-table">
        <el-table-column prop="title" label="文档" min-width="220"><template #default="{ row }"><strong>{{ row.title }}</strong><div class="muted">{{ row.original_filename }}</div></template></el-table-column>
        <el-table-column prop="document_type" label="类型" width="90"><template #default="{ row }"><span class="text-badge">{{ row.document_type.toUpperCase() }}</span></template></el-table-column>
        <el-table-column prop="file_size" label="大小" width="110"><template #default="{ row }">{{ formatSize(row.file_size) }}</template></el-table-column>
        <el-table-column prop="status_label" label="解析状态" width="110" />
        <el-table-column prop="uploaded_by_name" label="上传人" width="110" />
        <el-table-column prop="created_at" label="上传时间" width="180"><template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template></el-table-column>
        <el-table-column label="操作" width="110" align="center">
          <template #default="{ row }"><div class="action-cell">
            <el-tooltip content="下载原文"><el-button :icon="Download" @click="download(row)" /></el-tooltip>
            <el-tooltip content="删除文档"><el-button type="danger" :icon="Delete" @click="remove(row)" /></el-tooltip>
          </div></template>
        </el-table-column>
      </el-table>
      <div class="pagination-bar"><el-pagination v-model:current-page="page" v-model:page-size="pageSize" layout="total, sizes, prev, pager, next" :total="total" @current-change="loadDocuments" @size-change="loadDocuments" /></div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { Delete, Download, Refresh, Search, Upload, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteRequirementDocument, getRequirementDocuments, syncRequirementDocuments, uploadRequirementDocument } from '@/api/requirements'
import { useRequirementProjects } from './useRequirementProjects'

const { projects, selectedProject, loadProjects } = useRequirementProjects()
const documents = ref([]), loading = ref(false), uploading = ref(false), syncing = ref(false)
const selectedFile = ref(), title = ref(''), keyword = ref(''), uploadRef = ref()
const page = ref(1), pageSize = ref(10), total = ref(0)

async function loadDocuments() {
  if (!selectedProject.value) return
  loading.value = true
  try { const { data } = await getRequirementDocuments({ project: selectedProject.value, search: keyword.value, page: page.value, page_size: pageSize.value }); documents.value = data.results || data; total.value = data.count ?? documents.value.length } finally { loading.value = false }
}
function onFileChange(file) { selectedFile.value = file.raw }
function onFileRemove() { selectedFile.value = undefined }
async function submitUpload() {
  const payload = new FormData(); payload.append('project', selectedProject.value); payload.append('file', selectedFile.value); if (title.value) payload.append('title', title.value)
  uploading.value = true
  try { await uploadRequirementDocument(payload); ElMessage.success('文档已上传，尚未解析'); uploadRef.value.clearFiles(); selectedFile.value = undefined; title.value = ''; await loadDocuments() } catch (_error) { /* 统一错误中心已展示 */ } finally { uploading.value = false }
}
async function syncQiniu() { syncing.value = true; try { const { data } = await syncRequirementDocuments({ project: selectedProject.value }); ElMessage.success(`同步完成：新增 ${data.created}，更新 ${data.updated}`); await loadDocuments() } catch (_error) { /* 统一错误中心已展示 */ } finally { syncing.value = false } }
function download(row) { window.open(row.qiniu_url, '_blank', 'noopener') }
async function remove(row) {
  try {
    await ElMessageBox.confirm(`确认删除文档「${row.title}」？`, '删除文档', { type: 'warning' })
    await deleteRequirementDocument(row.id)
    ElMessage.success('文档及云端文件已删除')
    await loadDocuments()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    // API 错误由统一错误中心展示。
  }
}
function formatSize(size) { if (!size) return '0 B'; if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`; return `${(size / 1024 / 1024).toFixed(1)} MB` }
onMounted(async () => { await loadProjects(); await loadDocuments() })
</script>

<style scoped>
.admin-page{width:min(1440px,100%)}.page-head,.section-head,.toolbar,.action-cell{display:flex;align-items:center}.page-head,.section-head{justify-content:space-between;gap:24px}.page-head{margin-bottom:16px;align-items:flex-start}h1,h2,p{margin:0}h1{font-size:24px;color:#172033}h2{font-size:17px;color:#172033}.eyebrow,.muted,p{color:#64748b;font-size:12px}.project-select{width:240px}.upload-band{display:grid;grid-template-columns:1fr 340px;gap:14px;margin-bottom:16px;padding:14px;border:1px solid #e6ebf2;border-radius:8px;background:#fff}.upload-actions{display:flex;flex-direction:column;justify-content:center;gap:12px}.upload-icon{font-size:30px}.data-section{border:1px solid #e6ebf2;border-radius:8px;background:#fff}.section-head{min-height:58px;padding:12px 14px;border-bottom:1px solid #edf1f6}.toolbar{gap:8px}.toolbar .el-input{width:260px}.dense-table{font-size:14px}.dense-table :deep(.el-table__cell){padding:8px 0}.text-badge{padding:2px 8px;border:1px solid #e2e8f0;border-radius:999px;background:#f1f5f9;font-size:12px}.action-cell{justify-content:center;gap:4px}.action-cell .el-button{width:28px;height:28px;margin:0;padding:0}.pagination-bar{display:flex;justify-content:flex-end;padding:12px 14px;border-top:1px solid #edf1f6}@media(max-width:760px){.page-head,.section-head,.toolbar{align-items:stretch;flex-direction:column}.project-select,.toolbar .el-input{width:100%}.upload-band{grid-template-columns:1fr}}
</style>
