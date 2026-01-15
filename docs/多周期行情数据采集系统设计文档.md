# 多周期行情数据采集系统设计文档

## 1. 系统概述

本系统旨在为股票分析系统提供多周期（周、月、季、半年、年）的K线数据。系统覆盖 A股 和 港股 两个市场，基于已有的日线数据自动生成各周期的聚合数据，确保存储的高效性和数据的一致性。

## 2. 核心设计理念

- **基于日线生成**: 所有长周期数据均由日线数据（`historical_quotes` / `hk_historical_quotes`）聚合生成，不依赖外部API直接获取长周期数据。这确保了数据来源的一致性，且更易于维护。
- **独立存储**: 每个周期、每个市场的数据存储在独立的数据库表中，便于查询优化和管理。
- **定时增量更新**: 系统通过定时任务每日/每周自动更新最新数据，支持增量更新，避免全量重算的开销。
- **统一架构**: A股和港股采用相同的架构设计和代码模式，降低认知和维护成本。

## 3. 数据流程

```mermaid
graph TD
    Daily[日线数据 (Daily Data)] --> |聚合 Resample| Weekly[周线数据 (Weekly)]
    Daily --> |聚合 Resample| Monthly[月线数据 (Monthly)]
    Daily --> |聚合 Resample| Quarterly[季线数据 (Quarterly)]
    Daily --> |聚合 Resample| SemiAnnual[半年线数据 (Semi-Annual)]
    Daily --> |聚合 Resample| Annual[年线数据 (Annual)]
    
    subgraph A股市场
        A_Daily[historical_quotes]
        A_Weekly[weekly_quotes]
        A_Monthly[monthly_quotes]
        A_Quarterly[quarterly_quotes]
        A_Semi[semiannual_quotes]
        A_Annual[annual_quotes]
    end
    
    subgraph 港股市场
        HK_Daily[hk_historical_quotes]
        HK_Weekly[hk_weekly_quotes]
        HK_Monthly[hk_monthly_quotes]
        HK_Quarterly[hk_quarterly_quotes]
        HK_Semi[hk_semiannual_quotes]
        HK_Annual[hk_annual_quotes]
    end
```

## 4. 数据库设计

所有周期表结构基本一致，主要包含以下字段：

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| code | TEXT | 股票代码 | 主键之一 |
| date | TEXT | 周期结束日期 | 主键之一 (YYYY-MM-DD) |
| open | REAL | 开盘价 | 周期内首个交易日开盘价 |
| high | REAL | 最高价 | 周期内最高价 |
| low | REAL | 最低价 | 周期内最低价 |
| close | REAL | 收盘价 | 周期内最后交易日收盘价 |
| volume | REAL | 成交量 | 周期内总成交量 |
| amount | REAL | 成交额 | 周期内总成交额 |
| change_percent | REAL | 涨跌幅 (%) | (本周期收盘 - 上周期收盘) / 上周期收盘 |
| change | REAL | 涨跌额 | 本周期收盘 - 上周期收盘 |
| amplitude | REAL | 振幅 (%) | (本周期最高 - 本周期最低) / 上周期收盘 |
| turnover_rate | REAL | 换手率 | 周期内换手率之和 (可选) |
| collected_source | TEXT | 数据来源 | 默认为 "generated_from_daily" |
| collected_date | TIMESTAMP | 采集时间 | |

**表名清单**:

*   **A股**: `weekly_quotes`, `monthly_quotes`, `quarterly_quotes`, `semiannual_quotes`, `annual_quotes`
*   **港股**: `hk_weekly_quotes`, `hk_monthly_quotes`, `hk_quarterly_quotes`, `hk_semiannual_quotes`, `hk_annual_quotes`

## 5. 核心算法与实现

### 5.1 聚合逻辑 (Resampling)

使用 `pandas` 的 `resample` 方法进行数据聚合。

