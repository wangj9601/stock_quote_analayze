<template>
  <div class="report-comparison">
    <!-- 对比概览 -->
    <el-card class="comparison-overview" header="对比概览">
      <el-row :gutter="20">
        <el-col :span="8">
          <div class="overview-item">
            <div class="overview-label">对比报告数量</div>
            <div class="overview-value">{{ reports.length }}</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="overview-item">
            <div class="overview-label">最佳收益率</div>
            <div class="overview-value text-green-600">
              {{ formatPercent(bestPerformance.totalReturn) }}
            </div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="overview-item">
            <div class="overview-label">最佳夏普比率</div>
            <div class="overview-value text-blue-600">
              {{ formatNumber(bestPerformance.sharpeRatio, 2) }}
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 指标对比表格 -->
    <el-card class="metrics-comparison" header="指标对比">
      <el-table :data="comparisonData" stripe class="comparison-table">
        <el-table-column prop="reportId" label="报告ID" width="120" />
        <el-table-column prop="title" label="报告名称" min-width="150" />
        <el-table-column prop="totalReturn" label="总收益率" width="120">
          <template #default="scope">
            <span :class="getReturnClass(scope.row.totalReturn)">
              {{ formatPercent(scope.row.totalReturn) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="annualReturn" label="年化收益率" width="120">
          <template #default="scope">
            <span :class="getReturnClass(scope.row.annualReturn)">
              {{ formatPercent(scope.row.annualReturn) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="sharpeRatio" label="夏普比率" width="100">
          <template #default="scope">
            {{ formatNumber(scope.row.sharpeRatio, 2) }}
          </template>
        </el-table-column>
        <el-table-column prop="maxDrawdown" label="最大回撤" width="100">
          <template #default="scope">
            <span class="text-red-600">
              {{ formatPercent(scope.row.maxDrawdown) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="winRate" label="胜率" width="100">
          <template #default="scope">
            {{ formatPercent(scope.row.winRate) }}
          </template>
        </el-table-column>
        <el-table-column prop="tradeCount" label="交易次数" width="100" />
        <el-table-column label="排名" width="80">
          <template #default="scope">
            <el-tag :type="getRankTagType(scope.$index + 1)">
              {{ scope.$index + 1 }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 可视化对比 -->
    <el-row :gutter="20" class="visualization-section">
      <el-col :span="12">
        <el-card header="收益率对比">
          <div class="chart-container" ref="returnsChartContainer"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card header="风险指标对比">
          <div class="chart-container" ref="riskChartContainer"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="visualization-section">
      <el-col :span="24">
        <el-card header="资金曲线对比">
          <div class="chart-container large" ref="equityChartContainer"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 详细分析 -->
    <el-card class="detailed-analysis" header="详细分析">
      <el-tabs v-model="activeAnalysisTab">
        <el-tab-pane label="收益分析" name="returns">
          <div class="analysis-content">
            <h4>收益率统计</h4>
            <el-descriptions :column="3" border>
              <el-descriptions-item label="平均收益率">
                {{ formatPercent(analysisData.avgTotalReturn) }}
              </el-descriptions-item>
              <el-descriptions-item label="收益率标准差">
                {{ formatPercent(analysisData.returnStdDev) }}
              </el-descriptions-item>
              <el-descriptions-item label="收益率范围">
                {{ formatPercent(analysisData.minReturn) }} ~ {{ formatPercent(analysisData.maxReturn) }}
              </el-descriptions-item>
            </el-descriptions>
            
            <div class="analysis-insights">
              <h5>分析洞察</h5>
              <ul>
                <li v-for="insight in analysisData.returnInsights" :key="insight">
                  {{ insight }}
                </li>
              </ul>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="风险分析" name="risk">
          <div class="analysis-content">
            <h4>风险指标统计</h4>
            <el-descriptions :column="3" border>
              <el-descriptions-item label="平均最大回撤">
                {{ formatPercent(analysisData.avgMaxDrawdown) }}
              </el-descriptions-item>
              <el-descriptions-item label="平均夏普比率">
                {{ formatNumber(analysisData.avgSharpeRatio, 2) }}
              </el-descriptions-item>
              <el-descriptions-item label="风险调整收益">
                {{ formatNumber(analysisData.riskAdjustedReturn, 2) }}
              </el-descriptions-item>
            </el-descriptions>
            
            <div class="analysis-insights">
              <h5>风险洞察</h5>
              <ul>
                <li v-for="insight in analysisData.riskInsights" :key="insight">
                  {{ insight }}
                </li>
              </ul>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="交易分析" name="trading">
          <div class="analysis-content">
            <h4>交易统计</h4>
            <el-descriptions :column="3" border>
              <el-descriptions-item label="平均交易次数">
                {{ formatNumber(analysisData.avgTradeCount, 0) }}
              </el-descriptions-item>
              <el-descriptions-item label="平均胜率">
                {{ formatPercent(analysisData.avgWinRate) }}
              </el-descriptions-item>
              <el-descriptions-item label="交易频率范围">
                {{ analysisData.minTradeCount }} ~ {{ analysisData.maxTradeCount }} 次
              </el-descriptions-item>
            </el-descriptions>
            
            <div class="analysis-insights">
              <h5>交易洞察</h5>
              <ul>
                <li v-for="insight in analysisData.tradingInsights" :key="insight">
                  {{ insight }}
                </li>
              </ul>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="综合评价" name="overall">
          <div class="analysis-content">
            <h4>综合评分</h4>
            <div class="score-section">
              <div v-for="report in scoredReports" :key="report.reportId" class="score-item">
                <div class="score-header">
                  <span class="report-name">{{ report.title }}</span>
                  <span class="overall-score" :class="getScoreClass(report.overallScore)">
                    {{ report.overallScore.toFixed(1) }}分
                  </span>
                </div>
                <div class="score-breakdown">
                  <div class="score-metric">
                    <span>收益得分:</span>
                    <el-progress :percentage="report.returnScore" :stroke-width="8" />
                  </div>
                  <div class="score-metric">
                    <span>风险得分:</span>
                    <el-progress :percentage="report.riskScore" :stroke-width="8" />
                  </div>
                  <div class="score-metric">
                    <span>稳定性得分:</span>
                    <el-progress :percentage="report.stabilityScore" :stroke-width="8" />
                  </div>
                </div>
              </div>
            </div>
            
            <div class="recommendation">
              <h5>推荐策略</h5>
              <div class="recommended-strategy">
                <el-alert
                  :title="`推荐策略: ${recommendedStrategy.title}`"
                  :description="recommendedStrategy.reason"
                  type="success"
                  show-icon
                />
              </div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 导出功能 -->
    <div class="export-actions">
      <el-button type="primary" @click="exportComparison">
        <el-icon><Download /></el-icon>
        导出对比报告
      </el-button>
      <el-button type="success" @click="generatePDF">
        <el-icon><Document /></el-icon>
        生成PDF报告
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Document } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

// Props
const props = defineProps<{
  reports: any[]
}>()

// 响应式数据
const activeAnalysisTab = ref('returns')
const returnsChartContainer = ref()
const riskChartContainer = ref()
const equityChartContainer = ref()

// 计算属性
const comparisonData = computed(() => {
  return props.reports.map(report => ({
    reportId: report.report_id || report.id,
    title: report.title || `报告${report.report_id}`,
    totalReturn: report.total_return || report.totalReturn || 0,
    annualReturn: report.annual_return || report.annualReturn || 0,
    sharpeRatio: report.sharpe_ratio || report.sharpeRatio || 0,
    maxDrawdown: report.max_drawdown || report.maxDrawdown || 0,
    winRate: report.win_rate || report.winRate || 0,
    tradeCount: report.trades?.length || report.trade_count || 0
  })).sort((a, b) => b.totalReturn - a.totalReturn) // 按总收益率降序排序
})

const bestPerformance = computed(() => {
  if (comparisonData.value.length === 0) {
    return { totalReturn: 0, sharpeRatio: 0 }
  }
  
  const bestReturn = Math.max(...comparisonData.value.map(r => r.totalReturn))
  const bestSharpe = Math.max(...comparisonData.value.map(r => r.sharpeRatio))
  
  return {
    totalReturn: bestReturn,
    sharpeRatio: bestSharpe
  }
})

const analysisData = computed(() => {
  if (comparisonData.value.length === 0) {
    return {
      avgTotalReturn: 0,
      returnStdDev: 0,
      minReturn: 0,
      maxReturn: 0,
      avgMaxDrawdown: 0,
      avgSharpeRatio: 0,
      riskAdjustedReturn: 0,
      avgTradeCount: 0,
      avgWinRate: 0,
      minTradeCount: 0,
      maxTradeCount: 0,
      returnInsights: [],
      riskInsights: [],
      tradingInsights: []
    }
  }
  
  const returns = comparisonData.value.map(r => r.totalReturn)
  const drawdowns = comparisonData.value.map(r => r.maxDrawdown)
  const sharpeRatios = comparisonData.value.map(r => r.sharpeRatio)
  const tradeCounts = comparisonData.value.map(r => r.tradeCount)
  const winRates = comparisonData.value.map(r => r.winRate)
  
  const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length
  const returnStdDev = Math.sqrt(
    returns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / returns.length
  )
  
  // 生成分析洞察
  const returnInsights = []
  if (returnStdDev > 0.1) {
    returnInsights.push('策略收益率差异较大，建议关注风险控制')
  }
  if (avgReturn > 0.15) {
    returnInsights.push('整体收益表现良好，超过市场平均水平')
  }
  
  const riskInsights = []
  const avgDrawdown = drawdowns.reduce((a, b) => a + b, 0) / drawdowns.length
  if (avgDrawdown > 0.2) {
    riskInsights.push('平均回撤较高，需要加强风险管理')
  }
  
  const tradingInsights = []
  const avgTradeCount = tradeCounts.reduce((a, b) => a + b, 0) / tradeCounts.length
  if (avgTradeCount < 10) {
    tradingInsights.push('交易频率较低，可能错过部分机会')
  } else if (avgTradeCount > 100) {
    tradingInsights.push('交易频率较高，需要注意交易成本')
  }
  
  return {
    avgTotalReturn: avgReturn,
    returnStdDev: returnStdDev,
    minReturn: Math.min(...returns),
    maxReturn: Math.max(...returns),
    avgMaxDrawdown: avgDrawdown,
    avgSharpeRatio: sharpeRatios.reduce((a, b) => a + b, 0) / sharpeRatios.length,
    riskAdjustedReturn: avgReturn / (avgDrawdown || 1),
    avgTradeCount: avgTradeCount,
    avgWinRate: winRates.reduce((a, b) => a + b, 0) / winRates.length,
    minTradeCount: Math.min(...tradeCounts),
    maxTradeCount: Math.max(...tradeCounts),
    returnInsights,
    riskInsights,
    tradingInsights
  }
})

const scoredReports = computed(() => {
  return comparisonData.value.map(report => {
    // 计算各项得分 (0-100)
    const returnScore = Math.min(100, Math.max(0, (report.totalReturn + 0.2) * 250))
    const riskScore = Math.min(100, Math.max(0, (0.3 - report.maxDrawdown) * 333))
    const stabilityScore = Math.min(100, Math.max(0, report.sharpeRatio * 50))
    
    // 综合得分
    const overallScore = (returnScore * 0.4 + riskScore * 0.3 + stabilityScore * 0.3)
    
    return {
      ...report,
      returnScore,
      riskScore,
      stabilityScore,
      overallScore
    }
  }).sort((a, b) => b.overallScore - a.overallScore)
})

const recommendedStrategy = computed(() => {
  if (scoredReports.value.length === 0) {
    return { title: '无', reason: '没有可用的策略数据' }
  }
  
  const best = scoredReports.value[0]
  let reason = `综合得分最高 (${best.overallScore.toFixed(1)}分)`
  
  if (best.totalReturn > 0.2) {
    reason += '，收益表现优秀'
  }
  if (best.maxDrawdown < 0.1) {
    reason += '，风险控制良好'
  }
  if (best.sharpeRatio > 1.5) {
    reason += '，风险调整收益突出'
  }
  
  return {
    title: best.title,
    reason: reason
  }
})

// 方法
const initCharts = async () => {
  await nextTick()
  
  // 收益率对比图
  if (returnsChartContainer.value) {
    const returnsChart = echarts.init(returnsChartContainer.value)
    const returnsOption = {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' }
      },
      xAxis: {
        type: 'category',
        data: comparisonData.value.map(r => r.reportId),
        axisLabel: { rotate: 45 }
      },
      yAxis: {
        type: 'value',
        axisLabel: { formatter: '{value}%' }
      },
      series: [
        {
          name: '总收益率',
          type: 'bar',
          data: comparisonData.value.map(r => (r.totalReturn * 100).toFixed(2)),
          itemStyle: {
            color: (params: any) => {
              return params.data > 0 ? '#67C23A' : '#F56C6C'
            }
          }
        }
      ]
    }
    returnsChart.setOption(returnsOption)
  }
  
  // 风险指标对比图
  if (riskChartContainer.value) {
    const riskChart = echarts.init(riskChartContainer.value)
    const riskOption = {
      tooltip: {
        trigger: 'axis'
      },
      legend: {
        data: ['最大回撤', '夏普比率']
      },
      xAxis: {
        type: 'category',
        data: comparisonData.value.map(r => r.reportId),
        axisLabel: { rotate: 45 }
      },
      yAxis: [
        {
          type: 'value',
          name: '最大回撤 (%)',
          axisLabel: { formatter: '{value}%' }
        },
        {
          type: 'value',
          name: '夏普比率',
          axisLabel: { formatter: '{value}' }
        }
      ],
      series: [
        {
          name: '最大回撤',
          type: 'bar',
          yAxisIndex: 0,
          data: comparisonData.value.map(r => (r.maxDrawdown * 100).toFixed(2)),
          itemStyle: { color: '#F56C6C' }
        },
        {
          name: '夏普比率',
          type: 'line',
          yAxisIndex: 1,
          data: comparisonData.value.map(r => r.sharpeRatio.toFixed(2)),
          itemStyle: { color: '#409EFF' }
        }
      ]
    }
    riskChart.setOption(riskOption)
  }
  
  // 资金曲线对比图
  if (equityChartContainer.value && props.reports.length > 0) {
    const equityChart = echarts.init(equityChartContainer.value)
    
    const series = props.reports.map((report, index) => {
      const equityCurve = report.equity_curve || report.equityCurve || []
      return {
        name: report.title || `策略${index + 1}`,
        type: 'line',
        data: equityCurve.map((point: any) => [point.date, point.equity || point.value]),
        smooth: true
      }
    })
    
    const equityOption = {
      tooltip: {
        trigger: 'axis'
      },
      legend: {
        data: series.map(s => s.name)
      },
      xAxis: {
        type: 'time'
      },
      yAxis: {
        type: 'value',
        axisLabel: { formatter: '¥{value}' }
      },
      series: series
    }
    equityChart.setOption(equityOption)
  }
}

const exportComparison = () => {
  try {
    const exportData = {
      comparison_overview: {
        report_count: props.reports.length,
        best_performance: bestPerformance.value,
        analysis_data: analysisData.value
      },
      comparison_table: comparisonData.value,
      scored_reports: scoredReports.value,
      recommendation: recommendedStrategy.value,
      export_time: new Date().toISOString()
    }
    
    const dataStr = JSON.stringify(exportData, null, 2)
    const blob = new Blob([dataStr], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    
    const link = document.createElement('a')
    link.href = url
    link.download = `strategy_comparison_${new Date().toISOString().split('T')[0]}.json`
    link.click()
    
    URL.revokeObjectURL(url)
    ElMessage.success('对比报告导出成功')
    
  } catch (error) {
    ElMessage.error('导出失败')
    console.error('导出对比报告失败:', error)
  }
}

const generatePDF = () => {
  ElMessage.info('PDF生成功能开发中...')
}

// 辅助方法
const getReturnClass = (returnValue: number) => {
  if (returnValue > 0) return 'text-green-600'
  if (returnValue < 0) return 'text-red-600'
  return 'text-gray-600'
}

const getRankTagType = (rank: number) => {
  if (rank === 1) return 'success'
  if (rank === 2) return 'warning'
  if (rank === 3) return 'info'
  return ''
}

const getScoreClass = (score: number) => {
  if (score >= 80) return 'text-green-600'
  if (score >= 60) return 'text-yellow-600'
  return 'text-red-600'
}

const formatPercent = (value: number) => {
  if (value === null || value === undefined) return '-'
  return `${(value * 100).toFixed(2)}%`
}

const formatNumber = (value: number, digits = 2) => {
  if (value === null || value === undefined) return '-'
  return value.toFixed(digits)
}

// 生命周期
onMounted(() => {
  initCharts()
})
</script>

<style scoped lang="postcss">
.report-comparison {
  @apply space-y-6;
}

.comparison-overview,
.metrics-comparison,
.detailed-analysis {
  @apply shadow-sm;
}

.overview-item {
  @apply text-center;
}

.overview-label {
  @apply text-sm text-gray-600 mb-2;
}

.overview-value {
  @apply text-2xl font-bold text-gray-900;
}

.comparison-table {
  @apply w-full;
}

.visualization-section {
  @apply mb-6;
}

.chart-container {
  @apply w-full;
  height: 300px;
}

.chart-container.large {
  height: 400px;
}

.analysis-content {
  @apply space-y-4;
}

.analysis-insights {
  @apply mt-4;
}

.analysis-insights h5 {
  @apply text-lg font-medium text-gray-900 mb-2;
}

.analysis-insights ul {
  @apply list-disc list-inside space-y-1 text-gray-700;
}

.score-section {
  @apply space-y-4;
}

.score-item {
  @apply border border-gray-200 rounded-lg p-4;
}

.score-header {
  @apply flex justify-between items-center mb-3;
}

.report-name {
  @apply font-medium text-gray-900;
}

.overall-score {
  @apply text-xl font-bold;
}

.score-breakdown {
  @apply space-y-2;
}

.score-metric {
  @apply flex items-center gap-3;
}

.score-metric span {
  @apply w-20 text-sm text-gray-600;
}

.recommendation {
  @apply mt-6;
}

.recommendation h5 {
  @apply text-lg font-medium text-gray-900 mb-3;
}

.recommended-strategy {
  @apply max-w-2xl;
}

.export-actions {
  @apply flex gap-4 justify-center pt-6 border-t border-gray-200;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .visualization-section :deep(.el-col) {
    @apply mb-4;
  }
  
  .chart-container {
    height: 250px;
  }
  
  .chart-container.large {
    height: 300px;
  }
  
  .score-header {
    @apply flex-col items-start gap-2;
  }
  
  .export-actions {
    @apply flex-col;
  }
}
</style>