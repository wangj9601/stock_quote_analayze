"""
选股策略API路由
提供创业板中线选股策略接口
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from database import get_db
from stock.stock_screening import StockScreeningStrategy
from stock.high_tight_flag_strategy import HighTightFlagStrategy
from stock.keep_increasing_strategy import KeepIncreasingStrategy
from stock.long_lower_shadow_strategy import LongLowerShadowStrategy
from stock.low_nine_strategy import LowNineStrategy
from stock.one_yang_three_lines_strategy import OneYangThreeLinesStrategy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/screening", tags=["screening"])


@router.get("/cyb-midline-strategy")
async def get_cyb_midline_strategy(
    months: int = Query(4, ge=3, le=4, description="查询月数（3-4个月）"),
    db: Session = Depends(get_db)
):
    """
    创业板中线选股策略
    
    股票范围:
    - 创业板股票（代码以3开头）
    - 自动排除ST股票（包括ST、*ST、S*ST等所有ST类股票）
    
    策略条件：
    1. 第一个涨停（涨幅>=9.8%）
    2. 第一次回调不跌穿涨停底部
    3. 第二次上涨突破第一个涨停高点
    4. 中间有向上跳空和揉搓线
    5. 当前均线多头排列（MA5>MA10>MA20）
    
    Args:
        months: 查询月数，默认4个月
        db: 数据库会话
    
    Returns:
        符合条件的股票列表
    """
    try:
        logger.info(f"开始执行创业板中线选股策略，查询月数: {months}")
        
        # 执行选股策略
        results = StockScreeningStrategy.screening_cyb_midline_strategy(db, months=months)
        
        logger.info(f"选股策略执行完成，找到 {len(results)} 只符合条件的股票")
        
        return JSONResponse({
            "success": True,
            "data": results,
            "total": len(results),
            "search_date": datetime.now().strftime("%Y-%m-%d"),
            "months": months,
            "strategy_name": "创业板中线选股策略"
        })
        
    except Exception as e:
        logger.error(f"执行选股策略失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"选股策略执行失败: {str(e)}"
        )


@router.get("/parking-apron-strategy")
async def get_parking_apron_strategy(
    db: Session = Depends(get_db)
):
    """
    停机坪选股策略
    
    策略条件：
    1. 最近15日有涨幅大于9.5%，且必须是放量上涨
    2. 紧接的下个交易日必须高开，收盘价必须上涨，且与开盘价不能大于等于相差3%
    3. 接下2、3个交易日必须高开，收盘价必须上涨，且与开盘价不能大于等于相差3%，且每天涨跌幅在5%间
    
    Args:
        db: 数据库会话
    
    Returns:
        符合条件的股票列表
    """
    try:
        logger.info("开始执行停机坪选股策略")
        
        # 执行选股策略
        results = StockScreeningStrategy.screening_parking_apron_strategy(db)
        
        logger.info(f"停机坪选股策略执行完成，找到 {len(results)} 只符合条件的股票")
        
        return JSONResponse({
            "success": True,
            "data": results,
            "total": len(results),
            "search_date": datetime.now().strftime("%Y-%m-%d"),
            "strategy_name": "停机坪"
        })
        
    except Exception as e:
        logger.error(f"执行停机坪选股策略失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"停机坪选股策略执行失败: {str(e)}"
        )


@router.get("/backtrace-ma250-strategy")
async def get_backtrace_ma250_strategy(
    db: Session = Depends(get_db)
):
    """
    回踩年线选股策略
    
    策略条件：
    1. 时间段：前段=最近60交易日最高收盘价之前交易日(长度>0)，后段=最高价当日及后面的交易日
    2. 前段由年线(250日)以下向上突破
    3. 后段必须在年线以上运行，且后段最低价日与最高价日相差必须在10-50日间
    4. 回踩伴随缩量：最高价日交易量/后段最低价日交易量>2,后段最低价/最高价<0.8
    
    Args:
        db: 数据库会话
    
    Returns:
        符合条件的股票列表
    """
    try:
        logger.info("开始执行回踩年线选股策略")
        
        # 执行选股策略
        results = StockScreeningStrategy.screening_backtrace_ma250_strategy(db)
        
        logger.info(f"回踩年线选股策略执行完成，找到 {len(results)} 只符合条件的股票")
        
        return JSONResponse({
            "success": True,
            "data": results,
            "total": len(results),
            "search_date": datetime.now().strftime("%Y-%m-%d"),
            "strategy_name": "回踩年线"
        })
        
    except Exception as e:
        logger.error(f"执行回踩年线选股策略失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"回踩年线选股策略执行失败: {str(e)}"
        )


@router.get("/high-tight-flag-strategy")
async def get_high_tight_flag_strategy(
    db: Session = Depends(get_db)
):
    """
    高而窄的旗形选股策略
    
    策略条件：
    1. 必须至少上市交易60日
    2. 当日收盘价/之前24~10日的最低价>=1.9
    3. 之前24~10日必须连续两天涨幅大于等于9.5%
    
    Args:
        db: 数据库会话
    
    Returns:
        符合条件的股票列表
    """
    try:
        logger.info("开始执行高而窄的旗形选股策略")
        
        # 执行选股策略
        results = HighTightFlagStrategy.screening_high_tight_flag_strategy(db)
        
        logger.info(f"高而窄的旗形选股策略执行完成，找到 {len(results)} 只符合条件的股票")
        
        return JSONResponse({
            "success": True,
            "data": results,
            "total": len(results),
            "search_date": datetime.now().strftime("%Y-%m-%d"),
            "strategy_name": "高而窄的旗形"
        })
        
    except Exception as e:
        logger.error(f"执行高而窄的旗形选股策略失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"高而窄的旗形选股策略执行失败: {str(e)}"
        )


@router.get("/keep-increasing-strategy")
async def get_keep_increasing_strategy(
    db: Session = Depends(get_db)
):
    """
    持续上涨（MA30向上）选股策略
    
    策略条件：
    1. 均线多头：30日前的30日均线 < 20日前的30日均线 < 10日前的30日均线 < 当日的30日均线
    2. 涨幅要求：(当日的30日均线 / 30日前的30日均线) > 1.2
    
    Args:
        db: 数据库会话
    
    Returns:
        符合条件的股票列表
    """
    try:
        logger.info("开始执行持续上涨（MA30向上）选股策略")
        
        # 执行选股策略
        results = KeepIncreasingStrategy.screening_keep_increasing_strategy(db)
        
        logger.info(f"持续上涨（MA30向上）选股策略执行完成，找到 {len(results)} 只符合条件的股票")
        
        return JSONResponse({
            "success": True,
            "data": results,
            "total": len(results),
            "search_date": datetime.now().strftime("%Y-%m-%d"),
            "strategy_name": "持续上涨（MA30向上）"
        })
        
    except Exception as e:
        logger.error(f"执行持续上涨（MA30向上）选股策略失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"持续上涨（MA30向上）选股策略执行失败: {str(e)}"
        )


@router.get("/long-lower-shadow-strategy")
async def get_long_lower_shadow_strategy(
    lower_shadow_ratio: float = Query(1.0, ge=0.5, le=3.0, description="下影线长度 >= 实体长度的倍数（默认1.0倍）"),
    upper_shadow_ratio: float = Query(0.3, ge=0.1, le=0.5, description="上影线 <= 实体长度的比例（默认30%）"),
    min_amplitude: float = Query(0.02, ge=0.01, le=0.1, description="最小振幅要求（默认2%）"),
    recent_days: int = Query(2, ge=1, le=10, description="检查最近N个交易日（默认2天）"),
    db: Session = Depends(get_db)
):
    """
    长下影阳线选股策略（参数化版本）
    
    策略条件:
    1. 下跌趋势: 当日最低价 < MA20（20日移动平均线）
    2. 长下影线: 最近N个交易日内出现(阳线或阴线均可)
       - 下影线长度 >= 实体长度的X倍（可配置）
       - 上影线很短或几乎没有（<= 实体长度的Y%，可配置）
    3. 振幅: 出现长下影线当日振幅超过Z%（可配置）
    
    参数说明:
    - lower_shadow_ratio: 下影线倍数（0.5-3.0），默认1.0
    - upper_shadow_ratio: 上影线比例（0.1-0.5），默认0.3
    - min_amplitude: 最小振幅（0.01-0.1），默认0.02
    - recent_days: 检查天数（1-10），默认2
    
    Args:
        lower_shadow_ratio: 下影线长度倍数
        upper_shadow_ratio: 上影线比例
        min_amplitude: 最小振幅
        recent_days: 检查最近N天
        db: 数据库会话
    
    Returns:
        符合条件的股票列表
    """
    try:
        logger.info(f"开始执行长下影阳线选股策略 - 参数: 下影线倍数={lower_shadow_ratio}, "
                   f"上影线比例={upper_shadow_ratio}, 最小振幅={min_amplitude}, 检查天数={recent_days}")
        
        # 执行选股策略（传入参数）
        results = LongLowerShadowStrategy.screening_long_lower_shadow_strategy(
            db, 
            lower_shadow_ratio=lower_shadow_ratio,
            upper_shadow_ratio=upper_shadow_ratio,
            min_amplitude=min_amplitude,
            recent_days=recent_days
        )
        
        logger.info(f"长下影阳线选股策略执行完成，找到 {len(results)} 只符合条件的股票")
        
        return JSONResponse({
            "success": True,
            "data": results,
            "total": len(results),
            "search_date": datetime.now().strftime("%Y-%m-%d"),
            "strategy_name": "长下影阳线",
            "parameters": {
                "lower_shadow_ratio": lower_shadow_ratio,
                "upper_shadow_ratio": upper_shadow_ratio,
                "min_amplitude": min_amplitude,
                "recent_days": recent_days
            }
        })
        
    except Exception as e:
        logger.error(f"执行长下影阳线选股策略失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"长下影阳线选股策略执行失败: {str(e)}"
        )


@router.get("/low-nine-strategy")
async def get_low_nine_strategy(
    limit: int = Query(None, description="限制处理股票数量（测试用，None表示处理所有）"),
    db: Session = Depends(get_db)
):
    """
    低九策略选股
    
    策略条件:
    应用于下跌趋势中，构成条件：
    连续 9 根K线（或交易日），每一天的收盘价都低于它前面第4天的收盘价。
    
    股票范围:
    - 全部A股
    - 自动排除ST股票（包括ST、*ST、S*ST等所有ST类股票）
    
    Args:
        limit: 限制处理股票数量（可选，用于测试）
        db: 数据库会话
    
    Returns:
        符合条件的股票列表
    """
    try:
        if limit:
            logger.info(f"开始执行低九策略选股（测试模式：限制 {limit} 只股票）")
        else:
            logger.info("开始执行低九策略选股（生产模式：处理所有股票）")
        
        # 执行选股策略
        results = LowNineStrategy.screening_low_nine_strategy(db, limit=limit)
        
        logger.info(f"低九策略选股执行完成，找到 {len(results)} 只符合条件的股票")
        
        return JSONResponse({
            "success": True,
            "data": results,
            "total": len(results),
            "search_date": datetime.now().strftime("%Y-%m-%d"),
            "strategy_name": "低九策略",
            "test_mode": limit is not None,
            "limit": limit
        })
        
    except Exception as e:
        logger.error(f"执行低九策略选股失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"低九策略选股执行失败: {str(e)}"
        )


@router.get("/one-yang-three-lines")
async def get_one_yang_three_lines_strategy(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(100, ge=1, le=500, description="每页数量，最大500"),
    start_date: str = Query(None, description="开始日期，格式：YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期，格式：YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """
    一阳穿三线选股策略（又称"出水芙蓉"）
    
    策略条件:
    1. 长阳线：收盘价>开盘价，实体占比>=70%，涨幅>=3%
    2. 穿越至少三条均线（MA5/10/20/30/60/120中的任意三条或更多）
    3. 放量突破：成交量>=前5日平均成交量的2倍
    4. 位置判别：根据60日最高价回撤幅度判断低位/中位/高位
    5. 乖离率计算：BIAS5/10/30，BIAS30>10%时风险提示
    6. 信号质量评分：综合穿线数量、成交量、换手率、位置、乖离率
    
    股票范围:
    - 全部A股
    - 自动排除ST股票（包括ST、*ST、S*ST等所有ST类股票）
    
    Args:
        page: 页码（可选，默认1）
        page_size: 每页数量（可选，默认100，最大500）
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）
        db: 数据库会话
    
    Returns:
        符合条件的股票列表，按信号质量评分降序排列
    """
    try:
        logger.info(f"开始执行一阳穿三线选股策略 - 页码: {page}, 每页: {page_size}")
        if start_date:
            logger.info(f"日期范围: {start_date} 至 {end_date or '今天'}")
        
        # 参数验证
        if start_date:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="开始日期格式错误，应为 YYYY-MM-DD"
                )
        
        if end_date:
            try:
                datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="结束日期格式错误，应为 YYYY-MM-DD"
                )
        
        if start_date and end_date and start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="开始日期不能晚于结束日期"
            )
        
        # 执行选股策略
        all_results = OneYangThreeLinesStrategy.screening_one_yang_three_lines_strategy(db)
        
        # 日期范围过滤（如果提供）
        if start_date or end_date:
            filtered_results = []
            for result in all_results:
                signal_date = result.get("signal_date", "")
                if start_date and signal_date < start_date:
                    continue
                if end_date and signal_date > end_date:
                    continue
                filtered_results.append(result)
            all_results = filtered_results
        
        # 分页处理
        total = len(all_results)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_results = all_results[start_idx:end_idx]
        
        logger.info(f"一阳穿三线选股策略执行完成，找到 {total} 只符合条件的股票，返回第 {page} 页（共 {len(paginated_results)} 只）")
        
        return JSONResponse({
            "success": True,
            "data": paginated_results,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
            "search_date": datetime.now().strftime("%Y-%m-%d"),
            "strategy_name": "一阳穿三线",
            "date_range": {
                "start_date": start_date,
                "end_date": end_date
            } if start_date or end_date else None
        })
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"执行一阳穿三线选股策略失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"一阳穿三线选股策略执行失败: {str(e)}"
        )
