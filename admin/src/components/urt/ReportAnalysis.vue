<template>
  <div class="urt-report-analysis">
    <el-card header="历史报告与统计分析">
      <div class="report-header">
        <el-button :loading="loading" @click="refresh">刷新</el-button>
      </div>
      <el-table :data="reports" v-loading="loading" stripe size="small">
        <el-table-column prop="report_id" label="报告ID" width="100">
          <template #default="{ row }">{{ (row.report_id || '').slice(0, 8) }}</template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column label="结果摘要" min-width="280">
          <template #default="{ row }">
            <span v-if="row.summary">
              {{ row.summary.total_signals ?? row.summary.total_samples ?? 0 }} 信号 ·
              命中率 {{ formatPct(row.summary.hit_rate) }} ·
              胜率 {{ formatPct(row.summary.win_rate) }} ·
              均盈亏 {{ row.summary.avg_pnl_pct ?? '-' }}%
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="完成时间" width="180" />
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="viewReport(row)">查看</el-button>
            <el-button size="small" type="success" @click="downloadReport(row)" :disabled="!row.has_details_csv">下载明细</el-button>
            <el-button size="small" type="danger" plain @click="deleteReport(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="detailVisible" title="URT 报告详情" width="860px" destroy-on-close>
      <div v-if="currentReport" class="report-detail">
        <el-tabs v-model="detailTab">
          <el-tab-pane label="摘要" name="summary">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="报告ID">{{ currentReport.report_id?.slice(0, 8) }}</el-descriptions-item>
              <el-descriptions-item label="名称">{{ currentReport.name }}</el-descriptions-item>
              <el-descriptions-item label="完成时间" :span="2">{{ currentReport.created_at }}</el-descriptions-item>
              <template v-if="currentReport.summary">
                <el-descriptions-item label="信号数">{{ currentReport.summary.total_signals ?? currentReport.summary.total_samples }}</el-descriptions-item>
                <el-descriptions-item label="命中数">{{ currentReport.summary.target_hits ?? currentReport.summary.hit_count }}</el-descriptions-item>
                <el-descriptions-item label="命中率">{{ formatPct(currentReport.summary.hit_rate) }}</el-descriptions-item>
                <el-descriptions-item label="胜率">{{ formatPct(currentReport.summary.win_rate) }}</el-descriptions-item>
                <el-descriptions-item label="均盈亏">{{ currentReport.summary.avg_pnl_pct }}%</el-descriptions-item>
                <el-descriptions-item label="目标涨幅">{{ ((currentReport.summary.target_pct || 0) * 100).toFixed(1) }}%</el-descriptions-item>
                <el-descriptions-item label="观察日数">{{ currentReport.summary.horizon_days }}</el-descriptions-item>
                <el-descriptions-item label="日期区间">
                  {{ currentReport.summary.start_date }} ~ {{ currentReport.summary.end_date }}
                </el-descriptions-item>
              </template>
            </el-descriptions>

            <h4 v-if="scoreBucketRows.length" class="mt-4 mb-2">按分数分桶</h4>
            <el-table v-if="scoreBucketRows.length" :data="scoreBucketRows" size="small" border>
              <el-table-column prop="name" label="分桶" />
              <el-table-column prop="total" label="样本" width="80" />
              <el-table-column prop="hit" label="命中" width="80" />
              <el-table-column label="命中率" width="100">
                <template #default="{ row }">{{ formatPct(row.hit_rate) }}</template>
              </el-table-column>
              <el-table-column label="胜率" width="100">
                <template #default="{ row }">{{ formatPct(row.win_rate) }}</template>
              </el-table-column>
              <el-table-column label="均盈亏" width="100">
                <template #default="{ row }">{{ row.avg_pnl_pct ?? '-' }}%</template>
              </el-table-column>
            </el-table>

            <h4 v-if="factorBucketRows.length" class="mt-4 mb-2">按信号因子分桶</h4>
            <el-table v-if="factorBucketRows.length" :data="factorBucketRows" size="small" border>
              <el-table-column prop="factor" label="因子" width="120" />
              <el-table-column prop="bucket" label="分箱" width="100" />
              <el-table-column prop="total" label="样本" width="70" />
              <el-table-column label="命中率" width="90">
                <template #default="{ row }">{{ formatPct(row.hit_rate) }}</template>
              </el-table-column>
              <el-table-column label="均盈亏" width="90">
                <template #default="{ row }">{{ row.avg_pnl_pct ?? '-' }}%</template>
              </el-table-column>
              <el-table-column label="均最大涨幅" width="100">
                <template #default="{ row }">{{ row.avg_max_gain_pct ?? '-' }}%</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="分布图表" name="charts" v-if="currentReport.summary">
            <div ref="holdingChartRef" style="width:100%;height:260px;margin-bottom:16px"></div>
            <div ref="monthlyChartRef" style="width:100%;height:260px"></div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'

