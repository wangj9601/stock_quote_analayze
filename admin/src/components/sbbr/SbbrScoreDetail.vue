<template>
  <div class="sbbr-score-detail">
    <div class="meta-line">
      <strong>做小做底策略（SBBR）</strong>
      <span>日期 {{ text(stock.date) }}</span>
      <span>筑底 {{ bottomModeLabel(stock.bottom_mode) }}</span>
      <span>
        入场
        <el-tag :type="stock.entry_signal ? 'success' : 'info'" size="small">
          {{ stock.entry_signal ? '是' : '否' }}
        </el-tag>
      </span>
      <span v-if="stock.size_ok != null">做小 {{ stock.size_ok ? '通过' : '未通过' }}</span>
      <el-tag v-if="stock.price_adjust === 'qfq'" size="small" type="warning">前复权</el-tag>
    </div>

    <section>
      <h4>做小过滤</h4>
      <p class="hint">
        默认口径：总市值 20～300 亿元，或流通股本 &gt;5 亿股（任一项符合即通过；流通市值不参与默认过滤）。
      </p>
      <el-table :data="sizeRows" size="small" border>
        <el-table-column prop="name" label="指标" width="120" />
        <el-table-column prop="value" label="取值" min-width="160" />
        <el-table-column prop="note" label="说明" min-width="220" />
      </el-table>
    </section>

    <section>
      <h4>筑底识别</h4>
      <p class="hint">
        模式：{{ bottomModeLabel(stock.bottom_mode) }} · 命中
        {{ stock.bottom_matched == null ? '--' : stock.bottom_matched ? '是' : '否' }}
      </p>
      <el-table :data="bottomRows" size="small" border>
        <el-table-column prop="name" label="字段" width="120" />
        <el-table-column prop="value" label="取值" min-width="180" />
        <el-table-column prop="note" label="说明" min-width="240" />
      </el-table>
    </section>

    <section>
      <h4>入场判断逻辑</h4>
      <p class="hint">入场 = 筑底成立 AND 收盘上穿 MA20 AND 底部缩量 AND 当日微放量（大盘共振仅展示，暂不硬筛）</p>
      <p class="hint">
        上穿：昨收≤昨MA20 且 今收&gt;今MA20；缩量：近5日均量/更早5日均量≤0.7；微放量：当日量/近5日均量 ∈ [1.05, 1.8]；大盘：上证指数近5日累计收益≤-1%（始终计算；当前不作为入场硬条件）。
      </p>
      <el-table :data="entryRows" size="small" border>
        <el-table-column prop="name" label="条件" width="120" />
        <el-table-column prop="rule" label="规则" min-width="200" />
        <el-table-column prop="value" label="实际值" min-width="180" />
        <el-table-column label="结果" width="120">
          <template #default="{ row }">
            <span v-if="row.resultText">{{ row.resultText }}</span>
            <el-tag v-else-if="row.ok === true" type="success" size="small">通过</el-tag>
            <el-tag v-else-if="row.ok === false" type="danger" size="small">未通过</el-tag>
            <span v-else>--</span>
          </template>
        </el-table-column>
      </el-table>
      <p class="conclusion">
        结论：{{ entryReasonText(entryReason) }} → 入场
        <el-tag :type="stock.entry_signal ? 'success' : 'info'" size="small">
          {{ stock.entry_signal ? '是' : '否' }}
        </el-tag>
      </p>
    </section>

    <section>
      <h4>弹性防守</h4>
      <p class="hint">以入场低点为锚：defense_high = anchor，defense_low = anchor × (1 − buffer)；默认 buffer 约 3%。</p>
      <el-table :data="defenseRows" size="small" border>
        <el-table-column prop="name" label="字段" width="140" />
        <el-table-column prop="value" label="取值" width="140" />
        <el-table-column prop="note" label="说明" min-width="220" />
      </el-table>
    </section>

    <section>
      <h4>结构位 / KDE</h4>
      <div class="meta-line">
        <span>最近支撑 <strong>{{ fmt(nearSup) }}</strong></span>
        <span>最近阻力 <strong>{{ fmt(nearRes) }}</strong></span>
        <span v-if="kdeOk != null">KDE {{ kdeOk ? '成功' : '未识别' }}</span>
        <span v-if="kdeLookback != null">回看 {{ kdeLookback }} 日</span>
        <span v-if="kdeReason">{{ kdeReasonText(kdeReason) }}</span>
      </div>
      <el-table v-if="levelRows.length" :data="levelRows" size="small" border>
        <el-table-column prop="name" label="类型" width="100" />
        <el-table-column prop="value" label="价位（近→远）" min-width="240" />
      </el-table>
    </section>

    <section v-if="showPosition">
      <h4>仓位建议 / 支撑确认</h4>
      <div v-if="hasPosition" class="meta-line">
        <span>建议动作 {{ text(position.next_action) }}</span>
        <span v-if="position.next_pct != null">建议仓位 {{ fmt(position.next_pct, 0) }}%</span>
        <span v-if="position.probe_pct != null">试探 {{ fmt(position.probe_pct, 0) }}%</span>
        <span v-if="position.add_pct != null">追加 {{ fmt(position.add_pct, 0) }}%</span>
        <span v-if="position.reserve_cash_pct != null">保留现金 {{ fmt(position.reserve_cash_pct, 0) }}%</span>
      </div>
      <p v-if="position.message" class="hint">{{ position.message }}</p>
      <p v-if="supportConfirm" class="conclusion">
        上方支撑确认：
        <el-tag :type="supportConfirm.confirmed ? 'success' : 'info'" size="small">
          {{ supportConfirm.confirmed ? '是' : '否' }}
        </el-tag>
        <span v-if="supportConfirm.reason">（{{ supportConfirm.reason }}）</span>
      </p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ stock: Record<string, any> }>()

