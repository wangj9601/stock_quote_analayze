from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional, Tuple
import logging
from database import get_db
from .stock_analysis import StockAnalysisService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analysis", tags=["智能分析"])

_BATCH_LEVELS_MAX_CODES = 300


class LevelsBatchRequest(BaseModel):
    """批量计算 KDE 支撑/阻力（供选股列表「按前复权计算」等）。"""

    codes: List[str] = Field(default_factory=list, description="股票代码列表")
    adjust: str = Field("qfq", description="价格口径：none 或 qfq")
    max_levels: int = Field(8, ge=1, le=8)
    refresh_factor: bool = False
    factor_source: str = Field(
        "auto",
        description="因子源：auto / sina / baostock",
    )


def _normalize_levels_stock_code(raw: str) -> str:
    """归一化数字代码：港股补齐 5 位，A 股补齐 6 位。"""
    s = str(raw or "").strip()
    if not s:
        return s
    upper = s.upper()
    if upper.startswith(("SH", "SZ")) and len(s) > 2:
        s = s[2:].strip()
    if not s.isdigit():
        return s
    if len(s) == 6 and s[0] in "603":
        return s.zfill(6)
    if len(s) <= 5:
        return s.zfill(5)
    return s.zfill(6)


def resolve_levels_stock_identifier(db: Session, raw: str) -> Dict[str, Any]:
    """
    将用户输入的股票代码或名称解析为唯一代码。

    复用 stock_basic / stock_basic_hk 查询口径（与 /api/stock/list 一致）：
    - 数字代码（可带 SH/SZ 前缀）→ 直接归一化
    - 名称精确匹配唯一 → 直接采用
    - 多条精确/模糊候选 → ambiguous + candidates
    - 找不到 → not_found
    """
    s = str(raw or "").strip()
    if not s:
        return {"status": "not_found", "message": "请输入股票代码或名称", "candidates": []}

    # 兼容「600519 贵州茅台」：首段为代码时优先取代码
    if " " in s or "\t" in s:
        first = s.split(None, 1)[0].strip()
        first_norm = first.upper()
        if first_norm.startswith(("SH", "SZ")) and len(first) > 2:
            first_body = first[2:].strip()
        else:
            first_body = first
        if first_body.isdigit():
            s = first

    upper = s.upper()
    if upper.startswith(("SH", "SZ")) and len(s) > 2:
        s = s[2:].strip()

    if s.isdigit():
        code = _normalize_levels_stock_code(s)
        if len(code) not in (5, 6):
            return {
                "status": "not_found",
                "message": "股票代码格式错误（A股6位，港股5位）",
                "candidates": [],
            }
        return {"status": "ok", "code": code, "name": "", "candidates": []}

    try:
        from models import StockBasicInfo, StockBasicInfoHK
    except Exception:
        from backend_api.models import StockBasicInfo, StockBasicInfoHK

    def _row_item(row) -> Dict[str, str]:
        return {
            "code": str(getattr(row, "code", "") or "").strip(),
            "name": str(getattr(row, "name", "") or "").strip(),
        }

    def _dedupe(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
        seen = set()
        out: List[Dict[str, str]] = []
        for it in items:
            code = it.get("code") or ""
            if not code or code in seen:
                continue
            seen.add(code)
            out.append(it)
        return out

    exact: List[Dict[str, str]] = []
    for Model in (StockBasicInfo, StockBasicInfoHK):
        rows = db.query(Model).filter(Model.name == s).limit(20).all()
        exact.extend(_row_item(r) for r in rows)
    exact = _dedupe(exact)
    if len(exact) == 1:
        return {
            "status": "ok",
            "code": exact[0]["code"],
            "name": exact[0]["name"],
            "candidates": exact,
        }
    if len(exact) > 1:
        return {
            "status": "ambiguous",
            "message": f"名称「{s}」匹配到多只股票，请选择其一",
            "candidates": exact[:15],
        }

    like = f"%{s}%"
    fuzzy: List[Dict[str, str]] = []
    for Model in (StockBasicInfo, StockBasicInfoHK):
        rows = (
            db.query(Model)
            .filter((Model.code.like(like)) | (Model.name.like(like)))
            .limit(20)
            .all()
        )
        fuzzy.extend(_row_item(r) for r in rows)
    fuzzy = _dedupe(fuzzy)
    if len(fuzzy) == 1:
        return {
            "status": "ok",
            "code": fuzzy[0]["code"],
            "name": fuzzy[0]["name"],
            "candidates": fuzzy,
        }
    if len(fuzzy) > 1:
        return {
            "status": "ambiguous",
            "message": f"「{s}」匹配到多只股票，请选择其一或输入完整名称/代码",
            "candidates": fuzzy[:15],
        }
    return {
        "status": "not_found",
        "message": f"未找到股票「{s}」，请检查代码或名称",
        "candidates": [],
    }


def _compute_levels_payload(
    code: str,
    max_levels: int,
    *,
    db: Session,
    adjust: str = "none",
    refresh_factor: bool = False,
    factor_source: str = "auto",
) -> Tuple[int, Dict[str, Any]]:
    """计算单股 KDE 关键价位，返回 (http_status, body)。"""
    try:
        from backend_api.utils.adj_quotes import (
            AdjQuotesError,
            apply_qfq_to_bars,
            ensure_adj_factors,
        )
    except ImportError:
        from utils.adj_quotes import (  # type: ignore
            AdjQuotesError,
            apply_qfq_to_bars,
            ensure_adj_factors,
        )

    adjust_n = str(adjust or "none").strip().lower() or "none"
    if adjust_n not in ("none", "qfq"):
        return 400, {"success": False, "message": "adjust 仅支持 none 或 qfq"}

    # 复用请求 Session，避免 next(get_db) 泄漏
    with StockAnalysisService(db) as analysis_service:
        historical_data = None
        adj_meta = None
        if adjust_n == "qfq":
            if analysis_service._is_hk_stock(code):
                return 400, {
                    "success": False,
                    "message": "前复权计算目前仅支持 A 股，港股暂不支持",
                }
            try:
                from .stock_analysis import KeyLevels

                ensured = ensure_adj_factors(
                    db,
                    code,
                    force_refresh=bool(refresh_factor),
                    factor_source=factor_source or "auto",
                    prefer_db=True,
                )
                raw_bars = analysis_service._get_historical_data(
                    code, days=KeyLevels.KDE_LOOKBACK_MAX
                )
                # apply_qfq_to_bars 要求按日期升序；防御性再排一次
                raw_sorted = sorted(
                    list(raw_bars or []),
                    key=lambda b: str((b or {}).get("date") or ""),
                )
                historical_data = apply_qfq_to_bars(raw_sorted, ensured["factors"])
                adj_meta = {
                    "source": ensured.get("source"),
                    "adj_factor_asof": ensured.get("adj_factor_asof"),
                    "factor_fetched": ensured.get("factor_fetched"),
                    "factor_source": ensured.get("factor_source"),
                }
            except AdjQuotesError as e:
                return 400, {"success": False, "message": e.message}
            except Exception as e:
                logger.exception("前复权因子处理失败 code=%s", code)
                return 500, {"success": False, "message": f"前复权处理失败: {e}"}

        result = analysis_service.get_key_levels_only(
            code,
            max_levels=max_levels,
            historical_data=historical_data,
            price_adjust=adjust_n,
            adj_meta=adj_meta,
        )

        if not result.get("success"):
            if "data" in result:
                return 200, {
                    "success": False,
                    "message": result.get("error") or "无法计算关键价位",
                    "data": result.get("data") or {},
                }
            return 500, {
                "success": False,
                "message": result.get("error") or "获取关键价位失败",
            }

        return 200, {"success": True, "data": result["data"]}


def _levels_response_for_code(
    code: str,
    max_levels: int,
    *,
    db: Session,
    adjust: str = "none",
    refresh_factor: bool = False,
    factor_source: str = "auto",
) -> JSONResponse:
    status, content = _compute_levels_payload(
        code,
        max_levels,
        db=db,
        adjust=adjust,
        refresh_factor=refresh_factor,
        factor_source=factor_source,
    )
    return JSONResponse(status_code=status, content=content)


def _normalize_batch_codes(raw_codes: List[str]) -> List[str]:
    """去重并归一化代码，保持原序。"""
    seen = set()
    out: List[str] = []
    for raw in raw_codes or []:
        s = str(raw or "").strip()
        if not s:
            continue
        code = _normalize_levels_stock_code(s)
        if not code or code in seen:
            continue
        if code.isdigit() and len(code) not in (5, 6):
            continue
        seen.add(code)
        out.append(code)
    return out

@router.get("/stock/{stock_code}")
async def get_stock_analysis(
    stock_code: str,
    db: Session = Depends(get_db)
):
    """
    获取股票智能分析结果
    
    Args:
        stock_code: 股票代码
        
    Returns:
        包含技术指标、价格预测、交易建议、关键价位的分析结果
    """
    try:
        # 验证股票代码格式（A股6位，港股5位）
        if not stock_code or (len(stock_code) != 6 and len(stock_code) != 5):
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "股票代码格式错误（A股6位，港股5位）"}
            )
        
        with StockAnalysisService() as analysis_service:
            result = analysis_service.get_stock_analysis(stock_code)

            # 如果返回结果中包含error，但同时也包含data，说明是数据不足的情况，应该返回200但success为False
            if "error" in result and "data" in result:
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": False,
                        "message": result.get("error", "无法获取历史数据"),
                        "data": result.get("data", {})
                    }
                )
            elif "error" in result:
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": result["error"]}
                )

            return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"获取股票分析失败: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"分析失败: {str(e)}"}
        )

