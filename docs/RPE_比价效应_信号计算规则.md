# RPE（比价效应）信号计算规则说明

本文档基于当前代码实现整理，覆盖参数定义、计算公式、过滤规则、信号组装、离场与回测口径，便于策略校验与前后端对齐。

更完整的架构、表结构与 API 见：[RPE_STRATEGY_IMPLEMENTATION_DESIGN.md](./RPE_STRATEGY_IMPLEMENTATION_DESIGN.md)  
业务速览见：[RPE_比价效应_业务简化版.md](./RPE_比价效应_业务简化版.md)

工程包：`backend_core/strategies/rpe/`（与 GMS **零耦合**）。

---

## 1. 总体流程

1. 按行业或概念板块划定成分股簇（默认行业）  
2. 合成簇基准 \(I_t\)（当日成交量加权收盘价）  
3. 计算个股相对基准的滚动 Z-Score  
4. 对 \(I_t\) 做趋势斜率；弱势板块可否决入场  
5. 成交量加权 KDE 提取支撑/阻力，做结构过滤与流动性过滤  
6. 输出 `catch_up` / `lead` 及是否 `entry_signal`，可写入 `rpe_signal_trace`

单股评估入口：`RPEStrategyEngine.evaluate_in_sector`；全市场：`screen` → 按板 `screen_board` → 去重截断。

---

## 2. 参数一览（默认配置）

来源：`config.get_default_rpe_config()`。库内版本与默认 **深合并**。

### 2.1 一级参数

| 参数名 | 默认值 | 单位/范围 | 作用 |
|--------|--------|-----------|------|
| `lookback_days` | 250 | 交易日 | 日线与基准回溯长度 |
| `z_window` | 40 | ≥5（代码钳制） | 滚动 Z 窗口 |
| `z_lead` | 2.0 | 无量纲 | 领涨阈值：\(Z \ge z\_lead\) |
| `z_catch_up` | -1.5 | 无量纲 | 补涨阈值：\(Z \le z\_catch\_up\) |
| `sector_slope_window` | 60 | ≥5 | \(I_t\) 回归斜率窗口 |
| `enable_trend_veto` | true | bool | 斜率 &lt; 0 时禁止入场 |
| `enable_lead_trade` | false | bool | 是否允许领涨 `entry_signal` |
| `kde_base_factor` | 1.0 | 正数 | KDE 带宽系数 |
| `kde_grid_points` | 200 | ≥50 | 密度网格点数 |
| `min_rr_to_resistance` | 1.5 | 倍 | 结构盈亏比下限 |

### 2.2 `liquidity`

| 参数名 | 默认值 | 说明 |
|--------|--------|------|
| `lookback_days` | 20 | 近 N 日（代码下限 ≥5） |
| `min_avg_amount` | 5e6 | 日均成交额（元） |
| `min_avg_turnover_rate` | 0.5 | 日均换手（%）；无换手数据时仅判成交额 |

### 2.3 `scan` / `backtest`

| 参数名 | 默认值 | 说明 |
|--------|--------|------|
| `scan.max_results` | 200 | 结果条数上限 |
| `scan.min_sector_members` | 5 | 最少成分股数 |
| `scan.max_boards` | null | 可选板块数上限 |
| `backtest.horizon_days` | 40 | 回测前瞻天数 |
| `backtest.target_relative_pct` | 0.08 | 命中率目标涨幅 |
| `backtest.commission_bps` | 5.0 | 预留 |
| `backtest.slippage_bps` | 5.0 | 预留 |

---

## 3. 簇基准 \(I_t\)

对板块内当日有有效价量的成分股：

\[
I_t = \frac{\sum_i P_{i,t} V_{i,t}}{\sum_i V_{i,t}}
\]

- \(P\)：收盘价；\(V\)：成交量；任一 ≤0 则跳过该成分  
- 实现：`sector_benchmark.compute_vwap_benchmark`  
- 输出序列：`[{date, i_t, volume_sum}, ...]` 按日期升序  

**板块斜率**：对近 `sector_slope_window` 日 \(I_t\) 做线性回归 \(y = a + b x\)（\(x=0..n-1\)），取 \(b\)。  
当 `enable_trend_veto=true` 且 \(b < 0\) → `trend_veto=true`，禁止补涨/领涨入场。

---

## 4. 滚动 Z-Score

### 4.1 比价序列

对齐基准日期：\(R_t = P_t / I_t\)（\(P_t>0,\ I_t>0\)）。

### 4.2 滚动标准化

窗口 \(w=\max(5,z\_window)\)。对每个 \(t\)（需满窗）：

\[
\mu_t=\frac{1}{w}\sum_{k=t-w+1}^{t} R_k,\quad
\sigma_t=\sqrt{\frac{1}{w}\sum_{k=t-w+1}^{t}(R_k-\mu_t)^2},\quad
Z_t=\frac{R_t-\mu_t}{\sigma_t}
\]

- 使用总体方差（除以 \(w\)）  
- \(\sigma_t \le 10^{-12}\) 时记 \(Z_t=0\)  
- 序列长度不足窗口 → 无法出 Z（`no_z`）

### 4.3 阈值与类型

| 条件 | `signal_type` | 含义 |
|------|---------------|------|
| \(Z \le z\_catch\_up\)（默认 -1.5） | `catch_up` | 相对落后，潜在补涨 |
| \(Z \ge z\_lead\)（默认 2.0） | `lead` | 相对领涨 |
| 中间带 | 无 | `reason=in_band` |

`enable_lead_trade` 默认 `false`：领涨默认 `watch_only`，不产生可交易入场。

