# CSB 预计算性能加速 — 设计说明

**日期：** 2026-10-15  
**状态：** 已批准（聊天设计确认；按 Phase A→B 落地）  
**范围：** 预计算 / 区间补算评点路径；不改信号业务规则

---

## 1. 背景与目标

全市场区间预计算（及回测「优先读缓存」时的自动补算）日志形态为：

`区间一次扫描 done/5453 只（N 个交易日）`

当前实现对每只股票、每个目标交易日调用一次 `evaluate_one`：每次都会在 `compute_channel_state` / `count_squeeze_days` 内**重新计算整段 MA 序列**，区间越长 CPU 浪费越明显。

### 成功标准

| 项 | 要求 |
|----|------|
| 信号口径 | 与现网 `evaluate_one` **金标一致**（同输入同 `signal_type` / `entry_signal` / `score`，关键字段一致） |
| 性能 | 区间补算墙钟时间相对改造前 **≥3×**（理想 5×+）；样本：约 200 只×20 日可回归，全市场×约 59 日可对比 |
| 兼容 | `screen_universe_for_dates`、日终单日 `screen()`、回测补算入口行为不变 |
| 回归 | 日终单日预计算不显著变慢 |

### 非目标（本轮不做）

- 修改 CSB 买卖/评分规则
- 降低 `history_bars` 换速度
- 行情宽表 / 新存储层
- 分布式多机扫描

---

## 2. 方案选择

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| **Phase A** | 区间增量评点：`evaluate_range`，MA/粘合序列一次计算、按日复用 | 必做 |
| **Phase B** | 可选进程池：`CSB_SCREEN_POOL=process` + worker 调参 | Phase A 验收后按需 |

---

## 3. Phase A 设计

### 3.1 核心思路

在 `_hits_for_stock_dates` 路径上：

1. 对正序 `hist_asc` **只算一次** `compute_mas(closes)`。
2. 由 MA 序列预生成每日 `squeeze_pct`（及可选 squeeze 连续天数前缀），避免每个目标日 `count_squeeze_days` 再算一遍 MA。
3. 对每个目标日 `d`，仍用 `bars[:end_i+1]` 跑与现网等价的 setup / entry / score，但**通道状态从预计算序列取值**（或通过可注入 `mas` 的通道 API）。
4. 过滤逻辑（`require_entry`、`min_score`）保持与现网 `_hits_for_stock_dates` 相同。

对外推荐 API：

```text
evaluate_range(
  bars: List[dict],
  dates: List[str],
  *,
  code: str = "",
  name: str = "",
  config: Optional[dict] = None,
) -> List[dict]
```

- 返回：与多次 `evaluate_one` 在对应日得到的行列表（未做 entry/score 过滤；过滤仍在 `_hits_for_stock_dates`）。
- 单日场景：`evaluate_one` 可继续独立实现，或内部委托 `evaluate_range(..., dates=[td])[0]`（以实现时金标不漂为准）。

### 3.2 建议改动文件

| 文件 | 职责 |
|------|------|
| `backend_core/strategies/csb/channel.py` | 支持「预计算 mas / squeeze 序列」的通道状态查询，避免重复 `compute_mas` |
| `backend_core/strategies/csb/strategy_engine.py` | 新增 `evaluate_range`；`_hits_for_stock_dates` 改走 range；可选计时日志 |
| `backend_core/strategies/csb/setup_detector.py`（若需要） | `detect_setup` / 通道调用点允许注入预计算通道状态 |
| `test/test_csb_evaluate_range.py`（新建） | 金标对比 + 小样本计时 sanity |

尽量少改 `entry_detector.py` 规则本身；优先在通道与引擎层复用。

### 3.3 正确性策略

1. **金标测试（强制）**  
   用同一 `bars`、同一 `config`、同一 `dates`：  
   `evaluate_range` 结果 vs 循环 `evaluate_one(bars[:end+1], trade_date=d)`  
   对比字段至少：`signal_type`, `entry_signal`, `setup_ok`, `score`, `channel_lower`, `channel_upper`, `squeeze_days`。

2. **特性开关（建议）**  
   环境变量 `CSB_EVAL_RANGE=0` 可回退旧循环，便于线上止血（默认开启新路径）。

3. **可观测性**  
   区间扫描日志增加粗粒度耗时：`fetch_ms` / `eval_ms`（或等价字段），便于验收 3×。

### 3.4 风险与缓解

| 风险 | 缓解 |
|------|------|
| 通道/回踩边界与旧实现差 1 根 K | 金标全字段对比；发现差异先修 range，不改业务口径 |
| 预计算序列与截断 bars 不一致 | 严格用同一 `hist_asc` 下标 `end_i` |
| 单日路径变慢 | 单日仍可走原 `evaluate_one`；range 仅多日路径启用 |

---

## 4. Phase B 设计（可选）

- 新增 `CSB_SCREEN_POOL=thread|process`（默认 `thread`）。
- `process` 时用 `ProcessPoolExecutor`，`CSB_SCREEN_WORKERS` 上限可酌情放到 8～16（受内存与 DB 连接约束）。
- 子进程只做纯评点（已拉好的 `hist` + `cfg`），避免在子进程持有 ORM Session。
- 验收：全市场单日或短区间，CPU 利用率明显上升且结果与 thread 金标一致。

---

## 5. 验收清单

- [x] 金标单测通过（多日、含无信号日、不足 bars、边界日）
- [x] `_hits_for_stock_dates` / `screen_universe_for_dates` 走新路径
- [x] `CSB_EVAL_RANGE=0` 回退可用
- [x] 样本计时达到 ≥3×（记录改造前后数字：60 日合成样本 `_hits_for_stock_dates` legacy 2689ms → range 389ms ≈ **6.9×**）
- [x] 现有相关 `test/test_csb_*.py` 全绿（41 passed）
- [ ] （可选）Phase B 开关与金标 — 未做，视生产墙钟再开

---

## 6. 实现顺序

1. 通道层可复用 mas / squeeze 序列  
2. `evaluate_range` + 金标测试  
3. 接入 `_hits_for_stock_dates` + 开关 + 日志  
4. 文档一句更新（操作手册 FAQ 性能条）  
5. Phase B 按需  

---

## 7. 已确认决策

- 采用 **先 A 后 B**  
- 性能门槛 **≥3×**（无更硬的绝对时长 SLA）  
- 口径 **零漂移**（金标一致优先于极限优化）
