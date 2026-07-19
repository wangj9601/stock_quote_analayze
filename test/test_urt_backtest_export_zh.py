"""URT 回测明细导出中文列名。"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_core.strategies.urt.backtest_storage import _build_urt_details_csv_bytes


def test_urt_details_csv_chinese_headers():
    rows = [
        {
            "code": "000676",
            "name": "智度股份",
            "signal_date": "2026-07-17",
            "score": 86.0,
            "entry_date": "2026-07-18",
            "entry_price": 6.8,
            "exit_date": "2026-07-20",
            "exit_price": 7.5,
            "exit_reason": "target_hit",
            "hit_target": True,
            "hit_date": "2026-07-20",
            "pnl_pct": 10.2,
            "bars_held": 2,
        }
    ]
    text = _build_urt_details_csv_bytes(rows).decode("utf-8-sig")
    header = text.splitlines()[0]
    assert "股票代码" in header
    assert "股票名称" in header
    assert "信号日期" in header
    assert "是否命中目标" in header
    assert "出场原因" in header
    assert "code" not in header
    body = text.splitlines()[1]
    assert "是" in body
    assert "触及目标" in body
    assert "000676" in body
