# -*- coding: utf-8 -*-
"""集合竞价采集与查询服务。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_api.stock.auction_store import persist_auction_benchmark, persist_auction_items
from backend_api.utils.fuyao_client import (
    AUCTION_BATCH_SIZE,
    auction_item_to_record,
    fetch_a_share_auction_short_term_benchmark,
    fetch_a_share_auction_snapshot,
)

logger = logging.getLogger(__name__)

SH_TZ = timezone(timedelta(hours=8))


def sh_today() -> str:
    return datetime.now(SH_TZ).strftime("%Y-%m-%d")


def ms_to_sh_date(ms: Any) -> Optional[str]:
    try:
        if ms is None:
            return None
        return datetime.fromtimestamp(int(ms) / 1000, tz=SH_TZ).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return None


def norm_code(raw: Any) -> str:
    s = str(raw or "").strip().upper()
    if "." in s:
        s = s.split(".", 1)[0]
    for prefix in ("SH", "SZ", "BJ"):
        if s.startswith(prefix) and s[len(prefix) :].isdigit():
            s = s[len(prefix) :]
            break
    digits = "".join(ch for ch in s if ch.isdigit())
    if not digits:
        return s
    return digits.zfill(6) if len(digits) <= 6 else digits[-6:]


def _row_to_dict(row) -> Dict[str, Any]:
    if row is None:
        return {}
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    return dict(row)


def get_collectable_codes(db: Session, codes: Optional[List[str]] = None) -> List[str]:
    if codes:
        out = []
        seen = set()
        for c in codes:
            code = norm_code(c)
            if code and code not in seen:
                seen.add(code)
                out.append(code)
        return out

    rows = db.execute(
        text(
            """
            SELECT code FROM stock_basic_info
            WHERE COALESCE(collect_enabled, TRUE) = TRUE
            ORDER BY code
            """
        )
    ).fetchall()
    return [norm_code(r[0]) for r in rows if r and r[0]]


def collect_auction_benchmark(
    db: Session,
    trade_date: Optional[str] = None,
) -> Dict[str, Any]:
    day = (trade_date or "").strip() or None
    result = fetch_a_share_auction_short_term_benchmark(day)
    if not result.get("ok"):
        return {"success": False, "message": result.get("error") or "benchmark_failed"}

    resolved_date = (result.get("date") or day or sh_today())[:10]
    items = []
    for raw in result.get("items") or []:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        row["code"] = norm_code(row.get("ticker") or row.get("code"))
        row["source"] = "fuyao"
        items.append(row)

    saved = persist_auction_benchmark(
        resolved_date,
        items,
        response_timestamp=result.get("timestamp"),
        db=db,
    )
    return {
        "success": True,
        "trade_date": resolved_date,
        "saved": saved,
        "items": items,
        "timestamp": result.get("timestamp"),
    }


def collect_auction_snapshot(
    db: Session,
    *,
    codes: Optional[List[str]] = None,
    stage: str = "final",
    trade_date: Optional[str] = None,
    refresh_benchmark: bool = True,
) -> Dict[str, Any]:
    stage_norm = (stage or "final").strip().lower()
    if stage_norm not in ("live", "final"):
        stage_norm = "final"

    code_list = get_collectable_codes(db, codes)
    if not code_list:
        return {"success": False, "message": "没有可采集的股票代码"}

    benchmark_info: Dict[str, Any] = {}
    if refresh_benchmark:
        benchmark_info = collect_auction_benchmark(db, trade_date)
        if benchmark_info.get("success") and not trade_date:
            trade_date = benchmark_info.get("trade_date")

    resolved_date = (trade_date or sh_today())[:10]
    total_saved = 0
    failed_batches = 0
    last_status = None
    last_ts = None

    for i in range(0, len(code_list), AUCTION_BATCH_SIZE):
        batch = code_list[i : i + AUCTION_BATCH_SIZE]
        result = fetch_a_share_auction_snapshot(batch, stage=stage_norm)
        if not result.get("ok"):
            failed_batches += 1
            logger.warning(
                "集合竞价批次失败 offset=%s err=%s",
                i,
                result.get("error"),
            )
            continue
        records = [auction_item_to_record(x) for x in (result.get("items") or []) if isinstance(x, dict)]
        last_status = result.get("data_status")
        last_ts = result.get("timestamp")
        if ms_to_sh_date(last_ts):
            resolved_date = ms_to_sh_date(last_ts) or resolved_date
        total_saved += persist_auction_items(
            resolved_date,
            stage_norm,
            records,
            data_status=last_status,
            response_timestamp=last_ts,
            db=db,
        )

    return {
        "success": True,
        "trade_date": resolved_date,
        "auction_phase": stage_norm,
        "requested_codes": len(code_list),
        "saved": total_saved,
        "failed_batches": failed_batches,
        "data_status": last_status,
        "timestamp": last_ts,
        "benchmark": benchmark_info if refresh_benchmark else None,
    }


def query_auction_list(
    db: Session,
    *,
    trade_date: Optional[str] = None,
    auction_phase: str = "final",
    keyword: Optional[str] = None,
    sort_by: str = "auction_pct",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    day = (trade_date or sh_today())[:10]
    phase = (auction_phase or "final").strip().lower()
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)

    allowed_sort = {
        "auction_pct": "auction_pct",
        "auction_volume_ratio": "auction_volume_ratio",
        "auction_turnover_pct": "auction_turnover_pct",
        "auction_amount": "auction_amount",
        "code": "code",
    }
    sort_col = allowed_sort.get(sort_by, "auction_pct")
    order = "ASC" if str(sort_order).lower() == "asc" else "DESC"

    where = ["trade_date = :trade_date", "auction_phase = :auction_phase"]
    params: Dict[str, Any] = {"trade_date": day, "auction_phase": phase}
    if keyword:
        where.append(
            "(code LIKE :kw OR name LIKE :kw OR thscode LIKE :kw)"
        )
        params["kw"] = f"%{keyword.strip()}%"

    where_sql = " AND ".join(where)
    total = db.execute(
        text(f"SELECT COUNT(*) FROM stock_auction_daily WHERE {where_sql}"),
        params,
    ).scalar() or 0

    offset = (page - 1) * page_size
    rows = db.execute(
        text(
            f"""
            SELECT *
            FROM stock_auction_daily
            WHERE {where_sql}
            ORDER BY {sort_col} {order} NULLS LAST, code ASC
            LIMIT :limit OFFSET :offset
            """
        ),
        {**params, "limit": page_size, "offset": offset},
    ).fetchall()

    return {
        "success": True,
        "trade_date": day,
        "auction_phase": phase,
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "items": [_row_to_dict(r) for r in rows],
    }


def query_auction_benchmark(
    db: Session,
    trade_date: Optional[str] = None,
    *,
    live: bool = False,
) -> Dict[str, Any]:
    """短线风向标。默认只读库；``live=True`` 才请求 Fuyao。"""
    day = (trade_date or sh_today())[:10]
    rows = db.execute(
        text(
            """
            SELECT trade_date, seq, thscode, code, name, auction_pct, tags, source, response_timestamp
            FROM stock_auction_benchmark
            WHERE trade_date = :trade_date
            ORDER BY seq ASC
            """
        ),
        {"trade_date": day},
    ).fetchall()

    if rows and not live:
        return {
            "success": True,
            "trade_date": day,
            "source": "db",
            "items": [_row_to_dict(r) for r in rows],
        }

    if not live:
        return {
            "success": False,
            "message": f"库中暂无 {day} 短线风向标，请先采集或开启实时拉取",
            "trade_date": day,
            "items": [],
        }

    result = fetch_a_share_auction_short_term_benchmark(day if trade_date else None)
    if not result.get("ok"):
        if rows:
            return {
                "success": True,
                "trade_date": day,
                "source": "db",
                "items": [_row_to_dict(r) for r in rows],
                "live_error": result.get("error"),
            }
        err = result.get("error") or "benchmark_failed"
        if str(err).startswith("http_429") or str(err) == "429":
            err = "实时接口限流(429)，且库中无当日基准数据；请稍后重试或先采集"
        return {"success": False, "message": err}

    resolved_date = (result.get("date") or day)[:10]
    items = []
    for raw in result.get("items") or []:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        row["code"] = norm_code(row.get("ticker") or row.get("code"))
        items.append(row)

    try:
        persist_auction_benchmark(
            resolved_date,
            items,
            response_timestamp=result.get("timestamp"),
            db=db,
        )
    except Exception:
        logger.exception("基准实时落库失败")

    return {
        "success": True,
        "trade_date": resolved_date,
        "source": "fuyao",
        "timestamp": result.get("timestamp"),
        "items": items,
    }


def normalize_auction_phase(phase: Optional[str], *, fallback: str = "final") -> str:
    """将 Fuyao 返回的 closed/ready 等归一为 live/final。"""
    p = (phase or "").strip().lower()
    if p in ("live", "realtime", "ing"):
        return "live"
    if p in ("final", "closed", "end", "ready", "done"):
        return "final"
    fb = (fallback or "final").strip().lower()
    return fb if fb in ("live", "final") else "final"


def query_auction_stock(
    db: Session,
    code: str,
    *,
    trade_date: Optional[str] = None,
    auction_phase: str = "final",
    live: bool = False,
) -> Dict[str, Any]:
    """单股集合竞价。

    默认 ``live=False``：**只读本地库**，不请求 Fuyao（避免分析页并发打满限流 429）。
    ``live=True`` 时才拉实时快照；失败时若库中有当日记录则回退到库数据。
    """
    stock_code = norm_code(code)
    if not stock_code:
        return {"success": False, "message": "无效股票代码"}

    day = (trade_date or sh_today())[:10]
    phase = normalize_auction_phase(auction_phase, fallback="final")

    row = db.execute(
        text(
            """
            SELECT *
            FROM stock_auction_daily
            WHERE trade_date = :trade_date AND code = :code AND auction_phase = :auction_phase
            """
        ),
        {"trade_date": day, "code": stock_code, "auction_phase": phase},
    ).fetchone()

    # 兼容历史/接口返回 closed 等阶段名落库的情况
    if not row:
        row = db.execute(
            text(
                """
                SELECT *
                FROM stock_auction_daily
                WHERE trade_date = :trade_date AND code = :code
                ORDER BY
                    CASE auction_phase
                        WHEN 'final' THEN 0
                        WHEN 'closed' THEN 1
                        WHEN 'live' THEN 2
                        ELSE 3
                    END,
                    updated_at DESC NULLS LAST
                LIMIT 1
                """
            ),
            {"trade_date": day, "code": stock_code},
        ).fetchone()

    if row and not live:
        data = _row_to_dict(row)
        data["source_mode"] = "db"
        return {"success": True, "data": data}

    # 非 live：库无无当日该股数据则直接返回，不打外部接口
    if not live:
        return {
            "success": False,
            "message": f"库中暂无 {day} 集合竞价数据，请先在行情中心采集或开启实时拉取",
            "trade_date": day,
            "code": stock_code,
        }

    result = fetch_a_share_auction_snapshot([stock_code], stage=phase)
    if not result.get("ok"):
        if row:
            data = _row_to_dict(row)
            data["source_mode"] = "db"
            data["live_error"] = result.get("error")
            return {"success": True, "data": data}
        err = result.get("error") or "auction_failed"
        if str(err).startswith("http_429") or str(err) == "429":
            err = "实时接口限流(429)，且库中无当日该股数据；请稍后重试或先全市场采集"
        return {"success": False, "message": err}

    items = result.get("items") or []
    if not items:
        if row:
            data = _row_to_dict(row)
            data["source_mode"] = "db"
            return {"success": True, "data": data}
        return {"success": False, "message": "暂无集合竞价数据"}

    store_phase = normalize_auction_phase(result.get("auction_phase"), fallback=phase)
    record = auction_item_to_record(items[0])
    record.update(
        {
            "trade_date": ms_to_sh_date(result.get("timestamp")) or day,
            "auction_phase": store_phase,
            "data_status": result.get("data_status"),
            "response_timestamp": result.get("timestamp"),
            "source_mode": "fuyao",
        }
    )

    try:
        persist_auction_items(
            record["trade_date"],
            store_phase,
            [record],
            data_status=record.get("data_status"),
            response_timestamp=record.get("response_timestamp"),
            db=db,
        )
    except Exception:
        logger.exception("单股集合竞价落库失败 code=%s", stock_code)

    return {"success": True, "data": record}
