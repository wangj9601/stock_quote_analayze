# -*- coding: utf-8 -*-
"""龙虎榜快照落库。金额单位：元。机构净额、游资净额仅同花顺有值。"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

FUYAO_SOURCE = "fuyao"


def should_replace_snapshot(existing_source: Optional[str], incoming_source: str) -> bool:
    """已有同花顺快照时，不用东方财富覆盖（避免机构/游资净额被写成空）。"""
    src = (incoming_source or "").strip()
    if src in ("", "none"):
        return False
    if (existing_source or "").strip() == FUYAO_SOURCE and src != FUYAO_SOURCE:
        return False
    return True


def _items(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = data.get("items")
    if not isinstance(raw, list):
        return []
    return [x for x in raw if isinstance(x, dict)]


def _seats(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = data.get("hot_money_items")
    if not isinstance(raw, list):
        return []
    return [x for x in raw if isinstance(x, dict)]


def persist_dragon_tiger(data: Dict[str, Any], db: Optional[Session] = None) -> int:
    """写入一日一榜快照。无可落库内容或被同花顺保护跳过时返回 0。失败只打日志。"""
    trade_date = str(data.get("trade_date") or "").strip()[:10]
    board_type = str(data.get("board_type") or "all").strip().lower()
    source = str(data.get("source") or "").strip()
    items = _items(data)
    seats = _seats(data)
    if not trade_date or not should_replace_snapshot(None, source):
        return 0
    if not items and not seats:
        return 0

    own_session = db is None
    if own_session:
        from backend_api.database import SessionLocal

        db = SessionLocal()
    assert db is not None
    try:
        existing = db.execute(
            text(
                """
                SELECT source FROM dragon_tiger_snapshot
                WHERE trade_date = :trade_date AND board_type = :board_type
                """
            ),
            {"trade_date": trade_date, "board_type": board_type},
        ).scalar()
        if not should_replace_snapshot(existing, source):
            logger.info(
                "龙虎榜保留同花顺快照，跳过 %s %s source=%s",
                trade_date,
                board_type,
                source,
            )
            return 0

        db.execute(
            text(
                """
                DELETE FROM dragon_tiger_snapshot
                WHERE trade_date = :trade_date AND board_type = :board_type
                """
            ),
            {"trade_date": trade_date, "board_type": board_type},
        )
        db.execute(
            text(
                """
                INSERT INTO dragon_tiger_snapshot (
                    trade_date, board_type, source, source_label,
                    stock_count, item_count, amount_unit,
                    fallback_reason, board_type_note, updated_at
                ) VALUES (
                    :trade_date, :board_type, :source, :source_label,
                    :stock_count, :item_count, :amount_unit,
                    :fallback_reason, :board_type_note, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "trade_date": trade_date,
                "board_type": board_type,
                "source": source,
                "source_label": data.get("source_label"),
                "stock_count": data.get("stock_count"),
                "item_count": len(items),
                "amount_unit": data.get("amount_unit") or "yuan",
                "fallback_reason": data.get("fallback_reason"),
                "board_type_note": data.get("board_type_note"),
            },
        )
        stock_stmt = text(
            """
            INSERT INTO dragon_tiger_stock (
                trade_date, board_type, seq, code, name,
                change_percent, close, buy_value, sell_value, net_value, net_rate,
                org_net_value, hot_money_net_value,
                deal_value, market_turnover, turnover_rate,
                reason, interpretation, range_days, hot_rank, concepts,
                after_1d, after_2d, after_5d
            ) VALUES (
                :trade_date, :board_type, :seq, :code, :name,
                :change_percent, :close, :buy_value, :sell_value, :net_value, :net_rate,
                :org_net_value, :hot_money_net_value,
                :deal_value, :market_turnover, :turnover_rate,
                :reason, :interpretation, :range_days, :hot_rank, :concepts,
                :after_1d, :after_2d, :after_5d
            )
            """
        )
        org_filled = 0
        hot_filled = 0
        for seq, row in enumerate(items, 1):
            if row.get("org_net_value") is not None:
                org_filled += 1
            if row.get("hot_money_net_value") is not None:
                hot_filled += 1
            db.execute(
                stock_stmt,
                {
                    "trade_date": trade_date,
                    "board_type": board_type,
                    "seq": seq,
                    "code": str(row.get("code") or "")[:10],
                    "name": row.get("name"),
                    "change_percent": row.get("change_percent"),
                    "close": row.get("close"),
                    "buy_value": row.get("buy_value"),
                    "sell_value": row.get("sell_value"),
                    "net_value": row.get("net_value"),
                    "net_rate": row.get("net_rate"),
                    "org_net_value": row.get("org_net_value"),
                    "hot_money_net_value": row.get("hot_money_net_value"),
                    "deal_value": row.get("deal_value"),
                    "market_turnover": row.get("market_turnover"),
                    "turnover_rate": row.get("turnover_rate"),
                    "reason": row.get("reason"),
                    "interpretation": row.get("interpretation"),
                    "range_days": row.get("range_days"),
                    "hot_rank": row.get("hot_rank"),
                    "concepts": row.get("concepts"),
                    "after_1d": row.get("after_1d"),
                    "after_2d": row.get("after_2d"),
                    "after_5d": row.get("after_5d"),
                },
            )
        seat_stmt = text(
            """
            INSERT INTO dragon_tiger_hot_money (
                trade_date, board_type, seq, seat_name,
                buy_value, sell_value, net_value, stocks
            ) VALUES (
                :trade_date, :board_type, :seq, :seat_name,
                :buy_value, :sell_value, :net_value, CAST(:stocks AS JSONB)
            )
            """
        )
        for seq, seat in enumerate(seats, 1):
            stocks = seat.get("stocks") if isinstance(seat.get("stocks"), list) else []
            db.execute(
                seat_stmt,
                {
                    "trade_date": trade_date,
                    "board_type": board_type,
                    "seq": seq,
                    "seat_name": str(seat.get("name") or "未知席位"),
                    "buy_value": seat.get("buy_value"),
                    "sell_value": seat.get("sell_value"),
                    "net_value": seat.get("net_value"),
                    "stocks": json.dumps(stocks, ensure_ascii=False),
                },
            )
        db.commit()
        logger.info(
            "龙虎榜已落库 %s %s source=%s stocks=%s seats=%s org_net=%s hot_net=%s",
            trade_date,
            board_type,
            source,
            len(items),
            len(seats),
            org_filled,
            hot_filled,
        )
        return len(items)
    except Exception:
        db.rollback()
        logger.exception("龙虎榜落库失败 %s %s", trade_date, board_type)
        return 0
    finally:
        if own_session:
            db.close()
