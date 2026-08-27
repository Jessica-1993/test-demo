import { createRouter, createWebHistory } from 'vue-router'

import Layout from '@/layout/index.vue'
import Login from '@/views/auth/Login.vue'
import Home from '@/views/Home.vue'
import ConfigurationProjects from '@/views/configuration/ConfigurationProjects.vue'
import ConfigurationProjectDetail from '@/views/configuration/ConfigurationProjectDetail.vue'
import ConfigurationModels from '@/views/configuration/ConfigurationModels.vue'
import ConfigurationPrompts from '@/views/configuration/ConfigurationPrompts.vue'
import RequirementDocuments from '@/views/requirements/RequirementDocuments.vue'
import RequirementParsing from '@/views/requirements/RequirementParsing.vue'
import RequirementItems from '@/views/requirements/RequirementItems.vue'
import RequirementVersions from '@/views/requirements/RequirementVersions.vue'
import TestCaseGeneration from '@/views/requirements/TestCaseGeneration.vue'
import TestCaseLibrary from '@/views/requirements/TestCaseLibrary.vue'
import TestCaseDetail from '@/views/requirements/TestCaseDetail.vue'
import TestCaseEnhancement from '@/views/requirements/TestCaseEnhancement.vue'
import DefectLibrary from '@/views/requirements/DefectLibrary.vue'
import { useUserStore } from '@/stores/user'

const routes = [
  {
    path: '/',
    redirect: '/home',
  },
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresGuest: true },
  },
  {
    path: '/',
    component: Layout,
    meta: { requiresAuth: true },
    children: [
      {
        path: 'home',
        name: 'Home',
        component: Home,
        meta: { title: '工作台', module: '工作台', moduleKey: 'home', menuKey: '/home' },
      },
      {
        path: 'configuration',
        redirect: '/configuration/projects',
      },
      {
        path: 'configuration/projects',
        name: 'ConfigurationProjects',
        component: ConfigurationProjects,
        meta: { title: '项目配置', module: '配置中心', moduleKey: 'configuration', menuKey: '/configuration/projects' },
      },
      {
        path: 'configuration/projects/:id',
        name: 'ConfigurationProjectDetail',
        component: ConfigurationProjectDetail,
        meta: { title: '项目详情', module: '配置中心', moduleKey: 'configuration', menuKey: '/configuration/projects' },
      },
      {
        path: 'configuration/models',
        name: 'ConfigurationModels',
        component: ConfigurationModels,
        meta: { title: '大模型配置', module: '配置中心', moduleKey: 'configuration', menuKey: '/configuration/models' },
      },
      {
        path: 'configuration/prompts',
        name: 'ConfigurationPrompts',
        component: ConfigurationPrompts,
        meta: { title: '系统角色配置', module: '配置中心', moduleKey: 'configuration', menuKey: '/configuration/prompts' },
      },
      {
        path: 'requirements',
        redirect: '/requirements/documents',
      },
      {
        path: 'requirements/documents',
        name: 'RequirementDocuments',
        component: RequirementDocuments,
        meta: { title: '需求文档', module: '需求用例中心', moduleKey: 'requirements', menuKey: '/requirements/documents' },
      },
      {
        path: 'requirements/parsing',
        name: 'RequirementParsing',
        component: RequirementParsing,
        meta: { title: '需求解析', module: '需求用例中心', moduleKey: 'requirements', menuKey: '/requirements/parsing' },
      },
      {
        path: 'requirements/items',
        name: 'RequirementItems',
        component: RequirementItems,
        meta: { title: '详细需求', module: '需求用例中心', moduleKey: 'requirements', menuKey: '/requirements/items' },
      },
      {
        path: 'requirements/versions',
        name: 'RequirementVersions',
        component: RequirementVersions,
        meta: { title: '版本管理', module: '需求用例中心', moduleKey: 'requirements', menuKey: '/requirements/versions' },
      },
      {
        path: 'requirements/testcase-generation',
        name: 'TestCaseGeneration',
        component: TestCaseGeneration,
        meta: { title: '用例生成', module: '需求用例中心', moduleKey: 'requirements', menuKey: '/requirements/testcase-generation' },
      },
      {
        path: 'requirements/test-cases',
        name: 'TestCaseLibrary',
        component: TestCaseLibrary,
        meta: { title: '用例库', module: '需求用例中心', moduleKey: 'requirements', menuKey: '/requirements/test-cases' },
      },
      {
        path: 'requirements/testcase-enhancement',
        name: 'TestCaseEnhancement',
        component: TestCaseEnhancement,
        meta: { title: '用例增强', module: '需求用例中心', moduleKey: 'requirements', menuKey: '/requirements/testcase-enhancement' },
      },
      {
        path: 'requirements/defects',
        name: 'DefectLibrary',
        component: DefectLibrary,
        meta: { title: '缺陷库', module: '需求用例中心', moduleKey: 'requirements', menuKey: '/requirements/defects' },
      },
      {
        path: 'requirements/test-cases/:id',
        name: 'TestCaseDetail',
        component: TestCaseDetail,
        meta: { title: '用例详情', module: '需求用例中心', moduleKey: 'requirements', menuKey: '/requirements/test-cases' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, _from, next) => {
  const userStore = useUserStore()

  if (!userStore.initialized) {
    await userStore.initAuth()
  }

  if (to.meta.requiresAuth && !userStore.isAuthenticated) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }

  if (to.meta.requiresGuest && userStore.isAuthenticated) {
    next(to.query.redirect || '/home')
    return
  }

  next()
})

export default router
