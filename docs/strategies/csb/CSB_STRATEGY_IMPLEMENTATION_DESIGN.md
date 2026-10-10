# CSB 低位狭长通道磨底 + 放量突破 — 系统设计

> 策略代号 **CSB**（前端名「通道突破」）。本文档描述系统架构、模块职责、数据表、接口、预计算与前端集成。
> 业务规则见《CSB_通道突破_业务规则与信号计算规则.md》；操作步骤见《CSB_通道突破_操作使用手册.md》。

---

## 1. 定位

独立策略包：`backend_core/strategies/csb/`。**不耦合** GMS / URT / SBBR / RPE / VSB 引擎，使用独立表空间 `csb_*`。管理端能力与 URT 同级（参数版本 / 预计算 / 回测 / 报告 / 审计），但出场与因子分桶使用 CSB 自己的通道 / 量能字段。

**核心链路**

```
换手初筛 → MA5/10/20/60 粘合通道(≥15日) + 年线走平/向上 → N≥2 次独立回踩 + 地量
  → 买点1 PROBE（缩量止跌/Spring）
  → 买点2 BREAKOUT（放量实体阳线突破上轨）
  → 买点3 LPS（突破后缩量回踩确认）
  → 防守：三日不重回 / 基准止损 / 派发 / MA10-MA20+波段阶梯跟踪
```

---

## 2. 模块职责

| 文件 | 职责 |
|------|------|
| `config.py` | `CSBConfigManager`：默认参数、`csb_strategy_configs` 多版本 CRUD、缓存、v1→v2 运行时兼容升级；信号类型常量 |
| `indicators.py` | 纯函数指标（SMA、归一化斜率、均量/均换手、实体%、上影比）—— 可单测 |
| `channel.py` | 通道：MA5/10/20/60 计算、上下轨、粘合带宽、连续粘合天数、HH20、通道状态 |
| `setup_detector.py` | SETUP：换手初筛、年线斜率、独立回踩计数、Spring、地量 |
| `entry_detector.py` | 买点：`detect_probe` / `detect_breakout` / `confirm_lps` / `detect_lps` / `detect_entry`（优先级 BREAKOUT>LPS>PROBE） |
| `defense_exit.py` | 防守出场：假突破、基准止损、派发、阶梯跟踪；`evaluate_structure_exit_rules` / `evaluate_risk_exit_rules` |
| `strategy_engine.py` | `evaluate_one`（单票）、`CSBStrategyEngine.screen`（全市场/池扫描）、`screen_universe_for_dates`（区间一次扫描）、`compute_score_detail` |
| `data_loader.py` | `CSBDataLoader`：候选池、日 K 加载（单票/区间/批量分块流式，OOM 自动降级）、交易日解析、批量分块估算 |
| `trace_store.py` | `csb_signal_trace` 读写：upsert、按股查询、按日买点查询、purge、扫描标记 `__CSB_SCANNED__`、覆盖度判定 |
| `signal_storage.py` | 信号落库封装（`upsert_signal_traces` / `load_traces`） |
| `frontend_interface.py` | 对外选股入口：`CSBFrontendInterface.screen`（优先读 trace，全市场现算默认禁止） |
| `scheduled_precompute.py` | 日终预计算、区间 trace 刷新、cron 入口 `scheduled_csb_signals_cn` |
| `backtest_runner.py` | 回测执行器：多出场模式、次日开盘入场、评分/因子分桶、命中率对照 |
| `backtest_worker.py` | 后台回测线程：暂停/继续/取消协作式控制、自动创建命中率对照任务 |
| `backtest_storage.py` | 回测任务/报告持久化（`csb_backtest_tasks`） |
| `backtest_factor_report.py` | 因子展平、评分分桶、因子分桶、命中率对照结构 |
| `backtest_pdf.py` | 回测详情 PDF 渲染（依赖 `xhtml2pdf`） |
| `json_safe.py` | JSON 落库前的安全清洗（PG JSON 兼容） |

**调用链（选股）**

```
GET /api/screening/csb-strategy
  → CSBFrontendInterface.screen
      → [prefer_cache] trace_store.query_buy_signals_for_date   （命中 → source=csb_signal_trace）
      → [未命中且限定代码池] CSBStrategyEngine.screen          （现算）
      → [未命中且全市场] 默认返回 need_precompute
```

**调用链（回测）**

