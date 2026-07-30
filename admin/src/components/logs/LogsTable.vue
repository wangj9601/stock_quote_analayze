<template>
  <div class="logs-table table-scroll">
    <el-card>
      <el-table
        :data="logs"
        :loading="loading"
        stripe
        border
        style="width: 100%"
        class="responsive-table"
      >
        <el-table-column prop="id" label="ID" width="80" min-width="60" show-overflow-tooltip />
        
        <!-- 历史采集日志字段 -->
        <template v-if="props.logType === 'historical_collect' || props.logType === 'realtime_collect'">
          <el-table-column prop="operation_type" label="操作类型" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag :type="getOperationTypeTag(row.operation_type)" size="small">
                {{ row.operation_type }}
              </el-tag>
            </template>
          </el-table-column>
          
          <el-table-column prop="operation_desc" label="操作描述" min-width="300">
            <template #default="{ row }">
              <div class="message-cell">
                <span class="message-text">{{ row.operation_desc }}</span>
                <el-button
                  v-if="row.error_message"
                  type="text"
                  size="small"
                  @click="showDetails(row)"
                >
                  错误详情
                </el-button>
              </div>
            </template>
          </el-table-column>
          
          <el-table-column prop="affected_rows" label="影响行数" min-width="100" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag :type="row.affected_rows > 0 ? 'success' : 'info'" size="small">
                {{ row.affected_rows }}
              </el-tag>
            </template>
          </el-table-column>
          
          <el-table-column prop="status" label="状态" min-width="80" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)" size="small">
                {{ getStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          
          <el-table-column prop="collect_source" label="采集来源" min-width="100" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag :type="getCollectSourceTag(row.collect_source)" size="small">
                {{ getCollectSourceText(row.collect_source) }}
              </el-tag>
            </template>
          </el-table-column>
          
          <el-table-column prop="created_at" label="创建时间" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">
              {{ formatDateTime(row.created_at) }}
            </template>
          </el-table-column>
        </template>
        
        <!-- 操作日志字段 -->
        <template v-else-if="props.logType === 'operation'">
          <el-table-column prop="log_type" label="日志类型" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag :type="getLogTypeTag(row.log_type)" size="small">
                {{ row.log_type }}
              </el-tag>
            </template>
          </el-table-column>
          
          <el-table-column prop="log_message" label="日志消息" min-width="300">
            <template #default="{ row }">
              <div class="message-cell">
                <span class="message-text">{{ row.log_message }}</span>
                <el-button
                  v-if="row.error_info"
                  type="text"
                  size="small"
                  @click="showDetails(row)"
                >
                  错误详情
                </el-button>
              </div>
            </template>
          </el-table-column>
          
          <el-table-column prop="affected_count" label="影响数量" min-width="100" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag :type="row.affected_count > 0 ? 'success' : 'info'" size="small">
                {{ row.affected_count }}
              </el-tag>
            </template>
          </el-table-column>
          
          <el-table-column prop="log_status" label="状态" min-width="80" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.log_status)" size="small">
                {{ getStatusText(row.log_status) }}
              </el-tag>
            </template>
          </el-table-column>
          
          <el-table-column prop="log_time" label="日志时间" width="180">
            <template #default="{ row }">
              {{ formatDateTime(row.log_time) }}
            </template>
          </el-table-column>
        </template>
        
        <!-- 默认日志字段（兼容旧版本） -->
        <template v-else>
          <el-table-column prop="timestamp" label="时间" width="180">
            <template #default="{ row }">
              {{ formatDateTime(row.timestamp) }}
            </template>
          </el-table-column>
          
          <el-table-column prop="level" label="级别" width="100">
            <template #default="{ row }">
              <el-tag :type="getLevelType(row.level)" size="small">
                {{ row.level }}
              </el-tag>
            </template>
          </el-table-column>
          
          <el-table-column prop="source" label="来源" width="150" />
          
          <el-table-column prop="message" label="消息" min-width="300">
            <template #default="{ row }">
              <div class="message-cell">
                <span class="message-text">{{ row.message }}</span>
                <el-button
                  v-if="row.details"
                  type="text"
                  size="small"
                  @click="showDetails(row)"
                >
                  详情
                </el-button>
              </div>
            </template>
          </el-table-column>
          
          <el-table-column prop="user_id" label="用户ID" width="100" />
          
          <el-table-column prop="ip_address" label="IP地址" width="120" />
        </template>
      </el-table>
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog
      v-model="detailsVisible"
      title="日志详情"
      width="600px"
    >
      <div v-if="selectedLog" class="log-details">
        <div class="detail-item">
          <span class="detail-label">ID:</span>
          <span class="detail-value">{{ selectedLog.id }}</span>
        </div>
        
                 <!-- 历史采集日志详情 -->
         <template v-if="(props.logType === 'historical_collect' || props.logType === 'realtime_collect') && selectedLog && isCollectLogEntry(selectedLog)">
          <div class="detail-item">
            <span class="detail-label">操作类型:</span>
            <span class="detail-value">{{ selectedLog.operation_type }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">操作描述:</span>
            <span class="detail-value">{{ selectedLog.operation_desc }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">影响行数:</span>
            <span class="detail-value">{{ selectedLog.affected_rows }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">状态:</span>
            <span class="detail-value">{{ getStatusText(selectedLog.status) }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">采集来源:</span>
            <span class="detail-value">
              <el-tag :type="getCollectSourceTag(selectedLog.collect_source)" size="small">
                {{ getCollectSourceText(selectedLog.collect_source) }}
              </el-tag>
            </span>
          </div>
          <div class="detail-item">
            <span class="detail-label">创建时间:</span>
            <span class="detail-value">{{ formatDateTime(selectedLog.created_at) }}</span>
          </div>
          <div v-if="selectedLog.error_message" class="detail-item">
            <span class="detail-label">错误信息:</span>
            <div class="detail-value details-content">
              <pre>{{ selectedLog.error_message }}</pre>
            </div>
          </div>
        </template>
        
        <!-- 操作日志详情 -->
        <template v-else-if="props.logType === 'operation' && selectedLog && isOperationLogEntry(selectedLog)">
          <div class="detail-item">
            <span class="detail-label">日志类型:</span>
            <span class="detail-value">{{ selectedLog.log_type }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">日志消息:</span>
            <span class="detail-value">{{ selectedLog.log_message }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">影响数量:</span>
            <span class="detail-value">{{ selectedLog.affected_count }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">状态:</span>
            <span class="detail-value">{{ getStatusText(selectedLog.log_status) }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">日志时间:</span>
            <span class="detail-value">{{ formatDateTime(selectedLog.log_time) }}</span>
          </div>
          <div v-if="selectedLog.error_info" class="detail-item">
            <span class="detail-label">错误信息:</span>
            <div class="detail-value details-content">
              <pre>{{ selectedLog.error_info }}</pre>
            </div>
          </div>
        </template>
        
        <!-- 默认日志详情 -->
        <template v-else-if="selectedLog && isLogEntry(selectedLog)">
          <div class="detail-item">
            <span class="detail-label">时间:</span>
            <span class="detail-value">{{ formatDateTime(selectedLog.timestamp) }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">级别:</span>
            <span class="detail-value">
              <el-tag :type="getLevelType(selectedLog.level)" size="small">
                {{ selectedLog.level }}
              </el-tag>
            </span>
          </div>
          <div class="detail-item">
            <span class="detail-label">来源:</span>
            <span class="detail-value">{{ selectedLog.source }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">消息:</span>
            <span class="detail-value">{{ selectedLog.message }}</span>
          </div>
          <div v-if="selectedLog.details" class="detail-item">
            <span class="detail-label">详情:</span>
            <div class="detail-value details-content">
              <pre>{{ selectedLog.details }}</pre>
            </div>
          </div>
          <div v-if="selectedLog.user_id" class="detail-item">
            <span class="detail-label">用户ID:</span>
            <span class="detail-value">{{ selectedLog.user_id }}</span>
          </div>
          <div v-if="selectedLog.ip_address" class="detail-item">
            <span class="detail-label">IP地址:</span>
            <span class="detail-value">{{ selectedLog.ip_address }}</span>
          </div>
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import dayjs from 'dayjs'
import type { AnyLogEntry, LogEntry, OperationLogEntry, HistoricalCollectLogEntry, RealtimeCollectLogEntry } from '@/types/logs.types'

interface Props {
  logs: AnyLogEntry[]
  loading: boolean
  logType?: 'historical_collect' | 'realtime_collect' | 'operation' | string
}

const props = withDefaults(defineProps<Props>(), {
  logType: 'historical_collect'
})

// 详情对话框
const detailsVisible = ref(false)
const selectedLog = ref<AnyLogEntry | null>(null)

// 类型守卫函数
const isLogEntry = (log: AnyLogEntry): log is LogEntry => {
  return 'timestamp' in log && 'level' in log && 'source' in log && 'message' in log
}

const isOperationLogEntry = (log: AnyLogEntry): log is OperationLogEntry => {
  return 'log_type' in log && 'log_message' in log && 'log_time' in log
}

const isCollectLogEntry = (log: AnyLogEntry): log is HistoricalCollectLogEntry | RealtimeCollectLogEntry => {
  return 'operation_type' in log && 'operation_desc' in log && 'created_at' in log
}

// 格式化日期时间
const formatDateTime = (timestamp: string) => {
  return dayjs(timestamp).format('YYYY-MM-DD HH:mm:ss')
}

// 获取日志级别对应的标签类型（限定为 Element Plus 允许的取值）
const getLevelType = (level: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  if (level === 'WARNING') return 'warning'
  if (level === 'ERROR') return 'danger'
  // INFO、DEBUG 或未知都使用 'info'
  return 'info'
}

// 获取操作类型对应的标签类型
const getOperationTypeTag = (type: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  if (type.includes('historical')) return 'primary'
  if (type.includes('realtime')) return 'success'
  if (type.includes('watchlist')) return 'warning'
  return 'info'
}

// 获取日志类型对应的标签类型
const getLogTypeTag = (type: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  if (type.includes('error')) return 'danger'
  if (type.includes('warning')) return 'warning'
  if (type.includes('success')) return 'success'
  return 'info'
}

// 获取状态对应的标签类型
const getStatusType = (status: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  if (status === 'success') return 'success'
  if (status === 'error') return 'danger'
  if (status === 'partial_success') return 'warning'
  return 'info'
}

// 获取状态文本
const getStatusText = (status: string): string => {
  const statusMap: Record<string, string> = {
    'success': '成功',
    'error': '失败',
    'partial_success': '部分成功',
    'pending': '待处理',
    'running': '运行中'
  }
  return statusMap[status] || status
}

// 获取采集来源对应的标签类型
const getCollectSourceTag = (source: string | undefined): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  if (!source) return 'info'
  if (source === 'akshare') return 'primary'
  if (source === 'tushare') return 'success'
  return 'info'
}

// 获取采集来源文本
const getCollectSourceText = (source: string | undefined): string => {
  if (!source) return '其他'
  const sourceMap: Record<string, string> = {
    'akshare': 'akshare',
    'tushare': 'tushare',
    'other': '其他'
  }
  return sourceMap[source] || source || '其他'
}

// 显示详情
const showDetails = (log: AnyLogEntry) => {
  selectedLog.value = log
  detailsVisible.value = true
}
</script>

<style scoped>
.logs-table {
  @apply mb-6;
}

.message-cell {
  @apply flex items-center justify-between;
}

.message-text {
  @apply flex-1 truncate;
}

.log-details {
  @apply space-y-4;
}

.detail-item {
  @apply flex items-start;
}

.detail-label {
  @apply w-20 text-sm font-medium text-gray-700 mr-4;
}

.detail-value {
  @apply flex-1 text-sm text-gray-900;
}

.details-content {
  @apply bg-gray-50 p-3 rounded border;
}

.details-content pre {
  @apply text-xs text-gray-700 whitespace-pre-wrap;
}
</style> 