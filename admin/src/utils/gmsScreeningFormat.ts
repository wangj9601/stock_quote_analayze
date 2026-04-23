/** 与 frontend/js/screening.js 中 GMS 列与导出逻辑对齐 */

export interface GmsStockRow {
  symbol?: string
  code?: string
  name?: string
  signal_strength?: number
  score_total?: number
  buy_type?: string
  current_price?: number
  delta?: number
  falling_days?: number
  rising_days?: number
  d_ma20?: number
  ratio_relative?: number
  ratio_d20?: number
  ratio_d1?: number
  fz_ratio?: number
  current_change_percent?: number
  score_detail?: Record<string, unknown>
  left_buy_signal?: boolean
  right_buy_signal?: boolean
  ratio_d?: number
  avg_volume_20d?: number
  current_volume?: number
}

export function mergeGmsScoreDetail(stock: GmsStockRow): Record<string, unknown> {
  return {
    ratio_d: stock.ratio_d,
    avg_volume_20d: stock.avg_volume_20d,
    current_volume: stock.current_volume,
    ratio_d20: stock.ratio_d20,
    ratio_d1: stock.ratio_d1,
    delta: stock.delta,
    d: stock.d_ma20,
    rising_days: stock.rising_days,
    falling_days: stock.falling_days,
    fz_ratio: stock.fz_ratio,
    instant_deviation: (stock as any).instant_deviation,
    volume_ratio: (stock as any).volume_ratio,
    ...(stock.score_detail || {}),
  }
}

export function gmsSignalStrength(stock: GmsStockRow, sd: Record<string, unknown>): number {
  let sig =
    stock.signal_strength != null ? stock.signal_strength : stock.score_total != null ? stock.score_total / 100 : 0
  if (sig === 0 && sd.score_total != null && Number(sd.score_total) > 0) {
    sig = Number(sd.score_total) / 100
  }
  return sig
}

export function gmsFmt(v: unknown, type: string): string {
  if (v == null || (typeof v === 'number' && isNaN(v))) return '--'
  if (type === 'pct') return (Number(v) * 100).toFixed(2) + '%'
  if (type === 'int') return String(Math.round(Number(v)))
  if (type === 'vol') {
    const n = Number(v)
    return n >= 10000 ? (n / 10000).toFixed(2) + '万手' : Number(v).toFixed(0) + '手'
  }
  if (type === 'price') return typeof v === 'number' ? v.toFixed(2) : String(v)
  if (type === 'ratio') return typeof v === 'number' ? v.toFixed(2) : String(v)
  if (type === 'num') return typeof v === 'number' ? v.toFixed(4) : String(v)
  return String(v)
}

