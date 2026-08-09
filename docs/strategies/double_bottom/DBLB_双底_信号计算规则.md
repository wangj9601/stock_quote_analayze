# DBLB（双底）信号计算规则说明

本文档对应管理端「双底策略（DBLB）」MVP：经典 W 双底识别，支持形成中 / 已确认两种状态；可按行业板块、概念板块、个股限定分析范围。本期不对用户选股前端开放，不做回测。

## 1. 总体流程

1. 按股票池模式解析代码列表（行业 / 概念 / 个股 / 全市场）
2. 批量加载日线 OHLC（不复权），截断到基准交易日
3. 在回看窗内识别局部低点，配对双底并确定颈线
4. 按收盘是否突破颈线划分为 `forming` / `confirmed`
5. 试算直接返回；预计算写入 `dblb_signal_trace`

## 2. 形态规则（规则 A+B）

### 2.1 局部低点

- 回看窗默认 `lookback_days=120`
- 局部低点：左右各 `swing_left/swing_right`（默认 3）根内为最低

### 2.2 双底配对

在最近合法低点对 `(L1 更早, L2 更新)` 上要求：

- 间隔根数 ∈ `[min_trough_gap_bars, max_trough_gap_bars]`（默认 8~60）
- 两底价差相对均值 ≤ `trough_tol_pct`（默认 3%）
- 中间最高价为颈线 `neckline`
- `(neckline - min(L1,L2)) / min(L1,L2) ≥ min_rise_to_neck_pct`（默认 5%）
- L2 之后不出现明显破底（低于谷底再降超过容差）

### 2.3 状态

| 状态 | 含义 |
|------|------|
| `forming` | 形态成立，且 **尚未** 出现收盘突破颈线（含 `confirm_buffer_pct`） |
| `confirmed` | L2 之后某日收盘突破颈线；记录首次 `confirm_date` |

可选：`require_volume_expand=true` 时，确认日成交量需 ≥ 近 `volume_lookback` 日均量 × `volume_expand_ratio`。

## 3. 股票池（分析条件）

| mode | 入参 | 说明 |
|------|------|------|
| `industry_board` | `industry_board_codes[]` | 行业成分并集 |
| `concept_board` | `concept_board_codes[]` | 概念成分并集 |
| `stocks` | `stock_codes[]` | 个股多码 |
| `market` | （无上限） | 全市场；可选 `universe_limit` 运维截断，默认不截断（较慢）。命中后「所属板块」按同花顺行业归属填充。命中条数默认不截断（忽略历史 `scan.max_results=500`） |

多板取并集去重；股票池为空时 API 返回 400。

## 4. 管理端用法

路径：`/admin/#/dblb-management`

1. **策略配置**：新建 / 编辑 `config_params` JSON / 设默认  
2. **分析试算 / 预计算**：  
   - **试算（利旧入库）**：对股票池内已有 `(code, trade_date, config_id)` 信号直接复用，仅计算缺失代码；新命中默认写入 `dblb_signal_trace`  
   - **强制计算**：忽略利旧，全量重算并 upsert；范围内不再命中的旧信号会删除  
   - **写入预计算**：等同强制计算并入库  
3. **信号结果**：按交易日查询已落库信号，可导出 CSV  

API 前缀：`/api/admin/dblb`

- `GET/POST /strategy-configs`，`PUT .../update`，`PATCH .../default`
- `POST /trial`（`persist` 默认 true；`force=true` 强制重算）
- `POST /precompute/trigger`（强制重算并入库）
- `GET /signals`

## 5. 数据表

- `dblb_strategy_configs`：参数版本  
- `dblb_signal_trace`：日终信号（`code + trade_date + config_id` 唯一）

建表脚本：`migrations/add_dblb_tables.py`

## 6. 默认关键参数

见 `backend_core/strategies/double_bottom/config.py` 中 `get_default_dblb_config()`。
