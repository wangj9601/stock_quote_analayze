# URT 上升趋势策略 — 交易回测说明

本文档说明管理后台 **URT 回测** 的买卖规则、观察期、风控参数与汇总指标。实现代码主要位于：

| 模块 | 路径 |
|------|------|
| 回测执行 | `backend_core/strategies/urt/backtest_runner.py` |
| 离场规则 | `backend_core/strategies/urt/signal_detector.py` → `evaluate_exit_rules` |
| 任务持久化 / CSV 导出 | `backend_core/strategies/urt/backtest_storage.py` |
| 后台 Worker | `backend_core/strategies/urt/backtest_worker.py` |
| Admin API | `backend_api/admin/urt_admin_routes.py` |
| 管理端详情 | `admin/src/components/urt/TaskDetail.vue` |

策略选股与得分规则见：[URT_STRATEGY_IMPLEMENTATION_DESIGN.md](./URT_STRATEGY_IMPLEMENTATION_DESIGN.md)。  
回测优化结论与待办见：[URT策略回测优化方案.md](./URT策略回测优化方案.md)。  
GMS 对照见：[GMS交易回测买卖规则说明.md](./GMS交易回测买卖规则说明.md)。

---

## 1. 回测范围与任务参数

URT 回测目前 **仅 A 股**，无港股 / ETF 分支。支持三种出场模式（任务参数 `exit_mode`）：

| 模式 | 说明 |
|------|------|
| `hit_rate`（默认） | 命中率统计：观察期内不止损，满期参考出场 |
| `risk_exit` | 纪律出场：持仓期调用 `evaluate_exit_rules`（价格止损 / 连跌 / 回撤止盈） |
| `structure_exit` | 结构出场：信号日 KDE 最近支撑止损 / 最近阻力止盈（与选股明细同口径，持仓期不重算） |

### 1.1 创建任务常用参数

| 参数 | 含义 | 默认 | 说明 |
|------|------|------|------|
| `start_date` / `end_date` | 信号扫描区间 | 必填 | 按区间内交易日逐日扫描 |
| `target_pct` | 目标涨幅下限 | **0.10（10%）** | 入场价 × (1 + 下限) 为命中价；与上限相等时等同原单值 |
| `target_pct_max` | 目标涨幅上限 | **等于下限（缺省 10%～10%）** | 如 0.05～0.08 表示区间辅助统计；**命中=最大涨幅 ≥ 下限** |
| `horizon_days` | 观察期交易日数 | **10** | 入场日后最多取 N 根 K 线（短线默认；可对照 5/15） |
| `min_score` | 最低得分 | 策略配置（常为 70） | 过滤买点；可任务级覆盖 |
| `use_trace` | 优先读缓存 | `true` | 优先 `urt_signal_trace`；无则实时引擎 |
| `exit_mode` | 出场模式 | `hit_rate` | `hit_rate` / `risk_exit` |
| `strategy_config_id` | 参数版本 | 默认版本 | 含硬筛、得分、`risk` 风控 |
| `signal_quality_mode` | 信号质量 | **`standard`** | `standard`=排除均线多头分弱项区间；`premium`=近支撑≤2% + 排除弱项（见 §2.3） |
| `stock_pool_mode` | 股票池 | `all` | 全市场 / GMS观察股 / 自选 / 行业 / 概念 / 单股 / 自定义 |
| `cn_board_segment` | A 股板块 | 全部 | MAIN / CYB / SZ_SME / KCB / BJ |

创建时固化 `strategy_config_id`（默认绑生效/`is_default` 版本）。**改参不会改写已完成任务**；若 `use_trace=true` 重跑，读的是该 id **当前** trace（可能已按新参重算）。任务级覆盖 `min_score` 或选用非生效版本会标 `params_diverged`。

任务创建时会把 **交易逻辑说明（`trade_logic`）** 与 **风控快照（`risk_params`）** 写入任务 `config`；回测完成后亦写入 `summary`，在「任务详情」中展示。旧任务打开详情时由 API 按策略参数补齐。

---

## 2. 信号与买入前提

### 2.1 信号来源

