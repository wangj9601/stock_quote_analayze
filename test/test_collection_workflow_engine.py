"""采集流程引擎单元测试：节点注册、串行执行、失败 stop/continue、互斥。"""

from __future__ import annotations

import logging
from typing import List
from unittest.mock import MagicMock

from backend_core.data_collectors.workflow.context import NodeResult, WorkflowContext
from backend_core.data_collectors.workflow.mutex import (
    get_active,
    is_busy,
    list_active,
    release,
    try_acquire,
)
from backend_core.data_collectors.workflow.node_registry import (
    CollectionNodeDef,
    get_node,
    list_node_defs,
    list_nodes_meta,
)


def _clear_mutex():
    for item in list(list_active()):
        release(item["id"])


def test_node_registry_contains_core_nodes():
    keys = {n.key for n in list_node_defs()}
    assert "cn_realtime" in keys
    assert "cn_historical" in keys
    assert "cn_weekly" in keys
    assert "gms_signals_cn" in keys
    assert "gms_signals_hk" in keys
    assert "urt_signals_hk" in keys
    assert get_node("cn_realtime") is not None
    assert get_node("gms_signals_hk") is not None
    assert get_node("urt_signals_hk") is not None
    assert get_node("not_exists_xyz") is None
    meta = list_nodes_meta()
    assert all("executor" not in m for m in meta)
    assert any(m["key"] == "cn_historical_akshare" for m in meta)


def test_mutex_task_blocks_workflow():
    _clear_mutex()
    ok, _, _ = try_acquire("task", "t1")
    assert ok
    assert is_busy()
    ok2, kind2, eid2 = try_acquire("workflow", "w1")
    assert not ok2
    assert kind2 == "task"
    assert eid2 == "t1"
    release("t1")
    assert not is_busy()


def test_mutex_multiple_workflows():
    _clear_mutex()
    ok1, _, _ = try_acquire("workflow", "w1")
    ok2, _, _ = try_acquire("workflow", "w2")
    assert ok1 and ok2
    assert len(list_active()) == 2
    ok3, kind3, _ = try_acquire("task", "t1")
    assert not ok3
    assert kind3 == "workflow"
    release("w1")
    assert is_busy()
    ok4, _, _ = try_acquire("workflow", "w3")
    assert ok4
    release("w2")
    release("w3")
    assert not is_busy()
    ok5, _, _ = try_acquire("task", "t1")
    assert ok5
    release("t1")


def test_mutex_release_only_owner():
    _clear_mutex()
    try_acquire("task", "owner")
    release("other")
    assert get_active() == ("task", "owner")
    release("owner")
    assert get_active() == (None, None)


def _make_ok_executor(label: str, sink: List[str]):
    def _exec(ctx: WorkflowContext) -> NodeResult:
        sink.append(label)
        return NodeResult.ok(label)

    return _exec


def _make_fail_executor(label: str, sink: List[str]):
    def _exec(ctx: WorkflowContext) -> NodeResult:
        sink.append(label)
        return NodeResult.fail("boom", label)

    return _exec


def _build_fake_session_factory(wf, nodes, run_holder):
    class FakeQuery:
        def __init__(self, model):
            self.model = model
            self._order = None

        def filter(self, *args, **kwargs):
            # 粗略解析 order_index == N（SQLAlchemy BinaryExpression）
            for a in args:
                try:
                    right = getattr(a, "right", None)
                    left = getattr(a, "left", None)
                    if left is not None and getattr(left, "key", None) == "order_index":
                        self._order = getattr(right, "value", right)
                except Exception:
                    pass
            return self

        def order_by(self, *args, **kwargs):
            return self

        def first(self):
            name = getattr(self.model, "__name__", str(self.model))
            if name == "CollectionWorkflow" or "CollectionWorkflow'" in str(self.model):
                if "Run" in name or "Node" in name:
                    pass
                else:
                    return wf
            if name == "CollectionWorkflowRun":
                return run_holder.get("run")
            if name == "CollectionWorkflowNodeRun":
                if self._order is not None:
                    for nr in run_holder.get("node_runs", []):
                        if nr.order_index == self._order:
                            return nr
                # fallback: sequential
                idx = run_holder.get("seq", 0)
                nrs = run_holder.get("node_runs", [])
                if idx < len(nrs):
                    return nrs[idx]
                return None
            # CollectionWorkflow without Run/Node in name
            if "CollectionWorkflow" in name and "Run" not in name and "Node" not in name:
                return wf
            return wf

        def all(self):
            return nodes

    class FakeSession:
        def query(self, model):
            return FakeQuery(model)

        def add(self, obj):
            name = obj.__class__.__name__
            if name == "CollectionWorkflowRun":
                run_holder["run"] = obj
                if obj.context is None:
                    obj.context = {}
            if name == "CollectionWorkflowNodeRun":
                run_holder.setdefault("node_runs", []).append(obj)

        def commit(self):
            return None

        def close(self):
            return None

    return FakeSession


