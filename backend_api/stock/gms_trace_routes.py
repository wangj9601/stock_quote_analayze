"""
GMS 信号追溯 API 路由
提供单只股票从指标表首日到最新日的 GMS 策略信号追溯记录
"""

import logging
from typing import Optional, List
from datetime import datetime
from collections import defaultdict

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_api.models import GMSSignalTrace, MeanFrequencyResonanceIndicators

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stock", tags=["GMS信号追溯"])


def _merge_mfr_d1_d20_into_trace_dict(db: Session, row_dict: dict) -> dict:
    """从 mean_frequency_resonance_indicators 合并 d1、d20 及对应交易日期，与指标表一致。"""
    code = row_dict.get("code")
    date_str = str(row_dict.get("date", ""))[:10]
    market_type = row_dict.get("market_type", "CN")
    if not code or not date_str:
        return row_dict
    row = (
        db.query(MeanFrequencyResonanceIndicators)
        .filter(
            MeanFrequencyResonanceIndicators.code == code,
            MeanFrequencyResonanceIndicators.market_type == market_type,
            MeanFrequencyResonanceIndicators.date == date_str,
        )
        .first()
    )
    if not row:
        return row_dict

    out = dict(row_dict)

    def _norm_date(v):
        if v is None:
            return None
        s = str(v).strip()
        return s[:10] if len(s) >= 10 else s

    if getattr(row, "d1", None) is not None:
        try:
            out["d1"] = float(row.d1)
        except (TypeError, ValueError):
            pass
    if getattr(row, "d20", None) is not None:
        try:
            out["d20"] = float(row.d20)
        except (TypeError, ValueError):
            pass
    vd = getattr(row, "d1_date", None)
    if vd is not None:
        out["d1_date"] = _norm_date(vd)
    vd = getattr(row, "d20_date", None)
    if vd is not None:
        out["d20_date"] = _norm_date(vd)
    return out

try:
    from backend_core.strategies.gms.data_loader import GMSDataLoader
    from backend_core.strategies.gms.strategy_engine import GMSStrategyEngine
    from backend_core.strategies.gms.config import GMSConfigManager
    GMS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"GMS 模块导入失败: {e}")
    GMS_AVAILABLE = False


