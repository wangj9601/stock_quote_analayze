# -*- coding: utf-8 -*-
"""URT 打分：连阳强度 + 量能超额 + 可选换手/量比。"""

from __future__ import annotations

from typing import Any, Dict


def compute_score(ind: Dict[str, Any], cfg: Dict[str, Any]) -> float:
    """
    百分制：
    - 连阳：最高 40（5/5 或 4/4 满分）
    - 量能倍数：2.5x→30，最高 40（约 5x）
    - 站上 MA20：固定 10
    - 换手/量比：各最高 5（仅当启用时计入，否则把权重并入量能）
    """
    score = 0.0

    # 站上 MA
    if ind.get("above_ma20"):
        score += 10.0

    # 连阳强度
    ya = int(ind.get("yang_count_4") or 0)
    yb = int(ind.get("yang_count_5") or 0)
    yang_score = 0.0
    if yb >= 5:
        yang_score = 40.0
    elif yb >= 4:
        yang_score = 36.0
    elif ya >= 4:
        yang_score = 34.0
    elif ya >= 3:
        yang_score = 30.0
    else:
        yang_score = max(0.0, ya * 8.0)
    score += yang_score

    # 量能
    vm = float(ind.get("volume_multiple") or 0)
    need = float(cfg.get("volume_multiple") or 2.5)
    if vm >= need:
        # 2.5 → 30, 5.0 → 40
        vol_score = 30.0 + min(10.0, (vm - need) / max(need, 0.1) * 10.0)
    else:
        vol_score = max(0.0, vm / max(need, 0.1) * 30.0)
    score += vol_score

    use_to = bool(cfg.get("use_turnover"))
    use_vr = bool(cfg.get("use_volume_ratio"))
    if use_to:
        to = ind.get("turnover_rate")
        if to is not None:
            # 换手 1%~8% 线性给到 5 分
            score += min(5.0, max(0.0, float(to) / 8.0 * 5.0))
    if use_vr:
        vr = ind.get("volume_ratio")
        if vr is not None:
            score += min(5.0, max(0.0, float(vr) / 3.0 * 5.0))
    if not use_to and not use_vr:
        # 未启用精细参数时，量能超额再给一点空间（已在 vol_score 含）
        pass

    return round(min(100.0, score), 2)
