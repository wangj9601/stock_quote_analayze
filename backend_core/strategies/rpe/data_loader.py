"""RPE 数据加载：行业成分股 + 日线。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import bindparam, text

logger = logging.getLogger(__name__)


def _norm_code(code: str) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s


class RPEDataLoader:
    def __init__(self, db_session=None):
        self._db = db_session

    def _session(self):
        if self._db is not None:
            return self._db
        from backend_api.database import SessionLocal

        return SessionLocal()

    def resolve_trade_date(self) -> str:
        db = self._session()
        own = self._db is None
        try:
            from backend_api.models import HistoricalQuotes
            from sqlalchemy import func

            latest = db.query(func.max(HistoricalQuotes.date)).scalar()
            if latest:
                return latest.strftime("%Y-%m-%d") if hasattr(latest, "strftime") else str(latest)[:10]
        except Exception as e:
            logger.warning("resolve_trade_date failed: %s", e)
        finally:
            if own:
                db.close()
        return datetime.now().strftime("%Y-%m-%d")

    def list_industry_boards(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        db = self._session()
        own = self._db is None
        try:
            sql = text(
                """
                SELECT board_code, board_name
                FROM industry_board_basic_info
                ORDER BY board_code
                """
            )
            rows = db.execute(sql).fetchall()
            out = [{"board_code": str(r[0]), "board_name": str(r[1] or r[0])} for r in rows]
            if limit:
                out = out[: int(limit)]
            return out
        except Exception as e:
            logger.warning("list_industry_boards failed: %s", e)
            return []
        finally:
            if own:
                db.close()

    def list_concept_boards(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        db = self._session()
        own = self._db is None
        try:
            sql = text(
                """
                SELECT board_code, board_name
                FROM concept_board_basic_info
                WHERE board_code IS NOT NULL AND TRIM(board_code) <> ''
                ORDER BY board_code
                """
            )
            rows = db.execute(sql).fetchall()
            out = [{"board_code": str(r[0]), "board_name": str(r[1] or r[0])} for r in rows]
            if limit:
                out = out[: int(limit)]
            return out
        except Exception as e:
            logger.warning("list_concept_boards failed: %s", e)
            return []
        finally:
            if own:
                db.close()

    def list_boards(self, board_kind: str = "industry", limit: Optional[int] = None) -> List[Dict[str, str]]:
        if board_kind == "concept":
            return self.list_concept_boards(limit=limit)
        return self.list_industry_boards(limit=limit)

    def load_board_members(self, board_code: str, board_kind: str = "industry") -> List[Dict[str, str]]:
        db = self._session()
        own = self._db is None
        table = (
            "concept_board_constituents"
            if board_kind == "concept"
            else "industry_board_constituents"
        )
        try:
            sql = text(
                f"""
                SELECT stock_code, stock_name
                FROM {table}
                WHERE board_code = :bc
                """
            )
            rows = db.execute(sql, {"bc": board_code}).fetchall()
            return [
                {"code": _norm_code(r[0]), "name": str(r[1] or "")}
                for r in rows
                if r[0]
            ]
        except Exception as e:
            logger.warning("load_board_members %s (%s) failed: %s", board_code, board_kind, e)
            return []
        finally:
            if own:
                db.close()

    def _code_variants(self, code: str) -> List[str]:
        code_n = _norm_code(code)
        raw = str(code or "").strip()
        stripped = code_n.lstrip("0") or code_n
        return list(dict.fromkeys([v for v in (code_n, raw, stripped) if v]))

    def find_boards_for_code(self, code: str, board_kind: str = "industry") -> List[Dict[str, str]]:
        db = self._session()
        own = self._db is None
        try:
            variants = self._code_variants(code)
            if board_kind == "concept":
                sql = text(
                    """
                    SELECT c.board_code, COALESCE(b.board_name, c.board_code)
                    FROM concept_board_constituents c
                    LEFT JOIN concept_board_basic_info b ON b.board_code = c.board_code
                    WHERE c.stock_code IN :codes
                    ORDER BY c.board_code
                    """
                ).bindparams(bindparam("codes", expanding=True))
            else:
                sql = text(
                    """
                    SELECT c.board_code, COALESCE(b.board_name, c.board_code)
                    FROM industry_board_constituents c
                    LEFT JOIN industry_board_basic_info b ON b.board_code = c.board_code
                    WHERE c.stock_code IN :codes
                    ORDER BY c.board_code
                    """
                ).bindparams(bindparam("codes", expanding=True))
            rows = db.execute(sql, {"codes": variants}).fetchall()
            return [{"board_code": str(r[0]), "board_name": str(r[1] or r[0])} for r in rows]
        except Exception as e:
            logger.warning("find_boards_for_code failed: %s", e)
            return []
        finally:
            if own:
                db.close()

    def resolve_primary_board(
        self,
        code: str,
        board_kind: str = "industry",
        *,
        allow_fallback: bool = True,
    ) -> Optional[Dict[str, str]]:
        """
        固定个股主板块（用于选股/追溯，避免同股多板块按日跳变）。

        规则：
        1. 优先指定 kind（默认 industry）；无归属且 allow_fallback 时回退 concept
        2. 同 kind 多板块时取成分股数量最多者
        3. 成分数并列时按 board_code 升序，保证稳定可复现
        """
        kind = "concept" if board_kind == "concept" else "industry"
        picked = self._pick_primary_board_among(code, kind)
        if picked is None and allow_fallback and kind == "industry":
            picked = self._pick_primary_board_among(code, "concept")
        return picked

    def _pick_primary_board_among(self, code: str, board_kind: str) -> Optional[Dict[str, str]]:
        db = self._session()
        own = self._db is None
        try:
            variants = self._code_variants(code)
            if board_kind == "concept":
                sql = text(
                    """
                    SELECT c.board_code,
                           COALESCE(b.board_name, c.board_code) AS board_name,
                           cnt.n AS member_count
                    FROM concept_board_constituents c
                    JOIN (
                        SELECT board_code, COUNT(*) AS n
                        FROM concept_board_constituents
                        GROUP BY board_code
                    ) cnt ON cnt.board_code = c.board_code
                    LEFT JOIN concept_board_basic_info b ON b.board_code = c.board_code
                    WHERE c.stock_code IN :codes
                    ORDER BY cnt.n DESC, c.board_code ASC
                    LIMIT 1
                    """
                ).bindparams(bindparam("codes", expanding=True))
            else:
                sql = text(
                    """
                    SELECT c.board_code,
                           COALESCE(b.board_name, c.board_code) AS board_name,
                           cnt.n AS member_count
                    FROM industry_board_constituents c
                    JOIN (
                        SELECT board_code, COUNT(*) AS n
                        FROM industry_board_constituents
                        GROUP BY board_code
                    ) cnt ON cnt.board_code = c.board_code
                    LEFT JOIN industry_board_basic_info b ON b.board_code = c.board_code
                    WHERE c.stock_code IN :codes
                    ORDER BY cnt.n DESC, c.board_code ASC
                    LIMIT 1
                    """
                ).bindparams(bindparam("codes", expanding=True))
            row = db.execute(sql, {"codes": variants}).fetchone()
            if not row:
                return None
            return {
                "board_code": str(row[0]),
                "board_name": str(row[1] or row[0]),
                "board_kind": "concept" if board_kind == "concept" else "industry",
                "member_count": int(row[2] or 0),
            }
        except Exception as e:
            logger.warning("resolve_primary_board failed: %s", e)
            return None
        finally:
            if own:
                db.close()

    def load_bars(
        self,
        code: str,
        *,
        end_date: Optional[str] = None,
        limit: Optional[int] = 250,
        adjust: str = "none",
        factor_source: str = "auto",
        refresh_factor: bool = False,
    ) -> List[Dict[str, Any]]:
        db = self._session()
        own = self._db is None
        try:
            code_n = _norm_code(code)
            params: Dict[str, Any] = {"code": code_n}
            lim_sql = ""
            if limit is not None and int(limit) > 0:
                params["lim"] = int(limit)
                lim_sql = " LIMIT :lim"
            if end_date:
                params["d"] = end_date
                sql = text(
                    f"""
                    SELECT date, open, high, low, close, volume, amount, turnover_rate
                    FROM historical_quotes
                    WHERE code = :code AND date <= :d
                    ORDER BY date DESC
                    {lim_sql}
                    """
                )
            else:
                sql = text(
                    f"""
                    SELECT date, open, high, low, close, volume, amount, turnover_rate
                    FROM historical_quotes
                    WHERE code = :code
                    ORDER BY date DESC
                    {lim_sql}
                    """
                )
            rows = db.execute(sql, params).fetchall()
            bars = []
            for r in reversed(rows):
                d = r[0]
                ds = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
                bars.append(
                    {
                        "date": ds,
                        "open": float(r[1] or 0),
                        "high": float(r[2] or 0),
                        "low": float(r[3] or 0),
                        "close": float(r[4] or 0),
                        "volume": float(r[5] or 0),
                        "amount": float(r[6] or 0) if r[6] is not None else None,
                        "turnover_rate": float(r[7]) if r[7] is not None else None,
                    }
                )
            adjust_n = str(adjust or "none").strip().lower() or "none"
            if adjust_n == "qfq" and bars:
                bars = self._apply_qfq_bars(
                    db,
                    code_n,
                    bars,
                    factor_source=factor_source,
                    refresh_factor=refresh_factor,
                )
            return bars
        except Exception as e:
            logger.warning("load_bars %s failed: %s", code, e)
            return []
        finally:
            if own:
                db.close()

    def _apply_qfq_bars(
        self,
        db,
        code: str,
        bars: List[Dict[str, Any]],
        *,
        factor_source: str = "auto",
        refresh_factor: bool = False,
    ) -> List[Dict[str, Any]]:
        """对已加载的不复权 bars 现算前复权；失败返回空列表（从 panel 中剔除，避免混口径）。"""
        try:
            from backend_api.utils.adj_quotes import (
                AdjQuotesError,
                apply_qfq_to_bars,
                ensure_adj_factors,
            )
        except ImportError:
            from utils.adj_quotes import (  # type: ignore
                AdjQuotesError,
                apply_qfq_to_bars,
                ensure_adj_factors,
            )
        try:
            ensured = ensure_adj_factors(
                db,
                code,
                force_refresh=bool(refresh_factor),
                factor_source=factor_source or "auto",
            )
            return apply_qfq_to_bars(bars, ensured["factors"])
        except AdjQuotesError as e:
            logger.warning("RPE qfq bars skip %s: %s", code, e)
            return []
        except Exception as e:
            logger.warning("RPE qfq bars failed %s: %s", code, e)
            return []

    def load_sector_panel(
        self,
        member_codes: List[str],
        *,
        end_date: Optional[str] = None,
        lookback: Optional[int] = 250,
        adjust: str = "none",
        factor_source: str = "auto",
        refresh_factor: bool = False,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """批量加载成分股 bars（逐只；lookback=None 表示拉全历史）。

        adjust=qfq 时对 OHLC 现算前复权（成交额/换手不变），保证板块基准与个股同口径。
        """
        out: Dict[str, List[Dict[str, Any]]] = {}
        for code in member_codes:
            bars = self.load_bars(
                code,
                end_date=end_date,
                limit=lookback,
                adjust=adjust,
                factor_source=factor_source,
                refresh_factor=refresh_factor,
            )
            if bars:
                out[_norm_code(code)] = bars
        return out

    def build_date_members(
        self, panel: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[Tuple[float, float]]]:
        """{date: [(close, volume), ...]}"""
        date_map: Dict[str, List[Tuple[float, float]]] = {}
        for bars in panel.values():
            for b in bars:
                d = b["date"]
                date_map.setdefault(d, []).append((b["close"], b["volume"]))
        return date_map
