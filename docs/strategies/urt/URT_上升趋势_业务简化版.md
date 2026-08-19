# URT 上升趋势策略 — 最新业务规则

面向产品与业务的口径说明。**以当前代码实现为准**；公式细节与工程设计见 [URT_STRATEGY_IMPLEMENTATION_DESIGN.md](./URT_STRATEGY_IMPLEMENTATION_DESIGN.md)，回测买卖见 [URT策略交易回测说明.md](./URT策略交易回测说明.md)。

---

## 1. 策略定位与名称

| 项 | 说明 |
|----|------|
| 产品名 | **上升趋势**（选股页 Tab 文案） |
| 策略缩写 | **URT**（Upward Right-side Trend） |
| 一句话 | 找已**站上中期均线**、近期**连续收阳**、且当天**明显放量**的股票，等右侧「趋势确认」再考虑入场 |
| 不是什么 | 不是抄底；不做 GMS 式左侧均值吸附 |

主链路：日线 K 线现算指标 → 硬筛 → 百分制得分 → **结构硬闸（混合）** → **过热硬闸** → 正式买点；KDE 支撑/阻力、结构盈亏比与近期涨幅风险提示（RR 偏低 / 涨幅偏大为软标签）。

---

## 2. 数据来源 / Scope

选股 API：`GET /api/screening/urt-strategy`（`backend_api/stock/stock_screening_routes.py`）。  
前台入口：`frontend/screening.html`「上升趋势」Tab + `frontend/js/screening.js`。

| `scope` | 含义 | 股票池 |
|---------|------|--------|
| `cn`（默认；`all` 会归一成 `cn`） | 全部 A 股 | `stock_basic_info`，6 位码 |
| `hk` | 全部港股 | `stock_basic_info_hk`；行情表 `historical_quotes_hk` |
| `watchlist` | 我的自选 | 需登录；取当前用户自选代码；**空自选 = 空结果，禁止扫全市场** |
| `industry_board` | 行业板块 | `industry_board_constituents`，`industry_board_code` 可多选（并集） |
| `concept_board` | 概念板块 | `concept_board_constituents`，`concept_board_code` 可多选（并集） |
| `single` | 单只股票 | 按代码/名称解析；**仅支持 6 位 A 股**；跳过硬筛与最低得分，返回含未过筛的明细 |

**行情主源**：A 股 `historical_quotes`，港股 `historical_quotes_hk`（日线，日期 DESC 现算）。  
**基准日**：请求 `date`；若该日无数据则回退到表内最新交易日（`URTDataLoader.resolve_effective_history_end_date`）。

**行业/概念 + 龙头中军**：`scope` 为行业/概念时，可挂载 `role_tags`（`board_code_source` 默认同花顺），不参与 URT 硬筛/打分。

---

## 3. A 股板块筛选（代码段）

与选股页「A股板块（可多选）」一致，参数：`cn_board_segment`（优先）或旧参数 `boards`。

| 前端值 | 内部键 | 代码前缀（示意） |
|--------|--------|------------------|
| `MAIN` | `SH_MAIN` + `SZ_MAIN` | 600/601/602/603/605；000/001 |
| `CYB` | `CYB` | 300 |
| `SZ_SME` | `SZ_SME` | 002 |
| `KCB` | `KCB` | 688 |
| `BJ` | `BJ` | 43/83/87/88/92 |

规则（实现：`normalize_urt_board_keys` / `cn_listed_board_filter`）：

- **可多选**，多选为**并集**（OR）。
- **不选 / 空 / `ALL` = 不限板块**。
- 适用于 `cn`、以及行业/概念/自选池上的二次代码段过滤；`hk` 不适用该参数。

---

## 4. 候选池过滤

| 规则 | 口径 | 实现 |
|------|------|------|
| ST 剔除 | 名称 **包含** `ST`（`LIKE '%ST%'`）不进候选 | A/港股候选列表均剔除 |
| 采集开关 | `collect_enabled` 为 True 或 NULL 才进池 | 同上 |
| 港股混入 A 股 | 5 位数字码**禁止** `zfill(6)` 抬成 A 股 | `data_loader`、日报、缓存过滤 |
| A 股 URT 日报 | 仅用户自选中的 **CN / 6 位 A 股**；港股与 5 位码跳过 | `report_service._generate_urt_report_for_user` |

---

## 5. 核心指标与计算口径

实现：`backend_core/strategies/urt/indicators.py`。K 线 **index 0 = 基准日（最新）**。

