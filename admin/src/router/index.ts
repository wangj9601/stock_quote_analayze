import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    component: () => import('@/views/AdminLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/dashboard'
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/DashboardView.vue')
      },
      {
        path: 'logs',
        name: 'Logs',
        component: () => import('@/views/LogsView.vue')
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('@/views/UsersView.vue')
      },
      {
        path: 'quotes',
        name: 'Quotes',
        component: () => import('@/views/QuotesView.vue')
      },
      {
        path: 'indicators',
        name: 'Indicators',
        component: () => import('@/views/IndicatorsView.vue')
      },
      {
        path: 'pvfrs-strategy',
        name: 'PVFRSStrategy',
        component: () => import('@/views/PVFRSStrategyView.vue')
      },
      {
        path: 'datasource',
        name: 'DataSource',
        component: () => import('@/views/DataSourceView.vue')
      },
      {
        path: 'datacollect',
        name: 'DataCollect',
        component: () => import('@/views/DataCollectView.vue')
      },
      {
        path: 'monitoring',
        name: 'Monitoring',
        component: () => import('@/views/MonitoringView.vue')
      },
      {
        path: 'models',
        name: 'Models',
        component: () => import('@/views/ModelsView.vue')
      },
      {
        path: 'content',
        name: 'Content',
        component: () => import('@/views/ContentView.vue')
      },
      {
        path: 'announcements',
        name: 'Announcements',
        component: () => import('@/views/AnnouncementsView.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(process.env.NODE_ENV === 'production' ? '/admin/' : '/'),
  routes
})

// 路由守卫
router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()

  // 如果认证状态还未初始化完成，等待初始化
  if (!authStore.isInitialized) {
    console.log('⏳ 认证状态未初始化，等待初始化完成...')
    await authStore.initAuth()
  }

  console.log(`🔒 路由守卫检查: ${to.path}, 认证状态: ${authStore.isAuthenticated}`)

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    console.log('❌ 需要认证但未登录，重定向到登录页面')
    next('/login')
  } else if (to.path === '/login' && authStore.isAuthenticated) {
    console.log('✅ 已登录用户访问登录页面，重定向到dashboard')
    next('/dashboard')
  } else {
    console.log('✅ 路由检查通过')
    next()
  }
})

export default router 