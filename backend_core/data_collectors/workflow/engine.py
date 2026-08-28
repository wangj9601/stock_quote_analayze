"""采集流程引擎：串行执行、失败策略、重试、取消、强制重启当前环节、DB 状态持久化。"""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
import threading
import time
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

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

# 单测可置 True：节点在同进程同步执行（无法强制 terminate）
_FORCE_SYNC_EXEC = os.getenv("COLLECTION_WORKFLOW_SYNC_NODES", "").strip() in (
    "1",
    "true",
    "yes",
)

# 内存取消标记（跨线程）
_cancel_flags: Dict[str, bool] = {}
_cancel_lock = threading.Lock()

# 重启标记：run_id -> 目标 order_index（None 表示当前正在执行的节点）
_restart_flags: Dict[str, Optional[int]] = {}
_restart_lock = threading.Lock()

# 当前节点子进程：run_id -> (Process, Queue)
_active_procs: Dict[str, Tuple[Any, Any]] = {}
_active_procs_lock = threading.Lock()

# 引擎执行线程：run_id -> Thread（热重载/进程重启后可能消失，需 resume）
_active_threads: Dict[str, threading.Thread] = {}
_active_threads_lock = threading.Lock()


def request_cancel(run_id: str) -> None:
    with _cancel_lock:
        _cancel_flags[run_id] = True
    terminate_run_process(run_id)


def is_cancel_requested(run_id: str) -> bool:
    with _cancel_lock:
        return bool(_cancel_flags.get(run_id))


def clear_cancel(run_id: str) -> None:
    with _cancel_lock:
        _cancel_flags.pop(run_id, None)


def request_restart(run_id: str, order_index: Optional[int] = None) -> None:
    """请求强制重启指定（或当前）节点：立即 terminate 子进程并重跑。"""
    with _restart_lock:
        _restart_flags[run_id] = order_index
    terminated = terminate_run_process(run_id)
    if not terminated:
        logger.info(
            "重启请求已登记但无活跃节点进程 run_id=%s order_index=%s（可能引擎线程已丢失，将尝试恢复）",
            run_id,
            order_index,
        )


def is_restart_requested(run_id: str, order_index: int) -> bool:
    with _restart_lock:
        if run_id not in _restart_flags:
            return False
        target = _restart_flags[run_id]
        return target is None or target == order_index


def consume_restart(run_id: str, order_index: int) -> bool:
    """若存在匹配的重启请求则消费并返回 True。"""
    with _restart_lock:
        if run_id not in _restart_flags:
            return False
        target = _restart_flags[run_id]
        if target is None or target == order_index:
            _restart_flags.pop(run_id, None)
            return True
        return False


def clear_restart(run_id: str) -> None:
    with _restart_lock:
        _restart_flags.pop(run_id, None)


def is_engine_thread_alive(run_id: str) -> bool:
    with _active_threads_lock:
        t = _active_threads.get(run_id)
    return bool(t and t.is_alive())


def _register_engine_thread(run_id: str, thread: threading.Thread) -> None:
    with _active_threads_lock:
        _active_threads[run_id] = thread


def _unregister_engine_thread(run_id: str, thread: Optional[threading.Thread] = None) -> None:
    with _active_threads_lock:
        cur = _active_threads.get(run_id)
        if cur is None:
            return
        if thread is None or cur is thread:
            _active_threads.pop(run_id, None)


def terminate_run_process(run_id: str) -> bool:
    """强制结束该 run 当前节点子进程。"""
    with _active_procs_lock:
        pair = _active_procs.pop(run_id, None)
    if not pair:
        return False
    proc, _q = pair
    try:
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=3)
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=2)
        logger.info("已强制终止节点进程 run_id=%s pid=%s", run_id, getattr(proc, "pid", None))
        return True
    except Exception as e:
        logger.warning("终止节点进程失败 run_id=%s: %s", run_id, e)
        return False


def _persist_restart_order(run: CollectionWorkflowRun, order_index: int) -> None:
    ctx = dict(run.context or {})
    ctx["restart_order_index"] = int(order_index)
    run.context = ctx


def _clear_persisted_restart(run: CollectionWorkflowRun) -> None:
    ctx = dict(run.context or {})
    if "restart_order_index" not in ctx:
        return
    ctx.pop("restart_order_index", None)
    run.context = ctx


def _clear_persisted_restart_from_ctx(ctx_data: Dict[str, Any]) -> None:
    ctx_data.pop("restart_order_index", None)


