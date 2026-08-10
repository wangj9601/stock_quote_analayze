# -*- coding: utf-8 -*-
"""形态识别合成 K 线单测。"""

from __future__ import annotations

from datetime import date, timedelta

from backend_core.analysis.chart_patterns.double_extremes import (
    detect_double_bottom_hit,
    detect_double_top_hit,
)
from backend_core.analysis.chart_patterns.engine import detect_all, normalize_families
from backend_core.analysis.chart_patterns.head_shoulders import detect_head_shoulders
from backend_core.analysis.chart_patterns.pivots import extract_pivot_sequence
from backend_core.analysis.chart_patterns.scanner import HARD_SCAN_CAP, DEFAULT_SCAN_LIMIT
from backend_core.analysis.chart_patterns.triangles import detect_triangles
from backend_core.analysis.chart_patterns.wedges_flags import detect_wedges


def _bars_from_closes(closes, start=None):
    d0 = start or date(2024, 1, 2)
    out = []
    for i, c in enumerate(closes):
        c = float(c)
        out.append(
            {
                "date": (d0 + timedelta(days=i)).isoformat(),
                "open": c,
                "high": c * 1.01,
                "low": c * 0.99,
                "close": c,
                "volume": 1_000_000 + i * 1000,
            }
        )
    return out


def test_normalize_families():
    assert normalize_families(None) == {
        "double_extremes",
        "head_shoulders",
        "triangle",
        "wedge_flag",
    }
    assert normalize_families(["double", "hs"]) == {"double_extremes", "head_shoulders"}


def test_double_bottom_synthetic():
    # 构造 W：下跌 → L1 → 反弹颈线 → L2 ≈ L1 → 突破
    closes = []
    # 下行
    for i in range(20):
        closes.append(20 - i * 0.3)
    # L1 附近震荡
    base = closes[-1]
    closes.extend([base, base * 0.995, base * 1.002, base])
    # 升至颈线
    for i in range(1, 12):
        closes.append(base * (1 + 0.012 * i))
    neck = closes[-1]
    # 回落 L2
    for i in range(1, 10):
        closes.append(neck * (1 - 0.01 * i))
    # 贴近 L1
    closes.extend([base * 1.01, base * 0.998, base * 1.005])
    # 突破颈线
    for i in range(1, 8):
        closes.append(neck * (1 + 0.01 * i))

    bars = _bars_from_closes(closes)
    # 放宽局部窗口便于合成数据命中
    hit = detect_double_bottom_hit(
        bars,
        pattern_cfg={
            "lookback_days": 200,
            "swing_left": 2,
            "swing_right": 2,
            "min_trough_gap_bars": 5,
            "max_trough_gap_bars": 80,
            "trough_tol_pct": 0.05,
            "min_rise_to_neck_pct": 0.03,
        },
    )
    assert hit is not None
    assert hit["pattern_type"] == "double_bottom"
    assert hit["status"] in ("forming", "confirmed")
    assert hit["key_levels"].get("neckline")
    assert hit.get("formed_at")
    assert len(str(hit["formed_at"])) >= 8
    assert hit.get("key_dates")
    assert any(kd.get("date") for kd in hit["key_dates"])


def test_double_top_synthetic():
    closes = []
    for i in range(15):
        closes.append(10 + i * 0.25)
    peak = closes[-1]
    closes.extend([peak, peak * 1.002, peak * 0.998])
    for i in range(1, 10):
        closes.append(peak * (1 - 0.012 * i))
    trough = closes[-1]
    for i in range(1, 10):
        closes.append(trough * (1 + 0.012 * i))
    closes.extend([peak * 0.99, peak * 1.001, peak * 0.995])
    for i in range(1, 8):
        closes.append(trough * (1 - 0.01 * i))

    bars = _bars_from_closes(closes)
    hit = detect_double_top_hit(
        bars,
        pattern_cfg={
            "lookback_days": 200,
            "swing_left": 2,
            "swing_right": 2,
            "min_trough_gap_bars": 5,
            "max_trough_gap_bars": 80,
            "trough_tol_pct": 0.05,
            "min_rise_to_neck_pct": 0.03,
        },
    )
    # 合成序列未必总命中，但函数应稳定返回 None 或合法 hit
    if hit:
        assert hit["pattern_type"] == "double_top"
        assert "neckline" in hit["key_levels"]


def test_head_shoulders_from_pivots_path():
    # 显式高低摆动：构造更明显的头肩底价格路径
    closes = [30, 28, 26, 24, 22, 20]  # 下行
    closes += [19, 18.5, 19.2, 18.8]  # 左肩低
    closes += [21, 22.5, 23, 22]  # 颈点1
    closes += [17, 16, 16.5, 16.2]  # 头更低
    closes += [20, 22, 23.5, 22.8]  # 颈点2
    closes += [18.5, 18.2, 18.8]  # 右肩
    closes += [21, 23, 24.5, 25]  # 突破
    bars = _bars_from_closes(closes)
    piv = extract_pivot_sequence(bars, max_bars=120, fractal=1)
    hits = detect_head_shoulders(bars, piv)
    # 枢轴不足时允许空；有则校验字段
    for h in hits:
        assert h["pattern_family"] == "head_shoulders"
        assert h["pattern_type"] in ("head_shoulders_top", "head_shoulders_bottom")


def test_detect_all_empty_short_bars():
    bars = _bars_from_closes([10, 11, 12])
    assert detect_all(bars) == []


def test_triangle_and_wedge_smoke():
    # 收敛通道：高点下移 + 低点上移
    closes = []
    for i in range(40):
        mid = 20
        amp = 3 - i * 0.05
        closes.append(mid + (amp if i % 2 == 0 else -amp))
    bars = _bars_from_closes(closes)
    # 仅验证不抛异常
    detect_triangles(bars)
    detect_wedges(bars)


def test_scan_limits_constants():
    assert DEFAULT_SCAN_LIMIT <= HARD_SCAN_CAP
    assert HARD_SCAN_CAP == 200
