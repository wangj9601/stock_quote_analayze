# URT 上升趋势策略实现设计

本文档基于当前代码实现，说明上升趋势策略（URT）的规则、得分、工程架构与数据落库，便于研发校验、参数调优与业务对齐。

**相关文档：**

| 文档 | 读者 | 内容侧重 |
|------|------|----------|
| [URT_上升趋势_业务简化版.md](./URT_上升趋势_业务简化版.md) | 业务 / 交易员 | 找什么票、何时可买、推送与买点区别 |
| [URT策略交易回测说明.md](./URT策略交易回测说明.md) | 策略 / 业务 / 研发 | 回测入场、观察期、出场与汇总 |
| [URT策略回测优化方案.md](./URT策略回测优化方案.md) | 策略 / 研发 | 回测样本结论与出场/选股优化待办 |
| [URT_GMS功能对比与技术方案.md](./URT_GMS功能对比与技术方案.md) | 研发 | 与 GMS 能力对照 |
| **本文** | 研发 / 架构 | 硬筛、得分、模块、API、预计算、配置 |

工程包路径：`backend_core/strategies/urt/`。

---

## 1. 策略定义

产品名：**上升趋势策略**；短码：**urt**（Upward Right-side Trend）。

来源：会议纪要《股票交易策略会议纪要》《20260710 A股交易策略讨论》。

| 规则 | 说明 |
|------|------|
| 站上 MA20 | 收盘价 ≥ 20 日简单均线 |
| 连阳 | 4 日内 ≥3 阳 **或** 5 日内 ≥4 阳（阳线：`close > open`） |
| 量能 | 当日量 ≥ 近 20 日均量（不含当日）× `volume_multiple`（默认 2.5） |
| 得分 | 百分制，默认 `min_score=70`（详见 §1.1） |
| 换手 | 默认硬筛 ≥3%；积分默认开：相对近 20 日中位甜区加分、极端减分（绝对 ≥25%/40% 熔断） |
| 量比 | 默认关闭；管理端可启用硬筛，并可参与加分 |
| 中期阳线 10/15/20 | 默认仅展示与轻度加分；`use_yang_medium=true` 时硬筛（默认阈值 ≥6/≥8/≥10） |
| 均线多头 | 默认仅展示与轻度加分（MA5>MA10>MA20）；`require_ma_bull=true` 时硬筛 |

**出信号流程**：先过硬筛（MA20 + 连阳 + 量能，以及若启用的换手/量比/中期阳线/多头）→ 再计算得分 → **均线多头分弱项闸**（默认排除 f_ma_bull∈[4,7)）→ `score < min_score` 仍过滤。

交易纪律（写入配置，选股不强制；**回测持仓阶段生效**）：价格止损 5%–10%、连跌 3 日且浮亏≥4% 离场、涨约 **8%–10%** 后高点回撤 5% 止盈。完整买卖与观察期规则见：[URT策略交易回测说明.md](./URT策略交易回测说明.md)。  
回测与因子 A/B 结论见：[URT策略回测优化方案.md](./URT策略回测优化方案.md)（2026-08-27 更新）。

与 GMS 差异：不做左侧吸附；数据源为 `historical_quotes`（现算 MA），不依赖 `mean_frequency_resonance_indicators`。

### 1.1 信号得分规则（百分制）

实现：`backend_core/strategies/urt/scoring.py` → `compute_score`。最终 `round(clamp(0,100, 各项合计), 2)`。硬筛（站上 MA20 / 多头等）不变；打分用于过筛后排序。**满分≠已贴近买点**。

