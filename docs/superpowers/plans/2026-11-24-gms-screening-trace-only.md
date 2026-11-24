# GMS 用户选股只读预计算 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用户站 GMS 选股（全市场与小池）强制只读 `gms_signal_trace`/snapshot，禁止 HTTP 路径现算回填；缺预计算时返回 `need_precompute` 并由前端提示。

**Architecture:** API 层忽略客户端 `trace_only=false`，一律以 `trace_only=True` 调用 `GMSFrontendInterface.get_selection_results`；用户路径 miss 不写 snapshot。Core 在 `trace_only` 时 meta 带上 `need_precompute`，且 structure 补全不落库。前端删除二次全量请求。日批/管理端写路径不变。

**Tech Stack:** Python 3、FastAPI、pytest、现有 GMS 模块、原生前端 JS

**Spec:** `docs/superpowers/specs/2026-11-24-gms-screening-trace-only-design.md`

## Global Constraints

- 测试放在 `./test` 目录
- 不新增表、不做 Alembic
- 不改 URT/其它策略、不上 Redis
- 日批 `scheduled_precompute` / workflow 仍可 `trace_only=False` 写库
- 未明确要求时不主动 `git commit`（计划中的 Commit 步改为「暂存说明 / 等待用户要求再提交」）

## Review Focus

- 请求带 `trace_only=false`：用户选股仍只读，`computed_count=0`
- 无 trace 且预计算未成功：HTTP 200 + `need_precompute=true`，不调用策略引擎 screen
- 有 snapshot 命中：仍只读返回；用户路径不因后续逻辑 `save_snapshot`
- `trace_only` 时 `enrich_results_with_structure(..., persist=False)`，避免读路径写库
- 前端不再构造第二次无 `trace_only` 的 `/api/screening/gms-strategy` URL

---

### Task 1: Core — `trace_only` meta 与只读不落库

**Files:**
- Modify: `backend_core/strategies/gms/frontend_interface.py`（模块头注释、`get_selection_results` 的 meta / `enrich_results_with_structure` 的 `persist`）
- Test: `test/test_gms_selection_fast_path.py`（追加用例）或新建 `test/test_gms_trace_only_need_precompute.py`

**Interfaces:**
- Consumes: 现有 `get_selection_results(..., trace_only: bool, return_meta: bool)`
- Produces: 当 `return_meta=True` 且 `trace_only=True` 时，meta 含：
  - `trace_only: True`
  - `computed_count: 0`
  - `need_precompute: True` 若 `not precompute_ok`（或快路径/慢路径下无可用完整预计算）；若 `precompute_ok` 则为 `False`
  - `persist`：所有 `enrich_results_with_structure` 在 `trace_only=True` 时传 `persist=False`

- [ ] **Step 1: Write the failing test**

```python
def test_trace_only_sets_need_precompute_when_precompute_not_ok(monkeypatch):
    # GMSFrontendInterface；use_trace=True；_precompute_succeeded -> False
    # _load_traces_for_market -> [] 或少量行
    # out, meta = get_selection_results(..., trace_only=True, return_meta=True)
    # assert meta["need_precompute"] is True
    # assert meta["computed_count"] == 0
    # assert meta.get("trace_only") is True
    # patch GMSStrategyEngine.screen 并 assert 未被调用


def test_trace_only_structure_enrich_does_not_persist(monkeypatch):
    # 有 trace 行但缺 structure；trace_only=True
    # patch enrich_results_with_structure，assert 调用 kwargs persist is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test/test_gms_selection_fast_path.py -k "trace_only" -v`（或新文件路径）  
Expected: FAIL

- [ ] **Step 3: Implement meta + persist=False in `frontend_interface.py`**

在快路径与慢路径返回的 meta 中写入 `trace_only` / `need_precompute`；`trace_only` 时所有 `enrich_results_with_structure(..., persist=False)`。更新文件头「缺行现算回填」说明：用户选股只读，回填仅批处理/管理端。

- [ ] **Step 4: Run test to verify it passes**

Run: 同 Step 2  
Expected: PASS

- [ ] **Step 5: Commit（仅当用户要求）**

```bash
git add backend_core/strategies/gms/frontend_interface.py test/test_gms_selection_fast_path.py
# 或新测试文件
git commit -m "fix(gms): trace_only meta need_precompute and no persist on read"
```

---

### Task 2: API — 用户选股强制只读

**Files:**
- Modify: `backend_api/stock/stock_screening_routes.py`（`gms-strategy` 处理函数内：`trace_only` 入参强制、snapshot 保存条件、docstring）
- Test: `test/test_gms_user_screening_trace_only_api.py`（新建；风格对齐 `test/test_gms_etf_scope_route.py`）

