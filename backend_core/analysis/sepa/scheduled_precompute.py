# -*- coding: utf-8 -*-
"""SEPA 买点信号定时预计算。

日终按全市场流动性池扫描，把就位、未放量越过、放量突破、远离枢轴、收缩中
全部写入 sepa_signal_trace。选股页默认只展示可执行买点，勾选观察形态时
直接从这份结果里过滤，不再扫全市场。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# 入库不截断名单；选股页自己的 top 在读侧生效。
_STORE_TOP = 100_000


def _env_bool(key: str, default: bool = True) -> bool:
    raw = (os.getenv(key) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "y", "on")


def run_sepa_precompute(
    *,
    trade_date: Optional[str] = None,
    limit_codes: Optional[int] = None,
    min_avg_amount: Optional[float] = None,
) -> dict:
    """扫描并覆盖写入指定交易日。未指定日期时用库内最新行情日。"""
    from backend_api.database import SessionLocal
    from backend_core.analysis.sepa import screen_report, to_table_rows
    from backend_core.analysis.sepa.loaders import DEFAULT_MIN_AVG_AMOUNT, fetch_inputs, latest_trade_date
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
        inputs = fetch_inputs(
            db,
            end_date=date_s,
            limit_codes=limit_codes,
            min_avg_amount=amount,
        )
        report = screen_report(
            inputs["bars"],
            margin_by_code=inputs["margin"],
            circ_mv_by_code=inputs["float_mv"],
            names=inputs.get("names"),
            top=_STORE_TOP,
            include_forming=True,
            include_extended=True,
        )
        rows = to_table_rows(report["rows"])
        pool = dict(inputs.get("pool") or {})
        written = replace_trace(
            db,
            trade_date=date_s,
            rows=rows,
            universe=len(inputs.get("codes") or []),
            funnel=report.get("stats") or {},
            pool=pool,
        )
        elapsed = (datetime.now() - started).total_seconds()
        logger.info(
            "SEPA 预计算完成 date=%s universe=%s written=%s elapsed=%.1fs",
            date_s,
            len(inputs.get("codes") or []),
            written,
            elapsed,
        )
        return {
            "success": True,
            "skipped": False,
            "trade_date": date_s,
            "universe": len(inputs.get("codes") or []),
            "written": written,
            "funnel": report.get("stats") or {},
            "elapsed_sec": elapsed,
        }
    except Exception as e:
        db.rollback()
        logger.exception("SEPA 预计算失败: %s", e)
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def scheduled_sepa_signals_cn() -> None:
    """工作日 cron 入口。周末直接返回；失败抛出，便于采集节点标红。"""
    if datetime.now().weekday() >= 5:
        return
    if not _env_bool("ENABLE_SEPA_PRECOMPUTE", True):
        return
    out = run_sepa_precompute()
    if not out.get("success"):
        raise RuntimeError(out.get("error") or "SEPA 预计算失败")
