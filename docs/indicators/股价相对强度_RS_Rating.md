# 股价相对强度 RS Rating（IBD 风格）

## 一句话

对全市场 A 股做多周期加权动量得分，再做**截面百分位排名**，得到可横向比较的 **RS Rating（1–99）**。  
用作个股/管理端的交易参考，**不是** RSI，也**不是** RPE 板块比价 Z。

## 公式

```
ROC(n) = P_t / P_{t-n} - 1          # n 为有效交易日根数
RS_Raw = 0.4×ROC(63) + 0.2×ROC(126) + 0.2×ROC(189) + 0.2×ROC(252)
RS_Rating = round(percentile_rank × 98 + 1)   # 整数 1–99
```

- 百分位：当日有效宇宙内并列取平均秩；`percentile_rank ∈ [0,1]`。
- 覆盖率：有效 `RS_Raw` 数 / 候选池 &lt; **90%** 时，当日只落库 `rs_raw`，**不发布** `rs_rating`。

## 价格口径（前复权）

| 项 | A 股 | 港股 |
|----|------|------|
| 原始行情 | `historical_quotes.close`（不复权） | `historical_quotes_hk.close` |
| 复权方式 | 库内 `stock_adj_factor` **现算前复权** | 同左 |
| 因子源 | 优先 `akshare_sina_qfq`，否则 `baostock_qfq` | 优先 `akshare_sina_hk_qfq`，否则 `akshare_em_hk_qfq` |
| 外网 | **不打外网**；无库内因子不进入当日宇宙 | 同左 |
| 落库 | `rs_ratings` | **`rs_ratings_hk`（独立表）** |

改口径或补齐因子后，需分别重跑 `rs_rating_cn` / `rs_rating_hk`。

## 候选池

### A 股（CN）

- 当日 `historical_quotes` 有行情、代码 6 位
- `stock_basic_info` 存在且 `collect_enabled`
- 名称排除 ST、含「退」
- 另需：足够窗口的前复权收盘序列（约 ≥253 根）及库内复权因子（`akshare_sina_qfq` / `baostock_qfq`）
- 落库：`rs_ratings`（`market_type='CN'`）

### 港股（HK）

- 当日 `historical_quotes_hk` 有行情、代码 5 位
- `stock_basic_info_hk` 存在且 `collect_enabled`
- 另需：足够窗口的前复权收盘序列（约 ≥253 根）及库内港股复权因子（优先 `akshare_sina_hk_qfq`，否则 `akshare_em_hk_qfq`）
- **独立落库**：`rs_ratings_hk`（主键 `(code, date)`，与 A 股表分离）
- 港股截面只在港股宇宙内排名，**不与 A 股混排**

## 解读档（仅展示，不参与计算）

| RS | 文案 |
|----|------|
| ≥90 | 很强 |
| 70–89 | 偏强 |
| 50–69 | 中性 |
| 30–49 | 偏弱 |
| &lt;30 | 很弱 |

## 执行周期建议

| 场景 | 建议 |
|------|------|
| 正常交易日（A 股） | **每日 1 次**，挂在 A 股收盘采集流程中、日 K 入库之后 |
| 正常交易日（港股） | **每日 1 次**，挂在港股收盘采集流程中、指数归档之后、URT/GMS 之前 |
| 休市 | 随流程 `skip_on_holiday=CN/HK` **跳过** |
| 补采 / 改算法 / 补因子后 | 对目标交易日**按需重跑** `rs_rating_cn` / `rs_rating_hk`，或跑批量脚本 |
| 盘中 | **不必**；口径为日线收盘截面 |

### 批量脚本（离线回填）

```bash
# A 股：缺省行情最新交易日起向前约一年
python scripts/batch_rs_rating_precompute.py
python scripts/batch_rs_rating_precompute.py --start 2025-01-01 --end 2025-06-30

# 港股：写入 rs_ratings_hk
python scripts/batch_rs_rating_hk_precompute.py
python scripts/batch_rs_rating_hk_precompute.py --start 2025-01-01 --end 2025-06-30
python scripts/batch_rs_rating_hk_precompute.py --dry-run
```

按交易日逐日调用全市场预计算，与 HTTP 强制重算上限无关。

## 日终触发（采集流程节点）

节点 **`rs_rating_cn`**（显示名：A股相对强度RS预计算）：

- 挂在「A股收盘后标准流程」：`cn_industry_board` 之后、`gms_signals_cn` 之前
- 代码：`scheduled_precompute.py` → `scheduled_rs_rating_cn`；适配器 `exec_rs_rating_cn`

节点 **`rs_rating_hk`**（显示名：港股相对强度RS预计算）：

