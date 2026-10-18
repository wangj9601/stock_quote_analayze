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

买入后以 **假突破 / 基准止损 / 通道失效 / 派发 / 阶梯跟踪 / 到期平仓** 进行纪律化防守。

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
| 5 | 地量 | **不含信号日**：近 5 日均量/近 60 日均量 `≤ dry_vol_ratio`，且换手同口径不超阈值 | `dry_vol.dry_vol_ratio=0.55`、`lookback_short=5`、`lookback_long=60` |

**要点说明**

- **年线只判斜率，不看是否站上**：`close ≥ MA250` 不能替代斜率条件；年线下行（斜率 < `slope_min`）直接否决。
- **独立回踩计数**：连续贴轨只计 1 次；必须「离开下轨（收盘 ≥ 下轨×(1+`touch_leave_pct`)）后再回来」才计下一次。收盘 **有效跌破下轨（深于 Spring 上限）** 的触碰 **不计入** 支撑测试。每次计入的回踩写入 `touch_episodes`：`start_date` 为计入当天，`end_date` 为离开下轨之前的最后一天。选股表展示次数，明细列出各段起止日期。已落库的旧 trace 只有次数，重算后才有区间。
- **地量缺换手不阻断**：若 `turnover_rate` 缺失，换手比这一项视为通过，仅按成交量比判定。
- **地量不含信号日**：蓄势期地量在 `bars[:-1]` 上计算。信号日换手放大（BREAKOUT）不得否决 `setup_ok`，否则买点2/LPS 与 SETUP 同日互斥。
- **当前默认基线**：`min_score=80`；PROBE 基准止损缓冲 **2%**、连续 **3** 日；通道失效缓冲 **1.5%**、连续 **3** 日；利润保护见 6.5。这就是原先「出场 v3」加上分≥80，已写进 `get_default_csb_config()`。
- **同 config_id 升级**：`_apply_v2_runtime` 只改写已知工厂旧值（`min_score=60`、PROBE 止损 1%/2 日、通道失效缓冲 0.5% 或确认 2 日、上影 0.30、粘合加权 20 日）。用户改成其它数值的保留。trace 按实际得分落库，读选股/回测时再按 `min_score` 过滤，**只改分数不必重跑预计算**。通道、买点、出场规则变了才需要重算。
- 回测任务级预设见第 10 节。
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

前提：`setup_ok = True`（**优先当日；若当日不成立则回退前一交易日 setup**，通道上轨取该 setup），且存在通道上轨。需 **全部满足**：

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

LPS 在回测里很少单独成笔，原因是规则和记账方式，不是信号被关掉：

- 当天若已是 BREAKOUT，`detect_entry()` 不再记 LPS。
- `detect_lps` 从最近一日往前找突破。最近一次突破存在、但当日 LPS 条件不成立时，直接返回，不再看窗口里更早的突破日。
- 回测同一只股票在出场日之前不开新仓。突破单中位持有约 7 日，LPS 窗口只有 3 日，窗口内的补仓信号会被冷却跳过。LPS 只有在突破单已经出场、或突破日本身没有入选时，才可能单独出现。
- LPS 类型分 +16，且没有 BREAKOUT 的放量加分（最多 +10）。同样的蓄势结构，LPS 往往到不了默认分≥80。

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
| 放量倍数 | 仅 BREAKOUT：达到 `entry.vol_expand_mult` 记 10 分，`min(10, 10×倍数/阈值)`，超过阈值不再加分 | 10 |

`total = min(100, 各项之和)`；`min_score`（默认 **80**）为入选门槛。trace 仍保存门槛以下的买点，选股和回测读取时再筛。

> 示例：粘合 19 日、带宽 0.022、回踩 4 次、地量成立、换手达标、PROBE 信号
> → `22.8 + 9.5 + 15 + 10 + 10 + 12 = 79.3`。

---

## 6. 防守出场规则

入场价是信号日 **下一根 K 线开盘价**。信号日本身不做出场判断。观察期默认 `horizon_days = 10` 个交易日。结构出场同一天只记最先触发的一条，判断用 **收盘价**。

回测明细「出场原因」与代码枚举对照：

| 出场原因（导出） | `exit_reason` | 适用 |
|------|------|------|
| 假突破 | `false_break` | 仅 BREAKOUT |
| 基准止损 | `baseline_stop` | 全部买点 |
| 通道失效 | `channel_fail` | 仅 PROBE |
| 派发离场 | `distribution` | 全部买点 |
| 阶梯跟踪止损 | `ma_trail` | 全部买点 |
| 到期平仓 | `horizon_end` | 全部买点 |
| 价格止损 | `price_stop` | 仅 `risk_exit` |

