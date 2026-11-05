# 管理端 URT/CSB/RPE 预计算信号查询 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在管理端 URT、CSB、RPE 三页各增加「信号结果」Tab，按日只读查询日终预计算触发信号，并显示条数与最后写入时间。

**Architecture:** 各策略 `trace_store` / `signal_storage` 增加带分页与元数据的只读列表函数；URT/CSB 新增 `GET /api/admin/{urt|csb}/signals`；RPE 在 `selection-results` 的 **trace_only 分支**最小补参（`offset`、`last_written_at`、`has_any_trace`、真实 `total`），管理端 Tab 固定 `trace_only=true&entry_only=true`，禁止走 live 现算。前端对齐形态类信号 Tab（无导出、无行跳转）。

**Tech Stack:** FastAPI、SQLAlchemy、PostgreSQL（测试可用既有内存/SQLite fixture）、Vue3 + Element Plus（admin）

**Spec:** `docs/superpowers/specs/2026-11-05-admin-urt-csb-rpe-signal-query-design.md`

## Global Constraints

- 只读查询；不改日终预计算写入逻辑与买卖口径
- 触发定义：URT `buy_signal=true`；CSB `entry_signal=true`（排除 SCANNED/占位）；RPE `entry_only=true`
- 默认交易日：后端可解析最新交易日；默认 config：各策略 effective/default / precompute 启用版
- URT 支持 `market=CN|HK`（`is_hk_stock_code`）；CSB/RPE 本期仅 CN
- 分页默认 `limit=50`，`offset>=0`，`limit` 上限 `2000`
- 响应骨架字段名：`items`（RPE trace 分支可同时保留既有 `data` 别名指向同一列表）、`total`、`trade_date`、`config_id`、`last_written_at`、`has_any_trace`
- 测试放在 `./test`；提交仅在用户明确要求时执行（本计划 Step「Commit」视为可选门禁）
- 用中文 UI 文案，空态按 spec §5

## Review Focus

- URT `market=CN` 不得漏出港股代码，`market=HK` 不得漏出 A 股
- 仅有扫描占位/无触发行时 `total=0` 且 `has_any_trace=true`（若该策略有占位）
- RPE 管理端查询不得因未传 `trace_only` 误触 live screen / upsert
- `config_id` 省略时落到 effective/default，而不是静默空列表且无错误
- 分页：`total` 为触发总数，不是当前页长度

## File map

| 文件 | 职责 |
|------|------|
| `backend_core/strategies/urt/trace_store.py` | `list_admin_buy_signals(...)` 分页+市场+元数据 |
| `backend_core/strategies/csb/trace_store.py` | `list_admin_entry_signals(...)` 同上（无 market） |
| `backend_core/strategies/rpe/signal_storage.py` | `load_traces` 扩展 offset/count/meta 或新增 `list_admin_entry_signals` |
| `backend_api/admin/urt_admin_routes.py` | `GET /signals` |
| `backend_api/admin/csb_admin_routes.py` | `GET /signals` |
| `backend_api/admin/rpe_admin_routes.py` + `rpe/frontend_interface.py` | selection-results trace 分支补参；或薄封装保证 admin 默认 trace_only |
| `admin/src/services/urtApi.ts` / `csbApi.ts` / `rpeApi.ts` | listSignals / selectionResults 参数 |
| `admin/src/components/strategy/StrategySignalResultsPanel.vue`（新建） | 共用：日期/配置/市场/分页/空态/顶栏 |
| `admin/src/views/UrtManagementView.vue` / `CsbManagementView.vue` / `RPEManagementView.vue` | 挂「信号结果」Tab |
| `test/test_urt_admin_signals.py` | URT 列表单测 |
| `test/test_csb_admin_signals.py` | CSB 列表单测 |
| `test/test_rpe_admin_signals.py` | RPE trace 列表/补参单测 |

---

### Task 1: URT `list_admin_buy_signals` + admin `/signals`

**Files:**
- Modify: `backend_core/strategies/urt/trace_store.py`
- Modify: `backend_api/admin/urt_admin_routes.py`
- Create: `test/test_urt_admin_signals.py`

**Interfaces:**
- Consumes: `URTSignalTrace`；`is_hk_stock_code`（`urt.data_loader`）；`URTConfigManager.resolve_effective_config_id` / `list_precompute_config_ids`；`resolve_urt_trade_date`（缺省日）
- Produces:
  - `list_admin_buy_signals(db, *, trade_date: str, config_id: int, market: str = "CN", code: str | None = None, limit: int = 50, offset: int = 0) -> dict`  
    返回 `{items, total, trade_date, config_id, last_written_at, has_any_trace}`；`items` 仅 `buy_signal=True` 且非 `URT_TRACE_SCANNED_MARKER`；按 `score` desc；`market` 用 `is_hk_stock_code` 过滤
  - `GET /api/admin/urt/signals` → 同上；`config_id` 省略时 resolve effective，再无则 `list_precompute_config_ids` 的第一个；再无则 400

