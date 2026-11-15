"""A 股同花顺行业热力图：一票一格，面积看流通市值，颜色看当日涨跌幅。"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_api.utils.board_code_source import (
    DEFAULT_BOARD_CODE_SOURCE,
    LEGACY_DEFAULT_BOARD_CODE_SOURCE,
)

# 0–1%、1–3%、3–5%、5–7%、7% 以上。接近 0 用深灰。
_UP_COLORS = ("#5c2a32", "#8a2834", "#b42330", "#d61f28", "#f0342c")
_DOWN_COLORS = ("#1a4a38", "#0e6644", "#0b8550", "#0f9d5c", "#14b86a")
_FLAT_COLOR = "#2a3140"
_FLAT_ABS = 0.005


def normalize_stock_code(code: Any) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) < 6:
        return s.zfill(6)
    return s


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def tile_value(
    circulating_market_value: Any,
    total_market_value: Any,
    amount: Any,
) -> Optional[float]:
    """格子面积：流通市值，没有则总市值，再没有则成交额。非正数视为缺失。"""
    for raw in (circulating_market_value, total_market_value, amount):
        number = _finite(raw)
        if number is not None and number > 0:
            return number
    return None


def heat_color(change_percent: Any) -> str:
    """红涨绿跌阶梯色。|涨跌幅| < 0.005 视为平盘。"""
    number = _finite(change_percent)
    if number is None or abs(number) < _FLAT_ABS:
        return _FLAT_COLOR
    magnitude = abs(number)
    if magnitude < 1:
        index = 0
    elif magnitude < 3:
        index = 1
    elif magnitude < 5:
        index = 2
    elif magnitude < 7:
        index = 3
    else:
        index = 4
    palette = _UP_COLORS if number > 0 else _DOWN_COLORS
    return palette[index]


def _circ_contribution(circulating_market_value: Any) -> float:
    number = _finite(circulating_market_value)
    if number is None or number <= 0:
        return 0.0
    return number


def _round(value: Optional[float], digits: int) -> Optional[float]:
    if value is None:
        return None
    return round(value, digits)


def build_market_heatmap(
    trade_date: Optional[str],
    memberships: Iterable[Mapping[str, Any]],
    board_changes: Optional[Mapping[str, Any]] = None,
    *,
    board_kind: str = "industry",
    exclusive: Optional[bool] = None,
) -> Dict[str, Any]:
    """把「股票 × 板块」成员行收成树图。

    行业默认一只股票只出现一次：落在多个行业时，归到成分流通市值合计更大的行业；
    合计相同则取板块代码字典序较小的一个。
    概念允许重叠，同一只股票留在每一个所属概念里。
    ``memberships`` 每行是已经对上当日行情的成员。
    """
    kind = board_kind if board_kind in ("industry", "concept") else "industry"
    one_board_each = True if exclusive is None else bool(exclusive)
    if exclusive is None:
        one_board_each = kind != "concept"
    changes = board_changes or {}
    board_circ: Dict[str, float] = {}
    board_names: Dict[str, str] = {}
    seen_pairs = set()
    stock_boards: Dict[str, List[str]] = {}
    stock_rows: Dict[str, Mapping[str, Any]] = {}

    for row in memberships:
        code = normalize_stock_code(row.get("stock_code"))
        board_code = str(row.get("board_code") or "").strip()
        if not code or not board_code:
            continue
        pair = (code, board_code)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        board_names[board_code] = str(row.get("board_name") or "").strip() or board_code
        board_circ[board_code] = board_circ.get(board_code, 0.0) + _circ_contribution(
            row.get("circulating_market_value")
        )
        stock_boards.setdefault(code, []).append(board_code)
        stock_rows[code] = row

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for code, boards in stock_boards.items():
        row = stock_rows[code]
        change = _finite(row.get("change_percent"))
        value = tile_value(
            row.get("circulating_market_value"),
            row.get("total_market_value"),
            row.get("amount"),
        )
        if change is None or value is None:
            continue
        ordered = sorted(boards, key=lambda board: (-board_circ.get(board, 0.0), board))
        chosen_boards = ordered[:1] if one_board_each else ordered
        name = str(row.get("stock_name") or "").strip() or code
        tile = {
            "code": code,
            "name": name,
            "current_price": _round(_finite(row.get("current_price")), 4),
            "change_percent": _round(change, 4),
            "amount": _round(_finite(row.get("amount")), 2),
            "value": value,
            "color": heat_color(change),
        }
        for chosen in chosen_boards:
            grouped.setdefault(chosen, []).append(dict(tile))

    boards_out: List[Dict[str, Any]] = []
    for board_code, stocks in grouped.items():
        stocks.sort(key=lambda item: (-item["value"], item["code"]))
        board_change = _finite(changes.get(board_code))
        boards_out.append(
            {
                "board_code": board_code,
                "board_name": board_names.get(board_code) or board_code,
                "change_percent": _round(board_change, 4),
                "value": sum(item["value"] for item in stocks),
                "stocks": stocks,
            }
        )
    boards_out.sort(key=lambda item: (-item["value"], item["board_code"]))
    placed = [stock["code"] for item in boards_out for stock in item["stocks"]]
    return {
        "trade_date": trade_date,
        "board_kind": kind,
        "board_code_source": DEFAULT_BOARD_CODE_SOURCE,
        "stock_count": len(placed),
        "unique_stock_count": len(set(placed)),
        "board_count": len(boards_out),
        "boards": boards_out,
    }


def _latest_trade_date(db: Session) -> Optional[str]:
    row = db.execute(
        text(
            """
            SELECT MAX(trade_date) AS latest_date
            FROM stock_realtime_quote
            WHERE change_percent IS NOT NULL
            """
        )
    ).fetchone()
    if not row or row[0] is None:
        return None
    return str(row[0])


def _quote_map(db: Session, trade_date: str) -> Dict[str, Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT code, name, current_price, change_percent, amount,
                   circulating_market_value, total_market_value
            FROM stock_realtime_quote
            WHERE trade_date = :trade_date
              AND change_percent IS NOT NULL
            """
        ),
        {"trade_date": trade_date},
    ).fetchall()
    by_code: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        raw = str(row[0] or "").strip()
        if not raw:
            continue
        item = {
            "stock_name": row[1],
            "current_price": row[2],
            "change_percent": row[3],
            "amount": row[4],
            "circulating_market_value": row[5],
            "total_market_value": row[6],
        }
        by_code[raw] = item
        by_code.setdefault(normalize_stock_code(raw), item)
    return by_code


