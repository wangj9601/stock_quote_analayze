# CUPB（带柄杯底）信号计算规则说明

本文档对应管理端「杯底形态策略（CUPB）」与前端形态识别中的 **带柄茶杯**（`cup_with_handle`）。算法依据 O'Neil《股市生财之道》带柄杯底（Cup and Handle）框架实现，并针对 A 股日线数据做了可配置增强。

**代码入口**

| 模块 | 路径 |
|------|------|
| 检测核心 | `backend_core/strategies/cup_bottom/detector.py` → `detect_cup_bottom` |
| 形态工具封装 | `backend_core/analysis/chart_patterns/cup_handle.py` → `detect_cup_with_handle` |
| 默认配置 | `backend_core/strategies/cup_bottom/config.py` → `get_default_cupb_config()` |
| 管理端引擎 | `backend_core/strategies/cup_bottom/strategy_engine.py` |
| 信号落库 | `cupb_signal_trace`（迁移：`migrations/add_cupb_tables.py`） |

---

## 1. 总体流程

1. 按股票池模式解析代码列表（行业 / 概念 / 个股 / 全市场）
2. 批量加载日线 OHLCV（管理端默认**不复权**；前端形态工具可选前复权 `qfq`）
3. 在回看窗内枚举杯身 + 杯柄候选，按规则打分并**重锚**至最近有效结构
4. 校验量价特征，输出等级 `grade`（A/B/C/X）与状态 `forming` / `confirmed` / `invalidated`
5. 试算直接返回；预计算写入 `cupb_signal_trace`

---

## 2. 形态结构定义

### 2.1 五个关键枢轴

| 枢轴 | 默认取价 | 含义 |
|------|----------|------|
| 左沿 `left_rim` | 杯底之前窗口内 **最高价 high** | 杯口左肩 |
| 杯底 `cup_bottom` | 候选索引处 **最低价 low** | U 形底部（非收盘最低点） |
| 右沿 `right_rim` | 杯底之后首次回升至左沿附近的 **最高价 high** | 杯口右肩 |
| 柄低 `handle_low` | 右沿之后柄部区间 **最低价 low** | 柄部洗盘低点 |
| 确认日 `confirm_date` | 柄部结束后首次 **收盘突破杯口** 的交易日 | 突破确认 |

杯口 `rim = max(left_rim, right_rim)`。

### 2.2 杯身（The Cup）

| 规则 | 默认参数 | 说明 |
|------|----------|------|
| 前期上涨趋势 | `prior_trend_min_pct=0.30`，`prior_trend_lookback=120` | 左沿价相对此前 120 日内低点涨幅 ≥30% |
| 杯深 | `cup_depth_min=0.12`，`cup_depth_max=0.45` | 相对左沿高点的回调深度 12%～45% |
| 左右沿对齐 | `rim_rel_tol=0.12` | 右沿高点与左沿高点相对差 ≤12% |
| 杯身时长 | `min_cup_bars=20` | 左沿至右沿至少 20 根 K 线 |
| U 形检验 | `cup_u_shape_required=true` | 底部横盘、左右对称、斜率比合理；**延长基底**可豁免 |
| 破底失效 | `invalidate_on_lower_low=true` | 杯底确立后至右沿/柄部/柄后任一阶段创新低则候选作废 |

**深杯放宽（杯深 >33%）**：柄位下限降至杯深 35% 处、柄回撤相对杯口上限 26%、杯深内柄回撤上限 55%、允许略上倾柄，等级倾向 **C（延长基底）**。

### 2.3 杯柄（The Handle）

