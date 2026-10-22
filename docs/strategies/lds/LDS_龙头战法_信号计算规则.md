# LDS（龙头战法）信号计算规则说明

本文档对应管理端「龙头战法（LDS）」MVP。编排复用市场总龙头与板块龙头/中军；本期不对用户选股前端开放，不做回测，不做日终定时预计算。

设计规格：`docs/superpowers/specs/2026-10-22-lds-leader-dragon-design.md`

## 1. 总体流程

1. 解析股票池（行业 / 概念 / 个股 / 全市场），基准日 `T`
2. 加载 `T` 日涨停池；编排 **市场总龙头** 候选（`pick_market_leader`，含备选）
3. 解析板范围：`board_scope=mainline_plus_pool` 时 = 复盘当日主线相关板 ∪ 池内板；对每板取 `board_roles` 龙头
4. 硬过滤：ST、停牌/无量、流通市值 &lt; `min_mv_yi`（默认 30 亿）
5. 对每条候选计算带动性三维 → 孤板剔除 → 身份分 → 右侧 `watch_ready`
6. 试算返回；预计算写入 `lds_signal_trace`

## 2. 角色

| `role` | 含义 | `board_code` |
|--------|------|--------------|
| `market_leader` | 全市场情绪标杆 | 空串 `''`（可在 detail 记主线名） |
| `board_leader` | 单一主线/板块分支龙 | 必填 |

同一 `code` 同日可同时产出总龙与板龙两行。

## 3. 带动性 `drive_score`（0～100）

\[
drive = 0.40 A + 0.35 B + 0.25 C
\]

### 3.1 A 跟风计数（权重 0.40）

同板（概念或行业成分）：

- `zt_n`：当日涨停家数（不含/含自身按实现约定：计数含自身）
- `up_ratio`：上涨家数 / 有效样本

归一（可配）：`zt_n >= follow_zt_full`（默认 3）或 `up_ratio >= follow_up_ratio_full`（默认 0.60）→ A 接近 100；线性插值。

### 3.2 B 同步 / 炸板（权重 0.35）

- 当日：个股涨幅与板成分涨幅中位数同号且板中位 &gt; 0 → 加分；个股大涨而板中位 ≤ 0 → 低分
- 近 `lookback_bomb`（默认 5）日：若该股有炸板/大面代理（振幅大或曾涨停次日大跌），板中位未同步走弱 → **扣分**（孤板嫌疑）

缺板行情时 B 维记 50 并在 reasons 注明「同步样本不足」。

### 3.3 C 板内角色（权重 0.25）

映射 `board_role_score`（0～100）。总龙无单板时：用主线板角色分，若无则用 `market_leader.score` 归一到 0～100。

### 3.4 孤板

`drive_score < lonely_min`（默认 35）→ `is_lonely=true`，**不写入身份信号**。

## 4. 身份分 `identity_score`

\[
identity = 0.35 \times 辨识度 + 0.45 \times drive + 0.20 \times 流动性
\]

- **辨识度**：连板高度分位 + 涨幅/封单代理（总龙可用 market_leader 子项）
- **流动性**：成交额分位或相对板内中位

通过：`identity_score >= identity_min`（默认 55）且非孤板。  
总龙主选 `is_primary=true` 至多 1；备选可落库 `is_primary=false`。板龙每板至多 1～2（跟 board_roles）。

`same_as_height`：是否等于当日最高板（仅展示，不作硬通过）。

## 5. 右侧 `watch_ready`

身份通过后再判（缺数据子项跳过并写 reasons）：

1. `enable_diverge`：近 1～2 日曾分歧（炸板/回撤代理）
2. `enable_inflow`：净流入为正，或量能 ≥ 近 `vol_ma` 日均量 × `vol_ratio`
3. `enable_mainline`：所属板仍在主线/池范围内（总龙：市场连板生态未崩的弱条件可放宽为 true）

全开时默认需启用的子项均通过（跳过的不计入失败）。

## 6. 信号字段（落库 / 返回）

`code, name, trade_date, role, board_code, board_name, identity_score, drive_score, watch_ready, is_lonely, is_primary, same_as_height, identity_reasons, watch_reasons, detail`

### 6.1 按 code 合并（试算 / 入库）

同一 `code` 多板命中合并为一行：

- 主行：总龙优先，否则取身份分最高的板龙
- `board_name`：`主板名（主） · 其他板 · …`
- `watch_ready` / `same_as_height`：任一为真则真
- `detail.boards`：保留各板原始分；`detail.merged_from` 为合并前行数

## 7. 股票池与管理端

与 BVF 相同池模式。路径：`/admin/#/lds-management`，API：`/api/admin/lds`。

## 8. 数据表

- `lds_strategy_configs`
- `lds_signal_trace`  
  唯一：`(code, trade_date, config_id, role, board_code)`

迁移：`migrations/add_lds_tables.py`

## 9. 默认参数

见 `backend_core/strategies/lds/config.py` 中 `get_default_lds_config()`。
