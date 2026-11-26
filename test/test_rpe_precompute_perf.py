"""RPE 预计算性能相关：区间内跳过 KDE、批量日线缓存。"""

from __future__ import annotations

from backend_core.strategies.rpe.data_loader import RPEDataLoader
from backend_core.strategies.rpe.strategy_engine import RPEStrategyEngine


def _make_bars(n: int, *, close0: float = 10.0, start: str = "2024-01-01"):
    """生成升序日线；日期仅作占位，不校验日历。"""
    from datetime import datetime, timedelta

    d0 = datetime.strptime(start, "%Y-%m-%d")
    out = []
    for i in range(n):
        d = (d0 + timedelta(days=i)).strftime("%Y-%m-%d")
        c = close0 * (1.0 + 0.001 * (i % 7 - 3))
        out.append(
            {
                "date": d,
                "open": c,
                "high": c * 1.01,
                "low": c * 0.99,
                "close": c,
                "volume": 1_000_000.0,
                "amount": 10_000_000.0,
                "turnover_rate": 1.5,
            }
        )
    return out


def test_evaluate_skips_kde_for_in_band(monkeypatch):
    engine = RPEStrategyEngine(
        db_session=object(),
        config={
            "z_window": 40,
            "lookback_days": 80,
            "kde_lookback_max": 80,
            "z_lead": 2.0,
            "z_catch_up": -1.5,
            "enable_trend_veto": False,
            "liquidity": {"lookback_days": 5, "min_avg_amount": 1.0, "min_avg_turnover_rate": 0.0},
        },
    )
    trade_date = "2024-06-01"
    # 两只走势接近 → Z 落在区间内
    panel = {
        "000001": _make_bars(100, close0=10.0),
        "000002": _make_bars(100, close0=10.05),
    }
    # 截断到 trade_date
    for code, bars in panel.items():
        panel[code] = [b for b in bars if b["date"] <= trade_date]
    date_members = engine.loader.build_date_members(panel)
    from backend_core.strategies.rpe.sector_benchmark import compute_vwap_benchmark

    benchmark = compute_vwap_benchmark(date_members)
    kde_calls = {"n": 0}

    def _boom(*_a, **_k):
        kde_calls["n"] += 1
        raise AssertionError("in_band 不应调用 KDE")

    monkeypatch.setattr(
        "backend_core.strategies.rpe.strategy_engine.extract_kde_levels_expand_support",
        _boom,
    )
    row = engine.evaluate_in_sector(
        "000001",
        sector_id="C1",
        sector_name="概念一",
        panel=panel,
        benchmark=benchmark,
        slope=0.01,
        trade_date=trade_date,
        signal_candidates_only=True,
    )
    assert row is None
    assert kde_calls["n"] == 0


def test_evaluate_runs_kde_for_catch_up(monkeypatch):
    engine = RPEStrategyEngine(
        db_session=object(),
        config={
            "z_window": 40,
            "lookback_days": 80,
            "kde_lookback_max": 80,
            "z_lead": 2.0,
            "z_catch_up": -1.5,
            "enable_trend_veto": False,
            "min_rr_to_resistance": 0.1,
            "liquidity": {"lookback_days": 5, "min_avg_amount": 1.0, "min_avg_turnover_rate": 0.0},
        },
    )
    trade_date = "2024-06-01"
    panel = {
        "000001": _make_bars(100, close0=10.0),
        "000002": _make_bars(100, close0=10.0),
    }
    for code, bars in list(panel.items()):
        panel[code] = [b for b in bars if b["date"] <= trade_date]

    date_members = engine.loader.build_date_members(panel)
    from backend_core.strategies.rpe.sector_benchmark import compute_vwap_benchmark

    benchmark = compute_vwap_benchmark(date_members)
    kde_calls = {"n": 0}

    def _fake_z(*_a, **_k):
        return {
            "z_score": -2.0,
            "ratio": 0.8,
            "price": 10.0,
            "date": trade_date,
            "i_t": 12.0,
        }

    def _fake_kde(*_a, **_k):
        kde_calls["n"] += 1
        price = float(_k.get("price") or 10.0)
        return {
            "support_levels": [price * 0.9],
            "resistance_levels": [price * 1.2],
            "all_peaks": [price * 0.9, price * 1.2],
            "bw": 0.02,
            "ok": True,
            "reason": "ok",
            "lookback_used": 80,
            "lookback_expanded": False,
        }

    monkeypatch.setattr(
        "backend_core.strategies.rpe.strategy_engine.latest_zscore",
        _fake_z,
    )
    monkeypatch.setattr(
        "backend_core.strategies.rpe.strategy_engine.extract_kde_levels_expand_support",
        _fake_kde,
    )
    row = engine.evaluate_in_sector(
        "000001",
        sector_id="C1",
        sector_name="概念一",
        panel=panel,
        benchmark=benchmark,
        slope=0.01,
        trade_date=trade_date,
        signal_candidates_only=True,
    )
    assert row is not None
    assert row.get("signal_type") == "catch_up"
    assert kde_calls["n"] == 1


