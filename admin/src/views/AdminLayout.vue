<template>
  <div
    class="admin-layout"
    :class="{ 'sidebar-open': sidebarOpen, 'sidebar-collapsed': sidebarCollapsed }"
  >
    <div
      class="sidebar-overlay"
      :class="{ show: sidebarOpen }"
      @click="closeSidebar"
    />

    <aside class="admin-sidebar" :class="{ open: sidebarOpen }">
      <div class="sidebar-header">
        <div class="sidebar-header-text">
          <h2 class="text-xl font-bold text-gray-900">管理后台</h2>
          <p class="text-sm text-gray-600">{{ user?.username || '管理员' }}</p>
        </div>
        <button
          type="button"
          class="sidebar-collapse-btn"
          aria-label="收起菜单"
          title="收起菜单"
          @click="toggleSidebarCollapsed"
        >
          <el-icon><Fold /></el-icon>
        </button>
      </div>

      <nav class="sidebar-nav">
        <template v-for="item in menuItems" :key="item.path || item.name">
          <NavMenuGroup
            v-if="item.children?.length"
            :name="item.name"
            :icon="item.icon"
            :children="item.children"
            :is-child-active="isMenuActive"
            @navigate="closeSidebar"
          />
          <router-link
            v-else
            :to="item.path!"
            class="nav-item"
            :class="{ active: isMenuActive(item.path!) }"
            @click="closeSidebar"
          >
            <el-icon class="nav-icon">
              <component :is="item.icon" />
            </el-icon>
            <span class="nav-text">{{ item.name }}</span>
          </router-link>
        </template>
      </nav>

      <div class="sidebar-footer">
        <el-button type="danger" size="small" class="w-full" @click="handleLogout">
          退出登录
        </el-button>
      </div>
    </aside>

    <button
      v-show="sidebarCollapsed"
      type="button"
      class="sidebar-expand-rail"
      aria-label="展开菜单"
      title="展开菜单"
      @click="toggleSidebarCollapsed"
    >
      <el-icon><Expand /></el-icon>
    </button>

    <main class="admin-main">
      <header class="admin-topbar">
        <button type="button" class="menu-toggle" aria-label="打开菜单" @click="toggleSidebar">
          <span /><span /><span />
        </button>
        <div class="topbar-title">
          <span class="topbar-page">{{ currentPageName }}</span>
          <span class="topbar-user">{{ user?.username || '管理员' }}</span>
        </div>
        <el-button type="danger" size="small" class="topbar-logout" @click="handleLogout">
          退出
        </el-button>
      </header>

      <div class="admin-content">
        <router-view :key="$route.fullPath" />
      </div>

      <footer class="icp-footer">
        <div class="icp-container">
          <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">
            京ICP备18061239号-1
          </a>
        </div>
      </footer>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import {
  DataBoard,
  Document,
  TrendCharts,
  Setting,
  DataAnalysis,
  Histogram,
  Monitor,
  Cpu,
  Tickets,
  Select,
  Star,
  Lock,
  Fold,
  Expand,
} from '@element-plus/icons-vue'
import NavMenuGroup from '@/components/layout/NavMenuGroup.vue'
import { useAuthStore } from '@/stores/auth'

type MenuChild = { path: string; name: string }
type MenuItem = {
  path?: string
  name: string
  icon: typeof DataBoard
  children?: MenuChild[]
}

