<template>
  <el-container class="app-shell">
    <el-aside v-if="showSidebar" :width="`${sidebarWidth}px`" class="sidebar">
      <div class="brand">
        <span class="brand-mark">T</span>
        <span>TestHub Demo</span>
      </div>
      <button class="home-link" type="button" @click="router.push('/home')">
        <el-icon><House /></el-icon>
        <span>工作台</span>
      </button>
      <div class="menu-heading">{{ menuTitle }}</div>
      <el-menu :default-active="activeMenu" router>
        <el-menu-item
          v-for="item in currentMenu"
          :key="item.index"
          :index="item.index"
          :disabled="item.disabled"
          @click="handleMenuClick(item)"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
      <div class="sidebar-resizer" role="separator" aria-orientation="vertical" title="拖动调整导航宽度" @mousedown="startSidebarResize" />
    </el-aside>
    <el-container>
      <el-header class="topbar">
        <div v-if="isHome" class="topbar-brand">
          <span class="brand-mark small">T</span>
          <span>TestHub Demo</span>
        </div>
        <el-breadcrumb v-else separator="/">
          <el-breadcrumb-item v-if="!isHome" :to="{ path: '/home' }">工作台</el-breadcrumb-item>
          <el-breadcrumb-item v-if="route.meta.module && route.meta.module !== '工作台'">{{ route.meta.module }}</el-breadcrumb-item>
          <el-breadcrumb-item>{{ routeTitle }}</el-breadcrumb-item>
        </el-breadcrumb>
        <div class="user-actions">
          <el-avatar :size="30" :icon="UserFilled" />
          <span>{{ userStore.displayName }}</span>
          <el-button text :icon="SwitchButton" @click="handleLogout">退出</el-button>
        </div>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Cellphone,
  Coin,
  Connection,
  DataAnalysis,
  Document,
  DocumentChecked,
  Files,
  House,
  MagicStick,
  EditPen,
  Monitor,
  Setting,
  SwitchButton,
  UserFilled,
  WarningFilled,
} from '@element-plus/icons-vue'

import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const sidebarWidth = ref(Number(window.localStorage.getItem('testhub-sidebar-width')) || 232)
let resizingSidebar = false

const activeMenu = computed(() => route.meta.menuKey || route.path)
const routeTitle = computed(() => route.meta.title || route.name || '工作台')
const moduleKey = computed(() => route.meta.moduleKey || 'home')
const isHome = computed(() => moduleKey.value === 'home')
const showSidebar = computed(() => !isHome.value)
const menuTitle = computed(() => {
  return route.meta.module || '功能菜单'
})

const moduleMenus = {
  home: [
    { index: '/requirements/documents', label: '需求用例中心', icon: MagicStick },
    { index: '/configuration/projects', label: '配置中心', icon: Setting },
    { index: 'planned-api-testing', label: 'API 自动化', icon: DataAnalysis, disabled: true },
    { index: 'planned-ui-automation', label: 'UI 自动化', icon: Monitor, disabled: true },
    { index: 'planned-app-automation', label: 'APP 自动化', icon: Cellphone, disabled: true },
    { index: 'planned-reports', label: '执行报告', icon: DocumentChecked, disabled: true },
    { index: 'planned-data-factory', label: '数据工厂', icon: Coin, disabled: true },
  ],
  requirements: [
    { index: '/requirements/documents', label: '需求文档', icon: Files },
    { index: '/requirements/parsing', label: '需求解析', icon: MagicStick },
    { index: '/requirements/items', label: '详细需求', icon: Document },
    { index: '/requirements/versions', label: '版本管理', icon: DocumentChecked },
    { index: '/requirements/testcase-generation', label: '用例生成', icon: MagicStick },
    { index: '/requirements/testcase-enhancement', label: '用例增强', icon: MagicStick },
    { index: '/requirements/test-cases', label: '用例库', icon: DocumentChecked },
    { index: '/requirements/defects', label: '缺陷库', icon: WarningFilled },
  ],
  configuration: [
    { index: '/configuration/projects', label: '项目配置', icon: Setting },
    { index: '/configuration/models', label: '大模型配置', icon: Connection },
    { index: '/configuration/prompts', label: '系统角色配置', icon: EditPen },
  ],
}

const currentMenu = computed(() => moduleMenus[moduleKey.value] || moduleMenus.home)

function handleMenuClick(item) {
  if (item.disabled) {
    ElMessage.info(`${item.label} 模块规划中`)
  }
}

function startSidebarResize(event) {
  resizingSidebar = true
  document.body.classList.add('is-resizing-sidebar')
  window.addEventListener('mousemove', handleSidebarResize)
  window.addEventListener('mouseup', stopSidebarResize)
  event.preventDefault()
}

function handleSidebarResize(event) {
  if (!resizingSidebar) return
  const nextWidth = Math.min(Math.max(event.clientX, 188), 320)
  sidebarWidth.value = nextWidth
}

function stopSidebarResize() {
  if (!resizingSidebar) return
  resizingSidebar = false
  window.localStorage.setItem('testhub-sidebar-width', String(sidebarWidth.value))
  document.body.classList.remove('is-resizing-sidebar')
  window.removeEventListener('mousemove', handleSidebarResize)
  window.removeEventListener('mouseup', stopSidebarResize)
}

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确认退出当前账号？', '退出登录', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  } catch {
    // User cancelled.
  }
}

onBeforeUnmount(() => {
  stopSidebarResize()
})
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
}

.sidebar {
  position: relative;
  flex-shrink: 0;
  background: #ffffff;
  border-right: 1px solid #e5e7eb;
  user-select: none;
  transition: width 120ms ease;
}

.sidebar-resizer {
  position: absolute;
  top: 0;
  right: -4px;
  z-index: 3;
  width: 8px;
  height: 100%;
  cursor: col-resize;
}

.sidebar-resizer::after {
  position: absolute;
  top: 0;
  right: 3px;
  width: 1px;
  height: 100%;
  background: transparent;
  content: "";
  transition: background 150ms ease;
}

.sidebar-resizer:hover::after {
  background: #93c5fd;
}

:global(body.is-resizing-sidebar) {
  cursor: col-resize;
  user-select: none;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 60px;
  padding: 0 18px;
  font-size: 17px;
  font-weight: 700;
  color: #111827;
}

.home-link {
  display: flex;
  align-items: center;
  gap: 10px;
  width: calc(100% - 24px);
  height: 40px;
  margin: 10px 12px 8px;
  padding: 0 12px;
  color: #475569;
  text-align: left;
  border: 0;
  border-radius: 6px;
  background: #f8fafc;
  cursor: pointer;
}

.home-link:hover {
  color: #2563eb;
  background: #eff6ff;
}

.menu-heading {
  padding: 10px 18px 8px;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 700;
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 6px;
  color: #ffffff;
  background: #2563eb;
}

.brand-mark.small {
  width: 28px;
  height: 28px;
  font-size: 16px;
}

.topbar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #111827;
  font-size: 16px;
  font-weight: 700;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: 60px;
  font-weight: 600;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
}

.user-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #475569;
  font-size: 14px;
  font-weight: 500;
}

.main {
  padding: 24px;
}

@media (max-width: 760px) {
  .sidebar {
    width: 188px !important;
    transition: none;
  }

  .sidebar-resizer {
    display: none;
  }

  .brand {
    padding: 0 12px;
    font-size: 15px;
  }

  .main {
    padding: 16px;
  }
}
</style>
