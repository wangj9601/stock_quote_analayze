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
        path: 'roles',
        name: 'Roles',
        component: () => import('@/views/RolesView.vue')
      },
      {
        path: 'roles/:id/permissions',
        name: 'RolePermissions',
        component: () => import('@/views/RolePermissionsView.vue')
      },
      {
        path: 'users/:id/permissions',
        name: 'UserPermissions',
        component: () => import('@/views/UserPermissionsView.vue')
      },
      {
        path: 'permissions',
        name: 'Permissions',
        component: () => import('@/views/PermissionsView.vue')
      },
      {
        path: 'quotes',
        name: 'Quotes',
        component: () => import('@/views/QuotesView.vue')
      },
      {
        path: 'stock-basic',
        name: 'StockBasic',
        component: () => import('@/views/StockBasicInfoView.vue')
      },
      {
        path: 'board-constituents',
        name: 'BoardConstituents',
        component: () => import('@/views/BoardConstituentsView.vue')
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
        path: 'pvfrs-management',
        name: 'PVFRSManagement',
        component: () => import('@/views/PVFRSManagementView.vue')
      },
      {
        path: 'gms-management',
        name: 'GMSManagement',
        component: () => import('@/views/GMSManagementView.vue')
      },
      {
        path: 'sbbr-management',
        name: 'SBBRManagement',
        component: () => import('@/views/SBBRManagementView.vue')
      },
      {
        path: 'rpe-management',
        name: 'RPEManagement',
        component: () => import('@/views/RPEManagementView.vue')
      },
      {
        path: 'urt-management',
        name: 'URTManagement',
        component: () => import('@/views/UrtManagementView.vue')
      },
      {
        path: 'triple-volume-observe',
        name: 'TripleVolumeObserve',
        component: () => import('@/views/TripleVolumeObserveView.vue')
      },
      {
        path: 'selection-results',
        name: 'SelectionResults',
        component: () => import('@/views/SelectionResultsView.vue')
      },
      {
        path: 'gms-watchlist',
        name: 'GmsWatchlist',
        component: () => import('@/views/GmsWatchlistView.vue')
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
        redirect: { name: 'Dashboard' }
      },
      {
        path: 'announcements',
        redirect: { name: 'Dashboard' }
      },
      {
        path: 'reports/:id',
        name: 'ReportDetail',
        component: () => import('@/views/ReportDetailView.vue')
      },
      {
        path: 'report-management',
        name: 'ReportManagement',
        component: () => import('@/views/EmailManagementView.vue')
      },
      {
        path: 'email-sender-config',
        redirect: { path: '/report-management', query: { tab: 'sender' } }
      },
      {
        path: 'push-config',
        redirect: { path: '/report-management', query: { tab: 'push' } }
      },
      {
        path: 'email-logs',
        redirect: { path: '/report-management', query: { tab: 'logs' } }
      }
    ]
  }
]

// 根据环境确定基础路径
// 开发环境：如果访问路径包含 /admin/，则使用 /admin/ 作为基础路径
// 否则使用 / 作为基础路径
const getBasePath = () => {
  if (process.env.NODE_ENV === 'production') {
    return '/admin/'
  }
  // 开发环境：检查当前路径是否包含 /admin/
  if (typeof window !== 'undefined' && window.location.pathname.startsWith('/admin/')) {
    return '/admin/'
  }
  return '/'
}

const router = createRouter({
  history: createWebHistory(getBasePath()),
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