| 规则 | 默认参数 | 说明 |
|------|----------|------|
| 柄位 | `handle_floor_frac=0.50` | 柄低不得低于「杯底 + 50%×杯深」（上半区） |
| 柄回撤（相对杯深） | `handle_depth_min=0.05`，`handle_depth_max=0.35` | 深杯时上限放宽至 55% |
| 柄回撤（相对杯口） | `handle_retrace_of_rim_min=0.08`，`handle_retrace_of_rim_max=0.18` | O'Neil 口径 8%～18%；深杯放宽至 26% |
| 柄长 | `min_handle_bars=5`，`max_handle_bars=20` | 约 1～4 周 |
| 柄斜率 | `reject_upward_handle=true` | 柄部收盘回归斜率须 ≤0（深杯豁免） |
| 柄长 < 杯长 | — | 柄部 K 线数须少于杯身 |

### 2.4 候选重锚

对通过几何筛选的候选，按 **柄部结束日 `handle_end_date` 最晚** 优先；且柄后至当前不得跌破杯底价（`lower_low_tol_pct=0.005`）。  
用于避免「第一次探底 + 假柄」被误选，而忽略后续更深的真杯底（典型：**002412** 由 03-23 重锚至 06-29）。

---

## 3. 状态与确认

| 状态 | 条件 |
|------|------|
| `forming` | 柄部已形成，尚未收盘突破杯口（或未满足放量确认）；或曾突破但最新收盘跌回杯口下方 |
| `confirmed` | 最新收盘 > `rim × (1 + confirm_buffer_pct)`（默认 +0.5%） |
| `invalidated` | 收盘跌破柄低；或柄后破杯底；`exclude_invalidated=true` 时不返回 |

**历史确认（与当前 status 独立）**

| 字段 | 说明 |
|------|------|
| `ever_confirmed` | 柄后是否曾收盘突破杯口（含已跌回杯内的情况） |
| `first_confirm_date` | 柄后首次突破杯口的交易日；当前 `forming` 但曾突破时仍有值 |
| `confirm_date` | 仅当当前 `status=confirmed` 时与 `first_confirm_date` 一致；跌回杯内后为 `null` |

可选：`volume.require_volume_confirm=true` 时，无放量突破则维持 `forming`。

---

## 4. 量价评分与等级

配置块 `volume`（默认 `enabled=true`，`require_all=false`）：

| 检查项 | 默认阈值 | 含义 |
|--------|----------|------|
| 杯底缩量 | `vol[bottom] ≤ MA50 × 0.70` | 底部交投干涸 |
| 右侧放量 | 杯底→右沿至少 `3` 日量能 > MA50 | 右侧回升有资金参与 |
| 柄部缩量 | 柄部均量 ≤ MA50 × 0.65` | 柄部洗盘缩量 |
| 突破放量 | 确认日量能 ≥ MA50 × 1.40` | 突破有效性 |

**等级 `grade`**

| 等级 | 条件 |
|------|------|
| **A** | 结构合格，量价四项中 ≥3 项通过 |
| **B** | 结构合格，量价 1～2 项通过 |
| **C** | 延长型/深杯（杯深 >33% 或杯身 ≥60 日等），或量价偏弱 |
| **X** | 失效或结构不合格 |

扫描过滤：`scan.grade_filter` 可设为 `A` / `B` / `C` / `all`（默认 `all`）。

---

## 5. 股票池（分析条件）

| mode | 入参 | 说明 |
|------|------|------|
| `industry_board` | `industry_board_codes[]` | 行业成分并集 |
| `concept_board` | `concept_board_codes[]` | 概念成分并集 |
| `stocks` | `stock_codes[]` | 个股多码 |
| `market` | — | 全市场；支持 `market_scopes`（A股/港股）、`cn_board_segments`（主板/创业板等） |

多板取并集去重；股票池为空时 API 返回 400。

---

## 6. 管理端用法

路径：`/admin/#/cupb-management`（侧栏「形态策略 → 杯底形态」）

1. **策略配置**：新建 / 编辑 `config_params` JSON / 设默认
2. **分析试算 / 预计算**：
   - **试算（利旧入库）**：已有信号复用，仅算缺失代码
   - **强制计算**：全量重算并 upsert
   - **写入预计算**：等同强制计算并入库
3. **信号结果**：按交易日查询；表格含 **等级**、**量价分**；可导出 CSV

