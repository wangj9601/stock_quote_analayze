# URT 上升趋势策略实现设计

## 1. 策略定义

产品名：**上升趋势策略**；短码：**urt**（Upward Right-side Trend）。

来源：会议纪要《股票交易策略会议纪要》《20260710 A股交易策略讨论》。

| 规则 | 说明 |
|------|------|
| 站上 MA20 | 收盘价 ≥ 20 日简单均线 |
| 连阳 | 4 日内 ≥3 阳 **或** 5 日内 ≥4 阳（阳线：`close > open`） |
| 量能 | 当日量 ≥ 近 20 日均量（不含当日）× `volume_multiple`（默认 2.5） |
| 得分 | 百分制，默认 `min_score=70`（详见 §1.1） |
| 换手/量比 | 默认关闭；管理端可启用硬筛，并可参与加分 |

**出信号流程**：先过硬筛（MA20 + 连阳 + 量能，以及若启用的换手/量比阈值）→ 再计算得分 → `score < min_score` 仍过滤。

交易纪律（写入配置，选股不强制；**回测持仓阶段生效**）：价格止损 5%–10%、连跌 3 日离场、涨 25%–30% 后高点回撤 5% 止盈。完整买卖与观察期规则见：[URT策略交易回测说明.md](./URT策略交易回测说明.md)。

与 GMS 差异：不做左侧吸附；数据源为 `historical_quotes`（现算 MA），不依赖 `mean_frequency_resonance_indicators`。

### 1.1 信号得分规则（百分制）

实现：`backend_core/strategies/urt/scoring.py` → `compute_score`。最终 `round(min(100, 各项合计), 2)`。

| 分项 | 分值 | 说明 |
|------|------|------|
| 站上 MA20 | 固定 **+10** | `close >= MA20` 时计入 |
| 连阳强度 | 最高 **40** | 见下表 |
| 量能倍数 | 最高约 **40** | 相对配置阈值 `volume_multiple`（默认 2.5） |
| 换手率 | 最高 **5** | 仅当 `use_turnover=true` |
| 量比 | 最高 **5** | 仅当 `use_volume_ratio=true`（当日量/前日量） |

**连阳得分**（`yang_count_4` / `yang_count_5`，阳线：`close > open`）：

| 条件 | 得分 |
|------|------|
| 5 日内 5 阳 | 40 |
| 5 日内 ≥4 阳 | 36 |
| 4 日内 4 阳 | 34 |
| 4 日内 ≥3 阳 | 30 |
| 否则 | `4日阳线数 × 8`（最低 0） |

**量能得分**（`volume_multiple` = 当日成交量 / 近 20 日均量，均量不含当日；配置阈值记为 `need`，默认 2.5）：

| 情形 | 公式 |
|------|------|
| `vm >= need` | `30 + min(10, (vm - need) / need × 10)`（约 2.5 倍→30，约 5 倍→40） |
| `vm < need` | `vm / need × 30`（线性不足） |

**可选加分**（默认关闭）：

| 开关 | 规则 |
|------|------|
| `use_turnover` | 换手率按 **0%～8%** 线性映射到 **0～5** 分：`min(5, turnover / 8 × 5)` |
| `use_volume_ratio` | 量比按 **0～3** 线性映射到 **0～5** 分：`min(5, volume_ratio / 3 × 5)` |

默认配置下（换手/量比未启用）典型满分结构约为：MA20(10) + 连阳(≤40) + 量能(≤40) ≈ **90**；启用两项精细加分后理论上可逼近 100。

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

主要 Query：`scope`(all|watchlist)、`limit`、`date`、`config_id`、`volume_multiple`、`min_score`、`boards`、`use_turnover`、`use_volume_ratio`。

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

| 能力 | GMS | URT（本期） |
|------|-----|-------------|
| 选股引擎 | 有 | 有 |
| 参数多版本 | 有 | 有（`urt_strategy_configs`） |
| 前台 Tab | 有 | 有 |
| Admin 配置 | 有 | 有（精简） |
| 信号 trace / 观察股 / 回测中心 | 有 | 二期：`urt_signal_trace` + Admin 回测；观察股后续 |

## 5.1 二期：预计算 / 回测 / 历史·明细

### 预计算（暂仅 A 股）

| 项 | 说明 |
|----|------|
| 表 | `urt_signal_trace`（PK: `code`+`date`+`config_id`），含得分、硬筛字段、`score_detail` JSON（含 `structure`：KDE 支撑/阻力） |
| 结构位 | 信号计算时用成交量加权 KDE（`extract_kde_levels_expand_support`，与 RPE/个股关键价位同口径）；写入结果顶层 `support_levels`/`resistance_levels`/`nearest_*` 及 `score_detail.structure`；**不参与硬筛** |
| 配置 | `urt_strategy_configs.precompute_enabled`；默认版本或开关开启才算 |
| 任务 | `backend_core/strategies/urt/scheduled_precompute.py` → `scheduled_urt_signals_cn`；`data_collectors/main.py` 注册，默认 **16:45**（港股 17:20），`ENABLE_URT_PRECOMPUTE`；`urt_daily` 推送建议 **17:30**（须晚于预计算） |
| 选股 | `URTFrontendInterface.screen` 无 Query 覆盖时优先读 `urt_signal_trace` |
| 手动 | `POST /api/admin/urt/precompute/run?date=&config_id=&market=CN|HK`；管理端「URT上升趋势策略」页「信号预计算」支持选日期 |