*   **周线**: `W-FRI` (每周五作为结束日)
*   **月线**: `M` (月末)
*   **季线**: `Q` (季末)
*   **半年线**: 自定义逻辑 (每年6月30日和12月31日) 或基于月线/季线进一步聚合
*   **年线**: `A` (年末)

**聚合规则**:
```python
agg_dict = {
    'open': 'first',    # 开盘价取第一个
    'high': 'max',      # 最高价取最大值
    'low': 'min',       # 最低价取最小值
    'close': 'last',    # 收盘价取最后一个
    'volume': 'sum',    # 成交量求和
    'amount': 'sum'     # 成交额求和
}
```

### 5.2 技术指标计算

*   **涨跌幅**: 基于上一周期的收盘价计算。
*   **振幅**: `(周期最高 - 周期最低) / 上一周期收盘价`。
*   **注意**: 计算指标时需要获取上一周期的数据，因此在查询日线数据时通常会向前多查询一段时间（如40天）。

### 5.3 代码结构

所有采集器位于 `backend_core/data_collectors/akshare/` 目录下。

**A股采集器**:
*   `weekly_collector.py`: `WeeklyDataGenerator`
*   `monthly_collector.py`: `MonthlyDataGenerator`
*   `quarterly_collector.py`: `QuarterlyDataGenerator`
*   `semiannual_collector.py`: `SemiAnnualDataGenerator`
*   `annual_collector.py`: `AnnualDataGenerator`

**港股采集器**:
*   `hk_weekly_collector.py`: `HKWeeklyDataGenerator`
*   `hk_monthly_collector.py`: `HKMonthlyDataGenerator`
*   `hk_quarterly_collector.py`: `HKQuarterlyDataGenerator`
*   `hk_semiannual_collector.py`: `HKSemiAnnualDataGenerator`
*   `hk_annual_collector.py`: `HKAnnualDataGenerator`

## 6. 定时任务调度

所有任务由 `backend_core/data_collectors/main.py` 中的 `APScheduler` 统一调度。

### A股调度策略
*   **周线**: 周一至周五 18:00 (`generate_weekly_data`)
*   **月线**: 每日 18:30 (`generate_monthly_data`)
*   **季线**: 每日 19:00 (`generate_quarterly_data`)
*   **半年线**: 每日 19:10 (`generate_semiannual_data`)
*   **年线**: 每日 19:20 (`generate_annual_data`)

### 港股调度策略
*   **周线**: 周一至周五 18:10 (`generate_hk_weekly_data`) - 错开A股10分钟
*   **月线**: 每日 18:40 (`generate_hk_monthly_data`)
*   **季线**: 每日 19:05 (`generate_hk_quarterly_data`)
*   **半年线**: 每日 19:15 (`generate_hk_semiannual_data`)
*   **年线**: 每日 19:30 (`generate_hk_annual_data`)

*注：每日运行是为了确保在周期结束的当天（如月末、季末）能及时生成数据，非周期结束日运行通常不会产生新记录或仅更新当期数据。*

## 7. 异常处理与监控

*   **日志**: 每个采集器有独立的日志文件（如 `weekly_generation.log`, `hk_weekly_generation.log`）。
*   **重试**: 数据库操作包含重试机制，处理锁冲突。
*   **容错**: 单个股票失败不影响整体任务，错误会被记录并跳过。

## 8. 使用指南

### 手动运行

可以通过命令行手动触发特定周期的数据生成：

```bash
# A股周线
python backend_core/data_collectors/akshare/weekly_collector.py

# 港股月线
python backend_core/data_collectors/akshare/hk_monthly_collector.py

# 指定日期范围
python backend_core/data_collectors/akshare/weekly_collector.py 2024-01-01 2024-12-31
```

### 验证数据

```sql
-- 检查A股周线最新数据
SELECT * FROM weekly_quotes ORDER BY date DESC LIMIT 5;

-- 检查港股年线数据
SELECT * FROM hk_annual_quotes ORDER BY date DESC LIMIT 5;
```
