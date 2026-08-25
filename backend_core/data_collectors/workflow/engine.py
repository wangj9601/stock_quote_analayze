"""采集流程引擎：串行执行、失败策略、重试、取消、DB 状态持久化。"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from backend_core.data_collectors.workflow.context import NodeResult, WorkflowContext
from backend_core.data_collectors.workflow.mutex import release as mutex_release
from backend_core.data_collectors.workflow.mutex import try_acquire as mutex_try_acquire
from backend_core.data_collectors.workflow.node_registry import get_node
from backend_core.data_collectors.workflow.session_guard import should_skip_for_holiday
from backend_core.database.db import SessionLocal
from backend_core.models.collection_workflow import (
    CollectionWorkflow,
    CollectionWorkflowNode,
    CollectionWorkflowNodeRun,
    CollectionWorkflowRun,
)

logger = logging.getLogger(__name__)

# 内存取消标记（跨线程）
_cancel_flags: Dict[str, bool] = {}
_cancel_lock = threading.Lock()


def request_cancel(run_id: str) -> None:
    with _cancel_lock:
        _cancel_flags[run_id] = True


def is_cancel_requested(run_id: str) -> bool:
    with _cancel_lock:
        return bool(_cancel_flags.get(run_id))


def clear_cancel(run_id: str) -> None:
    with _cancel_lock:
        _cancel_flags.pop(run_id, None)


class CollectionWorkflowEngine:
    """流程串行执行器。"""

    def start(
        self,
        workflow_id: int,
        trigger_source: str = "manual",
        override_params: Optional[Dict[str, Any]] = None,
        *,
        background: bool = True,
    ) -> str:
        """
        创建运行实例并启动执行。
        返回 run_id；若互斥失败抛出 RuntimeError。
        """
        db = SessionLocal()
        try:
            wf = db.query(CollectionWorkflow).filter(CollectionWorkflow.id == workflow_id).first()
            if not wf:
                raise ValueError(f"流程不存在: {workflow_id}")
            if not wf.enabled and trigger_source == "cron":
                raise RuntimeError(f"流程已禁用，跳过 cron 触发: {workflow_id}")

            nodes = (
                db.query(CollectionWorkflowNode)
                .filter(
                    CollectionWorkflowNode.workflow_id == workflow_id,
                    CollectionWorkflowNode.enabled.is_(True),
                )
                .order_by(CollectionWorkflowNode.order_index.asc())
                .all()
            )
            if not nodes:
                raise ValueError("流程没有启用的节点")

            run_id = f"cwr_{uuid.uuid4().hex[:16]}"
            ok, kind, existing = mutex_try_acquire("workflow", run_id)
            if not ok:
                raise RuntimeError(f"已有执行占用中: {kind}={existing}")

            try:
                # 休市整条跳过
                skip, skip_msg = should_skip_for_holiday(wf.skip_on_holiday or "NONE")
                ctx = WorkflowContext(
                    run_id=run_id,
                    workflow_id=workflow_id,
                    trigger_source=trigger_source,
                    params=dict(override_params or {}),
                )
                ctx.merge_dates_from_params()

                run = CollectionWorkflowRun(
                    run_id=run_id,
                    workflow_id=workflow_id,
                    workflow_name=wf.name,
                    status="skipped" if skip else "pending",
                    trigger_source=trigger_source,
                    current_node_index=None,
                    started_at=datetime.now(),
                    finished_at=datetime.now() if skip else None,
                    error_message=skip_msg if skip else None,
                    context=ctx.to_dict(),
                )
                db.add(run)

                for n in nodes:
                    nr = CollectionWorkflowNodeRun(
                        run_id=run_id,
                        node_key=n.node_key,
                        order_index=n.order_index,
                        status="skipped" if skip else "pending",
                        message=skip_msg if skip else None,
                        finished_at=datetime.now() if skip else None,
                    )
                    db.add(nr)

                node_snapshot = [
                    {
                        "order_index": n.order_index,
                        "node_key": n.node_key,
                        "display_name": n.display_name,
                        "params": n.params or {},
                        "on_failure": n.on_failure or "stop",
                        "retry_count": int(n.retry_count or 0),
                        "wait_seconds": int(n.wait_seconds or 0),
                    }
                    for n in nodes
                ]
                ctx_dict = ctx.to_dict()
                ctx_dict["node_snapshot"] = node_snapshot
                run.context = ctx_dict
                db.commit()

                if skip:
                    mutex_release(run_id)
                    return run_id

                if background:
                    t = threading.Thread(
                        target=self._run_loop,
                        args=(run_id,),
                        name=f"workflow-{run_id}",
                        daemon=True,
                    )
                    t.start()
                else:
                    self._run_loop(run_id)
                return run_id
            except Exception:
                mutex_release(run_id)
                raise
        finally:
            db.close()

    def cancel(self, run_id: str) -> bool:
        request_cancel(run_id)
        db = SessionLocal()
        try:
            run = db.query(CollectionWorkflowRun).filter(CollectionWorkflowRun.run_id == run_id).first()
            if not run:
                return False
            if run.status in ("completed", "failed", "cancelled", "skipped"):
                return False
            run.status = "cancelled"
            run.error_message = (run.error_message or "") + "（已请求取消）"
            run.finished_at = datetime.now()
            db.commit()
            return True
        finally:
            db.close()

    def _run_loop(self, run_id: str) -> None:
        db = SessionLocal()
        try:
            run = db.query(CollectionWorkflowRun).filter(CollectionWorkflowRun.run_id == run_id).first()
            if not run:
                mutex_release(run_id)
                return

            run.status = "running"
            db.commit()

            ctx_data = dict(run.context or {})
            snapshot: List[Dict[str, Any]] = list(ctx_data.get("node_snapshot") or [])
            ctx = WorkflowContext(
                run_id=run_id,
                workflow_id=run.workflow_id,
                trigger_source=run.trigger_source,
                params=dict(ctx_data.get("params") or {}),
                start_date=ctx_data.get("start_date"),
                end_date=ctx_data.get("end_date"),
            )
            ctx.merge_dates_from_params()

            for node_cfg in snapshot:
                if is_cancel_requested(run_id):
                    self._mark_run(db, run, "cancelled", "用户取消")
                    break

                order_index = node_cfg["order_index"]
                node_key = node_cfg["node_key"]
                wait_seconds = int(node_cfg.get("wait_seconds") or 0)
                retry_count = int(node_cfg.get("retry_count") or 0)
                on_failure = (node_cfg.get("on_failure") or "stop").lower()

                node_run = (
                    db.query(CollectionWorkflowNodeRun)
                    .filter(
                        CollectionWorkflowNodeRun.run_id == run_id,
                        CollectionWorkflowNodeRun.order_index == order_index,
                    )
                    .first()
                )
                if not node_run:
                    continue

                run.current_node_index = order_index
                db.commit()

                if wait_seconds > 0:
                    time.sleep(wait_seconds)

                result = self._execute_with_retry(
                    db, node_run, ctx, node_cfg, retry_count
                )
                ctx.node_outputs[node_key] = {
                    "success": result.success,
                    "skipped": result.skipped,
                    "message": result.message,
                    "data": result.data,
                }
                ctx_data["node_outputs"] = ctx.node_outputs
                run.context = ctx_data
                db.commit()

                if not result.success and on_failure == "stop":
                    self._mark_run(
                        db,
                        run,
                        "failed",
                        result.error or result.message or f"节点 {node_key} 失败",
                    )
                    break
            else:
                # 正常走完所有节点
                if run.status == "running":
                    self._mark_run(db, run, "completed", None)
        except Exception as e:
            logger.exception("流程 run_id=%s 异常", run_id)
            try:
                run = db.query(CollectionWorkflowRun).filter(CollectionWorkflowRun.run_id == run_id).first()
                if run and run.status == "running":
                    self._mark_run(db, run, "failed", str(e))
            except Exception:
                pass
        finally:
            clear_cancel(run_id)
            mutex_release(run_id)
            db.close()

    def _execute_with_retry(
        self,
        db: Session,
        node_run: CollectionWorkflowNodeRun,
        ctx: WorkflowContext,
        node_cfg: Dict[str, Any],
        retry_count: int,
    ) -> NodeResult:
        node_key = node_cfg["node_key"]
        node_def = get_node(node_key)
        attempts = max(0, retry_count) + 1
        last: NodeResult = NodeResult.fail(f"未知节点: {node_key}")

        for attempt in range(attempts):
            if is_cancel_requested(ctx.run_id):
                node_run.status = "cancelled"
                node_run.message = "已取消"
                node_run.finished_at = datetime.now()
                db.commit()
                return NodeResult.fail("cancelled", "已取消")

            node_run.status = "running"
            node_run.started_at = node_run.started_at or datetime.now()
            node_run.message = f"执行中 (attempt {attempt + 1}/{attempts})"
            node_run.progress = 0
            db.commit()

            if not node_def:
                last = NodeResult.fail(f"未注册节点: {node_key}")
                break

            ctx.node_params = dict(node_cfg.get("params") or {})
            ctx.merge_dates_from_params()
            try:
                last = node_def.executor(ctx)
            except Exception as e:
                logger.exception("节点 %s 抛出异常", node_key)
                last = NodeResult.fail(str(e))

            if last.success:
                node_run.status = "skipped" if last.skipped else "completed"
                node_run.progress = 100
                node_run.message = last.message
                node_run.error = None
                node_run.result = last.data or {}
                node_run.finished_at = datetime.now()
                db.commit()
                return last

            if attempt < attempts - 1:
                time.sleep(min(30, 2 ** attempt))

        node_run.status = "failed"
        node_run.message = last.message
        node_run.error = last.error
        node_run.result = last.data or {}
        node_run.finished_at = datetime.now()
        db.commit()
        return last

    @staticmethod
    def _mark_run(
        db: Session,
        run: CollectionWorkflowRun,
        status: str,
        error_message: Optional[str],
    ) -> None:
        run.status = status
        if error_message:
            run.error_message = error_message
        run.finished_at = datetime.now()
        db.commit()


# 单例便于 API / cron 共用
workflow_engine = CollectionWorkflowEngine()
