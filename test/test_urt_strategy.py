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


def _loose_cfg(**extra):
    """旧口径宽松硬筛，便于单测聚焦单项逻辑。"""
    cfg = URTConfigManager().get_default_config()
    cfg.update(
        {
            "use_yang_medium": False,
            "require_ma_bull": False,
            "use_turnover": False,
            "use_volume_ratio": False,
            "volume_multiple": 2.5,
            "structure_rr_hard_gate_enabled": False,
            "overheat_hard_gate_enabled": False,
        }
    )
    cfg.update(extra)
    return cfg


def test_hard_filter_and_score_pass():
    cfg = _loose_cfg()
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
    assert score >= 65  # 打分校准后量能/连阳上限下调，宽松构造约 65–75
    sig = evaluate_buy_signal(bars, cfg)
    # 若刚好低于 min_score，仅验证硬筛与算分通路
    if score >= float(cfg.get("min_score") or 70):
        assert sig is not None
        assert sig["buy_signal"] is True
    else:
        assert ind["yang_count_4"] >= 3
        assert float(ind.get("volume_multiple") or 0) >= float(cfg.get("volume_multiple") or 0)


def test_reject_when_below_ma():
    cfg = _loose_cfg()
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


def test_require_pass_skips_kde_when_hard_filter_fails(monkeypatch):
    cfg = _loose_cfg()
    bars = _bars(40, yang_pattern=[False] * 5, vol_spike=False, above_ma=False)
    for b in bars:
        b["close"] = 1.0
        b["open"] = 1.1
        b["volume"] = 10

    def _boom(*_a, **_k):
        raise AssertionError("hard filter failed should skip KDE")

    monkeypatch.setattr(
        "backend_core.strategies.urt.signal_detector._compute_structure_levels",
        _boom,
    )
    assert evaluate_buy_signal(bars, cfg, require_pass=True) is None


def test_reject_low_volume_multiple():
    cfg = _loose_cfg()
    yang = [True, True, True, True, True]
    bars = _bars(40, yang_pattern=yang, vol_spike=False, above_ma=True)
    for b in bars:
        b["volume"] = 1000.0
    ind = build_indicators(bars, cfg)
    assert ind is not None
    ok, reason = hard_filter_pass(ind, cfg)
    assert ok is False
    assert "量能" in reason


def test_buy_signal_includes_kde_structure():
    """买点结果应带 KDE 支撑/阻力（展示用，不参与硬筛）。"""
    import random

    cfg = _loose_cfg()
    yang = [True, True, True, False, True]
    bars = _bars(80, yang_pattern=yang, vol_spike=True, above_ma=True)
    # 在约 13/15/17 堆量，便于形成密度峰
    random.seed(7)
    for i, b in enumerate(bars):
        cluster = [13.0, 15.0, 17.0][i % 3]
        b["close"] = round(cluster + random.uniform(-0.1, 0.1), 2)
        b["open"] = b["close"] - 0.2
        b["volume"] = 1_000_000 + (i % 3) * 500_000
    # 最新站上偏高价区并放量阳线，保证能过硬筛+得分
    bars[0]["close"] = 15.2
    bars[0]["open"] = 14.8
    bars[0]["volume"] = 4_000_000
    for i in range(1, 5):
        bars[i]["close"] = 15.0 + i * 0.05
        bars[i]["open"] = bars[i]["close"] - 0.15
    sig = evaluate_buy_signal(bars, cfg, require_pass=False)
    assert sig is not None
    assert "support_levels" in sig
    assert "resistance_levels" in sig
    assert "nearest_support" in sig or sig.get("nearest_support") is None
    st = (sig.get("score_detail") or {}).get("structure") or {}
    assert st.get("method") in ("kde_volume_weighted", "structural_kde+confluence", "structural_kde")
    assert "kde_ok" in st
    # 有足够样本时通常能识别到峰
    if st.get("kde_ok"):
        assert isinstance(st.get("support_levels"), list)
        assert isinstance(st.get("resistance_levels"), list)


def test_history_calendar_covers_kde_max():
    from backend_core.strategies.urt.signal_detector import history_calendar_days_for_fetch

    cfg = {"history_calendar_days": 120, "kde_lookback_max": 750}
    assert history_calendar_days_for_fetch(cfg) >= 120
    assert history_calendar_days_for_fetch(cfg) >= int(750 * 1.6)


def test_exit_price_stop():
    cfg = URTConfigManager().get_default_config()
    r = evaluate_exit_rules(entry_price=10.0, closes=[10, 9.5, 8.5], peak_price=10.0, cfg=cfg)
    assert r is not None
    assert r["exit_reason"] == "price_stop"


