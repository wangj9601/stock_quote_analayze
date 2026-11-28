# GMS 周线版实现设计

> 状态：已评审锁定（grill Q1–Q19）；**实现前文档**  
> 业务规则：`GMS_WEEKLY_BUSINESS_RULES.md`  
> 日线对照：`GMS_STRATEGY_IMPLEMENTATION_DESIGN.md`

---

## 1. 设计原则

1. **同一业务逻辑，换周期输入**：打分、信号、减分、KDE 结构位复用日线实现；差异收敛在数据源、默认窗口参数、`timeframe` 分支。  
2. **以周 K 为真相**：周频 MF 必须由 `weekly_quotes` 重算，禁止日频 MF 按周抽样。  
3. **存储隔离**：周频 MF、周 trace 独立表，避免改日线大表主键。  
4. **先选股闭环，后交易/回测**：第一期不做到交易观察、正式交易、周线回测。  
5. **Schema 变更走 Alembic**：`migrations/` 若保留手写脚本须与 `alembic/versions/` 同步。

---

## 2. 目标架构

```
weekly_quotes (CN, W-FRI)
        │
        ▼
weekly_mf_cn  →  mean_frequency_resonance_indicators_weekly
        │
        ▼
gms_signals_weekly_cn
        │  GMSDataLoader(timeframe=weekly)
        │  → Calculator / SignalDetector / structure / observation_range
        │  → 地板分过滤 + 未达标删旧行
        ▼
gms_signal_trace_weekly
        │
        ▼
/api/screening/gms-strategy?timeframe=weekly  (trace_only)
        │
        ▼
screening GMS 面板「日线 | 周线」切换
```

日线路径保持现网不变（仅预计算默认地板 50→30 与未达标删除语义对齐业务规则 §5）。

---

## 3. 数据模型

### 3.1 `mean_frequency_resonance_indicators_weekly`

- 列集合与 `mean_frequency_resonance_indicators` **对齐**（含 `ma60_d`、`bias`、`d1`/`d20` 及日期等）。  
- 主键建议：`(code, date, market_type)`，`date` = 周周五标签。  
- 第一期 `market_type` 仅写 `CN`。  
- `ma20_d` / `mavol20_m`：基于 **20 根周 K**。  
- `ma60_d`：按周线策略默认写入 **12 根周收盘均线**（语义位仍名 ma60，文档与 UI 注明「周线 12」）；计算可在周 MF 批算中完成，或独立 enrich（实现时二选一，优先与日线「MF 内带 ma60_d」消费方式一致）。

### 3.2 `gms_signal_trace_weekly`

- 列集合与 `gms_signal_trace` **对齐**（含 `config_id`、分数明细、买卖标记、`score_detail` 等既有字段）。  
- 主键：`(code, date, market_type, config_id)`，`date` = 信号周周五。  
- **不**把 `timeframe` 塞进日线 `gms_signal_trace`。

### 3.3 配置表

- 表：`gms_strategy_configs`（现表）。  
- 增加 `timeframe`（`daily` | `weekly`，默认 `daily`）或等价唯一命名约定（如 canonical `default_weekly`）；**推荐显式列 + 唯一约束 `(name, timeframe)` 或 name 全局唯一且 weekly 用独立 name**。  
- 实现选定一种并在迁移中写清；周线 canonical 快照写入 §业务规则表内默认窗口数字。  
- `precompute_min_score` 默认 **30**（日线/周线配置均如此）。

### 3.4 预计算运行记录

- 扩展现有 `gms_precompute_runs`（或并行 `gms_precompute_runs_weekly`）：需能区分 `timeframe=weekly`，供选股快路径判断「该周是否预计算成功」。  
- 推荐：现表加 `timeframe` 列（默认 `daily`）并纳入唯一/查询条件，避免两套 run 表逻辑分叉。

### 3.5 Alembic

- 凡新建表 / 加列 / 索引：必须同时有 `alembic/versions/` revision；`scripts/db_migrate.py upgrade` 可落地。

---

## 4. 模块改造要点

### 4.1 包结构（不新建 `gms_weekly` 包）

在 `backend_core/strategies/gms/` 内扩展：

| 模块 | 改动 |
|------|------|
| `data_loader.py` | `timeframe`：周线读周 MF + `weekly_quotes` bars |
| `observation_range.py` | 窗口按「根数」；数据源换周 K |
| `ma60_source.py` / 等价 | 周线 12 周均线；勿误用日线 `ma_indicators.ma60` |
| `structure_levels.py` | lookback 用周线配置；bars 为周 K |
| `board_resonance.py` | weekly 路径 **跳过**（返回空/禁用） |
| `config.py` | `get_default_config(timeframe=...)`；周线默认覆盖 |
| `frontend_interface.py` | trace 表路由；地板默认 30；未达标删除 |
| `scheduled_precompute.py` | 解析「最新已收盘周」；写周 trace |
| `strategy_engine.py` / `signal_detector.py` / `scoring/*` | 尽量无周期分支；靠输入与 config |

### 4.2 周频 MF 批算

- 新模块建议：`backend_core/data_collectors/batch_mean_frequency_weekly.py`（或扩展现有 batch 并强制 `source=weekly_quotes`）。  
- 输入：`weekly_quotes`；输出：周 MF 表。  
- 复用日线 PVFRS 计算公式与字段含义，迭代单位改为周 bar。

### 4.3 已收盘周解析（Q20=A）

