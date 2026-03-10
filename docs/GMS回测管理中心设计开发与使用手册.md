# GMS 回测管理中心 设计开发与使用手册

本文档说明「**GMS 回测管理中心**」的设计目标、后端/前端实现结构、接口清单、数据与产物存储方式，以及管理端的使用流程与常见问题排查。

---

## 一、功能概述

### 1.1 目标

- 在 admin 管理端新增 **GMS 回测管理中心**（UI/交互风格对齐 PVFARS 策略管理中心：状态卡片 + 多标签页）。
- 回测执行采用 **异步任务模式**：创建任务 → 后台执行 → 列表查看进度/日志 → 完成生成报告并可下载明细。
- 回测评估口径固定为 **目标命中率（准确率）**：
  - 信号日收盘价为入场价 \(entry = close_t\)
  - 看未来 **20 个交易日**最高价 \(max(high_{t+1..t+20})\)
  - 若 \(max\_high \ge entry \times (1 + target\_pct)\) 则记为 **命中**

### 1.2 覆盖市场

- **A 股**：日行情表 `historical_quotes`（`date` 为 Date）
- **港股**：日行情表 `historical_quotes_hk`（`date` 为 String）
- 管理端可选择市场：`cn` / `hk` / `all`

---

## 二、整体架构与数据流

### 2.1 模块分层

```
admin (Vue) 页面与组件
  └─ gmsApi.ts 调用 /api/admin/gms/*
backend_api (FastAPI)
  └─ admin/gms_admin_routes.py：任务/报告/配置 API
backend_core (策略与任务执行)
  ├─ strategies/gms/backtest_worker.py：后台线程执行回测
  ├─ strategies/gms/backtest_runner.py：回测口径与统计（命中率）
  ├─ strategies/gms/backtest_storage.py：任务/报告/明细文件存储（文件系统）
  └─ strategies/gms/admin_interface.py：对 routes 的统一封装
```

### 2.2 回测任务执行流

1. 管理端提交创建任务（日期区间、市场、target_pct、min_score 等）
2. 后端创建 task 记录（`pending`），启动后台线程 worker
3. worker 按交易日循环：
   - 调用 `GMSFrontendInterface.get_selection_results()` 获取当日信号
   - 取信号日收盘价作为入场价，读取未来 20 个交易日 high，判断是否命中
   - 持续写 progress、logs
4. 完成后：
   - 写入 summary（命中率与分组统计）
   - 保存 details 明细 CSV
   - 生成 report（与 task_id 同 ID）

---

## 三、后端设计（backend_api + backend_core）

### 3.1 路由与接口清单

路由文件：`backend_api/admin/gms_admin_routes.py`  
路由前缀：`/api/admin/gms`

#### 3.1.1 系统状态

- **GET** `/api/admin/gms/system/status`
  - 返回：
    - `runningBacktests`：运行中任务数（pending/running）
    - `totalReports`：历史报告数（completed）
    - `systemHealth`：健康状态（当前返回 `ok`）

#### 3.1.2 回测任务与股票池定义

**股票池在创建任务时定义**，通过「股票池」选项 + 可选代码输入：

| 选项       | 含义         | 前端传参               | 后端行为 |
|------------|--------------|------------------------|----------|
| 全市场     | 按市场取全量 | 不传 `stock_code`/`stock_pool` | `stock_pool=None`，由 `GMSFrontendInterface._get_stock_pool(date, market)` 从 `stock_basic_info` / `stock_basic_info_hk` 取码 |
| 单股回测   | 仅一只股票   | `stock_code`：如 000001、00700 | config 带 `stock_code`，worker 转为 `stock_pool=[code]`，每日只对该股做 GMS 选股与命中统计 |
| 自定义列表 | 多只股票     | `stock_pool`：代码数组 | config 带 `stock_pool`，每日只对列表中股票做选股与命中统计 |

- **POST** `/api/admin/gms/backtests`
  - body：
    - `task_name?`：任务名
    - `market`：`cn|hk|all`
    - `start_date` / `end_date`：`YYYY-MM-DD`
    - `target_pct`：如 `0.05`
    - `horizon_days`：默认 20
    - `min_score`：默认 0
    - `stock_pool_mode`：`all`（全市场）/ `single`（单股回测）/ `custom`（自定义列表）
    - `stock_code?`：单股回测时的股票代码（如 000001、00700）
    - `stock_pool?`：自定义列表时的代码数组
  - 返回：`task_id`

