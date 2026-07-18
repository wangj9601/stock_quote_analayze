"""SBBR 数据加载：股本、日线、大盘收益。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

logger = logging.getLogger(__name__)


def _norm_code(code: str) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s


class SBBRDataLoader:
    def __init__(self, db_session=None):
        self._db = db_session

    def _session(self):
        if self._db is not None:
            return self._db
        from backend_api.database import SessionLocal

        return SessionLocal()

    def load_share_map(
        self,
        codes: Optional[List[str]] = None,
        as_of_date: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        db = self._session()
        own = self._db is None
        try:
            from backend_api.models import StockBasicInfo

            q = db.query(
                StockBasicInfo.code,
                StockBasicInfo.name,
                StockBasicInfo.total_shares,
                StockBasicInfo.free_float_shares,
                StockBasicInfo.industry,
            )
            if codes:
                codes_n = [_norm_code(c) for c in codes]
                q = q.filter(StockBasicInfo.code.in_(codes_n))
            out: Dict[str, Dict[str, Any]] = {}
            for r in q.all():
                out[_norm_code(r.code)] = {
                    "code": _norm_code(r.code),
                    "name": r.name,
                    "total_shares": r.total_shares,
                    "free_float_shares": r.free_float_shares,
                    "industry": r.industry,
                    "shares_source": "basic_info",
                }

            # stock_basic_info.free_float_shares 多为 IPO 初始流通盘，随解禁会失真；
            # 优先用行情表权威市值反推股本（总市值/现价、流通市值/现价）。
            rt = self.load_shares_from_realtime(
                list(out.keys()) or (codes or None), as_of_date=as_of_date
            )
            for code_n, rec in rt.items():
                info = out.setdefault(
                    code_n,
                    {
                        "code": code_n,
                        "name": None,
                        "total_shares": None,
                        "free_float_shares": None,
                        "industry": None,
                        "shares_source": "basic_info",
                    },
                )
                if rec.get("total_shares"):
                    info["total_shares"] = rec["total_shares"]
                if rec.get("free_float_shares"):
                    info["free_float_shares"] = rec["free_float_shares"]
                info["shares_source"] = "realtime_mv"
            return out
        finally:
            if own:
                db.close()

    def load_shares_from_realtime(
        self,
        codes: Optional[List[str]] = None,
        as_of_date: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """从 stock_realtime_quote 用权威市值反推股本（股）。

        total_shares = 总市值 / 现价；free_float_shares = 流通市值 / 现价。
        取每只 <= as_of_date 且市值/现价有效的最新一行。
        """
        db = self._session()
        own = self._db is None
        try:
            params: Dict[str, Any] = {}
            filters = [
                "current_price IS NOT NULL",
                "current_price > 0",
                "(total_market_value IS NOT NULL OR circulating_market_value IS NOT NULL)",
            ]
            if codes:
                params["codes"] = [_norm_code(c) for c in codes]
                filters.append("code = ANY(:codes)")
            if as_of_date:
                params["d"] = as_of_date
                filters.append("trade_date <= :d")
            where = " AND ".join(filters)
            sql = text(
                f"""
                SELECT DISTINCT ON (code)
                    code, current_price, total_market_value, circulating_market_value
                FROM stock_realtime_quote
                WHERE {where}
                ORDER BY code, trade_date DESC
                """
            )
            out: Dict[str, Dict[str, Any]] = {}
            for r in db.execute(sql, params).fetchall():
                price = float(r[1]) if r[1] is not None else None
                if not price or price <= 0:
                    continue
                tmv = float(r[2]) if r[2] is not None else None
                cmv = float(r[3]) if r[3] is not None else None
                out[_norm_code(r[0])] = {
                    "total_shares": (tmv / price) if tmv and tmv > 0 else None,
                    "free_float_shares": (cmv / price) if cmv and cmv > 0 else None,
                }
            return out
        except Exception as e:
            logger.warning("load_shares_from_realtime failed: %s", e)
            return {}
        finally:
            if own:
                db.close()

    def load_latest_closes(self, codes: List[str], trade_date: Optional[str] = None) -> Dict[str, float]:
        if not codes:
            return {}
        db = self._session()
        own = self._db is None
        try:
            codes_n = [_norm_code(c) for c in codes]
            # 批量取每只最新收盘：用 DISTINCT ON
            if trade_date:
                sql = text(
                    """
                    SELECT code, close FROM historical_quotes
                    WHERE code = ANY(:codes) AND date = :d
                    """
                )
                rows = db.execute(sql, {"codes": codes_n, "d": trade_date}).fetchall()
            else:
                sql = text(
                    """
                    SELECT DISTINCT ON (code) code, close
                    FROM historical_quotes
                    WHERE code = ANY(:codes)
                    ORDER BY code, date DESC
                    """
                )
                rows = db.execute(sql, {"codes": codes_n}).fetchall()
            return {_norm_code(r[0]): float(r[1]) for r in rows if r[1] is not None}
        except Exception as e:
            logger.warning("load_latest_closes failed: %s", e)
            return {}
        finally:
            if own:
                db.close()

    def build_size_universe(
        self,
        config: Dict[str, Any],
        trade_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """全市场做小粗筛：有股本的股票按最新收盘估算市值。"""
        from .size_filter import evaluate_size

        shares = self.load_share_map(as_of_date=trade_date)
        codes = list(shares.keys())
        closes = self.load_latest_closes(codes, trade_date=trade_date)
        out: List[Dict[str, Any]] = []
        for code, info in shares.items():
            close = closes.get(code)
            size = evaluate_size(
                total_shares=info.get("total_shares"),
                free_float_shares=info.get("free_float_shares"),
                close=close,
                config=config,
            )
            if size.get("size_ok"):
                out.append({**info, **size, "close": close})
        out.sort(key=lambda x: (x.get("total_mv") or 0))
        if limit:
            out = out[: int(limit)]
        return out

    def load_bars(
        self,
        code: str,
        *,
        end_date: Optional[str] = None,
        limit: int = 120,
    ) -> List[Dict[str, Any]]:
        """返回时间正序 bars。"""
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
                        "amount": float(r[6] or 0),
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

    def load_market_returns(
        self,
        *,
        end_date: Optional[str] = None,
        lookback: int = 80,
        index_code: str = "000001",
    ) -> List[float]:
        """
        大盘日收益序列（正序）。
        优先用指数历史；若无则用全市场涨跌幅中位数近似（仅取 end_date 近 lookback 较贵，降级用上证成分近似：
        直接查 historical_quotes 中 code=000001 若存在）。
        """
        bars = self.load_bars(index_code, end_date=end_date, limit=lookback + 1)
        if len(bars) < 2:
            # 降级：用随机样本中位数成本高，返回空让入口规则放行
            return []
        rets: List[float] = []
        for i in range(1, len(bars)):
            p0 = bars[i - 1]["close"]
            p1 = bars[i]["close"]
            if p0 > 0:
                rets.append((p1 - p0) / p0)
            else:
                rets.append(0.0)
        return rets

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