| 分项 | 分值 | 说明 |
|------|------|------|
| MA20 趋势 | 最高 **10** | 默认 `ma20_score_mode=slope_bias`：站上后按乖离+近 5 日斜率梯度；贴线横盘偏低、温和发散偏高；极端乖离封顶不重奖 |
| 连阳天数 | 最高 **20** | 原 40 分档表 ×(20/40) |
| K 线实体质量 | 最高 **10** | 近窗实体比 + 突破波幅（`yang_quality`） |
| 量能倍数 | 最高 **25** | 相对配置阈值缩放；内部先按 40 分档再 ×25/40 |
| 中期阳线 | 最高 **5** | 10/15/20 日相对阈值完成度等权 |
| 均线多头/空头 | **+0～8 / −8** | 前缀链深度分档（满分 8）；空头 −8 |
| 筹码位置与 RR | 最高 **15** | 贴近支撑约 0～8 + RR 约 0～7；KDE/RR 缺失给中性偏低分 |
| 换手率 | **+8 / −8** | 见下「换手甜区」；`turnover_score_enabled` |
| 量比 | 最高 **5** | 仅当 `use_volume_ratio=true` |
| 过热扣分 | **−10～0** | 软阈值（涨幅/乖离 15%）起扣，逼近硬阈扣满；硬闸仍独立 |

**连阳天数原始档**（再缩放到 `yang_score_max`，默认 20）：

| 条件 | 原始分（/40） |
|------|------|
| 5 日内 5 阳 | 40 |
| 5 日内 ≥4 阳 | 36 |
| 4 日内 4 阳 | 34 |
| 4 日内 ≥3 阳 | 30 |
| 否则 | `4日阳线数 × 8`（最低 0） |

**量能得分**（`volume_multiple` = 当日成交量 / 近 20 日均量，均量不含当日；配置阈值记为 `need`，默认 3.0）：

先按原公式算满 40 分档，再 ×`volume_score_max`/40（默认 25）写入总分。

| 情形 | 公式（缩放前） |
|------|------|
| `vm >= full_multiple` | 40 |
| `need ≤ vm < full` | `30 + (vm-need)/(full-need)×10` |
| `vm < need` | `vm / need × 30` |

**换手甜区（个性化相对中位 + 绝对熔断）**：

| 规则 | 说明 |
|------|------|
| 相对主曲线 | \(r=t/\max(med,0.5)\)；约 1～2× 满分；过高 → 0 → 减至 −8 |
| 绝对熔断 | \(t≥25\%\) 进入减分插值；\(t≥40\%\)（含 50%）→ **−8** |
| 中位不足 | 绝对 3%～7% 甜区回退 |
| 硬筛解耦 | `turnover_hard_filter` / `turnover_score_enabled`；`use_turnover` 为总开关兼容 |

**可选加分 / 可选硬筛**：

| 开关 | 规则 |
|------|------|
| `use_turnover` | 总开关：未写细项时硬筛+积分同开同关 |
| `turnover_hard_filter` | 换手率 ≥ `min_turnover`（默认 3%） |
| `turnover_score_enabled` | 换手甜区加减分 |
| `use_volume_ratio` | 量比按 **0～3** 线性映射到 **0～5** 分；开启时亦作硬筛 |
| `use_yang_medium` | 中期阳线始终计最多约 5 分；`true` 时硬筛须满足 `yang_medium_rules`（默认 10≥6、15≥8、20≥10） |
| `require_ma_bull` | 积分按前缀深度分档（满分默认 8）；`true` 时硬筛仍须 `MA5>MA10>MA20`（`ma_bull_periods`，不加长） |

**均线多头前缀分档**（`ma_bull_score_periods` 默认 5/10/20/30/60/120/250；表默认 `[0,1.5,3,4.5,6,7,8]`）：

| 深度 d | 约至 | 得分 |
|--------|------|------|
| 0 | 连 5>10 不成 | 0 |
| 1 | 仅 5>10 | 1.5 |
| 2 | 5>10>20（硬筛基线） | 3 |
| 3～4 | 至 30 / 60 | 4.5 / 6 |
| 5～6 | 至 120 / 250 | 7 / 8 |

空头：硬筛三段 `MA5<MA10<MA20` → **−8**。短历史算不出长均线时深度自然截断。

默认配置下正项约：MA20(≤10) + 连阳天(≤20) + 实体(≤10) + 量能(≤25) + 中期(≤5) + 多头(≤8) + 位置RR(≤15) + 换手(±8)；过热另扣 −10～0。`min_score` 默认仍 **70**（上线后可按抽样校准）。

### 1.2 信号计算数据来源

