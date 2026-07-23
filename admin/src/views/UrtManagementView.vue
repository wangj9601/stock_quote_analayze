<template>
  <div class="urt-management">
    <div class="page-header">
      <div class="header-row">
        <div>
          <h2>URT 上升趋势策略</h2>
          <p class="subtitle">参数配置、多数据源回测、任务详情与统计分析报告</p>
        </div>
        <el-button type="success" size="small" @click="refreshSystemStatus">
          <el-icon><Refresh /></el-icon>
          刷新状态
        </el-button>
      </div>
    </div>

    <div class="status-cards">
      <el-row :gutter="16">
        <el-col :span="6">
          <el-card shadow="never" class="status-card">
            <div class="status-value">{{ systemStatus.runningBacktests }}</div>
            <div class="status-label">运行中回测</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="status-card">
            <div class="status-value">{{ systemStatus.pendingBacktests }}</div>
            <div class="status-label">待执行</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="status-card">
            <div class="status-value">{{ systemStatus.failedBacktests }}</div>
            <div class="status-label">失败任务</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="status-card">
            <div class="status-value">{{ systemStatus.totalReports }}</div>
            <div class="status-label">历史报告</div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="策略参数" name="config">
        <UrtStrategyConfiguration />
      </el-tab-pane>
      <el-tab-pane label="回测管理" name="backtest">
        <UrtBacktestManagement />
      </el-tab-pane>
      <el-tab-pane label="报告与分析" name="reports">
        <UrtReportAnalysis ref="reportRef" />
      </el-tab-pane>
      <el-tab-pane label="操作记录" name="audit">
        <UrtAuditLogs ref="auditRef" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { provide, ref, watch } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { urtApiService } from '@/services/urtApi'
import UrtStrategyConfiguration from '@/components/urt/StrategyConfiguration.vue'
import UrtBacktestManagement from '@/components/urt/BacktestManagement.vue'
import UrtReportAnalysis from '@/components/urt/ReportAnalysis.vue'
import UrtAuditLogs from '@/components/urt/UrtAuditLogs.vue'

provide('urtApi', urtApiService)

const activeTab = ref('backtest')
const reportRef = ref<{ refresh?: () => void } | null>(null)
const auditRef = ref<{ refresh?: () => void } | null>(null)

const systemStatus = ref({
  runningBacktests: 0,
  pendingBacktests: 0,
  failedBacktests: 0,
  totalReports: 0,
  systemHealth: 'ok',
})

async function refreshSystemStatus() {
  try {
    const data = await urtApiService.getSystemStatus()
    systemStatus.value = { ...systemStatus.value, ...data }
    ElMessage.success('系统状态已刷新')
  } catch {
    ElMessage.error('获取系统状态失败')
  }
}

watch(activeTab, (tab) => {
  if (tab === 'reports') reportRef.value?.refresh?.()
  if (tab === 'audit') auditRef.value?.refresh?.()
})

refreshSystemStatus()
</script>

<style scoped>
.urt-management {
  padding: 16px 20px;
}
.header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.page-header h2 {
  margin: 0 0 4px;
  font-size: 20px;
}
.subtitle {
  margin: 0;
  color: #6b7280;
  font-size: 13px;
}
.status-cards {
  margin-bottom: 16px;
}
.status-card {
  text-align: center;
}
.status-value {
  font-size: 22px;
  font-weight: 600;
  color: #1f2937;
}
.status-label {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}
</style>