def _membership_rows(db: Session, board_kind: str) -> Sequence[Tuple[Any, ...]]:
    if board_kind == "concept":
        cons_table = "concept_board_constituents"
        basic_table = "concept_board_basic_info"
    else:
        cons_table = "industry_board_constituents"
        basic_table = "industry_board_basic_info"
    return db.execute(
        text(
            f"""
            SELECT c.stock_code, c.stock_name, b.board_code, b.board_name
            FROM {cons_table} c
            INNER JOIN {basic_table} b
                ON b.board_code = c.board_code
            WHERE COALESCE(NULLIF(TRIM(b.board_code_source), ''), :legacy) = :source
            """
        ),
        {
            "legacy": LEGACY_DEFAULT_BOARD_CODE_SOURCE,
            "source": DEFAULT_BOARD_CODE_SOURCE,
        },
    ).fetchall()


def _industry_change_map(db: Session) -> Dict[str, Any]:
    rows = db.execute(
        text(
            """
            SELECT DISTINCT ON (q.board_code)
                   q.board_code, q.change_percent
            FROM industry_board_realtime_quotes q
            INNER JOIN industry_board_basic_info b
                ON b.board_code = q.board_code
            WHERE COALESCE(NULLIF(TRIM(b.board_code_source), ''), :legacy) = :source
            ORDER BY q.board_code, q.update_time DESC NULLS LAST
            """
        ),
        {
            "legacy": LEGACY_DEFAULT_BOARD_CODE_SOURCE,
            "source": DEFAULT_BOARD_CODE_SOURCE,
        },
    ).fetchall()
    return {str(row[0]).strip(): row[1] for row in rows if row[0]}


def _concept_change_map(db: Session, trade_date: str) -> Dict[str, Any]:
    """概念指数当日涨跌幅。没有当日 K 时，用同日板块资金流里的涨跌幅。"""
    rows = db.execute(
        text(
            """
            SELECT board_code,
                   (array_agg(trade_date ORDER BY trade_date DESC))[1] AS asof,
                   (array_agg(close ORDER BY trade_date DESC))[1] AS close_now,
                   (array_agg(close ORDER BY trade_date DESC))[2] AS close_prev
            FROM concept_board_historical_quotes
            WHERE trade_date <= CAST(:td AS date)
              AND close IS NOT NULL
              AND close > 0
            GROUP BY board_code
            """
        ),
        {"td": trade_date},
    ).fetchall()
    changes: Dict[str, Any] = {}
    for code, asof, close_now, close_prev in rows:
        if not code or close_now is None or close_prev in (None, 0):
            continue
        asof_text = asof.isoformat()[:10] if hasattr(asof, "isoformat") else str(asof)[:10]
        if asof_text != trade_date:
            continue
        changes[str(code).strip()] = (float(close_now) / float(close_prev) - 1.0) * 100.0
    flow_rows = db.execute(
        text(
            """
            SELECT board_code, change_percent
            FROM board_fund_flow_daily
            WHERE board_kind = 'concept'
              AND board_code_source = 'tonghuashun'
              AND trade_date = CAST(:td AS date)
              AND change_percent IS NOT NULL
            """
        ),
        {"td": trade_date},
    ).fetchall()
    for code, change in flow_rows:
        if not code:
            continue
        key = str(code).strip()
        if key not in changes:
            changes[key] = change
    return changes


def _board_change_map(db: Session, board_kind: str, trade_date: str) -> Dict[str, Any]:
    if board_kind == "concept":
        return _concept_change_map(db, trade_date)
    return _industry_change_map(db)


def fetch_market_heatmap(db: Session, board_kind: str = "industry") -> Dict[str, Any]:
    """读最新交易日快照。行业一票一块，概念按所属概念重叠。"""
    kind = board_kind if board_kind in ("industry", "concept") else "industry"
    trade_date = _latest_trade_date(db)
    if not trade_date:
        return build_market_heatmap(None, [], {}, board_kind=kind)
    quotes = _quote_map(db, trade_date)
    memberships: List[Dict[str, Any]] = []
    for stock_code, stock_name, board_code, board_name in _membership_rows(db, kind):
        raw = str(stock_code or "").strip()
        quote = quotes.get(raw) or quotes.get(normalize_stock_code(raw))
        if not quote:
            continue
        quote_name = str(quote.get("stock_name") or "").strip()
        fallback_name = str(stock_name or "").strip()
        memberships.append(
            {
                "stock_code": raw,
                "stock_name": quote_name or fallback_name,
                "board_code": board_code,
                "board_name": board_name,
                "current_price": quote.get("current_price"),
                "change_percent": quote.get("change_percent"),
                "amount": quote.get("amount"),
                "circulating_market_value": quote.get("circulating_market_value"),
                "total_market_value": quote.get("total_market_value"),
            }
        )
    return build_market_heatmap(
        trade_date,
        memberships,
        _board_change_map(db, kind, trade_date),
        board_kind=kind,
    )
