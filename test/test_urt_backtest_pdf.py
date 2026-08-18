# -*- coding: utf-8 -*-
"""URT 回测详情 PDF 导出单测。"""

from __future__ import annotations

import pytest

from backend_core.strategies.urt.backtest_pdf import (
    build_backtest_detail_html,
    exit_mode_label,
    render_backtest_pdf,
    resolve_exit_mode,
)


def _sample_task():
    return {
        "task_id": "8f48888a-test",
        "name": "URT回测_8f48888",
        "status": "completed",
        "progress": 100,
        "created_at": "2026-08-17T14:00:01Z",
        "config": {
            "stock_pool_mode": "watchlist",
            "stock_pool": ["600000"] * 3,
            "start_date": "2025-05-17",
            "end_date": "2026-07-17",
            "target_pct": 0.1,
            "horizon_days": 20,
            "min_score": 70,
            "use_trace": True,
            "exit_mode": "structure_exit",
            "trade_logic": {
                "summary": "结构出场：支撑止损 / 阻力止盈",
                "rules": ["信号日次日开盘买入", "观察期内按结构价位离场"],
                "exit_priority": [
                    {
                        "code": "structure_stop",
                        "label": "结构止损",
                        "desc": "跌破支撑缓冲",
                    }
                ],
            },
            "risk_params": {
                "stop_loss_pct_min": 5,
                "stop_loss_pct_max": 8,
                "time_stop_down_days": 3,
                "take_profit_alert_pct_min": 8,
                "take_profit_alert_pct_max": 12,
                "trailing_drawdown_pct": 5,
                "structure_stop_buffer_pct": 0.02,
                "exit_mode": "structure_exit",
            },
        },
        "summary": {
            "total_signals": 10,
            "target_hits": 4,
            "hit_rate": 0.4,
            "win_rate": 0.35,
            "avg_pnl_pct": -1.2,
            "avg_max_gain_pct": 6.5,
            "target_pct": 0.1,
            "exit_mode": "structure_exit",
            "stock_pool_size": 3,
            "structure_exit_stats": {
                "structure_stop": 2,
                "structure_target": 3,
                "pct_target": 1,
                "price_stop": 1,
                "horizon_end": 3,
                "structure_fallback_rate": 0.1,
            },
            "by_score_bucket": {
                "70-80": {"total": 5, "hit": 2, "hit_rate": 0.4, "win_rate": 0.4, "avg_pnl_pct": 1.2, "avg_max_gain_pct": 8.0},
            },
            "hit_rate_compare": {
                "note": "同一批成交信号对照",
                "hit_rate": 0.4,
                "avg_max_gain_pct": 6.5,
                "actual": {"avg_pnl_pct": -1.2, "win_rate": 0.35},
                "horizon_hold": {"avg_pnl_pct": 2.0, "win_rate": 0.4},
            },
            "by_factor_bucket": {
                "volume_multiple": {
                    "label": "量能倍数",
                    "bins": [{"bucket": "≥5", "total": 3, "hit": 2, "hit_rate": 0.67, "avg_pnl_pct": 1.0, "avg_max_gain_pct": 8.0}],
                }
            },
            "exit_reason_dist": {"structure_stop": 2, "horizon_end": 3},
        },
    }


def test_resolve_exit_mode_structure():
    assert resolve_exit_mode(_sample_task()) == "structure_exit"
    assert "结构出场" in exit_mode_label("structure_exit")


def test_resolve_exit_mode_from_config_fallback():
    task = {
        "config": {"exit_mode": "risk_exit"},
        "summary": {},
    }
    assert resolve_exit_mode(task) == "risk_exit"


def test_build_html_contains_key_sections():
    html = build_backtest_detail_html(_sample_task(), logs=[{"text": "done"}])
    assert "URT 交易回测详情" in html
    assert "结构出场" in html
    assert "结构出场归因" in html
    assert "命中率对照" in html
    assert "按信号因子分桶" in html
    assert "STSong-Light" in html
    assert "done" not in html
    assert "<h2>日志</h2>" not in html


def test_render_backtest_pdf_bytes():
    pytest.importorskip("xhtml2pdf")
    pdf = render_backtest_pdf(_sample_task(), logs=["完成"])
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 500
    try:
        from pypdf import PdfReader
    except ImportError:
        pytest.importorskip("PyPDF2")
        from PyPDF2 import PdfReader
    from io import BytesIO

    text = "".join((p.extract_text() or "") for p in PdfReader(BytesIO(pdf)).pages)
    assert "交易" in text or "结构" in text
