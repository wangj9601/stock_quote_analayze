# -*- coding: utf-8 -*-
"""GMS 信号：KDE 支撑/阻力写入 score_detail.structure 与读路径展平。"""

from backend_core.strategies.gms.config import GMSConfigManager
from backend_core.strategies.gms.structure_levels import (
    compute_structure_levels,
    empty_structure,
    flatten_structure_to_result,
)


def _bars_with_clusters(n=90):
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


def test_compute_structure_levels_synthetic_bars():
    cfg = GMSConfigManager().get_default_config()
    bars = _bars_with_clusters(90)
    st = compute_structure_levels(bars, cfg, price=15.2)
    assert st.get("method") == "kde_volume_weighted"
    assert "support_levels" in st
    assert "resistance_levels" in st
    assert "nearest_support" in st
    assert "nearest_resistance" in st
    assert "kde_ok" in st


def test_empty_structure_on_insufficient_bars():
    st = compute_structure_levels([], {}, price=10.0)
    assert st["kde_ok"] is False
    assert st["method"] == "kde_volume_weighted"
    assert st["support_levels"] == []


def test_screen_writes_structure_into_score_detail(monkeypatch):
    """screen 结果应含 score_detail.structure，并与顶层 nearest_* 一致。"""
    from backend_core.strategies.gms import strategy_engine as se
    from backend_core.strategies.gms.models import GMSIndicators

    cfg = GMSConfigManager().get_default_config()
    bars = _bars_with_clusters(90)

    class _Loader:
        def load_indicators(self, *a, **k):
            return [
                {
                    "code": "000001",
                    "date": "2026-08-04",
                    "market_type": "CN",
                    "macro_displacement_delta": 0.5,
                    "ma20_d": 14.0,
                    "ratio_d20": 0.01,
                    "ratio_d1": 0.02,
                    "instant_deviation": 1.2,
                    "rising_days_z": 8,
                    "falling_days_f": 12,
                    "mavol20_m": 1e6,
                    "efficiency_m20_minus_m": 2e5,
                    "ratio_d": 0.01,
                    "current_volume": 1.2e6,
                    "volume_ratio": 1.2,
                    "d1": 13.0,
                    "d20": 15.2,
                }
            ]

        def load_indicators_multi_day(self, *a, **k):
            return []

        def load_bars(self, *a, **k):
            return bars

    ind = GMSIndicators(
        code="000001",
        date="2026-08-04",
        market_type="CN",
        delta=0.5,
        d=14.0,
        instant_deviation=1.2,
        ratio_d20=0.01,
        ratio_d1=0.02,
        ratio_d=0.01,
        rising_days=8,
        falling_days=12,
        avg_volume_20d=1e6,
        current_volume=1.2e6,
        volume_ratio=1.2,
        fz_ratio=1.5,
        score_accumulation=70.0,
        score_balance=0.0,
        score_momentum=60.0,
        score_total=70.0,
        accumulation_grade="A",
        momentum_grade="",
    )
    ind.raw_row = {"d1_date": None, "d20_date": "2026-08-04"}

    class _Calc:
        accumulation_fz_min = 1.5
        balance_ratio_max = 0.01
        momentum_volume_ratio_min = 1.5
        acc_s_threshold = 85
        acc_a_threshold = 70
        mom_full_threshold = 90
        mom_batch_threshold = 80
        acc_fz_tiers = [2.5, 1.5]
        balance_tiers = [0.01, 0.015]
        vol_shrink_tiers = [0.6, 0.8]
        ratio_d1_tiers = [0.001, 0.03]
        vol_attack_tiers = [2.0, 1.5]
        weight_acc_fz = 30
        weight_acc_balance = 40
        weight_acc_volume = 30
        weight_mom_ratio_d1 = 40
        weight_mom_deviation = 30
        weight_mom_volume = 30

        def calculate(self, row, instant_deviation_series=None):
            return ind

    class _Det:
        def detect_left_buy(self, i):
            return False

        def detect_right_buy(self, i):
            return False

        def detect_sell(self, i):
            return False

    engine = se.GMSStrategyEngine(_Loader(), cfg)
    engine.calculator = _Calc()
    engine.detector = _Det()
    engine.stable_days = 1

    out = engine.screen(["000001"], "2026-08-04", "CN", min_score=0)
    assert len(out) == 1
    sd = out[0].get("score_detail") or {}
    st = sd.get("structure") or {}
    assert st.get("method") == "kde_volume_weighted"
    assert "support_levels" in st
    assert out[0].get("nearest_support") == st.get("nearest_support")
    assert out[0].get("nearest_resistance") == st.get("nearest_resistance")


