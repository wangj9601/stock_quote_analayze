"""板内短线领涨为主、流通市值门槛/弱加权的龙头/中军分类。"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

ROLE_LEADER = "leader"
ROLE_MID = "mid"
ROLE_LABELS = {ROLE_LEADER: "龙头", ROLE_MID: "中军"}

# 综合分权重（偏短线）
W_CHG = 0.70
W_AMT = 0.20
W_MV = 0.10

# 龙头门槛
LEADER_MV_PCTILE_MIN = 40.0
LEADER_CHG_PCTILE_MIN = 80.0
LEADER_SCORE_GAP = 5.0
LEADER_MAX = 2

# 中军门槛
MID_MV_PCTILE_MIN = 50.0
MID_MV_PCTILE_MAX = 95.0
MID_CHG_PCTILE_MIN = 60.0
MID_MAX = 5


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _percentile_ranks(values: Sequence[Optional[float]]) -> List[Optional[float]]:
    """返回与 values 等长的百分位（0–100）；并列取平均秩。None 保持 None。"""
    indexed = [(i, _safe_float(v)) for i, v in enumerate(values)]
    valid = [(i, v) for i, v in indexed if v is not None]
    out: List[Optional[float]] = [None] * len(values)
    n = len(valid)
    if n == 0:
        return out
    if n == 1:
        out[valid[0][0]] = 100.0
        return out
    valid.sort(key=lambda x: x[1])
    i = 0
    while i < n:
        j = i
        while j + 1 < n and valid[j + 1][1] == valid[i][1]:
            j += 1
        avg_rank = (i + j) / 2.0  # 0-based
        pct = 100.0 * avg_rank / (n - 1)
        for k in range(i, j + 1):
            out[valid[k][0]] = pct
        i = j + 1
    return out


def classify_board_roles(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    为板内成分股标注龙头/中军。

    输入行建议字段：code, name, change_percent, amount, circulating_market_value
    （current_price 可选，原样保留）。原地写入角色字段并返回同一列表。
    """
    if not rows:
        return rows

    for r in rows:
        r["board_role"] = None
        r["board_role_label"] = None
        r["board_role_score"] = None
        r["role_reason"] = None
        r["chg_pctile"] = None
        r["amt_pctile"] = None
        r["mv_pctile"] = None

    chg_vals = [_safe_float(r.get("change_percent")) for r in rows]
    amt_vals = [_safe_float(r.get("amount")) for r in rows]
    mv_vals = [_safe_float(r.get("circulating_market_value")) for r in rows]

    chg_pctiles = _percentile_ranks(chg_vals)
    amt_pctiles = _percentile_ranks(amt_vals)
    mv_pctiles = _percentile_ranks(mv_vals)

    scored: List[Dict[str, Any]] = []
    for i, r in enumerate(rows):
        chg = chg_vals[i]
        mv = mv_vals[i]
        if chg is None or mv is None or mv <= 0:
            continue
        chg_p = chg_pctiles[i] if chg_pctiles[i] is not None else 0.0
        amt_p = amt_pctiles[i] if amt_pctiles[i] is not None else 0.0
        mv_p = mv_pctiles[i] if mv_pctiles[i] is not None else 0.0
        score = W_CHG * chg_p + W_AMT * amt_p + W_MV * mv_p
        r["chg_pctile"] = round(chg_p, 2)
        r["amt_pctile"] = round(amt_p, 2)
        r["mv_pctile"] = round(mv_p, 2)
        r["board_role_score"] = round(score, 2)
        scored.append(r)

    n = len(scored)
    if n == 0:
        return rows

    # 涨幅排名（1=最高）
    by_chg = sorted(
        scored,
        key=lambda x: (_safe_float(x.get("change_percent")) or -1e18),
        reverse=True,
    )
    top_k = max(3, int(math.ceil(n * 0.1)))
    top_chg_codes = {str(x.get("code")) for x in by_chg[:top_k]}

    def _leader_ok(r: Dict[str, Any]) -> bool:
        mv_p = float(r.get("mv_pctile") or 0)
        chg_p = float(r.get("chg_pctile") or 0)
        if mv_p < LEADER_MV_PCTILE_MIN:
            return False
        if chg_p >= LEADER_CHG_PCTILE_MIN:
            return True
        return str(r.get("code")) in top_chg_codes

    candidates = [r for r in scored if _leader_ok(r)]
    candidates.sort(key=lambda x: float(x.get("board_role_score") or 0), reverse=True)

    leaders: List[Dict[str, Any]] = []
    if candidates:
        leaders.append(candidates[0])
        if (
            len(candidates) > 1
            and len(leaders) < LEADER_MAX
            and float(candidates[0].get("board_role_score") or 0)
            - float(candidates[1].get("board_role_score") or 0)
            <= LEADER_SCORE_GAP
            and _leader_ok(candidates[1])
        ):
            leaders.append(candidates[1])

    leader_codes = {str(x.get("code")) for x in leaders}
    for r in leaders:
        r["board_role"] = ROLE_LEADER
        r["board_role_label"] = ROLE_LABELS[ROLE_LEADER]
        r["role_reason"] = (
            f"短线领涨为主：涨幅分位{r.get('chg_pctile')}，"
            f"市值分位{r.get('mv_pctile')}，综合分{r.get('board_role_score')}"
        )

    mid_cap = MID_MAX
    if n < 15:
        mid_cap = max(1, int(round(MID_MAX * n / 15.0)))

    mid_cands = [
        r
        for r in scored
        if str(r.get("code")) not in leader_codes
        and MID_MV_PCTILE_MIN <= float(r.get("mv_pctile") or 0) <= MID_MV_PCTILE_MAX
        and float(r.get("chg_pctile") or 0) >= MID_CHG_PCTILE_MIN
    ]
    mid_cands.sort(key=lambda x: float(x.get("board_role_score") or 0), reverse=True)
    for r in mid_cands[:mid_cap]:
        r["board_role"] = ROLE_MID
        r["board_role_label"] = ROLE_LABELS[ROLE_MID]
        r["role_reason"] = (
            f"中军跟涨：涨幅分位{r.get('chg_pctile')}，"
            f"市值分位{r.get('mv_pctile')}，综合分{r.get('board_role_score')}"
        )

    return rows


def role_tag_from_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """转为选股 role_tags 单项。"""
    role = row.get("board_role")
    if role not in (ROLE_LEADER, ROLE_MID):
        return None
    return {
        "id": "board_leader" if role == ROLE_LEADER else "board_mid",
        "label": ROLE_LABELS[role],
        "level": "info",
        "reason": row.get("role_reason") or "",
    }


def board_change_percent_est(rows: Sequence[Dict[str, Any]]) -> Optional[float]:
    """成分涨幅中位数作为板强度估计。"""
    vals = [_safe_float(r.get("change_percent")) for r in rows]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    vals.sort()
    m = len(vals)
    if m % 2 == 1:
        return round(vals[m // 2], 4)
    return round((vals[m // 2 - 1] + vals[m // 2]) / 2.0, 4)
