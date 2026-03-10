<template>
  <div class="report-analysis">
    <el-card header="历史报告">
      <div class="report-header">
        <el-button @click="refresh" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
      <el-table :data="reports" v-loading="loading" stripe>
        <el-table-column prop="report_id" label="报告ID" width="100">
          <template #default="scope">{{ (scope.row.report_id || '').slice(0, 8) }}</template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column label="样本/命中率" width="140">
          <template #default="scope">
            <span v-if="scope.row.summary">
              {{ scope.row.summary.total_samples }} 样本，
              {{ ((scope.row.summary.hit_rate ?? 0) * 100).toFixed(1) }}%
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="完成时间" width="170">
          <template #default="scope">{{ formatDate(scope.row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="viewReport(scope.row)">查看</el-button>
            <el-button size="small" type="success" @click="downloadReport(scope.row)">下载CSV</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="detailVisible" title="报告详情" width="640px" destroy-on-close>
      <div v-if="currentReport" class="report-detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="报告ID">{{ currentReport.report_id?.slice(0, 8) }}</el-descriptions-item>
          <el-descriptions-item label="名称">{{ currentReport.name }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ formatDate(currentReport.created_at) }}</el-descriptions-item>
          <template v-if="currentReport.summary">
            <el-descriptions-item label="样本数">{{ currentReport.summary.total_samples }}</el-descriptions-item>
            <el-descriptions-item label="命中数">{{ currentReport.summary.hit_count }}</el-descriptions-item>
            <el-descriptions-item label="命中率">
              {{ ((currentReport.summary.hit_rate ?? 0) * 100).toFixed(2) }}%
            </el-descriptions-item>
            <el-descriptions-item label="目标涨幅">{{ (currentReport.summary.target_pct * 100) }}%</el-descriptions-item>
          </template>
        </el-descriptions>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, inject } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

const gmsApi = inject<any>('gmsApi')
const loading = ref(false)
const reports = ref<any[]>([])
const detailVisible = ref(false)
const currentReport = ref<any>(null)

function formatDate(v: string) {
  if (!v) return '-'
  return v.replace('Z', '').slice(0, 19)
}

async function refresh() {
  loading.value = true
  try {
    reports.value = await gmsApi.getReports({ limit: 100 })
  } catch (e) {
    ElMessage.error('获取报告列表失败')
    reports.value = []
  } finally {
    loading.value = false
  }
}

async function viewReport(row: any) {
  try {
    currentReport.value = await gmsApi.getReport(row.report_id)
    detailVisible.value = true
  } catch (e) {
    ElMessage.error('获取报告详情失败')
  }
}

async function downloadReport(row: any) {
  try {
    const blob = await gmsApi.downloadReport(row.report_id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `gms_backtest_${(row.report_id || '').slice(0, 8)}.csv`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('下载已开始')
  } catch (e) {
    ElMessage.error('下载失败')
  }
}

const emit = defineEmits<{ (e: 'report-generated', report: any): void }>()
defineExpose({ refresh })

onMounted(() => refresh())
</script>

<style scoped>
.report-header { margin-bottom: 12px; }
</style>
