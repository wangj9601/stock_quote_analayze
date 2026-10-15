# CSB 预计算性能加速 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 区间预计算评点改为「一次算 MA/粘合、按日复用」，在信号口径与现网 `evaluate_one` 金标一致的前提下，使区间补算墙钟时间 ≥3×。

**Architecture:** 在 `channel.py` 增加可复用的序列级通道辅助；在 `strategy_engine.py` 增加 `evaluate_range`，让 `_hits_for_stock_dates` 默认走新路径（`CSB_EVAL_RANGE=0` 可回退）。Phase B 用环境变量切换进程池。

**Tech Stack:** Python 3、现有 CSB 模块、pytest

**Spec:** `docs/superpowers/specs/2026-10-15-csb-precompute-perf-design.md`

## Global Constraints

- 不得更改 CSB 买卖/评分业务规则口径；差异只允许来自性能路径实现错误并必须修复到与金标一致
- 默认开启新评点路径；`CSB_EVAL_RANGE=0` 必须能回退旧循环
- 测试放在 `./test` 目录
- 提交信息简洁说明 why；未要求则不主动 commit

## Review Focus

- 目标日不在 `bars` 内：应跳过，不抛异常
- `bars` 长度 &lt; `min_listing_bars`：该日无行，与 `evaluate_one` 一致
- 多日中仅部分日有买点：过滤后列表与旧逻辑一致
- `require_entry=False` 时 SETUP 等非入场行是否仍按旧逻辑保留（若旧逻辑保留则新逻辑必须一致）
- 空 `dates` / 空 `bars`：返回 `[]`

---

### Task 1: 通道序列辅助（可复用 mas / squeeze）

**Files:**
- Modify: `backend_core/strategies/csb/channel.py`
- Test: `test/test_csb_channel_series.py`

**Interfaces:**
- Produces:
  - `build_channel_series(bars, config) -> dict` 至少含 `closes`, `mas`, 以及按日可用的通道字段访问方式
  - `channel_state_at(series, index, config) -> dict` 语义对齐 `compute_channel_state(bars[:index+1], config)` 的关键字段（`lower/upper/squeeze_pct/squeeze_days/squeeze_ok/...`）

- [ ] **Step 1: Write the failing test**

```python
def test_channel_state_at_matches_compute_channel_state_on_prefixes():
    # 构造 ≥60 根合成 K 线；多取几个 end index
    # assert channel_state_at(series, i, cfg) 关键字段 == compute_channel_state(bars[: i + 1], cfg)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test/test_csb_channel_series.py -v`  
Expected: FAIL（符号未定义或行为不符）

- [ ] **Step 3: Implement series helpers in `channel.py`**

一次 `compute_mas`；`squeeze_days` 由预计算的每日 `squeeze_pct` 从 `i` 向前计数，结果与 `count_squeeze_days(bars[:i+1], ...)` 一致。

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test/test_csb_channel_series.py -v`  
Expected: PASS

---

### Task 2: `evaluate_range` + 金标对比

**Files:**
- Modify: `backend_core/strategies/csb/strategy_engine.py`
- Test: `test/test_csb_evaluate_range.py`

**Interfaces:**
- Consumes: Task 1 的 `build_channel_series` / `channel_state_at`（若 setup 需注入通道，在本任务接线）
- Produces:
  - `evaluate_range(bars, dates, *, code="", name="", config=None) -> List[Dict]`
  - 对每个存在于 bars 的目标日，输出行与 `evaluate_one(bars[:end_i+1], code=..., name=..., trade_date=d, config=...)` 金标字段一致

- [ ] **Step 1: Write the failing gold-standard test**

```python
def test_evaluate_range_matches_evaluate_one_per_day():
    # 合成或 fixture bars；dates 含有信号日与无信号日
    # legacy = [evaluate_one(...) for d in dates if d in bars]
    # assert compare_rows(evaluate_range(...), legacy)
