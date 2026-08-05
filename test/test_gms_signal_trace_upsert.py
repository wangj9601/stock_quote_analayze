"""回归：gms_signal_trace 回填使用 ON CONFLICT UPSERT，避免 UniqueViolation。"""

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_core.strategies.gms.frontend_interface import _save_result_to_trace


def test_save_result_to_trace_uses_on_conflict_upsert():
    db = MagicMock()
    nested = MagicMock()
    nested.__enter__ = MagicMock(return_value=None)
    nested.__exit__ = MagicMock(return_value=False)
    db.begin_nested.return_value = nested

    result = {
        "code": "000967",
        "market_type": "CN",
        "score_total": 80.0,
        "score_accumulation": 0.0,
        "score_momentum": 100,
        "signal_strength": 0.8,
        "buy_type": "右侧",
        "left_buy_signal": False,
        "right_buy_signal": True,
        "sell_signal": False,
        "score_detail": {"score_total": 80.0},
        "risk_tags": [],
    }
    _save_result_to_trace(db, result, "2026-08-05", 2)

    assert db.execute.called
    stmt = db.execute.call_args[0][0]
    # PostgreSQL Insert ... ON CONFLICT
    assert hasattr(stmt, "on_conflict_do_update") or "ON CONFLICT" in str(stmt).upper()
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "ON CONFLICT" in compiled.upper()
    db.flush.assert_called()


if __name__ == "__main__":
    test_save_result_to_trace_uses_on_conflict_upsert()
    print("ok")
