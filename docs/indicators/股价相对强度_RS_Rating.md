# 股价相对强度 RS Rating（IBD 风格）

## 一句话

对全市场 A 股做多周期加权动量得分，再做**截面百分位排名**，得到可横向比较的 **RS Rating（1–99）**。  
用作个股交易参考，**不是** RSI，也**不是** RPE 板块比价 Z。

## 公式

```
ROC(n) = P_t / P_{t-n} - 1
RS_Raw = 0.4×ROC(63) + 0.2×ROC(126) + 0.2×ROC(189) + 0.2×ROC(252)
RS_Rating = round(percentile_rank × 98 + 1)   # 整数 1–99
```

- 窗口单位为**有效交易日**根数。
- V1 价格口径：`historical_quotes.close`（不复权）；除权除息对长窗口有影响，后续可评估前复权批算。
- 百分位：当日有效宇宙内并列取平均秩。
- 覆盖率：有效 `RS_Raw` 股票数 / 候选池 < **90%** 时，当日只落库 `rs_raw`，不发布 `rs_rating`。

## 候选池（CN）

- 当日 `historical_quotes` 有行情、代码 6 位
- `stock_basic_info` 存在且 `collect_enabled`
- 名称排除 ST、含「退」

港股：**不支持**。

## 解读档（仅展示）

| RS | 文案 |
|----|------|
| ≥90 | 很强 |
| 70–89 | 偏强 |
| 50–69 | 中性 |
| 30–49 | 偏弱 |
| &lt;30 | 很弱 |

## 日终触发

采集流程节点 **`rs_rating_cn`**（A股相对强度RS预计算）：

- 挂在「A股收盘后标准流程」中：`cn_industry_board` 之后、`gms_signals_cn` 之前
- 由流程 cron / 管理端「运行流程」或「重启环节」触发
- **不**在 `main.py` 分散 cron 中单独注册

代码入口：

- `backend_core/indicators/rs_rating/scheduled_precompute.py` → `scheduled_rs_rating_cn`
- 适配器：`exec_rs_rating_cn`

## 存储

表 `rs_ratings`，主键 `(code, date, market_type)`，V1 仅 `market_type='CN'`。

迁移：

```bash
python migrations/add_rs_ratings_table.py
python migrations/add_rs_rating_workflow_node.py
```

## API

`GET /api/analysis/rs-rating?code=&date=`

- 读预计算，不现算全市场
- 返回 `rs_rating`、`rs_raw`、四分期 ROC、`strength_label`、`universe_size` 等

## 前端

个股分析页（`stock.html?tab=analysis`）在「策略分析」与「阻力支撑」之间展示 **股价相对强度（RS Rating）** 区块。

## 与其它能力的区别

| 能力 | 含义 |
|------|------|
| 本 RS Rating | 全市场截面百分位（相对「所有股票」） |
| RPE Z | 个股相对**板块**量权基准的比价偏离 |
| RSI | 自身涨跌动量振荡 |
| PVFRS 即时强度 | 相对自身均线偏离 |
