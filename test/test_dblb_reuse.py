# -*- coding: utf-8 -*-
"""DBLB 利旧 / 强制计算。"""

from unittest.mock import MagicMock

from backend_core.strategies.double_bottom.strategy_engine import DblbStrategyEngine


def test_screen_reuses_cached_hits(monkeypatch):
    engine = DblbStrategyEngine(
        config={
            "pattern": {
                "lookback_days": 40,
                "swing_left": 1,
                "swing_right": 1,
                "min_trough_gap_bars": 2,
                "max_trough_gap_bars": 40,
                "trough_tol_pct": 0.05,
                "min_rise_to_neck_pct": 0.02,
                "confirm_close_above": True,
            },
            "scan": {"max_results": 0, "history_bars": 40, "status_filter": "both"},
            "_config_id": 1,
        }
    )

    monkeypatch.setattr(
        "backend_core.strategies.double_bottom.strategy_engine.resolve_effective_trade_date",
        lambda db, d: "2026-08-07",
    )
    monkeypatch.setattr(
        "backend_core.strategies.double_bottom.strategy_engine.resolve_stock_pool",
        lambda *a, **k: {
            "codes": ["000001", "000002"],
            "boards_by_code": {},
            "mode": "stocks",
            "scope_meta": {"stock_pool_mode": "stocks", "stock_count": 2},
        },
    )
    monkeypatch.setattr(
        "backend_core.strategies.double_bottom.signal_storage.load_traces_by_codes",
        lambda *a, **k: {
            "000001": {
                "code": "000001",
                "name": "缓存票",
                "status": "confirmed",
                "confirm_date": "2026-08-01",
                "board_labels": "银行",
                "_from_cache": True,
            }
        },
    )

    detected = []

    def fake_detect(bars, pattern_cfg=None):
        detected.append(True)
        return {
            "status": "forming",
            "l1_date": "2026-07-01",
            "l2_date": "2026-07-20",
            "l1_price": 10,
            "l2_price": 10.1,
            "neckline": 11,
            "neck_date": "2026-07-10",
            "last_close": 10.5,
            "confirm_date": None,
        }

    monkeypatch.setattr(
        "backend_core.strategies.double_bottom.strategy_engine.detect_double_bottom",
        fake_detect,
    )
    monkeypatch.setattr(
        "backend_core.strategies.double_bottom.strategy_engine.batch_load_ohlc_asc",
        lambda *a, **k: {"000002": [{"date": "2026-08-07", "close": 10, "name": "新票"}]},
    )
    monkeypatch.setattr(
        "backend_core.strategies.double_bottom.strategy_engine.load_names",
        lambda *a, **k: {"000002": "新票"},
    )
    monkeypatch.setattr(
        "backend_core.strategies.double_bottom.strategy_engine.enrich_items_with_ths_industry",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "backend_core.strategies.double_bottom.strategy_engine.DblbConfigManager.get_config",
        lambda self, cid: engine.config,
    )
    monkeypatch.setattr(
        "backend_core.strategies.double_bottom.strategy_engine.DblbConfigManager.get_default_config_id",
        lambda self: 1,
    )

    out = engine.screen(
        MagicMock(),
        trade_date="2026-08-07",
        config_id=1,
        stock_pool_mode="stocks",
        stock_codes=["000001", "000002"],
        force_recompute=False,
    )
    assert out["reused"] == 1
    assert out["computed"] == 1
    assert len(detected) == 1
    codes = {r["code"] for r in out["items"]}
    assert codes == {"000001", "000002"}


def test_screen_force_skips_reuse(monkeypatch):
    engine = DblbStrategyEngine(
        config={
            "pattern": {"lookback_days": 40, "swing_left": 1, "swing_right": 1},
            "scan": {"max_results": 0, "history_bars": 40},
            "_config_id": 1,
        }
    )
    monkeypatch.setattr(
        "backend_core.strategies.double_bottom.strategy_engine.resolve_effective_trade_date",
        lambda db, d: "2026-08-07",
    )
    monkeypatch.setattr(
        "backend_core.strategies.double_bottom.strategy_engine.resolve_stock_pool",
        lambda *a, **k: {
            "codes": ["000001"],
            "boards_by_code": {},
            "mode": "stocks",
            "scope_meta": {},
        },
    )

    called = {"reuse": False}

    def boom(*a, **k):
        called["reuse"] = True
        return {}

    monkeypatch.setattr(
        "backend_core.strategies.double_bottom.signal_storage.load_traces_by_codes",
        boom,
    )
    monkeypatch.setattr(
        "backend_core.strategies.double_bottom.strategy_engine.detect_double_bottom",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "backend_core.strategies.double_bottom.strategy_engine.batch_load_ohlc_asc",
        lambda *a, **k: {"000001": [{"date": "2026-08-07", "close": 1}]},
    )
    monkeypatch.setattr(
        "backend_core.strategies.double_bottom.strategy_engine.load_names",
        lambda *a, **k: {},
    )
    monkeypatch.setattr(
        "backend_core.strategies.double_bottom.strategy_engine.enrich_items_with_ths_industry",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "backend_core.strategies.double_bottom.strategy_engine.DblbConfigManager.get_config",
        lambda self, cid: engine.config,
    )

    out = engine.screen(
        MagicMock(),
        config_id=1,
        stock_pool_mode="stocks",
        stock_codes=["000001"],
        force_recompute=True,
    )
    assert called["reuse"] is False
    assert out["force_recompute"] is True
    assert out["computed"] == 1
    assert out["reused"] == 0