const detail = computed(() => (props.stock?.detail && typeof props.stock.detail === 'object' ? props.stock.detail : {}))
const entryD = computed(() => (detail.value.entry && typeof detail.value.entry === 'object' ? detail.value.entry : {}))
const bottomD = computed(() => (detail.value.bottom && typeof detail.value.bottom === 'object' ? detail.value.bottom : {}))
const structD = computed(() =>
  detail.value.structure && typeof detail.value.structure === 'object' ? detail.value.structure : {}
)
const position = computed(() =>
  props.stock?.position_advice && typeof props.stock.position_advice === 'object' ? props.stock.position_advice : {}
)
const supportConfirm = computed(() =>
  props.stock?.support_confirm && typeof props.stock.support_confirm === 'object' ? props.stock.support_confirm : null
)

function pick(...vals: unknown[]) {
  for (const v of vals) {
    if (v != null && v !== '') return v
  }
  return null
}

function fmt(v: unknown, digits = 2) {
  if (v == null || v === '') return '--'
  if (typeof v === 'boolean') return v ? '是' : '否'
  const n = Number(v)
  if (!Number.isFinite(n)) return String(v)
  return n.toFixed(digits)
}

function text(v: unknown) {
  if (v == null || v === '') return '--'
  return String(v)
}

function bottomModeLabel(mode: unknown) {
  if (mode === 'range_accumulation') return '横盘收集 range_accumulation'
  if (mode === 'panic_accumulation') return '打压恐慌 panic_accumulation'
  return text(mode)
}

const SIZE_REASON: Record<string, string> = {
  ok: '总市值与流通股本均落在区间内',
  out_of_range: '总市值或流通股本超出区间',
  total_only: '仅校验总市值（流通股本缺失）',
  circ_shares_only: '仅校验流通股本（总市值缺失）',
  unknown_shares: '总市值与流通股本均缺失',
}

const ENTRY_REASON: Record<string, string> = {
  ok: '入场子条件全部满足',
  no_bottom: '筑底未成立，不评估入场',
  insufficient_bars: 'K 线不足',
  no_ma: '无法计算 MA20',
  rules_not_met: '上穿/缩量/微放量未全部满足',
}

const KDE_REASON: Record<string, string> = {
  ok: 'KDE 识别成功',
  insufficient_samples: '有效价量样本不足',
  no_bars: '缺少行情',
  ok_histogram_fallback: '已用直方图回退',
}

function entryReasonText(code: unknown) {
  const key = String(code || '')
  return ENTRY_REASON[key] || text(code)
}

function kdeReasonText(code: unknown) {
  const key = String(code || '')
  return KDE_REASON[key] || text(code)
}

const entryReason = computed(() => pick(entryD.value.reason, props.stock.entry_reason, props.stock.reason))
const nearSup = computed(() => pick(props.stock.nearest_support, structD.value.nearest_support))
const nearRes = computed(() => pick(props.stock.nearest_resistance, structD.value.nearest_resistance))
const kdeOk = computed(() => pick(props.stock.kde_ok, structD.value.kde_ok) as boolean | null)
const kdeReason = computed(() => pick(props.stock.kde_reason, structD.value.kde_reason))
const kdeLookback = computed(() => pick(props.stock.kde_lookback_used, structD.value.kde_lookback_used))

