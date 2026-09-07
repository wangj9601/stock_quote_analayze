# -*- coding: utf-8 -*-
"""URT 数据加载：候选池 + historical_quotes（日期倒序，最新在前）。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, not_, or_, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

URT_BOARD_PREFIX_GROUPS: Dict[str, Tuple[str, ...]] = {
    "CYB": ("300",),
    "KCB": ("688",),
    "SH_MAIN": ("600", "601", "602", "603", "605"),
    "SZ_MAIN": ("000", "001"),
    "SZ_SME": ("002",),
    "BJ": ("43", "83", "87", "88", "92"),
}


def normalize_urt_board_keys(boards: Optional[List[str]]) -> List[str]:
    if not boards:
        return []
    seen: set[str] = set()
    out: List[str] = []
    for b in boards:
        if b is None:
            continue
        for piece in str(b).split(","):
            k = piece.strip().upper()
            if not k or k not in URT_BOARD_PREFIX_GROUPS or k in seen:
                continue
            seen.add(k)
            out.append(k)
    return out


def code_matches_urt_boards(code: Any, boards: Optional[List[str]]) -> bool:
    """按 URT 板块前缀判断代码是否命中（无 boards 或无法识别键时视为不过滤）。"""
    keys = normalize_urt_board_keys(boards)
    if not keys:
        return True
    s = str(code or "").replace("\u2060", "").strip()
    if s.isdigit() and 0 < len(s) < 6:
        s = s.zfill(6)
    if not s:
        return False
    for key in keys:
        for p in URT_BOARD_PREFIX_GROUPS.get(key) or ():
            if s.startswith(p):
                return True
    return False


def normalize_hk_code(code: str) -> Optional[str]:
    s = str(code or "").strip()
    if not s:
        return None
    if s.isdigit() and len(s) <= 5:
        return s.zfill(5)
    return s


def is_hk_stock_code(code: str) -> bool:
    s = str(code or "").strip()
    if not s.isdigit():
        return False
    return len(s) == 5 or (len(s) < 6 and len(s) > 0)


class URTDataLoader:
    def __init__(self, db: Session, *, market: str = "CN"):
        self.db = db
        self.market = str(market or "CN").strip().upper()

    def list_a_share_candidates(
        self,
        *,
        limit: Optional[int] = None,
        stock_codes: Optional[List[str]] = None,
        boards: Optional[List[str]] = None,
    ) -> List[Tuple[str, str]]:
        from backend_api.models import StockBasicInfo

        def _normalize(c: str) -> Optional[str]:
            s = str(c).replace("\u2060", "").strip()
            # 5 位数字是港股码，禁止抬成 6 位 A 股（00981→000981）
            if len(s) == 5 and s.isdigit():
                return None
            if s.isdigit() and 0 < len(s) < 6:
                s = s.zfill(6)
            if len(s) == 6 and s.isdigit():
                return s
            return None

        qry = (
            self.db.query(StockBasicInfo.code, StockBasicInfo.name)
            .filter(func.length(StockBasicInfo.code) == 6)
            .filter(not_(StockBasicInfo.name.like("%ST%")))
            .filter(or_(StockBasicInfo.collect_enabled.is_(True), StockBasicInfo.collect_enabled.is_(None)))
            .order_by(StockBasicInfo.code)
        )
        board_keys = normalize_urt_board_keys(boards)
        if board_keys:
            like_clauses = [
                StockBasicInfo.code.like(f"{p}%")
                for key in board_keys
                for p in URT_BOARD_PREFIX_GROUPS[key]
            ]
            qry = qry.filter(or_(*like_clauses))
        # 必须用 is not None：空列表表示「限定池为空」，不能当成「不限池」扫全市场
        if stock_codes is not None:
            cleaned = [_normalize(c) for c in stock_codes]
            cleaned = [c for c in cleaned if c]
            if not cleaned:
                return []
            qry = qry.filter(StockBasicInfo.code.in_(cleaned))
        rows = qry.all()
        out = [(str(r[0]), str(r[1] or "")) for r in rows]
        if limit is not None and limit > 0:
            out = out[: int(limit)]
        return out

    def list_hk_share_candidates(
        self,
        *,
        limit: Optional[int] = None,
        stock_codes: Optional[List[str]] = None,
    ) -> List[Tuple[str, str]]:
        """从 stock_basic_info_hk 取港股候选（排除 ST，尊重 collect_enabled）。"""
        from backend_api.models import StockBasicInfoHK

        qry = (
            self.db.query(StockBasicInfoHK.code, StockBasicInfoHK.name)
            .filter(not_(StockBasicInfoHK.name.like("%ST%")))
            .filter(
                or_(
                    StockBasicInfoHK.collect_enabled.is_(True),
                    StockBasicInfoHK.collect_enabled.is_(None),
                )
            )
            .order_by(StockBasicInfoHK.code)
        )
        if stock_codes is not None:
            cleaned = [normalize_hk_code(c) for c in stock_codes]
            cleaned = [c for c in cleaned if c]
            if not cleaned:
                return []
            qry = qry.filter(StockBasicInfoHK.code.in_(cleaned))
        rows = qry.all()
        out = [(str(r[0]), str(r[1] or "")) for r in rows]
        if limit is not None and limit > 0:
            out = out[: int(limit)]
        return out

    def fetch_historical_desc(
        self,
        code: str,
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        market: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """拉取日 K（日期 DESC）。start/end 均可选；强制重算时可省略以取该股全部历史。"""
        mkt = str(market or self.market or "CN").strip().upper()
        table = "historical_quotes_hk" if mkt == "HK" else "historical_quotes"
        clauses = ["code = :code"]
        params: Dict[str, Any] = {"code": str(code)}
        if start_date:
            clauses.append("date >= :start_date")
            params["start_date"] = str(start_date)[:10]
        if end_date:
            clauses.append("date <= :end_date")
            params["end_date"] = str(end_date)[:10]
        sql = f"""
            SELECT code, name, date, open, close, high, low,
                   change_percent, volume, amount, turnover_rate
            FROM {table}
            WHERE {' AND '.join(clauses)}
            ORDER BY date DESC
        """
        rows = self.db.execute(text(sql), params).fetchall()
        return [self._quote_row_to_bar(row) for row in rows]

    @staticmethod
    def resolve_hist_batch_chunk_size(
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        chunk_size: Optional[int] = None,
    ) -> int:
        """按日期跨度估算批量拉行情的 codes 分块大小，避免单次结果集撑爆客户端内存。

        生产曾出现：400 只 × ~3 年日 K → psycopg2「out of memory for query result」。
        """
        import os

        env_raw = (os.getenv("URT_HIST_BATCH_CODES") or "").strip()
        if env_raw.isdigit():
            return max(10, min(200, int(env_raw)))

        if chunk_size is not None:
            try:
                requested = int(chunk_size)
            except (TypeError, ValueError):
                requested = 0
            if requested > 0:
                return max(10, min(200, requested))

        cal_days = 120
        try:
            if start_date and end_date:
                d0 = datetime.strptime(str(start_date)[:10], "%Y-%m-%d").date()
                d1 = datetime.strptime(str(end_date)[:10], "%Y-%m-%d").date()
                cal_days = max(1, (d1 - d0).days + 1)
        except ValueError:
            pass

        # 粗估：目标单批约 ≤ 4 万行（codes × 交易日≈日历日×0.7）
        approx_bars = max(30, int(cal_days * 0.7))
        target_rows = 40_000
        auto = max(10, min(80, target_rows // approx_bars))
        return int(auto)

    def fetch_historical_desc_batch(
        self,
        codes: List[str],
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        market: Optional[str] = None,
        chunk_size: Optional[int] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """按代码批量拉取日 K（每只日期 DESC）。减少全市场扫描的逐股查询。

        分块 + yield_per 流式取回，避免大结果集一次进客户端内存。
        """
        from sqlalchemy import bindparam

        mkt = str(market or self.market or "CN").strip().upper()
        table = "historical_quotes_hk" if mkt == "HK" else "historical_quotes"
        uniq: List[str] = []
        seen: set[str] = set()
        for c in codes:
            s = str(c or "").strip()
            if not s or s in seen:
                continue
            seen.add(s)
            uniq.append(s)
        out: Dict[str, List[Dict[str, Any]]] = {c: [] for c in uniq}
        if not uniq:
            return out

        n = self.resolve_hist_batch_chunk_size(
            start_date=start_date, end_date=end_date, chunk_size=chunk_size
        )
        yield_per = 2000

        def _fetch_chunk(chunk: List[str]) -> None:
            clauses = ["code IN :codes"]
            params: Dict[str, Any] = {"codes": chunk}
            if start_date:
                clauses.append("date >= :start_date")
                params["start_date"] = str(start_date)[:10]
            if end_date:
                clauses.append("date <= :end_date")
                params["end_date"] = str(end_date)[:10]
            # 不选 name：结果集更小；名称由选股列表侧提供
            sql = text(
                f"""
                SELECT code, date, open, close, high, low,
                       change_percent, volume, amount, turnover_rate
                FROM {table}
                WHERE {' AND '.join(clauses)}
                ORDER BY code ASC, date DESC
                """
            ).bindparams(bindparam("codes", expanding=True))
            result = self.db.execute(
                sql,
                params,
                execution_options={"yield_per": yield_per},
            )
            for row in result:
                bar = self._quote_row_to_bar_compact(row)
                code = str(bar.get("code") or "")
                if code in out:
                    out[code].append(bar)

        i = 0
        while i < len(uniq):
            chunk = uniq[i : i + n]
            try:
                _fetch_chunk(chunk)
                i += len(chunk)
            except Exception as e:
                msg = str(e).lower()
                is_oom = (
                    "out of memory" in msg
                    or "memoryerror" in type(e).__name__.lower()
                    or "query result" in msg
                )
                if is_oom and n > 10:
                    new_n = max(10, n // 2)
                    logger.warning(
                        "URT 批量拉行情 OOM，缩小分块 %s→%s（本批 %s 只）: %s",
                        n,
                        new_n,
                        len(chunk),
                        e,
                    )
                    try:
                        self.db.rollback()
                    except Exception:
                        pass
                    n = new_n
                    continue
                raise
        return out

    @staticmethod
    def _quote_row_to_bar_compact(row: Any) -> Dict[str, Any]:
        """无 name 列的批量查询行 → bar（与 _quote_row_to_bar 字段对齐）。"""
        date_val = row[1]
        if hasattr(date_val, "strftime"):
            date_str = date_val.strftime("%Y-%m-%d")
        else:
            date_str = str(date_val)[:10]
        return {
            "code": row[0],
            "name": None,
            "date": date_str,
            "open": float(row[2]) if row[2] is not None else 0.0,
            "close": float(row[3]) if row[3] is not None else 0.0,
            "high": float(row[4]) if row[4] is not None else 0.0,
            "low": float(row[5]) if row[5] is not None else 0.0,
            "change_percent": float(row[6]) if row[6] is not None else 0.0,
            "volume": float(row[7]) if row[7] is not None else 0.0,
            "amount": float(row[8]) if row[8] is not None else 0.0,
            "turnover_rate": float(row[9]) if row[9] is not None else None,
        }

    @staticmethod
    def _quote_row_to_bar(row: Any) -> Dict[str, Any]:
        date_val = row[2]
        if hasattr(date_val, "strftime"):
            date_str = date_val.strftime("%Y-%m-%d")
        else:
            date_str = str(date_val)[:10]
        return {
            "code": row[0],
            "name": row[1],
            "date": date_str,
            "open": float(row[3]) if row[3] is not None else 0.0,
            "close": float(row[4]) if row[4] is not None else 0.0,
            "high": float(row[5]) if row[5] is not None else 0.0,
            "low": float(row[6]) if row[6] is not None else 0.0,
            "change_percent": float(row[7]) if row[7] is not None else 0.0,
            "volume": float(row[8]) if row[8] is not None else 0.0,
            "amount": float(row[9]) if row[9] is not None else 0.0,
            "turnover_rate": float(row[10]) if row[10] is not None else None,
        }

    @staticmethod
    def resolve_effective_history_end_date(
        db: Session,
        requested: Optional[str],
        *,
        market: str = "CN",
    ) -> str:
        mkt = str(market or "CN").strip().upper()
        if mkt == "HK":
            from backend_api.models import HistoricalQuotesHK

            quote_model = HistoricalQuotesHK
        else:
            from backend_api.models import HistoricalQuotes

            quote_model = HistoricalQuotes

        today = datetime.now().date()
        today_s = today.strftime("%Y-%m-%d")
        raw = (requested or "").strip()[:10]
        if not raw:
            target = today
            target_s = today_s
        else:
            try:
                target = datetime.strptime(raw, "%Y-%m-%d").date()
                target_s = raw
            except ValueError:
                target = today
                target_s = today_s

        row_max = db.query(func.max(quote_model.date)).scalar()
        if row_max is None:
            return target_s
        if hasattr(row_max, "strftime"):
            max_d = row_max
            max_s = max_d.strftime("%Y-%m-%d")
        else:
            max_s = str(row_max).strip()[:10]
            try:
                max_d = datetime.strptime(max_s, "%Y-%m-%d").date()
            except ValueError:
                return target_s

        if target > max_d:
            return max_s

        exists = (
            db.query(quote_model.code)
            .filter(quote_model.date == target_s)
            .limit(1)
            .first()
        )
        if exists is not None:
            return target_s
        return max_s

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
