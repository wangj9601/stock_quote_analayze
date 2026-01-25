<template>
  <div class="pvfrs-management">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <h1 class="page-title">PVFARS策略管理中心</h1>
        <p class="page-subtitle">量价频幅度共振策略 - 专业管理界面</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="showStrategyGuide = true">
          <el-icon><QuestionFilled /></el-icon>
          策略指南
        </el-button>
        <el-button type="success" @click="refreshSystemStatus">
          <el-icon><Refresh /></el-icon>
          刷新状态
        </el-button>
      </div>
    </div>

    <!-- 系统状态卡片 -->
    <div class="status-cards">
      <el-row :gutter="20">
        <el-col :span="6">
          <el-card class="status-card">
            <div class="status-item">
              <div class="status-icon success">
                <el-icon><TrendCharts /></el-icon>
              </div>
              <div class="status-content">
                <div class="status-value">{{ systemStatus.activeStrategies }}</div>
                <div class="status-label">活跃策略</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="status-card">
            <div class="status-item">
              <div class="status-icon info">
                <el-icon><DataAnalysis /></el-icon>
              </div>
              <div class="status-content">
                <div class="status-value">{{ systemStatus.runningBacktests }}</div>
                <div class="status-label">运行中回测</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="status-card">
            <div class="status-item">
              <div class="status-icon warning">
                <el-icon><Histogram /></el-icon>
              </div>
              <div class="status-content">
                <div class="status-value">{{ systemStatus.totalReports }}</div>
                <div class="status-label">历史报告</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="status-card">
            <div class="status-item">
              <div class="status-icon danger">
                <el-icon><Monitor /></el-icon>
              </div>
              <div class="status-content">
                <div class="status-value">{{ systemStatus.systemHealth }}%</div>
                <div class="status-label">系统健康度</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 主要功能标签页 -->
    <el-tabs v-model="activeTab" class="management-tabs" @tab-change="handleTabChange">
      <!-- 回测任务管理 -->
      <el-tab-pane label="回测任务管理" name="backtest">
        <BacktestManagement 
          ref="backtestRef"
          @task-created="handleTaskCreated"
          @task-updated="handleTaskUpdated"
        />
      </el-tab-pane>

      <!-- 报告与分析 -->
      <el-tab-pane label="报告与分析" name="reports">
        <ReportAnalysis 
          ref="reportRef"
          @report-generated="handleReportGenerated"
        />
      </el-tab-pane>

      <!-- 策略配置 -->
      <el-tab-pane label="策略配置" name="config">
        <StrategyConfiguration 
          ref="configRef"
          @config-saved="handleConfigSaved"
        />
      </el-tab-pane>

      <!-- 实时监控 -->
      <el-tab-pane label="实时监控" name="monitor">
        <RealTimeMonitor 
          ref="monitorRef"
          @alert-triggered="handleAlert"
        />
      </el-tab-pane>
    </el-tabs>

    <!-- 策略指南对话框 -->
    <el-dialog
      v-model="showStrategyGuide"
      title="PVFARS策略指南"
      width="80%"
      :before-close="handleGuideClose"
    >
      <StrategyGuide />
    </el-dialog>

    <!-- 全局通知 -->
    <el-notification
      v-if="notification.show"
      :title="notification.title"
      :message="notification.message"
      :type="notification.type"
      :duration="notification.duration"
      @close="notification.show = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, provide } from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
import { 
  QuestionFilled, 
  Refresh, 
  TrendCharts, 
  DataAnalysis, 
  Histogram, 
  Monitor 
} from '@element-plus/icons-vue'

// 导入子组件
import BacktestManagement from '@/components/pvfrs/BacktestManagement.vue'
import ReportAnalysis from '@/components/pvfrs/ReportAnalysis.vue'
import StrategyConfiguration from '@/components/pvfrs/StrategyConfiguration.vue'
import RealTimeMonitor from '@/components/pvfrs/RealTimeMonitor.vue'
import StrategyGuide from '@/components/pvfrs/StrategyGuide.vue'

