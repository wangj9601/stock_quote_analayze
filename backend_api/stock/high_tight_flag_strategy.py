"""
高而窄的旗形选股策略
独立策略文件

策略要求：
1. 必须至少上市交易60日
2. 当日收盘价/之前24~10日的最低价>=1.9
3. 之前24~10日必须连续两天涨幅大于等于9.5%
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


class HighTightFlagStrategy:
    """高而窄的旗形选股策略类"""
    
    @staticmethod
    def check_high_tight_flag_conditions(historical_data: List[Dict], threshold: int = 60) -> Tuple[bool, Optional[Dict]]:
        """
        检查高而窄的旗形策略条件
        
        策略要求：
        1. 必须至少上市交易60日
        2. 当日收盘价/之前24~10日的最低价>=1.9
        3. 之前24~10日必须连续两天涨幅大于等于9.5%
        
        Args:
            historical_data: 历史数据列表（倒序，最新在前）
            threshold: 检查的天数（默认60天）
        
        Returns:
            (是否满足条件, 策略信息)
        """
        # 条件1：必须至少上市交易60日
        if len(historical_data) < threshold:
            return False, None
        
        # 取最近threshold天的数据（倒序，最新在前）
        recent_data = historical_data[:threshold] if len(historical_data) >= threshold else historical_data
        
        # 需要至少24天的数据
        if len(recent_data) < 24:
            return False, None
        
        # 取最近24天的数据
        data_24 = recent_data[:24]
        
        # 取前14天（即24~10日，从第10日到第24日）
        # 注意：数据是倒序的，索引0是最新的一天，索引23是最旧的一天
        # 24~10日对应索引10到23（共14天）
        if len(data_24) < 14:
            return False, None
        
        period_data = data_24[10:24]  # 24~10日的数据（共14天）
        
        # 条件2：当日收盘价/之前24~10日的最低价>=1.9
        # 当日收盘价是索引0的收盘价
        current_close = float(recent_data[0].get('close', 0))
        if current_close <= 0:
            return False, None
        
        # 计算24~10日的最低价
        period_lows = [float(data.get('low', 0)) for data in period_data if float(data.get('low', 0)) > 0]
        if len(period_lows) == 0:
            return False, None
        
        period_low = min(period_lows)
        if period_low <= 0:
            return False, None
        
        price_ratio = current_close / period_low
        if price_ratio < 1.9:
            return False, None
        
        # 条件3：之前24~10日必须连续两天涨幅大于等于9.5%
        # 检查period_data中是否有连续两天涨幅>=9.5%
        previous_p_change = 0.0
        consecutive_days_found = False
        
        for data in period_data:
            p_change = float(data.get('change_percent', 0))
            
            if p_change >= 9.5:
                if previous_p_change >= 9.5:
                    consecutive_days_found = True
                    break
                else:
                    previous_p_change = p_change
            else:
                previous_p_change = 0.0
        
        if not consecutive_days_found:
            return False, None
        
        # 所有条件满足
        return True, {
            'current_price': current_close,
            'period_low': period_low,
            'price_ratio': price_ratio
        }
    
    @staticmethod
    def screening_high_tight_flag_strategy(db: Session) -> List[Dict]:
        """
        高而窄的旗形选股策略主函数
        
        策略要求：
        1. 必须至少上市交易60日
        2. 当日收盘价/之前24~10日的最低价>=1.9
        3. 之前24~10日必须连续两天涨幅大于等于9.5%
        
        Args:
            db: 数据库会话
        
        Returns:
            符合条件的股票列表
        """
        results = []
        
        try:
            # 1. 获取全部A股股票列表
            stocks_query = db.execute(text("""
                SELECT DISTINCT code, name 
                FROM stock_basic_info 
                WHERE LENGTH(code) = 6
                AND COALESCE(collect_enabled, TRUE) = TRUE
                ORDER BY code
            """))
            
            stocks = stocks_query.fetchall()
            logger.info(f"找到 {len(stocks)} 只A股股票")
            
            # 2. 计算查询日期范围（至少需要60个交易日的数据）
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=100)  # 往前推100天以确保有足够数据
            
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
                    
                    if len(history_rows) < 60:  # 至少需要60个交易日的数据
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
                    
                    # 检查高而窄的旗形策略条件
                    is_valid, strategy_info = HighTightFlagStrategy.check_high_tight_flag_conditions(
                        historical_data, threshold=60
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
                        'period_low': round(strategy_info['period_low'], 2),
                        'price_ratio': round(strategy_info['price_ratio'], 2)
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
            
            logger.info(f"高而窄的旗形选股策略执行完成，找到 {len(results)} 只符合条件的股票")
            
        except Exception as e:
            logger.error(f"高而窄的旗形选股策略执行失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
        return results