1. **优先**（`use_trace=true` 且有配置 ID）：读当日 `urt_signal_trace`，且 `score ≥ min_score`。
2. **区间补齐**：回测开始时检查时间范围内各交易日是否已具备**全市场/股票池级**预计算（仅有个股强制重算的零星 trace **不算**覆盖；**股票池扫描占位 `scope=pool` 也不能冒充全市场已覆盖**）。未覆盖日对全市场（或任务股票池）**一次拉齐区间行情、内存按日评买点**并写入 `urt_signal_trace`，打上 `__URT_SCANNED__` 扫描占位，再进入交易模拟。不要按每个交易日重复拉取全市场 K 线。
3. **关闭缓存**（`use_trace=false`）：同样走区间一次扫描（内存出信号），不再逐日 `screen_universe`。全市场务必打开「优先读缓存」：结果可复用，且命中率对照不必再扫一遍。

买点判定（硬筛 + 得分 + **均线多头分弱项闸**）与选股一致，详见设计文档 §1 / §6 与业务简化版 §6.1。  
读 trace 时会对 `volume_multiple`、因子弱项等做**后滤**（与实时硬闸对齐；见 §2.3）。  
「手动预计算」只跑选定的**一天**，不能覆盖整段回测区间。全市场首次回测若区间缺缓存，进度条前半段为「区间一次扫描」补齐预计算。环境变量 `URT_SCREEN_WORKERS`（默认最多 4）可加快评点。

### 2.3 信号质量模式（2026-08-27）

任务参数 `signal_quality_mode`（管理端回测页「信号质量」）与网站选股页同口径：

| 模式 | 说明 | trace 后滤 |
|------|------|------------|
| `standard`（默认） | 排除均线多头分 **∈ [4, 7)**（A/B 验证弱项区间） | 是 |
| `premium`（精选） | 在标准基础上再加：距支撑 **≤2%**、排除得分 **≥90** | 是 |

- **实时扫描 / 新预计算**：弱项闸在 `signal_detector` 打分后硬否决，不再产生 `[4,7)` 买点。  
- **读旧 trace**：仍可能含弱项行，由 `signal_filters.build_signal_filter_from_cfg` 后滤；筛后为空**不会**触发全市场实时重扫。  
- 汇总字段：`summary.signal_quality_mode` / `signal_quality_mode_label`；PDF/任务详情可见。

批量 A/B 脚本：`manual_scripts/urt_ab_backtest.py`（`--group default` 参数 A/B；`--group factor` 因子 C 组）。

### 2.2 买入规则

| 步骤 | 规则 |
|------|------|
| 信号日 | 扫描区间内某交易日出现有效 URT 买点 |
| 入场日 | **信号日之后下一交易日** |
| 入场价 | 该日 **开盘价**；无效或 ≤0 则跳过该信号 |
| 去重 | 同一标的在上一笔 **观察期结束日之前** 不再开新仓（对齐 GMS） |

---

## 3. 持仓观察与目标判定

### 3.0 模式 `hit_rate`（默认，对齐 GMS 命中率）

观察窗口为信号日之后共 **`horizon_days` 根交易日 K 线**（默认 **10**，首根为入场日）。

| 规则项 | 说明 |
|--------|------|
| 目标命中 | 观察期内最大涨幅 **≥ 下限**（`target_pct`）即 `hit_target=true`；单点（10%～10%）与区间（5%～10%）口径一致 |
| 上限命中 | 当 `target_pct_max` > 下限时，最大涨幅 ≥ 上限 → `hit_target_upper=true`（辅助统计） |
| 区间内 | 最大涨幅落在 [下限, 上限] → `hit_in_band=true`（辅助统计；冲过上限则为否） |
| 最高价 / 最大涨幅 | 输出 `max_high`、`max_gain_pct`（相对入场价） |
| 止损 | **不启用**价格止损 / 连跌离场 / 回撤止盈 |
| 参考出场 | 持有满观察期，以最后一根收盘价记 `exit_price`（`horizon_end`） |
| 去重 | 观察期结束前同标的不再开仓 |

### 3.0b 模式 `risk_exit`（纪律出场）

入场规则同 §2.2。持仓自入场次日起逐日收盘调用 `evaluate_exit_rules`：

