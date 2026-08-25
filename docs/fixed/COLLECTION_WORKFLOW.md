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

## 与单任务采集互斥

流程运行与 `/api/data-collection/*` 单任务共用全局互斥槽，避免并发写库。
