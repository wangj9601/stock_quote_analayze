<template>
  <div class="report-detail">
    
    <div class="loading-container" v-if="loading" style="min-height: 400px; display: flex; align-items: center; justify-content: center;">
      <el-loading 
        :loading="loading"
        text="加载中..."
      />
      <div style="margin-left: 20px;">
        <span>正在加载报告详情，请稍候...</span>
      </div>
    </div>
    
    <div v-else-if="error" class="error-container">
      <el-result
        icon="error"
        title="加载失败"
        :sub-title="error"
      >
        <template #extra>
          <el-button type="primary" @click="loadReport">重新加载</el-button>
        </template>
      </el-result>
    </div>
    
    <div v-else-if="report" class="report-content">
      <!-- 调试信息（开发环境） -->
      <div v-if="false" style="background: #f0f0f0; padding: 10px; margin-bottom: 20px; font-size: 12px;">
        <strong>调试信息:</strong>
        <pre>{{ JSON.stringify(report, null, 2) }}</pre>
      </div>
      <!-- 报告头部 -->
      <div class="report-header">
        <el-page-header @back="goBack" :title="report.title">
          <template #content>
            <div class="header-content">
              <h1>{{ report.title }}</h1>
              <div class="report-meta">
                <el-tag type="primary">{{ report.type }}</el-tag>
                <span class="date">{{ formatDate(report.created_at) }}</span>
              </div>
            </div>
          </template>
        </el-page-header>
      </div>
      
      <!-- 报告主体 -->
      <div class="report-body">
        <el-card class="report-card">
          <div class="report-summary" v-html="report.summary"></div>
          
          <!-- 详细内容 -->
          <div class="report-details" v-if="report.details">
            <h3>详细分析</h3>
            <div v-html="report.details"></div>
          </div>
          <div v-else class="report-details-empty">
            <el-empty description="暂无详细分析数据" :image-size="100" />
          </div>
          
          <!-- 如果有图表数据 -->
          <div class="report-charts" v-if="report.charts && report.charts.length > 0">
            <h3>数据图表</h3>
            <div class="charts-grid">
              <div 
                v-for="(chart, index) in report.charts" 
                :key="index"
                class="chart-item"
              >
                <el-card>
                  <h4>{{ chart.title }}</h4>
                  <div class="chart-container">
                    <!-- 这里可以根据图表类型渲染不同的图表组件 -->
                    <div class="chart-placeholder">
                      图表: {{ chart.type }}
                    </div>
                  </div>
                </el-card>
              </div>
            </div>
          </div>
          
          <!-- 如果有推荐股票 -->
          <div class="report-stocks" v-if="reportStocks && reportStocks.length > 0">
            <h3>推荐股票</h3>
            <el-table :data="reportStocks" style="width: 100%">
              <el-table-column prop="symbol" label="股票代码" width="120" />
              <el-table-column prop="name" label="股票名称" width="150" />
              <el-table-column prop="price" label="当前价格" width="120">
                <template #default="scope">
                  ¥{{ scope.row.price?.toFixed(2) }}
                </template>
              </el-table-column>
              <el-table-column prop="signal_strength" label="信号强度" width="120">
                <template #default="scope">
                  <el-tag 
                    :type="getSignalType(scope.row.signal_strength)"
                    size="small"
                  >
                    {{ (scope.row.signal_strength * 100).toFixed(1) }}%
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="reason" label="推荐理由" />
            </el-table>
          </div>

          <!-- 如果有交易记录 -->
          <div class="report-trades" v-if="reportTrades && reportTrades.length > 0">
            <h3>详细交易记录</h3>
            <el-table :data="reportTrades" style="width: 100%" stripe border>
              <el-table-column prop="stock_code" label="股票代码" width="100" sortable />
              <el-table-column prop="entry_date" label="买入日期" width="110" sortable />
              <el-table-column prop="entry_price" label="买入价格" width="100">
                <template #default="scope">
                  ¥{{ Number(scope.row.entry_price).toFixed(2) }}
                </template>
              </el-table-column>
              <el-table-column prop="exit_time" label="卖出日期" width="110">
                <template #default="scope">
                  {{ scope.row.exit_time ? formatDateOnly(scope.row.exit_time) : '持仓中' }}
                </template>
              </el-table-column>
              <el-table-column prop="exit_price" label="卖出价格" width="100">
                <template #default="scope">
                  {{ scope.row.exit_price ? '¥' + Number(scope.row.exit_price).toFixed(2) : '-' }}
                </template>
              </el-table-column>
              <el-table-column prop="quantity" label="数量" width="80" />
              <el-table-column prop="pnl" label="盈亏" width="110">
                <template #default="scope">
                  <span :class="scope.row.pnl >= 0 ? 'text-green-600' : 'text-red-600'">
                    ¥{{ Number(scope.row.pnl).toFixed(2) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="pnl_percent" label="盈亏比" width="100">
                <template #default="scope">
                  <span :class="scope.row.pnl_percent >= 0 ? 'text-green-600' : 'text-red-600'">
                    {{ (Number(scope.row.pnl_percent) * 100).toFixed(2) }}%
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="holding_period" label="持有(天)" width="90" />
              <el-table-column prop="exit_reason" label="退出原因" min-width="120" />
            </el-table>
          </div>
        </el-card>
      </div>
    </div>
    
    <!-- 如果没有报告数据且没有错误，显示提示 -->
    <div v-else class="error-container">
      <el-result
        icon="warning"
        title="暂无数据"
        sub-title="报告数据为空，请检查报告ID是否正确或报告是否已生成"
      >
        <template #extra>
          <el-button type="primary" @click="loadReport">重新加载</el-button>
        </template>
      </el-result>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, inject } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { API_BASE } from '@/config/api'

const route = useRoute()
const router = useRouter()

// 注入服务
const pvfrsApi = inject('pvfrsApi')

// 获取认证头部的辅助函数
const getAuthHeaders = () => {
  const token = localStorage.getItem('admin_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

const loading = ref(true)
const error = ref('')
const report = ref(null)

// 确保 stocks 始终是数组
const reportStocks = computed(() => {
  if (!report.value || !report.value.stocks) return []
  return Array.isArray(report.value.stocks) ? report.value.stocks : []
})

// 确保 trades 始终是数组
const reportTrades = computed(() => {
  if (!report.value || !report.value.trades) return []
  return Array.isArray(report.value.trades) ? report.value.trades : []
})

// 加载报告详情
const loadReport = async () => {
  try {
    loading.value = true
    error.value = ''
    
    const reportId = route.params.id
    console.log('开始加载报告详情，reportId:', reportId)
    
    // 尝试通过报告ID获取报告详情
    let reportData = null
    let lastError = null
    
    // 方法1: 尝试通过任务ID获取报告（report_id 可能就是 task_id）
    try {
      console.log('尝试方法1: 通过任务ID获取报告')
      const response = await fetch(`${API_BASE}/api/admin/pvfrs/backtest/report/${reportId}`, {
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        }
      })
      
      console.log('方法1响应状态:', response.status, response.statusText)
      
      if (response.ok) {
        const data = await response.json()
        console.log('方法1返回数据:', data)
        // 格式化器可能返回不同的结构
        if (data.data) {
          reportData = data.data
        } else if (data.report_id || data.total_return !== undefined) {
          reportData = data
        } else {
          // 可能是格式化后的数据，直接使用
          reportData = data
        }
      } else {
        const errorText = await response.text()
        console.warn('方法1失败:', response.status, errorText)
        lastError = `HTTP ${response.status}: ${errorText}`
      }
    } catch (e) {
      console.warn('方法1异常:', e)
      lastError = e.message
    }
    
    // 方法2: 如果方法1失败，尝试直接获取报告详情
    if (!reportData) {
      try {
        console.log('尝试方法2: 直接获取报告详情')
        const response = await fetch(`${API_BASE}/api/admin/pvfrs/reports/${reportId}`, {
          headers: {
            'Content-Type': 'application/json',
            ...getAuthHeaders()
          }
        })
        
        console.log('方法2响应状态:', response.status, response.statusText)
        
        if (response.ok) {
          const data = await response.json()
          console.log('方法2返回数据:', data)
          if (data.success && data.data) {
            reportData = data.data
          } else if (data.report_id || data.total_return !== undefined) {
            reportData = data
          }
        } else {
          const errorText = await response.text()
          console.warn('方法2失败:', response.status, errorText)
          lastError = `HTTP ${response.status}: ${errorText}`
        }
      } catch (e) {
        console.warn('方法2异常:', e)
        lastError = e.message
      }
    }
    
    // 方法3: 尝试使用 pvfrsApi.getReport
    if (!reportData && pvfrsApi && pvfrsApi.getReport) {
      try {
        console.log('尝试方法3: 使用 pvfrsApi.getReport')
        const response = await pvfrsApi.getReport(reportId)
        console.log('方法3返回数据:', response)
        reportData = response.data || response
      } catch (e) {
        console.warn('方法3异常:', e)
        lastError = e.message
      }
    }
    
    if (reportData) {
      console.log('成功获取报告数据，开始转换:', reportData)
      console.log('报告数据完整结构:', JSON.stringify(reportData, null, 2))
      
      // 检查数据是否在嵌套结构中
      let actualData = reportData
      if (reportData.data) {
        actualData = reportData.data
        console.log('数据在 data 字段中:', actualData)
      }
      
      // 提取 comprehensive_data（如果存在）
      const comprehensiveData = actualData.comprehensive_data || actualData.comprehensiveData
      if (comprehensiveData) {
        console.log('找到 comprehensive_data:', comprehensiveData)
        // 合并 comprehensive_data 中的数据到 actualData
        actualData = {
          ...actualData,
          ...comprehensiveData,
          // 保留原始字段
          report_id: actualData.report_id || actualData.id,
          task_id: actualData.task_id,
          config: actualData.config,
          created_at: actualData.created_at || comprehensiveData.report_metadata?.generated_at
        }
      }
      
      // 转换报告数据格式以匹配前端组件期望的格式
      report.value = {
        id: actualData.report_id || actualData.id || reportId,
        title: actualData.title || `PVFRS策略回测报告 - ${actualData.report_id || reportId}`,
        type: actualData.type || actualData.report_type || '回测报告',
        created_at: actualData.created_at || actualData.createdAt || new Date().toISOString(),
        summary: actualData.summary || generateSummaryFromReport(actualData),
        details: actualData.details || generateDetailsFromReport(actualData),
        charts: actualData.charts || actualData.visualization_data || [],
        stocks: actualData.stocks || actualData.stock_list || [],
        trades: actualData.trades || [],
        // 保留原始数据以便调试
        _rawData: actualData
      }
      
      console.log('报告数据转换完成:', report.value)
      console.log('摘要内容:', report.value.summary)
      console.log('详细信息内容:', report.value.details)
      console.log('是否有图表:', report.value.charts?.length || 0)
      console.log('是否有股票:', report.value.stocks?.length || 0)
    } else {
      const errorMsg = lastError || '无法获取报告数据，所有方法都失败了'
      console.error('获取报告数据失败:', errorMsg)
      error.value = `加载报告详情失败: ${errorMsg}`
    }
    
  } catch (err) {
    console.error('加载报告详情异常:', err)
    error.value = `加载报告详情失败: ${err.message || '请稍后重试'}`
  } finally {
    loading.value = false
    console.log('加载完成，loading:', loading.value, 'error:', error.value, 'report:', report.value ? '有数据' : '无数据')
  }
}

// 从报告数据生成摘要
const generateSummaryFromReport = (reportData) => {
  const metrics = []
  
  // 尝试多种可能的字段名
  const totalReturn = reportData.total_return ?? reportData.totalReturn ?? reportData.performance_metrics?.total_return
  const annualReturn = reportData.annual_return ?? reportData.annualReturn ?? reportData.performance_metrics?.annual_return
  const maxDrawdown = reportData.max_drawdown ?? reportData.maxDrawdown ?? reportData.risk_metrics?.max_drawdown
  const sharpeRatio = reportData.sharpe_ratio ?? reportData.sharpeRatio ?? reportData.performance_metrics?.sharpe_ratio
  const winRate = reportData.win_rate ?? reportData.winRate ?? reportData.trade_analysis?.win_rate
  
  if (totalReturn !== undefined && totalReturn !== null) {
    const color = totalReturn >= 0 ? '#10b981' : '#ef4444'
    metrics.push(`<span style="color: ${color}; font-weight: 600;">总收益率: ${(totalReturn * 100).toFixed(2)}%</span>`)
  }
  if (annualReturn !== undefined && annualReturn !== null) {
    const color = annualReturn >= 0 ? '#10b981' : '#ef4444'
    metrics.push(`<span style="color: ${color}; font-weight: 600;">年化收益率: ${(annualReturn * 100).toFixed(2)}%</span>`)
  }
  if (maxDrawdown !== undefined && maxDrawdown !== null) {
    metrics.push(`<span style="color: #ef4444; font-weight: 600;">最大回撤: ${(maxDrawdown * 100).toFixed(2)}%</span>`)
  }
  if (sharpeRatio !== undefined && sharpeRatio !== null) {
    metrics.push(`夏普比率: ${sharpeRatio.toFixed(2)}`)
  }
  if (winRate !== undefined && winRate !== null) {
    metrics.push(`胜率: ${(winRate * 100).toFixed(2)}%`)
  }
  
  // 获取回测期间
  let periodInfo = ''
  if (reportData.config) {
    periodInfo = `<p><strong>回测期间:</strong> ${reportData.config.start_date || ''} 至 ${reportData.config.end_date || ''}</p>`
  } else if (reportData.report_metadata?.period) {
    const period = reportData.report_metadata.period
    periodInfo = `<p><strong>回测期间:</strong> ${period.start_date || ''} 至 ${period.end_date || ''}</p>`
  }
  
  return `<div class="report-summary-content">
    <p>本报告基于PVFRS策略回测分析。</p>
    ${metrics.length > 0 ? `<div class="metrics-grid"><p><strong>核心指标:</strong></p><p>${metrics.join(' | ')}</p></div>` : ''}
    ${periodInfo}
  </div>`
}

// 从报告数据生成详细信息
const generateDetailsFromReport = (reportData) => {
  let details = '<div class="report-details-content">'
  
  // 交易分析
  const trades = reportData.trades || reportData.trade_analysis?.trades || []
  if (trades && Array.isArray(trades) && trades.length > 0) {
    details += `<div class="detail-section"><h4>交易记录</h4>`
    details += `<p>总交易次数: <strong>${trades.length}</strong></p>`
    
    const winningTrades = trades.filter(t => (t.pnl ?? t.profit) > 0).length
    const losingTrades = trades.filter(t => (t.pnl ?? t.profit) < 0).length
    details += `<p>盈利交易: <strong style="color: #10b981;">${winningTrades}</strong> | 亏损交易: <strong style="color: #ef4444;">${losingTrades}</strong></p>`
    
    if (reportData.trade_analysis) {
      const ta = reportData.trade_analysis
      if (ta.avg_profit !== undefined) details += `<p>平均盈利: ${(ta.avg_profit).toFixed(2)} 元</p>`
      if (ta.avg_loss !== undefined) details += `<p>平均亏损: ${(ta.avg_loss).toFixed(2)} 元</p>`
    }
    details += `</div>`
  } else if (reportData.trade_analysis) {
    const ta = reportData.trade_analysis
    details += `<div class="detail-section"><h4>交易分析</h4>`
    if (ta.total_trades !== undefined) details += `<p>总交易次数: <strong>${ta.total_trades}</strong></p>`
    if (ta.winning_trades !== undefined) details += `<p>盈利交易: <strong style="color: #10b981;">${ta.winning_trades}</strong></p>`
    if (ta.losing_trades !== undefined) details += `<p>亏损交易: <strong style="color: #ef4444;">${ta.losing_trades}</strong></p>`
    if (ta.avg_profit !== undefined) details += `<p>平均盈利: ${(ta.avg_profit).toFixed(2)} 元</p>`
    if (ta.avg_loss !== undefined) details += `<p>平均亏损: ${(ta.avg_loss).toFixed(2)} 元</p>`
    details += `</div>`
  }
  
  // 配置信息
  if (reportData.config || reportData.report_metadata) {
    details += `<div class="detail-section"><h4>配置信息</h4>`
    const config = reportData.config || {}
    const metadata = reportData.report_metadata || {}
    
    const initialCapital = config.initial_capital ?? metadata.initial_capital
    if (initialCapital) {
      details += `<p>初始资金: <strong>${Number(initialCapital).toLocaleString('zh-CN')} 元</strong></p>`
    }
    
    const stockPool = config.stock_pool || []
    if (stockPool && stockPool.length > 0) {
      details += `<p>股票池: <strong>${stockPool.length} 只股票</strong> (${stockPool.slice(0, 5).join(', ')}${stockPool.length > 5 ? '...' : ''})</p>`
    }
    
    if (metadata.final_capital) {
      details += `<p>最终资金: <strong>${Number(metadata.final_capital).toLocaleString('zh-CN')} 元</strong></p>`
    }
    details += `</div>`
  }
  
  // 风险指标
  if (reportData.risk_metrics) {
    const rm = reportData.risk_metrics
    details += `<div class="detail-section"><h4>风险指标</h4>`
    if (rm.max_drawdown !== undefined) details += `<p>最大回撤: <strong style="color: #ef4444;">${(rm.max_drawdown * 100).toFixed(2)}%</strong></p>`
    if (rm.volatility !== undefined) details += `<p>波动率: ${(rm.volatility * 100).toFixed(2)}%</p>`
    if (rm.calmar_ratio !== undefined) details += `<p>卡玛比率: ${rm.calmar_ratio.toFixed(2)}</p>`
    details += `</div>`
  }
  
  details += '</div>'
  return details || '<div class="report-details-content"><p>暂无详细分析数据</p></div>'
}

// 返回上一页
const goBack = () => {
  router.go(-1)
}

// 格式化日期
const formatDate = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 格式化日期（仅日期部分）
const formatDateOnly = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  })
}

