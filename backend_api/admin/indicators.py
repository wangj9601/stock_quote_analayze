"""
指标数据管理API模块
提供MA、MACD、RSI、KDJ等指标数据的查询接口
"""

from typing import List, Optional, Dict, Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, or_, text
from datetime import datetime, date
import asyncio
import traceback
from pydantic import BaseModel, Field, model_validator

from backend_api.models import (
    MAIndicators, MACDIndicators, RSIIndicators, KDJIndicators, BOLLIndicators,
    MAVOLIndicators, InfiniteCostIndicators, MeanFrequencyResonanceIndicators, HistoricalQuotes, HistoricalQuotesHK,
    FundHistoricalQuotes, User,
    StockBasicInfo
)
from backend_api.database import get_db
from backend_api.auth import get_current_admin, get_current_user
from backend_api.admin.quotes import (
    _try_append_operation_log,
    _parse_optional_trade_date,
    _normalize_code,
    _normalize_hk_stock_code,
)

router = APIRouter(prefix="/api/admin/indicators", tags=["admin_indicators"])


def _norm_indicator_market(s: Optional[str]) -> str:
    return (s or "").strip().upper()


def _normalize_indicator_code(raw: Any, market_type: Optional[str]) -> str:
    """按市场规范化代码：CN/ETF 用 A 股规则补零；HK 不强制 6 位。"""
    if _norm_indicator_market(market_type) == "HK":
        return _normalize_hk_stock_code(raw)
    return _normalize_code(raw)


class DeleteIndicatorDataBody(BaseModel):
    """删除 MA / MAVOL / PVFRS 等指标表行（按 code + date + market_type 复合主键）。"""

    scope: Literal["single", "all"]
    code: Optional[str] = None
    market_type: Optional[str] = Field(
        None, description="CN、HK 或 ETF；单个标的必选；全部时可限定仅删某市场"
    )
    start_date: Optional[str] = Field(None, description="指标日期下限（含）YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="指标日期上限（含）YYYY-MM-DD")

    @model_validator(mode="after")
    def _validate_indicator_delete(self):
        if self.scope == "single":
            if not (self.code or "").strip():
                raise ValueError("选择「单个标的」时必须填写代码")
            if not (self.market_type or "").strip():
                raise ValueError("选择「单个标的」时必须选择市场类型")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("开始日期不能晚于结束日期")
        return self


def _delete_indicator_rows(
    db: Session,
    model_cls,
    body: DeleteIndicatorDataBody,
    *,
    log_type: str,
    table_human: str,
    current_user: Any,
) -> Dict[str, Any]:
    """按条件删除指标表；date 列为字符串 YYYY-MM-DD。"""
    start = _parse_optional_trade_date("开始日期", body.start_date)
    end = _parse_optional_trade_date("结束日期", body.end_date)
    if start and end and start > end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开始日期不能晚于结束日期")

    q = db.query(model_cls)
    if body.scope == "single":
        mt = _norm_indicator_market(body.market_type)
        if mt not in ("CN", "HK", "ETF"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="市场类型须为 CN、HK 或 ETF")
        c = _normalize_indicator_code(body.code, mt)
        if not c:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="代码无效")
        q = q.filter(model_cls.code == c, model_cls.market_type == mt)
    else:
        if body.market_type:
            mt = _norm_indicator_market(body.market_type)
            if mt not in ("CN", "HK", "ETF"):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="市场类型须为 CN、HK 或 ETF")
            q = q.filter(model_cls.market_type == mt)
    if start:
        q = q.filter(model_cls.date >= start)
    if end:
        q = q.filter(model_cls.date <= end)

    deleted = q.delete(synchronize_session=False)
    db.commit()
    uname = getattr(current_user, "username", None) or "admin"
    _try_append_operation_log(
        db,
        log_type=log_type,
        log_message=(
            f"删除{table_human} scope={body.scope} code={body.code or '-'} "
            f"market={body.market_type or '-'} start={start or '-'} end={end or '-'} by {uname}"
        ),
        affected_count=deleted,
        log_status="成功",
        error_info=None,
    )
    return {"success": True, "data": {"deleted": deleted}, "message": f"已删除 {deleted} 条记录"}


