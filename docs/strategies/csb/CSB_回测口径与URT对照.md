# CSB 回测口径说明（对齐 URT 管理端能力）

## 出场模式 `exit_mode`

| 模式 | 说明 |
|------|------|
| `hit_rate` | 以 BREAKOUT（可含 PROBE）为样本，次日开盘入场；前瞻 `horizon_days` 是否触及 `target_pct`～`target_pct_max`；统计命中率与假突破率 |
| `risk_exit` | 纪律出场：三日不重回清仓、跌破基准点止损；汇总胜率 / 均盈亏 / `exit_reason` |
| `structure_exit` | 结构出场：基准点 + MA20 跟踪抬止损（首版）；swing 阶梯为后续增强 |

非 `hit_rate` 且 `compare_hit_rate=true` 时，完成后自动排队同配置命中率对照任务（对齐 URT）。

## 信号质量 `signal_quality_mode`

- `standard`：过 SETUP 门槛的入场
- `premium`：更严（粘合天数 / 触碰次数 / 放量倍数等，见配置 `premium` 节）

## 股票池

`all` / `single` / `custom` / `watchlist` / `gms_watchlist` / `industry_board` / `concept_board`，可选 `cn_board_segment`。

`gms_watchlist` 仅借用 GMS 观察股代码列表，不调用 GMS 引擎。

## 导出

任务明细 CSV / XLSX；详情 PDF（依赖 xhtml2pdf 时可用）。报告页与 completed 任务同源。

## 与 URT 对照

管理端任务生命周期、报告、预计算/purge/refresh、系统状态、审计与 URT 同级；出场与因子分桶使用 CSB 规则与通道/量能字段，不复用 URT 结构 KDE / HVZ。
