# 环境同步异步任务（落盘分片）— 设计说明

**日期：** 2026-11-03  
**状态：** 已批准（2026-11-03）  
**范围：** `backend_api/env_sync` + 管理端「环境数据同步」页；不改业务数据语义

---

## 1. 背景与目标

同步 HTTP（`/api/admin/env-sync/pull|push` 与网关 `/api/env-sync/v1/export|import`）在大体量行情/资金流下易触发：

- Nginx `upstream timed out` / 502
- 单次 JSON 过大、进程内存顶满

### 已确认约束

| 项 | 决定 |
|----|------|
| 原同步 Pull/Push | **保留**，行为与接口不变 |
| 存储 | **本机磁盘** `shared/env_sync/`（不做 OSS） |
| 异步范围 | **Push + Pull 一起做** |
| 鉴权 | 继续用现有 Sync Key / 管理端 JWT |

### 成功标准

1. 管理端可创建异步 Push/Pull Job，秒级返回 `job_id`，轮询进度至终态。
2. 大体量模块按**日或按行分片**落盘为 `.json.gz`，单请求体可控（建议单片原始 JSON ≤ 约 20–30MB 或行数受 `ENV_SYNC_PUSH_ROW_CHUNK` 同类限制）。
3. 原 `POST .../pull`、`POST .../push`、网关 `export`/`import` **保持可用**（小数据/测连通）。
4. 失败可在 Job 记录中看到阶段与错误；产物目录可配置 TTL 清理。
5. 单元测试覆盖：Job 状态机、分片写入/读取、鉴权下载。

### 非目标（本轮不做）

- 阿里云 OSS / MinIO / S3
- Celery / Redis / 独立 worker 进程（沿用进程内线程 + DB 状态，与采集任务类似）
- 替换或删除现有同步 Pull/Push
- 改变各 module 的 import/export 业务字段语义

---

## 2. 方案选择

| 方案 | 说明 | 结论 |
|------|------|------|
| A. 仅加长超时 | 不能解决内存与整包 export | 否 |
| B. 仅分页 export，仍同步 HTTP | 浏览器/网关仍可能挂死 | 不足 |
| **C. 异步 Job + 本机落盘分片 + HTTP 传片** | 请求短；传片可重试；兼容旧接口 | **采用** |
| D. 异步 + OSS | 运维更重，非当前两机迁移刚需 | 二期可选 |

---

## 3. 目录与产物

解析根目录（优先级从高到低）：

1. 环境变量 `ENV_SYNC_ARTIFACT_ROOT`
2. 若存在 `/opt/stock_quote/shared` → `/opt/stock_quote/shared/env_sync`
3. 否则仓库相对 `shared/env_sync`（开发机）

单 Job 目录：

```text
{root}/{job_id}/
  manifest.json          # modules、日期、分片列表、checksum、创建时间
  parts/
    0001.quotes.cn.2026-11-01.json.gz
    0002.quotes.cn.2026-11-02.json.gz
    ...
```

- 分片内容：与现网 `import` 兼容的 `{ "bundles": { "<bundle_key>": <SyncBundle> }, "modules": [...] }`（或单 bundle 包装，导入侧规范化）。
- `manifest.json` 含 `parts[].name`、`sha256`、`rows`、`module`、`date`（可选）。
- 默认保留 **7 天**（`ENV_SYNC_ARTIFACT_TTL_DAYS`），Job 成功/失败后可由定时或下次启动时惰性清理。

---

## 4. 数据模型

新表 `env_sync_jobs`（PostgreSQL；测试可用 SQLite）：

| 列 | 类型 | 说明 |
|----|------|------|
| id | UUID/字符串 PK | job_id |
| direction | varchar | `async_push` / `async_pull` / `async_export` / `async_import` |
| status | varchar | 见状态机 |
| modules | JSON | |
| start_date / end_date | varchar null | |
| progress | int 0–100 | |
| stage | varchar | 如 `exporting` / `uploading` / `downloading` / `importing` |
| message | text null | 当前说明 |
| artifact_dir | varchar null | 相对或绝对路径 |
| remote_job_id | varchar null | Pull/Push 对端 Job |
| summary | JSON null | 导入汇总等 |
| error_message | text null | |
| created_by | varchar null | 管理员用户名 |
| created_at / updated_at | timestamptz | |

状态机：

```text
pending → running → (ready) → importing → succeeded
                 ↘ failed
ready：仅「生产侧 async_export 产物已就绪、等待对端下载」时使用；
本机 async_push 可直接 exporting → uploading → succeeded（上传过程中对端边收边导或收齐再导）。
```

推荐 Push 简化态：`pending → running → succeeded|failed`（`stage` 区分子阶段）。  
Pull：`pending → running → succeeded|failed`（本机：请求对端 export job → 轮询 → 下载分片 → 本地 import）。

并发：同方向**同时只跑一个** running Job（与采集 mutex 类似）；其余返回 409。

---

## 5. API