def _enrich_trace_row_score_detail(db: Session, row_dict: dict, config: dict) -> dict:
    """
    当 trace 记录的得分明细或计算指标为空时，从指标表重新计算并补全。
    用于兼容迁移前写入的历史数据。
    """
    code = row_dict.get("code")
    date_str = str(row_dict.get("date", ""))[:10]
    market_type = row_dict.get("market_type", "CN")
    if not code or not date_str:
        return row_dict
    # 若已有完整得分明细则跳过
    if row_dict.get("score_acc_fz") is not None and row_dict.get("d") is not None:
        return row_dict
    try:
        from backend_core.strategies.gms.indicators_calculator import GMSIndicatorsCalculator

        row = (
            db.query(MeanFrequencyResonanceIndicators)
            .filter(
                MeanFrequencyResonanceIndicators.code == code,
                MeanFrequencyResonanceIndicators.market_type == market_type,
                MeanFrequencyResonanceIndicators.date == date_str,
            )
            .first()
        )
        if not row:
            return row_dict

        delta = getattr(row, "macro_displacement_delta", None)
        d = getattr(row, "ma20_d", None)
        mavol20_m = getattr(row, "mavol20_m", None)
        eff_m20_m = getattr(row, "efficiency_m20_minus_m", None)
        current_volume = (float(mavol20_m or 0) + float(eff_m20_m or 0)) if mavol20_m is not None else 0.0
        volume_ratio = (current_volume / float(mavol20_m)) if mavol20_m not in (None, 0) else None
        calc_row = {
            "code": code,
            "date": date_str,
            "market_type": market_type,
            "macro_displacement_delta": delta,
            "ma20_d": d,
            "ratio_d20": getattr(row, "ratio_d20", None),
            "ratio_d1": getattr(row, "ratio_d1", None),
            "instant_deviation": getattr(row, "instant_deviation", None),
            "rising_days_z": getattr(row, "rising_days_z", 0),
            "falling_days_f": getattr(row, "falling_days_f", 0),
            "mavol20_m": mavol20_m,
            "efficiency_m20_minus_m": eff_m20_m,
            "ratio_d": getattr(row, "bias", None),
            "current_volume": current_volume,
            "volume_ratio": volume_ratio,
            "d1": getattr(row, "d1", None),
            "d1_date": getattr(row, "d1_date", None),
            "d20": getattr(row, "d20", None),
            "d20_date": getattr(row, "d20_date", None),
        }
        stable_days = int(config.get("scoring", {}).get("instant_deviation_stable_days", 3) or 3)
        series_rows = (
            db.query(MeanFrequencyResonanceIndicators.instant_deviation)
            .filter(
                MeanFrequencyResonanceIndicators.code == code,
                MeanFrequencyResonanceIndicators.market_type == market_type,
                MeanFrequencyResonanceIndicators.date <= date_str,
            )
            .order_by(MeanFrequencyResonanceIndicators.date.desc())
            .limit(max(1, stable_days))
            .all()
        )
        series = [float(r[0]) for r in reversed(series_rows) if r and r[0] is not None]
        ind = GMSIndicatorsCalculator(config).calculate(calc_row, instant_deviation_series=series if series else None)
        if not ind:
            return row_dict

        # 补全得分明细与计算指标
        out = dict(row_dict)
        if out.get("score_acc_fz") is None:
            out["score_acc_fz"] = getattr(ind, "score_acc_fz", None)
            out["score_acc_balance"] = getattr(ind, "score_acc_balance", None)
            out["score_acc_volume"] = getattr(ind, "score_acc_volume", None)
            out["acc_fz_judge"] = getattr(ind, "acc_fz_judge", None) or ""
            out["acc_balance_judge"] = getattr(ind, "acc_balance_judge", None) or ""
            out["acc_volume_judge"] = getattr(ind, "acc_volume_judge", None) or ""
        if out.get("score_mom_ratio_d1") is None:
            out["score_mom_ratio_d1"] = getattr(ind, "score_mom_ratio_d1", None)
            out["score_mom_deviation"] = getattr(ind, "score_mom_deviation", None)
            out["score_mom_volume"] = getattr(ind, "score_mom_volume", None)
            out["mom_ratio_d1_judge"] = getattr(ind, "mom_ratio_d1_judge", None) or ""
            out["mom_deviation_judge"] = getattr(ind, "mom_deviation_judge", None) or ""
            out["mom_volume_judge"] = getattr(ind, "mom_volume_judge", None) or ""
        if out.get("delta") is None:
            out["delta"] = ind.delta
            out["d"] = ind.d
            out["ratio_d20"] = ind.ratio_d20
            out["ratio_d1"] = ind.ratio_d1
            out["fz_ratio"] = ind.fz_ratio
            out["volume_ratio"] = ind.volume_ratio
            out["instant_deviation"] = ind.instant_deviation
            out["rising_days"] = ind.rising_days
            out["falling_days"] = ind.falling_days
        if out.get("score_accumulation") is None:
            out["score_accumulation"] = ind.score_accumulation
        if out.get("score_momentum") is None:
            out["score_momentum"] = ind.score_momentum
        if out.get("score_total") is None:
            out["score_total"] = ind.score_total
        if out.get("accumulation_grade") in (None, ""):
            out["accumulation_grade"] = getattr(ind, "accumulation_grade", "") or ""
        if out.get("momentum_grade") in (None, ""):
            out["momentum_grade"] = getattr(ind, "momentum_grade", "") or ""
        if (out.get("signal_strength") is None or out.get("signal_strength") == 0) and ind.score_total and ind.score_total > 0:
            out["signal_strength"] = ind.score_total / 100.0
        return out
    except Exception as e:
        logger.debug("GMS 追溯 enrichment 失败 %s %s: %s", code, date_str, e)
        return row_dict


def _normalize_code(code: str, market_type: str) -> str:
    """港股代码 5 位补零"""
    s = str(code).strip()
    if market_type == "HK" and len(s) < 5 and s.isdigit():
        return s.zfill(5)
    return s


def _infer_market_type(code: str) -> str:
    """按代码规则推断市场：A股/CN、ETF、港股/HK。"""
    s = str(code).strip()
    if len(s) >= 6 and s.isdigit() and s[0] in "6039":
        return "CN"
    if len(s) >= 6 and s.isdigit() and s[0] in "518":
        return "ETF"
    return "HK"


