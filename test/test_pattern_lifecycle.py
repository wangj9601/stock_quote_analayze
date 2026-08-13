# -*- coding: utf-8 -*-
"""形态生命周期归档。"""

from datetime import date, timedelta

from backend_core.analysis.chart_patterns.lifecycle import apply_pattern_lifecycle
from backend_core.analysis.chart_patterns.schema import make_hit


def _bars_path(n=80, start=None, path=None):
    """path: 收盘价序列；缺省先涨后跌。"""
    d0 = start or date(2026, 5, 1)
    if path is None:
        path = []
        for i in range(n):
            if i < 30:
                path.append(100 + i * 3)  # 涨到约 187
            else:
                path.append(190 - (i - 30) * 2)  # 回落到约 90
    bars = []
    for i, c in enumerate(path):
        d = d0 + timedelta(days=i)
        bars.append(
            {
                "date": d.isoformat(),
                "open": c,
                "high": c * 1.01,
                "low": c * 0.99,
                "close": c,
            }
        )
    return bars


def test_double_bottom_archived_after_run_and_giveback():
    bars = _bars_path(80)
    hit = make_hit(
        pattern_family="double_extremes",
        pattern_type="double_bottom",
        status="confirmed",
        confidence=0.72,
        reason="双底",
        key_levels={"neckline": 133.53, "l1": 120.0, "l2": 121.0, "last_close": 90.0},
        pivots=[
            {"role": "l1", "date": "2026-05-01", "price": 120.0},
            {"role": "l2", "date": "2026-05-06", "price": 121.0},
        ],
        extra={"formed_at": "2026-05-06"},
    )
    out = apply_pattern_lifecycle([hit], bars)
    assert out[0]["status"] == "archived"
    assert "已归档" in out[0]["reason"] or "生命周期" in out[0]["reason"]


def test_fresh_confirmed_not_archived():
    # 刚确认双底，测幅未走完：颈线 105，谷 100 → 目标≈109.5；现价仅到 107
    bars = _bars_path(20, path=[100 + i * 0.3 for i in range(20)])
    for b in bars:
        b["high"] = float(b["close"]) + 0.2
        b["low"] = float(b["close"]) - 0.2
    hit = make_hit(
        pattern_family="double_extremes",
        pattern_type="double_bottom",
        status="confirmed",
        confidence=0.72,
        reason="双底",
        key_levels={"neckline": 105.0, "l1": 100.0, "l2": 101.0, "last_close": 106.0},
        pivots=[{"role": "l2", "date": bars[0]["date"], "price": 100.0}],
        extra={"formed_at": bars[0]["date"]},
    )
    out = apply_pattern_lifecycle([hit], bars)
    assert out[0]["status"] == "confirmed"


def test_double_top_archived_on_measured_target():
    """测幅目标兑现即归档，无需满 45 根或回吐。"""
    # 峰 100/98，颈线 80 → 高度 20 → 0.9 目标 = 80-18=62
    path = [75.0] * 5 + [50.0] * 10  # 低点 50 已越过目标 62
    bars = _bars_path(len(path), start=date(2026, 6, 15), path=path)
    for b in bars:
        b["low"] = float(b["close"]) * 0.98
        b["high"] = float(b["close"]) * 1.02
    bars[8]["low"] = 50.0
    hit = make_hit(
        pattern_family="double_extremes",
        pattern_type="double_top",
        status="confirmed",
        confidence=0.72,
        reason="双顶",
        key_levels={"neckline": 80.0, "h1": 100.0, "h2": 98.0, "last_close": 50.0},
        pivots=[
            {"role": "H1", "date": "2026-06-01", "price": 100.0},
            {"role": "H2", "date": "2026-06-10", "price": 98.0},
        ],
        extra={"formed_at": "2026-06-15", "confirm_date": "2026-06-15"},
    )
    out = apply_pattern_lifecycle([hit], bars)
    assert out[0]["status"] == "archived"
    assert "测幅目标" in out[0]["reason"]


