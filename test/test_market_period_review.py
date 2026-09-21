# -*- coding: utf-8 -*-
"""周报 / 月报区间与个股规则。"""

from datetime import date

from backend_core.market_review.period import (
    aggregate_daily_rows,
    period_bounds,
    previous_bounds,
    reconstruct_period_pct,
    select_persistent,
    weekday_gaps,
)
from backend_core.market_review.period_picks import (
    TRIGGER_MONTH,
    TRIGGER_WEEK,
    apply_period_triggers,
    assemble_period_picks,
    chase_threshold,
)
from backend_core.market_review.period_render import (
    build_period_review_pdf_bytes,
    render_period_markdown,
)


def test_clean_industry_drops_nan():
    from backend_core.market_review.period_render import clean_industry_name

    assert clean_industry_name("nan") == ""
    assert clean_industry_name("NaN") == ""
    assert clean_industry_name("半导体") == "半导体"


def test_period_bounds_week_and_month():
    start, end, key = period_bounds("week", date(2026, 9, 18))
    assert start == date(2026, 9, 14)
    assert end == date(2026, 9, 20)
    assert key.startswith("2026-W")
    prev_start, prev_end, _prev = previous_bounds("week", start)
    assert prev_end == date(2026, 9, 13)
    assert prev_start == date(2026, 9, 7)

    start, end, key = period_bounds("month", date(2026, 9, 18))
    assert (start, end, key) == (date(2026, 9, 1), date(2026, 9, 30), "2026-09")
    prev_start, prev_end, prev_key = previous_bounds("month", start)
    assert (prev_start, prev_end, prev_key) == (date(2026, 8, 1), date(2026, 8, 31), "2026-08")


def test_reconstruct_period_pct_uses_prior_close():
    pct = reconstruct_period_pct(10, 10, 12)
    assert round(pct, 2) == 32.0
    assert round(reconstruct_period_pct(10, None, 12), 2) == 20.0


def test_weekday_gaps_and_persistent_rules():
    gaps = weekday_gaps(date(2026, 9, 14), date(2026, 9, 18), ["2026-09-14", "2026-09-16"])
    assert gaps == ["2026-09-15", "2026-09-17", "2026-09-18"]
    boards = [
        {"board_code": "A", "hit_days": 1, "last_day_hit": True},
        {"board_code": "B", "hit_days": 2, "last_day_hit": False},
    ]
    short = select_persistent(boards, 2, "week")
    assert [b["board_code"] for b in short] == ["A"]
    full = select_persistent(boards, 4, "week")
    assert [b["board_code"] for b in full] == ["B"]
    month = select_persistent(
        [{"board_code": "C", "hit_days": 3, "last_day_hit": False}],
        10,
        "month",
    )
    assert [b["board_code"] for b in month] == ["C"]
    assert select_persistent([{"board_code": "D", "hit_days": 2}], 10, "month") == []


def _stat(pct, close=10, mid=8, last_change=1.0):
    return {
        "period_pct": pct,
        "last_close": close,
        "mid": mid,
        "last_change": last_change,
        "name": "测试",
        "period_high": 11,
        "period_low": 5,
    }


def _base_kwargs(**over):
    kw = dict(
        kind="week",
        constituents={},
        stats={},
        zt_rows=[],
        roles={},
        daily_track_counts={},
        season="春",
        gates_passed=3,
        gates_total=5,
        tape_label="放量普涨",
        tape_volume="expand",
        has_main=True,
        sideline_rows=[],
        faded=[],
        last_avoid=[],
    )
    kw.update(over)
    return kw


def test_limit_up_not_track_and_extended_is_no_chase():
    assert chase_threshold("week", "000001") == 15
    assert chase_threshold("week", "300001") == 25
    assert chase_threshold("month", "000001") == 30
    assert chase_threshold("month", "300001") == 45
    picks = assemble_period_picks(
        **_base_kwargs(
            constituents={
                "000001": {"name": "平安银行", "industry": "银行", "overlap_days": 3},
                "000002": {"name": "万科", "industry": "地产", "overlap_days": 3},
                "300001": {"name": "特锐德", "industry": "电力", "overlap_days": 2},
            },
            stats={
                "000001": _stat(3),
                "000002": _stat(16),
                "300001": _stat(20),
            },
            zt_rows=[{"code": "000001", "name": "平安银行", "board_count": 2, "seal_yi": 1.2, "break_count": 1}],
        )
    )
    codes = {r["code"] for r in picks["track"]}
    assert "000001" not in codes
    assert "000002" not in codes
    assert "300001" in codes
    chase = {r["code"]: r["stance"] for r in picks["no_chase"]}
    assert chase["000001"] == "炸板不追"
    assert chase["000002"] == "不追"
    assert "次日" not in picks["no_chase"][0]["trigger"]
    assert picks["track"][0]["trigger"] == TRIGGER_WEEK