URT **不读**预计算指标表（如 `mean_frequency_resonance_indicators` / `macd_indicators`），行情侧一律从日 K 现算。实现入口：`URTDataLoader` → `URTStrategyEngine` → `build_indicators` / `compute_score`。

#### 涉及表与文件

| 来源 | 用途 | 读取时机 |
|------|------|----------|
| `stock_basic_info` | 候选股票池（代码、名称）；过滤 6 位码、名称含 ST、`collect_enabled` 为 false 的标的；可选按代码前缀过滤板块 | `list_a_share_candidates` |
| `historical_quotes` | 单票区间日 K（OHLC、volume、turnover_rate 等）；解析有效基准日（`max(date)` / 指定日是否有数据） | `fetch_historical_desc` / `resolve_effective_history_end_date` |
| `urt_strategy_configs` | 策略参数版本（`config_params` JSON：MA 周期、连阳规则、量能倍数、`min_score`、换手/量比开关与阈值、`risk` 等） | `URTConfigManager.get_config`（有 DB 且存在默认/指定版本时） |
| `backend_core/strategies/urt/urt_config.json` | 无可用 DB 版本时的参数回退（与代码内 `get_default_config` 深度合并） | `load_file_config` |
| `watchlist`（+ `users`） | 仅 `scope=watchlist`：按当前登录用户取自选 `stock_code`，再回落到 `stock_basic_info` 过滤 | 选股路由 `GET /api/screening/urt-strategy` |

API Query 覆盖项（如 `volume_multiple`、`min_score`、`use_turnover` 等）在内存中 `merge_overrides`，**不落库**。

#### 行情字段 → 计算变量

以下字段均来自 `historical_quotes`（按 `code` + 日期窗口查询，结果按 `date DESC`，index 0 = 基准日）：

| 表字段 | 派生变量 / 用途 |
|--------|-----------------|
| `open` / `close` | 阳线判定（`close > open`）→ `yang_count_4` / `yang_count_5`；连阳硬筛与得分 |
| `close` | `sma(close, ma_period)` → `ma20`；`above_ma20`（`close >= ma20`） |
| `volume` | 近 `volume_lookback`（默认 20）日均量（**不含当日**）→ `avg_volume_20`；`volume_multiple = 当日量 / avg_volume_20`；量比近似 `volume_ratio = 当日量 / 前日量` |
| `turnover_rate` | 可选硬筛 / 加分（`use_turnover`） |
| `date` | `signal_date`、有效筛选基准日 |
| `high` / `low` / `amount` / `change_percent` / `name` | 随查询一并取出；**当前买点硬筛与得分未使用**（预留/展示） |

候选池展示名优先用 `stock_basic_info.name`；K 线行内亦带 `historical_quotes.name`。

#### 信号字段来源一览（结果行）

| 输出字段 | 数据来源 |
|----------|----------|
| `code` / `name` | `stock_basic_info`（候选池） |
| `signal_date` / `open` / `close` / `volume` / `turnover_rate` | `historical_quotes` 基准日行 |
| `ma20` / `yang_count_4` / `yang_count_5` / `avg_volume_20` / `volume_multiple` / `volume_ratio` | 内存现算（`indicators.py`） |
| `yang_rule` / `score` / `signal_strength` / `buy_signal` | 内存判定与打分（`signal_detector` / `scoring`） |
| 阈值类（`min_score`、`volume_multiple` 配置值等） | `urt_strategy_configs` 或 JSON，可被 API Query 覆盖 |

历史窗口长度由配置 `history_calendar_days`（默认 120 个自然日）决定，再截到有效基准日及以前。

## 2. 模块结构（对齐 GMS/VSB 垂直切片）

```
backend_core/strategies/urt/
  config.py / urt_config.json
  data_loader.py
  indicators.py / scoring.py / signal_detector.py
  strategy_engine.py
  frontend_interface.py

backend_api/
  models.py                 # URTStrategyConfig → urt_strategy_configs
  admin/urt_admin_routes.py # /api/admin/urt
  stock/stock_screening_routes.py  # GET /api/screening/urt-strategy

frontend/screening.html + js/screening.js  # Tab data-strategy="urt"
admin/  # /urt-management 参数配置页
```

