<template>
  <el-dialog
    v-model="visible"
    title="URT 交易回测详情"
    width="920px"
    destroy-on-close
    @close="handleClose"
  >
    <div v-if="loading" class="flex justify-center p-8">
      <el-icon class="is-loading"><Loading /></el-icon>
    </div>
    <div v-else-if="task" class="task-detail">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="任务ID">{{ task.task_id?.slice(0, 8) }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ task.name }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType">{{ task.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="进度">{{ displayProgress(task.progress) }}%</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ task.created_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{ task.completed_at || '-' }}</el-descriptions-item>
        <template v-if="task.config">
          <el-descriptions-item label="股票池">{{ stockPoolLabel }}</el-descriptions-item>
          <el-descriptions-item v-if="cnBoardLabel" label="A股板块">{{ cnBoardLabel }}</el-descriptions-item>
          <el-descriptions-item label="日期范围">{{ task.config.start_date }} ~ {{ task.config.end_date }}</el-descriptions-item>
          <el-descriptions-item label="目标涨幅">{{ formatTargetPctRange(task.config) }}</el-descriptions-item>
          <el-descriptions-item label="观察期">{{ task.config.horizon_days ?? 10 }} 个交易日</el-descriptions-item>
          <el-descriptions-item label="参数版本">
            {{ configVersionLabel }}
            <el-tag v-if="task.config.params_diverged" type="warning" size="small" class="ml-tag">已偏离生效配置</el-tag>
            <el-tag v-else-if="task.config.is_effective_config" type="success" size="small" class="ml-tag">生效</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="最低得分">
            {{ minScoreDisplay }}
            <span v-if="task.config.min_score_override" class="hint-inline">（任务覆盖）</span>
            <span v-else class="hint-inline">（参数版本）</span>
          </el-descriptions-item>
          <el-descriptions-item label="信号质量">{{ signalQualityLabel }}</el-descriptions-item>
          <el-descriptions-item label="优先读缓存">{{ task.config.use_trace ? '是' : '否' }}</el-descriptions-item>
          <el-descriptions-item label="出场模式">{{ exitModeLabel }}</el-descriptions-item>
          <el-descriptions-item v-if="poolSizeLabel" label="股票池规模">{{ poolSizeLabel }}</el-descriptions-item>
          <el-descriptions-item v-if="divergeReasonsLabel" label="偏离原因" :span="2">{{ divergeReasonsLabel }}</el-descriptions-item>
        </template>
      </el-descriptions>

      <h4 class="mt-4 mb-2">交易逻辑细节</h4>
      <el-alert
        v-if="tradeLogicSummary"
        class="mb-2"
        type="info"
        :closable="false"
        show-icon
        :title="tradeLogicSummary"
      />
      <ol v-if="tradeLogicRules.length" class="logic-list">
        <li v-for="(rule, i) in tradeLogicRules" :key="i">{{ rule }}</li>
      </ol>
      <el-table
        v-if="exitPriorityRows.length"
        :data="exitPriorityRows"
        size="small"
        border
        class="mt-2"
      >
        <el-table-column prop="order" label="优先级" width="70" />
        <el-table-column prop="label" label="出场类型" width="120" />
        <el-table-column prop="code" label="代码" width="160" />
        <el-table-column prop="desc" label="判定说明" />
      </el-table>
      <div v-if="!tradeLogicRules.length && !exitPriorityRows.length" class="text-gray-400 text-sm">
        暂无交易逻辑说明
      </div>

      <h4 class="mt-4 mb-2">风控参数</h4>
      <el-alert
        class="mb-2"
        type="info"
        :closable="false"
        show-icon
        :title="riskParamsAlertTitle"
      />
      <el-descriptions v-if="hasRiskParams" :column="2" border size="small">
        <el-descriptions-item label="价格止损阈值">
          −{{ num(riskParams.stop_loss_pct_max) }}%
          <span class="hint-inline">（文档区间 {{ num(riskParams.stop_loss_pct_min) }}%–{{ num(riskParams.stop_loss_pct_max) }}%）</span>
        </el-descriptions-item>
        <el-descriptions-item label="时间止损">
          连续收跌 ≥ {{ riskParams.time_stop_down_days ?? '-' }} 日
          <span v-if="riskParams.time_stop_min_loss_pct != null">
            且浮亏 ≥ {{ num(riskParams.time_stop_min_loss_pct) }}%
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="止盈警惕涨幅">
          {{ num(riskParams.take_profit_alert_pct_min) }}%–{{ num(riskParams.take_profit_alert_pct_max) }}%
        </el-descriptions-item>
        <el-descriptions-item label="高点回撤止盈">
          ≥ {{ num(riskParams.trailing_drawdown_pct) }}%
        </el-descriptions-item>
        <el-descriptions-item v-if="riskParams.structure_stop_buffer_pct != null" label="结构止损缓冲">
          {{ (Number(riskParams.structure_stop_buffer_pct) * 100).toFixed(0) }}%
        </el-descriptions-item>
        <el-descriptions-item v-if="riskParams.exit_mode" label="出场模式(快照)">
          {{ exitModeLabel }}
        </el-descriptions-item>
      </el-descriptions>
      <div v-else class="text-gray-400 text-sm">暂无风控参数快照</div>

      <template v-if="task.summary">
        <h4 class="mt-4 mb-2">汇总统计</h4>
        <el-alert
          v-if="targetRangeOpen"
          class="mb-2"
          type="info"
          :closable="false"
          show-icon
          title="区间目标模式：命中率 = 最大涨幅 ≥ 下限；「涨幅落在区间内」「上限触及率」为辅助统计。"
        />
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="信号数">{{ task.summary.total_signals ?? task.summary.total_samples ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="命中数">{{ task.summary.target_hits ?? task.summary.hit_count ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="命中率">{{ pct(task.summary.hit_rate) }}</el-descriptions-item>
          <el-descriptions-item v-if="targetRangeOpen" label="涨幅落在区间内">{{ pct(task.summary.in_band_rate) }}</el-descriptions-item>
          <el-descriptions-item v-if="targetRangeOpen" label="上限触及率">{{ pct(task.summary.hit_rate_upper) }}</el-descriptions-item>
          <template v-if="resolvedExitMode !== 'hit_rate'">
            <el-descriptions-item label="胜率">{{ pct(task.summary.win_rate) }}</el-descriptions-item>
            <el-descriptions-item label="均盈亏(期末)">{{ task.summary.avg_pnl_pct ?? '-' }}%</el-descriptions-item>
          </template>
          <el-descriptions-item label="均最大涨幅">{{ task.summary.avg_max_gain_pct ?? '-' }}%</el-descriptions-item>
          <el-descriptions-item label="目标涨幅">{{ formatTargetPctRange(task.summary) }}</el-descriptions-item>
          <el-descriptions-item label="出场模式">{{ exitModeLabel }}</el-descriptions-item>
          <el-descriptions-item v-if="task.summary.avg_bars_held != null" label="均持有天数">
            {{ task.summary.avg_bars_held }}
          </el-descriptions-item>
        </el-descriptions>

        <template v-if="task.summary.structure_exit_stats">
          <h4 class="mt-4 mb-2">结构出场归因</h4>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="结构止损">{{ task.summary.structure_exit_stats.structure_stop ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="阻力止盈">{{ task.summary.structure_exit_stats.structure_target ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="百分比止盈">{{ task.summary.structure_exit_stats.pct_target ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="百分比止损回退">{{ task.summary.structure_exit_stats.price_stop ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="保本止损">{{ task.summary.structure_exit_stats.breakeven_stop ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="移动止盈">{{ task.summary.structure_exit_stats.fallback_trail ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="分批出场">{{ task.summary.structure_exit_stats.partial_exit_count ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="到期平仓">{{ task.summary.structure_exit_stats.horizon_end ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="结构缺失回退率">{{ pct(task.summary.structure_exit_stats.structure_fallback_rate) }}</el-descriptions-item>
            <el-descriptions-item label="回退-无支撑">{{ task.summary.structure_exit_stats.fallback_no_support ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="回退-止损≥入场">{{ task.summary.structure_exit_stats.fallback_stop_above_entry ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="弱结构笔数">{{ task.summary.structure_exit_stats.weak_structure_count ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="KDE重算笔数">{{ task.summary.structure_exit_stats.kde_recomputed_count ?? 0 }}</el-descriptions-item>
          </el-descriptions>
        </template>

        <template v-if="hitRateCompare">
          <h4 class="mt-4 mb-2">命中率对照（同批信号）</h4>
          <el-alert
            class="mb-2"
            type="info"
            :closable="false"
            show-icon
            :title="hitRateCompare.note || '命中率/最大涨幅与出场无关；满观察期盈亏按末日收盘。'"
          />
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="同批命中率">{{ pct(hitRateCompare.hit_rate) }}</el-descriptions-item>
            <el-descriptions-item label="同批均最大涨幅">{{ hitRateCompare.avg_max_gain_pct ?? '-' }}%</el-descriptions-item>
            <el-descriptions-item label="实际出场均盈亏">{{ hitRateCompare.actual?.avg_pnl_pct ?? '-' }}%</el-descriptions-item>
            <el-descriptions-item label="实际出场胜率">{{ pct(hitRateCompare.actual?.win_rate) }}</el-descriptions-item>
            <el-descriptions-item label="满观察期均盈亏">{{ hitRateCompare.horizon_hold?.avg_pnl_pct ?? '-' }}%</el-descriptions-item>
            <el-descriptions-item label="满观察期胜率">{{ pct(hitRateCompare.horizon_hold?.win_rate) }}</el-descriptions-item>
            <el-descriptions-item label="最大涨幅−实际盈亏">{{ hitRateCompare.max_gain_vs_actual_pnl_gap ?? '-' }}%</el-descriptions-item>
            <el-descriptions-item label="满期盈亏−实际盈亏">{{ hitRateCompare.horizon_vs_actual_pnl_gap ?? '-' }}%</el-descriptions-item>
            <el-descriptions-item v-if="pairedHitRate" label="独立对照命中率" :span="2">
              {{ pct(pairedHitRate.hit_rate) }}
              · 信号 {{ pairedHitRate.total_signals ?? '-' }}
              · 均盈亏 {{ pairedHitRate.avg_pnl_pct ?? '-' }}%
              · 均最大涨幅 {{ pairedHitRate.avg_max_gain_pct ?? '-' }}%
              <span v-if="pairedTaskId" class="hint-inline">（任务 {{ pairedTaskId.slice(0, 8) }}）</span>
            </el-descriptions-item>
            <el-descriptions-item v-else-if="pairedTaskId" label="独立对照任务" :span="2">
              {{ pairedTaskId.slice(0, 8) }}（排队中或未完成）
            </el-descriptions-item>
          </el-descriptions>
        </template>

        <h4 v-if="scoreBucketRows.length" class="mt-4 mb-2">按分数分桶</h4>
        <el-table v-if="scoreBucketRows.length" :data="scoreBucketRows" size="small" border>
          <el-table-column prop="name" label="分桶" />
          <el-table-column prop="total" label="样本数" width="80" />
          <el-table-column prop="hit" label="命中" width="70" />
          <el-table-column label="命中率" width="90">
            <template #default="{ row }">{{ pct(row.hit_rate) }}</template>
          </el-table-column>
          <el-table-column v-if="resolvedExitMode !== 'hit_rate'" label="胜率" width="90">
            <template #default="{ row }">{{ pct(row.win_rate) }}</template>
          </el-table-column>
          <el-table-column v-if="resolvedExitMode !== 'hit_rate'" label="均盈亏" width="90">
            <template #default="{ row }">{{ row.avg_pnl_pct ?? '-' }}%</template>
          </el-table-column>
          <el-table-column label="均最大涨幅" width="100">
            <template #default="{ row }">{{ row.avg_max_gain_pct ?? '-' }}%</template>
          </el-table-column>
        </el-table>

        <h4 v-if="factorBucketRows.length" class="mt-4 mb-2">按信号因子分桶</h4>
        <el-table v-if="factorBucketRows.length" :data="factorBucketRows" size="small" border>
          <el-table-column prop="factor" label="因子" width="120" />
          <el-table-column prop="bucket" label="分箱" width="100" />
          <el-table-column prop="total" label="样本" width="70" />
          <el-table-column prop="hit" label="命中" width="70" />
          <el-table-column label="命中率" width="90">
            <template #default="{ row }">{{ pct(row.hit_rate) }}</template>
          </el-table-column>
          <el-table-column v-if="resolvedExitMode !== 'hit_rate'" label="胜率" width="90">
            <template #default="{ row }">{{ pct(row.win_rate) }}</template>
          </el-table-column>
          <el-table-column v-if="resolvedExitMode !== 'hit_rate'" label="均盈亏" width="90">
            <template #default="{ row }">{{ row.avg_pnl_pct ?? '-' }}%</template>
          </el-table-column>
          <el-table-column label="均最大涨幅" width="100">
            <template #default="{ row }">{{ row.avg_max_gain_pct ?? '-' }}%</template>
          </el-table-column>
        </el-table>

        <h4 v-if="exitReasonRows.length" class="mt-4 mb-2">离场原因分布</h4>
        <el-table v-if="exitReasonRows.length" :data="exitReasonRows" size="small" border>
          <el-table-column prop="name" label="原因" />
          <el-table-column prop="label" label="中文" width="120" />
          <el-table-column prop="count" label="笔数" width="100" />
        </el-table>
      </template>

      <h4 class="mt-4 mb-2">日志</h4>
      <div class="log-box">
        <div v-for="(log, i) in logs" :key="i" class="log-line">{{ log.text || log.message || log }}</div>
        <div v-if="!logs.length" class="text-gray-400">暂无日志</div>
      </div>
    </div>
    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button
        type="primary"
        :disabled="!task || loading"
        :loading="exporting"
        @click="exportPdf"
      >
        导出PDF
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, inject, onUnmounted, ref, watch } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{ modelValue: boolean; taskId: string }>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'closed'): void
  (e: 'task-updated', task: any): void
}>()

const urtApi = inject<any>('urtApi')
const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const task = ref<any>(null)
const logs = ref<any[]>([])
const loading = ref(false)
const exporting = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

const statusType = computed(() => {
  const s = task.value?.status
  if (s === 'completed') return 'success'
  if (s === 'failed') return 'danger'
  if (s === 'cancelled') return 'info'
  return 'primary'
})

const STOCK_POOL_LABELS: Record<string, string> = {
  all: '全市场',
  gms_watchlist: 'GMS观察股',
  watchlist: '自选股',
  industry_board: '行业板块',
  concept_board: '概念板块',
  single: '单股回测',
  custom: '自定义列表',
}

const CN_BOARD_LABELS: Record<string, string> = {
  MAIN: '主板',
  CYB: '创业板',
  SZ_SME: '中小板',
  KCB: '科创板',
  BJ: '北证',
}

const stockPoolLabel = computed(() => {
  const mode = String(task.value?.config?.stock_pool_mode || 'all')
  const base = STOCK_POOL_LABELS[mode] || mode
  const pool = task.value?.config?.stock_pool
  if (Array.isArray(pool) && pool.length && mode !== 'all') {
    return `${base}（${pool.length} 只）`
  }
  return base
})

const cnBoardLabel = computed(() => {
  const seg = String(task.value?.config?.cn_board_segment || '').toUpperCase()
  if (!seg || seg === 'ALL') return ''
  return CN_BOARD_LABELS[seg] || seg
})

const poolSizeLabel = computed(() => {
  const n = task.value?.summary?.stock_pool_size
  if (n == null) return ''
  return String(n)
})

const configVersionLabel = computed(() => {
  const cfg = task.value?.config || {}
  const id = cfg.strategy_config_id
  const name = cfg.config_name || ''
  const ver = cfg.config_version_label ? ` / ${cfg.config_version_label}` : ''
  if (id == null && !name) return '-'
  return `${name || '未命名'}${ver}${id != null ? ` (#${id})` : ''}`
})

const minScoreDisplay = computed(() => {
  const cfg = task.value?.config || {}
  const v = cfg.min_score ?? task.value?.summary?.min_score ?? cfg.package_min_score
  return v == null || Number.isNaN(Number(v)) ? '-' : String(v)
})

const signalQualityLabel = computed(() => {
  const t = task.value
  const summary = t?.summary || {}
  const cfg = t?.config || {}
  if (summary.signal_quality_mode_label) return String(summary.signal_quality_mode_label)
  const mode = String(cfg.signal_quality_mode || summary.signal_quality_mode || 'standard').toLowerCase()
  if (mode === 'premium') return '精选（近支撑≤2% + 排除弱项）'
  return '标准（排除均线多头分中段）'
})

const divergeReasonsLabel = computed(() => {
  const reasons = task.value?.config?.diverge_reasons
  if (!Array.isArray(reasons) || !reasons.length) return ''
  const map: Record<string, string> = {
    strategy_config_id_not_effective: '非生效参数版本',
    min_score_override: '最低得分任务覆盖',
  }
  return reasons.map((r: string) => map[r] || r).join('；')
})

const resolvedExitMode = computed(() => {
  const t = task.value || {}
  const raw =
    t.summary?.exit_mode ||
    t.config?.exit_mode ||
    t.summary?.risk_params?.exit_mode ||
    t.config?.risk_params?.exit_mode ||
    t.summary?.backtest_mode ||
    ''
  const m = String(raw || '').trim().toLowerCase()
  if (m === 'structure_exit') return 'structure_exit'
  if (m === 'risk_exit') return 'risk_exit'
  if (m === 'signal_hit_rate' || m === 'hit_rate') return 'hit_rate'
  if (t.summary?.apply_stop_loss === true && m !== 'structure_exit') return 'risk_exit'
  return 'hit_rate'
})

const exitModeLabel = computed(() => {
  const map: Record<string, string> = {
    hit_rate: '命中率（不止损）',
    risk_exit: '纪律出场（止损/连跌/回撤）',
    structure_exit: '结构出场（支撑止损/阻力止盈）',
  }
  return map[resolvedExitMode.value] || resolvedExitMode.value
})

const riskParamsAlertTitle = computed(() => {
  const mode = resolvedExitMode.value
  if (mode === 'structure_exit') {
    return '当前回测为「结构出场」：支撑止损/阻力止盈参与模拟；下方百分比风控作回退与文档快照。'
  }
  if (mode === 'risk_exit') {
    return '当前回测为「纪律出场」：以下价格止损/连跌/回撤参数参与出场模拟。'
  }
  return '当前回测为「命中率/不止损」模式（对齐 GMS signal_hit_rate）：仅统计观察期内是否触达目标涨幅；以下风控参数不参与模拟。'
})

const EXIT_REASON_ZH: Record<string, string> = {
  target_hit: '触及目标',
  horizon_end: '到期平仓',
  price_stop: '价格止损',
  time_stop: '时间止损',
  trailing_take_profit: '回撤止盈',
  structure_stop: '结构止损',
  structure_target: '阻力止盈',
  pct_target: '百分比止盈',
  breakeven_stop: '保本止损',
  fallback_trail: '移动止盈',
  rule_exit: '规则离场',
  stop_loss: '止损',
}

const tradeLogic = computed(() => {
  return (
    task.value?.summary?.trade_logic ||
    task.value?.config?.trade_logic ||
    null
  )
})

const tradeLogicSummary = computed(() => tradeLogic.value?.summary || '')

const tradeLogicRules = computed(() => {
  const rules = tradeLogic.value?.rules
  return Array.isArray(rules) ? rules.map((x: any) => String(x)) : []
})

const exitPriorityRows = computed(() => {
  const rows = tradeLogic.value?.exit_priority
  if (!Array.isArray(rows)) return []
  return rows.map((r: any, i: number) => ({
    order: i + 1,
    code: r?.code || '',
    label: r?.label || EXIT_REASON_ZH[r?.code] || r?.code || '',
    desc: r?.desc || '',
  }))
})

const riskParams = computed(() => {
  return (
    task.value?.summary?.risk_params ||
    task.value?.config?.risk_params ||
    task.value?.config?.strategy_risk ||
    {}
  )
})

const hasRiskParams = computed(() => {
  const r = riskParams.value
  return r && (r.stop_loss_pct_max != null || r.time_stop_down_days != null)
})

const scoreBucketRows = computed(() => {
  const buckets = task.value?.summary?.by_score_bucket || {}
  return Object.keys(buckets).map((name) => ({
    name,
    total: buckets[name]?.total ?? 0,
    hit: buckets[name]?.hit ?? 0,
    hit_rate: buckets[name]?.hit_rate ?? 0,
    win_rate: buckets[name]?.win_rate,
    avg_pnl_pct: buckets[name]?.avg_pnl_pct,
    avg_max_gain_pct: buckets[name]?.avg_max_gain_pct,
  }))
})

const hitRateCompare = computed(() => task.value?.summary?.hit_rate_compare || null)
const pairedHitRate = computed(() => task.value?.summary?.paired_hit_rate_summary || null)
const pairedTaskId = computed(() => {
  return (
    task.value?.summary?.paired_hit_rate_task_id ||
    task.value?.config?.paired_hit_rate_task_id ||
    pairedHitRate.value?.task_id ||
    ''
  )
})

const factorBucketRows = computed(() => {
  const factors = task.value?.summary?.by_factor_bucket || {}
  const rows: any[] = []
  Object.keys(factors).forEach((key) => {
    const spec = factors[key] || {}
    const label = spec.label || key
    const bins = Array.isArray(spec.bins) ? spec.bins : []
    bins.forEach((b: any) => {
      rows.push({
        factor: label,
        bucket: b.bucket,
        total: b.total,
        hit: b.hit,
        hit_rate: b.hit_rate,
        win_rate: b.win_rate,
        avg_pnl_pct: b.avg_pnl_pct,
        avg_max_gain_pct: b.avg_max_gain_pct,
      })
    })
  })
  return rows
})

const exitReasonRows = computed(() => {
  const dist = task.value?.summary?.exit_reason_dist || {}
  return Object.keys(dist).map((name) => ({
    name,
    label: EXIT_REASON_ZH[name] || name,
    count: dist[name],
  }))
})

function formatTargetPctRange(src: any) {
  if (!src) return '-'
  const lo = Number(src.target_pct || 0) * 100
  const hiRaw = src.target_pct_max
  const hi = hiRaw == null || hiRaw === '' ? lo : Number(hiRaw) * 100
  if (!Number.isFinite(lo)) return '-'
  if (!Number.isFinite(hi) || Math.abs(hi - lo) < 1e-6) return `${lo.toFixed(1)}%`
  return `${lo.toFixed(1)}%～${hi.toFixed(1)}%`
}

const targetRangeOpen = computed(() => {
  const s = task.value?.summary || task.value?.config
  if (!s) return false
  const lo = Number(s.target_pct || 0)
  const hi = s.target_pct_max == null || s.target_pct_max === '' ? lo : Number(s.target_pct_max)
  return Number.isFinite(hi) && Math.abs(hi - lo) > 1e-9
})

function pct(v: any) {
  if (v == null || Number.isNaN(Number(v))) return '-'
  return `${(Number(v) * 100).toFixed(2)}%`
}

function num(v: any) {
  if (v == null || Number.isNaN(Number(v))) return '-'
  return Number(v)
}

function displayProgress(p: any) {
  const n = Number(p)
  if (Number.isNaN(n)) return 0
  return Math.max(0, Math.min(100, Math.round(n)))
}

function isActive(status?: string) {
  return status === 'pending' || status === 'running'
}

async function load() {
  if (!props.taskId || !urtApi) return
  loading.value = !task.value
  try {
    task.value = await urtApi.getBacktest(props.taskId)
    try {
      logs.value = await urtApi.getBacktestLogs(props.taskId)
    } catch {
      logs.value = (task.value?.logs || []).map((x: any) =>
        typeof x === 'object' ? { text: x.message || x.text, ts: x.ts } : { text: String(x) }
      )
    }
    emit('task-updated', task.value)
  } finally {
    loading.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => {
    if (isActive(task.value?.status)) void load()
    else stopPolling()
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function handleClose() {
  stopPolling()
  emit('closed')
}

function pdfFilename() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const id = String(task.value?.task_id || props.taskId || '').slice(0, 8) || 'unknown'
  const rawName = String(task.value?.name || '').trim()
  const namePart = rawName
    .replace(/[\\/:*?"<>|]/g, '')
    .replace(/\s+/g, '_')
    .slice(0, 40)
  const mid = namePart || `URT回测_${id}`
  return `URT回测详情_${mid}_${y}${m}${day}.pdf`
}

async function exportPdf() {
  if (!props.taskId || !urtApi || exporting.value) return
  exporting.value = true
  try {
    const blob = await urtApi.downloadBacktestPdf(props.taskId)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = pdfFilename()
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('PDF导出成功')
  } catch (e: any) {
    console.error(e)
    ElMessage.error(e?.message || '导出PDF失败')
  } finally {
    exporting.value = false
  }
}

watch(
  () => [props.modelValue, props.taskId] as const,
  ([open]) => {
    if (open && props.taskId) {
      task.value = null
      void load().then(() => {
        if (isActive(task.value?.status)) startPolling()
      })
    } else {
      stopPolling()
    }
  },
  { immediate: true }
)

onUnmounted(stopPolling)
</script>

<style scoped>
.mt-4 { margin-top: 16px; }
.mt-2 { margin-top: 8px; }
.mb-2 { margin-bottom: 8px; }
.flex { display: flex; }
.justify-center { justify-content: center; }
.p-8 { padding: 32px; }
.logic-list {
  margin: 0;
  padding-left: 1.25rem;
  font-size: 13px;
  line-height: 1.65;
  color: #334155;
}
.logic-list li { margin-bottom: 4px; }
.hint-inline {
  margin-left: 4px;
  color: #94a3b8;
  font-size: 12px;
}
.ml-tag { margin-left: 8px; }
.text-sm { font-size: 13px; }
.log-box {
  max-height: 220px;
  overflow: auto;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 12px;
  line-height: 1.5;
}
.log-line { white-space: pre-wrap; }
.text-gray-400 { color: #9ca3af; }
</style>
