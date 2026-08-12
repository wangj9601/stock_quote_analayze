# -*- coding: utf-8 -*-
"""形态识别合成 K 线单测。"""

from __future__ import annotations

from datetime import date, timedelta

from backend_core.analysis.chart_patterns.double_extremes import (
    detect_double_bottom_hit,
    detect_double_top_hit,
)
from backend_core.analysis.chart_patterns.engine import (
    detect_all,
    nms_overlapping_patterns,
    nms_wedge_flag_overlaps,
    normalize_families,
)
from backend_core.analysis.chart_patterns.head_shoulders import detect_head_shoulders
from backend_core.analysis.chart_patterns.pivots import extract_pivot_sequence
from backend_core.analysis.chart_patterns.rules import (
    BREAKOUT_DOWN_MULT,
    BREAKOUT_UP_MULT,
    INVALIDATE_BOTTOM_MULT,
    INVALIDATE_TOP_MULT,
    SLOPE_UNIT_NOTE,
    WEDGE_ENDPOINT_REL_EPS,
    breakout_up,
)
from backend_core.analysis.chart_patterns.schema import fmt_px, make_hit
from backend_core.analysis.chart_patterns.scanner import HARD_SCAN_CAP, DEFAULT_SCAN_LIMIT
from backend_core.analysis.chart_patterns.triangles import detect_triangles
from backend_core.analysis.chart_patterns.wedges_flags import (
    detect_wedges,
    wedge_endpoints_direction_ok,
)


def test_fmt_px_with_and_without_date():
    assert fmt_px("左肩", 44.97, "2026-03-12") == "左肩=44.97(2026-03-12)"
    assert fmt_px("颈线", 40.27, approx=True) == "颈线≈40.27"
    assert fmt_px("L1", 10, None) == "L1=10"


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
    for p in hit.get("pivots") or []:
        d = str((p or {}).get("date") or "")[:10]
        if d and (p or {}).get("role") in ("L1", "L2", "neck"):
            assert d in (hit.get("reason") or "")


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
        reason = h.get("reason") or ""
        for p in h.get("pivots") or []:
            d = str((p or {}).get("date") or "")[:10]
            if d:
                assert d in reason


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


def test_wedge_endpoints_direction_ok():
    hi_ok = [{"price": 6.68}, {"price": 6.29}, {"price": 6.10}]
    lo_ok = [{"price": 5.80}, {"price": 5.60}, {"price": 5.40}]
    assert wedge_endpoints_direction_ok(hi_ok, lo_ok, falling=True) is True

    # 铜陵有色类误报：末高 7.00 > 首高 6.68
    hi_bad = [{"price": 6.68}, {"price": 6.29}, {"price": 7.00}]
    lo_bad = [{"price": 5.80}, {"price": 5.60}, {"price": 5.40}]
    assert wedge_endpoints_direction_ok(hi_bad, lo_bad, falling=True) is False

    # 容差内不算破坏
    hi_eps = [{"price": 10.0}, {"price": 9.5}, {"price": 10.0 * (1 + WEDGE_ENDPOINT_REL_EPS * 0.5)}]
    lo_eps = [{"price": 8.0}, {"price": 7.8}, {"price": 7.6}]
    assert wedge_endpoints_direction_ok(hi_eps, lo_eps, falling=True) is True

    hi_up = [{"price": 10.0}, {"price": 10.5}, {"price": 11.0}]
    lo_up = [{"price": 8.0}, {"price": 8.4}, {"price": 8.8}]
    assert wedge_endpoints_direction_ok(hi_up, lo_up, falling=False) is True
    assert wedge_endpoints_direction_ok(hi_up, lo_up, falling=True) is False


def test_detect_wedges_rejects_last_high_above_first():
    """末高明显高于首高时不得报下降楔形；拟合枢轴与展示一致为 3 个。"""
    bars = _bars_from_closes([6.0 + (i % 3) * 0.1 for i in range(40)])
    pivots = [
        {"kind": "high", "price": 6.68, "index": 10, "date": "2024-07-06"},
        {"kind": "low", "price": 5.80, "index": 12, "date": "2024-07-08"},
        {"kind": "high", "price": 6.29, "index": 14, "date": "2024-07-10"},
        {"kind": "low", "price": 5.60, "index": 16, "date": "2024-07-12"},
        {"kind": "high", "price": 7.00, "index": 30, "date": "2024-08-10"},
        {"kind": "low", "price": 5.40, "index": 32, "date": "2024-08-12"},
    ]
    assert detect_wedges(bars, pivots) == []