def _fetch_historical_quote_rows(db: Session, code: str, market_type: str):
    """按市场类型加载历史行情 ORM 行列表（日期升序）。不支持的市场类型返回 None。"""
    if market_type == "CN":
        return db.query(HistoricalQuotes).filter(
            HistoricalQuotes.code == code
        ).order_by(HistoricalQuotes.date).all()
    if market_type == "HK":
        return db.query(HistoricalQuotesHK).filter(
            HistoricalQuotesHK.code == code
        ).order_by(HistoricalQuotesHK.date).all()
    if market_type == "ETF":
        return db.query(FundHistoricalQuotes).filter(
            FundHistoricalQuotes.code == code
        ).order_by(FundHistoricalQuotes.date).all()
    return None


def _historical_quotes_to_dataframe(items):
    """从 ORM 行情列表构造 DataFrame；含 turnover_rate 供无穷成本均线（CYC∞）使用。"""
    import pandas as pd

    def _normalize_date_value(value):
        """统一将日期键规范为 YYYY-MM-DD 字符串，避免 varchar/date 比较错误。"""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)[:10]

    return pd.DataFrame(
        [
            {
                "date": _normalize_date_value(item.date),
                "open": item.open,
                "high": item.high,
                "low": item.low,
                "close": item.close,
                "volume": item.volume,
                "amount": getattr(item, "amount", None),
                "turnover_rate": getattr(item, "turnover_rate", None),
            }
            for item in items
        ]
    )


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


def _persist_icost_for_dataframe(
    db: Session,
    code: str,
    market_type: str,
    historical_df,
    *,
    force_replace: bool = False,
) -> int:
    """将无穷成本均线计算结果写入 icost_indicators。

    force_replace：为 True 时先删除该股该市场下已有 icost 全历史再写入，避免残留旧日期/旧算法结果（管理端生成建议 True）。
    """
    from backend_core.utils.infinite_cost_calculator import calculate_infinite_cost_for_dataframe, icost_rows_for_db

    icost_df = calculate_infinite_cost_for_dataframe(historical_df)
    if icost_df.empty:
        return 0
    rows = icost_rows_for_db(icost_df)
    if force_replace:
        db.query(InfiniteCostIndicators).filter(
            InfiniteCostIndicators.code == code,
            InfiniteCostIndicators.market_type == market_type,
        ).delete(synchronize_session=False)
        db.flush()
    n = 0
    for row in rows:
        if not row.get("date"):
            continue
        db_ic = InfiniteCostIndicators(
            code=code,
            date=row["date"],
            market_type=market_type,
            ic_price=row.get("ic_price"),
            cum_amount=row.get("cum_amount"),
            cum_volume=row.get("cum_volume"),
        )
        db.merge(db_ic)
        n += 1
    db.commit()
    return n


