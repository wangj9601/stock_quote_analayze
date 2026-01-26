<template>
  <div class="monitoring-view">
    <div class="page-header">
      <h1 class="text-2xl font-bold text-gray-900 mb-6">系统监控</h1>
      <div class="flex items-center space-x-4">
        <el-button 
          :type="monitoringStatus.isRunning ? 'danger' : 'success'"
          @click="toggleMonitoring"
          :loading="statusLoading"
        >
          {{ monitoringStatus.isRunning ? '停止监控' : '启动监控' }}
        </el-button>
        <el-button @click="refreshData" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新数据
        </el-button>
      </div>
    </div>

    <!-- 监控概览 -->
    <el-row :gutter="20" class="mb-6">
      <el-col :span="6">
        <el-card class="overview-card">
          <div class="overview-item">
            <div class="overview-icon success">
              <el-icon><Monitor /></el-icon>
            </div>
            <div class="overview-content">
              <div class="overview-value">{{ overviewData.status }}</div>
              <div class="overview-label">系统状态</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="overview-card">
          <div class="overview-item">
            <div class="overview-icon warning">
              <el-icon><Warning /></el-icon>
            </div>
            <div class="overview-content">
              <div class="overview-value">{{ overviewData.alerts?.total_24h || 0 }}</div>
              <div class="overview-label">24小时告警</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="overview-card">
          <div class="overview-item">
            <div class="overview-icon info">
              <el-icon><TrendCharts /></el-icon>
            </div>
            <div class="overview-content">
              <div class="overview-value">{{ overviewData.performance?.uptime?.toFixed(1) || 0 }}h</div>
              <div class="overview-label">运行时间</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="overview-card">
          <div class="overview-item">
            <div class="overview-icon danger">
              <el-icon><DataAnalysis /></el-icon>
            </div>
            <div class="overview-content">
              <div class="overview-value">{{ overviewData.performance?.process_count || 0 }}</div>
              <div class="overview-label">进程数量</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 系统健康状态 -->
    <el-card class="mb-6">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="text-lg font-semibold">系统健康状态</span>
          <el-button size="small" @click="refreshSystemHealth">刷新</el-button>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="12">
          <div class="health-section">
            <h4 class="mb-4">资源使用率</h4>
            <div class="metric-item">
              <div class="metric-label">CPU使用率</div>
              <el-progress 
                :percentage="systemHealth.cpu_usage" 
                :status="getProgressStatus(systemHealth.cpu_usage)"
                :show-text="true"
              />
            </div>
            <div class="metric-item">
              <div class="metric-label">内存使用率</div>
              <el-progress 
                :percentage="systemHealth.memory_usage" 
                :status="getProgressStatus(systemHealth.memory_usage)"
                :show-text="true"
              />
            </div>
            <div class="metric-item">
              <div class="metric-label">磁盘使用率</div>
              <el-progress 
                :percentage="systemHealth.disk_usage" 
                :status="getProgressStatus(systemHealth.disk_usage)"
                :show-text="true"
              />
            </div>
          </div>
        </el-col>
        
        <el-col :span="12">
          <div class="health-section">
            <h4 class="mb-4">服务状态</h4>
            <div class="service-list">
              <div 
                v-for="(status, service) in systemHealth.services" 
                :key="service"
                class="service-item"
              >
                <div class="service-name">{{ getServiceDisplayName(service) }}</div>
                <el-tag 
                  :type="getServiceStatusType(status)"
                  size="small"
                >
                  {{ status }}
                </el-tag>
              </div>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 性能指标图表 -->
    <el-card class="mb-6">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="text-lg font-semibold">性能指标</span>
          <div class="flex items-center space-x-2">
            <el-select v-model="metricsTimeRange" size="small" @change="refreshMetrics">
              <el-option label="1小时" value="1h" />
              <el-option label="6小时" value="6h" />
              <el-option label="12小时" value="12h" />
              <el-option label="1天" value="1d" />
            </el-select>
            <el-button size="small" @click="refreshMetrics">刷新</el-button>
          </div>
        </div>
      </template>
      
      <div ref="metricsChart" style="height: 300px;"></div>
    </el-card>

    <!-- 告警列表 -->
    <el-card>
      <template #header>
        <div class="flex items-center justify-between">
          <span class="text-lg font-semibold">告警列表</span>
          <div class="flex items-center space-x-2">
            <el-select v-model="alertFilter.level" size="small" placeholder="级别" clearable @change="refreshAlerts">
              <el-option label="严重" value="CRITICAL" />
              <el-option label="高" value="HIGH" />
              <el-option label="中" value="MEDIUM" />
              <el-option label="低" value="LOW" />
            </el-select>
            <el-select v-model="alertFilter.acknowledged" size="small" placeholder="状态" clearable @change="refreshAlerts">
              <el-option label="未确认" :value="false" />
              <el-option label="已确认" :value="true" />
            </el-select>
            <el-button size="small" @click="refreshAlerts">刷新</el-button>
          </div>
        </div>
      </template>
      
      <el-table :data="alerts" v-loading="alertsLoading" stripe>
        <el-table-column prop="level" label="级别" width="80">
          <template #default="{ row }">
            <el-tag :type="getAlertLevelType(row.level)" size="small">
              {{ row.level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="200" />
        <el-table-column prop="message" label="消息" min-width="300" show-overflow-tooltip />
        <el-table-column prop="source" label="来源" width="120" />
        <el-table-column prop="timestamp" label="时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.timestamp) }}
          </template>
        </el-table-column>
        <el-table-column prop="acknowledged" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.acknowledged ? 'success' : 'warning'" size="small">
              {{ row.acknowledged ? '已确认' : '未确认' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button 
              v-if="!row.acknowledged"
              size="small" 
              type="primary"
              @click="acknowledgeAlert(row.id)"
            >
              确认
            </el-button>
            <el-button 
              size="small" 
              type="danger"
              @click="resolveAlert(row.id)"
            >
              解决
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="mt-4 flex justify-center">
        <el-pagination
          v-model:current-page="alertPagination.page"
          v-model:page-size="alertPagination.pageSize"
          :total="alertPagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="refreshAlerts"
          @current-change="refreshAlerts"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Monitor, 
  Warning, 
  TrendCharts, 
  DataAnalysis, 
  Refresh 
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { systemMonitoringApi } from '@/services/systemMonitoring'

// 响应式数据
const loading = ref(false)
const statusLoading = ref(false)
const alertsLoading = ref(false)
const metricsTimeRange = ref('1h')

const overviewData = reactive({
  status: 'unknown',
  alerts: { total_24h: 0, critical_24h: 0 },
  performance: { uptime: 0, process_count: 0 }
})

const systemHealth = reactive({
  cpu_usage: 0,
  memory_usage: 0,
  disk_usage: 0,
  network_io: {},
  services: {},
  timestamp: ''
})

const monitoringStatus = reactive({
  isRunning: false,
  stopEventSet: false
})

const alerts = ref([])
const alertFilter = reactive({
  level: '',
  acknowledged: undefined
})

const alertPagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

let metricsChart = null
let refreshTimer = null

// 方法
const getProgressStatus = (percentage: number) => {
  if (percentage >= 90) return 'exception'
  if (percentage >= 70) return 'warning'
  return 'success'
}

const getServiceDisplayName = (service: string) => {
  const serviceNames: Record<string, string> = {
    'database': '数据库',
    'api_server': 'API服务器',
    'scheduler': '调度器'
  }
  return serviceNames[service] || service
}

const getServiceStatusType = (status: string) => {
  const statusTypes: Record<string, string> = {
    'healthy': 'success',
    'degraded': 'warning',
    'unhealthy': 'danger',
    'unknown': 'info'
  }
  return statusTypes[status] || 'info'
}

const getAlertLevelType = (level: string) => {
  const levelTypes: Record<string, string> = {
    'CRITICAL': 'danger',
    'HIGH': 'warning',
    'MEDIUM': 'info',
    'LOW': 'success'
  }
  return levelTypes[level] || 'info'
}

const formatDateTime = (timestamp: string) => {
  return new Date(timestamp).toLocaleString('zh-CN')
}

const refreshData = async () => {
  await Promise.all([
    refreshOverview(),
    refreshSystemHealth(),
    refreshAlerts(),
    refreshMonitoringStatus()
  ])
}

const refreshOverview = async () => {
  try {
    const response = await systemMonitoringApi.getOverview()
    Object.assign(overviewData, response.data)
  } catch (error) {
    ElMessage.error('获取监控概览失败')
  }
}

const refreshSystemHealth = async () => {
  try {
    const response = await systemMonitoringApi.getSystemHealth()
    Object.assign(systemHealth, response.data)
  } catch (error) {
    ElMessage.error('获取系统健康状态失败')
  }
}

const refreshMetrics = async () => {
  try {
    const response = await systemMonitoringApi.getMetrics(metricsTimeRange.value)
    updateMetricsChart(response.data)
  } catch (error) {
    ElMessage.error('获取性能指标失败')
  }
}

const refreshAlerts = async () => {
  alertsLoading.value = true
  try {
    const response = await systemMonitoringApi.getAlerts({
      limit: alertPagination.pageSize,
      level: alertFilter.level || undefined,
      acknowledged: alertFilter.acknowledged
    })
    alerts.value = response.data
    alertPagination.total = response.data.length
  } catch (error) {
    ElMessage.error('获取告警列表失败')
  } finally {
    alertsLoading.value = false
  }
}

const refreshMonitoringStatus = async () => {
  try {
    const response = await systemMonitoringApi.getMonitoringStatus()
    Object.assign(monitoringStatus, response.data)
  } catch (error) {
    ElMessage.error('获取监控状态失败')
  }
}

const toggleMonitoring = async () => {
  statusLoading.value = true
  try {
    if (monitoringStatus.isRunning) {
      await systemMonitoringApi.stopMonitoring()
      ElMessage.success('监控已停止')
    } else {
      await systemMonitoringApi.startMonitoring()
      ElMessage.success('监控已启动')
    }
    await refreshMonitoringStatus()
  } catch (error) {
    ElMessage.error('操作失败')
  } finally {
    statusLoading.value = false
  }
}

const acknowledgeAlert = async (alertId: number) => {
  try {
    await systemMonitoringApi.acknowledgeAlert(alertId, { acknowledged_by: 'admin' })
    ElMessage.success('告警已确认')
    refreshAlerts()
  } catch (error) {
    ElMessage.error('确认告警失败')
  }
}

const resolveAlert = async (alertId: number) => {
  try {
    await ElMessageBox.confirm('确定要解决这个告警吗？', '确认操作', {
      type: 'warning'
    })
    
    await systemMonitoringApi.resolveAlert(alertId, 'admin')
    ElMessage.success('告警已解决')
    refreshAlerts()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('解决告警失败')
    }
  }
}

const updateMetricsChart = (data: any) => {
  if (!metricsChart) return
  
  const option = {
    title: {
      text: '系统性能指标'
    },
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['CPU使用率', '内存使用率', '磁盘使用率']
    },
    xAxis: {
      type: 'category',
      data: data.timestamps || []
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: {
        formatter: '{value}%'
      }
    },
    series: [
      {
        name: 'CPU使用率',
        type: 'line',
        data: (data.cpuUsage || []).map((v: number) => v * 100)
      },
      {
        name: '内存使用率',
        type: 'line',
        data: (data.memoryUsage || []).map((v: number) => v * 100)
      },
      {
        name: '磁盘使用率',
        type: 'line',
        data: (data.diskUsage || []).map((v: number) => v * 100)
      }
    ]
  }
  
  metricsChart.setOption(option)
}

const initMetricsChart = () => {
  const chartDom = document.querySelector('.metrics-chart')
  if (chartDom) {
    metricsChart = echarts.init(chartDom)
  }
}

// 生命周期
onMounted(async () => {
  await refreshData()
  await refreshMetrics()
  
  // 初始化图表
  setTimeout(() => {
    initMetricsChart()
  }, 100)
  
  // 设置定时刷新
  refreshTimer = setInterval(() => {
    refreshData()
  }, 30000) // 30秒刷新一次
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
  if (metricsChart) {
    metricsChart.dispose()
  }
})
</script>

<style scoped>
.monitoring-view {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.overview-card {
  height: 100px;
}

.overview-item {
  display: flex;
  align-items: center;
  height: 100%;
}

.overview-icon {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 15px;
  font-size: 24px;
  color: white;
}

.overview-icon.success {
  background: linear-gradient(135deg, #67c23a, #85ce61);
}

.overview-icon.warning {
  background: linear-gradient(135deg, #e6a23c, #ebb563);
}

.overview-icon.info {
  background: linear-gradient(135deg, #409eff, #66b1ff);
}

.overview-icon.danger {
  background: linear-gradient(135deg, #f56c6c, #f78989);
}

.overview-content {
  flex: 1;
}

.overview-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
  line-height: 1;
}

.overview-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.health-section {
  padding: 10px 0;
}

.metric-item {
  margin-bottom: 20px;
}

.metric-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
}

.service-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.service-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
}

.service-name {
  font-size: 14px;
  color: #303133;
}

.metrics-chart {
  height: 300px;
}
</style>