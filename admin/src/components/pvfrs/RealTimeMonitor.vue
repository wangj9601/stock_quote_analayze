<template>
  <div class="real-time-monitor">
    <!-- 监控概览 -->
    <el-row :gutter="20" class="monitor-overview">
      <el-col :span="6">
        <el-card class="monitor-card">
          <div class="monitor-item">
            <div class="monitor-icon success">
              <el-icon><Monitor /></el-icon>
            </div>
            <div class="monitor-content">
              <div class="monitor-value">{{ monitorData.activeSignals }}</div>
              <div class="monitor-label">活跃信号</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="monitor-card">
          <div class="monitor-item">
            <div class="monitor-icon warning">
              <el-icon><Warning /></el-icon>
            </div>
            <div class="monitor-content">
              <div class="monitor-value">{{ monitorData.alerts }}</div>
              <div class="monitor-label">告警数量</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="monitor-card">
          <div class="monitor-item">
            <div class="monitor-icon info">
              <el-icon><TrendCharts /></el-icon>
            </div>
            <div class="monitor-content">
              <div class="monitor-value">{{ monitorData.performance }}%</div>
              <div class="monitor-label">策略表现</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="monitor-card">
          <div class="monitor-item">
            <div class="monitor-icon danger">
              <el-icon><DataAnalysis /></el-icon>
            </div>
            <div class="monitor-content">
              <div class="monitor-value">{{ monitorData.riskLevel }}</div>
              <div class="monitor-label">风险等级</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 实时图表 -->
    <el-card class="chart-card" header="实时监控图表">
      <div class="chart-container" ref="chartContainer"></div>
    </el-card>

    <!-- 告警列表 -->
    <el-card class="alerts-card" header="实时告警">
      <div class="alerts-header">
        <el-button @click="refreshAlerts" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button type="success" @click="acknowledgeAllAlerts">
          <el-icon><Check /></el-icon>
          全部确认
        </el-button>
      </div>
      
      <el-table :data="alerts" stripe>
        <el-table-column prop="level" label="级别" width="100">
          <template #default="scope">
            <el-tag :type="getAlertLevelType(scope.row.level)">
              {{ getAlertLevelLabel(scope.row.level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="告警信息" min-width="200" />
        <el-table-column prop="source" label="来源" width="120" />
        <el-table-column prop="timestamp" label="时间" width="160">
          <template #default="scope">
            {{ formatDateTime(scope.row.timestamp) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.acknowledged ? 'success' : 'warning'">
              {{ scope.row.acknowledged ? '已确认' : '待处理' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="scope">
            <el-button 
              size="small" 
              @click="acknowledgeAlert(scope.row)"
              :disabled="scope.row.acknowledged"
            >
              确认
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, inject, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { 
  Monitor, 
  Warning, 
  TrendCharts, 
  DataAnalysis,
  Refresh,
  Check
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'

// 注入服务
const pvfrsApi = inject('pvfrsApi')

// 响应式数据
const loading = ref(false)
const chartContainer = ref()
let chart: any = null
let monitorTimer: NodeJS.Timeout | null = null

// 监控数据
const monitorData = reactive({
  activeSignals: 0,
  alerts: 0,
  performance: 0,
  riskLevel: 'LOW'
})

// 告警列表
const alerts = ref([])

// 发射事件
const emit = defineEmits(['alert-triggered'])

// 方法
const startMonitoring = async () => {
  await refreshMonitorData()
  await refreshAlerts()
  initChart()
  
  // 开始定时刷新
  monitorTimer = setInterval(() => {
    refreshMonitorData()
    refreshAlerts()
    updateChart()
  }, 5000) // 每5秒刷新一次
}

const stopMonitoring = () => {
  if (monitorTimer) {
    clearInterval(monitorTimer)
    monitorTimer = null
  }
}

const refreshMonitorData = async () => {
  try {
    const data = await pvfrsApi.getMonitoringData()
    Object.assign(monitorData, data)
  } catch (error) {
    console.error('获取监控数据失败:', error)
  }
}

const refreshAlerts = async () => {
  try {
    loading.value = true
    const alertsData = await pvfrsApi.getMonitoringAlerts()
    alerts.value = alertsData || []
    
    // 检查是否有新告警
    const newAlerts = alerts.value.filter(alert => !alert.acknowledged)
    if (newAlerts.length > 0) {
      emit('alert-triggered', {
        count: newAlerts.length,
        message: `发现 ${newAlerts.length} 个新告警`
      })
    }
    
  } catch (error) {
    console.error('获取告警列表失败:', error)
  } finally {
    loading.value = false
  }
}

const acknowledgeAlert = async (alert: any) => {
  try {
    await pvfrsApi.acknowledgeAlert(alert.id)
    alert.acknowledged = true
    ElMessage.success('告警已确认')
  } catch (error) {
    ElMessage.error('确认告警失败')
  }
}

const acknowledgeAllAlerts = async () => {
  try {
    const unacknowledgedAlerts = alerts.value.filter(alert => !alert.acknowledged)
    
    for (const alert of unacknowledgedAlerts) {
      await pvfrsApi.acknowledgeAlert(alert.id)
      alert.acknowledged = true
    }
    
    ElMessage.success(`已确认 ${unacknowledgedAlerts.length} 个告警`)
  } catch (error) {
    ElMessage.error('批量确认告警失败')
  }
}

const initChart = async () => {
  await nextTick()
  
  if (chartContainer.value) {
    chart = echarts.init(chartContainer.value)
    
    const option = {
      title: {
        text: '策略性能实时监控'
      },
      tooltip: {
        trigger: 'axis'
      },
      legend: {
        data: ['信号强度', '收益率', '风险指标']
      },
      xAxis: {
        type: 'category',
        data: []
      },
      yAxis: {
        type: 'value'
      },
      series: [
        {
          name: '信号强度',
          type: 'line',
          data: [],
          smooth: true,
          itemStyle: { color: '#409EFF' }
        },
        {
          name: '收益率',
          type: 'line',
          data: [],
          smooth: true,
          itemStyle: { color: '#67C23A' }
        },
        {
          name: '风险指标',
          type: 'line',
          data: [],
          smooth: true,
          itemStyle: { color: '#F56C6C' }
        }
      ]
    }
    
    chart.setOption(option)
    
    // 响应式调整
    window.addEventListener('resize', () => {
      chart?.resize()
    })
  }
}

const updateChart = async () => {
  if (!chart) return
  
  try {
    const performanceData = await pvfrsApi.getPerformanceMetrics({
      timeRange: '1h',
      interval: '1m'
    })
    
    const option = {
      xAxis: {
        data: performanceData.timestamps || []
      },
      series: [
        {
          data: performanceData.signalStrength || []
        },
        {
          data: performanceData.returns || []
        },
        {
          data: performanceData.riskMetrics || []
        }
      ]
    }
    
    chart.setOption(option)
  } catch (error) {
    console.error('更新图表失败:', error)
  }
}

// 辅助方法
const getAlertLevelType = (level: string) => {
  const types = {
    LOW: 'info',
    MEDIUM: 'warning',
    HIGH: 'danger',
    CRITICAL: 'danger'
  }
  return types[level] || 'info'
}

const getAlertLevelLabel = (level: string) => {
  const labels = {
    LOW: '低',
    MEDIUM: '中',
    HIGH: '高',
    CRITICAL: '严重'
  }
  return labels[level] || level
}

const formatDateTime = (timestamp: string) => {
  if (!timestamp) return '-'
  return new Date(timestamp).toLocaleString()
}

// 暴露方法给父组件
defineExpose({
  startMonitoring,
  stopMonitoring
})

// 生命周期
onMounted(() => {
  startMonitoring()
})

onUnmounted(() => {
  stopMonitoring()
  if (chart) {
    chart.dispose()
  }
})
</script>

<style scoped lang="postcss">
.real-time-monitor {
  @apply space-y-6;
}

.monitor-overview {
  @apply mb-6;
}

.monitor-card {
  @apply h-full shadow-sm;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.monitor-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
}

.monitor-item {
  @apply flex items-center p-4;
}

.monitor-icon {
  @apply w-12 h-12 rounded-full flex items-center justify-center mr-4;
  font-size: 24px;
}

.monitor-icon.success {
  @apply bg-green-100 text-green-600;
}

.monitor-icon.warning {
  @apply bg-yellow-100 text-yellow-600;
}

.monitor-icon.info {
  @apply bg-blue-100 text-blue-600;
}

.monitor-icon.danger {
  @apply bg-red-100 text-red-600;
}

.monitor-content {
  flex: 1;
}

.monitor-value {
  @apply text-2xl font-bold text-gray-900 mb-1;
}

.monitor-label {
  @apply text-sm text-gray-600;
}

.chart-card {
  @apply shadow-sm;
}

.chart-container {
  @apply w-full;
  height: 400px;
}

.alerts-card {
  @apply shadow-sm;
}

.alerts-header {
  @apply flex gap-2 mb-4;
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .monitor-overview :deep(.el-col) {
    @apply mb-4;
  }
  
  .chart-container {
    height: 300px;
  }
}

@media (max-width: 768px) {
  .monitor-item {
    @apply p-3;
  }
  
  .monitor-icon {
    @apply w-10 h-10 mr-3;
    font-size: 20px;
  }
  
  .monitor-value {
    @apply text-xl;
  }
  
  .chart-container {
    height: 250px;
  }
  
  .alerts-header {
    @apply flex-col gap-2;
  }
  
  .alerts-header .el-button {
    @apply w-full;
  }
}

@media (max-width: 640px) {
  .monitor-overview :deep(.el-col) {
    @apply w-full;
  }
  
  .monitor-item {
    @apply flex-col text-center p-3;
  }
  
  .monitor-icon {
    @apply mb-2 mr-0;
  }
}

/* 动画效果 */
.monitor-card {
  animation: fadeInUp 0.6s ease-out;
}

.monitor-card:nth-child(1) { animation-delay: 0.1s; }
.monitor-card:nth-child(2) { animation-delay: 0.2s; }
.monitor-card:nth-child(3) { animation-delay: 0.3s; }
.monitor-card:nth-child(4) { animation-delay: 0.4s; }

.chart-card {
  animation: slideInUp 0.6s ease-out 0.3s both;
}

.alerts-card {
  animation: slideInUp 0.6s ease-out 0.5s both;
}

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

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>