# -*- coding: utf-8 -*-
"""市场总龙头（涨停池情绪标杆）与资金焦点（净流入第一）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from backend_core.market_review.rules import yuan_to_yi

# 可解释权重（第一版写死，便于单测）
W_HEIGHT = 100.0
W_SEAL_PER_YI = 8.0
SEAL_YI_CAP = 25.0
W_MAINLINE = 45.0
W_PEER_SAME = 12.0  # 同高度每多 1 家（不含自己）
PEER_SAME_CAP = 5
W_PEER_NEAR = 4.0  # 高度差 1 的跟风家数
PEER_NEAR_CAP = 8


def _name_matches_industry(stock_industry: Any, main_name: Any) -> bool:
    a = str(stock_industry or "").strip()
    b = str(main_name or "").strip()
    if len(a) < 2 or len(b) < 2:
        return False
    return a in b or b in a


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _score_row(
    row: Dict[str, Any],
    *,
    main_name: Optional[str],
    same_height_peers: int,
    near_height_peers: int,
) -> tuple[float, List[str]]:
    bc = _safe_int(row.get("board_count"))
    seal_yi = yuan_to_yi(row.get("seal_fund"))
    if seal_yi is None:
        seal_yi = 0.0
    seal_yi = min(float(seal_yi), SEAL_YI_CAP)

    score = bc * W_HEIGHT + seal_yi * W_SEAL_PER_YI
    reasons: List[str] = [f"连板 {bc}"]
    if seal_yi > 0:
        reasons.append(f"封单 {seal_yi:.2f} 亿")

    if main_name and _name_matches_industry(row.get("industry"), main_name):
        score += W_MAINLINE
        reasons.append("主线匹配")

    peer_s = min(max(same_height_peers, 0), PEER_SAME_CAP)
    if peer_s > 0:
        score += peer_s * W_PEER_SAME
        reasons.append(f"同高度跟风 {peer_s} 家")

    peer_n = min(max(near_height_peers, 0), PEER_NEAR_CAP)
    if peer_n > 0:
        score += peer_n * W_PEER_NEAR
        reasons.append(f"邻高度带动 {peer_n} 家")

    return round(score, 2), reasons


def pick_market_leader(
    zt_rows: List[Dict[str, Any]],
    *,
    main_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    从当日涨停池选出市场总龙头。

    zt_rows 项需含: code, name, board_count, seal_fund(元), industry
    """
    if not zt_rows:
        return None

    by_height: Dict[int, int] = {}
    for r in zt_rows:
        bc = _safe_int(r.get("board_count"))
        by_height[bc] = by_height.get(bc, 0) + 1

    scored: List[Dict[str, Any]] = []
    for r in zt_rows:
        bc = _safe_int(r.get("board_count"))
        same = max(by_height.get(bc, 1) - 1, 0)
        near = by_height.get(bc - 1, 0) + by_height.get(bc + 1, 0)
        score, reasons = _score_row(
            r,
            main_name=main_name,
            same_height_peers=same,
            near_height_peers=near,
        )
        seal_yi = yuan_to_yi(r.get("seal_fund"))
        scored.append(
            {
                "code": str(r.get("code") or ""),
                "name": str(r.get("name") or r.get("code") or ""),
                "board_count": bc,
                "seal_yi": None if seal_yi is None else round(float(seal_yi), 2),
                "score": score,
                "reasons": reasons,
                "industry": r.get("industry"),
            }
        )

    scored.sort(
        key=lambda x: (
            -float(x["score"]),
            -int(x["board_count"] or 0),
            -float(x["seal_yi"] or 0),
            str(x["code"]),
        )
    )
    top = scored[0]
    alternates = [
        {
            "code": a["code"],
            "name": a["name"],
            "board_count": a["board_count"],
            "score": a["score"],
        }
        for a in scored[1:3]
    ]
    return {
        "code": top["code"],
        "name": top["name"],
        "board_count": top["board_count"],
        "seal_yi": top["seal_yi"],
        "score": top["score"],
        "reasons": top["reasons"],
        "alternates": alternates,
        "same_as_capital_focus": False,
    }


def build_capital_focus(
    flow_top: List[Dict[str, Any]],
    zt_codes: Set[str],
) -> Optional[Dict[str, Any]]:
    """资金焦点：个股主力净流入第一（可不涨停）。"""
    if not flow_top:
        return None
    top = flow_top[0]
    code = str(top.get("code") or "")
    if not code:
        return None
    return {
        "code": code,
        "name": str(top.get("name") or code),
        "net_inflow_yi": top.get("net_inflow_yi"),
        "source": "flow_top",
        "is_limit_up": code in zt_codes,
    }


def attach_leader_flags(
    market_leader: Optional[Dict[str, Any]],
    capital_focus: Optional[Dict[str, Any]],
) -> None:
    """就地标记总龙头是否兼资金焦点。"""
    if not market_leader:
        return
    same = bool(
        capital_focus
        and market_leader.get("code")
        and str(market_leader["code"]) == str(capital_focus.get("code") or "")
    )
    market_leader["same_as_capital_focus"] = same
