# -*- coding: utf-8 -*-
"""SEPA 买点信号定时预计算。

日终按全市场流动性池扫描，把就位、未放量越过、放量突破、远离枢轴、收缩中
全部写入 sepa_signal_trace。选股页默认只展示可执行买点，勾选观察形态时
直接从这份结果里过滤，不再扫全市场。
"""

from __future__ import annotations

import gc
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 入库不截断名单；选股页自己的 top 在读侧生效。
_STORE_TOP = 100_000
# 分批评估时不在批内截断，等全池合并后再按 top 收口。
_BATCH_TOP = 1_000_000


def _env_bool(key: str, default: bool = True) -> bool:
    raw = (os.getenv(key) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "y", "on")


def _merge_funnel(total: Dict[str, int], part: Dict[str, Any]) -> None:
    for key, value in part.items():
        total[key] = int(total.get(key) or 0) + int(value or 0)


def scan_sepa_pool(
    db,
    *,
    end_date: str,
    limit_codes: Optional[int] = None,
    min_avg_amount: float,
    top: int = _STORE_TOP,
    include_forming: bool = False,
    include_extended: bool = False,
    statuses: Optional[List[str]] = None,
    tiers: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """全市场流动性池筛选。相对强度先在全池算完，K 线和两融按批读入、算完即丢。

    分批只为压低峰值内存。排名、漏斗、排序和 top 与一次装入 screen_universe 的结果一致
    （K 线按代码序进入横截面，和 load_bars 的 ORDER BY code 相同）。
    """
    from backend_core.analysis.sepa.bars import rs_rank
    from backend_core.analysis.sepa.loaders import (
        iter_code_batches,
        load_bars,
        load_float_mv,
        load_margin,
        load_momentum_map,
        load_universe,
    )
    from backend_core.analysis.sepa.screener import filter_table_rows, screen_universe, to_table_rows

    pool = load_universe(
        db,
        end_date=end_date,
        limit_codes=limit_codes,
        min_avg_amount=min_avg_amount,
    )
    names = dict(pool.get("names") or {})
    momentum = load_momentum_map(db, pool.get("codes") or [], end_date)
    ordered = sorted(momentum)
    rank_values = rs_rank([momentum[code] for code in ordered])
    ranks = dict(zip(ordered, rank_values))
    del momentum, rank_values
    logger.info("SEPA 相对强度完成 date=%s universe=%s", end_date, len(ordered))

    table_rows: List[Dict[str, Any]] = []
    funnel: Dict[str, int] = {}
    done = 0
    total = len(ordered)
    for batch in iter_code_batches(ordered):
        bars = load_bars(db, batch, end_date)
        used = list(bars)
        margin = load_margin(db, used, end_date) if used else {}
        float_mv = load_float_mv(db, used, end_date) if used else {}
        stats: Dict[str, int] = {}
        hits = screen_universe(
            bars,
            margin_by_code=margin,
            circ_mv_by_code=float_mv,
            names=names,
            top=_BATCH_TOP,
            include_forming=include_forming,
            include_extended=include_extended,
            statuses=statuses,
            tiers=tiers,
            stats=stats,
            ranks=ranks,
        )
        table_rows.extend(to_table_rows(hits))
        _merge_funnel(funnel, stats)
        done += len(batch)
        logger.info(
            "SEPA 预计算进度 %s/%s batch=%s hits=%s",
            done,
            total,
            len(batch),
            len(hits),
        )
        del bars, margin, float_mv, hits, stats
        gc.collect()

    rows = filter_table_rows(
        table_rows,
        top=top,
        include_forming=include_forming,
        include_extended=include_extended,
        statuses=statuses,
        tiers=tiers,
    )
    return {
        "rows": rows,
        "funnel": funnel,
        "universe": int(funnel.get("universe") or 0),
        "pool": pool,
    }


def run_sepa_precompute(
    *,
    trade_date: Optional[str] = None,
    limit_codes: Optional[int] = None,
    min_avg_amount: Optional[float] = None,
) -> dict:
    """扫描并覆盖写入指定交易日。未指定日期时用库内最新行情日。"""
    from backend_api.database import SessionLocal
    from backend_core.analysis.sepa.loaders import DEFAULT_MIN_AVG_AMOUNT, latest_trade_date
    from backend_core.analysis.sepa.trace_store import replace_trace

    if not _env_bool("ENABLE_SEPA_PRECOMPUTE", True):
        logger.info("SEPA 信号预计算已禁用（ENABLE_SEPA_PRECOMPUTE=false）")
        return {"success": True, "skipped": True, "reason": "ENABLE_SEPA_PRECOMPUTE=false"}

    db = SessionLocal()
    started = datetime.now()
    try:
        date_s = (trade_date or latest_trade_date(db) or "")[:10]
        if not date_s:
            return {"success": False, "error": "库内无行情数据"}
        amount = DEFAULT_MIN_AVG_AMOUNT if min_avg_amount is None else float(min_avg_amount)
        scanned = scan_sepa_pool(
            db,
            end_date=date_s,
            limit_codes=limit_codes,
            min_avg_amount=amount,
            top=_STORE_TOP,
            include_forming=True,
            include_extended=True,
        )
        written = replace_trace(
            db,
            trade_date=date_s,
            rows=scanned["rows"],
            universe=scanned["universe"],
            funnel=scanned["funnel"],
            pool=dict(scanned.get("pool") or {}),
        )
        elapsed = (datetime.now() - started).total_seconds()
        logger.info(
            "SEPA 预计算完成 date=%s universe=%s written=%s elapsed=%.1fs",
            date_s,
            scanned["universe"],
            written,
            elapsed,
        )
        return {
            "success": True,
            "skipped": False,
            "trade_date": date_s,
            "universe": scanned["universe"],
            "written": written,
            "funnel": scanned["funnel"],
            "elapsed_sec": elapsed,
        }
    except Exception as e:
        db.rollback()
        logger.exception("SEPA 预计算失败: %s", e)
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def scheduled_sepa_signals_cn():
    """工作日 cron 入口。周末直接返回；失败抛出，便于采集节点标红。"""
    if datetime.now().weekday() >= 5:
        return {"skipped": True, "reason": "周末跳过"}
    if not _env_bool("ENABLE_SEPA_PRECOMPUTE", True):
        return {"skipped": True, "reason": "ENABLE_SEPA_PRECOMPUTE=false"}
    out = run_sepa_precompute()
    if not out.get("success"):
        raise RuntimeError(out.get("error") or "SEPA 预计算失败")
    return out