**Interfaces:**
- Consumes: Task 1 的 meta 字段；`GMSFrontendInterface.get_selection_results`
- Produces: 路由行为 —— 无论 Query `trace_only` 真假，传入 Core 的 `_trace_only` 恒为 `True`；`save_snapshot` 仅在非用户只读计算路径触发（本期：用户路径永不 `save_snapshot`，因强制只读）

- [ ] **Step 1: Write the failing API tests**

```python
def test_gms_strategy_forces_trace_only_even_when_query_false():
    # TestClient + patch GMSFrontendInterface.get_selection_results
    # GET /api/screening/gms-strategy?scope=cn&date=2026-07-29&trace_only=false
    # assert 调用 kwargs/args 中 trace_only is True
    # assert response JSON gms_trace_meta.computed_count == 0


def test_gms_strategy_does_not_save_snapshot_on_user_path():
    # patch load_snapshot -> None；get_selection_results 返回 ([], meta)
    # patch save_snapshot
    # GET ...&trace_only=false
    # assert save_snapshot 未被调用
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test/test_gms_user_screening_trace_only_api.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement force-read-only in `gms-strategy` route**

在调用 `_run_gms` / executor 前设 `eff_trace_only = True`（忽略 Query）。更新 `Query`/`docstring` 说明：用户站选股强制只读；现算仅日批/管理端。`if use_snapshot and ... and not trace_only` 改为基于 `eff_trace_only`，保证不写 snapshot。响应中透出 Core 的 `need_precompute`。

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test/test_gms_user_screening_trace_only_api.py -v`  
Expected: PASS

- [ ] **Step 5: Commit（仅当用户要求）**

---

### Task 3: 前端 — 去掉二次全量 + 提示

**Files:**
- Modify: `frontend/js/screening.js`（`fetchGmsStrategyResult` 及附近提示）

**Interfaces:**
- Consumes: API `gms_trace_meta.need_precompute` / `trace_complete`
- Produces: 仅一次带 `trace_only=true` 的请求；缺预计算时 Toast/提示文案含「预计算未就绪」或「联系管理端补算」

- [ ] **Step 1: 定位并改写 `fetchGmsStrategyResult`**

删除 `needFullCompute` 分支及第二次 `fetch`；保留单次 `trace_only=true` 请求。若 `need_precompute === true` 或 `trace_complete === false`，用 `CommonUtils.showToast`（或现有条）提示，不自动重算。

- [ ] **Step 2: 静态检查**

在 `frontend/js/screening.js` 内确认 `fetchGmsStrategyResult` 中不再出现第二次 `/api/screening/gms-strategy` 无 `trace_only` 的 URL 拼接。

- [ ] **Step 3: Commit（仅当用户要求）**

---

### Task 4: 需求文档对齐

**Files:**
- Modify: `docs/design/需求分析.md`（约 L609、L931 等「缺失时计算并回填」）

- [ ] **Step 1: 改写表述**

改为：用户站 GMS 选股只读 `gms_signal_trace`（及 snapshot）；缺失时返回 `need_precompute`，由日批/管理端补算；不在用户选股 HTTP 路径现算回填。

- [ ] **Step 2: Grep 确认**

Run: 在 `docs/design/需求分析.md` 中搜索 `缺失时计算并回填`，应无残留（或仅指向非 GMS 用户选股的历史附录且已标注过时）。

- [ ] **Step 3: Commit（仅当用户要求）**

---

### Task 5: 回归烟测

**Files:**
- 不改生产代码（除非失败修复）

- [ ] **Step 1: 跑相关 pytest**

Run:

```bash
pytest test/test_gms_selection_fast_path.py test/test_gms_user_screening_trace_only_api.py test/test_gms_trace_batch.py -v --tb=short
```

Expected: PASS（若环境缺依赖，至少保证本计划新增用例 PASS）

- [ ] **Step 2: 确认日批入口仍可写**

抽查 `backend_core/strategies/gms/scheduled_precompute.py` 仍以可写方式调用选股（`trace_only=False` 或等价），无需改行为。

---

## Spec coverage（自检）

| Spec 要求 | Task |
|-----------|------|
| 用户站强制只读 / 忽略 `trace_only=false` | Task 2 |
| `need_precompute` / `computed_count=0` | Task 1–2 |
| 用户路径不 save_snapshot | Task 2 |
| 前端去二次全量 + 提示 | Task 3 |
| 日批仍可写 | Task 5 抽查；不改 scheduled_precompute |
| 需求文档 | Task 4 |
| 小池一并只读 | Task 2（整路由强制，含小池） |
