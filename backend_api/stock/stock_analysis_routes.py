from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
import logging
from ..database import get_db
from .stock_analysis import StockAnalysisService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analysis", tags=["智能分析"])

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
        # 验证股票代码格式
        if not stock_code or len(stock_code) != 6:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "股票代码格式错误"}
            )
        
        # 创建分析服务
        analysis_service = StockAnalysisService()
        
        # 获取分析结果
        result = analysis_service.get_stock_analysis(stock_code)
        
        if "error" in result:
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
        analysis_service = StockAnalysisService()
        result = analysis_service.get_stock_analysis(stock_code)
        
        if "error" in result:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": result["error"]}
            )
        
        # 只返回技术指标部分
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
        analysis_service = StockAnalysisService()
        result = analysis_service.get_stock_analysis(stock_code)
        
        if "error" in result:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": result["error"]}
            )
        
        # 只返回价格预测部分
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
        analysis_service = StockAnalysisService()
        result = analysis_service.get_stock_analysis(stock_code)
        
        if "error" in result:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": result["error"]}
            )
        
        # 只返回交易建议部分
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

@router.get("/levels/{stock_code}")
async def get_key_levels(
    stock_code: str,
    db: Session = Depends(get_db)
):
    """
    获取关键价位
    
    Args:
        stock_code: 股票代码
        
    Returns:
        支撑位和阻力位
    """
    try:
        analysis_service = StockAnalysisService()
        result = analysis_service.get_stock_analysis(stock_code)
        
        if "error" in result:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": result["error"]}
            )
        
        # 只返回关键价位部分
        levels_data = result["data"]["key_levels"]
        
        return JSONResponse(content={
            "success": True,
            "data": levels_data
        })
        
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
        analysis_service = StockAnalysisService()
        result = analysis_service.get_stock_analysis(stock_code)
        
        if "error" in result:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": result["error"]}
            )
        
        data = result["data"]
        
        # 生成摘要
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