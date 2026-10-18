<template>
  <div
    class="admin-layout"
    :class="{ 'sidebar-open': sidebarOpen, 'sidebar-collapsed': sidebarCollapsed }"
  >
    <a class="skip-link" href="#admin-main" @click.prevent="skipToMain">跳到主内容</a>

    <div
      class="sidebar-overlay"
      :class="{ show: sidebarOpen }"
      @click="closeSidebar"
    />

    <aside
      ref="sidebarEl"
      class="admin-sidebar"
      :class="{ open: sidebarOpen }"
      aria-label="管理菜单"
      :inert="sidebarHidden ? true : undefined"
    >
      <div class="sidebar-header">
        <div class="sidebar-header-text">
          <h2 class="sidebar-brand">冰枫堂</h2>
          <p class="sidebar-brand-sub">管理后台 · {{ user?.username || '管理员' }}</p>
        </div>
        <button
          type="button"
          class="sidebar-collapse-btn"
          aria-label="收起菜单"
          title="收起菜单"
          :aria-expanded="!sidebarCollapsed"
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
        <el-button size="small" class="w-full" @click="handleLogout">
          退出登录
        </el-button>
      </div>
    </aside>

    <button
      v-show="sidebarCollapsed"
      ref="expandRailEl"
      type="button"
      class="sidebar-expand-rail"
      aria-label="展开菜单"
      title="展开菜单"
      :aria-expanded="false"
      @click="toggleSidebarCollapsed"
    >
      <el-icon><Expand /></el-icon>
    </button>

    <main id="admin-main" class="admin-main" tabindex="-1" :inert="drawerModal ? true : undefined">
      <header class="admin-topbar">
        <button
          ref="menuToggleEl"
          type="button"
          class="menu-toggle"
          aria-label="打开菜单"
          :aria-expanded="sidebarOpen"
          @click="toggleSidebar"
        >
          <span /><span /><span />
        </button>
        <div class="topbar-title">
          <span class="topbar-page">{{ currentPageName }}</span>
          <span class="topbar-user">{{ user?.username || '管理员' }}</span>
        </div>
        <el-button size="small" class="topbar-logout" @click="handleLogout">
          退出
        </el-button>
      </header>

      <div class="admin-content">
        <div class="admin-crumb">
          <span class="crumb-mark">冰枫堂</span>
          <span class="crumb-sep" aria-hidden="true">/</span>
          <span class="crumb-page">{{ currentPageName }}</span>
        </div>
        <router-view :key="$route.path" />
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
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import {
  DataBoard,
  DataAnalysis,
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
const isMobile = ref(window.innerWidth <= 768)
const sidebarEl = ref<HTMLElement | null>(null)
const menuToggleEl = ref<HTMLButtonElement | null>(null)
const drawerModal = computed(() => isMobile.value && sidebarOpen.value)
const sidebarHidden = computed(() => (isMobile.value ? !sidebarOpen.value : sidebarCollapsed.value))
const expandRailEl = ref<HTMLButtonElement | null>(null)

const menuItems: MenuItem[] = [
  {
    name: '今日看板',
    icon: DataBoard,
    children: [
      { path: '/dashboard', name: '仪表板' },
      { path: '/recommend-brief', name: '策略推荐' },
    ],
  },
  {
    name: '策略',
    icon: Star,
    children: [
      { path: '/gms-watchlist', name: 'GMS 策略版本' },
      { path: '/gms-management', name: 'GMS 回测' },
      { path: '/selection-results', name: '选股管理' },
      { path: '/indicators', name: '指标管理' },
      { path: '/sbbr-management', name: '做小做底 SBBR' },
      { path: '/dblb-management', name: '双底 DBLB' },
      { path: '/cupb-management', name: '杯底 CUPB' },
      { path: '/kgt-management', name: '袋鼠尾 KGT' },
      { path: '/rpe-management', name: '比价 RPE' },
      { path: '/urt-management', name: '上升趋势 URT' },
      { path: '/csb-management', name: '通道突破 CSB' },
    ],
  },
  {
    name: '行情与采集',
    icon: DataAnalysis,
    children: [
      { path: '/quotes', name: '行情数据' },
      { path: '/stock-basic', name: '股票基本信息' },
      { path: '/board-constituents', name: '板块成分股' },
      { path: '/datasource', name: '数据源配置' },
      { path: '/env-sync', name: '环境数据同步' },
      { path: '/datacollect', name: '数据采集' },
      { path: '/collection-workflows', name: '采集流程' },
    ],
  },
  {
    name: '访问与审计',
    icon: Lock,
    children: [
      { path: '/access-management', name: '用户管理' },
      { path: '/monitoring', name: '系统监控' },
      { path: '/models', name: '预测模型' },
      { path: '/logs', name: '系统日志' },
      { path: '/report-management', name: '报告管理' },
    ],
  },
]

const user = computed(() => authStore.user)

const accessManagementPaths = new Set([
  '/access-management',
  '/users',
  '/roles',
  '/permissions',
  '/login-logs',
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
    if (tab === 'roles') return '用户管理 · 角色管理'
    if (tab === 'permissions') return '用户管理 · 权限资源'
    if (tab === 'login-logs') return '用户管理 · 登录日志'
    return '用户管理'
  }
  if (isSelectionResultsRoute()) {
    const tab = route.query.tab
    if (tab === 'triple-volume') return '选股管理 · 3倍量观察股'
    return '选股管理 · 策略选股'
  }
  if (route.path === '/report-management') {
    const tab = route.query.tab
    if (tab === 'sender') return '报告管理 · 发送邮箱配置'
    if (tab === 'push') return '报告管理 · 报告推送配置'
    if (tab === 'logs') return '报告管理 · 报告发送日志'
    return '报告管理'
  }
  if (route.path === '/pvfrs-strategy') return 'PVFRS 交易策略'
  if (route.path === '/pvfrs-management') return 'PVFRS 策略管理'
  if (route.path.startsWith('/reports/')) return '报告详情'
  const hit = findMenuName(route.path)
  return hit || '冰枫堂'
})

