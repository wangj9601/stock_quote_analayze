"""
选股策略核心算法
实现创业板中线选股策略：涨停-回调-突破-跳空揉搓-均线多头
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


class StockScreeningStrategy:
    """选股策略类"""
    
    @staticmethod
    def find_first_limit_up(historical_data: List[Dict], months_before: int = 4) -> Optional[Dict]:
        """
        查找第一个涨停（今天涨停前3-4个月都没有过涨停）
        
        Args:
            historical_data: 历史数据列表，按日期倒序排列（最新在前）
            months_before: 往前检查的月数（默认4个月）
        
        Returns:
            涨停信息字典，包含日期、价格、low、high等，如果未找到返回None
        """
        if not historical_data or len(historical_data) < 1:
            return None
        
        # 计算需要检查的天数（大约）
        days_to_check = months_before * 30
        
        # 从最新数据往前查找（历史数据是倒序的）
        for i, data in enumerate(historical_data):
            change_percent = data.get('change_percent')
            if change_percent is not None and change_percent >= 9.8:
                # 找到第一个涨停，现在需要检查这个涨停往前推3-4个月是否有其他涨停
                limit_up_index = i
                
                # 检查这个涨停往前推3-4个月（索引从i+1开始，因为数据是倒序的）
                # 如果涨停在第i个位置，那么往前（更早的日期）是从i+1开始
                has_previous_limit_up = False
                
                # 往前检查足够的天数（大约days_to_check个交易日）
                # 考虑到交易日和自然日的差异，我们检查更多数据以确保覆盖3-4个月
                check_end_index = min(limit_up_index + days_to_check, len(historical_data))
                
                for j in range(limit_up_index + 1, check_end_index):
                    prev_data = historical_data[j]
                    prev_change_percent = prev_data.get('change_percent')
                    
                    # 如果往前3-4个月内有涨停，则不符合条件
                    if prev_change_percent is not None and prev_change_percent >= 9.8:
                        has_previous_limit_up = True
                        break
                
                # 如果往前3-4个月内没有涨停，则符合条件
                if not has_previous_limit_up:
                    return {
                        'date': data.get('date'),
                        'index': i,  # 在历史数据中的索引位置
                        'close': float(data.get('close', 0)),
                        'low': float(data.get('low', 0)),
                        'high': float(data.get('high', 0)),
                        'open': float(data.get('open', 0)),
                        'change_percent': change_percent
                    }
                # 如果往前有涨停，继续往后查找下一个涨停（更新的日期）
        
        return None
    
    @staticmethod
    def check_pullback_not_break_bottom(historical_data: List[Dict], limit_up_info: Dict) -> Tuple[bool, Optional[Dict]]:
        """
        检查回调不破涨停底部
        
        Args:
            historical_data: 历史数据列表（倒序）
            limit_up_info: 涨停信息
        
        Returns:
            (是否满足条件, 回调信息)
        """
        limit_up_index = limit_up_info['index']
        limit_up_low = limit_up_info['low']
        
        # 在涨停之后的日期中查找回调（从涨停索引往前，因为数据是倒序的）
        pullback_found = False
        pullback_info = None
        
        # 涨停后的数据（索引更小，日期更新）
        for i in range(limit_up_index - 1, -1, -1):
            if i < 0 or i >= len(historical_data):
                break
            
            data = historical_data[i]
            current_low = float(data.get('low', 0))
            current_close = float(data.get('close', 0))
            
            # 如果最低价跌破涨停底部，不符合条件
            if current_low < limit_up_low:
                return False, None
            
            # 如果出现回调（收盘价低于涨停价，但最低价不低于涨停底部）
            if current_close < limit_up_info['close']:
                pullback_found = True
                pullback_info = {
                    'date': data.get('date'),
                    'index': i,
                    'low': current_low,
                    'close': current_close
                }
                break
        
        return pullback_found, pullback_info
    
    @staticmethod
    def check_breakthrough(historical_data: List[Dict], limit_up_info: Dict) -> Tuple[bool, Optional[Dict]]:
        """
        检查突破涨停高点
        
        Args:
            historical_data: 历史数据列表（倒序）
            limit_up_info: 涨停信息
        
        Returns:
            (是否满足条件, 突破信息)
        """
        limit_up_index = limit_up_info['index']
        limit_up_high = limit_up_info['high']
        
        # 在涨停之后的日期中查找突破（从最新数据往前查找）
        for i in range(limit_up_index - 1, -1, -1):
            if i < 0 or i >= len(historical_data):
                break
            
            data = historical_data[i]
            current_high = float(data.get('high', 0))
            current_close = float(data.get('close', 0))
            
            # 如果最高价突破涨停高点
            if current_high > limit_up_high:
                return True, {
                    'date': data.get('date'),
                    'index': i,
                    'high': current_high,
                    'close': current_close
                }
        
        return False, None
    
    @staticmethod
    def check_gap_and_doji(historical_data: List[Dict], limit_up_index: int, breakthrough_index: int) -> Tuple[bool, List[str], List[str]]:
        """
        检查涨停和突破之间的向上跳空和揉搓线
        
        Args:
            historical_data: 历史数据列表（倒序）
            limit_up_index: 涨停索引
            breakthrough_index: 突破索引
        
        Returns:
            (是否满足条件, 跳空日期列表, 揉搓线日期列表)
        """
        gap_dates = []
        doji_dates = []
        
        # 确定检查范围（从涨停到突破之间，注意索引是倒序的）
        start_idx = breakthrough_index + 1  # 突破后的第一个交易日
        end_idx = limit_up_index - 1  # 涨停前的最后一个交易日
        
        if start_idx > end_idx:
            return False, [], []
        
        # 从突破往涨停方向检查（索引递减）
        # 注意：数据是倒序的，索引i对应的是较新的日期，i+1对应的是较旧的日期（前一日）
        for i in range(start_idx, end_idx + 1):
            if i >= len(historical_data) or i < 0:
                continue
            
            current_data = historical_data[i]
            # 前一日数据（时间上更早，索引更大）
            if i + 1 < len(historical_data):
                prev_data = historical_data[i + 1]
                
                # 检查向上跳空：当日最低价 > 前一日最高价
                current_low = float(current_data.get('low', 0))
                prev_high = float(prev_data.get('high', 0))
                
                if current_low > prev_high and prev_high > 0:
                    gap_dates.append(str(current_data.get('date')))
                
                # 检查揉搓线
                current_open = float(current_data.get('open', 0))
                current_close = float(current_data.get('close', 0))
                current_high = float(current_data.get('high', 0))
                current_low = float(current_data.get('low', 0))
                prev_close = float(prev_data.get('close', 0))
                
                if prev_close > 0:
                    # 实体大小（相对前收盘）
                    body_size = abs(current_close - current_open) / prev_close
                    # 上影线长度
                    upper_shadow = (current_high - max(current_open, current_close)) / prev_close
                    # 下影线长度
                    lower_shadow = (min(current_open, current_close) - current_low) / prev_close
                    
                    # 揉搓线：实体小（<2%）且上下影线都较长（>1%）
                    if body_size < 0.02 and upper_shadow > 0.01 and lower_shadow > 0.01:
                        doji_dates.append(str(current_data.get('date')))
        
        # 至少需要有一个向上跳空和一个揉搓线
        has_gap = len(gap_dates) > 0
        has_doji = len(doji_dates) > 0
        
        return has_gap and has_doji, gap_dates, doji_dates
    
    @staticmethod
    def check_ma_alignment(historical_data: List[Dict], current_index: int = 0) -> Tuple[bool, Dict]:
        """
        检查均线多头排列（MA5 > MA10 > MA20）
        注意：只要满足MA5 > MA10 > MA20即可，不一定要求所有均线都向上发散
        
        Args:
            historical_data: 历史数据列表（倒序，最新在前）
            current_index: 当前日期索引（默认0，即最新日期）
        
        Returns:
            (是否满足条件, 均线信息)
        """
        if len(historical_data) < 20:
            return False, {}
        
        # 提取收盘价（从当前往前取足够的数据）
        closes = []
        for i in range(current_index, min(current_index + 20, len(historical_data))):
            closes.append(float(historical_data[i].get('close', 0)))
        
        if len(closes) < 20:
            return False, {}
        
        # 计算均线
        closes_array = np.array(closes)
        ma5 = np.mean(closes_array[:5]) if len(closes_array) >= 5 else 0
        ma10 = np.mean(closes_array[:10]) if len(closes_array) >= 10 else 0
        ma20 = np.mean(closes_array[:20]) if len(closes_array) >= 20 else 0
        
        ma_info = {
            'ma5': round(ma5, 2),
            'ma10': round(ma10, 2),
            'ma20': round(ma20, 2)
        }
        
        # 检查多头排列：MA5 > MA10 > MA20
        # 只要满足这个条件即可，不要求所有均线都向上发散
        is_aligned = ma5 > ma10 > ma20
        
        return is_aligned, ma_info
    
    @staticmethod
    def screening_cyb_midline_strategy(db: Session, months: int = 4) -> List[Dict]:
        """
        创业板中线选股策略主函数
        
        Args:
            db: 数据库会话
            months: 查询月数（默认4个月）
        
        Returns:
            符合条件的股票列表
        """
        results = []
        
        try:
            # 1. 获取创业板股票列表（代码以3开头，排除ST股票）
            cyb_stocks_query = db.execute(text("""
                SELECT DISTINCT code, name 
                FROM stock_basic_info 
                WHERE code LIKE '3%' AND LENGTH(code) = 6
                AND name NOT LIKE '%ST%'
                AND COALESCE(collect_enabled, TRUE) = TRUE
                ORDER BY code
            """))
            
            cyb_stocks = cyb_stocks_query.fetchall()
            logger.info(f"找到 {len(cyb_stocks)} 只创业板股票")
            
            # 2. 计算查询日期范围
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=months * 30)
            
            # 转换为字符串格式（数据库中的date字段是text类型）
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            logger.info(f"查询日期范围: {start_date_str} 至 {end_date_str}")
            
            # 3. 对每只股票执行选股策略
            for idx, (code, name) in enumerate(cyb_stocks):
                if idx % 100 == 0:
                    logger.info(f"处理进度: {idx}/{len(cyb_stocks)}")
                
                try:
                    # 获取该股票的历史数据（倒序，最新在前）
                    # 注意：数据库中的date字段是text类型，所以使用字符串比较
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
                    
                    if len(history_rows) < 20:  # 数据不足
                        continue
                    
                    # 转换为字典列表
                    historical_data = []
                    for row in history_rows:
                        date_val = row[2]
                        # 确保日期是字符串格式
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
                    
                    # 检查策略条件
                    # 条件1：查找第一个涨停（今天涨停前3-4个月都没有过涨停）
                    limit_up_info = StockScreeningStrategy.find_first_limit_up(historical_data, months_before=months)
                    if not limit_up_info:
                        continue
                    
                    # 条件2：检查回调不破底
                    has_pullback, pullback_info = StockScreeningStrategy.check_pullback_not_break_bottom(
                        historical_data, limit_up_info
                    )
                    if not has_pullback:
                        continue
                    
                    # 条件3：检查突破涨停高点
                    has_breakthrough, breakthrough_info = StockScreeningStrategy.check_breakthrough(
                        historical_data, limit_up_info
                    )
                    if not has_breakthrough:
                        continue
                    
                    # 条件4：检查跳空和揉搓线
                    has_gap_doji, gap_dates, doji_dates = StockScreeningStrategy.check_gap_and_doji(
                        historical_data, 
                        limit_up_info['index'], 
                        breakthrough_info['index']
                    )
                    if not has_gap_doji:
                        continue
                    
                    # 条件5：检查均线多头排列（使用最新数据）
                    has_ma_alignment, ma_info = StockScreeningStrategy.check_ma_alignment(
                        historical_data, current_index=0
                    )
                    if not has_ma_alignment:
                        continue
                    
                    # 获取当前价格信息
                    current_data = historical_data[0] if historical_data else {}
                    current_price = float(current_data.get('close', 0))
                    current_change_percent = current_data.get('change_percent', 0)
                    
                    # 所有条件满足，加入结果列表
                    result_item = {
                        'code': str(code),
                        'name': name,
                        'limit_up_date': str(limit_up_info['date']),
                        'limit_up_price': round(limit_up_info['close'], 2),
                        'limit_up_low': round(limit_up_info['low'], 2),
                        'limit_up_high': round(limit_up_info['high'], 2),
                        'breakthrough_date': str(breakthrough_info['date']),
                        'breakthrough_price': round(breakthrough_info['close'], 2),
                        'current_price': round(current_price, 2),
                        'current_change_percent': round(current_change_percent, 2) if current_change_percent else 0,
                        'ma5': ma_info.get('ma5', 0),
                        'ma10': ma_info.get('ma10', 0),
                        'ma20': ma_info.get('ma20', 0),
                        'gap_dates': gap_dates,
                        'doji_dates': doji_dates
                    }
                    
                    results.append(result_item)
                    logger.info(f"找到符合条件的股票: {code} {name}")
                    
                except Exception as e:
                    logger.error(f"处理股票 {code} 时出错: {str(e)}")
                    # 回滚事务以重置失败状态，避免影响后续查询
                    try:
                        db.rollback()
                    except Exception as rollback_error:
                        logger.warning(f"回滚事务时出错: {str(rollback_error)}")
                    continue
            
            logger.info(f"选股策略执行完成，找到 {len(results)} 只符合条件的股票")
            
        except Exception as e:
            logger.error(f"选股策略执行失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
        return results
    
    @staticmethod
    def check_volume_increase(historical_data: List[Dict], limit_up_index: int, days_before: int = 15) -> bool:
        """
        检查涨停日是否为放量上涨
        
        Args:
            historical_data: 历史数据列表（倒序）
            limit_up_index: 涨停日的索引
            days_before: 往前检查的天数（用于计算平均成交量）
        
        Returns:
            是否为放量上涨
        """
        if limit_up_index + days_before >= len(historical_data):
            return False
        
        limit_up_data = historical_data[limit_up_index]
        limit_up_volume = float(limit_up_data.get('volume', 0))
        
        if limit_up_volume <= 0:
            return False
        
        # 计算涨停前days_before天的平均成交量
        volumes = []
        for i in range(limit_up_index + 1, min(limit_up_index + 1 + days_before, len(historical_data))):
            vol = float(historical_data[i].get('volume', 0))
            if vol > 0:
                volumes.append(vol)
        
        if len(volumes) == 0:
            return False
        
        avg_volume = sum(volumes) / len(volumes)
        
        # 涨停日的成交量应该大于平均成交量的1.5倍（放量）
        return limit_up_volume >= avg_volume * 1.5
    
    @staticmethod
    def check_parking_apron_conditions(historical_data: List[Dict], threshold: int = 15) -> Tuple[bool, Optional[Dict]]:
        """
        检查停机坪策略条件
        
        策略要求：
        1. 最近15日有涨幅大于9.5%，且必须是放量上涨
        2. 紧接的下个交易日必须高开，收盘价必须上涨，且与开盘价不能大于等于相差3%
        3. 接下2、3个交易日必须高开，收盘价必须上涨，且与开盘价不能大于等于相差3%，且每天涨跌幅在5%间
        
        Args:
            historical_data: 历史数据列表（倒序，最新在前）
            threshold: 检查的天数（默认15天）
        
        Returns:
            (是否满足条件, 涨停信息)
        """
        if len(historical_data) < threshold + 3:
            return False, None
        
        # 查找最近threshold天内涨幅大于9.5%的涨停日
        limit_up_info = None
        for i in range(min(threshold, len(historical_data))):
            data = historical_data[i]
            change_percent = data.get('change_percent')
            
            if change_percent is not None and change_percent > 9.5:
                # 检查是否为放量上涨
                if StockScreeningStrategy.check_volume_increase(historical_data, i, days_before=15):
                    limit_up_info = {
                        'index': i,
                        'date': data.get('date'),
                        'close': float(data.get('close', 0)),
                        'open': float(data.get('open', 0)),
                        'high': float(data.get('high', 0)),
                        'low': float(data.get('low', 0)),
                        'change_percent': change_percent
                    }
                    break
        
        if not limit_up_info:
            return False, None
        
        limit_up_index = limit_up_info['index']
        limit_up_price = limit_up_info['close']
        
        # 检查涨停后的3个交易日
        # 注意：数据是倒序的，涨停日在索引i，那么下一个交易日是索引i-1（更新的日期）
        if limit_up_index < 3:
            return False, None
        
        # 条件2：紧接的下个交易日（索引limit_up_index - 1）
        day1 = historical_data[limit_up_index - 1]
        day1_open = float(day1.get('open', 0))
        day1_close = float(day1.get('close', 0))
        day1_change_percent = day1.get('change_percent', 0)
        
        # 必须高开（开盘价 > 涨停收盘价）
        if day1_open <= limit_up_price:
            return False, None
        
        # 收盘价必须上涨（收盘价 > 涨停收盘价）
        if day1_close <= limit_up_price:
            return False, None
        
        # 收盘价与开盘价不能大于等于相差3%（即 0.97 <= close/open <= 1.03）
        if day1_open <= 0:
            return False, None
        
        close_open_ratio = day1_close / day1_open
        if close_open_ratio < 0.97 or close_open_ratio >= 1.03:
            return False, None
        
        # 条件3：接下2、3个交易日（索引limit_up_index - 2 和 limit_up_index - 3）
        for day_offset in [2, 3]:
            day_idx = limit_up_index - day_offset
            if day_idx < 0:
                return False, None
            
            day_data = historical_data[day_idx]
            day_open = float(day_data.get('open', 0))
            day_close = float(day_data.get('close', 0))
            day_change_percent = day_data.get('change_percent', 0)
            
            # 必须高开（开盘价 > 涨停收盘价）
            if day_open <= limit_up_price:
                return False, None
            
            # 收盘价必须上涨（收盘价 > 涨停收盘价）
            if day_close <= limit_up_price:
                return False, None
            
            # 收盘价与开盘价不能大于等于相差3%
            if day_open <= 0:
                return False, None
            
            close_open_ratio = day_close / day_open
            if close_open_ratio < 0.97 or close_open_ratio >= 1.03:
                return False, None
            
            # 每天涨跌幅在5%间（-5% < change_percent < 5%）
            if day_change_percent <= -5 or day_change_percent >= 5:
                return False, None
        
        return True, limit_up_info
    
    @staticmethod
    def screening_parking_apron_strategy(db: Session) -> List[Dict]:
        """
        停机坪选股策略主函数
        
        策略要求：
        1. 最近15日有涨幅大于9.5%，且必须是放量上涨
        2. 紧接的下个交易日必须高开，收盘价必须上涨，且与开盘价不能大于等于相差3%
        3. 接下2、3个交易日必须高开，收盘价必须上涨，且与开盘价不能大于等于相差3%，且每天涨跌幅在5%间
        
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
                WHERE LENGTH(code) = 6 AND code NOT LIKE '3%'
                AND COALESCE(collect_enabled, TRUE) = TRUE
                ORDER BY code
            """))
            
            stocks = stocks_query.fetchall()
            logger.info(f"找到 {len(stocks)} 只A股股票")
            
            # 2. 计算查询日期范围（最近20个交易日，确保有足够数据）
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
                    
                    if len(history_rows) < 18:  # 至少需要18个交易日的数据
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
                    
                    # 检查停机坪策略条件
                    is_valid, limit_up_info = StockScreeningStrategy.check_parking_apron_conditions(
                        historical_data, threshold=15
                    )
                    
                    if not is_valid or not limit_up_info:
                        continue
                    
                    # 获取当前价格信息
                    current_data = historical_data[0] if historical_data else {}
                    current_price = float(current_data.get('close', 0))
                    current_change_percent = current_data.get('change_percent', 0)
                    
                    # 所有条件满足，加入结果列表
                    result_item = {
                        'code': str(code),
                        'name': name,
                        'limit_up_date': str(limit_up_info['date']),
                        'limit_up_price': round(limit_up_info['close'], 2),
                        'current_price': round(current_price, 2),
                        'current_change_percent': round(current_change_percent, 2) if current_change_percent else 0
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
            
            logger.info(f"停机坪选股策略执行完成，找到 {len(results)} 只符合条件的股票")
            
        except Exception as e:
            logger.error(f"停机坪选股策略执行失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
        return results
    
    @staticmethod
    def calculate_ma250(historical_data: List[Dict]) -> List[float]:
        """
        计算250日均线（年线）
        
        Args:
            historical_data: 历史数据列表（按日期正序排列，最旧在前）
        
        Returns:
            MA250值列表
        """
        if len(historical_data) < 250:
            return []
        
        closes = [float(data.get('close', 0)) for data in historical_data]
        ma250_list = []
        
        for i in range(len(closes)):
            if i < 249:
                ma250_list.append(0.0)  # 前249个数据点无法计算MA250
            else:
                # 计算最近250个交易日的平均收盘价
                ma250 = np.mean(closes[i-249:i+1])
                ma250_list.append(ma250)
        
        return ma250_list
    
    @staticmethod
    def check_backtrace_ma250_conditions(historical_data: List[Dict], threshold: int = 60) -> Tuple[bool, Optional[Dict]]:
        """
        检查回踩年线策略条件
        
        策略要求：
        1. 时间段：前段=最近60交易日最高收盘价之前交易日(长度>0)，后段=最高价当日及后面的交易日
        2. 前段由年线(250日)以下向上突破
        3. 后段必须在年线以上运行，且后段最低价日与最高价日相差必须在10-50日间
        4. 回踩伴随缩量：最高价日交易量/后段最低价日交易量>2,后段最低价/最高价<0.8
        
        Args:
            historical_data: 历史数据列表（倒序，最新在前）
            threshold: 检查的天数（默认60天）
        
        Returns:
            (是否满足条件, 策略信息)
        """
        # 需要至少250个交易日的数据来计算年线
        if len(historical_data) < 250:
            return False, None
        
        # 取最近threshold天的数据（倒序，最新在前）
        recent_data = historical_data[:threshold] if len(historical_data) >= threshold else historical_data
        
        # 为了计算MA250，需要获取足够的历史数据（至少250天，按日期正序）
        # 从数据库中获取的数据是倒序的，需要反转
        all_data_for_ma = historical_data[:250]  # 取最近250天的数据
        all_data_for_ma_reversed = list(reversed(all_data_for_ma))  # 反转为正序
        
        # 计算MA250（需要正序数据）
        ma250_list = StockScreeningStrategy.calculate_ma250(all_data_for_ma_reversed)
        
        if len(ma250_list) == 0:
            return False, None
        
        # 将MA250值添加到数据中（注意：ma250_list是正序的，需要反转回倒序）
        ma250_list_reversed = list(reversed(ma250_list))
        for i, data in enumerate(recent_data):
            if i < len(ma250_list_reversed):
                data['ma250'] = ma250_list_reversed[i]
            else:
                data['ma250'] = 0.0
        
        # 找到最近threshold天内最高收盘价及其日期
        highest_close = 0.0
        highest_index = -1
        highest_date = None
        highest_volume = 0.0
        
        for i, data in enumerate(recent_data):
            close = float(data.get('close', 0))
            if close > highest_close:
                highest_close = close
                highest_index = i
                highest_date = data.get('date')
                highest_volume = float(data.get('volume', 0))
        
        if highest_index < 0 or highest_volume <= 0:
            return False, None
        
        # 将数据分为前段和后段
        # 前段：最高价日之前的交易日（索引 > highest_index，因为数据是倒序的）
        # 后段：最高价日及之后的交易日（索引 <= highest_index）
        front_segment = recent_data[highest_index + 1:] if highest_index + 1 < len(recent_data) else []
        back_segment = recent_data[:highest_index + 1]  # 包含最高价日
        
        if len(front_segment) == 0:
            return False, None
        
        # 条件2：前段由年线以下向上突破
        # 检查前段第一个交易日（时间上最早，索引最大）和最后一个交易日（时间上最晚，索引最小）
        front_first = front_segment[-1] if front_segment else None  # 时间上最早的交易日
        front_last = front_segment[0] if front_segment else None   # 时间上最晚的交易日（接近最高价日）
        
        if not front_first or not front_last:
            return False, None
        
        front_first_close = float(front_first.get('close', 0))
        front_first_ma250 = float(front_first.get('ma250', 0))
        front_last_close = float(front_last.get('close', 0))
        front_last_ma250 = float(front_last.get('ma250', 0))
        
        # 前段第一个交易日的收盘价应该在年线以下，最后一个交易日的收盘价应该在年线以上
        if front_first_close >= front_first_ma250 or front_last_close <= front_last_ma250:
            return False, None
        
        # 条件3：后段必须在年线以上运行，且后段最低价日与最高价日相差必须在10-50日间
        if len(back_segment) == 0:
            return False, None
        
        # 检查后段所有交易日是否都在年线以上
        lowest_in_back = float('inf')
        lowest_index_in_back = -1
        lowest_date_in_back = None
        lowest_volume_in_back = 0.0
        
        for i, data in enumerate(back_segment):
            close = float(data.get('close', 0))
            ma250 = float(data.get('ma250', 0))
            
            # 后段必须在年线以上运行
            if ma250 > 0 and close < ma250:
                return False, None
            
            # 找到后段中的最低价
            if close < lowest_in_back:
                lowest_in_back = close
                lowest_index_in_back = i
                lowest_date_in_back = data.get('date')
                lowest_volume_in_back = float(data.get('volume', 0))
        
        if lowest_index_in_back < 0 or lowest_volume_in_back <= 0:
            return False, None
        
        # 计算最低价日与最高价日的日期差（交易日差）
        # 由于数据是倒序的，最高价日在索引0，最低价日在索引lowest_index_in_back
        # 交易日差 = lowest_index_in_back（因为数据是倒序的）
        trading_days_diff = lowest_index_in_back
        
        # 后段最低价日与最高价日相差必须在10-50日间
        if trading_days_diff < 10 or trading_days_diff > 50:
            return False, None
        
        # 条件4：回踩伴随缩量
        # 最高价日交易量/后段最低价日交易量>2
        volume_ratio = highest_volume / lowest_volume_in_back if lowest_volume_in_back > 0 else 0
        if volume_ratio <= 2:
            return False, None
        
        # 后段最低价/最高价<0.8
        price_ratio = lowest_in_back / highest_close if highest_close > 0 else 1.0
        if price_ratio >= 0.8:
            return False, None
        
        # 所有条件满足
        return True, {
            'highest_date': highest_date,
            'highest_price': highest_close,
            'highest_volume': highest_volume,
            'lowest_date': lowest_date_in_back,
            'lowest_price': lowest_in_back,
            'lowest_volume': lowest_volume_in_back,
            'trading_days_diff': trading_days_diff,
            'volume_ratio': volume_ratio,
            'price_ratio': price_ratio
        }
    
    @staticmethod
    def screening_backtrace_ma250_strategy(db: Session) -> List[Dict]:
        """
        回踩年线选股策略主函数
        
        策略要求：
        1. 时间段：前段=最近60交易日最高收盘价之前交易日(长度>0)，后段=最高价当日及后面的交易日
        2. 前段由年线(250日)以下向上突破
        3. 后段必须在年线以上运行，且后段最低价日与最高价日相差必须在10-50日间
        4. 回踩伴随缩量：最高价日交易量/后段最低价日交易量>2,后段最低价/最高价<0.8
        
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
            
            # 2. 计算查询日期范围（至少需要250个交易日的数据）
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=400)  # 往前推400天以确保有足够数据
            
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
                    
                    if len(history_rows) < 250:  # 至少需要250个交易日的数据
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
                    
                    # 检查回踩年线策略条件
                    is_valid, strategy_info = StockScreeningStrategy.check_backtrace_ma250_conditions(
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
                        'highest_date': strategy_info['highest_date'],
                        'highest_price': round(strategy_info['highest_price'], 2),
                        'lowest_date': strategy_info['lowest_date'],
                        'lowest_price': round(strategy_info['lowest_price'], 2),
                        'current_price': round(current_price, 2),
                        'current_change_percent': round(current_change_percent, 2) if current_change_percent else 0,
                        'trading_days_diff': strategy_info['trading_days_diff'],
                        'volume_ratio': round(strategy_info['volume_ratio'], 2),
                        'price_ratio': round(strategy_info['price_ratio'], 4)
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
            
            logger.info(f"回踩年线选股策略执行完成，找到 {len(results)} 只符合条件的股票")
            
        except Exception as e:
            logger.error(f"回踩年线选股策略执行失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
        return results

