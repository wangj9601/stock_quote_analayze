# -*- coding: utf-8 -*-
"""SEPA 引擎单测（合成 K 线，不连库）。"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend_core.analysis.sepa import (  # noqa: E402
    MarginConfig,
    SEPAConfig,
    TrendConfig,
    VCPConfig,
    assess_margin,
    compute_trend_template,
    detect_vcp,
    evaluate_stock,
    screen_universe,
    to_table_rows,
)

VCP_ANCHORS = [
    (0, 18.5), (60, 19.5), (120, 21.0), (180, 24.0),
    (220, 34.0), (232, 28.5), (246, 33.0), (256, 29.5),
    (266, 32.5), (273, 30.3), (279, 31.6), (288, 31.0), (299, 33.5),
]
VCP_VOL = [(0, 180, 1.0), (180, 220, 1.6), (220, 246, 1.05),
           (246, 266, 0.80), (266, 279, 0.60), (279, 295, 0.45), (295, 300, 2.6)]


def _bars(anchors, vol_segments, seed=7, n=300):
    rng = np.random.default_rng(seed)
    xs = np.array([a[0] for a in anchors], float)
    ys = np.array([a[1] for a in anchors], float)
    close = np.interp(np.arange(n, dtype=float), xs, ys) * (1 + rng.normal(0, 0.004, n))
    vol = np.full(n, 1.0e6)
    for s, e, m in vol_segments:
        vol[s:min(e, n)] = 1.0e6 * m
    vol = vol * rng.uniform(0.9, 1.1, n)
    import pandas as pd

    dates = pd.bdate_range(end="2026-10-29", periods=n)
    rows = []
    prev = close[0]
    for i, d in enumerate(dates):
        o = prev * (1 + rng.normal(0, 0.002))
        rows.append({
            "trade_date": d.strftime("%Y-%m-%d"),
            "open": round(o, 2),
            "high": round(max(o, close[i]) * (1 + abs(rng.normal(0.004, 0.003))), 2),
            "low": round(min(o, close[i]) * (1 - abs(rng.normal(0.004, 0.003))), 2),
            "close": round(float(close[i]), 2),
            "volume": round(float(vol[i]), 0),
        })
        prev = close[i]
    return rows


def _tighten_tail(rows, dist=0.012):
    """把末端收成紧凑平台，最后一根收到平台前高点上方 dist。

    合成 K 线的随机高低点会把突破前 10 日振幅撑过 8%，测不到可执行买点。
    平台取突破前一段的最高价下方，避免改写更早的收缩腿。
    """
    prior = rows[-25:-12]
    pivot_hint = max(r["high"] for r in prior)
    platform = pivot_hint * 0.985
    for r in rows[-11:-1]:
        r["open"] = round(platform * 0.998, 2)
        r["close"] = round(platform, 2)
        r["high"] = round(platform * 1.006, 2)
        r["low"] = round(platform * 0.994, 2)
    last = rows[-1]
    px = round(pivot_hint * (1.0 + dist), 2)
    last["open"] = round(platform, 2)
    last["close"] = px
    last["high"] = round(px * 1.004, 2)
    last["low"] = round(min(platform, px) * 0.998, 2)
    return rows


def _vcp_bars(seed=7):
    return _tighten_tail(_bars(VCP_ANCHORS, VCP_VOL, seed=seed))


def _uptrend_bars(seed=18):
    return _bars([(0, 18.0), (299, 33.0)], [(0, 300, 1.0)], seed=seed)


def _downtrend_bars(seed=30):
    return _bars([(0, 34.0), (299, 17.5)], [(0, 300, 1.0)], seed=seed)


def _margin_rows(kind="reflow", n=90, seed=7):
    rng = np.random.default_rng(seed + 1)
    t = np.arange(n)
    if kind == "reflow":
        base = 1.00e9 - 0.25e9 * np.clip(t / 72.0, 0, 1)
        base[-6:] = base[-6] * (1 + np.linspace(0, 0.045, 6))
        mv = 2.0e10
    elif kind == "crowded":
        base = 1.00e9 + 0.20e9 * np.clip(t / 60.0, 0, 1)
        mv = 1.5e10
    else:
        base = 1.20e9 - 0.45e9 * np.clip(t / 89.0, 0, 1)
        mv = 2.0e10
    rzye = base * (1 + rng.normal(0, 0.004, n))
    delta = np.diff(np.concatenate([[rzye[0]], rzye]))
    rzmre = np.where(delta > 0, 2.0e8, 1.0e8)
    rzche = rzmre - delta
    import pandas as pd

    dates = pd.bdate_range(end="2026-10-29", periods=n)
    return [{
        "trade_date": d.strftime("%Y-%m-%d"),
        "rzye": round(float(rzye[i]), 0),
        "rzmre": round(float(rzmre[i]), 0),
        "rzche": round(float(max(rzche[i], 0)), 0),
        "float_mv": mv,
    } for i, d in enumerate(dates)]


def test_trend_template_pass():
    res = compute_trend_template(_vcp_bars(), rs_rank=95.0)
    assert res["ok"] is True, res["failed"]
    assert res["ok_count"] == 8
    assert res["metrics"]["off_high_pct"] > -25


def test_trend_template_reject_downtrend():
    res = compute_trend_template(_downtrend_bars(), rs_rank=10.0)
    assert res["ok"] is False
    assert res["ok_count"] <= 3


def test_trend_reject_when_rs_missing():
    res = compute_trend_template(_vcp_bars(), rs_rank=None)
    assert res["ok"] is False
    assert res["conditions"][8] is False


def test_trend_insufficient_bars():
    res = compute_trend_template(_vcp_bars()[:100], rs_rank=90.0)
    assert res["ok"] is False
    assert res["reason"] == "k_bars_insufficient"


def test_vcp_breakout_detected():
    res = detect_vcp(_vcp_bars(), cfg=VCPConfig())
    assert res["count"] >= 3, res["count"]
    assert res["status"] == "breakout", res["status"]
    assert 31.0 <= res["pivot"] <= 33.0, res["pivot"]
    assert res["vol_ratio"] >= 1.5
    depths = [c["depth_pct"] for c in res["contractions"]]
    assert depths == sorted(depths, reverse=True), depths


def test_vcp_none_for_smooth_uptrend():
    res = detect_vcp(_uptrend_bars(), cfg=VCPConfig())
    assert res["status"] != "breakout"
    assert res["count"] < 2


def test_margin_reflow_and_crowded():
    reflow = assess_margin(_margin_rows("reflow"), cfg=MarginConfig())
    assert reflow["status"] == "reflow", reflow["status"]
    assert reflow["score"] >= 70

    crowded = assess_margin(_margin_rows("crowded"), cfg=MarginConfig())
    assert crowded["status"] == "crowded"
    assert crowded["score"] < 40


def test_margin_no_data_neutral():
    res = assess_margin([], cfg=MarginConfig())
    assert res["status"] == "no_data"
    assert res["score"] == MarginConfig().neutral_score


def test_evaluate_stock_tier_a():
    res = evaluate_stock(
        _vcp_bars(), code="600000.SH", name="合成突破", rs_rank=90.0,
        margin_rows=_margin_rows("reflow"), cfg=SEPAConfig(),
    )
    assert res["ok"] is True
    assert res["tier"] == "A", (res["tier"], res["score"])
    assert res["vcp"]["status"] == "breakout"
    assert res["margin"]["status"] == "reflow"


def test_evaluate_stock_downtrend_short_circuit():
    res = evaluate_stock(_downtrend_bars(), code="600002.SH", rs_rank=5.0)
    assert res["ok"] is False
    assert res["vcp"] is None
    assert res["reason"] == "trend_template_failed"


def test_screen_universe_filters_and_ranks():
    bars = {
        "600000.SH": _vcp_bars(),
        "600001.SH": _uptrend_bars(),
        "600002.SH": _downtrend_bars(),
        "600003.SH": _vcp_bars(seed=31),
    }
    margins = {"600000.SH": _margin_rows("reflow"), "600003.SH": _margin_rows("crowded")}
    picks = screen_universe(bars, margin_by_code=margins, cfg=SEPAConfig())
    codes = [p["code"] for p in picks]
    assert "600002.SH" not in codes          # 下跌趋势必须剔除
    assert "600001.SH" not in codes          # 无 VCP 必须剔除
    assert codes[0] == "600000.SH"           # 突破+回流排第一
    assert picks[0]["tier"] == "A"

    rows = to_table_rows(picks)
    assert rows[0]["vcp_status_label"] == "放量突破"
    assert rows[0]["margin_status_label"] == "回流确认"


def test_forming_included_when_requested():
    picks = screen_universe(
        {"600001.SH": _uptrend_bars()}, cfg=SEPAConfig(), include_forming=True
    )
    assert isinstance(picks, list)


def test_screen_report_funnel_counts():
    """漏斗计数必须与实际返回一致，否则前端面板的通过率会失真。"""
    from backend_core.analysis.sepa.screener import screen_report

    bars = {
        "600000.SH": _vcp_bars(seed=7),
        "600001.SH": _uptrend_bars(),
        "600002.SH": _downtrend_bars(),
    }
    rep = screen_report(bars, margin_by_code={"600000.SH": _margin_rows("reflow")})
    stats, rows = rep["stats"], rep["rows"]
    assert stats["universe"] == 3
    assert stats["trend_pass"] <= 3
    assert (
        stats["breakout"] + stats["quiet"] + stats["ready"]
        + stats["extended"] + stats["forming"]
    ) == stats["vcp_any"]
    assert all(r["vcp"]["status"] != "forming" for r in rows)   # 默认不含收缩中
    assert len(rows) <= stats["breakout"] + stats["ready"]


def test_enforce_last_depth_downgrades_breakout():
    """末次收缩过深时不能给出可执行状态——这是校准后新增的硬门槛。"""
    bars = _vcp_bars(seed=13)
    loose = detect_vcp(bars, cfg=VCPConfig(max_last_depth=0.99, enforce_last_depth=True))
    tight = detect_vcp(bars, cfg=VCPConfig(max_last_depth=0.001, enforce_last_depth=True))
    off = detect_vcp(bars, cfg=VCPConfig(max_last_depth=0.001, enforce_last_depth=False))
    assert loose["status"] in ("breakout", "ready")
    assert tight["status"] not in ("breakout", "ready")      # 门槛生效
    assert tight["ok"] is False
    assert "last_contraction_too_deep" in tight["notes"]
    assert off["status"] == loose["status"]                  # 关掉开关即恢复原判定


def test_excluded_name_covers_st_and_delist():
    from backend_core.analysis.sepa.loaders import is_excluded_name

    assert is_excluded_name("*ST海润")
    assert is_excluded_name("ST国华")
    assert is_excluded_name("S*ST前锋")
    assert is_excluded_name("退市海润")
    assert is_excluded_name("贵州茅台") is False
    assert is_excluded_name("") is False


def test_single_leg_is_not_breakout():
    res = detect_vcp(_uptrend_bars(), cfg=VCPConfig())
    assert res["status"] not in ("breakout", "quiet", "ready")
    assert res["ok"] is False


def test_quiet_when_price_clears_pivot_without_volume():
    bars = _vcp_bars()
    bars[-1]["volume"] = 1
    res = detect_vcp(bars, cfg=VCPConfig())
    assert res["count"] >= 2, res["count"]
    assert res["status"] == "quiet", (res["status"], res["dist_to_pivot_pct"], res["notes"], res["base_tight_range_pct"])
    assert res["ok"] is True
    assert res["invalidation"] is not None


def test_extended_above_chase_is_not_actionable():
    """同一根末端，把可执行距离收到实际距离之下，应标成远离枢轴。"""
    res = detect_vcp(_vcp_bars(), cfg=VCPConfig(chase_distance=0.005))
    assert res["dist_to_pivot_pct"] is not None and res["dist_to_pivot_pct"] > 0.5
    assert res["status"] == "extended", (res["status"], res["dist_to_pivot_pct"], res["notes"])
    assert res["ok"] is False
    assert "chase_risk" in res["notes"]


def test_no_data_margin_stays_actionable_tier():
    res = evaluate_stock(_vcp_bars(), code="600000", rs_rank=90.0, margin_rows=[], cfg=SEPAConfig())
    if res["vcp"] and res["vcp"]["status"] in ("breakout", "ready", "quiet"):
        assert res["tier"] == "A", (res["tier"], res["vcp"]["status"])
        assert res["margin"]["status"] == "no_data"


def test_prefer_ready_ranking_is_switchable():
    from backend_core.analysis.sepa.screener import _rank_map

    assert _rank_map(True)["ready"] > _rank_map(True)["breakout"]
    assert _rank_map(False)["breakout"] > _rank_map(False)["ready"]


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {fn.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
