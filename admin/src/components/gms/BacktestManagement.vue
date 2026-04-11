<template>
  <div class="backtest-management">
    <el-card class="create-task-card" header="创建回测任务">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px" class="task-form">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="任务名称" prop="task_name">
              <el-input v-model="form.task_name" placeholder="可选，默认自动生成" clearable @keyup.enter="createTask" />
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
              <div class="target-pct-row">
                <el-select
                  v-model="targetPctQuick"
                  placeholder="快捷"
                  clearable
                  class="target-pct-quick"
                  @change="applyTargetPctQuick"
                >
                  <el-option label="+3%" :value="3" />
                  <el-option label="+5%" :value="5" />
                  <el-option label="+10%" :value="10" />
                </el-select>
                <el-input-number
                  v-model="targetPctPercent"
                  :min="0.1"
                  :max="100"
                  :step="0.5"
                  :precision="2"
                  controls-position="right"
                  class="target-pct-input"
                  placeholder="输入涨幅，如 7.5"
                />
              </div>
              <div class="text-gray-500 text-sm mt-1">与「信号后持有窗口内最高价相对下一日开盘价」比较；可快捷选常用值或直接输入百分比。</div>
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
            <el-form-item label="任务类型" prop="backtest_type">
              <el-radio-group v-model="form.backtest_type">
                <el-radio label="signal_hit_rate">策略信号命中率回测</el-radio>
                <el-radio label="trade_simulation">交易回测</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
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
        <el-row v-if="form.backtest_type === 'trade_simulation'" :gutter="20">
          <el-col :span="24">
            <el-form-item label="策略预设">
              <div class="preset-row">
                <el-radio-group v-model="tradePreset" @change="applyTradePreset">
                  <el-radio-button label="conservative">稳健型</el-radio-button>
                  <el-radio-button label="balanced">平衡型（推荐）</el-radio-button>
                  <el-radio-button label="aggressive">进取型</el-radio-button>
                </el-radio-group>
                <span class="text-gray-500 text-sm">建议先用平衡型，稳定后再微调（不会修改“最低总分”）。</span>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item>
              <template #label>
                <span class="label-with-tip">
                  止损(%)
                  <el-tooltip content="固定百分比止损阈值。0 表示不启用固定止损，仅使用ATR等动态止损。建议先用 3%~8% 观察回撤变化。" placement="top">
                    <el-icon class="tip-icon"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <el-input-number
                v-model="stopLossPctPercent"
                :min="0"
                :max="100"
                :step="0.5"
                :precision="2"
                controls-position="right"
                class="w-full"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item>
              <template #label>
                <span class="label-with-tip">
                  手续费(bps)
                  <el-tooltip content="单边手续费，1 bps = 0.01%。买入和卖出都会计入。用于让回测更贴近实盘成本。" placement="top">
                    <el-icon class="tip-icon"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <el-input-number v-model="form.commission_bps" :min="0" :max="1000" :step="0.5" :precision="2" class="w-full" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item>
              <template #label>
                <span class="label-with-tip">
                  滑点(bps)
                  <el-tooltip content="单边成交滑点，反映买卖价差与冲击成本。波动较大或流动性较差标的可适当调高。" placement="top">
                    <el-icon class="tip-icon"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <el-input-number v-model="form.slippage_bps" :min="0" :max="1000" :step="0.5" :precision="2" class="w-full" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row v-if="form.backtest_type === 'trade_simulation'" :gutter="20">
          <el-col :span="8">
            <el-form-item>
              <template #label>
                <span class="label-with-tip">
                  移动止损(%)
                  <el-tooltip content="按价格回撤比例触发止损，例如 8% 表示从阶段高点回撤 8% 离场。数值越小越保守，越大越能让利润奔跑。" placement="top">
                    <el-icon class="tip-icon"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <el-input-number v-model="trailPctPercent" :min="0.1" :max="100" :step="0.5" :precision="2" class="w-full" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item>
              <template #label>
                <span class="label-with-tip">
                  保本触发(R)
                  <el-tooltip content="当浮盈达到该R倍数后，将止损抬到保本附近。R 为初始风险单位。" placement="top">
                    <el-icon class="tip-icon"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <el-input-number v-model="form.breakeven_trigger_r" :min="0" :max="20" :step="0.1" :precision="2" class="w-full" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item>
              <template #label>
                <span class="label-with-tip">
                  锁盈触发(R)
                  <el-tooltip content="当浮盈达到该R倍数后，进入锁盈阶段，避免盈利回吐过多。" placement="top">
                    <el-icon class="tip-icon"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <el-input-number v-model="form.profit_lock_trigger_r" :min="0" :max="20" :step="0.1" :precision="2" class="w-full" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row v-if="form.backtest_type === 'trade_simulation'" :gutter="20">
          <el-col :span="24">
            <div class="text-gray-500 text-sm mb-2">已隐藏 ATR 高级参数，系统自动使用默认值，保持策略简单易懂。</div>
          </el-col>
        </el-row>
        <el-row v-if="form.backtest_type === 'trade_simulation'" :gutter="20">
          <el-col :span="8">
            <el-form-item>
              <template #label>
                <span class="label-with-tip">
                  锁盈保留(R)
                  <el-tooltip content="进入锁盈后，至少保留的R收益。值越大，保护利润越强，但也可能更早离场。" placement="top">
                    <el-icon class="tip-icon"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <el-input-number v-model="form.profit_lock_r" :min="0" :max="20" :step="0.1" :precision="2" class="w-full" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item>
              <template #label>
                <span class="label-with-tip">
                  分批止盈触发(R)
                  <el-tooltip content="浮盈达到该R倍数时触发第一次部分减仓。设为较大值可近似关闭该功能。" placement="top">
                    <el-icon class="tip-icon"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <el-input-number v-model="form.partial_take_profit_r" :min="0" :max="20" :step="0.1" :precision="2" class="w-full" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item>
              <template #label>
                <span class="label-with-tip">
                  分批止盈比例
                  <el-tooltip content="触发分批止盈时减仓比例，0.4 表示卖出 40% 仓位，剩余仓位继续用移动止损跟踪。" placement="top">
                    <el-icon class="tip-icon"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <el-input-number v-model="form.partial_take_ratio" :min="0" :max="1" :step="0.05" :precision="2" class="w-full" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row v-if="form.backtest_type === 'trade_simulation'" :gutter="20">
          <el-col :span="8">
            <el-form-item>
              <template #label>
                <span class="label-with-tip">
                  时间止损K线数
                  <el-tooltip content="持仓超过该K线数量仍未走强时按规则离场，用于避免资金长期占用。常见 10~30。" placement="top">
                    <el-icon class="tip-icon"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <el-input-number v-model="form.time_stop_bars" :min="1" :max="500" :step="1" class="w-full" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item v-if="form.stock_pool_mode === 'single'" label="股票代码" prop="stock_code">
          <el-input v-model="form.stock_code" placeholder="如 000001（A股）、00700（港股）" clearable style="max-width: 280px" @keyup.enter="createTask" />
        </el-form-item>
        <el-form-item v-if="form.stock_pool_mode === 'custom'" label="股票列表" prop="stock_list">
          <el-input v-model="form.stock_list" type="textarea" :rows="4" placeholder="每行一个代码，如 000001&#10;600519&#10;00700" />
        </el-form-item>
        <el-row v-if="form.stock_pool_mode === 'watchlist'" :gutter="20">
          <el-col :span="12">
            <el-form-item label="自选股范围">
              <el-select v-model="watchlistScope" class="w-full">
                <el-option label="全部自选股（全用户）" value="all" />
                <el-option label="指定用户的自选股" value="user" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12" v-if="watchlistScope === 'user'">
            <el-form-item label="选择用户" required>
              <el-select
                v-model="watchlistUserId"
                class="w-full"
                filterable
                clearable
                placeholder="选择有自选股的用户"
              >
                <el-option
                  v-for="u in watchlistUsers"
                  :key="u.user_id"
                  :label="`${u.username || '用户'} (ID:${u.user_id}, ${u.watchlist_count}只)`"
                  :value="u.user_id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
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
          <template #default="scope">{{ displayProgress(scope.row.progress) }}%</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="scope">{{ formatDate(scope.row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="viewDetail(scope.row)">详情</el-button>
            <el-button
              size="small"
              type="primary"
              plain
              @click="rerunTask(scope.row)"
              :disabled="['pending', 'running'].includes(scope.row.status)"
            >
              重新执行
            </el-button>
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
import { ref, reactive, computed, onMounted, inject, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, QuestionFilled } from '@element-plus/icons-vue'
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
  backtest_type: 'signal_hit_rate',
  stop_loss_pct: 0,
  commission_bps: 0,
  slippage_bps: 0,
  atr_period: 14,
  init_stop_atr_k: 2.2,
  trail_stop_mode: 'atr',
  trail_atr_k: 3.0,
  trail_pct: 0.08,
  breakeven_trigger_r: 1.0,
  profit_lock_trigger_r: 2.0,
  profit_lock_r: 0.5,
  partial_take_profit_r: 2.0,
  partial_take_ratio: 0.4,
  time_stop_bars: 15,
  stock_pool_mode: 'all',
  stock_code: '',
  stock_list: ''
})
const tradePreset = ref<'conservative' | 'balanced' | 'aggressive'>('balanced')

