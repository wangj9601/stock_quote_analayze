# CSB 低位狭长通道磨底 + 放量突破 — 业务规则与信号计算规则

> 策略代号 **CSB**（Channel Squeeze Breakout），前端名称为「**通道突破**」。
> 本文档与代码一一对应，描述业务直觉、判定规则、评分口径与防守出场规则。
> 参数默认值以 `backend_core/strategies/csb/config.py::get_default_csb_config()` 为准。

---

## 1. 业务直觉

在一段 **年线走平或向上** 的中期格局下，股价经过较长时间横盘，使 **MA5/MA10/MA20/MA60 四条均线高度粘合**，形成一条狭长、低波动的「通道」。此时：

- 多头成本与空头成本高度一致，**抛压被反复消化**；
- 期间对通道下轨出现 **≥2 次独立回踩**，且伴随 **地量**（缩量磨底）；
- 其间若出现 **Spring（假跌破下轨后快速收回）**，则视为洗盘结束的强信号。

当满足上述「磨底」条件（**SETUP**）后，策略给出三类买点：

1. **买点1 · PROBE（试仓）**：下轨附近缩量止跌（高下影）或当日 Spring，试仓。
2. **买点2 · BREAKOUT（突破）**：换手显著放大的 **实体阳线** 收盘突破通道上轨，主仓加仓。
3. **买点3 · LPS（回踩确认）**：突破后缩量回踩上轨/突破阳线中位而不破，转强时补仓。

买入后以 **假突破 / 基准止损 / 派发 / 均线-波段阶梯跟踪** 进行纪律化防守。

---

## 2. 术语与数据前提

| 名称 | 含义 |
|------|------|
| 通道（channel） | 由 MA5/10/20/60 构成：上轨=四者最大值，下轨=四者最小值 |
| 粘合带宽 `squeeze_pct` | `(上轨 − 下轨) / 收盘价`，越小越粘合 |
| 粘合天数 `squeeze_days` | 自最新日向前，连续满足 `squeeze_pct ≤ ma_squeeze_pct` 的天数 |
| HH20 | 近 20 日最高价（默认不含当日） |
| Spring | 盘中跌破下轨（幅度在 1%~2%）但收盘收回下轨之上，且极度缩量 |
| 地量 | 近 5 日均量 / 近 60 日均量 ≤ 阈值 |
| 换手放大 | 当日换手率 / 近 20 日均换手率 |

**数据前提**

- `stock_basic_info`：6 位 A 股代码；**剔除名称含 `ST`**；`collect_enabled` 为真或空视为可采集。
- `historical_quotes`：日线 OHLCV + 换手率；**成交量 ≤ 0 的 K 线被丢弃**。
- 序列一律 **时间正序**（早 → 晚），最新一根为「当日」。
- 至少 `min_listing_bars`（默认 **250**）根 K 线才参与判定。

---

## 3. SETUP（磨底条件）

`detect_setup()` 需 **全部满足** 以下 5 项：

| # | 条件 | 规则 | 默认参数 |
|---|------|------|----------|
| 1 | 通道粘合 | 最新日 `squeeze_pct ≤ ma_squeeze_pct` 且 `squeeze_days ≥ squeeze_days` | `ma_squeeze_pct=0.04`、`squeeze_days=15` |
| 2 | 年线防守 | MA250 的 20 日归一化斜率 `≥ slope_min`（走平或向上） | `ma250.slope_min=-0.0005` |
| 3 | 换手初筛 | 近 20 日均换手率 `≥ min_avg_20`（%） | `turnover.min_avg_20=1.0` |
| 4 | 独立回踩 | 通道下轨支撑测试次数 `≥ min_touches` | `min_touches=2`、`touch_tol_pct=0.015`、`touch_leave_pct=0.03`、`touch_lookback=60` |
| 5 | 地量 | 近 5 日均量/近 60 日均量 `≤ dry_vol_ratio`，且换手同口径不超阈值 | `dry_vol.dry_vol_ratio=0.55`、`lookback_short=5`、`lookback_long=60` |

**要点说明**

- **年线只判斜率，不看是否站上**：`close ≥ MA250` 不能替代斜率条件；年线下行（斜率 < `slope_min`）直接否决。
- **独立回踩计数**：连续贴轨只计 1 次；必须「离开下轨（收盘 ≥ 下轨×(1+`touch_leave_pct`)）后再回来」才计下一次。收盘 **有效跌破下轨（深于 Spring 上限）** 的触碰 **不计入** 支撑测试。
- **地量缺换手不阻断**：若 `turnover_rate` 缺失，换手比这一项视为通过，仅按成交量比判定。
- 若 `len(bars) < 60`，通道判定直接返回 `insufficient_bars`。

满足 SETUP 但未触发任何买点时，信号类型回落为 **`CSB_SETUP`（观察）**。

