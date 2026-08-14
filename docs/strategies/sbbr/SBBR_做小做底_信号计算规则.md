# SBBR（做小做底）信号计算规则说明

本文档基于当前代码实现整理，覆盖 SBBR 的选股与交易信号计算逻辑，便于策略校验、参数调优与前后端对齐。

## 1. 总体流程

SBBR 按以下顺序计算信号：

1. 做小过滤（总市值 + 流通股本）
2. 筑底识别（横盘收集 / 打压恐慌）
3. 共振弱转强入场
4. 弹性防守线计算与破位检测
5. 三要素退出评估
6. 五三二仓位建议

其中前 1~3 步用于选股结果，后 4~6 步用于持仓跟踪与交易建议。

## 2. 做小过滤规则（size_filter）

### 2.1 指标计算

- 总市值（亿元）：`total_mv = total_shares * close / 1e8`
- 流通股本（亿股）：`circ_shares_yi = free_float_shares / 1e8`（单位是**亿股**，不是亿元）
- 流通市值（亿元）：`circ_mv = free_float_shares * close / 1e8`（仅展示，**不参与**默认过滤）

### 2.2 默认阈值

- 总市值区间：20 ~ 200 亿（元口径的市值）
- 流通股本区间：5 ~ 10 亿股
- 缺省行为：
  - 若总市值与流通股本都缺失，默认判为不通过（`exclude_unknown_size=true` 且 `require_shares=true`）
  - 若仅一侧缺失，则按有值那一侧判断（`total_only` 或 `circ_shares_only`）
- 库内若仍残留错误的 `circ_mv_min/max_yi` 默认（5~10 或 20~200），读取配置时会迁移为：`total_mv` 20~200 + `circ_shares` 5~10 亿股，并移除上述 `circ_mv_*` 默认约束
## 3. 筑底识别规则（bottom_detector）

SBBR 先判定横盘收集；不命中再判定打压恐慌（黄金坑）。

### 3.1 横盘收集（range_accumulation）

观察窗口默认 60 日，需同时满足基础条件，并通过下跌通道过滤（避免长期阴跌被误判为箱体筑底）：

1. 振幅约束：
   - `range_pct = (window_high - window_low) / ((window_high + window_low)/2)`
   - 要求 `range_pct <= max_range_pct`（默认 **0.35**）
2. 量价配合：
   - 上涨日平均成交量 > 下跌日平均成交量（默认开启）
3. 触底次数：
   - 收盘或最低价贴近区间下沿（容差 2%）
   - 触及次数在 3~4 次（参数可调）

下跌通道过滤（任一命中则拒绝 `range_accumulation`，不影响黄金坑路径）：

4. **趋势过滤（P0）**：
   - 近窗收盘跌幅 `(close_end - close_start) / close_start <= max_close_drop_pct`（默认 **-12%**）→ 拒绝
   - 或收盘相对 OLS 日斜率 `slope(close)/mean(close) < min_close_slope_norm`（默认 **-0.002**）→ 拒绝
5. **新低序列（P0）**：
   - 后半段最低价相对前半段最低再低 ≥ `half_low_drop_pct`（默认 5%）→ 拒绝
6. **高低点时间序（P1）**：
   - 窗口最高落在前 `high_early_frac`（默认 40%）、最低落在后段（位置 ≥ `low_late_frac`，默认 60%）→ 拒绝（高前低后）
7. **均线环境（P2，默认开启）**：
   - 最新收盘相对 MA60 折价 `< ma_env_max_discount_pct`（默认 -12%）→ 拒绝
   - 或 MA60 相对斜率 `< ma_env_min_slope_norm`（默认 -0.0015）→ 拒绝
   - 观察窗不足 MA 周期时跳过本项

命中后输出：

- `bottom_mode = range_accumulation`
- 支撑位 `support`（窗口最低点）
- 阻力位 `resistance`（窗口最高点）

### 3.2 打压恐慌（panic_accumulation）

在最近约 10 根内寻找“恐慌日”，条件为：

- 个股单日跌幅 <= -5%
- 同期大盘日收益 <= -2%

找到恐慌日后，默认还需满足“收复 MA20”：

- 当前收盘 >= 当前 MA20
- 且存在由弱转强的收复特征（相对前值/恐慌日位置）

命中后输出：

- `bottom_mode = panic_accumulation`
- `support` 取恐慌日最低价

## 4. 入场信号规则（entry_detector）

入场信号 `entry_signal=true` 需同时满足以下条件：