const SIDEBAR_COLLAPSED_KEY = 'admin_sidebar_collapsed'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const sidebarOpen = ref(false)
const sidebarCollapsed = ref(localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1')

const menuItems: MenuItem[] = [
  { path: '/dashboard', name: '仪表板', icon: DataBoard },
  { path: '/access-management', name: '用户与权限', icon: Lock },
  { path: '/quotes', name: '行情数据', icon: TrendCharts },
  { path: '/stock-basic', name: '股票基本信息', icon: Tickets },
  { path: '/board-constituents', name: '板块成分股维护', icon: Histogram },
  { path: '/selection-results', name: '选股管理', icon: Select },
  { path: '/gms-watchlist', name: 'GMS策略版本', icon: Star },
  { path: '/indicators', name: '指标管理', icon: Histogram },
  { path: '/gms-management', name: 'GMS策略回测管理', icon: TrendCharts },
  {
    name: '形态策略',
    icon: TrendCharts,
    children: [
      { path: '/sbbr-management', name: '做小做底 SBBR' },
      { path: '/dblb-management', name: '双底策略 DBLB' },
      { path: '/cupb-management', name: '杯底形态 CUPB' },
      { path: '/rpe-management', name: '比价效应 RPE' },
    ],
  },
  { path: '/urt-management', name: 'URT上升趋势策略', icon: TrendCharts },
  { path: '/datasource', name: '数据源配置', icon: Setting },
  { path: '/env-sync', name: '环境数据同步', icon: Setting },
  { path: '/datacollect', name: '数据采集', icon: DataAnalysis },
  { path: '/collection-workflows', name: '采集流程', icon: DataAnalysis },
  { path: '/monitoring', name: '系统监控', icon: Monitor },
  { path: '/models', name: '预测模型', icon: Cpu },
  { path: '/logs', name: '系统日志', icon: Document },
  { path: '/report-management', name: '报告管理', icon: Setting }
]

const user = computed(() => authStore.user)

const accessManagementPaths = new Set([
  '/access-management',
  '/users',
  '/roles',
  '/permissions',
])

function isAccessManagementRoute(path: string) {
  if (accessManagementPaths.has(path)) return true
  return /^\/users\/\d+\/permissions$/.test(path) || /^\/roles\/\d+\/permissions$/.test(path)
}

function findMenuName(path: string): string | undefined {
  for (const item of menuItems) {
    if (item.path === path) return item.name
    for (const child of item.children || []) {
      if (child.path === path) return child.name
    }
  }
  return undefined
}

function isSelectionResultsRoute() {
  return route.path === '/selection-results'
}

function isMenuActive(menuPath: string) {
  if (menuPath === '/access-management') {
    return isAccessManagementRoute(route.path)
  }
  if (menuPath === '/selection-results') {
    return isSelectionResultsRoute()
  }
  return route.path === menuPath
}

const currentPageName = computed(() => {
  if (route.path.match(/^\/users\/\d+\/permissions$/)) return '用户权限配置'
  if (route.path.match(/^\/roles\/\d+\/permissions$/)) return '角色权限配置'
  if (isAccessManagementRoute(route.path)) {
    const tab = route.query.tab
    if (tab === 'roles') return '用户与权限 · 角色管理'
    if (tab === 'permissions') return '用户与权限 · 权限资源'
    return '用户与权限'
  }
  if (isSelectionResultsRoute()) {
    const tab = route.query.tab
    if (tab === 'triple-volume') return '选股管理 · 3倍量观察股'
    return '选股管理 · 策略选股'
  }
  const hit = findMenuName(route.path)
  return hit || '管理后台'
})

function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value
}
function toggleSidebarCollapsed() {
  sidebarCollapsed.value = !sidebarCollapsed.value
  localStorage.setItem(SIDEBAR_COLLAPSED_KEY, sidebarCollapsed.value ? '1' : '0')
  if (sidebarCollapsed.value) {
    sidebarOpen.value = false
  }
}
function closeSidebar() {
  sidebarOpen.value = false
}
function onResize() {
  if (window.innerWidth <= 768) {
    sidebarOpen.value = false
  }
}

watch(
  () => route.fullPath,
  () => {
    closeSidebar()
  }
)

onMounted(() => {
  window.addEventListener('resize', onResize)
})
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
})

const handleLogout = async () => {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await authStore.logout()
    router.push('/login')
  } catch {
    // 用户取消
  }
}
</script>

<style scoped lang="postcss">
.admin-layout {
  @apply min-h-screen bg-gray-50;
}

.sidebar-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 40;
}
.sidebar-overlay.show {
  display: block;
}