## 3. API

### 选股

`GET /api/screening/urt-strategy`

主要 Query：`scope`(all|watchlist)、`limit`、`date`、`config_id`、`volume_multiple`、`min_score`、`signal_quality_mode`（`standard`|`premium`）、`boards`、`use_turnover`、`use_volume_ratio`。

响应：

```json
{
  "success": true,
  "data": [{ "code", "name", "signal_date", "close", "ma20", "yang_count_4", "yang_count_5", "volume_multiple", "score", ... }],
  "total": 0,
  "strategy_name": "上升趋势策略",
  "search_date": "YYYY-MM-DD",
  "parameters": {}
}
```

### 管理端

- `GET/POST /api/admin/urt/strategy-configs`
- `GET/PUT /api/admin/urt/strategy-configs/{id}`
- `GET /api/admin/urt/default-params`
- `POST /api/admin/urt/screen-preview`

## 4. 权限

权限码：

- `channel.screening.tab.urt` — 选股页「上升趋势」Tab
- `channel.screening.tab.urt.btn.refresh` — 刷新筛选
- `channel.screening.tab.urt.btn.export` — 导出 CSV

注册表：`frontend/js/permission-registry.js`、`backend_api/permission_registry_data.py`（`PERMISSION_TAB_MAP.urt`）。

行为：

- 前端 `PermissionEngine.decorateStrategyTabs` 为 Tab/内容区/刷新/导出挂载 `data-perm`，无权限则隐藏
- `ScreeningPage.switchStrategy` 无 Tab 权限时拒绝切换
- 后端启动时 `ensure_permissions_from_registry`：把注册表缺失项写入 DB，并给 **admin / standard** 补齐缺少的注册表权限（不影响其他自定义角色）
- 自定义角色：管理端「权限资源」同步后，在角色权限中勾选上述 URT 码

## 5. 与 GMS 对照

完整模块状态见：[URT_GMS功能对比与技术方案.md](./URT_GMS功能对比与技术方案.md)；业务口径见：[URT_上升趋势_业务简化版.md](./URT_上升趋势_业务简化版.md)。

| 能力 | GMS | URT（当前） |
|------|-----|-------------|
| 选股引擎 | 左+右双买点 | 仅右侧趋势买点 |
| 参数多版本 | 有 | 有（`urt_strategy_configs`） |
| 前台 Tab / 版本下拉 | 有 | 有 |
| Admin 配置 / 回测 | 有 | 有（精简；回测暂仅 A 股） |
| 信号 trace | 有 | 有（A/港预计算） |
| 交易观察 / 正式交易 | 有 | 有（用户侧三子面板；非版本池） |
| 策略版本观察股池 / ETF | 有 | **未实现**对等能力 |

## 5.1 预计算 / 回测 / 历史·明细

### 预计算（A 股 + 港股）

| 项 | 说明 |
|----|------|
| 表 | `urt_signal_trace`（PK: `code`+`date`+`config_id`），含得分、硬筛字段、`score_detail` JSON（含 `structure`：KDE 支撑/阻力） |
| 结构位 | 信号计算时用成交量加权 KDE（`extract_kde_levels_expand_support`，与 RPE/个股关键价位同口径）；写入结果顶层 `support_levels`/`resistance_levels`/`nearest_*` 及 `score_detail.structure`；**不参与硬筛** |
| 结构盈亏比提示 | `structure.rr`：无量纲 RR=上行/max(价−支撑, 价×1.5%, k×ATR)；打分默认第二档，最近档只硬闸。明细展示 RR、上行%、下行%、是否触分母下限。`poor_structure_rr` 偏低为 warn（阈值 2～3）；破位/贴阻力为 danger。 |
| 配置 | `urt_strategy_configs.precompute_enabled`；默认版本或开关开启才算 |
| 任务 | `backend_core/strategies/urt/scheduled_precompute.py` → `scheduled_urt_signals_cn`；`data_collectors/main.py` 注册，默认 **16:45**（港股 17:20），`ENABLE_URT_PRECOMPUTE`；`urt_daily` 推送建议 **17:30**（须晚于预计算） |
| 选股 | `URTFrontendInterface.screen` 无 Query 覆盖时优先读 `urt_signal_trace` |
| 手动 | `POST /api/admin/urt/precompute/run?date=&config_id=&market=CN|HK`；管理端「URT上升趋势策略」页「信号预计算」支持选日期 |

