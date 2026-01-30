<template>
  <div class="report-generator">
    <!-- 报告生成表单 -->
    <el-form 
      ref="reportFormRef" 
      :model="reportForm" 
      :rules="reportRules" 
      label-width="120px"
      class="report-form"
    >
      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="报告名称" prop="name">
            <el-input 
              v-model="reportForm.name" 
              placeholder="请输入报告名称"
              clearable
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="报告类型" prop="type">
            <el-select v-model="reportForm.type" placeholder="选择报告类型" class="w-full">
              <el-option label="单策略分析" value="single" />
              <el-option label="多策略对比" value="comparison" />
              <el-option label="参数优化" value="optimization" />
              <el-option label="风险分析" value="risk" />
              <el-option label="综合评估" value="comprehensive" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="数据来源" prop="dataSource">
            <el-select v-model="reportForm.dataSource" placeholder="选择数据来源" class="w-full">
              <el-option label="历史回测结果" value="backtest" />
              <el-option label="实时交易数据" value="live" />
              <el-option label="模拟交易数据" value="simulation" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="时间范围" prop="timeRange">
            <el-date-picker
              v-model="reportForm.timeRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              class="w-full"
            />
          </el-form-item>
        </el-col>
      </el-row>

      <!-- 策略选择 -->
      <el-form-item v-if="reportForm.type === 'single'" label="选择策略" prop="selectedStrategy">
        <el-select v-model="reportForm.selectedStrategy" placeholder="选择要分析的策略" class="w-full">
          <el-option 
            v-for="strategy in availableStrategies" 
            :key="strategy.id"
            :label="strategy.name"
            :value="strategy.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item v-if="reportForm.type === 'comparison'" label="选择策略" prop="selectedStrategies">
        <el-select 
          v-model="reportForm.selectedStrategies" 
          multiple 
          placeholder="选择要对比的策略（至少2个）" 
          class="w-full"
        >
          <el-option 
            v-for="strategy in availableStrategies" 
            :key="strategy.id"
            :label="strategy.name"
            :value="strategy.id"
          />
        </el-select>
      </el-form-item>

      <!-- 报告内容配置 -->
      <el-form-item label="报告内容">
        <el-checkbox-group v-model="reportForm.includeContent">
          <el-checkbox label="performance">绩效分析</el-checkbox>
          <el-checkbox label="risk">风险分析</el-checkbox>
          <el-checkbox label="trades">交易明细</el-checkbox>
          <el-checkbox label="charts">图表展示</el-checkbox>
          <el-checkbox label="statistics">统计数据</el-checkbox>
          <el-checkbox label="recommendations">投资建议</el-checkbox>
        </el-checkbox-group>
      </el-form-item>

      <!-- 高级选项 -->
      <el-form-item>
        <el-collapse v-model="activeAdvanced">
          <el-collapse-item title="高级选项" name="advanced">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="基准指数">
                  <el-select v-model="reportForm.benchmark" placeholder="选择基准指数">
                    <el-option label="沪深300" value="hs300" />
                    <el-option label="中证500" value="zz500" />
                    <el-option label="创业板指" value="cyb" />
                    <el-option label="上证指数" value="sh" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="风险度量">
                  <el-select v-model="reportForm.riskMeasure" placeholder="选择风险度量方法">
                    <el-option label="VaR (95%)" value="var95" />
                    <el-option label="VaR (99%)" value="var99" />
                    <el-option label="CVaR" value="cvar" />
                    <el-option label="最大回撤" value="maxdd" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="报告格式">
                  <el-checkbox-group v-model="reportForm.outputFormats">
                    <el-checkbox label="html">HTML网页</el-checkbox>
                    <el-checkbox label="pdf">PDF文档</el-checkbox>
                    <el-checkbox label="excel">Excel表格</el-checkbox>
                    <el-checkbox label="json">JSON数据</el-checkbox>
                  </el-checkbox-group>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="图表样式">
                  <el-select v-model="reportForm.chartStyle" placeholder="选择图表样式">
                    <el-option label="专业版" value="professional" />
                    <el-option label="简洁版" value="simple" />
                    <el-option label="彩色版" value="colorful" />
                    <el-option label="黑白版" value="monochrome" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item label="自定义指标">
              <el-input
                v-model="reportForm.customMetrics"
                type="textarea"
                :rows="3"
                placeholder="输入自定义指标计算公式，每行一个，例如：&#10;信息比率 = (策略收益 - 基准收益) / 跟踪误差&#10;卡尔玛比率 = 年化收益率 / 最大回撤"
              />
            </el-form-item>
          </el-collapse-item>
        </el-collapse>
      </el-form-item>

      <!-- 生成预览 -->
      <el-form-item v-if="reportForm.name && reportForm.type" label="报告预览">
        <el-card class="preview-card">
          <div class="preview-content">
            <h4>{{ reportForm.name }}</h4>
            <p class="preview-type">类型: {{ getTypeLabel(reportForm.type) }}</p>
            <p class="preview-period" v-if="reportForm.timeRange && reportForm.timeRange.length === 2">
              时间范围: {{ reportForm.timeRange[0] }} 至 {{ reportForm.timeRange[1] }}
            </p>
            <div class="preview-content-list">
              <span>包含内容: </span>
              <el-tag 
                v-for="content in reportForm.includeContent" 
                :key="content"
                size="small"
                class="content-tag"
              >
                {{ getContentLabel(content) }}
              </el-tag>
            </div>
            <div class="preview-formats" v-if="reportForm.outputFormats.length > 0">
              <span>输出格式: </span>
              <el-tag 
                v-for="format in reportForm.outputFormats" 
                :key="format"
                type="info"
                size="small"
                class="format-tag"
              >
                {{ format.toUpperCase() }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-form-item>

      <!-- 操作按钮 -->
      <el-form-item>
        <el-button 
          type="primary" 
          @click="generateReport" 
          :loading="generating"
          :disabled="!canGenerate"
        >
          <el-icon><DocumentAdd /></el-icon>
          生成报告
        </el-button>
        <el-button @click="resetForm">重置</el-button>
        <el-button @click="saveTemplate">保存模板</el-button>
        <el-button @click="loadTemplate">加载模板</el-button>
      </el-form-item>
    </el-form>

    <!-- 生成进度 -->
    <el-card v-if="generating" class="progress-card">
      <div class="progress-content">
        <h4>正在生成报告...</h4>
        <el-progress 
          :percentage="generationProgress" 
          :stroke-width="12"
          text-inside
        />
        <p class="progress-step">{{ currentStep }}</p>
      </div>
    </el-card>

    <!-- 模板管理对话框 -->
    <el-dialog
      v-model="showTemplateDialog"
      title="报告模板管理"
      width="60%"
    >
      <div class="template-management">
        <div class="template-actions">
          <el-button type="primary" @click="createNewTemplate">
            <el-icon><Plus /></el-icon>
            新建模板
          </el-button>
        </div>
        
        <el-table :data="reportTemplates" stripe class="template-table">
          <el-table-column prop="name" label="模板名称" min-width="150" />
          <el-table-column prop="type" label="类型" width="120">
            <template #default="scope">
              {{ getTypeLabel(scope.row.type) }}
            </template>
          </el-table-column>
          <el-table-column prop="createdAt" label="创建时间" width="160">
            <template #default="scope">
              {{ formatDateTime(scope.row.createdAt) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="scope">
              <el-button size="small" @click="applyTemplate(scope.row)">
                应用
              </el-button>
              <el-button size="small" type="warning" @click="editTemplate(scope.row)">
                编辑
              </el-button>
              <el-button size="small" type="danger" @click="deleteTemplate(scope.row)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  DocumentAdd, 
  Plus 
} from '@element-plus/icons-vue'

// 发射事件
const emit = defineEmits(['report-generated', 'cancel'])

// 响应式数据
const reportFormRef = ref()
const generating = ref(false)
const generationProgress = ref(0)
const currentStep = ref('')
const activeAdvanced = ref([])
const showTemplateDialog = ref(false)

// 表单数据
const reportForm = reactive({
  name: '',
  type: 'single',
  dataSource: 'backtest',
  timeRange: [] as string[],
  selectedStrategy: '',
  selectedStrategies: [],
  includeContent: ['performance', 'risk', 'charts'],
  benchmark: 'hs300',
  riskMeasure: 'var95',
  outputFormats: ['html'],
  chartStyle: 'professional',
  customMetrics: ''
})

// 表单验证规则
const reportRules = {
  name: [
    { required: true, message: '请输入报告名称', trigger: 'blur' }
  ],
  type: [
    { required: true, message: '请选择报告类型', trigger: 'change' }
  ],
  dataSource: [
    { required: true, message: '请选择数据来源', trigger: 'change' }
  ],
  timeRange: [
    { required: true, message: '请选择时间范围', trigger: 'change' }
  ],
  selectedStrategy: [
    { required: true, message: '请选择策略', trigger: 'change' }
  ],
  selectedStrategies: [
    { 
      validator: (_rule: any, value: any, callback: any) => {
        if (reportForm.type === 'comparison' && (!value || value.length < 2)) {
          callback(new Error('对比分析至少需要选择2个策略'))
        } else {
          callback()
        }
      }, 
      trigger: 'change' 
    }
  ]
}

// 可用策略列表
const availableStrategies = ref([
  { id: 'pvfrs_v1', name: 'PVFARS策略 v1.0' },
  { id: 'pvfrs_v2', name: 'PVFARS策略 v2.0' },
  { id: 'pvfrs_optimized', name: 'PVFARS优化版' },
  { id: 'pvfrs_conservative', name: 'PVFARS保守版' },
  { id: 'pvfrs_aggressive', name: 'PVFARS激进版' }
])

// 报告模板
const reportTemplates = ref([
  {
    id: 'template_1',
    name: '标准绩效报告',
    type: 'single',
    config: {},
    createdAt: '2024-01-15T10:30:00'
  },
  {
    id: 'template_2',
    name: '策略对比分析',
    type: 'comparison',
    config: {},
    createdAt: '2024-01-10T14:20:00'
  }
])

// 计算属性
const canGenerate = computed(() => {
  if (!reportForm.name || !reportForm.type || !reportForm.dataSource) {
    return false
  }
  
  if (!reportForm.timeRange || reportForm.timeRange.length !== 2) {
    return false
  }
  
  if (reportForm.type === 'single' && !reportForm.selectedStrategy) {
    return false
  }
  
  if (reportForm.type === 'comparison' && reportForm.selectedStrategies.length < 2) {
    return false
  }
  
  return reportForm.includeContent.length > 0
})

// 方法
const generateReport = async () => {
  try {
    await reportFormRef.value.validate()
    
    generating.value = true
    generationProgress.value = 0
    currentStep.value = '准备生成报告...'
    
    // 模拟报告生成过程
    const steps = [
      { progress: 10, step: '收集数据...' },
      { progress: 30, step: '计算绩效指标...' },
      { progress: 50, step: '生成图表...' },
      { progress: 70, step: '分析风险指标...' },
      { progress: 90, step: '生成报告文档...' },
      { progress: 100, step: '报告生成完成' }
    ]
    
    for (const stepInfo of steps) {
      await new Promise(resolve => setTimeout(resolve, 1000))
      generationProgress.value = stepInfo.progress
      currentStep.value = stepInfo.step
    }
    
    // 创建报告对象
    const report = {
      id: `report_${Date.now()}`,
      name: reportForm.name,
      type: reportForm.type,
      dataSource: reportForm.dataSource,
      timeRange: reportForm.timeRange,
      includeContent: reportForm.includeContent,
      outputFormats: reportForm.outputFormats,
      generatedAt: new Date().toISOString(),
      status: 'completed'
    }
    
    ElMessage.success('报告生成成功')
    emit('report-generated', report)
    
    // 重置表单
    resetForm()
    
  } catch (error) {
    ElMessage.error('报告生成失败')
    console.error('生成报告失败:', error)
  } finally {
    generating.value = false
    generationProgress.value = 0
    currentStep.value = ''
  }
}

const resetForm = () => {
  reportFormRef.value?.resetFields()
  Object.assign(reportForm, {
    name: '',
    type: 'single',
    dataSource: 'backtest',
    timeRange: [],
    selectedStrategy: '',
    selectedStrategies: [],
    includeContent: ['performance', 'risk', 'charts'],
    benchmark: 'hs300',
    riskMeasure: 'var95',
    outputFormats: ['html'],
    chartStyle: 'professional',
    customMetrics: ''
  })
}

const saveTemplate = async () => {
  try {
    if (!reportForm.name || !reportForm.type) {
      ElMessage.warning('请先填写报告名称和类型')
      return
    }
    
    const templateName = await ElMessageBox.prompt('请输入模板名称', '保存模板', {
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputValue: `${reportForm.name}_模板`
    })
    
    const template = {
      id: `template_${Date.now()}`,
      name: templateName.value,
      type: reportForm.type,
      config: { ...reportForm },
      createdAt: new Date().toISOString()
    }
    
    reportTemplates.value.push(template)
    ElMessage.success('模板保存成功')
    
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('保存模板失败')
    }
  }
}

const loadTemplate = () => {
  showTemplateDialog.value = true
}

const createNewTemplate = () => {
  // 创建新模板的逻辑
  ElMessage.info('新建模板功能开发中...')
}

const applyTemplate = (template: any) => {
  try {
    Object.assign(reportForm, template.config)
    showTemplateDialog.value = false
    ElMessage.success('模板应用成功')
  } catch (error) {
    ElMessage.error('应用模板失败')
  }
}

const editTemplate = (_template: any) => {
  ElMessage.info('编辑模板功能开发中...')
}

const deleteTemplate = async (template: any) => {
  try {
    await ElMessageBox.confirm(`确定要删除模板"${template.name}"吗？`, '确认删除', {
      type: 'warning'
    })
    
    const index = reportTemplates.value.findIndex(t => t.id === template.id)
    if (index > -1) {
      reportTemplates.value.splice(index, 1)
      ElMessage.success('模板删除成功')
    }
    
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除模板失败')
    }
    console.error('删除模板失败:', error)
  }
}

