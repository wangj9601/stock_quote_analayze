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


def test_viewpoint_expand_avoids_bear_template():
    from backend_core.market_review.rules import classify_tape_regime, draft_advice, draft_viewpoint

    today = {
        "vol_trillion": 2.08,
        "cb_count": 12,
        "height": 4,
        "limit_up_count": 79,
        "prev_cb_return": 3.88,
    }
    yest = {"vol_trillion": 1.83, "cb_count": 9, "height": 5}
    breadth = {"up_count": 4200, "down_count": 1100, "limit_down_count": 1}
    tape = classify_tape_regime(today, yest, breadth)
    assert tape["label"] == "放量普涨"
    rules = build_trend_rules(today, yest)
    env = {"breadth": breadth, "above_2t": True, "vol_delta_yi": tape["vol_delta_yi"], "sh_gap_to_high20": 40}
    sector = {"main": {"board_name": "半导体", "net_inflow_yi": 226.6}}
    text = draft_viewpoint(today, rules, {"season": "秋"}, tape, env, sector)
    assert "缩量阴跌" not in text
    assert "止跌" not in text
    assert "放量普涨" in text
    advice = draft_advice({"passed": 2, "total": 5}, {"season": "秋"}, rules, tape, {"watch": ["观察主线"]})
    assert "空仓" not in advice
    assert "连板生态仍偏冷" in advice


def test_viewpoint_shrink_keeps_defense():
    from backend_core.market_review.rules import classify_tape_regime, draft_viewpoint

    today = {"vol_trillion": 1.61, "cb_count": 7, "height": 5}
    yest = {"vol_trillion": 1.83, "cb_count": 11, "height": 4}
    tape = classify_tape_regime(today, yest, {"up_count": 800, "down_count": 3500})
    assert tape["label"] == "缩量调整"
    text = draft_viewpoint(today, build_trend_rules(today, yest), {"season": "秋"}, tape, {}, {})
    assert "观望" in text
    assert "缩量" in text


def test_render_inflow_yi_and_short_percentile():
    snap = {
        "trade_date": "2026-09-18",
        "vol_trillion": 2.08,
        "cb_count": 12,
        "height": 4,
        "lo_value": -3.04,
        "hi_value": 87.38,
        "sp_value": 90.42,
        "lo_percentile": None,
        "hi_percentile": None,
        "sp_percentile": None,
        "percentile_note": "样本不足",
        "limit_source": "em_zt_pool",
        "season": "秋",
        "viewpoint_md": "放量普涨",
        "advice_md": "观察",
        "hard_gates": {"rate": "2/5", "items": []},
        "rules_json": {
            "summary": "量能放大",
            "signals": ["量能放大"],
            "quadrant": "冬/冰点",
            "sp_eve": False,
            "delta": {},
            "curve_zones": {
                "lo": "阈值未校准",
                "hi": "阈值未校准",
                "sp": "阈值未校准",
                "summary": "阈值未校准",
                "percentile_note": "样本不足",
            },
            "percentile_sample": 3,
        },
        "mainline_json": {
            "summary": "概念",
            "rows": [
                {
                    "board_name": "存储芯片",
                    "hits_10d": 2,
                    "tier_label": "观察",
                    "today_status": "今日上榜",
                    "echelon": "持续",
                }
            ],
            "industry_confirm": {
                "summary": "赛道",
                "rows": [
                    {
                        "board_name": "半导体",
                        "reason_text": "涨幅Top15",
                        "change_percent": 4.31,
                        "net_inflow": 22660000000,
                    }
                ],
            },
        },
        "season_detail": {"season": "秋", "cb": 12, "height": 4, "prev_cb_return": 3.88},
    }
    md = render_markdown(snap)
    assert "226.6" in md
    assert "22660000000" not in md
    assert "样本不足" in md
    assert "阈值未校准" in md
    assert "100.00%" not in md


def test_concept_filter_hides_one_hit_dropout():
    from backend_core.market_review.compute import filter_concept_rows

    rows = [
        {"board_name": "存储芯片", "hits_10d": 2, "today_hit": True},
        {"board_name": "农业种植", "hits_10d": 1, "today_hit": False, "echelon": "掉队"},
        {"board_name": "半导体设备", "hits_10d": 1, "today_hit": True},
    ]
    shown = filter_concept_rows(rows, ["半导体"])
    names = [r["board_name"] for r in shown]
    assert "农业种植" not in names
    assert "存储芯片" in names
    assert "半导体设备" in names


def _quote(chg, **extra):
    row = {"name": extra.pop("name", "测试"), "change_percent": chg, "open": 10, "high": 11, "low": 9.8, "close": 10.5}
    row.update(extra)
    return row


