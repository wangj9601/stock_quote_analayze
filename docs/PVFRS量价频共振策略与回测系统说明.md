# PVFRS 量价频共振策略与回测系统说明

本文档整合 PVFARS 量价频幅度共振策略详细说明、PVFRS 策略与回测系统设计、回测数据库表说明及报告列表修复说明，作为策略与回测系统的完整参考。

---

## 目录

1. [概述与文档目的](#一概述与文档目的)
2. [PVFARS 策略详细说明](#二pvfars策略详细说明)
3. [PVFRS 策略与回测系统设计](#三pvfrs策略与回测系统设计)
4. [回测数据库表说明](#四回测数据库表说明)
5. [报告列表问题修复与验证](#五报告列表问题修复与验证)

---

## 一、概述与文档目的

### 1.1 策略名称与关系

- **PVFRS**：Price-Volume-Frequency Resonance Strategy，量价频三维共振策略（含回测系统）。
- **PVFARS**：Price, Volume, Frequency, Amplitude, Resonance Strategy，在三维共振基础上增加**幅度（Amplitude）**分析及更细的维度条件，即“量价频幅度共振”选股策略。

回测系统与前端管理中的“PVFRS”涵盖上述策略逻辑；指标与信号设计以 PVFARS 文档中的增强版为准。

### 1.2 文档目的

- 定义 PVFRS/PVFARS 的交易信号（买点/卖点/风控）及选股条件。
- 说明回测系统的数据依赖、模块结构、配置与运行方式。
- 提供回测相关数据库表结构及使用示例。
- 记录报告列表显示问题的修复与验证方法。

---

## 二、PVFARS 策略详细说明

### 2.1 策略概述

PVFARS 通过**价格、成交量、频率、幅度**四个维度综合分析，在**价格、频率、成交量**三个维度上检测共振，并结合幅度、趋势持续性、乖离率等，识别进入**高效率演化轨道**的投资机会。

**核心理念**：三维共振（价格、频率、成交量同时满足条件）、买点权重（F>Z）、趋势持续性验证、量化筛选。

**策略架构**：

```
PVFARS策略架构
├── 价格维度分析器 (PriceDimensionAnalyzer)
├── 频率维度分析器 (FrequencyDimensionAnalyzer)
├── 成交量维度分析器 (VolumeDimensionAnalyzer)
├── 三维共振检测器 (ResonanceDetector)
└── 信号生成器 (SignalGenerator)
```

### 2.2 价格维度

- **宏观位移** Δ = d₂₀ - d₁；**即时强度** d₂₀ - d（d 为 20 日均价）；**幅度** |Δ|；**幅度比例** Δ/d₂₀、Δ/d₁。
- **增强**：价格趋势持续性（5/10 日斜率、上涨天数占比、最大回撤）、波动率（标准差/均值 <15%）、乖离率及趋势类型。
- **价格维度有效**：Δ>0 且 d₂₀>d，且趋势持续性为真，且波动率<15%。

### 2.3 频率维度

- **Z**：20 日内收盘价高于前一日的天数；**F**：低于前一日的天数；横盘不计入。
- **买点权重**：F > Z（下跌天数多于上涨天数）作为买点侧权重。
- **增强**：虚假繁荣检测（单日/连续异常涨幅、涨幅集中度、上涨分布）、上涨集中度、最近 10 天上涨天数≥6。
- **频率维度有效**：F>Z、Z≥10、通过虚假繁荣检测、最近 10 天上涨≥6 天等（详见原文档条件 1–5）。

### 2.4 成交量维度

- **20 日均量** m；**当前成交量** m₂₀；**效率比** m₂₀/m。
- **增强**：量价共振（价涨且量放大）、强资金支撑（1.2≤倍数≤8、连续放量、递增）、成交量趋势持续性、低成色过滤（量不足或过度放大）。
- **成交量维度有效**：m₂₀>m、量价共振、强资金支撑且连续放量、排除低成色、量能趋势持续。

### 2.5 三维共振与信号

- **基本共振**：价格有效 AND 频率有效 AND 成交量有效；维度权重可设为价格 40%、频率 30%、成交量 30%。
- **买点排除**：F≥Z 且 Δ<0 排除；可配置横盘排除、Δ/d₂₀ 超限排除。
- **共振强度**：由各维度条件满足情况加权计算；**信号强度**在共振强度基础上做质量调整（高质量 +0.1，虚假繁荣 -0.2，量价背离 -0.1），范围 0–1。
- **建议等级**：三维共振且强度≥0.8 → BUY；部分共振 0.6–0.8 → HOLD；否则 WAIT。仓位建议、入场时机（最佳/良好/等待）、风险提示见原文档第 7–8 节。

### 2.6 业务流程与技术实现要点

- **选股流程**：数据获取 → 三维分析 → 共振检测 → 信号生成 → 结果输出。
- **核心类**：`StrategyEngine`（各维度分析器 + `ResonanceDetector` + `SignalGenerator`）、`StockScreener`（批量筛选、按信号强度排序）。
- **关键算法**：价格趋势持续性、虚假繁荣检测、连续放量验证、三维共振检测（含买点排除与强度计算）。代码位置与类结构见原 PVFARS 文档第 10 节。
- **策略优化建议**：参数调优（观察周期、波动率阈值、买点权重、放量天数等）、市场环境与行业轮动、风控与回测验证见原文档第 11–12 节。

---

## 三、PVFRS 策略与回测系统设计

### 3.1 理论与指标字段

**三维共振（PVFRS）**：高效率上涨 = 以下三者同时满足

- 价格：Δ>0，即时强度 d20>d（Close>MA20）。
- 频率：Z>F（上涨天数多于下跌天数）。
- 成交量：m20>m（Vol>MAVOL20）。

**指标存储**：表 `mean_frequency_resonance_indicators`，模型 `MeanFrequencyResonanceIndicators`。主要字段：`macro_displacement_delta`、`instant_deviation`、`rising_days_z`、`falling_days_f`、`efficiency_m20_minus_m`、`ma20_d`、`mavol20_m`、`bias`。行情来自 `HistoricalQuotes`（A 股）/ `HistoricalQuotesHK`（港股）。

### 3.2 交易策略（买/卖/风控）

**买入（严格条件均需满足）**  
- 价格：`macro_displacement_delta>0`，`instant_deviation>0`。  
- 频率：`rising_days_z > falling_days_f`。  
- 成交量：`efficiency_m20_minus_m > 0`。  
**增强**：`bias > buy_bias_min`（默认 2%），相对位移比>阈值（默认 5%），连续 `buy_consecutive_days` 天（默认 3 天）满足严格条件。

**卖出**  
- 趋势反转：在“跌破 MA20、宏观位移<0、F>Z、量缩、超买 bias、即时偏离过大”等条件中满足≥2 条即触发。  
- 价涨量缩背离：即时强度>0 且效率<0，连续≥2 天则触发。

**风控（回测引擎）**：止损默认 -10%、止盈 +20%、最大持有天数 30、最大仓位 10%。

### 3.3 系统实现与数据流

- **代码目录**：`backend_core/strategies/`  
  - `pvfrs_strategy.py`（策略、信号检测、回测引擎）  
  - `pvfrs_data_loader.py`（数据加载与合并）  
  - `pvfrs_performance_analyzer.py`（绩效与报告）  
  - `pvfrs_backtest_runner.py`（命令行入口）  
  - `pvfrs_config.json`（策略与回测配置）

- **回测主流程**：runner 解析参数 → 加载配置 → DataLoader 读 PVFRS 指标与行情 → 合并 DataFrame → Strategy 生成信号 → BacktestEngine 逐日回放 → 报告与统计。

### 3.4 配置与运行

- **pvfrs_config.json**：`strategy_params`（买卖阈值、连续天数、风控）、`backtest_config`（如 initial_capital）、`optimization_config`（可选网格搜索）。

- **单股回测**：  
  `python backend_core/strategies/pvfrs_backtest_runner.py --mode single --code 688256 --market CN --start-date 2023-01-01 --end-date 2025-12-31 --params-file backend_core/strategies/pvfrs_config.json`  
  可选 `--initial-capital 200000`。

- **批量回测**：`--mode batch --market CN --start-date ... --end-date ... --output pvfrs_batch_report.md`

- **参数优化**：`--mode optimize --code ... --market CN ... --output pvfrs_optimize_report.md`

### 3.5 已修复与可扩展点

- **已修复**：A 股日期类型对齐、配置分层读取、初始资金读取、可选依赖（matplotlib/seaborn）处理。  
- **可扩展**：交易成本（手续费、滑点）、组合回测、信号可视化、样本外验证、回测交易写入数据库供前端展示。  
- **限制与免责**：策略仅供研究，回测不代表未来收益；对数据完整性敏感；实盘需考虑停牌、涨跌停、流动性等。

---

## 四、回测数据库表说明

PVFRS 回测系统核心表：任务、结果、交易记录、收益曲线。

### 4.1 pvfrs_backtest_tasks（回测任务表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| task_id | VARCHAR(50) | 唯一，索引 |
| mode | VARCHAR(20) | single/batch/optimize |
| stock_codes | TEXT | JSON 列表 |
| market | VARCHAR(10) | CN/HK |
| start_date, end_date | DATE | 回测区间 |
| initial_capital | FLOAT | 初始资金 |
| status | VARCHAR(20) | running/completed/failed/cancelled |
| progress | INTEGER | 0–100 |
| current_step, error_message | TEXT | 步骤与错误 |
| created_at, completed_at | DATETIME | 创建/完成时间 |

### 4.2 pvfrs_backtest_results（回测结果表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| task_id | VARCHAR(50) | 外键→tasks.task_id |
| stock_code, market | VARCHAR | 股票、市场 |
| backtest_date, start_date, end_date | DATE | 回测日期与区间 |
| initial_capital, final_capital | FLOAT | 初始/最终资金 |
| total_return, annual_return | FLOAT | 总收益、年化（%） |
| max_drawdown, sharpe_ratio, win_rate, profit_factor | FLOAT | 回撤、夏普、胜率、盈亏比 |
| total_trades | INTEGER | 交易次数 |
| avg_holding_period | FLOAT | 平均持仓天数 |
| created_at | DATETIME | 创建时间 |

### 4.3 pvfrs_trade_records（交易记录表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| result_id | INTEGER | 外键→results.id |
| stock_code, market | VARCHAR | 股票、市场 |
| entry_date, exit_date | DATE | 入场/出场日 |
| entry_price, exit_price | FLOAT | 入场/出场价 |
| pnl, pnl_percent | FLOAT | 盈亏金额与百分比 |
| exit_reason | TEXT | 出场原因 |
| created_at | DATETIME | 创建时间 |

### 4.4 pvfrs_equity_curves（收益曲线表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| result_id | INTEGER | 外键→results.id |
| stock_code, market | VARCHAR | 股票、市场 |
| curve_date | DATE | 日期 |
| equity | FLOAT | 当日权益 |
| created_at | DATETIME | 创建时间 |

**关系**：tasks(1) → results(N) → trade_records(N)、equity_curves(N)。

**维护脚本**：创建表 `backend_api/create_pvfrs_tables.py`，验证 `backend_api/verify_pvfrs_tables.py`。注意 task_id 唯一性、外键级联、stock_codes 的 JSON 格式、百分比存储方式（如 50.0 表示 50%）。使用示例（创建任务、保存结果、记录交易、保存收益曲线、查询）见原 pvfrs_tables_documentation.md。

---

## 五、报告列表问题修复与验证

### 5.1 问题描述

“报告与分析”中报告列表无法显示。

### 5.2 原因

- 原接口 `/api/admin/pvfrs/reports` 依赖 `admin_interface.list_historical_reports()` 的持久化逻辑，易因路径、持久化或格式问题失败。
- 未直接查询数据库表 `pvfrs_backtest_results_enhanced`，导致库中有数据也无法展示。
- 前端 `ReportAnalysis.vue` 期望分页及字段格式（如 totalReturn、sharpeRatio、winRate、maxDrawdown 等为数值，createdAt、stockCode、taskId）。

### 5.3 解决方案

在 `backend_api/admin/pvfrs_admin_routes.py` 的 `list_reports` 中：

1. **直接查库**：从 `PVFRSBacktestResultEnhanced` 查询，支持按 startDate/endDate 过滤、按 created_at 倒序、分页（page、pageSize）。
2. **安全转换**：对 Decimal/None 使用 safe_float、safe_percent（百分比乘 100）；单条转换异常用 try-except 跳过并打日志，不影响其他记录。
3. **返回格式**：与前端约定一致（id、title、type、totalReturn、annualReturn、maxDrawdown、sharpeRatio、winRate、totalTrades、createdAt、stockCode、taskId）。

### 5.4 修复效果与数据库要求

- 报告列表可正常显示；分页与日期过滤正常；单条错误不影响整体。
- 需存在 `pvfrs_backtest_results_enhanced` 表及数据。若列表为空，可能原因：尚未运行回测、表未创建、数据库连接问题。

### 5.5 验证步骤

1. 启动后端，访问管理端 → PVFRS 策略管理 → 报告与分析。  
2. 检查列表（有数据应正常显示；无数据为空列表而非报错）。  
3. 测试分页、日期过滤、报告详情、下载。

### 5.6 相关文件与后续建议

- **相关文件**：`pvfrs_admin_routes.py`、`backend_api/models/pvfrs_enhanced.py`、`ReportAnalysis.vue`、`pvfrsApi.ts`。  
- **后续建议**：无数据时可运行一次回测或添加测试数据；大量数据时考虑索引与缓存；前端可加加载态、空数据提示、刷新按钮。

---

**文档整合说明**：本文档由《PVFARS量价频幅度共振策略详细说明》《PVFRS策略与回测系统设计文档》《pvfrs_tables_documentation》《PVFRS_REPORTS_LIST_FIX》合并而成，供策略理解、回测配置、表结构维护与问题排查使用。