API 前缀：`/api/admin/cupb`

---

## 7. 前端形态识别（与管理端对齐）

- 形态族：`cup_handle` → 类型 `cup_with_handle`（带柄茶杯）
- 默认勾选前复权；检测用 **前复权 OHLC**，展示价可按枢轴日回填**同日不复权** OHLC（与管理端数值对齐）
- 算法与管理端共用 `detect_cup_bottom`；`formed_at` = `confirm_date`（已确认时）
- 返回扩展字段：`grade`、`volume_score`、`volume_flags`、`quality_flags`

详见 [形态识别工具.md](../../features/形态识别工具.md)。

---

## 8. 数据表

| 表 | 说明 |
|----|------|
| `cupb_strategy_configs` | 参数版本（`config_params` JSON） |
| `cupb_signal_trace` | 日终信号（`code + trade_date + config_id` 唯一） |

`detail` JSON 存储 `grade`、`volume_score`、`volume_flags`、`quality_flags`、`boards` 等。

---

## 9. 默认配置示例

```json
{
  "pattern": {
    "lookback_days": 160,
    "min_bars": 50,
    "min_cup_bars": 20,
    "min_handle_bars": 5,
    "max_handle_bars": 20,
    "rim_rel_tol": 0.12,
    "cup_depth_min": 0.12,
    "cup_depth_max": 0.45,
    "handle_floor_frac": 0.50,
    "handle_retrace_of_rim_min": 0.08,
    "handle_retrace_of_rim_max": 0.18,
    "use_low_for_bottom": true,
    "use_high_for_rim": true,
    "invalidate_on_lower_low": true,
    "prior_trend_required": true,
    "cup_u_shape_required": true,
    "reject_upward_handle": true,
    "grade_filter": "all"
  },
  "volume": {
    "enabled": true,
    "ma_window": 50,
    "bottom_shrink_ratio": 0.70,
    "handle_shrink_ratio": 0.65,
    "breakout_expand_ratio": 1.40,
    "right_expand_min_days": 3,
    "require_volume_confirm": false,
    "require_all": false
  },
  "scan": {
    "history_bars": 180,
    "status_filter": "both",
    "grade_filter": "all"
  }
}
```

完整默认值以 `get_default_cupb_config()` 为准。

---

## 10. 典型案例：002412（汉森制药）

基准日 2026-08-25，不复权：

| 字段 | 旧算法（收盘启发式） | 现行算法 |
|------|---------------------|----------|
| 杯底日 | 2026-03-23 | **2026-06-29** |
| 杯底价 | 6.07（收盘） | **5.32**（最低） |
| 左沿 | 2026-02-09 / 8.02 | **2026-02-10 / 8.60**（高点） |
| 右沿 | 2026-04-28 | **2026-07-24 / 8.12** |
| 柄低 | 2026-04-30 | **2026-07-31 / 6.51** |
| 确认日 | 2026-08-19 | **2026-08-20** |
| 等级 | — | **C**（延长基底，杯深 38%） |

业务解读：03 月为第一次探底，04 月反弹未成真正右肩；06 月底缩量见真低，7 月放量回升构成右沿与柄部，8 月突破确认。详见 [业务简化版](./CUPB_带柄杯底_业务简化版.md)。

---

## 11. 单测

| 文件 | 内容 |
|------|------|
| `test/test_cupb_detector.py` | 合成杯柄、破底失效 |
| `test/test_cupb_002412.py` | 002412 杯底重锚回归（需 PostgreSQL） |
| `test/test_chart_patterns.py -k cup` | 形态工具封装 |

---

## 12. 参考

- O'Neil 带柄杯底形态要点（业务附件）：`什么是带柄杯底形态？如何识别？.md`
- 形态工具产品说明：[形态识别工具.md](../../features/形态识别工具.md)
- 算法总览 §3.3b：[支撑阻力与形态识别_算法说明.md](../../features/支撑阻力与形态识别_算法说明.md)