| 指标 | 公式 / 规则 | 默认窗口 |
|------|-------------|----------|
| 阳线 | `close > open` | — |
| MA（站上） | 收盘价简单均线；要求 `close ≥ MA` | `ma_period=20` |
| 连阳规则 A | 近 N 日阳线数 ≥ M | 窗口 **4**，≥ **3** |
| 连阳规则 B | 近 N 日阳线数 ≥ M | 窗口 **5**，≥ **4** |
| 连阳硬筛 | **A 或 B 任一通过** | — |
| 量能倍数 | 当日成交量 ÷ 近 N 日均量（**均量不含当日**） | N=`volume_lookback=20`；阈值 **3.0** |
| 量比 | 当日量 ÷ 前一日量（近似） | 默认**不**硬筛、不参与加分 |
| 换手率 | 取当日 K 线 `turnover_rate`；另算近 **20** 日中位（不含当日） | 默认硬筛 ≥ **3.0%**；积分用**相对中位甜区加分 / 极端减分**（绝对 ≥25% 熔断），区间约 **[-8,+8]** |
| 中期阳线 | 默认 10 日≥6 / 15≥8 / 20≥10（须**全部**满足才算 ok） | 默认 `use_yang_medium=true` **硬筛** |
| 均线多头 | 硬筛默认 `MA5 > MA10 > MA20`；积分可看至 250 | 默认 `require_ma_bull=true` **硬筛仍仅短中期**；加长均线只抬排序分 |
| 均线空头 | `MA5 < MA10 < MA20` → `ma_bear_ok` | 不硬筛；减分 + 风险标签 |

频率：**日线、按交易日**；选股可指定基准日，指标一律相对该日及之前的历史。

拉历史日历跨度：至少 `history_calendar_days`（默认 120），并为 KDE 最大回看留余量（`history_calendar_days_for_fetch`）。

---

## 6. 入选 / 正式买点 / 得分 / 排序

### 6.1 正式买点

```text
买点 = 硬筛全部通过 AND 结构硬闸通过 AND 过热硬闸通过 AND 得分 ≥ min_score
```

**默认硬筛**：

1. 站上 MA20  
2. 连阳（4 日≥3 或 5 日≥4）  
3. 量能倍数 ≥ 阈值（默认 **3.0**）  
4. 中期阳线全过（默认开）  
5. 均线多头（默认开）  
6. 换手率 ≥ 3%（默认开）  

**结构硬闸（混合，默认开）**：KDE 有效时，**破位支撑 / 贴·超阻力 / 上行空间不足**（相对现价 &lt; 3%）/ **悬空离支撑**（相对支撑 ≥ 8%）否决正式买点；**RR 偏低仅软标签，不否决**。KDE 无效不硬闸。

**过热硬闸（默认开）**：近 10 日相对最低价涨幅 ≥ **25%**，或相对 MA20 乖离 ≥ **20%** → 否决；15%/15% 仅为风险提示。

**得分门槛**：默认 `min_score=70`。

选股全部A股/全部港股：`require_pass=True`，**只返回正式买点**。  
`scope=watchlist|industry_board|concept_board|single`：对齐 GMS，`skip_screening_filters=True`，返回可算明细（含未过筛/未达分），得分原样展示；**不等于**给出买点（看 `buy_signal`）。

### 6.2 得分分项（封顶 100）

实现：`backend_core/strategies/urt/scoring.py`。硬筛不变；**满分≠已贴近买点**。`min_score` 默认仍 70（可按历史信号抽样后再调）。

| 分项 | 上限（约） | 口径摘要 |
|------|------------|----------|
| MA20 趋势 | 10 | 站上后按乖离 + 近 5 日斜率梯度（`slope_bias`）；非静态 +10 |
| 连阳天数 | 20 | 原 40 档 ×(20/40) |
| K 线实体质量 | 10 | 近窗实体比 + 突破波幅 |
| 量能倍数 | 25 | 达硬筛阈值起分；`volume_score_full_multiple`（默认 **4.0**）拉满；内部 40 档再 ×25/40 |
| 中期阳线 | 5 | 各窗口相对阈值完成度等权平均 ×5 |
| 均线多头/空头 | **+0～8 / −8** | 硬筛仍 `MA5>MA10>MA20`；积分按 `5…250` **前缀链深度**分档（短多约 +3，全链 +8）；空头仍只看 5/10/20 → −8 |
| 筹码位置与 RR | 15 | 贴近支撑 0～8 + RR 0～7；KDE/RR 缺失中性偏低 |
| **换手率** | **+8 / −8** | `turnover_score_enabled`：相对自身近 20 日中位约 1～2× 满分；过高倍数或绝对 ≥25%/40% **减分**；中位不足时绝对 3%～7% 甜区回退 |
| 量比 | 最多 5 | 仅 `use_volume_ratio` 开启时加分 |
| 过热扣分 | −10～0 | 涨幅/乖离达软阈（15%）起扣，逼近硬阈扣满；硬闸仍独立 |

