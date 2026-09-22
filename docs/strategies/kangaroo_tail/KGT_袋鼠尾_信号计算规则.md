# KGT（袋鼠尾）信号计算规则说明

本文档对应管理端「袋鼠尾策略（KGT）」：日线 OHLC 识别看涨 / 看跌袋鼠尾。本期不对用户选股前端开放，不做独立回测。可与现有「长下影线」选股并存——长下影更宽、仅看涨下影；袋鼠尾双向且几何更严。

## 1. 总体流程

1. 按股票池模式解析代码列表（行业 / 概念 / 个股 / 全市场，复用双底 universe）
2. 批量加载日线 OHLC（不复权），截断到基准交易日
3. 对每只股票计算 MA20，检测基准日（或最近 N 根）是否满足袋鼠尾几何
4. 按方向过滤（`bullish` / `bearish` / `both`）输出信号
5. 试算可直接返回；预计算写入 `kgt_signal_trace`

## 2. 形态规则

日线一根 K 线识别两类：

| 类型 | `direction` | 几何条件 | 位置语义 |
|------|-------------|----------|----------|
| 看涨袋鼠尾 | `bullish` | 长下影、短/无上影、实体小 | 下方探底失败，偏反弹 |
| 看跌袋鼠尾 | `bearish` | 长上影、短/无下影、实体小 | 上方冲高失败，偏回落 |

### 2.1 公共几何（默认）

设 `range = high - low`，`body = |close - open|`：

1. `range > 0`，且振幅 `(high - low) / close ≥ min_range_pct`（默认 **2%**）
2. `body / range ≤ max_body_ratio`（默认 **1/3**）
3. 可选排除一字板：`exclude_limit_board=true` 时极小振幅剔除

### 2.2 看涨袋鼠尾

- `lower_shadow ≥ max(body × shadow_body_mult, range × shadow_range_mult)`  
  默认：`max(body × 2, range × 0.5)`
- `upper_shadow ≤ body × opposite_shadow_body_mult`（默认 **0.3**）
- 收盘在全日区间上半区：`close ≥ low + range × close_half_ratio`（默认 **0.5**）
- **趋势过滤（默认开）**：当日 `low < MA20`（`ma_period` 默认 20）

### 2.3 看跌袋鼠尾（对称）

- `upper_shadow ≥ max(body × 2, range × 0.5)`
- `lower_shadow ≤ body × 0.3`
- 收盘在下半区：`close ≤ high - range × 0.5`（即 `close_pos ≤ 1 - close_half_ratio`）
- **趋势过滤（默认开）**：当日 `high > MA20`

### 2.4 得分（0–100）

影线相对实体、振幅、收盘位置、实体瘦小加权；管理端信号列表展示 `score`，形态工具侧映射为 `confidence = score / 100`。

### 2.5 信号日

形态 K 线当日为 `signal_date` / `formed_at`；单根形态一经命中即视为已确认（`confirmed`），无 forming 阶段。

## 3. 与「长下影线」选股的区别

| 项 | 长下影线选股 | KGT 袋鼠尾 |
|----|--------------|------------|
| 方向 | 仅看涨下影 | 看涨 + 看跌 |
| 下影门槛 | ≥ 实体 ×1 | ≥ max(实体×2, 波幅×0.5) |
| 振幅 | >2% | ≥2%（可配） |
| 实体约束 | 无显式 body/range | body/range ≤ 1/3 |
| 股票池 | 排除创业板/科创板等 | 默认主板+创业板+科创板（可配） |
| 产品形态 | 用户选股策略 | 管理端形态策略 + 分析页形态识别 |

## 4. 股票池（分析条件）

与 DBLB 一致：`industry_board` / `concept_board` / `stocks` / `market`。多板取并集去重。

扫描侧可用 `scan.direction_filter` 再过滤看涨/看跌。

## 5. 管理端用法

路径：`/admin/#/kgt-management`

1. **策略配置**：新建 / 编辑 `config_params` / 设默认  
2. **分析试算 / 预计算**：试算可 `persist`；强制重算忽略利旧  
3. **信号结果**：按交易日查询，展示方向（看涨/看跌）与得分  

API 前缀：`/api/admin/kgt`

- `GET/POST /strategy-configs`，`PUT .../update`，`PATCH .../default`
- `POST /trial`
- `POST /precompute/trigger`
- `GET /signals?trade_date=`

## 6. 数据表

- `kgt_strategy_configs`：参数版本  
- `kgt_signal_trace`：日终信号（`code + signal_date + config_id` 风格对齐 `dblb_*`）

建表脚本：`migrations/add_kgt_tables.py`

## 7. 形态识别接入

- `backend_core/analysis/chart_patterns/kangaroo_tail.py` 注册家族 `kangaroo_tail`
- 命中类型：`kangaroo_tail_bullish` / `kangaroo_tail_bearish`
- 形态工具默认勾选「袋鼠尾」；**默认关闭趋势过滤**以便个股标注更全

## 8. 默认关键参数

见 `backend_core/strategies/kangaroo_tail/config.py` 中 `get_default_kgt_config()`。