1. 前置条件：已通过筑底（`bottom_matched=true`）
2. 均线突破：
   - 昨收 <= 昨 MA20
   - 今收 > 今 MA20
3. 底部缩量（启动前）：
   - 近 5 日均量 / 更早 5 日均量 <= 0.7
4. 当日微放量（转强日）：
   - 当日量 / 近 5 日均量在 [1.05, 1.8]
5. 大盘共振（默认开启）：
   - 最近 5 日大盘累计收益 <= -1%
   - 若无大盘序列，当前实现默认不阻断

入场信号附带：

- `entry_low`：信号日最低价（后续防守锚点）
- `volume_ratio`：当日量能比
- `ma20`、`signal_date` 及各子条件布尔值

## 5. 防守规则（defense_exit.check_defense_breach）

### 5.1 弹性防守带

以入场锚点（通常是 `entry_low`）计算：

- 默认缓冲：3%（约束范围 2%~5%）
- 防守上沿：`defense_high = anchor_low`
- 防守下沿：`defense_low = anchor_low * (1 - buffer_pct)`

### 5.2 破位判定

- 仅看最新一根收盘
- 若 `close < defense_low`，判定 `breached=true`

## 6. 三要素退出规则（defense_exit.evaluate_exit_factors）

对持仓进行三项评估：

1. 空间充足（space）
   - 当前涨幅 `gain_pct = (last_close - entry_price) / entry_price`
   - 达到任一阈值即命中，默认阈值：50%、70%、100%
2. 高位盘整（consolidate）
   - **自入场日起**的子序列计算历史高点（无 `entry_idx`/`entry_date` 时退回全部已加载 K 线）
   - 近 15 日窗口
   - 当前价接近该段高位（>= 85% 高点）
   - 且窗口振幅 <= 15%
3. 高换手（turnover）
   - 最近 5 日累计换手率 >= 100%
   - 优先用 `turnover_rate`；缺失时用 `amount / (free_float_shares * close) * 100` 估算
   - 近窗仍无任何可用换手数据时：`turnover_ok=false`，`turnover_reason=missing_data`（避免静默当 0）

信号输出：

- `flags`：命中的要素集合
- `any_ok`：任一命中（建议分批锁定）
- `all_ok`：三项全中（建议全额退出）
- `suggest_partial_exit` / `suggest_full_exit`
- `turnover_sum` / `turnover_reason`

## 7. 五三二仓位建议（position_advisor）

默认参数：

- 试探仓：50%
- 追加仓：30%
- 现金保留：20%
- 最大同时持仓：3（小资金可降到 2）

阶段建议：

- 无持仓阶段（`stage=None`）：
  - 未超持仓上限 -> 建议 `probe`（50%）
  - 超上限 -> `blocked`
- 试探阶段（`probe`）：
  - 若**上方支撑确认**且不突破最大可分配仓位（80%）-> 建议 `add`（30%）
  - 否则 `hold_probe`
- 加仓阶段（`add`）：
  - 建议 `hold_reserve`（保留 20% 现金，不满仓）

### 7.1 上方支撑确认（support_confirm）

加仓门闩 `has_new_support` **不再**等同于「未破防守」或「筑底成立」，需同时满足：

1. 防守未破位（`close >= defense_low`）
2. KDE 有效且 `close > nearest_support`（与 URT/GMS 同口径成交量加权 KDE）
3. 箱体确认：
   - 有 `box_resistance`（横盘底）：`close >= box_resistance * (1 - tol)`，默认 tol=1%（阻力转支撑）
   - 无箱体阻力（如黄金坑）：`close >= MA20`

选股日 `evaluate_code` 的仓位建议固定为试探阶段，不会因 `bottom_matched` 误触发「可加仓」。

### 7.2 支撑/阻力数据字段

选股与持仓评估顶层输出：

- `box_support` / `box_resistance`：筑底箱体位（黄金坑通常仅有支撑）
- `nearest_support` / `nearest_resistance`：KDE 最近结构位
- `kde_ok` / `kde_reason` / `kde_lookback_used`
- `support_confirm`：持仓评估时的上方支撑确认明细（`confirmed` / `reason` 等）

前端选股表展示箱体与 KDE 四列；正式交易表展示「支撑确认」列。「按前复权计算」仅重算列表中的 KDE 列（调用 `/api/analysis/levels/batch`），不改写策略信号与箱体位。

## 8. 关键默认参数清单（可配置）

来自 `sbbr_strategy_configs` 默认版本：