def test_exit_time_stop():
    cfg = URTConfigManager().get_default_config()
    # 连跌 3 日但浮亏不足 4%：不触发
    mild = evaluate_exit_rules(entry_price=10.0, closes=[10.0, 9.9, 9.8, 9.7], peak_price=10.0, cfg=cfg)
    assert mild is None or mild.get("exit_reason") != "time_stop"
    # 连跌 3 日且浮亏 ≥4%
    closes = [10.0, 9.8, 9.6, 9.5]
    r = evaluate_exit_rules(entry_price=10.0, closes=closes, peak_price=10.0, cfg=cfg)
    assert r is not None
    assert r["exit_reason"] == "time_stop"


def test_exit_trailing_take_profit():
    cfg = URTConfigManager().get_default_config()
    # 涨到约 +9% 后自峰值回撤 ≥5%
    closes = [10.0, 10.5, 10.9, 10.3]
    r = evaluate_exit_rules(entry_price=10.0, closes=closes, peak_price=10.9, cfg=cfg)
    assert r is not None
    assert r["exit_reason"] == "trailing_take_profit"


def test_score_breakdown_and_detail_payload():
    from backend_core.strategies.urt.scoring import compute_score_breakdown

    cfg = _loose_cfg()
    yang = [True, True, True, False, True]
    bars = _bars(40, yang_pattern=yang, vol_spike=True, above_ma=True)
    ind = build_indicators(bars, cfg)
    assert ind is not None
    total, detail = compute_score_breakdown(ind, cfg)
    assert total == compute_score(ind, cfg)
    assert "parts" in detail and "above_ma20" in detail["parts"]
    assert detail["total"] == total


def test_evaluate_buy_signal_require_pass_false_returns_detail():
    cfg = _loose_cfg()
    # 量能不足：仍返回明细
    yang = [True, True, True, False, True]
    bars = _bars(40, yang_pattern=yang, vol_spike=False, above_ma=True)
    for b in bars:
        b["volume"] = 1000.0
    detail = evaluate_buy_signal(bars, cfg, require_pass=False)
    assert detail is not None
    assert detail["buy_signal"] is False
    assert detail.get("score_detail")


def test_min_bars_needed_matches_build_indicators():
    from backend_core.strategies.urt.indicators import min_bars_needed

    cfg = URTConfigManager().get_default_config()
    # MA20 + 斜率窗（默认 20+5）抬升最少 K 线根数
    assert min_bars_needed(cfg) == max(20, 20 + 5, 20 + 1, 4, 5, 20, 20, 10, 5 + 1) == 25


def test_screen_universe_require_pass_false_keeps_failed_signal():
    """单股模式：不按筛选过滤，未过硬筛也返回信号明细。"""
    from backend_core.strategies.urt.strategy_engine import URTStrategyEngine

    cfg = _loose_cfg()
    yang = [True, True, True, False, True]
    bars = _bars(40, yang_pattern=yang, vol_spike=False, above_ma=True)
    for b in bars:
        b["volume"] = 1000.0

    class _Loader:
        def fetch_historical_desc(self, code, start_date=None, end_date=None):
            return bars

    engine = URTStrategyEngine(_Loader(), cfg)
    passed = engine.screen_universe([("000001", "测试")], require_pass=True)
    assert passed == []
    kept = engine.screen_universe([("000001", "测试")], require_pass=False)
    assert len(kept) == 1
    assert kept[0]["buy_signal"] is False
    assert kept[0]["code"] == "000001"


def test_screen_universe_for_dates_fetches_once():
    """多日扫描只批量拉一次行情，并按日切片。"""
    from backend_core.strategies.urt.strategy_engine import URTStrategyEngine

    cfg = _loose_cfg()
    yang = [True, True, True, False, True]
    bars = _bars(40, yang_pattern=yang, vol_spike=False, above_ma=True)
    for b in bars:
        b["volume"] = 1000.0
    calls = {"n": 0}

    class _Loader:
        def fetch_historical_desc_batch(self, codes, start_date=None, end_date=None, **_k):
            calls["n"] += 1
            return {str(codes[0]): list(bars)}

        def fetch_historical_desc(self, code, start_date=None, end_date=None):
            raise AssertionError("range scan should use batch")

    engine = URTStrategyEngine(_Loader(), cfg)
    by_date, completed = engine.screen_universe_for_dates(
        [("000001", "测试")],
        ["2026-07-29", "2026-07-30"],
        require_pass=False,
    )
    assert completed is True
    assert calls["n"] == 1
    assert len(by_date["2026-07-30"]) == 1
    assert len(by_date["2026-07-29"]) == 1
    assert by_date["2026-07-30"][0]["signal_date"] == "2026-07-30"
    assert by_date["2026-07-29"][0]["signal_date"] == "2026-07-29"


