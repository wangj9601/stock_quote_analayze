# SBBR（做小做底）信号计算规则说明

本文档基于当前代码实现整理，覆盖 SBBR 的选股与交易信号计算逻辑，便于策略校验、参数调优与前后端对齐。

## 1. 总体流程

SBBR 按以下顺序计算信号：

1. 做小过滤（市值）
2. 筑底识别（横盘收集 / 打压恐慌）
3. 共振弱转强入场
4. 弹性防守线计算与破位检测
5. 三要素退出评估
6. 五三二仓位建议

其中前 1~3 步用于选股结果，后 4~6 步用于持仓跟踪与交易建议。

## 2. 做小过滤规则（size_filter）

### 2.1 市值计算

- 总市值（亿）：`total_mv = total_shares * close / 1e8`
- 流通市值（亿）：`circ_mv = free_float_shares * close / 1e8`

### 2.2 默认阈值

- 总市值区间：20 ~ 200 亿
- 流通市值区间：5 ~ 10 亿
- 缺省行为：
  - 若总/流通都缺失，默认判为不通过（`exclude_unknown_size=true` 且 `require_shares=true`）
  - 若仅一侧缺失，则按有值那一侧判断（`total_only` 或 `circ_only`）

## 3. 筑底识别规则（bottom_detector）

SBBR 先判定横盘收集；不命中再判定打压恐慌（黄金坑）。

### 3.1 横盘收集（range_accumulation）

观察窗口默认 60 日，需同时满足：

1. 振幅约束：
   - `range_pct = (window_high - window_low) / ((window_high + window_low)/2)`
   - 要求 `range_pct <= 0.60`
2. 量价配合：
   - 上涨日平均成交量 > 下跌日平均成交量（默认开启）
3. 触底次数：
   - 收盘或最低价贴近区间下沿（容差 2%）
   - 触及次数在 3~4 次（参数可调）

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
   - 近 15 日窗口
   - 当前价接近历史高位（>= 85% 高点）
   - 且窗口振幅 <= 15%
3. 高换手（turnover）
   - 最近 5 日累计换手率 >= 100%

信号输出：

- `flags`：命中的要素集合
- `any_ok`：任一命中（建议分批锁定）
- `all_ok`：三项全中（建议全额退出）
- `suggest_partial_exit` / `suggest_full_exit`

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
  - 若上方支撑确认且不突破最大可分配仓位（80%）-> 建议 `add`（30%）
  - 否则 `hold_probe`
- 加仓阶段（`add`）：
  - 建议 `hold_reserve`（保留 20% 现金，不满仓）

## 8. 关键默认参数清单（可配置）

来自 `sbbr_strategy_configs` 默认版本：

- `size.total_mv_min_yi=20`, `size.total_mv_max_yi=200`
- `size.circ_mv_min_yi=5`, `size.circ_mv_max_yi=10`
- `bottom.lookback_days=60`, `bottom.max_range_pct=0.60`, `bottom.min_touches=3`, `bottom.max_touches=4`
- `entry.ma_period=20`, `entry.shrink_volume_ratio_max=0.7`, `entry.expand_volume_ratio_min=1.05`, `entry.expand_volume_ratio_max=1.8`
- `entry.market_lookback_days=5`, `entry.market_drop_pct=-0.01`
- `defense.default_buffer_pct=0.03`
- `exit.space_pcts=[0.50,0.70,1.00]`, `exit.high_consolidate_days=15`, `exit.turnover_sum_days=5`, `exit.turnover_sum_pct=100`
- `position.probe_pct=50`, `position.add_pct=30`, `position.reserve_cash_pct=20`, `position.max_open_positions=3`

## 9. 实战解读（为什么会出现 0 条入场）

当用户勾选“仅入场信号”时，策略要求在同一天同时满足：

- 做小通过
- 筑底成立
- 上穿 MA20
- 缩量后微放量
- 大盘共振下跌（默认）

该组合较严格，某些交易日出现 0 条是正常现象。可先查看“筑底池”（关闭仅入场）再等待弱转强触发。