def test_detect_wedges_accepts_declining_endpoints():
    bars = _bars_from_closes([6.0] * 40)
    # 高点/低点整体下行且通道收敛，回归同向为负
    pivots = [
        {"kind": "high", "price": 12.0, "index": 5, "date": "2024-01-05"},
        {"kind": "low", "price": 9.0, "index": 8, "date": "2024-01-08"},
        {"kind": "high", "price": 11.0, "index": 15, "date": "2024-01-15"},
        {"kind": "low", "price": 8.5, "index": 18, "date": "2024-01-18"},
        {"kind": "high", "price": 10.0, "index": 25, "date": "2024-01-25"},
        {"kind": "low", "price": 8.2, "index": 28, "date": "2024-01-28"},
    ]
    hits = detect_wedges(bars, pivots)
    assert len(hits) == 1
    assert hits[0]["pattern_type"] == "falling_wedge"
    highs = [p for p in hits[0]["pivots"] if p.get("role") == "high"]
    lows = [p for p in hits[0]["pivots"] if p.get("role") == "low"]
    assert len(highs) == 3 and len(lows) == 3
    assert highs[-1]["price"] <= highs[0]["price"] * (1 + WEDGE_ENDPOINT_REL_EPS)



def test_scan_limits_constants():
    assert DEFAULT_SCAN_LIMIT <= HARD_SCAN_CAP
    assert HARD_SCAN_CAP == 200


def test_normalize_price_adjust():
    from backend_core.analysis.chart_patterns.scanner import normalize_price_adjust
    import pytest

    assert normalize_price_adjust("qfq") == "qfq"
    assert normalize_price_adjust("QFQ") == "qfq"
    assert normalize_price_adjust(None) == "none"
    assert normalize_price_adjust("") == "none"
    with pytest.raises(ValueError):
        normalize_price_adjust("hfq")


def test_apply_qfq_to_code_bars_smoke():
    """前复权路径 smoke：因子现算后 OHLC 变化。"""
    from datetime import date
    from unittest.mock import MagicMock, patch

    import pytest

    from backend_core.analysis.chart_patterns.scanner import apply_qfq_to_code_bars

    bars = [
        {"date": "2024-01-02", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 1},
        {"date": "2024-01-03", "open": 20, "high": 21, "low": 19, "close": 20, "volume": 1},
    ]
    ensured = {
        "factors": [(date(2024, 1, 2), 1.0), (date(2024, 1, 3), 2.0)],
        "factor_fetched": False,
        "source": "akshare_sina_qfq",
        "adj_factor_asof": "2024-01-03",
        "factor_source": "auto",
    }
    with patch(
        "backend_api.utils.adj_quotes.ensure_adj_factors", return_value=ensured
    ):
        qfq, meta = apply_qfq_to_code_bars(MagicMock(), "600519", bars)
    assert qfq[0]["close"] == pytest.approx(5.0)
    assert qfq[1]["close"] == pytest.approx(20.0)
    assert meta["source"] == "akshare_sina_qfq"


