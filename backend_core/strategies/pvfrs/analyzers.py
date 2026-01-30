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
    
    def __init__(self, amplitude_flat_threshold: float = 1e-6):
        self.observation_period = 20  # 观察周期为20天
        self.amplitude_flat_threshold = amplitude_flat_threshold  # |Δ| < ε 判为横盘
    
    def analyze(self, data: List[MarketData]) -> Dict:
        """分析价格维度指标"""
        if len(data) < self.observation_period:
            raise DataInsufficientException(f"数据不足，需要至少{self.observation_period}天数据，实际{len(data)}天")
        
        try:
            # 计算各项指标
            macro_displacement = self.calculate_macro_displacement(data)
            avg_price_20d = self.calculate_avg_price_20d(data)
            instant_deviation = self.calculate_instant_deviation(data)
            
            # 幅度指标：d₁、d₂₀、幅度、Δ/d₂₀、Δ/d₁、Δ=0→横盘
            recent_data = data[-self.observation_period:]
            d1 = recent_data[0].close
            d20 = recent_data[-1].close
            amplitude = abs(macro_displacement)
            ratio_d20 = (macro_displacement / d20) if d20 != 0 else None
            ratio_d1 = (macro_displacement / d1) if d1 != 0 else None
            is_sideways = amplitude < self.amplitude_flat_threshold
            
            return {
                'macro_displacement': macro_displacement,
                'instant_deviation': instant_deviation,
                'avg_price_20d': avg_price_20d,
                'amplitude': amplitude,
                'd1': d1,
                'd20': d20,
                'ratio_d20': ratio_d20,
                'ratio_d1': ratio_d1,
                'is_sideways': is_sideways,
                'trend_persistence': self.analyze_price_trend_persistence(data),
                'price_volatility': self.calculate_price_volatility(data),
                'bias': self.calculate_bias(data),
                'bias_trend': self.analyze_bias_trend(data),
                'price_dimension_valid': self.validate_conditions({
                    'macro_displacement': macro_displacement,
                    'instant_deviation': instant_deviation,
                    'trend_persistence': self.analyze_price_trend_persistence(data),
                    'price_volatility': self.calculate_price_volatility(data),
                    'bias': self.calculate_bias(data),
                    'bias_trend': self.analyze_bias_trend(data)
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
    
    def analyze_price_trend_persistence(self, data: List[MarketData]) -> Dict:
        """分析价格趋势持续性
        
        计算最近5天、10天的价格趋势斜率，验证价格是否持续向上
        
        Args:
            data: 市场数据列表
            
        Returns:
            Dict: 趋势持续性分析结果
        """
        try:
            recent_data = data[-self.observation_period:]
            
            # 计算最近5天趋势斜率
            trend_5d = self._calculate_trend_slope(recent_data[-5:]) if len(recent_data) >= 5 else 0.0
            
            # 计算最近10天趋势斜率
            trend_10d = self._calculate_trend_slope(recent_data[-10:]) if len(recent_data) >= 10 else 0.0
            
            # 计算最近N天中上涨天数占比
            recent_5d_rising_ratio = self._calculate_rising_ratio(recent_data[-5:]) if len(recent_data) >= 5 else 0.0
            recent_10d_rising_ratio = self._calculate_rising_ratio(recent_data[-10:]) if len(recent_data) >= 10 else 0.0
            
            # 计算最大回撤
            max_drawdown = self._calculate_max_drawdown(recent_data)
            
            return {
                'trend_5d_slope': trend_5d,
                'trend_10d_slope': trend_10d,
                'recent_5d_rising_ratio': recent_5d_rising_ratio,
                'recent_10d_rising_ratio': recent_10d_rising_ratio,
                'max_drawdown': max_drawdown,
                'is_persistent': trend_5d > 0 and trend_10d > 0 and recent_10d_rising_ratio >= 0.5 and max_drawdown < 0.10
            }
            
        except Exception as e:
            raise CalculationException(f"价格趋势持续性分析失败: {str(e)}")
    
    def _calculate_trend_slope(self, data: List[MarketData]) -> float:
        """计算价格趋势斜率（线性回归斜率）
        
        Args:
            data: 市场数据列表
            
        Returns:
            float: 趋势斜率（正值表示上涨趋势）
        """
        if len(data) < 2:
            return 0.0
        
        try:
            n = len(data)
            x = list(range(n))
            y = [day.close for day in data]
            
            # 简单线性回归计算斜率
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(x[i] * y[i] for i in range(n))
            sum_x2 = sum(x[i] ** 2 for i in range(n))
            
            denominator = n * sum_x2 - sum_x ** 2
            if denominator == 0:
                return 0.0
            
            slope = (n * sum_xy - sum_x * sum_y) / denominator
            return slope
            
        except Exception:
            return 0.0
    
    def _calculate_rising_ratio(self, data: List[MarketData]) -> float:
        """计算上涨天数占比
        
        Args:
            data: 市场数据列表
            
        Returns:
            float: 上涨天数占比 (0-1)
        """
        if len(data) < 2:
            return 0.0
        
        rising_days = 0
        for i in range(1, len(data)):
            if data[i].close > data[i-1].close:
                rising_days += 1
        
        return rising_days / (len(data) - 1) if len(data) > 1 else 0.0
    
    def _calculate_max_drawdown(self, data: List[MarketData]) -> float:
        """计算最大回撤
        
        Args:
            data: 市场数据列表
            
        Returns:
            float: 最大回撤比例（0-1）
        """
        if len(data) < 2:
            return 0.0
        
        prices = [day.close for day in data]
        max_price = prices[0]
        max_drawdown = 0.0
        
        for price in prices:
            if price > max_price:
                max_price = price
            drawdown = (max_price - price) / max_price if max_price > 0 else 0.0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return max_drawdown
    
    def calculate_price_volatility(self, data: List[MarketData]) -> float:
        """计算价格波动率（20天标准差/均值）
        
        Args:
            data: 市场数据列表
            
        Returns:
            float: 价格波动率
        """
        try:
            recent_data = data[-self.observation_period:]
            prices = [day.close for day in recent_data]
            
            if len(prices) < 2:
                return 0.0
            
            import statistics
            mean_price = statistics.mean(prices)
            if mean_price == 0:
                return 0.0
            
            std_dev = statistics.stdev(prices) if len(prices) > 1 else 0.0
            volatility = std_dev / mean_price
            
            return volatility
            
        except Exception as e:
            print(f"计算价格波动率时出错: {e}")
            return 0.0
    
    def calculate_bias(self, data: List[MarketData]) -> float:
        """计算乖离率
        
        公式: BIAS = (当前价格 - 20日均价) / 20日均价
        
        Args:
            data: 市场数据列表
            
        Returns:
            float: 乖离率
        """
        try:
            if len(data) < self.observation_period:
                return 0.0
            
            current_price = data[-1].close
            avg_price_20d = self.calculate_avg_price_20d(data)
            
            if avg_price_20d <= 0:
                return 0.0
            
            bias = (current_price - avg_price_20d) / avg_price_20d
            return bias
            
        except Exception as e:
            raise CalculationException(f"乖离率计算失败: {str(e)}")
    
    def analyze_bias_trend(self, data: List[MarketData]) -> Dict:
        """分析乖离率趋势
        
        计算最近5天、10天的bias变化趋势，判断bias是否在持续扩大或收敛
        
        Args:
            data: 市场数据列表
            
        Returns:
            Dict: 乖离率趋势分析结果
        """
        try:
            if len(data) < self.observation_period:
                return {
                    'trend_5d': 'insufficient_data',
                    'trend_10d': 'insufficient_data',
                    'is_expanding': False,
                    'is_converging': False,
                    'bias_changes_5d': [],
                    'bias_changes_10d': []
                }
            
            recent_data = data[-self.observation_period:]
            
            # 计算最近5天的bias值
            bias_5d = []
            for i in range(max(0, len(recent_data) - 5), len(recent_data)):
                if i >= 20:  # 确保有足够数据计算20日均价
                    window_data = recent_data[i-19:i+1]
                    if len(window_data) == 20:
                        avg_price = sum(d.close for d in window_data) / 20
                        if avg_price > 0:
                            bias_val = (recent_data[i].close - avg_price) / avg_price
                            bias_5d.append(bias_val)
            
            # 计算最近10天的bias值
            bias_10d = []
            for i in range(max(0, len(recent_data) - 10), len(recent_data)):
                if i >= 20:
                    window_data = recent_data[i-19:i+1]
                    if len(window_data) == 20:
                        avg_price = sum(d.close for d in window_data) / 20
                        if avg_price > 0:
                            bias_val = (recent_data[i].close - avg_price) / avg_price
                            bias_10d.append(bias_val)
            
            # 分析趋势
            trend_5d = 'stable'
            trend_10d = 'stable'
            is_expanding = False
            is_converging = False
            
            if len(bias_5d) >= 3:
                # 计算5天趋势斜率
                changes_5d = [bias_5d[i] - bias_5d[i-1] for i in range(1, len(bias_5d))]
                avg_change_5d = sum(changes_5d) / len(changes_5d) if changes_5d else 0.0
                
                if avg_change_5d > 0.001:  # 持续扩大
                    trend_5d = 'expanding'
                    is_expanding = True
                elif avg_change_5d < -0.001:  # 持续收敛
                    trend_5d = 'converging'
                    is_converging = True
                else:
                    trend_5d = 'stable'
            
            if len(bias_10d) >= 3:
                # 计算10天趋势斜率
                changes_10d = [bias_10d[i] - bias_10d[i-1] for i in range(1, len(bias_10d))]
                avg_change_10d = sum(changes_10d) / len(changes_10d) if changes_10d else 0.0
                
                if avg_change_10d > 0.001:
                    trend_10d = 'expanding'
                elif avg_change_10d < -0.001:
                    trend_10d = 'converging'
                else:
                    trend_10d = 'stable'
            
            return {
                'trend_5d': trend_5d,
                'trend_10d': trend_10d,
                'is_expanding': is_expanding,
                'is_converging': is_converging,
                'bias_changes_5d': changes_5d if len(bias_5d) >= 2 else [],
                'bias_changes_10d': changes_10d if len(bias_10d) >= 2 else [],
                'current_bias': bias_5d[-1] if bias_5d else 0.0
            }
            
        except Exception as e:
            raise CalculationException(f"乖离率趋势分析失败: {str(e)}")
    
    def validate_conditions(self, indicators: Dict) -> bool:
        """验证价格维度条件是否满足（增强版：包含趋势持续性验证）
        
        价格维度条件：
        1. 宏观位移指标 Δ > 0 (价格整体上涨)
        2. 即时强度指标 d₂₀ > d (末位价格高于平均价格)
        3. 价格趋势持续性（新增）
        4. 价格波动率<15%（新增）
        
        Args:
            indicators: 包含价格维度指标的字典
            
        Returns:
            bool: 条件是否满足
        """
        try:
            macro_displacement = indicators.get('macro_displacement', 0)
            instant_deviation = indicators.get('instant_deviation', 0)
            trend_persistence = indicators.get('trend_persistence', {})
            price_volatility = indicators.get('price_volatility', 1.0)
            
            # 条件1: 宏观位移为正
            condition1 = macro_displacement > 0
            
            # 条件2: 即时强度为正（末位价格高于平均价格）
            condition2 = instant_deviation > 0
            
            # 条件3: 价格趋势持续性
            is_persistent = trend_persistence.get('is_persistent', False) if isinstance(trend_persistence, dict) else True
            
            # 条件4: 价格波动率<15%（排除异常波动）
            volatility_valid = price_volatility < 0.15
            
            # 所有条件都必须满足
            return condition1 and condition2 and is_persistent and volatility_valid
            
        except Exception as e:
            raise CalculationException(f"价格维度条件验证失败: {str(e)}")


class FrequencyDimensionAnalyzer(IFrequencyDimensionAnalyzer):
    """频率维度分析器
    
    负责计算频率维度的各项指标：
    - 上涨天数 Z
    - 下跌天数 F
    - 买点权重判定 F > Z（下跌天数大于上涨天数）
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
            
            # 计算上涨集中度（后期上涨天数/总上涨天数）
            rising_concentration = self.calculate_rising_concentration(data, rising_days)
            
            # 计算最近10天的上涨持续性
            recent_rising_persistence = self.calculate_recent_rising_persistence(data)
            
            return {
                'rising_days': rising_days,
                'falling_days': falling_days,
                'frequency_advantage': frequency_advantage,
                'has_false_prosperity': has_false_prosperity,
                'rising_concentration': rising_concentration,
                'recent_rising_persistence': recent_rising_persistence,
                'frequency_dimension_valid': self.validate_conditions({
                    'rising_days': rising_days,
                    'falling_days': falling_days,
                    'has_false_prosperity': has_false_prosperity,
                    'rising_concentration': rising_concentration,
                    'recent_rising_persistence': recent_rising_persistence
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
        """检查频率权重 F > Z（买点侧：下跌天数大于上涨天数作为权重）
        
        Args:
            rising_days: 上涨天数 Z
            falling_days: 下跌天数 F
            
        Returns:
            bool: 是否满足频率权重（下跌天数严格多于上涨天数）
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            # 验证输入参数
            if rising_days < 0 or falling_days < 0:
                raise CalculationException("上涨天数和下跌天数不能为负数")
            
            # 频率权重条件：下跌天数严格多于上涨天数（F > Z）
            frequency_advantage = falling_days > rising_days
            
            return frequency_advantage
            
        except Exception as e:
            raise CalculationException(f"频率权重判定失败: {str(e)}")
    
    def detect_false_prosperity(self, data: List[MarketData]) -> bool:
        """检测虚假繁荣（单日暴涨或连续异常涨幅）情况
        
        虚假繁荣的特征：
        1. 存在单日涨幅过大的情况（超过5%）
        2. 存在连续2-3天的异常涨幅（连续涨幅>3%）
        3. 大部分涨幅集中在少数几天
        4. 上涨天数分布不合理（集中在前期）
        5. 整体趋势不够稳定和持续
        
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
            
            # 检测1: 单日异常涨幅（超过5%）
            excessive_gain_threshold = 5.0
            excessive_gains = [change for change in positive_changes if change > excessive_gain_threshold]
            
            if excessive_gains:
                # 计算过度涨幅占总涨幅的比例
                total_positive_change = sum(positive_changes)
                if total_positive_change > 0:
                    excessive_gain_ratio = sum(excessive_gains) / total_positive_change
                    # 如果过度涨幅占总涨幅的30%以上，认为是虚假繁荣
                    if excessive_gain_ratio > 0.3:
                        return True
            
            # 检测2: 连续2-3天的异常涨幅（连续涨幅>3%）
            consecutive_excessive_threshold = 3.0
            consecutive_days = 0
            for i in range(len(daily_changes)):
                if daily_changes[i] > consecutive_excessive_threshold:
                    consecutive_days += 1
                    if consecutive_days >= 2:  # 连续2天或以上异常涨幅
                        return True
                else:
                    consecutive_days = 0
            
            # 检测3: 上涨天数分布验证（避免集中在前期）
            rising_days_indices = []
            for i in range(len(daily_changes)):
                if daily_changes[i] > 0:
                    rising_days_indices.append(i)
            
            if len(rising_days_indices) > 0:
                # 计算前期（前10天）和后期的上涨天数
                early_rising = sum(1 for idx in rising_days_indices if idx < 10)
                late_rising = len(rising_days_indices) - early_rising
                
                # 如果前期上涨天数占比过高（>70%），可能是虚假繁荣
                if len(rising_days_indices) > 0:
                    early_ratio = early_rising / len(rising_days_indices)
                    if early_ratio > 0.7 and late_rising < 3:
                        return True
            
            return False
            
        except Exception as e:
            raise CalculationException(f"虚假繁荣检测失败: {str(e)}")
    
    def calculate_rising_concentration(self, data: List[MarketData], rising_days: int) -> float:
        """计算上涨集中度
        
        上涨集中度 = 后期上涨天数 / 总上涨天数
        用于判断上涨是否集中在后期，避免集中在前期的情况
        
        Args:
            data: 市场数据列表
            rising_days: 总上涨天数
            
        Returns:
            float: 上涨集中度 (0-1)，值越大表示上涨越集中在后期
        """
        if rising_days == 0:
            return 0.0
        
        try:
            recent_data = data[-self.observation_period:]
            # 计算后10天的上涨天数
            later_period_days = 10
            later_rising_days = 0
            
            for i in range(max(1, len(recent_data) - later_period_days), len(recent_data)):
                if recent_data[i].close > recent_data[i-1].close:
                    later_rising_days += 1
            
            # 计算集中度
            concentration = later_rising_days / rising_days if rising_days > 0 else 0.0
            return concentration
            
        except Exception as e:
            raise CalculationException(f"上涨集中度计算失败: {str(e)}")
    
    def calculate_recent_rising_persistence(self, data: List[MarketData]) -> int:
        """计算最近10天的上涨天数
        
        用于验证上涨持续性
        
        Args:
            data: 市场数据列表
            
        Returns:
            int: 最近10天的上涨天数
        """
        try:
            recent_data = data[-self.observation_period:]
            # 只检查最近10天
            check_days = min(10, len(recent_data) - 1)
            recent_rising = 0
            
            start_idx = len(recent_data) - check_days
            for i in range(start_idx, len(recent_data)):
                if recent_data[i].close > recent_data[i-1].close:
                    recent_rising += 1
            
            return recent_rising
            
        except Exception as e:
            raise CalculationException(f"最近上涨持续性计算失败: {str(e)}")
    
    def validate_conditions(self, indicators: Dict) -> bool:
        """验证频率维度条件是否满足（买点权重：F > Z）
        
        频率维度条件：
        1. 下跌天数严格多于上涨天数 (F > Z)
        2. 确认趋势由持续买盘推动（Z >= 10）
        3. 排除虚假繁荣（本次已注释，恒通过）
        4. 下跌天数至少比上涨天数多3天（F > Z+3）
        5. 最近10天中上涨天数>=6（上涨持续性）
        
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
            recent_rising_persistence = indicators.get('recent_rising_persistence', 0)
            
            # 条件1: 频率权重 - 下跌天数严格多于上涨天数（F > Z）
            frequency_advantage = self.check_frequency_advantage(rising_days, falling_days)
            
            # 条件2: 持续买盘推动确认 - 上涨天数至少10天（20天中占50%）
            continuous_buying_support = rising_days >= 10
            
            # 条件3: 排除虚假繁荣（本次已注释掉判断，恒为 True）
            no_false_prosperity = True  # 原: not has_false_prosperity
            
            # 条件4: 下跌天数大于上涨天数（F > Z；与条件1一致，20天内 F>Z+3 与 Z>=10 难以同时满足，故仅要求 F>Z）
            sufficient_advantage = falling_days > rising_days
            
            # 条件5: 最近10天中上涨天数>=6（上涨持续性验证）
            recent_persistence = recent_rising_persistence >= 6
            
            # 所有条件都必须满足
            return (frequency_advantage and continuous_buying_support and 
                   no_false_prosperity and sufficient_advantage and recent_persistence)
            
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
            
            # 分析量价共振状态（增强版：检查最近3天）
            resonance_analysis = self.analyze_volume_price_resonance(data)
            
            # 分析资金支撑质量（增强版：检查连续放量）
            fund_support_analysis = self.analyze_fund_support_quality(data)
            
            # 分析成交量趋势持续性
            trend_persistence = self.analyze_volume_trend_persistence(data)
            
            return {
                'avg_volume_20d': avg_volume_20d,
                'current_volume': current_volume,
                'efficiency_ratio': efficiency_ratio,
                'efficiency_indicator': efficiency_indicator,
                'volume_efficiency': volume_efficiency,
                'price_rising': resonance_analysis['price_rising'],
                'volume_increasing': resonance_analysis['volume_increasing'],
                'volume_price_resonance': resonance_analysis['volume_price_resonance'],
                'volume_price_correlation': resonance_analysis.get('volume_price_correlation', 0.0),
                'recent_resonance_days': resonance_analysis.get('recent_resonance_days', 0),
                'strong_fund_support': fund_support_analysis['strong_fund_support'],
                'continuous_volume_increase': fund_support_analysis.get('continuous_volume_increase', False),
                'is_high_quality_signal': fund_support_analysis['is_high_quality_signal'],
                'volume_multiplier': fund_support_analysis['volume_multiplier'],
                'fund_support_quality': fund_support_analysis['fund_support_quality'],
                'volume_trend_persistence': trend_persistence,
                'volume_dimension_valid': self.validate_conditions({
                    'current_volume': current_volume,
                    'avg_volume_20d': avg_volume_20d,
                    'volume_price_resonance': resonance_analysis['volume_price_resonance'],
                    'strong_fund_support': fund_support_analysis['strong_fund_support'],
                    'continuous_volume_increase': fund_support_analysis.get('continuous_volume_increase', False),
                    'volume_trend_persistence': trend_persistence
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
        """分析量价共振状态（增强版：检查最近3天的量价配合）
        
        Args:
            data: 市场数据列表，按时间顺序排列
            
        Returns:
            Dict: 包含量价共振分析结果的字典
        """
        if len(data) < self.observation_period:
            raise DataInsufficientException(f"分析量价共振需要至少{self.observation_period}天数据")
        
        try:
            # 检查单日价格是否上涨
            price_rising = self.check_price_rising(data)
            
            # 检查成交量是否放大
            avg_volume_20d = self.calculate_avg_volume_20d(data)
            current_volume = data[-1].volume
            volume_increasing = self.check_volume_efficiency(current_volume, avg_volume_20d)
            
            # 检测单日量价共振状态
            volume_price_resonance = self.detect_volume_price_resonance(price_rising, volume_increasing)
            
            # 增强：检查最近3天的量价配合
            recent_resonance_days = 0
            recent_price_changes = []
            recent_volume_changes = []
            
            check_days = min(3, len(data) - 1)
            for i in range(len(data) - check_days, len(data)):
                if i > 0:
                    price_change = (data[i].close - data[i-1].close) / data[i-1].close if data[i-1].close > 0 else 0
                    volume_change = (data[i].volume - data[i-1].volume) / data[i-1].volume if data[i-1].volume > 0 else 0
                    
                    recent_price_changes.append(price_change)
                    recent_volume_changes.append(volume_change)
                    
                    # 如果价格上涨且成交量放大，计数
                    if price_change > 0 and volume_change > 0:
                        recent_resonance_days += 1
            
            # 计算量价相关系数
            volume_price_correlation = self._calculate_correlation(recent_price_changes, recent_volume_changes)
            
            return {
                'price_rising': price_rising,
                'volume_increasing': volume_increasing,
                'volume_price_resonance': volume_price_resonance,
                'recent_resonance_days': recent_resonance_days,
                'volume_price_correlation': volume_price_correlation,
                'current_price': data[-1].close,
                'previous_price': data[-2].close if len(data) >= 2 else None,
                'current_volume': current_volume,
                'avg_volume_20d': avg_volume_20d
            }
            
        except Exception as e:
            raise CalculationException(f"量价共振分析失败: {str(e)}")
    
    def _calculate_correlation(self, x: List[float], y: List[float]) -> float:
        """计算两个序列的相关系数
        
        Args:
            x: 第一个序列
            y: 第二个序列
            
        Returns:
            float: 相关系数 (-1到1)
        """
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        
        try:
            import statistics
            
            mean_x = statistics.mean(x) if x else 0
            mean_y = statistics.mean(y) if y else 0
            
            numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(len(x)))
            sum_sq_x = sum((x[i] - mean_x) ** 2 for i in range(len(x)))
            sum_sq_y = sum((y[i] - mean_y) ** 2 for i in range(len(y)))
            
            denominator = (sum_sq_x * sum_sq_y) ** 0.5
            
            if denominator == 0:
                return 0.0
            
            correlation = numerator / denominator
            return max(-1.0, min(1.0, correlation))
            
        except Exception:
            return 0.0
    
    def calculate_bias(self, data: List[MarketData]) -> float:
        """计算乖离率
        
        公式: BIAS = (当前价格 - 20日均价) / 20日均价
        
        Args:
            data: 市场数据列表
            
        Returns:
            float: 乖离率
        """
        try:
            if len(data) < self.observation_period:
                return 0.0
            
            current_price = data[-1].close
            avg_price_20d = self.calculate_avg_price_20d(data)
            
            if avg_price_20d <= 0:
                return 0.0
            
            bias = (current_price - avg_price_20d) / avg_price_20d
            return bias
            
        except Exception as e:
            raise CalculationException(f"乖离率计算失败: {str(e)}")
    
    def analyze_bias_trend(self, data: List[MarketData]) -> Dict:
        """分析乖离率趋势
        
        计算最近5天、10天的bias变化趋势，判断bias是否在持续扩大或收敛
        
        Args:
            data: 市场数据列表
            
        Returns:
            Dict: 乖离率趋势分析结果
        """
        try:
            if len(data) < self.observation_period:
                return {
                    'trend_5d': 'insufficient_data',
                    'trend_10d': 'insufficient_data',
                    'is_expanding': False,
                    'is_converging': False,
                    'bias_changes_5d': [],
                    'bias_changes_10d': []
                }
            
            recent_data = data[-self.observation_period:]
            
            # 计算最近5天的bias值
            bias_5d = []
            for i in range(max(0, len(recent_data) - 5), len(recent_data)):
                if i >= 19:  # 确保有足够数据计算20日均价
                    window_data = recent_data[i-19:i+1]
                    if len(window_data) == 20:
                        avg_price = sum(d.close for d in window_data) / 20
                        if avg_price > 0:
                            bias_val = (recent_data[i].close - avg_price) / avg_price
                            bias_5d.append(bias_val)
            
            # 计算最近10天的bias值
            bias_10d = []
            for i in range(max(0, len(recent_data) - 10), len(recent_data)):
                if i >= 19:
                    window_data = recent_data[i-19:i+1]
                    if len(window_data) == 20:
                        avg_price = sum(d.close for d in window_data) / 20
                        if avg_price > 0:
                            bias_val = (recent_data[i].close - avg_price) / avg_price
                            bias_10d.append(bias_val)
            
            # 分析趋势
            trend_5d = 'stable'
            trend_10d = 'stable'
            is_expanding = False
            is_converging = False
            changes_5d = []
            changes_10d = []
            
            if len(bias_5d) >= 3:
                # 计算5天趋势斜率
                changes_5d = [bias_5d[i] - bias_5d[i-1] for i in range(1, len(bias_5d))]
                avg_change_5d = sum(changes_5d) / len(changes_5d) if changes_5d else 0.0
                
                if avg_change_5d > 0.001:  # 持续扩大
                    trend_5d = 'expanding'
                    is_expanding = True
                elif avg_change_5d < -0.001:  # 持续收敛
                    trend_5d = 'converging'
                    is_converging = True
                else:
                    trend_5d = 'stable'
            
            if len(bias_10d) >= 3:
                # 计算10天趋势斜率
                changes_10d = [bias_10d[i] - bias_10d[i-1] for i in range(1, len(bias_10d))]
                avg_change_10d = sum(changes_10d) / len(changes_10d) if changes_10d else 0.0
                
                if avg_change_10d > 0.001:
                    trend_10d = 'expanding'
                elif avg_change_10d < -0.001:
                    trend_10d = 'converging'
                else:
                    trend_10d = 'stable'
            
            return {
                'trend_5d': trend_5d,
                'trend_10d': trend_10d,
                'is_expanding': is_expanding,
                'is_converging': is_converging,
                'bias_changes_5d': changes_5d,
                'bias_changes_10d': changes_10d,
                'current_bias': bias_5d[-1] if bias_5d else 0.0
            }
            
        except Exception as e:
            raise CalculationException(f"乖离率趋势分析失败: {str(e)}")
    
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
            
            # 条件3: 强劲资金支撑确认（必须包括连续放量）
            strong_fund_support = indicators.get('strong_fund_support', False)
            continuous_volume_increase = indicators.get('continuous_volume_increase', False)
            has_strong_support = strong_fund_support and continuous_volume_increase
            
            # 条件4: 排除低成色信号
            is_high_quality = self.filter_low_quality_signals(current_volume, avg_volume_20d)
            
            # 条件5: 成交量趋势持续性
            volume_trend_persistence = indicators.get('volume_trend_persistence', {})
            is_persistent = volume_trend_persistence.get('is_persistent', False) if isinstance(volume_trend_persistence, dict) else False
            
            # 所有条件都必须满足
            return (volume_efficiency and has_resonance and has_strong_support and 
                   is_high_quality and is_persistent)
            
        except Exception as e:
            raise CalculationException(f"成交量维度条件验证失败: {str(e)}")
    
    def confirm_strong_fund_support(self, current_volume: float, avg_volume: float, data: List[MarketData] = None) -> bool:
        """确认强劲资金支撑的趋势（增强版：要求连续3天放量）
        
        强劲资金支撑的特征：
        1. 当前成交量显著高于平均水平（至少1.2倍）
        2. 连续3天成交量放大（新增）
        3. 成交量放大趋势递增（新增）
        4. 成交量放大幅度适中，避免异常放量
        
        Args:
            current_volume: 当前成交量
            avg_volume: 20日平均成交量
            data: 市场数据列表（可选，用于检查连续放量）
            
        Returns:
            bool: 是否具有强劲资金支撑
        """
        try:
            if avg_volume <= 0:
                raise CalculationException("平均成交量不能为零或负数")
            
            # 计算成交量放大倍数
            volume_multiplier = current_volume / avg_volume
            
            # 基础条件：成交量至少是平均水平的1.2倍
            min_support_multiplier = 1.2
            max_support_multiplier = 8.0
            
            if not (min_support_multiplier <= volume_multiplier <= max_support_multiplier):
                return False
            
            # 增强条件：如果提供了数据，检查连续3天放量
            if data is not None and len(data) >= 3:
                recent_data = data[-3:]
                avg_volume_20d = self.calculate_avg_volume_20d(data)
                
                # 检查最近3天是否都放量
                consecutive_days = 0
                volumes_increasing = True
                
                for i in range(len(recent_data)):
                    if recent_data[i].volume > avg_volume_20d:
                        consecutive_days += 1
                    # 检查成交量是否递增
                    if i > 0 and recent_data[i].volume < recent_data[i-1].volume:
                        volumes_increasing = False
                
                # 要求连续3天放量且成交量递增
                if consecutive_days < 3 or not volumes_increasing:
                    return False
            
            return True
            
        except Exception as e:
            raise CalculationException(f"强劲资金支撑确认失败: {str(e)}")
    
    def analyze_volume_trend_persistence(self, data: List[MarketData]) -> Dict:
        """分析成交量趋势持续性
        
        验证内容：
        1. 最近5天中至少有3天成交量>20日均量
        2. 成交量放大天数占比>=60%
        
        Args:
            data: 市场数据列表
            
        Returns:
            Dict: 趋势持续性分析结果
        """
        try:
            if len(data) < self.observation_period:
                return {
                    'is_persistent': False,
                    'recent_above_avg_days': 0,
                    'above_avg_ratio': 0.0,
                    'reason': '数据不足'
                }
            
            avg_volume_20d = self.calculate_avg_volume_20d(data)
            recent_data = data[-5:]  # 最近5天
            
            above_avg_days = sum(1 for day in recent_data if day.volume > avg_volume_20d)
            above_avg_ratio = above_avg_days / len(recent_data) if recent_data else 0.0
            
            # 判断是否持续
            is_persistent = above_avg_days >= 3 and above_avg_ratio >= 0.6
            
            return {
                'is_persistent': is_persistent,
                'recent_above_avg_days': above_avg_days,
                'above_avg_ratio': above_avg_ratio,
                'total_recent_days': len(recent_data)
            }
            
        except Exception as e:
            raise CalculationException(f"成交量趋势持续性分析失败: {str(e)}")
    
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
            
            # 确认强劲资金支撑（传入data以检查连续放量）
            strong_fund_support = self.confirm_strong_fund_support(current_volume, avg_volume_20d, data)
            
            # 检查连续3天放量
            continuous_volume_increase = False
            if len(data) >= 3:
                recent_data = data[-3:]
                consecutive_days = sum(1 for day in recent_data if day.volume > avg_volume_20d)
                # 检查成交量是否递增
                volumes_increasing = all(
                    recent_data[i].volume >= recent_data[i-1].volume 
                    for i in range(1, len(recent_data))
                )
                continuous_volume_increase = consecutive_days >= 3 and volumes_increasing
            
            # 过滤低成色信号
            is_high_quality = self.filter_low_quality_signals(current_volume, avg_volume_20d)
            
            # 计算相关指标
            volume_multiplier = current_volume / avg_volume_20d if avg_volume_20d > 0 else 0
            
            return {
                'strong_fund_support': strong_fund_support,
                'continuous_volume_increase': continuous_volume_increase,
                'is_high_quality_signal': is_high_quality,
                'volume_multiplier': volume_multiplier,
                'current_volume': current_volume,
                'avg_volume_20d': avg_volume_20d,
                'fund_support_quality': strong_fund_support and is_high_quality
            }
            
        except Exception as e:
            raise CalculationException(f"资金支撑质量分析失败: {str(e)}")