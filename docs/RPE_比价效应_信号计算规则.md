# RPE（比价效应）信号计算规则说明

本文档基于当前代码实现整理，覆盖 RPE 的选股、结构过滤、离场与预计算逻辑，便于策略校验与前后端对齐。

## 1. 总体流程

1. 按行业板块（`industry_board_constituents.board_code`）划定成分股簇  
2. 合成簇基准 \(I_t\)（当日成交量加权收盘价）  
3. 计算个股相对基准的滚动 Z-Score  
4. 对 \(I_t\) 做趋势斜率，弱势板块可否决补涨入场  
5. 成交量加权 KDE 提取支撑/阻力，做结构过滤与流动性过滤  
6. 输出 `catch_up` / `lead` 信号，写入 `rpe_signal_trace`

工程包路径：`backend_core/strategies/rpe/`，与 GMS **零耦合**。

## 2. 簇基准 \(I_t\)

对板块内当日有行情的成分股：

\[
I_t = \frac{\sum_i P_{i,t} V_{i,t}}{\sum_i V_{i,t}}
\]

默认回溯约 250 个交易日。实现见 `sector_benchmark.compute_vwap_benchmark`。

板块斜率：对近 `sector_slope_window`（默认 60）日 \(I_t\) 做线性回归斜率。斜率 &lt; 0 且 `enable_trend_veto=true` 时，禁止补涨类入场（`trend_veto`）。

## 3. 滚动 Z-Score

1. 比价序列：\( R_t = P_t / I_t \)  
2. 滚动窗口 `z_window`（默认 40，可配 20–60）  
3. \( Z_t = (R_t - \mu)/\sigma \)

阈值（默认）：

| 条件 | 含义 | `signal_type` |
|------|------|----------------|
| \(Z > 2.0\) | 领涨 | `lead` |
| \(Z < -1.5\) | 潜在补涨 | `catch_up` |

`enable_lead_trade` 默认 `false`：领涨默认仅观察/弱提示，不作为默认可交易入场。

## 4. KDE 支撑 / 阻力

- `scipy.stats.gaussian_kde`，成交量为权重  
- `bw_method = kde_base_factor * (sigma / mu)`（价格相对波动）  
- `find_peaks` 取密度极大值 → 支撑/阻力数组  
- 现价下方最近峰为最近支撑，上方最近峰为最近阻力  

结构过滤（`structure_filter`）：

- 现价须在最近一级支撑之上  
- 距最近阻力的「盈亏比」≥ `min_rr_to_resistance`（默认 1.5）

## 5. 流动性

近 `liquidity.lookback_days`（默认 20）日：

- 日均成交额 ≥ `min_avg_amount`（默认 500 万）  
- 日均换手 ≥ `min_avg_turnover_rate`（默认 0.5%）

不满足则 `liquidity_ok=false`，不给出入场信号。

## 6. 入场信号组装

`detect_signal` 同时满足时 `entry_signal=true`（补涨主路径）：

- `signal_type=catch_up`  
- 未触发趋势否决  
- `structure_valid`  
- `liquidity_ok`  

领涨：`signal_type=lead`；仅当 `enable_lead_trade=true` 且结构/流动性通过时才可 `entry_signal`。

## 7. 离场规则（明确禁止固定 % 止损）

策略内建离场准绳：**结构破位**——收盘价跌破最近有效支撑（`structure_break`）。

正式交易 API 拒绝将 `fixed_pct` / `percent_stop` 等作为唯一离场理由。

## 8. 数据与调度

| 项 | 说明 |
|----|------|
| 行情 | `historical_quotes`（与全站口径一致） |
| 成分股 | `industry_board_constituents` |
| 信号表 | `rpe_signal_trace`，按 `config_id` 隔离 |
| 日终任务 | `rpe_signals_cn`，默认工作日 19:40，`ENABLE_RPE_PRECOMPUTE` |
| 盘中二次确认 | 观察列表刷新时用 `stock_realtime_quote` 判断现价是否仍在支撑上（无独立盘中 cron） |

## 9. 回测类型

| `backtest_type` | 行为 |
|-----------------|------|
| `signal_hit_rate` | 补涨信号后 N 日内是否向基准收敛 / 触及目标相对收益 |
| `trade_simulation` | T+1 开盘入场；离场仅结构破位或触及阻力兑现 |

## 10. 默认配置摘要

见 `backend_core/strategies/rpe/config.py` 中 `get_default_rpe_config()`：

- `lookback_days=250`, `z_window=40`, `z_lead=2.0`, `z_catch_up=-1.5`  
- `sector_slope_window=60`, `enable_trend_veto=true`, `enable_lead_trade=false`  
- `kde_base_factor=1.0`, `min_rr_to_resistance=1.5`
