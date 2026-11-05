# 管理端 URT / CSB / RPE 预计算信号查询 — 设计说明

**日期：** 2026-11-05  
**状态：** 已批准（2026-11-05 用户确认书面 spec）；实现完成，待人工点验三页管理端 Tab  
**范围：** 管理端 URT、CSB、RPE 三策略内嵌「信号结果」查询；不改日终预计算规则与信号口径

---

## 1. 背景与目标

日终定时已将 GMS / URT / SBBR / RPE / CSB 等策略信号写入各 `*_signal_trace`。形态类（DBLB/KGT/BVF/LDS/CUPB）管理端已有「信号结果」Tab；URT/CSB 管理端偏运维与回测，**几乎不能按日浏览触发信号**；RPE 已有 `GET /api/admin/rpe/selection-results`，**无对应 UI**。

### 成功标准

| 项 | 要求 |
|----|------|
| 可查 | 管理员在 URT / CSB / RPE 管理页可按交易日查看当日**触发**信号列表 |
| 轻量核对 | 列表上方可见：触发条数、该查询范围内最后写入时间 |
| 口径 | 与现有选股/日终「买点/入场」语义一致（见 §4），不新造触发定义 |
| 体验 | 交互对齐形态类「信号结果」Tab（日期 + 配置 + 查询 + 表格），**本期无导出、无行跳转** |

### 非目标（本期不做）

- GMS / SBBR 管理端改造（已有间接查询路径）
- 形态类日终定时、ZHAB 管理页
- 统一「全策略信号总览」页
- CSV/Excel 导出、细粒度只读权限、采集流程深链状态机
- 展示全量未触发扫描行（含调试开关）
- 点行进入个股详情

---

## 2. 用户与场景

- **主用户：** 策略运营 — 打开某策略管理页 →「信号结果」→ 看「今天/指定日」出了哪些点。
- **辅目标：** 用条数与最后写入时间粗判「可能没跑完」vs「跑了但零触发」；不替代采集流程运维看板。

---

## 3. 方案选择

| 方案 | 内容 | 结论 |
|------|------|------|
| A. 各策略页内嵌「信号结果」Tab | 对齐 DBLB 等形态类 | **采用** |
| B. 新建统一信号查询页 | 跨策略总览 | 不做（可后续） |
| C. 仅挂在预计算对话框旁 | 塞进运维弹窗 | 拒绝：不符合运营主场景 |

实现上：

- **URT / CSB：** 页面已用 `StrategyOpsShell`；在 shell 的 `el-tabs` slot 中新增「信号结果」pane（与策略参数/回测并列）。
- **RPE：** 在 `RPEManagementView` 现有 tabs 中新增「信号结果」。

---

## 4. 触发信号口径（只展示触发行）

| 策略 | 表 | 触发条件 | 排序键 |
|------|-----|----------|--------|
| URT | `urt_signal_trace` | `buy_signal = true`，且排除扫描占位码 | `score` 降序 |
| CSB | `csb_signal_trace` | `entry_signal = true`，排除 `SCANNED` / 占位码 | `score` 降序 |
| RPE | `rpe_signal_trace` | `entry_only=true`（`entry_signal`） | 沿用现有 selection-results 排序；若无强度则按代码 |

复用已有查询能力优先：

- URT：`backend_core.strategies.urt.trace_store.query_buy_signals_for_date`（需扩展分页/市场/汇总元数据若不足）
- CSB：`backend_core.strategies.csb.trace_store.query_buy_signals_for_date(..., entry_only=True)`
- RPE：`GET /api/admin/rpe/selection-results` + `entry_only=true`；不足再补 query 参数（分页、`last_written_at` 等）

---

## 5. 查询 UX 与默认值

| 控件 | 行为 |
|------|------|
| 交易日 | 默认**最新交易日**（按该策略/市场行情日历解析，与预计算 `resolve_*_trade_date` 一致）；可切日 |
| 参数版本 | 默认 **precompute_enabled / 默认启用版本**；下拉可切其他历史版本 |
| 市场 | **URT：** CN / HK 切换（同表按代码市场过滤，与预计算 market 一致）。**CSB / RPE：** 本期仅 CN（RPE API 已 `scope=cn`）；不做港股壳 |
| 查询 | 显式「查询」按钮；进入 Tab 时用默认条件自动查一次 |
| 顶栏元信息 | `触发条数` + `最后写入时间`（`max(created_at/updated_at)`，字段以各表为准） |
| 分页 | 服务端分页；建议默认 `page_size=50`（上限与形态类类似，≤2000） |
| 行点击 | 无跳转 |
| 导出 | **不提供**（形态类有导出，本期刻意不加） |

