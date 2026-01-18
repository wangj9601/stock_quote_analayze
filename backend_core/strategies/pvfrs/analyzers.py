"""
PVFRS策略维度分析器实现
包含价格、频率、成交量三个维度的分析器
"""

from typing import List, Dict
from .models import MarketData, DataInsufficientException, CalculationException
from .interfaces import IPriceDimensionAnalyzer, IFrequencyDimensionAnalyzer, IVolumeDimensionAnalyzer


class PriceDimensionAnalyzer(IPriceDimensionAnalyzer):
    """价格维度分析器
    
    负责计算价格维度的各项指标：
    - 宏观位移指标 Δ = d₂₀ - d₁
    - 即时强度指标 d₂₀ - d
    - 20日平均价格 d
    """
    
    def __init__(self):
        self.observation_period = 20  # 观察周期为20天
    
    def analyze(self, data: List[MarketData]) -> Dict:
        """分析价格维度指标"""
        if len(data) < self.observation_period:
            raise DataInsufficientException(f"数据不足，需要至少{self.observation_period}天数据，实际{len(data)}天")
        
        try:
            # 计算各项指标
            macro_displacement = self.calculate_macro_displacement(data)
            avg_price_20d = self.calculate_avg_price_20d(data)
            instant_deviation = self.calculate_instant_deviation(data)
            
            return {
                'macro_displacement': macro_displacement,
                'instant_deviation': instant_deviation,
                'avg_price_20d': avg_price_20d,
                'price_dimension_valid': self.validate_conditions({
                    'macro_displacement': macro_displacement,
                    'instant_deviation': instant_deviation
                })
            }
        except Exception as e:
            raise CalculationException(f"价格维度计算失败: {str(e)}")
    
    def calculate_macro_displacement(self, data: List[MarketData]) -> float:
        """计算宏观位移指标 Δ = d₂₀ - d₁
        
        Args:
            data: 市场数据列表，按时间顺序排列
            
        Returns:
            float: 宏观位移指标值
            
        Raises:
            DataInsufficientException: 数据不足时抛出
            CalculationException: 计算异常时抛出
        """
        if len(data) < self.observation_period:
            raise DataInsufficientException(f"计算宏观位移指标需要至少{self.observation_period}天数据")
        
        try:
            # 取最近20天的数据
            recent_data = data[-self.observation_period:]
            
            # d₁: 观察周期起始价格（第1天收盘价）
            d1 = recent_data[0].close
            
            # d₂₀: 观察周期末位价格（第20天收盘价）
            d20 = recent_data[-1].close
            
            # 计算宏观位移 Δ = d₂₀ - d₁
            macro_displacement = d20 - d1
            
            return macro_displacement
            
        except (IndexError, AttributeError) as e:
            raise CalculationException(f"宏观位移指标计算失败: {str(e)}")
    
    def calculate_instant_deviation(self, data: List[MarketData]) -> float:
        """计算即时强度指标 d₂₀ - d
        
        Args:
            data: 市场数据列表，按时间顺序排列
            
        Returns:
            float: 即时强度指标值
        """
        if len(data) < self.observation_period:
            raise DataInsufficientException(f"计算即时强度指标需要至少{self.observation_period}天数据")
        
        try:
            # 取最近20天的数据
            recent_data = data[-self.observation_period:]
            
            # d₂₀: 观察周期末位价格（第20天收盘价）
            d20 = recent_data[-1].close
            
            # d: 20日平均价格
            avg_price = self.calculate_avg_price_20d(data)
            
            # 计算即时强度 = d₂₀ - d
            instant_deviation = d20 - avg_price
            
            return instant_deviation
            
        except Exception as e:
            raise CalculationException(f"即时强度指标计算失败: {str(e)}")
    
    def calculate_avg_price_20d(self, data: List[MarketData]) -> float:
        """计算20日平均价格 d = (d₁ + d₂ + ... + d₂₀) / 20
        
        Args:
            data: 市场数据列表，按时间顺序排列
            
        Returns:
            float: 20日平均价格
        """
        if len(data) < self.observation_period:
            raise DataInsufficientException(f"计算20日平均价格需要至少{self.observation_period}天数据")
        
        try:
            # 取最近20天的数据
            recent_data = data[-self.observation_period:]
            
            # 计算平均价格
            total_price = sum(day.close for day in recent_data)
            avg_price = total_price / self.observation_period
            
            return avg_price
            
        except Exception as e:
            raise CalculationException(f"20日平均价格计算失败: {str(e)}")
    
    def validate_conditions(self, indicators: Dict) -> bool:
        """验证价格维度条件是否满足
        
        价格维度条件：
        1. 宏观位移指标 Δ > 0 (价格整体上涨)
        2. 即时强度指标 d₂₀ > d (末位价格高于平均价格)
        
        Args:
            indicators: 包含价格维度指标的字典
            
        Returns:
            bool: 条件是否满足
        """
        try:
            macro_displacement = indicators.get('macro_displacement', 0)
            instant_deviation = indicators.get('instant_deviation', 0)
            
            # 条件1: 宏观位移为正
            condition1 = macro_displacement > 0
            
            # 条件2: 即时强度为正（末位价格高于平均价格）
            condition2 = instant_deviation > 0
            
            # 两个条件都必须满足
            return condition1 and condition2
            
        except Exception as e:
            raise CalculationException(f"价格维度条件验证失败: {str(e)}")