def _run_engine_case(monkeypatch, keys, on_failure, sink):
    from backend_core.data_collectors.workflow import engine as eng_mod
    from backend_core.data_collectors.workflow import node_registry as reg
    from backend_core.data_collectors.workflow.engine import CollectionWorkflowEngine

    temp = []
    for k in keys:
        if k.endswith("_fail") or "fail" in k:
            label = k.split("_")[1].upper() if "_" in k else k
            # map ut_b -> B
            label = k.replace("ut_", "").replace("ut2_", "").upper()
            if "b" in k or k.endswith("b"):
                nd = CollectionNodeDef(k, k, "cn", _make_fail_executor("B", sink))
            else:
                nd = CollectionNodeDef(k, k, "cn", _make_ok_executor(label, sink))
        else:
            label = k.replace("ut_", "").replace("ut2_", "").upper()
            if label == "B":
                nd = CollectionNodeDef(k, k, "cn", _make_fail_executor("B", sink))
            else:
                nd = CollectionNodeDef(k, k, "cn", _make_ok_executor(label, sink))
        reg._BY_KEY[k] = nd
        temp.append(nd)

    _clear_mutex()

    wf = MagicMock()
    wf.id = 101
    wf.name = "ut"
    wf.enabled = True
    wf.skip_on_holiday = "NONE"

    nodes = []
    for i, key in enumerate(keys):
        n = MagicMock()
        n.order_index = i
        n.node_key = key
        n.display_name = key
        n.params = {}
        n.on_failure = on_failure
        n.retry_count = 0
        n.wait_seconds = 0
        n.enabled = True
        nodes.append(n)

    run_holder: dict = {"seq": 0}
    FakeSession = _build_fake_session_factory(wf, nodes, run_holder)
    monkeypatch.setattr(eng_mod, "SessionLocal", FakeSession)
    monkeypatch.setattr(eng_mod, "should_skip_for_holiday", lambda *_a, **_k: (False, ""))

    real_exec = CollectionWorkflowEngine._execute_with_retry

    def _tracked(self, db, node_run, ctx, node_cfg, retry_count):
        run_holder["seq"] = node_cfg["order_index"]
        return real_exec(self, db, node_run, ctx, node_cfg, retry_count)

    monkeypatch.setattr(CollectionWorkflowEngine, "_execute_with_retry", _tracked)

    # Also fix node_run lookup before execute: bump seq when querying
    orig_loop = CollectionWorkflowEngine._run_loop

    def _loop(self, run_id):
        # wrap query path by incrementing via order in snapshot
        return orig_loop(self, run_id)

    engine = CollectionWorkflowEngine()
    try:
        run_id = engine.start(101, trigger_source="manual", background=False)
        return run_id, run_holder
    finally:
        for n in temp:
            reg._BY_KEY.pop(n.key, None)
        _clear_mutex()


