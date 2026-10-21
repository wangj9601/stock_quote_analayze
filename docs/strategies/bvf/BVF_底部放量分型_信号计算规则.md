# BVF（底部放量分型）信号计算规则说明

本文档对应管理端「底部放量分型（BVF）」MVP：前复权日线三 K 底分型 + 底部区域 + 中 K 放量。本期不对用户选股前端开放，不做回测，不做日终定时预计算。

## 1. 总体流程

1. 按股票池模式解析代码列表（行业 / 概念 / 个股 / 全市场）
2. 批量加载日线 OHLC（不复权原始量），截断到基准交易日 `T`
3. 对每只股票用库内复权因子现算前复权 OHLC；缺因子则跳过
4. 硬过滤：名称含 ST/\*ST、基准日停牌（无当日 K 或成交量为 0）、上市不足 `min_listing_bars` 个交易日
5. 仅当右 K 日期等于 `T` 时检测底分型 + 底部 + 放量
6. 试算直接返回；预计算写入 `bvf_signal_trace`

## 2. 形态规则

### 2.1 底分型（原始三 K，无包含合并）

在前复权序列上取连续三根：左 `L`、中 `M`、右 `R`（`R` 为序列最后一根且日期 = `T`）：

- `M.high < L.high` 且 `M.high < R.high`
- `M.low < L.low` 且 `M.low < R.low`

信号日 = `R` 的交易日。

### 2.2 底部区域

以 **中 K** 为窗口终点（含中 K），取近 `lookback_bottom`（默认 60）根前复权 `low` 的最小值 `min_low`，要求：

\[
M.low \le min\_low \times (1 + bottom\_tol)
\]

默认 `bottom_tol = 0.03`。

### 2.3 放量

中 K 成交量（原始量，不随价格复权）满足：

\[
M.volume \ge mean(前\ vol\_ma\ 日成交量) \times vol\_ratio
\]

默认 `vol_ma = 20`，`vol_ratio = 2.0`。前 `vol_ma` 日不含中 K。右 K 不强制放量。

### 2.4 展示字段（非硬筛）

- `bottom_dev_pct`：\((M.low - min\_low) / min\_low\)
- `vol_ratio_actual`：\(M.volume / 前20日均量\)
- `left_date` / `mid_date` / `right_date`
- `limit_flag`：右 K 相对昨收涨跌幅粗分涨停/跌停/普通（仅标记，不剔除）

## 3. 股票池

与双底相同：`industry_board` / `concept_board` / `stocks` / `market`。

## 4. 管理端

路径：`/admin/#/bvf-management`  
API 前缀：`/api/admin/bvf`

- 策略配置 CRUD / 设默认
- `POST /trial`（`persist` 默认 true；`force=true` 强制重算）
- `POST /precompute/trigger`
- `GET /signals` + CSV 导出

## 5. 数据表

- `bvf_strategy_configs`
- `bvf_signal_trace`（`code + trade_date + config_id` 唯一）

建表脚本：`migrations/add_bvf_tables.py`

## 6. 默认参数

见 `backend_core/strategies/bvf/config.py` 中 `get_default_bvf_config()`。
