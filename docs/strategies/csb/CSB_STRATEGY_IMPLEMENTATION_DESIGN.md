# CSB 低位狭长通道磨底 + 放量突破 — 实现设计

## 定位

独立策略包：`backend_core/strategies/csb/`。不耦合 GMS / URT / SBBR / RPE / VSB 引擎，使用独立表空间 `csb_*`。

核心链路：换手初筛 → MA5/10/20/60 粘合通道（≥15 日）+ 年线防守 → N≥2 回踩下轨 + 地量 → 买点1 PROBE → 买点2 BREAKOUT → 三日不重回 / 基准点止损 / MA20 跟踪。

## 信号枚举

| 类型 | 含义 |
|------|------|
| `CSB_SETUP` | 通道+年线+回踩+地量成立（观察） |
| `CSB_PROBE` | 买点1 缩量止跌试仓 |
| `CSB_BREAKOUT` | 买点2 放量突破上轨/前高 |
| `CSB_FALSE_BREAK` | 突破后三日收盘跌回上轨下 |
| `CSB_STOP` / `CSB_TRAIL` | 基准止损 / MA 跟踪 |

## 默认参数（节选）

见 `get_default_csb_config()`：

- `channel.ma_squeeze_pct=0.04`，`squeeze_days=15`，`touch_tol_pct=0.015`，`min_touches=2`
- `dry_vol.dry_vol_ratio=0.55`
- `entry.vol_expand_mult=2.0`，`break_pct=0.02`，`body_min_pct=0.03`
- `position.probe_pct=0.12`，`breakout_add_pct=0.25`
- `defense.false_break_days=3`，`trail_ma=20`
- `backtest.horizon_days=10`，`target_pct=0.10`

## 数据表

- `csb_strategy_configs`：多版本参数
- `csb_signal_trace`：唯一键 `(code, trade_date, config_id, signal_type)`
- `csb_backtest_tasks`：回测任务/报告同源（对齐 URT）

迁移：`python migrations/add_csb_tables.py`

## API

- 选股：`GET /api/screening/csb-strategy`
- 追溯：`GET /api/stock/csb/signal-history`，`POST /api/stock/csb/recompute`
- 管理端：`/api/admin/csb/*`（配置 / 预计算 / 回测 / 报告 / 审计，对齐 URT）

## 管理端

路由 `/csb-management`，四页签：策略参数 / 回测管理 / 报告与分析 / 操作记录。

## 预计算

- 日终 cron：`csb_signals_cn`（默认 19:50，`ENABLE_CSB_PRECOMPUTE`）
- 采集流程节点：`csb_signals_cn`
- 管理端：单日预计算、区间 refresh、purge

## 前端

- 选股 Tab「通道突破」：`channel.screening.tab.csb`
- 历史页：`stock_csb_trace.html`