---

## 4. 三大买点

`detect_entry()` 优先级：**BREAKOUT → LPS → PROBE**。

### 4.1 买点1 · PROBE（缩量止跌试仓）

前提：`setup_ok = True`。需同时满足：

- **贴近下轨** `near_lower`：当日 `low ≤ 下轨×(1+touch_tol_pct)` 或 `close ≤ 下轨×(1+touch_tol_pct)`；
- 且满足以下 **任一**：
  - **缩量 + 止跌形态**：近 5 日均量/近 20 日均量 `≤ vol_ratio_probe_max`(0.8)，且当日 K 线为「高下影止跌」——`下影 ≥ 实体`；或为 **小阴线**（跌幅 ≤ 2%）且 `下影 ≥ 实体×0.5`。**普通阳线（无长下影）不再自动通过**；
  - **当日 Spring**：当日盘中假跌破下轨后收回且极度缩量。

参数：`entry.vol_ratio_probe_max=0.8`。

### 4.2 买点2 · BREAKOUT（放量实体阳线突破上轨）

前提：`setup_ok = True`，且存在通道上轨。需 **全部满足**：

| 条件 | 规则 | 默认 |
|------|------|------|
| 换手放大 | 当日换手 / 近 20 日均换手 `≥ vol_expand_mult` | `2.0` |
| 实体阳线 | 实体涨幅 `≥ body_min_pct` 且 `close > open` | `body_min_pct=0.03` |
| 上影受限 | 上影 / 实体 `≤ upper_shadow_max_ratio` | `0.20` |
| 价格突破 | `close ≥ 上轨 × (1 + break_pct)` | `break_pct=0.02` |

**派发陷阱（distribution_trap）**：若换手已放大，但 **实体不足** 或 **上影过长**，判定为派发陷阱，**否决** 买点二，`reason=distribution_trap`。
量能口径以 **换手率** 为准（`expand_basis=turnover`）。

### 4.3 买点3 · LPS（突破后缩量回踩确认）

在最近 `lps_window`（默认 **3**）个交易日内，若某日出现过 **BREAKOUT**，且当日满足：

| 条件 | 规则 | 默认 |
|------|------|------|
| 缩量 | 当日量 `≤ 突破日量 × lps_vol_ratio_max`（量缺失时用换手比） | `0.80` |
| 回踩支撑 | `low ≤ 上轨×(1+touch_tol_pct)` 或 `low ≤ 突破阳线实体中位×(1+touch_tol_pct)` | — |
| 站稳 | `close ≥ 上轨` | — |
| 转强 | `close > open` | — |

### 4.4 建议仓位

| 信号 | 建议仓位 | 默认 |
|------|----------|------|
| `CSB_PROBE` | `position.probe_pct` | 0.12 |
| `CSB_BREAKOUT` | `position.breakout_add_pct` | 0.25 |
| `CSB_LPS` | `position.lps_add_pct` | 0.12 |

`BUY_SIGNAL_TYPES = {CSB_PROBE, CSB_BREAKOUT, CSB_LPS}` 即为「买入信号」集合。

---

## 5. 综合评分（0~100）

`compute_score_detail()` 分项：

| 分项 | 公式 | 上限 |
|------|------|------|
| 粘合天数 | `min(25, squeeze_days × 1.2)` | 25 |
| 粘合天数加权 | `squeeze_days ≥ premium.squeeze_days_min`(+`squeeze_bonus`) | 8（默认 30 日） |
| 粘合带宽 | `max(0, 15 × (1 − squeeze_pct / 0.06))` | 15 |
| 回踩次数 | `min(15, touch_count × 4)` | 15 |
| 地量 | 成立 +10 | 10 |
| 换手 | 20 日均换手达标 +10 | 10 |
| Spring | 近端出现 Spring +`premium.spring_bonus` | 6 |
| 买点类型 | `PROBE +12 / LPS +16 / BREAKOUT +20` | 20 |
| 放量倍数 | 仅 BREAKOUT：`min(10, vol_expand_mult)` | 10 |

`total = min(100, 各项之和)`；`min_score`（默认 **60**）为入选门槛。

> 示例：粘合 19 日、带宽 0.022、回踩 4 次、地量成立、换手达标、PROBE 信号
> → `22.8 + 9.5 + 15 + 10 + 10 + 12 = 79.3`。

---

## 6. 防守出场规则

### 6.1 假突破（全出场，最高优先级）

突破后 **T+1 ~ T+`false_break_days`**（默认 **3**）内任一日 **收盘 < 通道上轨** → 假突破信号 `CSB_FALSE_BREAK`，`exit_reason=false_break`。

### 6.2 基准止损

以 **买点日的 `entry_low`（当日最低价）** 为基准，止损价 `= entry_low × (1 − stop_buffer_pct)`（默认缓冲 0，即跌破买点日最低价收盘止损）。
`risk_exit` 模式另加 **固定百分比止损**（默认 8%）。