def test_double_top_archived_on_newer_falling_wedge():
    """旧双顶 vs 后续已确认下降楔上破 → 双顶降权归档（测幅未兑现时）。"""
    # 目标 = 90 - 0.9*(100-90)=81；全部 low=94 > 81 → 测幅未兑现
    path = [95.0] * 20
    bars = _bars_path(len(path), start=date(2026, 6, 15), path=path)
    for b in bars:
        b["low"] = 94.0
        b["high"] = 96.0
    dt = make_hit(
        pattern_family="double_extremes",
        pattern_type="double_top",
        status="confirmed",
        confidence=0.72,
        reason="双顶",
        key_levels={"neckline": 90.0, "h1": 100.0, "h2": 99.0, "last_close": 95.0},
        pivots=[{"role": "H2", "date": "2026-05-14", "price": 99.0}],
        extra={"formed_at": "2026-06-15"},
    )
    fw = make_hit(
        pattern_family="wedge_flag",
        pattern_type="falling_wedge",
        status="confirmed",
        confidence=0.62,
        reason="下降楔",
        key_levels={"upper": 92.0, "lower": 80.0, "last_close": 95.0},
        pivots=[{"role": "upper", "date": "2026-07-27", "price": 92.0}],
        extra={"formed_at": "2026-07-27", "confirm_date": "2026-07-27"},
    )
    out = apply_pattern_lifecycle([dt, fw], bars)
    by_type = {h["pattern_type"]: h for h in out}
    assert by_type["double_top"]["status"] == "archived"
    assert "反向巩固突破" in by_type["double_top"]["reason"]
    assert by_type["falling_wedge"]["status"] == "confirmed"


def test_hs_top_archived_on_failed_break_after_deep_low():
    """头肩顶：曾深破颈线（<颈×0.95）后又回到颈线上方足够远 → 失败破位归档。"""
    neck = 100.0
    # 深破到 94，再回到 103（> 100*1.02）
    path = [98.0] * 3 + [94.0] * 5 + [103.0] * 8
    bars = _bars_path(len(path), start=date(2026, 6, 1), path=path)
    for b in bars:
        b["low"] = float(b["close"]) * 0.995
        b["high"] = float(b["close"]) * 1.005
    bars[4]["low"] = 94.0
    hit = make_hit(
        pattern_family="head_shoulders",
        pattern_type="head_shoulders_top",
        status="confirmed",
        confidence=0.7,
        reason="头肩顶",
        key_levels={"neckline": neck, "head": 120.0, "last_close": 103.0},
        pivots=[
            {"role": "LS", "date": "2026-05-01", "price": 110.0},
            {"role": "head", "date": "2026-05-10", "price": 120.0},
            {"role": "RS", "date": "2026-05-20", "price": 109.0},
        ],
        extra={"formed_at": "2026-06-01", "confirm_date": "2026-06-01"},
    )
    out = apply_pattern_lifecycle([hit], bars)
    assert out[0]["status"] == "archived"
    assert "失败破位" in out[0]["reason"]


def test_hs_bottom_archived_on_failed_break_after_high():
    """头肩底对称：曾深破颈线上沿后又回到颈线下方足够远 → 归档。"""
    neck = 100.0
    # 上冲到 106（>100/0.95），再回到 97（<100/1.02）
    path = [102.0] * 3 + [106.0] * 5 + [97.0] * 8
    bars = _bars_path(len(path), start=date(2026, 6, 1), path=path)
    for b in bars:
        b["low"] = float(b["close"]) * 0.995
        b["high"] = float(b["close"]) * 1.005
    bars[4]["high"] = 106.0
    hit = make_hit(
        pattern_family="head_shoulders",
        pattern_type="head_shoulders_bottom",
        status="confirmed",
        confidence=0.7,
        reason="头肩底",
        key_levels={"neckline": neck, "head": 80.0, "last_close": 97.0},
        pivots=[
            {"role": "LS", "date": "2026-05-01", "price": 90.0},
            {"role": "head", "date": "2026-05-10", "price": 80.0},
            {"role": "RS", "date": "2026-05-20", "price": 91.0},
        ],
        extra={"formed_at": "2026-06-01", "confirm_date": "2026-06-01"},
    )
    out = apply_pattern_lifecycle([hit], bars)
    assert out[0]["status"] == "archived"
    assert "失败破位" in out[0]["reason"]


