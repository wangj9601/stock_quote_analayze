"""
长下影线选股策略(支持阳线和阴线)
独立策略文件

策略要求:
1. 股票范围: 排除创业板(3开头)、科创板(688开头)和北证A股(9开头)
2. 下跌趋势: 当日最低价 < MA20(20日移动平均线)
3. 长下影线: 最近2个交易日内出现(阳线或阴线均可)
   - 下影线长度 >= 实体长度的1倍
   - 上影线很短或几乎没有(上影线 <= 实体长度的30%)
   - 出现长下影线当日振幅超过2%
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


class LongLowerShadowStrategy:
    """长下影线选股策略类(支持阳线和阴线)"""
    
    @staticmethod
    def check_downtrend(historical_data: List[Dict], threshold: int = 20) -> bool:
        """
        检查是否处于下跌趋势
        
        Args:
            historical_data: 历史数据列表（倒序，最新在前）
            threshold: MA计算天数（默认20天）
        
        Returns:
            是否处于下跌趋势（当日最低价 < MA20）
        """
        if len(historical_data) < threshold:
            return False
        
        # 当日最低价
        current_low = float(historical_data[0].get('low', 0))
        
        if current_low <= 0:
            return False
        
        # 计算MA20（20日移动平均线）
        # 取最近20个交易日的收盘价
        prices = []
        for i in range(threshold):
            if i < len(historical_data):
                price = float(historical_data[i].get('close', 0))
                if price > 0:
                    prices.append(price)
        
        if len(prices) < threshold:
            return False
        
        # 计算平均值
        ma20 = sum(prices) / len(prices)
        
        # 下跌趋势: 当日最低价 < MA20
        return current_low < ma20
    
    @staticmethod
    def check_long_lower_shadow(day_data: Dict, 
                               lower_shadow_ratio: float = 1.0,
                               upper_shadow_ratio: float = 0.3) -> Tuple[bool, Optional[Dict]]:
        """
        检查单日是否为长下影线(阳线或阴线)
        
        Args:
            day_data: 单日数据
            lower_shadow_ratio: 下影线长度 >= 实体长度的倍数（默认1.0）
            upper_shadow_ratio: 上影线 <= 实体长度的比例（默认0.3）
        
        Returns:
            (是否为长下影线, 形态信息)
        """
        open_price = float(day_data.get('open', 0))
        close_price = float(day_data.get('close', 0))
        high_price = float(day_data.get('high', 0))
        low_price = float(day_data.get('low', 0))
        
        # 检查数据有效性
        if open_price <= 0 or close_price <= 0 or high_price <= 0 or low_price <= 0:
            return False, None
        
        # 计算实体长度(阳线或阴线都可以)
        body_length = abs(close_price - open_price)
        
        # 计算下影线长度
        lower_shadow = min(open_price, close_price) - low_price
        
        # 计算上影线长度
        upper_shadow = high_price - max(open_price, close_price)
        
        # 条件2: 下影线长度 >= 实体长度的X倍（可配置）
        is_long_lower_shadow = lower_shadow >= body_length * lower_shadow_ratio
        
        if not is_long_lower_shadow:
            return False, None
        
        # 条件3: 上影线很短或几乎没有（上影线 <= 实体长度的Y%，可配置）
        is_short_upper_shadow = upper_shadow <= body_length * upper_shadow_ratio
        
        if not is_short_upper_shadow:
            return False, None
        
        # 返回形态信息
        return True, {
            'date': day_data.get('date'),
            'open': open_price,
            'close': close_price,
            'high': high_price,
            'low': low_price,
            'body_length': body_length,
            'lower_shadow': lower_shadow,
            'upper_shadow': upper_shadow,
            'shadow_body_ratio': lower_shadow / body_length if body_length > 0 else 0,
            'upper_shadow_ratio': upper_shadow / body_length if body_length > 0 else 0
        }
    
    @staticmethod
    def check_long_lower_shadow_conditions(historical_data: List[Dict], 
                                           downtrend_days: int = 20,
                                           recent_days: int = 2,
                                           lower_shadow_ratio: float = 1.0,
                                           upper_shadow_ratio: float = 0.3,
                                           min_amplitude: float = 0.02) -> Tuple[bool, Optional[Dict]]:
        """
        检查长下影线策略条件（参数化版本）
        
        策略要求:
        1. 下跌趋势: 当日最低价 < MA20(20日移动平均线)
        2. 长下影线: 最近N个交易日内出现(阳线或阴线均可)
        3. 上影线很短或几乎没有
        4. 振幅: 出现长下影线当日振幅超过指定值
        
        Args:
            historical_data: 历史数据列表（倒序，最新在前）
            downtrend_days: 下跌趋势判断天数(默认20天)
            recent_days: 检查长下影线的天数(默认2天)
            lower_shadow_ratio: 下影线长度 >= 实体长度的倍数（默认1.0）
            upper_shadow_ratio: 上影线 <= 实体长度的比例（默认0.3）
            min_amplitude: 最小振幅要求（默认0.02）
        
        Returns:
            (是否满足条件, 策略信息)
        """
        # 需要至少20个交易日的数据
        if len(historical_data) < downtrend_days:
            return False, None
        
        # 条件1: 检查下跌趋势
        is_downtrend = LongLowerShadowStrategy.check_downtrend(historical_data, downtrend_days)
        if not is_downtrend:
            return False, None
        
        # 条件2: 检查最近2个交易日内是否有长下影线(阳线或阴线)
        # 注意：我们需要前一天的收盘价来计算振幅，所以需要确保 historical_data 足够长
        
        long_lower_shadow_found = False
        pattern_info = None
        
        for i in range(min(recent_days, len(historical_data) - 1)):
            day_data = historical_data[i]
            prev_day_data = historical_data[i+1]
            
            # 计算振幅: (最高价 - 最低价) / 昨收
            high_price = float(day_data.get('high', 0))
            low_price = float(day_data.get('low', 0))
            pre_close = float(prev_day_data.get('close', 0))
            
            if pre_close <= 0:
                continue
                
            amplitude = (high_price - low_price) / pre_close
            
            # 振幅必须达到指定值（包含）
            if amplitude < min_amplitude:
                continue

            is_pattern, info = LongLowerShadowStrategy.check_long_lower_shadow(
                day_data, 
                lower_shadow_ratio=lower_shadow_ratio,
                upper_shadow_ratio=upper_shadow_ratio
            )
            if is_pattern:
                long_lower_shadow_found = True
                pattern_info = info
                # 将振幅信息添加到 pattern_info
                pattern_info['amplitude'] = amplitude
                break  # 找到第一个符合条件的就返回
        
        if not long_lower_shadow_found:
            return False, None
        
        # 计算MA20
        current_price = float(historical_data[0].get('close', 0))
        
        # 计算MA20（20日移动平均线）
        prices = []
        for i in range(downtrend_days):
            if i < len(historical_data):
                price = float(historical_data[i].get('close', 0))
                if price > 0:
                    prices.append(price)
        
        ma20 = sum(prices) / len(prices) if prices else 0
        
        # 计算相对MA20的偏离度
        deviation_from_ma20 = (current_price - ma20) / ma20 if ma20 > 0 else 0
        
        # 所有条件满足
        return True, {
            'pattern_date': pattern_info['date'],
            'pattern_open': pattern_info['open'],
            'pattern_close': pattern_info['close'],
            'pattern_high': pattern_info['high'],
            'pattern_low': pattern_info['low'],
            'body_length': pattern_info['body_length'],
            'lower_shadow': pattern_info['lower_shadow'],
            'upper_shadow': pattern_info['upper_shadow'],
            'shadow_body_ratio': pattern_info['shadow_body_ratio'],
            'amplitude': pattern_info.get('amplitude', 0),
            'current_price': current_price,
            'ma20': ma20,
            'deviation_from_ma20': deviation_from_ma20
        }
    
    @staticmethod
    def screening_long_lower_shadow_strategy(db: Session,
                                            lower_shadow_ratio: float = 1.0,
                                            upper_shadow_ratio: float = 0.3,
                                            min_amplitude: float = 0.02,
                                            recent_days: int = 2) -> List[Dict]:
        """
        长下影线选股策略主函数(支持阳线和阴线，参数化版本)
        
        策略要求:
        1. 股票范围: 排除创业板(3开头)、科创板(688开头)和北证A股(9开头)
        2. 下跌趋势: 当日最低价 < MA20(20日移动平均线)
        3. 长下影线: 最近N个交易日内出现(阳线或阴线均可)
        4. 上影线很短或几乎没有
        5. 振幅: 出现长下影线当日振幅超过指定值
        
        Args:
            db: 数据库会话
            lower_shadow_ratio: 下影线长度 >= 实体长度的倍数（默认1.0）
            upper_shadow_ratio: 上影线 <= 实体长度的比例（默认0.3）
            min_amplitude: 最小振幅要求（默认0.02）
            recent_days: 检查最近N个交易日（默认2天）
        
        Returns:
            符合条件的股票列表
        """
        results = []
        
        try:
            logger.info(f"开始执行长下影线选股策略 - 参数: 下影线倍数={lower_shadow_ratio}, "
                       f"上影线比例={upper_shadow_ratio}, 最小振幅={min_amplitude}, 检查天数={recent_days}")
            
            # 1. 获取A股股票列表（排除创业板、科创板和北证A股）
            stocks_query = db.execute(text("""
                SELECT DISTINCT code, name 
                FROM stock_basic_info 
                WHERE LENGTH(code) = 6
                AND code NOT LIKE '3%'      -- 排除创业板
                AND code NOT LIKE '688%'    -- 排除科创板
                AND code NOT LIKE '9%'      -- 排除北证A股
                AND COALESCE(collect_enabled, TRUE) = TRUE
                ORDER BY code
            """))
            
            stocks = stocks_query.fetchall()
            logger.info(f"找到 {len(stocks)} 只A股股票（已排除创业板、科创板和北证A股）")
            
            # 2. 计算查询日期范围（至少需要20个交易日的数据）
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)  # 往前推30天以确保有足够数据
            
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            logger.info(f"查询日期范围: {start_date_str} 至 {end_date_str}")
            
            # 3. 对每只股票执行选股策略
            for idx, (code, name) in enumerate(stocks):
                if idx % 100 == 0:
                    logger.info(f"处理进度: {idx}/{len(stocks)}")
                
                try:
                    # 获取该股票的历史数据（倒序，最新在前）
                    history_query = db.execute(text("""
                        SELECT code, name, date, open, close, high, low, 
                               change_percent, volume, amount
                        FROM historical_quotes 
                        WHERE code = :code 
                        AND date >= :start_date 
                        AND date <= :end_date
                        ORDER BY date DESC
                    """), {
                        'code': str(code),
                        'start_date': start_date_str,
                        'end_date': end_date_str
                    })
                    
                    history_rows = history_query.fetchall()
                    
                    if len(history_rows) < 20:  # 至少需要20个交易日的数据
                        continue
                    
                    # 转换为字典列表
                    historical_data = []
                    for row in history_rows:
                        date_val = row[2]
                        if hasattr(date_val, 'strftime'):
                            date_str = date_val.strftime('%Y-%m-%d')
                        else:
                            date_str = str(date_val)
                        
                        historical_data.append({
                            'code': row[0],
                            'name': row[1],
                            'date': date_str,
                            'open': float(row[3]) if row[3] else 0.0,
                            'close': float(row[4]) if row[4] else 0.0,
                            'high': float(row[5]) if row[5] else 0.0,
                            'low': float(row[6]) if row[6] else 0.0,
                            'change_percent': float(row[7]) if row[7] else 0.0,
                            'volume': float(row[8]) if row[8] else 0.0,
                            'amount': float(row[9]) if row[9] else 0.0
                        })
                    
                    # 检查长下影线策略条件（传入参数）
                    is_valid, strategy_info = LongLowerShadowStrategy.check_long_lower_shadow_conditions(
                        historical_data,
                        downtrend_days=20,
                        recent_days=recent_days,
                        lower_shadow_ratio=lower_shadow_ratio,
                        upper_shadow_ratio=upper_shadow_ratio,
                        min_amplitude=min_amplitude
                    )
                    
                    if not is_valid or not strategy_info:
                        continue
                    
                    # 获取当前价格信息
                    current_data = historical_data[0] if historical_data else {}
                    current_price = float(current_data.get('close', 0))
                    current_change_percent = current_data.get('change_percent', 0)
                    
                    # 所有条件满足，加入结果列表
                    result_item = {
                        'code': str(code),
                        'name': name,
                        'current_price': round(current_price, 2),
                        'current_change_percent': round(current_change_percent, 2) if current_change_percent else 0,
                        'pattern_date': strategy_info['pattern_date'],
                        'pattern_close': round(strategy_info['pattern_close'], 2),
                        'lower_shadow': round(strategy_info['lower_shadow'], 2),
                        'body_length': round(strategy_info['body_length'], 2),
                        'shadow_body_ratio': round(strategy_info['shadow_body_ratio'], 2),
                        'amplitude': round(strategy_info.get('amplitude', 0), 4),
                        'ma20': round(strategy_info.get('ma20', 0), 2),
                        'deviation_from_ma20': round(strategy_info.get('deviation_from_ma20', 0), 4)
                    }
                    
                    results.append(result_item)
                    logger.info(f"找到符合条件的股票: {code} {name}")
                    
                except Exception as e:
                    logger.error(f"处理股票 {code} 时出错: {str(e)}")
                    try:
                        db.rollback()
                    except Exception as rollback_error:
                        logger.warning(f"回滚事务时出错: {str(rollback_error)}")
                    continue
            
            logger.info(f"长下影线选股策略执行完成,找到 {len(results)} 只符合条件的股票")
            
        except Exception as e:
            logger.error(f"长下影线选股策略执行失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
        return results
