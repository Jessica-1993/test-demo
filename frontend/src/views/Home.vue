<template>
  <section class="home-page">
    <div class="workspace-head">
      <div class="workspace-title">
        <p class="eyebrow">TestHub Demo</p>
        <h1>工作台</h1>
        <p class="subtitle">
          选择一个功能区进入对应工作空间。
        </p>
      </div>
      <div class="status-strip">
        <div v-for="item in summaries" :key="item.label" class="status-item">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>
    </div>

    <div class="section-title">
      <h2>模块入口</h2>
      <p>可用模块直接进入；规划模块先保留入口位置。</p>
    </div>

    <el-row :gutter="14" class="module-grid">
      <el-col :xs="24" :sm="12" :lg="6" v-for="item in modules" :key="item.title" class="module-col">
        <button class="module-card" type="button" @click="handleModuleClick(item)">
          <span class="icon-box" :class="item.tone">
            <el-icon><component :is="item.icon" /></el-icon>
          </span>
          <span class="module-content">
            <span class="module-header">
              <strong>{{ item.title }}</strong>
              <el-tag size="small" :type="item.ready ? 'success' : 'info'">
                {{ item.ready ? '可用' : '规划中' }}
              </el-tag>
            </span>
            <span>{{ item.description }}</span>
            <span class="feature-list">
              <span v-for="feature in item.features" :key="feature">{{ feature }}</span>
            </span>
            <span class="module-footer">
              <span>{{ item.features.length }} 个功能</span>
              <span>{{ item.ready ? '进入工作区' : '暂未开放' }}</span>
            </span>
          </span>
        </button>
      </el-col>
    </el-row>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Cellphone,
  Coin,
  DataAnalysis,
  DocumentChecked,
  MagicStick,
  Monitor,
  Setting,
} from '@element-plus/icons-vue'

import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const router = useRouter()

const summaries = computed(() => [
  { label: '当前用户', value: userStore.displayName },
  { label: '认证方式', value: 'JWT' },
  { label: '平台阶段', value: 'Demo 骨架' },
])

const modules = [
  {
    title: '需求用例中心',
    icon: MagicStick,
    tone: 'blue',
    description: '需求文档、详细需求、版本管理和 AI 用例生成入库。',
    features: ['需求文档', '详细需求', '用例生成', '用例库'],
    ready: true,
    route: '/requirements/documents',
  },
  {
    title: 'API 自动化',
    icon: DataAnalysis,
    tone: 'cyan',
    description: '接口集合、环境变量、请求执行和历史记录。',
    features: ['接口项目', '自动化执行', '请求历史'],
    ready: false,
  },
  {
    title: 'UI 自动化',
    icon: Monitor,
    tone: 'orange',
    description: '页面元素、脚本编排、套件执行和报告追踪。',
    features: ['元素管理', '用例管理', '执行记录'],
    ready: false,
  },
  {
    title: 'APP 自动化',
    icon: Cellphone,
    tone: 'purple',
    description: '设备、安装包、场景流和移动端执行记录。',
    features: ['设备管理', '场景用例', '执行记录'],
    ready: false,
  },
  {
    title: '执行报告',
    icon: DocumentChecked,
    tone: 'red',
    description: '测试计划、执行结果、趋势统计和报告沉淀。',
    features: ['测试计划', '执行结果', '测试报告'],
    ready: false,
  },
  {
    title: '数据工厂',
    icon: Coin,
    tone: 'teal',
    description: '测试数据模板、生成规则和环境数据准备。',
    features: ['数据模板', '生成规则'],
    ready: false,
  },
  {
    title: '配置中心',
    icon: Setting,
    tone: 'slate',
    description: 'AI 模型、Prompt、执行环境和通知配置。',
    features: ['项目配置', '大模型配置', '系统角色配置'],
    ready: true,
    route: '/configuration/projects',
  },
]

function handleModuleClick(item) {
  if (item.route) {
    router.push(item.route)
    return
  }
  ElMessage.info(`${item.title} 模块规划中`)
}
</script>

<style scoped>
.home-page {
  width: min(1180px, 100%);
  margin: 0 auto;
}

.workspace-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 22px;
  padding: 4px 0 22px;
  border-bottom: 1px solid #e5e7eb;
}

.workspace-title {
  max-width: 620px;
}

.eyebrow {
  margin: 0 0 8px;
  color: #2563eb;
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
}

h1,
h2,
p {
  margin: 0;
}

h1 {
  margin-bottom: 10px;
  font-size: 36px;
  line-height: 1.25;
}

.subtitle,
.section-title p,
.module-content > span:nth-child(2) {
  color: #64748b;
  line-height: 1.7;
}

.status-strip {
  display: flex;
  align-items: stretch;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.status-item {
  display: grid;
  align-content: center;
  gap: 4px;
  min-width: 132px;
  min-height: 58px;
  padding: 0 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;
}

.status-item span {
  color: #64748b;
  font-size: 12px;
}

.status-item strong {
  color: #111827;
  font-size: 15px;
}

.section-title {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.section-title h2 {
  font-size: 22px;
}

.module-grid {
  align-items: stretch;
}

.module-col {
  display: flex;
}

.module-card {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  width: 100%;
  height: 188px;
  margin-bottom: 14px;
  padding: 18px;
  text-align: left;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.module-card:hover {
  border-color: #93c5fd;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
  transform: translateY(-2px);
}

.module-card:disabled,
.module-card[aria-disabled='true'] {
  cursor: default;
}

.icon-box {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 42px;
  width: 42px;
  height: 42px;
  border-radius: 8px;
  font-size: 22px;
}

.blue {
  color: #2563eb;
  background: #dbeafe;
}

.green {
  color: #16a34a;
  background: #dcfce7;
}

.cyan {
  color: #0891b2;
  background: #cffafe;
}

.orange {
  color: #d97706;
  background: #ffedd5;
}

.purple {
  color: #7c3aed;
  background: #ede9fe;
}

.red {
  color: #dc2626;
  background: #fee2e2;
}

.teal {
  color: #0f766e;
  background: #ccfbf1;
}

.slate {
  color: #475569;
  background: #e2e8f0;
}

.module-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  height: 100%;
  width: 100%;
}

.module-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #111827;
}

.module-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: auto;
  padding-top: 4px;
  color: #64748b;
  font-size: 12px;
}

.module-content > span:nth-child(2) {
  display: -webkit-box;
  min-height: 48px;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.feature-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 26px;
  max-height: 58px;
  overflow: hidden;
}

.feature-list span {
  padding: 3px 8px;
  border-radius: 6px;
  color: #475569;
  background: #f1f5f9;
  font-size: 12px;
  line-height: 1.4;
}

@media (max-width: 760px) {
  .workspace-head {
    align-items: stretch;
    flex-direction: column;
  }

  .status-strip {
    justify-content: stretch;
  }

  .status-item {
    flex: 1 1 100%;
  }

  .section-title {
    flex-direction: column;
    align-items: stretch;
  }

  .module-card {
    height: auto;
    min-height: 164px;
  }
}
</style>