// 辅助方法
const getTypeLabel = (type: string): string => {
  const labels: Record<string, string> = {
    single: '单策略分析',
    comparison: '多策略对比',
    optimization: '参数优化',
    risk: '风险分析',
    comprehensive: '综合评估'
  }
  return labels[type as keyof typeof labels] || type
}

const getContentLabel = (content: string): string => {
  const labels: Record<string, string> = {
    performance: '绩效分析',
    risk: '风险分析',
    trades: '交易明细',
    charts: '图表展示',
    statistics: '统计数据',
    recommendations: '投资建议'
  }
  return labels[content as keyof typeof labels] || content
}

const formatDateTime = (dateTime: string) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString()
}

// 生命周期
onMounted(() => {
  // 初始化默认值
  const today = new Date()
  const lastMonth = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000)
  
  reportForm.timeRange = [
    lastMonth.toISOString().split('T')[0],
    today.toISOString().split('T')[0]
  ]
})
</script>

<style scoped lang="postcss">
.report-generator {
  @apply space-y-6;
}

.report-form {
  @apply max-w-none;
}

.preview-card {
  @apply bg-gray-50;
}

.preview-content {
  @apply space-y-2;
}

.preview-content h4 {
  @apply text-lg font-medium text-gray-900;
}

.preview-type,
.preview-period {
  @apply text-sm text-gray-600;
}

.preview-content-list,
.preview-formats {
  @apply flex items-center gap-2 flex-wrap;
}

.content-tag,
.format-tag {
  @apply mr-1 mb-1;
}

.progress-card {
  @apply shadow-sm;
}

.progress-content {
  @apply text-center space-y-4;
}

.progress-content h4 {
  @apply text-lg font-medium text-gray-900;
}

.progress-step {
  @apply text-sm text-gray-600;
}

.template-management {
  @apply space-y-4;
}

.template-actions {
  @apply flex justify-end;
}

.template-table {
  @apply w-full;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .preview-content-list,
  .preview-formats {
    @apply flex-col items-start;
  }
  
  .template-actions {
    @apply justify-center;
  }
  
  :deep(.el-table) {
    font-size: 12px;
  }
  
  :deep(.el-button--small) {
    @apply px-2 py-1 text-xs;
  }
}

/* 动画效果 */
.progress-card {
  animation: slideInDown 0.6s ease-out;
}

@keyframes slideInDown {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>