@router.get("/technical/{stock_code}")
async def get_technical_indicators(
    stock_code: str,
    db: Session = Depends(get_db)
):
    """
    获取股票技术指标
    
    Args:
        stock_code: 股票代码
        
    Returns:
        技术指标数据（RSI、MACD、KDJ、布林带）
    """
    try:
        with StockAnalysisService() as analysis_service:
            result = analysis_service.get_stock_analysis(stock_code)

            if "error" in result:
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": result["error"]}
                )

            technical_data = result["data"]["technical_indicators"]

            return JSONResponse(content={
                "success": True,
                "data": technical_data
            })

    except Exception as e:
        logger.error(f"获取技术指标失败: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"获取技术指标失败: {str(e)}"}
        )

@router.get("/prediction/{stock_code}")
async def get_price_prediction(
    stock_code: str,
    days: int = Query(30, description="预测天数", ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    获取股票价格预测
    
    Args:
        stock_code: 股票代码
        days: 预测天数（1-365天）
        
    Returns:
        价格预测结果
    """
    try:
        with StockAnalysisService() as analysis_service:
            result = analysis_service.get_stock_analysis(stock_code)

            if "error" in result:
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": result["error"]}
                )

            prediction_data = result["data"]["price_prediction"]

            return JSONResponse(content={
                "success": True,
                "data": prediction_data
            })

    except Exception as e:
        logger.error(f"获取价格预测失败: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"获取价格预测失败: {str(e)}"}
        )

@router.get("/recommendation/{stock_code}")
async def get_trading_recommendation(
    stock_code: str,
    db: Session = Depends(get_db)
):
    """
    获取交易建议
    
    Args:
        stock_code: 股票代码
        
    Returns:
        交易建议和风险分析
    """
    try:
        with StockAnalysisService() as analysis_service:
            result = analysis_service.get_stock_analysis(stock_code)

            if "error" in result:
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": result["error"]}
                )

            recommendation_data = result["data"]["trading_recommendation"]

            return JSONResponse(content={
                "success": True,
                "data": recommendation_data
            })

    except Exception as e:
        logger.error(f"获取交易建议失败: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"获取交易建议失败: {str(e)}"}
        )

@router.get("/levels")
async def get_key_levels_by_query(
    q: str = Query(..., description="股票代码或名称"),
    max_levels: int = Query(8, description="每侧最多返回档位数", ge=1, le=8),
    adjust: str = Query("none", description="价格口径：none=不复权，qfq=前复权现算"),
    refresh_factor: bool = Query(False, description="强制重新拉取复权因子"),
    factor_source: str = Query(
        "auto",
        description="因子源：auto=归一化新浪优先BaoStock备用，sina=仅归一化新浪，baostock=仅BaoStock",
    ),
    db: Session = Depends(get_db),
):
    """按 query 参数 q（代码或名称）计算 KDE 支撑/压力位。"""
    return await get_key_levels(
        stock_code=q,
        max_levels=max_levels,
        adjust=adjust,
        refresh_factor=refresh_factor,
        factor_source=factor_source,
        db=db,
    )


@router.post("/levels/batch")
async def get_key_levels_batch(
    body: LevelsBatchRequest,
    db: Session = Depends(get_db),
):
    """
    批量计算 KDE 支撑/阻力。

    供 URT/RPE 等选股列表「按前复权计算」：只刷新支撑/阻力口径，不改写策略信号与得分。
    单股失败不影响其它代码；港股在 adjust=qfq 时记为失败项。
    """
    codes = _normalize_batch_codes(body.codes)
    if not codes:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "请提供至少一个有效股票代码"},
        )
    if len(codes) > _BATCH_LEVELS_MAX_CODES:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": f"单次最多 {_BATCH_LEVELS_MAX_CODES} 只，当前 {len(codes)} 只",
            },
        )

    adjust_n = str(body.adjust or "qfq").strip().lower() or "qfq"
    if adjust_n not in ("none", "qfq"):
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "adjust 仅支持 none 或 qfq"},
        )

    items: List[Dict[str, Any]] = []
    ok_count = 0
    for code in codes:
        status, payload = _compute_levels_payload(
            code,
            int(body.max_levels or 8),
            db=db,
            adjust=adjust_n,
            refresh_factor=bool(body.refresh_factor),
            factor_source=body.factor_source or "auto",
        )
        data = payload.get("data") or {}
        if payload.get("success") and status < 400:
            ok_count += 1
            items.append(
                {
                    "code": code,
                    "success": True,
                    "nearest_support": data.get("nearest_support"),
                    "nearest_resistance": data.get("nearest_resistance"),
                    "support_levels": data.get("support_levels") or [],
                    "resistance_levels": data.get("resistance_levels") or [],
                    "current_price": data.get("current_price"),
                    "price_adjust": data.get("price_adjust") or adjust_n,
                    "message": None,
                }
            )
        else:
            items.append(
                {
                    "code": code,
                    "success": False,
                    "nearest_support": data.get("nearest_support"),
                    "nearest_resistance": data.get("nearest_resistance"),
                    "support_levels": data.get("support_levels") or [],
                    "resistance_levels": data.get("resistance_levels") or [],
                    "current_price": data.get("current_price"),
                    "price_adjust": adjust_n,
                    "message": payload.get("message") or "计算失败",
                }
            )

    return JSONResponse(
        content={
            "success": True,
            "adjust": adjust_n,
            "total": len(codes),
            "ok_count": ok_count,
            "fail_count": len(codes) - ok_count,
            "items": items,
        }
    )


@router.get("/levels/{stock_code}")
async def get_key_levels(
    stock_code: str,
    max_levels: int = Query(8, description="每侧最多返回档位数", ge=1, le=8),
    adjust: str = Query("none", description="价格口径：none=不复权，qfq=前复权现算"),
    refresh_factor: bool = Query(False, description="强制重新拉取复权因子"),
    factor_source: str = Query(
        "auto",
        description="因子源：auto=归一化新浪优先BaoStock备用，sina=仅归一化新浪，baostock=仅BaoStock",
    ),
    db: Session = Depends(get_db)
):
    """
    获取个股 KDE 支撑 / 压力（阻力）位，并附带参考价：

    - classic_levels：ZigZag 锚定 Fib + 经典/Camarilla/ATR Pivot + confluence_zones
    - confluence_zones：多源共振带（与 classic_levels 内一致）
    - volume_profile：固定回看日线 Volume Profile（POC/VAH/VAL）
    - vp_vs_kde：VP 与 KDE 最近支撑/压力对比（辅助参考，不改策略硬门槛）

    轻量接口：只拉日K并复用 RPE 成交量加权 KDE，不跑完整技术分析。
    stock_code 支持 A股/港股代码，或股票名称（精确唯一则直接计算；多候选返回 candidates）。
    adjust=qfq 时按需拉取前复权因子写入 stock_adj_factor（生产默认归一化新浪，备用 BaoStock），
    再对不复权日K现算后计算（KDE/VP/Fib/Pivot 同口径）。
    """
    try:
        resolved = resolve_levels_stock_identifier(db, stock_code)
        status = resolved.get("status")
        if status == "not_found":
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": resolved.get("message") or "未找到匹配的股票",
                    "candidates": [],
                },
            )
        if status == "ambiguous":
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": resolved.get("message") or "匹配到多只股票，请选择",
                    "candidates": resolved.get("candidates") or [],
                },
            )

        code = str(resolved.get("code") or "").strip()
        if not code or (len(code) != 6 and len(code) != 5):
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "股票代码格式错误（A股6位，港股5位）"},
            )

        return _levels_response_for_code(
            code,
            max_levels,
            db=db,
            adjust=adjust,
            refresh_factor=refresh_factor,
            factor_source=factor_source,
        )

    except Exception as e:
        logger.error(f"获取关键价位失败: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"获取关键价位失败: {str(e)}"}
        )

@router.get("/summary/{stock_code}")
async def get_analysis_summary(
    stock_code: str,
    db: Session = Depends(get_db)
):
    """
    获取分析摘要（简化版）
    
    Args:
        stock_code: 股票代码
        
    Returns:
        分析摘要信息
    """
    try:
        with StockAnalysisService() as analysis_service:
            result = analysis_service.get_stock_analysis(stock_code)

            if "error" in result:
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": result["error"]}
                )

            data = result["data"]

            summary = {
                "stock_code": stock_code,
                "current_price": data["current_price"],
                "prediction": {
                    "target_price": data["price_prediction"]["target_price"],
                    "change_percent": data["price_prediction"]["change_percent"],
                    "confidence": data["price_prediction"]["confidence"]
                },
                "recommendation": {
                    "action": data["trading_recommendation"]["action"],
                    "risk_level": data["trading_recommendation"]["risk_level"],
                    "strength": data["trading_recommendation"]["strength"]
                },
                "technical_summary": {
                    "rsi": data["technical_indicators"]["rsi"]["signal"],
                    "macd": data["technical_indicators"]["macd"]["signal"],
                    "kdj": data["technical_indicators"]["kdj"]["signal"]
                },
                "analysis_time": data["analysis_time"]
            }

            return JSONResponse(content={
                "success": True,
                "data": summary
            })

    except Exception as e:
        logger.error(f"获取分析摘要失败: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"获取分析摘要失败: {str(e)}"}
        ) 