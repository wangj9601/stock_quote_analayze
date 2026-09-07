# -*- coding: utf-8 -*-
"""URT：板块筛选可读缓存 + 空缓存命中 + 全市场无预计算快速失败。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = Path(__file__).resolve().parents[1]
for p in (str(project_root), str(project_root / "backend_api"), str(project_root / "backend_core")):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend_core.strategies.urt.data_loader import (  # noqa: E402
    code_matches_urt_boards,
    normalize_urt_board_keys,
)
from backend_core.strategies.urt.frontend_interface import URTFrontendInterface  # noqa: E402

CFG = {
    "ma_period": 20,
    "volume_lookback": 20,
    "volume_multiple": 2.0,
    "min_score": 70,
    "yang_rule_a": True,
    "yang_rule_b": True,
    "use_turnover": False,
    "use_volume_ratio": False,
    "min_turnover": 0,
    "min_volume_ratio": 0,
    "signal_quality_mode": "standard",
}


def test_code_matches_urt_boards():
    assert code_matches_urt_boards("600519", ["SH_MAIN"]) is True
    assert code_matches_urt_boards("002230", ["SZ_SME"]) is True
    assert code_matches_urt_boards("000001", ["SZ_MAIN", "SZ_SME"]) is True
    assert code_matches_urt_boards("300750", ["SH_MAIN", "SZ_SME"]) is False
    assert code_matches_urt_boards("600519", None) is True
    assert normalize_urt_board_keys(["MAIN"]) == []


def test_screen_uses_cache_when_boards_set():
    rows = [
        {"code": "600519", "name": "茅台", "buy_signal": True, "score": 80},
        {"code": "002230", "name": "讯飞", "buy_signal": True, "score": 75},
        {"code": "300750", "name": "宁德", "buy_signal": True, "score": 90},
    ]
    db = MagicMock()
    with patch.object(URTFrontendInterface, "_resolve_config_id", return_value=1), patch(
        "backend_core.strategies.urt.frontend_interface.URTConfigManager"
    ) as CM, patch(
        "backend_core.strategies.urt.frontend_interface.URTDataLoader"
    ) as Loader, patch(
        "backend_core.strategies.urt.frontend_interface.query_buy_signals_for_date",
        return_value=rows,
    ) as q, patch(
        "backend_core.strategies.urt.frontend_interface.dates_ready_for_universe_backtest",
        return_value=set(),
    ), patch(
        "backend_core.strategies.urt.frontend_interface.get_trace_freshness",
        return_value={"stale": False, "need_recompute": False, "config_updated_at": None, "trace_computed_at": None},
    ), patch(
        "backend_core.strategies.urt.signal_detector.build_buy_logic",
        return_value={"filter_ok": True, "score_ok": True},
    ):
        cm = CM.return_value
        cm.get_config.return_value = CFG
        cm.merge_overrides.return_value = CFG
        Loader.resolve_effective_history_end_date.return_value = "2026-09-05"
        Loader.return_value = MagicMock()
        out = URTFrontendInterface.screen(
            db, scope="all", boards=["SH_MAIN", "SZ_SME"], config_id=1, prefer_cache=True, market="CN"
        )
    assert q.called
    assert {r["code"] for r in out["data"]} == {"600519", "002230"}
    assert out["data_source"] == "urt_signal_trace"


def test_empty_buy_signals_but_date_ready_uses_cache():
    """已预计算但当日无买点：应缓存命中空结果，禁止实时全扫。"""
    db = MagicMock()
    with patch.object(URTFrontendInterface, "_resolve_config_id", return_value=1), patch(
        "backend_core.strategies.urt.frontend_interface.URTConfigManager"
    ) as CM, patch(
        "backend_core.strategies.urt.frontend_interface.URTDataLoader"
    ) as Loader, patch(
        "backend_core.strategies.urt.frontend_interface.query_buy_signals_for_date",
        return_value=[],
    ), patch(
        "backend_core.strategies.urt.frontend_interface.dates_ready_for_universe_backtest",
        return_value={"2026-09-05"},
    ), patch(
        "backend_core.strategies.urt.frontend_interface.get_trace_freshness",
        return_value={"stale": False, "need_recompute": False, "config_updated_at": None, "trace_computed_at": None},
    ), patch(
        "backend_core.strategies.urt.frontend_interface.URTStrategyEngine"
    ) as Eng:
        cm = CM.return_value
        cm.get_config.return_value = CFG
        cm.merge_overrides.return_value = CFG
        Loader.resolve_effective_history_end_date.return_value = "2026-09-05"
        Loader.return_value = MagicMock()
        out = URTFrontendInterface.screen(db, scope="all", config_id=1, prefer_cache=True, market="CN")
    assert out["success"] is True
    assert out["data"] == []
    assert out["data_source"] == "urt_signal_trace"
    Eng.assert_not_called()


def test_full_market_no_precompute_failfast():
    """无预计算时默认快速失败，避免拖成网关 502。"""
    db = MagicMock()
    fake_stocks = [(f"{i:06d}", f"n{i}") for i in range(600)]
    with patch.object(URTFrontendInterface, "_resolve_config_id", return_value=1), patch(
        "backend_core.strategies.urt.frontend_interface.URTConfigManager"
    ) as CM, patch(
        "backend_core.strategies.urt.frontend_interface.URTDataLoader"
    ) as Loader, patch(
        "backend_core.strategies.urt.frontend_interface.query_buy_signals_for_date",
        return_value=[],
    ), patch(
        "backend_core.strategies.urt.frontend_interface.dates_ready_for_universe_backtest",
        return_value=set(),
    ), patch(
        "backend_core.strategies.urt.frontend_interface.get_trace_freshness",
        return_value={"stale": False, "need_recompute": False, "config_updated_at": None, "trace_computed_at": None},
    ), patch.dict("os.environ", {"URT_ALLOW_FULL_MARKET_REALTIME": "0"}, clear=False):
        cm = CM.return_value
        cm.get_config.return_value = CFG
        cm.merge_overrides.return_value = CFG
        Loader.resolve_effective_history_end_date.return_value = "2026-09-05"
        loader = MagicMock()
        loader.list_a_share_candidates.return_value = fake_stocks
        Loader.return_value = loader
        out = URTFrontendInterface.screen(db, scope="all", config_id=1, prefer_cache=True, market="CN")
    assert out["success"] is False
    assert out.get("need_precompute") is True
    assert "预计算" in (out.get("message") or "")


if __name__ == "__main__":
    test_code_matches_urt_boards()
    test_screen_uses_cache_when_boards_set()
    test_empty_buy_signals_but_date_ready_uses_cache()
    test_full_market_no_precompute_failfast()
    print("test_urt_board_cache_filter.py: all passed")
