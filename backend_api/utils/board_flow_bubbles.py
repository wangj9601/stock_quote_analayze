"""收盘后的同花顺行业资金气泡。

横轴用当日涨跌幅，纵轴用主力净流入（元）。气泡大小由净流入绝对值决定。
净流入缺失时，用流入减流出。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def _float(value: Any) -> Optional[float]:
    try:
        if value in (None, "", "-"):
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


def _net_amount(row: Dict[str, Any]) -> Optional[float]:
    net = _float(row.get("main_net_inflow"))
    if net is not None:
        return net
    inflow = _float(row.get("inflow_amount"))
    outflow = _float(row.get("outflow_amount"))
    if inflow is None or outflow is None:
        return None
    return inflow - outflow


def _direction(net: float) -> str:
    if net > 0:
        return "in"
    if net < 0:
        return "out"
    return "flat"


def build_fund_bubbles(
    trade_date: Optional[str],
    rows: Iterable[Dict[str, Any]],
    *,
    board_kind: str = "industry",
) -> Dict[str, Any]:
    """把一日行业资金流收成气泡点。没有涨跌幅或净流入的行不进图。"""
    items: List[Dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        net = _net_amount(row)
        change = _float(row.get("change_percent"))
        if net is None or change is None:
            continue
        code = str(row.get("board_code") or "").strip()
        name = str(row.get("board_name") or code).strip() or code
        if not code:
            continue
        items.append(
            {
                "board_code": code,
                "board_name": name,
                "change_percent": round(change, 2),
                "main_net_inflow": net,
                "main_net_yi": round(net / 1e8, 4),
                "direction": _direction(net),
            }
        )
    items.sort(key=lambda item: abs(item["main_net_inflow"]), reverse=True)
    kind = board_kind if board_kind in ("industry", "concept") else "industry"
    label = "概念" if kind == "concept" else "行业"
    return {
        "trade_date": trade_date,
        "board_kind": kind,
        "board_count": len(items),
        "in_count": sum(1 for item in items if item["direction"] == "in"),
        "out_count": sum(1 for item in items if item["direction"] == "out"),
        "items": items,
        "note": "" if items else f"暂无{label}资金流，无法画气泡。",
    }


def fetch_industry_fund_bubbles(db: Session, board_kind: str = "industry") -> Dict[str, Any]:
    """最新一个有数据的交易日。board_kind 为 industry 或 concept。"""
    kind = board_kind if board_kind in ("industry", "concept") else "industry"
    latest = db.execute(
        text(
            """
            SELECT MAX(trade_date)
            FROM board_fund_flow_daily
            WHERE board_kind = :kind
              AND board_code_source = 'tonghuashun'
            """
        ),
        {"kind": kind},
    ).scalar()
    if latest is None:
        return build_fund_bubbles(None, [], board_kind=kind)
    trade_date = latest.isoformat() if hasattr(latest, "isoformat") else str(latest)[:10]
    rows = db.execute(
        text(
            """
            SELECT board_code, board_name, change_percent,
                   inflow_amount, outflow_amount, main_net_inflow
            FROM board_fund_flow_daily
            WHERE board_kind = :kind
              AND board_code_source = 'tonghuashun'
              AND trade_date = CAST(:td AS date)
            """
        ),
        {"kind": kind, "td": trade_date},
    ).mappings().all()
    return build_fund_bubbles(trade_date, rows, board_kind=kind)
