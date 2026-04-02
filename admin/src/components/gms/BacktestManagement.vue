<template>
  <div class="backtest-management">
    <el-card class="create-task-card" header="创建回测任务">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px" class="task-form">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="任务名称" prop="task_name">
              <el-input v-model="form.task_name" placeholder="可选，默认自动生成" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="市场" prop="market">
              <el-select v-model="form.market" placeholder="选择市场" class="w-full">
                <el-option label="A股" value="cn" />
                <el-option label="港股" value="hk" />
                <el-option label="A股+港股" value="all" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="开始日期" prop="start_date">
              <el-date-picker
                v-model="form.start_date"
                type="date"
                placeholder="选择开始日期"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                class="w-full"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期" prop="end_date">
              <el-date-picker
                v-model="form.end_date"
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
            <el-form-item label="目标阈值(%)" prop="target_pct">
              <el-select v-model="form.target_pct" placeholder="信号后20日内最高价达+X%" class="w-full">
                <el-option label="+3%" :value="0.03" />
                <el-option label="+5%" :value="0.05" />
                <el-option label="+10%" :value="0.1" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="持有窗口(日)">
              <el-input-number v-model="form.horizon_days" :min="10" :max="30" class="w-full" />
              <span class="text-gray-500 text-sm ml-1">交易日</span>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="最低总分" prop="min_score">
              <el-input-number v-model="form.min_score" :min="0" :max="100" :step="5" class="w-full" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="股票池">
              <el-select v-model="form.stock_pool_mode" class="w-full" placeholder="选择股票池范围">
                <el-option label="全市场" value="all" />
                <el-option label="自选股" value="watchlist" />
                <el-option label="单股回测" value="single" />
                <el-option label="自定义列表" value="custom" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item v-if="form.stock_pool_mode === 'single'" label="股票代码" prop="stock_code">
          <el-input v-model="form.stock_code" placeholder="如 000001（A股）、00700（港股）" clearable style="max-width: 280px" />
        </el-form-item>
        <el-form-item v-if="form.stock_pool_mode === 'custom'" label="股票列表" prop="stock_list">
          <el-input v-model="form.stock_list" type="textarea" :rows="4" placeholder="每行一个代码，如 000001&#10;600519&#10;00700" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="createTask" :loading="creating">创建任务</el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="task-list-card" header="任务列表">
      <div class="task-list-header">
        <el-button @click="refresh" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-select v-model="statusFilter" placeholder="状态" clearable style="width:120px">
          <el-option label="全部" value="" />
          <el-option label="等待中" value="pending" />
          <el-option label="运行中" value="running" />
          <el-option label="已完成" value="completed" />
          <el-option label="失败" value="failed" />
          <el-option label="已取消" value="cancelled" />
        </el-select>
      </div>
      <el-table :data="filteredTasks" v-loading="loading" stripe>
        <el-table-column prop="task_id" label="任务ID" width="100">
          <template #default="scope">{{ (scope.row.task_id || '').slice(0, 8) }}</template>
        </el-table-column>
        <el-table-column prop="name" label="任务名称" min-width="140" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="scope">
            <el-tag :type="statusTagType(scope.row.status)">{{ scope.row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="80">
          <template #default="scope">{{ scope.row.progress ?? 0 }}%</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="scope">{{ formatDate(scope.row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="viewDetail(scope.row)">详情</el-button>
            <el-button
              size="small"
              type="warning"
              @click="cancelTask(scope.row)"
              :disabled="!['pending','running'].includes(scope.row.status)"
            >
              取消
            </el-button>
            <el-button size="small" type="danger" plain @click="deleteTask(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <TaskDetail v-model="detailVisible" :task-id="selectedTaskId" @closed="selectedTaskId = ''" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, inject } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import TaskDetail from './TaskDetail.vue'

const gmsApi = inject<any>('gmsApi')

const formRef = ref()
const loading = ref(false)
const creating = ref(false)
const detailVisible = ref(false)
const selectedTaskId = ref('')

const form = reactive({
  task_name: '',
  market: 'all',
  start_date: '',
  end_date: '',
  target_pct: 0.05,
  horizon_days: 20,
  min_score: 0,
  stock_pool_mode: 'all',
  stock_code: '',
  stock_list: ''
})

const rules = {
  start_date: [{ required: true, message: '请选择开始日期', trigger: 'change' }],
  end_date: [{ required: true, message: '请选择结束日期', trigger: 'change' }]
}

const tasks = ref<any[]>([])
const statusFilter = ref('')

const filteredTasks = computed(() => {
  if (!statusFilter.value) return tasks.value
  return tasks.value.filter((t: any) => t.status === statusFilter.value)
})

function statusTagType(s: string): 'info' | 'primary' | 'success' | 'warning' | 'danger' {
  const map: Record<string, 'info' | 'primary' | 'success' | 'warning' | 'danger'> = {
    pending: 'info',
    running: 'primary',
    completed: 'success',
    failed: 'danger',
    cancelled: 'info'
  }
  return map[s] || 'info'
}

function formatDate(v: string) {
  if (!v) return '-'
  return v.replace('Z', '').slice(0, 19)
}

async function createTask() {
  await formRef.value?.validate()
  if (form.stock_pool_mode === 'single' && !form.stock_code?.trim()) {
    ElMessage.warning('请填写单股回测的股票代码')
    return
  }
  if (form.stock_pool_mode === 'custom' && !form.stock_list?.trim()) {
    ElMessage.warning('请填写自定义股票列表（每行一个代码）')
    return
  }
  creating.value = true
  try {
    const body: any = {
      task_name: form.task_name || undefined,
      market: form.market,
      start_date: form.start_date,
      end_date: form.end_date,
      target_pct: form.target_pct,
      horizon_days: form.horizon_days,
      min_score: form.min_score,
      stock_pool_mode: form.stock_pool_mode
    }
    if (form.stock_pool_mode === 'single') body.stock_code = form.stock_code.trim()
    if (form.stock_pool_mode === 'custom') {
      body.stock_pool = form.stock_list.split(/\n/).map((s: string) => s.trim()).filter(Boolean)
    }
    const taskId = await gmsApi.createBacktest(body)
    ElMessage.success('任务已创建: ' + taskId.slice(0, 8))
    resetForm()
    await refresh()
    emit('task-created', { id: taskId })
  } catch (e: any) {
    ElMessage.error(e?.message || '创建失败')
  } finally {
    creating.value = false
  }
}

function resetForm() {
  form.task_name = ''
  form.market = 'all'
  form.start_date = ''
  form.end_date = ''
  form.target_pct = 0.05
  form.horizon_days = 20
  form.min_score = 0
  form.stock_pool_mode = 'all'
  form.stock_code = ''
  form.stock_list = ''
}

async function refresh() {
  loading.value = true
  try {
    const list = await gmsApi.getBacktestTasks({ status: statusFilter.value || undefined, limit: 100 })
    tasks.value = Array.isArray(list) ? list : []
  } catch (e) {
    ElMessage.error('获取任务列表失败')
    tasks.value = []
  } finally {
    loading.value = false
  }
}

function viewDetail(row: any) {
  selectedTaskId.value = row.task_id
  detailVisible.value = true
}

async function cancelTask(row: any) {
  try {
    await ElMessageBox.confirm('确定取消该任务？', '确认', { type: 'warning' })
    await gmsApi.cancelBacktestTask(row.task_id)
    ElMessage.success('已取消')
    await refresh()
    emit('task-updated', row)
  } catch (e) {
    if ((e as string) !== 'cancel') ElMessage.error('取消失败')
  }
}

async function deleteTask(row: any) {
  try {
    await ElMessageBox.confirm('确定删除该任务及报告？', '确认', { type: 'warning' })
    await gmsApi.deleteBacktestTask(row.task_id)
    ElMessage.success('已删除')
    await refresh()
  } catch (e) {
    if ((e as string) !== 'cancel') ElMessage.error('删除失败')
  }
}

const emit = defineEmits<{ (e: 'task-created', task: any): void; (e: 'task-updated', task: any): void }>()
defineExpose({ refresh })

onMounted(() => refresh())
</script>

<style scoped>
.task-list-header { display: flex; gap: 12px; margin-bottom: 12px; }
.w-full { width: 100%; }
</style>
