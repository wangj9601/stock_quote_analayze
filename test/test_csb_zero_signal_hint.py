# -*- coding: utf-8 -*-
"""CSB 回测：预计算/读库有买点但回测信号为 0 时的诊断提示。"""

from backend_core.strategies.csb.backtest_runner import build_zero_signal_diagnostics


def test_hint_when_probe_excluded_by_allowed_types():
    diag = build_zero_signal_diagnostics(
        total_signals=0,
        loaded_before_filter=12,
        kept_after_filter=0,
        type_counts_before_filter={"CSB_PROBE": 12},
        allowed_signal_types=["CSB_BREAKOUT", "CSB_LPS"],
        precompute_hits=12,
        min_score=60.0,
    )
    assert diag is not None
    assert diag["loaded_before_filter"] == 12
    assert diag["kept_after_filter"] == 0
    assert "CSB_PROBE" in (diag.get("message") or "")
    assert "CSB_BREAKOUT" in (diag.get("message") or "") or "BREAKOUT" in (diag.get("message") or "")


def test_no_hint_when_has_trades():
    assert (
        build_zero_signal_diagnostics(
            total_signals=3,
            loaded_before_filter=3,
            kept_after_filter=3,
            type_counts_before_filter={"CSB_BREAKOUT": 3},
            allowed_signal_types=["CSB_BREAKOUT", "CSB_LPS"],
            precompute_hits=3,
            min_score=60.0,
        )
        is None
    )


def test_hint_when_precompute_hits_but_nothing_loaded():
    diag = build_zero_signal_diagnostics(
        total_signals=0,
        loaded_before_filter=0,
        kept_after_filter=0,
        type_counts_before_filter={},
        allowed_signal_types=["CSB_BREAKOUT", "CSB_LPS"],
        precompute_hits=12,
        min_score=60.0,
    )
    assert diag is not None
    assert "预计算" in (diag.get("message") or "")


def test_pdf_html_includes_zero_signal_hint():
    from backend_core.strategies.csb.backtest_pdf import build_csb_backtest_html

    html = build_csb_backtest_html(
        {
            "name": "t",
            "config": {"start_date": "2024-01-01", "end_date": "2024-01-31"},
            "summary": {
                "total_signals": 0,
                "hit_rate": 0,
                "zero_signal_hint": {
                    "message": "读到 12 笔买点（CSB_PROBE×12），但当前允许类型仅含 CSB_BREAKOUT、CSB_LPS"
                },
            },
        }
    )
    assert "零信号提示" in html
    assert "CSB_PROBE" in html
