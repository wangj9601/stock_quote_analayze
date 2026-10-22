# LDS 龙头战法选股 — 设计规格

> 日期：2026-10-22  
> 状态：已定稿（对话确认 §1～§3 + 方案 1）  
> 实现对照：`docs/strategies/lds/LDS_龙头战法_信号计算规则.md`

## 1. 目标

把 A 股短线「龙头战法」落成管理端选股策略（对齐 BVF MVP）：

- 识别 **市场总龙头** 与 **板块龙头**
- 真龙须具备辨识度、带动性、流动性；**最高板 ≠ 龙头**；孤板妖股剔除
- 身份信号 + 右侧 `watch_ready` 两档
- 编排复用：`market_review.market_leader`、`board_roles`；不重写板内/总龙基础识别

## 2. 非目标（第一版）

用户选股前端、回测、日终定时、跟风推荐、人工改选、实时推送。

## 3. 架构

包名：`backend_core/strategies/lds`  
管理端：`/api/admin/lds` + `/admin/#/lds-management`

```
涨停池 / 主线板 / 股票池
        ↓
候选：总龙(pick_market_leader) + 板龙(board_roles)
        ↓
带动性三维(A跟风/B同步炸板/C角色) → 孤板剔除
        ↓
身份分 → 过线落 identity 信号
        ↓
右侧条件 → watch_ready
        ↓
试算返回 / lds_signal_trace
```

## 4. 信号模型

见规则文档 §信号字段。唯一键：`(code, trade_date, config_id, role, board_code)`。

## 5. 带动性与身份 / 右侧

见规则文档 §带动性、§身份、§右侧。

## 6. 数据与接口

- 表：`lds_strategy_configs`、`lds_signal_trace`
- API：配置 CRUD、trial、precompute/trigger、signals（对齐 BVF）

## 7. 测试

`test/test_lds_detector.py`：孤板剔除、角色、watch_ready、最高板非硬通过。