@router.get("/ma")
async def get_ma_indicators(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    code: Optional[str] = None,
    market_type: Optional[str] = Query(None, description="CN、HK 或 ETF"),
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
    market_type: Optional[str] = Query(None, description="CN、HK 或 ETF"),
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
    market_type: Optional[str] = Query(None, description="CN、HK 或 ETF"),
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
    market_type: Optional[str] = Query(None, description="CN、HK 或 ETF"),
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
    market_type: Optional[str] = Query(None, description="CN、HK 或 ETF"),
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
    market_type: Optional[str] = Query(None, description="CN、HK 或 ETF"),
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


@router.get("/icost")
async def get_icost_indicators(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    code: Optional[str] = None,
    market_type: Optional[str] = Query(None, description="CN、HK 或 ETF"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """查询无穷成本均线（累计成交均价）指标"""
    query = db.query(InfiniteCostIndicators)

    if code:
        query = query.filter(InfiniteCostIndicators.code == code)
    if market_type:
        query = query.filter(InfiniteCostIndicators.market_type == market_type)
    if start_date:
        query = query.filter(InfiniteCostIndicators.date >= start_date)
    if end_date:
        query = query.filter(InfiniteCostIndicators.date <= end_date)

    query = query.order_by(desc(InfiniteCostIndicators.date), InfiniteCostIndicators.code)
    result = paginate_query(query, page, page_size)

    return {
        "success": True,
        "data": result["items"],
        "total": result["total"],
        "page": page,
        "page_size": page_size,
    }


@router.get("/pvfrs")
async def get_pvfrs_indicators(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    code: Optional[str] = None,
    market_type: Optional[str] = Query(None, description="CN、HK 或 ETF"),
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


@router.post("/ma/delete")
async def delete_ma_indicators(
    body: DeleteIndicatorDataBody,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """删除 MA 表 ma_indicators（按 date 字符串与 market_type）。"""
    return _delete_indicator_rows(
        db,
        MAIndicators,
        body,
        log_type="indicator_ma_delete",
        table_human="MA(ma_indicators)",
        current_user=current_user,
    )


@router.post("/mavol/delete")
async def delete_mavol_indicators(
    body: DeleteIndicatorDataBody,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """删除 MAVOL 表 mavol_indicators。"""
    return _delete_indicator_rows(
        db,
        MAVOLIndicators,
        body,
        log_type="indicator_mavol_delete",
        table_human="MAVOL(mavol_indicators)",
        current_user=current_user,
    )


@router.post("/pvfrs/delete")
async def delete_pvfrs_indicators(
    body: DeleteIndicatorDataBody,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """删除 PVFRS 表 mean_frequency_resonance_indicators。"""
    return _delete_indicator_rows(
        db,
        MeanFrequencyResonanceIndicators,
        body,
        log_type="indicator_pvfrs_delete",
        table_human="PVFRS(mean_frequency_resonance_indicators)",
        current_user=current_user,
    )


@router.get("/details")
async def get_indicator_details(
    code: str = Query(..., description="股票代码"),
    date: str = Query(..., description="日期 YYYY-MM-DD"),
    market_type: str = Query("CN", description="CN、HK 或 ETF"),
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
    market_type: str = Query("CN", description="CN、HK 或 ETF"),
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

@router.post("/generate-batch-watchlist")
async def generate_batch_watchlist_indicators(
    request: Dict[str, Any],
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """批量生成自选股的指标数据"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"[批量生成指标] 收到请求，用户: {current_user.username if hasattr(current_user, 'username') else 'unknown'}")
    indicators = request.get("indicators", [])
    logger.info(f"[批量生成指标] 请求的指标类型: {indicators}")
    
    if not indicators:
        logger.warning("[批量生成指标] 未选择指标类型")
        return {
            "success": False,
            "message": "请选择要生成的指标类型"
        }
    
    try:
        # 导入自选股模型
        from backend_api.models import Watchlist
        
        # 获取所有自选股
        watchlist_stocks = db.query(Watchlist).all()
        logger.info(f"[批量生成指标] 找到 {len(watchlist_stocks)} 只自选股")
        
        if not watchlist_stocks:
            logger.warning("[批量生成指标] 自选股表中没有股票数据")
            return {
                "success": False,
                "message": "自选股表中没有股票数据"
            }
        
        # 导入指标计算器和pandas
        import pandas as pd
        from backend_core.utils.ma_calculator import MACalculator
        from backend_core.utils.mavol_calculator import MAVOLCalculator
        from backend_core.utils.macd_calculator import MACDCalculator
        from backend_core.utils.kdj_calculator import KDJCalculator
        from backend_core.utils.rsi_calculator import RSICalculator
        from backend_core.utils.boll_calculator import BOLLCalculator
        from backend_core.utils.mean_frequency_calculator import MeanFrequencyResonanceCalculator
        
        results = {
            "total_stocks": len(watchlist_stocks),
            "processed_stocks": 0,
            "success_stocks": 0,
            "failed_stocks": 0,
            "indicator_results": {},
            "failed_stocks_detail": []
        }
        
        # 为每个指标初始化统计
        for indicator in indicators:
            results["indicator_results"][indicator] = {
                "success_count": 0,
                "failed_count": 0
            }
        
        # 逐个处理自选股
        logger.info(f"[批量生成指标] 开始处理 {len(watchlist_stocks)} 只股票")
        for idx, stock in enumerate(watchlist_stocks, 1):
            if idx % 10 == 0:
                logger.info(f"[批量生成指标] 已处理 {idx}/{len(watchlist_stocks)} 只股票")
            stock_code = stock.stock_code
            results["processed_stocks"] += 1
            
            try:
                # 判断股票市场类型
                market_type = "CN" if len(stock_code) == 6 else "HK"
                
                # 从数据库获取历史数据
                if market_type == "CN":
                    # A股历史数据
                    historical_data = db.query(HistoricalQuotes).filter(
                        HistoricalQuotes.code == stock_code
                    ).order_by(HistoricalQuotes.date).all()
                else:  # HK
                    # 港股历史数据
                    historical_data = db.query(HistoricalQuotesHK).filter(
                        HistoricalQuotesHK.code == stock_code
                    ).order_by(HistoricalQuotesHK.date).all()
                
                # 转换为DataFrame（含成交额、换手率，供 icost 等）
                historical_df = _historical_quotes_to_dataframe(historical_data)
                
                if historical_df.empty:
                    results["failed_stocks"] += 1
                    results["failed_stocks_detail"].append({
                        "stock_code": stock_code,
                        "stock_name": stock.stock_name,
                        "error": "数据库中没有历史数据"
                    })
                    continue
                
                # 生成各个指标
                stock_success = True
                for indicator in indicators:
                    try:
                        if indicator == "ma":
                            ma_data = MACalculator.calculate_ma_for_dataframe(historical_df)
                            # 保存到数据库
                            for _, row in ma_data.iterrows():
                                db_ma = MAIndicators(
                                    code=stock_code,
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
                            results["indicator_results"][indicator]["success_count"] += 1
                            
                        elif indicator == "mavol":
                            calculator = MAVOLCalculator()
                            mavol_data = calculator.calculate_mavol_for_dataframe(historical_df)
                            # 保存到数据库
                            for _, row in mavol_data.iterrows():
                                db_mavol = MAVOLIndicators(
                                    code=stock_code,
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
                            results["indicator_results"][indicator]["success_count"] += 1
                            
                        elif indicator == "macd":
                            calculator = MACDCalculator()
                            macd_data = calculator.calculate_macd_batch(historical_df['close'].tolist())
                            # 保存到数据库
                            for i, row_data in enumerate(macd_data):
                                if i < len(historical_df):
                                    db_macd = MACDIndicators(
                                        code=stock_code,
                                        date=historical_df.iloc[i]['date'],
                                        market_type=market_type,
                                        dif=row_data.get('dif'),
                                        dea=row_data.get('dea'),
                                        macd=row_data.get('macd')
                                    )
                                    db.merge(db_macd)
                            db.commit()
                            results["indicator_results"][indicator]["success_count"] += 1
                            
                        elif indicator == "kdj":
                            calculator = KDJCalculator()
                            kdj_data = calculator.calculate_kdj_batch(
                                historical_df['close'].tolist(),
                                historical_df['high'].tolist(),
                                historical_df['low'].tolist()
                            )
                            # 保存到数据库
                            for i, row_data in enumerate(kdj_data):
                                if i < len(historical_df):
                                    db_kdj = KDJIndicators(
                                        code=stock_code,
                                        date=historical_df.iloc[i]['date'],
                                        market_type=market_type,
                                        k=row_data.get('k'),
                                        d=row_data.get('d'),
                                        j=row_data.get('j')
                                    )
                                    db.merge(db_kdj)
                            db.commit()
                            results["indicator_results"][indicator]["success_count"] += 1
                            
                        elif indicator == "rsi":
                            calculator = RSICalculator()
                            rsi_data = calculator.calculate_rsi_batch(historical_df['close'].tolist())
                            # 保存到数据库
                            for i, row_data in enumerate(rsi_data):
                                if i < len(historical_df):
                                    db_rsi = RSIIndicators(
                                        code=stock_code,
                                        date=historical_df.iloc[i]['date'],
                                        market_type=market_type,
                                        rsi6=row_data.get('rsi6'),
                                        rsi12=row_data.get('rsi12'),
                                        rsi24=row_data.get('rsi24')
                                    )
                                    db.merge(db_rsi)
                            db.commit()
                            results["indicator_results"][indicator]["success_count"] += 1
                            
                        elif indicator == "boll":
                            calculator = BOLLCalculator()
                            boll_data = calculator.calculate_boll_batch(historical_df['close'].tolist())
                            # 保存到数据库
                            for i, row_data in enumerate(boll_data):
                                if i < len(historical_df):
                                    db_boll = BOLLIndicators(
                                        code=stock_code,
                                        date=historical_df.iloc[i]['date'],
                                        market_type=market_type,
                                        upper=row_data.get('upper'),
                                        mid=row_data.get('mid'),  # 使用正确的字段名
                                        lower=row_data.get('lower')
                                    )
                                    db.merge(db_boll)
                            db.commit()
                            results["indicator_results"][indicator]["success_count"] += 1
                            
                        elif indicator == "pvfrs":
                            calculator = MeanFrequencyResonanceCalculator()
                            # 创建简单的类来模拟ORM对象
                            class HistoryRow:
                                def __init__(self, date, close, volume):
                                    self.date = date
                                    self.close = close
                                    self.volume = volume
                            
                            # 转换数据为ORM对象格式
                            history_rows = []
                            for _, row in historical_df.iterrows():
                                history_rows.append(HistoryRow(row['date'], row['close'], row['volume']))
                            
                            pvfrs_data = calculator.calculate_for_dataframe(history_rows)
                            # 保存到数据库
                            if pvfrs_data.empty:
                                print(f"[PVFRS] 股票 {stock_code} 计算结果为空，跳过")
                                continue
                            
                            for _, row in pvfrs_data.iterrows():
                                try:
                                    db_pvfrs = MeanFrequencyResonanceIndicators(
                                        code=stock_code,
                                        date=row['date'],
                                        market_type=market_type,
                                        macro_displacement_delta=row.get('macro_displacement_delta'),
                                        amplitude=row.get('amplitude'),
                                        ratio_d20=row.get('ratio_d20'),
                                        ratio_d1=row.get('ratio_d1'),
                                        instant_deviation=row.get('instant_deviation'),
                                        rising_days_z=row.get('rising_days_z'),
                                        falling_days_f=row.get('falling_days_f'),
                                        efficiency_m20_minus_m=row.get('efficiency_m20_minus_m'),
                                        ma20_d=row.get('ma20_d'),
                                        mavol20_m=row.get('mavol20_m'),
                                        bias=row.get('bias')
                                    )
                                    db.merge(db_pvfrs)
                                except Exception as e:
                                    print(f"[PVFRS] 保存股票 {stock_code} 数据时出错: {e}")
                                    continue
                            db.commit()
                            results["indicator_results"][indicator]["success_count"] += 1

                        elif indicator == "icost":
                            n = _persist_icost_for_dataframe(
                                db, stock_code, market_type, historical_df, force_replace=True
                            )
                            results["indicator_results"][indicator]["success_count"] += 1
                            
                    except Exception as e:
                        print(f"Error generating {indicator} for {stock_code}: {str(e)}")
                        results["indicator_results"][indicator]["failed_count"] += 1
                        stock_success = False
                
                if stock_success:
                    results["success_stocks"] += 1
                else:
                    results["failed_stocks"] += 1
                    results["failed_stocks_detail"].append({
                        "stock_code": stock_code,
                        "stock_name": stock.stock_name,
                        "error": "部分指标生成失败"
                    })
                    
            except Exception as e:
                print(f"Error processing stock {stock_code}: {str(e)}")
                results["failed_stocks"] += 1
                results["failed_stocks_detail"].append({
                    "stock_code": stock_code,
                    "stock_name": stock.stock_name,
                    "error": str(e)
                })
        
        logger.info(f"[批量生成指标] 处理完成: 成功 {results['success_stocks']} 只，失败 {results['failed_stocks']} 只")
        return {
            "success": True,
            "message": f"成功处理 {results['success_stocks']} 只股票，失败 {results['failed_stocks']} 只",
            "data": results
        }
        
    except Exception as e:
        logger.error(f"[批量生成指标] 发生异常: {str(e)}")
        logger.error(traceback.format_exc())
        print(f"Error in generate_batch_watchlist_indicators: {str(e)}")
        print(traceback.format_exc())
        return {
            "success": False,
            "message": f"批量生成失败: {str(e)}"
        }


@router.post("/generate-batch-all-a-shares")
async def generate_batch_all_a_shares_indicators(
    request: Dict[str, Any],
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """为全部A股批量生成指标数据"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"[批量生成指标-全部A股] 收到请求，用户: {current_user.username if hasattr(current_user, 'username') else 'unknown'}")
    indicators = request.get("indicators", [])
    logger.info(f"[批量生成指标-全部A股] 请求的指标类型: {indicators}")
    
    if not indicators:
        logger.warning("[批量生成指标-全部A股] 未选择指标类型")
        return {
            "success": False,
            "message": "请选择要生成的指标类型"
        }
    
    try:
        # 获取全部A股（过滤 collect_enabled=false 的股票）
        all_a_stocks = db.query(StockBasicInfo).filter(
            text("COALESCE(collect_enabled, TRUE) = TRUE")
        ).all()
        logger.info(f"[批量生成指标-全部A股] 找到 {len(all_a_stocks)} 只A股")
        
        if not all_a_stocks:
            logger.warning("[批量生成指标-全部A股] stock_basic_info 表中没有A股数据")
            return {
                "success": False,
                "message": "stock_basic_info 表中没有A股数据，请先采集股票基础信息"
            }
        
        # 导入指标计算器和pandas
        import pandas as pd
        from backend_core.utils.ma_calculator import MACalculator
        from backend_core.utils.mavol_calculator import MAVOLCalculator
        from backend_core.utils.macd_calculator import MACDCalculator
        from backend_core.utils.kdj_calculator import KDJCalculator
        from backend_core.utils.rsi_calculator import RSICalculator
        from backend_core.utils.boll_calculator import BOLLCalculator
        from backend_core.utils.mean_frequency_calculator import MeanFrequencyResonanceCalculator
        
        results = {
            "total_stocks": len(all_a_stocks),
            "processed_stocks": 0,
            "success_stocks": 0,
            "failed_stocks": 0,
            "indicator_results": {},
            "failed_stocks_detail": []
        }
        
        # 为每个指标初始化统计
        for indicator in indicators:
            results["indicator_results"][indicator] = {
                "success_count": 0,
                "failed_count": 0
            }
        
        # 逐个处理A股
        logger.info(f"[批量生成指标-全部A股] 开始处理 {len(all_a_stocks)} 只股票")
        for idx, stock in enumerate(all_a_stocks, 1):
            if idx % 100 == 0:
                logger.info(f"[批量生成指标-全部A股] 已处理 {idx}/{len(all_a_stocks)} 只股票")
            # code 可能是 int 或 str，统一转为 6 位字符串
            stock_code = str(stock.code).zfill(6) if isinstance(stock.code, int) else str(stock.code)
            stock_name = stock.name or ""
            results["processed_stocks"] += 1
            
            try:
                market_type = "CN"
                
                # 从数据库获取历史数据
                historical_data = db.query(HistoricalQuotes).filter(
                    HistoricalQuotes.code == stock_code
                ).order_by(HistoricalQuotes.date).all()
                
                # 转换为DataFrame（含成交额、换手率，供 icost 等）
                historical_df = _historical_quotes_to_dataframe(historical_data)
                
                if historical_df.empty:
                    results["failed_stocks"] += 1
                    results["failed_stocks_detail"].append({
                        "stock_code": stock_code,
                        "stock_name": stock_name,
                        "error": "数据库中没有历史数据"
                    })
                    continue
                
                # 生成各个指标（与 generate_batch_watchlist 相同逻辑）
                stock_success = True
                for indicator in indicators:
                    try:
                        if indicator == "ma":
                            ma_data = MACalculator.calculate_ma_for_dataframe(historical_df)
                            for _, row in ma_data.iterrows():
                                db_ma = MAIndicators(
                                    code=stock_code,
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
                            results["indicator_results"][indicator]["success_count"] += 1
                            
                        elif indicator == "mavol":
                            calculator = MAVOLCalculator()
                            mavol_data = calculator.calculate_mavol_for_dataframe(historical_df)
                            for _, row in mavol_data.iterrows():
                                db_mavol = MAVOLIndicators(
                                    code=stock_code,
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
                            results["indicator_results"][indicator]["success_count"] += 1
                            
                        elif indicator == "macd":
                            calculator = MACDCalculator()
                            macd_data = calculator.calculate_macd_batch(historical_df['close'].tolist())
                            for i, row_data in enumerate(macd_data):
                                if i < len(historical_df):
                                    db_macd = MACDIndicators(
                                        code=stock_code,
                                        date=historical_df.iloc[i]['date'],
                                        market_type=market_type,
                                        dif=row_data.get('dif'),
                                        dea=row_data.get('dea'),
                                        macd=row_data.get('macd')
                                    )
                                    db.merge(db_macd)
                            db.commit()
                            results["indicator_results"][indicator]["success_count"] += 1
                            
                        elif indicator == "kdj":
                            calculator = KDJCalculator()
                            kdj_data = calculator.calculate_kdj_batch(
                                historical_df['close'].tolist(),
                                historical_df['high'].tolist(),
                                historical_df['low'].tolist()
                            )
                            for i, row_data in enumerate(kdj_data):
                                if i < len(historical_df):
                                    db_kdj = KDJIndicators(
                                        code=stock_code,
                                        date=historical_df.iloc[i]['date'],
                                        market_type=market_type,
                                        k=row_data.get('k'),
                                        d=row_data.get('d'),
                                        j=row_data.get('j')
                                    )
                                    db.merge(db_kdj)
                            db.commit()
                            results["indicator_results"][indicator]["success_count"] += 1
                            
                        elif indicator == "rsi":
                            calculator = RSICalculator()
                            rsi_data = calculator.calculate_rsi_batch(historical_df['close'].tolist())
                            for i, row_data in enumerate(rsi_data):
                                if i < len(historical_df):
                                    db_rsi = RSIIndicators(
                                        code=stock_code,
                                        date=historical_df.iloc[i]['date'],
                                        market_type=market_type,
                                        rsi6=row_data.get('rsi6'),
                                        rsi12=row_data.get('rsi12'),
                                        rsi24=row_data.get('rsi24')
                                    )
                                    db.merge(db_rsi)
                            db.commit()
                            results["indicator_results"][indicator]["success_count"] += 1
                            
                        elif indicator == "boll":
                            calculator = BOLLCalculator()
                            boll_data = calculator.calculate_boll_batch(historical_df['close'].tolist())
                            for i, row_data in enumerate(boll_data):
                                if i < len(historical_df):
                                    db_boll = BOLLIndicators(
                                        code=stock_code,
                                        date=historical_df.iloc[i]['date'],
                                        market_type=market_type,
                                        upper=row_data.get('upper'),
                                        mid=row_data.get('mid'),
                                        lower=row_data.get('lower')
                                    )
                                    db.merge(db_boll)
                            db.commit()
                            results["indicator_results"][indicator]["success_count"] += 1
                            
                        elif indicator == "pvfrs":
                            calculator = MeanFrequencyResonanceCalculator()
                            class HistoryRow:
                                def __init__(self, date, close, volume):
                                    self.date = date
                                    self.close = close
                                    self.volume = volume
                            
                            history_rows = []
                            for _, row in historical_df.iterrows():
                                history_rows.append(HistoryRow(row['date'], row['close'], row['volume']))
                            
                            pvfrs_data = calculator.calculate_for_dataframe(history_rows)
                            if pvfrs_data.empty:
                                continue
                            
                            for _, row in pvfrs_data.iterrows():
                                try:
                                    date_val = row['date']
                                    date_str = date_val.strftime('%Y-%m-%d') if hasattr(date_val, 'strftime') else str(date_val)[:10]
                                    db_pvfrs = MeanFrequencyResonanceIndicators(
                                        code=stock_code,
                                        date=date_str,
                                        market_type=market_type,
                                        macro_displacement_delta=row.get('macro_displacement_delta'),
                                        amplitude=row.get('amplitude'),
                                        ratio_d20=row.get('ratio_d20'),
                                        ratio_d1=row.get('ratio_d1'),
                                        instant_deviation=row.get('instant_deviation'),
                                        rising_days_z=row.get('rising_days_z'),
                                        falling_days_f=row.get('falling_days_f'),
                                        efficiency_m20_minus_m=row.get('efficiency_m20_minus_m'),
                                        ma20_d=row.get('ma20_d'),
                                        mavol20_m=row.get('mavol20_m'),
                                        bias=row.get('bias'),
                                        d1=row.get('d1'),
                                        d1_date=row.get('d1_date'),
                                        d20=row.get('d20'),
                                        d20_date=row.get('d20_date')
                                    )
                                    db.merge(db_pvfrs)
                                except Exception as e:
                                    continue
                            db.commit()
                            results["indicator_results"][indicator]["success_count"] += 1

                        elif indicator == "icost":
                            _persist_icost_for_dataframe(
                                db, stock_code, market_type, historical_df, force_replace=True
                            )
                            results["indicator_results"][indicator]["success_count"] += 1
                            
                    except Exception as e:
                        logger.debug(f"Error generating {indicator} for {stock_code}: {str(e)}")
                        results["indicator_results"][indicator]["failed_count"] += 1
                        stock_success = False
                
                if stock_success:
                    results["success_stocks"] += 1
                else:
                    results["failed_stocks"] += 1
                    results["failed_stocks_detail"].append({
                        "stock_code": stock_code,
                        "stock_name": stock_name,
                        "error": "部分指标生成失败"
                    })
                    
            except Exception as e:
                logger.debug(f"Error processing stock {stock_code}: {str(e)}")
                results["failed_stocks"] += 1
                results["failed_stocks_detail"].append({
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "error": str(e)
                })
        
        logger.info(f"[批量生成指标-全部A股] 处理完成: 成功 {results['success_stocks']} 只，失败 {results['failed_stocks']} 只")
        return {
            "success": True,
            "message": f"成功处理 {results['success_stocks']} 只A股，失败 {results['failed_stocks']} 只",
            "data": results
        }
        
    except Exception as e:
        logger.error(f"[批量生成指标-全部A股] 发生异常: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "message": f"全部A股批量生成失败: {str(e)}"
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

    if market_type not in ("CN", "HK", "ETF"):
        return {
            "success": False,
            "message": "市场类型须为 CN（A股）、HK（港股）或 ETF",
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

        # 从数据库获取历史数据（A股 / 港股 / ETF）
        historical_data = _fetch_historical_quote_rows(db, code, market_type)

        # 转换为DataFrame（含成交额、换手率，供 icost 等指标使用）
        historical_data = _historical_quotes_to_dataframe(historical_data)
        
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
                    dates_list = historical_data['date'].tolist()
                    pvfrs_data = calculator.calculate(
                        historical_data['close'].tolist(),
                        historical_data['volume'].tolist(),
                        dates=dates_list
                    )
                    # 保存到数据库
                    for i, row in enumerate(historical_data.itertuples()):
                        if i < len(pvfrs_data) and pvfrs_data[i] is not None:
                            pvfrs_item = pvfrs_data[i]
                            date_val = row.date
                            date_str = date_val.strftime('%Y-%m-%d') if hasattr(date_val, 'strftime') else str(date_val)[:10]
                            db_pvfrs = MeanFrequencyResonanceIndicators(
                                code=code,
                                date=date_str,
                                market_type=market_type,
                                ma20_d=pvfrs_item.get('ma20_d'),
                                mavol20_m=pvfrs_item.get('mavol20_m'),
                                macro_displacement_delta=pvfrs_item.get('macro_displacement_delta'),
                                amplitude=pvfrs_item.get('amplitude'),
                                ratio_d20=pvfrs_item.get('ratio_d20'),
                                ratio_d1=pvfrs_item.get('ratio_d1'),
                                instant_deviation=pvfrs_item.get('instant_deviation'),
                                efficiency_m20_minus_m=pvfrs_item.get('efficiency_m20_minus_m'),
                                rising_days_z=pvfrs_item.get('rising_days_z'),
                                falling_days_f=pvfrs_item.get('falling_days_f'),
                                bias=pvfrs_item.get('bias'),
                                d1=pvfrs_item.get('d1'),
                                d1_date=pvfrs_item.get('d1_date'),
                                d20=pvfrs_item.get('d20'),
                                d20_date=pvfrs_item.get('d20_date')
                            )
                            db.merge(db_pvfrs)
                    db.commit()
                    results[indicator] = {"success": True, "count": len([x for x in pvfrs_data if x is not None])}

                elif indicator == "icost":
                    n = _persist_icost_for_dataframe(
                        db, code, market_type, historical_data, force_replace=True
                    )
                    results[indicator] = {"success": True, "count": n}

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