### 6.1 假突破（全出场，最高优先级）

仅 **BREAKOUT**。突破后 **T+1 ~ T+`false_break_days`**（默认 **3**）内任一日 **收盘 < 通道上轨** → `CSB_FALSE_BREAK`，`exit_reason=false_break`（导出「假突破」）。PROBE 入场本就在通道内，LPS 是回踩上轨，这两类不做「三日不重回上轨」。

### 6.2 基准止损

止损锚是信号里的 `entry_low`：PROBE、BREAKOUT 取 **信号日最低价**；LPS 取 **当初突破那根 K 线的最低价**。

- BREAKOUT、LPS，以及 `risk_exit` 的全部买点：止损价 `= entry_low × (1 − stop_buffer_pct)`，默认缓冲 **0**。收盘价小于或等于止损价，当天离场。
- 结构出场里的 PROBE：止损价 `= entry_low × (1 − probe_stop_buffer_pct)`，默认再下移 **2%**，并且要 **连续 `probe_stop_confirm_days` 天**（默认 **3**）收盘都在止损价之下才离场。

→ `CSB_STOP`，`exit_reason=baseline_stop`（导出「基准止损」）。

`risk_exit` 在基准止损之后另加 **固定百分比止损**：收盘价小于或等于入场价的 **92%**（默认下跌 8%）→ `exit_reason=price_stop`（导出「价格止损」）。该模式不用 PROBE 的缓冲和连续确认。

### 6.3 通道失效（仅 PROBE）

结构出场在基准止损之后检查。收盘价 **连续 `channel_fail_confirm_days` 天**（默认 **3**）都小于或等于 `通道下轨 × (1 − channel_fail_buffer_pct)`（默认下移 **1.5%**），在确认日收盘离场。用来避免下轨被一根 K 线刺穿就卖出。

→ `CSB_STOP`，`exit_reason=channel_fail`（导出「通道失效」）。BREAKOUT、LPS 不走这条。

### 6.4 派发离场

浮盈 `≥ distribution_min_gain`（默认 **8%**，按当日收盘相对入场价）后，成交量或换手率达到近 20 日正值均值的 `distribution_turnover_mult` 倍（默认 **2.0**），再满足以下任一：

- **天量滞涨**：实体涨幅 `< distribution_body_max`（默认 0.03；阴线实体为负，也算不足），或上影线长度 `> 实体 × distribution_shadow_max`（默认 0.20）；
- **放量跌破 MA10**：`close < MA10`（周期 `trail_ma_fast`，默认 10）。

→ `CSB_DISTRIBUTE`，`exit_reason=distribution`（导出「派发离场」）。

### 6.5 阶梯跟踪止损（浮盈保护）

此前某根 K 线的最高价曾经达到入场价的 `1 + trail_arm_gain`（默认 **1.03**）之后才武装。当天新高留到收盘后才计入，避免同一根 K 线冲高回落就离场。

武装之后，跟踪线在下面四者中取 **仍低于当日收盘** 的最高者，并且 **只上移**、不低于武装价（入场价 × 1.03）：

- 已确认波段低点（左右各 `swing_window` 根，默认 2，低点都更高）
- MA10（`trail_ma_fast`）
- MA20（`trail_ma`）
- 武装价

收盘价回到武装价或以下，或低于这条跟踪线 → `CSB_TRAIL`，`exit_reason=ma_trail`（导出「阶梯跟踪止损」）。

前序最高价相对入场价的浮盈达到 `profit_lock_gain`（默认 **10%**）后进入利润保护，仍记为 `ma_trail`，明细里 `trail_kind=profit_lock`：

- 跟踪地板抬到入场价 × `(1 + profit_lock_floor_pct)`（默认 **+5%**），且不低于原来的武装价；
- 跟踪线只保留快线 MA10，不再用 MA20；
- 收盘价相对前序最高价回撤达到 `profit_lock_giveback_pct`（默认 **8%**）也离场。

当日新高仍留到收盘后才计入前序最高价。利润保护在派发之后判断，派发条件先满足时不会走到这里。

### 6.6 到期平仓

观察期内以上规则都没触发，用窗口最后一根 K 线的收盘价离场。`exit_reason=horizon_end`（导出「到期平仓」）。`hit_rate` 模式不止损，同样持有到期，按末日收盘计盈亏；目标涨幅只统计期间最高价是否碰到，不提前卖出。

### 6.7 出场模式对照

