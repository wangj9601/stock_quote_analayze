<template>
  <div class="backtest-management">
    <!-- 任务创建区域 -->
    <el-card class="create-task-card" header="创建回测任务">
      <el-form 
        ref="taskFormRef" 
        :model="taskForm" 
        :rules="taskRules" 
        label-width="120px"
        class="task-form"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="任务名称" prop="name">
              <el-input 
                v-model="taskForm.name" 
                placeholder="请输入任务名称"
                clearable
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="回测模式" prop="mode">
              <el-select v-model="taskForm.mode" placeholder="选择回测模式" class="w-full">
                <el-option label="单股回测" value="single" />
                <el-option label="批量回测" value="batch" />
                <el-option label="参数优化" value="optimize" />
                <el-option label="组合回测" value="portfolio" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="开始日期" prop="startDate">
              <el-date-picker
                v-model="taskForm.startDate"
                type="date"
                placeholder="选择开始日期"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                class="w-full"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期" prop="endDate">
              <el-date-picker
                v-model="taskForm.endDate"
                type="date"
                placeholder="选择结束日期"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                class="w-full"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="初始资金" prop="initialCapital">
              <el-input-number
                v-model="taskForm.initialCapital"
                :min="10000"
                :step="10000"
                placeholder="100000"
                class="w-full"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="市场类型" prop="market">
              <el-select v-model="taskForm.market" placeholder="选择市场" class="w-full">
                <el-option label="A股市场" value="CN" />
                <el-option label="港股市场" value="HK" />
                <el-option label="美股市场" value="US" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 股票选择 -->
        <el-form-item v-if="taskForm.mode === 'single'" label="股票代码" prop="stockCode">
          <el-input 
            v-model="taskForm.stockCode" 
            placeholder="例如：000001"
            clearable
          />
        </el-form-item>

        <el-form-item v-if="taskForm.mode === 'batch'" label="股票列表" prop="stockList">
          <el-input
            v-model="taskForm.stockList"
            type="textarea"
            :rows="5"
            placeholder="请输入股票代码，每行一个"
          />
        </el-form-item>

        <el-form-item v-if="taskForm.mode === 'optimize'" label="优化股票代码" prop="optimizeStockCode">
          <el-input 
            v-model="taskForm.optimizeStockCode" 
            placeholder="例如：000001"
            clearable
          />
        </el-form-item>

        <el-form-item>
          <el-button 
            type="primary" 
            @click="createTask" 
            :loading="creating"
            :disabled="!canCreateTask"
          >
            创建任务
          </el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 任务列表 -->
    <el-card class="task-list-card" header="任务列表">
      <div class="task-list-header">
        <div class="list-actions">
          <el-button @click="refreshTasks" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
          <el-button type="danger" @click="clearCompletedTasks">
            <el-icon><Delete /></el-icon>
            清理已完成
          </el-button>
        </div>
        <div class="list-filters">
          <el-select v-model="statusFilter" placeholder="状态筛选" clearable>
            <el-option label="全部" value="" />
            <el-option label="等待中" value="pending" />
            <el-option label="运行中" value="running" />
            <el-option label="已完成" value="completed" />
            <el-option label="已失败" value="failed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </div>
      </div>

      <el-table 
        :data="filteredTasks" 
        v-loading="loading"
        stripe
        class="task-table"
      >
        <el-table-column prop="id" label="任务ID" width="80" />
        <el-table-column prop="name" label="任务名称" min-width="150" />
        <el-table-column prop="mode" label="模式" width="100">
          <template #default="scope">
            <el-tag :type="getModeTagType(scope.row.mode)">
              {{ getModeLabel(scope.row.mode) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="150">
          <template #default="scope">
            <el-tag :type="getStatusTagType(scope.row.status)">
              {{ getStatusLabel(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="160">
          <template #default="scope">
            {{ formatDateTime(scope.row.createdAt) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="scope">
            <el-button 
              size="small" 
              @click="viewTask(scope.row)"
              :disabled="scope.row.status === 'pending'"
            >
              查看
            </el-button>
            <el-button 
              size="small" 
              type="warning" 
              @click="pauseTask(scope.row)"
              :disabled="!canPauseTask(scope.row.status)"
            >
              暂停
            </el-button>
            <el-button 
              size="small" 
              type="danger" 
              @click="cancelTask(scope.row)"
              :disabled="!canCancelTask(scope.row.status)"
            >
              取消
            </el-button>
            <el-button
              size="small"
              type="danger"
              plain
              @click="deleteTask(scope.row)"
              :disabled="scope.row.status === 'running'"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, inject } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Refresh, 
  Delete
} from '@element-plus/icons-vue'

// 类型定义
interface BacktestTask {
  id: string
  name: string
  mode: string
  status: string
  startDate: string
  endDate: string
  initialCapital: number
  market: string
  stockCode?: string
  stockList?: string[]
  createdAt: string
  updatedAt?: string
}

interface ComparisonConfig {
  name: string
  description: string
  config: any
}

interface PVRFSApi {
  createBacktestTask(taskData: any): Promise<any>
  getBacktestTasks(params: any): Promise<any>
  pauseBacktestTask(taskId: string): Promise<void>
  cancelBacktestTask(taskId: string): Promise<void>
  clearCompletedTasks(): Promise<void>
  deleteBacktestTask(taskId: string): Promise<void>
  deleteAllBacktestTasks(): Promise<void>
}

// 注入服务
const pvfrsApi = inject('pvfrsApi') as PVRFSApi

// 响应式数据
const taskFormRef = ref()
const loading = ref(false)
const creating = ref(false)
const showTaskDetail = ref(false)
const selectedTask = ref<BacktestTask | null>(null)

// 表单数据
const taskForm = reactive({
  name: '',
  mode: 'single',
  startDate: '',
  endDate: '',
  initialCapital: 100000,
  market: 'CN',
  stockCode: '',
  stockList: '',
  optimizeStockCode: '',
  paramGridBuyBiasMin: '0.01,0.02,0.03',
  paramGridSellBiasMax: '0.10,0.15,0.20',
  paramGridStopLoss: '-0.06,-0.08,-0.10',
  paramGridTakeProfit: '0.15,0.20,0.25',
  paramGridMaxHoldingDays: '30,45,60',
  optimizationObjective: ['composite_score'],
  comparisonConfigs: [] as ComparisonConfig[]
})

// 表单验证规则
const taskRules = {
  name: [
    { required: true, message: '请输入任务名称', trigger: 'blur' }
  ],
  mode: [
    { required: true, message: '请选择回测模式', trigger: 'change' }
  ],
  startDate: [
    { required: true, message: '请选择开始日期', trigger: 'change' }
  ],
  endDate: [
    { required: true, message: '请选择结束日期', trigger: 'change' }
  ],
  initialCapital: [
    { required: true, message: '请输入初始资金', trigger: 'blur' }
  ],
  market: [
    { required: true, message: '请选择市场类型', trigger: 'change' }
  ],
  stockCode: [
    { required: true, message: '请输入股票代码', trigger: 'blur' }
  ]
}

// 任务列表
const tasks = ref<BacktestTask[]>([])
const statusFilter = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const totalTasks = ref(0)

// 计算属性
const canCreateTask = computed(() => {
  if (!taskForm.name || !taskForm.startDate || !taskForm.endDate) {
    return false
  }
  
  if (taskForm.mode === 'single' && !taskForm.stockCode) {
    return false
  }
  
  if (taskForm.mode === 'batch' && !taskForm.stockList) {
    return false
  }
  
  if (taskForm.mode === 'optimize' && !taskForm.optimizeStockCode) {
    return false
  }
  
  return true
})

const filteredTasks = computed(() => {
  const taskList = Array.isArray(tasks.value) ? tasks.value : []
  if (!statusFilter.value) {
    return taskList
  }
  return taskList.filter(task => task.status === statusFilter.value)
})

// 方法
const createTask = async () => {
  try {
    await taskFormRef.value.validate()
    
    creating.value = true
    
    const taskData = {
      ...taskForm,
      stockList: taskForm.mode === 'batch' ? taskForm.stockList.split('\n').filter(s => s.trim()) : undefined,
      stockCode: taskForm.mode === 'optimize' ? taskForm.optimizeStockCode : taskForm.stockCode
    }
    
    await pvfrsApi.createBacktestTask(taskData)
    
    ElMessage.success('任务创建成功')
    resetForm()
    await refreshTasks()
    
  } catch (error) {
    ElMessage.error('任务创建失败')
    console.error('创建任务失败:', error)
  } finally {
    creating.value = false
  }
}

const resetForm = () => {
  taskFormRef.value?.resetFields()
  Object.assign(taskForm, {
    name: '',
    mode: 'single',
    startDate: '',
    endDate: '',
    initialCapital: 100000,
    market: 'CN',
    stockCode: '',
    stockList: '',
    optimizeStockCode: '',
    comparisonConfigs: []
  })
}

const refreshTasks = async () => {
  try {
    loading.value = true
    const result = await pvfrsApi.getBacktestTasks({
      page: currentPage.value,
      pageSize: pageSize.value,
      status: statusFilter.value
    })
    
    if (result && typeof result === 'object') {
      const taskData = result.data || result.tasks || []
      tasks.value = Array.isArray(taskData) ? taskData : []
      totalTasks.value = result.total || 0
    } else {
      tasks.value = []
      totalTasks.value = 0
    }
    
  } catch (error) {
    ElMessage.error('获取任务列表失败')
    console.error('获取任务列表失败:', error)
    tasks.value = []
    totalTasks.value = 0
  } finally {
    loading.value = false
  }
}

const viewTask = (task: BacktestTask) => {
  selectedTask.value = task
  showTaskDetail.value = true
}

const pauseTask = async (task: BacktestTask) => {
  try {
    await pvfrsApi.pauseBacktestTask(task.id)
    ElMessage.success('任务已暂停')
    await refreshTasks()
  } catch (error) {
    ElMessage.error('暂停任务失败')
  }
}

const cancelTask = async (task: BacktestTask) => {
  try {
    await ElMessageBox.confirm('确定要取消这个任务吗？', '确认取消', {
      type: 'warning'
    })
    
    await pvfrsApi.cancelBacktestTask(task.id)
    ElMessage.success('任务已取消')
    await refreshTasks()
    
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('取消任务失败')
    }
  }
}

const clearCompletedTasks = async () => {
  try {
    await ElMessageBox.confirm('确定要清理所有已完成的任务吗？', '确认清理', {
      type: 'warning'
    })
    
    await pvfrsApi.clearCompletedTasks()
    ElMessage.success('已完成任务已清理')
    await refreshTasks()
    
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('清理任务失败')
    }
  }
}

const deleteTask = async (task: BacktestTask) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除任务"${task.name}"吗？该操作不可恢复。`,
      '确认删除',
      { type: 'warning' }
    )
    await pvfrsApi.deleteBacktestTask(task.id)
    ElMessage.success('任务已删除')
    await refreshTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除任务失败')
    }
  }
}

// 工具函数 - el-tag type 仅支持以下字面量
type ElTagType = 'info' | 'primary' | 'success' | 'warning' | 'danger'
const getModeTagType = (mode: string): ElTagType => {
  const types: Record<string, ElTagType> = {
    single: 'primary',
    batch: 'success',
    optimize: 'warning',
    portfolio: 'info'
  }
  return (types[mode] || 'info') as ElTagType
}

const getModeLabel = (mode: string): string => {
  const labels: Record<string, string> = {
    single: '单股',
    batch: '批量',
    optimize: '优化',
    portfolio: '组合'
  }
  return labels[mode] || mode
}

const getStatusTagType = (status: string): ElTagType => {
  const types: Record<string, ElTagType> = {
    pending: 'info',
    running: 'primary',
    completed: 'success',
    failed: 'danger',
    cancelled: 'warning'
  }
  return (types[status] || 'info') as ElTagType
}

const getStatusLabel = (status: string): string => {
  const labels: Record<string, string> = {
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '已失败',
    cancelled: '已取消'
  }
  return labels[status] || status
}

const formatDateTime = (dateStr: string): string => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const canPauseTask = (status: string): boolean => {
  return status === 'running'
}

const canCancelTask = (status: string): boolean => {
  return ['pending', 'running'].includes(status)
}

// 生命周期
onMounted(() => {
  refreshTasks()
})
</script>

<style scoped>
.backtest-management {
  padding: 20px;
}

.create-task-card {
  margin-bottom: 20px;
}

.task-form {
  max-width: 800px;
}

.task-list-card {
  margin-bottom: 20px;
}

.task-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.list-actions {
  display: flex;
  gap: 10px;
}

.list-filters {
  display: flex;
  gap: 10px;
}

.task-table {
  margin-top: 20px;
}
</style>
