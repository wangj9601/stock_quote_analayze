<template>
  <div class="admin-layout">
    <!-- 侧边栏 -->
    <aside class="admin-sidebar">
      <div class="sidebar-header">
        <h2 class="text-xl font-bold text-gray-900">📊 管理后台</h2>
        <p class="text-sm text-gray-600">{{ user?.username || '管理员' }}</p>
      </div>
      
      <nav class="sidebar-nav">
        <router-link
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: $route.path === item.path }"
        >
          <el-icon class="nav-icon" :key="'icon-' + item.path">
            <component :is="item.icon" />
          </el-icon>
          <span class="nav-text" :key="'text-' + item.path">{{ item.name }}</span>
        </router-link>
      </nav>
      
      <div class="sidebar-footer">
        <el-button
          type="danger"
          size="small"
          class="w-full"
          @click="handleLogout"
        >
          退出登录
        </el-button>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="admin-main">
      <!-- 页面内容 -->
      <div class="admin-content">
        <router-view :key="$route.fullPath" />
      </div>
      
      <!-- ICP备案信息 -->
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
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
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
  Notebook
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

// 菜单项配置
const menuItems = [
  { path: '/dashboard', name: '仪表板', icon: DataBoard },
  { path: '/users', name: '用户管理', icon: User },
  { path: '/quotes', name: '行情数据', icon: TrendCharts },
  { path: '/stock-basic', name: '股票基本信息管理', icon: Tickets },
  { path: '/board-constituents', name: '板块成分股维护', icon: Histogram },
  { path: '/selection-results', name: '选股管理', icon: Select },
  { path: '/gms-watchlist', name: 'GMS策略版本', icon: Star },
  { path: '/triple-volume-observe', name: '3倍量观察股', icon: Notebook },
  { path: '/indicators', name: '指标管理', icon: Histogram },
  { path: '/gms-management', name: 'GMS策略回测管理', icon: TrendCharts },
  { path: '/datasource', name: '数据源配置', icon: Setting },
  { path: '/datacollect', name: '数据采集', icon: DataAnalysis },
  { path: '/monitoring', name: '系统监控', icon: Monitor },
  { path: '/models', name: '预测模型', icon: Cpu },
  { path: '/logs', name: '系统日志', icon: Document },
  { path: '/report-management', name: '报告管理', icon: Setting }
]

// 计算属性
const user = computed(() => authStore.user)

// 生命周期钩子
onMounted(() => {
  console.log('🏗️ AdminLayout已挂载')
  if (authStore.isAuthenticated) {
    console.log('✅ 认证状态正常，用户:', authStore.user?.username)
  }
})

// 方法
const handleLogout = async () => {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await authStore.logout()
    router.push('/login')
  } catch (err) {
    // 用户取消
  }
}
</script>

<style scoped lang="postcss">
.admin-layout {
  @apply min-h-screen bg-gray-50;
}

.admin-sidebar {
  @apply fixed left-0 top-0 h-full w-64 bg-white shadow-lg z-50;
  transition: width 0.3s ease, transform 0.3s ease;
  overflow-x: hidden;
  overflow-y: auto;
}

/* 移动端侧边栏优化 */
@media (max-width: 768px) {
  .admin-sidebar {
    @apply w-48;
    transform: translateX(0);
  }
  
  /* 添加触摸滚动支持 */
  .admin-sidebar::-webkit-scrollbar {
    width: 4px;
  }
  
  .admin-sidebar::-webkit-scrollbar-track {
    background: transparent;
  }
  
  .admin-sidebar::-webkit-scrollbar-thumb {
    background: rgba(156, 163, 175, 0.5);
    border-radius: 2px;
  }
  
  .admin-sidebar::-webkit-scrollbar-thumb:hover {
    background: rgba(156, 163, 175, 0.8);
  }
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
  /* 触摸优化 */
  -webkit-tap-highlight-color: transparent;
  touch-action: manipulation;
  cursor: pointer;
  user-select: none;
}

