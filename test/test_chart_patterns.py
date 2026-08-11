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
from backend_core.analysis.chart_patterns.schema import fmt_px
from backend_core.analysis.chart_patterns.scanner import HARD_SCAN_CAP, DEFAULT_SCAN_LIMIT
from backend_core.analysis.chart_patterns.triangles import detect_triangles
from backend_core.analysis.chart_patterns.wedges_flags import detect_wedges


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