def test_trace_row_to_result_flattens_structure():
    from backend_core.strategies.gms import frontend_interface as gfi

    class _Row:
        code = "000009"
        date = "2026-08-04"
        market_type = "CN"
        score_total = 80.0
        score_accumulation = 75.0
        score_momentum = 60.0
        left_buy_signal = False
        right_buy_signal = True
        buy_type = "右侧"
        signal_strength = 0.8
        sell_signal = False
        delta = 0.5
        d = 14.0
        ratio_d20 = 0.01
        ratio_d1 = 0.02
        fz_ratio = 1.5
        rising_days = 8
        falling_days = 12
        instant_deviation = 1.2
        score_acc_fz = 20.0
        score_acc_balance = 30.0
        score_acc_volume = 25.0
        score_mom_ratio_d1 = 20.0
        score_mom_deviation = 20.0
        score_mom_volume = 20.0
        acc_fz_judge = ""
        acc_balance_judge = ""
        acc_volume_judge = ""
        mom_ratio_d1_judge = ""
        mom_deviation_judge = ""
        mom_volume_judge = ""
        accumulation_grade = "A"
        momentum_grade = ""
        risk_tags = []
        score_detail = {
            "ratio_d": 0.01,
            "avg_volume_20d": 1e6,
            "current_volume": 1.2e6,
            "structure": {
                "method": "kde_volume_weighted",
                "support_levels": [14.5, 13.0],
                "resistance_levels": [16.0],
                "nearest_support": 14.5,
                "nearest_resistance": 16.0,
                "kde_ok": True,
                "kde_reason": "ok",
                "kde_lookback_used": 250,
            },
        }

    out = gfi._trace_row_to_result(_Row())
    assert out["nearest_support"] == 14.5
    assert out["nearest_resistance"] == 16.0
    assert out["support_levels"] == [14.5, 13.0]
    assert (out["score_detail"].get("structure") or {}).get("method") == "kde_volume_weighted"


def test_attach_trace_score_detail_preserves_structure():
    from backend_api.stock import gms_trace_routes as routes

    row = {
        "code": "000001",
        "date": "2026-08-04",
        "market_type": "CN",
        "score_total": 70.0,
        "score_accumulation": 70.0,
        "score_momentum": 50.0,
        "score_detail": {
            "structure": {
                "method": "kde_volume_weighted",
                "nearest_support": 14.5,
                "nearest_resistance": 16.0,
                "support_levels": [14.5],
                "resistance_levels": [16.0],
                "kde_ok": True,
            },
            "ratio_d": 0.01,
            "avg_volume_20d": 1e6,
            "current_volume": 1.2e6,
            "ma60_d": 13.0,
        },
        "ratio_d": 0.01,
        "avg_volume_20d": 1e6,
        "current_volume": 1.2e6,
        "ma60_d": 13.0,
    }
    cfg = GMSConfigManager().get_default_config()
    calc_meta = {
        "accumulation_fz_min": 1.5,
        "balance_ratio_max": 0.01,
        "momentum_volume_ratio_min": 1.5,
        "accumulation_s_threshold": 85,
        "accumulation_a_threshold": 70,
        "momentum_full_threshold": 90,
        "momentum_batch_threshold": 80,
        "acc_fz_tiers": [2.5, 1.5],
        "balance_tiers": [0.01, 0.015],
        "vol_shrink_tiers": [0.6, 0.8],
        "ratio_d1_tiers": [0.001, 0.03],
        "vol_attack_tiers": [2.0, 1.5],
        "weight_acc_fz": 30,
        "weight_acc_balance": 40,
        "weight_acc_volume": 30,
        "weight_mom_ratio_d1": 40,
        "weight_mom_deviation": 30,
        "weight_mom_volume": 30,
    }
    out = routes._attach_trace_score_detail(
        db=None,
        row_dict=row,
        config=cfg,
        gms_config_meta={"strategy_config_id": 1},
        calc_meta=calc_meta,
    )
    st = (out.get("score_detail") or {}).get("structure") or {}
    assert st.get("nearest_support") == 14.5
    assert out.get("nearest_support") == 14.5
    assert out.get("nearest_resistance") == 16.0


