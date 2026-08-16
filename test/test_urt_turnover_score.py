# -*- coding: utf-8 -*-
"""URT 换手甜区：相对中位加减分 + 绝对熔断（含 50% → −8）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend_core.strategies.urt.config import URTConfigManager  # noqa: E402
from backend_core.strategies.urt.scoring import (  # noqa: E402
    compute_score_breakdown,
    compute_turnover_score_part,
    resolve_turnover_flags,
)
from backend_core.strategies.urt.risk_tags import build_turnover_risk_tags  # noqa: E402


def _cfg(**overrides):
    cfg = URTConfigManager().get_default_config()
    cfg.update(overrides)
    return cfg


def test_resolve_turnover_flags_legacy_and_decouple():
    assert resolve_turnover_flags({"use_turnover": True}) == {
        "hard_filter": True,
        "score_enabled": True,
    }
    assert resolve_turnover_flags({"use_turnover": False}) == {
        "hard_filter": False,
        "score_enabled": False,
    }
    # 显式细项覆盖总开关
    flags = resolve_turnover_flags(
        {
            "use_turnover": False,
            "turnover_hard_filter": True,
            "turnover_score_enabled": False,
        }
    )
    assert flags["hard_filter"] is True
    assert flags["score_enabled"] is False


def test_turnover_relative_sweet_full_score():
    cfg = _cfg()
    # med=4, t=6 → r=1.5 落在 1~2 满分
    part = compute_turnover_score_part(6.0, 4.0, cfg)
    assert part["mode"] == "relative"
    assert abs(part["relative"] - 1.5) < 1e-6
    assert part["score"] == 8.0
    assert part["abs_penalty"] is False


def test_turnover_relative_penalty_high_multiple():
    cfg = _cfg()
    # med=3, t=18 → r=6 ≥ penalty_full 5 → score_min
    part = compute_turnover_score_part(18.0, 3.0, cfg)
    assert part["mode"] == "relative"
    assert part["score"] == -8.0


def test_turnover_abs_50_percent_full_penalty():
    """创力集团类：日换手 50% → 绝对满额减分 −8。"""
    cfg = _cfg()
    part = compute_turnover_score_part(50.0, 5.0, cfg)
    assert part["score"] == -8.0
    assert part["abs_penalty"] is True
    assert part["reason"] == "abs_penalty_full"
    tags = build_turnover_risk_tags(
        {"turnover_rate": 50.0, "turnover_median_n": 5.0},
        cfg,
        turnover_part=part,
    )
    assert any(t.get("id") == "turnover_extreme" for t in tags)
    assert tags[0]["level"] == "danger"


def test_turnover_abs_penalty_overrides_relative_bonus():
    """相对倍数仍在甜区，但绝对 ≥25% → 强制不高于绝对负分插值。"""
    cfg = _cfg()
    # med=20, t=30 → r=1.5 本应满分，但绝对熔断
    part = compute_turnover_score_part(30.0, 20.0, cfg)
    assert part["abs_penalty"] is True
    assert part["score"] < 0
    assert part["score"] > -8.0  # 25~40 插值，30 约中间偏负


def test_turnover_absolute_fallback_when_no_median():
    cfg = _cfg()
    part = compute_turnover_score_part(5.0, None, cfg)
    assert part["mode"] == "absolute_fallback"
    assert part["score"] == 8.0  # 3~7 甜区
    part_hi = compute_turnover_score_part(50.0, None, cfg)
    assert part_hi["score"] == -8.0


def test_turnover_score_disabled():
    cfg = _cfg(turnover_score_enabled=False, use_turnover=True)
    part = compute_turnover_score_part(50.0, 5.0, cfg)
    assert part["enabled"] is False
    assert part["score"] == 0.0


def test_score_breakdown_volume_max_31_and_turnover_part():
    cfg = _cfg(use_yang_medium=False, require_ma_bull=False)
    ind = {
        "above_ma20": True,
        "yang_count_4": 3,
        "yang_count_5": 4,
        "volume_multiple": 5.0,
        "ma_bull_ok": False,
        "ma_bear_ok": False,
        "turnover_rate": 50.0,
        "turnover_median_n": 4.0,
        "yang_medium_detail": [],
    }
    total, detail = compute_score_breakdown(ind, cfg)
    assert detail["parts"]["volume"]["max"] == 31
    assert detail["parts"]["turnover"]["score"] == -8.0
    assert 0 <= total <= 100
