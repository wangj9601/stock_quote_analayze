"""
多指标综合交易策略实现
基于MACD、KDJ、RSI、BOLL、PVFRS指标的综合交易策略
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


@dataclass
class TradeSignal:
    """交易信号数据类"""
    date: str
    action: str  # 'buy', 'sell', 'hold'
    indicators: Dict
    confidence: float  # 0-1之间的置信度
    reason: str


@dataclass
class Position:
    """持仓信息"""
    symbol: str
    entry_price: float
    entry_date: str
    quantity: int
    exit_price: Optional[float] = None
    exit_date: Optional[str] = None
    is_closed: bool = False


class MultiIndicatorStrategy:
    """多指标综合交易策略类"""
    
    def __init__(self, initial_capital: float = 100000, risk_per_trade: float = 0.02):
        """
        初始化策略
        :param initial_capital: 初始资金
        :param risk_per_trade: 每次交易风险比例
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.risk_per_trade = risk_per_trade
        self.positions: List[Position] = []
        self.trade_history: List[TradeSignal] = []
        self.current_position: Optional[Position] = None
        
        # 策略参数
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.kdj_oversold = 20
        self.kdj_overbought = 80
        self.macd_threshold = 0.0
        self.min_signals_for_buy = 3  # 最少需要多少个指标信号才能买入
        self.min_signals_for_sell = 3  # 最少需要多少个指标信号才能卖出
        
    def calculate_rsi(self, prices: List[float], period: int = 14) -> List[float]:
        """计算RSI指标"""
        if len(prices) < period + 1:
            return [50.0] * len(prices)
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # 使用滑动窗口计算RSI
        rsi_values = []
        for i in range(period, len(prices)):
            period_gains = gains[i-period:i]
            period_losses = losses[i-period:i]
            
            avg_gain = np.mean(period_gains)
            avg_loss = np.mean(period_losses)
            
            if avg_loss == 0:
                rsi_values.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
                rsi_values.append(rsi)
        
        # 前period个值用50填充
        rsi_values = [50.0] * period + rsi_values
        return rsi_values
    
    def calculate_macd(self, prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, List[float]]:
        """计算MACD指标"""
        if len(prices) < slow:
            return {
                "macd": [0.0] * len(prices),
                "signal": [0.0] * len(prices),
                "histogram": [0.0] * len(prices)
            }
        
        prices_array = np.array(prices)
        
        # 计算EMA
        def calculate_ema(data, period):
            ema = np.zeros_like(data)
            ema[0] = data[0]
            alpha = 2 / (period + 1)
            for i in range(1, len(data)):
                ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
            return ema
        
        ema_fast = calculate_ema(prices_array, fast)
        ema_slow = calculate_ema(prices_array, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line
        
        return {
            "macd": macd_line.tolist(),
            "signal": signal_line.tolist(),
            "histogram": histogram.tolist()
        }
    
    def calculate_kdj(self, highs: List[float], lows: List[float], closes: List[float], period: int = 9) -> Dict[str, List[float]]:
        """计算KDJ指标"""
        if len(closes) < period:
            return {
                "k": [50.0] * len(closes),
                "d": [50.0] * len(closes),
                "j": [50.0] * len(closes)
            }
        
        highs_array = np.array(highs)
        lows_array = np.array(lows)
        closes_array = np.array(closes)
        
        # 计算RSV
        rsv_values = []
        for i in range(len(closes)):
            if i < period - 1:
                rsv_values.append(50.0)
            else:
                highest_high = np.max(highs_array[i-period+1:i+1])
                lowest_low = np.min(lows_array[i-period+1:i+1])
                
                if highest_high == lowest_low:
                    rsv = 50.0
                else:
                    rsv = 100 * (closes_array[i] - lowest_low) / (highest_high - lowest_low)
                rsv_values.append(rsv)
        
        # 计算K、D、J值
        k_values = []
        d_values = []
        j_values = []
        
        k = 50.0
        d = 50.0
        
        for rsv in rsv_values:
            k = (2/3) * k + (1/3) * rsv
            d = (2/3) * d + (1/3) * k
            j = 3 * k - 2 * d
            
            k_values.append(k)
            d_values.append(d)
            j_values.append(j)
        
        return {
            "k": k_values,
            "d": d_values,
            "j": j_values
        }
    
    def calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: int = 2) -> Dict[str, List[float]]:
        """计算布林带"""
        if len(prices) < period:
            return {
                "upper": [0.0] * len(prices),
                "middle": [0.0] * len(prices),
                "lower": [0.0] * len(prices)
            }
        
        prices_array = np.array(prices)
        upper_band = []
        middle_band = []
        lower_band = []
        
        for i in range(len(prices)):
            if i < period - 1:
                # 前期用简单平均值填充
                middle = np.mean(prices_array[:i+1])
                std = np.std(prices_array[:i+1])
            else:
                # 使用指定周期的移动平均
                middle = np.mean(prices_array[i-period+1:i+1])
                std = np.std(prices_array[i-period+1:i+1])
            
            upper = middle + (std_dev * std)
            lower = middle - (std_dev * std)
            
            upper_band.append(upper)
            middle_band.append(middle)
            lower_band.append(lower)
        
        return {
            "upper": upper_band,
            "middle": middle_band,
            "lower": lower_band
        }
    
    def analyze_pvfrs_signal(self, pvfrs_data: List[Dict]) -> List[str]:
        """
        分析PVFRS指标信号
        :param pvfrs_data: PVFRS指标数据列表
        :return: 信号列表
        """
        signals = []
        for item in pvfrs_data:
            if item and isinstance(item, dict):
                # 分析bias指标（乖离率）
                bias = item.get('bias')
                if bias is not None:
                    if bias < -0.05:  # 负乖离过大，可能反弹
                        signals.append('pvfrs_buy')
                    elif bias > 0.05:  # 正乖离过大，可能回调
                        signals.append('pvfrs_sell')
                
                # 分析macro_displacement_delta（宏观位移Delta）
                delta = item.get('macro_displacement_delta')
                if delta is not None:
                    if delta > 0.02:  # 正向位移过大
                        signals.append('pvfrs_sell')
                    elif delta < -0.02:  # 负向位移过大
                        signals.append('pvfrs_buy')
        
        return signals
    
    def generate_signals(self, data: List[Dict]) -> List[TradeSignal]:
        """
        基于历史数据生成交易信号
        :param data: 包含历史价格和指标数据的列表
        :return: 交易信号列表
        """
        if len(data) < 30:  # 需要足够的数据来计算指标
            return []
        
        # 提取价格数据
        closes = [item['close'] for item in data]
        highs = [item['high'] for item in data]
        lows = [item['low'] for item in data]
        dates = [item['date'] for item in data]
        
        # 计算技术指标
        rsi_values = self.calculate_rsi(closes)
        macd_data = self.calculate_macd(closes)
        kdj_data = self.calculate_kdj(highs, lows, closes)
        boll_data = self.calculate_bollinger_bands(closes)
        
        signals = []
        
        # 从第30个数据点开始生成信号（确保有足够的历史数据）
        for i in range(29, len(data)):
            date = dates[i]
            current_price = closes[i]
            
            # 检查MACD信号
            macd_signal = self._check_macd_signal(macd_data, i)
            # 检查KDJ信号
            kdj_signal = self._check_kdj_signal(kdj_data, i)
            # 检查RSI信号
            rsi_signal = self._check_rsi_signal(rsi_values, i)
            # 检查BOLL信号
            boll_signal = self._check_boll_signal(data, boll_data, i)
            # 检查PVFRS信号（如果有数据）
            pvfrs_signal = self._check_pvfrs_signal(data, i)
            
            # 统计买入和卖出信号数量
            buy_signals = sum([
                macd_signal == 'buy',
                kdj_signal == 'buy', 
                rsi_signal == 'buy',
                boll_signal == 'buy',
                pvfrs_signal == 'buy'
            ])
            
            sell_signals = sum([
                macd_signal == 'sell',
                kdj_signal == 'sell',
                rsi_signal == 'sell', 
                boll_signal == 'sell',
                pvfrs_signal == 'sell'
            ])
            
            action = 'hold'
            reasons = []
            
            # 生成买入信号
            if buy_signals >= self.min_signals_for_buy:
                action = 'buy'
                reasons.append(f'多指标共振买入({buy_signals}个信号)')
                
            # 生成卖出信号
            elif sell_signals >= self.min_signals_for_sell:
                action = 'sell'
                reasons.append(f'多指标共振卖出({sell_signals}个信号)')
            
            # 计算置信度（基于信号数量）
            max_signals = 5  # 总共5个指标
            confidence = min(1.0, (buy_signals if action == 'buy' else sell_signals) / max_signals)
            
            # 构建指标字典
            indicators = {
                'rsi': rsi_values[i],
                'macd': macd_data['macd'][i],
                'macd_signal': macd_data['signal'][i],
                'macd_histogram': macd_data['histogram'][i],
                'k': kdj_data['k'][i],
                'd': kdj_data['d'][i],
                'j': kdj_data['j'][i],
                'boll_upper': boll_data['upper'][i],
                'boll_middle': boll_data['middle'][i],
                'boll_lower': boll_data['lower'][i],
                'close': current_price
            }
            
            if action != 'hold':
                signal = TradeSignal(
                    date=date,
                    action=action,
                    indicators=indicators,
                    confidence=confidence,
                    reason='; '.join(reasons)
                )
                signals.append(signal)
        
        return signals
    
    def _check_macd_signal(self, macd_data: Dict, index: int) -> str:
        """检查MACD信号"""
        if index < 1:
            return 'hold'
        
        macd = macd_data['macd'][index]
        signal = macd_data['signal'][index]
        histogram = macd_data['histogram'][index]
        
        prev_macd = macd_data['macd'][index-1]
        prev_signal = macd_data['signal'][index-1]
        prev_histogram = macd_data['histogram'][index-1]
        
        # 金叉：MACD线上穿信号线，且柱状图由负转正或正在放大
        if (prev_macd <= prev_signal and macd > signal) or \
           (prev_histogram < 0 and histogram > prev_histogram):
            return 'buy'
        
        # 死叉：MACD线下穿信号线，且柱状图由正转负或正在缩小
        elif (prev_macd >= prev_signal and macd < signal) or \
             (prev_histogram > 0 and histogram < prev_histogram):
            return 'sell'
        
        return 'hold'
    
    def _check_kdj_signal(self, kdj_data: Dict, index: int) -> str:
        """检查KDJ信号"""
        k = kdj_data['k'][index]
        d = kdj_data['d'][index]
        j = kdj_data['j'][index]
        
        if index > 0:
            prev_k = kdj_data['k'][index-1]
            prev_d = kdj_data['d'][index-1]
            
            # K线上穿D线，且J值在合理范围内
            if prev_k <= prev_d and k > d and j <= 80:
                return 'buy'
            # K线下穿D线，且J值在合理范围内
            elif prev_k >= prev_d and k < d and j >= 20:
                return 'sell'
        
        # 超卖区域金叉
        if j < 20 and k > d:
            return 'buy'
        # 超买区域死叉
        elif j > 80 and k < d:
            return 'sell'
        
        return 'hold'
    
    def _check_rsi_signal(self, rsi_values: List[float], index: int) -> str:
        """检查RSI信号"""
        current_rsi = rsi_values[index]
        
        if index > 0:
            prev_rsi = rsi_values[index-1]
            
            # RSI从超卖区向上突破30
            if prev_rsi <= self.rsi_oversold and current_rsi > self.rsi_oversold:
                return 'buy'
            # RSI从超买区向下跌破70
            elif prev_rsi >= self.rsi_overbought and current_rsi < self.rsi_overbought:
                return 'sell'
        
        # 直接超买超卖信号
        if current_rsi < 20:  # 极度超卖
            return 'buy'
        elif current_rsi > 80:  # 极度超买
            return 'sell'
        
        return 'hold'
    
    def _check_boll_signal(self, data: List[Dict], boll_data: Dict, index: int) -> str:
        """检查布林带信号"""
        current_price = data[index]['close']
        upper = boll_data['upper'][index]
        middle = boll_data['middle'][index]
        lower = boll_data['lower'][index]
        
        # 触及下轨后反弹
        if index > 0:
            prev_price = data[index-1]['close']
            if prev_price <= lower and current_price > lower:
                return 'buy'
            # 触及上轨后回落
            elif prev_price >= upper and current_price < upper:
                return 'sell'
        
        # 当前价格在下轨以下
        if current_price < lower:
            return 'buy'
        # 当前价格在上轨以上
        elif current_price > upper:
            return 'sell'
        
        return 'hold'
    
    def _check_pvfrs_signal(self, data: List[Dict], index: int) -> str:
        """检查PVFRS信号"""
        # 检查数据中是否包含PVFRS指标
        current_data = data[index]
        if 'pvfrs' in current_data and current_data['pvfrs']:
            pvfrs = current_data['pvfrs']
            bias = pvfrs.get('bias')
            
            if bias is not None:
                if bias < -0.05:  # 负乖离过大，买入信号
                    return 'buy'
                elif bias > 0.05:  # 正乖离过大，卖出信号
                    return 'sell'
        return 'hold'
    
    def execute_trade(self, signal: TradeSignal, current_price: float) -> bool:
        """
        执行交易
        :param signal: 交易信号
        :param current_price: 当前价格
        :return: 是否成功执行
        """
        if signal.action == 'buy' and self.current_position is None:
            # 计算买入数量
            risk_amount = self.current_capital * self.risk_per_trade
            stop_loss_price = current_price * 0.95  # 5%止损
            expected_risk_per_share = current_price - stop_loss_price
            
            if expected_risk_per_share > 0:
                quantity = min(
                    int(risk_amount / expected_risk_per_share),
                    int(self.current_capital * 0.9 / current_price)  # 最大使用90%资金
                )
                
                if quantity > 0:
                    self.current_position = Position(
                        symbol="TEST",
                        entry_price=current_price,
                        entry_date=signal.date,
                        quantity=quantity
                    )
                    cost = quantity * current_price
                    self.current_capital -= cost
                    self.trade_history.append(signal)
                    return True
        
        elif signal.action == 'sell' and self.current_position is not None:
            # 卖出当前持仓
            revenue = self.current_position.quantity * current_price
            self.current_capital += revenue
            
            # 更新持仓信息
            self.current_position.exit_price = current_price
            self.current_position.exit_date = signal.date
            self.current_position.is_closed = True
            
            # 将持仓移到历史记录
            self.positions.append(self.current_position)
            self.current_position = None
            self.trade_history.append(signal)
            return True
        
        return False
    
    def backtest(self, data: List[Dict]) -> Dict:
        """
        执行回测
        :param data: 历史数据
        :return: 回测结果
        """
        # 生成交易信号
        signals = self.generate_signals(data)
        
        # 执行交易
        for signal in signals:
            # 找到对应日期的价格
            matching_data = next((item for item in data if item['date'] == signal.date), None)
            if matching_data:
                current_price = matching_data['close']
                self.execute_trade(signal, current_price)
        
        # 计算最终结果
        final_capital = self.current_capital
        if self.current_position:
            # 如果还有持仓，按最后价格计算
            last_price = data[-1]['close']
            final_capital += self.current_position.quantity * last_price
        
        total_return = (final_capital - self.initial_capital) / self.initial_capital
        total_trades = len(self.trade_history)
        winning_trades = sum(1 for pos in self.positions 
                           if pos.exit_price and pos.exit_price > pos.entry_price)
        win_rate = winning_trades / len(self.positions) if self.positions else 0
        
        return {
            'initial_capital': self.initial_capital,
            'final_capital': final_capital,
            'total_return': total_return,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': len(self.positions) - winning_trades,
            'win_rate': win_rate,
            'max_drawdown': self._calculate_max_drawdown(),
            'signals': signals,
            'positions': self.positions
        }
    
    def _calculate_max_drawdown(self) -> float:
        """计算最大回撤（简化版）"""
        # 这里可以实现更复杂的回撤计算
        return 0.0  # 简化实现


# 示例使用
if __name__ == "__main__":
    # 创建示例数据
    sample_data = []
    base_price = 100
    import random
    
    for i in range(200):
        date = f"2023-01-{i+1:02d}" if i < 31 else f"2023-02-{i-30:02d}"
        close = base_price + random.uniform(-2, 3)
        high = close + abs(random.uniform(0, 1.5))
        low = close - abs(random.uniform(0, 1.5))
        open_price = base_price + random.uniform(-1.5, 1.5)
        
        sample_data.append({
            'date': date,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': random.randint(1000000, 5000000)
        })
        
        base_price = close
    
    # 创建策略实例并回测
    strategy = MultiIndicatorStrategy(initial_capital=100000)
    results = strategy.backtest(sample_data)
    
    print("回测结果:")
    print(f"初始资金: {results['initial_capital']:.2f}")
    print(f"最终资金: {results['final_capital']:.2f}")
    print(f"总收益率: {results['total_return']:.4f}")
    print(f"总交易次数: {results['total_trades']}")
    print(f"盈利交易: {results['winning_trades']}")
    print(f"亏损交易: {results['losing_trades']}")
    print(f"胜率: {results['win_rate']:.4f}")
    print(f"信号数量: {len(results['signals'])}")