# 行业指数分析 — 设计说明

**日期：** 2026-11-16  
**状态：** 已按此实现（2026-11-16）  
**范围：** 把同花顺行业板块指数当作一根日 K，做与大盘指数分析同构的环境研判和价格行为。入口两处：行业板块详情页、分析中心「行业指数分析」工作台。

---

## 1. 背景与目标

大盘指数分析已经是独立通道：`index_detail.html` 与分析中心 Tab `index-ai`，接口 `GET /api/analysis/index-analysis-bundle`。日 K 来自 `index_historical_quotes`，实时 OHLC 来自 `index_realtime_quotes`，成分来自 `index_board_constituents`。价格行为复用阻力支撑、形态、波段、江恩；研判口吻是偏多 / 中性 / 偏空，没有买卖点。

行业侧已有同花顺行业指数日 K（`industry_board_historical_quotes`，含 OHLC、成交量、成交额），也有成分表和实时快照。板块详情页展示点位、斜率、闸门、龙头中军、资金流；分析频道 `board-signals` 在成分股上跑四策略。这两条都不是「把行业指数本身当 K 线做环境研判」。

### 成功标准

| 项 | 要求 |
|----|------|
| 身份隔离 | 日 K 只读 `industry_board_historical_quotes`；不读 `index_historical_quotes`，不读个股 `historical_quotes`。成分涨跌读 `stock_realtime_quote` |
| 价格行为 | 日 K 足够时给出阻力支撑、形态、波段、江恩 |
| 环境研判 | 标题「行业环境研判」，输出偏多 / 中性 / 偏空与要点；无买卖、仓位、止损、目标价 |
| 成分 | 有成分且有涨跌幅时给出涨跌家数、中位数、领涨领跌；无成分时明确空态 |
| 双入口 | 分析中心工作台可搜索行业板并在本页出结果；带 `board_code` 的深链打开板块详情并挂同一面板 |
| 实时 | 按钮刷新现价、涨跌与广度锚点；不编造当日开高低 |

### 非目标（本期不做）

- 概念板块（`concept_board_historical_quotes` 只在加载函数留 `board_kind` 参数，不开放入口）
- 把行业代码并入现有「指数分析」输入框
- 大盘那种「行业贡献」区块（单行业内部再按行业拆没有对象）
- 四策略扫描、斜率重算、入场闸门、资金流（留在板块详情现有区块）
- 用实时价合成一根假 K（行业实时表没有开、高、低、昨收）
- 交易口吻的进出场建议
- 港股行业

---

## 2. 用户与场景

- **工作台：** 分析中心打开「行业指数分析」→ 搜索行业名称或代码 → 分析 → 阅读环境研判和价格行为，可导出 PNG / PDF。
- **详情：** 从行情行业板进入 `board_detail.html` → 在现有斜率区块之后看到同一套行业指数分析。闸门、斜率、资金流仍在原处。
- **深链：** `analysis.html?tab=industry-index-ai&board_code=` 进入对应行业板块详情，并自动跑一次分析。

---

## 3. 方案选择

| 方案 | 内容 | 结论 |
|------|------|------|
| A. 新建 Tab + 独立接口，绘制函数按区块前缀复用 | 与指数分析并列，身份分开 | **采用** |
| B. 复制一整份 `index_analysis.js` | 上线快 | 拒绝：环境研判和价格行为会两处各改 |
| C. 在现有指数分析 Tab 里切换「大盘 / 行业」 | 一个输入框两种代码 | 拒绝：`881xxx` 与 `000001` 不能混通道 |

---

## 4. 数据与计算

### 4.1 日 K

新增加载函数（建议 `backend_core/analysis/industry_index_bars.py`）：

- 按 `board_code` 读 `industry_board_historical_quotes`，升序。一次加载不少于 KDE 回看上限（与指数关位所用上限一致，当前为 750 根），供关位和形态共用。本期不另开关位重算接口。
- 输出与 `index_bars.load_index_ohlc_asc` 相同的 bar：`date, open, high, low, close, volume, amount`。
- 列名映射：表字段 `volume`（指数表是 `vol`）。查询键是 `board_code`，不生成 `ts_code`。
- 身份：`industry_board_basic_info` 取名称；没有基础资料时用行情表最近一行的 `board_name`。只有实时、没有日 K 时仍视为找到该板块，由 bundle 以「无可用日线」失败。日 K 与实时都没有时返回未找到。

### 4.2 实时

`industry_board_realtime_quotes` 提供 `latest_price`、`change_amount`、`change_percent`、`volume`、`amount`、`up_count`、`down_count`。没有 open / high / low / pre_close。