- **GET** `/api/admin/gms/backtests?status=&limit=&offset=`
  - 返回：任务列表

- **GET** `/api/admin/gms/backtests/{task_id}`
  - 返回：任务详情（含 config、summary、details_path 等）

- **GET** `/api/admin/gms/backtests/{task_id}/logs`
  - 返回：日志列表（按写入顺序）

- **POST** `/api/admin/gms/backtests/{task_id}/cancel`
  - 取消任务（worker 会在下一次检查时退出）

- **DELETE** `/api/admin/gms/backtests/{task_id}`
  - 删除任务、对应报告及明细文件

#### 3.1.3 报告

- **GET** `/api/admin/gms/reports?limit=&offset=`
  - 返回：历史报告列表

- **GET** `/api/admin/gms/reports/{report_id}`
  - 返回：报告详情（summary + details_path）

- **GET** `/api/admin/gms/reports/{report_id}/download`
  - 下载明细 CSV 文件

#### 3.1.4 策略配置

- **GET** `/api/admin/gms/config`
  - 返回：`gms_config.json`（默认配置与文件配置深度合并）

- **PUT** `/api/admin/gms/config`
  - body：`{ "config": { ... } }`
  - 行为：与当前配置深度合并后写回 `backend_core/strategies/gms/gms_config.json`

### 3.2 任务与报告存储（文件系统）

实现文件：`backend_core/strategies/gms/backtest_storage.py`

默认存储目录（相对本项目根目录）：

- `backend_core/strategies/gms/backtest_data/`
  - `tasks/{task_id}.json`：任务详情（含 config、progress、logs、summary、details_path）
  - `reports/{report_id}.json`：报告（report_id 与 task_id 相同）
  - `details/{task_id}.csv`：明细 CSV
  - `task_index.json`：用于快速列出任务/状态的索引

> 注：Windows 下实际绝对路径形如  
> `E:\wangxw\股票分析软件\编码\stock_quote_analayze\backend_core\strategies\gms\backtest_data`

### 3.3 回测核心口径与统计

实现文件：`backend_core/strategies/gms/backtest_runner.py`

- **信号来源**：`GMSFrontendInterface.get_selection_results(date, stock_pool=..., market=...)`；`stock_pool` 为 None 时按市场取全市场代码，否则仅对给定代码列表选股。
- **入场价**：信号日 `close`
- **命中判断**：未来 `horizon_days`（默认 20）个交易日内的 `high` 最大值是否满足目标阈值
- **汇总输出**：
  - `hit_rate`：命中率
  - `by_buy_type`：按 `buy_type` 分组命中率
  - `by_score_bucket`：按 `score_total` 分桶命中率
- **日期类型兼容**：
  - A 股 `historical_quotes.date` 为 Date，代码中会将 `YYYY-MM-DD` 转为 `date` 对象比较
  - 港股 `historical_quotes_hk.date` 为 String，按字符串 `YYYY-MM-DD` 比较与排序

### 3.4 异步执行方式

实现文件：`backend_core/strategies/gms/backtest_worker.py`

- 当前采用 **后台线程**（daemon thread）执行
- 取消方式：
  - API 侧调用 cancel 后会写 task 状态为 `cancelled`
  - worker 每步调用 `cancel_check()` 检测取消请求

---

## 四、前端设计（admin）

### 4.1 页面与路由

- 页面：`admin/src/views/GMSManagementView.vue`
  - 顶部状态卡片：活跃策略/运行中任务/历史报告/健康度
  - Tabs：
    - 回测任务管理
    - 报告与分析
    - 策略配置

- 路由：`admin/src/router/index.ts`
  - `path: 'gms-management'` → `GMSManagementView.vue`

- 菜单：`admin/src/views/AdminLayout.vue`
  - 新增入口：`/gms-management`（显示名：GMS回测管理）

### 4.2 服务封装

- `admin/src/services/gmsApi.ts`
  - 统一封装 `GET/POST/PUT/DELETE /api/admin/gms/*`
  - 自动附带 `admin_token`（Bearer）

### 4.3 组件结构（与 PVFRS 目录结构对齐）

目录：`admin/src/components/gms/`