def _sync_restart_flag_from_db(run: CollectionWorkflowRun) -> None:
    """把 DB 中的重启意图同步到内存（resume 线程启动后可见）。"""
    ctx = run.context or {}
    if "restart_order_index" not in ctx:
        return
    try:
        order = int(ctx["restart_order_index"])
    except (TypeError, ValueError):
        return
    with _restart_lock:
        _restart_flags[run.run_id] = order


def _ctx_to_payload(ctx: WorkflowContext) -> Dict[str, Any]:
    return {
        "run_id": ctx.run_id,
        "workflow_id": ctx.workflow_id,
        "trigger_source": ctx.trigger_source,
        "params": dict(ctx.params or {}),
        "node_params": dict(ctx.node_params or {}),
        "node_outputs": dict(ctx.node_outputs or {}),
        "start_date": ctx.start_date,
        "end_date": ctx.end_date,
        "trade_date": ctx.trade_date.isoformat() if ctx.trade_date else None,
    }


def _payload_to_ctx(payload: Dict[str, Any]) -> WorkflowContext:
    td = payload.get("trade_date")
    trade_date = date.fromisoformat(td) if td else None
    ctx = WorkflowContext(
        run_id=payload["run_id"],
        workflow_id=int(payload["workflow_id"]),
        trigger_source=payload.get("trigger_source") or "manual",
        params=dict(payload.get("params") or {}),
        node_params=dict(payload.get("node_params") or {}),
        node_outputs=dict(payload.get("node_outputs") or {}),
        start_date=payload.get("start_date"),
        end_date=payload.get("end_date"),
        trade_date=trade_date,
    )
    ctx.merge_dates_from_params()
    return ctx


def _node_result_to_dict(result: NodeResult) -> Dict[str, Any]:
    return {
        "success": bool(result.success),
        "skipped": bool(result.skipped),
        "message": result.message or "",
        "error": result.error,
        "data": result.data or {},
    }


def _dict_to_node_result(d: Dict[str, Any]) -> NodeResult:
    return NodeResult(
        success=bool(d.get("success")),
        skipped=bool(d.get("skipped")),
        message=str(d.get("message") or ""),
        error=d.get("error"),
        data=dict(d.get("data") or {}),
    )


def _configure_worker_logging(
    node_key: str,
    run_id: str,
    log_queue: Any = None,
) -> None:
    """
    子进程独立进程空间，不会继承 uvicorn 的 logging 配置；
    未配置时 INFO 业务日志会被丢弃（仅 WARNING+ 走 lastResort）。

    若传入 log_queue，则通过 QueueHandler 把日志回传到父进程（API 终端可见）。
    """
    root = logging.getLogger()
    if getattr(root, "_collection_workflow_worker_configured", False):
        return
    try:
        from logging.handlers import QueueHandler

        from backend_core.logging_utils import resolve_log_file

        fmt = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [wf:%(wf_node)s] - [%(filename)s:%(lineno)d] - %(message)s"
        )

        class _WfFilter(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                if not hasattr(record, "wf_node"):
                    record.wf_node = f"{run_id}/{node_key}"  # type: ignore[attr-defined]
                return True

        handlers: List[logging.Handler] = []
        if log_queue is not None:
            # 回传到父进程，由父进程 handler 输出到 uvicorn 终端 / app.log（避免双写）
            handlers.append(QueueHandler(log_queue))
        else:
            handlers.append(logging.StreamHandler())
            try:
                fh = logging.FileHandler(resolve_log_file("app.log"), encoding="utf-8", mode="a")
                fh.setFormatter(fmt)
                handlers.append(fh)
            except Exception:
                pass

        root.handlers.clear()
        root.setLevel(logging.INFO)
        wf_filter = _WfFilter()
        for h in handlers:
            if not isinstance(h, QueueHandler):
                h.setFormatter(fmt)
            h.addFilter(wf_filter)
            root.addHandler(h)
        root._collection_workflow_worker_configured = True  # type: ignore[attr-defined]
        logging.getLogger(__name__).info(
            "节点子进程日志已就绪 run_id=%s node=%s", run_id, node_key
        )
    except Exception as e:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            force=True,
        )
        logging.getLogger(__name__).warning("节点子进程日志配置降级: %s", e)


def _drain_worker_log_queue(log_queue: Any) -> None:
    """把子进程经 QueueHandler 发来的 LogRecord 交给父进程 logger 输出。"""
    if log_queue is None:
        return
    while True:
        try:
            record = log_queue.get_nowait()
        except Exception:
            break
        if record is None:
            break
        try:
            logging.getLogger(record.name).handle(record)
        except Exception:
            pass