def test_flatten_structure_helper():
    result = {}
    flatten_structure_to_result(result, empty_structure())
    assert result["nearest_support"] is None
    assert result["support_levels"] == []


def test_result_needs_structure_detects_missing():
    from backend_core.strategies.gms.frontend_interface import result_needs_structure

    assert result_needs_structure({"score_detail": {}}) is True
    assert result_needs_structure({"score_detail": {"structure": {}}}) is True
    assert (
        result_needs_structure(
            {
                "score_detail": {
                    "structure": {
                        "method": "kde_volume_weighted",
                        "nearest_support": None,
                    }
                }
            }
        )
        is False
    )


def test_enrich_results_with_structure_when_trace_lacks_it(monkeypatch):
    """读出的选股结果无 structure 时，应补算并展平 nearest_*。"""
    from backend_core.strategies.gms import frontend_interface as gfi

    bars = _bars_with_clusters(90)
    cfg = GMSConfigManager().get_default_config()

    class _Loader:
        def load_bars(self, *a, **k):
            return bars

    monkeypatch.setattr(gfi, "GMSDataLoader", lambda db: _Loader())
    persisted = []

    def _fake_persist(db, **kw):
        persisted.append(kw)

    monkeypatch.setattr(gfi, "_persist_structure_to_trace", _fake_persist)

    results = [
        {
            "code": "601138",
            "symbol": "601138",
            "date": "2026-08-04",
            "market_type": "CN",
            "d": 15.2,
            "score_detail": {"ratio_d": 0.01, "avg_volume_20d": 1e6},
        }
    ]
    n = gfi.enrich_results_with_structure(
        db=None,
        results=results,
        config=cfg,
        date="2026-08-04",
        config_id=1,
        persist=True,
    )
    assert n == 1
    st = (results[0].get("score_detail") or {}).get("structure") or {}
    assert st.get("method") == "kde_volume_weighted"
    assert "nearest_support" in results[0]
    assert "nearest_resistance" in results[0]
    assert results[0].get("nearest_support") == st.get("nearest_support")
    assert len(persisted) == 1
    assert persisted[0]["code"] == "601138"
    assert persisted[0]["structure"].get("method") == "kde_volume_weighted"


def test_enrich_skips_when_structure_already_present(monkeypatch):
    from backend_core.strategies.gms import frontend_interface as gfi

    called = []

    class _Loader:
        def load_bars(self, *a, **k):
            called.append(1)
            return []

    monkeypatch.setattr(gfi, "GMSDataLoader", lambda db: _Loader())
    results = [
        {
            "code": "601138",
            "date": "2026-08-04",
            "market_type": "CN",
            "score_detail": {
                "structure": {
                    "method": "kde_volume_weighted",
                    "nearest_support": 34.49,
                    "nearest_resistance": 62.02,
                }
            },
            "nearest_support": 34.49,
            "nearest_resistance": 62.02,
        }
    ]
    n = gfi.enrich_results_with_structure(
        db=None,
        results=results,
        config={},
        date="2026-08-04",
        config_id=1,
        persist=False,
    )
    assert n == 0
    assert called == []
    assert results[0]["nearest_support"] == 34.49