export function buildGmsScoreDetailCommentText(sdIn: Record<string, unknown> | null | undefined): string {
  if (!sdIn || typeof sdIn !== 'object') return '—'
  const sd = sdIn
  const n = (v: unknown) => (v != null && !isNaN(Number(v)) ? Number(v).toFixed(1) : '--')
  const accS =
    sd.accumulation_s_threshold != null && !isNaN(Number(sd.accumulation_s_threshold))
      ? Number(sd.accumulation_s_threshold)
      : 85
  const accA =
    sd.accumulation_a_threshold != null && !isNaN(Number(sd.accumulation_a_threshold))
      ? Number(sd.accumulation_a_threshold)
      : 70
  const momFull =
    sd.momentum_full_threshold != null && !isNaN(Number(sd.momentum_full_threshold))
      ? Number(sd.momentum_full_threshold)
      : 90
  const momBatch =
    sd.momentum_batch_threshold != null && !isNaN(Number(sd.momentum_batch_threshold))
      ? Number(sd.momentum_batch_threshold)
      : 80
  const fzTiers = (sd.acc_fz_tiers as number[]) || [2.5, 1.5]
  const balTiers = (sd.balance_tiers as number[]) || [0.01, 0.015]
  const volShrink = (sd.vol_shrink_tiers as number[]) || [0.6, 0.8]
  const ratioD1Tiers = (sd.ratio_d1_tiers as number[]) || [0.001, 0.03]
  const volAttack = (sd.vol_attack_tiers as number[]) || [2.0, 1.5]
  const wAccFz = sd.weight_acc_fz != null && !isNaN(Number(sd.weight_acc_fz)) ? Number(sd.weight_acc_fz) : 30
  const wAccBal = sd.weight_acc_balance != null && !isNaN(Number(sd.weight_acc_balance)) ? Number(sd.weight_acc_balance) : 40
  const wAccVol = sd.weight_acc_volume != null && !isNaN(Number(sd.weight_acc_volume)) ? Number(sd.weight_acc_volume) : 30
  const wMomD1 = sd.weight_mom_ratio_d1 != null && !isNaN(Number(sd.weight_mom_ratio_d1)) ? Number(sd.weight_mom_ratio_d1) : 40
  const wMomDev = sd.weight_mom_deviation != null && !isNaN(Number(sd.weight_mom_deviation)) ? Number(sd.weight_mom_deviation) : 30
  const wMomVol = sd.weight_mom_volume != null && !isNaN(Number(sd.weight_mom_volume)) ? Number(sd.weight_mom_volume) : 30
  const lines: string[] = []
  lines.push('【均值收敛态】得分明细')
  lines.push('维度\t得分\t判定\t规则')
  lines.push(
    `时间耗散 F/Z\t${n(sd.score_acc_fz)}\t${String(sd.acc_fz_judge || '—')}\t权重${wAccFz}: ≥${fzTiers[0]}→满分; [${fzTiers[1]},${fzTiers[0]})→2/3`
  )
  lines.push(
    `引力粘合 |Δ/d|\t${n(sd.score_acc_balance)}\t${String(sd.acc_balance_judge || '—')}\t权重${wAccBal}: ≤${(balTiers[0] * 100).toFixed(1)}%→满分; ≤${(balTiers[1] * 100).toFixed(1)}%→1/2`
  )
  lines.push(
    `成交量缩 m₂₀/m\t${n(sd.score_acc_volume)}\t${String(sd.acc_volume_judge || '—')}\t权重${wAccVol}: ≤${volShrink[0]}→满分; (${volShrink[0]},${volShrink[1]}]→1/2`
  )
  lines.push(`均值收敛态小计\t${n(sd.score_accumulation)}\t判定: ${String(sd.accumulation_grade || '—')} (≥${accS} S; ≥${accA} A)`)
  lines.push('')
  lines.push('【动量溢出态】得分明细')
  lines.push('维度\t得分\t判定\t规则')
  lines.push(
    `盈亏反转 Δ/d₁\t${n(sd.score_mom_ratio_d1)}\t${String(sd.mom_ratio_d1_judge || '—')}\t权重${wMomD1}: (0,${(ratioD1Tiers[1] * 100).toFixed(1)}%]→满分; 刚过0→1/2`
  )
  lines.push(
    `推力支撑 d₂₀-d\t${n(sd.score_mom_deviation)}\t${String(sd.mom_deviation_judge || '—')}\t权重${wMomDev}: 站稳3日→满分; 仅当日→1/2; <0→-10`
  )
  lines.push(
    `攻击强度 m₂₀/m\t${n(sd.score_mom_volume)}\t${String(sd.mom_volume_judge || '—')}\t权重${wMomVol}: ≥${volAttack[0]}→满分; [${volAttack[1]},${volAttack[0]})→2/3`
  )
  lines.push(`动量溢出态小计\t${n(sd.score_momentum)}\t判定: ${String(sd.momentum_grade || '—')} (≥${momFull}全速; ≥${momBatch}分批)`)
  lines.push('')
  lines.push('综合  总分=' + (sd.score_total != null ? Number(sd.score_total).toFixed(1) : '--') + '；信号强度=总分/100')
  lines.push('说明  总分=max(均值收敛态小计,动量溢出态小计)，非两模块相加')
  lines.push('')
  lines.push('计算指标细项')
  lines.push('d₁ (首日收盘价)\t' + gmsFmt(sd.d1, 'price') + '\t周期起点价格' + (sd.d1_date ? '，交易日期 ' + String(sd.d1_date) : ''))
  lines.push('d₂₀ (末日收盘价)\t' + gmsFmt(sd.d20, 'price') + '\t周期末位/当日价格' + (sd.d20_date ? '，交易日期 ' + String(sd.d20_date) : ''))
  lines.push('d (20日均价)\t' + gmsFmt(sd.d, 'price') + '\t周期均价')
  lines.push('Δ (d₂₀ - d₁)\t' + gmsFmt(sd.delta, 'num') + '\t宏观位移')
  lines.push(
    'Δ/d\t' +
      (sd.delta != null && sd.d != null && Number(sd.d) !== 0 ? gmsFmt(Number(sd.delta) / Number(sd.d), 'pct') : '--') +
      '\t宏观位移相对均价'
  )
  lines.push(
    'Δ/d₂₀（宏观位移/收盘价）\t' + gmsFmt(sd.ratio_d20, 'pct') + '\t左侧买点用|Δ/d₂₀|；≠ 均线乖离'
  )
  lines.push('Δ/d₁（突变率）\t' + gmsFmt(sd.ratio_d1, 'pct') + '\t现价相对周期起点位移')
  lines.push('Δ₂₀/d（均线乖离）\t' + gmsFmt(sd.ratio_d, 'pct') + '\t(d₂₀−d)/d，非左侧判定用 Δ/d₂₀')
  lines.push('Z (上涨天数)\t' + gmsFmt(sd.rising_days, 'int') + '\t多头天数')
  lines.push('F (下跌天数)\t' + gmsFmt(sd.falling_days, 'int') + '\t空头天数')
  lines.push('m (20日平均成交量)\t' + gmsFmt(sd.avg_volume_20d, 'vol') + '\t平均量')
  lines.push('m₂₀ (当日成交量)\t' + gmsFmt(sd.current_volume, 'vol') + '\t当日成交量')
  lines.push('量比 (m₂₀/m)\t' + gmsFmt(sd.volume_ratio, 'ratio') + '\t放量/地量判断')
  lines.push('F/Z (数方比)\t' + gmsFmt(sd.fz_ratio, 'ratio') + '\t蓄势判断')
  lines.push('d₂₀ - d (价格vs均线)\t' + gmsFmt(sd.instant_deviation, 'num') + '\t价格相对均线偏离')
  return lines.join('\n')
}

export function gmsCsvScoreDetailStr(stock: GmsStockRow): string {
  const sd = mergeGmsScoreDetail(stock)
  const fmt = (v: unknown) => (v != null && typeof v === 'number' && !isNaN(v) ? v.toFixed(1) : '--')
  const accPart =
    sd.score_accumulation != null
      ? `蓄势${fmt(sd.score_accumulation)}(引力${fmt(sd.score_acc_fz)}+平衡${fmt(sd.score_acc_balance)}+量缩${fmt(sd.score_acc_volume)})${sd.accumulation_grade || ''}`
      : '蓄势--'
  const momPart =
    sd.score_momentum != null
      ? `动量${fmt(sd.score_momentum)}(推力${fmt(sd.score_mom_ratio_d1)}+支撑${fmt(sd.score_mom_deviation)}+攻击${fmt(sd.score_mom_volume)})${sd.momentum_grade || ''}`
      : '动量--'
  return `总分${fmt(sd.score_total)} ${accPart} ${momPart}`
}