```
POST /api/admin/csb/backtests
  → backtest_storage.create_task
  → backtest_worker.start_backtest_task（线程）
      → run_csb_backtest
          → _ensure_trace_for_backtest_range（缺失日自动补算 + 写扫描标记）
          → 逐日读买点 → 次日开盘入场 → 按 exit_mode 出场
          → 分桶统计 → complete_task
      → _maybe_start_hit_rate_compare（非 hit_rate 自动对照）
```

---

## 3. 信号枚举

| 类型 | 含义 |
|------|------|
| `CSB_SETUP` | 通道 + 年线 + 回踩 + 地量成立（观察） |
| `CSB_PROBE` | 买点1 缩量止跌试仓 |
| `CSB_BREAKOUT` | 买点2 放量突破上轨 |
| `CSB_LPS` | 买点3 突破后缩量回踩确认 |
| `CSB_FALSE_BREAK` | 突破后三日收盘跌回上轨下 |
| `CSB_STOP` | 基准/百分比止损 |
| `CSB_TRAIL` | 均线-波段阶梯跟踪卖出 |
| `CSB_DISTRIBUTE` | 主升后放量派发 |

`BUY_SIGNAL_TYPES = {CSB_PROBE, CSB_BREAKOUT, CSB_LPS}`；`CSB_TRACE_SCANNED_MARKER = "__CSB_SCANNED__"`（全市场扫描占位，用于覆盖度判定）。

---

## 4. 数据表

### 4.1 `csb_strategy_configs` — 参数版本

| 字段 | 类型 | 说明 |
|------|------|------|
| id | serial PK | |
| name | varchar(100) UNIQUE | 版本名 |
| description | text | |
| config_params | jsonb NOT NULL | 参数包（深合并默认值） |
| is_active | bool | 启用 |
| is_default | bool | 默认版本（读取优先级最高） |
| precompute_enabled | bool | 纳入日终预计算 |
| created_at / updated_at | timestamp | |

### 4.2 `csb_signal_trace` — 日终信号追溯

| 字段 | 类型 | 说明 |
|------|------|------|
| id | serial PK | |
| code | varchar(20) | 股票代码（或 `__CSB_SCANNED__`） |
| trade_date | date | 交易日 |
| config_id | int FK→csb_strategy_configs(id) ON DELETE CASCADE | 参数版本 |
| signal_type | varchar(32) | 信号类型 |
| name / setup_ok / entry_signal / score | | 摘要字段 |
| close_price / channel_lower / channel_upper / squeeze_days / entry_low | | 展示字段 |
| detail | jsonb | setup/entry/score 明细 |
| created_at / updated_at | timestamp | |

**唯一键**：`(code, trade_date, config_id, signal_type)`。
索引：code / trade_date / config_id / signal_type / (config_id, trade_date)。

### 4.3 `csb_backtest_tasks` — 回测任务与报告

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | varchar(64) PK | |
| name | varchar(500) | |
| status | varchar(20) | pending/running/completed/failed/cancelled/paused |
| progress / message | | 进度 |
| config | jsonb | 回测配置 + trade_logic/risk_params |
| logs | jsonb | 日志行 |
| summary | jsonb | 汇总（命中率/胜率/分桶/对照…） |
| error | text | |
| details_path / details_csv_bytes | varchar / bytea | 明细落盘或内联 |
| created_at / started_at / completed_at | timestamp | |

**迁移**：`python migrations/add_csb_tables.py`（幂等 `CREATE TABLE IF NOT EXISTS`）。

---

## 5. API

### 5.1 前台选股

`GET /api/screening/csb-strategy`

| 参数 | 说明 |
|------|------|
| `scope` | market / watchlist / single / industry_board / concept_board |
| `date` | 基准日 YYYY-MM-DD |
| `config_id` | 参数版本 |
| `trace_only` | 仅读 trace（建议 scope=market） |
| `signal_type` | 过滤信号类型 |
| `entry_only` | 仅买点（默认 true） |
| `cn_board_segment[]` | A 股板型（可多选） |
| `industry_board_code[]` / `concept_board_code[]` / `stock_code` | 分范围入参 |
| `max_results` | 最大返回（默认 10000） |

返回：`data / total / search_date / strategy_name("CSB通道突破") / config_id / source / need_precompute / trace_only`。

### 5.2 前台追溯

| 方法 | 路径 |
|------|------|
| GET | `/api/stock/csb/signal-history` |
| POST | `/api/stock/csb/recompute` |
| GET | `/api/stock/csb/recompute/{task_id}` |

### 5.3 管理端 `/api/admin/csb/*`