### 改参后行为与验收（参数统一）

| 项 | 约定 |
|----|------|
| 生效源 | 日常路径一律绑定 `is_default=true` 的版本；回测创建固化 `strategy_config_id`；前台默认同一生效 id |
| 保存参数 | 管理端「策略参数」保存成功后提示重跑预计算；确认则打开「信号预计算」并预填当前 `config_id`（**不自动**全市场重算） |
| 旧 trace | 按 `(code, date, config_id)` 隔离；保存**不删除**旧行；同 id 原地改参后，若 `trace.created_at < config.updated_at` 则接口标 `stale` / `need_recompute` |
| 日终预计算 | 仅 `is_default` 或 `precompute_enabled`（及环境变量额外 id）；只 upsert 命中买点，收紧参数后旧买点可能残留，需手动预计算或个股强制重算 |
| 个股强制重算 | `POST /api/stock/urt-signal-trace/recompute`：仅清除该 `code+config_id` 再全历史写入 |
| 历史回测 | 已完成任务快照不改写；改参后重跑任务仍用任务内 `strategy_config_id`，读到的是**当前**该 id 的 trace |
| 验收 | ① 保存有提示且可打开预计算；② 改参后选股/信号历史可见陈旧提示；③ 预计算或强制重算后 `stale=false`；④ 新旧 `config_id` 不串；⑤ 旧回测任务结果不变 |

### 回测管理

详细买卖规则、观察期、风控与汇总字段见专文：[URT策略交易回测说明.md](./URT策略交易回测说明.md)。

| 项 | 说明 |
|----|------|
| 表 | `urt_backtest_tasks` |
| Core | `backtest_runner` / `backtest_storage` / `backtest_worker` |
| 市场 | 暂仅 A 股 |
| 信号 | 优先 `urt_signal_trace`；区间内缺失日先按时间范围全市场/股票池补算一次再回测；`use_trace=false` 则逐日实时（含全市场） |
| 入场 | 信号次日开盘价；同标的上一笔出场日前不重复开仓 |
| 观察期 | `horizon_days`，**默认 10 个交易日**（短线；可任务级改为 5/15/20） |
| 出场 | 默认 `hit_rate`：观察期内最高价判定目标（默认 10%），**不止损**；可选 `risk_exit` / `structure_exit` |
| 信号质量 | 任务 `signal_quality_mode`：`standard`（默认，ma_bull 弱项后滤）/ `premium`（精选） |
| 元数据 | 任务 `config`/`summary` 含 `trade_logic`、`risk_params`；详情页展示 |
| 导出 | UTF-8-BOM CSV，中文列名（Excel 可开） |
| API | `/api/admin/urt/backtests*`（创建/列表/详情/取消/重跑/删除/导出） |
| Admin | `/urt-management` →「回测管理」Tab；详情见 `TaskDetail.vue` |

### 前台页面与选股按钮

| 入口 | 页面 |
|------|------|
| 选股结果「历史」 | `frontend/stock_urt_trace.html` → `GET /api/stock/urt-signal-trace` |
| 选股结果「明细」（原「详情」） | `frontend/stock_urt_score_detail.html` → `GET /api/stock/urt-score-detail` |

## 6. 参数说明与值域

参数持久化优先级：`urt_strategy_configs.config_params`（指定/默认版本）→ 文件 `backend_core/strategies/urt/urt_config.json` → 代码内 `get_default_config()`。  
选股 API Query 可覆盖部分运行时项（不落库）；管理端表单校验见 `admin/.../StrategyConfiguration.vue`。

### 6.1 硬筛与得分（选股核心）