`use_realtime=true` 时：

- 抬头现价、涨跌用实时表。
- 关位锚点用 `latest_price`（没有则用最后一根日 K 收盘）。
- **不**调用与 `merge_index_realtime_bar` 等价的改写。返回 `realtime.merged = false`，`realtime.reason` 说明未改写当日 K。
- 价格行为仍用已收盘日 K。

`use_realtime=false` 且带 `date` 时，日 K 截到该日（含当日）。

### 4.3 价格行为

行业 bundle 把已加载的 bars 交给现有引擎，不走 `resolve_index_identity` / `load_index_bars_with_realtime`。

| 模块 | 调用方式 |
|------|----------|
| 阻力支撑 | `StockAnalysisService.get_key_levels_only(..., historical_data=bars, price_adjust="none", anchor_price=锚点)`。必须传入 `historical_data`，避免函数内部按代码读个股日 K |
| 形态 | 现有 `_compute_pattern_from_bars`。传给 `_tactical_enrichment` 的 asof 为空，关闭 RPE / GMS。行业代码也是 6 位，带基准日会按个股去查策略 |
| 波段、江恩 | 现有 `_compute_swing_from_bars`、`_compute_gann_from_bars`，只吃 bars |
| 环境研判 | 现有 `_build_market_view` 的打分规则。`title` 改为「行业环境研判」。`entry` / `stop` / `target` / `position` / `action` 保持 `null` |

上述函数里的 `asset_type` 与「指数日线不足」类文案需能区分行业。给现有函数增加 `asset_type`（行业为 `industry_index`）和对应空数据文案；指数调用保持 `index`，行为不变。

关位计算禁止走 `compute_index_key_levels`：该函数会按指数代码回读 `index_historical_quotes`。

日 K 不足（关位少于 20 根、形态 / 波段 / 江恩少于 30 根）时，对应区块 `ok: false` 并给出原因；有身份但完全没有日 K 时接口失败，提示无可用日线。

### 4.4 广度与领涨领跌

成分来自 `industry_board_constituents`，涨跌幅与成交额来自 `stock_realtime_quote`（按代码留最新一行）。算法与指数 bundle 的 `_compute_breadth_and_leaders` 相同：上涨 / 下跌 / 平盘家数、上涨占比、中位数、均涨跌幅；领涨领跌各 10。

无成分或无涨跌幅时 `available: false`，并写明原因。

实时表的 `up_count` / `down_count` 放入 `breadth.official_up_count` / `official_down_count`（有则填，无则 `null`），作对照，不替代成分统计。

`sector_contrib` 固定为 `null`。前端不渲染该块。

### 4.5 明确不读的表

单次行业指数分析不得查询：

- `index_historical_quotes`、`index_realtime_quotes`、`index_board_constituents`
- 个股 `historical_quotes`（关位与形态都已持有 bars；RPE/GMS 关闭）

斜率、闸门、资金流不在本接口内触发。

---

## 5. 接口

`GET /api/analysis/industry-index-analysis-bundle`

| 参数 | 说明 |
|------|------|
| `board_code` | 行业板代码，必填 |
| `date` | 可选，`YYYY-MM-DD`。`use_realtime=true` 时忽略，与指数 bundle 一致 |
| `use_realtime` | 默认 false。语义见 §4.2 |

权限：`channel.analyze.tab.industry_index`。

成功时 `data`：

- `index`：`code`（即 board_code）、`name`、`asset_type=industry_index`、现价、涨跌额、涨跌幅、`last_close`、`last_date`
- `trade_date`、`use_realtime`、`realtime`、`bar_count`
- `market_view`、`breadth`、`leaders`
- `sector_contrib: null`
- `levels`、`pattern`、`swing`、`gann`

失败：缺少代码 400；找不到或无日线 404；未捕获异常 500。响应形状与指数 bundle 一致（`success` / `message` / `data`）。

关位回看若指数侧有单独的 `index-levels`，行业本期不单开重算接口。工作台与详情只用 bundle 内的关位结果。KDE/VP 回看控件若现有面板强依赖单独接口，行业面板隐藏该重算入口，避免把行业代码送进 `/api/analysis/index-levels`。

实现文件建议：

- `backend_core/analysis/industry_index_bars.py`
- `backend_core/analysis/industry_index_analysis_bundle.py`
- `backend_api/stock/industry_index_analysis_routes.py`，并在 `backend_api/main.py` 注册

---

## 6. 权限

新增两条，写入 `permission_registry_data.py`：

