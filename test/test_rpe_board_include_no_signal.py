"""RPE 板块扫描：包含无信号成分股。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import patch

from backend_core.strategies.rpe.strategy_engine import RPEStrategyEngine


def _bars(n: int = 80, close: float = 10.0) -> List[Dict[str, Any]]:
    out = []
    for i in range(n):
        d = f"2024-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}"
        out.append(
            {
                "date": d,
                "open": close,
                "high": close + 0.3,
                "low": close - 0.3,
                "close": close,
                "volume": 1000.0,
                "amount": 8_000_000.0,
                "turnover_rate": 1.0,
            }
        )
    return out


class _BoardLoader:
    def resolve_trade_date(self) -> str:
        return "2024-03-20"

    def list_boards(self, board_kind="industry", limit=None):
        return [{"board_code": "BK1", "board_name": "测试板块"}]

    def load_board_members(self, board_code, board_kind="industry"):
        return [{"code": f"{i:06d}", "name": f"S{i}"} for i in range(1, 8)]

    def load_bars(self, code, *, end_date=None, limit=None):
        # 全员同价，Z 接近 0 → 多数无 catch_up/lead 信号
        return _bars()

    def load_sector_panel(self, member_codes, *, end_date=None, lookback=None):
        return {str(c).zfill(6): _bars() for c in member_codes}

    def build_date_members(self, panel):
        date_map = {}
        for bars in panel.values():
            for b in bars:
                date_map.setdefault(b["date"], []).append((b["close"], b["volume"]))
        return date_map

    def find_boards_for_code(self, code, board_kind="industry"):
        return [{"board_code": "BK1", "board_name": "测试板块"}]


def test_board_screen_include_no_signal_returns_members():
    engine = RPEStrategyEngine(config={
        "lookback_days": 80,
        "z_window": 20,
        "z_lead": 2.0,
        "z_catch_up": -1.5,
        "sector_slope_window": 20,
        "enable_trend_veto": False,
        "enable_lead_trade": False,
        "kde_base_factor": 1.0,
        "min_rr_to_resistance": 1.0,
        "liquidity": {"lookback_days": 10, "min_avg_amount": 1.0, "min_avg_turnover_rate": 0.0},
        "scan": {"min_sector_members": 5, "max_results": 200},
    })
    engine.loader = _BoardLoader()

    with_signal_only = engine.screen(
        date="2024-03-20",
        board_codes=["BK1"],
        board_kind="industry",
        include_no_signal=False,
        max_results=200,
    )
    with_all = engine.screen(
        date="2024-03-20",
        board_codes=["BK1"],
        board_kind="industry",
        include_no_signal=True,
        max_results=200,
    )
    assert len(with_all) >= len(with_signal_only)
    assert len(with_all) >= 5
    # 同价序列下多数应为无 signal_type
    no_sig = [r for r in with_all if not r.get("signal_type")]
    assert len(no_sig) >= 1
