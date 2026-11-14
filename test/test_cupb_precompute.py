# -*- coding: utf-8 -*-
"""CUPB 日终预计算节点与调度入口。"""

from backend_core.data_collectors.workflow.adapters import exec_cupb_cn
from backend_core.data_collectors.workflow.context import WorkflowContext
from backend_core.data_collectors.workflow.node_registry import get_node


def test_cupb_node_registered():
    node = get_node("cupb_signals_cn")
    assert node is not None
    assert "CUPB" in node.name
    assert node.executor is exec_cupb_cn


def test_scheduled_cupb_calls_market_cn_none(monkeypatch):
    captured = {}

    def _fake(**kwargs):
        captured.update(kwargs)
        return {
            "ok": True,
            "trade_date": "2026-11-14",
            "config_id": 1,
            "hit_count": 2,
            "saved": 2,
            "deleted_stale": 0,
        }

    monkeypatch.setenv("ENABLE_CUPB_PRECOMPUTE", "true")
    monkeypatch.setattr(
        "backend_core.strategies.cup_bottom.scheduled_precompute.run_cupb_precompute",
        _fake,
    )
    import backend_core.strategies.cup_bottom.scheduled_precompute as mod
    from datetime import datetime as real_datetime

    class _FakeDT:
        @staticmethod
        def now():
            return real_datetime(2026, 11, 11, 16, 0, 0)  # Wednesday

    monkeypatch.setattr(mod, "datetime", _FakeDT)
    mod.scheduled_cupb_signals_cn()
    assert captured.get("stock_pool_mode") == "market"
    assert captured.get("market_scopes") == ["CN"]
    assert captured.get("price_adjust") == "none"
    assert captured.get("status_filter") == "both"
    assert captured.get("force_recompute") is True
    assert captured.get("universe_limit") == 0
    assert captured.get("max_results") == 0


def test_scheduled_cupb_respects_enable_flag(monkeypatch):
    called = {"n": 0}

    def _fake(**kwargs):
        called["n"] += 1
        return {"ok": True}

    monkeypatch.setenv("ENABLE_CUPB_PRECOMPUTE", "false")
    monkeypatch.setattr(
        "backend_core.strategies.cup_bottom.scheduled_precompute.run_cupb_precompute",
        _fake,
    )
    import backend_core.strategies.cup_bottom.scheduled_precompute as mod

    class _FakeDT:
        @staticmethod
        def now():
            class _N:
                @staticmethod
                def weekday():
                    return 2

            return _N()

    monkeypatch.setattr(mod, "datetime", _FakeDT)
    mod.scheduled_cupb_signals_cn()
    assert called["n"] == 0


def test_exec_cupb_cn_runs(monkeypatch):
    monkeypatch.setenv("ENABLE_CUPB_PRECOMPUTE", "true")
    monkeypatch.setattr(
        "backend_core.strategies.cup_bottom.scheduled_precompute.scheduled_cupb_signals_cn",
        lambda: None,
    )
    ctx = WorkflowContext(run_id="t", workflow_id=1, trigger_source="manual")
    result = exec_cupb_cn(ctx)
    assert result.success is True
