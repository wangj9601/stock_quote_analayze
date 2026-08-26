<template>
  <div class="admin-layout" :class="{ 'sidebar-open': sidebarOpen }">
    <div
      class="sidebar-overlay"
      :class="{ show: sidebarOpen }"
      @click="closeSidebar"
    />

    <aside class="admin-sidebar" :class="{ open: sidebarOpen }">
      <div class="sidebar-header">
        <h2 class="text-xl font-bold text-gray-900">管理后台</h2>
        <p class="text-sm text-gray-600">{{ user?.username || '管理员' }}</p>
      </div>

      <nav class="sidebar-nav">
        <template v-for="item in menuItems" :key="item.path || item.name">
          <div v-if="item.children?.length" class="nav-group">
            <button
              type="button"
              class="nav-item nav-group-toggle"
              :class="{ active: isGroupActive(item) }"
              @click="toggleGroup(item.name)"
            >
              <el-icon class="nav-icon">
                <component :is="item.icon" />
              </el-icon>
              <span class="nav-text">{{ item.name }}</span>
              <el-icon class="nav-chevron" :class="{ expanded: isGroupExpanded(item.name) }">
                <ArrowDown />
              </el-icon>
            </button>
            <div v-show="isGroupExpanded(item.name)" class="nav-children">
              <router-link
                v-for="child in item.children"
                :key="child.path"
                :to="child.path"
                class="nav-item nav-child"
                :class="{ active: isMenuActive(child.path) }"
                @click="closeSidebar"
              >
                <span class="nav-text">{{ child.name }}</span>
              </router-link>
            </div>
          </div>
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
  User,
  TrendCharts,
  Setting,
  DataAnalysis,
  Histogram,
  Monitor,
  Cpu,
  Tickets,
  Select,
  Star,
  Notebook,
  Lock,
  ArrowDown
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

type MenuChild = { path: string; name: string }
type MenuItem = {
  path?: string
  name: string
  icon: typeof DataBoard
  children?: MenuChild[]
}

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const sidebarOpen = ref(false)
const expandedGroups = ref<Record<string, boolean>>({})

const menuItems: MenuItem[] = [
  { path: '/dashboard', name: '仪表板', icon: DataBoard },
  { path: '/access-management', name: '用户与权限', icon: Lock },
  { path: '/quotes', name: '行情数据', icon: TrendCharts },
  { path: '/stock-basic', name: '股票基本信息管理', icon: Tickets },
  { path: '/board-constituents', name: '板块成分股维护', icon: Histogram },
  { path: '/selection-results', name: '选股管理', icon: Select },
  { path: '/gms-watchlist', name: 'GMS策略版本', icon: Star },
  { path: '/triple-volume-observe', name: '3倍量观察股', icon: Notebook },
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


function isGroupActive(item: MenuItem) {
  return (item.children || []).some((child) => child.path === route.path)
}

function isGroupExpanded(groupName: string) {
  return expandedGroups.value[groupName] ?? false
}

function toggleGroup(groupName: string) {
  expandedGroups.value[groupName] = !isGroupExpanded(groupName)
}

function ensureActiveGroupExpanded() {
  for (const item of menuItems) {
    if (item.children?.length && isGroupActive(item)) {
      expandedGroups.value[item.name] = true
    }
  }
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

function isMenuActive(menuPath: string) {
  if (menuPath === '/access-management') {
    return isAccessManagementRoute(route.path)
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
  const hit = findMenuName(route.path)
  return hit || '管理后台'
})

function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value
}
function closeSidebar() {
  sidebarOpen.value = false
}
function onResize() {
  if (window.innerWidth > 768) sidebarOpen.value = false
}

watch(
  () => route.fullPath,
  () => {
    ensureActiveGroupExpanded()
    closeSidebar()
  }
)

onMounted(() => {
  ensureActiveGroupExpanded()
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
}

.sidebar-nav {
  @apply flex-1 p-4 space-y-2;
}

.nav-item {
  @apply flex items-center px-4 py-3 text-gray-700 rounded-lg transition-colors hover:bg-gray-100;
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
  text-decoration: none;
}

.nav-group-toggle {
  width: 100%;
  border: none;
  background: transparent;
  text-align: left;
}

.nav-chevron {
  margin-left: auto;
  font-size: 14px;
  transition: transform 0.2s ease;
}

.nav-chevron.expanded {
  transform: rotate(180deg);
}

.nav-children {
  @apply ml-3 pl-3 border-l border-gray-200 space-y-1 mb-1;
}

.nav-child {
  @apply py-2;
}

.nav-child .nav-text {
  @apply text-sm;
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

/* ≤768：侧栏抽屉，主区全宽 */
@media (max-width: 768px) {
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