| 出场码 | 条件 |
|--------|------|
| `price_stop` | 浮亏 ≤ −`risk.stop_loss_pct_max`（默认 10%） |
| `time_stop` | 连续收跌 ≥ `risk.time_stop_down_days`（默认 3）**且**浮亏 ≥ `risk.time_stop_min_loss_pct`（默认 **4%**） |
| `trailing_take_profit` | 涨幅达警惕区（默认 **8%–10%**）后自峰值回撤 ≥ `risk.trailing_drawdown_pct` |
| `horizon_end` | 未触发纪律则满观察期收盘出场 |

同时仍统计 `hit_target`（观察窗内最高价是否触及目标），与是否提前纪律离场独立。

### 3.0c 模式 `structure_exit`（结构出场）

入场规则同 §2.2。结构位与**个股关键价位**同口径：

1. ZigZag **结构锚窗**成交量加权 KDE（`compute_kde_bundle`）
2. Fib/Pivot/Cam + Volume Profile → **`compute_confluence_from_reference`**
3. 默认以共振带中心作为 `nearest_support` / `nearest_resistance`（可优先 `tier=strong`）

| 规则 | 口径 |
|------|------|
| 止损价 | `nearest_support × (1 − structure_stop_buffer_pct)`，默认缓冲 **2%** |
| 止损触发 | 持仓第 2 日起，**收盘** ≤ 止损价 → `structure_stop` |
| 止盈价 | 优先 `nearest_resistance`（相对入场上行 ≥ `structure_exit_min_upside_pct`，默认 **5%**）；否则进入百分比目标区 |
| 止盈触发 | 阻力：**最高价** ≥ 阻力 → 默认可先平 `structure_partial_exit_frac`（50%），余仓改移动止盈；百分比目标默认**不硬平**，改武装跟踪 |
| P0 缺位补齐 | 缓存缺支撑或 `kde_ok=false` 时按上述同口径重算；明细含 `fallback_reason` / `structure_level_source` |
| P2 弱结构 | 仍无支撑时用近窗低点 / MA20 兜底（`structure_source=weak_*`） |
| P3 回退止损 | 无有效结构止损时用 `structure_fallback_stop_loss_pct`（默认 **8%**）→ `price_stop` |
| 全路径保护 | 浮盈达约 **+6.5%** 后保本；峰值回撤约 **4%** → `breakeven_stop` / `fallback_trail`（正结构与回退路径均启用） |
| 满期 | `horizon_end` |
| 同日优先级 | 先判保护/止损，再判阻力/百分比目标（可分批或改跟踪） |

配置开关：`structure_use_structural_window` / `structure_use_confluence` / `structure_prefer_confluence` / `structure_prefer_strong_confluence`（默认均开）。

汇总 `structure_exit_stats` 另含：回退原因拆分、弱结构笔数、KDE/共振重算笔数、保本/移动止盈笔数。

汇总额外字段 `structure_exit_stats`：各出场原因笔数、结构缺失回退率等，便于与 `hit_rate` / `risk_exit` 对照。

### 3.1 明细主要字段

| 字段 | 计算 |
|------|------|
| `max_high` | 观察期内最高价 |
| `max_gain_pct` | `(max_high - entry_price) / entry_price × 100` |
| `hit_target` / `hit_date` | 是否触及下限目标及首次触及日（相对 `target_pct`，独立统计） |
| `hit_target_upper` / `hit_date_upper` | 是否触及上限及首次触及日（相对 `target_pct_max`） |
| `hit_in_band` | 最大涨幅是否落在 [下限, 上限]（辅助统计；与 `hit_target` 独立） |
| `pnl_pct` | 出场价相对入场价盈亏 |
| `bars_held` | 实际持有 K 线根数 |
| `stop_price` / `target_price` | （`structure_exit`）结构或回退止损/止盈价 |
| `nearest_support` / `nearest_resistance` / `structure_rr` | （`structure_exit`）信号日结构字段 |
| `structure_fallback` | （`structure_exit`）是否因无支撑等回退百分比止损 |

---

## 4. 风控参数（`config.risk`）

来自策略配置版本（`urt_strategy_configs` / `urt_config.json`）。选股不强制；**当前回测命中率模式亦不启用止损离场**（参数仍写入任务快照供对照）。