// 获取信号强度类型
const getSignalType = (strength) => {
  if (strength >= 0.8) return 'success'
  if (strength >= 0.6) return 'warning'
  return 'info'
}

onMounted(() => {
  loadReport()
})
</script>

<style scoped>
.report-detail {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.loading-container,
.error-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}

.report-header {
  margin-bottom: 20px;
}

.header-content h1 {
  margin: 0 0 10px 0;
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
}

.report-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}

.date {
  color: #6b7280;
  font-size: 14px;
}

.report-card {
  margin-bottom: 20px;
}

.report-summary {
  margin-bottom: 24px;
  line-height: 1.6;
}

.report-summary-content {
  padding: 16px 0;
}

.metrics-grid {
  margin: 16px 0;
  padding: 12px;
  background-color: #f9fafb;
  border-radius: 6px;
  border-left: 3px solid #3b82f6;
}

.metrics-grid p {
  margin: 8px 0;
  line-height: 1.8;
}

.report-details-content {
  padding: 16px 0;
}

.detail-section {
  margin-bottom: 24px;
  padding: 16px;
  background-color: #ffffff;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
}

.detail-section h4 {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  padding-bottom: 8px;
  border-bottom: 2px solid #3b82f6;
}

.detail-section p {
  margin: 8px 0;
  line-height: 1.6;
  color: #374151;
}

.report-details,
.report-charts,
.report-stocks {
  margin-top: 32px;
}

.report-details h3,
.report-charts h3,
.report-stocks h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid #e5e7eb;
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 20px;
  margin-top: 16px;
}

.chart-item h4 {
  font-size: 16px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 12px;
}

.chart-container {
  height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f9fafb;
  border-radius: 8px;
  border: 1px dashed #d1d5db;
}

.chart-placeholder {
  color: #6b7280;
  font-size: 14px;
}

@media (max-width: 768px) {
  .report-detail {
    padding: 16px;
  }
  
  .charts-grid {
    grid-template-columns: 1fr;
  }
  
  .report-meta {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
}
</style>