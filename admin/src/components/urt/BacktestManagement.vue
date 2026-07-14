<template>
  <div class="urt-backtest">
    <el-card shadow="never">
      <template #header>
        <div class="flex justify-between items-center">
          <span>创建回测任务</span>
          <el-button size="small" @click="loadTasks">刷新列表</el-button>
        </div>
      </template>
      <el-form :inline="true" label-width="90px">
        <el-form-item label="开始日期">
          <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="目标涨幅">
          <el-input-number v-model="form.target_pct" :min="0.01" :max="1" :step="0.01" :precision="2" />
        </el-form-item>
        <el-form-item label="观察日数">
          <el-input-number v-model="form.horizon_days" :min="1" :max="120" />
        </el-form-item>
        <el-form-item label="最低分">
          <el-input-number v-model="form.min_score" :min="0" :max="100" />
        </el-form-item>
        <el-form-item label="参数版本">
          <el-select v-model="form.strategy_config_id" clearable placeholder="默认" style="width: 160px">
            <el-option v-for="c in configs" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先读缓存">
          <el-switch v-model="form.use_trace" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="creating" @click="createTask">创建并运行</el-button>
          <el-button :loading="precomputing" @click="runPrecompute">手动预计算</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="mt-3" shadow="never" header="任务列表">
      <el-table :data="tasks" v-loading="loading" size="small">
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="progress" label="进度" width="80" />
        <el-table-column prop="message" label="消息" min-width="160" show-overflow-tooltip />
        <el-table-column label="摘要" min-width="220">
          <template #default="{ row }">
            <span v-if="row.summary">
              信号 {{ row.summary.total_signals }} · 命中率 {{ pct(row.summary.hit_rate) }} · 胜率 {{ pct(row.summary.win_rate) }} · 均盈亏 {{ row.summary.avg_pnl_pct }}%
            </span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="refreshOne(row.task_id)">刷新</el-button>
            <el-button link @click="exportCsv(row.task_id)" :disabled="!row.has_details_csv">导出</el-button>
            <el-button link type="warning" @click="cancel(row.task_id)" :disabled="['completed','failed','cancelled'].includes(row.status)">取消</el-button>
            <el-button link type="danger" @click="remove(row.task_id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { urtApiService, type URTStrategyConfig } from '@/services/urtApi'

const form = reactive({
  start_date: '',
  end_date: '',
  target_pct: 0.1,
  horizon_days: 20,
  min_score: 70,
  strategy_config_id: undefined as number | undefined,
  use_trace: true,
})

const configs = ref<URTStrategyConfig[]>([])
const tasks = ref<any[]>([])
const loading = ref(false)
const creating = ref(false)
const precomputing = ref(false)
let timer: number | undefined

function pct(v: any) {
  if (v == null) return '--'
  return `${(Number(v) * 100).toFixed(1)}%`
}

async function loadConfigs() {
  configs.value = await urtApiService.listStrategyConfigs(true)
}

async function loadTasks() {
  loading.value = true
  try {
    tasks.value = await urtApiService.listBacktests(50)
  } catch (e: any) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function createTask() {
  if (!form.start_date || !form.end_date) {
    ElMessage.warning('请填写日期区间')
    return
  }
  creating.value = true
  try {
    await urtApiService.createBacktest({ ...form })
    ElMessage.success('任务已创建')
    await loadTasks()
  } catch (e: any) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    creating.value = false
  }
}

async function runPrecompute() {
  precomputing.value = true
  try {
    await urtApiService.runPrecompute({ config_id: form.strategy_config_id })
    ElMessage.success('预计算已启动（后台）')
  } catch (e: any) {
    ElMessage.error(e.message || '启动失败')
  } finally {
    precomputing.value = false
  }
}

async function refreshOne(id: string) {
  try {
    const row = await urtApiService.getBacktest(id)
    const idx = tasks.value.findIndex((t) => t.task_id === id)
    if (idx >= 0) tasks.value[idx] = row
  } catch (e: any) {
    ElMessage.error(e.message || '刷新失败')
  }
}

async function cancel(id: string) {
  await urtApiService.cancelBacktest(id)
  await loadTasks()
}

async function remove(id: string) {
  await urtApiService.deleteBacktest(id)
  await loadTasks()
}

function exportCsv(id: string) {
  window.open(urtApiService.backtestExportUrl(id), '_blank')
}

onMounted(async () => {
  const end = new Date()
  const start = new Date()
  start.setMonth(start.getMonth() - 3)
  form.end_date = end.toISOString().slice(0, 10)
  form.start_date = start.toISOString().slice(0, 10)
  await loadConfigs()
  await loadTasks()
  timer = window.setInterval(() => {
    if (tasks.value.some((t) => t.status === 'running' || t.status === 'pending')) {
      loadTasks()
    }
  }, 4000)
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<style scoped>
.mt-3 { margin-top: 12px; }
.flex { display: flex; }
.justify-between { justify-content: space-between; }
.items-center { align-items: center; }
</style>
