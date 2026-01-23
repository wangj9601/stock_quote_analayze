<template>
  <div class="report-analysis">
    <!-- 报告概览 -->
    <el-row :gutter="20" class="overview-cards">
      <el-col :span="6">
        <el-card class="overview-card">
          <div class="card-content">
            <div class="card-icon success">
              <el-icon><TrendCharts /></el-icon>
            </div>
            <div class="card-info">
              <div class="card-value">{{ overview.totalReports }}</div>
              <div class="card-label">总报告数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="overview-card">
          <div class="card-content">
            <div class="card-icon info">
              <el-icon><DataAnalysis /></el-icon>
            </div>
            <div class="card-info">
              <div class="card-value">{{ overview.avgReturn }}%</div>
              <div class="card-label">平均收益率</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="overview-card">
          <div class="card-content">
            <div class="card-icon warning">
              <el-icon><Histogram /></el-icon>
            </div>
            <div class="card-info">
              <div class="card-value">{{ overview.winRate }}%</div>
              <div class="card-label">平均胜率</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="overview-card">
          <div class="card-content">
            <div class="card-icon danger">
              <el-icon><Warning /></el-icon>
            </div>
            <div class="card-info">
              <div class="card-value">{{ overview.maxDrawdown }}%</div>
              <div class="card-label">最大回撤</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 报告管理 -->
    <el-card class="report-management-card" header="报告管理">
      <div class="management-header">
        <div class="header-actions">
          <el-button type="primary" @click="generateReport">
            <el-icon><DocumentAdd /></el-icon>
            生成报告
          </el-button>
          <el-button @click="refreshReports" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
          <el-button type="success" @click="compareReports" :disabled="selectedReports.length < 2">
            <el-icon><DataLine /></el-icon>
            对比分析
          </el-button>
          <el-button type="danger" plain @click="deleteAllReports">
            清空报告
          </el-button>
        </div>
        <div class="header-filters">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            @change="handleDateRangeChange"
          />
          <el-select v-model="typeFilter" placeholder="报告类型" clearable>
            <el-option label="全部" value="" />
            <el-option label="单股回测" value="single" />
            <el-option label="批量回测" value="batch" />
            <el-option label="参数优化" value="optimize" />
            <el-option label="组合分析" value="portfolio" />
          </el-select>
        </div>
      </div>

      <!-- 报告列表 -->
      <el-table 
        :data="filteredReports" 
        v-loading="loading"
        @selection-change="handleSelectionChange"
        stripe
        class="report-table"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="id" label="报告ID" width="80" />
        <el-table-column prop="title" label="报告标题" min-width="200" />
        <el-table-column prop="type" label="类型" width="100">
          <template #default="scope">
            <el-tag :type="getTypeTagType(scope.row.type)">
              {{ getTypeLabel(scope.row.type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="totalReturn" label="总收益率" width="120">
          <template #default="scope">
            <span :class="getReturnClass(scope.row.totalReturn)">
              {{ formatPercent(scope.row.totalReturn) }}
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
        <el-table-column prop="createdAt" label="生成时间" width="160">
          <template #default="scope">
            {{ formatDateTime(scope.row.createdAt) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="viewReport(scope.row)">
              查看
            </el-button>
            <el-button size="small" type="success" @click="downloadReport(scope.row)">
              下载
            </el-button>
            <el-button size="small" type="success" plain @click="exportReportPdf(scope.row)">
              PDF
            </el-button>
            <el-button size="small" type="danger" @click="deleteReport(scope.row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="totalReports"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 报告详情对话框 -->
    <el-dialog
      v-model="showReportDetail"
      title="报告详情"
      width="90%"
      :before-close="handleDetailClose"
    >
      <ReportDetail 
        v-if="selectedReport"
        :report="selectedReport"
        @report-updated="handleReportUpdated"
      />
    </el-dialog>

    <!-- 报告对比对话框 -->
    <el-dialog
      v-model="showCompareDialog"
      title="报告对比分析"
      width="95%"
      :before-close="handleCompareClose"
    >
      <ReportComparison 
        v-if="compareReportsData.length > 0"
        :reports="compareReportsData"
      />
    </el-dialog>

    <!-- 生成报告对话框 -->
    <el-dialog
      v-model="showGenerateDialog"
      title="生成报告"
      width="60%"
      :before-close="handleGenerateClose"
    >
      <ReportGenerator 
        @report-generated="handleReportGenerated"
        @cancel="showGenerateDialog = false"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, inject } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  TrendCharts, 
  DataAnalysis, 
  Histogram, 
  Warning,
  DocumentAdd,
  Refresh,
  DataLine
} from '@element-plus/icons-vue'

// 导入子组件
import ReportDetail from './ReportDetail.vue'
import ReportComparison from './ReportComparison.vue'
import ReportGenerator from './ReportGenerator.vue'

// 注入服务
const pvfrsApi = inject('pvfrsApi')

// 响应式数据
const loading = ref(false)
const showReportDetail = ref(false)
const showCompareDialog = ref(false)
const showGenerateDialog = ref(false)
const selectedReport = ref(null)
const selectedReports = ref([])
const compareReportsData = ref([])

// 概览数据
const overview = reactive({
  totalReports: 0,
  avgReturn: 0,
  winRate: 0,
  maxDrawdown: 0
})

// 报告列表
const reports = ref([])
const dateRange = ref([])
const typeFilter = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const totalReports = ref(0)

// 计算属性
const filteredReports = computed(() => {
  let filtered = reports.value

  // 日期范围过滤
  if (dateRange.value && dateRange.value.length === 2) {
    const [startDate, endDate] = dateRange.value
    filtered = filtered.filter(report => {
      const reportDate = report.createdAt.split('T')[0]
      return reportDate >= startDate && reportDate <= endDate
    })
  }

  // 类型过滤
  if (typeFilter.value) {
    filtered = filtered.filter(report => report.type === typeFilter.value)
  }

  return filtered
})

// 发射事件
const emit = defineEmits(['report-generated'])

// 方法
const refreshReports = async () => {
  try {
    loading.value = true
    
    const result = await pvfrsApi.getReports({
      page: currentPage.value,
      pageSize: pageSize.value,
      type: typeFilter.value,
      startDate: dateRange.value?.[0],
      endDate: dateRange.value?.[1]
    })
    
    // 后端返回的数据在 result.data 中，不在 result.reports 中
    reports.value = result.data || result.reports || []
    totalReports.value = result.total || 0
    
    // 更新概览数据
    await refreshOverview()
    
  } catch (error) {
    ElMessage.error('获取报告列表失败')
    console.error('获取报告列表失败:', error)
  } finally {
    loading.value = false
  }
}

const refreshOverview = async () => {
  try {
    const result = await pvfrsApi.getReportOverview()
    // 后端返回的数据在 result.data 中
    if (result.data) {
      overview.totalReports = result.data.totalReports || 0
      overview.avgReturn = result.data.avgReturn || 0
      overview.winRate = result.data.winRate || 0
      overview.maxDrawdown = result.data.maxDrawdown || 0
    } else {
      // 兼容旧格式
      overview.totalReports = result.totalReports || 0
      overview.avgReturn = result.avgReturn || 0
      overview.winRate = result.winRate || 0
      overview.maxDrawdown = result.maxDrawdown || 0
    }
  } catch (error) {
    console.error('获取概览数据失败:', error)
  }
}

const generateReport = () => {
  showGenerateDialog.value = true
}

const viewReport = (report: any) => {
  selectedReport.value = report
  showReportDetail.value = true
}

const downloadReport = async (report: any) => {
  try {
    const blob = await pvfrsApi.downloadReport(report.id)
    
    // 创建下载链接
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    // 后端下载端点返回的是 HTML 报告，不能用 .pdf 否则会提示格式错误
    link.download = `${report.title}_${report.id}.html`
    link.click()
    
    window.URL.revokeObjectURL(url)
    ElMessage.success('报告下载成功')
    
  } catch (error) {
    ElMessage.error('报告下载失败')
    console.error('下载报告失败:', error)
  }
}

const exportReportPdf = async (report: any) => {
  try {
    const blob = await pvfrsApi.downloadReportPdf(report.id)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${report.title}_${report.id}.pdf`
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('PDF导出成功')
  } catch (error) {
    ElMessage.error('PDF导出失败')
    console.error('导出PDF失败:', error)
  }
}

const deleteReport = async (report: any) => {
  try {
    await ElMessageBox.confirm(`确定要删除报告"${report.title}"吗？`, '确认删除', {
      type: 'warning'
    })
    
    await pvfrsApi.deleteReport(report.id)
    ElMessage.success('报告删除成功')
    await refreshReports()
    
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('报告删除失败')
    }
  }
}

const deleteAllReports = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清空全部报告吗？\n该操作会删除所有报告对应的回测结果/交易记录/收益曲线数据，且不可恢复。',
      '危险操作确认',
      { type: 'warning' }
    )
    await pvfrsApi.deleteAllReports()
    ElMessage.success('全部报告已清空')
    await refreshReports()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('清空报告失败')
    }
  }
}

const compareReports = async () => {
  if (selectedReports.value.length < 2) {
    ElMessage.warning('请至少选择两个报告进行对比')
    return
  }
  
  try {
    const reportIds = selectedReports.value.map(report => report.id)
    const result = await pvfrsApi.compareReports(reportIds)
    
    compareReportsData.value = result
    showCompareDialog.value = true
    
  } catch (error) {
    ElMessage.error('报告对比失败')
    console.error('报告对比失败:', error)
  }
}

const handleSelectionChange = (selection: any[]) => {
  selectedReports.value = selection
}

const handleDateRangeChange = () => {
  currentPage.value = 1
  refreshReports()
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  refreshReports()
}

const handleCurrentChange = (page: number) => {
  currentPage.value = page
  refreshReports()
}

const handleReportUpdated = () => {
  refreshReports()
}

const handleReportGenerated = (report: any) => {
  showGenerateDialog.value = false
  emit('report-generated', report)
  refreshReports()
}

const handleDetailClose = () => {
  showReportDetail.value = false
  selectedReport.value = null
}

const handleCompareClose = () => {
  showCompareDialog.value = false
  compareReportsData.value = []
}

const handleGenerateClose = () => {
  showGenerateDialog.value = false
}

// 辅助方法
const getTypeTagType = (type: string) => {
  const types = {
    single: '',
    batch: 'success',
    optimize: 'warning',
    portfolio: 'info'
  }
  return types[type] || ''
}

const getTypeLabel = (type: string) => {
  const labels = {
    single: '单股回测',
    batch: '批量回测',
    optimize: '参数优化',
    portfolio: '组合分析'
  }
  return labels[type] || type
}

const getReturnClass = (returnValue: number) => {
  if (returnValue > 0) return 'text-green-600'
  if (returnValue < 0) return 'text-red-600'
  return 'text-gray-600'
}

const formatPercent = (value: number) => {
  if (value === null || value === undefined) return '-'
  // 后端返回的百分比数据已经乘以100，所以直接使用
  // 如果值小于1，说明是小数形式，需要乘以100；否则已经是百分比形式
  if (Math.abs(value) < 1) {
    return `${(value * 100).toFixed(2)}%`
  } else {
    return `${value.toFixed(2)}%`
  }
}

const formatNumber = (value: number, digits = 2) => {
  if (value === null || value === undefined) return '-'
  return value.toFixed(digits)
}

const formatDateTime = (dateTime: string) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString()
}

// 暴露方法给父组件
defineExpose({
  refresh: refreshReports
})

// 生命周期
onMounted(() => {
  refreshReports()
})
</script>

<style scoped lang="postcss">
.report-analysis {
  @apply space-y-6;
}

.overview-cards {
  @apply mb-6;
}

.overview-card {
  @apply h-full shadow-sm;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.overview-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
}

.card-content {
  @apply flex items-center p-4;
}

.card-icon {
  @apply w-12 h-12 rounded-full flex items-center justify-center mr-4;
  font-size: 24px;
}

.card-icon.success {
  @apply bg-green-100 text-green-600;
}

.card-icon.info {
  @apply bg-blue-100 text-blue-600;
}

.card-icon.warning {
  @apply bg-yellow-100 text-yellow-600;
}

.card-icon.danger {
  @apply bg-red-100 text-red-600;
}

.card-info {
  flex: 1;
}

.card-value {
  @apply text-2xl font-bold text-gray-900 mb-1;
}

.card-label {
  @apply text-sm text-gray-600;
}

.report-management-card {
  @apply shadow-sm;
}

.management-header {
  @apply flex justify-between items-center mb-4;
}

.header-actions {
  @apply flex gap-2;
}

.header-filters {
  @apply flex gap-2;
}

.report-table {
  @apply w-full;
}

.pagination-wrapper {
  @apply flex justify-center mt-6;
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .management-header {
    @apply flex-col gap-4 items-stretch;
  }
  
  .header-actions,
  .header-filters {
    @apply justify-center;
  }
}

@media (max-width: 768px) {
  .overview-cards :deep(.el-col) {
    @apply mb-4;
  }
  
  .card-content {
    @apply p-3;
  }
  
  .card-icon {
    @apply w-10 h-10 mr-3;
    font-size: 20px;
  }
  
  .card-value {
    @apply text-xl;
  }
  
  .header-actions {
    @apply flex-wrap;
  }
  
  .header-filters {
    @apply flex-col gap-2;
  }
  
  :deep(.el-table) {
    font-size: 12px;
  }
  
  :deep(.el-button--small) {
    @apply px-2 py-1 text-xs;
  }
}

@media (max-width: 640px) {
  .overview-cards :deep(.el-col) {
    @apply w-full;
  }
  
  .card-content {
    @apply flex-col text-center p-3;
  }
  
  .card-icon {
    @apply mb-2 mr-0;
  }
}

/* 动画效果 */
.overview-card {
  animation: fadeInUp 0.6s ease-out;
}

.overview-card:nth-child(1) { animation-delay: 0.1s; }
.overview-card:nth-child(2) { animation-delay: 0.2s; }
.overview-card:nth-child(3) { animation-delay: 0.3s; }
.overview-card:nth-child(4) { animation-delay: 0.4s; }

.report-management-card {
  animation: slideInUp 0.6s ease-out 0.3s both;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>