def _process_node_worker(
    node_key: str,
    ctx_payload: Dict[str, Any],
    result_queue,
    log_queue=None,
) -> None:
    """子进程入口：按 node_key 执行注册节点（须为模块级函数以便 Windows spawn）。"""
    try:
        run_id = str((ctx_payload or {}).get("run_id") or "")
        _configure_worker_logging(node_key, run_id, log_queue=log_queue)
        # 触发节点注册表加载
        from backend_core.data_collectors.workflow import node_registry  # noqa: F401

        node_def = get_node(node_key)
        if not node_def:
            result_queue.put(
                {"ok": False, "result": _node_result_to_dict(NodeResult.fail(f"未注册节点: {node_key}"))}
            )
            return
        ctx = _payload_to_ctx(ctx_payload)
        result = node_def.executor(ctx)
        result_queue.put({"ok": True, "result": _node_result_to_dict(result)})
    except Exception as e:
        result_queue.put(
            {"ok": False, "result": _node_result_to_dict(NodeResult.fail(str(e), "节点子进程异常"))}
        )
    finally:
        if log_queue is not None:
            try:
                log_queue.put_nowait(None)
            except Exception:
                pass


def run_executor_interruptible(
    node_key: str,
    ctx: WorkflowContext,
    order_index: int,
) -> NodeResult:
    """
    在独立子进程中执行节点，支持 cancel/restart 时 terminate 强杀。

    单测可设 COLLECTION_WORKFLOW_SYNC_NODES=1 或模块 _FORCE_SYNC_EXEC=True 退回同步执行。
    """
    node_def = get_node(node_key)
    if not node_def:
        return NodeResult.fail(f"未注册节点: {node_key}")

    if _FORCE_SYNC_EXEC:
        try:
            return node_def.executor(ctx)
        except Exception as e:
            logger.exception("节点 %s 同步执行异常", node_key)
            return NodeResult.fail(str(e))

    ctx_payload = _ctx_to_payload(ctx)
    # Windows 默认 spawn；显式使用该上下文
    ctx_mp = mp.get_context("spawn")
    result_queue = ctx_mp.Queue()
    log_queue = ctx_mp.Queue()
    proc = ctx_mp.Process(
        target=_process_node_worker,
        args=(node_key, ctx_payload, result_queue, log_queue),
        name=f"wf-node-{ctx.run_id}-{order_index}",
        # 不可设 daemon：节点内可能再用 ProcessPoolExecutor（如 MA/MAVOL）
        daemon=False,
    )
    with _active_procs_lock:
        # 若仍有旧进程，先清掉
        old = _active_procs.pop(ctx.run_id, None)
        _active_procs[ctx.run_id] = (proc, result_queue)
    if old:
        old_p, _ = old
        try:
            if old_p.is_alive():
                old_p.terminate()
                old_p.join(timeout=2)
        except Exception:
            pass

    proc.start()
    logger.info(
        "节点子进程已启动 run_id=%s node=%s order=%s pid=%s",
        ctx.run_id,
        node_key,
        order_index,
        getattr(proc, "pid", None),
    )
    try:
        while proc.is_alive():
            _drain_worker_log_queue(log_queue)
            if is_cancel_requested(ctx.run_id):
                terminate_run_process(ctx.run_id)
                return NodeResult.fail("cancelled", "已强制取消")
            if is_restart_requested(ctx.run_id, order_index):
                terminate_run_process(ctx.run_id)
                return NodeResult.fail("restart_requested", "已强制停止并请求重启")
            proc.join(timeout=0.4)

        _drain_worker_log_queue(log_queue)

        # 进程已退出：优先识别外部 cancel/restart（terminate 后可能未走进上面的分支）
        if is_cancel_requested(ctx.run_id):
            return NodeResult.fail("cancelled", "已强制取消")
        if is_restart_requested(ctx.run_id, order_index):
            return NodeResult.fail("restart_requested", "已强制停止并请求重启")

        try:
            payload = result_queue.get(timeout=3)
        except Exception:
            return NodeResult.fail("节点进程异常退出且无结果", "节点失败")
        if not isinstance(payload, dict):
            return NodeResult.fail("节点进程返回无效结果", "节点失败")
        return _dict_to_node_result(payload.get("result") or {})
    finally:
        _drain_worker_log_queue(log_queue)
        with _active_procs_lock:
            cur = _active_procs.get(ctx.run_id)
            if cur and cur[0] is proc:
                _active_procs.pop(ctx.run_id, None)
        try:
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=1)
        except Exception:
            pass


