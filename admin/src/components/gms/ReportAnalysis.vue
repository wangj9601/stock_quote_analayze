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
        <el-table-column label="结果摘要" min-width="260">
          <template #default="scope">
            <span v-if="scope.row.summary && isTradeSimulationSummary(scope.row.summary)">
              {{ scope.row.summary.total_trades ?? 0 }} 笔 · 胜率 {{ formatPct(scope.row.summary.win_rate) }} ·
              近似年化 {{ formatPct(scope.row.summary.approx_annual_return_simple) }}
            </span>
            <span v-else-if="scope.row.summary">
              {{ scope.row.summary.total_samples }} 样本 · 命中率 {{ ((scope.row.summary.hit_rate ?? 0) * 100).toFixed(1) }}%
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="完成时间" width="180">
          <template #default="scope">{{ formatDateTimeBeijing(scope.row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="viewReport(scope.row)">查看</el-button>
            <el-button size="small" type="success" @click="downloadReport(scope.row)">下载明细</el-button>
            <el-button size="small" @click="downloadReport(scope.row, 'csv')">下载CSV</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="detailVisible" title="报告详情" width="720px" destroy-on-close>
      <div v-if="currentReport" class="report-detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="报告ID">{{ currentReport.report_id?.slice(0, 8) }}</el-descriptions-item>
          <el-descriptions-item label="名称">{{ currentReport.name }}</el-descriptions-item>
          <el-descriptions-item label="完成时间" :span="2">{{ formatDateTimeBeijing(currentReport.created_at) }}</el-descriptions-item>
          <template v-if="currentReport.summary && isTradeSimulationSummary(currentReport.summary)">
            <el-descriptions-item label="任务类型" :span="2">交易回测</el-descriptions-item>
            <el-descriptions-item label="说明" :span="2">
              <span class="text-gray-600 text-sm">优先看近似年化、算术累计、笔均组合贡献；链条复利笔数多时易极端放大，仅作参考。</span>
            </el-descriptions-item>
            <el-descriptions-item label="近似年化（简单折算）">
              {{ formatPct(currentReport.summary.approx_annual_return_simple) }}
            </el-descriptions-item>
            <el-descriptions-item label="算术累计收益">
              {{ formatPct(currentReport.summary.total_return_arithmetic) }}
            </el-descriptions-item>
            <el-descriptions-item label="笔均组合贡献">
              {{ formatPct(currentReport.summary.avg_portfolio_pnl_per_trade) }}
            </el-descriptions-item>
            <el-descriptions-item label="回测自然日">
              {{ currentReport.summary.backtest_calendar_days ?? '-' }} 天
            </el-descriptions-item>
            <el-descriptions-item label="单笔仓位">
              {{ ((Number(currentReport.summary.position_fraction) || 1) * 100).toFixed(0) }}%
            </el-descriptions-item>
            <el-descriptions-item label="交易数">{{ currentReport.summary.total_trades ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="胜率">{{ formatPct(currentReport.summary.win_rate) }}</el-descriptions-item>
            <el-descriptions-item label="链条复利（参考）">
              {{ formatPct(currentReport.summary.total_return_compound) }}
            </el-descriptions-item>
            <el-descriptions-item label="最大回撤">{{ formatPct(currentReport.summary.max_drawdown) }}</el-descriptions-item>
            <el-descriptions-item label="盈亏比">{{ formatProfitFactor(currentReport.summary.profit_factor) }}</el-descriptions-item>
            <el-descriptions-item label="目标涨幅">{{ ((currentReport.summary.target_pct ?? 0) * 100).toFixed(2) }}%</el-descriptions-item>
          </template>
          <template v-else-if="currentReport.summary">
            <el-descriptions-item label="任务类型">策略信号命中率</el-descriptions-item>
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
import { formatDateTimeBeijing } from '@/utils/formatBeijingTime'

const gmsApi = inject<any>('gmsApi')
const loading = ref(false)
const reports = ref<any[]>([])
const detailVisible = ref(false)
const currentReport = ref<any>(null)

function isTradeSimulationSummary(s: Record<string, unknown> | null | undefined): boolean {
  return String(s?.backtest_type || '') === 'trade_simulation'
}

/** 比率转百分比展示，如 0.052 -> 5.20% */
function formatPct(v: unknown): string {
  const n = Number(v)
  if (Number.isNaN(n)) return '-'
  return `${(n * 100).toFixed(2)}%`
}

function formatProfitFactor(v: unknown): string {
  const n = Number(v)
  if (Number.isNaN(n)) return '-'
  return n.toFixed(3)
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

async function downloadReport(row: any, variant?: 'csv' | 'xlsx') {
  try {
    const { blob, filename } = await gmsApi.downloadReport(row.report_id, variant)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('下载已开始')
  } catch (e) {
    ElMessage.error('下载失败')
  }
}

defineEmits<{ (e: 'report-generated', report: any): void }>()
defineExpose({ refresh })

onMounted(() => refresh())
</script>

<style scoped>
.report-header { margin-bottom: 12px; }
</style>
