# 股票分析系统需求设计（重构版）

## 1. 个股分时图

### 1.1 功能目标
- 展示指定股票的当日分时行情数据。

### 1.2 后端实现
- 新增API：`GET /api/stock/minute_data_by_code?code=xxxxxx`
- 调用 AkShare `stock_intraday_em` 获取分时数据。
- 若为非交易日，调用 `stock_zh_a_hist_min_em` 获取最近一个交易日的分钟数据。
- 返回字段：时间、最新价、成交量、均价、成交额、涨跌幅、涨跌额。

### 1.3 前端实现
- 移除模拟分时数据生成逻辑。
- 新增 `loadMinuteData()` 方法，请求API并渲染分时图。
- 切换“分时”标签时自动拉取数据。

### 1.4 测试要点
- 有效股票代码返回数据，字段齐全。
- 无效代码返回404。
- 缺参返回400。
- 交易日/非交易日数据切换正确。

---

## 2. 个股K线图

### 2.1 日线/周线/月线

#### 2.1.1 功能目标
- 展示指定股票的历史K线（日/周/月）数据。

#### 2.1.2 后端实现
- API：`GET /api/stock/kline_hist`
- 参数：code、period（daily/weekly/monthly）、start_date、end_date、adjust
- 调用 AkShare `stock_zh_a_hist`。
- 返回字段：日期、股票代码、开盘、收盘、最高、最低、成交量、成交额、振幅、涨跌幅、涨跌额、换手率。

#### 2.1.3 前端实现
- 移除K线模拟数据生成逻辑。
- `loadKlineData()` 根据周期参数请求API并渲染K线图。
- 切换周期按钮时自动刷新。

#### 2.1.4 测试要点
- 有效参数返回数据，字段齐全。
- 无效代码/缺参返回404/400。
- 数值字段格式化（两位小数，成交量为整数）。

### 2.2 小时线/分钟线

#### 2.2.1 功能目标
- 展示指定股票的小时线/分钟线K线数据。

#### 2.2.2 后端实现
- API：`GET /api/stock/kline_min_hist`
- 参数：code、period（1/5/15/30/60）、start_time、end_time、adjust
- 调用 AkShare `stock_zh_a_hist_min_em`。
- 返回字段同日K。

#### 2.2.3 前端实现
- 移除所有分钟线模拟数据生成逻辑。
- `loadKlineData()` 支持不同分钟周期，自动请求API并渲染。

#### 2.2.4 测试要点
- 不同周期、时间区间数据正确。
- 切换周期按钮时自动刷新。

---

## 3. 个股资金流向

### 3.1 功能目标
- 展示指定股票的资金流向数据。

### 3.2 后端实现
- 新增API：`GET /api/stock/fund_flow/{code}`
- 调用 AkShare 获取资金流向数据，返回主力净流入、散户净流入、日期等。

### 3.3 前端实现
- 移除资金流向模拟数据生成逻辑。
- `loadFlowData()` 请求API并渲染资金流向图表。

### 3.4 测试要点
- 数据字段与前端解析一致。
- 无效代码/缺参返回错误。

---

## 4. 个股财务数据

### 4.1 关键指标

#### 4.1.1 功能目标
- 展示指定股票最新报告期的财务关键指标。

#### 4.1.2 后端实现
- 新增API，调用 AkShare 获取市盈率、市净率、ROE、ROA、营业收入、净利润、EPS、BPS 等。

#### 4.1.3 前端实现
- 请求API，赋值到财务数据标签页。

### 4.2 盈利能力

#### 4.2.1 功能目标
- 展示指定股票最新报告期的盈利能力数据。

#### 4.2.2 后端实现
- 新增API，调用 AkShare `stock_financial_abstract_ths` 获取主要财务指标列表。

#### 4.2.3 前端实现
- 请求API，赋值到财务数据标签页的盈利能力区域。

---

## 5. 指数/行业板块实时行情采集

### 5.1 指数实时行情

#### 5.1.1 后端实现
- 新建采集类，调用 AkShare `stock_zh_index_spot_em`。
- 数据写入 `index_realtime_quotes` 表。
- 定时任务每5分钟采集一次。
- API `/indices` 从数据库读取并返回上证、深证、创业板、沪深300等指数数据。

### 5.2 行业板块实时行情

#### 5.2.1 后端实现
- 新建采集类，调用 AkShare `stock_board_industry_name_em`。
- 数据写入 `industry_board_realtime_quotes` 表。
- 定时任务每30分钟采集一次。
- API `/industry_board` 从数据库读取行业板块数据。

### 5.2 自选股历史行情

#### 5.2.1 后端实现
- 新建采集类，从'watchlist'表读取我的自选股数据，按'stock_code'字段排重。按'stock_code'列表循环调用 AkShare `stock_zh_a_hist`，每次调用延时10秒。
    - AkShare `stock_zh_a_hist` 输入参数：symbol、period（'daily'）、start_date（'YYYYMMDD'）、end_date（'YYYYMMDD'）、adjust（'qfq'）。
    - 每次采集时长为此股票30年内历史数据。
- 数据写入 `historical_quotes` 表。
- 采集日志写入'watchlist_history_collection_logs'表，字段包括id，stock_code，affected_rows,status,erro_message，created_at等。
- 每次采集时，需从'watchlist_history_collection_logs'表 判断'stock_code'是否已经采集过历史数据，已经采集过，不再采集。
- 定时任务每天采集一次。
- 表结构 CREATE TABLE watchlist_history_collection_logs (
        id SERIAL PRIMARY KEY,
        stock_code VARCHAR(20),
        affected_rows INTEGER,
        status VARCHAR(20),
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

---

## 6. 首页自选股列表

### 6.1 后端实现
- `get_watchlist` 从 `stock_realtime_quote` 表读取自选股实时行情数据，格式化输出。

---

## 7. 个股新闻与公告

### 7.1 新闻

#### 7.1.1 后端实现
- 新增API，调用 AkShare `stock_news_em` 获取指定股票新闻资讯。
- 数据写入个股新闻公告表。

#### 7.1.2 前端实现
- 请求API，展示新闻数据。

### 7.2 公告

#### 7.2.1 后端实现
- 新建采集类，调用 AkShare `stock_notice_report`。
- 数据写入公告数据表。
- 定时任务每日采集。

---

## 8. 个股研报

### 8.1 后端实现
- 新增API `research_reports`，迁移原有研报读取逻辑。
- 数据写入个股研报信息表，字段包括序号、股票代码、简称、报告名称、评级、机构、盈利预测等。

---

## 9. 数据库与ORM重构

### 9.1 目标
- 全面切换为 PostgreSQL，统一数据库访问为 SQLAlchemy ORM。

### 9.2 步骤
1. 修改 `.env` 或环境变量，设置 `DATABASE_URL` 为 PostgreSQL 连接串。
2. 确认 `requirements.txt` 包含 `psycopg2-binary`。
3. 检查/补充所有 ORM Model，兼容 PostgreSQL。
4. 替换所有 `sqlite3` 相关代码为 SQLAlchemy ORM。
5. 测试所有接口，确保数据读写正常。

---

## 10. 其他注意事项

- 所有API需有详细日志，便于排查。
- 所有表结构、字段类型需兼容 PostgreSQL。
- 历史数据如需迁移，编写脚本导入 PostgreSQL。

---

如需详细接口字段、表结构、采集/定时任务代码示例，可进一步补充。  
如需自动化脚本或代码重构示例，请指定具体模块或功能。

---

**本重构版文档更适合团队协作、开发排期、接口联调和后续维护。**  
如需导出为markdown、word或其他格式，可随时告知！


