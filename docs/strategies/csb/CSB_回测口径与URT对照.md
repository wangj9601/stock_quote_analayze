# CSB 回测口径说明（对齐 URT 管理端能力）

> 代码依据：`backend_core/strategies/csb/backtest_runner.py`、`backtest_worker.py`、`backtest_factor_report.py`。

---

## 1. 通用口径

- **信号来源**：`use_trace=True` 时优先读 `csb_signal_trace`；缺失日由 `_ensure_trace_for_backtest_range` **自动补算**并写扫描标记。
- **入场**：信号 **次日开盘价**（`entry_price = future[0].open`）；无次日行情则跳过。
- **冷却**：同一只股票在持仓区间内不重复开仓（`hit_rate` 用 `d ≤ 冷却日`，纪律/结构出场用 `d < 冷却日`）。
- **观察期** `horizon_days`：默认 10 个交易日。
- **目标涨幅**：`target_pct`（默认 0.10）；给 `target_pct_max` 时形成 `[lo, hi]` 区间带。
- **最低得分** `min_score`：默认取参数包（当前基线 **80**）。trace 按实际得分落库，任务读取时再筛；只改门槛不必重跑预计算。
- **信号质量** `signal_quality_mode`：`standard` / `premium`。

---

## 2. 出场模式 `exit_mode`

| 模式 | 说明 |
|------|------|
| `hit_rate` | 以 BREAKOUT/LPS/PROBE（过门槛）为样本，次日开盘入场；前瞻 `horizon_days` 内 **最高价** 是否触及 `target_pct`；**不止损**，到期按末日收盘计盈亏；统计命中率。 |
| `risk_exit` | 纪律出场：**基准止损**（缓冲 0、当日确认）→ **价格止损**（默认入场价下跌 8%）→ **到期平仓**。 |
| `structure_exit` | 结构出场：**假突破**（仅 BREAKOUT，3 日）→ **基准止损**（PROBE 默认下移 2% 且连续 3 日；BREAKOUT/LPS 缓冲 0、当日确认）→ **通道失效**（仅 PROBE，下轨下移 1.5%、连续 3 日）→ **派发离场** → **阶梯跟踪止损**（前序浮盈达 10% 后抬地板到 +5%、只跟 MA10，并允许相对前高回撤 8% 离场）→ **到期平仓**。 | |

**命中率对照**：非 `hit_rate` 模式下（`compare_hit_rate` 默认开），任务完成后 **自动排队一条同配置 `hit_rate` 对照任务**（`backtest_worker._maybe_start_hit_rate_compare`），回填 `paired_hit_rate_summary` 到父任务。

**出场原因枚举** `exit_reason`（导出中文见《CSB_通道突破_业务规则与信号计算规则》第 6 节）：`false_break` 假突破 / `baseline_stop` 基准止损 / `channel_fail` 通道失效 / `distribution` 派发离场 / `ma_trail` 阶梯跟踪止损 / `price_stop` 价格止损 / `horizon_end` 到期平仓。

---

## 3. 汇总指标

**通用**

- `total_signals` / `total_samples`、`hit_count` / `hit_rate`、`target_pct` / `target_pct_max`、`horizon_days`、`backtest_mode`、`exit_mode`、`avg_max_gain_pct`、`avg_bars_held`。
- `by_score_bucket`、`by_factor_bucket`、`risk_params`、`trade_logic`、`precompute`（补算元信息）。

**非 `hit_rate` 追加**

- `win_count` / `win_rate`、`avg_pnl_pct`、`exit_reason_dist`、`hit_rate_compare`（同批次样本的命中 vs 实际 vs 满观察期持有）。

**任务级过滤**（预设或创建体覆盖，0/空表示不启用）：`min_touch_count` / `max_touch_count`、`min_channel_width_pct`、`min_entry_pos_in_channel`、`probe_min_score`、`max_signals_per_day`、`allowed_signal_types`。预设列表见业务规则第 10 节；分段对照用 `structure_v7`（不锁定分数和观察日）。

**评分分桶**（`score`）

`[0,60) / [60,70) / [70,80) / [80,90) / [90,100] / 未知`

**因子分桶**（`_FACTOR_BIN_SPECS`）

| 因子 | 分桶 |
|------|------|
| 粘合天数 | `<15` / `[15,20)` / `≥20` |
| 放量倍数 | `<2` / `[2,2.5)` / `≥2.5` |
| 回踩次数 | `<2` / `[2,3)` / `≥3` |

**明细字段**（导出）：`code/name/signal_date/signal_type/score/entry_date/entry_price/exit_date/exit_price/exit_reason/max_high/max_gain_pct/pnl_pct/bars_held/hit_target/hit_in_band/hit_date`，并展平通道与量能因子：`squeeze_days/squeeze_pct/touch_count/vol_expand_mult/channel_upper/channel_lower/horizon_pnl_pct/horizon_exit_price`。

---

## 4. 股票池

`all` / `single` / `custom` / `watchlist` / `gms_watchlist` / `industry_board` / `concept_board`，可选 **A 股板型** `cn_board_segment`（`ALL/MAIN/CYB/SZ_SME/KCB/BJ`）。

- `all` + 选择板型 → 展开为具体股票池。
- `gms_watchlist` **仅借用 GMS 观察股代码列表**（`status=active` 且 `market=A`），**不调用 GMS 引擎**。

---

## 5. 任务治理与导出

- **生命周期**：`pending → running → completed/failed/cancelled/paused`；支持暂停/继续/取消/重跑/删除/批量删除。
- **控制机制**：`backtest_worker` 协作式——worker 轮询 `_cancelled/_paused` 标志并参考任务状态，暂停时阻塞、取消时中断。
- **导出**：明细 CSV / XLSX；详情 PDF（依赖 `xhtml2pdf`，缺失返回 501）。报告页与 completed 任务同源。

---

## 6. 与 URT 对照

管理端任务生命周期、报告、预计算/purge/refresh、系统状态、审计与 URT **同级**。

**差异**：CSB 的出场与因子分桶使用 **CSB 规则与通道 / 量能字段**（粘合天数、放量倍数、回踩次数），**不复用** URT 的结构 KDE / HVZ。命中率对照机制与 URT 一致（自动排队 + 回填父任务）。