.admin-sidebar {
  @apply fixed left-0 top-0 h-full w-64 bg-white shadow-lg z-50;
  transition: transform 0.3s ease;
  overflow-x: hidden;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  @apply p-6 border-b border-gray-200;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.sidebar-header-text {
  min-width: 0;
  flex: 1;
}

.sidebar-collapse-btn {
  flex-shrink: 0;
  display: none;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  color: #6b7280;
  cursor: pointer;
  transition: background-color 0.2s, color 0.2s;
}
.sidebar-collapse-btn:hover {
  background: #f3f4f6;
  color: #111827;
}

.sidebar-expand-rail {
  display: none;
  position: fixed;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  z-index: 45;
  width: 28px;
  height: 72px;
  border: 1px solid #e5e7eb;
  border-left: none;
  border-radius: 0 10px 10px 0;
  background: #fff;
  color: #374151;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.06);
  cursor: pointer;
  align-items: center;
  justify-content: center;
}
.sidebar-expand-rail:hover {
  background: #f9fafb;
  color: #2563eb;
}

.sidebar-nav {
  @apply flex-1 p-4 space-y-2;
}

.nav-item {
  @apply flex items-center px-4 py-3 text-gray-700 rounded-lg transition-colors hover:bg-gray-100;
  font-size: 14px;
  line-height: 20px;
  text-decoration: none;
  -webkit-tap-highlight-color: transparent;
  touch-action: manipulation;
  cursor: pointer;
  user-select: none;
}

@media (hover: none) and (pointer: coarse) {
  .nav-item {
    @apply py-4;
    min-height: 48px;
  }
  .nav-item:active {
    @apply bg-gray-200;
  }
}

.nav-item.active {
  @apply bg-blue-50 text-blue-700;
  text-decoration: none;
}

.nav-icon {
  @apply mr-3 text-lg;
}

.nav-text {
  @apply font-medium;
  font-size: inherit;
  line-height: inherit;
  text-decoration: none;
}

.nav-group-toggle {
  width: 100%;
  border: none;
  background: transparent;
  text-align: left;
  font: inherit;
  color: inherit;
}

.nav-chevron {
  margin-left: auto;
  font-size: 14px;
}

.nav-children {
  @apply ml-3 pl-3 border-l border-gray-200 space-y-1 mb-1;
}

.nav-child {
  @apply py-2;
}

.nav-child .nav-text {
  font-size: 13px;
  font-weight: 400;
}

.nav-item,
.nav-item:hover,
.nav-item:focus,
.nav-item:active,
.nav-item.router-link-active,
.nav-item.router-link-exact-active {
  text-decoration: none !important;
}

.sidebar-footer {
  @apply p-4 border-t border-gray-200;
}

.sidebar-footer .el-button {
  -webkit-tap-highlight-color: transparent;
  touch-action: manipulation;
  min-height: 40px;
}

.admin-main {
  @apply ml-64 min-h-screen;
  transition: margin-left 0.3s ease;
  display: flex;
  flex-direction: column;
}

.admin-topbar {
  display: none;
  align-items: center;
  gap: 12px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  padding: 10px 12px;
  position: sticky;
  top: 0;
  z-index: 30;
}

.menu-toggle {
  display: inline-flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  width: 40px;
  height: 40px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  padding: 8px;
  cursor: pointer;
}
.menu-toggle span {
  display: block;
  height: 2px;
  background: #374151;
  border-radius: 1px;
}

.topbar-title {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.topbar-page {
  font-weight: 600;
  color: #111827;
  font-size: 15px;
}
.topbar-user {
  font-size: 12px;
  color: #6b7280;
}

.admin-content {
  @apply p-6;
  flex: 1;
  padding-bottom: 60px;
}

.icp-footer {
  background: #f8f9fa;
  border-top: 1px solid #e5e7eb;
  padding: 15px 0;
  text-align: center;
  margin-top: auto;
}

.icp-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}

.icp-footer a {
  color: #6b7280;
  text-decoration: none;
  font-size: 12px;
}

.icp-footer a:hover {
  color: #3b82f6;
}

@media (max-width: 1024px) {
  .admin-sidebar {
    @apply w-56;
  }
  .admin-main {
    @apply ml-56;
  }
  .admin-content {
    @apply p-5;
  }
}

/* 桌面端：收起侧栏，主区全宽 */
@media (min-width: 769px) {
  .sidebar-collapse-btn {
    display: inline-flex;
  }
  .admin-layout.sidebar-collapsed .admin-sidebar {
    transform: translateX(-100%);
  }
  .admin-layout.sidebar-collapsed .admin-main {
    margin-left: 0 !important;
  }
  .admin-layout.sidebar-collapsed .sidebar-expand-rail {
    display: inline-flex;
  }
}

/* ≤768：侧栏抽屉，主区全宽 */
@media (max-width: 768px) {
  .sidebar-collapse-btn,
  .sidebar-expand-rail {
    display: none !important;
  }
  .admin-sidebar {
    width: min(280px, 82vw);
    transform: translateX(-100%);
  }
  .admin-sidebar.open {
    transform: translateX(0);
  }
  .admin-main {
    margin-left: 0 !important;
  }
  .admin-topbar {
    display: flex;
  }
  .admin-content {
    @apply p-3;
    padding-bottom: calc(48px + env(safe-area-inset-bottom, 0px));
  }
  .sidebar-header {
    @apply p-4;
  }
  .sidebar-nav {
    @apply p-3;
  }
  .icp-footer {
    padding: 10px 0;
  }
  .icp-footer a {
    font-size: 11px;
  }
}

@media (max-width: 480px) {
  .admin-content {
    @apply p-2;
  }
  .topbar-logout {
    padding: 6px 8px;
  }
}
</style>
