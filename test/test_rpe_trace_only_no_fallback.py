"""RPE 全市场：trace_only 空结果不现算；全市场现算默认概念板块。"""

from unittest.mock import MagicMock, patch

from backend_core.strategies.rpe.frontend_interface import RPEFrontendInterface
from backend_core.strategies.rpe.strategy_engine import RPEStrategyEngine


def test_trace_only_empty_entry_does_not_screen():
    fake_engine = MagicMock()
    fake_engine.loader.resolve_trade_date.return_value = "2024-03-20"

    cm = MagicMock()
    cm.get_default_config_id.return_value = 1
    cm.get_config.return_value = {}

    with patch("backend_core.strategies.rpe.config.RPEConfigManager", return_value=cm), patch(
        "backend_core.strategies.rpe.strategy_engine.RPEStrategyEngine",
        return_value=fake_engine,
    ), patch(
        "backend_core.strategies.rpe.signal_storage.load_traces",
        side_effect=[
            [],  # entry_only 查询为空
            [{"code": "000001", "signal_type": "catch_up", "entry_signal": False}],  # probe
        ],
    ) as load_traces, patch(
        "backend_api.database.SessionLocal", return_value=MagicMock()
    ):
        out = RPEFrontendInterface.get_selection_results(
            scope="cn",
            trace_only=True,
            entry_only=True,
            max_results=50,
        )

    fake_engine.screen.assert_not_called()
    assert out["source"] == "trace"
    assert out["total"] == 0
    assert out["data"] == []
    assert out.get("need_precompute") is False
    assert "入场买点" in (out.get("message") or "")
    assert load_traces.call_count == 2


def test_trace_only_no_data_need_precompute():
    fake_engine = MagicMock()
    fake_engine.loader.resolve_trade_date.return_value = "2024-03-20"

    cm = MagicMock()
    cm.get_default_config_id.return_value = 1
    cm.get_config.return_value = {}

    with patch("backend_core.strategies.rpe.config.RPEConfigManager", return_value=cm), patch(
        "backend_core.strategies.rpe.strategy_engine.RPEStrategyEngine",
        return_value=fake_engine,
    ), patch(
        "backend_core.strategies.rpe.signal_storage.load_traces",
        return_value=[],
    ), patch(
        "backend_api.database.SessionLocal", return_value=MagicMock()
    ):
        out = RPEFrontendInterface.get_selection_results(
            scope="cn",
            trace_only=True,
            entry_only=False,
            max_results=50,
        )

    fake_engine.screen.assert_not_called()
    assert out["source"] == "trace"
    assert out.get("need_precompute") is True
    assert "不自动全市场现算" in (out.get("message") or "")


def test_full_market_live_defaults_to_concept_boards():
    loader = MagicMock()
    loader.resolve_trade_date.return_value = "2024-03-20"
    loader.list_boards.return_value = [
        {"board_code": "C1", "board_name": "概念一"},
    ]
    engine = RPEStrategyEngine.__new__(RPEStrategyEngine)
    engine.loader = loader
    engine.config = {"scan": {"max_boards": 10, "max_results": 50}}
    engine.board_code_source = "tonghuashun"

    with patch.object(engine, "screen_board", return_value=[]) as screen_board:
        engine.screen(date="2024-03-20", board_kind="industry")

    loader.list_boards.assert_called_once_with("concept", limit=10)
    screen_board.assert_called_once()
    assert screen_board.call_args.args[0] == "C1"
    assert screen_board.call_args.kwargs.get("board_kind") == "concept"


def test_get_selection_results_live_cn_passes_concept():
    fake_engine = MagicMock()
    fake_engine.loader.resolve_trade_date.return_value = "2024-03-20"
    fake_engine.screen.return_value = []

    cm = MagicMock()
    cm.get_default_config_id.return_value = 1
    cm.get_config.return_value = {}

    with patch("backend_core.strategies.rpe.config.RPEConfigManager", return_value=cm), patch(
        "backend_core.strategies.rpe.strategy_engine.RPEStrategyEngine",
        return_value=fake_engine,
    ), patch(
        "backend_core.strategies.rpe.signal_storage.upsert_signal_traces"
    ), patch(
        "backend_api.database.SessionLocal", return_value=MagicMock()
    ):
        out = RPEFrontendInterface.get_selection_results(
            scope="cn",
            trace_only=False,
            board_kind="industry",
            max_results=50,
        )

    assert out["source"] == "live"
    assert fake_engine.screen.call_args.kwargs.get("board_kind") == "concept"
