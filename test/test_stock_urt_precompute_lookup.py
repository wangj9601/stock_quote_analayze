"""个股分析优先读取 URT 预计算。"""

from backend_core.analysis.stock_multi_strategy import (
    _URT_NEED_REALTIME,
    _lookup_urt_precompute,
)


def test_lookup_urt_precompute_uses_trace_row(monkeypatch):
    monkeypatch.setattr(
        "backend_core.strategies.urt.frontend_interface.URTFrontendInterface._resolve_config_id",
        staticmethod(lambda db, config_id, cm: 1),
    )
    monkeypatch.setattr(
        "backend_core.strategies.urt.trace_store.query_trace_by_code",
        lambda db, **kwargs: [
            {
                "code": "002437",
                "date": "2026-09-17",
                "buy_signal": False,
                "score": 40,
                "score_detail": {"inputs": {}},
            }
        ],
    )
    monkeypatch.setattr(
        "backend_core.strategies.urt.trace_store.get_trace_freshness",
        lambda db, **kwargs: {"need_recompute": False},
    )
    monkeypatch.setattr(
        "backend_core.strategies.urt.signal_detector.hydrate_detail_from_score_detail",
        lambda row: row,
    )

    class _CM:
        pass

    monkeypatch.setattr(
        "backend_core.strategies.urt.config.URTConfigManager",
        _CM,
    )

    row = _lookup_urt_precompute(object(), "002437", "2026-09-17", "CN")
    assert isinstance(row, dict)
    assert row["buy_signal"] is False
    assert row["data_source"] == "urt_signal_trace"
    assert row["from_cache"] is True


def test_lookup_urt_precompute_covered_day_without_row_is_miss(monkeypatch):
    monkeypatch.setattr(
        "backend_core.strategies.urt.frontend_interface.URTFrontendInterface._resolve_config_id",
        staticmethod(lambda db, config_id, cm: 1),
    )
    monkeypatch.setattr(
        "backend_core.strategies.urt.trace_store.query_trace_by_code",
        lambda db, **kwargs: [],
    )
    monkeypatch.setattr(
        "backend_core.strategies.urt.trace_store.dates_ready_for_universe_backtest",
        lambda db, **kwargs: {"2026-09-17"},
    )

    class _CM:
        pass

    monkeypatch.setattr("backend_core.strategies.urt.config.URTConfigManager", _CM)

    assert _lookup_urt_precompute(object(), "002437", "2026-09-17", "CN") is None


def test_lookup_urt_precompute_falls_back_when_uncovered(monkeypatch):
    monkeypatch.setattr(
        "backend_core.strategies.urt.frontend_interface.URTFrontendInterface._resolve_config_id",
        staticmethod(lambda db, config_id, cm: 1),
    )
    monkeypatch.setattr(
        "backend_core.strategies.urt.trace_store.query_trace_by_code",
        lambda db, **kwargs: [],
    )
    monkeypatch.setattr(
        "backend_core.strategies.urt.trace_store.dates_ready_for_universe_backtest",
        lambda db, **kwargs: set(),
    )

    class _CM:
        pass

    monkeypatch.setattr("backend_core.strategies.urt.config.URTConfigManager", _CM)

    assert _lookup_urt_precompute(object(), "002437", "2026-09-17", "CN") is _URT_NEED_REALTIME