### 6.3 排序

- 选股引擎实时结果：按 **得分降序**（`URTStrategyEngine.screen_universe`）。  
- `urt_daily` 推送 Excel：先 **是否买点**，再按 **得分**（买点优先）。

### 6.4 「连阳补充收录」（仅日报）

选股列表默认**不**输出非买点。自选股日终 `urt_daily` 额外收录：

| | 正式买点 | 连阳补充 |
|--|----------|----------|
| 条件 | 硬筛全过且得分够 | 未买点，但 4 日阳≥3 **或** 5 日阳≥4 |
| 「是否买点」列 | 是 | 否 |
| 用途 | 可交易候选 | 观察池补充 |

回测**只按正式买点**入场（信号日次日开盘），不把连阳补充当买入信号。

---

## 7. 支撑 / 阻力与风险提示（混合硬闸 + 软标签）

- **KDE 筹码密度峰**支撑/阻力：与 RPE / 个股关键价位同口径（`signal_detector._compute_structure_levels` → `rpe.kde_levels`）。  
- 默认回看：初始 60、步进 250、最大 750；网格 200 等（配置 `kde_*`）。  
- **结构盈亏比**（无量纲）`RR = 上行 / max(价−支撑, 现价×1.5%, k×ATR)`，k 默认 **0.75**。打分/「RR 偏低」默认用**第二档**支撑阻力；**最近档只做硬闸**。展示同时给 RR、上行%、下行%、是否触分母下限。  
- **软标签**：结构 RR &lt; `structure_rr_min_rr`（默认 **2.0**；满分档 3.0）→「结构盈亏比偏低」warn；**不否决买点**。  
- **硬闸**（`structure_rr_hard_gate_enabled`，默认 true）：相对**最近**支撑/阻力判定破位、贴/超阻力、**上行空间不足**（距最近阻力 &lt; `structure_rr_min_upside_pct`，默认 **3%**）、悬空离支撑（默认 8%）→ 否决正式买点。  
- **趋势标签**：空头排列 → `bearish_ma_trend`；跌破 MA20 → `below_ma20`（warn）。  
- **近期涨幅过大**（`indicators.ret_from_low_n` / `ma20_bias`）：  
  - 口径：近 **N** 日（默认 10）相对窗内最低价涨幅 \(R_N=close/\min(close_{0..N-1})-1\)；另算相对 MA20 乖离。  
  - **软标签**：\(R_N\ge 15\%\) →「近期涨幅偏大」；乖离 \(\ge 15\%\) →「均线乖离偏大」（warn，不否决）。  
  - **过热扣分**：自软阈值起阶梯扣至约 −10（影响排序与 `min_score`）。  
  - **硬闸**（默认开）：\(R_N\ge 25\%\) 或 乖离 \(\ge 20\%\) → 否决正式买点（danger）。  
- **买点建议（选股明细固化）**：信号计算后写入 `trade_advice`（并进 `score_detail`），选股「明细」展示【买点建议】：  
  - 正式买点 + 现价贴近支撑 → 现价附近可跟，回踩支撑/MA20 不破可加；  
  - 正式买点但现价相对支撑偏远（≥3%）或存在过热**软**提示 → **回踩承接**；  
  - **短线可执行区**钉近端结构支撑一带；**止损**相对支撑下移约 **2%**，且须**严格低于**买入下沿（与个股分析形态买点 `invalidation` 钳制同口径）；  
  - 当 **MA20（或更深锚）低于止损**时：不写入买入下沿，降为 **中线更深回撤关注**（`deeper_watch` / `horizon.medium_term`），避免「买区盖住止损」死锁；  
  - 若行上已有个股形态 `tactical` / `buy_hints`（个股分析路径），软融合短/中线文案与失效旁证，**选股默认不强算全套形态**；  
  - 未达正式买点 → 仅观察；  
  - 明细徽章：动作 / 信心 / RR / 关键位单独高亮；表格区分短线承接与中线关注。  
  实现：`backend_core/analysis/trade_advice.py`（`urt`）+ `signal_detector.evaluate_bar`；前端 `urt_score_detail.js`。  
