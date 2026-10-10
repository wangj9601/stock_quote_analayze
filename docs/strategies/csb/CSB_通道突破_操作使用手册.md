# CSB 通道突破 — 操作使用手册

> 面向使用者（选股 / 回测 / 运维）。策略规则见《CSB_通道突破_业务规则与信号计算规则.md》，架构与接口见《CSB_STRATEGY_IMPLEMENTATION_DESIGN.md》。

---

## 1. 快速上手（三个入口）

| 场景 | 入口 | 说明 |
|------|------|------|
| 选股 | 前台「策略选股」→ **通道突破** 页签 | `frontend/screening.html` + `csb_screening.js`；调 `GET /api/screening/csb-strategy` |
| 个股信号追溯 | 前台个股 → **CSB 追溯**页 | `frontend/stock_csb_trace.html` + `stock_csb_trace.js` |
| 参数 / 预计算 / 回测 | 管理端 **`/csb-management`** | 四个页签：策略参数 / 回测管理 / 报告与分析 / 操作记录 |

权限点：`channel.screening.tab.csb`（页签）、`channel.screening.tab.csb.btn.refresh`（刷新）。

---

## 2. 选股页操作

**可选范围（scope）**

- `market` 全市场（A 股）
- `watchlist` 我的自选（需登录）
- `single` 单只股票（代码或名称）
- `industry_board` 行业板块（BK 编码，可多选）
- `concept_board` 概念板块（可多选）

**筛选项**

- **基准日** `date`：默认取行情最新交易日。
- **参数版本** `config_id`：默认使用「默认」版本。
- **A 股板型** `cn_board_segment`：`ALL/MAIN/CYB/SZ_SME/KCB/BJ`，可多选。
- **信号类型** `signal_type`：`CSB_PROBE / CSB_BREAKOUT / CSB_LPS` 等。
- **仅看买点** `entry_only`（默认开）。
- **最大返回条数** `max_results`（默认 10000）。

**数据来源与「需预计算」提示**

选股默认 **优先读 `csb_signal_trace` 预计算结果**；命中缓存或当日已扫描即返回 `source=csb_signal_trace`。

- **全市场 + 无预计算**：出于性能与「只扫前 N 只必然 0 条」的误导性现算考虑，**默认不现算**，返回 `need_precompute=true` 并提示先执行预计算或缩小范围。
- 如需强制全市场现算：设置环境变量 `CSB_ALLOW_FULL_MARKET_REALTIME=true`（**不推荐**，耗时很长）。
- **缩小范围（自选/板块/单股）** 时会 **现算**，无需预计算。

> 推荐工作流：**收盘后跑预计算 → 次日开盘前看选股页**。这样选股页秒开且结果即最终口径。

---

## 3. 个股信号追溯页

页面：`/stock_csb_trace.html`

- 读取该股 `csb_signal_trace` 历史信号序列（可按日期区间、仅买点、参数版本过滤）。
- **强制重新计算**：对该股按当前参数版本重算并覆盖写库；异步执行，页面轮询 `task_id` 进度。
  - 会自动 **清除该股该版本旧记录** 后重算，**不影响其他股票、其他版本**。
  - 同一股票同一版本已有任务在跑时会复用，不会重复触发。
- 评分明细弹窗由 `csb_score_detail.js` 渲染（粘合天数/带宽/回踩/地量/换手/买点/放量各项得分）。