- [ ] **Step 1: 写失败单测** `test/test_urt_admin_signals.py`

覆盖：
1. `test_list_admin_buy_signals_filters_market_and_non_buys` — 同日同 config 混入 CN 买点、HK 买点、`buy_signal=False`、扫描占位；`market=CN` 只返回 CN 买点；`total`/`has_any_trace` 正确
2. `test_list_admin_buy_signals_pagination` — 3 条买点 `limit=2,offset=0` → 2 条且 `total=3`；`offset=2` → 1 条
3. `test_list_admin_buy_signals_empty_with_scanned_only` — 仅占位行 → `items=[]`,`total=0`,`has_any_trace=True`
4. （可选）路由级：无 config 可解析时 400（可用 FastAPI TestClient + 既有 admin fixture；若项目路由测成本高，可只测 store 层并把 resolve 逻辑抽成纯函数测）

用内存 SQLite 或项目既有 test DB fixture；插入 `URTSignalTrace` 最小字段即可。

- [ ] **Step 2: 跑测确认失败**

Run: `pytest test/test_urt_admin_signals.py -v`  
Expected: FAIL（函数未定义）

- [ ] **Step 3: 实现 `list_admin_buy_signals` 与 `GET /signals`**

路由鉴权风格与同文件其它 URT admin 端点一致（不单独引入与现网不一致的 auth）。

- [ ] **Step 4: 跑测通过**

Run: `pytest test/test_urt_admin_signals.py -v`  
Expected: PASS

- [ ] **Step 5: Commit（仅当用户要求提交时）**

```bash
git add backend_core/strategies/urt/trace_store.py backend_api/admin/urt_admin_routes.py test/test_urt_admin_signals.py
git commit -m "feat(urt): admin list precomputed buy signals by date"
```

---

### Task 2: CSB `list_admin_entry_signals` + admin `/signals`

**Files:**
- Modify: `backend_core/strategies/csb/trace_store.py`
- Modify: `backend_api/admin/csb_admin_routes.py`
- Create: `test/test_csb_admin_signals.py`

**Interfaces:**
- Consumes: `CSBSignalTrace`；CSB config resolve（`is_default` / `list_precompute_config_ids`）；CSB 交易日 resolve（与 `scheduled_precompute` 一致）
- Produces:
  - `list_admin_entry_signals(db, *, trade_date: str, config_id: int, code: str | None = None, limit: int = 50, offset: int = 0) -> dict`  
    同 URT 骨架；过滤 `entry_signal=True`，排除 `CSB_TRACE_SCANNED_MARKER` 与 `CSB_STOCK_DAY_SCANNED`；按 `score` desc
  - `GET /api/admin/csb/signals` — query：`trade_date`,`config_id`,`code`,`limit`,`offset`（无 market）

- [ ] **Step 1: 写失败单测** `test/test_csb_admin_signals.py`

1. `test_list_admin_entry_signals_only_entries` — 混入 entry / 非 entry / SCANNED → 只返回 entry
2. `test_list_admin_entry_signals_pagination_and_meta` — 分页 + `last_written_at` 非空
3. `test_list_admin_entry_signals_no_rows_has_any_false` — 完全无行 → `has_any_trace=False`

- [ ] **Step 2: 跑测失败** — `pytest test/test_csb_admin_signals.py -v`

- [ ] **Step 3: 实现 store + 路由**

- [ ] **Step 4: 跑测通过** — `pytest test/test_csb_admin_signals.py -v`

- [ ] **Step 5: Commit（用户要求时）** — `feat(csb): admin list precomputed entry signals by date`

---

### Task 3: RPE 管理端只读信号列表（trace 路径补参）

**Files:**
- Modify: `backend_core/strategies/rpe/signal_storage.py`
- Modify: `backend_core/strategies/rpe/frontend_interface.py`（trace_only 分支）
- Modify: `backend_api/admin/rpe_admin_routes.py`（必要时显式文档化/默认参数）
- Create: `test/test_rpe_admin_signals.py`

**Interfaces:**
- Consumes: 现有 `load_traces`
- Produces:
  - `list_admin_entry_signals(db, *, trade_date, config_id, code=None, limit=50, offset=0) -> dict`  
    或扩展 `load_traces` 返回同骨架；`entry_only=True`；`last_written_at = max(updated_at or created_at)`；`has_any_trace` = 该日该 config 是否存在任意行
  - Admin `GET /selection-results` 在 **管理端信号 Tab 调用约定**：必须 `trace_only=true&entry_only=true`；trace 分支响应增加 `items`（=`data`）、`last_written_at`、`has_any_trace`、`offset` 支持；`total` 为触发总数  
  - 若补参会迫使 live 路径行为变化：改为新增 `GET /api/admin/rpe/signals` 只调 `list_admin_entry_signals`，**禁止**调用 `engine.screen`；UI 走 `/signals`

