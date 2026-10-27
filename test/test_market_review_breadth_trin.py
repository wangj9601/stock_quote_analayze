# -*- coding: utf-8 -*-
"""复盘：市场宽广度增强与阿姆士(TRIN) 及近N日序列。"""

from backend_core.market_review.compute import (
    BREADTH_SERIES_DAYS,
    calc_arms_trin,
    summarize_breadth_rows,
)
from backend_core.market_review.render import render_markdown


def test_arms_trin_neutral():
    # (1800/1200) / (9e8/6e8) = 1.5/1.5 = 1.0
    assert calc_arms_trin(1800, 1200, 9e8, 6e8) == 1.0


def test_arms_trin_bullish_below_one():
    # 上涨家数略多，但上涨额显著更大 → TRIN < 1
    trin = calc_arms_trin(2000, 1500, 12e8, 4e8)
    assert trin is not None
    assert trin < 1.0


def test_arms_trin_invalid_returns_none():
    assert calc_arms_trin(0, 100, 1e8, 1e8) is None
    assert calc_arms_trin(100, 0, 1e8, 1e8) is None
    assert calc_arms_trin(100, 100, 0, 1e8) is None
    assert calc_arms_trin(100, 100, 1e8, 0) is None


def test_summarize_breadth_rows_counts_and_trin():
    rows = [
        ("000001", "平安银行", 1.2, 1_000_000.0),
        ("000002", "万科A", -0.5, 500_000.0),
        ("000003", "ST某股", 2.0, 999_999.0),  # ST 剔除
        ("000004", "平盘股", 0.0, 200_000.0),
        ("300001", "创业板", -20.0, 300_000.0),  # 跌停代理计入 limit_down
    ]
    out = summarize_breadth_rows(rows)
    assert out["up_count"] == 1
    assert out["down_count"] == 2
    assert out["flat_count"] == 1
    assert out["limit_down_count"] >= 1
    assert out["up_amount"] == 1_000_000.0
    assert out["down_amount"] == 800_000.0
    assert out["trin_basis"] == "amount"
    assert out["up_ratio"] == round(1 / 3, 4)  # up/(up+down)
    assert out["trin"] == calc_arms_trin(1, 2, 1_000_000.0, 800_000.0)


def test_summarize_breadth_empty():
    assert summarize_breadth_rows([]) == {}


def test_render_includes_trin_and_series():
    snap = {
        "trade_date": "2026-10-22",
        "vol_trillion": 2.0,
        "limit_up_count": 80,
        "cb_count": 10,
        "height": 5,
        "prev_cb_return": 2.0,
        "lo_value": 20,
        "hi_value": 60,
        "sp_value": 40,
        "lo_percentile": 30,
        "hi_percentile": 40,
        "sp_percentile": 20,
        "limit_source": "em_zt_pool",
        "season": "秋",
        "viewpoint_md": "测",
        "advice_md": "议",
        "hard_gates": {"rate": "1/5", "items": []},
        "rules_json": {
            "summary": "摘要",
            "signals": [],
            "quadrant": "—",
            "sp_eve": False,
            "delta": {},
            "market_env": {
                "vol_trillion": 2.0,
                "vol_delta_yi": 100,
                "above_2t": True,
                "breadth": {
                    "up_count": 3000,
                    "down_count": 2000,
                    "flat_count": 100,
                    "limit_down_count": 5,
                    "up_ratio": 0.6,
                    "trin": 0.85,
                    "trin_basis": "amount",
                },
                "breadth_series": [
                    {"trade_date": "2026-10-21", "up_ratio": 0.55, "trin": 1.1},
                    {"trade_date": "2026-10-22", "up_ratio": 0.6, "trin": 0.85},
                ],
                "indexes": [],
            },
        },
        "mainline_json": {
            "policy": "concept_primary",
            "rows": [],
            "summary": "无",
            "industry_confirm": {"rows": [], "summary": "无", "count": 0},
        },
        "season_detail": {"season": "秋", "cb": 10, "height": 5, "prev_cb_return": 2.0},
    }
    md = render_markdown(snap)
    assert "阿姆士" in md or "TRIN" in md
    assert "0.85" in md
    assert "宽广" in md or "上涨占比" in md
    assert BREADTH_SERIES_DAYS >= 5
    assert "近" in md and "日" in md
