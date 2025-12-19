# KDJ 指标集成设计文档

## 1. 概述
本文档概述了将 KDJ（随机指标）集成到股票行情分析系统中的设计与实现方案。目标是为 A 股和港股提供 KDJ 值（K、D、J），在前端图表上进行可视化展示，并包含在数据导出功能中。

## 2. 系统架构更新

### 2.1 数据库模式
引入了一个新表 `kdj_indicators` 来高效存储计算出的 KDJ 值。

**表结构：** `kdj_indicators`
- `code` (VARCHAR(20)): 股票代码（主键）
- `date` (VARCHAR(20)): 交易日期（主键）
- `market_type` (VARCHAR(10)): 市场类型（'CN' 代表 A 股，'HK' 代表港股）（主键）
- `k` (REAL): K 值
- `d` (REAL): D 值
- `j` (REAL): J 值
- `rsv` (REAL): RSV（未成熟随机值），中间计算结果
- `created_at` (TIMESTAMP): 创建时间戳

**约束：**
- 复合主键：`(code, date, market_type)`
- 冲突解决：`ON CONFLICT DO UPDATE` 以确保重新运行时的数据一致性。

### 2.2 后端核心 (数据采集与计算)

#### KDJ 计算工具类
- **位置**: `backend_core/utils/kdj_calculator.py`
- **功能**:
    - 实现标准 KDJ 算法（N=9, M1=3, M2=3）。
    - 支持基于收盘价、最高价和最低价列表的批量计算。
    - 处理边界情况（数据不足、除以零）。

#### 历史数据采集器
- **A 股采集器**: `backend_core/data_collectors/akshare/historical_collector.py`
- **港股采集器**: `backend_core/data_collectors/akshare/hk_historical.py`
- **变更**:
    - 初始化逻辑现在确保 `kdj_indicators` 表存在。
    - 数据采集例程在获取价格数据后调用 `KDJCalculator`。
    - 计算出的 KDJ 值被持久化到 `kdj_indicators` 表中。
    - **健壮性**: 增强了 `akshare` API 调用的错误处理（针对 SSL/属性错误的重试机制）。

#### 回溯脚本
- **脚本**: `backend_core/data_collectors/akshare/kdj_backfill.py`
- **目的**: 批量处理数据库中所有现有股票的历史 KDJ 数据。
- **特性**: 支持按市场（'CN', 'HK', 'ALL'）、日期范围和特定股票代码进行过滤。

### 2.3 后端 API

#### 模型
- **位置**: `backend_api/models.py`
- **更新**: 添加了 `KDJIndicators` SQLAlchemy 模型映射。

#### API 端点
- **K 线图股票管理**:
    - `backend_api/stock/stock_manage.py` (A 股)
    - `backend_api/stock/hk_stock_manage.py` (港股)
    - **逻辑**: 当调用 `get_kline_hist` 时，系统查询指定日期范围内的 `kdj_indicators` 表，并将 `k`、`d`、`j` 值合并到每日 K 线数据响应中。

- **历史数据列表 API**:
    - `backend_api/stock/history_api.py`
    - **端点**: `/api/stock/history` 和 `/api/stock/history/export`
    - **逻辑**: SQL查询已更新，使用 `code`、`date` 和 `market_type` 对 `kdj_indicators` 表进行 `LEFT JOIN`。
    - **输出**: API 现在在 JSON 响应中返回 `k`、`d`、`j` 字段，并支持将其导出到 Excel/CSV。

### 2.4 前端

#### 股票详情页 (`frontend/js/stock.js`)
- **可视化**: 集成到主 ECharts K 线图中。
- **副图指标切换**:
    - 添加了在成交量 (Volume)、MACD 和 KDJ 指标之间切换的逻辑。
    - `showKDJChart(option)`: 配置 KDJ 的网格和系列可见性。
    - `hideKDJChart(option)`: 隐藏 KDJ 元素。
- **系列配置**: 添加了 3 条折线系列，分别为 K（白色）、D（黄色）、J（红/紫色）。
- **提示框**: 更新了格式化程序，在悬停时与价格和 MACD 数据一起显示 K、D、J 值。

#### 行情视图 (`admin/src/views/QuotesView.vue`)
- **表格显示**:
    - 在 A 股和港股的历史数据表格中添加了 "K"、"D"、"J" 列。
    - 数值格式化为保留 2 位小数。

## 3. 实施步骤总结

1.  **数据库**: 创建 `kdj_indicators` 表。
2.  **核心**: 实现 `KDJCalculator` 并将其集成到采集器中。
3.  **回溯**: 运行回溯脚本以填充历史 KDJ 数据。
4.  **API**: 通过 `get_kline_hist` 和 `get_stock_history` 暴露 KDJ 数据。
5.  **前端**: 更新图表和表格以使用并显示新数据。

## 4. 未来改进
- **实时 KDJ**: 目前 KDJ 是基于历史收盘价计算的。可以添加实时盘中 KDJ 计算。
- **参数自定义**: 允许用户自定义 N, M1, M2 参数（目前固定为 9, 3, 3）。
