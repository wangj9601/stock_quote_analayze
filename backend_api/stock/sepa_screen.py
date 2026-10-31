# -*- coding: utf-8 -*-
"""SEPA 选股接口：趋势模板 + VCP 收缩 + 枢轴点突破 + 两融旁证。

只读接口，不写库；取数全部走 analysis.sepa.loaders（已适配库内三处口径）。

    GET /api/stock/sepa/screen   全市场筛选（按可执行度 + 得分排序）
    GET /api/stock/sepa/{code}   单票明细（含八条趋势逐条判定、收缩序列、两融状态）

口径提醒：突破是技术面提示，不是买入建议；两融为公开数据推断，不代表机构账户归属。
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_core.analysis.sepa import (
    DISCLAIMER,
    SEPAConfig,
    evaluate_stock,
    to_table_rows,
)
from backend_core.analysis.sepa.loaders import (
    cross_section_rs,
    fetch_inputs,
    latest_trade_date,
    load_bars,
    load_float_mv,
    load_margin,
    load_universe,
)
from backend_core.analysis.sepa.screener import screen_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stock", tags=["sepa"])

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CODE_RE = re.compile(r"^\d{6}$")


@router.get("/sepa/screen")
async def get_sepa_screen(
    trade_date: Optional[str] = Query(None, description="交易日 YYYY-MM-DD，缺省取库内最新"),
    limit_codes: int = Query(0, ge=0, le=4000, description="0 表示按成交额取到安全上限；否则取成交额最高的 N 只"),
    top: int = Query(30, ge=1, le=200),
    min_avg_amount: float = Query(50_000_000, ge=0, description="近20日均成交额下限（元），0 表示不设流动性门槛"),
    include_forming: bool = Query(False, description="是否包含仍在收缩、尚未就位的标的"),
    include_extended: bool = Query(False, description="是否包含距枢轴超过 6% 的远离枢轴标的"),
    status: Optional[str] = Query(None, description="形态过滤，逗号分隔：ready,quiet,breakout,forming,extended"),
    tier: Optional[str] = Query(None, description="只返回指定分级 A/B/C"),
    db: Session = Depends(get_db),
):
    if trade_date and not _DATE_RE.match(trade_date):
        return JSONResponse(
            {"success": False, "message": "trade_date 格式应为 YYYY-MM-DD"}, status_code=400
        )
    d = trade_date or latest_trade_date(db)
    if not d:
        return JSONResponse({"success": False, "message": "库内无行情数据"}, status_code=404)

    try:
        statuses = [x.strip() for x in status.split(",") if x.strip()] if status else None
        tiers = [x.strip().upper() for x in tier.split(",") if x.strip()] if tier else None
        inputs = fetch_inputs(
            db,
            end_date=d,
            limit_codes=limit_codes or None,
            min_avg_amount=min_avg_amount,
        )
        report = screen_report(
            inputs["bars"],
            margin_by_code=inputs["margin"],
            circ_mv_by_code=inputs["float_mv"],
            names=inputs.get("names"),
            top=top,
            include_forming=include_forming,
            include_extended=include_extended,
            statuses=statuses,
            tiers=tiers,
        )
        rows = to_table_rows(report["rows"])
        pool = inputs.get("pool") or {}
        return JSONResponse(
            {
                "success": True,
                "data": {
                    "trade_date": d,
                    "universe": len(inputs["codes"]),
                    "count": len(rows),
                    "funnel": report["stats"],
                    "pool": {
                        "min_avg_amount": pool.get("min_avg_amount", min_avg_amount),
                        "amount_start": pool.get("amount_start"),
                        "cap": pool.get("cap"),
                        "exclude_st": pool.get("exclude_st", True),
                    },
                    "rows": rows,
                    "disclaimer": DISCLAIMER,
                },
            }
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("get_sepa_screen")
        return JSONResponse({"success": False, "message": f"筛选失败: {e}"}, status_code=500)


@router.get("/sepa/{code}")
async def get_sepa_detail(
    code: str,
    trade_date: Optional[str] = Query(None, description="交易日 YYYY-MM-DD，缺省取库内最新"),
    rank_universe: int = Query(0, ge=0, le=4000, description="0 表示与筛选同一流动性池；否则取成交额最高的 N 只"),
    rs_rank: Optional[float] = Query(None, description="已有横截面分位时传入，可跳过参照池"),
    db: Session = Depends(get_db),
):
    if not _CODE_RE.match(code or ""):
        return JSONResponse(
            {"success": False, "message": "code 应为 6 位数字（库内不带 .SH/.SZ）"}, status_code=400
        )
    if trade_date and not _DATE_RE.match(trade_date):
        return JSONResponse(
            {"success": False, "message": "trade_date 格式应为 YYYY-MM-DD"}, status_code=400
        )
    d = trade_date or latest_trade_date(db)
    if not d:
        return JSONResponse({"success": False, "message": "库内无行情数据"}, status_code=404)

    try:
        bars = load_bars(db, [code], d)
        if not bars.get(code):
            return JSONResponse({"success": False, "message": f"{code} 无行情数据"}, status_code=404)

        # 相对强度与筛选页同一只流动性池。调用方已有分位时不再扫参照池。
        name_from_pool = ""
        if rs_rank is None:
            pool = load_universe(db, end_date=d, limit_codes=rank_universe or None)
            ref = list(pool["codes"])
            if code not in ref:
                ref.append(code)
            rank = cross_section_rs(db, ref, d)
            rs_value = rank.get(code)
            name_from_pool = pool["names"].get(code) or ""
        else:
            rs_value = rs_rank

        name = name_from_pool or db.execute(
            text("SELECT name FROM stock_basic_info WHERE code = :c LIMIT 1"), {"c": code}
        ).scalar()

        res = evaluate_stock(
            bars[code],
            code=code,
            name=str(name or ""),
            rs_rank=rs_value,
            margin_rows=load_margin(db, [code], d).get(code),
            circ_mv=load_float_mv(db, [code], d).get(code),
            cfg=SEPAConfig(),
        )
        data = to_table_rows([res])[0]
        data.update(
            {
                "trade_date": d,
                "ok": res["ok"],
                "reason": res["reason"],
                "failed": res["failed"],
                "trend": res["trend"],
                "vcp": res["vcp"],
                "margin": res["margin"],
                "disclaimer": DISCLAIMER,
            }
        )
        return JSONResponse({"success": True, "data": data})
    except Exception as e:  # noqa: BLE001
        logger.exception("get_sepa_detail")
        return JSONResponse({"success": False, "message": f"评估失败: {e}"}, status_code=500)