const sizeRows = computed(() => {
  const rows: { name: string; value: string; note: string }[] = [
    { name: '总市值', value: `${fmt(props.stock.total_mv)} 亿元`, note: 'total_shares × 收盘 / 1e8' },
    {
      name: '流通股本',
      value: `${fmt(pick(props.stock.circ_shares_yi, detail.value.circ_shares_yi))} 亿股`,
      note: 'free_float_shares / 1e8（单位亿股，非亿元）',
    },
  ]
  if (props.stock.circ_mv != null) {
    rows.push({ name: '流通市值', value: `${fmt(props.stock.circ_mv)} 亿元`, note: '仅展示，不参与默认过滤' })
  }
  const reason = SIZE_REASON[String(props.stock.size_reason || '')] || text(props.stock.size_reason)
  rows.push({
    name: 'size_ok',
    value: props.stock.size_ok === true ? '通过' : props.stock.size_ok === false ? '未通过' : '--',
    note: reason,
  })
  return rows
})

const bottomRows = computed(() => {
  const b = bottomD.value
  const boxSup = pick(props.stock.box_support, detail.value.support)
  const boxRes = pick(props.stock.box_resistance, detail.value.resistance)
  const rows: { name: string; value: string; note: string }[] = [
    {
      name: '箱体支撑',
      value: fmt(boxSup),
      note: b.box_frozen
        ? `冻结箱体下沿（锁定日 ${text(b.box_lock_date || props.stock.box_lock_date)}）`
        : 'bottom.support / 横盘下沿或恐慌日低点',
    },
    {
      name: '箱体阻力',
      value: fmt(boxRes),
      note: b.box_frozen ? '冻结箱体上沿（识别命中后锁定，失效前不随滚动窗抬升）' : 'bottom.resistance（黄金坑常无）',
    },
  ]
  const winHi = pick(b.window_high, props.stock.window_high, detail.value.window_high)
  const winLo = pick(b.window_low, props.stock.window_low, detail.value.window_low)
  if (winHi != null || winLo != null) {
    rows.push({
      name: '滚动窗高低',
      value: `${fmt(winLo)} ~ ${fmt(winHi)}`,
      note: '近 lookback 日最高/最低（仅参考，不进箱体硬逻辑）',
    })
  }
  if (b.range || b.panic) {
    const rg = b.range && typeof b.range === 'object' ? b.range : {}
    const pk = b.panic && typeof b.panic === 'object' ? b.panic : {}
    if (rg.reason || rg.vol_ok != null || rg.touch_ok != null) {
      rows.push({
        name: '横盘要点',
        value: text(
          rg.reason ||
            `量价${rg.vol_ok ? 'OK' : '否'} · 触底${rg.touch_ok ? 'OK' : '否'} · 触及日 ${(rg.touch_dates || []).join(',') || '--'}`
        ),
        note: '未命中时的 range 诊断',
      })
    }
    if (pk.reason || pk.panic_date || pk.reclaim != null) {
      rows.push({
        name: '恐慌要点',
        value: text(
          pk.reason ||
            `恐慌日 ${pk.panic_date || '--'} · 收复MA20 ${pk.reclaim == null ? '--' : pk.reclaim ? '是' : '否'}`
        ),
        note: '未命中时的 panic 诊断',
      })
    }
  } else {
    if (b.vol_ok != null || b.touch_ok != null) {
      rows.push({ name: '量价配合', value: b.vol_ok ? '通过' : '未通过', note: '上涨日均量 > 下跌日均量' })
      rows.push({
        name: '触底次数',
        value: b.touch_ok ? '通过' : '未通过',
        note: `触及日 ${(b.touch_dates || []).join('、') || '--'}`,
      })
      if (b.up_vol_avg != null) {
        rows.push({
          name: '涨/跌均量',
          value: `${fmt(b.up_vol_avg, 0)} / ${fmt(b.down_vol_avg, 0)}`,
          note: '横盘窗口量价',
        })
      }
    }
    if (b.panic_date) {
      rows.push({ name: '恐慌日', value: text(b.panic_date), note: '个股急跌且大盘同步走弱' })
      rows.push({
        name: '收复 MA20',
        value: b.reclaim == null ? '--' : b.reclaim ? '通过' : '未通过',
        note: `last ${fmt(b.last_close)} / MA20 ${fmt(b.ma20)}`,
      })
    }
    if (b.reason) rows.push({ name: '原因', value: text(b.reason), note: 'detail.bottom.reason' })
    if (b.range_pct != null) rows.push({ name: '振幅', value: fmt(b.range_pct, 4), note: 'range_pct' })
  }
  return rows
})

