# A股周线数据系统 — 设计与使用手册（合并版）

本文档由原 `weekly_data_README.md`、`weekly_data_quickstart.md`、`weekly_data_implementation.md`、`weekly_data_api.md`、`weekly_data_strategy_update.md` 合并而成，并已通读相关程序代码并更新。**后续以本文档为准**，原五份文档可保留作历史参考。

---

## 一、概述与文档导航

### 1.1 系统简介

周线数据系统基于已有**日线数据**自动生成周线 K 线，用于技术分析与图表展示。**不依赖外部周线 API**，数据来源为本地 `historical_quotes`（A股）、`historical_quotes_hk`（港股）等日线表。

**核心特性**：

- 基于日线数据聚合生成，可自定义计算规则
- 支持**每日更新当前周**（工作日定时任务），实时性更好
- 支持历史区间批量生成
- 提供多周期 API（日/周/月/季/半年/年），周线可用于 K 线图与选股

### 1.2 推荐阅读路径

| 角色       | 建议阅读顺序 |
|------------|--------------|
| 新手/运维  | 第二节（快速开始）→ 第六节（使用示例）→ 第八节（常见问题） |
| 开发       | 第三节（设计与实现）→ 第四节（定时任务）→ 第五节（API） |
| 对接前端   | 第五节（API）→ 第六节（使用示例） |

### 1.3 技术栈与数据流

| 组件     | 技术/说明 |
|----------|------------|
| 编程语言 | Python 3.8+ |
| 数据处理 | pandas |
| 数据库   | PostgreSQL（周线生成器使用 `backend_core.database.db`） |
| 生成器   | `backend_core/data_collectors/akshare/weekly_collector.py`（A股）、`hk_weekly_collector.py`（港股） |
| 定时任务 | APScheduler（`backend_core/data_collectors/main.py`） |
| API      | FastAPI，`backend_api`（多周期列表、K 线接口） |

**数据流**：

```
日线表 (historical_quotes / historical_quotes_hk)
    → WeeklyDataGenerator / HKWeeklyDataGenerator（重采样 + 指标计算）
    → 周线表 (weekly_quotes / hk_weekly_quotes)
    → API：/api/quotes/historical/multi-period?period=weekly、/api/stock/kline_hist?period=weekly
    → 前端 K 线图等
```

---

## 二、快速开始

### 2.1 环境要求

- 操作系统：Windows / Linux / macOS  
- Python：3.8+  
- 数据库：PostgreSQL 12+  
- 依赖：`pandas`、`sqlalchemy`、`psycopg2-binary`（或项目已有依赖）

### 2.2 数据库与数据准备

- 周线生成器连接：`backend_core.database.db` 中配置的 PostgreSQL（见 `backend_core/database/db.py`）。  
- 确保日线表有数据，例如：

```sql
SELECT COUNT(*) FROM historical_quotes;
SELECT MIN(date), MAX(date) FROM historical_quotes;
```

- A 股周线生成器使用的**股票列表**来自 `stock_basic_info` 表（非 historical_quotes），需保证该表有代码。

### 2.3 测试模式运行（推荐首次使用）

在项目根目录执行，仅处理前 5 只股票：

```bash
python backend_core/data_collectors/akshare/weekly_collector.py 2025-01-01 2025-11-30 --test
```

### 2.4 验证生成结果

```sql
SELECT COUNT(*) FROM weekly_quotes;
SELECT * FROM weekly_quotes WHERE code = '000001' ORDER BY date DESC LIMIT 10;
```

### 2.5 全量或指定范围生成

```bash
# 指定日期范围
python backend_core/data_collectors/akshare/weekly_collector.py 2025-01-01 2025-11-30

# 指定股票
python backend_core/data_collectors/akshare/weekly_collector.py 2025-01-01 2025-11-30 --stocks 000001 600000
```

---

## 三、系统设计与实现

### 3.1 方案说明

周线数据由**日线数据聚合**生成，不直接调用 AKShare 周线 API。实现文件：

- A 股：`backend_core/data_collectors/akshare/weekly_collector.py`（类 `WeeklyDataGenerator`）
- 港股：`backend_core/data_collectors/akshare/hk_weekly_collector.py`（类 `HKWeeklyDataGenerator`，表 `hk_weekly_quotes`）

### 3.2 核心逻辑