class FrequencyDimensionAnalyzer(IFrequencyDimensionAnalyzer):
    """频率维度分析器
    
    负责计算频率维度的各项指标：
    - 上涨天数 Z
    - 下跌天数 F  
    - 频率优势判定 Z > F
    """
    
    def __init__(self):
        self.observation_period = 20  # 观察周期为20天
    
    def analyze(self, data: List[MarketData]) -> Dict:
        """分析频率维度指标"""
        if len(data) < self.observation_period:
            raise DataInsufficientException(f"数据不足，需要至少{self.observation_period}天数据，实际{len(data)}天")
        
        try:
            rising_days = self.count_rising_days(data)
            falling_days = self.count_falling_days(data)
            frequency_advantage = self.check_frequency_advantage(rising_days, falling_days)
            
            # 检测虚假繁荣
            has_false_prosperity = self.detect_false_prosperity(data)
            
            return {
                'rising_days': rising_days,
                'falling_days': falling_days,
                'frequency_advantage': frequency_advantage,
                'has_false_prosperity': has_false_prosperity,
                'frequency_dimension_valid': self.validate_conditions({
                    'rising_days': rising_days,
                    'falling_days': falling_days,
                    'has_false_prosperity': has_false_prosperity
                })
            }
        except Exception as e:
            raise CalculationException(f"频率维度计算失败: {str(e)}")
    
    def count_rising_days(self, data: List[MarketData]) -> int:
        """统计上涨天数 Z = count(dᵢ > dᵢ₋₁) for i in [2, 20]
        
        Args:
            data: 市场数据列表，按时间顺序排列
            
        Returns:
            int: 观察周期内的上涨天数
            
        Raises:
            DataInsufficientException: 数据不足时抛出
            CalculationException: 计算异常时抛出
        """
        if len(data) < self.observation_period:
            raise DataInsufficientException(f"统计上涨天数需要至少{self.observation_period}天数据")
        
        try:
            # 取最近20天的数据
            recent_data = data[-self.observation_period:]
            
            rising_days = 0
            
            # 从第2天开始比较（i从1开始，因为要与前一天比较）
            for i in range(1, len(recent_data)):
                current_price = recent_data[i].close
                previous_price = recent_data[i-1].close
                
                # 如果当天收盘价高于前一天收盘价，则为上涨天
                if current_price > previous_price:
                    rising_days += 1
            
            return rising_days
            
        except (IndexError, AttributeError) as e:
            raise CalculationException(f"上涨天数统计失败: {str(e)}")
    
    def count_falling_days(self, data: List[MarketData]) -> int:
        """统计下跌天数 F = count(dᵢ < dᵢ₋₁) for i in [2, 20]
        
        Args:
            data: 市场数据列表，按时间顺序排列
            
        Returns:
            int: 观察周期内的下跌天数
            
        Raises:
            DataInsufficientException: 数据不足时抛出
            CalculationException: 计算异常时抛出
        """
        if len(data) < self.observation_period:
            raise DataInsufficientException(f"统计下跌天数需要至少{self.observation_period}天数据")
        
        try:
            # 取最近20天的数据
            recent_data = data[-self.observation_period:]
            
            falling_days = 0
            
            # 从第2天开始比较（i从1开始，因为要与前一天比较）
            for i in range(1, len(recent_data)):
                current_price = recent_data[i].close
                previous_price = recent_data[i-1].close
                
                # 如果当天收盘价低于前一天收盘价，则为下跌天
                if current_price < previous_price:
                    falling_days += 1
            
            return falling_days
            
        except (IndexError, AttributeError) as e:
            raise CalculationException(f"下跌天数统计失败: {str(e)}")
    
    def check_frequency_advantage(self, rising_days: int, falling_days: int) -> bool:
        """检查频率优势 Z > F
        
        Args:
            rising_days: 上涨天数 Z
            falling_days: 下跌天数 F
            
        Returns:
            bool: 是否具有频率优势（上涨天数严格多于下跌天数）
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            # 验证输入参数
            if rising_days < 0 or falling_days < 0:
                raise CalculationException("上涨天数和下跌天数不能为负数")
            
            # 频率优势条件：上涨天数严格多于下跌天数
            frequency_advantage = rising_days > falling_days
            
            return frequency_advantage
            
        except Exception as e:
            raise CalculationException(f"频率优势判定失败: {str(e)}")
    
    def detect_false_prosperity(self, data: List[MarketData]) -> bool:
        """检测虚假繁荣（单日暴涨）情况
        
        虚假繁荣的特征：
        1. 存在单日涨幅过大的情况（超过5%）
        2. 大部分涨幅集中在少数几天
        3. 整体趋势不够稳定和持续
        
        Args:
            data: 市场数据列表，按时间顺序排列
            
        Returns:
            bool: 是否存在虚假繁荣（True表示存在，应该被过滤）
            
        Raises:
            DataInsufficientException: 数据不足时抛出
            CalculationException: 计算异常时抛出
        """
        if len(data) < self.observation_period:
            raise DataInsufficientException(f"检测虚假繁荣需要至少{self.observation_period}天数据")
        
        try:
            # 取最近20天的数据
            recent_data = data[-self.observation_period:]
            
            # 计算每日涨跌幅
            daily_changes = []
            for i in range(1, len(recent_data)):
                current_price = recent_data[i].close
                previous_price = recent_data[i-1].close
                if previous_price > 0:  # 避免除零错误
                    change_pct = (current_price - previous_price) / previous_price * 100
                    daily_changes.append(change_pct)
            
            if not daily_changes:
                return False
            
            # 只考虑上涨的日子
            positive_changes = [change for change in daily_changes if change > 0]
            
            if not positive_changes:
                return False  # 没有上涨日，不存在虚假繁荣
            
            # 检测是否存在异常大的单日涨幅
            # 如果有任何一天的涨幅超过5%，则认为可能是虚假繁荣
            excessive_gain_threshold = 5.0
            
            excessive_gains = [change for change in positive_changes if change > excessive_gain_threshold]
            
            # 如果存在过度涨幅，进一步检查
            if excessive_gains:
                # 计算过度涨幅占总涨幅的比例
                total_positive_change = sum(positive_changes)
                if total_positive_change > 0:
                    excessive_gain_ratio = sum(excessive_gains) / total_positive_change
                    
                    # 如果过度涨幅占总涨幅的30%以上，认为是虚假繁荣
                    if excessive_gain_ratio > 0.3:
                        return True
            
            return False
            
        except Exception as e:
            raise CalculationException(f"虚假繁荣检测失败: {str(e)}")
    
    def validate_conditions(self, indicators: Dict) -> bool:
        """验证频率维度条件是否满足
        
        频率维度条件：
        1. 上涨天数严格多于下跌天数 (Z > F)
        2. 确认趋势由持续买盘推动
        3. 排除虚假繁荣（单日暴涨）情况
        
        Args:
            indicators: 包含频率维度指标的字典
            
        Returns:
            bool: 条件是否满足
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            rising_days = indicators.get('rising_days', 0)
            falling_days = indicators.get('falling_days', 0)
            has_false_prosperity = indicators.get('has_false_prosperity', False)
            
            # 条件1: 频率优势 - 上涨天数严格多于下跌天数
            frequency_advantage = self.check_frequency_advantage(rising_days, falling_days)
            
            # 条件2: 持续买盘推动确认 - 上涨天数应该占据明显优势
            # 在20天观察期内，至少要有超过一半的交易日是上涨的
            # 这确保了趋势是由持续的买盘推动，而不是偶然的波动
            continuous_buying_support = rising_days >= (self.observation_period - 1) // 2
            
            # 条件3: 排除虚假繁荣 - 不能存在单日暴涨情况
            no_false_prosperity = not has_false_prosperity
            
            # 三个条件都必须满足
            return frequency_advantage and continuous_buying_support and no_false_prosperity
            
        except Exception as e:
            raise CalculationException(f"频率维度条件验证失败: {str(e)}")


