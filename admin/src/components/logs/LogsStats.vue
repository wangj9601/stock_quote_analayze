<template>
  <div class="logs-stats">
    <el-row :gutter="16">
      <el-col :xs="12" :sm="12" :md="6" :lg="6" :xl="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon total">
              <el-icon><Document /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats?.total || 0 }}</div>
              <div class="stat-label">{{ mode === 'app' ? '匹配条数' : '总日志数' }}</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="12" :sm="12" :md="6" :lg="6" :xl="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" :class="mode === 'app' ? 'warning' : 'success'">
              <el-icon><component :is="mode === 'app' ? Warning : CircleCheck" /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ mode === 'app' ? (stats?.warning || 0) : (stats?.success || 0) }}</div>
              <div class="stat-label">{{ mode === 'app' ? '警告' : '成功日志' }}</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="12" :sm="12" :md="6" :lg="6" :xl="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon error">
              <el-icon><CircleClose /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats?.error || 0 }}</div>
              <div class="stat-label">{{ mode === 'app' ? '错误' : '错误日志' }}</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="12" :sm="12" :md="6" :lg="6" :xl="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon rate">
              <el-icon><TrendCharts /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">
                <template v-if="mode === 'app'">{{ formatBytes(stats?.bytesRead) }}</template>
                <template v-else>{{ formatSuccessRate(stats?.successRate) }}%</template>
              </div>
              <div class="stat-label">{{ mode === 'app' ? '已扫描字节' : '成功率' }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { Document, CircleCheck, CircleClose, TrendCharts, Warning } from '@element-plus/icons-vue'
import type { LogStats } from '@/types/logs.types'

interface Props {
  stats: LogStats | null
  mode?: 'db' | 'app'
}

withDefaults(defineProps<Props>(), {
  mode: 'db',
})

const formatSuccessRate = (rate: number | undefined) => {
  if (rate === undefined || rate === null) return 0
  return Math.round(rate * 100)
}

const formatBytes = (n: number | undefined) => {
  if (!n) return '0 B'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<style scoped>
.logs-stats {
  @apply mb-6;
}

.stat-card {
  @apply h-24;
}

.stat-content {
  @apply flex items-center h-full;
}

.stat-icon {
  @apply w-12 h-12 rounded-lg flex items-center justify-center mr-4;
}

.stat-icon.total {
  @apply bg-blue-100 text-blue-600;
}

.stat-icon.success {
  @apply bg-green-100 text-green-600;
}

.stat-icon.warning {
  @apply bg-yellow-100 text-yellow-700;
}

.stat-icon.error {
  @apply bg-red-100 text-red-600;
}

.stat-icon.rate {
  @apply bg-purple-100 text-purple-600;
}

.stat-info {
  @apply flex-1;
}

.stat-value {
  @apply text-2xl font-bold text-gray-900;
}

.stat-label {
  @apply text-sm text-gray-500 mt-1;
}

@media (max-width: 768px) {
  .logs-stats {
    @apply mb-4;
  }

  .stat-card {
    @apply h-20 mb-4;
  }

  .stat-icon {
    @apply w-10 h-10 mr-3;
  }

  .stat-value {
    @apply text-xl;
  }

  .stat-label {
    @apply text-xs;
  }
}
</style>
