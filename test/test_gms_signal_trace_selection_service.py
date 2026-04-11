"""gms_signal_trace 选股列表服务单元测试（无真实库时使用 Mock）。"""

from unittest.mock import MagicMock

from backend_api.services.gms_signal_trace_selection import query_gms_signal_trace_selection


def test_query_returns_data_source_and_empty_when_no_table_date():
    db = MagicMock()
    db.query.return_value.scalar.return_value = None

    payload, fb = query_gms_signal_trace_selection(db, date=None, min_strength=0.3, limit=50)

    assert payload["data_source"] == "gms_signal_trace"
    assert payload["data"] == []
    assert fb is None