| 参数 | 含义 | 默认 | 建议/界面值域 | 说明 |
|------|------|------|---------------|------|
| `ma_period` | 均线周期（日） | 20 | 管理端 **5～60** | 用收盘价算 SMA；站上条件：`close ≥ MA` |
| `volume_lookback` | 量能均量窗口（交易日） | 20 | 管理端 **5～60** | 均量**不含当日**；量能倍数 = 当日量 / 该均量 |
| `volume_multiple` | 量能倍数阈值 | 2.5 | 管理端/API **1～30** | 硬筛：派生量能倍数 ≥ 本值；同时是量能打分基准 |
| `min_score` | 最低得分 | 70 | **0～100** | 硬筛通过后仍须 `score ≥ min_score` |
| `exclude_ma_bull_score_mid_enabled` | 均线多头分弱项闸 | **true** | — | 默认否决 f_ma_bull ∈ [lo, hi) |
| `exclude_ma_bull_score_lo` / `hi` | 弱项区间 | **4.0 / 7.0** | — | 左闭右开；A/B 验证 |
| `premium_signal_near_support_max_pct` | 精选：距支撑上限 | **2.0** | — | 仅 `signal_quality_mode=premium` |
| `premium_signal_exclude_score_ge` | 精选：排除高分 | **90.0** | — | 同上 |
| `premium_signal_exclude_hvz_near_max_pct` | 精选：排除贴身 HVZ | **1.0** | — | 距压力带 ≤ 该% 且 `chips_hvz` |
| `yang_rule_a.window` | 规则 A 窗口（日） | 4 | 表单固定 4；JSON 可改 | 与 `min_up_days` 组成「N 日至少 M 阳」 |
| `yang_rule_a.min_up_days` | 规则 A 最少阳线数 | 3 | 管理端 **1～4** | 满足 A **或** B 即过连阳硬筛 |
| `yang_rule_b.window` | 规则 B 窗口（日） | 5 | 表单固定 5；JSON 可改 | 同上 |
| `yang_rule_b.min_up_days` | 规则 B 最少阳线数 | 4 | 管理端 **1～5** | 同上；阳线判定：`close > open` |

连阳硬筛逻辑：`yang_count(window_a) ≥ min_up_days_a` **OR** `yang_count(window_b) ≥ min_up_days_b`。

### 6.2 精细化（可选硬筛 + 可选加分）

| 参数 | 含义 | 默认 | 值域 | 说明 |
|------|------|------|------|------|
| `use_turnover` | 是否启用换手硬筛/加分 | `false` | bool | `true` 时：换手率须 ≥ `min_turnover`，且得分最多 +5（按 0%～8% 线性） |
| `min_turnover` | 最低换手率（%） | 0 | ≥0（管理端步长 0.1） | 仅 `use_turnover=true` 时生效；API `min_turnover≥0` |
| `use_volume_ratio` | 是否启用量比硬筛/加分 | `false` | bool | `true` 时：量比须 ≥ `min_volume_ratio`，且得分最多 +5（按 0～3 线性） |
| `min_volume_ratio` | 最低量比 | 0 | ≥0（管理端步长 0.1） | 量比 = 当日量 / 前日量；仅开关开启时生效 |
| `yang_medium_rules` | 中期阳线窗口与阈值 | 10/6、15/8、20/10 | list | 始终计算 `yang_count_*` 并轻度加分 |
| `use_yang_medium` | 中期阳线是否硬筛 | `false` | bool | `true` 时须全部窗口达标 |
| `ma_bull_periods` | 硬筛多头均线周期 | `[5,10,20]` | list | 严格递减即为硬筛多头 |
| `ma_bull_score_periods` | 积分用均线链 | `[5,10,20,30,60,120,250]` | list | 前缀深度分档；不抬硬筛门槛 |
| `ma_bull_score_max` / `ma_bull_score_table` | 满分与深度→分表 | `8` / `[0,1.5,3,4.5,6,7,8]` | | d=2（短多）约 +3；d=6 全链 +8 |
| `volume_score_max` | 量能分项满分 | 25 | | 内部 40 档 ×25/40 |
| `yang_score_max` / `yang_quality_score_max` | 连阳天数 / 实体质量 | 20 / 10 | | |
| `yang_medium_score_max` | 中期阳线满分 | 5 | | |
| `ma20_score_mode` / `ma20_score_max` | MA20 趋势计分 | `slope_bias` / 10 | | `binary` 可回退静态满分 |
| `structure_*_score_*` | 位置与 RR 分项 | 贴近 8 + RR 7 | | KDE 缺失中性给分 |
| `overheat_penalty_max` | 过热扣分上限 | 10 | | 软阈起扣，硬闸独立 |
| `require_ma_bull` | 多头是否硬筛 | `false` | bool | `true` 时须硬筛链多头排列 |