class VolumeDimensionAnalyzer(IVolumeDimensionAnalyzer):
    """成交量维度分析器
    
    负责计算成交量维度的各项指标：
    - 20日平均成交量 m
    - 效率指标 m₂₀ - m
    - 效率比 m₂₀ / m
    - 量价共振状态检测
    """
    
    def __init__(self):
        self.observation_period = 20  # 观察周期为20天
    
    def analyze(self, data: List[MarketData]) -> Dict:
        """分析成交量维度指标"""
        if len(data) < self.observation_period:
            raise DataInsufficientException(f"数据不足，需要至少{self.observation_period}天数据，实际{len(data)}天")
        
        try:
            avg_volume_20d = self.calculate_avg_volume_20d(data)
            current_volume = data[-1].volume
            efficiency_ratio = self.calculate_efficiency_ratio(current_volume, avg_volume_20d)
            efficiency_indicator = self.calculate_efficiency_indicator(current_volume, avg_volume_20d)
            volume_efficiency = self.check_volume_efficiency(current_volume, avg_volume_20d)
            
            # 分析量价共振状态
            resonance_analysis = self.analyze_volume_price_resonance(data)
            
            # 分析资金支撑质量
            fund_support_analysis = self.analyze_fund_support_quality(data)
            
            return {
                'avg_volume_20d': avg_volume_20d,
                'current_volume': current_volume,
                'efficiency_ratio': efficiency_ratio,
                'efficiency_indicator': efficiency_indicator,
                'volume_efficiency': volume_efficiency,
                'price_rising': resonance_analysis['price_rising'],
                'volume_increasing': resonance_analysis['volume_increasing'],
                'volume_price_resonance': resonance_analysis['volume_price_resonance'],
                'strong_fund_support': fund_support_analysis['strong_fund_support'],
                'is_high_quality_signal': fund_support_analysis['is_high_quality_signal'],
                'volume_multiplier': fund_support_analysis['volume_multiplier'],
                'fund_support_quality': fund_support_analysis['fund_support_quality'],
                'volume_dimension_valid': self.validate_conditions({
                    'current_volume': current_volume,
                    'avg_volume_20d': avg_volume_20d,
                    'volume_price_resonance': resonance_analysis['volume_price_resonance']
                })
            }
        except Exception as e:
            raise CalculationException(f"成交量维度计算失败: {str(e)}")
    
    def calculate_avg_volume_20d(self, data: List[MarketData]) -> float:
        """计算20日平均成交量 m = (m₁ + m₂ + ... + m₂₀) / 20
        
        Args:
            data: 市场数据列表，按时间顺序排列
            
        Returns:
            float: 20日平均成交量
            
        Raises:
            DataInsufficientException: 数据不足时抛出
            CalculationException: 计算异常时抛出
        """
        if len(data) < self.observation_period:
            raise DataInsufficientException(f"计算20日平均成交量需要至少{self.observation_period}天数据")
        
        try:
            # 取最近20天的数据
            recent_data = data[-self.observation_period:]
            
            # 计算平均成交量
            total_volume = sum(day.volume for day in recent_data)
            avg_volume = total_volume / self.observation_period
            
            return avg_volume
            
        except Exception as e:
            raise CalculationException(f"20日平均成交量计算失败: {str(e)}")
    
    def calculate_efficiency_ratio(self, current_volume: float, avg_volume: float) -> float:
        """计算效率比 m₂₀ / m
        
        Args:
            current_volume: 当前成交量 m₂₀
            avg_volume: 20日平均成交量 m
            
        Returns:
            float: 效率比
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            if avg_volume <= 0:
                raise CalculationException("平均成交量不能为零或负数")
            
            # 计算效率比 = 当前成交量 / 平均成交量
            efficiency_ratio = current_volume / avg_volume
            
            return efficiency_ratio
            
        except Exception as e:
            raise CalculationException(f"效率比计算失败: {str(e)}")
    
    def calculate_efficiency_indicator(self, current_volume: float, avg_volume: float) -> float:
        """计算进出效率指标 m₂₀ - m
        
        Args:
            current_volume: 当前成交量 m₂₀
            avg_volume: 20日平均成交量 m
            
        Returns:
            float: 进出效率指标值
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            # 计算进出效率指标 = 当前成交量 - 平均成交量
            efficiency_indicator = current_volume - avg_volume
            
            return efficiency_indicator
            
        except Exception as e:
            raise CalculationException(f"进出效率指标计算失败: {str(e)}")
    
    def check_volume_efficiency(self, current_volume: float, avg_volume: float) -> bool:
        """检查成交量效率条件 m₂₀ > m
        
        Args:
            current_volume: 当前成交量 m₂₀
            avg_volume: 20日平均成交量 m
            
        Returns:
            bool: 是否满足成交量效率条件（即时成交量高于平均成交量）
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            # 验证输入参数
            if current_volume < 0 or avg_volume < 0:
                raise CalculationException("成交量不能为负数")
            
            # 成交量效率条件：即时成交量高于平均成交量
            volume_efficiency = current_volume > avg_volume
            
            return volume_efficiency
            
        except Exception as e:
            raise CalculationException(f"成交量效率条件检查失败: {str(e)}")
    
    def detect_volume_price_resonance(self, price_rising: bool, volume_increasing: bool) -> bool:
        """检测量价共振状态
        
        量价共振的定义：
        - 价格上涨且成交量放大的组合条件
        - 表明趋势得到资金支撑，具有较强的持续性
        
        Args:
            price_rising: 价格是否上涨
            volume_increasing: 成交量是否放大
            
        Returns:
            bool: 是否处于量价共振状态
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            # 量价共振条件：价格上涨 AND 成交量放大
            volume_price_resonance = price_rising and volume_increasing
            
            return volume_price_resonance
            
        except Exception as e:
            raise CalculationException(f"量价共振状态检测失败: {str(e)}")
    
    def check_price_rising(self, data: List[MarketData]) -> bool:
        """检查价格是否上涨
        
        Args:
            data: 市场数据列表，按时间顺序排列
            
        Returns:
            bool: 价格是否上涨（当前价格高于前一天）
            
        Raises:
            DataInsufficientException: 数据不足时抛出
            CalculationException: 计算异常时抛出
        """
        if len(data) < 2:
            raise DataInsufficientException("检查价格上涨需要至少2天数据")
        
        try:
            # 获取最近两天的收盘价
            current_price = data[-1].close
            previous_price = data[-2].close
            
            # 判断价格是否上涨
            price_rising = current_price > previous_price
            
            return price_rising
            
        except (IndexError, AttributeError) as e:
            raise CalculationException(f"价格上涨检查失败: {str(e)}")
    
    def analyze_volume_price_resonance(self, data: List[MarketData]) -> Dict:
        """分析量价共振状态
        
        Args:
            data: 市场数据列表，按时间顺序排列
            
        Returns:
            Dict: 包含量价共振分析结果的字典
            
        Raises:
            DataInsufficientException: 数据不足时抛出
            CalculationException: 计算异常时抛出
        """
        if len(data) < self.observation_period:
            raise DataInsufficientException(f"分析量价共振需要至少{self.observation_period}天数据")
        
        try:
            # 检查价格是否上涨
            price_rising = self.check_price_rising(data)
            
            # 检查成交量是否放大
            avg_volume_20d = self.calculate_avg_volume_20d(data)
            current_volume = data[-1].volume
            volume_increasing = self.check_volume_efficiency(current_volume, avg_volume_20d)
            
            # 检测量价共振状态
            volume_price_resonance = self.detect_volume_price_resonance(price_rising, volume_increasing)
            
            return {
                'price_rising': price_rising,
                'volume_increasing': volume_increasing,
                'volume_price_resonance': volume_price_resonance,
                'current_price': data[-1].close,
                'previous_price': data[-2].close if len(data) >= 2 else None,
                'current_volume': current_volume,
                'avg_volume_20d': avg_volume_20d
            }
            
        except Exception as e:
            raise CalculationException(f"量价共振分析失败: {str(e)}")
    
    def validate_conditions(self, indicators: Dict) -> bool:
        """验证成交量维度条件是否满足
        
        成交量维度条件：
        1. 进出效率指标 m₂₀ > m（即时成交量高于平均成交量）
        2. 量价共振状态（价格上涨且成交量放大）
        3. 强劲资金支撑确认
        4. 排除低成色信号
        
        Args:
            indicators: 包含成交量维度指标的字典
            
        Returns:
            bool: 条件是否满足
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            current_volume = indicators.get('current_volume', 0)
            avg_volume_20d = indicators.get('avg_volume_20d', 0)
            volume_price_resonance = indicators.get('volume_price_resonance', False)
            
            # 条件1: 进出效率指标 - 即时成交量高于平均成交量
            volume_efficiency = self.check_volume_efficiency(current_volume, avg_volume_20d)
            
            # 条件2: 量价共振状态
            has_resonance = volume_price_resonance
            
            # 条件3: 强劲资金支撑确认
            strong_fund_support = self.confirm_strong_fund_support(current_volume, avg_volume_20d)
            
            # 条件4: 排除低成色信号
            is_high_quality = self.filter_low_quality_signals(current_volume, avg_volume_20d)
            
            # 所有条件都必须满足
            return volume_efficiency and has_resonance and strong_fund_support and is_high_quality
            
        except Exception as e:
            raise CalculationException(f"成交量维度条件验证失败: {str(e)}")
    
    def confirm_strong_fund_support(self, current_volume: float, avg_volume: float) -> bool:
        """确认强劲资金支撑的趋势
        
        强劲资金支撑的特征：
        1. 当前成交量显著高于平均水平（至少1.2倍）
        2. 成交量放大幅度适中，避免异常放量
        3. 资金流入具有持续性特征
        
        Args:
            current_volume: 当前成交量
            avg_volume: 20日平均成交量
            
        Returns:
            bool: 是否具有强劲资金支撑
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            if avg_volume <= 0:
                raise CalculationException("平均成交量不能为零或负数")
            
            # 计算成交量放大倍数
            volume_multiplier = current_volume / avg_volume
            
            # 强劲资金支撑的条件：
            # 1. 成交量至少是平均水平的1.2倍，表明有明显的资金流入
            min_support_multiplier = 1.2  # 降低门槛从1.5到1.2
            
            # 2. 成交量不能过度放大（不超过8倍），避免异常情况
            max_support_multiplier = 8.0  # 提高上限从5.0到8.0
            
            # 判断是否在合理的资金支撑范围内
            strong_support = min_support_multiplier <= volume_multiplier <= max_support_multiplier
            
            return strong_support
            
        except Exception as e:
            raise CalculationException(f"强劲资金支撑确认失败: {str(e)}")
    
    def filter_low_quality_signals(self, current_volume: float, avg_volume: float) -> bool:
        """识别并排除低成色信号
        
        低成色信号的特征：
        1. 价格上涨但成交量不足（成交量低于平均水平）
        2. 成交量过度放大，可能是异常交易
        3. 成交量波动过于剧烈，缺乏稳定性
        
        Args:
            current_volume: 当前成交量
            avg_volume: 20日平均成交量
            
        Returns:
            bool: 是否为高质量信号（True表示高质量，False表示低成色应排除）
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            if avg_volume <= 0:
                raise CalculationException("平均成交量不能为零或负数")
            
            # 计算成交量比率
            volume_ratio = current_volume / avg_volume
            
            # 低成色信号的判定标准：
            
            # 1. 成交量严重不足（低于平均水平的80%）
            insufficient_volume_threshold = 0.8
            if volume_ratio < insufficient_volume_threshold:
                return False  # 成交量不足，为低成色信号
            
            # 2. 成交量过度放大（超过平均水平的10倍）
            excessive_volume_threshold = 10.0
            if volume_ratio > excessive_volume_threshold:
                return False  # 成交量过度放大，可能是异常交易
            
            # 3. 成交量在合理范围内，认为是高质量信号
            return True
            
        except Exception as e:
            raise CalculationException(f"低成色信号过滤失败: {str(e)}")
    
    def analyze_fund_support_quality(self, data: List[MarketData]) -> Dict:
        """分析资金支撑质量
        
        Args:
            data: 市场数据列表，按时间顺序排列
            
        Returns:
            Dict: 包含资金支撑质量分析结果的字典
            
        Raises:
            DataInsufficientException: 数据不足时抛出
            CalculationException: 计算异常时抛出
        """
        if len(data) < self.observation_period:
            raise DataInsufficientException(f"分析资金支撑质量需要至少{self.observation_period}天数据")
        
        try:
            avg_volume_20d = self.calculate_avg_volume_20d(data)
            current_volume = data[-1].volume
            
            # 确认强劲资金支撑
            strong_fund_support = self.confirm_strong_fund_support(current_volume, avg_volume_20d)
            
            # 过滤低成色信号
            is_high_quality = self.filter_low_quality_signals(current_volume, avg_volume_20d)
            
            # 计算相关指标
            volume_multiplier = current_volume / avg_volume_20d if avg_volume_20d > 0 else 0
            
            return {
                'strong_fund_support': strong_fund_support,
                'is_high_quality_signal': is_high_quality,
                'volume_multiplier': volume_multiplier,
                'current_volume': current_volume,
                'avg_volume_20d': avg_volume_20d,
                'fund_support_quality': strong_fund_support and is_high_quality
            }
            
        except Exception as e:
            raise CalculationException(f"资金支撑质量分析失败: {str(e)}")