- `channel.analyze.tab.industry_index`（行业指数分析，level 2，父级 `channel.analyze`）
- `channel.analyze.tab.industry_index.btn.analyze`（行业指数分析执行）

数据脚本 `migrations/add_industry_index_analysis_tab_permission.py`，写法对齐 `migrations/add_index_analysis_tab_permission.py`：`ON CONFLICT` 更新权限行；`standard` / `admin` 保底；把已经拥有 `channel.analyze.tab.index` 的角色复制到新权限。

本次不建表、不加列，不新增 Alembic revision。

---

## 7. 前端

### 7.1 绘制复用

指数分析的绘制写死了 `isa*` 元素 id（`frontend/js/index_analysis.js`）。抽出按前缀绘制的函数（建议 `frontend/js/pa_analysis_view.js`）：环境研判、广度与领涨、波段、形态、关位、江恩、导出根节点。调用方传入前缀和「是否渲染行业贡献」。

- 指数：前缀 `isa`，渲染行业贡献，文案保持现状。
- 行业：前缀 `iia`，不渲染行业贡献。区块标题为「行业环境研判」「成分广度与领涨领跌」。价格行为说明写明「行业指数日线、不复权；实时分析不改写当日 K」。

导出 PNG / PDF 复用指数导出骨架，标题改为「行业指数分析」，文件名含板块代码。PDF 不包含行业贡献段。

### 7.2 分析中心工作台

`frontend/analysis.html` 在「指数分析」旁增加 Tab：

- 按钮文案「行业指数分析」
- `data-tab="industry-index-ai"`
- `data-perm="channel.analyze.tab.industry_index"`

面板内容：

- 可搜索的行业板选择（名称或代码）。选项来自已有 `GET /api/market/industry_board/list`（同花顺来源）。不用四个快选按钮。
- 基准日、分析、实时分析、导出 PDF、导出 PNG。分析按钮权限 `channel.analyze.tab.industry_index.btn.analyze`。
- 空态文案：搜索并选中行业后点击「分析」。
- 结果区顺序：行业环境研判 → 成分广度与领涨领跌 → 价格行为（波段 → 形态 → 关位）→ 江恩。

`frontend/js/analysis.js` 为 `industry-index-ai` 增加脚本加载与初始化，加载价格行为工具脚本（与 `index-ai` 相同的 kde / pattern / market structure / gann）以及行业编排脚本。编排脚本建议 `frontend/js/industry_index_analysis.js`。

深链：

- `tab=industry-index-ai` 且带 `board_code`：跳转 `board_detail.html?board_kind=industry&board_code=&board_code_source=tonghuashun&analyze=1`（保留 `popup=1`）。
- 只有 Tab、没有代码：留在工作台。
- 工作台内选中行业并点击分析：留在本页出结果，不跳转。

### 7.3 板块详情

仅 `board_kind=industry` 挂载分析面板，放在现有斜率区块之后（闸门、斜率、资金流的现有位置不变）。已知板块代码，不再做搜索框。提供分析、实时分析、导出。`analyze=1` 时详情加载完成后自动分析一次。

概念板块详情不挂该面板。

---

## 8. 测试

放在 `test/`。

`test/test_industry_index_analysis_bundle.py`：

- 日 K 来自行业历史表，bar 字段齐全。
- 分析过程不查询 `index_historical_quotes` 与个股 `historical_quotes`（可对 Session.execute 的 SQL 做断言，或对这两处加载函数打补丁并断言未被调用）。
- 有成分时涨跌家数、中位数、领涨领跌条数正确；无成分时广度 `available: false`。
- `market_view` 无 `entry` / `stop` / `target` / `position` / `action` 的非空值；`sector_contrib` 为 `null`；`asset_type` 为 `industry_index`。
- `use_realtime=true` 时不追加、不改写日 K 的开高低收；`realtime.merged` 为 false；锚点现价仍可进入关位结果。
- 无日 K 返回失败。

指数 bundle 现有测试保持通过，确认 `asset_type` 参数默认仍是指数。

---

## 9. 验收时人工看的路径

- 分析中心新 Tab：搜索一个日 K 足够的行业板，分析结果含环境研判和价格行为，没有行业贡献，没有买卖建议。
- 实时分析后，环境研判所依据的 K 线日期仍是最后收盘日，页上能看到「未改写当日 K」。
- 从该 Tab 的深链打开板块详情，自动出现同一板块的分析结果。
- 概念板块详情没有这套面板。
- 现有指数分析 Tab 对 `000001` / `000300` 的结果与改动前一致。
