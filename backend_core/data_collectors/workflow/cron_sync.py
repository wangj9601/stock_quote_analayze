"""采集流程 cron 热同步：DB 变更后无需重启 core，空闲时自动重注册 APScheduler 任务。

说明：
- 节点列表本身在每次 engine.start 时从 DB 读取，保存后下次运行即生效。
- 本模块负责把「启用/禁用、trigger、cron 时间」同步到 core 进程内的 APScheduler。
- 仅在无 running/pending 流程时重载，避免改调度打断执行中流程。
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Callable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

WORKFLOW_CRON_JOB_PREFIX = "collection_workflow_"
SYNC_JOB_ID = "collection_workflow_cron_sync"

_lock = threading.Lock()
_last_signature: Optional[str] = None


def workflow_job_id(workflow_id: int) -> str:
    return f"{WORKFLOW_CRON_JOB_PREFIX}{int(workflow_id)}"


def has_running_workflow_in_db(db_session_factory: Callable) -> bool:
    """跨进程判定：DB 中是否有未结束流程（pending/running）。"""
    from backend_core.models.collection_workflow import CollectionWorkflowRun

    db = db_session_factory()
    try:
        q = (
            db.query(CollectionWorkflowRun.run_id)
            .filter(CollectionWorkflowRun.status.in_(("pending", "running")))
            .limit(1)
        )
        return q.first() is not None
    finally:
        db.close()


def load_cron_workflow_rows(db_session_factory: Callable) -> List[Any]:
    from backend_core.models.collection_workflow import CollectionWorkflow

    db = db_session_factory()
    try:
        return (
            db.query(CollectionWorkflow)
            .filter(
                CollectionWorkflow.enabled.is_(True),
                CollectionWorkflow.trigger_type == "cron",
            )
            .order_by(CollectionWorkflow.id.asc())
            .all()
        )
    finally:
        db.close()


def build_cron_signature(rows: Sequence[Any]) -> str:
    """用于判断是否需要重注册；含 updated_at，节点保存也会触发同步。"""
    parts: List[str] = []
    for wf in rows:
        updated = wf.updated_at.isoformat(timespec="seconds") if getattr(wf, "updated_at", None) else ""
        parts.append(
            "|".join(
                [
                    str(wf.id),
                    "1" if wf.enabled else "0",
                    str(wf.trigger_type or ""),
                    str(wf.cron_dow or ""),
                    str(wf.cron_hour if wf.cron_hour is not None else ""),
                    str(wf.cron_minute if wf.cron_minute is not None else ""),
                    str(wf.skip_on_holiday or "NONE"),
                    updated,
                ]
            )
        )
    return "\n".join(parts)


def _cron_trigger_kwargs(wf: Any) -> dict:
    kwargs: dict = {"id": workflow_job_id(wf.id)}
    if wf.cron_dow:
        kwargs["day_of_week"] = wf.cron_dow
    if wf.cron_hour is not None and str(wf.cron_hour).strip() != "":
        hour_raw = str(wf.cron_hour).strip()
        if "," in hour_raw:
            kwargs["hour"] = hour_raw
        else:
            try:
                kwargs["hour"] = int(hour_raw)
            except ValueError:
                kwargs["hour"] = hour_raw
    if wf.cron_minute is not None:
        kwargs["minute"] = int(wf.cron_minute)
    return kwargs


def _make_cron_job(workflow_id: int, start_fn: Callable[..., str]) -> Callable[[], None]:
    def _job() -> None:
        try:
            run_id = start_fn(workflow_id, trigger_source="cron", background=True)
            logger.info(
                "[流程定时] 已触发 workflow_id=%s run_id=%s",
                workflow_id,
                run_id,
            )
        except RuntimeError as e:
            logger.warning("[流程定时] workflow_id=%s 跳过: %s", workflow_id, e)
        except Exception as e:
            logger.error("[流程定时] workflow_id=%s 异常: %s", workflow_id, e)

    return _job


def remove_workflow_cron_jobs(scheduler: Any) -> int:
    removed = 0
    for job in list(scheduler.get_jobs()):
        jid = getattr(job, "id", "") or ""
        if jid.startswith(WORKFLOW_CRON_JOB_PREFIX):
            try:
                scheduler.remove_job(jid)
                removed += 1
            except Exception as e:
                logger.warning("移除流程 cron 失败 id=%s: %s", jid, e)
    return removed


def register_workflow_cron_jobs(
    scheduler: Any,
    rows: Sequence[Any],
    *,
    start_fn: Optional[Callable[..., str]] = None,
) -> int:
    """按 DB 行注册 cron jobs，返回注册数量。"""
    if start_fn is None:
        from backend_core.data_collectors.workflow.engine import workflow_engine

        start_fn = workflow_engine.start

    count = 0
    for wf in rows:
        wid = int(wf.id)
        kwargs = _cron_trigger_kwargs(wf)
        # 同 id 已存在则先删，避免 replace_existing 差异
        try:
            if scheduler.get_job(kwargs["id"]):
                scheduler.remove_job(kwargs["id"])
        except Exception:
            pass
        scheduler.add_job(_make_cron_job(wid, start_fn), "cron", **kwargs)
        count += 1
        logger.info(
            "已注册采集流程 cron：id=%s name=%s dow=%s hour=%s minute=%s",
            wid,
            wf.name,
            wf.cron_dow,
            wf.cron_hour,
            wf.cron_minute,
        )
    return count


def reload_workflow_cron_jobs(
    scheduler: Any,
    db_session_factory: Callable,
    *,
    start_fn: Optional[Callable[..., str]] = None,
    force: bool = False,
) -> Tuple[bool, str]:
    """
    从 DB 重载流程 cron。
    返回 (changed, message)。
    force=False 时签名未变则跳过。
    """
    global _last_signature
    rows = load_cron_workflow_rows(db_session_factory)
    signature = build_cron_signature(rows)
    with _lock:
        if not force and signature == _last_signature:
            return False, "unchanged"
        removed = remove_workflow_cron_jobs(scheduler)
        registered = register_workflow_cron_jobs(scheduler, rows, start_fn=start_fn)
        _last_signature = signature
    msg = f"removed={removed} registered={registered}"
    logger.info("采集流程 cron 已热同步：%s", msg)
    return True, msg


def sync_workflow_cron_if_idle(
    scheduler: Any,
    db_session_factory: Callable,
    *,
    start_fn: Optional[Callable[..., str]] = None,
    local_busy_check: Optional[Callable[[], bool]] = None,
) -> Tuple[bool, str]:
    """
    空闲时若 DB 签名变化则热同步。
    - DB 有 pending/running：跳过
    - local_busy_check 为 True（本进程互斥占用）：跳过
    """
    rows = load_cron_workflow_rows(db_session_factory)
    signature = build_cron_signature(rows)
    with _lock:
        if signature == _last_signature:
            return False, "unchanged"

    if has_running_workflow_in_db(db_session_factory):
        logger.info("采集流程配置已变更，但有流程在运行，暂缓 cron 热同步")
        return False, "busy_db"

    if local_busy_check is not None:
        try:
            if local_busy_check():
                logger.info("采集流程配置已变更，但本进程有执行占用，暂缓 cron 热同步")
                return False, "busy_local"
        except Exception as e:
            logger.warning("local_busy_check 异常，继续尝试同步: %s", e)

    return reload_workflow_cron_jobs(
        scheduler,
        db_session_factory,
        start_fn=start_fn,
        force=True,
    )


def get_last_signature() -> Optional[str]:
    with _lock:
        return _last_signature


def reset_sync_state_for_tests() -> None:
    global _last_signature
    with _lock:
        _last_signature = None