def test_hs_forming_timeout_archived():
    """形成中头肩：右肩后超过超时根数仍未破颈 → 归档。"""
    from backend_core.analysis.chart_patterns.rules import HS_FORMING_TIMEOUT_BARS

    n = HS_FORMING_TIMEOUT_BARS + 10
    path = [101.0] * n  # 始终在颈线上方，未破颈
    bars = _bars_path(n, start=date(2026, 1, 1), path=path)
    for b in bars:
        b["low"] = 100.5
        b["high"] = 101.5
    hit = make_hit(
        pattern_family="head_shoulders",
        pattern_type="head_shoulders_top",
        status="forming",
        confidence=0.5,
        reason="头肩顶形成中",
        key_levels={"neckline": 100.0, "head": 120.0, "last_close": 101.0},
        pivots=[
            {"role": "LS", "date": bars[0]["date"], "price": 110.0},
            {"role": "head", "date": bars[2]["date"], "price": 120.0},
            {"role": "RS", "date": bars[5]["date"], "price": 109.0},
        ],
    )
    out = apply_pattern_lifecycle([hit], bars)
    assert out[0]["status"] == "archived"
    assert "形成中超时" in out[0]["reason"]


def test_hs_top_archived_on_failed_pullback_near_rs():
    """confirmed 头肩顶：破颈后反抽逼近右肩 → 失败反抽归档（不回 forming）。"""
    neck = 100.0
    rs = 109.0
    # 破颈到 98，再反抽到 108（≥右肩×0.98），未达深破 0.95 路径
    path = [98.0] * 5 + [108.0] * 8
    bars = _bars_path(len(path), start=date(2026, 6, 1), path=path)
    for b in bars:
        b["low"] = float(b["close"]) * 0.995
        b["high"] = float(b["close"]) * 1.005
    bars[2]["low"] = 97.5
    hit = make_hit(
        pattern_family="head_shoulders",
        pattern_type="head_shoulders_top",
        status="confirmed",
        confidence=0.7,
        reason="头肩顶；破颈确认",
        key_levels={
            "neckline": neck,
            "head": 120.0,
            "right_shoulder": rs,
            "last_close": 108.0,
        },
        pivots=[
            {"role": "LS", "date": "2026-05-01", "price": 110.0},
            {"role": "head", "date": "2026-05-10", "price": 120.0},
            {"role": "RS", "date": "2026-05-20", "price": rs},
        ],
        extra={"formed_at": "2026-06-01", "confirm_date": "2026-06-01"},
    )
    out = apply_pattern_lifecycle([hit], bars)
    assert out[0]["status"] == "archived"
    assert "失败反抽" in out[0]["reason"]
    assert out[0]["status"] != "forming"


