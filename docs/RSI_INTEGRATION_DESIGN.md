# RSI 指标集成设计文档

## 1. 目标
在股票分析软件中集成相对强弱指标 (Relative Strength Index, RSI)，用于衡量价格走势的强弱，帮助识别超买和超卖状态。实现从数据采集、计算、存储到前端展示的全链路功能。

## 2. 系统架构

### 2.1 核心组件
*   **计算引擎**: `backend_core/utils/rsi_calculator.py`
    *   实现了标准的 RSI 计算逻辑。
    *   默认周期参数：6, 12, 24。
    *   使用 Wilder 平滑法 (Wilder's Smoothing) 处理移动平均。
*   **数据库**: SQLite
    *   表名: `rsi_indicators`
    *   存储 A 股和港股的 RSI 数据。

### 2.2 数据流
1.  **数据采集**: 获取股票历史 K 线收盘价数据。
2.  **指标计算**: 使用 `RSICalculator` 计算 RSI(6, 12, 24)。
3.  **数据存储**: 存入 `rsi_indicators` 表。
4.  **API 服务**: 查询 K 线数据时，关联查询 RSI 数据并合并返回。
5.  **前端展示**: 在 K 线图副图中绘制 RSI 曲线。

## 3. 详细设计

### 3.1 数据库设计 (`models.py`)

新增 `RSIIndicators` 模型，对应数据库表 `rsi_indicators`。

| 字段名 | 类型 | 说明 | 索引 |
| :--- | :--- | :--- | :--- |
| `id` | Integer | 主键 | Primary Key |
| `code` | String(20) | 股票代码 | 联合唯一索引 |
| `date` | Date | 交易日期 | 联合唯一索引 |
| `market_type` | String(10) | 市场类型 ('CN', 'HK') | 联合唯一索引 |
| `rsi6` | Float | 6日 RSI | |
| `rsi12` | Float | 12日 RSI | |
| `rsi24` | Float | 24日 RSI | |
| `created_at` | DateTime | 创建时间 | |

**唯一约束**: `(code, date, market_type)`

### 3.2 后端实现

#### 3.2.1 工具类 (`backend_core/utils/rsi_calculator.py`)
*   **输入**: 收盘价序列 (Pandas Series / List)。
*   **输出**: 包含 RSI6, RSI12, RSI24 的 DataFrame 或字典。
*   **算法**:
    *   计算每日价格变动：`change = price_today - price_yesterday`
    *   区分涨跌：`gain = max(change, 0)`, `loss = abs(min(change, 0))`
    *   计算平滑移动平均 (SMMA / Wilder's):
        *   `avg_gain = (prev_avg_gain * (n-1) + current_gain) / n`
        *   `avg_loss = (prev_avg_loss * (n-1) + current_loss) / n`
    *   `RS = avg_gain / avg_loss`
    *   `RSI = 100 - (100 / (1 + RS))`

#### 3.2.2 数据采集与回补
*   **历史数据回补**: `backend_core/data_collectors/akshare/rsi_backfill.py`
    *   支持命令行参数指定市场 (`CN`/`HK`)、日期范围、和特定代码。
    *   批量获取历史收盘价，计算并存入数据库。
*   **每日采集 (A股)**: `backend_core/data_collectors/akshare/historical_collector.py`
    *   在采集日线行情 (`collect_single_stock_data`) 后触发。
    *   调用 `_calculate_and_save_rsi` 方法。
*   **每日采集 (港股)**: `backend_core/data_collectors/akshare/hk_historical.py`
    *   在采集港股日线 (`collect_historical_quotes`) 后触发。
    *   调用 `_calculate_and_save_rsi_hk` 方法。

#### 3.2.3 API 接口
*   **A 股 K 线接口**: `backend_api/stock/stock_manage.py` -> `get_kline_hist`
    *   在返回 K 线数据前，查询 `rsi_indicators` 表。
    *   将 `rsi6`, `rsi12`, `rsi24` 字段合并到对应的日期记录中。
*   **港股 K 线接口**: `backend_api/stock/hk_stock_manage.py` -> `get_hk_kline_hist`
    *   同上，查询时指定 `market_type='HK'`。
*   **历史数据列表接口**: `backend_api/stock/history_api.py` -> `get_stock_history`
    *   支持在管理后台的历史数据表格中返回 RSI 数据。

### 3.3 前端实现

#### 3.3.1 K 线图表 (`frontend/js/stock.js` & `stock_hk.js`)
*   **图表配置**:
    *   在 ECharts `series` 中增加 3 条折线：`RSI6` (白色), `RSI12` (黄色), `RSI24` (紫色)。
    *   更新 `tooltip` formatter 以显示 RSI 数值。
    *   更新 `legend` 显示。
*   **交互逻辑**:
    *   增加 `sub-indicator-select` 下拉选项 `RSI`。
    *   实现 `showRSIChart()`: 调整 Grid 布局，隐藏 Volume/MACD/KDJ，显示 RSI。
    *   实现 `hideRSIChart()`: 隐藏 RSI Series。
    *   更新 `updateSubIndicator()` 调度逻辑。
*   **数据加载**:
    *   在 `loadKlineData()` 中解析 API 返回的 RSI 数据并填充到 Series data。

#### 3.3.2 后台管理 (`admin/src/views/QuotesView.vue`)
*   在 A 股和港股的“历史行情数据”表格中增加 `RSI6`, `RSI12`, `RSI24` 列。

## 4. 测试验证
1.  **数据准确性**: 对比通达信或同花顺等主流软件的 RSI 数值。
2.  **显示正常**:
    *   切换不同股票，RSI 曲线绘制正确。
    *   Tooltip 显示数值正确。
    *   副图切换 (成交量 -> MACD -> KDJ -> RSI) 平滑无误。
3.  **性能**: 大量数据下的加载和渲染性能。

## 5. 后续优化
*   支持用户自定义 RSI 周期参数 (目前固定为 6, 12, 24)。
*   支持 RSI 导出功能 (Excel/CSV)。
