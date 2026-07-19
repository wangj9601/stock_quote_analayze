"""URT 回测区间预计算覆盖检测。"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_core.strategies.urt.trace_store import (
    URT_TRACE_SCANNED_MARKER,
    dates_ready_for_universe_backtest,
    dates_with_trace_coverage,
)


def test_scanned_marker_constant():
    assert URT_TRACE_SCANNED_MARKER == "__URT_SCANNED__"


def test_dates_with_trace_coverage_empty_dates():
    class _Dummy:
        pass

    # 无日期时不访问 DB
    assert dates_with_trace_coverage(_Dummy(), config_id=1, dates=[]) == set()
    assert dates_ready_for_universe_backtest(_Dummy(), config_id=1, dates=[]) == set()