- `size.total_mv_min_yi=20`, `size.total_mv_max_yi=200`（总市值，亿元）
- `size.circ_shares_min_yi=5`, `size.circ_shares_max_yi=10`（流通股本，亿股）
- `bottom.lookback_days=60`, `bottom.max_range_pct=0.35`, `bottom.min_touches=3`, `bottom.max_touches=4`
- `bottom.max_close_drop_pct=-0.12`, `bottom.min_close_slope_norm=-0.002`
- `bottom.reject_new_low_seq=true`, `bottom.half_low_drop_pct=0.05`
- `bottom.reject_high_before_low=true`, `bottom.high_early_frac=0.40`, `bottom.low_late_frac=0.60`
- `bottom.require_ma_env=true`, `bottom.ma_env_period=60`, `bottom.ma_env_max_discount_pct=-0.12`, `bottom.ma_env_min_slope_norm=-0.0015`
- `entry.ma_period=20`, `entry.shrink_volume_ratio_max=0.7`, `entry.expand_volume_ratio_min=1.05`, `entry.expand_volume_ratio_max=1.8`
- `entry.market_lookback_days=5`, `entry.market_drop_pct=-0.01`
- `defense.default_buffer_pct=0.03`
- `support_confirm.box_resistance_tol_pct=0.01`, `support_confirm.ma_period=20`
- `exit.space_pcts=[0.50,0.70,1.00]`, `exit.high_consolidate_days=15`, `exit.turnover_sum_days=5`, `exit.turnover_sum_pct=100`
- `position.probe_pct=50`, `position.add_pct=30`, `position.reserve_cash_pct=20`, `position.max_open_positions=3`
- KDE：`kde_lookback_initial/days=60`, `kde_lookback_step=250`, `kde_lookback_max=750`

## 9. 实战解读（为什么会出现 0 条入场）

当用户勾选“仅入场信号”时，策略要求在同一天同时满足：

- 做小通过
- 筑底成立
- 上穿 MA20
- 缩量后微放量
- 大盘共振下跌（默认）

该组合较严格，某些交易日出现 0 条是正常现象。可先查看“筑底池”（关闭仅入场）再等待弱转强触发。

## 10. 历史回溯（asof 基准日）

选股接口 `GET /api/screening/sbbr-strategy` 支持 Query `date=YYYY-MM-DD`（前端「基准日」）：

1. **对齐交易日**：`resolve_effective_trade_date` 取 `historical_quotes` 中 `MAX(date) WHERE date <= 请求日`；请求日晚于表内最新日或留空时，用表内全局最新交易日。
2. **K 线截断**：`load_bars(..., end_date=asof)` 仅加载 `date <= asof` 的行情；引擎再以 `truncate_bars_asof` 兜底，保证不用未来数据。
3. **做小宇宙收盘**：`load_latest_closes` 在有基准日时按 `date <= asof` 取各股最近收盘（非精确日等值匹配），避免非交易日宇宙为空。
4. **股本/市值**：`load_shares_from_realtime` 同样按 `trade_date <= asof`。
5. **预计算**：勾选「优先读预计算」时读 `sbbr_signal_trace` 中该 `trade_date` 的行；管理端「手动预计算」可指定基准日写入。无预计算数据时前端会回退 live 现算。
6. **响应字段**：`search_date` / `asof_date`（实际计算日）、`requested_date`（用户请求日）、`data_max_date`（行情表最新日）、`source`（`live`|`trace`）、`source_label`（实时计算|预计算）、`date_snapped`（是否发生对齐）。

默认行为不变：不传 `date` 时按最新交易日计算。

## 11. 单股信号历史

- 选股结果操作列「历史」→ `stock_sbbr_trace.html`（对齐 URT `stock_urt_trace`）。
- `GET /api/stock/sbbr-signal-history`：按日 asof 现算（`evaluate_history`），跨度上限 180 自然日 / 120 交易日；一次加载 K 线与大盘收益后按日截断。
- `GET /api/stock/sbbr-signal-trace`：读 `sbbr_signal_trace` 该股预计算序列。

## 12. 选股范围「个股」（scope=single）

- 与 URT/RPE 一致：前端范围选「个股」，传 `stock_code`（代码或名称）；后端解析为 6 位 A 股后对该股 live 现算。
- **不强制落在做小宇宙**：`require_size`/`require_bottom` 硬筛对个股关闭，结果仍含 `size_ok`/`bottom_matched` 等字段；未过做小会提示并展示明细。`entry_only` 仍生效。
