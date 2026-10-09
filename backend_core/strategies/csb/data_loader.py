# -*- coding: utf-8 -*-
"""CSB 数据加载：A 股日 K（含 turnover）。"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import bindparam, func, not_, or_, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _norm_code(code: str) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s


def history_calendar_days_for_fetch(config: Optional[Dict[str, Any]] = None) -> int:
    """由 history_bars 估算需拉取的自然日跨度（含缓冲）。"""
    scan = (config or {}).get("scan") or {}
    try:
        hist_n = int(scan.get("history_bars", 280))
    except (TypeError, ValueError):
        hist_n = 280
    # 约 280 个交易日 ≈ 400+ 自然日；再留余量避免长假缺口
    return max(420, int(hist_n * 1.65) + 40)


class CSBDataLoader:
    def __init__(self, db_session=None):
        self._db = db_session

    def _session(self):
        if self._db is not None:
            return self._db
        from backend_api.database import SessionLocal

        return SessionLocal()

    def _rollback_quiet(self) -> None:
        db = self._db
        if db is None:
            return
        try:
            db.rollback()
        except Exception:
            pass

    def list_a_share_candidates(
        self,
        *,
        limit: Optional[int] = None,
        stock_codes: Optional[List[str]] = None,
    ) -> List[Tuple[str, str]]:
        from backend_api.models import StockBasicInfo

        db = self._session()
        own = self._db is None
        try:
            qry = (
                db.query(StockBasicInfo.code, StockBasicInfo.name)
                .filter(func.length(StockBasicInfo.code) == 6)
                .filter(not_(StockBasicInfo.name.like("%ST%")))
                .filter(or_(StockBasicInfo.collect_enabled.is_(True), StockBasicInfo.collect_enabled.is_(None)))
                .order_by(StockBasicInfo.code)
            )
            if stock_codes is not None:
                cleaned = [_norm_code(c) for c in stock_codes if _norm_code(c)]
                if not cleaned:
                    return []
                qry = qry.filter(StockBasicInfo.code.in_(cleaned))
            rows = qry.all()
            out = [(str(r[0]), str(r[1] or "")) for r in rows]
            if limit is not None and limit > 0:
                out = out[: int(limit)]
            return out
        finally:
            if own:
                db.close()

    @staticmethod
    def _row_to_bar(r: Any) -> Optional[Dict[str, Any]]:
        """(date, open, high, low, close, volume, amount, turnover_rate) → 正序 bar。"""
        d = r[0]
        ds = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
        vol = float(r[5] or 0)
        if vol <= 0:
            return None
        return {
            "date": ds,
            "open": float(r[1] or 0),
            "high": float(r[2] or 0),
            "low": float(r[3] or 0),
            "close": float(r[4] or 0),
            "volume": vol,
            "amount": float(r[6] or 0),
            "turnover_rate": float(r[7]) if r[7] is not None else None,
        }

    def load_bars(
        self,
        code: str,
        *,
        end_date: Optional[str] = None,
        limit: int = 280,
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
            bars: List[Dict[str, Any]] = []
            for r in reversed(rows):
                bar = self._row_to_bar(r)
                if bar:
                    bars.append(bar)
            return bars
        except Exception as e:
            logger.warning("CSB load_bars %s failed: %s", code, e)
            return []
        finally:
            if own:
                db.close()

    def load_bars_range(
        self,
        code: str,
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """按日期窗口拉取单票日 K，时间正序。"""
        db = self._session()
        own = self._db is None
        try:
            code_n = _norm_code(code)
            clauses = ["code = :code"]
            params: Dict[str, Any] = {"code": code_n}
            if start_date:
                clauses.append("date >= :start_date")
                params["start_date"] = str(start_date)[:10]
            if end_date:
                clauses.append("date <= :end_date")
                params["end_date"] = str(end_date)[:10]
            sql = text(
                f"""
                SELECT date, open, high, low, close, volume, amount, turnover_rate
                FROM historical_quotes
                WHERE {' AND '.join(clauses)}
                ORDER BY date ASC
                """
            )
            rows = db.execute(sql, params).fetchall()
            bars: List[Dict[str, Any]] = []
            for r in rows:
                bar = self._row_to_bar(r)
                if bar:
                    bars.append(bar)
            return bars
        except Exception as e:
            logger.warning("CSB load_bars_range %s failed: %s", code, e)
            self._rollback_quiet()
            return []
        finally:
            if own:
                db.close()

    @staticmethod
    def resolve_hist_batch_chunk_size(
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        chunk_size: Optional[int] = None,
    ) -> int:
        """按日期跨度估算批量拉行情的 codes 分块，避免单次结果集 OOM。"""
        env_raw = (os.getenv("CSB_HIST_BATCH_CODES") or "").strip()
        if env_raw.isdigit():
            return max(1, min(120, int(env_raw)))

        if chunk_size is not None:
            try:
                requested = int(chunk_size)
            except (TypeError, ValueError):
                requested = 0
            if requested > 0:
                return max(1, min(120, requested))

        cal_days = 120
        try:
            if start_date and end_date:
                d0 = datetime.strptime(str(start_date)[:10], "%Y-%m-%d").date()
                d1 = datetime.strptime(str(end_date)[:10], "%Y-%m-%d").date()
                cal_days = max(1, (d1 - d0).days + 1)
        except ValueError:
            pass

        approx_bars = max(30, int(cal_days * 0.7))
        target_rows = 12_000
        auto = max(1, min(40, target_rows // approx_bars))
        return int(auto)

    def load_bars_batch(
        self,
        codes: List[str],
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        chunk_size: Optional[int] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """批量拉取日 K（每只时间正序）。分块流式取回；OOM 时自动缩小分块。"""
        uniq: List[str] = []
        seen: set[str] = set()
        for c in codes:
            s = _norm_code(c)
            if not s or s in seen:
                continue
            seen.add(s)
            uniq.append(s)
        out: Dict[str, List[Dict[str, Any]]] = {c: [] for c in uniq}
        if not uniq:
            return out

        db = self._session()
        own = self._db is None
        n = self.resolve_hist_batch_chunk_size(
            start_date=start_date, end_date=end_date, chunk_size=chunk_size
        )
        yield_per = 500
        min_chunk = 1

        def _is_oom_error(exc: Exception) -> bool:
            msg = str(exc).lower()
            name = type(exc).__name__.lower()
            return (
                "out of memory" in msg
                or "memoryerror" in name
                or "query result" in msg
                or "portalholdcontext" in msg
                or "内存用尽" in str(exc)
            )

        def _fetch_chunk(chunk: List[str]) -> None:
            clauses = ["code IN :codes"]
            params: Dict[str, Any] = {"codes": chunk}
            if start_date:
                clauses.append("date >= :start_date")
                params["start_date"] = str(start_date)[:10]
            if end_date:
                clauses.append("date <= :end_date")
                params["end_date"] = str(end_date)[:10]
            sql = text(
                f"""
                SELECT code, date, open, high, low, close, volume, amount, turnover_rate
                FROM historical_quotes
                WHERE {' AND '.join(clauses)}
                """
            ).bindparams(bindparam("codes", expanding=True))
            result = db.execute(
                sql,
                params,
                execution_options={"stream_results": True, "yield_per": yield_per},
            )
            for row in result:
                code = _norm_code(str(row[0] or ""))
                if code not in out:
                    continue
                bar = self._row_to_bar(row[1:])
                if bar:
                    out[code].append(bar)
            for code in chunk:
                bars = out.get(code) or []
                if len(bars) > 1:
                    bars.sort(key=lambda b: str(b.get("date") or ""))

        def _fetch_codes_solo(solo_codes: List[str]) -> None:
            for code in solo_codes:
                try:
                    out[code] = self.load_bars_range(
                        code, start_date=start_date, end_date=end_date
                    )
                except Exception as solo_e:
                    self._rollback_quiet()
                    logger.warning("CSB 单票拉行情失败 code=%s: %s", code, solo_e)
                    out[code] = []

        try:
            i = 0
            while i < len(uniq):
                chunk = uniq[i : i + n]
                try:
                    _fetch_chunk(chunk)
                    i += len(chunk)
                except Exception as e:
                    if _is_oom_error(e) and n > min_chunk:
                        new_n = max(min_chunk, n // 2)
                        logger.warning(
                            "CSB 批量拉行情 OOM，缩小分块 %s→%s（本批 %s 只）: %s",
                            n,
                            new_n,
                            len(chunk),
                            e,
                        )
                        self._rollback_quiet()
                        n = new_n
                        continue
                    if _is_oom_error(e):
                        logger.warning(
                            "CSB 批量拉行情 OOM（分块=%s），本批改逐票拉取: %s",
                            n,
                            e,
                        )
                        self._rollback_quiet()
                        _fetch_codes_solo(chunk)
                        i += len(chunk)
                        continue
                    self._rollback_quiet()
                    raise
            return out
        finally:
            if own:
                db.close()

    def resolve_effective_trade_date(self, requested: Optional[str] = None) -> str:
        db = self._session()
        own = self._db is None
        today_s = datetime.now().strftime("%Y-%m-%d")
        try:
            from backend_api.models import HistoricalQuotes

            raw = (requested or "").strip()[:10]
            target_s: Optional[str] = None
            if raw:
                try:
                    datetime.strptime(raw, "%Y-%m-%d")
                    target_s = raw
                except ValueError:
                    target_s = None

            latest = db.query(func.max(HistoricalQuotes.date)).scalar()
            if latest is None:
                return target_s or today_s
            max_s = latest.strftime("%Y-%m-%d") if hasattr(latest, "strftime") else str(latest)[:10]
            if not target_s:
                return max_s
            asof = (
                db.query(func.max(HistoricalQuotes.date))
                .filter(HistoricalQuotes.date <= target_s)
                .scalar()
            )
            if asof is None:
                return max_s
            return asof.strftime("%Y-%m-%d") if hasattr(asof, "strftime") else str(asof)[:10]
        except Exception as e:
            logger.warning("CSB resolve_effective_trade_date failed: %s", e)
            return (requested or "").strip()[:10] or today_s
        finally:
            if own:
                db.close()

    @staticmethod
    def truncate_bars_asof(bars: List[Dict[str, Any]], asof: Optional[str]) -> List[Dict[str, Any]]:
        if not bars or not asof:
            return list(bars or [])
        d = str(asof)[:10]
        return [b for b in bars if str(b.get("date") or "")[:10] <= d]

    @staticmethod
    def default_date_window(calendar_days: int, end_anchor: Optional[str] = None) -> Tuple[str, str]:
        if end_anchor:
            try:
                end = datetime.strptime(str(end_anchor)[:10], "%Y-%m-%d").date()
            except ValueError:
                end = datetime.now().date()
        else:
            end = datetime.now().date()
        start = end - timedelta(days=max(30, int(calendar_days)))
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    @staticmethod
    def resolve_effective_history_end_date(db: Session, requested: Optional[str] = None) -> str:
        loader = CSBDataLoader(db)
        return loader.resolve_effective_trade_date(requested)