| 分组 | 端点 |
|------|------|
| 系统 | `GET /system/status` |
| 审计 | `GET /audit-logs` |
| 参数 | `GET /strategy-configs`、`GET /strategy-configs/{id}`、`POST /strategy-configs`、`PUT /strategy-configs/{id}`（别名 `POST /strategy-configs/{id}/update`）、`GET /default-params` |
| 辅助 | `GET /watchlist-users`、`POST /screen-preview` |
| 预计算 | `POST /precompute/run`、`GET /trace/stats`、`POST /trace/purge`、`POST /trace/refresh-range` |
| 回测 | `POST /backtests`、`GET /backtests`、`GET /backtests/{id}`、`GET /backtests/{id}/logs`、`POST /backtests/{id}/{cancel\|pause\|resume\|rerun\|delete}`、`POST /backtests/batch-delete`、`GET /backtests/{id}/export-pdf\|export\|export-xlsx` |
| 报告 | `GET /reports`、`GET /reports/{id}`、`POST /reports/{id}/delete`、`GET /reports/{id}/download\|download-xlsx` |

路由注册见 `backend_api/main.py`（前台 `csb_frontend_router`、管理端 `csb_admin_router`）。

---

## 6. 预计算与调度

- **管理端单日预计算**：`run_csb_precompute_for_config` → `engine.screen(require_entry=True)` → `upsert_trace_rows` → `mark_date_scanned`。
- **区间刷新**：`run_csb_trace_refresh_range`（可先 purge）→ `_ensure_trace_for_backtest_range`。
- **日终 cron**：`csb_signals_cn`，周一~周五 19:50（`SCHED_CSB_SIGNALS_CN_*`，开关 `ENABLE_CSB_PRECOMPUTE`），注册于 `backend_core/data_collectors/main.py`。
- **采集流程节点**：`csb_signals_cn`，位于 `urt_signals_cn` → `csb_signals_cn` → `sbbr_signals_cn`。
- **覆盖度判定**：`dates_ready_for_universe_backtest` — 依据 `__CSB_SCANNED__` 标记或当日股票数阈值（`CSB_FULL_MARKET_TRACE_MIN_CODES`，默认 500）；限定股票池时按池覆盖 80% 判定。
- **预计算覆盖版本**：`is_active` 且（`is_default` 或 `precompute_enabled`）。

---

## 7. 前端集成

| 入口 | 文件 | 说明 |
|------|------|------|
| 选股 Tab「通道突破」 | `frontend/screening.html` + `js/csb_screening.js` | 权限点 `channel.screening.tab.csb` |
| 个股追溯 | `frontend/stock_csb_trace.html` + `js/stock_csb_trace.js` | 预计算查询 + 强制重算 |
| 评分明细 | `frontend/js/csb_score_detail.js` | 分项得分渲染 |
| 管理端 | `admin/src/views/CsbManagementView.vue` + `components/csb/*` | 路由 `/csb-management`，四页签 |
| API 封装 | `admin/src/services/csbApi.ts` | `PREFIX='/api/admin/csb'` |

**管理端组件**：`StrategyConfiguration.vue`（参数）、`BacktestManagement.vue`（回测）、`ReportAnalysis.vue`（报告）、`CsbAuditLogs.vue`（审计）、`TaskDetail.vue`（任务详情）。

**交易观察集成**：`trade_observe_service.py` 中 `SOURCE_CSB = "csb"`，支持将 CSB 买点加入统一观察股。

---

## 8. 性能与健壮性

- **扫描**：分块批量拉行情 + 线程池评点；`CSB_SCREEN_WORKERS`（默认 min(4, CPU)，上限 16）。
- **批量拉取**：`load_bars_batch` 流式（`stream_results` + `yield_per`），按日期跨度自动估算 codes 分块（目标 ~12000 行/批），**OOM 自动减半分块**，极端情况逐票兜底。
- **区间扫描**：`screen_universe_for_dates` 一次拉齐 `[最早日−回看, 最晚日]`，内存中按日截断评点。
- **历史窗口**：由 `history_bars`(280) 估算自然日跨度（≥420 天）。
- **事务**：批量失败回滚后降级；单票失败跳过不影响整体。

---

## 9. 测试

| 文件 | 覆盖 |
|------|------|
| `test/test_csb_core.py` | 默认参数、通道状态、假突破、`evaluate_one` 结构、评分分项、回踩聚类、年线斜率、突破/上影/Probe/Spring/LPS、日期窗口与分块 |
| `test_csb_defense.py` | 防守出场规则 |
| `test_csb_admin_backtest_api.py` | 管理端回测 API |
| `test_csb_backtest_pause_resume.py` | 回测暂停/继续 |
