<template>
  <div class="gms-detail-block p-2 text-sm">
    <div class="space-y-4">
      <div>
        <div class="font-semibold mb-2">【均值收敛态】得分明细</div>
        <el-table :data="accRows" border size="small" class="mb-2">
          <el-table-column prop="dim" label="维度" width="140" />
          <el-table-column prop="score" label="得分" width="72" />
          <el-table-column prop="judge" label="判定" width="100" />
          <el-table-column prop="rule" label="规则" min-width="240" />
        </el-table>
      </div>
      <div>
        <div class="font-semibold mb-2">【动量溢出态】得分明细</div>
        <el-table :data="momRows" border size="small" class="mb-2">
          <el-table-column prop="dim" label="维度" width="140" />
          <el-table-column prop="score" label="得分" width="72" />
          <el-table-column prop="judge" label="判定" width="100" />
          <el-table-column prop="rule" label="规则" min-width="240" />
        </el-table>
      </div>
      <div class="text-gray-700">
        <strong>综合</strong> 总分={{ scoreTotal }}；信号强度=总分/100
      </div>
      <div>
        <div class="font-semibold mb-2">计算指标细项</div>
        <el-table :data="indicatorRows" border size="small">
          <el-table-column prop="name" label="项目" width="180" />
          <el-table-column prop="val" label="数值" width="120" />
          <el-table-column prop="note" label="说明" min-width="200" />
        </el-table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { mergeGmsScoreDetail, gmsFmt, type GmsStockRow } from '@/utils/gmsScreeningFormat'

const props = defineProps<{ stock: GmsStockRow }>()

const sd = computed(() => mergeGmsScoreDetail(props.stock) as Record<string, any>)

const accS = computed(() =>
  sd.value.accumulation_s_threshold != null && !isNaN(Number(sd.value.accumulation_s_threshold))
    ? Number(sd.value.accumulation_s_threshold)
    : 85
)
const accA = computed(() =>
  sd.value.accumulation_a_threshold != null && !isNaN(Number(sd.value.accumulation_a_threshold))
    ? Number(sd.value.accumulation_a_threshold)
    : 70
)
const momFull = computed(() =>
  sd.value.momentum_full_threshold != null && !isNaN(Number(sd.value.momentum_full_threshold))
    ? Number(sd.value.momentum_full_threshold)
    : 90
)
const momBatch = computed(() =>
  sd.value.momentum_batch_threshold != null && !isNaN(Number(sd.value.momentum_batch_threshold))
    ? Number(sd.value.momentum_batch_threshold)
    : 80
)
const fzTiers = computed(() => (sd.value.acc_fz_tiers as number[]) || [2.5, 1.5])
const balTiers = computed(() => (sd.value.balance_tiers as number[]) || [0.01, 0.015])
const volShrink = computed(() => (sd.value.vol_shrink_tiers as number[]) || [0.6, 0.8])
const ratioD1Tiers = computed(() => (sd.value.ratio_d1_tiers as number[]) || [0.001, 0.03])
const volAttack = computed(() => (sd.value.vol_attack_tiers as number[]) || [2.0, 1.5])
const wAccFz = computed(() => (sd.value.weight_acc_fz != null ? Number(sd.value.weight_acc_fz) : 30))
const wAccBal = computed(() => (sd.value.weight_acc_balance != null ? Number(sd.value.weight_acc_balance) : 40))
const wAccVol = computed(() => (sd.value.weight_acc_volume != null ? Number(sd.value.weight_acc_volume) : 30))
const wMomD1 = computed(() => (sd.value.weight_mom_ratio_d1 != null ? Number(sd.value.weight_mom_ratio_d1) : 40))
const wMomDev = computed(() => (sd.value.weight_mom_deviation != null ? Number(sd.value.weight_mom_deviation) : 30))
const wMomVol = computed(() => (sd.value.weight_mom_volume != null ? Number(sd.value.weight_mom_volume) : 30))

const n = (v: unknown) => (v != null && !isNaN(Number(v)) ? Number(v).toFixed(1) : '--')

