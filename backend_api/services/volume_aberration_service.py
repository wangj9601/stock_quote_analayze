"""
成交量异动榜数据服务 - 供 API 与 ReportService 复用
从行情表 JOIN mavol_indicators 按量比(20) 排序，返回全量或分页数据。
"""

import logging
from typing import List, Tuple, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from backend_api.models import HistoricalQuotes, HistoricalQuotesHK

logger = logging.getLogger(__name__)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value in (None, "", "-"):
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def get_volume_aberration_data(
    db: Session,
    market: str,
    date: Optional[str] = None,
    order: str = "desc",
) -> Tuple[List[dict], Optional[str]]:
    """
    获取成交量异动榜全量数据（不分页），供 API 分页或 ReportService 导出使用。

    Args:
        db: 数据库会话
        market: 市场 'cn'(A股) 或 'hk'(港股)
        date: 交易日期 YYYY-MM-DD，None 表示该市场最新交易日
        order: 排序 'desc' 放量榜(量比降序) / 'asc' 缩量榜(量比升序)

    Returns:
        (result_list, trade_date): 记录列表（每项含 code, name, date, volume, amount, mavol5/10/20, ratio_5, ratio_20, change_percent, close, turnover_rate），
        以及交易日期字符串；无数据时 trade_date 可能为 None。
    """
    if market not in ("cn", "hk"):
        return [], None
    if order not in ("desc", "asc"):
        order = "desc"

    try:
        if market == "cn":
            if date:
                trade_date = date.strip()[:10]
            else:
                r = db.query(func.max(HistoricalQuotes.date)).scalar()
                if not r:
                    return [], None
                trade_date = r.strftime("%Y-%m-%d") if hasattr(r, "strftime") else str(r).strip()[:10]
            sql = text("""
                SELECT h.code, h.name, h.date, h.volume, h.amount, h.change_percent, h.close, h.turnover_rate,
                       m.mavol5 AS mavol5, m.mavol10 AS mavol10, m.mavol20 AS mavol20
                FROM historical_quotes h
                INNER JOIN mavol_indicators m ON h.code = m.code AND m.market_type = 'CN'
                   AND m.date = :trade_date
                WHERE h.date = :h_date
                  AND m.mavol20 IS NOT NULL AND m.mavol20 > 0
            """)
            rows = db.execute(sql, {"trade_date": trade_date, "h_date": trade_date}).fetchall()
        else:
            if date:
                trade_date = date.strip()[:10]
            else:
                r = db.execute(text("SELECT MAX(date) as d FROM historical_quotes_hk")).scalar()
                if not r:
                    return [], None
                trade_date = str(r).strip()[:10]
            sql = text("""
                SELECT h.code, h.name, h.date, h.volume, h.amount, h.change_percent, h.close, h.turnover_rate,
                       m.mavol5 AS mavol5, m.mavol10 AS mavol10, m.mavol20 AS mavol20
                FROM historical_quotes_hk h
                INNER JOIN mavol_indicators m ON h.code = m.code AND m.market_type = 'HK'
                   AND m.date = :trade_date
                WHERE h.date = :trade_date
                  AND m.mavol20 IS NOT NULL AND m.mavol20 > 0
            """)
            rows = db.execute(sql, {"trade_date": trade_date}).fetchall()

        def _get(r, name: str):
            try:
                if hasattr(r, "_mapping"):
                    return r._mapping.get(name)
                return getattr(r, name, None)
            except Exception:
                return None

        result = []
        for r in rows:
            vol = float(r.volume) if r.volume is not None else None
            _m5, _m10, _m20 = _get(r, "mavol5"), _get(r, "mavol10"), _get(r, "mavol20")
            m5 = float(_m5) if _m5 is not None and float(_m5) > 0 else None
            m20 = float(_m20) if _m20 is not None and float(_m20) > 0 else None
            ratio_5 = round(vol / m5, 4) if vol is not None and m5 else None
            ratio_20 = round(vol / m20, 4) if vol is not None and m20 else None
            date_str = r.date.strftime("%Y-%m-%d") if hasattr(r.date, "strftime") else str(r.date).strip()[:10]
            result.append({
                "code": str(r.code) if r.code else "",
                "name": (r.name or "").strip(),
                "date": date_str,
                "volume": vol,
                "amount": _safe_float(r.amount),
                "mavol5": m5,
                "mavol10": _safe_float(_m10),
                "mavol20": m20,
                "ratio_5": ratio_5,
                "ratio_20": ratio_20,
                "change_percent": _safe_float(r.change_percent),
                "close": _safe_float(r.close),
                "turnover_rate": _safe_float(r.turnover_rate),
            })

        result.sort(key=lambda x: (x["ratio_20"] is None, -(x["ratio_20"] or 0) if order == "desc" else (x["ratio_20"] or 0)))
        for i, item in enumerate(result):
            item["rank"] = i + 1

        return result, trade_date
    except Exception as e:
        logger.exception("get_volume_aberration_data 失败: %s", e)
        return [], None
