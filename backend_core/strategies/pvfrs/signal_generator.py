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
        self.default_buy_bias_min = 0.02  # 默认买入乖离率阈值2%
    
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
            
            # 确定信号质量等级
            quality_level = self._determine_signal_quality(signal_strength, indicators, conditions_met)
            
            # 计算乖离率质量得分（新增）
            # 从价格维度指标中获取bias
            price_indicators_dict = {}
            if hasattr(indicators, 'avg_price_20d') and indicators.avg_price_20d > 0:
                # 计算bias = (当前价格 - 20日均价) / 20日均价
                # 当前价格可以通过 instant_deviation + avg_price_20d 计算
                current_price_estimate = indicators.instant_deviation + indicators.avg_price_20d
                price_indicators_dict['bias'] = (current_price_estimate - indicators.avg_price_20d) / indicators.avg_price_20d
            else:
                price_indicators_dict['bias'] = 0.0
            
            # 从conditions_met中获取bias（如果已计算）
            if 'bias' in conditions_met:
                price_indicators_dict['bias'] = conditions_met['bias']
            
            bias_score = self._calculate_bias_quality_score_from_dict(price_indicators_dict, conditions_met)
            
            # 根据质量等级调整信号强度
            adjusted_strength = self._adjust_strength_by_quality(signal_strength, quality_level, bias_score)
            
            # 生成信号原因描述
            reason = self._generate_buy_signal_reason(conditions_met, adjusted_strength, quality_level)
            
            # 创建买入信号
            buy_signal = Signal(
                symbol=symbol,
                date=date,
                signal_type=SignalType.BUY,
                price=price,
                strength=adjusted_strength,
                reason=reason,
                indicators=indicators,
                conditions_met=conditions_met.copy()
            )
            
            # 添加质量等级信息
            buy_signal.conditions_met['quality_level'] = quality_level
            buy_signal.conditions_met['original_strength'] = signal_strength
            buy_signal.conditions_met['bias_score'] = bias_score
            
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
    
    def _determine_signal_quality(self, signal_strength: float, indicators: PVFRSIndicators, 
                                  conditions_met: Dict[str, bool]) -> str:
        """确定信号质量等级
        
        Args:
            signal_strength: 信号强度
            indicators: PVFRS指标
            conditions_met: 满足的条件
            
        Returns:
            str: 质量等级 ('high', 'medium', 'low')
        """
        # 高质量信号标准：
        # 1. 共振强度 > 0.85
        # 2. 所有关键条件都满足
        if signal_strength >= 0.85:
            critical_conditions = [
                'macro_displacement_positive',
                'frequency_advantage',
                'volume_price_resonance',
                'strong_fund_support',
                'continuous_buying_support'
            ]
            critical_met = sum(1 for cond in critical_conditions if conditions_met.get(cond, False))
            if critical_met >= 4:  # 至少满足4个关键条件
                return 'high'
        
        # 中等质量信号标准：
        # 1. 共振强度 >= 0.7
        # 2. 至少满足基本条件
        if signal_strength >= 0.7:
            basic_conditions = [
                'macro_displacement_positive',
                'frequency_advantage',
                'volume_efficiency'
            ]
            basic_met = sum(1 for cond in basic_conditions if conditions_met.get(cond, False))
            if basic_met >= 2:  # 至少满足2个基本条件
                return 'medium'
        
        # 其他情况为低质量
        return 'low'
    
    def _calculate_bias_quality_score_from_dict(self, price_indicators: Dict, conditions_met: Dict[str, bool]) -> float:
        """计算乖离率质量得分（从字典获取）
        
        Args:
            price_indicators: 价格维度指标字典
            conditions_met: 满足的条件
            
        Returns:
            float: 乖离率质量得分 (0-1)
        """
        try:
            bias = price_indicators.get('bias', 0.0)
            
            # 计算bias质量得分
            if 0.01 <= bias <= 0.05:  # 1%-5%：合理区间
                return 1.0
            elif bias < 0.01:  # <1%：偏低，可能还未启动
                return 0.7
            elif bias > 0.05:  # >5%：偏高，可能已过热
                return 0.8
            else:
                return 0.7
                
        except Exception:
            return 0.7
    
    def _calculate_bias_quality_score(self, indicators: PVFRSIndicators, conditions_met: Dict[str, bool]) -> float:
        """计算乖离率质量得分
        
        bias处于合理区间（1%-5%）：得分1.0
        bias偏低（<1%）：得分0.7（可能还未启动）
        bias偏高（>5%）：得分0.8（可能已过热）
        
        Args:
            indicators: PVFRS指标
            conditions_met: 满足的条件
            
        Returns:
            float: 乖离率质量得分 (0-1)
        """
        try:
            # 从价格维度指标中获取bias
            # 注意：bias需要从价格维度分析结果中获取
            # 这里假设bias已经包含在indicators中，或者需要从conditions_met中获取
            
            # 如果没有bias信息，返回中等得分
            bias = conditions_met.get('bias', None)
            if bias is None:
                # 尝试从indicators计算
                if indicators.avg_price_20d > 0:
                    bias = (indicators.macro_displacement + indicators.avg_price_20d - indicators.avg_price_20d) / indicators.avg_price_20d
                else:
                    return 0.7
            
            # 计算bias质量得分
            if 0.01 <= bias <= 0.05:  # 1%-5%：合理区间
                return 1.0
            elif bias < 0.01:  # <1%：偏低，可能还未启动
                return 0.7
            elif bias > 0.05:  # >5%：偏高，可能已过热
                return 0.8
            else:
                return 0.7
                
        except Exception:
            return 0.7
    
    def _adjust_strength_by_quality(self, signal_strength: float, quality_level: str, bias_score: float = 0.7) -> float:
        """根据质量等级调整信号强度（增强版：包含bias得分）
        
        Args:
            signal_strength: 原始信号强度
            quality_level: 质量等级
            bias_score: 乖离率质量得分（新增）
            
        Returns:
            float: 调整后的信号强度
        """
        if quality_level == 'high':
            # 高质量信号：轻微提升（最多到1.0）
            base_adjustment = signal_strength * 1.05
        elif quality_level == 'medium':
            # 中等质量信号：保持原样
            base_adjustment = signal_strength
        else:
            # 低质量信号：降低强度
            base_adjustment = signal_strength * 0.9
        
        # 根据bias得分进一步调整（权重10%）
        bias_adjustment = base_adjustment * 0.9 + base_adjustment * bias_score * 0.1
        
        return max(0.0, min(1.0, bias_adjustment))
    
    def _generate_buy_signal_reason(self, conditions_met: Dict[str, bool], 
                                  signal_strength: float, quality_level: str = None) -> str:
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
        if conditions_met.get('continuous_volume_increase', False):
            reasons.append("连续放量")
        
        # 生成描述
        if quality_level:
            quality_desc_map = {
                'high': '高质量',
                'medium': '中等质量',
                'low': '低质量'
            }
            quality_desc = quality_desc_map.get(quality_level, '中等质量')
        elif signal_strength >= self.high_quality_threshold:
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
    
    def calculate_dynamic_buy_bias_threshold(self, price_indicators: Dict, current_price: float) -> float:
        """动态计算买入乖离率阈值
        
        根据市场波动率和股票价格区间动态调整buy_bias_min
        
        Args:
            price_indicators: 价格维度指标
            current_price: 当前价格
            
        Returns:
            float: 动态调整后的买入乖离率阈值
        """
        try:
            base_threshold = self.default_buy_bias_min  # 基础阈值2%
            
            # 1. 根据市场波动率调整
            price_volatility = price_indicators.get('price_volatility', 0.15)
            
            if price_volatility > 0.20:  # 高波动市场（波动率>20%）
                volatility_adjustment = 0.01  # +1%
            elif price_volatility > 0.10:  # 中等波动市场（10%<波动率<=20%）
                volatility_adjustment = 0.0  # 不变
            else:  # 低波动市场（波动率<=10%）
                volatility_adjustment = -0.01  # -1%
            
            # 2. 根据股票价格区间调整
            if current_price < 10:  # 低价股（<10元）
                price_adjustment = 0.005  # +0.5%
            elif current_price > 50:  # 高价股（>50元）
                price_adjustment = -0.005  # -0.5%
            else:
                price_adjustment = 0.0
            
            # 计算最终阈值
            dynamic_threshold = base_threshold + volatility_adjustment + price_adjustment
            
            # 确保阈值在合理范围内（0.5%-5%）
            return max(0.005, min(0.05, dynamic_threshold))
            
        except Exception as e:
            # 如果计算失败，返回默认值
            return self.default_buy_bias_min
    
    def filter_signals(self, price_indicators: Dict, frequency_indicators: Dict, 
                      volume_indicators: Dict) -> bool:
        """信号过滤逻辑（增强版：包含乖离率协同验证）
        
        确保任一维度条件不满足时不生成信号，实现严格的条件验证。
        新增：乖离率与其他指标的协同验证
        
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
            basic_validation = self._strict_dimension_validation(
                price_indicators, frequency_indicators, volume_indicators
            )
            
            if not basic_validation:
                return False
            
            # 新增：乖离率协同验证
            bias_validation = self._validate_bias_synergy(
                price_indicators, volume_indicators
            )
            
            return bias_validation
            
        except Exception as e:
            raise CalculationException(f"信号过滤失败: {str(e)}")
    
    def _validate_bias_synergy(self, price_indicators: Dict, volume_indicators: Dict) -> bool:
        """验证乖离率与其他指标的协同
        
        bias与价格位置的协同：
        - 价格在20天区间低位（<30%）+ bias适中（1%-3%）：买入信号增强
        - 价格在20天区间高位（>70%）+ bias偏高（>5%）：卖出信号增强
        
        bias与成交量的协同：
        - bias扩大 + 成交量放大：买入信号增强
        - bias扩大 + 成交量萎缩：卖出信号（背离）
        
        Args:
            price_indicators: 价格维度指标
            volume_indicators: 成交量维度指标
            
        Returns:
            bool: 是否通过协同验证
        """
        try:
            bias = price_indicators.get('bias', 0.0)
            bias_trend = price_indicators.get('bias_trend', {})
            
            # 获取价格位置信息（如果有）
            # 这里需要从entry_timing_optimizer获取价格位置，暂时使用bias作为代理
            
            # 基础验证：bias必须在合理范围内（0.5%-8%）
            if bias < 0.005 or bias > 0.08:
                return False
            
            # 验证bias趋势：买入时bias应该向上或稳定
            if isinstance(bias_trend, dict):
                trend_5d = bias_trend.get('trend_5d', 'stable')
                # 如果bias在收敛且bias<1%，可能还未启动，允许通过
                if trend_5d == 'converging' and bias < 0.01:
                    return True
                # 如果bias在扩大，需要配合成交量放大
                if trend_5d == 'expanding':
                    volume_increasing = volume_indicators.get('volume_increasing', False)
                    if not volume_increasing:
                        return False  # bias扩大但成交量未放大，可能是背离
            
            return True
            
        except Exception:
            return True  # 如果验证失败，默认通过
    
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
        
        # 条件4: 幅度系数验证（优化：范围从0.5%-50%调整为1%-30%）
        amplitude_ratio = macro_displacement / avg_price_20d
        if amplitude_ratio < 0.01 or amplitude_ratio > 0.30:  # 1%-30%范围
            return False
        
        # 条件5: 价格趋势持续性验证（新增）
        trend_persistence = price_indicators.get('trend_persistence', {})
        if isinstance(trend_persistence, dict):
            if not trend_persistence.get('is_persistent', False):
                return False
        
        # 条件6: 价格波动率验证（新增：波动率<15%）
        price_volatility = price_indicators.get('price_volatility', 1.0)
        if price_volatility >= 0.15:
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
        
        # 条件2: 上涨天数必须明显多于下跌天数（至少多3天，即 Z > F+3）
        if rising_days <= falling_days + 2:  # Z > F+3 等价于 Z > F+2（因为整数）
            return False
        
        # 条件3: 上涨天数必须达到最低要求（20天中至少10天，占50%）
        if rising_days < 10:
            return False
        
        # 条件6: 最近10天中上涨天数>=6（上涨持续性验证）
        recent_rising_persistence = frequency_indicators.get('recent_rising_persistence', 0)
        if recent_rising_persistence < 6:
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
        
        # 条件5: 必须有强劲资金支撑（包括连续放量）
        strong_fund_support = volume_indicators.get('strong_fund_support', False)
        continuous_volume_increase = volume_indicators.get('continuous_volume_increase', False)
        if not (strong_fund_support and continuous_volume_increase):
            return False
        
        # 条件6: 成交量趋势持续性
        volume_trend_persistence = volume_indicators.get('volume_trend_persistence', {})
        if isinstance(volume_trend_persistence, dict):
            if not volume_trend_persistence.get('is_persistent', False):
                return False
        
        # 条件7: 成交量增幅验证（至少增加20%）
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