### 空态文案

1. 该配置 + 交易日（+ 市场）下 **存在任意 trace（含占位/扫描标记）但触发条数为 0** → 「当日无触发信号」。
2. **完全无任何相关 trace** → 「当日可能尚未预计算或无扫描记录；若任务异常请到采集流程核对」。
3. 若实现上无法廉价区分 (1)(2)，统一：「当日无触发信号；若任务异常请到采集流程核对」。

---

## 6. API 设计

### 6.1 共同响应骨架

列表接口建议返回：

```json
{
  "items": [ /* 策略语义字段，见 §7 */ ],
  "total": 0,
  "trade_date": "YYYY-MM-DD",
  "config_id": 1,
  "last_written_at": "ISO-8601 或 null",
  "has_any_trace": true
}
```

`has_any_trace` 用于空态区分；若某策略难以实现可省略并走统一文案。

### 6.2 URT

- **新增** `GET /api/admin/urt/signals`
- Query：`trade_date`（必填）、`config_id`（可选，缺省=有效预计算版本）、`market`（`CN`|`HK`，默认 `CN`）、`code`（可选）、`limit`、`offset`
- 鉴权：与现有 URT admin 相同
- 实现：基于 `query_buy_signals_for_date` + count/分页 + `last_written_at` / `has_any_trace`

### 6.3 CSB

- **新增** `GET /api/admin/csb/signals`
- Query：同 URT（无 `market`，或固定 CN）
- 实现：基于 `query_buy_signals_for_date(..., entry_only=True)` + 分页与元数据

### 6.4 RPE

- **优先复用** `GET /api/admin/rpe/selection-results`
- 管理端调用时固定 `entry_only=true`
- 若缺分页 / `total` / `last_written_at` / 默认 config：在该接口上**最小补参**，避免平行再造一套 `/signals`；仅当补参会破坏现有调用方时，才新增 `/signals` 并让 UI 走新接口

---

## 7. 表格列

**共同骨架：** 交易日、代码、名称、信号类型/方向（策略无则省略）、关键价位或分数、配置版本 id（或名称）、写入时间。

**策略语义列（对齐用户端/选股已有含义，不全量 dump JSON）：**

| 策略 | 建议列（可微调，以实现时对照 frontend screening 为准） |
|------|--------------------------------------------------------|
| URT | score、signal_strength、close、ma20、volume_multiple / volume_ratio、yang_rule |
| CSB | signal_type、score、close_price、channel_lower/upper、squeeze_days、entry_low |
| RPE | signal_type、z_score、ratio、sector_name、close_price、nearest_support / nearest_resistance |

---

## 8. 前端落点

| 文件/组件 | 改动 |
|-----------|------|
| `admin/src/views/UrtManagementView.vue` | 增加「信号结果」tab + 面板 |
| `admin/src/views/CsbManagementView.vue` | 同上 |
| `admin/src/views/RPEManagementView.vue` | 同上；subtitle 可改为含「信号结果」 |
| `admin/src/services/urtApi.ts` / `csbApi.ts` / `rpeApi.ts` | 封装 listSignals / 补全 selection-results 参数 |
| 可选共用 | 抽 `StrategySignalResultsPanel.vue`（日期/配置/分页/空态），策略列通过 slots 或 column 配置注入；若三页复制成本低也可先各写一份再抽 |

权限：能进入该策略管理页即可查；不新增角色。

---

## 9. 测试

- **后端（`./test`）：** URT/CSB 新 `/signals`：有触发行、仅扫描无触发、完全无数据、分页、默认 config、URT market 过滤；RPE：`entry_only` 与补参行为回归。
- **前端：** 手工验收三页 Tab：默认日/默认配置自动查询、切日切版本、空态文案、顶栏条数与时间、无导出按钮。

---

## 10. 风险与约束

- URT CN/HK 共表，市场过滤依赖代码规范；过滤错误会导致串市场，测试需覆盖。
- 日终「只写命中行」与「含占位/扫描标记」因策略而异；空态区分以表内真实数据为准，不强行对接采集流程 API。
- 不修改预计算写入逻辑；只读查询。

---

## 11. 批准记录

- 2026-11-05：grill Q1–Q16 全部采纳并口头确认共享理解。
- 2026-11-05：书面 spec 已确认；实现计划见 `docs/superpowers/plans/2026-11-05-admin-urt-csb-rpe-signal-query.md`。