- `BacktestManagement.vue`
  - 创建任务表单字段：
    - 任务名称（可选）
    - 市场：CN/HK/ALL
    - 日期范围 start/end
    - 目标阈值 X（默认 5%）
    - 持有窗口（默认 20）
    - min_score（默认 0）
    - **股票池**：全市场 / **单股回测**（需填股票代码）/ **自定义列表**（多行代码）
  - 任务列表：状态、进度、详情、取消、删除

- `TaskDetail.vue`
  - 展示：任务参数、汇总指标、按 buy_type 分组、按分数分桶、日志

- `ReportAnalysis.vue`
  - 报告列表、报告详情、下载明细 CSV

- `StrategyConfiguration.vue`
  - 读取/编辑 JSON 配置、保存、重置默认

---

## 五、使用指南（管理端）

### 5.1 进入页面

管理端左侧菜单选择 **GMS回测管理**（路径：`/gms-management`）。

### 5.2 创建回测任务

在「回测任务管理」Tab：

1. 选择市场（A股/港股/全市场）
2. 选择开始/结束日期
3. 选择目标阈值（+3% / +5% / +10%）
4. **股票池**：选「全市场」则对全市场回测；选「单股回测」需填写一只股票代码（如 000001、00700）；选「自定义列表」需在多行框中输入多只代码（每行一个）。
5. 可选：调整持有窗口、min_score
6. 点击「创建任务」

创建后任务会出现在任务列表中，状态通常为 `pending` → `running` → `completed`（或 `failed/cancelled`）。

### 5.3 查看任务详情与日志

在任务列表中点击「详情」：

- 查看任务 config
- 查看汇总指标（样本数/命中数/命中率）
- 查看分组统计与分桶统计
- 查看日志（进度写入）

### 5.4 查看与下载报告

在「报告与分析」Tab：

- 查看历史报告列表
- 点击「查看」查看 summary
- 点击「下载CSV」获取明细文件

### 5.5 配置管理

在「策略配置」Tab：

- 点击「重新加载」读取当前配置（`gms_config.json`）
- 直接修改 JSON 后「保存配置」
- 可用「重置为默认」快速填充默认模板（不会自动保存）

---

## 六、开发与扩展说明

### 6.1 股票池与单股/自定义说明

当前已支持：

- **全市场**：不传 `stock_code`/`stock_pool`，runner 调用 `get_selection_results(..., stock_pool=None)`，由接口内部按 `market` 从基础信息表取全量代码。
- **单股回测**：传 `stock_code`，worker 转为 `stock_pool=[code]` 传给 runner，每日仅对该只股票做 GMS 选股与命中统计。
- **自定义列表**：传 `stock_pool` 数组，每日仅对列表中股票做选股与命中统计。

### 6.2 若要增加“报告导出 Excel”

当前明细保存为 CSV（`save_details_csv`）。如需 Excel：

- 增加 `save_details_xlsx()`（建议用 `openpyxl` 或 `pandas`）
- download 接口根据参数选择下载格式

### 6.3 若要切换为统一任务调度器

目前使用后台线程（简单可靠）。如需接入统一调度/队列：

- 将 `backtest_worker.start_backtest()` 替换为投递到调度器
- storage 与 runner 可保持不变

---

## 七、常见问题（FAQ）

### 7.1 任务一直不动/无日志

- 检查后端进程是否启动、API 是否可访问
- 检查任务文件是否生成：`backtest_data/tasks/{task_id}.json`
- 若任务 `failed`，在任务详情中查看 `error` 字段与日志

### 7.2 命中率为 0 或样本数为 0

常见原因：

- 选定日期区间内指标表无数据或无买入信号
- 行情表缺少对应股票/日期的 close 或未来 20 交易日 high
- `min_score` 设置过高导致信号被过滤

### 7.3 港股日期类型不同导致查询异常

- A 股 `historical_quotes.date` 为 Date，港股为 String；已在 runner 中做了转换与兼容。
- 若港股行情日期格式不是 `YYYY-MM-DD`，需要先统一清洗存储格式。

---

## 八、相关参考文档

- `docs/GMS_STRATEGY_IMPLEMENTATION_DESIGN.md`：GMS 策略实现设计
- `docs/GMS_STATE_DETECTION_RULES.md`：GMS 状态判定规则
- `docs/PVFRS量价频共振策略与回测系统说明.md`：PVFRS/PVFARS 管理中心与回测系统参考

