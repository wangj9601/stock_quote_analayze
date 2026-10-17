# -*- coding: utf-8 -*-
"""CSB 选股入口：优先读预计算；全市场现算默认关闭，需显式开启。"""

from unittest.mock import MagicMock, patch

from backend_core.strategies.csb.frontend_interface import CSBFrontendInterface
from backend_core.strategies.csb.trace_store import marker_covers_universe_request


def test_full_market_scope_marker_ready_even_if_candidates_low():
    assert marker_covers_universe_request(
        {"scope": "full_market", "candidates": 10, "hits": 0},
        want_pool=False,
        min_full_market_codes=500,
    )


def test_screen_trace_only_empty_sets_need_precompute():
    db = MagicMock()
    with patch.object(CSBFrontendInterface, "_resolve_config_id", return_value=1), patch(
        "backend_core.strategies.csb.frontend_interface.CSBConfigManager"
    ) as CM, patch(
        "backend_core.strategies.csb.frontend_interface.CSBDataLoader"
    ) as Loader, patch(
        "backend_core.strategies.csb.frontend_interface.query_buy_signals_for_date",
        return_value=[],
    ), patch(
        "backend_core.strategies.csb.frontend_interface.dates_ready_for_universe_backtest",
        return_value=set(),
    ):
        CM.return_value.get_config.return_value = {"min_score": 60}
        CM.return_value.merge_overrides.return_value = {"min_score": 60}
        Loader.return_value.resolve_effective_trade_date.return_value = "2026-07-28"
        Loader.return_value.is_trading_day.return_value = True
        out = CSBFrontendInterface.screen(
            db,
            screening_date="2026-07-28",
            config_id=1,
            trace_only=True,
            prefer_cache=True,
        )
    assert out.get("need_precompute") is True
    assert out.get("source") == "empty_trace"


def test_screen_full_market_realtime_denied_by_default():
    """默认关闭全市场现算：无缓存时快速返回 need_precompute，不启动现算。"""
    db = MagicMock()
    with patch.object(CSBFrontendInterface, "_resolve_config_id", return_value=1), patch(
        "backend_core.strategies.csb.frontend_interface.CSBConfigManager"
    ) as CM, patch(
        "backend_core.strategies.csb.frontend_interface.CSBDataLoader"
    ) as Loader, patch(
        "backend_core.strategies.csb.frontend_interface.CSBStrategyEngine"
    ) as Eng, patch(
        "backend_core.strategies.csb.frontend_interface.query_buy_signals_for_date",
        return_value=[],
    ), patch(
        "backend_core.strategies.csb.frontend_interface.dates_ready_for_universe_backtest",
        return_value=set(),
    ), patch.dict(
        "os.environ", {"CSB_ALLOW_FULL_MARKET_REALTIME": "0"}, clear=False
    ):
        CM.return_value.get_config.return_value = {"min_score": 60}
        Loader.return_value.resolve_effective_trade_date.return_value = "2026-07-28"
        Loader.return_value.is_trading_day.return_value = True
        out = CSBFrontendInterface.screen(
            db,
            screening_date="2026-07-28",
            config_id=1,
            trace_only=False,
            prefer_cache=True,
        )

    assert out.get("need_precompute") is True
    assert out.get("source") == "empty_trace"
    assert "CSB_ALLOW_FULL_MARKET_REALTIME" in (out.get("message") or "")
    Eng.assert_not_called()


def test_screen_live_full_market_persists_trace():
    db = MagicMock()
    hits = [
        {
            "code": "000001",
            "name": "测试",
            "signal_date": "2026-07-28",
            "signal_type": "CSB_PROBE",
            "entry_signal": True,
            "score": 70,
        }
    ]
    with patch.object(CSBFrontendInterface, "_resolve_config_id", return_value=1), patch(
        "backend_core.strategies.csb.frontend_interface.CSBConfigManager"
    ) as CM, patch(
        "backend_core.strategies.csb.frontend_interface.CSBDataLoader"
    ) as Loader, patch(
        "backend_core.strategies.csb.frontend_interface.CSBStrategyEngine"
    ) as Eng, patch(
        "backend_core.strategies.csb.frontend_interface.query_buy_signals_for_date",
        return_value=[],
    ), patch(
        "backend_core.strategies.csb.frontend_interface.dates_ready_for_universe_backtest",
        return_value=set(),
    ), patch(
        "backend_core.strategies.csb.frontend_interface.upsert_trace_rows"
    ) as upsert, patch(
        "backend_core.strategies.csb.frontend_interface.mark_date_scanned"
    ) as mark, patch.dict(
        "os.environ", {"CSB_ALLOW_FULL_MARKET_REALTIME": "1"}, clear=False
    ):
        CM.return_value.get_config.return_value = {"min_score": 60}
        loader = Loader.return_value
        loader.resolve_effective_trade_date.return_value = "2026-07-28"
        loader.is_trading_day.return_value = True
        loader.list_a_share_candidates.return_value = [("000001", "测试")]
        Eng.return_value.screen.return_value = hits

        out = CSBFrontendInterface.screen(
            db,
            screening_date="2026-07-28",
            config_id=1,
            trace_only=False,
            prefer_cache=True,
            persist_realtime=True,
        )

    assert out.get("need_precompute") is not True
    assert out.get("total") == 1
    assert "realtime" in str(out.get("source") or "")
    upsert.assert_called_once()
    mark.assert_called_once()
    extra = mark.call_args.kwargs.get("extra") or {}
    assert extra.get("scope") == "full_market"