/* 触摸设备优化 */
@media (hover: none) and (pointer: coarse) {
  .nav-item {
    @apply py-4; /* 增加触摸区域 */
    min-height: 48px; /* 确保触摸区域足够大 */
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

/* 确保所有导航链接都没有下划线 */
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
  /* 触摸优化 */
  -webkit-tap-highlight-color: transparent;
  touch-action: manipulation;
  min-height: 40px; /* 确保触摸区域足够大 */
}

/* 触摸设备优化 */
@media (hover: none) and (pointer: coarse) {
  .sidebar-footer .el-button {
    min-height: 44px;
    @apply py-2;
  }
}

.admin-main {
  @apply ml-64 min-h-screen;
  padding-left: 1rem; /* 增加左边距 */
  transition: margin-left 0.3s ease, padding-left 0.3s ease;
  display: flex;
  flex-direction: column;
}

.admin-content {
  @apply p-6;
  transition: padding 0.3s ease;
  flex: 1;
  padding-bottom: 60px; /* 为ICP备案留出空间 */
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .admin-sidebar {
    @apply w-56;
  }
  
  .admin-main {
    @apply ml-56;
    padding-left: 0.75rem;
  }
  
  .admin-content {
    @apply p-5;
  }
}

@media (max-width: 768px) {
  .admin-sidebar {
    @apply w-48;
  }
  
  .admin-main {
    @apply ml-48;
    padding-left: 0.5rem;
  }
  
  .admin-content {
    @apply p-4;
  }
  
  .sidebar-header {
    @apply p-4;
  }
  
  .sidebar-nav {
    @apply p-3;
  }
  
  .nav-text {
    @apply text-sm;
  }
  
  .admin-header {
    @apply px-4 py-3;
  }
  
  .header-left h1 {
    @apply text-xl;
  }
  
  .breadcrumb {
    @apply text-xs;
  }
}

@media (max-width: 640px) {
  .admin-sidebar {
    @apply w-40;
  }
  
  .admin-main {
    @apply ml-40;
    padding-left: 0.25rem;
  }
  
  .admin-content {
    @apply p-3;
  }
  
  .sidebar-header {
    @apply p-3;
  }
  
  .sidebar-header h2 {
    @apply text-lg;
  }
  
  .sidebar-header p {
    @apply text-xs;
  }
  
  .nav-item {
    @apply px-3 py-2;
  }
  
  .nav-icon {
    @apply mr-2 text-base;
  }
  
  .nav-text {
    @apply text-xs;
  }
  
  .admin-header {
    @apply px-3 py-2;
  }
  
  .header-left h1 {
    @apply text-lg;
  }
  
  .user-name {
    @apply text-xs;
  }
  
  .user-avatar {
    @apply w-6 h-6;
  }
}

/* 超小屏幕适配 */
@media (max-width: 480px) {
  .admin-sidebar {
    @apply w-36;
  }
  
  .admin-main {
    @apply ml-36;
    padding-left: 0.125rem;
  }
  
  .admin-content {
    @apply p-2;
  }
  
  .sidebar-header {
    @apply p-2;
  }
  
  .sidebar-header h2 {
    @apply text-base;
  }
  
  .nav-item {
    @apply px-2 py-1.5;
  }
  
  .nav-icon {
    @apply mr-1.5 text-sm;
  }
  
  .nav-text {
    @apply text-xs;
  }
  
  .admin-header {
    @apply px-2 py-1.5;
  }
  
  .header-left h1 {
    @apply text-base;
  }
  
  .breadcrumb {
    @apply hidden;
  }
}

/* 超超小屏幕适配 */
@media (max-width: 360px) {
  .admin-sidebar {
    @apply w-32;
  }
  
  .admin-main {
    @apply ml-32;
    padding-left: 0.0625rem;
  }
  
  .admin-content {
    @apply p-1.5;
  }
  
  .sidebar-header {
    @apply p-1.5;
  }
  
  .sidebar-header h2 {
    @apply text-sm;
  }
  
  .sidebar-header p {
    @apply text-xs;
  }
  
  .nav-item {
    @apply px-1.5 py-1;
  }
  
  .nav-icon {
    @apply mr-1 text-sm;
  }
  
  .nav-text {
    @apply text-xs;
  }
  
  .admin-header {
    @apply px-1.5 py-1;
  }
  
  .header-left h1 {
    @apply text-sm;
  }
  
  .user-name {
    @apply text-xs;
  }
  
  .user-avatar {
    @apply w-5 h-5;
  }
}

.admin-header {
  @apply bg-white shadow-sm border-b border-gray-200 px-6 py-4 flex justify-between items-center;
}

.header-left {
  @apply flex flex-col;
}

.breadcrumb {
  @apply text-sm text-gray-500 mt-1;
}

.header-right {
  @apply flex items-center;
}

.user-menu {
  @apply flex items-center space-x-3;
}

.user-name {
  @apply text-sm font-medium text-gray-700;
}

.user-avatar {
  @apply bg-gray-300;
}

/* ICP备案信息样式 */
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
  transition: color 0.3s ease;
}

.icp-footer a:hover {
  color: #3b82f6;
}

/* 响应式ICP备案 */
@media (max-width: 768px) {
  .icp-footer {
    padding: 10px 0;
  }
  
  .icp-container {
    padding: 0 15px;
  }
  
  .icp-footer a {
    font-size: 11px;
  }
}
</style> 