最少 K 线根数约：`max(ma_period, volume_lookback+1, yang 短窗, 中期最大窗, 硬筛多头最大周期)`（积分长均线不足时深度截断，不整段失败）。

**均线多头前缀分档**：从短到长连续满足 `MA[i]>MA[i+1]` 的相邻对数为深度 d；空头减分仍只看硬筛链 `MA5<MA10<MA20` → −8。

### 6.3 KDE 结构位与盈亏比风险提示

| 参数 | 含义 | 默认 | 说明 |
|------|------|------|------|
| `kde_lookback_days` 等 | KDE 回看 | 60/250/750 | 初始/步进/上限 |
| `structure_rr_warn_enabled` | 是否打盈亏比风险标签 | `true` | 软提示；关闭后不生成 `risk_tags` |
| `structure_rr_min_rr` | 最低可接受 RR | `2.0` | 无量纲；≥3 满分档、2～3 插值；偏低为 warn |
| `structure_rr_min_downside_pct` | RR 价格比例分母下限 | `0.015` | 与 k×ATR 取 max；贴支撑避免 RR 虚高 |
| `structure_rr_atr_k` | ATR 分母系数 | `0.75` | 分母 max(价−支撑, 价×1.5%, k×ATR)；0=关闭 |
| `structure_rr_use_second_level` | 第二档算结构 RR | `true` | 打分/提示用第 2 档；最近档只做硬闸 |

实现：`signal_detector.evaluate_buy_signal` → `urt/risk_tags.enrich_structure_with_rr`（复用 GMS `compute_structure_rr`）。旧 trace 读路径由 `trace_store._enrich_trace_structure_fields` 只读补算。

### 6.4 数据窗口

| 参数 | 含义 | 默认 | 值域 | 说明 |
|------|------|------|------|------|
| `history_calendar_days` | 拉取行情的自然日窗口 | 120 | 建议 ≥60；代码下限按窗口至少约 30 日 | 从基准日向前取日历天数，再截到有效交易日；须覆盖 MA/量能/连阳/中期窗所需最少 K 线根数 |

### 6.5 交易纪律 `risk`（回测扩展，选股不强制）

实现：`signal_detector.evaluate_exit_rules`。管理端表单暴露部分字段；其余可在 JSON 中改。  
回测入场/观察期/出场优先级与任务参数见：[URT策略交易回测说明.md](./URT策略交易回测说明.md) §3–§4。

| 参数 | 含义 | 默认 | 界面/建议值域 | 说明 |
|------|------|------|---------------|------|
| `risk.stop_loss_pct_min` | 止损区间下限（%） | 5 | JSON | 文档化区间；当前离场逻辑主要用上限 |
| `risk.stop_loss_pct_max` | 价格止损阈值（%） | 10 | 管理端 **1～30** | 浮亏 ≤ −该值 → `price_stop` |
| `risk.time_stop_down_days` | 连跌离场天数 | 3 | 管理端 **1～10** | 连续收跌天数 ≥ 该值，且浮亏 ≥ `time_stop_min_loss_pct` → `time_stop` |
| `risk.time_stop_min_loss_pct` | 连跌须浮亏（%） | **4** | 管理端 **0～20** | 0 表示仅看连跌天数 |
| `risk.take_profit_alert_pct_min` | 止盈警惕涨幅下限（%） | **8** | 管理端 | 自成本涨幅达警惕区后才启用回撤止盈 |
| `risk.take_profit_alert_pct_max` | 止盈警惕涨幅上限（%） | **10** | 管理端 | 文档区间上限；实现以 `alert_min` 起步 |
| `risk.trailing_drawdown_pct` | 高点回撤止盈（%） | 5 | 管理端 **1～20** | 达警惕涨幅后，自峰值回撤 ≥ 该值 → `trailing_take_profit` |

