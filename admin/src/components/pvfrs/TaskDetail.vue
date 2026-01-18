<template>
  <div class="task-detail">
    <!-- 任务基本信息 -->
    <el-card class="task-info-card" header="任务信息">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="任务ID">{{ task.id }}</el-descriptions-item>
        <el-descriptions-item label="任务名称">{{ task.name }}</el-descriptions-item>
        <el-descriptions-item label="回测模式">
          <el-tag :type="getModeTagType(task.mode)">
            {{ getModeLabel(task.mode) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="任务状态">
          <el-tag :type="getStatusTagType(task.status)">
            {{ getStatusLabel(task.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDateTime(task.createdAt) }}</el-descriptions-item>
        <el-descriptions-item label="开始时间">{{ formatDateTime(task.startedAt) }}</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{ formatDateTime(task.completedAt) }}</el-descriptions-item>
        <el-descriptions-item label="执行耗时">{{ formatDuration(task.duration) }}</el-descriptions-item>
        <el-descriptions-item label="初始资金">¥{{ formatNumber(task.initialCapital) }}</el-descriptions-item>
        <el-descriptions-item label="市场类型">{{ getMarketLabel(task.market) }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 任务进度 -->
    <el-card class="progress-card" header="执行进度">
      <div class="progress-content">
        <el-progress 
          :percentage="task.progress || 0" 
          :status="getProgressStatus(task.status)"
          :stroke-width="12"
          text-inside
        />
        <div class="progress-details">
          <div class="progress-item">
            <span class="progress-label">已处理股票:</span>
            <span class="progress-value">{{ task.processedStocks || 0 }} / {{ task.totalStocks || 0 }}</span>
          </div>
          <div class="progress-item">
            <span class="progress-label">处理速度:</span>
            <span class="progress-value">{{ task.processingSpeed || 0 }} 股票/分钟</span>
          </div>
          <div class="progress-item">
            <span class="progress-label">预计剩余时间:</span>
            <span class="progress-value">{{ formatDuration(task.estimatedTimeRemaining) }}</span>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 配置参数 -->
    <el-card class="config-card" header="配置参数">
      <el-tabs v-model="activeConfigTab">
        <el-tab-pane label="基本配置" name="basic">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="回测开始日期">{{ task.startDate }}</el-descriptions-item>
            <el-descriptions-item label="回测结束日期">{{ task.endDate }}</el-descriptions-item>
            <el-descriptions-item label="初始资金">¥{{ formatNumber(task.initialCapital) }}</el-descriptions-item>
            <el-descriptions-item label="交易手续费">{{ (task.commission * 100).toFixed(3) }}%</el-descriptions-item>
            <el-descriptions-item label="滑点设置">{{ (task.slippage * 100).toFixed(2) }}%</el-descriptions-item>
            <el-descriptions-item label="基准指数">{{ task.benchmark || '沪深300' }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
        
        <el-tab-pane label="策略参数" name="strategy">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="买入乖离率阈值">{{ (task.config?.buyBiasMin * 100).toFixed(2) }}%</el-descriptions-item>
            <el-descriptions-item label="卖出乖离率阈值">{{ (task.config?.sellBiasMax * 100).toFixed(2) }}%</el-descriptions-item>
            <el-descriptions-item label="连续确认天数">{{ task.config?.buyConsecutiveDays }}天</el-descriptions-item>
            <el-descriptions-item label="止损比例">{{ (task.config?.stopLoss * 100).toFixed(2) }}%</el-descriptions-item>
            <el-descriptions-item label="止盈比例">{{ (task.config?.takeProfit * 100).toFixed(2) }}%</el-descriptions-item>
            <el-descriptions-item label="最大仓位">{{ (task.config?.maxPositionSize * 100).toFixed(2) }}%</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
        
        <el-tab-pane label="股票列表" name="stocks" v-if="task.mode === 'batch'">
          <div class="stocks-list">
            <el-tag 
              v-for="stock in task.stockList" 
              :key="stock"
              class="stock-tag"
            >
              {{ stock }}
            </el-tag>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 执行日志 -->
    <el-card class="logs-card" header="执行日志">
      <div class="logs-header">
        <el-button @click="refreshLogs" :loading="logsLoading">
          <el-icon><Refresh /></el-icon>
          刷新日志
        </el-button>
        <el-select v-model="logLevel" placeholder="日志级别" clearable>
          <el-option label="全部" value="" />
          <el-option label="信息" value="INFO" />
          <el-option label="警告" value="WARNING" />
          <el-option label="错误" value="ERROR" />
        </el-select>
      </div>
      
      <div class="logs-content" ref="logsContainer">
        <div 
          v-for="(log, index) in filteredLogs" 
          :key="index"
          class="log-item"
          :class="getLogLevelClass(log.level)"
        >
          <span class="log-time">{{ formatDateTime(log.timestamp) }}</span>
          <span class="log-level">{{ log.level }}</span>
          <span class="log-message">{{ log.message }}</span>
        </div>
      </div>
    </el-card>

    <!-- 结果预览 -->
    <el-card v-if="task.status === 'completed'" class="results-card" header="结果预览">
      <div class="results-summary">
        <el-row :gutter="20">
          <el-col :span="6">
            <div class="result-item">
              <div class="result-label">总收益率</div>
              <div class="result-value" :class="getReturnClass(task.results?.totalReturn)">
                {{ formatPercent(task.results?.totalReturn) }}
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="result-item">
              <div class="result-label">年化收益率</div>
              <div class="result-value" :class="getReturnClass(task.results?.annualizedReturn)">
                {{ formatPercent(task.results?.annualizedReturn) }}
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="result-item">
              <div class="result-label">最大回撤</div>
              <div class="result-value text-red-600">
                {{ formatPercent(task.results?.maxDrawdown) }}
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="result-item">
              <div class="result-label">夏普比率</div>
              <div class="result-value">
                {{ formatNumber(task.results?.sharpeRatio, 2) }}
              </div>
            </div>
          </el-col>
        </el-row>
      </div>
      
      <div class="results-actions">
        <el-button type="primary" @click="viewFullReport">
          <el-icon><Document /></el-icon>
          查看完整报告
        </el-button>
        <el-button type="success" @click="downloadResults">
          <el-icon><Download /></el-icon>
          下载结果
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, inject } from 'vue'
import { ElMessage } from 'element-plus'
import { 
  Refresh, 
  Document, 
  Download 
} from '@element-plus/icons-vue'

// Props
const props = defineProps<{
  task: any
}>()

// 注入服务
const pvfrsApi = inject('pvfrsApi')

// 响应式数据
const activeConfigTab = ref('basic')
const logsLoading = ref(false)
const logLevel = ref('')
const logs = ref([])
const logsContainer = ref()

// 发射事件
const emit = defineEmits(['task-updated'])

// 计算属性
const filteredLogs = computed(() => {
  if (!logLevel.value) {
    return logs.value
  }
  return logs.value.filter(log => log.level === logLevel.value)
})

// 方法
const refreshLogs = async () => {
  try {
    logsLoading.value = true
    const result = await pvfrsApi.getTaskLogs(props.task.id)
    logs.value = result.logs || []
    
    // 滚动到底部
    setTimeout(() => {
      if (logsContainer.value) {
        logsContainer.value.scrollTop = logsContainer.value.scrollHeight
      }
    }, 100)
    
  } catch (error) {
    ElMessage.error('获取日志失败')
    console.error('获取任务日志失败:', error)
  } finally {
    logsLoading.value = false
  }
}

const viewFullReport = () => {
  // 跳转到报告详情页面
  window.open(`/reports/${props.task.reportId}`, '_blank')
}

const downloadResults = async () => {
  try {
    const blob = await pvfrsApi.downloadTaskResults(props.task.id)
    
    // 创建下载链接
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `task_${props.task.id}_results.xlsx`
    link.click()
    
    window.URL.revokeObjectURL(url)
    ElMessage.success('结果下载成功')
    
  } catch (error) {
    ElMessage.error('结果下载失败')
    console.error('下载任务结果失败:', error)
  }
}

// 辅助方法
const getModeTagType = (mode: string) => {
  const types = {
    single: '',
    batch: 'success',
    optimize: 'warning',
    portfolio: 'info'
  }
  return types[mode] || ''
}

const getModeLabel = (mode: string) => {
  const labels = {
    single: '单股回测',
    batch: '批量回测',
    optimize: '参数优化',
    portfolio: '组合回测'
  }
  return labels[mode] || mode
}

const getStatusTagType = (status: string) => {
  const types = {
    pending: 'info',
    running: 'warning',
    completed: 'success',
    failed: 'danger',
    cancelled: 'info'
  }
  return types[status] || ''
}

const getStatusLabel = (status: string) => {
  const labels = {
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '已失败',
    cancelled: '已取消'
  }
  return labels[status] || status
}

const getProgressStatus = (status: string) => {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'exception'
  return ''
}

const getMarketLabel = (market: string) => {
  const labels = {
    CN: 'A股市场',
    HK: '港股市场',
    US: '美股市场'
  }
  return labels[market] || market
}

const getLogLevelClass = (level: string) => {
  const classes = {
    INFO: 'log-info',
    WARNING: 'log-warning',
    ERROR: 'log-error'
  }
  return classes[level] || 'log-info'
}

const getReturnClass = (returnValue: number) => {
  if (returnValue > 0) return 'text-green-600'
  if (returnValue < 0) return 'text-red-600'
  return 'text-gray-600'
}

const formatDateTime = (dateTime: string) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString()
}

const formatDuration = (duration: number) => {
  if (!duration) return '-'
  const hours = Math.floor(duration / 3600)
  const minutes = Math.floor((duration % 3600) / 60)
  const seconds = duration % 60
  return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
}

const formatNumber = (value: number, digits = 0) => {
  if (value === null || value === undefined) return '-'
  return value.toLocaleString('zh-CN', { 
    minimumFractionDigits: digits,
    maximumFractionDigits: digits 
  })
}

const formatPercent = (value: number) => {
  if (value === null || value === undefined) return '-'
  return `${(value * 100).toFixed(2)}%`
}

// 生命周期
onMounted(() => {
  refreshLogs()
})
</script>

<style scoped lang="postcss">
.task-detail {
  @apply space-y-6;
}

.task-info-card,
.progress-card,
.config-card,
.logs-card,
.results-card {
  @apply shadow-sm;
}

.progress-content {
  @apply space-y-4;
}

.progress-details {
  @apply grid grid-cols-3 gap-4;
}

.progress-item {
  @apply flex justify-between items-center;
}

.progress-label {
  @apply text-sm text-gray-600;
}

.progress-value {
  @apply font-medium text-gray-900;
}

.stocks-list {
  @apply flex flex-wrap gap-2;
}

.stock-tag {
  @apply mb-2;
}

.logs-header {
  @apply flex justify-between items-center mb-4;
}

.logs-content {
  @apply bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-sm;
  height: 300px;
  overflow-y: auto;
}

.log-item {
  @apply mb-1 flex gap-2;
}

.log-time {
  @apply text-gray-500 flex-shrink-0;
  width: 160px;
}

.log-level {
  @apply flex-shrink-0;
  width: 60px;
}

.log-message {
  @apply flex-1;
}

.log-info .log-level {
  @apply text-blue-400;
}

.log-warning .log-level {
  @apply text-yellow-400;
}

.log-error .log-level {
  @apply text-red-400;
}

.results-summary {
  @apply mb-6;
}

.result-item {
  @apply text-center;
}

.result-label {
  @apply text-sm text-gray-600 mb-2;
}

.result-value {
  @apply text-2xl font-bold;
}

.results-actions {
  @apply flex gap-4 justify-center;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .progress-details {
    @apply grid-cols-1 gap-2;
  }
  
  .results-summary :deep(.el-col) {
    @apply mb-4;
  }
  
  .results-actions {
    @apply flex-col;
  }
  
  .logs-content {
    height: 200px;
    @apply text-xs;
  }
  
  .log-time {
    width: 120px;
  }
  
  .log-level {
    width: 50px;
  }
}
</style>