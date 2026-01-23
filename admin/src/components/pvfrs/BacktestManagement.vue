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
          <div class="stock-input-area">
            <el-tabs v-model="stockInputMode" type="border-card">
              <el-tab-pane label="文件上传" name="upload">
                <el-upload
                  class="upload-demo"
                  drag
                  :auto-upload="false"
                  :on-change="handleStockFileChange"
                  accept=".txt,.csv"
                >
                  <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                  <div class="el-upload__text">
                    将股票列表文件拖到此处，或<em>点击上传</em>
                  </div>
                  <template #tip>
                    <div class="el-upload__tip">
                      支持 txt/csv 文件，每行一个股票代码
                    </div>
                  </template>
                </el-upload>
              </el-tab-pane>
              
              <el-tab-pane label="手动输入" name="manual">
                <el-input
                  v-model="taskForm.stockList"
                  type="textarea"
                  :rows="6"
                  placeholder="请输入股票代码，每行一个，例如：&#10;000001&#10;000002&#10;600519"
                />
              </el-tab-pane>
            </el-tabs>
          </div>
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
          <el-button type="danger" plain @click="deleteAllTasksAndReports">
            <el-icon><Delete /></el-icon>
            删除全部数据
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
            <div class="status-cell">
              <el-tag :type="getStatusTagType(scope.row.status)">
                {{ getStatusLabel(scope.row.status) }}
              </el-tag>
              <el-tooltip 
                v-if="scope.row.status === 'failed' && scope.row.error_message" 
                :content="scope.row.error_message" 
                placement="top" 
                effect="dark"
                :show-after="200"
              >
                <el-icon class="error-icon" style="margin-left: 8px; color: #f56c6c; cursor: pointer;">
                  <Warning />
                </el-icon>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="120">
          <template #default="scope">
            <el-progress 
              :percentage="scope.row.progress || 0" 
              :status="getProgressStatus(scope.row.status)"
              :stroke-width="8"
            />
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="160">
          <template #default="scope">
            {{ formatDateTime(scope.row.createdAt) }}
          </template>
        </el-table-column>
        <el-table-column prop="duration" label="耗时" width="100">
          <template #default="scope">
            {{ formatDuration(scope.row.duration) }}
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

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="totalTasks"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 任务详情对话框 -->
    <el-dialog
      v-model="showTaskDetail"
      title="任务详情"
      width="80%"
      :before-close="handleDetailClose"
    >
      <TaskDetail 
        v-if="selectedTask"
        :task="selectedTask"
        @task-updated="handleTaskUpdated"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, inject } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Refresh, 
  Delete, 
  UploadFilled,
  Warning
} from '@element-plus/icons-vue'
import TaskDetail from './TaskDetail.vue'

// 注入服务
const pvfrsApi = inject('pvfrsApi')
const authStore = inject('authStore')

// 响应式数据
const taskFormRef = ref()
const loading = ref(false)
const creating = ref(false)
const showTaskDetail = ref(false)
const selectedTask = ref(null)
const stockInputMode = ref('manual')

// 表单数据
const taskForm = reactive({
  name: '',
  mode: 'single',
  startDate: '',
  endDate: '',
  initialCapital: 100000,
  market: 'CN',
  stockCode: '',
  stockList: ''
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
const tasks = ref([])
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
  
  return true
})

// 确保表格数据始终是数组
const filteredTasks = computed(() => {
  const taskList = Array.isArray(tasks.value) ? tasks.value : []
  if (!statusFilter.value) {
    return taskList
  }
  return taskList.filter(task => task.status === statusFilter.value)
})

// 发射事件
const emit = defineEmits(['task-created', 'task-updated'])

// 方法
const createTask = async () => {
  try {
    await taskFormRef.value.validate()
    
    creating.value = true
    
    const taskData = {
      ...taskForm,
      stockList: taskForm.mode === 'batch' ? parseStockList(taskForm.stockList) : undefined
    }
    
    const result = await pvfrsApi.createBacktestTask(taskData)
    
    ElMessage.success('任务创建成功')
    emit('task-created', result)
    
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
    stockList: ''
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
    
    // 后端返回的格式是 { success: true, data: [...], total: ... }
    // 确保 data 始终是数组
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
    // 确保即使出错，tasks 也是数组
    tasks.value = []
    totalTasks.value = 0
  } finally {
    loading.value = false
  }
}

const viewTask = (task: any) => {
  selectedTask.value = task
  showTaskDetail.value = true
}