- 选股页「按前复权计算」：仅对列表重算 KDE 支撑/阻力，**不改**得分与买卖点。

说明：若最近支撑几乎贴着现价、最近阻力只高几毛（如 12.57 / 12.58 / 12.93），旧口径可能因风险分母下限出现「RR 偏低」软提示但仍买点=是；现已按**最小上行比例**硬否决，避免「涨一点就到阻力」的虚买点。

---

## 8. 参数可配置项与默认值来源

| 来源 | 说明 |
|------|------|
| 代码内置默认 | `URTConfigManager.get_default_config()` |
| JSON 文件 | `backend_core/strategies/urt/urt_config.json`（与内置 deep merge） |
| 数据库 | 表 `urt_strategy_configs`；有启用默认版本时**优先 DB**；管理端可多版本 / `precompute_enabled` |
| 选股 Query 覆盖 | `volume_multiple`、`min_score`：仅 **全部A股 / 全部港股** 覆盖并过滤买点；**自选/行业/概念/单股** 对齐 GMS：不按硬筛与最低得分过滤列表、得分原样返回（正式买点仍看 `buy_signal`）；有覆盖时全市场不走预计算缓存 |

### 8.1 常用默认（文件 + 代码一致部分）

| 键 | 默认 |
|----|------|
| `ma_period` | 20 |
| `yang_rule_a` / `yang_rule_b` | 4日≥3 / 5日≥4 |
| `volume_lookback` / `volume_multiple` | 20 / **3.0** |
| `volume_score_full_multiple` | **4.0** |
| `min_score` | 70 |
| `use_turnover` / `min_turnover` | **true / 3.0**（总开关；细项见下） |
| `turnover_hard_filter` / `turnover_score_enabled` | **true / true**（与 `use_turnover` 解耦；未写时回退总开关） |
| `turnover_score_max` / `min` | **+8 / −8** |
| `turnover_lookback` | **20**（相对中位） |
| `turnover_rel_sweet_*` / `soft_cap` / `penalty_full` | **1.0 / 2.0 / 3.5 / 5.0** |
| `turnover_abs_penalty_above` / `full` | **25 / 40**（绝对熔断减分；≥40% → −8） |
| `use_volume_ratio` | false |
| `use_yang_medium` / `require_ma_bull` | **true / true** |
| `history_calendar_days` | 120 |
| `structure_rr_warn_enabled` / `structure_rr_min_rr` | true / **2.0** |
| `structure_rr_hard_gate_enabled` | **true** |
| `structure_rr_min_upside_pct` | **0.03**（最近档最小上行；不足则硬闸） |
| `structure_rr_atr_k` | **0.75**（0=关闭 ATR 分母） |
| `structure_rr_use_second_level` | **true**（打分用第二档） |
| `structure_hang_min_upside_pct` | **0.08** |
| `overheat_lookback_days` | **10** |
| `overheat_soft_pct` / `overheat_hard_pct` | **0.15 / 0.25**（相对近窗最低价） |
| `overheat_bias_soft_pct` / `overheat_bias_hard_pct` | **0.15 / 0.20**（相对 MA20） |
| `overheat_warn_enabled` / `overheat_hard_gate_enabled` | **true / true** |

### 8.2 买后纪律（主要在回测 `risk_exit`）

配置块 `risk`（`evaluate_exit_rules`）：

| 项 | 默认 | 行为 |
|----|------|------|
| 价格止损 | `stop_loss_pct_max=10`（另有 min=5 作区间说明） | 浮亏达 **上限 %** 离场 |
| 时间止损 | 连续收跌 **3** 日 | 离场 |
| 回撤止盈 | 涨幅达警惕区下限 **25%** 后，自高点回撤 **5%** | 止盈 |

回测另有 `hit_rate`（默认）：观察约 **20** 交易日、目标约 **10%**，期内不止损。详见回测专文。

---

## 9. API 与前端交互要点

### 9.1 选股

- **路径**：`GET /api/screening/urt-strategy`  
- **关键 Query**：`scope`、`date`、`limit`、`config_id`、`cn_board_segment`（可重复）、`industry_board_code` / `concept_board_code`、`board_code_source`、`stock_code`、`volume_multiple`、`min_score` 等  
- **超时**：环境变量 `URT_SCREENING_TIMEOUT`（默认至少 600s）  
- **缓存**：无 Query 覆盖、无板块键过滤、非单股时优先读 `urt_signal_trace` 当日买点；否则实时扫描  
- **刷新**：改 scope / 板块 / 版本 / 量能 / 得分后须点「刷新筛选」才重算（前端不自动刷新）