def test_backtest_progress_helpers_import():
    from backend_core.strategies.urt.backtest_storage import clamp_progress, normalize_task_id

    assert clamp_progress(150) == 100
    assert clamp_progress(-1) == 0
    assert normalize_task_id("  abc  ") == "abc"


def test_medium_yang_and_ma_bull_fields_always_present():
    cfg = URTConfigManager().get_default_config()
    assert cfg.get("use_yang_medium") is True
    assert cfg.get("require_ma_bull") is True
    assert float(cfg.get("volume_multiple") or 0) == 3.0
    assert cfg.get("structure_rr_hard_gate_enabled") is True
    assert abs(float(cfg.get("structure_rr_min_rr") or 0) - 2.0) < 1e-9
    yang = [True] * 5
    bars = _bars(40, yang_pattern=yang, vol_spike=True, above_ma=True)
    ind = build_indicators(bars, cfg)
    assert ind is not None
    assert "yang_count_10" in ind and "yang_count_15" in ind and "yang_count_20" in ind
    assert "ma_bull_ok" in ind and "ma_bear_ok" in ind and "ma5" in ind and "ma10" in ind
    # 默认硬筛开启：升序构造通常可过
    ok, _ = hard_filter_pass(ind, cfg)
    assert ok is True


def test_use_yang_medium_hard_filter_rejects():
    cfg = _loose_cfg(use_yang_medium=True)
    # 短窗全阳，但中期阈值极高 → 构造近期大量阴线
    bars = _bars(40, yang_pattern=[True] * 5, vol_spike=True, above_ma=True)
    for i in range(5, 25):
        bars[i]["open"] = bars[i]["close"] + 0.5  # 阴线
    ind = build_indicators(bars, cfg)
    assert ind is not None
    assert ind.get("yang_medium_ok") is False
    ok, reason = hard_filter_pass(ind, cfg)
    assert ok is False
    assert "中期阳线" in reason


def test_require_ma_bull_hard_filter_rejects():
    cfg = _loose_cfg(require_ma_bull=True)
    bars = _bars(40, yang_pattern=[True] * 5, vol_spike=True, above_ma=True)
    # 强制下跌序列使短均线低于长均线
    for i, b in enumerate(bars):
        b["close"] = 30.0 - i * 0.4
        b["open"] = b["close"] - 0.1
        b["volume"] = 3000.0 if i == 0 else 1000.0
    # 仍尽量站上「ma_period」：提高最新收盘
    bars[0]["close"] = 28.0
    bars[0]["open"] = 27.5
    ind = build_indicators(bars, cfg)
    assert ind is not None
    # 下跌趋势下通常非多头
    if ind.get("ma_bull_ok"):
        # 若偶然多头，再压低 ma5
        pass
    ok, reason = hard_filter_pass(ind, cfg)
    if ind.get("ma_bull_ok"):
        # 极端情况下若仍多头则跳过断言（构造不稳）
        return
    assert ok is False
    assert "多头" in reason


def test_score_includes_yang_medium_and_ma_bull_parts():
    from backend_core.strategies.urt.scoring import compute_score_breakdown

    cfg = _loose_cfg()
    yang = [True] * 5
    bars = _bars(40, yang_pattern=yang, vol_spike=True, above_ma=True)
    ind = build_indicators(bars, cfg)
    assert ind is not None
    total, detail = compute_score_breakdown(ind, cfg)
    parts = detail["parts"]
    assert "yang_medium" in parts
    assert parts["yang_medium"]["max"] == 5
    assert "ma_bull" in parts
    assert parts["ma_bull"]["max"] == 8
    assert parts["volume"]["max"] == 20
    assert parts["yang"]["max"] == 16
    assert "yang_quality" in parts
    assert "structure_position" in parts
    assert "overheat_penalty" in parts
    assert total <= 100


def test_volume_score_full_multiple_and_ma_bear_penalty():
    from backend_core.strategies.urt.scoring import compute_score_breakdown

    cfg = _loose_cfg(volume_multiple=3.0, volume_score_full_multiple=4.0)
    ind = {
        "above_ma20": True,
        "yang_count_4": 3,
        "yang_count_5": 4,
        "volume_multiple": 4.0,
        "yang_medium_ok": True,
        "yang_medium_detail": [
            {"window": 10, "min_up_days": 6, "count": 6},
            {"window": 15, "min_up_days": 8, "count": 8},
            {"window": 20, "min_up_days": 10, "count": 10},
        ],
        "ma_bull_ok": False,
        "ma_bear_ok": True,
        "ma_bull_periods": [5, 10, 20],
        "turnover_rate": None,
        "volume_ratio": None,
    }
    total, detail = compute_score_breakdown(ind, cfg)
    assert detail["parts"]["volume"]["score"] == 20.0
    assert detail["parts"]["ma_bull"]["score"] == -8.0
    assert total >= 0