const entryRows = computed(() => {
  const crossUp = pick(entryD.value.cross_up, props.stock.cross_up)
  const shrinkOk = pick(entryD.value.shrink_ok, props.stock.shrink_ok)
  const expandOk = pick(entryD.value.expand_ok, props.stock.expand_ok)
  const marketOk = pick(entryD.value.market_ok, props.stock.market_ok) as boolean | null
  const marketRequired = pick(entryD.value.market_required, props.stock.market_required)
  const marketCumRet = pick(entryD.value.market_cum_ret, props.stock.market_cum_ret)
  const volumeRatio = pick(props.stock.volume_ratio, entryD.value.volume_ratio)
  const ma20 = pick(props.stock.ma20, entryD.value.ma20)
  const entryLow = pick(props.stock.entry_low, entryD.value.entry_low)
  const mktCumTxt =
    marketCumRet == null || marketCumRet === '' ? '--' : `${(Number(marketCumRet) * 100).toFixed(2)}%`
  const mktGate = marketRequired ? '硬筛' : '仅展示'
  let marketResult = '--'
  if (marketRequired) marketResult = ''
  else if (marketOk == null) marketResult = '--'
  else marketResult = marketOk ? '参考·达标' : '参考·未达标'
  const marketValue =
    marketOk == null ? '--' : marketOk ? `满足（${mktCumTxt}）` : `未满足（${mktCumTxt}）`
  return [
    {
      name: '筑底前置',
      rule: 'bottom_matched',
      value: props.stock.bottom_matched == null ? '--' : props.stock.bottom_matched ? '是' : '否',
      ok: props.stock.bottom_matched,
      resultText: '',
    },
    {
      name: '上穿 MA20',
      rule: '昨收≤昨MA20 且 今收>今MA20',
      value: `收 ${fmt(props.stock.close)} / MA20 ${fmt(ma20)}`,
      ok: crossUp,
      resultText: '',
    },
    {
      name: '底部缩量',
      rule: '近5均量/更早5均量 ≤ 0.7',
      value: shrinkOk == null ? '--' : shrinkOk ? '满足' : '未满足',
      ok: shrinkOk,
      resultText: '',
    },
    {
      name: '当日微放量',
      rule: '量比 ∈ [1.05, 1.8]',
      value: `量比 ${fmt(volumeRatio)}`,
      ok: expandOk,
      resultText: '',
    },
    {
      name: '大盘共振',
      rule: `上证近5日累计 ≤ -1%（${mktGate}）`,
      value: marketValue,
      ok: marketRequired ? marketOk : null,
      resultText: marketRequired ? '' : marketResult,
    },
    {
      name: '入场低点',
      rule: '信号日最低价（防守锚点）',
      value: fmt(entryLow),
      ok: null,
      resultText: '--',
    },
  ]
})

const defenseRows = computed(() => {
  const buf = props.stock.defense_buffer_pct
  return [
    { name: 'defense_high', value: fmt(props.stock.defense_high), note: '防守上沿（通常=入场低点）' },
    { name: 'defense_low', value: fmt(props.stock.defense_low), note: '防守下沿；收盘跌破则破位' },
    {
      name: 'buffer',
      value: buf == null ? '--' : `${(Number(buf) * 100).toFixed(1)}%`,
      note: 'defense_buffer_pct',
    },
  ]
})

const levelRows = computed(() => {
  const supports = Array.isArray(props.stock.support_levels) ? props.stock.support_levels : []
  const resists = Array.isArray(props.stock.resistance_levels) ? props.stock.resistance_levels : []
  if (!supports.length && !resists.length) return []
  return [
    { name: '阻力', value: resists.length ? resists.map((x: unknown) => fmt(x)).join('、') : '--' },
    { name: '支撑', value: supports.length ? supports.map((x: unknown) => fmt(x)).join('、') : '--' },
  ]
})

const hasPosition = computed(
  () => !!(position.value.next_action || position.value.message || position.value.probe_pct != null)
)
const showPosition = computed(() => hasPosition.value || !!supportConfirm.value)
</script>

<style scoped>
.sbbr-score-detail {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 4px 8px 8px;
  background: #f8fafc;
}
.sbbr-score-detail h4 {
  margin: 0 0 6px;
  font-size: 13px;
  color: #0f172a;
}
.meta-line {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  align-items: center;
  font-size: 13px;
  color: #334155;
}
.hint {
  margin: 0 0 6px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}
.conclusion {
  margin: 8px 0 0;
  font-size: 13px;
  color: #0f172a;
}
</style>