### 6.3 派发减仓

浮盈 `≥ distribution_min_gain`（默认 **8%**）后，出现以下任一：

- **天量滞涨**：换手或量 `≥ 20 日均值 × distribution_turnover_mult`（默认 2.0），但 `实体 < distribution_body_max`（0.03）或 `上影 > distribution_shadow_max`（0.20）；
- **放量跌破 MA10**：`close < MA10` 且同时满足放量条件。

→ `CSB_DISTRIBUTE`，`exit_reason=distribution`。

### 6.4 阶梯跟踪（浮盈保护）

浮盈达到 `trail_arm_gain`（默认 **3%**）后 **启用**：
跟踪线取 **已确认波段低点**（左右各 `swing_window` 根更高）、**MA10**、**MA20** 中 **位于收盘价之下** 的 **最高者**，且 **只上移不下移**（ratchet）。
收盘跌破跟踪线 → `CSB_TRAIL`，`exit_reason=ma_trail`。

### 6.5 出场模式对照

| 模式 | 出场规则 |
|------|----------|
| `hit_rate` | **不止损**；信号次日开盘入场，观察 `horizon_days`，按前瞻最高价是否触及目标涨幅统计命中率 |
| `risk_exit` | 基准止损 + 固定百分比止损（默认 8%） |
| `structure_exit` | 假突破 → 基准止损 → 派发 → MA10/MA20 + 波段阶梯跟踪 → 到期 |

---

## 7. 信号类型枚举

| 类型 | 含义 |
|------|------|
| `CSB_SETUP` | 磨底条件成立（观察） |
| `CSB_PROBE` | 买点1 缩量止跌试仓 |
| `CSB_BREAKOUT` | 买点2 放量突破上轨 |
| `CSB_LPS` | 买点3 突破后缩量回踩确认 |
| `CSB_FALSE_BREAK` | 突破后三日收盘跌回上轨下 |
| `CSB_STOP` | 基准/百分比止损 |
| `CSB_TRAIL` | 均线-波段阶梯跟踪卖出 |
| `CSB_DISTRIBUTE` | 主升后放量派发 |

---

## 8. 默认参数一览

```jsonc
{
  "channel":  { "ma_squeeze_pct": 0.04, "squeeze_days": 15, "touch_tol_pct": 0.015,
                "min_touches": 2, "touch_leave_pct": 0.03, "touch_lookback": 60 },
  "ma250":    { "slope_min": -0.0005 },
  "spring":   { "pierce_min_pct": 0.01, "pierce_max_pct": 0.02, "vol_ratio_max": 0.55 },
  "turnover": { "min_avg_20": 1.0 },
  "dry_vol":  { "dry_vol_ratio": 0.55, "lookback_short": 5, "lookback_long": 60 },
  "entry":    { "vol_ratio_probe_max": 0.8, "vol_expand_mult": 2.0, "break_pct": 0.02,
                "body_min_pct": 0.03, "upper_shadow_max_ratio": 0.20,
                "lps_window": 3, "lps_vol_ratio_max": 0.80 },
  "position": { "probe_pct": 0.12, "breakout_add_pct": 0.25, "lps_add_pct": 0.12 },
  "defense":  { "false_break_days": 3, "trail_ma": 20, "trail_ma_fast": 10,
                "stop_buffer_pct": 0.0, "trail_arm_gain": 0.03, "swing_window": 2,
                "distribution_min_gain": 0.08, "distribution_turnover_mult": 2.0,
                "distribution_body_max": 0.03, "distribution_shadow_max": 0.20 },
  "scan":     { "history_bars": 280, "max_results": 0, "batch_size": 200 },
  "backtest": { "horizon_days": 10, "target_pct": 0.10, "commission_bps": 5, "slippage_bps": 5 },
  "premium":  { "squeeze_days_min": 30, "squeeze_bonus": 8.0, "spring_bonus": 6.0,
                "min_touches": 3, "vol_expand_mult": 2.5 },
  "min_score": 60.0,
  "min_listing_bars": 250,
  "signal_quality_mode": "standard"
}
```

> **参数版本升级（v1 → v2 运行时兼容）**：`_apply_v2_runtime` 在读取旧配置时，会把工厂旧值 `entry.upper_shadow_max_ratio=0.30 → 0.20`、`premium.squeeze_days_min=20 → 30` 自动升级；仅改写「恰好等于旧工厂值」的记录，用户手动改过的数值会保留。

---

## 9. 信号质量模式

- `standard`：过 SETUP 门槛的入场（默认）。
- `premium`：更严口径（`premium` 节：粘合 ≥30 日、回踩 ≥3 次、放量 ≥2.5 倍等），用于回测/精选对照。
