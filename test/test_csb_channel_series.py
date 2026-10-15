# -*- coding: utf-8 -*-
"""CSB 通道序列辅助：与按前缀 compute_channel_state 金标一致。"""

from __future__ import annotations

from typing import Any, Dict, List

from backend_core.strategies.csb.channel import (
    build_channel_series,
    channel_state_at,
    compute_channel_state,
)


def _synth_bars(n: int = 320, start: float = 10.0) -> List[Dict[str, Any]]:
    bars: List[Dict[str, Any]] = []
    px = start
    for i in range(n):
        # 温和波动，便于出现粘合
        px = max(1.0, px * (1.0 + ((i % 7) - 3) * 0.0015))
        o = px * 0.999
        h = px * 1.008
        l = px * 0.992
        c = px
        bars.append(
            {
                "date": f"2024-{(i // 28) % 12 + 1:02d}-{(i % 28) + 1:02d}",
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": 1_000_000 + (i % 50) * 10_000,
                "turnover_rate": 1.2 + (i % 10) * 0.05,
            }
        )
    return bars


def _key_fields(ch: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ok": ch.get("ok"),
        "reason": ch.get("reason"),
        "lower": ch.get("lower"),
        "upper": ch.get("upper"),
        "squeeze_pct": ch.get("squeeze_pct"),
        "squeeze_days": ch.get("squeeze_days"),
        "squeeze_ok": ch.get("squeeze_ok"),
        "ma5": ch.get("ma5"),
        "ma10": ch.get("ma10"),
        "ma20": ch.get("ma20"),
        "ma60": ch.get("ma60"),
        "ma250": ch.get("ma250"),
        "hh20": ch.get("hh20"),
        "close": ch.get("close"),
    }


def test_channel_state_at_matches_compute_channel_state_on_prefixes():
    bars = _synth_bars(320)
    cfg = {"channel": {"ma_squeeze_pct": 0.04, "squeeze_days": 15}}
    series = build_channel_series(bars, cfg)
    for i in (59, 60, 120, 200, 250, 319):
        got = _key_fields(channel_state_at(series, i, cfg))
        exp = _key_fields(compute_channel_state(bars[: i + 1], cfg))
        assert got == exp, f"mismatch at i={i}: got={got} exp={exp}"


def test_channel_state_at_insufficient_bars():
    bars = _synth_bars(40)
    cfg = {"channel": {}}
    series = build_channel_series(bars, cfg)
    got = channel_state_at(series, 39, cfg)
    assert got.get("ok") is False
    assert got.get("reason") == "insufficient_bars"