def test_kde_reused_across_concept_boards(monkeypatch):
    engine = RPEStrategyEngine(
        db_session=object(),
        config={
            "z_window": 40,
            "lookback_days": 80,
            "kde_lookback_max": 80,
            "z_lead": 2.0,
            "z_catch_up": -1.5,
            "enable_trend_veto": False,
            "min_rr_to_resistance": 0.1,
            "liquidity": {"lookback_days": 5, "min_avg_amount": 1.0, "min_avg_turnover_rate": 0.0},
        },
    )
    trade_date = "2024-06-01"
    panel = {
        "000001": _make_bars(100, close0=10.0),
        "000002": _make_bars(100, close0=10.0),
    }
    for code, bars in list(panel.items()):
        panel[code] = [b for b in bars if b["date"] <= trade_date]
    date_members = engine.loader.build_date_members(panel)
    from backend_core.strategies.rpe.sector_benchmark import compute_vwap_benchmark

    benchmark = compute_vwap_benchmark(date_members)
    kde_calls = {"n": 0}

    def _fake_z(*_a, **_k):
        return {
            "z_score": -2.0,
            "ratio": 0.8,
            "price": 10.0,
            "date": trade_date,
            "i_t": 12.0,
        }

    def _fake_kde(*_a, **_k):
        kde_calls["n"] += 1
        price = float(_k.get("price") or 10.0)
        return {
            "support_levels": [price * 0.9],
            "resistance_levels": [price * 1.2],
            "all_peaks": [price * 0.9, price * 1.2],
            "bw": 0.02,
            "ok": True,
            "reason": "ok",
            "lookback_used": 80,
            "lookback_expanded": False,
        }

    monkeypatch.setattr(
        "backend_core.strategies.rpe.strategy_engine.latest_zscore",
        _fake_z,
    )
    monkeypatch.setattr(
        "backend_core.strategies.rpe.strategy_engine.extract_kde_levels_expand_support",
        _fake_kde,
    )
    for sector in ("C1", "C2"):
        row = engine.evaluate_in_sector(
            "000001",
            sector_id=sector,
            sector_name=sector,
            panel=panel,
            benchmark=benchmark,
            slope=0.01,
            trade_date=trade_date,
            signal_candidates_only=True,
        )
        assert row is not None
        assert row.get("signal_type") == "catch_up"
    assert kde_calls["n"] == 1


def test_load_sector_panel_uses_batch_and_cache(monkeypatch):
    loader = RPEDataLoader(db_session=object())
    calls = {"batch": 0, "codes": []}

    def _fake_batch(codes, **kwargs):
        calls["batch"] += 1
        calls["codes"].append(list(codes))
        out = {}
        for c in codes:
            key = loader._bars_cache_key(
                c,
                end_date=kwargs.get("end_date"),
                limit=kwargs.get("limit"),
                adjust=str(kwargs.get("adjust") or "none"),
                factor_source=str(kwargs.get("factor_source") or "auto"),
                refresh_factor=bool(kwargs.get("refresh_factor")),
            )
            bars = _make_bars(30)
            loader._bars_cache[key] = bars
            out[c.zfill(6) if str(c).isdigit() else c] = bars
        return out

    monkeypatch.setattr(loader, "load_bars_batch", _fake_batch)
    p1 = loader.load_sector_panel(["1", "2"], end_date="2024-06-01", lookback=30)
    assert set(p1.keys()) == {"000001", "000002"}
    assert calls["batch"] == 1