1. **数据来源**：从 `historical_quotes`（或港股对应日线表）按 code、日期范围查询日线。  
2. **时间重采样**：使用 `pandas` 的 `resample('W-FRI')`，以**周五**为周结束日。  
3. **聚合规则**：
   - 开盘价：该周**第一个交易日**开盘价  
   - 最高价：该周最高价  
   - 最低价：该周最低价  
   - 收盘价：该周**最后一个交易日**收盘价  
   - 成交量/成交额：该周求和  
4. **衍生指标**：
   - 涨跌幅：`(本周收盘 - 上周收盘) / 上周收盘 × 100`（用 `pct_change`）  
   - 涨跌额：本周收盘 - 上周收盘  
   - 振幅：`(本周最高 - 本周最低) / 上周收盘 × 100`  
5. **为计算涨跌幅**：生成时会将查询起始日向前扩展约 40 天，以拿到“上一周”收盘价。  
6. **写入**：`INSERT ... ON CONFLICT (code, date) DO UPDATE`，实现覆盖更新。

### 3.3 数据表结构（A 股 weekly_quotes）

生成器内建表逻辑（与当前实现一致）：

```sql
CREATE TABLE IF NOT EXISTS weekly_quotes (
    code TEXT,
    ts_code TEXT,
    name TEXT,
    market TEXT,
    date TEXT,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    amount REAL,
    change_percent REAL,
    change REAL,
    amplitude REAL,
    turnover_rate REAL,
    collected_source TEXT,
    collected_date TIMESTAMP,
    PRIMARY KEY (code, date)
);
```

港股为 `hk_weekly_quotes`，结构类似。

### 3.4 日志与操作记录

- 生成日志：运行目录下的 `weekly_generation.log`（A股）、`hk_weekly_generation.log`（港股）。  
- 操作记录：写入 `historical_collect_operation_logs`（如 `operation_type = 'generate_weekly_from_daily'`）。

---

## 四、定时任务与更新策略

### 4.1 当前策略（已实施）

- **更新方式**：**每日更新当前周**，只生成/更新“本周一至当前日”的周线，覆盖写入当周对应周五日期的记录。  
- **执行时间**（工作日）：
  - A 股周线：**周一至周五 16:25**
  - 港股周线：**周一至周五 17:03**  
- **任务入口**：`backend_core/data_collectors/main.py` 中 `generate_weekly_data()`、`generate_hk_weekly_data()`，内部调用 `generate_current_week_data()`。

### 4.2 当前周的计算范围

- 逻辑：取“本周一”到“今天”的日线，重采样后得到当周一条记录，日期标为当周周五。  
- 为算涨跌幅会向前多查约 40 天日线。  
- 周六、周日不执行；若需“周末再跑一次”可自行加任务或沿用现有逻辑。

### 4.3 历史数据

历史周线需**手动执行**生成，例如：

```bash
python backend_core/data_collectors/akshare/weekly_collector.py 2020-01-01 2025-12-31
```

---

## 五、API 接口（与代码一致）

### 5.1 按股票代码获取周线 K 线（前端图表用）

- **路径**：`GET /api/stock/kline_hist`  
- **位置**：`backend_api/stock/stock_manage.py`  
- **参数**：`code`（必填）、`period=weekly`、`start_date`、`end_date`，以及 `adjust`、`indicator` 等可选参数。  
- **行为**：优先从 `weekly_quotes` 表查询；若失败或表无数据则用日线实时聚合（resample）返回。  
- **返回**：`{ "success": true, "data": [ { "date", "code", "open", "close", "high", "low", "volume", "amount", "amplitude", "pct_chg", "change", "turnover" }, ... ] }`，按日期正序。

**示例**：

```bash
GET /api/stock/kline_hist?code=000001&period=weekly&start_date=2025-01-01&end_date=2025-11-30
```

### 5.2 多周期列表（分页、关键词）

- **路径**：`GET /api/quotes/historical/multi-period`  
- **位置**：`backend_api/multi_period_quotes_routes.py`  
- **参数**：`period=weekly`、`page`、`page_size`、`keyword`（股票代码或名称）、`start_date`、`end_date`。  
- **说明**：查询 `weekly_quotes` 表，分页返回多条记录，适合列表/筛选，**不是**按单只股票时间序列的 K 线接口。  
- **返回**：`{ "success": true, "data": [...], "total", "page", "page_size", "period" }`，每条含 `code, name, date, open, high, low, close, volume, amount, change_percent`。

**示例**：

```bash
GET /api/quotes/historical/multi-period?period=weekly&keyword=000001&start_date=2025-01-01&end_date=2025-11-30&page=1&page_size=20
```