```

对比字段：`signal_type`, `entry_signal`, `setup_ok`, `score`, `channel_lower`, `channel_upper`, `squeeze_days`。

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test/test_csb_evaluate_range.py::test_evaluate_range_matches_evaluate_one_per_day -v`  
Expected: FAIL

- [ ] **Step 3: Implement `evaluate_range`**

优先：共享 MA/通道序列后，按日调用与 `evaluate_one` 相同的 entry/score 组装；若需轻改 `detect_setup` 以注入通道状态，保持对外字段不变。

- [ ] **Step 4: Run gold + edge tests**

Run: `pytest test/test_csb_evaluate_range.py -v`  
Expected: PASS（含空 dates、缺日、不足 bars）

---

### Task 3: 接入 `_hits_for_stock_dates` + 开关 + 日志

**Files:**
- Modify: `backend_core/strategies/csb/strategy_engine.py`
- Test: `test/test_csb_evaluate_range.py`（或新建 `test/test_csb_hits_for_stock_dates.py`）

**Interfaces:**
- Consumes: `evaluate_range`
- Produces: `_hits_for_stock_dates` 默认用 range；`CSB_EVAL_RANGE` 在 `0/false/off` 时走旧循环；过滤语义不变

- [ ] **Step 1: Write failing test for switch + filter parity**

```python
def test_hits_for_stock_dates_range_matches_legacy_filter():
    # 同一 bars/dates/cfg；强制新旧两路径（可 mock env 或抽 _hits_legacy）
    # require_entry=True 时两边列表一致
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test/test_csb_evaluate_range.py -k hits_for_stock -v`  
Expected: FAIL

- [ ] **Step 3: Wire `_hits_for_stock_dates` + env switch + optional timing log in `screen_universe_for_dates` chunk loop**

日志保持现有进度文案；可额外 debug/info 输出 `eval_ms`（避免刷屏则按 chunk 聚合）。

- [ ] **Step 4: Run related CSB tests**

Run: `pytest test/test_csb_evaluate_range.py test/test_csb_frontend_screen.py test/test_csb_core.py -q`  
Expected: PASS

---

### Task 4: 文档与手册一句更新

**Files:**
- Modify: `docs/strategies/csb/CSB_通道突破_操作使用手册.md`（FAQ 性能相关）
- Modify: `docs/superpowers/specs/2026-10-15-csb-precompute-perf-design.md`（勾选验收项若已完成）

- [ ] **Step 1: 补充 FAQ：区间预计算走一次扫描+增量评点；`CSB_EVAL_RANGE` /（Phase B）`CSB_SCREEN_POOL` 说明**
- [ ] **Step 2: 目视确认无过时「将自动全市场现算」冲突表述**

---

### Task 5 (Optional Phase B): 进程池

**Files:**
- Modify: `backend_core/strategies/csb/strategy_engine.py`
- Test: `test/test_csb_screen_pool.py`

**Interfaces:**
- Produces: `_screen_pool_mode() -> "thread"|"process"`；`screen` / `screen_universe_for_dates` 的 map 阶段可切换；子进程入参仅为可 pickle 的 `(code, name, hist, dates, cfg)`

- [ ] **Step 1: Write test that process pool results match thread for a tiny in-memory jobs list**（可对 `_run_job` 级函数测）
- [ ] **Step 2: Implement pool switch**
- [ ] **Step 3: Document env in 操作手册**
- [ ] **Step 4: Run `pytest test/test_csb_screen_pool.py test/test_csb_evaluate_range.py -q`**

---

## Self-review notes

- Spec Phase A → Tasks 1–4；Phase B → Task 5
- Review Focus 五项均落在 Task 2/3 测试
- 不在计划中展开 `detect_entry` 算法正文；以金标约束实现

## Execution

推荐 **Native（本会话直接按任务实现）**：任务接口强依赖、金标对比需紧密迭代；Phase B 可留到 A 验收后再开。
