# CAN SLIM 信号计算规则（第一期）

对应选股 API `GET /api/screening/canslim` 与引擎 `backend_core/strategies/canslim/`。

## 1. 数据依赖

| 字母 | 表 / 来源 | 采集节点 |
|------|-----------|----------|
| C/A | `stock_fina_indicator` | `fina_indicator_cn`（**Tushare 优先，失败/无 token 回退 AkShare**） |
| L | `rs_ratings` | `rs_rating_cn` |
| N 新高 | `historical_quotes` + `stock_adj_factor`（前复权现算） | 日 K / 复权因子 |
| N 杯柄 | `cupb_signal_trace` | CUPB 预计算（管理端） |
| S | `stock_basic_info.free_float_shares`、`mavol_indicators` | `stock_shares_update`、MAVOL |
| M | `index_historical_quotes` | `index_daily_cn`（**优先 AkShare**，失败可回退 Tushare） |

### 采集数据源开关

| 环境变量 | 取值 | 说明 |
|----------|------|------|
| `CANSLIM_FINA_SOURCE` | `auto`（默认）/ `tushare` / `akshare` | 财务指标源；`auto` 下 Tushare **无接口权限时立即改走 AkShare**（不会继续扫全市场） |
| `CANSLIM_INDEX_SOURCE` | `auto`（默认，**优先 AkShare**）/ `akshare` / `tushare` | 指数日线源 |
| `CANSLIM_FINA_MAX_STOCKS` | 正整数 | 限流试跑（全市场很慢） |
| `CANSLIM_FINA_YEARS_BACK` | 默认 4 | 仅 Tushare 路径使用 |
| `CANSLIM_AK_FINA_TIMEOUT` | 默认 25 | AkShare 单次请求超时（秒） |
| `CANSLIM_AK_FINA_SLEEP` | 默认 0.25 | AkShare 股票间隔（秒） |
| `CANSLIM_AK_FINA_LOG_EVERY` | 默认 10 | AkShare 进度日志间隔（只） |

AkShare 财务路径：优先 `stock_financial_abstract`（1 次/票），不足再补 `stock_financial_abstract_ths(按报告期)`；自算同比后 UPSERT。带超时与进度/ETA 日志。  
AkShare 指数路径：`stock_zh_index_daily`（如 `sh000300`）。

**禁止误用：** `quarterly_quotes` / `annual_quotes` 是 K 线聚合不是财报；`fund_*` 是 ETF 不是机构持仓。

选股**只读库表**，不对全市场现场调 AkShare/Tushare。

## 2. 合取顺序

1. 解析 `asof`（默认 `historical_quotes` 最新日）。
2. **M**：若 `M.enabled`，不通过则 `data=[]` 并返回 `message`。
3. 宇宙：`stock_basic_info` 且 `collect_enabled`，排除名称含 ST / 退。
4. 对每只票依次硬过滤 **C → A → L → N → S**（任一失败剔除）。
5. 结果按 `rs_rating` 降序。

## 3. 各字母算法

### C

- 在该股 `stock_fina_indicator` 按 `end_date` 降序，取第一条有 `q_eps_yoy` / `q_netprofit_yoy` / `q_profit_yoy` 的行。
- `ok` ⇔ 取值 ≥ `C.q_eps_yoy_min`（默认 25）。
- 可选 `C.require_sales_yoy`：同时要求 `q_sales_yoy` ≥ `C.q_sales_yoy_min`。

### A

- 筛 `end_date` 以 `1231` 结尾的年报，取最近 `A.annual_years`（默认 3）期。
- 优先各期 `basic_eps_yoy`（或 `dt_eps_yoy`）均 ≥ `A.annual_eps_yoy_min`。
- 若不满足且 `use_cagr_fallback`：用年报 `eps` 算 CAGR ≥ `cagr_min`。
- ROE：默认 `roe_source=freshest_annualized`——取最新有 ROE 的报告期；若为中报/季报则按 4/2/4÷3 年化后再与 `A.roe_min` 比较。设为 `annual` 则仍只用最新年报 ROE。
- 年报期数不足 → 失败。

### N

- 取 asof 前约 252 根日 K；若 `use_qfq`，用库内复权因子按 \(P_{qfq}=P_{raw}\times f_t/f_T\) 现算。
- `near_ok` ⇔ `close / max(high_52w) ≥ near_high_min_ratio`（默认 0.85）。
- `cupb_ok` ⇔ `cupb_signal_trace` 在 asof 及之前最新一条 `status ∈ {forming, confirmed}`。
- `ok` ⇔ near_ok **或** cupb_ok。

### S

- `circ_shares_yi = free_float_shares / 1e8` ≤ `circ_shares_max_yi`（默认 20）。
- 若 `require_up_day_volume` 且当日收盘 > 开盘：`volume / mavol20 ≥ volume_ratio_min`（默认 1.0）；缺量能数据则失败。
- 阴线日不强制放量。

### L

- 取 asof 及之前最近一日有 `rs_rating` 的截面；`rs_rating ≥ L.rs_rating_min`（默认 80）。
- 无评级 → 失败。

### M

- 读 `index_historical_quotes` 中 `M.index_ts_code`（默认 `000300.SH`）。
- `close > MA(ma_window)` 且 `MA_now > MA_{t-ma_slope_lookback}`（默认 window=50, lookback=10）。
- 指数日线不足 → 视为未确认上升。

### I

- 第一期 `ok=null`，不参与过滤。

## 4. 配置入口

`backend_core/strategies/canslim/config.py` → `get_default_canslim_config()`。  
API 查询参数：`market_filter`、`rs_min`、`asof`、`stock_code`。

## 5. 迁移

```bash
python migrations/add_canslim_tables.py
```