const accRows = computed(() => {
  const s = sd.value
  return [
    {
      dim: '时间耗散 F/Z',
      score: n(s.score_acc_fz),
      judge: s.acc_fz_judge || '—',
      rule: `权重${wAccFz.value}: ≥${fzTiers.value[0]}→满分; [${fzTiers.value[1]},${fzTiers.value[0]})→2/3`,
    },
    {
      dim: '引力粘合 |Δ/d|',
      score: n(s.score_acc_balance),
      judge: s.acc_balance_judge || '—',
      rule: `权重${wAccBal.value}: ≤${(balTiers.value[0] * 100).toFixed(1)}%→满分; ≤${(balTiers.value[1] * 100).toFixed(1)}%→1/2`,
    },
    {
      dim: '成交量缩 m₂₀/m',
      score: n(s.score_acc_volume),
      judge: s.acc_volume_judge || '—',
      rule: `权重${wAccVol.value}: ≤${volShrink.value[0]}→满分; (${volShrink.value[0]},${volShrink.value[1]}]→1/2`,
    },
    {
      dim: '均值收敛态小计',
      score: n(s.score_accumulation),
      judge: `判定: ${s.accumulation_grade || '—'}`,
      rule: `(≥${accS.value} S; ≥${accA.value} A)`,
    },
  ]
})

const momRows = computed(() => {
  const s = sd.value
  return [
    {
      dim: '盈亏反转 Δ/d₁',
      score: n(s.score_mom_ratio_d1),
      judge: s.mom_ratio_d1_judge || '—',
      rule: `权重${wMomD1.value}: (0,${(ratioD1Tiers.value[1] * 100).toFixed(1)}%]→满分; 刚过0→1/2`,
    },
    {
      dim: '推力支撑 d₂₀-d',
      score: n(s.score_mom_deviation),
      judge: s.mom_deviation_judge || '—',
      rule: `权重${wMomDev.value}: 站稳3日→满分; 仅当日→1/2; <0→-10`,
    },
    {
      dim: '攻击强度 m₂₀/m',
      score: n(s.score_mom_volume),
      judge: s.mom_volume_judge || '—',
      rule: `权重${wMomVol.value}: ≥${volAttack.value[0]}→满分; [${volAttack.value[1]},${volAttack.value[0]})→2/3`,
    },
    {
      dim: '动量溢出态小计',
      score: n(s.score_momentum),
      judge: `判定: ${s.momentum_grade || '—'}`,
      rule: `(≥${momFull.value}全速; ≥${momBatch.value}分批)`,
    },
  ]
})

const scoreTotal = computed(() =>
  sd.value.score_total != null ? Number(sd.value.score_total).toFixed(1) : '--'
)

const indicatorRows = computed(() => {
  const s = sd.value
  const d = s.d != null ? s.d : props.stock.d_ma20
  const deltaPct =
    s.delta != null && d != null && Number(d) !== 0 ? gmsFmt(Number(s.delta) / Number(d), 'pct') : '--'
  return [
    { name: 'd₁ (首日收盘价)', val: gmsFmt(s.d1, 'price'), note: '周期起点价格' + (s.d1_date ? '，交易日期 ' + s.d1_date : '') },
    { name: 'd₂₀ (末日收盘价)', val: gmsFmt(s.d20, 'price'), note: '周期末位/当日价格' + (s.d20_date ? '，交易日期 ' + s.d20_date : '') },
    { name: 'd (20日均价)', val: gmsFmt(d, 'price'), note: '周期均价' },
    { name: 'Δ (d₂₀ - d₁)', val: gmsFmt(s.delta, 'num'), note: '宏观位移' },
    { name: 'Δ/d', val: deltaPct, note: '宏观位移相对均价 (Δ/d)' },
    { name: '偏离率 (Δ/d₂₀)', val: gmsFmt(s.ratio_d20, 'pct'), note: '现价相对周期末价张力' },
    { name: '突变率 (Δ/d₁)', val: gmsFmt(s.ratio_d1, 'pct'), note: '现价相对周期起点位移' },
    { name: 'Δ₂₀/d', val: gmsFmt(s.ratio_d, 'pct'), note: '价格相对均线偏离率' },
    { name: 'Z (上涨天数)', val: gmsFmt(s.rising_days, 'int'), note: '多头天数' },
    { name: 'F (下跌天数)', val: gmsFmt(s.falling_days, 'int'), note: '空头天数' },
    { name: 'm (20日平均成交量)', val: gmsFmt(s.avg_volume_20d, 'vol'), note: '平均量' },
    { name: 'm₂₀ (当日成交量)', val: gmsFmt(s.current_volume, 'vol'), note: '当日成交量' },
    { name: '量比 (m₂₀/m)', val: gmsFmt(s.volume_ratio, 'ratio'), note: '放量/地量判断' },
    { name: 'F/Z (数方比)', val: gmsFmt(s.fz_ratio, 'ratio'), note: '蓄势判断' },
    { name: 'd₂₀ - d (价格vs均线)', val: gmsFmt(s.instant_deviation, 'num'), note: '价格相对均线偏离' },
  ]
})
</script>
