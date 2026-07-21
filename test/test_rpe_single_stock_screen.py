"""RPE 单股/自选：按所属板块建簇并返回策略明细。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from backend_core.strategies.rpe.strategy_engine import RPEStrategyEngine


def _make_bars(n: int = 80, base: float = 10.0, vol: float = 1000.0) -> List[Dict[str, Any]]:
    bars = []
    for i in range(n):
        # 简单递增日期键，足够滚动 Z 窗口
        d = f"2024-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}"
        bars.append(
            {
                "date": d,
                "open": base,
                "high": base + 0.5,
                "low": base - 0.5,
                "close": base + (i % 5) * 0.1,
                "volume": vol,
                "amount": 8_000_000.0,
                "turnover_rate": 1.2,
            }
        )
    return bars


class _FakeLoader:
    def __init__(self):
        self._industry = {
            "000001": [{"board_code": "BK0001", "board_name": "银行"}],
        }
        self._concept = {
            "000002": [{"board_code": "BK9001", "board_name": "深圳本地"}],
        }
        self._members = {
            ("BK0001", "industry"): [
                {"code": f"{i:06d}", "name": f"M{i}"} for i in range(1, 8)
            ],
            ("BK9001", "concept"): [
                {"code": "000002", "name": "万科A"},
                {"code": "000003", "name": "C3"},
                {"code": "000004", "name": "C4"},
                {"code": "000005", "name": "C5"},
                {"code": "000006", "name": "C6"},
                {"code": "000007", "name": "C7"},
            ],
        }

    def resolve_trade_date(self) -> str:
        return "2024-03-20"

    def find_boards_for_code(self, code: str, board_kind: str = "industry"):
        c = str(code).zfill(6) if str(code).isdigit() else str(code)
        if board_kind == "concept":
            return list(self._concept.get(c) or [])
        return list(self._industry.get(c) or [])

    def load_board_members(self, board_code: str, board_kind: str = "industry"):
        return list(self._members.get((board_code, board_kind)) or [])

    def list_boards(self, board_kind: str = "industry", limit: Optional[int] = None):
        return []

    def load_bars(self, code: str, *, end_date=None, limit=None):
        return _make_bars()

    def load_sector_panel(self, member_codes, *, end_date=None, lookback=None):
        return {str(c).zfill(6): _make_bars() for c in member_codes}

    def build_date_members(self, panel):
        date_map = {}
        for bars in panel.values():
            for b in bars:
                d = b["date"]
                date_map.setdefault(d, []).append((b["close"], b["volume"]))
        return date_map


def test_resolve_boards_industry_first_then_concept_fallback():
    eng = RPEStrategyEngine(db_session=MagicMock())
    eng.loader = _FakeLoader()
    jobs = eng._resolve_boards_for_codes(["000001", "000002"], "industry")
    kinds = {(j["board_code"], j["board_kind"]) for j in jobs}
    assert ("BK0001", "industry") in kinds
    assert ("BK9001", "concept") in kinds


def test_screen_single_returns_in_band_with_include_no_signal():
    eng = RPEStrategyEngine(db_session=MagicMock())
    eng.loader = _FakeLoader()
    # 默认阈值下中间 Z 多为 in_band，无 signal_type
    rows = eng.screen(
        date="2024-03-20",
        codes=["000001"],
        include_no_signal=True,
        max_results=10,
    )
    assert len(rows) == 1
    assert rows[0]["code"] == "000001"
    assert rows[0]["sector_id"] == "BK0001"
    assert "z_score" in rows[0]


def test_screen_watchlist_codes_filter_only_targets():
    eng = RPEStrategyEngine(db_session=MagicMock())
    eng.loader = _FakeLoader()
    rows = eng.screen(
        date="2024-03-20",
        codes=["000001"],
        include_no_signal=True,
        max_results=50,
    )
    assert all(r["code"] == "000001" for r in rows)