const TRADE_PRESETS: Record<'conservative' | 'balanced' | 'aggressive', Record<string, number | string>> = {
  conservative: {
    stop_loss_pct: 0.05,
    commission_bps: 3,
    slippage_bps: 5,
    atr_period: 14,
    init_stop_atr_k: 2.6,
    trail_stop_mode: 'percent',
    trail_atr_k: 3.4,
    trail_pct: 0.08,
    breakeven_trigger_r: 1.1,
    profit_lock_trigger_r: 2.2,
    profit_lock_r: 0.6,
    partial_take_profit_r: 999,
    partial_take_ratio: 0,
    time_stop_bars: 10
  },
  balanced: {
    stop_loss_pct: 0.06,
    commission_bps: 3,
    slippage_bps: 5,
    atr_period: 14,
    init_stop_atr_k: 2.6,
    trail_stop_mode: 'percent',
    trail_atr_k: 3.4,
    trail_pct: 0.08,
    breakeven_trigger_r: 1.3,
    profit_lock_trigger_r: 2.5,
    profit_lock_r: 0.5,
    partial_take_profit_r: 999,
    partial_take_ratio: 0,
    time_stop_bars: 12
  },
  aggressive: {
    stop_loss_pct: 0.07,
    commission_bps: 3,
    slippage_bps: 5,
    atr_period: 14,
    init_stop_atr_k: 2.6,
    trail_stop_mode: 'percent',
    trail_atr_k: 3.4,
    trail_pct: 0.1,
    breakeven_trigger_r: 1.6,
    profit_lock_trigger_r: 3.2,
    profit_lock_r: 0.4,
    partial_take_profit_r: 999,
    partial_take_ratio: 0,
    time_stop_bars: 16
  }
}

