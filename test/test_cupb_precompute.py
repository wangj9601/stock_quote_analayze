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


def test_screen_loads_ohlc_in_configured_batches(monkeypatch):
    """全市场扫描按 scan.batch_size 分批取 K 线，名单与一次装入时相同。"""
    from backend_core.strategies.cup_bottom.config import get_default_cupb_config
    from backend_core.strategies.cup_bottom.strategy_engine import CupbStrategyEngine

    calls = []

    def _load(db, codes, lookback, asof):
        calls.append(list(codes))
        return {
            code: [{"date": "2026-11-18", "high": 2, "low": 1, "close": 1.5, "volume": 10, "name": code}]
            for code in codes
        }

    def _hit(bars, pattern_cfg=None):
        return {"status": "forming", "grade": "B", "last_close": 1.5}

    monkeypatch.setattr(
        "backend_core.strategies.cup_bottom.strategy_engine.batch_load_ohlc_asc",
        _load,
    )
    monkeypatch.setattr(
        "backend_core.strategies.cup_bottom.strategy_engine.load_names",
        lambda db, codes: {code: code for code in codes},
    )
    monkeypatch.setattr(
        "backend_core.strategies.cup_bottom.strategy_engine.detect_cup_bottom",
        _hit,
    )
    monkeypatch.setattr(
        "backend_core.strategies.cup_bottom.strategy_engine.resolve_effective_trade_date",
        lambda db, requested=None: "2026-11-18",
    )
    monkeypatch.setattr(
        "backend_core.strategies.cup_bottom.strategy_engine.resolve_stock_pool",
        lambda db, **kwargs: {
            "codes": ["000003", "000001", "000002"],
            "boards_by_code": {},
            "mode": "market",
            "scope_meta": {"stock_count": 3},
        },
    )
    monkeypatch.setattr(
        "backend_core.strategies.cup_bottom.strategy_engine.enrich_items_with_ths_industry",
        lambda db, items, force=False: None,
    )

    cfg = get_default_cupb_config()
    cfg["scan"]["batch_size"] = 1
    cfg["_config_id"] = 1
    out = CupbStrategyEngine(config=cfg).screen(
        object(),
        stock_pool_mode="market",
        market_scopes=["CN"],
        force_recompute=True,
        max_results=0,
    )
    assert calls == [["000003"], ["000001"], ["000002"]]
    assert out["screened"] == 3
    assert out["computed"] == 3
    assert [row["code"] for row in out["items"]] == ["000001", "000002", "000003"]
    assert out["scope_codes"] == ["000003", "000001", "000002"]


def test_screen_batch_size_env_overrides_config(monkeypatch):
    from backend_core.strategies.cup_bottom.config import get_default_cupb_config
    from backend_core.strategies.cup_bottom.strategy_engine import CupbStrategyEngine

    calls = []

    def _load(db, codes, lookback, asof):
        calls.append(list(codes))
        return {}

    monkeypatch.setenv("CUPB_BARS_BATCH_SIZE", "2")
    monkeypatch.setattr(
        "backend_core.strategies.cup_bottom.strategy_engine.batch_load_ohlc_asc",
        _load,
    )
    monkeypatch.setattr(
        "backend_core.strategies.cup_bottom.strategy_engine.load_names",
        lambda db, codes: {},
    )
    monkeypatch.setattr(
        "backend_core.strategies.cup_bottom.strategy_engine.resolve_effective_trade_date",
        lambda db, requested=None: "2026-11-18",
    )
    monkeypatch.setattr(
        "backend_core.strategies.cup_bottom.strategy_engine.resolve_stock_pool",
        lambda db, **kwargs: {
            "codes": ["000001", "000002", "000003"],
            "boards_by_code": {},
            "mode": "stocks",
            "scope_meta": {},
        },
    )
    cfg = get_default_cupb_config()
    cfg["scan"]["batch_size"] = 50
    cfg["_config_id"] = 1
    out = CupbStrategyEngine(config=cfg).screen(object(), force_recompute=True, max_results=0)
    assert calls == [["000001", "000002"], ["000003"]]
    assert out["hit_count"] == 0


def test_exec_cupb_cn_runs(monkeypatch):
    monkeypatch.setenv("ENABLE_CUPB_PRECOMPUTE", "true")
    monkeypatch.setattr(
        "backend_core.strategies.cup_bottom.scheduled_precompute.scheduled_cupb_signals_cn",
        lambda: None,
    )
    ctx = WorkflowContext(run_id="t", workflow_id=1, trigger_source="manual")
    result = exec_cupb_cn(ctx)
    assert result.success is True