### 5.3 前端调用与 ECharts

- 画周线 K 线图：使用 **kline_hist**，`period=weekly`，将返回的 `data` 按日期正序后传入 ECharts。  
- K 线单条格式：`[open, close, low, high]`（开、收、低、高）。  
- 多周期列表需按股票筛选时，可用 `keyword=股票代码` 或在前端做过滤。

---

## 六、使用示例

### 6.1 命令行

```bash
# 测试（前 5 只）
python backend_core/data_collectors/akshare/weekly_collector.py 2025-01-01 2025-11-30 --test

# 全量日期范围
python backend_core/data_collectors/akshare/weekly_collector.py 2025-01-01 2025-11-30

# 指定股票
python backend_core/data_collectors/akshare/weekly_collector.py 2025-01-01 2025-11-30 --stocks 000001 600000 000002
```

### 6.2 手动触发“当前周”更新

```bash
python -c "from backend_core.data_collectors.akshare.weekly_collector import WeeklyDataGenerator; WeeklyDataGenerator().generate_current_week_data()"
```

### 6.3 API 调用示例

```javascript
// 周线 K 线（按股票）
const resp = await fetch(
  '/api/stock/kline_hist?code=000001&period=weekly&start_date=2025-01-01&end_date=2025-11-30'
);
const { data } = await resp.json();
// data 为 [{ date, code, open, close, high, low, volume, ... }, ...]
```

### 6.4 SQL 查询

```sql
-- 某只股票最近 20 周
SELECT * FROM weekly_quotes WHERE code = '000001' ORDER BY date DESC LIMIT 20;

-- 统计
SELECT COUNT(DISTINCT code) AS stock_count, COUNT(*) AS total_rows FROM weekly_quotes;
```

---

## 七、常见问题与运维

### 7.1 数据库连接失败

- 周线生成器使用 `backend_core.database.db` 的 `SessionLocal`，请检查该模块中配置的主机、端口、用户名、密码。  
- 确认 PostgreSQL 已启动，防火墙允许连接。

### 7.2 没有生成数据

- 检查日线表在对应日期范围内是否有数据（如 `historical_quotes` 中该 code、日期）。  
- A 股生成器依赖 `stock_basic_info` 提供股票列表，若该表为空则不会生成。  
- 查看 `weekly_generation.log` 或 `hk_weekly_generation.log` 中的报错。

### 7.3 涨跌幅为 NULL

- 第一周无“上一周收盘价”，涨跌幅、涨跌额、振幅可能为 NULL，属正常。查询时可过滤 `WHERE change_percent IS NOT NULL`。

### 7.4 生成速度慢

- 缩小日期范围或使用 `--stocks` 只生成部分股票。  
- 为 `historical_quotes`、`weekly_quotes` 的 (code, date) 建索引有利于查询。

### 7.5 定时任务未执行

- 确认已启动调度进程：`python -m backend_core.data_collectors.main`。  
- 当前 A 股周线为工作日 16:25、港股 17:03，请在该时间段后查看日志与 `weekly_quotes` / `hk_weekly_quotes` 的 `collected_date`。

### 7.6 数据校验

可对比某一周的日线聚合结果与 `weekly_quotes` 中对应 code、date 的 open/high/low/close/volume/amount，应与 resample 规则一致。

---

## 八、版本与代码索引

| 项目         | 路径或说明 |
|--------------|------------|
| A 股周线生成器 | `backend_core/data_collectors/akshare/weekly_collector.py` |
| 港股周线生成器 | `backend_core/data_collectors/akshare/hk_weekly_collector.py` |
| 定时任务配置 | `backend_core/data_collectors/main.py`（generate_weekly_data, generate_hk_weekly_data） |
| 周线 K 线 API | `backend_api/stock/stock_manage.py`（get_kline_hist，period=weekly） |
| 多周期列表 API | `backend_api/multi_period_quotes_routes.py`（period=weekly → weekly_quotes） |
| 数据库连接（生成器） | `backend_core/database/db.py` |
| 日线表（A 股） | `historical_quotes` |
| 日线表（港股） | `historical_quotes_hk` |
| 周线表（A 股） | `weekly_quotes` |
| 周线表（港股） | `hk_weekly_quotes` |

**文档版本**：合并版 v1，已按当前代码更新（定时任务时间、API 路径与参数、表名与生成器逻辑）。  
**最后更新**：以合并时代码为准。