function isVisible(el: HTMLElement) {
  return el.getClientRects().length > 0
}
function focusFirstInSidebar() {
  const root = sidebarEl.value
  if (!root) return
  const candidates = root.querySelectorAll<HTMLElement>('button, a')
  for (const el of candidates) {
    if (isVisible(el)) {
      el.focus()
      return
    }
  }
}
function skipToMain() {
  if (drawerModal.value) sidebarOpen.value = false
  nextTick(() => document.getElementById('admin-main')?.focus())
}
function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value
  if (sidebarOpen.value) nextTick(focusFirstInSidebar)
}
function toggleSidebarCollapsed() {
  sidebarCollapsed.value = !sidebarCollapsed.value
  localStorage.setItem(SIDEBAR_COLLAPSED_KEY, sidebarCollapsed.value ? '1' : '0')
  if (sidebarCollapsed.value) {
    sidebarOpen.value = false
    nextTick(() => expandRailEl.value?.focus())
  } else {
    nextTick(focusFirstInSidebar)
  }
}
function closeSidebar() {
  const restoreFocus = drawerModal.value
  sidebarOpen.value = false
  if (restoreFocus) {
    nextTick(() => menuToggleEl.value?.focus())
  }
}
function onResize() {
  const mobile = window.innerWidth <= 768
  if (mobile && !isMobile.value) sidebarOpen.value = false
  isMobile.value = mobile
}
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && sidebarOpen.value) closeSidebar()
}

watch(
  () => route.fullPath,
  () => {
    closeSidebar()
  }
)

onMounted(() => {
  window.addEventListener('resize', onResize)
  window.addEventListener('keydown', onKeydown)
})
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  window.removeEventListener('keydown', onKeydown)
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
  --admin-rise: #c23b3b;
  --admin-fall: #2f9e6b;
  --admin-brand: #6b5420;
  --admin-brand-soft: #f4efe3;
}

.admin-layout ::selection {
  background: #e7d7a8;
  color: #1c1917;
}

.sidebar-brand {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--admin-brand);
  line-height: 1.2;
}

.sidebar-brand-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: #4b5563;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding-top: env(safe-area-inset-top);
  padding-left: env(safe-area-inset-left);
  padding-bottom: env(safe-area-inset-bottom);
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
  box-sizing: border-box;
  width: 44px;
  height: 44px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  color: #4b5563;
  cursor: pointer;
  transition: background-color 0.2s, color 0.2s;
}
.sidebar-collapse-btn:hover,
.sidebar-collapse-btn:active {
  background: #f3f4f6;
  color: #111827;
}
.sidebar-collapse-btn:focus-visible {
  outline: 2px solid var(--admin-brand);
  outline-offset: 2px;
}