def test_limit_up_not_trackable():
    from backend_core.market_review.picks import assemble_picks

    picks = assemble_picks(
        constituents={"600001", "600002"},
        quotes={"600001": _quote(10.0, name="涨停"), "600002": _quote(3.0, name="未涨停")},
        zt_rows=[{"code": "600001", "name": "涨停", "change_percent": 10, "seal_fund": 1e8, "seal_yi": 1, "board_count": 1, "break_count": 0}],
        strategy_by_code={
            "600001": {"strategies": ["urt"], "best_score": 80, "name": "涨停"},
            "600002": {"strategies": ["gms"], "best_score": 70, "name": "未涨停"},
        },
        roles={},
        season="秋",
        gates_passed=1,
        gates_total=5,
        tape_label="放量普涨",
        tape_volume="expand",
        main={"board_name": "半导体", "board_code": "881001"},
        sideline_rep={"code": "000001", "name": "支线", "change_percent": 2, "industry": "光伏"},
        prev_zt_codes=set(),
        concept_codes=None,
        brief_stance={},
    )
    assert [r["code"] for r in picks["track"]] == ["600002"]
    assert picks["no_chase"][0]["stance"] == "不追"
    assert picks["no_chase"][0]["code"] == "600001"
    assert len(picks["sideline"]) == 1


def test_shrink_has_no_track():
    from backend_core.market_review.picks import assemble_picks

    picks = assemble_picks(
        constituents={"600001"},
        quotes={"600001": _quote(-2, name="转弱", high=12, open=10, close=9.5, low=9.4)},
        zt_rows=[],
        strategy_by_code={"600001": {"strategies": ["urt"], "best_score": 90, "name": "转弱"}},
        roles={},
        season="春",
        gates_passed=5,
        gates_total=5,
        tape_label="缩量调整",
        tape_volume="shrink",
        main={"board_name": "半导体", "board_code": "881001"},
        sideline_rep={"code": "000001", "name": "支线", "change_percent": 2, "industry": "光伏"},
        prev_zt_codes={"600001"},
        concept_codes=None,
        brief_stance={},
    )
    assert picks["track"] == []
    assert picks["no_chase"] == []
    assert picks["sideline"] == []
    assert picks["avoid"][0]["stance"] == "回避"
    assert "由强转弱" in picks["avoid"][0]["reason"]


def test_same_industry_cap_six():
    from backend_core.market_review.picks import assemble_picks

    codes = [f"60000{i}" for i in range(1, 9)]
    strategies = {
        code: {"strategies": ["urt", "gms"], "best_score": 90 - i, "name": code}
        for i, code in enumerate(codes)
    }
    quotes = {code: _quote(2) for code in strategies}
    picks = assemble_picks(
        constituents=set(strategies),
        quotes=quotes,
        zt_rows=[],
        strategy_by_code=strategies,
        roles={},
        season="春",
        gates_passed=3,
        gates_total=5,
        tape_label="放量普涨",
        tape_volume="expand",
        main={"board_name": "半导体", "board_code": "881001"},
        sideline_rep=[
            {"code": "000001", "name": "支线甲", "change_percent": 3, "industry": "光伏"},
            {"code": "000002", "name": "支线乙", "change_percent": 2, "industry": "光伏"},
            {"code": "000003", "name": "支线丙", "change_percent": 1, "industry": "医药"},
        ],
        prev_zt_codes=set(),
        concept_codes=None,
        brief_stance={},
    )
    assert len(picks["track"]) == 6
    assert picks["track_cap"] == 10
    assert len(picks["sideline"]) == 2


def test_overbought_does_not_reject_no_chase():
    from backend_core.market_review.picks import apply_indicator_gate, should_downgrade

    row = {"stance": "不追", "rsi": 90}
    apply_indicator_gate(row, macd="金叉/零轴上", rsi=90, trend="向上")
    assert row["stance"] == "不追"
    assert should_downgrade("金叉/零轴上", 90, "向上") is False
    track = {"stance": "可跟踪"}
    apply_indicator_gate(track, macd="金叉/零轴上", rsi=85, trend="向上")
    assert track["stance"] == "可跟踪"
    weak = {"stance": "可跟踪", "trigger": "看支撑。"}
    apply_indicator_gate(weak, macd="死叉/零轴下", rsi=30, trend="向下")
    assert weak["stance"] == "观察"


def test_missing_macd_does_not_raise():
    from backend_core.market_review.picks import apply_indicator_gate, macd_label

    assert macd_label(None, None, None) == "--"
    row = {"stance": "可跟踪", "trigger": "高开不追。"}
    apply_indicator_gate(row, macd=macd_label(None, None, None), rsi=None, trend="--")
    assert row["stance"] == "可跟踪"


def test_render_picks_section():
    snap = {
        "trade_date": "2026-09-18",
        "vol_trillion": 2.0,
        "cb_count": 12,
        "height": 4,
        "season": "秋",
        "viewpoint_md": "v",
        "advice_md": "a",
        "hard_gates": {"rate": "1/5", "items": []},
        "season_detail": {"season": "秋", "cb": 12, "height": 4},
        "rules_json": {
            "summary": "摘要",
            "picks": {
                "disclaimer": "规则合成参考，非投资建议。",
                "note": "",
                "no_chase": [{"code": "600001", "name": "龙头", "board_count": 1, "seal_yi": 1.2, "break_count": 0, "limit_band": "10cm", "stance": "不追", "trigger": "不追"}],
                "track": [],
                "sideline": [],
                "avoid": [],
            },
        },
        "mainline_json": {"rows": [], "summary": "无", "industry_confirm": {"rows": [], "summary": "无"}},
    }
    md = render_markdown(snap)
    assert "明日个股" in md
    assert "不追" in md
    assert "龙头" in md
