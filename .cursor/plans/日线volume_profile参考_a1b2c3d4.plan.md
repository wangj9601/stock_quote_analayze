# 轻量日线 Volume Profile（与 KDE 对照）

## 目标

在「我的 → 支撑压力」中增加固定回看日线 Volume Profile（POC / VAH / VAL），与 KDE 最近支撑/压力并列对比，仅作辅助参考；**不改四策略硬门槛**。

## 算法（已固化）

- 模块：`backend_core/analysis/volume_profile.py`
- 回看默认 60 日；价格区间分约 24 桶；日成交量在 [low,high] 桶上均匀分摊
- POC = 最大量桶中点；价值区自 POC 扩展至总成交量 70% → VAL / VAH
- 前复权与不复权：与 KDE/Fib/Pivot 同口径（qfq 时用复权 OHLC）

## 接口

`GET /api/analysis/levels/{code}` 响应 `data` 增加：

- `volume_profile`：poc / vah / val / nearest_support / nearest_resistance / lookback …
- `vp_vs_kde`：支撑/压力的 kde vs vp 差值与是否共振（≤1.5%）

## UI

`profile.html` 支撑压力结果区：KDE 下方增加「Volume Profile（参考）」卡片 +「与 KDE 对比」表。

## 非目标

- 不做通达信筹码分布 / 分笔 VP
- 不写入 GMS/URT/SBBR/RPE 选股硬条件
- 不替代 KDE 作为主结构位

## 测试

`test/test_volume_profile.py`
