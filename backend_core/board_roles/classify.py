"""板内短线领涨为主、流通市值门槛/弱加权的龙头/中军分类。

本轮规则要点（详见 docs/features/板块龙头中军业务规则.md）：
- 涨停代理加分（无首封时间，二期再接）
- 绝对流通市值 + 相对分位双门槛；涨幅 ≥0
- Top-K 收紧；双龙头 gap 收紧
- 中军取消市值分位上限；ST 剔除；小样本护栏
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROLE_LEADER = "leader"
ROLE_MID = "mid"
ROLE_LABELS = {ROLE_LEADER: "龙头", ROLE_MID: "中军"}

# 综合分权重（偏短线）
W_CHG = 0.70
W_AMT = 0.20
W_MV = 0.10

# 涨停代理加分（百分制封顶 100）；首封时间二期
LIMIT_UP_BONUS = 12.0
LIMIT_UP_MAIN_MIN = 9.8  # 主板/北交所等
LIMIT_UP_GEM_STAR_MIN = 19.8  # 创业板/科创板

# 龙头门槛
LEADER_MV_PCTILE_MIN = 40.0
LEADER_CHG_PCTILE_MIN = 80.0
LEADER_SCORE_GAP = 2.5
LEADER_MAX = 2
LEADER_ABS_MV_MIN = 3e9  # 30 亿（元）
LEADER_DUAL_CHG_DIFF_MAX = 1.0  # 双龙头：涨幅差 < 1 个百分点

# 中军门槛（取消 mv 分位上限）
MID_MV_PCTILE_MIN = 50.0
MID_CHG_PCTILE_MIN = 60.0
MID_MAX = 5
MID_ABS_MV_MIN = 8e9  # 80 亿（元）

# 涨幅地板与小样本
MIN_CHANGE_PERCENT = 0.0
SAMPLE_NO_ROLE_MAX = 2  # N < 3 不标注
SAMPLE_SMALL_MAX = 7  # N < 8：最多 1 龙头、中军至多 1

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


def is_st_name(name: Any) -> bool:
    """名称以 ST / *ST / S*ST / SST 开头则视为 ST 股。"""
    s = str(name or "").strip().upper().replace(" ", "")
    if not s:
        return False
    return (
        s.startswith("ST")
        or s.startswith("*ST")
        or s.startswith("S*ST")
        or s.startswith("SST")
    )


def limit_up_threshold_for_code(code: Any) -> float:
    """按代码前缀返回涨停幅度阈值（百分比）。"""
    c = str(code or "").strip().zfill(6)
    if c.startswith(("300", "301", "688")):
        return LIMIT_UP_GEM_STAR_MIN
    return LIMIT_UP_MAIN_MIN


def is_limit_up(code: Any, change_percent: Any) -> bool:
    """日终涨幅代理是否涨停（无首封时间）。"""
    chg = _safe_float(change_percent)
    if chg is None:
        return False
    return chg >= limit_up_threshold_for_code(code)


def leader_top_k(n: int) -> int:
    """领涨 Top-K：min(10, max(2, ceil(N×0.05)))."""
    if n <= 0:
        return 0
    return min(10, max(2, int(math.ceil(n * 0.05))))


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


def _chg_sort_key(r: Dict[str, Any]) -> Tuple[float, float, float]:
    """涨幅降序，并列按成交额、流通市值降序。"""
    return (
        _safe_float(r.get("change_percent")) or -1e18,
        _safe_float(r.get("amount")) or -1e18,
        _safe_float(r.get("circulating_market_value")) or -1e18,
    )


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
        r["is_limit_up"] = False

    # ST 不进入有效样本，也不参与分位
    pool = [r for r in rows if not is_st_name(r.get("name"))]
    chg_vals = [_safe_float(r.get("change_percent")) for r in pool]
    amt_vals = [_safe_float(r.get("amount")) for r in pool]
    mv_vals = [_safe_float(r.get("circulating_market_value")) for r in pool]

    chg_pctiles = _percentile_ranks(chg_vals)
    amt_pctiles = _percentile_ranks(amt_vals)
    mv_pctiles = _percentile_ranks(mv_vals)

    scored: List[Dict[str, Any]] = []
    for i, r in enumerate(pool):
        chg = chg_vals[i]
        mv = mv_vals[i]
        if chg is None or mv is None or mv <= 0:
            continue
        chg_p = chg_pctiles[i] if chg_pctiles[i] is not None else 0.0
        amt_p = amt_pctiles[i] if amt_pctiles[i] is not None else 0.0
        mv_p = mv_pctiles[i] if mv_pctiles[i] is not None else 0.0
        base = W_CHG * chg_p + W_AMT * amt_p + W_MV * mv_p
        lim = is_limit_up(r.get("code"), chg)
        r["is_limit_up"] = lim
        score = min(100.0, base + (LIMIT_UP_BONUS if lim else 0.0))
        r["chg_pctile"] = round(chg_p, 2)
        r["amt_pctile"] = round(amt_p, 2)
        r["mv_pctile"] = round(mv_p, 2)
        r["board_role_score"] = round(score, 2)
        scored.append(r)

    n = len(scored)
    if n == 0:
        return rows
    if n <= SAMPLE_NO_ROLE_MAX:
        return rows

    # 涨幅排名（破同分：额 → 市值）
    by_chg = sorted(scored, key=_chg_sort_key, reverse=True)
    top_k = leader_top_k(n)
    top_chg_codes = {str(x.get("code")) for x in by_chg[:top_k]}

    def _leader_ok(r: Dict[str, Any]) -> bool:
        chg = _safe_float(r.get("change_percent"))
        mv = _safe_float(r.get("circulating_market_value"))
        if chg is None or chg < MIN_CHANGE_PERCENT:
            return False
        if mv is None or mv < LEADER_ABS_MV_MIN:
            return False
        mv_p = float(r.get("mv_pctile") or 0)
        chg_p = float(r.get("chg_pctile") or 0)
        if mv_p < LEADER_MV_PCTILE_MIN:
            return False
        if chg_p >= LEADER_CHG_PCTILE_MIN:
            return True
        return str(r.get("code")) in top_chg_codes

    def _second_leader_ok(first: Dict[str, Any], second: Dict[str, Any]) -> bool:
        gap = float(first.get("board_role_score") or 0) - float(
            second.get("board_role_score") or 0
        )
        if gap > LEADER_SCORE_GAP:
            return False
        if not _leader_ok(second):
            return False
        if second.get("is_limit_up"):
            return True
        c1 = _safe_float(first.get("change_percent")) or 0.0
        c2 = _safe_float(second.get("change_percent")) or 0.0
        return abs(c1 - c2) < LEADER_DUAL_CHG_DIFF_MAX

    candidates = [r for r in scored if _leader_ok(r)]
    candidates.sort(key=lambda x: float(x.get("board_role_score") or 0), reverse=True)

    leader_max = 1 if n <= SAMPLE_SMALL_MAX else LEADER_MAX
    leaders: List[Dict[str, Any]] = []
    if candidates:
        leaders.append(candidates[0])
        if (
            leader_max >= 2
            and len(candidates) > 1
            and _second_leader_ok(candidates[0], candidates[1])
        ):
            leaders.append(candidates[1])

    leader_codes = {str(x.get("code")) for x in leaders}
    for r in leaders:
        r["board_role"] = ROLE_LEADER
        r["board_role_label"] = ROLE_LABELS[ROLE_LEADER]
        bonus_note = "，涨停加分" if r.get("is_limit_up") else ""
        r["role_reason"] = (
            f"短线领涨为主：涨幅分位{r.get('chg_pctile')}，"
            f"市值分位{r.get('mv_pctile')}，综合分{r.get('board_role_score')}"
            f"{bonus_note}"
        )

    mid_cap = MID_MAX
    if n < 15:
        mid_cap = max(1, int(round(MID_MAX * n / 15.0)))
    if n <= SAMPLE_SMALL_MAX:
        mid_cap = min(mid_cap, 1)

    mid_cands = []
    for r in scored:
        if str(r.get("code")) in leader_codes:
            continue
        chg = _safe_float(r.get("change_percent"))
        mv = _safe_float(r.get("circulating_market_value"))
        if chg is None or chg < MIN_CHANGE_PERCENT:
            continue
        if mv is None or mv < MID_ABS_MV_MIN:
            continue
        if float(r.get("mv_pctile") or 0) < MID_MV_PCTILE_MIN:
            continue
        if float(r.get("chg_pctile") or 0) < MID_CHG_PCTILE_MIN:
            continue
        mid_cands.append(r)
    mid_cands.sort(key=lambda x: float(x.get("board_role_score") or 0), reverse=True)
    for r in mid_cands[:mid_cap]:
        r["board_role"] = ROLE_MID
        r["board_role_label"] = ROLE_LABELS[ROLE_MID]
        bonus_note = "，涨停加分" if r.get("is_limit_up") else ""
        r["role_reason"] = (
            f"中军跟涨：涨幅分位{r.get('chg_pctile')}，"
            f"市值分位{r.get('mv_pctile')}，综合分{r.get('board_role_score')}"
            f"{bonus_note}"
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
