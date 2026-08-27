<template>
  <main class="login-page">
    <section class="brand-panel">
      <div class="brand-lockup">
        <span class="brand-mark">T</span>
        <div>
          <p class="eyebrow">TestHub Demo</p>
          <h1>测试管理平台</h1>
        </div>
      </div>
      <p class="brand-copy">
        参考 TestHub 的产品入口，聚合需求分析、用例管理、自动化执行和报告追踪。
      </p>
      <div class="feature-grid">
        <div v-for="feature in features" :key="feature.title" class="feature-item">
          <el-icon><component :is="feature.icon" /></el-icon>
          <span>{{ feature.title }}</span>
        </div>
      </div>
    </section>

    <section class="form-panel" aria-label="登录表单">
      <div class="form-header">
        <h2>欢迎回来</h2>
        <p>使用 Django 用户账号登录 TestHub Demo。</p>
      </div>

      <el-alert
        v-if="error"
        type="error"
        :closable="false"
        :title="error"
        class="login-alert"
      />

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @submit.prevent="handleLogin"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model.trim="form.username"
            :prefix-icon="User"
            autocomplete="username"
            placeholder="请输入用户名"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            :prefix-icon="Lock"
            autocomplete="current-password"
            placeholder="请输入密码"
            show-password
            type="password"
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          class="login-button"
          :loading="loading"
          @click="handleLogin"
        >
          登录
        </el-button>
      </el-form>

      <p class="form-tip">没有账号时，先在后端使用 createsuperuser 创建 Django 用户。</p>
    </section>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Cpu, DataLine, DocumentChecked, Lock, MagicStick, Monitor, User } from '@element-plus/icons-vue'

import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref()
const loading = ref(false)
const error = ref('')
const form = reactive({
  username: '',
  password: '',
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const features = [
  { title: 'AI 用例生成', icon: MagicStick },
  { title: 'API 自动化', icon: Cpu },
  { title: 'UI 自动化', icon: Monitor },
  { title: '执行报告', icon: DocumentChecked },
  { title: '数据工厂', icon: DataLine },
]

async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  error.value = ''

  try {
    await userStore.login(form)
    ElMessage.success('登录成功')
    router.push(route.query.redirect || '/home')
  } catch (err) {
    const data = err.response?.data
    error.value = data?.non_field_errors?.[0] || data?.detail || data?.error || err.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(360px, 480px);
  min-height: 100vh;
  color: #111827;
  background: #f5f7fb;
}

.brand-panel {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 28px;
  padding: 64px;
  color: #ffffff;
  background:
    linear-gradient(135deg, rgba(17, 24, 39, 0.92), rgba(37, 99, 235, 0.84)),
    url('https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1400&q=80') center/cover;
}

.brand-lockup {
  display: flex;
  align-items: center;
  gap: 16px;
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  border-radius: 8px;
  font-size: 24px;
  font-weight: 800;
  color: #2563eb;
  background: #ffffff;
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
  opacity: 0.82;
}

h1,
h2,
p {
  margin: 0;
}

h1 {
  font-size: 42px;
  line-height: 1.16;
}

.brand-copy {
  max-width: 620px;
  color: rgba(255, 255, 255, 0.84);
  font-size: 18px;
  line-height: 1.8;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(180px, 1fr));
  gap: 14px;
  max-width: 560px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 48px;
  padding: 0 14px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.12);
}

.form-panel {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 56px;
  background: #ffffff;
}

.form-header {
  margin-bottom: 28px;
}

.form-header h2 {
  margin-bottom: 10px;
  font-size: 28px;
}

.form-header p,
.form-tip {
  color: #64748b;
  line-height: 1.7;
}

.login-alert {
  margin-bottom: 18px;
}

.login-button {
  width: 100%;
  margin-top: 8px;
}

.form-tip {
  margin-top: 18px;
  font-size: 13px;
}

@media (max-width: 900px) {
  .login-page {
    grid-template-columns: 1fr;
  }

  .brand-panel {
    min-height: 360px;
    padding: 36px 24px;
  }

  .form-panel {
    padding: 32px 24px;
  }
}

@media (max-width: 560px) {
  h1 {
    font-size: 32px;
  }

  .feature-grid {
    grid-template-columns: 1fr;
  }
}
</style>
