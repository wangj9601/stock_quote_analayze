"""RPE 数据加载：行业成分股 + 日线。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

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

    def find_boards_for_code(self, code: str, board_kind: str = "industry") -> List[Dict[str, str]]:
        db = self._session()
        own = self._db is None
        try:
            code_n = _norm_code(code)
            if board_kind == "concept":
                sql = text(
                    """
                    SELECT c.board_code, COALESCE(b.board_name, c.board_code)
                    FROM concept_board_constituents c
                    LEFT JOIN concept_board_basic_info b ON b.board_code = c.board_code
                    WHERE c.stock_code = :code OR c.stock_code = :code2
                    """
                )
            else:
                sql = text(
                    """
                    SELECT c.board_code, COALESCE(b.board_name, c.board_code)
                    FROM industry_board_constituents c
                    LEFT JOIN industry_board_basic_info b ON b.board_code = c.board_code
                    WHERE c.stock_code = :code OR c.stock_code = :code2
                    """
                )
            rows = db.execute(sql, {"code": code_n, "code2": code}).fetchall()
            return [{"board_code": str(r[0]), "board_name": str(r[1] or r[0])} for r in rows]
        except Exception as e:
            logger.warning("find_boards_for_code failed: %s", e)
            return []
        finally:
            if own:
                db.close()

    def load_bars(
        self,
        code: str,
        *,
        end_date: Optional[str] = None,
        limit: int = 250,
    ) -> List[Dict[str, Any]]:
        db = self._session()
        own = self._db is None
        try:
            code_n = _norm_code(code)
            params: Dict[str, Any] = {"code": code_n, "lim": int(limit)}
            if end_date:
                sql = text(
                    """
                    SELECT date, open, high, low, close, volume, amount, turnover_rate
                    FROM historical_quotes
                    WHERE code = :code AND date <= :d
                    ORDER BY date DESC
                    LIMIT :lim
                    """
                )
                params["d"] = end_date
            else:
                sql = text(
                    """
                    SELECT date, open, high, low, close, volume, amount, turnover_rate
                    FROM historical_quotes
                    WHERE code = :code
                    ORDER BY date DESC
                    LIMIT :lim
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
            return bars
        except Exception as e:
            logger.warning("load_bars %s failed: %s", code, e)
            return []
        finally:
            if own:
                db.close()

    def load_sector_panel(
        self,
        member_codes: List[str],
        *,
        end_date: Optional[str] = None,
        lookback: int = 250,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """批量加载成分股 bars（逐只，简单实现；后续可优化 SQL）。"""
        out: Dict[str, List[Dict[str, Any]]] = {}
        for code in member_codes:
            bars = self.load_bars(code, end_date=end_date, limit=lookback)
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
