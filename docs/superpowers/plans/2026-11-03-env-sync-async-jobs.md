# Env Sync Async Jobs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add async Push/Pull jobs that shard exports to `shared/env_sync/{job_id}/` and transfer/import part files, while keeping existing sync pull/push/export/import unchanged.

**Architecture:** DB-backed `env_sync_jobs` + filesystem artifacts; background threads run export→upload/download→import; gateway endpoints authenticate with Sync Key; admin endpoints use JWT. Sync APIs remain for small payloads.

**Tech Stack:** FastAPI, SQLAlchemy, gzip JSON parts, stdlib threading, existing `export_modules`/`import_modules`/`remote_http`.

**Spec:** `docs/superpowers/specs/2026-11-03-env-sync-async-jobs-design.md`

## Global Constraints

- Keep `POST /api/admin/env-sync/pull` and `POST /api/admin/env-sync/push` and gateway `export`/`import` behavior unchanged.
- Artifact root: `ENV_SYNC_ARTIFACT_ROOT` or `/opt/stock_quote/shared/env_sync` or repo `shared/env_sync`.
- No OSS, no Celery in this phase.
- One running job per process direction mutex (409 if busy).
- Never log Sync Key plaintext.
- PostgreSQL production; SQLite in-memory OK for unit tests.

## Review Focus

- Missing Sync Key on part download → 401, no file leaked.
- Second concurrent async push while one running → 409.
- Corrupt/missing part checksum → job failed, no silent skip.
- Oversized date range exceeding `ENV_SYNC_JOB_MAX_PARTS` → 400 before start.
- Sync pull/push still pass existing `test/test_env_sync.py` tests.

---

### Task 1: Model + migration + artifact helpers

**Files:**
- Create: `backend_api/env_sync/artifacts.py`
- Create: `backend_api/env_sync/job_store.py`
- Create: `migrations/add_env_sync_jobs_table.py`
- Modify: `backend_api/models.py` (add `EnvSyncJob`)
- Test: `test/test_env_sync_async_jobs.py`

**Interfaces:**
- Produces: `EnvSyncJob` model; `resolve_artifact_root() -> Path`; `job_dir(job_id) -> Path`; `write_manifest(dir, data)`, `read_manifest(dir)`; `create_job(...)`, `get_job`, `update_job`, `list_jobs`, `claim_running_slot(direction) / release_running_slot`

- [ ] **Step 1: Write failing tests** for `resolve_artifact_root` with env override and for create/get job status pending.

- [ ] **Step 2: Run** `pytest test/test_env_sync_async_jobs.py -v` → expect FAIL (import errors).

- [ ] **Step 3: Implement model, migration, artifacts, job_store.**

- [ ] **Step 4: Run tests → PASS.**

- [ ] **Step 5: Commit** `feat(env-sync): add async job model and artifact helpers`

---

### Task 2: Part writer (per-day export to gzip)

**Files:**
- Create: `backend_api/env_sync/part_io.py`
- Modify: reuse `export_modules` with single-day windows
- Test: `test/test_env_sync_async_jobs.py`

**Interfaces:**
- Produces: `build_export_parts(db, modules, start_date, end_date, dest: Path) -> dict` returns manifest with `parts: [{name, sha256, rows, modules}]`; writes `parts/*.json.gz`

- [ ] **Step 1: Failing test** — export one fake day of strategy configs into tmp dir, manifest has ≥1 part, gunzip JSON has `bundles`.

- [ ] **Step 2: Implement `build_export_parts` + gzip write/read helpers `write_part_json` / `read_part_json` / `sha256_file`.

- [ ] **Step 3: Tests PASS; enforce `ENV_SYNC_JOB_MAX_PARTS` (default 400) raising `ValueError`.**

- [ ] **Step 4: Commit** `feat(env-sync): write gzipped export parts and manifest`

---

### Task 3: Gateway async export + part download + import finalize

**Files:**
- Create: `backend_api/env_sync/job_runner.py` (server-side export thread)
- Modify: `backend_api/env_sync/gateway_routes.py`
- Test: `test/test_env_sync_async_jobs.py`

**Interfaces:**
- Produces gateway:
  - `POST /api/env-sync/v1/jobs/export` → `{job_id, status}`
  - `GET /api/env-sync/v1/jobs/{job_id}`
  - `GET /api/env-sync/v1/jobs/{job_id}/parts/{name}` FileResponse/StreamingResponse
  - `POST /api/env-sync/v1/jobs/import` body multipart or JSON `{job_id?, part_name, bundles, modules}` — if no job_id create import job; save part; **import immediately**
  - Optional `POST /api/env-sync/v1/jobs/{job_id}/finalize-import` no-op or mark succeeded if all parts done

- [ ] **Step 1: Failing API tests** with TestClient + Sync Key header.

- [ ] **Step 2: Implement routes + runner; Auth via `require_env_sync_key`.**

- [ ] **Step 3: Tests PASS (401 without key; export job reaches succeeded with empty/small modules; part download 200).**

- [ ] **Step 4: Commit** `feat(env-sync): gateway async export/import job endpoints`

---

### Task 4: Admin async push/pull jobs

**Files:**
- Modify: `backend_api/env_sync/admin_routes.py`
- Modify: `backend_api/env_sync/job_runner.py` (client push/pull runners)
- Modify: `backend_api/env_sync/remote_http.py` if need binary GET/POST helpers
- Test: `test/test_env_sync_async_jobs.py`

**Interfaces:**
- Produces:
  - `POST /api/admin/env-sync/jobs/push`
  - `POST /api/admin/env-sync/jobs/pull`
  - `GET /api/admin/env-sync/jobs/{job_id}`
  - `GET /api/admin/env-sync/jobs`
  - `POST /api/admin/env-sync/jobs/{job_id}/cancel`
- Push runner: `build_export_parts` locally → upload each part to remote `/jobs/import` → mark done
- Pull runner: create remote export job → poll → download parts → `import_modules` each

- [ ] **Step 1: Failing admin API tests** (mock remote_http).

- [ ] **Step 2: Implement admin routes + runners; keep sync pull/push untouched.**

- [ ] **Step 3: Tests PASS; run `pytest test/test_env_sync.py -v` regression.**

- [ ] **Step 4: Commit** `feat(env-sync): admin async push/pull job APIs`

---

### Task 5: Admin UI

**Files:**
- Modify: `admin/src/services/envSyncApi.ts`
- Modify: `admin/src/views/EnvSyncView.vue`

**Interfaces:**
- Produces: `createAsyncPush`, `createAsyncPull`, `getJob`, poll helper; UI buttons「异步 Pull」「异步 Push」+ progress alert

- [ ] **Step 1: Add API methods and UI controls; poll every 2s until terminal status.**

- [ ] **Step 2: Manual smoke on dev if possible; no build break.**

- [ ] **Step 3: Commit** `feat(admin): env-sync async job buttons and progress`

---

### Task 6: Docs + example env

**Files:**
- Modify: `docs/prod/ubuntu-aliyun-runbook.md` (short § on async env-sync)
- Modify: `scripts/deploy/linux/.env.ubuntu.example` (optional `ENV_SYNC_ARTIFACT_ROOT`, `ENV_SYNC_JOB_MAX_PARTS`, `ENV_SYNC_ARTIFACT_TTL_DAYS`)

- [ ] **Step 1: Document migrate command `python migrations/add_env_sync_jobs_table.py` and async usage.**

- [ ] **Step 2: Commit** `docs: env-sync async jobs runbook notes`
