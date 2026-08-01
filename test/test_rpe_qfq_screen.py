"""RPE 整策略前复权现算：不写 trace，panel 同口径。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from backend_core.strategies.rpe.frontend_interface import RPEFrontendInterface
from backend_core.strategies.rpe.strategy_engine import RPEStrategyEngine


def _make_bars(n: int = 80, base: float = 10.0) -> List[Dict[str, Any]]:
    bars = []
    for i in range(n):
        d = f"2024-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}"
        bars.append(
            {
                "date": d,
                "open": base,
                "high": base + 0.5,
                "low": base - 0.5,
                "close": base + (i % 5) * 0.1,
                "volume": 1000.0,
                "amount": 8_000_000.0,
                "turnover_rate": 1.2,
            }
        )
    return bars


class _FakeLoader:
    def __init__(self):
        self.last_panel_kwargs: Dict[str, Any] = {}
        self._members = {
            ("BK1", "industry"): [{"code": f"{i:06d}", "name": f"M{i}"} for i in range(1, 8)]
        }

    def resolve_trade_date(self) -> str:
        return "2024-03-20"

    def list_boards(self, board_kind="industry", limit=None):
        return [{"board_code": "BK1", "board_name": "测试板"}]

    def load_board_members(self, board_code, board_kind="industry"):
        return list(self._members.get((board_code, board_kind)) or [])

    def resolve_primary_board(self, code, board_kind="industry", *, allow_fallback=True):
        return {"board_code": "BK1", "board_name": "测试板", "board_kind": "industry", "member_count": 7}

    def find_boards_for_code(self, code, board_kind="industry"):
        return [{"board_code": "BK1", "board_name": "测试板"}]

    def load_bars(self, code, *, end_date=None, limit=250, adjust="none", factor_source="auto", refresh_factor=False):
        bars = _make_bars()
        if adjust == "qfq":
            for b in bars:
                b["close"] = float(b["close"]) * 0.9
                b["price_adjust"] = "qfq"
        return bars

    def load_sector_panel(
        self,
        member_codes,
        *,
        end_date=None,
        lookback=250,
        adjust="none",
        factor_source="auto",
        refresh_factor=False,
    ):
        self.last_panel_kwargs = {
            "adjust": adjust,
            "factor_source": factor_source,
            "lookback": lookback,
        }
        out = {}
        for c in member_codes:
            bars = self.load_bars(
                c,
                end_date=end_date,
                limit=lookback,
                adjust=adjust,
                factor_source=factor_source,
                refresh_factor=refresh_factor,
            )
            if bars:
                out[str(c).zfill(6)] = bars
        return out

    def build_date_members(self, panel):
        date_map = {}
        for bars in panel.values():
            for b in bars:
                date_map.setdefault(b["date"], []).append((b["close"], b["volume"]))
        return date_map


def test_screen_board_passes_qfq_to_panel():
    engine = RPEStrategyEngine(db_session=MagicMock(), config={
        "z_window": 40,
        "lookback_days": 60,
        "z_catch_up": -1.5,
        "z_lead": 2.0,
        "enable_trend_veto": False,
        "scan": {"min_sector_members": 5},
        "liquidity": {"lookback_days": 20, "min_avg_amount": 1, "min_avg_turnover_rate": 0},
    })
    fake = _FakeLoader()
    engine.loader = fake
    rows = engine.screen_board(
        "BK1",
        "测试板",
        date="2024-03-20",
        price_adjust="qfq",
        factor_source="sina",
        include_no_signal=True,
        codes_filter={"000001"},
    )
    assert fake.last_panel_kwargs.get("adjust") == "qfq"
    assert fake.last_panel_kwargs.get("factor_source") == "sina"
    assert rows
    assert rows[0].get("price_adjust") == "qfq"


def test_get_selection_results_qfq_skips_upsert():
    fake_engine = MagicMock()
    fake_engine.loader.resolve_trade_date.return_value = "2024-03-20"
    fake_engine._resolve_boards_for_codes.return_value = [
        {"board_code": "BK1", "board_name": "测试板", "board_kind": "industry"}
    ]
    fake_engine.screen.return_value = [
        {"code": "000001", "entry_signal": True, "z_score": -2.0, "price_adjust": "qfq"}
    ]

    cm = MagicMock()
    cm.get_default_config_id.return_value = 1
    cm.get_config.return_value = {}

    with patch("backend_core.strategies.rpe.config.RPEConfigManager", return_value=cm), patch(
        "backend_core.strategies.rpe.strategy_engine.RPEStrategyEngine",
        return_value=fake_engine,
    ), patch(
        "backend_core.strategies.rpe.signal_storage.upsert_signal_traces"
    ) as upsert, patch(
        "backend_api.database.SessionLocal", return_value=MagicMock()
    ):
        out = RPEFrontendInterface.get_selection_results(
            codes=["000001"],
            adjust="qfq",
            include_no_signal=True,
            max_results=50,
        )

    assert out["source"] == "live_qfq"
    assert out["price_adjust"] == "qfq"
    assert out["total"] == 1
    upsert.assert_not_called()
    assert fake_engine.screen.call_args.kwargs.get("price_adjust") == "qfq"


def test_get_selection_results_none_still_upserts():
    fake_engine = MagicMock()
    fake_engine.loader.resolve_trade_date.return_value = "2024-03-20"
    fake_engine._resolve_boards_for_codes.return_value = [
        {"board_code": "BK1", "board_name": "测试板", "board_kind": "industry"}
    ]
    fake_engine.screen.return_value = [{"code": "000001", "entry_signal": True, "z_score": -2.0}]

    cm = MagicMock()
    cm.get_default_config_id.return_value = 1
    cm.get_config.return_value = {}

    with patch("backend_core.strategies.rpe.config.RPEConfigManager", return_value=cm), patch(
        "backend_core.strategies.rpe.strategy_engine.RPEStrategyEngine",
        return_value=fake_engine,
    ), patch(
        "backend_core.strategies.rpe.signal_storage.upsert_signal_traces"
    ) as upsert, patch(
        "backend_api.database.SessionLocal", return_value=MagicMock()
    ):
        out = RPEFrontendInterface.get_selection_results(
            codes=["000001"],
            adjust="none",
            include_no_signal=True,
            max_results=50,
        )

    assert out["source"] == "live"
    upsert.assert_called_once()