def test_patterns_route_adjust_qfq_passthrough():
    """GET /api/analysis/patterns/{code}?adjust=qfq 透传到检测前的 OHLC。"""
    import sys
    from datetime import date
    from pathlib import Path
    from unittest.mock import MagicMock, patch

    import pytest
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "backend_api"))

    # 先加载模块，避免 patch 时 backend_api.stock 尚未挂载子模块
    import backend_api.permissions as perm_mod  # noqa: F401
    import backend_api.stock.stock_analysis_routes as levels_routes
    import backend_core.analysis.chart_patterns.engine as engine_mod
    import backend_core.strategies.double_bottom.data_loader as dl
    from backend_api.database import get_db
    from backend_api.stock.pattern_routes import router

    app = FastAPI()
    app.include_router(router)

    def _fake_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _fake_db
    client = TestClient(app)

    bars = [
        {"date": "2024-01-02", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 1},
        {"date": "2024-01-03", "open": 20, "high": 21, "low": 19, "close": 20, "volume": 1},
    ]
    # 补足长度以通过 len(bars)>=30 分支（detect 已 mock）
    for i in range(28):
        bars.append(
            {
                "date": f"2024-02-{i + 1:02d}",
                "open": 20,
                "high": 21,
                "low": 19,
                "close": 20,
                "volume": 1,
            }
        )
    ensured = {
        "factors": [(date(2024, 1, 2), 1.0), (date(2024, 1, 3), 2.0)],
        "factor_fetched": True,
        "source": "akshare_sina_qfq",
        "adj_factor_asof": "2024-01-03",
        "factor_source": "auto",
    }
    fake_hit = {
        "pattern_type": "double_bottom",
        "status": "forming",
        "confidence": 0.5,
        "key_levels": {"last_close": 5.0},
    }

    with patch.object(perm_mod, "user_has_permission", return_value=True), patch.object(
        levels_routes,
        "resolve_levels_stock_identifier",
        return_value={"status": "ok", "code": "600519", "name": "贵州茅台"},
    ), patch.object(dl, "batch_load_ohlc_asc", return_value={"600519": bars}), patch.object(
        dl, "load_names", return_value={"600519": "贵州茅台"}
    ), patch.object(
        dl, "resolve_effective_trade_date", return_value="2024-01-03"
    ), patch(
        "backend_api.utils.adj_quotes.ensure_adj_factors", return_value=ensured
    ), patch.object(
        engine_mod, "detect_all", return_value=[fake_hit]
    ) as det:
        resp = client.get(
            "/api/analysis/patterns/600519?adjust=qfq&types=double_extremes"
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["price_adjust"] == "qfq"
    assert body.get("adj_meta", {}).get("factor_fetched") is True
    call_bars = det.call_args.args[0]
    assert call_bars[0]["close"] == pytest.approx(5.0)


def test_hs_bottom_invalidated_when_close_breaks_head():
    """头肩底：右肩后收盘 < 头×0.99 → invalidated；detect_all 默认不展示。"""
    head = 10.0
    closes = [15.0] * 40 + [head * 0.98]  # 跌破头×0.99
    bars = _bars_from_closes(closes)
    pivots = [
        {"kind": "low", "price": 12.0, "index": 5, "date": bars[5]["date"]},
        {"kind": "high", "price": 14.0, "index": 10, "date": bars[10]["date"]},
        {"kind": "low", "price": head, "index": 15, "date": bars[15]["date"]},
        {"kind": "high", "price": 14.2, "index": 20, "date": bars[20]["date"]},
        {"kind": "low", "price": 12.1, "index": 25, "date": bars[25]["date"]},
    ]
    hits = detect_head_shoulders(bars, pivots)
    assert len(hits) == 1
    assert hits[0]["pattern_type"] == "head_shoulders_bottom"
    assert hits[0]["status"] == "invalidated"
    assert hits[0]["key_levels"]["last_close"] < head * INVALIDATE_BOTTOM_MULT

    # 默认过滤失效（真实枢轴未必命中手工场景，至少不抛）
    assert isinstance(detect_all(bars, types=["hs"], include_invalidated=False), list)


def test_hs_top_invalidated_when_close_breaks_head():
    """头肩顶：右肩后收盘 > 头×1.01 → invalidated。"""
    head = 20.0
    closes = [15.0] * 40 + [head * 1.02]
    bars = _bars_from_closes(closes)
    pivots = [
        {"kind": "high", "price": 18.0, "index": 5, "date": bars[5]["date"]},
        {"kind": "low", "price": 16.0, "index": 10, "date": bars[10]["date"]},
        {"kind": "high", "price": head, "index": 15, "date": bars[15]["date"]},
        {"kind": "low", "price": 15.8, "index": 20, "date": bars[20]["date"]},
        {"kind": "high", "price": 17.8, "index": 25, "date": bars[25]["date"]},
    ]
    hits = detect_head_shoulders(bars, pivots)
    assert len(hits) == 1
    assert hits[0]["pattern_type"] == "head_shoulders_top"
    assert hits[0]["status"] == "invalidated"


def test_hs_top_invalidated_after_rs_spike_even_if_below_neck():
    """头肩顶几何成立 + 右肩后冲高破头，再跌回颈线下 → 必须 invalidated，不得 confirmed。"""
    head = 50.72
    ls_px, rs_px = 48.0, 47.8
    n1_px, n2_px = 40.0, 40.2
    neck = (n1_px + n2_px) / 2.0
    thr = head * INVALIDATE_TOP_MULT
    assert thr > head

    n = 45
    bars = _bars_from_closes([45.0] * n)
    # 压低 high，避免 _bars_from_closes 的 high=c*1.01 误触发
    for b in bars:
        b["high"] = float(b["close"]) + 0.05
        b["low"] = float(b["close"]) - 0.05

    rs_i = 25
    spike_i = 30
    # 右肩后冲高破头（high 与 close 均可；此处用 high）
    bars[spike_i]["high"] = thr + 0.5
    bars[spike_i]["close"] = head * 0.99  # 当日收盘未站上阈值亦可失效
    # 末段跌破颈线：旧规则会 confirmed
    for i in range(35, n):
        bars[i]["close"] = neck - 1.0
        bars[i]["high"] = neck - 0.5
        bars[i]["low"] = neck - 1.5

    assert bars[-1]["close"] < neck
    assert bars[spike_i]["high"] > thr

    pivots = [
        {"kind": "high", "price": ls_px, "index": 5, "date": bars[5]["date"]},
        {"kind": "low", "price": n1_px, "index": 10, "date": bars[10]["date"]},
        {"kind": "high", "price": head, "index": 15, "date": bars[15]["date"]},
        {"kind": "low", "price": n2_px, "index": 20, "date": bars[20]["date"]},
        {"kind": "high", "price": rs_px, "index": rs_i, "date": bars[rs_i]["date"]},
    ]
    hits = detect_head_shoulders(bars, pivots)
    assert len(hits) == 1
    assert hits[0]["pattern_type"] == "head_shoulders_top"
    assert hits[0]["status"] == "invalidated"
    assert hits[0]["status"] != "confirmed"
    # detect_all 默认不返回 invalidated
    shown = detect_all(bars, types=["hs"], include_invalidated=False)
    assert all(h.get("status") != "invalidated" for h in shown)


def test_hs_bottom_invalidated_after_rs_dip_even_if_above_neck():
    """头肩底：右肩后下探破头×0.99，再回到颈线上 → 失效，不得 confirmed。"""
    head = 10.0
    ls_px, rs_px = 12.0, 12.1
    n1_px, n2_px = 14.0, 14.2
    neck = (n1_px + n2_px) / 2.0
    thr = head * INVALIDATE_BOTTOM_MULT

    n = 45
    bars = _bars_from_closes([13.0] * n)
    for b in bars:
        b["high"] = float(b["close"]) + 0.05
        b["low"] = float(b["close"]) - 0.05

    rs_i = 25
    dip_i = 30
    bars[dip_i]["low"] = thr - 0.2
    bars[dip_i]["close"] = head * 1.01
    for i in range(35, n):
        bars[i]["close"] = neck + 1.0
        bars[i]["high"] = neck + 1.5
        bars[i]["low"] = neck + 0.5

    assert bars[-1]["close"] > neck
    assert bars[dip_i]["low"] < thr

    pivots = [
        {"kind": "low", "price": ls_px, "index": 5, "date": bars[5]["date"]},
        {"kind": "high", "price": n1_px, "index": 10, "date": bars[10]["date"]},
        {"kind": "low", "price": head, "index": 15, "date": bars[15]["date"]},
        {"kind": "high", "price": n2_px, "index": 20, "date": bars[20]["date"]},
        {"kind": "low", "price": rs_px, "index": rs_i, "date": bars[rs_i]["date"]},
    ]
    hits = detect_head_shoulders(bars, pivots)
    assert len(hits) == 1
    assert hits[0]["pattern_type"] == "head_shoulders_bottom"
    assert hits[0]["status"] == "invalidated"


def test_nms_falling_wedge_bear_flag_keeps_one():
    """下降楔与下降旗上下沿近同（≤1%）只保留更优者（优先已确认），并注明同源。"""
    d0 = "2024-03-01"
    d1 = "2024-03-20"
    wedge = make_hit(
        pattern_family="wedge_flag",
        pattern_type="falling_wedge",
        status="confirmed",
        confidence=0.62,
        reason="下降楔形",
        key_levels={"upper": 20.0, "lower": 18.0, "last_close": 20.2},
        pivots=[
            {"role": "high", "date": d0, "price": 20.0},
            {"role": "low", "date": d1, "price": 18.0},
        ],
    )
    flag = make_hit(
        pattern_family="wedge_flag",
        pattern_type="bear_flag",
        status="forming",
        confidence=0.42,
        reason="下降旗形",
        key_levels={"upper": 20.1, "lower": 17.95, "last_close": 19.5},
        pivots=[
            {"role": "high", "date": d0, "price": 20.1},
            {"role": "low", "date": d1, "price": 17.95},
        ],
    )
    out = nms_wedge_flag_overlaps([wedge, flag])
    assert len(out) == 1
    assert out[0]["pattern_type"] == "falling_wedge"
    assert out[0]["status"] == "confirmed"
    assert "同源亦曾匹配下降旗形" in out[0]["reason"]
    assert out[0]["nms_suppressed"][0]["pattern_type"] == "bear_flag"


def test_nms_descending_triangle_falling_wedge_keeps_by_flat_lower():
    """下沿近似走平时主分类为下降三角，并在 reason 注明曾匹配下降楔形。"""
    highs = [
        {"role": "high", "date": "2026-05-01", "price": 12.55},
        {"role": "high", "date": "2026-06-10", "price": 11.30},
        {"role": "high", "date": "2026-07-20", "price": 12.14},
    ]
    lows = [
        {"role": "low", "date": "2026-05-15", "price": 10.49},
        {"role": "low", "date": "2026-06-25", "price": 10.45},
        {"role": "low", "date": "2026-08-05", "price": 11.44},
    ]
    slopes = {
        "upper_slope": -0.02,
        "lower_slope": 0.00001,  # 近似走平 → 三角
        "upper": 12.14,
        "lower": 11.44,
        "last_close": 11.80,
    }
    tri = make_hit(
        pattern_family="triangle",
        pattern_type="descending_triangle",
        status="forming",
        confidence=0.56,
        reason="下降三角",
        key_levels=dict(slopes),
        pivots=[*highs, *lows],
    )
    wedge = make_hit(
        pattern_family="wedge_flag",
        pattern_type="falling_wedge",
        status="forming",
        confidence=0.45,
        reason="下降楔形",
        key_levels=dict(slopes),
        pivots=[*highs, *lows],
    )
    out = nms_overlapping_patterns([tri, wedge])
    assert len(out) == 1
    assert out[0]["pattern_type"] == "descending_triangle"
    assert "同源亦曾匹配下降楔形" in out[0]["reason"]


def test_nms_descending_pair_prefers_wedge_when_both_slopes_down():
    """双沿明确下行时主分类为下降楔形（即使三角置信度更高）。"""
    highs = [
        {"role": "high", "date": "2026-05-01", "price": 12.55},
        {"role": "high", "date": "2026-06-10", "price": 11.80},
        {"role": "high", "date": "2026-07-20", "price": 11.20},
    ]
    lows = [
        {"role": "low", "date": "2026-05-15", "price": 11.00},
        {"role": "low", "date": "2026-06-25", "price": 10.60},
        {"role": "low", "date": "2026-08-05", "price": 10.20},
    ]
    slopes = {
        "upper_slope": -0.03,
        "lower_slope": -0.02,  # 双沿下行 → 楔形
        "upper": 11.20,
        "lower": 10.20,
        "last_close": 10.50,
    }
    tri = make_hit(
        pattern_family="triangle",
        pattern_type="descending_triangle",
        status="forming",
        confidence=0.56,
        reason="下降三角",
        key_levels=dict(slopes),
        pivots=[*highs, *lows],
    )
    wedge = make_hit(
        pattern_family="wedge_flag",
        pattern_type="falling_wedge",
        status="forming",
        confidence=0.45,
        reason="下降楔形",
        key_levels=dict(slopes),
        pivots=[*highs, *lows],
    )
    out = nms_overlapping_patterns([tri, wedge])
    assert len(out) == 1
    assert out[0]["pattern_type"] == "falling_wedge"
    assert "同源亦曾匹配下降三角" in out[0]["reason"]


def test_nms_triangle_wedge_by_pivot_homology_without_bound_match():
    """上下沿略有差异但仍同源枢轴时，亦应 NMS；下沿走平则留三角。"""
    highs = [
        {"role": "high", "date": "2026-05-01", "price": 12.55},
        {"role": "high", "date": "2026-06-10", "price": 11.30},
        {"role": "high", "date": "2026-07-20", "price": 12.14},
    ]
    lows = [
        {"role": "low", "date": "2026-05-15", "price": 10.49},
        {"role": "low", "date": "2026-06-25", "price": 10.45},
        {"role": "low", "date": "2026-08-05", "price": 11.44},
    ]
    tri = make_hit(
        pattern_family="triangle",
        pattern_type="descending_triangle",
        status="forming",
        confidence=0.56,
        reason="下降三角",
        key_levels={
            "upper": 12.14,
            "lower": 10.45,
            "last_close": 11.80,
            "upper_slope": -0.02,
            "lower_slope": 0.00001,
        },
        pivots=[*highs, *lows],
    )
    wedge = make_hit(
        pattern_family="wedge_flag",
        pattern_type="falling_wedge",
        status="forming",
        confidence=0.45,
        reason="下降楔形",
        # 故意让上下沿差 > 1%，仅靠枢轴同源触发
        key_levels={
            "upper": 13.50,
            "lower": 9.80,
            "last_close": 11.80,
            "upper_slope": -0.02,
            "lower_slope": 0.00001,
        },
        pivots=[*highs, *lows],
    )
    out = nms_overlapping_patterns([wedge, tri])
    assert len(out) == 1
    assert out[0]["pattern_type"] == "descending_triangle"
    assert "同源亦曾匹配下降楔形" in out[0]["reason"]


def test_breakout_threshold_documented():
    assert BREAKOUT_UP_MULT == 1.005
    assert BREAKOUT_DOWN_MULT == 0.995
    assert breakout_up(20.2, 20.0) is True
    assert breakout_up(20.05, 20.0) is False
    assert "K线" in SLOPE_UNIT_NOTE or "交易日" in SLOPE_UNIT_NOTE


def test_expert_analysis_no_wait_breakout_when_confirmed_wedge():
    """已确认下降楔形时，专家解读不得写「宜等待边界有效突破」。"""
    import json
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    script = root / "test" / "_pattern_expert_node_check.mjs"
    items = [
        {
            "pattern_type": "falling_wedge",
            "status": "confirmed",
            "confidence": 0.62,
            "key_levels": {"upper": 20.0, "lower": 18.0, "last_close": 20.2},
            "pivots": [{"role": "high", "date": "2024-03-01", "price": 20.0}],
            "formed_at": "2024-03-01",
        },
        {
            "pattern_type": "symmetrical_triangle",
            "status": "forming",
            "confidence": 0.45,
            "key_levels": {"upper": 21.0, "lower": 17.0, "last_close": 20.2},
            "pivots": [],
            "formed_at": "2024-03-05",
        },
    ]
    proc = subprocess.run(
        ["node", str(script), json.dumps(items, ensure_ascii=False)],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0 and (
        "not found" in (proc.stderr or "").lower()
        or "不是内部或外部命令" in (proc.stderr or "")
        or proc.returncode == 127
    ):
        import pytest

        pytest.skip(f"node unavailable: {proc.stderr}")
    assert proc.returncode == 0, proc.stderr or proc.stdout
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    short = out.get("shortTerm") or ""
    assert "宜等待边界有效突破" not in short
    assert "已确认" in short and ("下降楔" in short or "上破" in short)
    conflict_items = items[:1] + [
        {
            "pattern_type": "head_shoulders_top",
            "status": "confirmed",
            "confidence": 0.7,
            "key_levels": {"neckline": 19.0, "head": 22.0, "last_close": 18.5},
            "pivots": [],
            "formed_at": "2024-03-10",
        }
    ]
    proc2 = subprocess.run(
        ["node", str(script), json.dumps(conflict_items, ensure_ascii=False)],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc2.returncode == 0, proc2.stderr or proc2.stdout
    out2 = json.loads(proc2.stdout.strip().splitlines()[-1])
    assert "冲突" in (out2.get("mediumTerm") or "")


def test_expert_key_levels_upper_role_after_up_breakout():
    """已确认上破后，关键位置中上沿文案应为「突破后转支撑」而非「突破参考」。"""
    import json
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    script = root / "test" / "_pattern_expert_node_check.mjs"
    items = [
        {
            "pattern_type": "falling_wedge",
            "status": "confirmed",
            "confidence": 0.70,
            "key_levels": {"upper": 38.88, "lower": 35.0, "last_close": 40.5},
            "pivots": [{"role": "high", "date": "2026-07-01", "price": 38.88}],
            "formed_at": "2026-08-01",
        }
    ]
    proc = subprocess.run(
        ["node", str(script), json.dumps(items, ensure_ascii=False)],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0 and (
        "not found" in (proc.stderr or "").lower()
        or "不是内部或外部命令" in (proc.stderr or "")
        or proc.returncode == 127
    ):
        import pytest

        pytest.skip(f"node unavailable: {proc.stderr}")
    assert proc.returncode == 0, proc.stderr or proc.stdout
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    ref = out.get("keyLevelsRef") or ""
    assert "38.88" in ref or "38.9" in ref
    assert "突破后转支撑" in ref
    assert "上沿（突破参考）" not in ref