const urtApi = inject<any>('urtApi')
const loading = ref(false)
const reports = ref<any[]>([])
const detailVisible = ref(false)
const detailTab = ref('summary')
const currentReport = ref<any>(null)
const holdingChartRef = ref<HTMLElement | null>(null)
const monthlyChartRef = ref<HTMLElement | null>(null)
let holdingChart: echarts.ECharts | null = null
let monthlyChart: echarts.ECharts | null = null

const scoreBucketRows = computed(() => {
  const buckets = currentReport.value?.summary?.by_score_bucket || {}
  return Object.keys(buckets).map((name) => ({
    name,
    total: buckets[name]?.total ?? 0,
    hit: buckets[name]?.hit ?? 0,
    hit_rate: buckets[name]?.hit_rate ?? 0,
    win_rate: buckets[name]?.win_rate,
    avg_pnl_pct: buckets[name]?.avg_pnl_pct,
  }))
})

const factorBucketRows = computed(() => {
  const factors = currentReport.value?.summary?.by_factor_bucket || {}
  const rows: any[] = []
  Object.keys(factors).forEach((key) => {
    const spec = factors[key] || {}
    const label = spec.label || key
    const bins = Array.isArray(spec.bins) ? spec.bins : []
    bins.forEach((b: any) => {
      rows.push({
        factor: label,
        bucket: b.bucket,
        total: b.total,
        hit_rate: b.hit_rate,
        avg_pnl_pct: b.avg_pnl_pct,
        avg_max_gain_pct: b.avg_max_gain_pct,
      })
    })
  })
  return rows
})

function formatPct(v: unknown) {
  const n = Number(v)
  if (Number.isNaN(n)) return '-'
  return `${(n * 100).toFixed(2)}%`
}

async function refresh() {
  if (!urtApi) return
  loading.value = true
  try {
    reports.value = await urtApi.getReports({ limit: 100 })
  } catch (e: any) {
    ElMessage.error(e.message || '获取报告失败')
    reports.value = []
  } finally {
    loading.value = false
  }
}

async function viewReport(row: any) {
  try {
    currentReport.value = await urtApi.getReport(row.report_id)
    detailTab.value = 'summary'
    detailVisible.value = true
    await nextTick()
  } catch (e: any) {
    ElMessage.error(e.message || '获取报告详情失败')
  }
}

function renderCharts() {
  const summary = currentReport.value?.summary
  if (!summary) return
  const hist = summary.holding_days_histogram || {}
  const monthly = summary.monthly_returns || []
  if (holdingChartRef.value) {
    holdingChart?.dispose()
    holdingChart = echarts.init(holdingChartRef.value)
    holdingChart.setOption({
      title: { text: '持有天数分布', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: Object.keys(hist) },
      yAxis: { type: 'value', name: '笔数' },
      series: [{ type: 'bar', data: Object.values(hist), itemStyle: { color: '#409eff' } }],
    })
  }
  if (monthlyChartRef.value && monthly.length) {
    monthlyChart?.dispose()
    monthlyChart = echarts.init(monthlyChartRef.value)
    monthlyChart.setOption({
      title: { text: '分月平均盈亏(%)', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: monthly.map((m: any) => m.month) },
      yAxis: { type: 'value', name: '%' },
      series: [{ type: 'line', data: monthly.map((m: any) => m.return_pct), smooth: true, itemStyle: { color: '#67c23a' } }],
    })
  }
}

watch(detailTab, async (tab) => {
  if (tab === 'charts' && detailVisible.value) {
    await nextTick()
    renderCharts()
  }
})

watch(detailVisible, (v) => {
  if (!v) {
    holdingChart?.dispose()
    monthlyChart?.dispose()
    holdingChart = null
    monthlyChart = null
  }
})

function downloadReport(row: any) {
  window.open(urtApi.reportDownloadUrl(row.report_id), '_blank')
}

async function deleteReport(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除报告「${row.name}」？`, '提示', { type: 'warning' })
    await urtApi.deleteReport(row.report_id)
    ElMessage.success('已删除')
    await refresh()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

onMounted(refresh)

defineExpose({ refresh })
</script>

<style scoped>
.report-header { margin-bottom: 12px; }
.mt-4 { margin-top: 16px; }
.mb-2 { margin-bottom: 8px; }
</style>