const pauseTask = async (task: any) => {
  try {
    await pvfrsApi.pauseBacktestTask(task.id)
    ElMessage.success('任务已暂停')
    await refreshTasks()
  } catch (error) {
    ElMessage.error('暂停任务失败')
  }
}

const cancelTask = async (task: any) => {
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

const deleteTask = async (task: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除任务“${task.name}”吗？\n该操作会同时删除该任务的所有回测结果/报告/交易记录/收益曲线，且不可恢复。`,
      '确认删除',
      { type: 'warning' }
    )
    await pvfrsApi.deleteBacktestTask(task.id)
    ElMessage.success('任务及关联数据已删除')
    await refreshTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除任务失败')
    }
  }
}

const deleteAllTasksAndReports = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要删除全部任务、报告及所有相关数据吗？\n该操作会清空任务/回测结果/交易记录/收益曲线，且不可恢复。',
      '危险操作确认',
      { type: 'warning' }
    )
    await pvfrsApi.deleteAllBacktestTasks()
    ElMessage.success('全部任务/报告等相关数据已删除')
    await refreshTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除全部数据失败')
    }
  }
}

const handleStockFileChange = async (file: any) => {
  try {
    const text = await readFileContent(file.raw)
    taskForm.stockList = text
    ElMessage.success('文件上传成功')
  } catch (error) {
    ElMessage.error('文件读取失败')
  }
}

const readFileContent = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      if (e.target?.result) {
        resolve(e.target.result as string)
      } else {
        reject(new Error('文件读取失败'))
      }
    }
    reader.onerror = () => reject(new Error('文件读取错误'))
    reader.readAsText(file, 'utf-8')
  })
}

const parseStockList = (text: string): string[] => {
  return text.split('\n')
    .map(line => line.trim())
    .filter(line => line && /^\d{6}$/.test(line))
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  refreshTasks()
}

const handleCurrentChange = (page: number) => {
  currentPage.value = page
  refreshTasks()
}

const handleTaskUpdated = (task: any) => {
  emit('task-updated', task)
  refreshTasks()
}

const handleDetailClose = () => {
  showTaskDetail.value = false
  selectedTask.value = null
}

// 辅助方法
const getModeTagType = (mode: string) => {
  const types = {
    single: '',
    batch: 'success',
    optimize: 'warning',
    portfolio: 'info'
  }
  return types[mode] || ''
}

const getModeLabel = (mode: string) => {
  const labels = {
    single: '单股',
    batch: '批量',
    optimize: '优化',
    portfolio: '组合'
  }
  return labels[mode] || mode
}

const getStatusTagType = (status: string) => {
  const types = {
    pending: 'info',
    running: 'warning',
    completed: 'success',
    failed: 'danger',
    cancelled: 'info'
  }
  return types[status] || ''
}

const getStatusLabel = (status: string) => {
  const labels = {
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '已失败',
    cancelled: '已取消'
  }
  return labels[status] || status
}

const getProgressStatus = (status: string) => {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'exception'
  return ''
}

const canPauseTask = (status: string) => {
  return status === 'running'
}

const canCancelTask = (status: string) => {
  return ['pending', 'running'].includes(status)
}

const formatDateTime = (dateTime: string) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString()
}

const formatDuration = (duration: number) => {
  if (!duration) return '-'
  const minutes = Math.floor(duration / 60)
  const seconds = duration % 60
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

// 暴露方法给父组件
defineExpose({
  refresh: refreshTasks
})

// 生命周期
onMounted(() => {
  refreshTasks()
})
</script>

<style scoped lang="postcss">
.backtest-management {
  @apply space-y-6;
}

.create-task-card {
  @apply shadow-sm;
}

.task-form {
  @apply max-w-none;
}

.stock-input-area {
  @apply w-full;
}

.upload-demo {
  @apply w-full;
}

:deep(.el-upload-dragger) {
  @apply w-full h-32;
}

.task-list-card {
  @apply shadow-sm;
}

.task-list-header {
  @apply flex justify-between items-center mb-4;
}

.list-actions {
  @apply flex gap-2;
}

.list-filters {
  @apply flex gap-2;
}

.task-table {
  @apply w-full;
}

.status-cell {
  @apply flex items-center;
}

.error-icon {
  @apply cursor-pointer;
}

.pagination-wrapper {
  @apply flex justify-center mt-6;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .task-list-header {
    @apply flex-col gap-4 items-stretch;
  }
  
  .list-actions,
  .list-filters {
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
.create-task-card,
.task-list-card {
  animation: slideInUp 0.6s ease-out;
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