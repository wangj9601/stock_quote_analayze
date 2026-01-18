"""
PVFRS策略信号生成器实现
负责基于三维共振结果生成买入信号，记录满足的具体条件和信号强度
"""

from typing import Dict, List, Optional
from datetime import datetime
from .models import MarketData, Signal, SignalType, PVFRSIndicators, CalculationException
from .interfaces import ISignalGenerator
from .entry_timing_optimizer import EntryTimingOptimizer


class SignalGenerator(ISignalGenerator):
    """信号生成器
    
    负责基于三维共振检测结果生成交易信号：
    - 生成买入信号
    - 生成卖出信号
    - 记录满足的具体条件和信号强度
    - 优化入场时机
    """
    
    def __init__(self):
        """初始化信号生成器"""
        self.min_signal_strength = 0.6  # 最小信号强度阈值
        self.high_quality_threshold = 0.8  # 高质量信号阈值
        self.entry_timing_optimizer = EntryTimingOptimizer()  # 入场时机优化器
    
    def generate_buy_signal(self, symbol: str, date: str, price: float, 
                           indicators: PVFRSIndicators, conditions_met: Dict[str, bool]) -> Signal:
        """生成买入信号
        
        基于三维共振结果和满足的条件生成买入信号，记录详细信息。
        
        Args:
            symbol: 股票代码
            date: 信号日期
            price: 信号价格
            indicators: PVFRS指标
            conditions_met: 满足的条件
            
        Returns:
            Signal: 买入信号对象
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            # 计算信号强度
            signal_strength = self._calculate_buy_signal_strength(indicators, conditions_met)
            
            # 生成信号原因描述
            reason = self._generate_buy_signal_reason(conditions_met, signal_strength)
            
            # 创建买入信号
            buy_signal = Signal(
                symbol=symbol,
                date=date,
                signal_type=SignalType.BUY,
                price=price,
                strength=signal_strength,
                reason=reason,
                indicators=indicators,
                conditions_met=conditions_met.copy()
            )
            
            return buy_signal
            
        except Exception as e:
            raise CalculationException(f"买入信号生成失败: {str(e)}")
    
    def generate_sell_signal(self, symbol: str, date: str, price: float, 
                            reason: str, strength: float) -> Signal:
        """生成卖出信号
        
        Args:
            symbol: 股票代码
            date: 信号日期
            price: 信号价格
            reason: 卖出原因
            strength: 信号强度
            
        Returns:
            Signal: 卖出信号对象
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            # 验证输入参数
            if strength < 0 or strength > 1:
                raise CalculationException("信号强度必须在0-1之间")
            
            # 创建卖出信号
            sell_signal = Signal(
                symbol=symbol,
                date=date,
                signal_type=SignalType.SELL,
                price=price,
                strength=strength,
                reason=reason,
                conditions_met={}
            )
            
            return sell_signal
            
        except Exception as e:
            raise CalculationException(f"卖出信号生成失败: {str(e)}")
    
    def optimize_entry_timing(self, data: List[MarketData], base_signal: Signal) -> Optional[Signal]:
        """优化入场时机
        
        基于价格穿越和成交量突破等条件优化入场时机。
        
        Args:
            data: 市场数据列表
            base_signal: 基础信号
            
        Returns:
            Optional[Signal]: 优化后的信号，如果不满足优化条件则返回None
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            if len(data) < 2 or base_signal.indicators is None:
                return base_signal  # 数据不足或缺少指标，返回原信号
            
            # 使用入场时机优化器进行综合分析
            optimization_result = self.entry_timing_optimizer.optimize_entry_timing_comprehensive(
                data, base_signal.indicators
            )
            
            # 检查是否满足优化条件
            if optimization_result['optimal_entry_timing']:
                # 生成优化后的信号
                optimized_strength = min(1.0, base_signal.strength * 1.15)  # 提升信号强度15%
                
                optimized_reason = (
                    f"{base_signal.reason} + 入场时机优化"
                    f"(综合评分: {optimization_result['comprehensive_score']:.2f})"
                )
                
                optimized_signal = Signal(
                    symbol=base_signal.symbol,
                    date=base_signal.date,
                    signal_type=base_signal.signal_type,
                    price=base_signal.price,
                    strength=optimized_strength,
                    reason=optimized_reason,
                    indicators=base_signal.indicators,
                    conditions_met=base_signal.conditions_met.copy()
                )
                
                # 添加优化条件记录
                optimized_signal.conditions_met.update({
                    'entry_timing_optimized': True,
                    'price_breakthrough': optimization_result['price_analysis']['has_breakthrough'],
                    'volume_breakthrough': optimization_result['volume_analysis']['has_breakthrough'],
                    'amplitude_validation': optimization_result['amplitude_analysis']['is_valid'],
                    'comprehensive_score': optimization_result['comprehensive_score'],
                    'timing_recommendation': optimization_result['recommendation']
                })
                
                return optimized_signal
            
            elif optimization_result['good_entry_timing']:
                # 良好时机，轻微优化
                optimized_strength = min(1.0, base_signal.strength * 1.05)  # 提升信号强度5%
                
                optimized_reason = (
                    f"{base_signal.reason} + 时机良好"
                    f"(评分: {optimization_result['comprehensive_score']:.2f})"
                )
                
                optimized_signal = Signal(
                    symbol=base_signal.symbol,
                    date=base_signal.date,
                    signal_type=base_signal.signal_type,
                    price=base_signal.price,
                    strength=optimized_strength,
                    reason=optimized_reason,
                    indicators=base_signal.indicators,
                    conditions_met=base_signal.conditions_met.copy()
                )
                
                # 添加时机分析记录
                optimized_signal.conditions_met.update({
                    'entry_timing_good': True,
                    'comprehensive_score': optimization_result['comprehensive_score'],
                    'timing_recommendation': optimization_result['recommendation']
                })
                
                return optimized_signal
            
            else:
                # 时机不佳，可能需要等待
                if optimization_result['amplitude_analysis']['should_wait']:
                    # 如果需要等待，降低信号强度或返回None
                    wait_reason = optimization_result['amplitude_analysis']['wait_reason']
                    
                    # 根据等待优先级决定是否保留信号
                    wait_priority = optimization_result['amplitude_analysis']['waiting_assessment']['priority']
                    
                    if wait_priority == 'high':
                        # 高优先级等待，不建议入场
                        return None
                    else:
                        # 低优先级等待，降低信号强度
                        reduced_strength = base_signal.strength * 0.8
                        
                        modified_reason = f"{base_signal.reason} (时机待优化: {wait_reason})"
                        
                        modified_signal = Signal(
                            symbol=base_signal.symbol,
                            date=base_signal.date,
                            signal_type=base_signal.signal_type,
                            price=base_signal.price,
                            strength=reduced_strength,
                            reason=modified_reason,
                            indicators=base_signal.indicators,
                            conditions_met=base_signal.conditions_met.copy()
                        )
                        
                        modified_signal.conditions_met.update({
                            'entry_timing_suboptimal': True,
                            'wait_recommended': True,
                            'wait_reason': wait_reason,
                            'comprehensive_score': optimization_result['comprehensive_score']
                        })
                        
                        return modified_signal
                
                else:
                    # 不需要等待但时机一般，返回原信号
                    return base_signal
            
        except Exception as e:
            raise CalculationException(f"入场时机优化失败: {str(e)}")
    
    def get_entry_timing_analysis(self, data: List[MarketData], 
                                indicators: PVFRSIndicators) -> Dict:
        """获取入场时机分析
        
        提供详细的入场时机分析，不修改信号，仅用于分析。
        
        Args:
            data: 市场数据列表
            indicators: PVFRS指标
            
        Returns:
            Dict: 入场时机分析结果
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            if len(data) < 2:
                return {
                    'analysis_available': False,
                    'reason': '数据不足，需要至少2天数据'
                }
            
            # 获取综合分析
            analysis_result = self.entry_timing_optimizer.optimize_entry_timing_comprehensive(
                data, indicators
            )
            
            return {
                'analysis_available': True,
                'price_breakthrough': {
                    'detected': analysis_result['price_analysis']['has_breakthrough'],
                    'strength': analysis_result['price_analysis']['breakthrough_strength'],
                    'status': analysis_result['price_analysis']['monitoring_status']
                },
                'volume_breakthrough': {
                    'detected': analysis_result['volume_analysis']['has_breakthrough'],
                    'timing_score': analysis_result['volume_analysis']['entry_timing_score'],
                    'status': analysis_result['volume_analysis']['confirmation_status']
                },
                'amplitude_validation': {
                    'valid': analysis_result['amplitude_analysis']['is_valid'],
                    'coefficient': analysis_result['amplitude_analysis']['amplitude_coefficient'],
                    'should_wait': analysis_result['amplitude_analysis']['should_wait'],
                    'recommendation': analysis_result['amplitude_analysis']['entry_readiness']['recommendation']
                },
                'comprehensive_assessment': {
                    'score': analysis_result['comprehensive_score'],
                    'optimal_timing': analysis_result['optimal_entry_timing'],
                    'good_timing': analysis_result['good_entry_timing'],
                    'recommendation': analysis_result['recommendation']
                },
                'timing_summary': analysis_result['timing_summary']
            }
            
        except Exception as e:
            raise CalculationException(f"入场时机分析失败: {str(e)}")
    
    def _calculate_buy_signal_strength(self, indicators: PVFRSIndicators, 
                                     conditions_met: Dict[str, bool]) -> float:
        """计算买入信号强度
        
        Args:
            indicators: PVFRS指标
            conditions_met: 满足的条件
            
        Returns:
            float: 信号强度 (0-1)
        """
        # 基础强度来自共振强度
        base_strength = indicators.resonance_strength
        
        # 根据满足的关键条件调整强度
        strength_adjustments = 0.0
        
        # 价格维度加分项
        if conditions_met.get('macro_displacement_positive', False):
            strength_adjustments += 0.05
        if conditions_met.get('instant_strength_positive', False):
            strength_adjustments += 0.05
        
        # 频率维度加分项
        if conditions_met.get('frequency_advantage', False):
            strength_adjustments += 0.05
        if conditions_met.get('no_false_prosperity', False):
            strength_adjustments += 0.03
        
        # 成交量维度加分项
        if conditions_met.get('volume_price_resonance', False):
            strength_adjustments += 0.07
        if conditions_met.get('strong_fund_support', False):
            strength_adjustments += 0.05
        
        # 计算最终强度
        final_strength = base_strength + strength_adjustments
        
        # 确保在0-1范围内
        return max(0.0, min(1.0, final_strength))
    
    def _generate_buy_signal_reason(self, conditions_met: Dict[str, bool], 
                                  signal_strength: float) -> str:
        """生成买入信号原因描述
        
        Args:
            conditions_met: 满足的条件
            signal_strength: 信号强度
            
        Returns:
            str: 信号原因描述
        """
        reasons = []
        
        # 价格维度原因
        if conditions_met.get('macro_displacement_positive', False):
            reasons.append("价格宏观位移为正")
        if conditions_met.get('instant_strength_positive', False):
            reasons.append("即时强度为正")
        
        # 频率维度原因
        if conditions_met.get('frequency_advantage', False):
            reasons.append("上涨频率优势")
        if conditions_met.get('continuous_buying_support', False):
            reasons.append("持续买盘支撑")
        if conditions_met.get('no_false_prosperity', False):
            reasons.append("无虚假繁荣")
        
        # 成交量维度原因
        if conditions_met.get('volume_efficiency', False):
            reasons.append("成交量效率提升")
        if conditions_met.get('volume_price_resonance', False):
            reasons.append("量价共振")
        if conditions_met.get('strong_fund_support', False):
            reasons.append("强劲资金支撑")
        
        # 生成描述
        if signal_strength >= self.high_quality_threshold:
            quality_desc = "高质量"
        elif signal_strength >= self.min_signal_strength:
            quality_desc = "中等质量"
        else:
            quality_desc = "低质量"
        
        reason_text = f"PVFRS三维共振{quality_desc}买入信号"
        if reasons:
            reason_text += f": {', '.join(reasons)}"
        
        reason_text += f" (强度: {signal_strength:.2f})"
        
        return reason_text
    
    def _check_price_breakthrough(self, data: List[MarketData], 
                                indicators: PVFRSIndicators) -> bool:
        """检查价格穿越条件
        
        检测价格向上穿越平均价格d的时机。
        
        Args:
            data: 市场数据列表
            indicators: PVFRS指标
            
        Returns:
            bool: 是否满足价格穿越条件
        """
        if len(data) < 2:
            return False
        
        current_price = data[-1].close
        previous_price = data[-2].close
        avg_price = indicators.avg_price_20d
        
        # 价格穿越条件：当前价格高于平均价格，且前一天价格低于或等于平均价格
        price_breakthrough = (current_price > avg_price and previous_price <= avg_price)
        
        return price_breakthrough
    
    def _check_volume_breakthrough(self, current_data: MarketData, 
                                 indicators: PVFRSIndicators) -> bool:
        """检查成交量突破条件
        
        检测当日成交量突破平均量m的情况。
        
        Args:
            current_data: 当前市场数据
            indicators: PVFRS指标
            
        Returns:
            bool: 是否满足成交量突破条件
        """
        current_volume = current_data.volume
        avg_volume = indicators.avg_volume_20d
        
        # 成交量突破条件：当前成交量显著高于平均成交量（至少1.2倍）
        volume_breakthrough = current_volume >= avg_volume * 1.2
        
        return volume_breakthrough
    
    def _validate_amplitude_coefficient(self, indicators: PVFRSIndicators) -> bool:
        """验证幅度校验系数
        
        计算并验证Δ₂₀/d系数的有效性。
        
        Args:
            indicators: PVFRS指标
            
        Returns:
            bool: 幅度校验系数是否有效
        """
        if indicators.avg_price_20d <= 0:
            return False
        
        # 计算幅度校验系数
        amplitude_coefficient = indicators.macro_displacement / indicators.avg_price_20d
        
        # 幅度校验系数有效性标准：
        # 1. 系数必须为正（价格整体上涨）
        # 2. 系数不能过小（至少1%的涨幅）
        # 3. 系数不能过大（避免异常波动）
        min_coefficient = 0.01  # 最小1%涨幅
        max_coefficient = 0.30  # 最大30%涨幅
        
        amplitude_validation = min_coefficient <= amplitude_coefficient <= max_coefficient
        
        return amplitude_validation
    
    def generate_signal_summary(self, signals: List[Signal]) -> Dict:
        """生成信号汇总统计
        
        Args:
            signals: 信号列表
            
        Returns:
            Dict: 信号汇总统计
        """
        if not signals:
            return {
                'total_signals': 0,
                'buy_signals': 0,
                'sell_signals': 0,
                'avg_strength': 0.0,
                'high_quality_signals': 0,
                'signal_distribution': {}
            }
        
        # 统计信号类型
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        sell_signals = [s for s in signals if s.signal_type == SignalType.SELL]
        
        # 计算平均强度
        avg_strength = sum(s.strength for s in signals) / len(signals)
        
        # 统计高质量信号
        high_quality_signals = len([s for s in signals if s.strength >= self.high_quality_threshold])
        
        # 信号强度分布
        strength_ranges = {
            '0.0-0.3': 0,
            '0.3-0.6': 0,
            '0.6-0.8': 0,
            '0.8-1.0': 0
        }
        
        for signal in signals:
            if signal.strength < 0.3:
                strength_ranges['0.0-0.3'] += 1
            elif signal.strength < 0.6:
                strength_ranges['0.3-0.6'] += 1
            elif signal.strength < 0.8:
                strength_ranges['0.6-0.8'] += 1
            else:
                strength_ranges['0.8-1.0'] += 1
        
        return {
            'total_signals': len(signals),
            'buy_signals': len(buy_signals),
            'sell_signals': len(sell_signals),
            'avg_strength': avg_strength,
            'high_quality_signals': high_quality_signals,
            'signal_distribution': strength_ranges
        }
    
    def validate_signal_quality(self, signal: Signal) -> bool:
        """验证信号质量
        
        Args:
            signal: 待验证的信号
            
        Returns:
            bool: 信号是否达到质量要求
        """
        # 基本质量要求
        if signal.strength < self.min_signal_strength:
            return False
        
        # 买入信号的额外质量要求
        if signal.signal_type == SignalType.BUY:
            # 必须有关键条件满足
            required_conditions = [
                'macro_displacement_positive',
                'frequency_advantage',
                'volume_efficiency'
            ]
            
            for condition in required_conditions:
                if not signal.conditions_met.get(condition, False):
                    return False
        
        return True
    
    def filter_signals(self, price_indicators: Dict, frequency_indicators: Dict, 
                      volume_indicators: Dict) -> bool:
        """信号过滤逻辑
        
        确保任一维度条件不满足时不生成信号，实现严格的条件验证。
        
        Args:
            price_indicators: 价格维度分析结果
            frequency_indicators: 频率维度分析结果
            volume_indicators: 成交量维度分析结果
            
        Returns:
            bool: 是否应该生成信号（True表示通过过滤，可以生成信号）
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            # 严格的三维条件验证
            return self._strict_dimension_validation(
                price_indicators, frequency_indicators, volume_indicators
            )
            
        except Exception as e:
            raise CalculationException(f"信号过滤失败: {str(e)}")
    
    def _strict_dimension_validation(self, price_indicators: Dict, 
                                   frequency_indicators: Dict, 
                                   volume_indicators: Dict) -> bool:
        """严格的维度条件验证
        
        实现严格的条件验证，确保所有维度条件都满足才生成信号。
        
        Args:
            price_indicators: 价格维度指标
            frequency_indicators: 频率维度指标
            volume_indicators: 成交量维度指标
            
        Returns:
            bool: 是否通过严格验证
        """
        # 价格维度严格验证
        price_valid = self._validate_price_dimension_strict(price_indicators)
        if not price_valid:
            return False
        
        # 频率维度严格验证
        frequency_valid = self._validate_frequency_dimension_strict(frequency_indicators)
        if not frequency_valid:
            return False
        
        # 成交量维度严格验证
        volume_valid = self._validate_volume_dimension_strict(volume_indicators)
        if not volume_valid:
            return False
        
        # 所有维度都通过验证
        return True
    
    def _validate_price_dimension_strict(self, price_indicators: Dict) -> bool:
        """价格维度严格验证
        
        Args:
            price_indicators: 价格维度指标
            
        Returns:
            bool: 价格维度是否通过严格验证
        """
        # 检查必需指标是否存在
        required_keys = ['macro_displacement', 'instant_deviation', 'avg_price_20d']
        for key in required_keys:
            if key not in price_indicators:
                return False
        
        # 严格条件验证
        macro_displacement = price_indicators.get('macro_displacement', 0)
        instant_deviation = price_indicators.get('instant_deviation', 0)
        avg_price_20d = price_indicators.get('avg_price_20d', 0)
        
        # 条件1: 宏观位移必须为正且有意义（至少0.01）
        if macro_displacement <= 0.01:
            return False
        
        # 条件2: 即时强度必须为正
        if instant_deviation <= 0:
            return False
        
        # 条件3: 平均价格必须有效
        if avg_price_20d <= 0:
            return False
        
        # 条件4: 幅度系数验证
        amplitude_ratio = macro_displacement / avg_price_20d
        if amplitude_ratio < 0.005 or amplitude_ratio > 0.5:  # 0.5%-50%范围
            return False
        
        return True
    
    def _validate_frequency_dimension_strict(self, frequency_indicators: Dict) -> bool:
        """频率维度严格验证
        
        Args:
            frequency_indicators: 频率维度指标
            
        Returns:
            bool: 频率维度是否通过严格验证
        """
        # 检查必需指标是否存在
        required_keys = ['rising_days', 'falling_days', 'frequency_advantage']
        for key in required_keys:
            if key not in frequency_indicators:
                return False
        
        # 严格条件验证
        rising_days = frequency_indicators.get('rising_days', 0)
        falling_days = frequency_indicators.get('falling_days', 0)
        frequency_advantage = frequency_indicators.get('frequency_advantage', False)
        has_false_prosperity = frequency_indicators.get('has_false_prosperity', True)
        
        # 条件1: 必须有频率优势
        if not frequency_advantage:
            return False
        
        # 条件2: 上涨天数必须明显多于下跌天数（至少多2天）
        if rising_days <= falling_days + 1:
            return False
        
        # 条件3: 上涨天数必须达到最低要求（20天中至少8天）
        if rising_days < 8:
            return False
        
        # 条件4: 不能有虚假繁荣
        if has_false_prosperity:
            return False
        
        # 条件5: 总的交易天数验证（上涨+下跌天数应该合理）
        total_trend_days = rising_days + falling_days
        if total_trend_days < 15 or total_trend_days > 19:  # 20天中应该有15-19天有明确趋势
            return False
        
        return True
    
    def _validate_volume_dimension_strict(self, volume_indicators: Dict) -> bool:
        """成交量维度严格验证
        
        Args:
            volume_indicators: 成交量维度指标
            
        Returns:
            bool: 成交量维度是否通过严格验证
        """
        # 检查必需指标是否存在
        required_keys = ['current_volume', 'avg_volume_20d', 'efficiency_ratio']
        for key in required_keys:
            if key not in volume_indicators:
                return False
        
        # 严格条件验证
        current_volume = volume_indicators.get('current_volume', 0)
        avg_volume_20d = volume_indicators.get('avg_volume_20d', 0)
        efficiency_ratio = volume_indicators.get('efficiency_ratio', 0)
        volume_price_resonance = volume_indicators.get('volume_price_resonance', False)
        strong_fund_support = volume_indicators.get('strong_fund_support', False)
        
        # 条件1: 成交量数据有效性
        if current_volume <= 0 or avg_volume_20d <= 0:
            return False
        
        # 条件2: 效率比必须大于1（当前成交量高于平均）
        if efficiency_ratio <= 1.0:
            return False
        
        # 条件3: 效率比不能过度异常（避免异常交易）
        if efficiency_ratio > 10.0:
            return False
        
        # 条件4: 必须有量价共振
        if not volume_price_resonance:
            return False
        
        # 条件5: 必须有强劲资金支撑
        if not strong_fund_support:
            return False
        
        # 条件6: 成交量增幅验证（至少增加20%）
        volume_increase_ratio = (current_volume - avg_volume_20d) / avg_volume_20d
        if volume_increase_ratio < 0.2:
            return False
        
        return True
    
    def get_filter_rejection_reason(self, price_indicators: Dict, 
                                  frequency_indicators: Dict, 
                                  volume_indicators: Dict) -> str:
        """获取过滤拒绝原因
        
        当信号被过滤时，返回具体的拒绝原因。
        
        Args:
            price_indicators: 价格维度指标
            frequency_indicators: 频率维度指标
            volume_indicators: 成交量维度指标
            
        Returns:
            str: 拒绝原因描述
        """
        reasons = []
        
        # 检查价格维度
        if not self._validate_price_dimension_strict(price_indicators):
            price_issues = []
            
            macro_displacement = price_indicators.get('macro_displacement', 0)
            instant_deviation = price_indicators.get('instant_deviation', 0)
            avg_price_20d = price_indicators.get('avg_price_20d', 0)
            
            if macro_displacement <= 0.01:
                price_issues.append("宏观位移不足")
            if instant_deviation <= 0:
                price_issues.append("即时强度为负")
            if avg_price_20d > 0:
                amplitude_ratio = macro_displacement / avg_price_20d
                if amplitude_ratio < 0.005:
                    price_issues.append("幅度系数过小")
                elif amplitude_ratio > 0.5:
                    price_issues.append("幅度系数过大")
            
            if price_issues:
                reasons.append(f"价格维度: {', '.join(price_issues)}")
        
        # 检查频率维度
        if not self._validate_frequency_dimension_strict(frequency_indicators):
            frequency_issues = []
            
            rising_days = frequency_indicators.get('rising_days', 0)
            falling_days = frequency_indicators.get('falling_days', 0)
            has_false_prosperity = frequency_indicators.get('has_false_prosperity', True)
            
            if rising_days <= falling_days + 1:
                frequency_issues.append("频率优势不足")
            if rising_days < 8:
                frequency_issues.append("上涨天数不足")
            if has_false_prosperity:
                frequency_issues.append("存在虚假繁荣")
            
            if frequency_issues:
                reasons.append(f"频率维度: {', '.join(frequency_issues)}")
        
        # 检查成交量维度
        if not self._validate_volume_dimension_strict(volume_indicators):
            volume_issues = []
            
            efficiency_ratio = volume_indicators.get('efficiency_ratio', 0)
            volume_price_resonance = volume_indicators.get('volume_price_resonance', False)
            strong_fund_support = volume_indicators.get('strong_fund_support', False)
            
            if efficiency_ratio <= 1.0:
                volume_issues.append("成交量效率不足")
            elif efficiency_ratio > 10.0:
                volume_issues.append("成交量异常放大")
            if not volume_price_resonance:
                volume_issues.append("缺乏量价共振")
            if not strong_fund_support:
                volume_issues.append("资金支撑不足")
            
            if volume_issues:
                reasons.append(f"成交量维度: {', '.join(volume_issues)}")
        
        if reasons:
            return f"信号被过滤 - {'; '.join(reasons)}"
        else:
            return "信号通过所有过滤条件"