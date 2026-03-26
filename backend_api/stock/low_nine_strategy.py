"""
低九策略选股
独立策略文件

策略要求:
应用于下跌趋势中，构成条件：
连续 9 根K线（或交易日），每一天的收盘价都低于它前面第4天的收盘价。

股票范围:
- 全部A股
- 排除ST股票（包括ST、*ST、S*ST等所有ST类股票）
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


class LowNineStrategy:
    """低九策略选股类"""
    
    @staticmethod
    def check_low_nine_pattern(historical_data: List[Dict]) -> Tuple[bool, Optional[Dict]]:
        """
        检查是否满足低九策略
        
        策略要求:
        连续 9 根K线（或交易日），每一天的收盘价都低于它前面第4天的收盘价。
        
        Args:
            historical_data: 历史数据列表（倒序，最新在前）
        
        Returns:
            (是否满足条件, 策略信息)
        """
        # 需要至少13个交易日的数据（9天 + 4天前置数据）
        if len(historical_data) < 13:
            return False, None
        
        # 检查连续9天的收盘价是否都低于其前面第4天的收盘价
        # historical_data[0] 是最新的一天
        # 我们检查 historical_data[0] 到 historical_data[8] 这9天
        
        pattern_valid = True
        pattern_start_date = None
        pattern_end_date = None
        
        for i in range(9):
            # 当前天的收盘价
            current_close = float(historical_data[i].get('close', 0))
            
            # 前面第4天的收盘价（i+4 因为数据是倒序的）
            fourth_day_before_close = float(historical_data[i + 4].get('close', 0))
            
            # 检查数据有效性
            if current_close <= 0 or fourth_day_before_close <= 0:
                pattern_valid = False
                break
            
            # 检查条件：当前收盘价必须低于前面第4天的收盘价
            if current_close >= fourth_day_before_close:
                pattern_valid = False
                break
            
            # 记录日期范围
            if i == 0:
                pattern_end_date = historical_data[i].get('date')
            if i == 8:
                pattern_start_date = historical_data[i].get('date')
        
        if not pattern_valid:
            return False, None
        
        # 计算一些统计信息
        current_price = float(historical_data[0].get('close', 0))
        pattern_start_price = float(historical_data[8].get('close', 0))
        
        # 计算9天的跌幅
        decline_ratio = (current_price - pattern_start_price) / pattern_start_price if pattern_start_price > 0 else 0
        
        # 计算9天内的最高价和最低价
        prices = [float(historical_data[i].get('close', 0)) for i in range(9)]
        max_price = max(prices)
        min_price = min(prices)
        
        # 所有条件满足
        return True, {
            'pattern_start_date': pattern_start_date,
            'pattern_end_date': pattern_end_date,
            'pattern_start_price': pattern_start_price,
            'current_price': current_price,
            'decline_ratio': decline_ratio,
            'max_price_in_9days': max_price,
            'min_price_in_9days': min_price
        }
    
    @staticmethod
    def screening_low_nine_strategy(db: Session, limit: int = None) -> List[Dict]:
        """
        低九策略选股主函数
        
        策略要求:
        连续 9 根K线（或交易日），每一天的收盘价都低于它前面第4天的收盘价。
        
        Args:
            db: 数据库会话
            limit: 限制处理的股票数量（用于测试，None表示处理所有）
        
        Returns:
            符合条件的股票列表
        """
        results = []
        
        try:
            logger.info("=" * 60)
            logger.info("开始执行低九策略选股")
            logger.info("=" * 60)
            
            # 1. 获取A股股票列表（排除ST股票）
            stocks_query = db.execute(text("""
                SELECT DISTINCT code, name 
                FROM stock_basic_info 
                WHERE LENGTH(code) = 6
                AND name NOT LIKE '%ST%'
                AND COALESCE(collect_enabled, TRUE) = TRUE
                ORDER BY code
            """))
            
            stocks = stocks_query.fetchall()
            total_stocks = len(stocks)
            
            # 如果设置了limit，只处理前N只股票
            if limit:
                stocks = stocks[:limit]
                logger.info(f"测试模式：只处理前 {limit} 只股票（总共 {total_stocks} 只）")
            else:
                logger.info(f"生产模式：处理所有 {total_stocks} 只A股股票")
            
            # 2. 计算查询日期范围（至少需要13个交易日的数据）
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)  # 往前推30天以确保有足够数据
            
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            logger.info(f"查询日期范围: {start_date_str} 至 {end_date_str}")
            logger.info("-" * 60)
            
            # 3. 对每只股票执行选股策略
            processed_count = 0
            error_count = 0
            
            for idx, (code, name) in enumerate(stocks):
                # 每处理100只股票输出一次进度
                if idx % 100 == 0:
                    progress = (idx / len(stocks)) * 100
                    logger.info(f"处理进度: {idx}/{len(stocks)} ({progress:.1f}%) - "
                              f"找到: {len(results)} 只, 错误: {error_count} 只")
                
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
                    
                    if len(history_rows) < 13:  # 至少需要13个交易日的数据
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
                    
                    # 检查低九策略条件
                    is_valid, strategy_info = LowNineStrategy.check_low_nine_pattern(historical_data)
                    
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
                        'pattern_start_date': strategy_info['pattern_start_date'],
                        'pattern_end_date': strategy_info['pattern_end_date'],
                        'pattern_start_price': round(strategy_info['pattern_start_price'], 2),
                        'decline_ratio': round(strategy_info['decline_ratio'], 4),
                        'max_price_in_9days': round(strategy_info['max_price_in_9days'], 2),
                        'min_price_in_9days': round(strategy_info['min_price_in_9days'], 2)
                    }
                    
                    results.append(result_item)
                    logger.info(f"✓ 找到符合条件的股票: {code} {name} (跌幅: {strategy_info['decline_ratio']*100:.2f}%)")
                    
                    processed_count += 1
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"✗ 处理股票 {code} 时出错: {str(e)}")
                    try:
                        db.rollback()
                    except Exception as rollback_error:
                        logger.warning(f"回滚事务时出错: {str(rollback_error)}")
                    continue
            
            logger.info("=" * 60)
            logger.info(f"低九策略选股执行完成!")
            logger.info(f"处理股票数: {processed_count}/{len(stocks)}")
            logger.info(f"找到符合条件: {len(results)} 只")
            logger.info(f"处理错误: {error_count} 只")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"低九策略选股执行失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
        return results