def test_hs_top_mild_return_above_neck_stays_confirmed():
    """仅小幅回到颈线上方、未逼近右肩且反抽不足 2ATR → 保持 confirmed（不回 forming）。"""
    neck = 100.0
    rs = 120.0
    # 破颈到 99，再回到 101（仅 +1%，远低于右肩，ATR 约 1～2 → 反抽约 2 < 2*ATR）
    path = [99.0] * 10 + [101.0] * 10
    bars = _bars_path(len(path), start=date(2026, 6, 1), path=path)
    for b in bars:
        # 放大 TR 使 ATR 偏大，确保反抽不足 2ATR
        b["low"] = float(b["close"]) - 2.0
        b["high"] = float(b["close"]) + 2.0
    bars[3]["low"] = 98.5
    hit = make_hit(
        pattern_family="head_shoulders",
        pattern_type="head_shoulders_top",
        status="confirmed",
        confidence=0.7,
        reason="头肩顶；破颈确认",
        key_levels={
            "neckline": neck,
            "head": 130.0,
            "right_shoulder": rs,
            "last_close": 101.0,
        },
        pivots=[
            {"role": "LS", "date": "2026-05-01", "price": 118.0},
            {"role": "head", "date": "2026-05-10", "price": 130.0},
            {"role": "RS", "date": "2026-05-20", "price": rs},
        ],
        extra={"formed_at": "2026-06-01", "confirm_date": "2026-06-01"},
    )
    out = apply_pattern_lifecycle([hit], bars)
    assert out[0]["status"] == "confirmed"
    assert "失败反抽" not in (out[0].get("reason") or "")


def test_hs_bottom_archived_on_failed_pullback_near_rs():
    """confirmed 头肩底对称：破颈上破后大幅回撤逼近右肩低点 → 归档。"""
    neck = 100.0
    rs = 91.0
    # 上破到 102，再回撤到 92（≤右肩×1.02）
    path = [102.0] * 5 + [92.0] * 8
    bars = _bars_path(len(path), start=date(2026, 6, 1), path=path)
    for b in bars:
        b["low"] = float(b["close"]) * 0.995
        b["high"] = float(b["close"]) * 1.005
    bars[2]["high"] = 103.0
    hit = make_hit(
        pattern_family="head_shoulders",
        pattern_type="head_shoulders_bottom",
        status="confirmed",
        confidence=0.7,
        reason="头肩底；破颈确认",
        key_levels={
            "neckline": neck,
            "head": 80.0,
            "right_shoulder": rs,
            "last_close": 92.0,
        },
        pivots=[
            {"role": "LS", "date": "2026-05-01", "price": 90.0},
            {"role": "head", "date": "2026-05-10", "price": 80.0},
            {"role": "RS", "date": "2026-05-20", "price": rs},
        ],
        extra={"formed_at": "2026-06-01", "confirm_date": "2026-06-01"},
    )
    out = apply_pattern_lifecycle([hit], bars)
    assert out[0]["status"] == "archived"
    assert "失败反抽" in out[0]["reason"]
    assert out[0]["status"] != "forming"


def test_hs_top_archived_on_failed_pullback_by_atr():
    """confirmed 头肩顶：未逼近右肩，但反抽幅度 ≥ 约 2ATR → 归档。"""
    neck = 100.0
    rs = 130.0  # 很远，不触发右肩条件
    # 破颈到 96（未达深破 0.95 路径），再反抽到 105；TR≈1 → ATR≈1，反抽≥2ATR
    path = [96.0] * 8 + [105.0] * 10
    bars = _bars_path(len(path), start=date(2026, 6, 1), path=path)
    for b in bars:
        b["low"] = float(b["close"]) - 0.5
        b["high"] = float(b["close"]) + 0.5
    bars[2]["low"] = 95.5  # >= neck*0.95，避免走「失败破位」深破分支
    hit = make_hit(
        pattern_family="head_shoulders",
        pattern_type="head_shoulders_top",
        status="confirmed",
        confidence=0.7,
        reason="头肩顶；破颈确认",
        key_levels={
            "neckline": neck,
            "head": 140.0,
            "right_shoulder": rs,
            "last_close": 105.0,
        },
        pivots=[
            {"role": "LS", "date": "2026-05-01", "price": 125.0},
            {"role": "head", "date": "2026-05-10", "price": 140.0},
            {"role": "RS", "date": "2026-05-20", "price": rs},
        ],
        extra={"formed_at": "2026-06-01", "confirm_date": "2026-06-01"},
    )
    out = apply_pattern_lifecycle([hit], bars)
    assert out[0]["status"] == "archived"
    assert "失败反抽" in out[0]["reason"]
    assert "ATR" in out[0]["reason"]