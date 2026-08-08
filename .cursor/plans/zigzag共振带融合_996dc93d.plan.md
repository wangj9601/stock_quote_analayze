# ZigZag 锚定 Fib + 波动率 Pivot + 共振带融合（仓库同步说明）

> 产品边界与算法细节以实施代码为准；不改四策略选股硬门槛，仅软增强 `trade_advice` 与参考价 UI。

## 已落地

| 模块 | 路径 |
|------|------|
| ZigZag+分形 | `backend_core/analysis/swing_zigzag.py` |
| Camarilla / ATR-Pivot | `backend_core/analysis/pivot_variants.py` |
| 共振带 | `backend_core/analysis/confluence_zones.py` |
| 编排 | `classic_levels.py`（Fib 锚 ZigZag；挂 cam/atr/confluence）；`board_signals` lookback=180；`trade_advice` 软对齐 |
| UI | `profile.*`、`board_analysis.js`（Fib/Cam/VP/合） |
| 测试 | `test_swing_zigzag.py`、`test_pivot_variants.py`、`test_confluence_zones.py`、更新 classic/trade_advice/key_levels |

## 非目标（保持）

- 不通达信筹码；不 Woodie 全套替换经典 Pivot
- 共振带 / Camarilla 不作选股硬过滤
- 不做实时分笔 ZigZag