// 导入服务
import { pvfrsApiService } from '@/services/pvfrsApi'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

// 响应式数据
const activeTab = ref('backtest')
const showStrategyGuide = ref(false)

// 系统状态
const systemStatus = reactive({
  activeStrategies: 0,
  runningBacktests: 0,
  totalReports: 0,
  systemHealth: 100
})

// 通知系统
const notification = reactive({
  show: false,
  title: '',
  message: '',
  type: 'info' as 'success' | 'warning' | 'info' | 'error',
  duration: 4500
})

// 告警提示防抖：记录上次提示时间，避免频繁提示
let lastAlertNotificationTime = 0
const ALERT_NOTIFICATION_INTERVAL = 60000 // 60秒内最多提示一次告警

// 子组件引用
const backtestRef = ref()
const reportRef = ref()
const configRef = ref()
const monitorRef = ref()

// 定时器
let statusTimer: NodeJS.Timeout | null = null

// 提供全局服务
provide('pvfrsApi', pvfrsApiService)
provide('authStore', authStore)

// 方法
const refreshSystemStatus = async () => {
  try {
    const status = await pvfrsApiService.getSystemStatus()
    Object.assign(systemStatus, status)
    ElMessage.success('系统状态已刷新')
  } catch (error) {
    ElMessage.error('获取系统状态失败')
    console.error('获取系统状态失败:', error)
  }
}

const handleTabChange = (tabName: string) => {
  console.log('切换到标签页:', tabName)
  
  // 根据标签页执行相应的初始化操作
  switch (tabName) {
    case 'backtest':
      backtestRef.value?.refresh?.()
      break
    case 'reports':
      reportRef.value?.refresh?.()
      break
    case 'config':
      configRef.value?.loadConfig?.()
      break
    case 'monitor':
      monitorRef.value?.startMonitoring?.()
      break
  }
}

const handleTaskCreated = (task: any) => {
  showNotification('success', '任务创建成功', `回测任务 ${task.id} 已创建并开始执行`)
  refreshSystemStatus()
}

const handleTaskUpdated = (task: any) => {
  if (task.status === 'completed') {
    showNotification('success', '任务完成', `回测任务 ${task.id} 已完成`)
  } else if (task.status === 'failed') {
    showNotification('error', '任务失败', `回测任务 ${task.id} 执行失败`)
  }
  refreshSystemStatus()
}

const handleReportGenerated = (report: any) => {
  showNotification('info', '报告生成', `新的分析报告已生成: ${report.title}`)
  refreshSystemStatus()
}

const handleConfigSaved = (config: any) => {
  showNotification('success', '配置保存', '策略配置已成功保存')
}

const handleAlert = (alert: any) => {
  // 防抖：如果距离上次提示时间太短，则不提示
  const now = Date.now()
  if (now - lastAlertNotificationTime < ALERT_NOTIFICATION_INTERVAL) {
    console.log('告警提示过于频繁，已忽略本次提示')
    return
  }
  
  lastAlertNotificationTime = now
  showNotification('warning', '监控告警', alert.message)
}

const showNotification = (type: string, title: string, message: string) => {
  notification.type = type as any
  notification.title = title
  notification.message = message
  notification.show = true
}

const handleGuideClose = () => {
  showStrategyGuide.value = false
}

const startStatusPolling = () => {
  statusTimer = setInterval(() => {
    refreshSystemStatus()
  }, 30000) // 每30秒刷新一次
}

const stopStatusPolling = () => {
  if (statusTimer) {
    clearInterval(statusTimer)
    statusTimer = null
  }
}

// 生命周期
onMounted(async () => {
  console.log('PVFRS管理中心已挂载')
  await refreshSystemStatus()
  startStatusPolling()
})

onUnmounted(() => {
  stopStatusPolling()
})
</script>

<style scoped lang="postcss">
.pvfrs-management {
  @apply min-h-screen bg-gray-50;
}

