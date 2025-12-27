# 股票行情分析系统 (Stock Quote Analyze) 全新设计文档

## 1. 总体架构 (General Architecture)

本系统采用现代的前后端分离架构，由四个核心工程组成，涵盖了从数据采集、数据处理、API 提供到用户管理后台与前端展示的全流程。

### 1.1 系统模块划分
*   **`backend_core`（底座/核心层）**：
    *   **职责**：数据采集、清洗、计算、定时任务调度。
    *   **核心组件**：基于 `AKShare` 和 `TuShare` 的数据采集器，负责 A 股和港股的实时与历史数据（日、周、月、季、年）的同步。
    *   **调度**：包含新闻调度、报告调度等自动化脚本。
*   **`backend_api`（接口层/服务端）**：
    *   **职责**：提供对外的 RESTful API，处理业务逻辑（选股策略、指标计算评分、交易记录、自选股管理等）。
    *   **技术栈**：基于 `FastAPI` 框架，使用 `SQLAlchemy` 进行 ORM 处理。
*   **`frontend`（展示层/客户端）**：
    *   **职责**：面向普通用户的行情展示、个股分析细节、选股策略筛选、自选股监控、模拟交易平台等。
    *   **技术栈**：原生 JS + HTML5 + CSS3，结合 ECharts 进行性能优异的图表展示。
*   **`admin`（管理后台）**：
    *   **职责**：面向管理员的系统监控、数据采集触发、用户管理、指标统计查看。
    *   **技术栈**：基于 `Vue 3` + `TypeScript` + `Vite` + `TailwindCSS` + `Element Plus`。

### 1.2 架构示意图
```
[ 用户端 ] <---> [ backend_api (FastAPI) ] <---> [ SQLite 数据库 ]
                               ^                     ^
                               |                     |
[ 管理端 ] <---> [ backend_api (FastAPI) ] <---> [ backend_core (数据处理) ]
                                                     |
                                            [ AKShare / TuShare API ]
```

---

## 2. 模型设计 (Data Model Design)

系统主要依赖 SQLite 数据库，核心模型定义在 `backend_api/models.py` 中。

### 2.1 用户与管理
*   **User**: 用户基础信息（ID, 账号, 邮箱, 角色, 状态, 最后登录时间）。
*   **Admin**: 管理员账户。
*   **Watchlist / WatchlistGroup**: 用户自选股及自选分组。

### 2.2 行情与基础数据
*   **StockBasicInfo / StockBasicInfoHK**: A股及港股的股票列表。
*   **QuoteData / StockRealtimeQuote**: 实时行情数据缓存。
*   **HistoricalQuotes / HistoricalQuotesHK**: 历史行情主表。支持 **5日/10日/30日/60日** 累计涨跌幅计算。
*   **IndexRealtimeQuotes / HKIndexRealtimeQuotes**: 指数行情（标普、恒指、上证等及相关核心指数）。

### 2.3 技术指标 (Indicators)
*   **MACDIndicators**: 包含 DIF, DEA, MACD。
*   **KDJIndicators**: 包含 K, D, J。
*   **RSIIndicators**: 包含 RSI6, RSI12, RSI24。
*   **MAIndicators / MAVOLIndicators**: 均线及均量线指标。
*   **BOLLIndicators**: 布林带指标。

### 2.4 扩展业务模型
*   **StockNews / StockNoticeReport**: 个股新闻与公告。
*   **StockResearchReport**: 研报深度数据（包含 2024-2026 盈利预期、PE 预测）。
*   **SimTradeAccount / Position / Order**: 模拟交易账户、持仓、订单记录。
*   **TradingNotes**: 用户针对个股的交易笔记、风险等级评估。

---

## 3. 业务流程与规则 (Business Process & Rules)

### 3.1 数据采集流程
1.  **管理端下单**：管理员在 `admin` 后台选择采集市场（A股/港股）、日期范围及采集模式（增量/全量/测试模式）。
2.  **API 调度**：`backend_api` 接收请求并调用 `backend_core` 中的采集类（如 `HKHistoricalCollector`）。
3.  **限流与重试**：由于 `AKShare` 经常触发限流，`backend_core/base.py` 实现了指数级退避重试机制。
4.  **数据清洗与入库**：采集到的 DataFrame 经过字段映射、涨跌幅重构计算后存入 `HistoricalQuotes`。

### 3.2 选股策略与规则
系统内置了多种策略脚本（`backend_api/stock/`）：
*   **长下影阳线 (Long Lower Shadow)**：识别股价触底回升的信号。
*   **九转序列 (Low Nine)**：识别连续下跌后的转折点。
*   **高紧旗形 (High Tight Flag)**：针对强势股的突破形态。
*   **持续增长策略 (Keep Increasing)**：筛选财务或表现持续向好的个股。

### 3.3 认证与权限规则
*   **双重认证系统**：前端交互使用 JWT 令牌。管理端与用户端路由有独立的权限校验中间件。
*   **操作日志**：管理端所有的采集操作和用户状态变更均会记录在操作日志表中。

---

## 4. 功能规格描述 (Feature Specifications)

### 4.1 前端核心功能 (frontend)
*   **综合市场看板**：多指数（A股、港股、美股重要指数）同屏预览，红绿涨跌实时动态感官。
*   **深度个股页**：
    *   **K线图系统**：支持日/周/月线切换，动态加载 MACD、KDJ、RSI、BOLL 等副图。
    *   **资讯集成**：个股公告、研报、深度新闻联动。
    *   **财务评估**：可视化展示个股盈利预期与历史 PE 变动。
*   **策略选股系统**：支持用户直接运行系统策略并查看实时扫描结果。

### 4.2 管理端后台功能 (admin)
*   **Dashboard**：实时系统资源占用监控、昨日/今日数据采集统计图。
*   **任务管理**：精细化的数据采集控制台，显示采集任务 ID、当前进度百分比、成功/失败数量。
*   **用户看板**：统计用户活跃度，管理自选股分组。
*   **指标维护**：支持对历史数据重新计算（Backfill）技术指标，修正历史断点。

### 4.3 后端核心处理 (backend_core/api)
*   **多周期数据自动聚合**：除了采集日线，系统具备将日线数据聚合为周、月、季、半年、年线的能力。
*   **计算服务**：内置 `five_day_change_calculator.py` 等算法服务，实时更新个股的短期爆发力指标。
