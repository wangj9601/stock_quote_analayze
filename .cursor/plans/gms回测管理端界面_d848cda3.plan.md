---
name: GMS回测管理端界面
overview: 在管理端新增 GMS 回测管理中心界面，风格与交互对齐 PVFARS策略管理中心（状态卡片+多标签页），并采用异步任务模式（创建任务/进度/日志/报告）。复用现有 GMS 选股引擎与回测评估口径（20日内最高价达 +X% 为命中）。
todos: []
isProject: false
---

# GMS 回测管理端界面（参考 PVFARS 管理中心）

## 一、目标

- 在 admin 管理端增加 **GMS策略管理中心**，UI/交互参考 `[admin/src/views/PVFRSManagementView.vue](admin/src/views/PVFRSManagementView.vue)` 与其子组件（`admin/src/components/pvfrs/`*）。
- 回测执行方式采用 **异步任务**：创建任务 → 后台计算 → 任务列表查看进度/日志 → 完成后生成报告并可查看/下载。

## 二、前端（admin）改造范围

### 1) 新增页面与路由

- 新增页面：`admin/src/views/GMSManagementView.vue`
  - 结构对齐 `PVFRSManagementView.vue`：
    - 顶部状态卡片（活跃策略/运行中任务/历史报告/健康度）
    - tabs：回测任务管理、报告与分析、策略配置、（可选）监控
- 注册路由：在 `[admin/src/router/index.ts](admin/src/router/index.ts)` 增加
  - `path: 'gms-management'` → `GMSManagementView.vue`
- 左侧菜单（如有）：在 `[admin/src/views/AdminLayout.vue](admin/src/views/AdminLayout.vue)` 增加入口（命名与 pvfrs 保持一致）。

### 2) 新增组件（对齐 pvfrs 目录结构）

新增目录：`admin/src/components/gms/`

- `BacktestManagement.vue`
  - 参考 `[admin/src/components/pvfrs/BacktestManagement.vue](admin/src/components/pvfrs/BacktestManagement.vue)`
  - 表单字段按 GMS 回测需要：
    - 任务名称
    - 市场：CN/HK/ALL
    - 日期范围 start/end
    - 目标阈值 X（如 3/5/10%，默认 5%）
    - 持有窗口：固定 20（可展示为只读或可调）
    - min_score（可选）
    - 股票池模式（可选）：全市场/自定义列表（默认全市场）
  - 任务列表：状态、进度、查看详情、取消/删除
- `TaskDetail.vue`
  - 展示：任务参数、进度日志、样本数/命中率汇总、分组统计（左侧/右侧、分数分桶）
- `ReportAnalysis.vue`
  - 历史报告列表、报告详情、下载明细（CSV/Excel）
- `StrategyConfiguration.vue`
  - 读取/编辑 GMS 配置（对齐 `backend_core/strategies/gms/gms_config.json` / `GMSConfigManager`）
  - 提供“保存配置/重置默认/历史版本”（最低先做保存/加载）
- `RealTimeMonitor.vue`（可选）
  - 若短期不做实时监控，可先复用状态卡片+任务列表完成主要诉求。

### 3) 新增前端 service

- 新增：`admin/src/services/gmsApi.ts`
  - 参考 `[admin/src/services/pvfrsApi.ts](admin/src/services/pvfrsApi.ts)`
  - 封装 GMS 后台接口：system/status、backtests CRUD、progress/logs、reports 列表/详情/下载、config 读写。

## 三、后端（backend_api + backend_core）接口与任务体系

### 1) 新增 GMS 管理端 API 路由

- 新增：`backend_api/admin/gms_admin_routes.py`
  - 路由前缀建议：`/api/admin/gms`
  - API 设计对齐 `pvfrs_admin_routes_enhanced.py` 的风格与返回结构（success + data/tasks 等）：

建议最小闭环接口：

- `GET /api/admin/gms/system/status`
  - 返回：runningBacktests/totalReports/systemHealth 等
- `POST /api/admin/gms/backtests`
  - 创建任务，返回 task_id
- `GET /api/admin/gms/backtests?status=&limit=&offset=`
  - 任务列表
- `GET /api/admin/gms/backtests/{task_id}`
  - 任务详情（含参数与汇总指标）
- `GET /api/admin/gms/backtests/{task_id}/logs`
  - 任务日志
- `POST /api/admin/gms/backtests/{task_id}/cancel`
  - 取消任务
- `DELETE /api/admin/gms/backtests/{task_id}`
  - 删除任务
- `GET /api/admin/gms/reports?limit=&offset=`
  - 报告列表
- `GET /api/admin/gms/reports/{report_id}`
  - 报告详情
- `GET /api/admin/gms/reports/{report_id}/download`
  - 下载明细文件
- `GET /api/admin/gms/config`
- `PUT /api/admin/gms/config`

并在 `[backend_api/main.py](backend_api/main.py)` 注册该 router（参考 pvfrs admin router 注册方式）。

### 2) 任务存储与执行

复用 PVFRS 的“任务存储+执行”思路，但为 GMS 定制最小集：

- 新增 `backend_core/strategies/gms/admin_interface.py`
  - `create_backtest(config) -> task_id`
  - `list_backtest_tasks(...)`
  - `get_task(task_id)` / `get_logs(task_id)`
  - `cancel_task(task_id)` / `delete_task(task_id)`
  - `list_reports(...)` / `get_report(report_id)` / `download_report(report_id)`
- 新增 `backend_core/strategies/gms/backtest_storage.py`
  - 保存任务元数据、进度、日志、产物路径（可落地到 sqlite/json 文件，或新增 DB 表；优先跟 PVFRS 一致的落地方式）
- 新增 `backend_core/strategies/gms/backtest_worker.py`
  - 真正跑回测：调用既定的回测逻辑（见下一节）并持续写 progress/log。

任务执行方式（与现有项目匹配）：

- 若 PVFRS 采用后台线程/进程 + storage 轮询：GMS 同样实现。
- 若已有统一的任务调度组件：直接挂载。

### 3) 回测与“准确率”评估核心逻辑

- 复用上一版计划中的核心模块（建议位置）：
  - `backend_core/strategies/gms/backtest_runner.py`
- 评估口径固定为：信号后 20 个交易日内最高价是否达到 `close_t*(1+target_pct)`。
- 产物：
  - 汇总 JSON（命中率、分组统计、分桶统计）
  - 明细 CSV/Excel（样本级）

## 四、实施顺序（推荐）

- 后端先打通：任务 storage + 创建任务 + 列表/详情 + worker 跑出报告
- 前端再对接：用 `gmsApi.ts` 拉任务列表、查看进度、下载报告
- 最后补齐：策略配置页与系统状态卡片数据

## 五、涉及文件

- 前端：
  - `[admin/src/views/PVFRSManagementView.vue](admin/src/views/PVFRSManagementView.vue)`（参考）
  - `[admin/src/components/pvfrs/BacktestManagement.vue](admin/src/components/pvfrs/BacktestManagement.vue)`（参考）
  - `[admin/src/router/index.ts](admin/src/router/index.ts)`
  - 新增：`admin/src/views/GMSManagementView.vue`
  - 新增：`admin/src/components/gms/`*
  - 新增：`admin/src/services/gmsApi.ts`
- 后端：
  - 参考：`backend_api/admin/pvfrs_admin_routes_enhanced.py`
  - 新增：`backend_api/admin/gms_admin_routes.py`
  - 新增：`backend_core/strategies/gms/admin_interface.py`、`backtest_storage.py`、`backtest_worker.py`、`backtest_runner.py`