```text
closed(F, as_of) := 不存在 A 股交易日 T 满足 as_of < T <= F

resolve_gms_week_end(as_of) -> Friday date F
  在候选周标签（来自 weekly_quotes 或 W-FRI 序列）中
  取满足 closed(F, as_of) 的最大 F
```

交易日来源（实现优先级）：

1. 市场交易日历表（若项目已有可靠 CN 日历）；否则  
2. `historical_quotes` 全市场（或指数）去重 `date` 作为交易日集合。

注意：`F` 本身可以不是交易日（周五休市）；判定看的是区间 `(as_of, F]` 内是否还有交易日，而不是 `as_of >= F`。

预计算任务的「信号日」= 该 `F`；选股默认日期同理。

### 4.4 入库地板与删除

统一入口（日线已有，改为默认 30 并补删除）：

1. `resolve_gms_trace_storage_min_score` 默认 **30.0**。  
2. upsert 前过滤 `score_total >= floor`。  
3. 同一作用域本轮未通过地板的 code：`DELETE` 对应 trace 行。  
4. 周线对 `gms_signal_trace_weekly` 执行相同策略。

### 4.5 工作流节点

在 `node_registry.py`（及执行器）注册：

| node_id | 依赖 | 职责 |
|---------|------|------|
| `cn_weekly` | （现有） | 生成/更新 `weekly_quotes` |
| `weekly_mf_cn` | `cn_weekly` | 写周 MF |
| `gms_signals_weekly_cn` | `weekly_mf_cn` | 最新已收盘周 GMS 预计算 |

挂入「A股收盘后标准流程」：`migrations/add_gms_weekly_workflow_nodes.py`（`cn_weekly` 之后依次插入；`on_failure=continue`）。  
失败策略：周线节点默认 continue，避免阻断后续月 K / 日线 GMS。

### 4.6 API

- `GET /api/screening/gms-strategy` 增加查询参数 `timeframe=daily|weekly`（默认 `daily`）。  
- 其它前端 GMS 摘要/trace 查询若暴露给用户站，同步支持 `timeframe`，读对应表。  
- 管理端强制重算：第一期至少支持周线 CN 触发（可与日线任务入口并列或加参数）。

### 4.7 前端

- `frontend/partials/screening/gms.html` + `screening.js`：日线/周线切换，请求带 `timeframe`。  
- 日期选择器：周线模式下展示/约束为周五或「信号周」文案，避免用户误以为是任意交易日 bar。

---

## 5. 回填与运维脚本

建议 `scripts/` 或 `test/` 旁运维入口（实现时定名）：

1. **周 MF 回填**：按 code 列表或全市场，默认近 **5 年**周 K → 周 MF。  
2. **周 GMS 预计算回填**：近 **52** 个已收盘周 × 周线 canonical `config_id`。  
3. **日线地板变更后可选清理**：对历史 `score_total < 30` 的日线 trace 可批删（与日常重算删除语义一致；若全量重算成本高，提供一次性 SQL/脚本）。

参数均需可配置（N 年、M 周、市场、config_id）。

---

## 6. 测试计划（实现阶段）

| 用例 | 期望 |
|------|------|
| 周中 `as_of=周三` | 信号周为上一已收盘周五，不写当周未完成 bar |
| `as_of=周五`（该周有行情） | 可用该周五标签周 |
| 周五休市、`as_of=周四`（本周最后交易日） | 该周 `F` 视为已收盘，可用 |
| 同一公式样例股 | 手算/对照：20 根周 MA 与 MF 字段一致 |
| 地板 | 29.9 不入库且删旧行；30.0 入库 |
| 日线回归 | 默认地板 30；选股/预计算路径单测更新 |
| UI | `timeframe=weekly` 只读周 trace，不混日线结果 |
| 板共振 | weekly 路径无板共振扣分/强制字段 |

测试文件放在 `./test` 目录。

---

## 7. 明确非目标（防范围爬升）

- `gms_weekly` 独立策略包复制  
- 日表加 period 主键大迁移  
- 周线板共振、回测、交易观察/正式交易  
- HK `hk_weekly_quotes` / ETF 周线 GMS  
- 用日频 MF「每周五一行」冒充周指标  

---

## 8. 实现顺序建议

1. Alembic：周 MF 表、周 trace 表、configs/precompute_runs 的 timeframe（或 name）支持；默认地板配置。  
2. 周 MF 批算 + 工作流节点 `weekly_mf_cn`。  
3. GMS loader/engine/precompute 的 `timeframe=weekly` + 已收盘周解析。  
4. 日线+周线地板 30 + 未达标删除。  
5. Screening API + 前端切换。  
6. 回填脚本 + `./test` 用例。  
7. 文档交叉链接回日线设计文档「扩展：周线」。

**未获「文档确认 / 可以开工」前，不提交上述代码实现。**

---

## 9. 风险与注意事项

| 风险 | 缓解 |
|------|------|
| `W-FRI` 在周中生成会留下不完整周五行 | 策略层用交易日完备 `closed(F,as_of)`；预计算只用已收盘周 |
| 周五休市 | 不要求 `as_of >= F`；周四 EOD 即可确认该周 |
| MA20=20 周 vs 观察期=4 周量级差大 | 已在业务规则拆分 MF 窗口与策略窗口；UI/说明勿混称 |
| ma60 字段名表示 12 周 | 配置与文档写清；避免误读日线 ma_indicators |
| 删 trace 影响审计 | 仅删未达地板行；预计算 run 日志保留成功/跳过统计 |
| 工作流未串依赖 | 节点 registry + 编排清单双检 |
