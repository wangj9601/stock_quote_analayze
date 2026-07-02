<template>
  <div class="gms-management">
    <div class="page-header">
      <div class="header-content">
        <h1 class="page-title">GMS 回测管理中心</h1>
        <p class="page-subtitle">目标命中率回测 - 任务 / 报告 / 策略配置</p>
      </div>
      <div class="header-actions">
        <el-button type="success" @click="() => refreshSystemStatus()">
          <el-icon><Refresh /></el-icon>
          刷新状态
        </el-button>
      </div>
    </div>

    <div class="status-cards">
      <el-row :gutter="20">
        <el-col :span="6">
          <el-card class="status-card">
            <div class="status-item">
              <div class="status-icon success">
                <el-icon><TrendCharts /></el-icon>
              </div>
              <div class="status-content">
                <div class="status-value">GMS</div>
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
              <div :class="['status-icon', systemStatus.systemHealth === 'ok' ? 'success' : 'danger']">
                <el-icon><Monitor /></el-icon>
              </div>
              <div class="status-content">
                <div class="status-value">{{ systemStatus.systemHealth === 'ok' ? '正常' : '降级' }}</div>
                <div class="status-label">系统健康度</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
      <el-row v-if="systemStatus.alertMessage || systemStatus.screeningStats" :gutter="20" class="mt-4">
        <el-col :span="24">
          <el-alert
            v-if="systemStatus.alertMessage"
            :title="systemStatus.alertMessage"
            type="warning"
            show-icon
            :closable="false"
            class="mb-3"
          />
          <el-descriptions v-if="systemStatus.screeningStats" :column="4" border size="small" title="选股与预计算">
            <el-descriptions-item label="选股请求">{{ systemStatus.screeningStats.request_count ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="超时次数">{{ systemStatus.screeningStats.timeout_count ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="Trace命中率均值">
              {{
                systemStatus.screeningStats.avg_trace_hit_rate != null
                  ? (Number(systemStatus.screeningStats.avg_trace_hit_rate) * 100).toFixed(1) + '%'
                  : '—'
              }}
            </el-descriptions-item>
            <el-descriptions-item label="待执行/失败回测">
              {{ systemStatus.pendingBacktests ?? 0 }} / {{ systemStatus.failedBacktests ?? 0 }}
            </el-descriptions-item>
          </el-descriptions>
        </el-col>
      </el-row>
    </div>

    <el-tabs v-model="activeTab" class="management-tabs" @tab-change="handleTabChange">
      <el-tab-pane label="回测任务管理" name="backtest">
        <BacktestManagement
          ref="backtestRef"
          @task-created="handleTaskCreated"
          @task-updated="handleTaskUpdated"
        />
      </el-tab-pane>
      <el-tab-pane label="报告与分析" name="reports">
        <ReportAnalysis ref="reportRef" @report-generated="handleReportGenerated" @report-deleted="handleReportDeleted" />
      </el-tab-pane>
      <el-tab-pane label="策略配置" name="config">
        <StrategyConfiguration ref="configRef" @config-saved="handleConfigSaved" />
      </el-tab-pane>
      <el-tab-pane label="操作记录" name="audit">
        <GmsAuditLogs ref="auditRef" />
      </el-tab-pane>
    </el-tabs>

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
import { ElMessage } from 'element-plus'
import { Refresh, TrendCharts, DataAnalysis, Histogram, Monitor } from '@element-plus/icons-vue'
import BacktestManagement from '@/components/gms/BacktestManagement.vue'
import ReportAnalysis from '@/components/gms/ReportAnalysis.vue'
import StrategyConfiguration from '@/components/gms/StrategyConfiguration.vue'
import GmsAuditLogs from '@/components/gms/GmsAuditLogs.vue'
import { gmsApiService } from '@/services/gmsApi'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const activeTab = ref('backtest')

const systemStatus = reactive({
  runningBacktests: 0,
  totalReports: 0,
  systemHealth: 'ok' as string,
  pendingBacktests: 0,
  failedBacktests: 0,
  screeningStats: null as Record<string, unknown> | null,
  alertMessage: null as string | null,
})

const notification = reactive({
  show: false,
  title: '',
  message: '',
  type: 'info' as 'success' | 'warning' | 'info' | 'error',
  duration: 4500
})

const backtestRef = ref()
const reportRef = ref()
const configRef = ref()
const auditRef = ref()

let statusTimer: ReturnType<typeof setInterval> | null = null

provide('gmsApi', gmsApiService)
provide('authStore', authStore)

const refreshSystemStatus = async (silent = false) => {
  try {
    const data = await gmsApiService.getSystemStatus()
    systemStatus.runningBacktests = data.runningBacktests ?? 0
    systemStatus.totalReports = data.totalReports ?? 0
    systemStatus.systemHealth = data.systemHealth ?? 'ok'
    systemStatus.pendingBacktests = data.pendingBacktests ?? 0
    systemStatus.failedBacktests = data.failedBacktests ?? 0
    systemStatus.screeningStats = data.screeningStats ?? null
    systemStatus.alertMessage = data.alertMessage ?? null
    if (!silent) ElMessage.success('系统状态已刷新')
  } catch (e) {
    ElMessage.error('获取系统状态失败')
    console.error(e)
  }
}

const handleTabChange = (tabName: string | number) => {
  if (tabName === 'backtest') backtestRef.value?.refresh?.()
  if (tabName === 'reports') reportRef.value?.refresh?.()
  if (tabName === 'config') configRef.value?.loadConfig?.()
  if (tabName === 'audit') auditRef.value?.refresh?.()
}

const handleTaskCreated = (_task: any) => {
  showNotification('success', '任务创建成功', '回测任务已创建并开始执行')
  refreshSystemStatus()
}

const handleTaskUpdated = (task: any) => {
  if (task?.status === 'completed') showNotification('success', '任务完成', '回测任务已完成')
  else if (task?.status === 'failed') showNotification('error', '任务失败', '回测任务执行失败')
  refreshSystemStatus()
}

const handleReportGenerated = (_report: any) => {
  showNotification('info', '报告', '新报告已生成')
  refreshSystemStatus(true)
}

const handleReportDeleted = () => {
  refreshSystemStatus(true)
}

const handleConfigSaved = () => {
  showNotification('success', '配置保存', '策略配置已保存')
}

const showNotification = (type: string, title: string, message: string) => {
  notification.type = type as any
  notification.title = title
  notification.message = message
  notification.show = true
}

/*
const startStatusPolling = () => {
  statusTimer = setInterval(() => refreshSystemStatus(), 30000)
}
*/

const stopStatusPolling = () => {
  if (statusTimer) {
    clearInterval(statusTimer)
    statusTimer = null
  }
}

onMounted(async () => {
  await refreshSystemStatus()
  // startStatusPolling()
})

onUnmounted(() => {
  stopStatusPolling()
})
</script>

<style scoped lang="postcss">
.gms-management {
  @apply min-h-screen bg-gray-50;
}

.page-header {
  @apply bg-white shadow-sm border-b border-gray-200 p-6 mb-6;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-content .page-title {
  @apply text-2xl font-bold text-gray-900;
}

.page-subtitle {
  @apply text-gray-500 mt-1;
}

.status-cards {
  @apply mb-6 px-6;
}

.status-card .status-item {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.status-icon {
  @apply w-12 h-12 rounded-lg flex items-center justify-center text-white text-xl;
}

.status-icon.success { @apply bg-green-500; }
.status-icon.info { @apply bg-blue-500; }
.status-icon.warning { @apply bg-amber-500; }
.status-icon.danger { @apply bg-gray-600; }

.status-value { @apply text-xl font-semibold text-gray-900; }
.status-label { @apply text-sm text-gray-500; }

.management-tabs {
  @apply bg-white rounded-lg shadow p-4;
}
</style>
