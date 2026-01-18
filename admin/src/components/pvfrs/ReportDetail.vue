<template>
  <div class="report-detail">
    <div class="loading-container" v-if="loading">
      <el-loading-directive />
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
          
          <!-- 如果有详细内容 -->
          <div class="report-details" v-if="report.details">
            <h3>详细分析</h3>
            <div v-html="report.details"></div>
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
          <div class="report-stocks" v-if="report.stocks && report.stocks.length > 0">
            <h3>推荐股票</h3>
            <el-table :data="report.stocks" style="width: 100%">
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
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const error = ref('')
const report = ref(null)

// 加载报告详情
const loadReport = async () => {
  try {
    loading.value = true
    error.value = ''
    
    const reportId = route.params.id
    // 这里应该调用 API 获取报告详情
    // const response = await api.getReportDetail(reportId)
    // report.value = response.data
    
    // 模拟数据
    report.value = {
      id: reportId,
      title: 'PVFRS策略选股报告',
      type: '选股报告',
      created_at: new Date().toISOString(),
      summary: '<p>本报告基于PVFRS策略分析，筛选出符合条件的优质股票。</p>',
      details: '<p>详细分析内容...</p>',
      charts: [
        { title: '信号强度分布', type: 'bar' },
        { title: '行业分布', type: 'pie' }
      ],
      stocks: [
        {
          symbol: '000001',
          name: '平安银行',
          price: 12.50,
          signal_strength: 0.85,
          reason: '共振强度高，频率优势明显'
        },
        {
          symbol: '000002',
          name: '万科A',
          price: 18.75,
          signal_strength: 0.78,
          reason: '价格维度表现良好'
        }
      ]
    }
    
  } catch (err) {
    console.error('加载报告详情失败:', err)
    error.value = '加载报告详情失败，请稍后重试'
  } finally {
    loading.value = false
  }
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