"""大盘环境、板环境与个股 enrichment。"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from backend_core.recommend.config import (
    BOARD_SLOPE_VETO_5,
    BOARD_SLOPE_VETO_10,
    MARKET_INDEX_CODE,
)

logger = logging.getLogger(__name__)


def resolve_asof_date(db: Session, asof_date: Optional[str] = None) -> str:
    """解析 asof：显式日期，否则取 A 股历史行情最新日。"""
    if asof_date:
        return str(asof_date).strip()[:10]
    try:
        row = db.execute(
            text("SELECT MAX(date) FROM historical_quotes WHERE date IS NOT NULL")
        ).fetchone()
        if row and row[0]:
            v = row[0]
            if hasattr(v, "isoformat"):
                return v.isoformat()[:10]
            return str(v)[:10]
    except Exception as e:
        logger.warning("resolve_asof_date from historical_quotes failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
    return date.today().isoformat()


def evaluate_market_stance(db: Session, asof_date: str) -> Dict[str, Any]:
    """轻量大盘立场：指数收盘相对 MA20。

    bull / neutral / bear
    """
    code = MARKET_INDEX_CODE
    try:
        # 优先 index_historical_quotes（CAN SLIM），否则 historical_quotes
        rows = db.execute(
            text(
                """
                SELECT trade_date::text, close
                FROM index_historical_quotes
                WHERE (code = :code OR ts_code LIKE :like_code)
                  AND trade_date <= CAST(:asof AS date)
                ORDER BY trade_date DESC
                LIMIT 30
                """
            ),
            {"code": code, "like_code": f"{code}%", "asof": asof_date},
        ).fetchall()
        if not rows:
            rows = db.execute(
                text(
                    """
                    SELECT date::text, close
                    FROM historical_quotes
                    WHERE code = :code AND date <= :asof
                    ORDER BY date DESC
                    LIMIT 30
                    """
                ),
                {"code": code, "asof": asof_date},
            ).fetchall()
    except Exception as e:
        logger.debug("evaluate_market_stance query failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return {
            "stance": "neutral",
            "index_code": code,
            "reason": f"query_failed:{e}",
            "close": None,
            "ma20": None,
        }

    closes: List[float] = []
    for r in rows:
        try:
            closes.append(float(r[1]))
        except (TypeError, ValueError):
            continue
    if len(closes) < 5:
        return {
            "stance": "neutral",
            "index_code": code,
            "reason": "insufficient_bars",
            "close": closes[0] if closes else None,
            "ma20": None,
        }
    closes_asc = list(reversed(closes))
    window = closes_asc[-20:] if len(closes_asc) >= 20 else closes_asc
    ma20 = sum(window) / len(window)
    last = closes_asc[-1]
    prev = closes_asc[-5] if len(closes_asc) >= 5 else closes_asc[0]
    slope_up = last >= prev
    if last >= ma20 and slope_up:
        stance = "bull"
        reason = "above_ma20_rising"
    elif last < ma20 and not slope_up:
        stance = "bear"
        reason = "below_ma20_falling"
    else:
        stance = "neutral"
        reason = "mixed"
    return {
        "stance": stance,
        "index_code": code,
        "reason": reason,
        "close": round(last, 4),
        "ma20": round(ma20, 4),
    }


def map_stocks_to_industry_boards(
    db: Session, codes: Sequence[str]
) -> Dict[str, Dict[str, Any]]:
    """兼容旧名：同花顺行业映射。"""
    return map_stocks_to_ths_industry(db, codes)


def map_stocks_to_ths_industry(
    db: Session, codes: Sequence[str]
) -> Dict[str, Dict[str, Any]]:
    """code -> {board_code, board_name, industry, board_kind}，行业以同花顺为准。

    优先 ``industry_board_constituents`` × ``industry_board_basic_info``
    （board_code_source=tonghuashun）；否则回退 ``stock_basic_info.industry``。
    """
    norm = []
    for c in codes:
        s = str(c or "").strip()
        if s.isdigit() and len(s) < 6:
            s = s.zfill(6)
        if s:
            norm.append(s)
    if not norm:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    try:
        from backend_api.utils.board_code_source import (
            DEFAULT_BOARD_CODE_SOURCE,
            LEGACY_DEFAULT_BOARD_CODE_SOURCE,
            resolve_board_code_source,
        )
        from backend_api.utils.industry_board_query import (
            batch_industry_board_names_by_stock_codes,
        )

        src = resolve_board_code_source(
            DEFAULT_BOARD_CODE_SOURCE, fallback=DEFAULT_BOARD_CODE_SOURCE
        )
        # 名称（可能多板逗号分隔）
        name_map = batch_industry_board_names_by_stock_codes(
            db, list(set(norm)), board_code_source=src
        ) or {}

        # 取每个股票的首个同花顺行业板代码（用于分散/角色）
        rows = db.execute(
            text(
                """
                SELECT DISTINCT ON (c.stock_code)
                       c.stock_code, c.board_code, b.board_name
                FROM industry_board_constituents c
                INNER JOIN industry_board_basic_info b ON b.board_code = c.board_code
                WHERE c.stock_code IN :codes
                  AND COALESCE(NULLIF(TRIM(b.board_code_source), ''), :legacy) = :source
                ORDER BY c.stock_code, b.board_name NULLS LAST, c.board_code
                """
            ).bindparams(bindparam("codes", expanding=True)),
            {
                "codes": list(set(norm)),
                "source": src,
                "legacy": LEGACY_DEFAULT_BOARD_CODE_SOURCE,
            },
        ).fetchall()
        for r in rows:
            code = str(r[0]).strip()
            board_code = str(r[1]).strip() if r[1] else None
            board_name = str(r[2]).strip() if r[2] else None
            display = (name_map.get(code) or board_name or "").split(",")[0].strip()
            out[code] = {
                "board_code": board_code,
                "board_name": display or board_name,
                "industry": display or board_name,
                "board_kind": "industry",
                "board_code_source": "tonghuashun",
            }
    except Exception as e:
        logger.warning("map_stocks_to_ths_industry failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass

    # 补 stock_basic_info 名称与行业回退
    try:
        from backend_api.models import StockBasicInfo

        missing = [c for c in set(norm) if c not in out]
        q_codes = list(set(norm))
        basic_rows = (
            db.query(StockBasicInfo.code, StockBasicInfo.name, StockBasicInfo.industry)
            .filter(StockBasicInfo.code.in_(q_codes))
            .all()
        )
        for row in basic_rows:
            code = str(row.code).strip()
            name = str(row.name or "").strip() or None
            ind = str(row.industry or "").strip()
            if ind in ("", "-", "--", "None", "null"):
                ind = ""
            bucket = out.setdefault(
                code,
                {
                    "board_code": None,
                    "board_name": ind or None,
                    "industry": ind or None,
                    "board_kind": "industry",
                    "board_code_source": "stock_basic_info" if ind else None,
                },
            )
            if name:
                bucket["stock_name"] = name
            if ind and not bucket.get("industry"):
                bucket["industry"] = ind
                bucket["board_name"] = ind
                bucket["board_code_source"] = bucket.get("board_code_source") or "stock_basic_info"
            elif name and "stock_name" not in bucket:
                bucket["stock_name"] = name
    except Exception as e:
        logger.debug("stock_basic enrich failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
    return out


def load_stock_names(
    db: Session, codes: Sequence[str]
) -> Dict[str, str]:
    """批量股票名称。"""
    norm = []
    for c in codes:
        s = str(c or "").strip()
        if s.isdigit() and len(s) < 6:
            s = s.zfill(6)
        if s:
            norm.append(s)
    if not norm:
        return {}
    try:
        from backend_api.models import StockBasicInfo

        rows = (
            db.query(StockBasicInfo.code, StockBasicInfo.name)
            .filter(StockBasicInfo.code.in_(list(set(norm))))
            .all()
        )
        return {
            str(r.code).strip(): str(r.name).strip()
            for r in rows
            if r.name
        }
    except Exception as e:
        logger.debug("load_stock_names failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return {}


def load_board_env_bundle(
    db: Session, board_codes: Sequence[str], asof_date: str
) -> Dict[str, Dict[str, Any]]:
    """板短窗斜率 + 资金流摘要。"""
    from backend_core.board_metrics.sector_slope_store import load_board_sector_slopes_multi

    codes = [str(c).strip() for c in board_codes if c]
    if not codes:
        return {}
    multi = load_board_sector_slopes_multi(
        db, codes, board_kind="industry", asof_date=asof_date, windows=(5, 10, 20, 60, 120)
    )
    fund: Dict[str, Any] = {}
    try:
        rows = db.execute(
            text(
                """
                SELECT DISTINCT ON (board_code)
                       board_code, main_net_inflow, trade_date
                FROM board_fund_flow_daily
                WHERE board_code IN :codes
                  AND trade_date <= CAST(:asof AS date)
                ORDER BY board_code, trade_date DESC
                """
            ).bindparams(bindparam("codes", expanding=True)),
            {"codes": codes, "asof": asof_date},
        ).fetchall()
        for r in rows:
            fund[str(r[0])] = {
                "main_net_inflow": float(r[1]) if r[1] is not None else None,
                "trade_date": str(r[2])[:10] if r[2] is not None else None,
            }
    except Exception as e:
        logger.debug("board fund flow load failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass

    out: Dict[str, Dict[str, Any]] = {}
    for bc in codes:
        slopes = {
            w: (multi.get(w) or {}).get(bc)
            for w in (5, 10, 20, 60, 120)
        }
        s5 = (slopes.get(5) or {}).get("sector_slope")
        s10 = (slopes.get(10) or {}).get("sector_slope")
        veto = False
        try:
            if s5 is not None and float(s5) <= BOARD_SLOPE_VETO_5:
                veto = True
            if s10 is not None and float(s10) <= BOARD_SLOPE_VETO_10:
                veto = True
        except (TypeError, ValueError):
            pass
        out[bc] = {
            "slopes": {
                str(w): slopes[w]
                for w in (5, 10, 20, 60, 120)
                if slopes.get(w)
            },
            "fund_flow": fund.get(bc),
            "board_weak": veto,
        }
    return out


def load_quotes_snapshot(
    db: Session, codes: Sequence[str], asof_date: str
) -> Dict[str, Dict[str, Any]]:
    """收盘价、涨跌幅、近 N 日涨幅。"""
    from backend_core.recommend.config import ANTI_CHASE_LOOKBACK_DAYS
    from backend_core.board_roles.classify import limit_up_threshold_for_code

    norm = []
    for c in codes:
        s = str(c or "").strip()
        if s.isdigit() and len(s) < 6:
            s = s.zfill(6)
        if s:
            norm.append(s)
    if not norm:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    try:
        rows = db.execute(
            text(
                """
                SELECT code, date::text, open, high, low, close, change_percent
                FROM historical_quotes
                WHERE code IN :codes AND date <= :asof
                ORDER BY code, date DESC
                """
            ).bindparams(bindparam("codes", expanding=True)),
            {"codes": list(set(norm)), "asof": asof_date},
        ).fetchall()
    except Exception as e:
        logger.warning("load_quotes_snapshot failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return {}

    by_code: Dict[str, List[Any]] = {}
    for r in rows:
        code = str(r[0]).strip()
        by_code.setdefault(code, []).append(r)

    lookback = max(2, ANTI_CHASE_LOOKBACK_DAYS)
    for code, hist in by_code.items():
        latest = hist[0]
        close = float(latest[5]) if latest[5] is not None else None
        try:
            pct_f = float(latest[6]) if latest[6] is not None else None
        except (TypeError, ValueError):
            pct_f = None
        n_day_gain = None
        if close is not None and len(hist) > lookback:
            try:
                base = float(hist[lookback][5])
                if base and base > 0:
                    n_day_gain = (close / base - 1.0) * 100.0
            except (TypeError, ValueError):
                pass
        limit_th = limit_up_threshold_for_code(code)
        is_limit_up = bool(pct_f is not None and pct_f >= limit_th - 0.05)
        out[code] = {
            "close": close,
            "pct_chg": pct_f,
            "n_day_gain_pct": n_day_gain,
            "is_limit_up": is_limit_up,
            "limit_up_threshold": limit_th,
            "date": str(latest[1])[:10] if latest[1] else asof_date,
        }
    return out


def is_week_last_trading_day(db: Session, asof: str) -> bool:
    """asof 是否为本周最后一个交易日（下一自然日直至周日均休市）。"""
    try:
        d0 = date.fromisoformat(asof[:10])
    except ValueError:
        return False
    from backend_api.utils.trading_calendar_utils import is_market_session_closed

    # 若下周还有同周交易日则否
    for i in range(1, 8):
        nxt = d0 + timedelta(days=i)
        if nxt.weekday() == 0 and i > 1:
            # 已跨到下周一之后的检查在下面
            pass
        if nxt.weekday() <= 4 and not is_market_session_closed(db, "CN", nxt):
            # 仍在同一日历周？
            if nxt.isocalendar()[1] == d0.isocalendar()[1] and nxt.year == d0.year:
                return False
            break
    # 本周内 asof 之后无交易日
    week = d0.isocalendar()[1]
    year = d0.year
    for i in range(1, 8 - d0.weekday()):
        nxt = d0 + timedelta(days=i)
        if nxt.isocalendar()[1] != week or nxt.year != year:
            break
        if not is_market_session_closed(db, "CN", nxt):
            return False
    return True


def is_month_last_trading_day(db: Session, asof: str) -> bool:
    try:
        d0 = date.fromisoformat(asof[:10])
    except ValueError:
        return False
    from backend_api.utils.trading_calendar_utils import is_market_session_closed

    # 查到月末
    if d0.month == 12:
        end = date(d0.year, 12, 31)
    else:
        end = date(d0.year, d0.month + 1, 1) - timedelta(days=1)
    cur = d0 + timedelta(days=1)
    while cur <= end:
        if not is_market_session_closed(db, "CN", cur):
            return False
        cur += timedelta(days=1)
    return True