### 回测管理

详细买卖规则、观察期、风控与汇总字段见专文：[URT策略交易回测说明.md](./URT策略交易回测说明.md)。

| 项 | 说明 |
|----|------|
| 表 | `urt_backtest_tasks` |
| Core | `backtest_runner` / `backtest_storage` / `backtest_worker` |
| 市场 | 暂仅 A 股 |
| 信号 | 优先 `urt_signal_trace`；区间内缺失日先按时间范围全市场/股票池补算一次再回测；`use_trace=false` 则逐日实时（含全市场） |
| 入场 | 信号次日开盘价；同标的上一笔出场日前不重复开仓 |
| 观察期 | `horizon_days`，**默认 20 个交易日** |
| 出场 | 对齐 GMS 命中率：观察期内最高价判定目标（默认 10%）；**不止损**；持有满观察期以收盘作参考出场 |
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

### 6.3 数据窗口

| 参数 | 含义 | 默认 | 值域 | 说明 |
|------|------|------|------|------|
| `history_calendar_days` | 拉取行情的自然日窗口 | 120 | 建议 ≥60；代码下限按窗口至少约 30 日 | 从基准日向前取日历天数，再截到有效交易日；须覆盖 MA/量能/连阳所需最少 K 线根数 |

最少 K 线根数约：`max(ma_period, volume_lookback+1, yang_rule_a.window, yang_rule_b.window)`。

### 6.4 交易纪律 `risk`（回测扩展，选股不强制）

实现：`signal_detector.evaluate_exit_rules`。管理端表单暴露部分字段；其余可在 JSON 中改。  
回测入场/观察期/出场优先级与任务参数见：[URT策略交易回测说明.md](./URT策略交易回测说明.md) §3–§4。

| 参数 | 含义 | 默认 | 界面/建议值域 | 说明 |
|------|------|------|---------------|------|
| `risk.stop_loss_pct_min` | 止损区间下限（%） | 5 | JSON | 文档化区间；当前离场逻辑主要用上限 |
| `risk.stop_loss_pct_max` | 价格止损阈值（%） | 10 | 管理端 **1～30** | 浮亏 ≤ −该值 → `price_stop` |
| `risk.time_stop_down_days` | 连跌离场天数 | 3 | 管理端 **1～10** | 连续收跌天数 ≥ 该值 → `time_stop` |
| `risk.take_profit_alert_pct_min` | 止盈警惕涨幅下限（%） | 25 | JSON | 自成本涨幅达警惕区后才启用回撤止盈 |
| `risk.take_profit_alert_pct_max` | 止盈警惕涨幅上限（%） | 30 | JSON | 与会议纪律区间对应；现实现以 `alert_min` 起步 |
| `risk.trailing_drawdown_pct` | 高点回撤止盈（%） | 5 | 管理端 **1～20** | 达警惕涨幅后，自峰值回撤 ≥ 该值 → `trailing_take_profit` |

回测任务级参数（不写入 `risk`，写在任务 `config`）：

| 参数 | 含义 | 默认 |
|------|------|------|
| `target_pct` | 目标涨幅（小数） | 0.10 |
| `horizon_days` | 观察期交易日数 | **20** |
| `use_trace` | 是否优先读 `urt_signal_trace` | true |

### 6.5 选股 API 运行时参数（Query，不写配置表）

`GET /api/screening/urt-strategy`：

| Query | 含义 | 校验/枚举 | 备注 |
|-------|------|-----------|------|
| `scope` | 股票范围 | `cn`/`all` \| `watchlist` \| `industry_board` \| `concept_board` \| `single` | 自选需登录；**`single` 见下方说明** |
| `stock_code` | 个股代码/名称 | 文本 | 仅 `scope=single` |
| `limit` | 扫描股票数上限 | ≥1（可选） | 先截断候选池再算信号；全市场建议带 limit |
| `date` | 筛选基准日 | `YYYY-MM-DD` | 无数据时回退表内最新交易日 |
| `config_id` | 参数版本 ID | ≥1 | 不传则用默认版本 / JSON |
| `volume_multiple` | 临时覆盖量能阈值 | **1.0～30.0** | 覆盖配置中同名项；**单股模式忽略** |
| `min_score` | 临时覆盖最低分 | **0～100** | 同上；**单股模式忽略** |
| `use_turnover` / `use_volume_ratio` | 临时开关 | bool | 同上 |
| `min_turnover` / `min_volume_ratio` | 临时阈值 | ≥0 | 同上 |
| `boards` | 板块过滤（可多选） | `CYB` / `KCB` / `SH_MAIN` / `SZ_MAIN` / `SZ_SME` / `BJ` | 按代码前缀过滤 `stock_basic_info`；不传=不限板块 |

**`scope=single`（单只股票）**：不应用硬筛与最低得分过滤，实时计算并返回该股策略信号明细（含 `buy_signal=false`）；前端禁用量能/最低得分控件。实现：`URTFrontendInterface.screen(skip_screening_filters=True)` → `evaluate_buy_signal(..., require_pass=False)`。

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