- 挂在「港股收盘后标准流程」：`hk_index_historical` 之后、`urt_signals_hk` 之前
- 代码：`scheduled_precompute_hk.py` → `scheduled_rs_rating_hk`；适配器 `exec_rs_rating_hk`
- 前复权：`historical_quotes_hk` + 港股 `stock_adj_factor` 源

采集流程总述见 [`docs/fixed/COLLECTION_WORKFLOW.md`](../fixed/COLLECTION_WORKFLOW.md)。

## 存储

表 **`rs_ratings`**（PostgreSQL），主键 `(code, date, market_type)`，仅使用 `market_type='CN'`。

表 **`rs_ratings_hk`**（PostgreSQL），主键 `(code, date)`，港股专用。

| 字段 | 说明 |
|------|------|
| `rs_raw` | 多周期加权得分（前复权 ROC） |
| `rs_rating` | 1–99；覆盖率不足时可为 NULL |
| `roc_63/126/189/252` | 四分期收益率 |
| `universe_size` / `coverage_ratio` | 当日有效宇宙与覆盖率 |

迁移：

```bash
python migrations/add_rs_ratings_table.py
python migrations/add_rs_rating_workflow_node.py
python migrations/add_rs_ratings_hk_table.py
python migrations/add_rs_rating_hk_workflow_node.py
```

## API

### 个股最新（分析频道）

`GET /api/analysis/rs-rating?code=&date=`

- 只读预计算，**不在请求内现算全市场**
- A 股读 `rs_ratings`；港股（5 位）读 `rs_ratings_hk`
- 返回：`rs_rating`、`rs_raw`、四分期 ROC、`strength_label`、`universe_size`、`price_adjust`（`qfq`）、`market_type` 等

### 个股历史追溯

`GET /api/analysis/rs-rating/history?code=&start_date=&end_date=&limit=`

- 返回该股按日期降序的历史行（默认最多 120，上限 500）
- 独立页：`frontend/stock_rs_trace.html?code=`

### 强制重算（全市场截面）

`POST /api/analysis/rs-rating/precompute`  
`POST /api/admin/stock-basic/rs-ratings/precompute`

- Body：`trade_date`（单日，可选）或 `start_date`+`end_date`（短区间，上限 **10** 个交易日）；`market`=`CN`|`HK`（默认 `CN`）
- **语义**：重算指定日的**对应市场全截面**排名；A 股写 `rs_ratings`，港股写 `rs_ratings_hk`
- 异步任务；查询进度：`GET .../precompute/{task_id}`
- 同时仅允许一个进行中的强制任务

### 管理端列表

`GET /api/admin/stock-basic/rs-ratings?keyword=&date=&min_rating=&page=&page_size=`

- 默认取最新有评级日；按 **`rs_rating DESC NULLS LAST`**（最高在前；当前为 A 股列表）

### 管理端历史

`GET /api/admin/stock-basic/rs-ratings/history?code=&start_date=&end_date=&limit=`

- 支持 A 股 6 位 / 港股 5 位

## 前端与管理端

| 入口 | 说明 |
|------|------|
| 个股分析 | `stock.html?tab=analysis`：RS 区块含「历史追溯」链接与「展开近期历史」；标题栏亦可进追溯页 |
| 追溯页 | `stock_rs_trace.html`：历史查询 +「强制重算区间（全市场）」（起止日，最多 10 个交易日） |
| 分析工作台 | `analysis.html` 同构区块 |
| 管理端 | **股票基本信息** → **股价相对强度**：列表/追溯对话框均可按区间强制重算全市场 |

## 模块结构

```
backend_core/indicators/rs_rating/
  config.py                   # 窗口/权重/覆盖率/PRICE_ADJUST/港股因子源
  calculator.py               # ROC、RS_Raw、截面百分位
  qfq_closes.py               # A/港股不复权 K + 因子 → 前复权收盘
  universe.py / universe_hk.py
  storage.py / storage_hk.py
  scheduled_precompute.py     # A 股日终预计算
  scheduled_precompute_hk.py  # 港股日终预计算 → rs_ratings_hk
  force_precompute.py         # 强制重算异步任务（market=CN|HK）
  service.py                  # 个股 as-of / 历史查询（按市场分流）
```

## 与其它能力的区别

| 能力 | 含义 |
|------|------|
| **本 RS Rating** | 全市场截面百分位（相对「所有可评股票」），前复权多周期动量；A/港股分表分截面 |
| RPE Z | 个股相对**板块**量权基准的比价偏离 |
| RSI | 自身涨跌动量振荡（副图技术指标） |
| PVFRS 即时强度 | 相对自身均线偏离 |
| GMS「个股相对强度消失」 | 文档规则（个股 5 日涨幅 vs 板块），**未实现**，与本 RS 无关 |

RSI 等副图指标说明见 [`技术指标集成设计说明.md`](./技术指标集成设计说明.md)。
