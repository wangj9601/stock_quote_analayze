"""收盘后的同花顺行业资金气泡。

横轴用当日涨跌幅，纵轴用主力净流入（元）。气泡大小由净流入绝对值决定。
净流入缺失时，用流入减流出。

可选叠加相对轮动（RRG）象限：按气泡交易日取每个板块最后一条不超过该日的 RRG 点，
再由 backend_core.analysis.rotation_flow_signal 交叉成信号（领先+流出=兑现预警 等）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_core.analysis.rotation_flow_signal import (
    classify_flow_rotation,
    quadrant_label,
    summarize_flow_rotation,
)

logger = logging.getLogger(__name__)

ROTATION_WINDOW = 10
ROTATION_LOOKBACK = 120


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


def _rotation_point(points: Iterable[Dict[str, Any]], trade_date: Optional[str]) -> Optional[Dict[str, Any]]:
    """points 按日期升序；取最后一条 trade_date 不晚于气泡日的点。"""
    if not trade_date:
        return None
    latest: Optional[Dict[str, Any]] = None
    for point in points:
        point_date = str(point.get("trade_date") or "")
        if not point_date:
            continue
        if point_date > trade_date:
            break
        latest = point
    return latest


def attach_rotation(
    items: List[Dict[str, Any]],
    rotation: Optional[Dict[str, Any]],
    trade_date: Optional[str],
) -> List[Dict[str, Any]]:
    """给每个气泡补上轮动象限与交叉信号；没有对应板块就记成未覆盖。"""
    boards = {
        str(board.get("board_code")): board
        for board in ((rotation or {}).get("boards") or [])
        if board.get("board_code")
    }
    for item in items:
        board = boards.get(item["board_code"])
        point = _rotation_point((board or {}).get("points") or [], trade_date)
        quadrant = str(point.get("quadrant") or "") if point else ""
        if quadrant:
            item["rotation_quadrant"] = quadrant
            item["rotation_label"] = quadrant_label(quadrant)
            item["rs_ratio"] = point.get("rs_ratio")
            item["rs_momentum"] = point.get("rs_momentum")
            item["rotation_trade_date"] = point.get("trade_date")
        else:
            item["rotation_quadrant"] = None
            item["rotation_label"] = None
            item["rs_ratio"] = None
            item["rs_momentum"] = None
            item["rotation_trade_date"] = None
        item.update(classify_flow_rotation(item["rotation_quadrant"], item["direction"]))
    return items


def build_fund_bubbles(
    trade_date: Optional[str],
    rows: Iterable[Dict[str, Any]],
    *,
    board_kind: str = "industry",
    rotation: Optional[Dict[str, Any]] = None,
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
    attach_rotation(items, rotation, trade_date)
    kind = board_kind if board_kind in ("industry", "concept") else "industry"
    label = "概念" if kind == "concept" else "行业"
    summary = summarize_flow_rotation(items)
    rotation_note = str((rotation or {}).get("note") or "")
    if rotation is None:
        rotation_note = "未叠加相对轮动"
    return {
        "trade_date": trade_date,
        "board_kind": kind,
        "board_count": len(items),
        "in_count": sum(1 for item in items if item["direction"] == "in"),
        "out_count": sum(1 for item in items if item["direction"] == "out"),
        "items": items,
        "rotation": {
            "enabled": rotation is not None,
            "as_of": trade_date,
            "window": (rotation or {}).get("window"),
            "benchmark_name": (rotation or {}).get("benchmark_name"),
            "note": rotation_note,
        },
        "flow_rotation": summary,
        "note": "" if items else f"暂无{label}资金流，无法画气泡。",
    }


def fetch_industry_fund_bubbles(
    db: Session,
    board_kind: str = "industry",
    *,
    include_rotation: bool = True,
) -> Dict[str, Any]:
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
    rotation = None
    if include_rotation:
        rotation = _load_rotation(db, kind)
    return build_fund_bubbles(trade_date, rows, board_kind=kind, rotation=rotation)


def _load_rotation(db: Session, kind: str) -> Optional[Dict[str, Any]]:
    """轮动算不出来不该拖垮气泡：失败只记日志，气泡照常返回。"""
    from backend_api.utils.board_rotation import fetch_industry_rotation

    try:
        return fetch_industry_rotation(
            db,
            window=ROTATION_WINDOW,
            lookback=ROTATION_LOOKBACK,
            board_kind=kind,
        )
    except Exception:
        logger.exception("资金气泡叠加相对轮动失败，退回纯资金视图")
        return None
