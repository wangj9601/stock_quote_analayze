# GMS 用户选股只读预计算（trace-only）设计

**日期**: 2026-11-24  
**状态**: 已评审（对话确认方案 B；小池一并只读）  
**范围**: 第一期仅 GMS 用户选股路径  

## 1. 背景与目标

架构评审要求逐步做到「Core 预计算写库、API 尽量只读」。GMS 已具备：

- 表：`gms_signal_trace`
- 日批：`backend_core/strategies/gms/scheduled_precompute.py` + workflow 适配
- API/Core：`trace_only` 与前端「先只读、再按需全量」二次请求

问题：用户站在 `trace_complete !== true` 或命中率低时会再发**无** `trace_only` 的请求，在 HTTP 路径触发缺失现算回填，拖垮 API（超时/502）。

**目标**：用户站 GMS 选股（含全市场与小池）默认且强制只读预计算结果；缺数据时给出明确业务态，**不再**在用户选股 HTTP 路径现算回填。

**非目标（第一期）**：URT/其它策略、Redis/Celery、调度进程归属改造、双 ORM `Base` 合并。

## 2. 行为契约

### 2.1 用户站选股 API

入口：`GET /api/screening/gms-strategy`（`backend_api/stock/stock_screening_routes.py`）。

对**所有**用户选股 scope（含但不限于 `cn` / `hk` / `etf` / `all`、自选 `watchlist`、`gms_watchlist`、行业/概念板块、单股 `code=`）：

| 规则 | 说明 |
|------|------|
| 强制只读 | 内部一律按 `trace_only=True` 调用 Core；查询参数 `trace_only=false` **不生效** |
| 不现算回填 | `computed_count` 恒为 0；不因缺行调用策略引擎增量/全量计算并写 `gms_signal_trace` |
| Snapshot | 可继续作为只读加速层；miss 后只读 trace；**用户只读路径 miss 后不** `save_snapshot` |
| 缺预计算 | HTTP 200 + 空或已有行；`gms_trace_meta.need_precompute=true`（或等价）、`trace_complete=false` |

响应 `gms_trace_meta`（或合并后的等价字段）至少包含：

- `trace_only: true`
- `trace_complete` / `precompute_ok`
- `from_trace_count` / `computed_count`（后者为 0）
- `need_precompute`（无可用预计算或不足以展示完整结果时为 true）

### 2.2 仍允许写库 / 现算的路径

- Core 日批与采集 workflow：`scheduled_precompute` 等（`trace_only=False` 写 `gms_signal_trace`）
- 管理端既有「预计算 / 强制重算 / 追溯补算」入口（不经由用户站选股「放开 `trace_only=false`」）

用户选股 API **不**作为全市场或小池现算入口。

### 2.3 前端

文件：`frontend/js/screening.js` 中 `fetchGmsStrategyResult`。

- 只发只读请求（带 `trace_only=true`，或依赖 API 强制只读）
- **删除**二次无 `trace_only` 的全量请求
- 当 `need_precompute` 或 `trace_complete === false`：Toast/条提示「当日预计算未就绪，请稍后或联系管理端补算」，不自动重算

## 3. 实现落点

| 层 | 文件 | 改动要点 |
|----|------|----------|
| API | `backend_api/stock/stock_screening_routes.py` | `gms-strategy`：强制 `trace_only`；用户路径不因计算 miss 写 snapshot；文档字符串更新 |
| Core | `backend_core/strategies/gms/frontend_interface.py` | 模块/函数说明改为「用户选股只读；回填仅批处理/管理端写路径」；行为由 API 传入 `trace_only=True` 即可，日批调用保持可写 |
| 前端 | `frontend/js/screening.js` | 去掉二次全量；补 UX 提示 |
| 需求文档 | `docs/design/需求分析.md` | 「GMS 缺失时计算并回填」改为与本契约一致 |
| 测试 | `test/` | 见 §5 |

不新增表、不改 Alembic（沿用现有 `gms_signal_trace`）。

## 4. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 日批失败 → 选股空/提示 | 明确 `need_precompute`；运维用 core/管理端补算；禁止用户 API 回退现算 |
| 外部客户端依赖选股 API 现算 | 文档与参数行为写死只读；现算仅管理端/日批 |
| Snapshot 与 trace 不一致 | 用户路径只读；不在用户 miss 路径写 snapshot |
| 旧前端二次请求 | 删除回退逻辑；API 强制只读兜底 |

## 5. 验收标准

1. 用户站 GMS 选股（全市场与自选/观察股/板块/单股）单次请求内 `computed_count=0`，不触发策略引擎现算回填。  
2. 请求携带 `trace_only=false` 时，用户选股 API 行为仍只读。  
3. 无预计算时：业务成功 + `need_precompute=true`（或等价）；前端有提示且无自动二次全量。  
4. Core 日批 / workflow GMS 预计算仍能写入 `gms_signal_trace`。  
5. `docs/design/需求分析.md` 中相关「选股缺失回填」表述已更新。

## 6. 测试计划

- API：有 trace 数据时只读返回且 `computed_count=0`。  
- API：无 trace 时 `need_precompute`（或等价）为 true，且不调用现算写库。  
- API：显式 `trace_only=false` 仍只读。  
- 回归：既有 GMS scheduled precompute 相关测试不被削弱（可引用现有用例）。  
- 前端：若有自动化则断言不再发起第二次全量 URL；否则手工验收选股页。

## 7. 决策记录

- 方案：**B**（前端去掉二次全量 + API 强制用户选股只读）  
- 小池（自选 / GMS 观察股 / 行业·概念 / 单股）：**一并只读**  
- 用户站不允许用 `trace_only=false` 打开现算  

## 8. 后续（不在本期）

- URT / RPE / CSB / SBBR 等同样收紧用户选股只读  
- 调度单一真相源、双 `Base` 收敛等架构项另开 spec  
