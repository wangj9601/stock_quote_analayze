"""从 DB 取成分 + 实时行情并标注龙头/中军。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_api.utils.board_code_source import (
    DEFAULT_BOARD_CODE_SOURCE,
    board_code_source_label,
)
from backend_api.utils.industry_board_query import (
    list_board_constituent_codes,
    resolve_board_for_roles,
)
from backend_core.board_roles.classify import (
    board_change_percent_est,
    classify_board_roles,
    role_tag_from_row,
)
from backend_core.strategies.sbbr.size_filter import calc_mv_yi


def _normalize_stock_code(code: str) -> str:
    s = str(code).strip()
    if s.isdigit() and len(s) < 6:
        return s.zfill(6)
    return s


def _latest_ashare_trade_date(db: Session) -> Optional[str]:
    row = db.execute(
        text(
            """
            SELECT MAX(trade_date) AS latest_date
            FROM stock_realtime_quote
            WHERE change_percent IS NOT NULL
            """
        )
    ).fetchone()
    return str(row[0]) if row and row[0] else None


def enrich_constituents_with_quotes(
    db: Session, constituents: Sequence[Dict[str, str]]
) -> List[Dict[str, Any]]:
    """成分列表 + 最新实时行情/市值。"""
    if not constituents:
        return []
    trade_date = _latest_ashare_trade_date(db)
    codes = [_normalize_stock_code(c["code"]) for c in constituents if c.get("code")]
    quote_map: Dict[str, Dict[str, Any]] = {}
    shares_map: Dict[str, Dict[str, Any]] = {}

    if trade_date and codes:
        placeholders = ",".join([f":c{i}" for i in range(len(codes))])
        params = {f"c{i}": codes[i] for i in range(len(codes))}
        params["trade_date"] = trade_date
        sql = text(
            f"""
            SELECT code, name, current_price, change_percent, amount,
                   circulating_market_value, total_market_value
            FROM stock_realtime_quote
            WHERE trade_date = :trade_date AND code IN ({placeholders})
            """
        )
        for row in db.execute(sql, params).fetchall():
            quote_map[str(row[0])] = {
                "name_rt": row[1],
                "current_price": row[2],
                "change_percent": float(row[3]) if row[3] is not None else None,
                "amount": float(row[4]) if row[4] is not None else None,
                "circulating_market_value": (
                    float(row[5]) if row[5] is not None else None
                ),
                "total_market_value": float(row[6]) if row[6] is not None else None,
            }

        need_shares = [
            c
            for c in codes
            if not (quote_map.get(c) or {}).get("circulating_market_value")
        ]
        if need_shares:
            ph2 = ",".join([f":s{i}" for i in range(len(need_shares))])
            params2 = {f"s{i}": need_shares[i] for i in range(len(need_shares))}
            for row in db.execute(
                text(
                    f"""
                    SELECT code, free_float_shares, total_shares
                    FROM stock_basic_info
                    WHERE code IN ({ph2})
                    """
                ),
                params2,
            ).fetchall():
                shares_map[str(row[0])] = {
                    "free_float_shares": row[1],
                    "total_shares": row[2],
                }

    items: List[Dict[str, Any]] = []
    for c in constituents:
        code = _normalize_stock_code(c.get("code") or "")
        if not code:
            continue
        q = quote_map.get(code, {})
        price = q.get("current_price")
        circ = q.get("circulating_market_value")
        if circ is None or circ <= 0:
            sh = shares_map.get(code) or {}
            # calc_mv_yi 返回亿元；实时表通常为元。统一用元参与分位：亿元 * 1e8
            circ_yi = calc_mv_yi(sh.get("free_float_shares"), price)
            if circ_yi is not None:
                circ = circ_yi * 1e8
        items.append(
            {
                "code": code,
                "name": c.get("name") or q.get("name_rt") or code,
                "change_percent": q.get("change_percent"),
                "current_price": price,
                "amount": q.get("amount"),
                "circulating_market_value": circ,
                "total_market_value": q.get("total_market_value"),
            }
        )
    return items


def fetch_board_roles_payload(
    db: Session,
    *,
    board_type: str,
    board_code: str,
    board_code_source: Optional[str] = None,
    board_name: Optional[str] = None,
    limit: Optional[int] = None,
    sort_by_change: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    解析板块来源 → 成分 → 行情 → 角色。
    解析失败返回 None（调用方 404）；无成分返回空 stocks。
    """
    meta = resolve_board_for_roles(
        db,
        board_type,
        board_code,
        board_code_source=board_code_source,
        board_name=board_name,
    )
    if not meta:
        return None

    cons = list_board_constituent_codes(db, meta["board_type"], meta["board_code"])
    items = enrich_constituents_with_quotes(db, cons)
    classify_board_roles(items)
    if sort_by_change:
        items.sort(
            key=lambda x: (
                x["change_percent"] if x.get("change_percent") is not None else -1e9
            ),
            reverse=True,
        )
    est = board_change_percent_est(items)
    if limit is not None:
        items = items[: max(0, int(limit))]
    return {
        "board_type": meta["board_type"],
        "board_code": meta["board_code"],
        "board_name": meta["board_name"],
        "board_code_source": meta["board_code_source"],
        "board_code_source_label": meta["board_code_source_label"],
        "board_change_percent_est": est,
        "stocks": items,
        "total": len(cons),
        "data_source": f"{meta['board_type']}_board_constituents",
    }


def enrich_screening_results_with_role_tags(
    db: Session,
    results: List[Dict[str, Any]],
    *,
    board_type: str,
    board_codes: Sequence[str],
    board_code_source: Optional[str] = None,
) -> None:
    """按所选板为选股结果挂 role_tags（多板取 score 最高角色）。"""
    if not results or not board_codes:
        return
    source = board_code_source or DEFAULT_BOARD_CODE_SOURCE
    # code -> best (score, tag)
    best: Dict[str, Any] = {}
    for bc in board_codes:
        payload = fetch_board_roles_payload(
            db,
            board_type=board_type,
            board_code=str(bc).strip(),
            board_code_source=source,
            limit=None,
        )
        if not payload:
            continue
        for row in payload.get("stocks") or []:
            tag = role_tag_from_row(row)
            if not tag:
                continue
            code = _normalize_stock_code(str(row.get("code") or ""))
            score = float(row.get("board_role_score") or 0)
            prev = best.get(code)
            if prev is None or score > prev[0]:
                reason = tag.get("reason") or ""
                label_src = board_code_source_label(payload["board_code_source"])
                tag = dict(tag)
                tag["reason"] = (
                    f"[{payload['board_name']}/{label_src}] {reason}".strip()
                )
                best[code] = (score, tag)

    for item in results:
        code = _normalize_stock_code(
            str(item.get("code") or item.get("symbol") or "")
        )
        hit = best.get(code)
        item["role_tags"] = [hit[1]] if hit else []
