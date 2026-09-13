"""纸面复盘 KPI（观察期用）。"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Dict, List, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session


def _herfindahl(shares: List[float]) -> float:
    total = sum(shares)
    if total <= 0:
        return 0.0
    return sum((s / total) ** 2 for s in shares)


def compute_brief_concentration_kpi(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """可执行名单板上集中度（赫芬达尔）与角色分布。"""
    exec_items = [x for x in items if x.get("action") == "buy"]
    boards = [str(x.get("board_code") or "_none_") for x in exec_items]
    cnt = Counter(boards)
    hhi = _herfindahl([float(v) for v in cnt.values()]) if cnt else 0.0
    role_cnt = Counter(str(x.get("role") or "normal") for x in exec_items)
    return {
        "executable_count": len(exec_items),
        "board_counts": dict(cnt),
        "board_hhi": round(hhi, 4),
        "role_counts": dict(role_cnt),
        "theme_board_count": len([b for b in cnt if b != "_none_"]),
    }


def compute_buy_zone_touch_rate(
    db: Session,
    *,
    asof_date: str,
    horizon: str = "daily",
    forward_days: int = 3,
) -> Dict[str, Any]:
    """触达买区率：简报可执行标的在 T+1～T+N 是否触及买区。

    买区取 buy_zone.low～high 或 price±1%。
    """
    from backend_core.recommend.store import get_brief

    brief = get_brief(db, horizon=horizon, asof_date=asof_date)
    if not brief:
        return {"ok": False, "reason": "brief_not_found"}
    exec_items = [x for x in (brief.get("items") or []) if x.get("action") == "buy"]
    if not exec_items:
        return {
            "ok": True,
            "asof_date": asof_date,
            "sample": 0,
            "touched": 0,
            "touch_rate": None,
        }

    touched = 0
    sample = 0
    details: List[Dict[str, Any]] = []
    for it in exec_items:
        code = str(it.get("code") or "").strip()
        if not code:
            continue
        zone = it.get("buy_zone") or {}
        low = zone.get("low")
        high = zone.get("high")
        price = zone.get("price")
        try:
            if low is None and high is None and price is not None:
                p = float(price)
                low, high = p * 0.99, p * 1.01
            if low is None or high is None:
                continue
            lo, hi = float(low), float(high)
        except (TypeError, ValueError):
            continue
        sample += 1
        try:
            rows = db.execute(
                text(
                    """
                    SELECT date::text, low, high, close
                    FROM historical_quotes
                    WHERE code = :code AND date > CAST(:asof AS date)
                    ORDER BY date ASC
                    LIMIT :n
                    """
                ),
                {"code": code, "asof": asof_date, "n": int(forward_days)},
            ).fetchall()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            rows = []
        hit = False
        hit_date = None
        for r in rows:
            try:
                bar_low = float(r[1]) if r[1] is not None else None
                bar_high = float(r[2]) if r[2] is not None else None
            except (TypeError, ValueError):
                continue
            if bar_low is None or bar_high is None:
                continue
            # 区间重叠即触及
            if bar_low <= hi and bar_high >= lo:
                hit = True
                hit_date = str(r[0])[:10]
                break
        if hit:
            touched += 1
        details.append({"code": code, "touched": hit, "hit_date": hit_date})

    rate = (touched / sample) if sample else None
    return {
        "ok": True,
        "asof_date": asof_date,
        "forward_days": forward_days,
        "sample": sample,
        "touched": touched,
        "touch_rate": round(rate, 4) if rate is not None else None,
        "details": details[:50],
    }
