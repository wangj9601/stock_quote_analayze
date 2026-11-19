"""单个行业或概念在资金气泡里的位置，以及它自己的相对轮动轨迹。

全市场只用来排名：净流入、涨跌幅各排一次。轮动只算这一只相对沪深300。
没有资金流时不拿轮动去猜交叉信号。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_api.utils.board_flow_bubbles import _direction, _net_amount
from backend_api.utils.board_rotation import _ROTATION_TABLES, build_rotation
from backend_core.analysis.rotation_flow_signal import (
    UNCOVERED_SIGNAL,
    classify_flow_rotation,
    quadrant_label,
)

logger = logging.getLogger(__name__)

TRAIL_LIMIT = 15
ROTATION_WINDOW = 10
ROTATION_LOOKBACK = 120


def _date_text(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    text_value = str(value).strip()
    return text_value[:10]


def _float(value: Any) -> Optional[float]:
    try:
        if value in (None, "", "-"):
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _kind_label(board_kind: str) -> str:
    return "概念" if board_kind == "concept" else "行业"


def _empty_rotation(benchmark_name: str, window: int, note: str = "") -> Dict[str, Any]:
    return {
        "available": False,
        "note": note,
        "benchmark_name": benchmark_name,
        "window": window,
        "trade_date": None,
        "quadrant": None,
        "label": None,
        "rs_ratio": None,
        "rs_momentum": None,
        "trail": [],
    }


def _normalize_flow_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        code = str(row.get("board_code") or "").strip()
        trade_date = _date_text(row.get("trade_date") or row.get("date"))
        change = _float(row.get("change_percent"))
        net = _net_amount(row)
        if not code or not trade_date or change is None or net is None:
            continue
        name = str(row.get("board_name") or code).strip() or code
        normalized.append(
            {
                "board_code": code,
                "board_name": name,
                "trade_date": trade_date,
                "change_percent": round(change, 2),
                "main_net_inflow": net,
                "main_net_yi": round(net / 1e8, 4),
                "direction": _direction(net),
            }
        )
    return normalized


def _rank(rows: List[Dict[str, Any]], code: str, field: str) -> int:
    ordered = sorted(rows, key=lambda item: (-float(item[field]), item["board_code"]))
    for index, item in enumerate(ordered, start=1):
        if item["board_code"] == code:
            return index
    return 0


def _rotation_on_or_before(
    points: Iterable[Dict[str, Any]],
    trade_date: str,
    *,
    benchmark_name: str,
    window: int,
    trail_limit: int,
) -> Dict[str, Any]:
    kept: List[Dict[str, Any]] = []
    for raw in points:
        point_date = _date_text(raw.get("trade_date") or raw.get("date"))
        if not point_date or point_date > trade_date:
            continue
        if raw.get("rs_ratio") is None or raw.get("rs_momentum") is None:
            continue
        quadrant = str(raw.get("quadrant") or "")
        kept.append(
            {
                "trade_date": point_date,
                "rs_ratio": raw.get("rs_ratio"),
                "rs_momentum": raw.get("rs_momentum"),
                "quadrant": quadrant,
                "label": quadrant_label(quadrant),
            }
        )
    kept.sort(key=lambda item: item["trade_date"])
    if not kept:
        return _empty_rotation(benchmark_name, window, "日线不足，无法计算相对轮动。")
    trail = kept[-trail_limit:]
    head = trail[-1]
    return {
        "available": True,
        "note": "",
        "benchmark_name": benchmark_name,
        "window": window,
        "trade_date": head["trade_date"],
        "quadrant": head["quadrant"],
        "label": head["label"],
        "rs_ratio": head["rs_ratio"],
        "rs_momentum": head["rs_momentum"],
        "trail": trail,
    }


def build_board_flow_focus(
    board_code: str,
    flow_rows: Iterable[Dict[str, Any]],
    rotation_points: Iterable[Dict[str, Any]],
    *,
    board_kind: str = "industry",
    requested_date: Optional[str] = None,
    benchmark_name: str = "沪深300",
    window: int = ROTATION_WINDOW,
    trail_limit: int = TRAIL_LIMIT,
) -> Dict[str, Any]:
    """用一日全市场资金流给当前板块排名，轮动点不晚于该资金日。"""
    kind = board_kind if board_kind in ("industry", "concept") else "industry"
    label = _kind_label(kind)
    code = str(board_code or "").strip()
    requested = _date_text(requested_date) if requested_date else ""
    rows = _normalize_flow_rows(flow_rows)
    uncovered = dict(UNCOVERED_SIGNAL)

    def unavailable(note: str, trade_date: Optional[str] = None, date_note: str = "") -> Dict[str, Any]:
        return {
            "available": False,
            "board_code": code,
            "board_name": None,
            "board_kind": kind,
            "requested_date": requested or None,
            "trade_date": trade_date,
            "date_note": date_note,
            "note": note,
            "flow": None,
            "rotation": _empty_rotation(benchmark_name, window),
            "signal": uncovered,
        }

    if not rows:
        if requested:
            return unavailable(f"基准日之前暂无{label}资金流，无法给出资金与轮动交叉。")
        return unavailable(f"暂无{label}资金流，无法给出资金与轮动交叉。")

    if requested:
        eligible = [row for row in rows if row["trade_date"] <= requested]
    else:
        eligible = rows
    if not eligible:
        return unavailable(f"基准日之前暂无{label}资金流，无法给出资金与轮动交叉。")

    trade_date = max(row["trade_date"] for row in eligible)
    date_note = ""
    if requested and trade_date != requested:
        date_note = f"基准日无资金流，改用 {trade_date}"
    day_rows = [row for row in eligible if row["trade_date"] == trade_date]
    target = next((row for row in day_rows if row["board_code"] == code), None)
    if target is None:
        return unavailable(f"{trade_date} 无该板块资金流。", trade_date, date_note)

    rotation = _rotation_on_or_before(
        rotation_points,
        trade_date,
        benchmark_name=benchmark_name,
        window=window,
        trail_limit=trail_limit,
    )
    signal = classify_flow_rotation(rotation.get("quadrant"), target["direction"])
    return {
        "available": True,
        "board_code": code,
        "board_name": target["board_name"],
        "board_kind": kind,
        "requested_date": requested or None,
        "trade_date": trade_date,
        "date_note": date_note,
        "note": "",
        "flow": {
            "change_percent": target["change_percent"],
            "main_net_inflow": target["main_net_inflow"],
            "main_net_yi": target["main_net_yi"],
            "direction": target["direction"],
            "net_rank": _rank(day_rows, code, "main_net_inflow"),
            "change_rank": _rank(day_rows, code, "change_percent"),
            "universe": len(day_rows),
        },
        "rotation": rotation,
        "signal": signal,
    }


def fetch_board_flow_focus(
    db: Session,
    board_code: str,
    *,
    board_kind: str = "industry",
    asof: Optional[str] = None,
    window: int = ROTATION_WINDOW,
    lookback: int = ROTATION_LOOKBACK,
) -> Dict[str, Any]:
    """资金流取不晚于基准日的最近一天；轮动只查这一只板块。"""
    kind = board_kind if board_kind in _ROTATION_TABLES else "industry"
    code = str(board_code or "").strip()
    requested = _date_text(asof) if asof else None
    date_sql = """
        SELECT MAX(trade_date)
        FROM board_fund_flow_daily
        WHERE board_kind = :kind
          AND board_code_source = 'tonghuashun'
    """
    params: Dict[str, Any] = {"kind": kind}
    if requested:
        date_sql += " AND trade_date <= CAST(:asof AS date)"
        params["asof"] = requested
    latest = db.execute(text(date_sql), params).scalar()
    if latest is None:
        return build_board_flow_focus(
            code,
            [],
            [],
            board_kind=kind,
            requested_date=requested,
        )
    trade_date = _date_text(latest)
    rows = db.execute(
        text(
            """
            SELECT board_code, board_name, trade_date, change_percent,
                   inflow_amount, outflow_amount, main_net_inflow
            FROM board_fund_flow_daily
            WHERE board_kind = :kind
              AND board_code_source = 'tonghuashun'
              AND trade_date = CAST(:td AS date)
            """
        ),
        {"kind": kind, "td": trade_date},
    ).mappings().all()
    points: List[Dict[str, Any]] = []
    try:
        from backend_core.analysis.index_bars import load_index_ohlc_asc

        bars = load_index_ohlc_asc(db, "000300", lookback=int(lookback), asof=trade_date)
        if bars:
            table = _ROTATION_TABLES[kind]
            quote_rows = db.execute(
                text(
                    f"""
                    SELECT board_code, board_name, trade_date, close
                    FROM {table}
                    WHERE board_code = :code
                      AND trade_date >= CAST(:start AS date)
                      AND trade_date <= CAST(:end AS date)
                      AND close IS NOT NULL
                      AND close > 0
                    """
                ),
                {"code": code, "start": bars[0]["date"], "end": bars[-1]["date"]},
            ).mappings().all()
            rotation = build_rotation(
                bars,
                quote_rows,
                window,
                benchmark_code="000300",
                benchmark_name="沪深300",
                board_kind=kind,
            )
            matched = next(
                (board for board in rotation.get("boards") or [] if board.get("board_code") == code),
                None,
            )
            points = list((matched or {}).get("points") or [])
    except Exception:
        logger.exception("单板块相对轮动计算失败 %s", code)
        points = []
    return build_board_flow_focus(
        code,
        rows,
        points,
        board_kind=kind,
        requested_date=requested,
    )


def flow_focus_or_note(
    db: Session,
    board_code: str,
    *,
    board_kind: str,
    asof: Optional[str] = None,
) -> Dict[str, Any]:
    """分析包用。算失败时退回说明，不把整次指数分析打掉。"""
    try:
        return fetch_board_flow_focus(db, board_code, board_kind=board_kind, asof=asof)
    except Exception:
        logger.exception("资金与相对轮动读取失败 %s", board_code)
        try:
            db.rollback()
        except Exception:
            pass
        return {
            "available": False,
            "board_code": str(board_code or "").strip(),
            "board_kind": board_kind if board_kind in ("industry", "concept") else "industry",
            "note": "资金与相对轮动暂时算不出来。",
            "flow": None,
            "rotation": _empty_rotation("沪深300", ROTATION_WINDOW),
            "signal": dict(UNCOVERED_SIGNAL),
        }