def _compute_gms_trace_for_stock(db: Session, code: str, market_type: str, config: dict) -> int:
    """
    对单只股票从 mean_frequency_resonance_indicators 的首日到最新日执行 GMS 追溯计算，
    并写入 gms_signal_trace 表。
    返回写入条数。
    """
    if not GMS_AVAILABLE:
        raise RuntimeError("GMS 策略模块不可用")

    # 查询该股票所有日期（升序）
    rows = (
        db.query(MeanFrequencyResonanceIndicators.date)
        .filter(
            MeanFrequencyResonanceIndicators.code == code,
            MeanFrequencyResonanceIndicators.market_type == market_type,
        )
        .order_by(MeanFrequencyResonanceIndicators.date.asc())
        .all()
    )
    dates = [str(r.date)[:10] for r in rows if r.date]
    if not dates:
        return 0

    loader = GMSDataLoader(db)
    engine = GMSStrategyEngine(loader, config)
    stable_days = int(config.get("scoring", {}).get("instant_deviation_stable_days", 3))
    codes = [code]
    saved = 0

    for i, target_date in enumerate(dates):
        try:
            # 加载当日指标（精确日期，不用 use_latest）
            rows_data = loader.load_indicators(codes, target_date, market_type, use_latest_per_stock=False)
            if not rows_data:
                continue

            # 加载多日序列（用于站稳3日）
            dev_series_by_code = {}
            if stable_days > 1:
                multi_rows = loader.load_indicators_multi_day(codes, target_date, market_type, days=stable_days)
                by_code = defaultdict(list)
                for r in multi_rows:
                    by_code[r["code"]].append(r)
                for c, code_rows in by_code.items():
                    code_rows.sort(key=lambda x: x["date"])
                    recent = code_rows[-stable_days:]
                    dev_series_by_code[c] = [float(r.get("instant_deviation", 0) or 0) for r in recent]

            row = rows_data[0]
            dev_series = dev_series_by_code.get(code)
            ind = engine.calculator.calculate(row, instant_deviation_series=dev_series)
            if ind is None:
                continue

            left = engine.detector.detect_left_buy(ind)
            right = engine.detector.detect_right_buy(ind)
            sell = engine.detector.detect_sell(ind)
            buy_type = "左侧" if left else ("右侧" if right else "")
            signal_strength = (ind.score_total / 100.0) if ind.score_total and ind.score_total > 0 else 0.0

            rec = GMSSignalTrace(
                code=code,
                date=target_date,
                market_type=market_type,
                score_total=ind.score_total,
                score_accumulation=ind.score_accumulation,
                score_momentum=ind.score_momentum,
                signal_strength=signal_strength,
                buy_type=buy_type or None,
                left_buy_signal=left,
                right_buy_signal=right,
                sell_signal=sell,
                accumulation_grade=getattr(ind, "accumulation_grade", "") or None,
                momentum_grade=getattr(ind, "momentum_grade", "") or None,
                delta=ind.delta,
                d=ind.d,
                ratio_d20=ind.ratio_d20,
                ratio_d1=ind.ratio_d1,
                fz_ratio=ind.fz_ratio,
                volume_ratio=ind.volume_ratio,
                instant_deviation=ind.instant_deviation,
                rising_days=ind.rising_days,
                falling_days=ind.falling_days,
                score_acc_fz=getattr(ind, "score_acc_fz", None),
                score_acc_balance=getattr(ind, "score_acc_balance", None),
                score_acc_volume=getattr(ind, "score_acc_volume", None),
                score_mom_ratio_d1=getattr(ind, "score_mom_ratio_d1", None),
                score_mom_deviation=getattr(ind, "score_mom_deviation", None),
                score_mom_volume=getattr(ind, "score_mom_volume", None),
                acc_fz_judge=getattr(ind, "acc_fz_judge", None) or None,
                acc_balance_judge=getattr(ind, "acc_balance_judge", None) or None,
                acc_volume_judge=getattr(ind, "acc_volume_judge", None) or None,
                mom_ratio_d1_judge=getattr(ind, "mom_ratio_d1_judge", None) or None,
                mom_deviation_judge=getattr(ind, "mom_deviation_judge", None) or None,
                mom_volume_judge=getattr(ind, "mom_volume_judge", None) or None,
            )
            db.merge(rec)
            saved += 1
        except Exception as e:
            logger.warning(f"GMS 追溯 {code} {target_date} 失败: {e}")
            continue

    db.commit()
    return saved