### 9.2 其它前台接口（摘要）

| 能力 | 路径 / 页面 |
|------|-------------|
| 参数版本列表 | `GET /api/frontend/urt/strategy-configs` |
| 信号历史 | `stock_urt_trace.html` + `/api/stock/urt-signal-trace*` |
| 得分明细 | `stock_urt_score_detail.html` |
| 交易观察 / 正式交易 | `/api/stock/urt-trade-observe*`、`/api/stock/urt-formal-trade*`；选股页三子面板 |
| 管理端 | `/urt-management` → `/api/admin/urt/*` |

### 9.3 预计算与推送

- 预计算：`scheduled_precompute.py`；默认工作日 A 股约 **16:45**、港股约 **17:20**（`ENABLE_URT_PRECOMPUTE`）；写入 `urt_signal_trace`。  
- 日报：`report_type=urt_daily`；建议推送时刻晚于预计算（约 **17:30**）；仅自选 A 股 + 买点/连阳补充。
- **改参后**：管理端保存参数会提示打开「信号预计算」；旧信号按 `config_id` 保留、**不自动删**，也不改历史回测任务。同版本原地改严后，日终只覆盖命中行，旧买点可能残留——需对该版本手动预计算，或个股页「强制重新计算」。前台在 `stale` 时提示缓存可能过期。

---

## 10. 与 GMS 的差异要点

| 维度 | URT | GMS |
|------|-----|-----|
| 买点哲学 | 右侧趋势确认（均线 + 连阳 + 放量） | 左侧均值吸附 + 右侧动量 |
| 数据 | 日线现算为主；可选读 `urt_signal_trace` | 依赖预计算指标表等 |
| 结构 RR | 仅风险标签，不减分 | 可有减分版 |
| 覆盖 | A 股 + 港股选股/预计算；单股明细仅 A 股；日报仅 A 股自选 | A/港/ETF 等更全（以 GMS 文档为准） |

更细模块对照与技术方案：[URT_GMS功能对比与技术方案.md](./URT_GMS功能对比与技术方案.md)（以代码与本文为准）。

---

## 11. 边界与常见误解

| 点 | 说明 |
|----|------|
| 量能 ≠ 量比 | 量能倍数相对近 20 日均量；量比相对前日量 |
| 0 条结果 | 硬筛 + 最低分较严，部分交易日全市场很少属正常 |
| 单股「明细」 | 可看未过筛；≠ 正式买点 |
| 港股 | 可全市场选股/预计算；**不进** A 股 `urt_daily`；单股 scope 暂仅 A 股 |
| ETF | 选股 scope **当前未实现**独立 ETF 池（与 GMS 不同） |
| 观察股版本池 | GMS 有策略版本观察池；URT **当前未实现**对等能力（有「交易观察」个股列表，非版本池） |

---

## 12. 相关实现（维护索引）

| 层级 | 路径 |
|------|------|
| 策略包 | `backend_core/strategies/urt/`（`indicators` / `scoring` / `signal_detector` / `frontend_interface` / `data_loader` / `risk_tags` / `config`） |
| 选股路由 | `backend_api/stock/stock_screening_routes.py` → `get_urt_strategy` |
| 前台公开配置 | `backend_api/stock/urt_public_frontend_routes.py` |
| 信号/回测/交易 | `urt_frontend_routes.py`、`urt_trade_observe_routes.py`、`urt_formal_trade_routes.py` |
| 管理端 | `backend_api/admin/urt_admin_routes.py`、`admin/src/views/UrtManagementView.vue` |
| 日报 | `backend_api/services/report_service.py`（`urt_daily`） |
| 默认配置 | `backend_core/strategies/urt/urt_config.json` |
| 表 | `urt_strategy_configs`、`urt_signal_trace`、`urt_backtest_tasks`、`urt_trace_recompute_tasks` 等 |
| 测试 | `test/test_urt_*.py` |

---

## 13. 对外话术（可复用）

- 「URT 是右侧确认：站上均线 + 连阳 + 放量，再看得分够不够。」  
- 「推送表里『是否买点=否』是连阳观察补充，不是正式买点。」  
- 「港股不会进 A 股 URT 日报；别把 5 位码当成 A 股。」  
- 「回测命中率和纪律出场是两套口径，对客户说明时不要混着讲。」  
- 「结构盈亏比偏低只是风险提示，不会因此刷掉买点或扣分。」
