"""
从 stock_basic_info / historical_quotes 加载 A 股日线（日期倒序，最新在前）。
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, not_, or_, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# 板块/代码段：与前端 checkbox value 一致（大写）
VSB_BOARD_PREFIX_GROUPS: Dict[str, Tuple[str, ...]] = {
    "CYB": ("300",),  # 创业板
    "KCB": ("688",),  # 科创板
    "SH_MAIN": ("600", "601", "602", "603", "605"),  # 沪市主板（不含 688）
    "SZ_MAIN": ("000", "001"),  # 深市主板
    "SZ_SME": ("002",),  # 深圳中小板
}


def normalize_vsb_board_keys(boards: Optional[List[str]]) -> List[str]:
    """去重、大写，仅保留已定义板块键。支持 `boards=CYB,KCB` 或重复 query。"""
    if not boards:
        return []
    seen: set[str] = set()
    out: List[str] = []
    for b in boards:
        if b is None:
            continue
        for piece in str(b).split(","):
            k = piece.strip().upper()
            if not k or k not in VSB_BOARD_PREFIX_GROUPS or k in seen:
                continue
            seen.add(k)
            out.append(k)
    return out


def code_matches_vsb_boards(code: str, board_keys: List[str]) -> bool:
    """无 board_keys 或空列表表示不过滤。"""
    if not board_keys:
        return True
    c = str(code).strip()
    if len(c) == 5 and c.isdigit():
        c = c.zfill(6)
    if len(c) != 6:
        return False
    for key in board_keys:
        for p in VSB_BOARD_PREFIX_GROUPS.get(key, ()):
            if c.startswith(p):
                return True
    return False


class VolumeShrinkBreakoutDataLoader:
    def __init__(self, db: Session):
        self.db = db

    def list_a_share_candidates(
        self,
        *,
        limit: Optional[int] = None,
        stock_codes: Optional[List[str]] = None,
        boards: Optional[List[str]] = None,
    ) -> List[Tuple[str, str]]:
        """
        返回 (code, name)。若 stock_codes 非空则只保留其中在 basic 表存在且非 ST 的代码；
        否则全市场 A 股（6 位、排除 ST、collect_enabled）。
        boards: 板块/代码段多选（CYB/KCB/SH_MAIN/SZ_MAIN/SZ_SME），空或 None 表示不限。
        """
        from backend_api.models import StockBasicInfo

        def _normalize(c: str) -> Optional[str]:
            s = str(c).strip()
            if len(s) == 5 and s.isdigit():
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
        board_keys = normalize_vsb_board_keys(boards)
        if board_keys:
            like_clauses = [
                StockBasicInfo.code.like(f"{p}%")
                for key in board_keys
                for p in VSB_BOARD_PREFIX_GROUPS[key]
            ]
            qry = qry.filter(or_(*like_clauses))
        if stock_codes:
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

    def fetch_historical_desc(
        self,
        code: str,
        *,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """按日期 DESC，字段与 low_nine_strategy 一致。"""
        rows = self.db.execute(
            text(
                """
                SELECT code, name, date, open, close, high, low,
                       change_percent, volume, amount
                FROM historical_quotes
                WHERE code = :code
                  AND date >= :start_date
                  AND date <= :end_date
                ORDER BY date DESC
                """
            ),
            {"code": str(code), "start_date": start_date, "end_date": end_date},
        ).fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            date_val = row[2]
            if hasattr(date_val, "strftime"):
                date_str = date_val.strftime("%Y-%m-%d")
            else:
                date_str = str(date_val)[:10]
            out.append(
                {
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
                }
            )
        return out

    @staticmethod
    def resolve_effective_history_end_date(db: Session, requested: Optional[str]) -> str:
        """
        将「筛选基准日」解析为 historical_quotes 上可用的 K 线窗口止日（YYYY-MM-DD）：
        - 未传或空：按当前自然日意图处理；
        - 若该日大于表内全局最新 date：钳到 MAX(date)；
        - 若该日表内无任何记录：回退为表内全局 MAX(date)；
        - 否则使用请求日。
        """
        from backend_api.models import HistoricalQuotes

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

        row_max = db.query(func.max(HistoricalQuotes.date)).scalar()
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

        # 生产库常见为 TEXT 存 YYYY-MM-DD；与 Python date 比较会触发 PG「text = date」错误，统一用字符串比较。
        exists = (
            db.query(HistoricalQuotes.code)
            .filter(HistoricalQuotes.date == target_s)
            .limit(1)
            .first()
        )
        if exists is not None:
            return target_s
        return max_s

    @staticmethod
    def default_date_window(calendar_days: int, end_anchor: Optional[str] = None) -> Tuple[str, str]:
        if end_anchor:
            s = str(end_anchor).strip()[:10]
            try:
                end_d = datetime.strptime(s, "%Y-%m-%d").date()
            except ValueError:
                end_d = datetime.now().date()
        else:
            end_d = datetime.now().date()
        start_d = end_d - timedelta(days=int(calendar_days))
        return start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d")