class CollectionWorkflowEngine:
    """流程串行执行器。"""

    def _spawn_engine_thread(self, run_id: str) -> bool:
        """若该 run 无存活引擎线程则启动；已存活返回 False。"""
        if is_engine_thread_alive(run_id):
            return False
        t = threading.Thread(
            target=self._run_loop,
            args=(run_id,),
            name=f"workflow-{run_id}",
            daemon=True,
        )
        _register_engine_thread(run_id, t)
        t.start()
        logger.info("已启动/恢复流程引擎线程 run_id=%s", run_id)
        return True

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
                    self._spawn_engine_thread(run_id)
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
        clear_restart(run_id)
        db = SessionLocal()
        try:
            run = db.query(CollectionWorkflowRun).filter(CollectionWorkflowRun.run_id == run_id).first()
            if not run:
                return False
            if run.status in ("completed", "failed", "cancelled", "skipped"):
                return False
            _clear_persisted_restart(run)
            run.status = "cancelled"
            run.error_message = (run.error_message or "") + "（已请求取消）"
            run.finished_at = datetime.now()
            db.commit()
            return True
        finally:
            db.close()

    def restart_node(self, run_id: str, order_index: Optional[int] = None) -> bool:
        """
        强制停止并重启正在运行的环节。

        - order_index 为空：重启 run.current_node_index 对应节点
        - 立刻 terminate 当前节点子进程；若引擎线程已丢失则恢复线程并重跑
        """
        db = SessionLocal()
        try:
            run = db.query(CollectionWorkflowRun).filter(CollectionWorkflowRun.run_id == run_id).first()
            if not run:
                return False
            if run.status not in ("running", "pending"):
                return False

            target = order_index if order_index is not None else run.current_node_index
            if target is None:
                return False

            node_run = (
                db.query(CollectionWorkflowNodeRun)
                .filter(
                    CollectionWorkflowNodeRun.run_id == run_id,
                    CollectionWorkflowNodeRun.order_index == int(target),
                )
                .first()
            )
            if not node_run:
                return False
            # 允许：正在执行；或已标记为当前节点（等待/重试间隙）
            if node_run.status not in ("running", "pending") and run.current_node_index != int(target):
                return False

            # DB + 内存双写，避免热重载后仅内存标记无人消费
            _persist_restart_order(run, int(target))
            node_run.status = "pending"
            node_run.progress = 0
            node_run.error = None
            node_run.result = {}
            node_run.finished_at = None
            node_run.started_at = None
            node_run.message = "已强制停止，即将重跑"
            if run.status == "pending":
                run.status = "running"
            run.current_node_index = int(target)
            run.finished_at = None
            db.commit()

            request_restart(run_id, int(target))

            if not is_engine_thread_alive(run_id):
                ok, kind, existing = mutex_try_acquire("workflow", run_id)
                if not ok and existing != run_id:
                    logger.warning(
                        "恢复引擎失败：互斥占用中 kind=%s existing=%s run_id=%s",
                        kind,
                        existing,
                        run_id,
                    )
                    return False
                self._spawn_engine_thread(run_id)
                logger.info(
                    "引擎线程已丢失，已恢复并强制重跑 run_id=%s order_index=%s",
                    run_id,
                    target,
                )
            else:
                logger.info("已强制重启节点 run_id=%s order_index=%s", run_id, target)
            return True
        finally:
            db.close()

    def _run_loop(self, run_id: str) -> None:
        current_thread = threading.current_thread()
        _register_engine_thread(run_id, current_thread)
        db = SessionLocal()
        try:
            run = db.query(CollectionWorkflowRun).filter(CollectionWorkflowRun.run_id == run_id).first()
            if not run:
                mutex_release(run_id)
                return

            _sync_restart_flag_from_db(run)
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
            # 恢复已完成节点输出（resume 场景）
            for node_cfg in snapshot:
                nk = node_cfg["node_key"]
                prev = (ctx_data.get("node_outputs") or {}).get(nk)
                if prev:
                    ctx.node_outputs[nk] = prev

            for node_cfg in snapshot:
                if is_cancel_requested(run_id):
                    self._mark_run(db, run, "cancelled", "用户取消")
                    break

                order_index = node_cfg["order_index"]
                node_key = node_cfg["node_key"]
                wait_seconds = int(node_cfg.get("wait_seconds") or 0)
                retry_count = int(node_cfg.get("retry_count") or 0)
                on_failure = (node_cfg.get("on_failure") or "stop").lower()

                # 每轮从 DB 拉重启意图（跨线程/恢复后）
                db.refresh(run)
                _sync_restart_flag_from_db(run)

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

                # 已完成节点跳过（除非正请求重启该节点）
                if node_run.status in ("completed", "skipped", "cancelled") and not is_restart_requested(
                    run_id, order_index
                ):
                    if node_key not in ctx.node_outputs:
                        ctx.node_outputs[node_key] = {
                            "success": node_run.status != "cancelled",
                            "skipped": node_run.status == "skipped",
                            "message": node_run.message or "",
                            "data": node_run.result or {},
                        }
                    continue

                run.current_node_index = order_index
                db.commit()

                if wait_seconds > 0:
                    slept = 0
                    while slept < wait_seconds:
                        if is_cancel_requested(run_id):
                            break
                        if is_restart_requested(run_id, order_index):
                            break
                        time.sleep(min(1, wait_seconds - slept))
                        slept += 1

                while True:
                    if is_cancel_requested(run_id):
                        self._mark_run(db, run, "cancelled", "用户取消")
                        break

                    db.refresh(run)
                    _sync_restart_flag_from_db(run)

                    if consume_restart(run_id, order_index):
                        _clear_persisted_restart(run)
                        node_run.status = "pending"
                        node_run.progress = 0
                        node_run.error = None
                        node_run.result = {}
                        node_run.finished_at = None
                        node_run.started_at = None
                        node_run.message = "已强制停止，重新执行"
                        db.commit()
                        logger.info(
                            "重启节点 run_id=%s node=%s order=%s",
                            run_id,
                            node_key,
                            order_index,
                        )

                    result = self._execute_with_retry(
                        db, node_run, ctx, node_cfg, retry_count
                    )

                    db.refresh(run)
                    _sync_restart_flag_from_db(run)
                    if result.error == "restart_requested" or consume_restart(
                        run_id, order_index
                    ):
                        clear_restart(run_id)
                        _clear_persisted_restart(run)
                        node_run.status = "pending"
                        node_run.progress = 0
                        node_run.error = None
                        node_run.result = {}
                        node_run.finished_at = None
                        node_run.started_at = None
                        node_run.message = "已强制停止，重新执行"
                        db.commit()
                        continue

                    ctx.node_outputs[node_key] = {
                        "success": result.success,
                        "skipped": result.skipped,
                        "message": result.message,
                        "data": result.data,
                    }
                    ctx_data = dict(run.context or {})
                    ctx_data["node_outputs"] = ctx.node_outputs
                    _clear_persisted_restart_from_ctx(ctx_data)
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

                if is_cancel_requested(run_id) or run.status != "running":
                    break
            else:
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
            clear_restart(run_id)
            terminate_run_process(run_id)
            mutex_release(run_id)
            _unregister_engine_thread(run_id, current_thread)
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
        order_index = int(node_cfg["order_index"])
        node_def = get_node(node_key)
        attempts = max(0, retry_count) + 1
        last: NodeResult = NodeResult.fail(f"未知节点: {node_key}")

        attempt = 0
        while attempt < attempts:
            if is_cancel_requested(ctx.run_id):
                node_run.status = "cancelled"
                node_run.message = "已取消"
                node_run.finished_at = datetime.now()
                db.commit()
                return NodeResult.fail("cancelled", "已取消")

            # 重试间隙响应重启：从第 0 次 attempt 重来
            if is_restart_requested(ctx.run_id, order_index):
                # 不在此处 consume，留给 _run_loop 统一重置状态后重入
                return NodeResult.fail("restart_requested", "已请求重启")

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
            # 子进程执行，支持 restart/cancel 时 terminate 强杀
            last = run_executor_interruptible(node_key, ctx, order_index)

            if last.error == "cancelled" or is_cancel_requested(ctx.run_id):
                node_run.status = "cancelled"
                node_run.message = "已强制取消"
                node_run.finished_at = datetime.now()
                db.commit()
                return NodeResult.fail("cancelled", "已强制取消")

            if last.error == "restart_requested" or is_restart_requested(
                ctx.run_id, order_index
            ):
                return NodeResult.fail("restart_requested", "已强制停止并请求重启")

            if last.success:
                node_run.status = "skipped" if last.skipped else "completed"
                node_run.progress = 100
                node_run.message = last.message
                node_run.error = None
                node_run.result = last.data or {}
                node_run.finished_at = datetime.now()
                db.commit()
                return last

            attempt += 1
            if attempt < attempts:
                # 退避等待期间也可响应取消/重启
                delay = min(30, 2 ** (attempt - 1))
                slept = 0.0
                while slept < delay:
                    if is_cancel_requested(ctx.run_id) or is_restart_requested(
                        ctx.run_id, order_index
                    ):
                        break
                    time.sleep(min(1.0, delay - slept))
                    slept += 1.0

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
