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
