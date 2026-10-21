<template>
  <div class="csb-audit-logs">
    <div class="flex items-center justify-between mb-3">
      <span class="text-sm text-gray-600">CSB 管理操作留痕（operation_logs · csb_*）</span>
      <el-button size="small" :loading="loading" @click="refresh">
        <el-icon class="mr-1"><Refresh /></el-icon>
        刷新
      </el-button>
    </div>
    <el-table :data="items" v-loading="loading" stripe border size="small" max-height="480">
      <el-table-column prop="log_time" label="时间" width="168" />
      <el-table-column prop="log_type" label="类型" width="160" />
      <el-table-column label="详情" min-width="320">
        <template #default="{ row }">
          <div class="text-xs break-all leading-5">
            <div v-if="summarizeMessage(row)" class="text-gray-800">{{ summarizeMessage(row) }}</div>
            <div class="font-mono text-gray-500">{{ formatMessage(row.log_message) }}</div>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="affected_count" label="影响数" width="72" />
      <el-table-column prop="log_status" label="状态" width="80" />
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, inject } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const csbApi = inject<any>('csbApi')
const loading = ref(false)
const items = ref<any[]>([])

function parseMessage(msg: unknown): Record<string, unknown> | null {
  if (msg == null) return null
  if (typeof msg === 'object' && !Array.isArray(msg)) return msg as Record<string, unknown>
  if (typeof msg === 'string') {
    try {
      const obj = JSON.parse(msg)
      return obj && typeof obj === 'object' && !Array.isArray(obj) ? obj : null
    } catch {
      return null
    }
  }
  return null
}

function formatMessage(msg: unknown): string {
  if (msg == null) return ''
  if (typeof msg === 'string') {
    try {
      return JSON.stringify(JSON.parse(msg), null, 0)
    } catch {
      return msg
    }
  }
  return JSON.stringify(msg)
}

/** 关键展示区间起止等关键字段，避免只看压缩 JSON */
function summarizeMessage(row: { log_type?: string; log_message?: unknown }): string {
  const obj = parseMessage(row?.log_message)
  if (!obj) return ''
  const type = String(row?.log_type || '')
  const cid = obj.config_id != null ? `版本 ${obj.config_id}` : ''
  const start = obj.start_date != null ? String(obj.start_date) : ''
  const end = obj.end_date != null ? String(obj.end_date) : ''
  if (type.includes('trace_refresh_range') || (start && end)) {
    const range = start && end ? `区间 ${start}～${end}` : ''
    const phase = obj.phase === 'started'
      ? '已启动'
      : obj.phase === 'completed'
        ? '已完成'
        : obj.phase === 'failed'
          ? '失败'
          : ''
    const purged = obj.purged_rows != null ? `删除 ${obj.purged_rows}` : ''
    const hits = obj.precompute_hits != null ? `写入买点 ${obj.precompute_hits}` : ''
    const days = obj.precomputed_days != null ? `补算 ${obj.precomputed_days} 日` : ''
    return [cid, range, phase, purged, days, hits].filter(Boolean).join(' · ')
  }
  if (type.includes('trace_purge') && cid) {
    return `${cid} · 清空全部 trace`
  }
  return cid
}

async function refresh() {
  loading.value = true
  try {
    items.value = await csbApi.getAuditLogs({ limit: 100 })
  } catch {
    ElMessage.error('加载操作记录失败')
    items.value = []
  } finally {
    loading.value = false
  }
}

defineExpose({ refresh })
onMounted(() => refresh())
</script>
