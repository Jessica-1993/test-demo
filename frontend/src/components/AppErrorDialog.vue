<template>
  <el-dialog
    v-model="errorState.visible"
    class="app-error-dialog"
    width="min(540px, 94vw)"
    :title="current.message"
    append-to-body
  >
    <div v-if="current" class="error-content">
      <section>
        <span>发生原因</span>
        <p>{{ current.reason }}</p>
      </section>
      <section class="solution-block">
        <span>解决办法</span>
        <p>{{ current.solution }}</p>
      </section>
      <el-collapse class="error-details">
        <el-collapse-item title="查看诊断详情" name="details">
          <dl>
            <dt>错误码</dt><dd class="mono-code">{{ current.code }}</dd>
            <dt>错误编号</dt>
            <dd class="trace-cell"><span class="mono-code">{{ current.trace_id || '-' }}</span><el-button v-if="current.trace_id" text type="primary" @click="copyTraceId">复制</el-button></dd>
            <template v-for="(value, key) in current.details || {}" :key="key">
              <dt>{{ detailLabels[key] || key }}</dt><dd>{{ value }}</dd>
            </template>
          </dl>
        </el-collapse-item>
      </el-collapse>
    </div>
    <template #footer>
      <el-button @click="closeErrorDialog">关闭</el-button>
      <el-button v-if="current.action" type="primary" @click="runAction">{{ current.action.label }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { closeErrorDialog, errorState } from '@/utils/errors'

const router = useRouter()
const current = computed(() => errorState.current || {})
const detailLabels = { provider: '模型供应商', http_status: 'HTTP 状态', stage: '业务阶段', task_no: '任务编号', resource: '资源', operation: '操作' }

async function copyTraceId() {
  await navigator.clipboard.writeText(current.value.trace_id)
  ElMessage.success('错误编号已复制')
}

async function runAction() {
  if (errorState.actionHandler) {
    const handler = errorState.actionHandler
    closeErrorDialog()
    await handler()
    return
  }
  const type = current.value.action?.type
  closeErrorDialog()
  if (type === 'login') await router.push({ path: '/login', query: { redirect: router.currentRoute.value.fullPath } })
  else if (type === 'open_model_config') await router.push('/configuration/prompts')
  else if (type === 'refresh') window.location.reload()
}
</script>

<style scoped>
.error-content{display:grid;gap:12px}.error-content section{padding:12px 14px;border:1px solid #e6ebf2;border-radius:8px;background:#fbfcfe}.error-content section span{display:block;margin-bottom:6px;color:#64748b;font-size:12px;font-weight:650}.error-content p{margin:0;color:#334155;font-size:14px;line-height:1.65}.solution-block{border-color:#bfdbfe!important;background:#f8fbff!important}.error-details{border-top:0}.error-details dl{display:grid;grid-template-columns:92px 1fr;margin:0;font-size:13px}.error-details dt,.error-details dd{margin:0;padding:7px 0;border-bottom:1px solid #edf1f6}.error-details dt{color:#64748b}.error-details dd{color:#334155;overflow-wrap:anywhere}.trace-cell{display:flex;align-items:center;justify-content:space-between;gap:8px}.mono-code{font-family:"SFMono-Regular",Consolas,monospace;font-size:12px}@media(max-width:657px){.error-details dl{grid-template-columns:78px 1fr}}
</style>
