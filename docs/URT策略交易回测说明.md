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
GMS 对照见：[GMS交易回测买卖规则说明.md](./GMS交易回测买卖规则说明.md)。

---

## 1. 回测范围与任务参数

URT 回测目前 **仅 A 股**，无港股 / ETF 分支。支持两种出场模式（任务参数 `exit_mode`）：

| 模式 | 说明 |
|------|------|
| `hit_rate`（默认） | 命中率统计：观察期内不止损，满期参考出场 |
| `risk_exit` | 纪律出场：持仓期调用 `evaluate_exit_rules`（价格止损 / 连跌 / 回撤止盈） |

### 1.1 创建任务常用参数

| 参数 | 含义 | 默认 | 说明 |
|------|------|------|------|
| `start_date` / `end_date` | 信号扫描区间 | 必填 | 按区间内交易日逐日扫描 |
| `target_pct` | 目标涨幅 | **0.10（10%）** | 入场价 × (1 + target_pct) 为目标价 |
| `horizon_days` | 观察期交易日数 | **20** | 入场日后最多取 N 根 K 线 |
| `min_score` | 最低得分 | 策略配置（常为 70） | 过滤买点；可任务级覆盖 |
| `use_trace` | 优先读缓存 | `true` | 优先 `urt_signal_trace`；无则实时引擎 |
| `exit_mode` | 出场模式 | `hit_rate` | `hit_rate` / `risk_exit` |
| `strategy_config_id` | 参数版本 | 默认版本 | 含硬筛、得分、`risk` 风控 |
| `stock_pool_mode` | 股票池 | `all` | 全市场 / 自选 / 行业 / 概念 / 单股 / 自定义 |
| `cn_board_segment` | A 股板块 | 全部 | MAIN / CYB / SZ_SME / KCB / BJ |

任务创建时会把 **交易逻辑说明（`trade_logic`）** 与 **风控快照（`risk_params`）** 写入任务 `config`；回测完成后亦写入 `summary`，在「任务详情」中展示。旧任务打开详情时由 API 按策略参数补齐。

---

## 2. 信号与买入前提

### 2.1 信号来源

1. **优先**（`use_trace=true` 且有配置 ID）：读当日 `urt_signal_trace`，且 `score ≥ min_score`。
2. **区间补齐**：回测开始时检查时间范围内各交易日是否已具备**全市场/股票池级**预计算（仅有个股强制重算的零星 trace **不算**覆盖）。未覆盖日对全市场（或任务股票池）扫描一次并写入 `urt_signal_trace`，并打上 `__URT_SCANNED__` 扫描占位，再进入交易模拟。
3. **关闭缓存**（`use_trace=false`）：逐日实时 `screen_universe`（含全市场，不再因候选过多跳过）。

买点判定（硬筛 + 得分）与选股一致，详见设计文档 §1 / §6。  
全市场首次回测若区间较长，预计算阶段耗时会明显增加，进度条前半段为「补齐预计算」。

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

观察窗口为信号日之后共 **`horizon_days` 根交易日 K 线**（默认 **20**，首根为入场日）。

| 规则项 | 说明 |
|--------|------|
| 目标命中 | 观察期内 **最高价 ≥ 入场价 × (1 + target_pct)** → `hit_target=true` |
| 最高价 / 最大涨幅 | 输出 `max_high`、`max_gain_pct`（相对入场价） |
| 止损 | **不启用**价格止损 / 连跌离场 / 回撤止盈 |
| 参考出场 | 持有满观察期，以最后一根收盘价记 `exit_price`（`horizon_end`） |
| 去重 | 观察期结束前同标的不再开仓 |

### 3.0b 模式 `risk_exit`（纪律出场）

入场规则同 §2.2。持仓自入场次日起逐日收盘调用 `evaluate_exit_rules`：

| 出场码 | 条件 |
|--------|------|
| `price_stop` | 浮亏 ≤ −`risk.stop_loss_pct_max`（默认 10%） |
| `time_stop` | 连续收跌 ≥ `risk.time_stop_down_days`（默认 3） |
| `trailing_take_profit` | 涨幅达警惕区后自峰值回撤 ≥ `risk.trailing_drawdown_pct` |
| `horizon_end` | 未触发纪律则满观察期收盘出场 |

同时仍统计 `hit_target`（观察窗内最高价是否触及目标），与是否提前纪律离场独立。

### 3.1 明细主要字段

| 字段 | 计算 |
|------|------|
| `max_high` | 观察期内最高价 |
| `max_gain_pct` | `(max_high - entry_price) / entry_price × 100` |
| `hit_target` / `hit_date` | 是否触及目标及首次触及日 |
| `pnl_pct` | 期末收盘相对入场价的参考盈亏（满仓持有满期） |
| `bars_held` | 观察期 K 线根数（通常等于 `horizon_days`） |

---

## 4. 风控参数（`config.risk`）

来自策略配置版本（`urt_strategy_configs` / `urt_config.json`）。选股不强制；**当前回测命中率模式亦不启用止损离场**（参数仍写入任务快照供对照）。

| 参数 | 含义 | 默认 |
|------|------|------|
| `stop_loss_pct_min` | 止损区间下限（%） | 5 |
| `stop_loss_pct_max` | 价格止损阈值（%） | 10 |
| `time_stop_down_days` | 连跌离场天数 | 3 |
| `take_profit_alert_pct_min` | 止盈警惕涨幅下限（%） | 25 |
| `take_profit_alert_pct_max` | 止盈警惕涨幅上限（%） | 30 |
| `trailing_drawdown_pct` | 高点回撤止盈（%） | 5 |

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
| 分月收益 | 按出场月对 `pnl_pct` 取均值（简化） |
| `trade_logic` / `risk_params` | 交易逻辑说明与风控快照 |

### 5.2 明细导出

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
观察期（默认 20 个交易日）逐日检查
        ├─ high ≥ 目标价 → target_hit（出场价=目标价）
        ├─ 浮亏 ≤ −止损% → price_stop
        ├─ 连跌 ≥ N 日 → time_stop
        ├─ 涨幅达警惕区后高点回撤 → trailing_take_profit
        └─ 期满 → horizon_end（最后收盘）
        ↓
记 pnl / 持有天数；同标的冷却至出场日
```