.page-header {
  @apply bg-white shadow-sm border-b border-gray-200 p-6 mb-6;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-content {
  flex: 1;
}

.page-title {
  @apply text-3xl font-bold text-gray-900 mb-2;
}

.page-subtitle {
  @apply text-lg text-gray-600;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.status-cards {
  @apply mb-6;
}

.status-card {
  @apply h-full;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.status-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
}

.status-item {
  display: flex;
  align-items: center;
  padding: 20px;
}

.status-icon {
  @apply w-12 h-12 rounded-full flex items-center justify-center mr-4;
  font-size: 24px;
}

.status-icon.success {
  @apply bg-green-100 text-green-600;
}

.status-icon.info {
  @apply bg-blue-100 text-blue-600;
}

.status-icon.warning {
  @apply bg-yellow-100 text-yellow-600;
}

.status-icon.danger {
  @apply bg-red-100 text-red-600;
}

.status-content {
  flex: 1;
}

.status-value {
  @apply text-2xl font-bold text-gray-900 mb-1;
}

.status-label {
  @apply text-sm text-gray-600;
}

.management-tabs {
  @apply bg-white rounded-lg shadow-sm;
}

:deep(.el-tabs__header) {
  @apply bg-gray-50 rounded-t-lg px-6 pt-4 mb-0;
}

:deep(.el-tabs__nav-wrap) {
  @apply bg-transparent;
}

:deep(.el-tabs__item) {
  @apply px-6 py-3 text-base font-medium;
  transition: all 0.3s ease;
}

:deep(.el-tabs__item:hover) {
  @apply text-blue-600;
}

:deep(.el-tabs__item.is-active) {
  @apply text-blue-600 bg-white rounded-t-lg;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
}

:deep(.el-tabs__content) {
  @apply p-6;
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .page-header {
    @apply flex-col items-start gap-4;
  }
  
  .header-actions {
    @apply w-full justify-end;
  }
  
  .status-cards :deep(.el-col) {
    @apply mb-4;
  }
}

@media (max-width: 768px) {
  .page-header {
    @apply p-4;
  }
  
  .page-title {
    @apply text-2xl;
  }
  
  .page-subtitle {
    @apply text-base;
  }
  
  .header-actions {
    @apply flex-col w-full gap-2;
  }
  
  .header-actions .el-button {
    @apply w-full;
  }
  
  .status-item {
    @apply p-4;
  }
  
  .status-icon {
    @apply w-10 h-10 mr-3;
    font-size: 20px;
  }
  
  .status-value {
    @apply text-xl;
  }
  
  :deep(.el-tabs__header) {
    @apply px-4 pt-3;
  }
  
  :deep(.el-tabs__item) {
    @apply px-4 py-2 text-sm;
  }
  
  :deep(.el-tabs__content) {
    @apply p-4;
  }
}

@media (max-width: 640px) {
  .status-cards :deep(.el-col) {
    @apply w-full;
  }
  
  .status-item {
    @apply flex-col text-center p-3;
  }
  
  .status-icon {
    @apply mb-2 mr-0;
  }
}

/* 动画效果 */
.status-card {
  animation: fadeInUp 0.6s ease-out;
}

.status-card:nth-child(1) { animation-delay: 0.1s; }
.status-card:nth-child(2) { animation-delay: 0.2s; }
.status-card:nth-child(3) { animation-delay: 0.3s; }
.status-card:nth-child(4) { animation-delay: 0.4s; }

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 深色模式支持 */
@media (prefers-color-scheme: dark) {
  .pvfrs-management {
    @apply bg-gray-900;
  }
  
  .page-header {
    @apply bg-gray-800 border-gray-700;
  }
  
  .page-title {
    @apply text-white;
  }
  
  .page-subtitle {
    @apply text-gray-300;
  }
  
  .management-tabs {
    @apply bg-gray-800;
  }
  
  :deep(.el-tabs__header) {
    @apply bg-gray-700;
  }
  
  :deep(.el-tabs__item.is-active) {
    @apply bg-gray-800;
  }
}
</style>