API：

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/stock/csb/signal-history` | 读取该股预计算信号 |
| POST | `/api/stock/csb/recompute` | 触发异步重算，返回 `task_id` |
| GET | `/api/stock/csb/recompute/{task_id}` | 查询重算进度 |

---

## 4. 管理端 `/csb-management`

顶部状态卡：运行中回测 / 待执行 / 失败任务 / 历史报告；右上「信号预计算」「刷新状态」。

### 4.1 策略参数（策略参数页签）

- 查看 **默认参数**、创建/编辑 **参数版本**（名称唯一、描述、`config_params`）。
- 每个版本可设：`is_active`（启用）、`is_default`（默认版本）、`precompute_enabled`（纳入日终预计算）。
- **保存参数后不会自动重算**：页面会提示 `need_recompute`。旧 trace 按 `config_id` 保留，需对该版本 **重跑预计算** 或对个股 **强制重新计算**。

> 预计算覆盖的版本 = `is_active = True` 且（`is_default = True` 或 `precompute_enabled = True`）。

### 4.2 信号预计算

`POST /api/admin/csb/precompute/run`（后台执行）：

- **交易日**：默认取行情最新日。
- **参数版本**：空 = 全部「预计算启用」版本。
- **候选上限** `limit`：仅调试用，正式跑留空（全市场）。

**预计算做什么**：全市场硬筛 → 命中买点写入 `csb_signal_trace` → 写 `__CSB_SCANNED__` 扫描标记。

**区间强制刷新 / 清空**

- `POST /api/admin/csb/trace/refresh-range`：对 `[start, end]` 区间重算，`purge_first=true` 时先清空该版本全部 trace。
- `POST /api/admin/csb/trace/purge`：清空某版本全部 trace。
- `GET /api/admin/csb/trace/stats`：查看某版本 trace 行数。

> ⚠️ **收紧参数后旧买点可能残留**：日终预计算只覆盖「当日命中行」，不会自动删除历史 trace。若担心残留，请对该版本执行 `purge` 或 `refresh-range`。

### 4.3 回测管理（见第 5 节）

### 4.4 报告与分析

- 已完成任务即报告，同一数据源。支持查看明细、导出 CSV/XLSX、导出 PDF。
- 报告含 **评分分桶**、**因子分桶**、**命中率对照** 等分析。

### 4.5 操作记录

审计日志（写 `operation_logs`，类型前缀 `csb_*`）：`csb_config_create / csb_config_update / csb_trace_purge / csb_trace_refresh_range / csb_backtest_create` 等。

---

## 5. 回测操作

创建回测 `POST /api/admin/csb/backtests`。

**核心参数**

| 参数 | 含义 | 默认 |
|------|------|------|
| `start_date` / `end_date` | 回测区间 | 必填 |
| `strategy_config_id` | 参数版本 | 空=默认版本 |
| `target_pct` / `target_pct_max` | 目标涨幅（小数）；给上限则按 `[lo, hi]` 区间带 | 0.10 |
| `horizon_days` | 观察期（交易日） | 10 |
| `min_score` | 得分门槛覆盖 | 空=用参数包 |
| `use_trace` | 优先读 trace（缺失日自动补算） | true |
| `exit_mode` | `hit_rate` / `risk_exit` / `structure_exit` | hit_rate |
| `signal_quality_mode` | `standard` / `premium` | standard |
| `compare_hit_rate` | 非 hit_rate 完成后自动再跑同配置命中率对照 | 非 hit_rate 时默认开 |

**股票池 `stock_pool_mode`**

`all` 全市场 · `single` 单股 · `custom` 自定义列表 · `watchlist` 自选（可指定 `watchlist_user_id`）· `gms_watchlist` GMS 观察股（仅借代码列表，**不调用 GMS 引擎**）· `industry_board` 行业板块 · `concept_board` 概念板块。

可选 **A 股板型** `cn_board_segment` 收窄；`all` 时选择板型会 **展开为具体股票池**。

**任务生命周期**：`pending → running → completed/failed/cancelled`，支持 **暂停 / 继续 / 取消 / 重跑 / 删除 / 批量删除**（协作式：worker 轮询暂停与取消标志）。

**导出**：明细 `CSV` / `XLSX`；详情 `PDF`（依赖 `xhtml2pdf`，未安装返回 501）。

> 回测口径（出场模式、分桶、与 URT 对照）详见《CSB_回测口径与URT对照.md》。

---

## 6. 定时任务与采集流程

**日终 cron**

- 任务 ID：`csb_signals_cn`，默认 **周一~周五 19:50**。
- 环境变量：`SCHED_CSB_SIGNALS_CN_DOW`（默认 `mon-fri`）、`SCHED_CSB_SIGNALS_CN_HOUR`（19）、`SCHED_CSB_SIGNALS_CN_MINUTE`（50）。
- 总开关：`ENABLE_CSB_PRECOMPUTE`（默认 true）；关闭需 `ENABLE_LEGACY_COLLECTION_CRON=true` 才会注册。

**采集工作流节点**

`csb_signals_cn`（节点名「CSB信号预计算(A股)」），位于 `urt_signals_cn` 之后、`sbbr_signals_cn` 之前：

```
... → gms_signals_cn → urt_signals_cn → csb_signals_cn → sbbr_signals_cn → rpe_signals_cn
```

**手动触发**：管理端「信号预计算」、`POST /api/admin/csb/precompute/run`。

---

## 7. 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `ENABLE_CSB_PRECOMPUTE` | true | 关闭日终 CSB 预计算 |
| `SCHED_CSB_SIGNALS_CN_DOW/HOUR/MINUTE` | mon-fri / 19 / 50 | cron 时间 |
| `CSB_SCREEN_WORKERS` | min(4, CPU) | 扫描线程数（上限 16） |
| `CSB_HIST_BATCH_CODES` | 自动 | 批量拉行情的 codes 分块（上限 120） |
| `CSB_FULL_MARKET_TRACE_MIN_CODES` | 500 | 判定「全市场已扫描」的最小股票数阈值 |
| `CSB_ALLOW_FULL_MARKET_REALTIME` | 空 | 允许全市场现算（谨慎开启） |

---

## 8. 常见问题（FAQ）

**Q1：选股页全市场返回空并提示「需预计算」？**
正常。全市场默认不现算。请先跑预计算，或把范围缩小为自选/板块/单股（会自动现算）。

**Q2：改了参数为什么选股结果没变？**
参数保存后不自动重算。请对该版本「跑预计算」，或对个股「强制重新计算」。

**Q3：收紧参数后还出现老买点？**
日终预计算不删历史 trace。对该版本执行 `trace/purge` 或 `trace/refresh-range`。

**Q4：回测 `structure_exit` 跑完多出一条「命中率对照」任务？**
是设计行为（`compare_hit_rate`）。不想联动可显式传 `compare_hit_rate=false`。

**Q5：PDF 导出报 501？**
服务端未安装 `xhtml2pdf`。改用 CSV/XLSX 导出，或安装依赖。

**Q6：预计算/回测很慢或 OOM？**
大幅拉取时会自动缩小分块（`CSB_HIST_BATCH_CODES`），仍慢可下调 `CSB_SCREEN_WORKERS`，或用 `limit` 先小范围验证。

**Q7：港股能跑 CSB 吗？**
CSB 为 **A 股（CN）** 策略。管理端预计算弹窗的「港股」选项当前不接入 CSB 链路，仅 A 股有效。

---

## 9. 相关文件索引

| 用途 | 路径 |
|------|------|
| 策略内核 | `backend_core/strategies/csb/` |
| 前台选股 API | `backend_api/stock/stock_screening_routes.py`（`/api/screening/csb-strategy`） |
| 前台追溯 API | `backend_api/stock/csb_frontend_routes.py` |
| 管理端 API | `backend_api/admin/csb_admin_routes.py` |
| 选股页脚本 | `frontend/js/csb_screening.js` |
| 追溯页 | `frontend/stock_csb_trace.html` + `js/stock_csb_trace.js` |
| 评分明细 | `frontend/js/csb_score_detail.js` |
| 管理端视图 | `admin/src/views/CsbManagementView.vue` + `admin/src/components/csb/*` |
| 建表迁移 | `migrations/add_csb_tables.py` |
| 单测 | `test/test_csb_core.py`、`test_csb_defense.py`、`test_csb_admin_backtest_api.py`、`test_csb_backtest_pause_resume.py` |