/** 界面用百分比数字（5 = 5%），与 form.target_pct 同步 */
const targetPctPercent = computed({
  get: () => Math.round(form.target_pct * 10000) / 100,
  set: (v: number | undefined) => {
    if (v === undefined || v === null) return
    const n = Number(v)
    if (Number.isNaN(n)) return
    form.target_pct = Math.min(1, Math.max(0.001, n / 100))
  }
})

const targetPctQuick = ref<number | string | undefined>(undefined)
const stopLossPctPercent = computed({
  get: () => Math.round(form.stop_loss_pct * 10000) / 100,
  set: (v: number | undefined) => {
    if (v === undefined || v === null) return
    const n = Number(v)
    if (Number.isNaN(n)) return
    form.stop_loss_pct = Math.min(1, Math.max(0, n / 100))
  }
})
const trailPctPercent = computed({
  get: () => Math.round(form.trail_pct * 10000) / 100,
  set: (v: number | undefined) => {
    if (v === undefined || v === null) return
    const n = Number(v)
    if (Number.isNaN(n)) return
    form.trail_pct = Math.min(1, Math.max(0, n / 100))
  }
})

function applyTargetPctQuick(v: number | string | undefined) {
  if (v === '' || v == null) return
  const n = Number(v)
  if (Number.isNaN(n)) return
  form.target_pct = Math.min(1, Math.max(0.001, n / 100))
  nextTick(() => {
    targetPctQuick.value = undefined
  })
}

function applyTradePreset(preset: 'conservative' | 'balanced' | 'aggressive') {
  const cfg = TRADE_PRESETS[preset]
  form.stop_loss_pct = Number(cfg.stop_loss_pct)
  form.commission_bps = Number(cfg.commission_bps)
  form.slippage_bps = Number(cfg.slippage_bps)
  // ATR 高级参数固定为系统默认，不在前端暴露给用户
  form.atr_period = Number(cfg.atr_period ?? 14)
  form.init_stop_atr_k = Number(cfg.init_stop_atr_k ?? 2.6)
  form.trail_stop_mode = String(cfg.trail_stop_mode ?? 'percent')
  form.trail_atr_k = Number(cfg.trail_atr_k ?? 3.4)
  form.trail_pct = Number(cfg.trail_pct)
  form.breakeven_trigger_r = Number(cfg.breakeven_trigger_r)
  form.profit_lock_trigger_r = Number(cfg.profit_lock_trigger_r)
  form.profit_lock_r = Number(cfg.profit_lock_r)
  form.partial_take_profit_r = Number(cfg.partial_take_profit_r)
  form.partial_take_ratio = Number(cfg.partial_take_ratio)
  form.time_stop_bars = Number(cfg.time_stop_bars)
}

