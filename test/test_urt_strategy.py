# -*- coding: utf-8 -*-
"""URT 上升趋势策略单元测试（不连库）。"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
for p in (str(project_root), str(project_root / "backend_api"), str(project_root / "backend_core")):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend_core.strategies.urt.indicators import (  # noqa: E402
    build_indicators,
    hard_filter_pass,
    yang_count,
    avg_volume_prev,
)
from backend_core.strategies.urt.scoring import compute_score  # noqa: E402
from backend_core.strategies.urt.signal_detector import (  # noqa: E402
    evaluate_buy_signal,
    evaluate_exit_rules,
)
from backend_core.strategies.urt.config import URTConfigManager  # noqa: E402


def _bars(n=30, *, yang_pattern=None, vol_spike=True, above_ma=True):
    """构造 DESC K 线：index0 最新。"""
    bars = []
    base = 10.0
    for i in range(n):
        # i=0 最新
        day_idx_from_old = n - 1 - i
        close = base + day_idx_from_old * 0.1
        if above_ma:
            close = base + 5 + (n - i) * 0.05
        open_ = close - 0.2
        if yang_pattern is not None and i < len(yang_pattern):
            if yang_pattern[i]:
                open_ = close - 0.3
            else:
                open_ = close + 0.3
        vol = 1000.0
        if vol_spike and i == 0:
            vol = 3000.0
        elif i > 0:
            vol = 1000.0
        bars.append(
            {
                "date": f"2026-07-{30 - i:02d}" if 30 - i >= 1 else f"2026-06-{30 - (i - 29):02d}",
                "open": open_,
                "close": close,
                "volume": vol,
                "turnover_rate": 3.0,
            }
        )
    return bars


def test_yang_count():
    opens = [10, 10, 10, 11, 11]
    closes = [11, 11, 9, 12, 10]  # Y Y N Y N
    assert yang_count(opens, closes, 4) == 3
    assert yang_count(opens, closes, 5) == 3


def test_avg_volume_prev():
    vols = [3000.0] + [1000.0] * 20
    assert avg_volume_prev(vols, 20) == 1000.0


def test_hard_filter_and_score_pass():
    cfg = URTConfigManager().get_default_config()
    # 最新 4 根：阳阳阳阴 → 3/4；量 3x
    yang = [True, True, True, False, True]
    bars = _bars(40, yang_pattern=yang, vol_spike=True, above_ma=True)
    # 确保量能：prev 20 = 1000, today 3000 → 3.0 >= 2.5
    ind = build_indicators(bars, cfg)
    assert ind is not None
    assert ind["above_ma20"] is True
    ok, _ = hard_filter_pass(ind, cfg)
    assert ok
    score = compute_score(ind, cfg)
    assert score >= 70
    sig = evaluate_buy_signal(bars, cfg)
    assert sig is not None
    assert sig["buy_signal"] is True


def test_reject_when_below_ma():
    cfg = URTConfigManager().get_default_config()
    bars = _bars(40, yang_pattern=[True] * 5, vol_spike=True, above_ma=True)
    # 最新收盘压到明显低于近 20 日均价
    for i, b in enumerate(bars):
        b["close"] = 20.0 - i * 0.01  # 近端高、远端略低 → 最新远高于均线
        b["open"] = b["close"] - 0.1
    bars[0]["close"] = 1.0
    bars[0]["open"] = 0.9
    bars[0]["volume"] = 5000
    for i in range(1, 21):
        bars[i]["volume"] = 1000
        bars[i]["close"] = 20.0
        bars[i]["open"] = 19.8
    ind = build_indicators(bars, cfg)
    assert ind is not None
    assert ind["above_ma20"] is False
    ok, reason = hard_filter_pass(ind, cfg)
    assert ok is False
    assert "MA20" in reason


def test_reject_low_volume_multiple():
    cfg = URTConfigManager().get_default_config()
    yang = [True, True, True, True, True]
    bars = _bars(40, yang_pattern=yang, vol_spike=False, above_ma=True)
    for b in bars:
        b["volume"] = 1000.0
    ind = build_indicators(bars, cfg)
    assert ind is not None
    ok, reason = hard_filter_pass(ind, cfg)
    assert ok is False
    assert "量能" in reason


def test_exit_price_stop():
    cfg = URTConfigManager().get_default_config()
    r = evaluate_exit_rules(entry_price=10.0, closes=[10, 9.5, 8.5], peak_price=10.0, cfg=cfg)
    assert r is not None
    assert r["exit_reason"] == "price_stop"


def test_exit_time_stop():
    cfg = URTConfigManager().get_default_config()
    # 连跌 3 日但跌幅未达 10%
    closes = [10.0, 9.9, 9.8, 9.7]
    r = evaluate_exit_rules(entry_price=10.0, closes=closes, peak_price=10.0, cfg=cfg)
    assert r is not None
    assert r["exit_reason"] == "time_stop"


def test_exit_trailing_take_profit():
    cfg = URTConfigManager().get_default_config()
    # 涨到 13(+30%) 后回撤到 12.2 (~6% from peak)
    closes = [10.0, 11.0, 12.0, 13.0, 12.2]
    r = evaluate_exit_rules(entry_price=10.0, closes=closes, peak_price=13.0, cfg=cfg)
    assert r is not None
    assert r["exit_reason"] == "trailing_take_profit"