---

## 5. KDE 支撑 / 阻力

实现：`kde_levels.extract_kde_levels`。

1. 样本：回溯 bars 的 close、volume；有效点 &lt; 20 → `ok=false`（`insufficient_samples`）  
2. 带宽：\(\mathrm{bw}=\max(0.01,\ \mathrm{kde\_base\_factor}\cdot \sigma_P/\mu_P)\)  
3. `gaussian_kde` + 成交量权重（旧 scipy 无 weights 时按权重离散复制）  
4. 网格：`[0.98 minP, 1.02 maxP]`，`kde_grid_points` 点  
5. `find_peaks`，prominence ≥ `0.05 * max(density)`；失败则本地极大值回退  
6. 峰 &lt; 现价 → 支撑（近→远，最多 8）；峰 ≥ 现价 → 阻力（近→远，最多 8）

`nearest_levels`：取现价下方最近支撑、上方最近阻力。

---

## 6. 结构过滤与流动性

### 6.1 `structure_filter`

| 情况 | `structure_valid` | reason |
|------|-------------------|--------|
| 无支撑或 \(P\le S\) | false | `below_or_no_support` |
| \(D=P-S\le 0\) | false | `zero_downside` |
| 无上方阻力 | **true** | `no_resistance`（视为空间充足） |
| \(U=R-P\le 0\) | false | `at_resistance` |
| \(\mathrm{RR}=U/D \ge \mathrm{min\_rr}\) | true | `ok` |
| RR 不足 | false | `rr_too_small` |

默认 `min_rr_to_resistance=1.5`。

### 6.2 `liquidity_ok`

近 N 日：

- 日均成交额 ≥ `min_avg_amount`  
- 若有换手序列：日均换手 ≥ `min_avg_turnover_rate`  

不满足 → 不给出入场信号。

---

## 7. 入场信号组装

`signal_detector.detect_signal`：

**补涨主路径**（`entry_signal=true`）：

- `signal_type=catch_up`  
- 未 `trend_veto`  
- `structure_valid`  
- `liquidity_ok`  

**领涨**：`signal_type=lead`；仅当 `enable_lead_trade=true` 且结构/流动性通过且未否决时才可 `entry_signal`；否则 `watch_only`。

### 7.1 reason 码

| reason | 含义 |
|--------|------|
| `catch_up_ok` | 补涨且全部过滤通过，可入场 |
| `catch_up_filtered` | 补涨但被否决/结构/流动性挡住 |
| `lead_watch` | 领涨仅观察 |
| `lead_trade_ok` | 允许领涨交易且通过过滤 |
| `in_band` | Z 在阈值带内 |
| `no_z` | 无法计算 Z |

引擎同时写入 `detail.judgment.steps`（逐步规则、实际值、是否通过），供追溯页展示。

---

## 8. 离场规则

**禁止**将固定百分比止损作为策略唯一离场理由。

策略内建准绳：

- **结构破位** `structure_break`：收盘价 &lt; 最近有效结构支撑  

正式交易 API 若提交 `fixed_pct` / `percent_stop` 等 → HTTP 400。  
`trade_structure_plan.build_structure_plan` 固定 `exit_rule=structure_break`。

盘中二次确认：观察列表刷新时用 `stock_realtime_quote` 判断现价是否仍在支撑上（无独立盘中 cron）。

---

## 9. 选股排序与去重

全市场 `screen` 结果排序优先级（降序）：

1. `entry_signal`  
2. `signal_type == catch_up`  
3. `|z_score|`  

同代码多板块：

- **单股 / 自选 / 强制重算**：每只股票固定一个**主板块**（行业优先；同 kind 取成分股数最多，并列取 `board_code` 升序），追溯全历史使用同一板块，避免按日跳变。  
- **显式多选板块**等仍可能同股多行时：保留 `|z|` 最大的一条，再截断至 `max_results`。

---

## 10. 数据、调度与存储

| 项 | 说明 |
|----|------|
| 行情 | `historical_quotes` |
| 成分 | `industry_board_constituents` / 概念成分 |
| 信号表 | `rpe_signal_trace`，按 `config_id` 隔离 |
| 日终任务 | `rpe_signals_cn`，默认工作日 19:40，`ENABLE_RPE_PRECOMPUTE` |
| 强制重算 | `rpe_trace_recompute_tasks` + 追溯页 |

---

## 11. 回测类型

| `backtest_type` | 行为 |
|-----------------|------|
| `signal_hit_rate` | 信号日后 N 日内是否触及 `entry*(1+target_relative_pct)`，且未先结构破位 |
| `trade_simulation` | T+1 开盘入场；离场：结构破位 → 触及阻力 → 否则持有至 horizon |

实现：`backtest_runner.py`。

---

## 12. 计算示例（示意）

假设某日：

- \(Z=-1.8\) → 类型 `catch_up`  
- 板块斜率 \(+0.02\) → 未否决  
- \(P=10\)，\(S=9.5\)，\(R=11.0\) → \(D=0.5\)，\(U=1.0\)，\(\mathrm{RR}=2.0 \ge 1.5\) → 结构通过  
- 近 20 日均额、换手达标 → 流动性通过  

→ `entry_signal=true`，`reason=catch_up_ok`，结构计划支撑 9.5、阻力 11.0；若日后收盘跌破 9.5 → 结构破位离场。

若同条件但斜率 \(=-0.01\) 且开启否决 → 仍可为 `catch_up`，但 `entry_signal=false`，`watch_only=true`，`reason=catch_up_filtered`。
