# -*- coding: utf-8 -*-
"""每日复盘规则与渲染冒烟。"""

from backend_core.market_review.rules import (
    build_trend_rules,
    classify_season,
    evaluate_hard_gates,
)
from backend_core.market_review.render import render_markdown


def test_hard_gates_all_fail():
    today = {
        "vol_trillion": 1.61,
        "cb_count": 7,
        "height": 5,
        "lo_value": 27,
        "hi_value": 67,
    }
    hist = [
        {**today, "lo_value": 29, "hi_value": 90},
        {**today, "lo_value": 28, "hi_value": 80},
        today,
    ]
    g = evaluate_hard_gates(today, hist)
    assert g["passed"] == 0
    assert g["total"] == 5


def test_season_autumn():
    s = classify_season(7, 5, 3.3)
    assert s["season"] == "秋"


def test_render_has_sections():
    snap = {
        "trade_date": "2026-09-15",
        "vol_trillion": 1.61,
        "cb_count": 7,
        "height": 5,
        "prev_cb_return": 3.3,
        "lo_value": 27,
        "hi_value": 67,
        "sp_value": 40,
        "lo_percentile": 20,
        "hi_percentile": 40,
        "sp_percentile": 15,
        "limit_source": "zt_pool_em",
        "season": "秋",
        "viewpoint_md": "测试",
        "advice_md": "建议",
        "hard_gates": {"rate": "0/5", "items": []},
        "rules_json": {"summary": "摘要", "signals": [], "quadrant": "—", "sp_eve": False, "delta": {}},
        "mainline_json": {
            "policy": "concept_primary",
            "rows": [],
            "summary": "无",
            "industry_confirm": {"rows": [], "summary": "无行业确认", "count": 0},
        },
        "season_detail": {"season": "秋", "cb": 7, "height": 5, "prev_cb_return": 3.3},
    }
    md = render_markdown(snap)
    assert "股市复盘报告" in md
    assert "五项硬门槛" in md
    assert "双曲线分析" in md
    assert "操作建议" in md
    assert "概念主线" in md
    assert "行业赛道确认" in md


def test_mainline_summary_concept_only():
    """近10日主线聚合应忽略 industry 历史行。"""
    from unittest.mock import MagicMock

    from backend_core.market_review.compute import build_mainline_summary

    db = MagicMock()

    def fake_execute(sql, params=None):
        s = str(sql)
        result = MagicMock()
        if "FROM board_fund_flow_daily" in s or "industry_board_realtime" in s:
            result.fetchall.return_value = []
            return result
        if "FROM market_daily_mainline_hits" in s:
            assert "board_type = 'concept'" in s
            result.fetchall.return_value = [
                ("concept", "885001", "固态电池", "2026-09-15", ["涨幅Top15"]),
                ("concept", "885001", "固态电池", "2026-09-14", ["涨幅Top15"]),
                ("concept", "885001", "固态电池", "2026-09-13", ["资金流Top10"]),
            ]
            return result
        # trading dates helper
        result.fetchall.return_value = [
            ("2026-09-15",),
            ("2026-09-14",),
            ("2026-09-13",),
        ]
        result.scalars = MagicMock(return_value=MagicMock(all=lambda: ["2026-09-15", "2026-09-14", "2026-09-13"]))
        return result

    db.execute.side_effect = fake_execute

    # Patch trading dates to avoid depending on historical_quotes SQL shape
    import backend_core.market_review.compute as compute_mod

    orig = compute_mod._trading_dates_on_or_before
    compute_mod._trading_dates_on_or_before = lambda _db, _d, _n: [
        "2026-09-15",
        "2026-09-14",
        "2026-09-13",
    ]
    try:
        out = build_mainline_summary(db, "2026-09-15")
    finally:
        compute_mod._trading_dates_on_or_before = orig

    assert out["policy"] == "concept_primary"
    assert len(out["rows"]) == 1
    assert out["rows"][0]["board_name"] == "固态电池"
    assert out["rows"][0]["hits_10d"] == 3
    assert "核心主线" in out["rows"][0]["tier_label"]
    assert "industry_confirm" in out
    assert "概念" in out["summary"]


def test_isolated_height_signal():
    today = {
        "cb_count": 7,
        "height": 5,
        "vol_trillion": 1.61,
        "lo_value": 27,
        "hi_value": 67,
        "sp_value": 40,
        "prev_cb_return": 3.3,
    }
    yest = {
        "cb_count": 11,
        "height": 4,
        "vol_trillion": 1.63,
        "lo_value": 28,
        "hi_value": 96,
        "sp_value": 68,
        "prev_cb_return": 3.5,
    }
    r = build_trend_rules(today, yest)
    assert r["isolated_height"] is True


def test_pdf_bytes_smoke():
    from backend_core.market_review.pdf_export import build_daily_review_pdf_bytes

    snap = {
        "trade_date": "2026-09-15",
        "vol_trillion": 1.61,
        "cb_count": 7,
        "height": 5,
        "prev_cb_return": 3.3,
        "lo_value": 27,
        "hi_value": 67,
        "sp_value": 40,
        "lo_percentile": 20,
        "hi_percentile": 40,
        "sp_percentile": 15,
        "limit_source": "zt_pool_em",
        "season": "秋",
        "viewpoint_md": "测试观点",
        "advice_md": "测试建议",
        "hard_gates": {
            "rate": "0/5",
            "items": [
                {
                    "id": 1,
                    "name": "量能",
                    "standard": "≥2",
                    "value": 1.61,
                    "passed": False,
                }
            ],
        },
        "rules_json": {
            "summary": "测试摘要",
            "signals": ["信号A"],
            "quadrant": "低位弱势",
            "sp_eve": True,
            "delta": {
                "height": {"from": 4, "to": 5},
                "cb_count": {"from": 11, "to": 7},
            },
        },
        "mainline_json": {
            "policy": "concept_primary",
            "summary": "主线摘要",
            "rows": [
                {
                    "board_name": "固态电池",
                    "hits_10d": 5,
                    "tier_label": "主线",
                    "today_status": "在榜",
                    "echelon": "第一梯队",
                }
            ],
            "industry_confirm": {
                "summary": "行业确认摘要",
                "count": 1,
                "rows": [
                    {
                        "board_name": "半导体",
                        "reason_text": "涨幅Top15",
                        "change_percent": 3.2,
                        "net_inflow": 1e8,
                    }
                ],
            },
        },
        "season_detail": {
            "season": "秋",
            "cb": 7,
            "height": 5,
            "prev_cb_return": 3.3,
        },
    }
    pdf = build_daily_review_pdf_bytes(snap)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 500