| 参数 | 含义 | 默认 |
|------|------|------|
| `stop_loss_pct_min` | 止损区间下限（%） | 5 |
| `stop_loss_pct_max` | 价格止损阈值（%） | 10 |
| `time_stop_down_days` | 连跌离场天数 | 3 |
| `time_stop_min_loss_pct` | 连跌须同时达到的浮亏（%） | **4** |
| `take_profit_alert_pct_min` | 止盈警惕涨幅下限（%） | **8** |
| `take_profit_alert_pct_max` | 止盈警惕涨幅上限（%） | **10** |
| `trailing_drawdown_pct` | 高点回撤止盈（%） | 5 |
| `structure_stop_buffer_pct` | 结构止损相对支撑下移缓冲 | 0.02（顶层配置） |

`structure_exit` 另读顶层 `structure_exit_min_upside_pct`（默认 **0.05**）判定阻力是否可用作止盈；选股贴阻力硬闸仍用 `structure_rr_min_upside_pct`（默认 0.03）。  
全路径保护键：`structure_protect_enabled` / `structure_protect_arm_pct` / `structure_protect_trail_drawdown_pct`；分批：`structure_partial_exit_*`；百分比跟踪：`structure_pct_target_trail_enabled`。

---

## 5. 汇总与导出

### 5.1 汇总指标（`summary`）

| 指标 | 说明 |
|------|------|
| 信号数 / 样本数 | 实际入场笔数 |
| 命中数 / 命中率 | `hit_target=true` 的比例 |
| 胜率 | `pnl_pct > 0` 的比例 |
| 均盈亏 | 各笔 `pnl_pct` 算术平均 |
| 按分数分桶 | 得分区间样本与命中率 |
| 持有天数分布 | 1–3 / 4–10 / 11–20 / 21+ |
| 离场原因分布 | 各 `exit_reason` 笔数 |
| `structure_exit_stats` | 仅 `structure_exit`：结构止损/阻力止盈/回退占比等 |
| 分月收益 | 按出场月对 `pnl_pct` 取均值（简化） |
| `avg_bars_held` | 平均持有天数 |
| `trade_logic` / `risk_params` | 交易逻辑说明与风控快照 |
| `signal_quality_mode` / `signal_quality_mode_label` | 任务信号质量模式及中文标签 |

### 5.2 明细导出

- CSV：`GET /api/admin/urt/backtests/{task_id}/export`
- XLSX：`GET /api/admin/urt/backtests/{task_id}/export-xlsx`
- 详情 PDF（服务端 xhtml2pdf）：`GET /api/admin/urt/backtests/{task_id}/export-pdf`  
  Admin 回测详情弹窗「导出PDF」走此接口；依赖 `xhtml2pdf`，中文使用 ReportLab CID 字体 `STSong-Light`。

完成任务后生成 UTF-8-BOM CSV（Excel 可直接打开），中文列名包括：股票代码、股票名称、信号日期、得分、入场日期、入场价、出场日期、出场价、出场原因、是否命中目标、命中日期、盈亏比例(%)、持有天数。  
出场原因会译为中文（如「触及目标」「到期平仓」）。旧任务需重跑后才会带中文表头。

---

## 6. 管理端入口

| 项 | 说明 |
|----|------|
| 页面 | Admin → `/urt-management` →「回测管理」 |
| 详情 | 「详情」对话框展示任务参数、**交易逻辑细节**、**风控参数**、汇总与日志 |
| API | `/api/admin/urt/backtests*`（创建 / 列表 / 详情 / 取消 / 重跑 / 删除 / 导出） |

---

## 7. 流程简图

```text
按交易日扫描买点（trace 或实时引擎）
        ↓
信号次日开盘价入场
        ↓
观察期（默认 10 个交易日）逐日检查
        ├─ high ≥ 目标价 → target_hit（出场价=目标价）
        ├─ 浮亏 ≤ −止损% → price_stop
        ├─ 连跌 ≥ N 日 → time_stop
        ├─ 涨幅达警惕区后高点回撤 → trailing_take_profit
        └─ 期满 → horizon_end（最后收盘）
        ↓
记 pnl / 持有天数；同标的冷却至出场日
```