@router.get("/gms-signal-trace")
async def get_gms_signal_trace(
    code: str = Query(..., description="股票代码"),
    start_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    force_compute: Optional[int] = Query(None, description="1 时强制重新计算"),
    db: Session = Depends(get_db),
):
    """
    查询某股票的 GMS 信号追溯记录。
    若表中无该股票记录且未传 force_compute：先执行追溯计算并入库，再返回。
    force_compute=1：重新全量计算后返回。
    """
    if not GMS_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={"success": False, "message": "GMS 策略暂不可用", "data": [], "total": 0},
        )

    code = str(code).strip()
    if not code:
        raise HTTPException(status_code=400, detail="股票代码不能为空")

    # 判断市场类型（A股/ETF/港股）
    market_type = _infer_market_type(code)
    code_norm = _normalize_code(code, market_type)

    try:
        config = GMSConfigManager().get_config()

        if force_compute == 1:
            # 先删除该股票已有追溯记录
            db.query(GMSSignalTrace).filter(
                GMSSignalTrace.code == code_norm,
                GMSSignalTrace.market_type == market_type,
            ).delete()
            db.commit()
            logger.info(f"GMS 追溯 强制重新计算: {code_norm}")
            count = _compute_gms_trace_for_stock(db, code_norm, market_type, config)
            logger.info(f"GMS 追溯 计算完成: {code_norm}, 写入 {count} 条")

        else:
            # 检查是否有记录
            exists = (
                db.query(GMSSignalTrace)
                .filter(
                    GMSSignalTrace.code == code_norm,
                    GMSSignalTrace.market_type == market_type,
                )
                .first()
            )
            if not exists:
                # 检查 mean_frequency_resonance_indicators 是否有该股票数据
                has_mfr = (
                    db.query(MeanFrequencyResonanceIndicators)
                    .filter(
                        MeanFrequencyResonanceIndicators.code == code_norm,
                        MeanFrequencyResonanceIndicators.market_type == market_type,
                    )
                    .first()
                )
                if not has_mfr:
                    return JSONResponse({
                        "success": True,
                        "data": [],
                        "total": 0,
                        "message": "该股票暂无 GMS 指标数据",
                    })
                # 执行追溯计算
                logger.info(f"GMS 追溯 首次计算: {code_norm}")
                count = _compute_gms_trace_for_stock(db, code_norm, market_type, config)
                logger.info(f"GMS 追溯 计算完成: {code_norm}, 写入 {count} 条")

        # 查询返回
        q = (
            db.query(GMSSignalTrace)
            .filter(
                GMSSignalTrace.code == code_norm,
                GMSSignalTrace.market_type == market_type,
            )
        )
        if start_date:
            q = q.filter(GMSSignalTrace.date >= str(start_date)[:10])
        if end_date:
            q = q.filter(GMSSignalTrace.date <= str(end_date)[:10])
        q = q.order_by(GMSSignalTrace.date.desc())
        rows = q.all()

        def to_dict(r):
            return {
                "code": r.code,
                "date": r.date,
                "market_type": r.market_type,
                "score_total": r.score_total,
                "score_accumulation": r.score_accumulation,
                "score_momentum": r.score_momentum,
                "signal_strength": r.signal_strength,
                "buy_type": r.buy_type or "",
                "left_buy_signal": r.left_buy_signal,
                "right_buy_signal": r.right_buy_signal,
                "sell_signal": r.sell_signal,
                "accumulation_grade": r.accumulation_grade or "",
                "momentum_grade": r.momentum_grade or "",
                "delta": r.delta,
                "d": r.d,
                "ratio_d20": r.ratio_d20,
                "ratio_d1": r.ratio_d1,
                "fz_ratio": r.fz_ratio,
                "volume_ratio": r.volume_ratio,
                "instant_deviation": r.instant_deviation,
                "rising_days": r.rising_days,
                "falling_days": r.falling_days,
                "score_acc_fz": getattr(r, "score_acc_fz", None),
                "score_acc_balance": getattr(r, "score_acc_balance", None),
                "score_acc_volume": getattr(r, "score_acc_volume", None),
                "score_mom_ratio_d1": getattr(r, "score_mom_ratio_d1", None),
                "score_mom_deviation": getattr(r, "score_mom_deviation", None),
                "score_mom_volume": getattr(r, "score_mom_volume", None),
                "acc_fz_judge": getattr(r, "acc_fz_judge", None) or "",
                "acc_balance_judge": getattr(r, "acc_balance_judge", None) or "",
                "acc_volume_judge": getattr(r, "acc_volume_judge", None) or "",
                "mom_ratio_d1_judge": getattr(r, "mom_ratio_d1_judge", None) or "",
                "mom_deviation_judge": getattr(r, "mom_deviation_judge", None) or "",
                "mom_volume_judge": getattr(r, "mom_volume_judge", None) or "",
            }

        data = [to_dict(r) for r in rows]
        # 合并指标表中的 d1/d20 与交易日期；再对缺失得分明细的历史记录做 enrichment
        for i, item in enumerate(data):
            merged = _merge_mfr_d1_d20_into_trace_dict(db, item)
            data[i] = _enrich_trace_row_score_detail(db, merged, config)
        return JSONResponse({
            "success": True,
            "data": data,
            "total": len(data),
        })
    except Exception as e:
        logger.exception("GMS 信号追溯查询失败")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": str(e), "data": [], "total": 0},
        )