回测任务级参数（不写入 `risk`，写在任务 `config`）：

| 参数 | 含义 | 默认 |
|------|------|------|
| `target_pct` | 目标涨幅下限（小数） | 0.10 |
| `target_pct_max` | 目标涨幅上限（小数） | 等于下限（缺省 10%～10%） |
| `horizon_days` | 观察期交易日数 | **10** |
| `use_trace` | 是否优先读 `urt_signal_trace` | true |
| `signal_quality_mode` | 信号质量 | **`standard`** |
| `compare_hit_rate` | 结构/纪律完成后自动命中率对照 | 非 `hit_rate` 默认开 |
| `stock_pool_mode` | 股票池 | `all`（含 `gms_watchlist`） |

### 6.6 选股 API 运行时参数（Query，不写配置表）

`GET /api/screening/urt-strategy`：

| Query | 含义 | 校验/枚举 | 备注 |
|-------|------|-----------|------|
| `scope` | 股票范围 | `cn`/`all` \| `watchlist` \| `industry_board` \| `concept_board` \| `single` | 自选需登录；**`single` 见下方说明** |
| `stock_code` | 个股代码/名称 | 文本 | 仅 `scope=single` |
| `limit` | 扫描股票数上限 | ≥1（可选） | 先截断候选池再算信号；全市场建议带 limit |
| `date` | 筛选基准日 | `YYYY-MM-DD` | 无数据时回退表内最新交易日 |
| `config_id` | 参数版本 ID | ≥1 | 不传则用默认版本 / JSON |
| `volume_multiple` | 临时覆盖量能阈值 | **1.0～30.0** | 仅全部A股/港股前端会传并过滤；自选/板块/单股不传且列表不过滤 |
| `min_score` | 临时覆盖最低分 | **0～100** | 同上 |
| `signal_quality_mode` | 信号质量 | **`standard`** | `standard` / `premium`；见回测说明 §2.3 |
| `use_turnover` / `use_volume_ratio` | 临时开关 | bool | 同上 |
| `min_turnover` / `min_volume_ratio` | 临时阈值 | ≥0 | 同上 |
| `boards` | 板块过滤（可多选） | `CYB` / `KCB` / `SH_MAIN` / `SZ_MAIN` / `SZ_SME` / `BJ` | 按代码前缀过滤 `stock_basic_info`；不传=不限板块 |

**`scope=single` / `watchlist` / `industry_board` / `concept_board`**：不按硬筛与最低得分过滤结果列表，实时计算并返回策略信号明细（含 `buy_signal=false`）；前端禁用量能/最低得分覆盖。实现：`URTFrontendInterface.screen(skip_screening_filters=True)` → `evaluate_buy_signal(..., require_pass=False)`。正式买点仍由行内 `buy_signal` 标识。

板块前缀（`URT_BOARD_PREFIX_GROUPS`）：创业板 `300*`、科创 `688*`、沪主板 `600/601/602/603/605*`、深主板 `000/001*`、中小 `002*`、北证 `43/83/87/88/92*`。

### 6.6 量能 vs 量比（易混项）

| | 量能 `volume_multiple`（派生） | 量比 `volume_ratio`（派生） |
|--|--|--|
| 公式 | 当日量 ÷ 近 N 日均量（N=`volume_lookback`，不含当日） | 当日量 ÷ 前日量 |
| 配置阈值字段 | `volume_multiple` | `min_volume_ratio`（需 `use_volume_ratio`） |
| 默认 | **启用**硬筛与主得分 | **关闭** |

得分细则见 §1.1；表字段映射见 §1.2。

## 7. 测试

`test/test_urt_strategy.py`：连阳计数、量能、硬筛、得分/分项明细、`require_pass=False` 明细、止损/止盈路径、回测 storage 工具函数。
