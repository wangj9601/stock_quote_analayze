"""
一阳穿三线选股策略
独立策略文件

策略要求:
识别股价在均线系统粘合或走平过程中，出现一根带量长阳线并一次性向上突破至少三根移动平均线的技术形态。

核心条件:
1. 长阳线：实体占比>=70%，涨幅>=3%
2. 穿越至少3条均线（MA5/10/20/30/60/120中的任意3条或更多）
3. 成交量放大：当日成交量>=前5日平均成交量的2倍
4. 位置判别：根据60日最高价回撤幅度判断低位/中位/高位
5. 乖离率计算：评估回调风险

股票范围:
- 全部A股
- 排除ST股票（包括ST、*ST、S*ST等所有ST类股票）
"""

import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Optional
import logging
import json
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class OneYangThreeLinesStrategy:
    """一阳穿三线选股策略类"""
    
    @staticmethod
    def calculate_moving_averages(
        historical_data: List[Dict], 
        current_index: int = 0
    ) -> Dict[str, float]:
        """
        计算多条移动平均线
        
        Args:
            historical_data: 历史数据列表(倒序,最新在前)
            current_index: 当前日期索引
            
        Returns:
            均线字典: {'ma5': float, 'ma10': float, ...}
        """
        # 定义需要计算的均线周期
        periods = [5, 10, 20, 30, 60, 120]
        ma_values = {}
        
        # 对每个周期计算移动平均线
        for period in periods:
            # 检查数据是否足够
            if current_index + period > len(historical_data):
                # 数据不足，返回None
                ma_values[f'ma{period}'] = None
                logger.warning(f"数据不足以计算MA{period}，需要{period}个数据点，实际只有{len(historical_data) - current_index}个")
                continue
            
            # 提取从current_index开始的period个收盘价
            # historical_data是倒序的（最新在前），所以从current_index开始取period个
            closes = []
            for i in range(current_index, current_index + period):
                close_price = historical_data[i].get('close')
                if close_price is None or close_price <= 0:
                    logger.warning(f"索引{i}处的收盘价无效: {close_price}")
                    break
                closes.append(float(close_price))
            
            # 如果成功提取了足够的收盘价，计算平均值
            if len(closes) == period:
                ma_value = sum(closes) / period
                ma_values[f'ma{period}'] = round(ma_value, 4)  # 保留4位小数
            else:
                ma_values[f'ma{period}'] = None
                logger.warning(f"无法计算MA{period}，有效数据点不足")
        
        return ma_values
    
    @staticmethod
    def check_long_yang_candle(candle_data: Dict) -> Tuple[bool, Dict]:
        """
        检查是否为长阳线
        
        条件:
        1. 收盘价 > 开盘价 (阳线)
        2. 实体长度占K线总长度 >= 70%
        3. 涨幅 >= 3%
        
        Args:
            candle_data: K线数据
            
        Returns:
            (是否为长阳线, 阳线信息)
        """
        # 提取K线数据
        open_price = candle_data.get('open')
        close_price = candle_data.get('close')
        high_price = candle_data.get('high')
        low_price = candle_data.get('low')
        
        # 初始化返回信息
        candle_info = {
            'is_yang': False,
            'body_length': 0.0,
            'total_length': 0.0,
            'body_ratio': 0.0,
            'change_percent': 0.0
        }
        
        # 验证数据有效性
        if None in [open_price, close_price, high_price, low_price]:
            logger.warning(f"K线数据不完整: open={open_price}, close={close_price}, high={high_price}, low={low_price}")
            return False, candle_info
        
        # 转换为浮点数
        try:
            open_price = float(open_price)
            close_price = float(close_price)
            high_price = float(high_price)
            low_price = float(low_price)
        except (ValueError, TypeError) as e:
            logger.warning(f"K线数据类型转换失败: {e}")
            return False, candle_info
        
        # 验证价格合理性
        if open_price <= 0 or close_price <= 0 or high_price <= 0 or low_price <= 0:
            logger.warning(f"K线价格数据无效: open={open_price}, close={close_price}, high={high_price}, low={low_price}")
            return False, candle_info
        
        # 条件1: 判断是否为阳线（收盘价 > 开盘价）
        is_yang = close_price > open_price
        candle_info['is_yang'] = is_yang
        
        if not is_yang:
            return False, candle_info
        
        # 条件2: 计算实体长度和K线总长度
        body_length = close_price - open_price  # 阳线实体长度
        total_length = high_price - low_price    # K线总长度
        
        candle_info['body_length'] = round(body_length, 4)
        candle_info['total_length'] = round(total_length, 4)
        
        # 如果K线总长度为0（一字板），无法计算占比
        if total_length == 0:
            logger.warning(f"K线总长度为0，无法计算实体占比")
            return False, candle_info
        
        # 计算实体占比
        body_ratio = body_length / total_length
        candle_info['body_ratio'] = round(body_ratio, 4)
        
        # 条件3: 判断实体占比是否 >= 70%
        # 使用rounded后的值进行比较，避免浮点数精度问题
        if candle_info['body_ratio'] < 0.7:
            return False, candle_info
        
        # 条件4: 计算涨幅
        change_percent = (close_price - open_price) / open_price
        candle_info['change_percent'] = round(change_percent, 4)
        
        # 判断涨幅是否 >= 3%
        # 使用rounded后的值进行比较，避免浮点数精度问题
        if candle_info['change_percent'] < 0.03:
            return False, candle_info
        
        # 所有条件都满足，返回True
        return True, candle_info
    
    @staticmethod
    def check_cross_three_lines(
        candle_data: Dict,
        ma_values: Dict[str, float]
    ) -> Tuple[bool, List[str], int]:
        """
        检查是否穿越至少三条均线
        
        条件:
        1. 收盘价 > 至少三条均线
        2. 开盘价 < 这三条均线中的至少两条
        3. 最低价 < 这三条均线中的至少一条
        
        Args:
            candle_data: K线数据
            ma_values: 均线值字典
            
        Returns:
            (是否穿越, 穿越的均线列表, 穿越数量)
        """
        # 提取K线数据
        open_price = candle_data.get('open')
        close_price = candle_data.get('close')
        low_price = candle_data.get('low')
        
        # 验证数据有效性
        if None in [open_price, close_price, low_price]:
            logger.warning(f"K线数据不完整: open={open_price}, close={close_price}, low={low_price}")
            return False, [], 0
        
        # 转换为浮点数
        try:
            open_price = float(open_price)
            close_price = float(close_price)
            low_price = float(low_price)
        except (ValueError, TypeError) as e:
            logger.warning(f"K线数据类型转换失败: {e}")
            return False, [], 0
        
        # 验证价格合理性
        if open_price <= 0 or close_price <= 0 or low_price <= 0:
            logger.warning(f"K线价格数据无效: open={open_price}, close={close_price}, low={low_price}")
            return False, [], 0
        
        # 定义均线名称列表
        ma_names = ['ma5', 'ma10', 'ma20', 'ma30', 'ma60', 'ma120']
        
        # 筛选出有效的均线（非None且大于0）
        valid_mas = {}
        for ma_name in ma_names:
            ma_value = ma_values.get(ma_name)
            if ma_value is not None and ma_value > 0:
                valid_mas[ma_name] = float(ma_value)
        
        # 如果有效均线少于3条，无法判断
        if len(valid_mas) < 3:
            logger.warning(f"有效均线数量不足3条: {len(valid_mas)}")
            return False, [], 0
        
        # 条件1: 找出收盘价大于的均线
        close_above_mas = []
        for ma_name, ma_value in valid_mas.items():
            if close_price > ma_value:
                close_above_mas.append(ma_name)
        
        # 如果收盘价大于的均线少于3条，不满足条件
        if len(close_above_mas) < 3:
            return False, [], 0
        
        # 条件2: 在收盘价大于的均线中，找出开盘价小于的均线
        open_below_mas = []
        for ma_name in close_above_mas:
            ma_value = valid_mas[ma_name]
            if open_price < ma_value:
                open_below_mas.append(ma_name)
        
        # 开盘价必须小于至少2条均线
        if len(open_below_mas) < 2:
            return False, [], 0
        
        # 条件3: 在收盘价大于的均线中，找出最低价低于的均线
        low_below_mas = []
        for ma_name in close_above_mas:
            ma_value = valid_mas[ma_name]
            if low_price < ma_value:
                low_below_mas.append(ma_name)
        
        # 最低价必须低于至少1条均线
        if len(low_below_mas) < 1:
            return False, [], 0
        
        # 所有条件都满足，返回穿越的均线列表
        # 穿越的均线是指：收盘价大于、开盘价小于、最低价低于的均线
        # 实际上就是close_above_mas中同时满足开盘价和最低价条件的均线
        crossed_lines = []
        for ma_name in close_above_mas:
            ma_value = valid_mas[ma_name]
            # 穿越的定义：收盘价在均线上方，且开盘价或最低价在均线下方
            if open_price < ma_value or low_price < ma_value:
                crossed_lines.append(ma_name)
        
        # 穿越的均线数量
        crossed_count = len(crossed_lines)
        
        # 必须穿越至少3条均线
        if crossed_count < 3:
            return False, [], 0
        
        return True, crossed_lines, crossed_count
    
    @staticmethod
    def check_volume_increase(
        historical_data: List[Dict],
        current_index: int,
        days_before: int = 5
    ) -> Tuple[bool, float, float]:
        """
        检查成交量是否放大
        
        条件:
        1. 当日成交量 >= 前期平均成交量的2倍
        2. 换手率在3%-10%之间为理想
        
        Args:
            historical_data: 历史数据列表(倒序,最新在前)
            current_index: 当前日期索引
            days_before: 计算平均成交量的天数
            
        Returns:
            (是否放量, 成交量倍数, 换手率)
        """
        # 获取当日数据
        if current_index >= len(historical_data):
            logger.warning(f"当前索引{current_index}超出数据范围{len(historical_data)}")
            return False, 0.0, 0.0
        
        current_data = historical_data[current_index]
        
        # 获取当日成交量
        current_volume = current_data.get('volume')
        if current_volume is None or current_volume <= 0:
            logger.warning(f"当日成交量数据无效: {current_volume}")
            return False, 0.0, 0.0
        
        try:
            current_volume = float(current_volume)
        except (ValueError, TypeError) as e:
            logger.warning(f"当日成交量类型转换失败: {e}")
            return False, 0.0, 0.0
        
        # 获取当日换手率
        turnover_rate = current_data.get('turnover_rate')
        if turnover_rate is None:
            # 换手率可能为None，设置为0
            turnover_rate = 0.0
            logger.warning(f"当日换手率数据缺失，设置为0")
        else:
            try:
                turnover_rate = float(turnover_rate)
            except (ValueError, TypeError) as e:
                logger.warning(f"换手率类型转换失败: {e}")
                turnover_rate = 0.0
        
        # 检查是否有足够的历史数据来计算平均成交量
        # 需要从current_index+1开始往后取days_before个交易日
        if current_index + days_before >= len(historical_data):
            logger.warning(f"历史数据不足以计算前{days_before}日平均成交量")
            return False, 0.0, turnover_rate
        
        # 计算前期平均成交量（前days_before个交易日）
        volumes = []
        for i in range(current_index + 1, current_index + 1 + days_before):
            volume = historical_data[i].get('volume')
            if volume is None or volume <= 0:
                logger.warning(f"索引{i}处的成交量无效: {volume}")
                continue
            try:
                volumes.append(float(volume))
            except (ValueError, TypeError) as e:
                logger.warning(f"索引{i}处的成交量类型转换失败: {e}")
                continue
        
        # 如果有效成交量数据不足，无法计算平均值
        if len(volumes) == 0:
            logger.warning(f"前{days_before}日没有有效的成交量数据")
            return False, 0.0, turnover_rate
        
        # 计算平均成交量
        avg_volume = sum(volumes) / len(volumes)
        
        # 如果平均成交量为0，无法计算倍数
        if avg_volume == 0:
            logger.warning(f"前{days_before}日平均成交量为0")
            return False, 0.0, turnover_rate
        
        # 计算成交量倍数
        volume_ratio = current_volume / avg_volume
        volume_ratio = round(volume_ratio, 2)  # 保留2位小数
        
        # 判断是否放量（当日成交量 >= 前期平均成交量的2倍）
        is_volume_increase = volume_ratio >= 2.0
        
        return is_volume_increase, volume_ratio, turnover_rate
    
    @staticmethod
    def check_position_type(
        historical_data: List[Dict],
        current_index: int
    ) -> Tuple[str, float]:
        """
        判断突破位置类型
        
        分类:
        - 低位: 距离60日最高价回撤 >= 30%
        - 中位: 回撤在10%-30%之间
        - 高位: 回撤 < 10%
        
        Args:
            historical_data: 历史数据列表(倒序,最新在前)
            current_index: 当前日期索引
            
        Returns:
            (位置类型, 回撤幅度)
        """
        # 获取当日数据
        if current_index >= len(historical_data):
            logger.warning(f"当前索引{current_index}超出数据范围{len(historical_data)}")
            return "未知", 0.0
        
        current_data = historical_data[current_index]
        
        # 获取当前价格（收盘价）
        current_price = current_data.get('close')
        if current_price is None or current_price <= 0:
            logger.warning(f"当前价格数据无效: {current_price}")
            return "未知", 0.0
        
        try:
            current_price = float(current_price)
        except (ValueError, TypeError) as e:
            logger.warning(f"当前价格类型转换失败: {e}")
            return "未知", 0.0
        
        # 检查是否有足够的历史数据来计算60日最高价
        # 需要从current_index开始往后取60个交易日
        days_needed = 60
        if current_index + days_needed > len(historical_data):
            logger.warning(f"历史数据不足以计算60日最高价，需要{days_needed}个数据点，实际只有{len(historical_data) - current_index}个")
            return "未知", 0.0
        
        # 计算60日最高价（包括当日）
        high_prices = []
        for i in range(current_index, current_index + days_needed):
            high_price = historical_data[i].get('high')
            if high_price is None or high_price <= 0:
                logger.warning(f"索引{i}处的最高价无效: {high_price}")
                continue
            try:
                high_prices.append(float(high_price))
            except (ValueError, TypeError) as e:
                logger.warning(f"索引{i}处的最高价类型转换失败: {e}")
                continue
        
        # 如果没有有效的最高价数据，无法计算
        if len(high_prices) == 0:
            logger.warning(f"60日内没有有效的最高价数据")
            return "未知", 0.0
        
        # 找出60日最高价
        max_high_60d = max(high_prices)
        
        # 如果60日最高价为0，无法计算回撤幅度
        if max_high_60d == 0:
            logger.warning(f"60日最高价为0")
            return "未知", 0.0
        
        # 计算回撤幅度（百分比）
        # 回撤幅度 = (60日最高价 - 当前价格) / 60日最高价 × 100%
        retracement = (max_high_60d - current_price) / max_high_60d * 100
        retracement = round(retracement, 2)  # 保留2位小数
        
        # 根据回撤幅度判断位置类型
        if retracement >= 30:
            position_type = "低位"
        elif retracement >= 10:
            position_type = "中位"
        else:
            position_type = "高位"
        
        return position_type, retracement
    
    @staticmethod
    def calculate_bias(
        current_price: float,
        ma_values: Dict[str, float]
    ) -> Dict[str, float]:
        """
        计算乖离率
        
        公式: BIAS = (收盘价 - MA) / MA × 100%
        
        Args:
            current_price: 当前价格
            ma_values: 均线值字典
            
        Returns:
            乖离率字典: {'bias5': float, 'bias10': float, 'bias30': float}
        """
        # 验证当前价格有效性
        if current_price is None or current_price <= 0:
            logger.warning(f"当前价格数据无效: {current_price}")
            return {'bias5': None, 'bias10': None, 'bias30': None}
        
        try:
            current_price = float(current_price)
        except (ValueError, TypeError) as e:
            logger.warning(f"当前价格类型转换失败: {e}")
            return {'bias5': None, 'bias10': None, 'bias30': None}
        
        # 初始化乖离率字典
        bias_values = {}
        
        # 定义需要计算乖离率的均线周期
        periods = [5, 10, 30]
        
        # 对每个周期计算乖离率
        for period in periods:
            ma_key = f'ma{period}'
            bias_key = f'bias{period}'
            
            # 获取对应的均线值
            ma_value = ma_values.get(ma_key)
            
            # 检查均线值是否有效
            if ma_value is None or ma_value <= 0:
                logger.warning(f"均线{ma_key}数据无效: {ma_value}，无法计算乖离率")
                bias_values[bias_key] = None
                continue
            
            try:
                ma_value = float(ma_value)
            except (ValueError, TypeError) as e:
                logger.warning(f"均线{ma_key}类型转换失败: {e}")
                bias_values[bias_key] = None
                continue
            
            # 计算乖离率: BIAS = (收盘价 - MA) / MA × 100%
            bias = (current_price - ma_value) / ma_value * 100
            bias_values[bias_key] = round(bias, 2)  # 保留2位小数
        
        return bias_values
    
    @staticmethod
    def calculate_signal_score(
        crossed_lines_count: int,
        volume_ratio: float,
        turnover_rate: float,
        position_type: str,
        bias30: float
    ) -> int:
        """
        计算信号质量评分(0-100分)
        
        评分规则:
        - 穿越均线数量: 3条=20分, 4条=30分, 5条=40分, 6条=50分
        - 成交量倍数: >=2倍=20分, >=3倍=25分
        - 换手率: 3%-10%=15分, 其他=5分
        - 位置类型: 低位=15分, 中位=10分, 高位=0分
        - 乖离率: <5%=10分, 5%-10%=5分, >10%=0分
        
        Args:
            crossed_lines_count: 穿越的均线数量
            volume_ratio: 成交量倍数
            turnover_rate: 换手率
            position_type: 位置类型
            bias30: 30日乖离率
            
        Returns:
            信号质量评分
        """
        score = 0
        
        # 1. 根据穿越均线数量评分
        if crossed_lines_count == 3:
            score += 20
        elif crossed_lines_count == 4:
            score += 30
        elif crossed_lines_count == 5:
            score += 40
        elif crossed_lines_count >= 6:
            score += 50
        
        # 2. 根据成交量倍数评分
        if volume_ratio >= 3.0:
            score += 25
        elif volume_ratio >= 2.0:
            score += 20
        
        # 3. 根据换手率评分
        if 3.0 <= turnover_rate <= 10.0:
            score += 15
        else:
            score += 5
        
        # 4. 根据位置类型评分
        if position_type == "低位":
            score += 15
        elif position_type == "中位":
            score += 10
        elif position_type == "高位":
            score += 0
        
        # 5. 根据乖离率评分
        # 如果bias30为None，给0分
        if bias30 is None:
            score += 0
        elif bias30 < 5.0:
            score += 10
        elif 5.0 <= bias30 <= 10.0:
            score += 5
        else:  # bias30 > 10.0
            score += 0
        
        return score
    
    @staticmethod
    def screening_one_yang_three_lines_strategy(
        db: Session,
        limit: int = None
    ) -> List[Dict]:
        """
        一阳穿三线选股策略主函数
        
        执行流程:
        1. 获取A股股票列表(排除ST)
        2. 获取最近20个交易日的历史数据
        3. 计算6条移动平均线(MA5/10/20/30/60/120)
        4. 检查最新K线是否为长阳线
        5. 检查是否穿越至少三条均线
        6. 验证成交量放大
        7. 判断位置类型
        8. 计算乖离率
        9. 计算信号质量评分
        10. 返回符合条件的股票列表
        
        Args:
            db: 数据库会话
            limit: 限制处理的股票数量（用于测试，None表示处理所有）
            
        Returns:
            符合条件的股票列表
        """
        results = []
        
        try:
            logger.info("=" * 60)
            logger.info("开始执行一阳穿三线选股策略")
            logger.info("=" * 60)
            
            # 1. 获取A股股票列表（排除ST股票）
            stocks_query = db.execute(text("""
                SELECT DISTINCT code, name 
                FROM stock_basic_info 
                WHERE LENGTH(code) = 6
                AND name NOT LIKE '%ST%'
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
            
            logger.info(f"找到 {len(stocks)} 只A股股票（已排除ST股票）")
            
            # 2. 计算查询日期范围（需要至少120个交易日的数据以计算MA120）
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=250)  # 往前推250天以确保有足够数据
            
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            logger.info(f"查询日期范围: {start_date_str} 至 {end_date_str}")
            logger.info("-" * 60)
            
            # 3. 对每只股票执行策略检查
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
                               change_percent, volume, amount, turnover_rate
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
                    
                    # 至少需要120个交易日的数据以计算MA120
                    if len(history_rows) < 120:
                        logger.warning(f"股票 {code} 数据不足，跳过（需要120个交易日，实际{len(history_rows)}个）")
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
                            'amount': float(row[9]) if row[9] else 0.0,
                            'turnover_rate': float(row[10]) if row[10] else 0.0
                        })
                    
                    # 获取当前K线数据（最新的一天）
                    current_candle = historical_data[0]
                    
                    # 4. 检查最新K线是否为长阳线
                    is_long_yang, candle_info = OneYangThreeLinesStrategy.check_long_yang_candle(current_candle)
                    
                    if not is_long_yang:
                        continue
                    
                    # 5. 计算6条移动平均线
                    ma_values = OneYangThreeLinesStrategy.calculate_moving_averages(historical_data, current_index=0)
                    
                    # 检查是否所有均线都计算成功
                    if any(v is None for v in ma_values.values()):
                        logger.warning(f"股票 {code} 均线计算失败，跳过")
                        continue
                    
                    # 6. 检查是否穿越至少三条均线
                    is_cross, crossed_lines, crossed_count = OneYangThreeLinesStrategy.check_cross_three_lines(
                        current_candle, ma_values
                    )
                    
                    if not is_cross:
                        continue
                    
                    # 7. 验证成交量放大
                    is_volume_increase, volume_ratio, turnover_rate = OneYangThreeLinesStrategy.check_volume_increase(
                        historical_data, current_index=0, days_before=5
                    )
                    
                    if not is_volume_increase:
                        continue
                    
                    # 8. 判断位置类型
                    position_type, retracement = OneYangThreeLinesStrategy.check_position_type(
                        historical_data, current_index=0
                    )
                    
                    # 9. 计算乖离率
                    current_price = float(current_candle.get('close', 0))
                    bias_values = OneYangThreeLinesStrategy.calculate_bias(current_price, ma_values)
                    
                    # 10. 计算信号质量评分
                    signal_score = OneYangThreeLinesStrategy.calculate_signal_score(
                        crossed_count,
                        volume_ratio,
                        turnover_rate,
                        position_type,
                        bias_values.get('bias30')
                    )
                    
                    # 11. 生成风险提示
                    risk_warnings = []
                    
                    # 换手率警告
                    if turnover_rate < 3.0:
                        risk_warnings.append("动能不足")
                    elif turnover_rate > 10.0:
                        risk_warnings.append("可能存在对倒")
                    
                    # 高位突破警告
                    if position_type == "高位":
                        risk_warnings.append("警惕诱多")
                    
                    # 高乖离率警告
                    if bias_values.get('bias30') and bias_values.get('bias30') > 10.0:
                        risk_warnings.append("乖离过大，注意回调风险")
                    
                    # 12. 构建结果项
                    result_item = {
                        'code': str(code),
                        'name': name,
                        'signal_date': current_candle.get('date'),
                        'current_price': round(current_price, 2),
                        'ma5': round(ma_values.get('ma5', 0), 2),
                        'ma10': round(ma_values.get('ma10', 0), 2),
                        'ma20': round(ma_values.get('ma20', 0), 2),
                        'ma30': round(ma_values.get('ma30', 0), 2),
                        'ma60': round(ma_values.get('ma60', 0), 2),
                        'ma120': round(ma_values.get('ma120', 0), 2),
                        'crossed_lines': '+'.join([ma.upper() for ma in crossed_lines]),
                        'crossed_count': crossed_count,
                        'volume_ratio': round(volume_ratio, 2),
                        'turnover_rate': round(turnover_rate, 2),
                        'position_type': position_type,
                        'retracement': round(retracement, 2),
                        'bias5': round(bias_values.get('bias5', 0), 2) if bias_values.get('bias5') is not None else None,
                        'bias10': round(bias_values.get('bias10', 0), 2) if bias_values.get('bias10') is not None else None,
                        'bias30': round(bias_values.get('bias30', 0), 2) if bias_values.get('bias30') is not None else None,
                        'signal_score': signal_score,
                        'risk_warnings': risk_warnings
                    }
                    
                    # 13. 保存信号到数据库（可选）
                    try:
                        # 将signal_date转换为date对象
                        signal_date_str = current_candle.get('date')
                        if isinstance(signal_date_str, str):
                            signal_date_obj = datetime.strptime(signal_date_str, '%Y-%m-%d').date()
                        elif isinstance(signal_date_str, date):
                            signal_date_obj = signal_date_str
                        elif isinstance(signal_date_str, datetime):
                            signal_date_obj = signal_date_str.date()
                        else:
                            signal_date_obj = datetime.now().date()
                        
                        # 将风险提示列表转换为JSON字符串
                        risk_warnings_json = json.dumps(risk_warnings, ensure_ascii=False)
                        
                        # 使用INSERT ... ON CONFLICT DO UPDATE实现去重和更新
                        # PostgreSQL语法
                        insert_sql = text("""
                            INSERT INTO one_yang_three_lines_signals 
                            (code, name, signal_date, current_price, ma5, ma10, ma20, ma30, ma60, ma120,
                             crossed_lines, crossed_count, volume_ratio, turnover_rate, position_type, 
                             retracement, bias5, bias10, bias30, signal_score, risk_warnings, created_at)
                            VALUES 
                            (:code, :name, :signal_date, :current_price, :ma5, :ma10, :ma20, :ma30, :ma60, :ma120,
                             :crossed_lines, :crossed_count, :volume_ratio, :turnover_rate, :position_type,
                             :retracement, :bias5, :bias10, :bias30, :signal_score, :risk_warnings, :created_at)
                            ON CONFLICT (code, signal_date) 
                            DO UPDATE SET
                                name = EXCLUDED.name,
                                current_price = EXCLUDED.current_price,
                                ma5 = EXCLUDED.ma5,
                                ma10 = EXCLUDED.ma10,
                                ma20 = EXCLUDED.ma20,
                                ma30 = EXCLUDED.ma30,
                                ma60 = EXCLUDED.ma60,
                                ma120 = EXCLUDED.ma120,
                                crossed_lines = EXCLUDED.crossed_lines,
                                crossed_count = EXCLUDED.crossed_count,
                                volume_ratio = EXCLUDED.volume_ratio,
                                turnover_rate = EXCLUDED.turnover_rate,
                                position_type = EXCLUDED.position_type,
                                retracement = EXCLUDED.retracement,
                                bias5 = EXCLUDED.bias5,
                                bias10 = EXCLUDED.bias10,
                                bias30 = EXCLUDED.bias30,
                                signal_score = EXCLUDED.signal_score,
                                risk_warnings = EXCLUDED.risk_warnings
                        """)
                        
                        db.execute(insert_sql, {
                            'code': str(code),
                            'name': name,
                            'signal_date': signal_date_obj,
                            'current_price': round(current_price, 2),
                            'ma5': round(ma_values.get('ma5', 0), 2),
                            'ma10': round(ma_values.get('ma10', 0), 2),
                            'ma20': round(ma_values.get('ma20', 0), 2),
                            'ma30': round(ma_values.get('ma30', 0), 2),
                            'ma60': round(ma_values.get('ma60', 0), 2),
                            'ma120': round(ma_values.get('ma120', 0), 2),
                            'crossed_lines': '+'.join([ma.upper() for ma in crossed_lines]),
                            'crossed_count': crossed_count,
                            'volume_ratio': round(volume_ratio, 2),
                            'turnover_rate': round(turnover_rate, 2),
                            'position_type': position_type,
                            'retracement': round(retracement, 2),
                            'bias5': round(bias_values.get('bias5', 0), 2) if bias_values.get('bias5') is not None else None,
                            'bias10': round(bias_values.get('bias10', 0), 2) if bias_values.get('bias10') is not None else None,
                            'bias30': round(bias_values.get('bias30', 0), 2) if bias_values.get('bias30') is not None else None,
                            'signal_score': signal_score,
                            'risk_warnings': risk_warnings_json,
                            'created_at': datetime.now()
                        })
                        
                        db.commit()
                        logger.debug(f"信号已保存到数据库: {code} {name} {signal_date_str}")
                        
                    except IntegrityError as ie:
                        # 唯一约束冲突，说明该信号已存在
                        db.rollback()
                        logger.debug(f"信号已存在，跳过保存: {code} {signal_date_str}")
                    except Exception as save_error:
                        # 保存失败不影响策略执行，记录错误日志并继续
                        db.rollback()
                        logger.error(f"保存信号到数据库失败: {code} {name} - {str(save_error)}")
                    
                    results.append(result_item)
                    logger.info(f"✓ 找到符合条件的股票: {code} {name} (评分: {signal_score}, 穿越: {crossed_count}条均线)")
                    
                    processed_count += 1
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"✗ 处理股票 {code} 时出错: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    try:
                        db.rollback()
                    except Exception as rollback_error:
                        logger.warning(f"回滚事务时出错: {str(rollback_error)}")
                    continue
            
            # 13. 按评分降序排列结果
            results.sort(key=lambda x: x['signal_score'], reverse=True)
            
            logger.info("=" * 60)
            logger.info(f"一阳穿三线策略执行完成!")
            logger.info(f"处理股票数: {processed_count}/{len(stocks)}")
            logger.info(f"找到符合条件: {len(results)} 只")
            logger.info(f"信号已保存到数据库: one_yang_three_lines_signals表")
            logger.info(f"处理错误: {error_count} 只")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"一阳穿三线策略执行失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
        return results
