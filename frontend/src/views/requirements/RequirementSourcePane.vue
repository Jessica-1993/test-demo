<template>
  <section class="requirement-source-pane">
    <div class="source-head">
      <div>
        <span class="eyebrow">原始需求</span>
        <h2>{{ item.requirement_no }} · {{ item.title }}</h2>
      </div>
      <span class="module-badge">{{ item.module || '未设置模块' }}</span>
    </div>

    <div class="source-fields">
      <article class="source-field">
        <h3>需求描述</h3>
        <p>{{ item.description || '无' }}</p>
      </article>
      <article class="source-field">
        <h3>补充描述</h3>
        <p>{{ item.supplementary_description || '无' }}</p>
      </article>
      <article class="source-field">
        <h3>验收标准</h3>
        <p>{{ item.acceptance_criteria || '无' }}</p>
      </article>
    </div>

    <div class="content-head">
      <h3>原文内容块</h3>
      <span>文本 {{ blockCount('text') }} · 表格 {{ blockCount('table') }} · 图片 {{ blockCount('image') }}</span>
    </div>
    <div v-if="item.content_blocks?.length" class="content-list">
      <article v-for="block in item.content_blocks" :key="block.id" class="content-block">
        <div class="block-meta">
          <span>{{ typeLabel(block.block_type) }}</span>
          <span v-if="block.heading_level">H{{ block.heading_level }}</span>
          <span v-if="block.page">第 {{ block.page }} 页</span>
        </div>
        <p v-if="block.block_type === 'text'" class="block-text">{{ block.text || '空文本块' }}</p>
        <div v-else-if="block.block_type === 'table'" class="table-scroll">
          <div v-if="block.table_data?.html" class="source-table" v-html="block.table_data.html"></div>
          <table v-else-if="block.table_data?.rows?.length">
            <tbody>
              <tr v-for="(row, rowIndex) in block.table_data.rows" :key="rowIndex">
                <component :is="rowIndex === 0 ? 'th' : 'td'" v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell }}</component>
              </tr>
            </tbody>
          </table>
          <p v-else class="empty-content">表格无结构化内容</p>
        </div>
        <div v-else-if="block.block_type === 'image'" class="image-block">
          <el-image
            v-if="block.image_url"
            class="document-image"
            :src="block.image_url"
            :preview-src-list="[block.image_url]"
            fit="contain"
            preview-teleported
          />
          <p v-else class="empty-content">图片地址不可用</p>
          <div v-if="block.image_analysis" class="image-analysis">
            <strong>图片分析摘要</strong>
            <pre v-if="hasImageSummary(block)">{{ formatImageSummary(block.image_analysis.summary) }}</pre>
            <p v-else>{{ block.image_analysis.error_message || '暂无有效分析结果' }}</p>
          </div>
        </div>
      </article>
    </div>
    <el-empty v-else description="暂无原文内容块" :image-size="72" />
  </section>
</template>

<script setup>
const props = defineProps({
  item: { type: Object, required: true },
})

function blockCount(type) {
  return props.item.content_blocks?.filter(block => block.block_type === type).length || 0
}

function typeLabel(type) {
  return { text: '文本', table: '表格', image: '图片' }[type] || type
}

function hasImageSummary(block) {
  const summary = block.image_analysis?.summary
  return summary && (typeof summary !== 'object' || Object.keys(summary).length > 0)
}

function formatImageSummary(summary) {
  if (typeof summary === 'string') return summary
  return JSON.stringify(summary, null, 2)
}
</script>

<style scoped>
.requirement-source-pane{overflow:auto;padding:16px;border:1px solid #e3e8ef;border-radius:8px;background:#f8fafc}
.source-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding-bottom:14px;border-bottom:1px solid #e2e8f0}
.eyebrow{display:block;margin-bottom:5px;color:#64748b;font-size:12px;font-weight:600}
h2,h3,p{margin:0}
h2{color:#172033;font-size:17px;line-height:1.45}
h3{color:#334155;font-size:14px}
.module-badge{display:inline-flex;align-items:center;min-height:24px;padding:0 8px;border:1px solid #dbe3ec;border-radius:999px;background:#fff;color:#475569;font-size:12px;white-space:nowrap}
.source-fields{display:grid;gap:12px;margin-top:14px}
.source-field{padding:12px;border:1px solid #e2e8f0;border-radius:6px;background:#fff}
.source-field p{margin-top:7px;color:#334155;font-size:14px;line-height:1.7;white-space:pre-wrap}
.content-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:18px 0 10px}
.content-head span{color:#64748b;font-size:12px}
.content-list{display:grid;gap:10px}
.content-block{overflow:hidden;border:1px solid #dce4ee;border-radius:6px;background:#fff}
.block-meta{display:flex;align-items:center;gap:8px;min-height:34px;padding:0 10px;border-bottom:1px solid #edf1f6;background:#f8fafc;color:#64748b;font-size:12px}
.block-text{padding:12px;color:#334155;font-size:14px;line-height:1.7;white-space:pre-wrap}
.table-scroll{overflow:auto;padding:12px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:8px;border:1px solid #dbe3ec;text-align:left}
th{background:#f1f5f9}
.source-table :deep(table){width:100%;border-collapse:collapse}
.source-table :deep(th),.source-table :deep(td){padding:8px;border:1px solid #dbe3ec;text-align:left}
.source-table :deep(th){background:#f1f5f9}
.document-image{width:100%;height:320px;background:#f8fafc}
.image-analysis{padding:12px;border-top:1px solid #edf1f6}
.image-analysis strong{color:#334155;font-size:13px}
.image-analysis p,.image-analysis pre{margin:7px 0 0;color:#475569;font-size:13px;line-height:1.6;white-space:pre-wrap;word-break:break-word}
.image-analysis pre{font-family:"SFMono-Regular",Consolas,"Liberation Mono",monospace}
.empty-content{padding:16px;color:#94a3b8;font-size:13px;text-align:center}
@media(max-width:760px){
  .source-head,.content-head{align-items:stretch;flex-direction:column}
  .module-badge{align-self:flex-start}
}
</style>