def test_screen_date_ready_zero_hits_not_need_precompute():
    db = MagicMock()
    with patch.object(CSBFrontendInterface, "_resolve_config_id", return_value=1), patch(
        "backend_core.strategies.csb.frontend_interface.CSBConfigManager"
    ) as CM, patch(
        "backend_core.strategies.csb.frontend_interface.CSBDataLoader"
    ) as Loader, patch(
        "backend_core.strategies.csb.frontend_interface.query_buy_signals_for_date",
        return_value=[],
    ), patch(
        "backend_core.strategies.csb.frontend_interface.dates_ready_for_universe_backtest",
        return_value={"2026-07-28"},
    ):
        CM.return_value.get_config.return_value = {"min_score": 60}
        Loader.return_value.resolve_effective_trade_date.return_value = "2026-07-28"
        Loader.return_value.is_trading_day.return_value = True
        out = CSBFrontendInterface.screen(
            db,
            screening_date="2026-07-28",
            config_id=1,
            trace_only=True,
            prefer_cache=True,
        )
    assert out.get("need_precompute") is False
    assert out.get("source") == "csb_signal_trace"
    assert out.get("total") == 0
    assert "无符合条件" in (out.get("message") or "")


def test_screen_trace_only_without_entry_filter_keeps_entry_rows():
    """未勾选仅入场时仍读预计算，已有入场信号不能被当成「暂无预计算」。"""
    db = MagicMock()
    probe = {
        "code": "600449",
        "name": "宁夏建材",
        "signal_type": "CSB_PROBE",
        "entry_signal": True,
        "score": 70,
    }
    with patch.object(CSBFrontendInterface, "_resolve_config_id", return_value=1), patch(
        "backend_core.strategies.csb.frontend_interface.CSBConfigManager"
    ) as CM, patch(
        "backend_core.strategies.csb.frontend_interface.CSBDataLoader"
    ) as Loader, patch(
        "backend_core.strategies.csb.frontend_interface.query_buy_signals_for_date",
        return_value=[probe],
    ) as query_cache, patch(
        "backend_core.strategies.csb.frontend_interface.dates_ready_for_universe_backtest",
        return_value={"2026-10-09"},
    ):
        CM.return_value.get_config.return_value = {"min_score": 60}
        Loader.return_value.resolve_effective_trade_date.return_value = "2026-10-09"
        Loader.return_value.is_trading_day.return_value = True
        out = CSBFrontendInterface.screen(
            db,
            screening_date="2026-10-09",
            config_id=1,
            trace_only=True,
            prefer_cache=True,
            require_entry=False,
        )
    assert out.get("need_precompute") is False
    assert out.get("source") == "csb_signal_trace"
    assert out.get("total") == 1
    assert out["data"][0]["code"] == "600449"
    assert query_cache.call_args.kwargs.get("entry_only") is False


def test_screen_non_trading_day_no_fallback():
    """显式选节假日：不回退上一交易日，空结果 + 固定文案。"""
    db = MagicMock()
    with patch.object(CSBFrontendInterface, "_resolve_config_id", return_value=1), patch(
        "backend_core.strategies.csb.frontend_interface.CSBConfigManager"
    ) as CM, patch(
        "backend_core.strategies.csb.frontend_interface.CSBDataLoader"
    ) as Loader, patch(
        "backend_core.strategies.csb.frontend_interface.query_buy_signals_for_date"
    ) as query_cache:
        CM.return_value.get_config.return_value = {"min_score": 60}
        loader = Loader.return_value
        loader.is_trading_day.return_value = False
        loader.resolve_effective_trade_date.return_value = "2026-09-30"

        out = CSBFrontendInterface.screen(
            db,
            screening_date="2026-10-07",
            config_id=1,
            trace_only=True,
            prefer_cache=True,
        )

    assert out.get("success") is True
    assert out.get("total") == 0
    assert out.get("data") == []
    assert out.get("message") == "非交易日、无数据"
    assert out.get("search_date") == "2026-10-07"
    assert out.get("non_trading_day") is True
    assert out.get("need_precompute") is False
    assert out.get("source") == "non_trading_day"
    query_cache.assert_not_called()
    loader.resolve_effective_trade_date.assert_not_called()
