# -*- coding: utf-8 -*-
"""行业板块：实时行情表 ↔ 历史指数日 K 字段互补。

同花顺实时一览无指数点位（latest_price 故意为空）；
``ak.stock_board_industry_index_ths`` 写入 ``industry_board_historical_quotes.close``。

互补规则（仅行业板）：
1. 实时 ← 历史：最新快照缺指数（或均价残留）时，用历史表最近收盘补 ``latest_price``，
   并可推算 ``change_amount``（相对上一交易日收盘）。
2. 历史 ← 实时：指定交易日历史缺 ``close``，且实时最新快照有「像指数」的点位时补 close。
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, Optional, Union

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_api.utils.board_code_source import DEFAULT_BOARD_CODE_SOURCE
from backend_core.database.db import SessionLocal

logger = logging.getLogger(__name__)

DateLike = Union[str, date, datetime, None]


def _ymd(val: DateLike) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, date):
        return val.isoformat()
    s = str(val).strip()
    return s[:10] if s else None


def supplement_realtime_from_historical(
    session: Session,
    *,
    asof_date: DateLike = None,
) -> Dict[str, Any]:
    """用历史指数收盘价补实时表最新快照的 latest_price。"""
    asof = _ymd(asof_date)
    # 仅更新每个 board_code 最新一条快照；不覆盖已有指数点位
    sql = text(
        """
        WITH latest_rt AS (
            SELECT DISTINCT ON (board_code)
                board_code,
                update_time,
                latest_price,
                change_amount
            FROM industry_board_realtime_quotes
            ORDER BY board_code, update_time DESC
        ),
        hist_pick AS (
            SELECT DISTINCT ON (h.board_code)
                h.board_code,
                h.trade_date,
                h.close,
                h.board_name
            FROM industry_board_historical_quotes h
            WHERE h.close IS NOT NULL
              AND (
                    :asof IS NULL
                    OR h.trade_date <= CAST(:asof AS date)
                  )
            ORDER BY h.board_code, h.trade_date DESC
        ),
        hist_prev AS (
            SELECT DISTINCT ON (h.board_code)
                h.board_code,
                h.close AS prev_close
            FROM industry_board_historical_quotes h
            INNER JOIN hist_pick p
              ON p.board_code = h.board_code
             AND h.trade_date < p.trade_date
            WHERE h.close IS NOT NULL
            ORDER BY h.board_code, h.trade_date DESC
        )
        UPDATE industry_board_realtime_quotes q
        SET
            latest_price = p.close,
            change_amount = COALESCE(
                q.change_amount,
                CASE
                    WHEN pv.prev_close IS NOT NULL THEN p.close - pv.prev_close
                    ELSE NULL
                END
            ),
            board_name = COALESCE(q.board_name, p.board_name)
        FROM latest_rt lr
        INNER JOIN hist_pick p ON p.board_code = lr.board_code
        LEFT JOIN hist_prev pv ON pv.board_code = lr.board_code
        WHERE q.board_code = lr.board_code
          AND q.update_time = lr.update_time
          AND (
                q.latest_price IS NULL
                OR (
                    q.latest_price < 100
                    AND q.change_amount IS NULL
                )
              )
        """
    )
    res = session.execute(sql, {"asof": asof})
    n = int(res.rowcount or 0)
    return {"updated": n, "asof_date": asof}


def supplement_historical_from_realtime(
    session: Session,
    *,
    trade_date: DateLike,
) -> Dict[str, Any]:
    """用实时表「像指数」的最新价，补指定日历史表缺失的 close。"""
    td = _ymd(trade_date)
    if not td:
        return {"upserted": 0, "trade_date": None, "error": "missing_trade_date"}

    sql = text(
        """
        WITH latest_rt AS (
            SELECT DISTINCT ON (q.board_code)
                q.board_code,
                q.board_name,
                q.latest_price,
                q.change_amount,
                q.volume,
                q.amount
            FROM industry_board_realtime_quotes q
            INNER JOIN industry_board_basic_info b
              ON b.board_code = q.board_code
            WHERE COALESCE(NULLIF(TRIM(b.board_code_source), ''), '')
                  = :src
              AND q.latest_price IS NOT NULL
              AND (
                    q.latest_price >= 100
                    OR q.change_amount IS NOT NULL
                  )
            ORDER BY q.board_code, q.update_time DESC
        )
        INSERT INTO industry_board_historical_quotes (
            board_code, trade_date, board_name,
            open, high, low, close, volume, amount,
            collected_source, update_time
        )
        SELECT
            r.board_code,
            CAST(:td AS date),
            r.board_name,
            NULL, NULL, NULL,
            r.latest_price,
            r.volume,
            r.amount,
            'realtime_index_fill',
            CURRENT_TIMESTAMP
        FROM latest_rt r
        ON CONFLICT (board_code, trade_date) DO UPDATE SET
            close = COALESCE(
                industry_board_historical_quotes.close,
                EXCLUDED.close
            ),
            volume = COALESCE(
                industry_board_historical_quotes.volume,
                EXCLUDED.volume
            ),
            amount = COALESCE(
                industry_board_historical_quotes.amount,
                EXCLUDED.amount
            ),
            board_name = COALESCE(
                industry_board_historical_quotes.board_name,
                EXCLUDED.board_name
            ),
            update_time = CURRENT_TIMESTAMP,
            collected_source = CASE
                WHEN industry_board_historical_quotes.close IS NULL
                THEN EXCLUDED.collected_source
                ELSE industry_board_historical_quotes.collected_source
            END
        WHERE industry_board_historical_quotes.close IS NULL
        """
    )
    res = session.execute(
        sql,
        {"td": td, "src": DEFAULT_BOARD_CODE_SOURCE},
    )
    n = int(res.rowcount or 0)
    return {"upserted": n, "trade_date": td}


def supplement_industry_board_quotes(
    session: Optional[Session] = None,
    *,
    trade_date: DateLike = None,
    asof_date: DateLike = None,
    commit: bool = True,
) -> Dict[str, Any]:
    """双向互补：历史→实时，再实时→历史（同日）。"""
    own = session is None
    db = session or SessionLocal()
    td = _ymd(trade_date) or _ymd(asof_date) or datetime.now().strftime("%Y-%m-%d")
    asof = _ymd(asof_date) or td
    out: Dict[str, Any] = {
        "trade_date": td,
        "asof_date": asof,
        "realtime_from_hist": {},
        "hist_from_realtime": {},
    }
    try:
        # 先用「实时里已有的指数点位」补当日历史缺 close（避免先用 T-1 历史灌实时再反写污染当日）
        out["hist_from_realtime"] = supplement_historical_from_realtime(
            db, trade_date=td
        )
        out["realtime_from_hist"] = supplement_realtime_from_historical(
            db, asof_date=asof
        )
        if commit:
            db.commit()
        logger.info(
            "行业板实时↔历史互补完成 hist+=%s rt+=%s date=%s",
            out["hist_from_realtime"].get("upserted"),
            out["realtime_from_hist"].get("updated"),
            td,
        )
        return out
    except Exception:
        if commit:
            db.rollback()
        raise
    finally:
        if own:
            db.close()