- [ ] **Step 1: 写失败单测**

1. `test_rpe_list_admin_entry_signals_entry_only` — 有/无 entry 混合
2. `test_rpe_list_admin_entry_signals_pagination` — total 与 offset
3. `test_rpe_admin_path_does_not_require_live_screen` — 断言列表函数不调用 `RPEStrategyEngine.screen`（monkeypatch 哨兵）

- [ ] **Step 2–4: 红 → 实现 → 绿** — `pytest test/test_rpe_admin_signals.py -v`

- [ ] **Step 5: Commit（用户要求时）** — `feat(rpe): admin read-only precomputed entry signal list`

---

### Task 4: 前端共用面板 + 三策略挂载

**Files:**
- Create: `admin/src/components/strategy/StrategySignalResultsPanel.vue`
- Modify: `admin/src/services/urtApi.ts`、`csbApi.ts`、`rpeApi.ts`
- Modify: `admin/src/views/UrtManagementView.vue`、`CsbManagementView.vue`、`RPEManagementView.vue`

**Interfaces:**
- Consumes: Task 1–3 API；各策略已有 `listConfigs` / strategy-configs
- Produces: Tab `name="signals"` label「信号结果」；props 示例：
  - `strategyCode: 'URT'|'CSB'|'RPE'`
  - `listSignals: (q) => Promise<SignalListResponse>`
  - `listConfigs: () => Promise<ConfigRow[]>`
  - `showMarketSwitcher?: boolean`（URT true）
  - `columns: { prop, label, width?, formatter? }[]`
  - 默认：进入 Tab / mount 时用默认日+默认 config 自动查询；顶栏展示 `total` 与 `last_written_at`；空态按 `has_any_trace`；**无导出按钮、无 row-click 跳转**；`el-pagination` 绑定 limit/offset

列配置（实现时可微调对齐 screening）：
- URT: code, name, score, signal_strength, close, ma20, volume_multiple, yang_rule, created_at/写入时间
- CSB: code, name, signal_type, score, close_price, channel_lower, channel_upper, squeeze_days, entry_low, updated_at
- RPE: code, name, signal_type, z_score, ratio, sector_name, close, nearest_support, nearest_resistance, updated_at

- [ ] **Step 1: API 客户端加 `listSignals`（RPE 可用 `selectionResults` 封装固定 `trace_only/entry_only` 或走 `/signals`）**

- [ ] **Step 2: 实现 `StrategySignalResultsPanel.vue` 并在三 View 增加 Tab**

URT/CSB：在 `StrategyOpsShell` 的 slot 内与其它 pane 并列增加 signals pane。  
RPE：在现有 `el-tabs` 增加 pane；subtitle 可改为含「信号结果」。

- [ ] **Step 3: 手工验收清单（实现者勾选）**

1. 三页均出现「信号结果」
2. 默认日/默认配置自动出表或正确空态
3. URT 切换 CN/HK 结果变化
4. 切版本、切日、分页正常
5. 无导出、点击行无跳转
6. 顶栏条数与最后写入时间可见

- [ ] **Step 4: Commit（用户要求时）** — `feat(admin): signal results tab for URT/CSB/RPE`

---

### Task 5: 回归与收尾

**Files:** 无新文件（除非修 bug）

- [ ] **Step 1: 跑相关单测**

```bash
pytest test/test_urt_admin_signals.py test/test_csb_admin_signals.py test/test_rpe_admin_signals.py -v
```

Expected: 全部 PASS

- [ ] **Step 2: 快速冒烟既有 RPE selection-results 调用方（若改了响应字段）** — `pytest test/test_rpe_api_and_backtest.py -v -k selection`（或文件内相关用例）；不应破坏旧字段 `data`/`total`

- [ ] **Step 3: 更新 spec 状态旁注「已实现」仅在全部验收后（可选）**

- [ ] **Step 4: 请用户在管理端点验三页后再决定是否 commit/push**

---

## Self-review (plan author)

| Spec 要求 | 对应 Task |
|-----------|-----------|
| URT/CSB/RPE 信号 Tab | Task 4 |
| 仅触发行 + 排序 | Task 1–3 |
| 默认日/配置、切日切版 | Task 1–3 resolve + Task 4 UI |
| URT CN/HK | Task 1 + Task 4 `showMarketSwitcher` |
| 顶栏条数/写入时间、空态 | 响应 meta + Task 4 |
| 分页 | Task 1–3 |
| 无导出/无跳转 | Task 4 |
| RPE 优先复用/最小补参 | Task 3 |
| 不做 GMS/SBBR/导出/采集深链 | 未列入 |

Review Focus 五项均有对应用例（Task 1 market/scanned；Task 3 no live；Task 1–2 default config 400；分页 total）。