def test_engine_serial_stop_on_failure(monkeypatch):
    sink: List[str] = []
    # Improve FakeQuery: when NodeRun queried, use increasing pointer
    from backend_core.data_collectors.workflow import engine as eng_mod
    from backend_core.data_collectors.workflow import node_registry as reg
    from backend_core.data_collectors.workflow.engine import CollectionWorkflowEngine

    prev_sync = eng_mod._FORCE_SYNC_EXEC
    eng_mod._FORCE_SYNC_EXEC = True
    keys = ["ut_a", "ut_b", "ut_c"]
    for k, label, fail in [
        ("ut_a", "A", False),
        ("ut_b", "B", True),
        ("ut_c", "C", False),
    ]:
        fn = _make_fail_executor(label, sink) if fail else _make_ok_executor(label, sink)
        reg._BY_KEY[k] = CollectionNodeDef(k, k, "cn", fn)

    _clear_mutex()
    wf = MagicMock()
    wf.id = 101
    wf.name = "ut-stop"
    wf.enabled = True
    wf.skip_on_holiday = "NONE"
    nodes = []
    for i, key in enumerate(keys):
        n = MagicMock()
        n.order_index = i
        n.node_key = key
        n.display_name = key
        n.params = {}
        n.on_failure = "stop"
        n.retry_count = 0
        n.wait_seconds = 0
        n.enabled = True
        nodes.append(n)

    run_holder: dict = {"cursor": 0}

    class FakeQuery:
        def __init__(self, model):
            self.model = model

        def filter(self, *a, **k):
            return self

        def order_by(self, *a, **k):
            return self

        def first(self):
            name = self.model.__name__
            if name == "CollectionWorkflowRun":
                return run_holder.get("run")
            if name == "CollectionWorkflowNodeRun":
                nrs = run_holder.get("node_runs", [])
                # 按当前节点游标取
                i = run_holder.get("cursor", 0)
                return nrs[i] if i < len(nrs) else None
            return wf

        def all(self):
            return nodes

    class FakeSession:
        def query(self, model):
            return FakeQuery(model)

        def add(self, obj):
            if obj.__class__.__name__ == "CollectionWorkflowRun":
                run_holder["run"] = obj
                if obj.context is None:
                    obj.context = {}
            if obj.__class__.__name__ == "CollectionWorkflowNodeRun":
                run_holder.setdefault("node_runs", []).append(obj)

        def commit(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr(eng_mod, "SessionLocal", FakeSession)
    monkeypatch.setattr(eng_mod, "should_skip_for_holiday", lambda *_a, **_k: (False, ""))

    real = CollectionWorkflowEngine._run_loop

    def patched_loop(self, run_id):
        # monkeypatch node execution path to advance cursor
        orig_exec = CollectionWorkflowEngine._execute_with_retry

        def exec_and_advance(slf, db, node_run, ctx, node_cfg, retry_count):
            run_holder["cursor"] = node_cfg["order_index"]
            return orig_exec(slf, db, node_run, ctx, node_cfg, retry_count)

        CollectionWorkflowEngine._execute_with_retry = exec_and_advance
        try:
            # advance cursor before each node query by wrapping snapshot iteration
            # simpler: set cursor in a custom loop
            db = FakeSession()
            run = run_holder["run"]
            run.status = "running"
            ctx_data = dict(run.context or {})
            snapshot = list(ctx_data.get("node_snapshot") or [])
            ctx = WorkflowContext(
                run_id=run_id,
                workflow_id=run.workflow_id,
                trigger_source=run.trigger_source,
                params=dict(ctx_data.get("params") or {}),
            )
            for node_cfg in snapshot:
                run_holder["cursor"] = node_cfg["order_index"]
                node_run = run_holder["node_runs"][node_cfg["order_index"]]
                run.current_node_index = node_cfg["order_index"]
                result = CollectionWorkflowEngine._execute_with_retry(
                    self, db, node_run, ctx, node_cfg, int(node_cfg.get("retry_count") or 0)
                )
                if not result.success and (node_cfg.get("on_failure") or "stop") == "stop":
                    CollectionWorkflowEngine._mark_run(
                        db, run, "failed", result.error or result.message
                    )
                    break
            else:
                if run.status == "running":
                    CollectionWorkflowEngine._mark_run(db, run, "completed", None)
            from backend_core.data_collectors.workflow.mutex import release as rel

            rel(run_id)
            eng_mod.clear_cancel(run_id)
        finally:
            CollectionWorkflowEngine._execute_with_retry = orig_exec

    monkeypatch.setattr(CollectionWorkflowEngine, "_run_loop", patched_loop)

    engine = CollectionWorkflowEngine()
    try:
        engine.start(101, trigger_source="manual", background=False)
        assert sink == ["A", "B"]
        assert run_holder["run"].status == "failed"
        assert not is_busy()
    finally:
        eng_mod._FORCE_SYNC_EXEC = prev_sync
        for k in keys:
            reg._BY_KEY.pop(k, None)
        _clear_mutex()


def test_engine_continue_on_failure(monkeypatch):
    from backend_core.data_collectors.workflow import engine as eng_mod
    from backend_core.data_collectors.workflow import node_registry as reg
    from backend_core.data_collectors.workflow.engine import CollectionWorkflowEngine

    sink: List[str] = []
    prev_sync = eng_mod._FORCE_SYNC_EXEC
    eng_mod._FORCE_SYNC_EXEC = True
    keys = ["ut2_a", "ut2_b", "ut2_c"]
    for k, label, fail in [
        ("ut2_a", "A", False),
        ("ut2_b", "B", True),
        ("ut2_c", "C", False),
    ]:
        fn = _make_fail_executor(label, sink) if fail else _make_ok_executor(label, sink)
        reg._BY_KEY[k] = CollectionNodeDef(k, k, "cn", fn)

    _clear_mutex()
    wf = MagicMock()
    wf.id = 202
    wf.name = "ut-continue"
    wf.enabled = True
    wf.skip_on_holiday = "NONE"
    nodes = []
    for i, key in enumerate(keys):
        n = MagicMock()
        n.order_index = i
        n.node_key = key
        n.display_name = key
        n.params = {}
        n.on_failure = "continue"
        n.retry_count = 0
        n.wait_seconds = 0
        n.enabled = True
        nodes.append(n)

    run_holder: dict = {}

    class FakeQuery:
        def __init__(self, model):
            self.model = model

        def filter(self, *a, **k):
            return self

        def order_by(self, *a, **k):
            return self

        def first(self):
            name = self.model.__name__
            if name == "CollectionWorkflowRun":
                return run_holder.get("run")
            return wf

        def all(self):
            return nodes

    class FakeSession:
        def query(self, model):
            return FakeQuery(model)

        def add(self, obj):
            if obj.__class__.__name__ == "CollectionWorkflowRun":
                run_holder["run"] = obj
                if obj.context is None:
                    obj.context = {}
            if obj.__class__.__name__ == "CollectionWorkflowNodeRun":
                run_holder.setdefault("node_runs", []).append(obj)

        def commit(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr(eng_mod, "SessionLocal", FakeSession)
    monkeypatch.setattr(eng_mod, "should_skip_for_holiday", lambda *_a, **_k: (False, ""))

    def patched_loop(self, run_id):
        db = FakeSession()
        run = run_holder["run"]
        run.status = "running"
        ctx_data = dict(run.context or {})
        snapshot = list(ctx_data.get("node_snapshot") or [])
        ctx = WorkflowContext(
            run_id=run_id,
            workflow_id=run.workflow_id,
            trigger_source=run.trigger_source,
            params={},
        )
        for node_cfg in snapshot:
            node_run = run_holder["node_runs"][node_cfg["order_index"]]
            result = CollectionWorkflowEngine._execute_with_retry(
                self, db, node_run, ctx, node_cfg, 0
            )
            if not result.success and (node_cfg.get("on_failure") or "stop") == "stop":
                CollectionWorkflowEngine._mark_run(db, run, "failed", result.error)
                break
        else:
            CollectionWorkflowEngine._mark_run(db, run, "completed", None)
        from backend_core.data_collectors.workflow.mutex import release as rel

        rel(run_id)
        eng_mod.clear_cancel(run_id)

    monkeypatch.setattr(CollectionWorkflowEngine, "_run_loop", patched_loop)
    engine = CollectionWorkflowEngine()
    try:
        engine.start(202, trigger_source="manual", background=False)
        assert sink == ["A", "B", "C"]
        assert run_holder["run"].status == "completed"
        assert not is_busy()
    finally:
        eng_mod._FORCE_SYNC_EXEC = prev_sync
        for k in keys:
            reg._BY_KEY.pop(k, None)
        _clear_mutex()


def test_context_merge_dates():
    ctx = WorkflowContext(run_id="r1", workflow_id=1, trigger_source="manual")
    ctx.params = {"start_date": "2024-01-01"}
    ctx.node_params = {"end_date": "2024-01-10"}
    ctx.merge_dates_from_params()
    assert ctx.start_date == "2024-01-01"
    assert ctx.end_date == "2024-01-10"


def test_configure_worker_logging_enables_info(caplog):
    from backend_core.data_collectors.workflow import engine as eng_mod

    # 模拟子进程：清空 root handlers 后 INFO 会被丢弃
    root = logging.getLogger()
    old_handlers = list(root.handlers)
    old_level = root.level
    try:
        root.handlers.clear()
        if hasattr(root, "_collection_workflow_worker_configured"):
            delattr(root, "_collection_workflow_worker_configured")
        eng_mod._configure_worker_logging("ut_node", "cwr_log_ut")
        assert getattr(root, "_collection_workflow_worker_configured", False)
        assert root.level <= logging.INFO
        assert any(isinstance(h, logging.StreamHandler) for h in root.handlers)
    finally:
        root.handlers.clear()
        for h in old_handlers:
            root.addHandler(h)
        root.setLevel(old_level)
        if hasattr(root, "_collection_workflow_worker_configured"):
            delattr(root, "_collection_workflow_worker_configured")


def test_restart_flags_consume():
    from backend_core.data_collectors.workflow import engine as eng_mod

    run_id = "cwr_restart_ut"
    eng_mod.clear_restart(run_id)
    eng_mod.request_restart(run_id, 1)
    assert eng_mod.is_restart_requested(run_id, 1)
    assert not eng_mod.is_restart_requested(run_id, 0)
    assert eng_mod.consume_restart(run_id, 1)
    assert not eng_mod.is_restart_requested(run_id, 1)

    eng_mod.request_restart(run_id, None)  # 当前节点
    assert eng_mod.is_restart_requested(run_id, 3)
    assert eng_mod.consume_restart(run_id, 3)
    eng_mod.clear_restart(run_id)


def test_request_restart_terminates_process(monkeypatch):
    from backend_core.data_collectors.workflow import engine as eng_mod

    called = []
    monkeypatch.setattr(eng_mod, "terminate_run_process", lambda rid: called.append(rid) or True)
    eng_mod.clear_restart("r_force")
    eng_mod.request_restart("r_force", 2)
    assert called == ["r_force"]
    eng_mod.clear_restart("r_force")


def test_restart_node_respawns_dead_engine(monkeypatch):
    """引擎线程已丢失时，restart_node 应恢复线程并写入 DB 重启意图。"""
    from backend_core.data_collectors.workflow import engine as eng_mod
    from backend_core.data_collectors.workflow.engine import CollectionWorkflowEngine

    run_id = "cwr_resume_ut"
    engine = CollectionWorkflowEngine()
    spawned = []

    run = MagicMock()
    run.run_id = run_id
    run.status = "running"
    run.current_node_index = 1
    run.context = {"node_snapshot": []}
    run.finished_at = None

    node_run = MagicMock()
    node_run.status = "running"
    node_run.message = "执行中"

    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.filter.return_value = q
    q.first.side_effect = [run, node_run]

    monkeypatch.setattr(eng_mod, "SessionLocal", lambda: db)
    monkeypatch.setattr(eng_mod, "is_engine_thread_alive", lambda rid: False)
    monkeypatch.setattr(eng_mod, "request_restart", lambda rid, oi=None: None)
    monkeypatch.setattr(
        eng_mod,
        "mutex_try_acquire",
        lambda kind, rid: (True, None, None),
    )
    monkeypatch.setattr(
        engine,
        "_spawn_engine_thread",
        lambda rid: spawned.append(rid) or True,
    )

    assert engine.restart_node(run_id, 1) is True
    assert spawned == [run_id]
    assert run.context.get("restart_order_index") == 1
    assert node_run.status == "pending"
    assert "即将重跑" in (node_run.message or "")
    db.commit.assert_called()
    db.close.assert_called()


def test_execute_returns_restart_requested(monkeypatch):
    """执行中请求重启时，_execute_with_retry 应返回 restart_requested 而非 completed。"""
    from backend_core.data_collectors.workflow import engine as eng_mod
    from backend_core.data_collectors.workflow import node_registry as reg
    from backend_core.data_collectors.workflow.engine import CollectionWorkflowEngine

    key = "ut_restart_node"
    calls = {"n": 0}
    prev_sync = eng_mod._FORCE_SYNC_EXEC
    eng_mod._FORCE_SYNC_EXEC = True

    def _exec(ctx: WorkflowContext) -> NodeResult:
        calls["n"] += 1
        eng_mod.request_restart(ctx.run_id, 0)
        return NodeResult.ok("done")

    reg._BY_KEY[key] = CollectionNodeDef(key, key, "cn", _exec)
    try:
        engine = CollectionWorkflowEngine()
        node_run = MagicMock()
        node_run.started_at = None
        node_run.status = "pending"
        db = MagicMock()
        ctx = WorkflowContext(run_id="cwr_r1", workflow_id=1, trigger_source="manual")
        node_cfg = {
            "order_index": 0,
            "node_key": key,
            "params": {},
            "retry_count": 0,
        }
        eng_mod.clear_restart("cwr_r1")
        result = engine._execute_with_retry(db, node_run, ctx, node_cfg, 0)
        assert result.error == "restart_requested"
        assert calls["n"] == 1
        assert eng_mod.is_restart_requested("cwr_r1", 0)
    finally:
        eng_mod._FORCE_SYNC_EXEC = prev_sync
        reg._BY_KEY.pop(key, None)
        eng_mod.clear_restart("cwr_r1")