def test_retreat_has_no_track_and_industry_cap():
    faded = assemble_period_picks(
        **_base_kwargs(
            tape_volume="shrink",
            tape_label="缩量调整",
            constituents={"000001": {"name": "平安银行", "industry": "银行", "overlap_days": 2}},
            stats={"000001": _stat(3)},
            faded=[{"code": "000001", "name": "平安银行", "reason": "由强转弱"}],
        )
    )
    assert faded["mode"] == "retreat"
    assert faded["track"] == []
    assert faded["no_chase"] == []
    assert faded["avoid"] and faded["avoid"][0]["reason"] == "由强转弱"

    constituents = {
        f"00000{i}": {"name": f"票{i}", "industry": "银行", "overlap_days": i}
        for i in range(1, 7)
    }
    stats = {code: _stat(4 + i) for i, code in enumerate(constituents)}
    capped = assemble_period_picks(**_base_kwargs(constituents=constituents, stats=stats))
    assert capped["track_cap"] == 8
    assert len(capped["track"]) == 4

    month_trigger = assemble_period_picks(
        **_base_kwargs(
            kind="month",
            constituents={"000001": {"name": "平安银行", "industry": "银行", "overlap_days": 6}},
            stats={"000001": _stat(8)},
        )
    )
    assert month_trigger["track"][0]["trigger"] == TRIGGER_MONTH


def test_apply_period_triggers_replaces_next_day_text():
    picks = {
        "no_chase": [{"stance": "不追", "trigger": "次日只看溢价，不追。"}],
        "track": [{"stance": "可跟踪", "trigger": "次日回踩。"}],
    }
    apply_period_triggers(picks, "week")
    assert picks["no_chase"][0]["trigger"] == TRIGGER_WEEK
    assert "次日" not in picks["track"][0]["trigger"]


def test_markdown_height_integer_and_pdf_smoke():
    rows = [
        {
            "trade_date": "2026-09-14",
            "height": 5,
            "cb_count": 9,
            "vol_trillion": 2.1,
            "season": "秋",
            "hard_gates": {"items": [{"id": 2, "name": "连板家数", "standard": "≥ 13家", "passed": False}]},
            "rules_json": {"market_env": {"indexes": [{"name": "上证指数", "close": 3800, "pct_chg": 1.0}]}, "tape": {"label": "平量观察"}},
            "mainline_json": {"rows": [{"board_code": "C1", "board_name": "通信设备", "today_hit": True, "tier_label": "主线", "echelon": "持续"}]},
        },
        {
            "trade_date": "2026-09-18",
            "height": 4,
            "cb_count": 12,
            "vol_trillion": 2.4,
            "season": "秋",
            "hard_gates": {"items": [{"id": 2, "name": "连板家数", "standard": "≥ 13家", "passed": True}]},
            "rules_json": {"market_env": {"indexes": [{"name": "上证指数", "close": 3900, "pct_chg": 0.5}]}, "tape": {"label": "放量普涨"}},
            "mainline_json": {"rows": [{"board_code": "C1", "board_name": "通信设备", "today_hit": True, "tier_label": "主线", "echelon": "持续"}]},
        },
    ]
    snap = aggregate_daily_rows(
        rows,
        kind="week",
        start=date(2026, 9, 14),
        end=date(2026, 9, 20),
        period_key="2026-W38",
    )
    assert snap["delta"]["height"]["from"] == 5
    assert snap["gates"][0]["passed_days"] == 1
    assert snap["persistent_mainlines"][0]["board_name"] == "通信设备"
    snap["picks"] = {
        "disclaimer": TRIGGER_WEEK and "规则合成参考，非投资建议。这是下周计划，不是按周五收盘价买入。",
        "note": "",
        "mode": "plan",
        "no_chase": [],
        "track": [{"code": "000001", "name": "平安银行", "industry": "银行", "stance": "可跟踪", "period_pct": 4.2, "pattern": "head_shoulders_bottom", "trigger": TRIGGER_WEEK}],
        "sideline": [],
        "avoid": [],
    }
    snap["viewpoint_md"] = "区间观点"
    snap["advice_md"] = "不追高开"
    md = render_period_markdown(snap)
    assert "5 → 4（-1板）" in md
    assert "9 → 12（+3家）" in md
    assert "5.00" not in md
    assert "头肩底" in md
    assert "次日" not in md
    pdf = build_period_review_pdf_bytes(snap)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 500