# ---------- 用户端：单股 GMS 策略回测（复用 admin_interface 任务队列） ----------
try:
    from backend_core.strategies.gms import admin_interface as _gms_admin_if
    from backend_api.admin.gms_admin_routes import _build_task_name_with_stocks as _gms_build_task_name

    _GMS_BACKTEST_AVAILABLE = True
except Exception as _e:
    logger.warning("GMS 回测接口依赖导入失败: %s", _e)
    _gms_admin_if = None  # type: ignore
    _gms_build_task_name = None  # type: ignore
    _GMS_BACKTEST_AVAILABLE = False


class GMSStockBacktestBody(BaseModel):
    """信号追溯页发起的单股回测参数（与管理端 GMS 回测一致，仅允许 single）"""

    code: str = Field(..., description="股票代码")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    market: str = Field("all", description="市场: cn / etf / hk / all")
    target_pct: float = Field(0.05, description="目标涨幅，如 0.05 表示 5%")
    horizon_days: int = Field(20, ge=10, le=30, description="持有窗口交易日数")
    min_score: float = Field(0, ge=0, le=100, description="最低总分（与 GMSFrontendInterface 一致，管理端回测相同）")


@router.post("/gms-backtest")
async def create_gms_stock_backtest(body: GMSStockBacktestBody, db: Session = Depends(get_db)):
    """
    创建单股 GMS 回测任务，返回 task_id。
    与 POST /api/admin/gms/backtests（stock_pool_mode=single）等价，供前端信号追溯页使用。
    """
    if not _GMS_BACKTEST_AVAILABLE or _gms_admin_if is None:
        raise HTTPException(status_code=503, detail="GMS 回测服务暂不可用")
    code = str(body.code).strip()
    if not code:
        raise HTTPException(status_code=400, detail="股票代码不能为空")
    try:
        config = {
            "task_name": None,
            "market": body.market,
            "start_date": str(body.start_date).strip()[:10],
            "end_date": str(body.end_date).strip()[:10],
            "target_pct": float(body.target_pct),
            "horizon_days": int(body.horizon_days),
            "min_score": float(body.min_score),
            "backtest_type": "signal_hit_rate",
            "stop_loss_pct": 0,
            "commission_bps": 0,
            "slippage_bps": 0,
            "stock_pool_mode": "single",
            "stock_code": code,
        }
        task_name = _gms_build_task_name(db, config) if _gms_build_task_name else None
        task_id = _gms_admin_if.create_backtest(config, name=task_name or None)
        return {"success": True, "data": {"task_id": task_id}}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("创建 GMS 单股回测任务失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gms-backtest/{task_id}")
async def get_gms_stock_backtest(task_id: str):
    """查询回测任务状态与结果（与 admin 任务详情一致）。"""
    if not _GMS_BACKTEST_AVAILABLE or _gms_admin_if is None:
        raise HTTPException(status_code=503, detail="GMS 回测服务暂不可用")
    task = _gms_admin_if.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"success": True, "data": task}


@router.post("/gms-backtest/{task_id}/cancel")
async def cancel_gms_stock_backtest(task_id: str):
    """取消回测任务。"""
    if not _GMS_BACKTEST_AVAILABLE or _gms_admin_if is None:
        raise HTTPException(status_code=503, detail="GMS 回测服务暂不可用")
    ok = _gms_admin_if.cancel_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="任务不存在或无法取消")
    return {"success": True}


@router.get("/gms-backtest/{task_id}/export")
async def export_gms_stock_backtest_csv(task_id: str):
    """导出该回测任务明细（新任务为带列宽的 Excel；旧任务可能仍为 CSV）。"""
    if not _GMS_BACKTEST_AVAILABLE or _gms_admin_if is None:
        raise HTTPException(status_code=503, detail="GMS 回测服务暂不可用")
    payload = _gms_admin_if.download_report(task_id)
    if not payload:
        raise HTTPException(status_code=404, detail="明细不存在或任务未完成")
    data, filename, media_type = payload
    from urllib.parse import quote

    disp = f"attachment; filename*=UTF-8''{quote(filename)}"
    return Response(content=data, media_type=media_type, headers={"Content-Disposition": disp})
