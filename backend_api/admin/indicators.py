"""
指标数据管理API模块
提供MA、MACD、RSI、KDJ等指标数据的查询接口
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, or_
from datetime import datetime
import asyncio
import traceback

from backend_api.models import (
    MAIndicators, MACDIndicators, RSIIndicators, KDJIndicators, BOLLIndicators, 
    MAVOLIndicators, MeanFrequencyResonanceIndicators, HistoricalQuotes, HistoricalQuotesHK, User
)
from backend_api.database import get_db
from backend_api.auth import get_current_admin, get_current_user

router = APIRouter(prefix="/api/admin/indicators", tags=["admin_indicators"])

def paginate_query(query, page, page_size):
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    
    # 处理 nan 值
    import math
    def clean_item(item):
        if not item:
            return item
        d = item.__dict__.copy()
        if '_sa_instance_state' in d:
            del d['_sa_instance_state']
        for key, value in d.items():
            if isinstance(value, float) and math.isnan(value):
                d[key] = None
        return d
    
    cleaned_items = [clean_item(item) for item in items]
    
    return {
        "items": cleaned_items,
        "total": total,
        "page": page,
        "page_size": page_size
    }

@router.get("/ma")
async def get_ma_indicators(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    code: Optional[str] = None,
    market_type: Optional[str] = Query(None, description="CN 或 HK"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """查询 MA 移动平均线指标"""
    query = db.query(MAIndicators)
    
    if code:
        query = query.filter(MAIndicators.code == code)
    if market_type:
        query = query.filter(MAIndicators.market_type == market_type)
    if start_date:
        query = query.filter(MAIndicators.date >= start_date)
    if end_date:
        query = query.filter(MAIndicators.date <= end_date)
        
    query = query.order_by(desc(MAIndicators.date), MAIndicators.code)
    result = paginate_query(query, page, page_size)
    
    return {
        "success": True,
        "data": result["items"],
        "total": result["total"],
        "page": page,
        "page_size": page_size
    }

@router.get("/macd")
async def get_macd_indicators(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    code: Optional[str] = None,
    market_type: Optional[str] = Query(None, description="CN 或 HK"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """查询 MACD 指标"""
    query = db.query(MACDIndicators)
    
    if code:
        query = query.filter(MACDIndicators.code == code)
    if market_type:
        # MACD 模型的 market_type 字段在 models.py 中似乎叫 market_type，
        # 但在有些地方可能叫别的。检查 models.py 发现是 market_type。
        query = query.filter(MACDIndicators.market_type == market_type)
    if start_date:
        query = query.filter(MACDIndicators.date >= start_date)
    if end_date:
        query = query.filter(MACDIndicators.date <= end_date)
        
    query = query.order_by(desc(MACDIndicators.date), MACDIndicators.code)
    result = paginate_query(query, page, page_size)
    
    return {
        "success": True,
        "data": result["items"],
        "total": result["total"],
        "page": page,
        "page_size": page_size
    }

@router.get("/rsi")
async def get_rsi_indicators(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    code: Optional[str] = None,
    market_type: Optional[str] = Query(None, description="CN 或 HK"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """查询 RSI 指标"""
    query = db.query(RSIIndicators)
    
    if code:
        query = query.filter(RSIIndicators.code == code)
    if market_type:
        query = query.filter(RSIIndicators.market_type == market_type)
    if start_date:
        query = query.filter(RSIIndicators.date >= start_date)
    if end_date:
        query = query.filter(RSIIndicators.date <= end_date)
        
    query = query.order_by(desc(RSIIndicators.date), RSIIndicators.code)
    result = paginate_query(query, page, page_size)
    
    return {
        "success": True,
        "data": result["items"],
        "total": result["total"],
        "page": page,
        "page_size": page_size
    }

@router.get("/kdj")
async def get_kdj_indicators(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    code: Optional[str] = None,
    market_type: Optional[str] = Query(None, description="CN 或 HK"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """查询 KDJ 指标"""
    query = db.query(KDJIndicators)
    
    if code:
        query = query.filter(KDJIndicators.code == code)
    if market_type:
        query = query.filter(KDJIndicators.market_type == market_type)
    if start_date:
        query = query.filter(KDJIndicators.date >= start_date)
    if end_date:
        query = query.filter(KDJIndicators.date <= end_date)
        
    query = query.order_by(desc(KDJIndicators.date), KDJIndicators.code)
    result = paginate_query(query, page, page_size)
    
    return {
        "success": True,
        "data": result["items"],
        "total": result["total"],
        "page": page,
        "page_size": page_size
    }

@router.get("/boll")
async def get_boll_indicators(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    code: Optional[str] = None,
    market_type: Optional[str] = Query(None, description="CN 或 HK"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """查询 BOLL 布林带指标"""
    query = db.query(BOLLIndicators)
    
    if code:
        query = query.filter(BOLLIndicators.code == code)
    if market_type:
        query = query.filter(BOLLIndicators.market_type == market_type)
    if start_date:
        query = query.filter(BOLLIndicators.date >= start_date)
    if end_date:
        query = query.filter(BOLLIndicators.date <= end_date)
        
    query = query.order_by(desc(BOLLIndicators.date), BOLLIndicators.code)
    result = paginate_query(query, page, page_size)
    
    return {
        "success": True,
        "data": result["items"],
        "total": result["total"],
        "page": page,
        "page_size": page_size
    }

@router.get("/mavol")
async def get_mavol_indicators(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    code: Optional[str] = None,
    market_type: Optional[str] = Query(None, description="CN 或 HK"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """查询 MAVOL 成交量移动平均线指标"""
    query = db.query(MAVOLIndicators)
    
    if code:
        query = query.filter(MAVOLIndicators.code == code)
    if market_type:
        query = query.filter(MAVOLIndicators.market_type == market_type)
    if start_date:
        query = query.filter(MAVOLIndicators.date >= start_date)
    if end_date:
        query = query.filter(MAVOLIndicators.date <= end_date)
        
    query = query.order_by(desc(MAVOLIndicators.date), MAVOLIndicators.code)
    result = paginate_query(query, page, page_size)
    
    return {
        "success": True,
        "data": result["items"],
        "total": result["total"],
        "page": page,
        "page_size": page_size
    }

@router.get("/pvfrs")
async def get_pvfrs_indicators(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    code: Optional[str] = None,
    market_type: Optional[str] = Query(None, description="CN 或 HK"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """查询 PVFRS 均值频率共振指标"""
    query = db.query(MeanFrequencyResonanceIndicators)
    
    if code:
        query = query.filter(MeanFrequencyResonanceIndicators.code == code)
    if market_type:
        query = query.filter(MeanFrequencyResonanceIndicators.market_type == market_type)
    if start_date:
        query = query.filter(MeanFrequencyResonanceIndicators.date >= start_date)
    if end_date:
        query = query.filter(MeanFrequencyResonanceIndicators.date <= end_date)
        
    query = query.order_by(desc(MeanFrequencyResonanceIndicators.date), MeanFrequencyResonanceIndicators.code)
    result = paginate_query(query, page, page_size)
    
    return {
        "success": True,
        "data": result["items"],
        "total": result["total"],
        "page": page,
        "page_size": page_size
    }

@router.get("/details")
async def get_indicator_details(
    code: str = Query(..., description="股票代码"),
    date: str = Query(..., description="日期 YYYY-MM-DD"),
    market_type: str = Query("CN", description="CN 或 HK"),
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """查询指定股票和日期的所有指标数据"""
    
    # helper to process query result to dict or None
    def row_to_dict(row):
        if not row:
            return None
        d = row.__dict__.copy()
        if '_sa_instance_state' in d:
            del d['_sa_instance_state']
        
        # 处理 nan 值，将其转换为 None
        import math
        for key, value in d.items():
            if isinstance(value, float) and math.isnan(value):
                d[key] = None
        
        return d

    # Run queries
    ma_data = db.query(MAIndicators).filter_by(code=code, date=date, market_type=market_type).first()
    macd_data = db.query(MACDIndicators).filter_by(code=code, date=date, market_type=market_type).first()
    kdj_data = db.query(KDJIndicators).filter_by(code=code, date=date, market_type=market_type).first()
    rsi_data = db.query(RSIIndicators).filter_by(code=code, date=date, market_type=market_type).first()
    boll_data = db.query(BOLLIndicators).filter_by(code=code, date=date, market_type=market_type).first()
    mavol_data = db.query(MAVOLIndicators).filter_by(code=code, date=date, market_type=market_type).first()
    pvfrs_data = db.query(MeanFrequencyResonanceIndicators).filter_by(code=code, date=date, market_type=market_type).first()

    return {
        "success": True,
        "data": {
            "code": code,
            "date": date,
            "market_type": market_type,
            "ma": row_to_dict(ma_data),
            "macd": row_to_dict(macd_data),
            "kdj": row_to_dict(kdj_data),
            "rsi": row_to_dict(rsi_data),
            "boll": row_to_dict(boll_data),
            "mavol": row_to_dict(mavol_data),
            "pvfrs": row_to_dict(pvfrs_data)
        }
    }

@router.get("/history")
async def get_indicator_history(
    code: str = Query(..., description="股票代码"),
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    market_type: str = Query("CN", description="CN 或 HK"),
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """查询指定股票和日期范围的所有指标数据"""
    
    # 辅助函数：将查询结果转换为以日期为键的字典
    def list_to_date_dict(items):
        result = {}
        for item in items:
            d = item.__dict__.copy()
            if '_sa_instance_state' in d:
                del d['_sa_instance_state']
            
            # 确保日期格式一致
            date_key = str(d.get('date'))
            result[date_key] = d
        return result

    # 并行查询所有指标表
    # 注意：这里假设数据量不大（单只股票一段时间），直接全部查询后在内存合并
    
    # 1. MA
    ma_items = db.query(MAIndicators).filter(
        MAIndicators.code == code,
        MAIndicators.date >= start_date,
        MAIndicators.date <= end_date,
        MAIndicators.market_type == market_type
    ).all()
    ma_dict = list_to_date_dict(ma_items)
    
    # 2. MACD
    macd_items = db.query(MACDIndicators).filter(
        MACDIndicators.code == code,
        MACDIndicators.date >= start_date,
        MACDIndicators.date <= end_date,
        MACDIndicators.market_type == market_type
    ).all()
    macd_dict = list_to_date_dict(macd_items)
    
    # 3. KDJ
    kdj_items = db.query(KDJIndicators).filter(
        KDJIndicators.code == code,
        KDJIndicators.date >= start_date,
        KDJIndicators.date <= end_date,
        KDJIndicators.market_type == market_type
    ).all()
    kdj_dict = list_to_date_dict(kdj_items)
    
    # 4. RSI
    rsi_items = db.query(RSIIndicators).filter(
        RSIIndicators.code == code,
        RSIIndicators.date >= start_date,
        RSIIndicators.date <= end_date,
        RSIIndicators.market_type == market_type
    ).all()
    rsi_dict = list_to_date_dict(rsi_items)
    
    # 5. BOLL
    boll_items = db.query(BOLLIndicators).filter(
        BOLLIndicators.code == code,
        BOLLIndicators.date >= start_date,
        BOLLIndicators.date <= end_date,
        BOLLIndicators.market_type == market_type
    ).all()
    boll_dict = list_to_date_dict(boll_items)
    
    # 6. MAVOL
    mavol_items = db.query(MAVOLIndicators).filter(
        MAVOLIndicators.code == code,
        MAVOLIndicators.date >= start_date,
        MAVOLIndicators.date <= end_date,
        MAVOLIndicators.market_type == market_type
    ).all()
    mavol_dict = list_to_date_dict(mavol_items)
    
    # 7. PVFRS
    pvfrs_items = db.query(MeanFrequencyResonanceIndicators).filter(
        MeanFrequencyResonanceIndicators.code == code,
        MeanFrequencyResonanceIndicators.date >= start_date,
        MeanFrequencyResonanceIndicators.date <= end_date,
        MeanFrequencyResonanceIndicators.market_type == market_type
    ).all()
    pvfrs_dict = list_to_date_dict(pvfrs_items)
    
    # 收集所有涉及的日期
    all_dates = set()
    all_dates.update(ma_dict.keys())
    all_dates.update(macd_dict.keys())
    all_dates.update(kdj_dict.keys())
    all_dates.update(rsi_dict.keys())
    all_dates.update(boll_dict.keys())
    all_dates.update(mavol_dict.keys())
    all_dates.update(pvfrs_dict.keys())
    
    # 排序日期（降序，最近的在前）
    sorted_dates = sorted(list(all_dates), reverse=True)
    
    # 构建最终列表
    result_list = []
    for date in sorted_dates:
        result_list.append({
            "code": code,
            "date": date,
            "market_type": market_type,
            "ma": ma_dict.get(date),
            "macd": macd_dict.get(date),
            "kdj": kdj_dict.get(date),
            "rsi": rsi_dict.get(date),
            "boll": boll_dict.get(date),
            "mavol": mavol_dict.get(date),
            "pvfrs": pvfrs_dict.get(date)
        })
        
    return {
        "success": True,
        "data": result_list,
        "total": len(result_list)
    }

@router.post("/generate")
async def generate_indicators(
    request: Dict[str, Any],
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """生成指定股票的指标数据"""
    code = request.get("code")
    market_type = request.get("market_type")
    indicators = request.get("indicators", [])
    
    if not code or not market_type or not indicators:
        return {
            "success": False,
            "message": "参数不完整，需要股票代码、市场类型和指标列表"
        }
    
    results = {}
    
    try:
        # 导入指标计算器和pandas
        import pandas as pd
        from backend_core.utils.ma_calculator import MACalculator
        from backend_core.utils.mavol_calculator import MAVOLCalculator
        from backend_core.utils.macd_calculator import MACDCalculator
        from backend_core.utils.kdj_calculator import KDJCalculator
        from backend_core.utils.rsi_calculator import RSICalculator
        from backend_core.utils.boll_calculator import BOLLCalculator
        from backend_core.utils.mean_frequency_calculator import MeanFrequencyResonanceCalculator
        
        # 从数据库获取历史数据
        if market_type == "CN":
            # A股历史数据
            historical_data = db.query(HistoricalQuotes).filter(
                HistoricalQuotes.code == code
            ).order_by(HistoricalQuotes.date).all()
        else:  # HK
            # 港股历史数据
            historical_data = db.query(HistoricalQuotesHK).filter(
                HistoricalQuotesHK.code == code
            ).order_by(HistoricalQuotesHK.date).all()
        
        # 转换为DataFrame
        historical_data = pd.DataFrame([{
            'date': item.date,
            'open': item.open,
            'high': item.high,
            'low': item.low,
            'close': item.close,
            'volume': item.volume
        } for item in historical_data])
        
        if historical_data.empty:
            return {
                "success": False,
                "message": f"数据库中没有股票 {code} 的历史数据"
            }
        
        # 生成各个指标
        for indicator in indicators:
            try:
                if indicator == "ma":
                    ma_data = MACalculator.calculate_ma_for_dataframe(historical_data)
                    # 保存到数据库
                    for _, row in ma_data.iterrows():
                        db_ma = MAIndicators(
                            code=code,
                            date=row['date'],
                            market_type=market_type,
                            ma5=row['ma5'],
                            ma10=row['ma10'],
                            ma20=row['ma20'],
                            ma30=row['ma30'],
                            ma60=row['ma60'],
                            ma120=row['ma120'],
                            ma200=row['ma200']
                        )
                        db.merge(db_ma)
                    db.commit()
                    results[indicator] = {"success": True, "count": len(ma_data)}
                    
                elif indicator == "mavol":
                    calculator = MAVOLCalculator()
                    mavol_data = calculator.calculate_mavol_for_dataframe(historical_data)
                    # 保存到数据库
                    for _, row in mavol_data.iterrows():
                        db_mavol = MAVOLIndicators(
                            code=code,
                            date=row['date'],
                            market_type=market_type,
                            mavol5=row['mavol5'],
                            mavol10=row['mavol10'],
                            mavol20=row['mavol20'],
                            mavol30=row['mavol30'],
                            mavol60=row['mavol60'],
                            mavol120=row['mavol120'],
                            mavol200=row['mavol200']
                        )
                        db.merge(db_mavol)
                    db.commit()
                    results[indicator] = {"success": True, "count": len(mavol_data)}
                    
                elif indicator == "macd":
                    calculator = MACDCalculator()
                    macd_data = calculator.calculate_macd_batch(historical_data['close'].tolist())
                    # 保存到数据库
                    for i, row in enumerate(historical_data.itertuples()):
                        if i < len(macd_data):
                            macd_item = macd_data[i]
                            db_macd = MACDIndicators(
                                code=code,
                                date=row.date,
                                market_type=market_type,
                                dif=macd_item.get('dif'),
                                dea=macd_item.get('dea'),
                                macd=macd_item.get('macd'),
                                ema12=macd_item.get('ema12'),
                                ema26=macd_item.get('ema26')
                            )
                            db.merge(db_macd)
                    db.commit()
                    results[indicator] = {"success": True, "count": len(macd_data)}
                    
                elif indicator == "kdj":
                    calculator = KDJCalculator()
                    kdj_data = calculator.calculate_kdj_batch(
                        historical_data['close'].tolist(),
                        historical_data['high'].tolist(),
                        historical_data['low'].tolist()
                    )
                    # 保存到数据库
                    for i, row in enumerate(historical_data.itertuples()):
                        if i < len(kdj_data):
                            kdj_item = kdj_data[i]
                            db_kdj = KDJIndicators(
                                code=code,
                                date=row.date,
                                market_type=market_type,
                                k=kdj_item.get('k'),
                                d=kdj_item.get('d'),
                                j=kdj_item.get('j'),
                                rsv=kdj_item.get('rsv')
                            )
                            db.merge(db_kdj)
                    db.commit()
                    results[indicator] = {"success": True, "count": len(kdj_data)}
                    
                elif indicator == "rsi":
                    calculator = RSICalculator()
                    rsi_data = calculator.calculate_rsi_batch(historical_data['close'].tolist())
                    # 保存到数据库
                    for i, row in enumerate(historical_data.itertuples()):
                        if i < len(rsi_data):
                            rsi_item = rsi_data[i]
                            db_rsi = RSIIndicators(
                                code=code,
                                date=row.date,
                                market_type=market_type,
                                rsi6=rsi_item.get('rsi6'),
                                rsi12=rsi_item.get('rsi12'),
                                rsi24=rsi_item.get('rsi24')
                            )
                            db.merge(db_rsi)
                    db.commit()
                    results[indicator] = {"success": True, "count": len(rsi_data)}
                    
                elif indicator == "boll":
                    calculator = BOLLCalculator()
                    boll_data = calculator.calculate_boll_for_dataframe(historical_data)
                    # 保存到数据库
                    for _, row in boll_data.iterrows():
                        db_boll = BOLLIndicators(
                            code=code,
                            date=row['date'],
                            market_type=market_type,
                            mid=row['boll_mid'],
                            upper=row['boll_upper'],
                            lower=row['boll_lower']
                        )
                        db.merge(db_boll)
                    db.commit()
                    results[indicator] = {"success": True, "count": len(boll_data)}
                    
                elif indicator == "pvfrs":
                    calculator = MeanFrequencyResonanceCalculator()
                    pvfrs_data = calculator.calculate(
                        historical_data['close'].tolist(),
                        historical_data['volume'].tolist()
                    )
                    # 保存到数据库
                    for i, row in enumerate(historical_data.itertuples()):
                        if i < len(pvfrs_data) and pvfrs_data[i] is not None:
                            pvfrs_item = pvfrs_data[i]
                            db_pvfrs = MeanFrequencyResonanceIndicators(
                                code=code,
                                date=row.date,
                                market_type=market_type,
                                ma20_d=pvfrs_item.get('ma20_d'),
                                mavol20_m=pvfrs_item.get('mavol20_m'),
                                macro_displacement_delta=pvfrs_item.get('macro_displacement_delta'),
                                instant_deviation=pvfrs_item.get('instant_deviation'),
                                efficiency_m20_minus_m=pvfrs_item.get('efficiency_m20_minus_m'),
                                rising_days_z=pvfrs_item.get('rising_days_z'),
                                falling_days_f=pvfrs_item.get('falling_days_f'),
                                bias=pvfrs_item.get('bias')
                            )
                            db.merge(db_pvfrs)
                    db.commit()
                    results[indicator] = {"success": True, "count": len([x for x in pvfrs_data if x is not None])}
                    
            except Exception as e:
                db.rollback()
                results[indicator] = {"success": False, "message": str(e)}
                print(f"Error generating {indicator} for {code}: {str(e)}")
                print(traceback.format_exc())
        
        return {
            "success": True,
            "message": f"成功为股票 {code} 生成指标数据",
            "data": results
        }
        
    except Exception as e:
        db.rollback()
        print(f"Error in generate_indicators: {str(e)}")
        print(traceback.format_exc())
        return {
            "success": False,
            "message": f"生成指标数据失败: {str(e)}"
        }