.sidebar-expand-rail {
  display: none;
  position: fixed;
  left: env(safe-area-inset-left);
  top: 50%;
  transform: translateY(-50%);
  z-index: 45;
  box-sizing: border-box;
  width: 44px;
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
.sidebar-expand-rail:hover,
.sidebar-expand-rail:active {
  background: var(--admin-brand-soft);
  color: #111827;
}
.sidebar-expand-rail:focus-visible {
  outline: 2px solid var(--admin-brand);
  outline-offset: 2px;
}

.sidebar-nav {
  @apply flex-1 p-4 space-y-2;
  min-height: 0;
  overflow-y: auto;
  scrollbar-color: #d6d3d1 transparent;
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
  background: var(--admin-brand-soft);
  color: var(--admin-brand);
  text-decoration: none;
}

.nav-item:focus-visible {
  outline: 2px solid var(--admin-brand);
  outline-offset: 2px;
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
  min-height: 44px;
}

.admin-main {
  @apply ml-64 min-h-screen;
  transition: margin-left 0.3s ease;
  display: flex;
  flex-direction: column;
}
.admin-main:focus {
  outline: none;
}

.admin-topbar {
  display: none;
  align-items: center;
  gap: 12px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  padding: calc(10px + env(safe-area-inset-top)) calc(12px + env(safe-area-inset-right)) 10px calc(12px + env(safe-area-inset-left));
  position: sticky;
  top: 0;
  z-index: 30;
}

.menu-toggle {
  display: inline-flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  box-sizing: border-box;
  width: 44px;
  height: 44px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  padding: 8px;
  cursor: pointer;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
}
.menu-toggle:active {
  background: #f3f4f6;
}
.menu-toggle span {
  display: block;
  height: 2px;
  background: #374151;
  border-radius: 1px;
}
.menu-toggle:focus-visible {
  outline: 2px solid var(--admin-brand);
  outline-offset: 2px;
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
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.topbar-user {
  font-size: 12px;
  color: #4b5563;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.admin-content {
  @apply p-6;
  flex: 1;
  padding-bottom: 60px;
}

.admin-crumb {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
  margin: -4px 0 16px;
  font-size: 14px;
  color: #374151;
}

.crumb-mark {
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--admin-brand);
}

.crumb-sep {
  color: #4b5563;
}

.crumb-page {
  font-weight: 600;
  color: #111827;
  min-width: 0;
  overflow-wrap: anywhere;
}

.icp-footer {
  background: #f8f9fa;
  border-top: 1px solid #e5e7eb;
  padding: 15px 0 max(15px, env(safe-area-inset-bottom));
  text-align: center;
  margin-top: auto;
}

.icp-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}

.icp-footer a {
  color: #4b5563;
  text-decoration: none;
  font-size: 12px;
}

.icp-footer a:hover {
  color: var(--admin-brand);
}

.icp-footer a:focus-visible {
  outline: 2px solid var(--admin-brand);
  outline-offset: 2px;
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
  }
  .admin-crumb {
    display: none;
  }
  .sidebar-header {
    @apply p-4;
  }
  .sidebar-nav {
    @apply p-3;
  }
  .icp-footer {
    padding: 10px 0 max(10px, env(safe-area-inset-bottom));
  }
  .icp-footer a {
    font-size: 12px;
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

.skip-link {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
.skip-link:focus {
  position: fixed;
  left: max(12px, env(safe-area-inset-left));
  top: max(12px, env(safe-area-inset-top));
  z-index: 80;
  width: auto;
  height: auto;
  margin: 0;
  padding: 8px 12px;
  overflow: visible;
  clip: auto;
  background: #fff;
  color: var(--admin-brand);
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  outline: 2px solid var(--admin-brand);
  outline-offset: 2px;
}

.topbar-logout {
  min-width: 44px;
  min-height: 44px;
}

@media (pointer: coarse) {
  .menu-toggle,
  .sidebar-collapse-btn,
  .sidebar-footer .el-button,
  .topbar-logout {
    min-width: 48px;
    min-height: 48px;
  }
  .menu-toggle,
  .sidebar-collapse-btn {
    width: 48px;
    height: 48px;
  }
  .sidebar-expand-rail {
    width: 48px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .admin-sidebar,
  .admin-main {
    transition: none;
  }
}
</style>
