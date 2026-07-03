/** 将嵌套 config_params 转为选股表单扁平字段（与 backend config_to_flat_form 一致） */
export function configParamsToFlatForm(config: Record<string, unknown>): Record<string, number | undefined> {
  const scoring = (config.scoring || {}) as Record<string, number>
  const left = (config.left_buy || {}) as Record<string, number>
  const right = (config.right_buy || {}) as Record<string, number>
  const exit_ = (config.exit || {}) as Record<string, number>
  return {
    observation_period: (config.observation_period as number) ?? 20,
    ratio_d20_max: left.ratio_d20_abs_max,
    volume_ratio_max: left.volume_ratio_max,
    left_buy_min_accumulation: left.min_accumulation_score ?? 0,
    volume_ratio_min: right.volume_ratio_min ?? scoring.momentum_volume_ratio_min,
    accumulation_fz_min: scoring.accumulation_fz_min,
    balance_ratio_max: scoring.balance_ratio_max,
    watch_threshold: scoring.watch_threshold,
    alert_threshold: scoring.alert_threshold,
    overbought_ratio: exit_.overbought_ratio,
    accumulation_s_threshold: scoring.accumulation_s_threshold,
    accumulation_a_threshold: scoring.accumulation_a_threshold,
    momentum_full_threshold: scoring.momentum_full_threshold,
    momentum_batch_threshold: scoring.momentum_batch_threshold,
    instant_deviation_stable_days: scoring.instant_deviation_stable_days,
    weight_acc_fz: scoring.weight_acc_fz,
    weight_acc_balance: scoring.weight_acc_balance,
    weight_acc_volume: scoring.weight_acc_volume,
    weight_mom_ratio_d1: scoring.weight_mom_ratio_d1,
    weight_mom_deviation: scoring.weight_mom_deviation,
    weight_mom_volume: scoring.weight_mom_volume,
    ma60_flat_lookback_days: scoring.ma60_flat_lookback_days,
    ma60_flat_tol: scoring.ma60_flat_tol,
  }
}
