"""
选股策略API路由
提供创业板中线选股策略接口
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status, Body
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
import logging
import asyncio
from typing import Optional, Dict, Any

# PVFRS 选股为 CPU 密集型，允许较长超时（秒）；Nginx 的 proxy_read_timeout 需 >= 此值
PVFRS_SCREENING_TIMEOUT = 300

from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

from backend_api.auth import SECRET_KEY, ALGORITHM
from backend_api.models import Watchlist, TokenData

from backend_api.database import get_db
from backend_api.models import MeanFrequencyResonanceIndicators
from .stock_screening import StockScreeningStrategy
from .high_tight_flag_strategy import HighTightFlagStrategy
from .keep_increasing_strategy import KeepIncreasingStrategy
from .long_lower_shadow_strategy import LongLowerShadowStrategy
from .low_nine_strategy import LowNineStrategy
from .one_yang_three_lines_strategy import OneYangThreeLinesStrategy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/screening", tags=["screening"])

# OAuth2 scheme (optional auth)
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)

# 添加调试日志
logger.info("stock_screening_routes.py 模块加载完成，开始注册路由...")
print("[DEBUG] stock_screening_routes.py 模块加载完成")

# 尝试导入PVFRS前端接口与配置
try:
    from backend_core.strategies.pvfrs.frontend_interface import create_frontend_interface
    from backend_core.strategies.pvfrs.config import PVFRSConfigManager
    from backend_core.strategies.pvfrs.pvfrs_system import PVFRSSystem
    print(" DEBUG: PVFRS前端接口导入成功")
    logger.info("PVFRS前端接口导入成功")
    PVFRS_AVAILABLE = True
except Exception as e:
    print(f"🔧 DEBUG: PVFRS前端接口导入失败: {e}")
    logger.error(f"PVFRS前端接口导入失败: {e}")
    PVFRS_AVAILABLE = False

# PVFRS 策略参数（供选股界面显示与编辑）
PVFRS_PARAM_KEYS = [
    "observation_period", "buy_ratio_d20_max", "buy_exclude_sideways",
    "amplitude_flat_threshold", "buy_macro_displacement_min", "buy_instant_deviation_min",
    "buy_bias_min", "buy_relative_displacement_min",
]


@router.get("/pvfrs-params")
async def get_pvfrs_params():
    """获取 PVFARS 选股策略参数（供前端显示与编辑）"""
    if not PVFRS_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={"success": False, "message": "PVFARS 暂不可用", "data": {}}
        )
    try:
        config_manager = PVFRSConfigManager()
        config_manager.load_config()
        config = config_manager.get_current_config()
        params = {k: config.get(k) for k in PVFRS_PARAM_KEYS if k in config}
        params.setdefault("observation_period", 20)
        params.setdefault("buy_ratio_d20_max", 0.5)
        params.setdefault("buy_exclude_sideways", True)
        params.setdefault("amplitude_flat_threshold", 1e-6)
        params.setdefault("buy_macro_displacement_min", 0)
        params.setdefault("buy_instant_deviation_min", 0)
        params.setdefault("buy_bias_min", 0.02)
        params.setdefault("buy_relative_displacement_min", 0.05)
        return JSONResponse({"success": True, "data": params})
    except Exception as e:
        logger.exception("获取 PVFRS 参数失败")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": str(e), "data": {}}
        )


@router.post("/pvfrs-params")
async def save_pvfrs_params(body: Dict[str, Any] = Body(...)):
    """保存 PVFARS 选股策略参数"""
    if not PVFRS_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={"success": False, "message": "PVFARS 暂不可用"}
        )
    try:
        config_manager = PVFRSConfigManager()
        config_manager.load_config()
        updates = {k: v for k, v in body.items() if k in PVFRS_PARAM_KEYS}
        if not updates:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "无有效参数"}
            )
        config_manager.update_config(updates)
        return JSONResponse({"success": True, "message": "参数已保存"})
    except Exception as e:
        logger.exception("保存 PVFRS 参数失败")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": str(e)}
        )


# PVFRS 路由定义
print("[DEBUG] 即将定义 /pvfrs-strategy 路由")
@router.get("/pvfrs-strategy")
async def get_pvfrs_strategy(
    date: str = Query(None, description="目标日期，格式：YYYY-MM-DD，不提供则使用当前日期"),
    limit: int = Query(None, ge=1, description="最大返回结果数量，不限制则返回所有符合条件的股票"),
    min_strength: float = Query(0.3, ge=0.0, le=1.0, description="最低信号强度阈值，默认0.3"),
    scope: str = Query("all", description="股票范围：all(全部), watchlist(自选)"),
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db)
):
    """PVFARS量价频幅度共振策略选股"""
    print(f"🔧 DEBUG: PVFRS路由被调用 - 日期: {date}, 限制: {limit}, 最低强度: {min_strength}")
    logger.info(f"开始执行PVFARS策略选股 - 日期: {date or '当前'}, 限制: {limit}, 最低强度: {min_strength}")
    
    # 检查PVFRS是否可用
    if not PVFRS_AVAILABLE:
        logger.error("PVFRS前端接口不可用")
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "message": "PVFARS策略暂时不可用，请稍后重试",
                "error": "PVFARS frontend interface not available",
                "data": []
            }
        )
    
    try:
        
        # 参数验证
        if date:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="日期格式错误，应为 YYYY-MM-DD"
                )
        
        # 加载策略配置并创建前端接口（使选股使用当前保存的 PVFRS 参数）
        config_manager = PVFRSConfigManager()
        config_manager.load_config()
        config = config_manager.get_current_config()
        pvfrs_system = PVFRSSystem(config)
        frontend_interface = create_frontend_interface(pvfrs_system=pvfrs_system)
        
        # 设置选股配置：【我的自选】时返回全部筛选结果（含信号强度30%以下），其他范围使用传入的最低强度
        effective_min_strength = 0.0 if scope == 'watchlist' else min_strength
        if limit is not None:
            frontend_interface.set_selection_config(max_results=limit, min_strength=effective_min_strength)
        else:
            frontend_interface.set_selection_config(max_results=10000, min_strength=effective_min_strength)
        
        # 获取选股结果
        stock_pool = None
        market = 'all'  # 默认为全部（A股+港股）
        
        # 处理不同的 scope
        if scope == 'watchlist':
            if not token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="查看自选股需要登录",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            try:
                # 验证 token
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                username: str = payload.get("sub")
                if username is None:
                    raise HTTPException(status_code=401, detail="无效的认证凭据")
                
                # 获取用户信息
                from backend_api.models import User
                user = db.query(User).filter(User.username == username).first()
                if not user:
                    raise HTTPException(status_code=401, detail="用户不存在")
                
                # 查询自选股
                watchlist_items = db.query(Watchlist).filter(Watchlist.user_id == user.id).all()
                if not watchlist_items:
                    # 如果自选股为空，直接返回空结果
                    return JSONResponse({
                        "success": True,
                        "data": [],
                        "total": 0,
                        "search_date": date or datetime.now().strftime("%Y-%m-%d"),
                        "strategy_name": "PVFARS量价频幅度共振策略",
                        "scope": "watchlist",
                        "message": "您的自选股列表为空"
                    })
                
                stock_pool = [item.stock_code for item in watchlist_items]
                logger.info(f"用户 {username} 请求筛选自选股，共 {len(stock_pool)} 只")
                
            except JWTError:
                raise HTTPException(status_code=401, detail="无效的认证凭据")
        elif scope in ['cn', 'hk', 'all']:
            # 设置市场范围
            market = scope
            logger.info(f"请求筛选市场: {market}")
        else:
            # 兼容旧版本，如果传入的是其他值，默认也作为 'all' 处理
            market = 'all'
            logger.info(f"未知 scope '{scope}'，默认使用 'all'")
        
        # 选股为 CPU 密集型同步调用，放入线程池执行并设置超时，避免阻塞事件循环与网关超时
        loop = asyncio.get_event_loop()
        def _run_screening():
            return frontend_interface.get_selection_results(date, stock_pool=stock_pool, market=market)
        try:
            selection_results = await asyncio.wait_for(
                loop.run_in_executor(None, _run_screening),
                timeout=PVFRS_SCREENING_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning(f"PVFARS选股超时({PVFRS_SCREENING_TIMEOUT}s)，scope={scope}")
            return JSONResponse(
                status_code=504,
                content={
                    "success": False,
                    "message": f"选股计算超时（超过{PVFRS_SCREENING_TIMEOUT}秒），请缩小范围（如先选 A股 或 港股）或稍后重试",
                    "data": []
                }
            )
        
        # 批量获取实时行情数据（用于获取当前价格和涨跌幅）
        from backend_api.models import StockRealtimeQuote, StockRealtimeQuoteHK, HistoricalQuotes
        from sqlalchemy import func
        import pandas as pd
        
        # 获取所有股票代码
        stock_codes = [result.symbol for result in selection_results]
        
        # 从历史行情数据库获取最新日期（用于查询PVFRS指标数据）
        # 查询 historical_quotes 表中的最新日期
        try:
            latest_date_result = db.query(func.max(HistoricalQuotes.date)).scalar()
            if latest_date_result:
                # 将日期转换为字符串格式 YYYY-MM-DD（与PVFRS指标表中的date格式一致）
                if isinstance(latest_date_result, str):
                    target_date = latest_date_result.strip()
                elif hasattr(latest_date_result, 'strftime'):
                    # date 对象
                    target_date = latest_date_result.strftime("%Y-%m-%d")
                else:
                    # 其他类型，尝试转换为字符串
                    target_date = str(latest_date_result).strip()
                logger.info(f"[DEBUG] 从历史行情数据库获取最新日期: {target_date} (用于查询PVFRS指标数据)")
            else:
                # 如果历史行情表中没有数据，使用传入的日期或当前日期
                target_date = date or datetime.now().strftime("%Y-%m-%d")
                logger.warning(f"[WARNING] 历史行情数据库中没有数据，使用日期: {target_date}")
        except Exception as e:
            # 如果查询失败，使用传入的日期或当前日期
            target_date = date or datetime.now().strftime("%Y-%m-%d")
            logger.error(f"[ERROR] 查询历史行情数据库最新日期失败: {str(e)}，使用日期: {target_date}")
        
        # 初始化结果数据列表（提前定义，避免后续使用时未定义错误）
        results_data = []
        
        # 批量查询PVFRS指标数据（价格维度和频率维度）
        # 注意：CN和HK数据在同一张表中，不需要区分market_type
        pvfrs_indicators_map = {}  # {stock_code: {price_dim: ..., freq_dim: ...}}
        if stock_codes:
            # 确保日期格式正确（去除可能的空格）
            target_date_clean = target_date.strip()
            
            # 批量查询所有股票的PVFRS指标（不区分市场类型）
            pvfrs_indicators = db.query(MeanFrequencyResonanceIndicators).filter(
                MeanFrequencyResonanceIndicators.code.in_(stock_codes),
                MeanFrequencyResonanceIndicators.date == target_date_clean
            ).all()
            
            for indicator in pvfrs_indicators:
                pvfrs_indicators_map[indicator.code] = {
                    'macro_displacement_delta': indicator.macro_displacement_delta,
                    'ratio_d20': getattr(indicator, 'ratio_d20', None),
                    'ratio_d1': getattr(indicator, 'ratio_d1', None),
                    'rising_days_z': indicator.rising_days_z,
                    'falling_days_f': indicator.falling_days_f,
                    'market_type': indicator.market_type
                }
            
            logger.info(f"[DEBUG] 从PVFRS指标表查询数据: 目标日期='{target_date_clean}', 查询到{len(pvfrs_indicators)}条记录, "
                      f"股票代码={stock_codes[:5] if len(stock_codes) > 5 else stock_codes}...")  # 只显示前5个代码
            
            # 详细日志：显示前几条查询结果
            if len(pvfrs_indicators) > 0 and len(results_data) == 0:  # 只在第一次循环时显示
                for idx, ind in enumerate(pvfrs_indicators[:3]):
                    logger.info(f"[DEBUG] 查询结果示例 {idx+1}: 代码={ind.code}, 日期={ind.date}, 市场类型={ind.market_type}, "
                              f"上涨天数={ind.rising_days_z}, 下跌天数={ind.falling_days_f}")
            
            # 检查是否有股票在数据库中找不到数据
            missing_codes = [code for code in stock_codes if code not in pvfrs_indicators_map]
            if missing_codes and len(missing_codes) <= 10:  # 如果缺失的股票不多，记录日志
                logger.warning(f"[DEBUG] 以下股票在PVFRS指标表中未找到数据 (日期={target_date_clean}): {missing_codes}")
        
        if stock_codes:
            # 获取最新交易日期
            latest_date_result = pd.read_sql_query("""
                SELECT MAX(trade_date) as latest_date 
                FROM stock_realtime_quote 
                WHERE change_percent IS NOT NULL
            """, db.bind)
            
            latest_trade_date = None
            if not latest_date_result.empty and latest_date_result.iloc[0]['latest_date'] is not None:
                latest_trade_date = latest_date_result.iloc[0]['latest_date']
            
            # 批量查询实时行情（A股）
            realtime_quotes_a = {}
            if latest_trade_date:
                quotes_a = db.query(StockRealtimeQuote).filter(
                    StockRealtimeQuote.code.in_(stock_codes),
                    StockRealtimeQuote.trade_date == latest_trade_date
                ).all()
                realtime_quotes_a = {q.code: q for q in quotes_a}
            
            # 批量查询实时行情（港股）
            hk_codes = [code for code in stock_codes if (len(code) <= 5 and code.isdigit()) or (code.startswith('0') and len(code) == 5)]
            realtime_quotes_hk = {}
            if hk_codes and latest_trade_date:
                quotes_hk = db.query(StockRealtimeQuoteHK).filter(
                    StockRealtimeQuoteHK.code.in_(hk_codes),
                    StockRealtimeQuoteHK.trade_date == latest_trade_date
                ).all()
                realtime_quotes_hk = {q.code: q for q in quotes_hk}
        else:
            realtime_quotes_a = {}
            realtime_quotes_hk = {}
        
        # 转换为API响应格式（results_data已在上面初始化）
        for result in selection_results:
            result_dict = result.to_dict()
            
            # 确保股票名称字段是真实的真实名称
            current_name = result_dict.get('name', '')
            if not current_name or current_name.startswith('股票'):
                # 如果没有名称字段、名称为空，或者名称是以"股票"开头的默认值，尝试从数据库查询真实名称
                from backend_api.models import StockBasicInfo, StockBasicInfoHK
                
                # 清理股票代码格式
                stock_code = str(result.symbol).strip()
                
                # 尝试多种查询方式
                stock_info = None
                
                # 1. 判断是否为港股 (通常是5位数字，如 00700)
                is_hk = False
                if len(stock_code) <= 5 and stock_code.isdigit():
                    is_hk = True
                elif not (stock_code.startswith('6') or stock_code.startswith('0') or stock_code.startswith('3') or 
                          stock_code.startswith('SZ') or stock_code.startswith('SH')):
                    is_hk = True
                
                if is_hk:
                    # 查询港股基础信息
                    stock_info = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == stock_code).first()
                    # 如果没找到且代码长度小于5，尝试补全为5位
                    if not stock_info and len(stock_code) < 5:
                        padded_code = stock_code.zfill(5)
                        stock_info = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == padded_code).first()
                else:
                    # 查询A股基础信息
                    # 方式1：直接查询
                    stock_info = db.query(StockBasicInfo).filter(StockBasicInfo.code == stock_code).first()
                    
                    # 方式2：如果失败，尝试去掉SZ前缀
                    if not stock_info and stock_code.startswith('SZ'):
                        clean_code = stock_code[2:]
                        stock_info = db.query(StockBasicInfo).filter(StockBasicInfo.code == clean_code).first()
                    
                    # 方式3：如果失败，尝试去掉SH前缀
                    if not stock_info and stock_code.startswith('SH'):
                        clean_code = stock_code[2:]
                        stock_info = db.query(StockBasicInfo).filter(StockBasicInfo.code == clean_code).first()
                
                if stock_info and stock_info.name:
                    result_dict['name'] = stock_info.name
                    logger.debug(f"[DEBUG] 从数据库查询真实name: {stock_code} -> {stock_info.name}")
                else:
                    # 如果数据库中也没有，保留原样或使用股票代码作为名称
                    if not result_dict.get('name'):
                        result_dict['name'] = f"股票{stock_code}"
                    logger.warning(f"[WARNING] 无法找到股票真实名称，代码: {stock_code}")
            
            # 调试日志：检查name字段
            if len(results_data) < 3:  # 只打印前3条数据
                logger.info(f"[DEBUG] 股票 {result.symbol} 的name字段: '{result_dict.get('name', 'MISSING')}'")
            
            # 提取指标信息
            indicators = result_dict.get('indicators', {})
            
            # 从 resonance_analysis.details 中获取维度信息
            resonance_analysis = indicators.get('resonance_analysis', {})
            resonance_details = resonance_analysis.get('details', {})
            
            # 调试日志：输出指标结构信息
            if len(results_data) < 1:  # 只打印第一条数据的调试信息，避免日志过多
                logger.info(f"[DEBUG] resonance_details keys: {list(resonance_details.keys())}")
                logger.info(f"[DEBUG] indicators keys: {list(indicators.keys())}")
            
            # 优先从 resonance_analysis.details 中获取，如果不存在则从顶层 indicators 中获取
            price_indicators = resonance_details.get('price_indicators') or indicators.get('price_dimension') or {}
            frequency_indicators = resonance_details.get('frequency_indicators') or indicators.get('frequency_dimension') or {}
            volume_indicators = resonance_details.get('volume_indicators') or indicators.get('volume_dimension') or {}
            
            # log debug info if still empty
            if not price_indicators:
                logger.debug(f"Stock {result.symbol} missing price_indicators")
            entry_timing_analysis = indicators.get('entry_timing_analysis', {})
            
            # 从PVFRS指标数据表中获取价格维度和频率维度数据
            stock_code = result.symbol
            pvfrs_data = pvfrs_indicators_map.get(stock_code)
            
            # 价格维度状态 - 位移幅度数据（|Δ|、Δ/d₂₀、Δ/d₁、横盘）
            parts = []
            ampl = price_indicators.get('amplitude') if price_indicators and isinstance(price_indicators, dict) else None
            if ampl is not None:
                parts.append(f"位移幅度: {float(ampl):.2f}")
            rd20 = None
            if price_indicators and isinstance(price_indicators, dict) and price_indicators.get('ratio_d20') is not None:
                rd20 = price_indicators['ratio_d20']
            elif pvfrs_data and pvfrs_data.get('ratio_d20') is not None:
                rd20 = pvfrs_data['ratio_d20']
            if rd20 is not None:
                parts.append(f"Δ/d₂₀: {float(rd20) * 100:.2f}%")
            rd1 = None
            if price_indicators and isinstance(price_indicators, dict) and price_indicators.get('ratio_d1') is not None:
                rd1 = price_indicators['ratio_d1']
            elif pvfrs_data and pvfrs_data.get('ratio_d1') is not None:
                rd1 = pvfrs_data['ratio_d1']
            if rd1 is not None:
                parts.append(f"Δ/d₁: {float(rd1) * 100:.2f}%")
            sideways = price_indicators.get('is_sideways') if price_indicators and isinstance(price_indicators, dict) else None
            if sideways is not None:
                parts.append(f"横盘: {'是' if sideways else '否'}")
            price_dimension_status = " | ".join(parts) if parts else "--"
            
            # 频率维度状态 - 从PVFRS指标表获取（优先使用数据库数据）
            if pvfrs_data:
                # 注意：0 是有效值，不能使用 or 0，应该使用 is not None 判断
                rising_days_z = pvfrs_data.get('rising_days_z')
                falling_days_f = pvfrs_data.get('falling_days_f')
                
                if rising_days_z is not None and falling_days_f is not None:
                    # 使用数据库中的值（强制使用，不使用策略分析的值）
                    rising_days = int(rising_days_z)
                    falling_days = int(falling_days_f)
                    frequency_dimension_status = f"上涨{rising_days}天/下跌{falling_days}天"
                    
                    # 调试日志：对比数据库值和策略分析值
                    if len(results_data) < 3:  # 只打印前3条数据的调试信息
                        strategy_rising = frequency_indicators.get('rising_days') if frequency_indicators else None
                        strategy_falling = frequency_indicators.get('falling_days') if frequency_indicators else None
                        logger.info(f"[DEBUG] 股票 {stock_code} 频率维度 - 使用数据库值: 上涨{rising_days}天/下跌{falling_days}天, "
                                  f"策略分析值: 上涨{strategy_rising}天/下跌{strategy_falling}天, "
                                  f"目标日期: {target_date}")
                else:
                    # 如果数据库中有记录但字段为None，记录警告并尝试使用策略分析值
                    logger.warning(f"股票 {stock_code} 在PVFRS指标表中存在记录，但上涨/下跌天数字段为None，尝试使用策略分析值")
                    if frequency_indicators and isinstance(frequency_indicators, dict) and frequency_indicators:
                        rising_days = frequency_indicators.get('rising_days', 0) or 0
                        falling_days = frequency_indicators.get('falling_days', 0) or 0
                        frequency_dimension_status = f"上涨{rising_days}天/下跌{falling_days}天"
                    else:
                        frequency_dimension_status = "--"
            else:
                # 如果PVFRS表中没有数据，尝试从策略分析结果中获取（向后兼容）
                if frequency_indicators and isinstance(frequency_indicators, dict) and frequency_indicators:
                    rising_days = frequency_indicators.get('rising_days', 0) or 0
                    falling_days = frequency_indicators.get('falling_days', 0) or 0
                    frequency_dimension_status = f"上涨{rising_days}天/下跌{falling_days}天"
                    
                    # 调试日志：记录使用策略分析值的情况（重要警告）
                    if len(results_data) < 3:
                        logger.warning(f"[WARNING] 股票 {stock_code} 在PVFRS指标表中未找到数据 (日期={target_date})，使用策略分析值: "
                                     f"上涨{rising_days}天/下跌{falling_days}天。请检查数据库中是否有该股票该日期的数据。")
                else:
                    frequency_dimension_status = "--"
            
            # 成交量维度状态 - 显示实际数值
            if volume_indicators and isinstance(volume_indicators, dict) and volume_indicators:
                efficiency_ratio = volume_indicators.get('efficiency_ratio', 0) or 0
                # 显示效率比
                volume_dimension_status = f"效率比: {efficiency_ratio:.2f}"
            else:
                volume_dimension_status = "--"
            
            # 获取条件验证信息
            conditions_met = result_dict.get('conditions_met', {})
            
            # 共振状态
            resonance_detected = conditions_met.get("resonance_detected", False)
            three_dimension_resonance = conditions_met.get("three_dimension_resonance", False)
            if three_dimension_resonance or resonance_detected:
                resonance_status = "三维共振"
            elif conditions_met.get("price_dimension_met", False) and \
                 (conditions_met.get("frequency_dimension_met", False) or conditions_met.get("volume_dimension_met", False)):
                resonance_status = "部分共振"
            else:
                resonance_status = "--"
            
            # 入场时机状态（从 entry_timing_analysis 中提取）
            entry_timing_status = "--"
            if entry_timing_analysis and isinstance(entry_timing_analysis, dict):
                comprehensive_assessment = entry_timing_analysis.get('comprehensive_assessment', {})
                if comprehensive_assessment and isinstance(comprehensive_assessment, dict):
                    timing_score = comprehensive_assessment.get('score', 0)
                    optimal_timing = comprehensive_assessment.get('optimal_timing', False)
                    good_timing = comprehensive_assessment.get('good_timing', False)
                    
                    if optimal_timing:
                        entry_timing_status = f"最佳时机({timing_score:.2f})"
                    elif good_timing:
                        entry_timing_status = f"良好时机({timing_score:.2f})"
                    elif timing_score > 0:
                        entry_timing_status = f"评分:{timing_score:.2f}"
                else:
                    # 尝试直接获取评分
                    timing_score = entry_timing_analysis.get('timing_score', 0)
                    if timing_score > 0:
                        entry_timing_status = f"评分:{timing_score:.2f}"
            
            # 如果没有从 entry_timing_analysis 中获取到，尝试从 conditions_met 中获取
            if entry_timing_status == "--":
                entry_timing_met = conditions_met.get("entry_timing_optimized", False)
                if entry_timing_met:
                    entry_timing_status = "满足"
                else:
                    entry_timing_status = "--"
            
            # 获取当前价格和涨跌幅（从实时行情表）
            current_price = result_dict.get('price', None)  # 先使用历史数据中的价格
            change_percent = None
            
            # 优先从实时行情表获取
            realtime_quote = realtime_quotes_a.get(stock_code) or realtime_quotes_hk.get(stock_code)
            if realtime_quote:
                if hasattr(realtime_quote, 'current_price') and realtime_quote.current_price:
                    current_price = float(realtime_quote.current_price)
                if hasattr(realtime_quote, 'change_percent') and realtime_quote.change_percent is not None:
                    change_percent = float(realtime_quote.change_percent)
            
            # 投资建议（从 indicators 中提取）
            investment_advice_dict = indicators.get('investment_advice', {})
            if isinstance(investment_advice_dict, dict):
                investment_advice = investment_advice_dict.get('recommendation', '--')
                # 如果是英文，转换为中文
                if investment_advice == 'BUY':
                    investment_advice = '买入'
                elif investment_advice == 'HOLD':
                    investment_advice = '持有'
                elif investment_advice == 'WAIT':
                    investment_advice = '等待'
                elif investment_advice == 'SELL':
                    investment_advice = '卖出'
            else:
                investment_advice = "--"
            
            # 得分明细（供前端展示：共振强度、各维度得分）
            score_detail = indicators.get("score_detail", {})
            if not score_detail and resonance_analysis:
                resonance_details = resonance_analysis.get("details", {})
                dim_scores = resonance_details.get("dimension_scores", resonance_details.get("dimension_scores") or {})
                if isinstance(dim_scores, dict):
                    score_detail = {
                        "resonance_strength": resonance_analysis.get("resonance_strength") or resonance_details.get("resonance_strength"),
                        "price_score": dim_scores.get("price_score"),
                        "frequency_score": dim_scores.get("frequency_score"),
                        "volume_score": dim_scores.get("volume_score"),
                    }
            
            # 添加选股策略特有的字段
            result_dict.update({
                "strategy_type": "PVFARS",
                "signal_date": date or datetime.now().strftime("%Y-%m-%d"),
                # 添加前端期望的字段
                "current_price": current_price,  # 使用从实时行情表获取的价格
                "price_dimension_status": price_dimension_status,
                "frequency_dimension_status": frequency_dimension_status,
                "volume_dimension_status": volume_dimension_status,
                "resonance_status": resonance_status,
                "entry_timing_status": entry_timing_status,
                "investment_advice": investment_advice,
                "current_change_percent": change_percent if change_percent is not None else 0.0,  # 添加当前涨跌幅（前端期望的字段名）
                "score_detail": score_detail,  # 得分明细：共振强度、价格/频率/成交量维度得分
                # 保留原有的 analysis_dimensions 字段
                "analysis_dimensions": {
                    "price_dimension": conditions_met.get("price_dimension_met", False),
                    "frequency_dimension": conditions_met.get("frequency_dimension_met", False),
                    "volume_dimension": conditions_met.get("volume_dimension_met", False),
                    "resonance_detected": resonance_detected
                }
            })
            results_data.append(result_dict)
        
        logger.info(f"PVFARS策略选股执行完成，找到 {len(results_data)} 只符合条件的股票")
        
        return JSONResponse({
            "success": True,
            "data": results_data,
            "total": len(results_data),
            "search_date": date or datetime.now().strftime("%Y-%m-%d"),
            "strategy_name": "PVFARS量价频幅度共振策略",
            "parameters": {
                "limit": limit or "无限制",
                "min_strength": min_strength,
                "scope": scope
            }
        })
    
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"执行PVFARS策略选股失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PVFARS策略选股执行失败: {str(e)}"
        )
print("[DEBUG] /pvfrs-strategy 路由定义完成")

# 添加一个简单的测试路由
@router.get("/test-pvfrs")
async def test_pvfrs():
    """测试PVFRS路由是否工作"""
    return JSONResponse({
        "success": True,
        "message": "PVFRS测试路由工作正常",
        "pvfrs_available": PVFRS_AVAILABLE
    })

# 调试：打印路由对象中的所有路由
print(f"[DEBUG] router.routes count: {len(router.routes)}")
for route in router.routes:
    if hasattr(route, 'path'):
        print(f"[DEBUG] route path: {route.path}, methods: {getattr(route, 'methods', None)}")


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
    # 一阳穿三线策略参数
    min_increase_percent: float = Query(3.0, ge=0, le=50, description="最小涨幅百分比（默认3%）"),
    min_body_ratio: float = Query(0.7, ge=0.1, le=1.0, description="最小实体占比（默认0.7）"),
    min_cross_lines: int = Query(3, ge=2, le=6, description="最小穿越均线数量（默认3）"),
    min_volume_ratio: float = Query(2.0, ge=0.1, le=10.0, description="最小成交量倍数（默认2.0）"),
    min_turnover_rate: float = Query(3.0, ge=0, le=50, description="最小换手率（默认3%）"),
    max_turnover_rate: float = Query(10.0, ge=0, le=100, description="最大换手率（默认10%）"),
    recent_days: int = Query(1, ge=1, le=10, description="检查最近N个交易日（默认1天）"),
    ma_periods: str = Query("5,10,20,30,60,120", description="均线周期，逗号分隔（默认5,10,20,30,60,120）"),
    db: Session = Depends(get_db)
):
    """
    一阳穿三线选股策略（又称"出水芙蓉"）
    
    策略条件:
    1. 长阳线：收盘价>开盘价，实体占比>=min_body_ratio，涨幅>=min_increase_percent%
    2. 穿越至少min_cross_lines条均线（从ma_periods中选择）
    3. 放量突破：成交量>=前5日平均成交量的min_volume_ratio倍
    4. 换手率范围：min_turnover_rate% - max_turnover_rate%
    5. 位置判别：根据60日最高价回撤幅度判断低位/中位/高位
    6. 乖离率计算：BIAS5/10/30，BIAS30>10%时风险提示
    7. 信号质量评分：综合穿线数量、成交量、换手率、位置、乖离率
    8. 检查天数：最近N个交易日内出现符合上述条件的形态
    
    股票范围:
    - 全部A股
    - 自动排除ST股票（包括ST、*ST、S*ST等所有ST类股票）
    
    Args:
        page: 页码（可选，默认1）
        page_size: 每页数量（可选，默认100，最大500）
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）
        min_increase_percent: 最小涨幅百分比（默认3%）
        min_body_ratio: 最小实体占比（默认0.7）
        min_cross_lines: 最小穿越均线数量（默认3）
        min_volume_ratio: 最小成交量倍数（默认2.0）
        min_turnover_rate: 最小换手率（默认3%）
        max_turnover_rate: 最大换手率（默认10%）
        recent_days: 检查最近N个交易日（默认1天）
        ma_periods: 均线周期，逗号分隔（默认5,10,20,30,60,120）
        db: 数据库会话
    
    Returns:
        符合条件的股票列表，按信号质量评分降序排列
    """
    try:
        logger.info(f"开始执行一阳穿三线选股策略 - 页码: {page}, 每页: {page_size}, 检查最近 {recent_days} 天")
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
        
        # 解析均线周期参数
        try:
            ma_periods_list = [int(x.strip()) for x in ma_periods.split(',')]
            if len(ma_periods_list) < 2:
                raise ValueError("至少需要2个均线周期")
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"均线周期参数错误: {str(e)}"
            )
        
        # 构建策略参数
        strategy_params = {
            'min_increase_percent': min_increase_percent,
            'min_body_ratio': min_body_ratio,
            'min_cross_lines': min_cross_lines,
            'min_volume_ratio': min_volume_ratio,
            'min_turnover_rate': min_turnover_rate,
            'max_turnover_rate': max_turnover_rate,
            'recent_days': recent_days,
            'ma_periods': ma_periods_list
        }
        
        logger.info(f"策略参数: {strategy_params}")
        
        # 执行选股策略
        all_results = OneYangThreeLinesStrategy.screening_one_yang_three_lines_strategy(db, **strategy_params)
        
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
