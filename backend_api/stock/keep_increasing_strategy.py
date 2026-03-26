"""
持续上涨（MA30向上）选股策略
独立策略文件

策略要求：
1. 均线多头：30日前的30日均线 < 20日前的30日均线 < 10日前的30日均线 < 当日的30日均线
2. 涨幅要求：(当日的30日均线 / 30日前的30日均线) > 1.2
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


class KeepIncreasingStrategy:
    """持续上涨（MA30向上）选股策略类"""
    
    @staticmethod
    def calculate_ma30(historical_data: List[Dict]) -> List[float]:
        """
        计算30日均线
        
        Args:
            historical_data: 历史数据列表（按日期正序排列，最旧在前）
        
        Returns:
            MA30值列表
        """
        if len(historical_data) < 30:
            return []
        
        closes = [float(data.get('close', 0)) for data in historical_data]
        ma30_list = []
        
        for i in range(len(closes)):
            if i < 29:
                ma30_list.append(0.0)  # 前29个数据点无法计算MA30
            else:
                # 计算最近30个交易日的平均收盘价
                ma30 = np.mean(closes[i-29:i+1])
                ma30_list.append(ma30)
        
        return ma30_list
    
    @staticmethod
    def check_keep_increasing_conditions(historical_data: List[Dict], threshold: int = 30) -> Tuple[bool, Optional[Dict]]:
        """
        检查持续上涨（MA30向上）策略条件
        
        策略要求：
        1. 均线多头：30日前的30日均线 < 20日前的30日均线 < 10日前的30日均线 < 当日的30日均线
        2. 涨幅要求：(当日的30日均线 / 30日前的30日均线) > 1.2
        
        Args:
            historical_data: 历史数据列表（倒序，最新在前）
            threshold: 检查的天数（默认30天）
        
        Returns:
            (是否满足条件, 策略信息)
        """
        # 需要至少30个交易日的数据来计算MA30
        if len(historical_data) < threshold:
            return False, None
        
        # 取最近threshold天的数据（倒序，最新在前）
        recent_data = historical_data[:threshold] if len(historical_data) >= threshold else historical_data
        
        # 为了计算MA30，需要获取足够的历史数据（至少30天，按日期正序）
        # 从数据库中获取的数据是倒序的，需要反转
        all_data_for_ma = historical_data[:threshold]  # 取最近threshold天的数据
        all_data_for_ma_reversed = list(reversed(all_data_for_ma))  # 反转为正序
        
        # 计算MA30（需要正序数据）
        ma30_list = KeepIncreasingStrategy.calculate_ma30(all_data_for_ma_reversed)
        
        if len(ma30_list) == 0:
            return False, None
        
        # 将MA30值添加到数据中（注意：ma30_list是正序的，需要反转回倒序）
        ma30_list_reversed = list(reversed(ma30_list))
        for i, data in enumerate(recent_data):
            if i < len(ma30_list_reversed):
                data['ma30'] = ma30_list_reversed[i]
            else:
                data['ma30'] = 0.0
        
        # 计算关键时间点的索引
        # 数据是倒序的：索引0是当日，索引threshold-1是30日前
        # step1 = round(30/3) = 10，表示20日前（索引10）
        # step2 = round(30*2/3) = 20，表示10日前（索引20）
        step1 = round(threshold / 3)  # 20日前
        step2 = round(threshold * 2 / 3)  # 10日前
        
        # 获取各个时间点的MA30值
        # 注意：数据是倒序的
        # ma30_list_reversed[0] 是当日的MA30
        # ma30_list_reversed[step1] 是20日前的MA30
        # ma30_list_reversed[step2] 是10日前的MA30
        # ma30_list_reversed[threshold-1] 是30日前的MA30
        
        if len(ma30_list_reversed) < threshold:
            return False, None
        
        ma30_current = ma30_list_reversed[0]  # 当日的MA30
        ma30_step1 = ma30_list_reversed[step1] if step1 < len(ma30_list_reversed) else 0.0  # 20日前的MA30
        ma30_step2 = ma30_list_reversed[step2] if step2 < len(ma30_list_reversed) else 0.0  # 10日前的MA30
        ma30_before_30 = ma30_list_reversed[threshold - 1]  # 30日前的MA30
        
        # 检查MA30值是否有效
        if ma30_current <= 0 or ma30_step1 <= 0 or ma30_step2 <= 0 or ma30_before_30 <= 0:
            return False, None
        
        # 条件1：均线多头
        # 30日前的30日均线 < 20日前的30日均线 < 10日前的30日均线 < 当日的30日均线
        if not (ma30_before_30 < ma30_step1 < ma30_step2 < ma30_current):
            return False, None
        
        # 条件2：涨幅要求
        # (当日的30日均线 / 30日前的30日均线) > 1.2
        ma30_ratio = ma30_current / ma30_before_30 if ma30_before_30 > 0 else 0
        if ma30_ratio <= 1.2:
            return False, None
        
        # 所有条件满足
        return True, {
            'current_ma30': ma30_current,
            'ma30_before_30': ma30_before_30,
            'ma30_step1': ma30_step1,
            'ma30_step2': ma30_step2,
            'ma30_increase_ratio': ma30_ratio - 1.0  # 涨幅比例（用于显示）
        }
    
    @staticmethod
    def screening_keep_increasing_strategy(db: Session) -> List[Dict]:
        """
        持续上涨（MA30向上）选股策略主函数
        
        策略要求：
        1. 均线多头：30日前的30日均线 < 20日前的30日均线 < 10日前的30日均线 < 当日的30日均线
        2. 涨幅要求：(当日的30日均线 / 30日前的30日均线) > 1.2
        
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
            
            # 2. 计算查询日期范围（至少需要30个交易日的数据）
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=60)  # 往前推60天以确保有足够数据
            
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
                    
                    if len(history_rows) < 30:  # 至少需要30个交易日的数据
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
                    
                    # 检查持续上涨策略条件
                    is_valid, strategy_info = KeepIncreasingStrategy.check_keep_increasing_conditions(
                        historical_data, threshold=30
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
                        'current_ma30': round(strategy_info['current_ma30'], 2),
                        'ma30_before_30': round(strategy_info['ma30_before_30'], 2),
                        'ma30_increase_ratio': round(strategy_info['ma30_increase_ratio'], 4)
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
            
            logger.info(f"持续上涨（MA30向上）选股策略执行完成，找到 {len(results)} 只符合条件的股票")
            
        except Exception as e:
            logger.error(f"持续上涨（MA30向上）选股策略执行失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
        return results