const rules = {
  start_date: [{ required: true, message: '请选择开始日期', trigger: 'change' }],
  end_date: [{ required: true, message: '请选择结束日期', trigger: 'change' }]
}

const tasks = ref<any[]>([])
const statusFilter = ref('')
const watchlistScope = ref<'all' | 'user'>('all')
const watchlistUserId = ref<number | undefined>(undefined)
const watchlistUsers = ref<Array<{ user_id: number; username: string; watchlist_count: number }>>([])

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

/** 任务进度 0–100，防止异常数据在列表中显示超过 100% */
function displayProgress(p: unknown): number {
  const n = Number(p)
  if (Number.isNaN(n)) return 0
  return Math.min(100, Math.max(0, Math.round(n)))
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
  if (form.stock_pool_mode === 'watchlist' && watchlistScope.value === 'user' && !watchlistUserId.value) {
    ElMessage.warning('请选择一个自选股用户')
    return
  }
  if (form.target_pct < 0.001 || form.target_pct > 1) {
    ElMessage.warning('目标阈值请在 0.1%～100% 之间（即 0.001～1）')
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
      backtest_type: form.backtest_type,
      stock_pool_mode: form.stock_pool_mode
    }
    if (form.backtest_type === 'trade_simulation') {
      body.stop_loss_pct = form.stop_loss_pct
      body.commission_bps = form.commission_bps
      body.slippage_bps = form.slippage_bps
      body.atr_period = form.atr_period
      body.init_stop_atr_k = form.init_stop_atr_k
      body.trail_stop_mode = form.trail_stop_mode
      body.trail_atr_k = form.trail_atr_k
      body.trail_pct = form.trail_pct
      body.breakeven_trigger_r = form.breakeven_trigger_r
      body.profit_lock_trigger_r = form.profit_lock_trigger_r
      body.profit_lock_r = form.profit_lock_r
      body.partial_take_profit_r = form.partial_take_profit_r
      body.partial_take_ratio = form.partial_take_ratio
      body.time_stop_bars = form.time_stop_bars
    }
    if (form.stock_pool_mode === 'single') body.stock_code = form.stock_code.trim()
    if (form.stock_pool_mode === 'custom') {
      body.stock_pool = form.stock_list.split(/\n/).map((s: string) => s.trim()).filter(Boolean)
    }
    if (form.stock_pool_mode === 'watchlist' && watchlistScope.value === 'user' && watchlistUserId.value) {
      body.watchlist_user_id = watchlistUserId.value
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
  form.backtest_type = 'signal_hit_rate'
  tradePreset.value = 'balanced'
  applyTradePreset('balanced')
  form.stock_pool_mode = 'all'
  form.stock_code = ''
  form.stock_list = ''
  watchlistScope.value = 'all'
  watchlistUserId.value = undefined
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

async function loadWatchlistUsers() {
  try {
    const users = await gmsApi.getWatchlistUsers()
    watchlistUsers.value = Array.isArray(users) ? users : []
  } catch (e) {
    watchlistUsers.value = []
    ElMessage.error('获取自选股用户列表失败')
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

async function rerunTask(row: any) {
  try {
    await ElMessageBox.confirm(
      '将使用与原任务相同的参数创建新的回测任务，是否继续？',
      '重新执行',
      { type: 'info' }
    )
    const newId = await gmsApi.rerunBacktestTask(row.task_id)
    ElMessage.success('已创建新任务: ' + newId.slice(0, 8))
    await refresh()
    emit('task-created', { id: newId })
  } catch (e) {
    if ((e as string) !== 'cancel') ElMessage.error((e as Error)?.message || '重新执行失败')
  }
}

const emit = defineEmits<{ (e: 'task-created', task: any): void; (e: 'task-updated', task: any): void }>()
defineExpose({ refresh })

onMounted(async () => {
  await Promise.all([refresh(), loadWatchlistUsers()])
})
</script>

<style scoped>
.task-list-header { display: flex; gap: 12px; margin-bottom: 12px; }
.w-full { width: 100%; }
.target-pct-row { display: flex; gap: 8px; align-items: center; width: 100%; flex-wrap: wrap; }
.target-pct-quick { width: 110px; flex-shrink: 0; }
.target-pct-input { flex: 1; min-width: 140px; }
.preset-row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.mt-1 { margin-top: 4px; }
.label-with-tip { display: inline-flex; align-items: center; gap: 4px; }
.tip-icon { color: var(--el-text-color-secondary); cursor: help; font-size: 14px; vertical-align: middle; }
</style>
