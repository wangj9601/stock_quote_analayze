<template>
  <el-dialog
    v-model="visible"
    title="任务详情"
    width="720px"
    destroy-on-close
    @close="handleClose"
  >
    <div v-if="loading" class="flex justify-center p-8"><el-icon class="is-loading"><Loading /></el-icon></div>
    <div v-else-if="task" class="task-detail">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="任务ID">{{ task.task_id?.slice(0, 8) }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ task.name }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="task.status === 'completed' ? 'success' : task.status === 'failed' ? 'danger' : 'primary'">
            {{ task.status }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="进度">{{ displayProgress(task.progress) }}%</el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ formatDateTimeBeijing(task.created_at) }}</el-descriptions-item>
        <template v-if="task.config">
          <el-descriptions-item label="任务类型">{{ backtestTypeLabel }}</el-descriptions-item>
          <el-descriptions-item label="市场">{{ task.config.market }}</el-descriptions-item>
          <el-descriptions-item label="日期范围">{{ task.config.start_date }} ~ {{ task.config.end_date }}</el-descriptions-item>
          <el-descriptions-item label="目标阈值">{{ (task.config.target_pct * 100) }}%</el-descriptions-item>
          <el-descriptions-item label="生效最低总分">{{ effectiveMinScore }}</el-descriptions-item>
          <el-descriptions-item label="持有窗口">{{ task.config.horizon_days }} 日</el-descriptions-item>
          <template v-if="isTradeSimulation">
            <el-descriptions-item label="单笔仓位">
              {{ ((Number(task.config.position_fraction) || 1) * 100).toFixed(0) }}%
            </el-descriptions-item>
            <el-descriptions-item label="止损阈值">{{ ((task.config.stop_loss_pct || 0) * 100).toFixed(2) }}%</el-descriptions-item>
            <el-descriptions-item label="交易费用">{{ `手续费 ${task.config.commission_bps || 0}bps / 滑点 ${task.config.slippage_bps || 0}bps` }}</el-descriptions-item>
          </template>
        </template>
      </el-descriptions>
      <el-alert
        v-if="scoreFilterMismatchCount > 0"
        class="mt-4"
        type="warning"
        show-icon
        :closable="false"
        :title="`检测到 ${scoreFilterMismatchCount} 条样本低于最低总分 ${effectiveMinScore}，请确认任务参数或缓存数据。`"
      />

      <template v-if="task.summary && !isTradeSimulation">
        <h4 class="mt-4 mb-2">汇总</h4>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="样本数">{{ task.summary.total_samples }}</el-descriptions-item>
          <el-descriptions-item label="命中数">{{ task.summary.hit_count }}</el-descriptions-item>
          <el-descriptions-item label="命中率">{{ (task.summary.hit_rate * 100).toFixed(2) }}%</el-descriptions-item>
        </el-descriptions>
        <h4 class="mt-4 mb-2">按买入类型</h4>
        <el-table :data="buyTypeRows" size="small" border>
          <el-table-column prop="name" label="类型" />
          <el-table-column prop="total" label="样本数" width="80" />
          <el-table-column prop="hit" label="命中" width="80" />
          <el-table-column prop="hit_rate" label="命中率">
            <template #default="scope">{{ (scope.row.hit_rate * 100).toFixed(2) }}%</template>
          </el-table-column>
        </el-table>
        <h4 class="mt-4 mb-2">按分数分桶</h4>
        <el-table :data="scoreBucketRows" size="small" border>
          <el-table-column prop="name" label="分桶" />
          <el-table-column prop="total" label="样本数" width="80" />
          <el-table-column prop="hit" label="命中" width="80" />
          <el-table-column prop="hit_rate" label="命中率">
            <template #default="scope">{{ (scope.row.hit_rate * 100).toFixed(2) }}%</template>
          </el-table-column>
        </el-table>
      </template>
      <template v-if="task.summary && isTradeSimulation">
        <h4 class="mt-4 mb-2">交易回测汇总</h4>
        <el-alert
          class="mb-3"
          type="info"
          :closable="false"
          show-icon
        >
          <template #title>
            <span class="text-sm">收益指标说明：优先参考「近似年化、算术累计、笔均组合贡献」。链条复利按成交顺序连乘，笔数多时易被极端放大，仅作对照。</span>
          </template>
        </el-alert>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="近似年化（简单折算）">{{ pct(task.summary.approx_annual_return_simple) }}</el-descriptions-item>
          <el-descriptions-item label="算术累计收益">{{ pct(task.summary.total_return_arithmetic) }}</el-descriptions-item>
          <el-descriptions-item label="笔均组合贡献">{{ pct(task.summary.avg_portfolio_pnl_per_trade) }}</el-descriptions-item>
          <el-descriptions-item label="回测自然日">{{ task.summary.backtest_calendar_days ?? '-' }} 天</el-descriptions-item>
          <el-descriptions-item label="交易数">{{ task.summary.total_trades ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="胜率">{{ pct(task.summary.win_rate) }}</el-descriptions-item>
          <el-descriptions-item label="链条复利（参考）">{{ pct(task.summary.total_return_compound) }}</el-descriptions-item>
          <el-descriptions-item label="最大回撤">{{ pct(task.summary.max_drawdown) }}</el-descriptions-item>
          <el-descriptions-item label="回撤恢复(bar)">{{ task.summary.max_drawdown_recovery_bars ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="平均持仓K线">{{ (task.summary.avg_holding_bars ?? 0).toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="平均盈利">{{ pct(task.summary.avg_win) }}</el-descriptions-item>
          <el-descriptions-item label="平均亏损">{{ pct(task.summary.avg_loss) }}</el-descriptions-item>
          <el-descriptions-item label="最大盈利单">{{ pct(task.summary.max_win_trade) }}</el-descriptions-item>
          <el-descriptions-item label="P50/P80/P95收益">
            {{ `${pctFine(task.summary.pnl_p50)} / ${pctFine(task.summary.pnl_p80)} / ${pctFine(task.summary.pnl_p95)}` }}
          </el-descriptions-item>
          <el-descriptions-item label="R均值/P50/P80/P95">{{ `${num(task.summary.r_multiple_avg)} / ${num(task.summary.r_multiple_p50)} / ${num(task.summary.r_multiple_p80)} / ${num(task.summary.r_multiple_p95)}` }}</el-descriptions-item>
          <el-descriptions-item label="盈亏比">{{ displayProfitFactor(task.summary.profit_factor) }}</el-descriptions-item>
          <el-descriptions-item label="平仓分布">{{ exitReasonText }}</el-descriptions-item>
        </el-descriptions>
      </template>

      <h4 class="mt-4 mb-2">日志</h4>
      <div class="log-box">
        <div v-for="(log, i) in logs" :key="i" class="log-line">{{ log.text }}</div>
        <div v-if="logs.length === 0" class="text-gray-400">暂无日志</div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed, inject } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { formatDateTimeBeijing } from '@/utils/formatBeijingTime'

const props = defineProps<{ modelValue: boolean; taskId: string }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void; (e: 'closed'): void }>()

const gmsApi = inject<any>('gmsApi')
const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const task = ref<any>(null)
const logs = ref<any[]>([])
const loading = ref(false)
const isTradeSimulation = computed(() => {
  const t = String(task.value?.config?.backtest_type || task.value?.summary?.backtest_type || 'signal_hit_rate')
  return t === 'trade_simulation'
})
const backtestTypeLabel = computed(() => {
  return isTradeSimulation.value ? '交易回测' : '策略信号命中率回测'
})
const effectiveMinScore = computed(() => {
  const n = Number(task.value?.config?.min_score ?? 0)
  return Number.isNaN(n) ? 0 : n
})

const buyTypeRows = computed(() => {
  const s = task.value?.summary?.by_buy_type
  if (!s || typeof s !== 'object') return []
  return Object.entries(s).map(([name, v]: [string, any]) => ({
    name,
    total: v.total ?? 0,
    hit: v.hit ?? 0,
    hit_rate: v.hit_rate ?? 0
  }))
})

const scoreBucketRows = computed(() => {
  const s = task.value?.summary?.by_score_bucket
  if (!s || typeof s !== 'object') return []
  return Object.entries(s).map(([name, v]: [string, any]) => ({
    name,
    total: v.total ?? 0,
    hit: v.hit ?? 0,
    hit_rate: v.hit_rate ?? 0
  }))
})
const exitReasonText = computed(() => {
  const m = task.value?.summary?.by_exit_reason
  if (!m || typeof m !== 'object') return '-'
  const labelMap: Record<string, string> = {
    止盈: '止盈',
    止损: '止损',
    时间出场: '时间出场',
    take_profit: '止盈',
    stop_loss: '止损',
    time_exit: '时间出场'
  }
  return Object.entries(m)
    .map(([k, v]) => `${labelMap[k] || k}:${v}`)
    .join(' / ')
})
const scoreFilterMismatchCount = computed(() => {
  const ms = Number(effectiveMinScore.value || 0)
  if (!Number.isFinite(ms) || ms <= 0) return 0
  const details = task.value?.details || task.value?.report?.details || []
  if (!Array.isArray(details) || details.length === 0) return 0
  let bad = 0
  for (const d of details) {
    const s = Number(d?.score_total)
    if (Number.isFinite(s) && s < ms) bad += 1
  }
  return bad
})

function displayProgress(p: unknown): number {
  const n = Number(p)
  if (Number.isNaN(n)) return 0
  return Math.min(100, Math.max(0, Math.round(n)))
}
function pct(v: unknown): string {
  const n = Number(v)
  if (Number.isNaN(n)) return '-'
  return `${(n * 100).toFixed(2)}%`
}
/** 分位数等需区分细微差异时用，避免与「最大盈利单」等同宽 2 位小数时被合并成同一显示 */
function pctFine(v: unknown, fractionDigits = 4): string {
  const n = Number(v)
  if (Number.isNaN(n)) return '-'
  return `${(n * 100).toFixed(fractionDigits)}%`
}
function displayProfitFactor(v: unknown): string {
  const n = Number(v)
  if (Number.isNaN(n)) return '-'
  return n.toFixed(3)
}
function num(v: unknown): string {
  const n = Number(v)
  if (Number.isNaN(n)) return '-'
  return n.toFixed(3)
}

async function load() {
  if (!props.taskId) return
  loading.value = true
  task.value = null
  logs.value = []
  try {
    task.value = await gmsApi.getBacktestTask(props.taskId)
    const logList = await gmsApi.getBacktestLogs(props.taskId)
    logs.value = Array.isArray(logList) ? logList : []
  } finally {
    loading.value = false
  }
}

function handleClose() {
  emit('closed')
}

watch(
  () => [props.modelValue, props.taskId],
  ([v, id]) => {
    if (v && id) load()
  },
  { immediate: true }
)
</script>

<style scoped>
.log-box { max-height: 200px; overflow-y: auto; border: 1px solid var(--el-border-color); border-radius: 4px; padding: 8px; font-size: 12px; }
.log-line { padding: 2px 0; }
.mt-4 { margin-top: 1rem; }
.mb-2 { margin-bottom: 0.5rem; }
</style>
