"""RPE 选股：同日同股多概念只保留 |Z| 最大的一条。"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from backend_core.strategies.rpe.signal_storage import (
    dedupe_rpe_rows_by_code,
    load_traces,
)


def test_dedupe_rpe_rows_keeps_max_abs_z():
    rows = [
        {"code": "603358", "z_score": -2.53, "signal_type": "catch_up", "entry_signal": False, "sector_id": "A"},
        {"code": "603358", "z_score": -2.88, "signal_type": "catch_up", "entry_signal": False, "sector_id": "B"},
        {"code": "603358", "z_score": -2.66, "signal_type": "catch_up", "entry_signal": False, "sector_id": "C"},
        {"code": "000892", "z_score": -2.37, "signal_type": "catch_up", "entry_signal": False, "sector_id": "D"},
        {"code": "000892", "z_score": -2.41, "signal_type": "catch_up", "entry_signal": False, "sector_id": "E"},
    ]
    out = dedupe_rpe_rows_by_code(rows)
    assert [r["code"] for r in out] == ["603358", "000892"]
    assert out[0]["z_score"] == -2.88
    assert out[0]["sector_id"] == "B"
    assert out[1]["z_score"] == -2.41
    assert out[1]["sector_id"] == "E"


def test_dedupe_prefers_entry_when_abs_z_tied():
    rows = [
        {"code": "000001", "z_score": -2.0, "signal_type": "catch_up", "entry_signal": False, "sector_id": "X"},
        {"code": "000001", "z_score": -2.0, "signal_type": "catch_up", "entry_signal": True, "sector_id": "Y"},
    ]
    out = dedupe_rpe_rows_by_code(rows)
    assert len(out) == 1
    assert out[0]["entry_signal"] is True
    assert out[0]["sector_id"] == "Y"


def test_load_traces_dedupes_before_limit():
    """去重在 limit 之前，避免重复概念行占满配额。"""
    trade_date = "2024-11-26"
    d = __import__("datetime").datetime.strptime(trade_date, "%Y-%m-%d").date()

    def _row(code, z, sector):
        return SimpleNamespace(
            code=code,
            name=code,
            trade_date=d,
            market_type="CN",
            sector_id=sector,
            sector_name=sector,
            z_score=z,
            ratio=None,
            signal_type="catch_up",
            entry_signal=False,
            watch_only=False,
            trend_veto=False,
            sector_slope=None,
            support_levels=[],
            resistance_levels=[],
            nearest_support=None,
            nearest_resistance=None,
            structure_valid=True,
            liquidity_ok=True,
            close_price=10.0,
            detail={},
            config_id=1,
        )

    db_rows = [
        _row("603358", -2.53, "A"),
        _row("603358", -2.88, "B"),
        _row("000892", -2.41, "C"),
        _row("000001", -1.9, "D"),
    ]

    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = db_rows
    query.limit.return_value = query

    db = MagicMock()
    db.query.return_value = query

    out = load_traces(db, trade_date=trade_date, config_id=1, limit=2)
    assert len(out) == 2
    assert [r["code"] for r in out] == ["603358", "000892"]
    assert out[0]["z_score"] == -2.88
    query.limit.assert_not_called()