| 模式 | 出场规则 |
|------|----------|
| `hit_rate` | **不止损**；信号次日开盘入场，观察 `horizon_days`，按前瞻最高价是否触及目标涨幅统计命中率，到期平仓 |
| `risk_exit` | 基准止损（缓冲 0、当日确认）→ 固定百分比止损（默认 8%）→ 到期平仓 |
| `structure_exit` | 假突破（仅 BREAKOUT）→ 基准止损 → 通道失效（仅 PROBE）→ 派发离场 → 阶梯跟踪止损（含利润保护）→ 到期平仓 |

---

## 7. 信号类型枚举

| 类型 | 含义 |
|------|------|
| `CSB_SETUP` | 磨底条件成立（观察） |
| `CSB_PROBE` | 买点1 缩量止跌试仓 |
| `CSB_BREAKOUT` | 买点2 放量突破上轨 |
| `CSB_LPS` | 买点3 突破后缩量回踩确认 |
| `CSB_FALSE_BREAK` | 突破后三日收盘跌回上轨下（假突破） |
| `CSB_STOP` | 基准止损、通道失效或百分比止损 |
| `CSB_TRAIL` | 阶梯跟踪止损 |
| `CSB_DISTRIBUTE` | 主升后放量派发离场 |

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
                "stop_buffer_pct": 0.0, "probe_stop_buffer_pct": 0.02,
                "probe_stop_confirm_days": 3, "trail_arm_gain": 0.03, "swing_window": 2,
                "profit_lock_gain": 0.10, "profit_lock_floor_pct": 0.05,
                "profit_lock_giveback_pct": 0.08,
                "channel_fail_buffer_pct": 0.015, "channel_fail_confirm_days": 3,
                "distribution_min_gain": 0.08, "distribution_turnover_mult": 2.0,
                "distribution_body_max": 0.03, "distribution_shadow_max": 0.20 },
  "scan":     { "history_bars": 280, "max_results": 0, "batch_size": 200 },
  "backtest": { "horizon_days": 10, "target_pct": 0.10, "commission_bps": 5, "slippage_bps": 5,
                "min_touch_count": 0, "max_touch_count": 0, "min_channel_width_pct": null,
                "min_entry_pos_in_channel": null, "probe_min_score": null,
                "max_signals_per_day": 0, "allowed_signal_types": null },
  "premium":  { "squeeze_days_min": 30, "squeeze_bonus": 8.0, "spring_bonus": 6.0,
                "min_touches": 3, "vol_expand_mult": 2.5 },
  "min_score": 80.0,
  "min_listing_bars": 250,
  "signal_quality_mode": "standard"
}
```

> **参数版本升级**：`_apply_v2_runtime` 在读取旧配置时，把恰好等于旧工厂值的项升到当前基线：`upper_shadow_max_ratio` 0.30→0.20、`squeeze_days_min` 20→30、`min_score` 60→80、PROBE 止损 1%/2 日→2%/3 日、通道失效缓冲 0.5%→1.5%、确认天数 2→3。用户改成其它数值的保留。默认行还会经 `sync_default_row_baseline` 把升级后的参数写回同一 `config_id`。

---

## 10. 回测预设

管理端一键套用，定义在 `backtest_presets.py`。预设只改本次任务的过滤和出场覆盖，不改参数版本里的默认包。

| 预设 | 作用 |
|------|------|
| `optimized_probe` | 结构出场、目标 5%、分≥80、回踩≥3、单日最多 30 只 |
| `breakout_lps_only` / `breakout_lps_v3` | 排除 PROBE；v3 带上当前出场基线 |
| `hit_rate_probe` | 只做 PROBE 的命中率，不止损 |
| `structure_v2`～`v3` | 任务级出场覆盖；v3 的止损/通道失效数值已与当前默认相同 |
| `structure_v4` | 出场沿用 v3；分≥85、回踩≥4 |
| `structure_v5` | 出场沿用 v3；通道宽≥2%、回踩 4～5、分≥80 |
| `structure_v6` | 在 v5 上增加 `entry_pos≥0`（信号价不低于通道下轨），并锁定分≥80、观察 10 日 |
| `structure_v7` | 保留 v6 的入场过滤和出场 v3；**不锁定**最低分、PROBE 分和观察日。创建任务时没填这些字段，就用参数版本默认（当前基线分≥80、观察 10 日） |

60/70/80 分段对照用 `structure_v7`，在任务上分别填写最低得分。同一股票若先出现较低分信号，会占用持仓，后面紧邻的更高分信号进不了该任务，所以三档结果不是严格嵌套。

---

## 9. 信号质量模式

- `standard`：过 SETUP 门槛的入场（默认）。
- `premium`：更严口径（`premium` 节：粘合 ≥30 日、回踩 ≥3 次、放量 ≥2.5 倍等），用于回测/精选对照。
