# -*- coding: utf-8 -*-
"""CAN SLIM 数据加载（只读库表，不打外网）。"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _norm_code(code: str) -> str:
    s = str(code).strip()
    if s.isdigit() and len(s) < 6:
        return s.zfill(6)
    return s


def _to_date_str(d: Any) -> Optional[str]:
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%d")
    if isinstance(d, date):
        return d.isoformat()
    s = str(d).strip()
    if len(s) >= 10:
        return s[:10]
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s or None


class CanSlimDataLoader:
    def __init__(self, db: Session):
        self.db = db

    def resolve_asof_date(self, asof: Optional[str] = None) -> str:
        if asof:
            return str(asof).strip()[:10]
        row = self.db.execute(
            text("SELECT MAX(date)::text FROM historical_quotes WHERE length(code) = 6")
        ).fetchone()
        if row and row[0]:
            return str(row[0])[:10]
        return datetime.now().strftime("%Y-%m-%d")

    def list_universe(self, exclude_st: bool = True) -> List[Dict[str, Any]]:
        sql = """
            SELECT code, name, free_float_shares, total_shares
            FROM stock_basic_info
            WHERE COALESCE(collect_enabled, TRUE) = TRUE
              AND length(code) = 6
        """
        if exclude_st:
            sql += " AND name IS NOT NULL AND name NOT ILIKE '%ST%' AND name NOT LIKE '%退%'"
        sql += " ORDER BY code"
        rows = self.db.execute(text(sql)).fetchall()
        return [
            {
                "code": _norm_code(r[0]),
                "name": r[1],
                "free_float_shares": float(r[2]) if r[2] is not None else None,
                "total_shares": float(r[3]) if r[3] is not None else None,
            }
            for r in rows
            if r and r[0]
        ]

    def load_latest_fina_by_codes(
        self, codes: Sequence[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """每只股票按 end_date 降序的全部财务行（调用方取最新季/年）。"""
        if not codes:
            return {}
        out: Dict[str, List[Dict[str, Any]]] = {c: [] for c in codes}
        # 分批 IN
        chunk = 500
        for i in range(0, len(codes), chunk):
            part = list(codes[i : i + chunk])
            placeholders = ",".join([f":c{j}" for j in range(len(part))])
            params = {f"c{j}": part[j] for j in range(len(part))}
            rows = self.db.execute(
                text(
                    f"""
                    SELECT code, end_date, ann_date, eps, q_eps,
                           basic_eps_yoy, dt_eps_yoy, q_eps_yoy,
                           q_profit_yoy, q_netprofit_yoy, q_sales_yoy,
                           roe, roe_waa
                    FROM stock_fina_indicator
                    WHERE code IN ({placeholders})
                    ORDER BY code, end_date DESC
                    """
                ),
                params,
            ).fetchall()
            for r in rows:
                code = _norm_code(r[0])
                out.setdefault(code, []).append(
                    {
                        "end_date": str(r[1] or ""),
                        "ann_date": str(r[2] or "") if r[2] else None,
                        "eps": float(r[3]) if r[3] is not None else None,
                        "q_eps": float(r[4]) if r[4] is not None else None,
                        "basic_eps_yoy": float(r[5]) if r[5] is not None else None,
                        "dt_eps_yoy": float(r[6]) if r[6] is not None else None,
                        "q_eps_yoy": float(r[7]) if r[7] is not None else None,
                        "q_profit_yoy": float(r[8]) if r[8] is not None else None,
                        "q_netprofit_yoy": float(r[9]) if r[9] is not None else None,
                        "q_sales_yoy": float(r[10]) if r[10] is not None else None,
                        "roe": float(r[11]) if r[11] is not None else None,
                        "roe_waa": float(r[12]) if r[12] is not None else None,
                    }
                )
        return out

    def load_rs_map(self, asof: str) -> Dict[str, Dict[str, Any]]:
        """取 asof 当日或之前最近一日有评级的 RS。"""
        row = self.db.execute(
            text(
                """
                SELECT MAX(date) FROM rs_ratings
                WHERE market_type = 'CN' AND date <= :asof AND rs_rating IS NOT NULL
                """
            ),
            {"asof": asof},
        ).fetchone()
        if not row or not row[0]:
            return {}
        d = str(row[0])[:10]
        rows = self.db.execute(
            text(
                """
                SELECT code, rs_rating, rs_raw
                FROM rs_ratings
                WHERE market_type = 'CN' AND date = :d AND rs_rating IS NOT NULL
                """
            ),
            {"d": d},
        ).fetchall()
        return {
            _norm_code(r[0]): {"rs_rating": int(r[1]), "rs_raw": float(r[2]) if r[2] is not None else None, "date": d}
            for r in rows
            if r[0] is not None and r[1] is not None
        }

    def load_cupb_codes(self, asof: str, statuses: Sequence[str]) -> Dict[str, Dict[str, Any]]:
        if not statuses:
            return {}
        status_list = [str(s).strip().lower() for s in statuses]
        placeholders = ",".join([f":s{i}" for i in range(len(status_list))])
        params: Dict[str, Any] = {f"s{i}": status_list[i] for i in range(len(status_list))}
        params["asof"] = asof
        # 取 asof 当日（或之前最近）每个 code 最新一条
        rows = self.db.execute(
            text(
                f"""
                SELECT DISTINCT ON (code)
                    code, status, trade_date::text, last_close, rim
                FROM cupb_signal_trace
                WHERE trade_date <= CAST(:asof AS DATE)
                  AND lower(status) IN ({placeholders})
                ORDER BY code, trade_date DESC, updated_at DESC
                """
            ),
            params,
        ).fetchall()
        return {
            _norm_code(r[0]): {
                "status": str(r[1] or ""),
                "trade_date": _to_date_str(r[2]),
                "last_close": float(r[3]) if r[3] is not None else None,
                "rim": float(r[4]) if r[4] is not None else None,
            }
            for r in rows
            if r and r[0]
        }

    def load_mavol_map(self, asof: str, codes: Sequence[str]) -> Dict[str, Dict[str, Any]]:
        if not codes:
            return {}
        out: Dict[str, Dict[str, Any]] = {}
        chunk = 500
        for i in range(0, len(codes), chunk):
            part = list(codes[i : i + chunk])
            placeholders = ",".join([f":c{j}" for j in range(len(part))])
            params = {f"c{j}": part[j] for j in range(len(part))}
            params["asof"] = asof
            rows = self.db.execute(
                text(
                    f"""
                    SELECT DISTINCT ON (code)
                        code, date, mavol20, mavol60
                    FROM mavol_indicators
                    WHERE market_type IN ('CN', 'A股')
                      AND date <= :asof
                      AND code IN ({placeholders})
                    ORDER BY code, date DESC
                    """
                ),
                params,
            ).fetchall()
            for r in rows:
                out[_norm_code(r[0])] = {
                    "date": _to_date_str(r[1]),
                    "mavol20": float(r[2]) if r[2] is not None else None,
                    "mavol60": float(r[3]) if r[3] is not None else None,
                }
        return out

    def load_quote_window(
        self, code: str, asof: str, bars: int
    ) -> List[Dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT date::text, open, high, low, close, volume
                FROM historical_quotes
                WHERE code = :code AND date::text <= :asof
                ORDER BY date DESC
                LIMIT :lim
                """
            ),
            {"code": code, "asof": asof, "lim": int(bars) + 5},
        ).fetchall()
        bars_out = [
            {
                "date": _to_date_str(r[0]),
                "open": float(r[1]) if r[1] is not None else None,
                "high": float(r[2]) if r[2] is not None else None,
                "low": float(r[3]) if r[3] is not None else None,
                "close": float(r[4]) if r[4] is not None else None,
                "volume": float(r[5]) if r[5] is not None else None,
            }
            for r in rows
        ]
        bars_out.reverse()  # 升序
        return bars_out

    def load_adj_factors(self, code: str) -> List[Tuple[str, float]]:
        """优先 sina qfq 因子。"""
        rows = self.db.execute(
            text(
                """
                SELECT trade_date::text, adj_factor, source
                FROM stock_adj_factor
                WHERE code = :code
                  AND source IN ('akshare_sina_qfq', 'baostock_qfq')
                ORDER BY trade_date
                """
            ),
            {"code": code},
        ).fetchall()
        if not rows:
            return []
        # 单源：优先 sina
        sina = [(str(r[0])[:10], float(r[1])) for r in rows if r[2] == "akshare_sina_qfq" and r[1] is not None]
        if sina:
            return sina
        return [(str(r[0])[:10], float(r[1])) for r in rows if r[2] == "baostock_qfq" and r[1] is not None]

    def load_index_closes(self, ts_code: str, asof: str, limit: int = 80) -> List[Dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT trade_date::text, close
                FROM index_historical_quotes
                WHERE ts_code = :ts AND trade_date <= CAST(:asof AS DATE)
                ORDER BY trade_date DESC
                LIMIT :lim
                """
            ),
            {"ts": ts_code, "asof": asof, "lim": int(limit)},
        ).fetchall()
        out = [
            {"date": _to_date_str(r[0]), "close": float(r[1]) if r[1] is not None else None}
            for r in rows
        ]
        out.reverse()
        return out
