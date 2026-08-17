# -*- coding: utf-8 -*-
"""URT 信号历史：重算写入 KDE 支撑/阻力，查询时展平。"""

from backend_core.strategies.urt.config import URTConfigManager
from backend_core.strategies.urt.signal_detector import evaluate_buy_signal


def _bars_with_clusters(n=80):
    import random

    random.seed(11)
    bars = []
    for i in range(n):
        cluster = [13.0, 15.0, 17.0][i % 3]
        close = round(cluster + random.uniform(-0.08, 0.08), 2)
        bars.append(
            {
                "date": f"2026-{(8 if i < 30 else 7):02d}-{max(1, 28 - (i % 28)):02d}",
                "open": close - 0.2,
                "close": close,
                "volume": 1_000_000 + (i % 3) * 400_000,
                "turnover_rate": 2.0,
            }
        )
    bars[0]["close"] = 15.2
    bars[0]["open"] = 14.8
    bars[0]["volume"] = 4_000_000
    for i in range(1, 5):
        bars[i]["close"] = 15.0 + i * 0.05
        bars[i]["open"] = bars[i]["close"] - 0.15
        bars[i]["volume"] = 3_000_000
    return bars


def test_evaluate_buy_signal_structure_ready_for_trace_upsert():
    """强制重算每日调用 evaluate 后，score_detail.structure 应可写入记录表。"""
    cfg = URTConfigManager().get_default_config()
    bars = _bars_with_clusters(90)
    detail = evaluate_buy_signal(bars, cfg, require_pass=False)
    assert detail is not None
    sd = detail.get("score_detail") or {}
    st = sd.get("structure") or {}
    assert st.get("method") in (
        "structural_kde+confluence",
        "structural_kde",
        "kde_volume_weighted",
    )
    assert "support_levels" in st
    assert "resistance_levels" in st
    assert "nearest_support" in st or st.get("nearest_support") is None
    assert "structure_level_source" in st or st.get("structure_level_source") is None
    # 与顶层字段一致，便于 upsert / 查询展平
    assert detail.get("support_levels") == st.get("support_levels")
    assert detail.get("resistance_levels") == st.get("resistance_levels")


def test_query_trace_by_code_flattens_structure(monkeypatch):
    from backend_core.strategies.urt import trace_store as ts

    class _Row:
        code = "000009"
        name = "中国宝安"
        date = "2026-08-04"
        config_id = 1
        buy_signal = True
        score = 80.0
        close = 15.2
        open = 14.8
        ma20 = 14.0
        above_ma20 = True
        yang_count_4 = 3
        yang_count_5 = 4
        yang_rule = "4d3"
        volume = 1e6
        avg_volume_20 = 5e5
        volume_multiple = 2.0
        volume_ratio = 1.2
        turnover_rate = 3.0
        score_detail = {
            "structure": {
                "method": "kde_volume_weighted",
                "support_levels": [14.5, 13.0],
                "resistance_levels": [16.0],
                "nearest_support": 14.5,
                "nearest_resistance": 16.0,
                "kde_ok": True,
                "kde_reason": "ok",
                "kde_lookback_used": 250,
            }
        }

    class _Q:
        def filter(self, *a, **k):
            return self

        def order_by(self, *a, **k):
            return self

        def limit(self, *a, **k):
            return self

        def all(self):
            return [_Row()]

    class _DB:
        def query(self, *a, **k):
            return _Q()

    rows = ts.query_trace_by_code(_DB(), code="000009", config_id=1, limit=10)
    assert len(rows) == 1
    assert rows[0]["nearest_support"] == 14.5
    assert rows[0]["nearest_resistance"] == 16.0
    assert rows[0]["support_levels"] == [14.5, 13.0]
