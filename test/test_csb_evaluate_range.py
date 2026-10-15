# -*- coding: utf-8 -*-
"""CSB evaluate_range 与逐日 evaluate_one 金标一致。"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from backend_core.strategies.csb.strategy_engine import (
    _hits_for_stock_dates,
    evaluate_one,
    evaluate_range,
)


GOLD_KEYS = (
    "signal_type",
    "entry_signal",
    "setup_ok",
    "score",
    "channel_lower",
    "channel_upper",
    "squeeze_days",
)


def _synth_bars(n: int = 320, start: float = 10.0) -> List[Dict[str, Any]]:
    bars: List[Dict[str, Any]] = []
    px = start
    for i in range(n):
        px = max(1.0, px * (1.0 + ((i % 11) - 5) * 0.002))
        bars.append(
            {
                "date": f"2025-{(i // 28) % 12 + 1:02d}-{(i % 28) + 1:02d}",
                "open": px * 0.998,
                "high": px * 1.01,
                "low": px * 0.99,
                "close": px,
                "volume": 800_000 + (i % 40) * 20_000,
                "turnover_rate": 1.0 + (i % 8) * 0.08,
            }
        )
    return bars


def _row_gold(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {k: row.get(k) for k in GOLD_KEYS}


def test_evaluate_range_matches_evaluate_one_per_day():
    bars = _synth_bars(300)
    dates = [str(bars[i]["date"])[:10] for i in (80, 120, 180, 220, 260, 299)]
    cfg = {"min_score": 0, "scan": {"history_bars": 280}}
    ranged = evaluate_range(bars, dates, code="000001", name="测试", config=cfg)
    by_date = {str(r.get("signal_date") or r.get("trade_date") or "")[:10]: r for r in ranged}

    legacy: List[Dict[str, Any]] = []
    for d in dates:
        end_i = next(i for i, b in enumerate(bars) if str(b.get("date") or "")[:10] == d)
        row = evaluate_one(
            bars[: end_i + 1], code="000001", name="测试", trade_date=d, config=cfg
        )
        if row:
            legacy.append(row)

    assert len(ranged) == len(legacy)
    for leg in legacy:
        d = str(leg.get("signal_date") or "")[:10]
        assert _row_gold(by_date.get(d)) == _row_gold(leg), f"mismatch on {d}"


def test_evaluate_range_empty_dates_or_bars():
    assert evaluate_range([], ["2025-01-01"]) == []
    assert evaluate_range(_synth_bars(100), []) == []


def test_evaluate_range_skips_missing_dates():
    bars = _synth_bars(120)
    out = evaluate_range(bars, ["2099-01-01", str(bars[100]["date"])[:10]], code="1")
    assert all(str(r.get("signal_date"))[:10] != "2099-01-01" for r in out)


def test_hits_for_stock_dates_range_matches_legacy_filter(monkeypatch):
    bars = _synth_bars(280)
    dates = [str(bars[i]["date"])[:10] for i in (100, 150, 200, 250)]
    cfg = {"min_score": 0}

    monkeypatch.setenv("CSB_EVAL_RANGE", "0")
    legacy = _hits_for_stock_dates("000001", "测试", bars, dates, cfg, require_entry=True)

    monkeypatch.setenv("CSB_EVAL_RANGE", "1")
    modern = _hits_for_stock_dates("000001", "测试", bars, dates, cfg, require_entry=True)

    assert [_row_gold(r) for r in modern] == [_row_gold(r) for r in legacy]
