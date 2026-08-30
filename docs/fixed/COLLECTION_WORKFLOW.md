# 采集流程自动化

## 概述

将分散的采集/聚合/预计算步骤注册为可编排节点，支持管理端定义串行流程，一次手动启动或单一 cron 触发整条链。

## 启用步骤

1. 执行迁移：

```bash
python migrations/add_collection_workflow_tables.py
```

2. 重启 `backend_api` 与（如使用定时流程）`start_backend_core.py`。

3. 管理端打开 **采集流程**（`/collection-workflows`），编辑预置「A股收盘后标准流程」或新建流程。

4. 切换到流程级定时、停用分散 cron（可选）：

```env
ENABLE_LEGACY_COLLECTION_CRON=false
```

流程的 cron 变更后需重启 `start_backend_core.py` 才会重新注册。

## API

前缀：`/api/admin/collection-workflows`（与管理端 `apiService` 的 baseURL `/api/admin` 一致）

- `GET /nodes` 节点库
- CRUD `/`、`/{id}`、`/{id}/nodes`
- `POST /{id}/run` 手动启动
- `GET /runs`、`GET /runs/{run_id}`、`POST /runs/{run_id}/cancel`
- `POST /runs/{run_id}/restart-node` 重启正在运行的环节（body 可选 `order_index`；省略则重启当前节点）

### 重启环节说明

- 仅当流程状态为 `running` / `pending`，且目标节点为 `running`（或等于 `current_node_index`）时可重启。
- **强制停止**：节点在独立子进程中执行；点击重启会对子进程 `terminate`/`kill`，然后立即重跑该节点并继续后续环节。
- **引擎恢复**：若 API 热重载/进程重启导致引擎线程丢失，强制重启会写入 DB 意图并重新拉起执行线程（跳过已完成节点，从目标节点重跑）。
- **子进程日志**：节点业务日志经 Queue 回传到 API 进程（uvicorn 终端可见），并写入 `logs/app.log`，带 `[wf:run_id/node_key]` 前缀。IDE 若只盯父进程输出，旧行为下会误以为「没日志」——可直接看 `logs/app.log`。
- **非 daemon 子进程**：节点进程必须 `daemon=False`，否则内部 `ProcessPoolExecutor`（如批量 MA/MAVOL）会报 `daemonic processes are not allowed to have children`。
- 与「取消整条流程」不同：重启不结束 run，只强杀并重做当前环节。
- 单测可用环境变量 `COLLECTION_WORKFLOW_SYNC_NODES=1` 退回同进程同步执行（无法强杀）。

## 与单任务采集互斥

- **多个采集流程**可并行运行（每个流程占用独立 execution 槽）。
- **单任务采集**（`/api/data-collection/*`）仍全局独占：不能与任何流程或其它单任务并发，避免写库冲突。
- 流程运行期间无法从管理端启动单任务采集；单任务运行期间无法启动流程。

`GET /active-execution` 返回 `active` 数组与 `active_count`，便于监控并发流程。

## 预置「A股收盘后标准流程」要点

推荐顺序（节选）：

1. … `cn_historical`（日 K；内部算 MA/RSI 等）
2. … 周期 K / 指数 / `cn_industry_board`
3. **`rs_rating_cn`**：A 股相对强度 RS Rating 全市场预计算  
   - 输入：不复权日 K + 库内 `stock_adj_factor` → **前复权**现算 ROC  
   - 输出：截面百分位写入 `rs_ratings`  
   - 建议：**每个交易日收盘链路跑一次**；休市跳过；改算法/补因子后需重跑  
4. `gms_signals_cn` → `urt_signals_cn`

新增 RS 节点迁移：

```bash
python migrations/add_rs_ratings_table.py
python migrations/add_rs_rating_workflow_node.py
```

说明见 [`docs/indicators/股价相对强度_RS_Rating.md`](../indicators/股价相对强度_RS_Rating.md)。已有库若流程里尚无该节点，跑第二条迁移即可插入到 `cn_industry_board` 之后。
