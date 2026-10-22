# LDS 龙头战法 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** 管理端 MVP 策略包 `lds`，编排总龙+板龙，带动性三维 + watch_ready，对齐 BVF 骨架。

**Spec:** `docs/superpowers/specs/2026-10-22-lds-leader-dragon-design.md`  
**Rules:** `docs/strategies/lds/LDS_龙头战法_信号计算规则.md`

## File map

| 文件 | 职责 |
|------|------|
| `backend_core/strategies/lds/detector.py` | 纯函数打分 / 孤板 / watch |
| `backend_core/strategies/lds/strategy_engine.py` | 编排候选 + 扫板 |
| `backend_core/strategies/lds/config.py` | 默认配置与 ConfigManager |
| `backend_core/strategies/lds/signal_storage.py` | upsert/load |
| `backend_core/strategies/lds/scheduled_precompute.py` | 手动预计算 |
| `backend_api/admin/lds_admin_routes.py` | Admin API |
| `backend_api/models.py` | ORM |
| `migrations/add_lds_tables.py` | DDL |
| `admin/...` | 管理页 / 路由 / 菜单 |
| `test/test_lds_detector.py` | 单测 |

## Tasks

- [x] Task 1: detector 纯函数 + 失败单测再实现
- [x] Task 2: config / storage / engine / precompute
- [x] Task 3: models + migration + admin routes + main 挂载
- [x] Task 4: admin 前端页（仿 BVF）
- [x] Task 5: 跑通 pytest；迁移可选手动执行
