"""
验证图片中幅度计算及指标与 PVFRS 对齐。
- 幅度 = |Δ|
- ratio_d20 = Δ/d20, ratio_d1 = Δ/d1
- is_sideways: |Δ| < ε
"""
import pytest
from backend_core.strategies.pvfrs.analyzers import PriceDimensionAnalyzer
from backend_core.strategies.pvfrs.models import MarketData, PVFRSIndicators
from backend_core.strategies.pvfrs.strategy_engine import StrategyEngine


def _make_data(d1_close: float, d20_close: float, n: int = 20) -> list:
    """构造 20 天数据，首尾为 d1、d20，中间线性插值。"""
    data = []
    for i in range(n):
        t = i / (n - 1) if n > 1 else 1.0
        close = d1_close + (d20_close - d1_close) * t
        data.append(
            MarketData(
                "000001",
                f"2024-01-{i+1:02d}",
                close,
                close + 0.1,
                close - 0.05,
                close,
                1_000_000,
                1e7,
            )
        )
    data[0] = MarketData("000001", "2024-01-01", d1_close, d1_close + 0.1, d1_close - 0.05, d1_close, 1_000_000, 1e7)
    data[-1] = MarketData("000001", "2024-01-20", d20_close, d20_close + 0.1, d20_close - 0.05, d20_close, 1_000_000, 1e7)
    return data


def test_amplitude_ratio_d20_ratio_d1_is_sideways():
    """PriceDimensionAnalyzer.analyze 包含 amplitude、ratio_d20、ratio_d1、is_sideways。"""
    d1, d20 = 10.0, 11.0
    data = _make_data(d1, d20)
    pa = PriceDimensionAnalyzer()
    r = pa.analyze(data)

    assert "amplitude" in r
    assert "ratio_d20" in r
    assert "ratio_d1" in r
    assert "is_sideways" in r
    assert "d1" in r
    assert "d20" in r

    delta = d20 - d1
    assert r["macro_displacement"] == delta
    assert r["amplitude"] == abs(delta)
    assert r["d1"] == d1
    assert r["d20"] == d20
    assert r["ratio_d20"] == pytest.approx(delta / d20)
    assert r["ratio_d1"] == pytest.approx(delta / d1)
    assert r["is_sideways"] is False


def test_is_sideways_when_delta_near_zero():
    """|Δ| < ε 时 is_sideways 为 True。"""
    d1 = d20 = 10.0
    data = _make_data(d1, d20)
    pa = PriceDimensionAnalyzer(amplitude_flat_threshold=1e-6)
    r = pa.analyze(data)

    assert r["macro_displacement"] == 0.0
    assert r["amplitude"] == 0.0
    assert r["is_sideways"] is True
    assert r["ratio_d20"] == 0.0
    assert r["ratio_d1"] == 0.0


def test_pvfrs_indicators_has_new_fields():
    """StrategyEngine.analyze_stock 产出的 PVFRSIndicators 包含新字段。"""
    data = _make_data(10.0, 11.0)
    eng = StrategyEngine()
    ind = eng.analyze_stock("000001", data)

    assert ind.amplitude is not None
    assert ind.ratio_d20 is not None
    assert ind.ratio_d1 is not None
    assert ind.is_sideways is not None
    assert ind.amplitude == 1.0
    assert ind.ratio_d20 == pytest.approx(1.0 / 11.0)
    assert ind.ratio_d1 == pytest.approx(0.1)
    assert ind.is_sideways is False
