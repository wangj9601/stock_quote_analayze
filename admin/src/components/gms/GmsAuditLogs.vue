<template>
  <div class="gms-audit-logs">
    <div class="flex items-center justify-between mb-3">
      <span class="text-sm text-gray-600">GMS 管理/交易操作留痕（operation_logs · gms_*）</span>
      <el-button size="small" :loading="loading" @click="refresh">
        <el-icon class="mr-1"><Refresh /></el-icon>
        刷新
      </el-button>
    </div>
    <el-table :data="items" v-loading="loading" stripe border size="small" max-height="480">
      <el-table-column prop="log_time" label="时间" width="168" />
      <el-table-column prop="log_type" label="类型" width="160" />
      <el-table-column label="详情" min-width="280">
        <template #default="{ row }">
          <span class="text-xs font-mono break-all">{{ formatMessage(row.log_message) }}</span>
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

const gmsApi = inject<any>('gmsApi')
const loading = ref(false)
const items = ref<any[]>([])

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

async function refresh() {
  loading.value = true
  try {
    items.value = await gmsApi.getAuditLogs({ limit: 100 })
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
