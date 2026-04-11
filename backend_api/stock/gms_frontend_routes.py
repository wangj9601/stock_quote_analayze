"""
GMS 策略 — 前端公开 API（与 PVFRS 路径完全独立）
前缀: /api/frontend/gms
数据来源：gms_signal_trace 等 GMS 专用存储。
"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import desc, func, or_, text
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_api.models import GMSSignalTrace, MeanFrequencyResonanceIndicators
from backend_api.services.gms_signal_trace_selection import (
    _txt_name_cn,
    _txt_name_hk,
    query_gms_signal_trace_selection,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/frontend/gms", tags=["GMS前端接口"])


@router.get("/selection-results")
async def get_gms_selection_results(
    date: Optional[str] = Query(None, description="目标日期 YYYY-MM-DD，不传则使用 gms_signal_trace 表内最新日期"),
    limit: Optional[int] = Query(None, ge=1, description="最大返回条数"),
    min_strength: float = Query(0.3, ge=0.0, le=1.0, description="最低信号强度 0~1"),
    db: Session = Depends(get_db),
):
    """选股结果列表，数据来自 **gms_signal_trace**。"""
    try:
        payload, fallback_message = query_gms_signal_trace_selection(db, date, min_strength, limit)
        if fallback_message:
            payload["message"] = fallback_message
        return JSONResponse(payload)
    except Exception as e:
        logger.error(f"GMS selection-results 失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取 GMS 选股结果失败: {str(e)}",
        )


@router.get("/selection-summary")
async def get_gms_selection_summary(db: Session = Depends(get_db)):
    """GMS 选股汇总（基于 gms_signal_trace 最新一日）。"""
    try:
        logger.info("获取 GMS 选股汇总 (gms_signal_trace)")
        latest_date = db.query(func.max(GMSSignalTrace.date)).scalar()
        if not latest_date:
            return JSONResponse({
                "success": True,
                "data": {
                    "total_stocks": 0,
                    "strong_signals": 0,
                    "last_update_date": None,
                },
                "strategy_name": "GMS均值引力动量策略",
                "data_source": "gms_signal_trace",
            })

        total_count = db.query(func.count(GMSSignalTrace.code)).filter(
            GMSSignalTrace.date == latest_date
        ).scalar()

        strong_count = db.query(func.count(GMSSignalTrace.code)).filter(
            GMSSignalTrace.date == latest_date,
            or_(
                GMSSignalTrace.score_total >= 70,
                GMSSignalTrace.accumulation_grade == "S",
                GMSSignalTrace.momentum_grade == "全速切入",
            ),
        ).scalar()

        summary_data = {
            "total_stocks": total_count,
            "active_signals": total_count,
            "strong_signals": strong_count,
            "latest_date": latest_date,
            "dimension_stats": {
                "high_accumulation": db.query(func.count(GMSSignalTrace.code)).filter(
                    GMSSignalTrace.date == latest_date,
                    GMSSignalTrace.score_accumulation >= 80,
                ).scalar(),
                "high_momentum": db.query(func.count(GMSSignalTrace.code)).filter(
                    GMSSignalTrace.date == latest_date,
                    GMSSignalTrace.score_momentum >= 80,
                ).scalar(),
            },
        }

        return JSONResponse({
            "success": True,
            "data": summary_data,
            "query_time": datetime.now().isoformat(),
            "strategy_name": "GMS均值引力动量策略",
            "data_source": "gms_signal_trace",
        })
    except Exception as e:
        logger.error(f"获取 GMS 选股汇总失败: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse({
            "success": False,
            "error": f"获取汇总信息失败: {str(e)}",
            "query_time": datetime.now().isoformat(),
            "data_source": "gms_signal_trace",
        })


@router.get("/stock-detail/{symbol}")
async def get_gms_stock_detail(symbol: str, db: Session = Depends(get_db)):
    """单股 GMS 详情，优先读 gms_signal_trace。"""
    try:
        if not symbol:
            raise HTTPException(status_code=400, detail="股票代码不能为空")

        trace = (
            db.query(GMSSignalTrace)
            .filter(GMSSignalTrace.code == symbol)
            .order_by(desc(GMSSignalTrace.date))
            .first()
        )

        if not trace:
            ind = (
                db.query(MeanFrequencyResonanceIndicators)
                .filter(MeanFrequencyResonanceIndicators.code == symbol)
                .order_by(desc(MeanFrequencyResonanceIndicators.date))
                .first()
            )
            if not ind:
                raise HTTPException(status_code=404, detail="未找到该股票的GMS指标数据")
            return JSONResponse({
                "success": True,
                "data": {
                    "symbol": symbol,
                    "date": ind.date,
                    "score_total": 0,
                    "score_accumulation": 0,
                    "score_momentum": 0,
                    "score_balance": 0,
                    "accumulation_grade": "无数据",
                    "momentum_grade": "无数据",
                    "buy_type": "观望",
                    "indicators": {
                        "delta": ind.macro_displacement_delta,
                        "d": ind.ma20_d,
                        "ratio_d20": ind.ratio_d20,
                        "ratio_d1": ind.ratio_d1,
                        "instant_deviation": ind.instant_deviation,
                        "rising_days": ind.rising_days_z,
                        "falling_days": ind.falling_days_f,
                        "avg_volume_20d": ind.mavol20_m,
                    },
                },
                "strategy_name": "GMS均值引力动量策略",
                "data_source": "mean_frequency_resonance_indicators",
            })

        name = symbol
        sym = str(symbol).strip() if symbol is not None else ""
        is_cn = len(sym) >= 6 and sym.isdigit() and sym[0] in "6039"
        if is_cn:
            row = db.execute(_txt_name_cn(), {"code": sym}).fetchone()
        else:
            row = db.execute(_txt_name_hk(), {"code": sym}).fetchone()
        if row and row[0]:
            name = row[0]

        st = trace.score_total or 0
        if st >= 90:
            advice = "强烈推荐"
        elif st >= 75:
            advice = "推荐"
        elif st >= 60:
            advice = "关注"
        else:
            advice = "观望"

        detail_data = {
            "symbol": symbol,
            "name": name,
            "price": trace.d,
            "signal_strength": st / 100.0,
            "investment_advice": advice,
            "analysis_time": trace.date,
            "indicators": {
                "price_dimension": {
                    "macro_displacement": trace.score_accumulation,
                    "instant_deviation": trace.instant_deviation,
                    "avg_price_20d": trace.d,
                    "price_dimension_valid": True,
                },
                "frequency_dimension": {
                    "rising_days": trace.rising_days,
                    "falling_days": trace.falling_days,
                    "frequency_advantage": (trace.falling_days or 0) > (trace.rising_days or 0),
                    "has_false_prosperity": False,
                    "frequency_dimension_valid": True,
                },
                "volume_dimension": {
                    "avg_volume_20d": getattr(trace, "avg_volume_20d", None),
                    "current_volume": getattr(trace, "current_volume", None),
                    "efficiency_ratio": getattr(trace, "score_acc_balance", 0) or 0,
                    "volume_dimension_valid": True,
                },
                "amplitude_ratio": getattr(trace, "fz_ratio", 0),
                "volume_multiplier": getattr(trace, "volume_ratio", 1.0),
                "entry_timing_analysis": {
                    "comprehensive_assessment": {
                        "score": st / 100.0,
                        "optimal_timing": st >= 85,
                        "recommendation": advice,
                    }
                },
            },
            "score_detail": {
                "score_acc_fz": getattr(trace, "score_acc_fz", 0),
                "score_acc_balance": getattr(trace, "score_acc_balance", 0),
                "score_acc_volume": getattr(trace, "score_acc_volume", 0),
                "score_mom_ratio_d1": getattr(trace, "score_mom_ratio_d1", 0),
                "score_mom_deviation": getattr(trace, "score_mom_deviation", 0),
                "score_mom_volume": getattr(trace, "score_mom_volume", 0),
            },
        }

        return JSONResponse({
            "success": True,
            "data": detail_data,
            "strategy_name": "GMS均值引力动量策略",
            "data_source": "gms_signal_trace",
            "timestamp": datetime.now().isoformat(),
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 GMS 股票详情失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
