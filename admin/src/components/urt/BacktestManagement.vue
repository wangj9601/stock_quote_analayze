<template>
  <div class="urt-backtest">
    <el-card shadow="never" header="创建回测任务">
      <el-form label-width="110px" class="task-form">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="任务名称">
              <el-input v-model="form.task_name" placeholder="可选，默认自动生成" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="参数版本">
              <el-select v-model="form.strategy_config_id" clearable placeholder="默认" class="w-full" filterable>
                <el-option
                  v-for="c in configs"
                  :key="c.id"
                  :label="`${c.name}${c.is_default ? ' (默认)' : ''}`"
                  :value="c.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="开始日期" required>
              <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" class="w-full" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期" required>
              <el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" class="w-full" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="目标涨幅(%)">
              <el-input-number v-model="targetPctPercent" :min="0.1" :max="100" :step="0.5" :precision="2" class="w-full" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="观察日数">
              <el-input-number v-model="form.horizon_days" :min="1" :max="120" class="w-full" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="最低得分">
              <el-input-number v-model="form.min_score" :min="0" :max="100" :step="5" class="w-full" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="股票池">
              <el-select v-model="form.stock_pool_mode" class="w-full" @change="onStockPoolModeChange">
                <el-option label="全市场" value="all" />
                <el-option label="自选股" value="watchlist" />
                <el-option label="行业板块" value="industry_board" />
                <el-option label="概念板块" value="concept_board" />
                <el-option label="单股回测" value="single" />
                <el-option label="自定义列表" value="custom" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先读缓存">
              <el-switch v-model="form.use_trace" />
              <span class="hint">开启后优先使用 urt_signal_trace 预计算信号</span>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="出场模式">
              <el-select v-model="form.exit_mode" class="w-full">
                <el-option label="命中率（不止损）" value="hit_rate" />
                <el-option label="纪律出场（止损/连跌/回撤）" value="risk_exit" />
                <el-option label="结构出场（支撑止损/阻力止盈）" value="structure_exit" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="form.exit_mode !== 'hit_rate'" :span="12">
            <el-form-item label="命中率对照">
              <el-switch v-model="form.compare_hit_rate" />
              <span class="hint">完成后自动再跑一条同配置「命中率（不止损）」</span>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="24">
            <el-form-item label="A股板块">
              <el-radio-group v-model="cnBoardSegment">
                <el-radio label="ALL">全部A股</el-radio>
                <el-radio label="MAIN">主板</el-radio>
                <el-radio label="CYB">创业板</el-radio>
                <el-radio label="SZ_SME">中小板</el-radio>
                <el-radio label="KCB">科创板</el-radio>
                <el-radio label="BJ">北证</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row v-if="form.stock_pool_mode === 'single'" :gutter="16">
          <el-col :span="12">
            <el-form-item label="股票代码" required>
              <el-input v-model="form.stock_code" placeholder="如 000676" clearable />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row v-if="form.stock_pool_mode === 'custom'" :gutter="16">
          <el-col :span="24">
            <el-form-item label="股票列表" required>
              <el-input
                v-model="form.stock_list"
                type="textarea"
                :rows="3"
                placeholder="多个代码用逗号或换行分隔，如 000001,000676"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row v-if="form.stock_pool_mode === 'watchlist'" :gutter="16">
          <el-col :span="12">
            <el-form-item label="自选股范围">
              <el-radio-group v-model="watchlistScope">
                <el-radio label="all">全部用户</el-radio>
                <el-radio label="user">指定用户</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col v-if="watchlistScope === 'user'" :span="12">
            <el-form-item label="用户">
              <el-select v-model="watchlistUserId" filterable clearable placeholder="选择用户" class="w-full">
                <el-option
                  v-for="u in watchlistUsers"
                  :key="u.user_id"
                  :label="`${u.username}（${u.watchlist_count}）`"
                  :value="u.user_id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row v-if="form.stock_pool_mode === 'industry_board'" :gutter="16">
          <el-col :span="24">
            <el-form-item label="行业板块" required>
              <el-select
                v-model="selectedIndustryBoardCodes"
                multiple
                filterable
                remote
                :remote-method="searchIndustryBoards"
                :loading="industryBoardLoading"
                placeholder="搜索并选择行业板块"
                class="w-full"
              >
                <el-option
                  v-for="b in industryBoardOptions"
                  :key="b.board_code"
                  :label="`${b.board_name}（${b.board_code}）`"
                  :value="b.board_code"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row v-if="form.stock_pool_mode === 'concept_board'" :gutter="16">
          <el-col :span="24">
            <el-form-item label="概念板块" required>
              <el-select
                v-model="selectedConceptBoardCodes"
                multiple
                filterable
                remote
                :remote-method="searchConceptBoards"
                :loading="conceptBoardLoading"
                placeholder="搜索并选择概念板块"
                class="w-full"
              >
                <el-option
                  v-for="b in conceptBoardOptions"
                  :key="b.board_code"
                  :label="`${b.board_name}（${b.board_code}）`"
                  :value="b.board_code"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item>
          <el-button type="primary" :loading="creating" @click="createTask">创建并运行</el-button>
          <el-button :loading="precomputing" @click="openPrecomputeDialog">手动预计算</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-dialog v-model="precomputeVisible" title="URT 信号预计算" width="440px">
      <el-form label-width="90px">
        <el-form-item label="交易日" required>
          <el-date-picker
            v-model="precomputeDate"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择交易日"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="市场">
          <el-radio-group v-model="precomputeMarket">
            <el-radio-button label="CN">A股</el-radio-button>
            <el-radio-button label="HK">港股</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="参数版本">
          <span>{{ form.strategy_config_id ? `ID ${form.strategy_config_id}` : '默认/全部启用版本' }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="precomputeVisible = false">取消</el-button>
        <el-button type="primary" :loading="precomputing" @click="runPrecompute">启动</el-button>
      </template>
    </el-dialog>

    <el-card class="mt-3" shadow="never">
      <template #header>
        <div class="list-header">
          <span>任务列表</span>
          <div class="list-actions">
            <el-select v-model="statusFilter" clearable placeholder="状态筛选" style="width: 130px" @change="loadTasks">
              <el-option label="全部" value="" />
              <el-option label="pending" value="pending" />
              <el-option label="running" value="running" />
              <el-option label="completed" value="completed" />
              <el-option label="failed" value="failed" />
              <el-option label="cancelled" value="cancelled" />
            </el-select>
            <el-button size="small" @click="loadTasks">刷新</el-button>
            <el-button size="small" type="danger" plain :disabled="!selectedIds.length" @click="batchDelete">批量删除</el-button>
          </div>
        </div>
      </template>
      <el-table
        :data="tasks"
        v-loading="loading"
        size="small"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="42" />
        <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="progress" label="进度" width="70" />
        <el-table-column label="股票池" width="110">
          <template #default="{ row }">{{ poolModeLabel(row.config?.stock_pool_mode) }}</template>
        </el-table-column>
        <el-table-column label="出场模式" width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ exitModeLabel(resolveExitMode(row)) }}</template>
        </el-table-column>
        <el-table-column label="摘要" min-width="240">
          <template #default="{ row }">
            <span v-if="row.summary">
              信号 {{ row.summary.total_signals ?? 0 }} · 命中率 {{ pct(row.summary.hit_rate) }} · 胜率 {{ pct(row.summary.win_rate) }} · 均盈亏 {{ row.summary.avg_pnl_pct }}%
            </span>
            <span v-else>{{ row.message || '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row.task_id)">详情</el-button>
            <el-button link @click="exportCsv(row.task_id)" :disabled="!row.has_details_csv">导出</el-button>
            <el-button link @click="rerun(row.task_id)" :disabled="['pending','running'].includes(row.status)">重跑</el-button>
            <el-button link type="warning" @click="cancel(row.task_id)" :disabled="['completed','failed','cancelled'].includes(row.status)">取消</el-button>
            <el-button link type="danger" @click="remove(row.task_id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <UrtTaskDetail
      v-model="detailVisible"
      :task-id="selectedTaskId"
      @task-updated="onTaskUpdated"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { urtApiService, type URTStrategyConfig } from '@/services/urtApi'
import { boardConstituentsService, type BoardSummary } from '@/services/boardConstituents.service'
import UrtTaskDetail from './TaskDetail.vue'

const form = reactive({
  task_name: '',
  start_date: '',
  end_date: '',
  target_pct: 0.1,
  horizon_days: 20,
  min_score: 70,
  strategy_config_id: undefined as number | undefined,
  use_trace: true,
  exit_mode: 'hit_rate' as 'hit_rate' | 'risk_exit' | 'structure_exit',
  compare_hit_rate: true,
  stock_pool_mode: 'all',
  stock_code: '',
  stock_list: '',
})

const targetPctPercent = computed({
  get: () => Math.round(form.target_pct * 10000) / 100,
  set: (v: number | undefined) => {
    if (v == null) return
    form.target_pct = Math.min(1, Math.max(0.001, Number(v) / 100))
  },
})

const cnBoardSegment = ref<'ALL' | 'MAIN' | 'CYB' | 'SZ_SME' | 'KCB' | 'BJ'>('ALL')
const watchlistScope = ref<'all' | 'user'>('all')
const watchlistUserId = ref<number | undefined>()
const watchlistUsers = ref<Array<{ user_id: number; username: string; watchlist_count: number }>>([])
const selectedIndustryBoardCodes = ref<string[]>([])
const selectedConceptBoardCodes = ref<string[]>([])
const industryBoardOptions = ref<BoardSummary[]>([])
const conceptBoardOptions = ref<BoardSummary[]>([])
const industryBoardLoading = ref(false)
const conceptBoardLoading = ref(false)

const configs = ref<URTStrategyConfig[]>([])
const tasks = ref<any[]>([])
const loading = ref(false)
const creating = ref(false)
const precomputing = ref(false)
const precomputeVisible = ref(false)
const precomputeDate = ref(new Date().toISOString().slice(0, 10))
const precomputeMarket = ref<'CN' | 'HK'>('CN')
const statusFilter = ref('')
const selectedIds = ref<string[]>([])
const detailVisible = ref(false)
const selectedTaskId = ref('')
let timer: number | undefined

function pct(v: any) {
  if (v == null) return '--'
  return `${(Number(v) * 100).toFixed(1)}%`
}

function poolModeLabel(mode?: string) {
  const map: Record<string, string> = {
    all: '全市场',
    watchlist: '自选股',
    industry_board: '行业板块',
    concept_board: '概念板块',
    single: '单股',
    custom: '自定义',
  }
  return map[mode || 'all'] || mode || '全市场'
}

function resolveExitMode(row: any): string {
  const raw =
    row?.summary?.exit_mode ||
    row?.config?.exit_mode ||
    row?.summary?.risk_params?.exit_mode ||
    row?.config?.risk_params?.exit_mode ||
    row?.summary?.backtest_mode ||
    ''
  const m = String(raw || '').trim().toLowerCase()
  if (m === 'structure_exit') return 'structure_exit'
  if (m === 'risk_exit') return 'risk_exit'
  if (m === 'signal_hit_rate' || m === 'hit_rate') return 'hit_rate'
  // 旧任务：仅有 apply_stop_loss 时推断
  if (row?.summary?.apply_stop_loss === true) return 'risk_exit'
  return 'hit_rate'
}

function exitModeLabel(mode?: string) {
  const map: Record<string, string> = {
    hit_rate: '命中率(不止损)',
    risk_exit: '纪律出场',
    structure_exit: '结构出场',
  }
  const m = String(mode || 'hit_rate').trim().toLowerCase()
  return map[m] || m || '命中率(不止损)'
}

function onStockPoolModeChange() {
  if (form.stock_pool_mode === 'industry_board') void searchIndustryBoards('')
  if (form.stock_pool_mode === 'concept_board') void searchConceptBoards('')
  if (form.stock_pool_mode === 'watchlist') void loadWatchlistUsers()
}

async function searchIndustryBoards(keyword = '') {
  industryBoardLoading.value = true
  try {
    const res = await boardConstituentsService.listBoards({
      boardType: 'industry',
      keyword: keyword.trim() || undefined,
      page: 1,
      pageSize: 80,
    })
    industryBoardOptions.value = res.data || []
  } catch {
    industryBoardOptions.value = []
  } finally {
    industryBoardLoading.value = false
  }
}

async function searchConceptBoards(keyword = '') {
  conceptBoardLoading.value = true
  try {
    const res = await boardConstituentsService.listBoards({
      boardType: 'concept',
      keyword: keyword.trim() || undefined,
      page: 1,
      pageSize: 80,
    })
    conceptBoardOptions.value = res.data || []
  } catch {
    conceptBoardOptions.value = []
  } finally {
    conceptBoardLoading.value = false
  }
}

async function loadWatchlistUsers() {
  try {
    watchlistUsers.value = await urtApiService.getWatchlistUsers()
  } catch {
    watchlistUsers.value = []
  }
}

async function loadConfigs() {
  configs.value = await urtApiService.listStrategyConfigs(true)
}

async function loadTasks() {
  loading.value = true
  try {
    tasks.value = await urtApiService.listBacktests(50, statusFilter.value || undefined)
  } catch (e: any) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function parseCustomPool(text: string): string[] {
  return text
    .split(/[\s,;，；\n\r]+/)
    .map((s) => s.trim())
    .filter(Boolean)
}

async function createTask() {
  if (!form.start_date || !form.end_date) {
    ElMessage.warning('请填写日期区间')
    return
  }
  const mode = form.stock_pool_mode
  if (mode === 'single' && !form.stock_code.trim()) {
    ElMessage.warning('请填写股票代码')
    return
  }
  if (mode === 'custom' && !parseCustomPool(form.stock_list).length) {
    ElMessage.warning('请填写自定义股票列表')
    return
  }
  if (mode === 'watchlist' && watchlistScope.value === 'user' && !watchlistUserId.value) {
    ElMessage.warning('请选择自选股用户')
    return
  }
  if (mode === 'industry_board' && !selectedIndustryBoardCodes.value.length) {
    ElMessage.warning('请选择行业板块')
    return
  }
  if (mode === 'concept_board' && !selectedConceptBoardCodes.value.length) {
    ElMessage.warning('请选择概念板块')
    return
  }

  creating.value = true
  try {
    const body: Record<string, any> = {
      start_date: form.start_date,
      end_date: form.end_date,
      task_name: form.task_name || undefined,
      target_pct: form.target_pct,
      horizon_days: form.horizon_days,
      min_score: form.min_score,
      strategy_config_id: form.strategy_config_id,
      use_trace: form.use_trace,
      exit_mode: form.exit_mode,
      compare_hit_rate: form.exit_mode === 'hit_rate' ? false : form.compare_hit_rate,
      stock_pool_mode: mode,
      cn_board_segment: cnBoardSegment.value === 'ALL' ? undefined : cnBoardSegment.value,
    }
    if (mode === 'single') body.stock_code = form.stock_code.trim()
    if (mode === 'custom') body.stock_pool = parseCustomPool(form.stock_list)
    if (mode === 'watchlist' && watchlistScope.value === 'user') {
      body.watchlist_user_id = watchlistUserId.value
    }
    if (mode === 'industry_board') body.industry_board_codes = selectedIndustryBoardCodes.value
    if (mode === 'concept_board') body.concept_board_codes = selectedConceptBoardCodes.value

    await urtApiService.createBacktest(body)
    ElMessage.success('任务已创建')
    await loadTasks()
  } catch (e: any) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    creating.value = false
  }
}

function openPrecomputeDialog() {
  precomputeDate.value = form.end_date || new Date().toISOString().slice(0, 10)
  precomputeVisible.value = true
}

async function runPrecompute() {
  if (!precomputeDate.value) {
    ElMessage.warning('请选择交易日')
    return
  }
  precomputing.value = true
  try {
    await urtApiService.runPrecompute({
      date: precomputeDate.value,
      config_id: form.strategy_config_id,
      market: precomputeMarket.value,
    })
    ElMessage.success(`预计算已启动（${precomputeMarket.value} / ${precomputeDate.value}）`)
    precomputeVisible.value = false
  } catch (e: any) {
    ElMessage.error(e.message || '启动失败')
  } finally {
    precomputing.value = false
  }
}

function openDetail(id: string) {
  selectedTaskId.value = id
  detailVisible.value = true
}

function onTaskUpdated(task: any) {
  const idx = tasks.value.findIndex((t) => t.task_id === task.task_id)
  if (idx >= 0) tasks.value[idx] = { ...tasks.value[idx], ...task }
}

function exportCsv(id: string) {
  window.open(urtApiService.backtestExportUrl(id), '_blank')
}

async function cancel(id: string) {
  await urtApiService.cancelBacktest(id)
  await loadTasks()
}

async function rerun(id: string) {
  try {
    await urtApiService.rerunBacktest(id)
    ElMessage.success('已重新排队')
    await loadTasks()
  } catch (e: any) {
    ElMessage.error(e.message || '重跑失败')
  }
}

async function remove(id: string) {
  try {
    await ElMessageBox.confirm('确认删除该任务？', '提示', { type: 'warning' })
    await urtApiService.deleteBacktest(id)
    await loadTasks()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

function onSelectionChange(rows: any[]) {
  selectedIds.value = rows.map((r) => r.task_id)
}

async function batchDelete() {
  try {
    await ElMessageBox.confirm(`确认删除选中的 ${selectedIds.value.length} 个任务？`, '提示', { type: 'warning' })
    await urtApiService.batchDeleteBacktests(selectedIds.value)
    ElMessage.success('已删除')
    await loadTasks()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e.message || '批量删除失败')
  }
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
.w-full { width: 100%; }
.hint { margin-left: 8px; color: #6b7280; font-size: 12px; }
.list-header { display: flex; justify-content: space-between; align-items: center; }
.list-actions { display: flex; gap: 8px; align-items: center; }
</style>