### 5.1 管理端（JWT，前缀 `/api/admin/env-sync`）— 新增

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/jobs/push` | body 同现 `SyncModulesBody`；返回 `{ job_id, status }` |
| POST | `/jobs/pull` | 同上 |
| GET | `/jobs/{job_id}` | 状态、进度、summary/error |
| GET | `/jobs` | 最近 N 条（可选） |
| POST | `/jobs/{job_id}/cancel` | 尽力取消（设标志；运行中检查） |

**保留不变：**  
`GET/POST server-config|client-config`、`POST test-connection`、`POST pull`、`POST push`、`GET modules`。

### 5.2 生产网关（Sync Key，前缀 `/api/env-sync/v1`）— 新增

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/jobs/export` | 创建服务端 export Job（modules + 日期） |
| GET | `/jobs/{job_id}` | 对端查询进度/manifest 摘要 |
| GET | `/jobs/{job_id}/parts/{name}` | 下载分片（Key 鉴权；支持流式） |
| POST | `/jobs/import` | 上传一个分片或完整小包 → 入队/立即写入 parts 并累计；或单接口「finalize」触发导入 |
| POST | `/jobs/{job_id}/finalize-import` | 可选：全部分片收齐后开始导入 |

**保留不变：**  
`GET /health`、`GET /export`、`POST /import`。

### 5.3 Push 时序（旧站 → 新站）

```text
旧站 UI → POST /api/admin/env-sync/jobs/push
       → 后台线程：
            1. 按模块/按日 export → 写本地 parts + manifest
            2. POST 新站 /api/env-sync/v1/jobs/import（先建 remote job 或每片带 job_id）
            3. 逐片上传；遇 502/413 缩小分片重试（复用现有自适应思路）
            4. finalize → 轮询新站 job 至 succeeded/failed
            5. 更新本地 job + audit
```

### 5.4 Pull 时序（本机 ← 生产）

```text
本机 UI → POST /api/admin/env-sync/jobs/pull
       → 后台：
            1. POST 生产 /api/env-sync/v1/jobs/export
            2. 轮询生产 job 至 ready/succeeded（export 完成）
            3. 按 manifest 下载 parts → 本地落盘
            4. 逐片 import_modules
            5. 完成本地 job + audit
```

Nginx：现有 `/api/` `proxy_read_timeout 600s`、`client_max_body_size 200m` 足够传单片；异步创建接口本身应在数秒内返回。

---

## 6. 分片策略

| 数据类型 | 策略 |
|----------|------|
| quotes / fund_flow / adj_factors / board / fina / computed | **优先按交易日** 一片；单日仍过大再按行切（`ENV_SYNC_JOB_ROW_CHUNK`，默认与 push chunk 同级，如 400～2000） |
| strategy / observe / permissions / 小配置 | 可单片或按 bundle 一片 |

导出复用现有 `export_modules` / `market_data.export_*`，但调用方限制日期窗口为单日或多日循环，避免一次 `q.all()` 全区间。

导入复用现有 `import_modules` 与批量 UPSERT；每片独立事务（与现 push 分批一致）。

---

## 7. 管理端 UI

在「环境数据同步」页：

- **保留**「从生产 Pull」「Push 到生产」（同步）。
- **新增**「异步 Pull」「异步 Push」；提交后展示 Job 进度（轮询 `GET /jobs/{id}`，间隔 2s）。
- 文案提示：大体量行情/资金流建议用异步；同步接口适合小模块或短日期。

---

## 8. 安全与运维

- 分片下载/上传均需 Sync Key（网关）或管理员 JWT（管理端）。
- 产物目录仅本机服务账号可写；Nginx **不要**直接静态暴露 `shared/env_sync`。
- 日志：job_id、stage、分片名、远端 status；禁止打印 Sync Key 明文。
- 迁移脚本：`migrations/add_env_sync_jobs_table.py`（或 Alembic，与现有 env_sync 表风格一致）。

---

## 9. 测试计划

| 测试 | 内容 |
|------|------|
| 单元 | manifest 读写、按日切分、job 状态迁移 |
| API | 创建 job → mock export → 下载 part → import；错误路径 401/409 |
| 回归 | 现有 `test/test_env_sync.py` 同步 pull/push/网关仍通过 |
| 手工 | 旧站异步 Push 1～2 日 A 股行情到新站；异步 Pull 小日期回旧站 |

---

## 10. 实施顺序

1. 表 + artifact 目录工具 + Job 存储
2. 网关：`jobs/export`、parts 下载、`jobs/import`+finalize
3. 管理端：`jobs/push`、`jobs/pull`、查询/取消 + 后台 runner
4. 管理端 UI 按钮与进度
5. 测试与手册短文（ubuntu runbook 一小节）

---

## 11. 开放细节（实现时可定默认值）

- 单 Job 最大分片数上限（防误选超长区间）：默认按 `ENV_SYNC_JOB_MAX_PARTS`（如 400）拒绝或自动截断并警告。
- Finalize 是「每片立即 import」还是「收齐再 import」：默认 **每片上传成功即 import**（降低磁盘峰值；失败可记录已导入片便于续传——续传为增强项，第一期失败则整 Job failed，已导入数据保留不自动回滚）。
