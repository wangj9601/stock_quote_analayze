"""
PVFRS策略入场时机优化器实现
负责优化入场时机，检测价格穿越、成交量突破和幅度校验
"""

from typing import List, Dict, Optional, Tuple
from .models import MarketData, PVFRSIndicators, Signal, CalculationException, DataInsufficientException
from .interfaces import ISignalGenerator


class EntryTimingOptimizer:
    """入场时机优化器
    
    负责优化PVFRS策略的入场时机：
    - 检测价格向上穿越平均价格d的时机
    - 检测当日成交量突破平均量m的情况
    - 计算和验证幅度校验系数Δ₂₀/d
    - 实现等待机制直到最佳入场时机
    """
    
    def __init__(self):
        """初始化入场时机优化器"""
        self.min_amplitude_coefficient = 0.01  # 最小幅度系数1%
        self.max_amplitude_coefficient = 0.30  # 最大幅度系数30%
        self.volume_breakthrough_multiplier = 1.2  # 成交量突破倍数
        self.price_breakthrough_buffer = 0.001  # 价格穿越缓冲区0.1%
    
    def monitor_price_breakthrough(self, data: List[MarketData], avg_price_20d: float) -> Dict:
        """监控价格穿越条件
        
        检测价格向上穿越平均价格d的时机，实现入场机会监控逻辑。
        
        Args:
            data: 市场数据列表，按时间顺序排列
            avg_price_20d: 20日平均价格d
            
        Returns:
            Dict: 价格穿越监控结果
            
        Raises:
            DataInsufficientException: 数据不足时抛出
            CalculationException: 计算异常时抛出
        """
        if len(data) < 2:
            raise DataInsufficientException("价格穿越监控需要至少2天数据")
        
        if avg_price_20d <= 0:
            raise CalculationException("20日平均价格必须大于0")
        
        try:
            current_data = data[-1]
            previous_data = data[-2]
            
            current_price = current_data.close
            previous_price = previous_data.close
            
            # 检测价格穿越条件
            breakthrough_result = self._detect_price_breakthrough(
                current_price, previous_price, avg_price_20d
            )
            
            # 计算价格相对位置
            price_position = self._calculate_price_position(current_price, avg_price_20d)
            
            # 分析穿越强度
            breakthrough_strength = self._analyze_breakthrough_strength(
                current_price, previous_price, avg_price_20d
            )
            
            # 检测穿越趋势
            breakthrough_trend = self._detect_breakthrough_trend(data, avg_price_20d)
            
            return {
                'has_breakthrough': breakthrough_result['has_breakthrough'],
                'breakthrough_type': breakthrough_result['breakthrough_type'],
                'breakthrough_margin': breakthrough_result['breakthrough_margin'],
                'current_price': current_price,
                'previous_price': previous_price,
                'avg_price_20d': avg_price_20d,
                'price_position': price_position,
                'breakthrough_strength': breakthrough_strength,
                'breakthrough_trend': breakthrough_trend,
                'entry_opportunity': breakthrough_result['has_breakthrough'] and breakthrough_strength > 0.5,
                'monitoring_status': self._get_monitoring_status(
                    breakthrough_result, price_position, breakthrough_strength
                )
            }
            
        except Exception as e:
            raise CalculationException(f"价格穿越监控失败: {str(e)}")
    
    def _detect_price_breakthrough(self, current_price: float, previous_price: float, 
                                 avg_price: float) -> Dict:
        """检测价格穿越
        
        Args:
            current_price: 当前价格
            previous_price: 前一日价格
            avg_price: 平均价格
            
        Returns:
            Dict: 穿越检测结果
        """
        # 添加缓冲区避免噪音
        breakthrough_threshold = avg_price * (1 + self.price_breakthrough_buffer)
        
        # 检测向上穿越
        upward_breakthrough = (
            current_price > breakthrough_threshold and 
            previous_price <= avg_price
        )
        
        # 检测向下穿越
        downward_breakthrough = (
            current_price < avg_price and 
            previous_price >= breakthrough_threshold
        )
        
        # 计算穿越幅度
        if upward_breakthrough:
            breakthrough_margin = (current_price - avg_price) / avg_price
            breakthrough_type = "upward"
        elif downward_breakthrough:
            breakthrough_margin = (avg_price - current_price) / avg_price
            breakthrough_type = "downward"
        else:
            breakthrough_margin = 0.0
            breakthrough_type = "none"
        
        return {
            'has_breakthrough': upward_breakthrough,  # 只关注向上穿越
            'breakthrough_type': breakthrough_type,
            'breakthrough_margin': breakthrough_margin,
            'upward_breakthrough': upward_breakthrough,
            'downward_breakthrough': downward_breakthrough
        }
    
    def _calculate_price_position(self, current_price: float, avg_price: float) -> Dict:
        """计算价格相对位置
        
        Args:
            current_price: 当前价格
            avg_price: 平均价格
            
        Returns:
            Dict: 价格位置信息
        """
        relative_position = (current_price - avg_price) / avg_price
        
        if relative_position > 0.05:
            position_level = "significantly_above"
        elif relative_position > 0.01:
            position_level = "moderately_above"
        elif relative_position > -0.01:
            position_level = "near_average"
        elif relative_position > -0.05:
            position_level = "moderately_below"
        else:
            position_level = "significantly_below"
        
        return {
            'relative_position': relative_position,
            'position_level': position_level,
            'above_average': relative_position > 0,
            'distance_from_average': abs(relative_position)
        }
    
    def _analyze_breakthrough_strength(self, current_price: float, previous_price: float, 
                                     avg_price: float) -> float:
        """分析穿越强度
        
        Args:
            current_price: 当前价格
            previous_price: 前一日价格
            avg_price: 平均价格
            
        Returns:
            float: 穿越强度 (0-1)
        """
        if current_price <= avg_price:
            return 0.0
        
        # 计算价格变化幅度
        if previous_price > 0:
            price_change = (current_price - previous_price) / previous_price
        else:
            price_change = 0.0
        
        # 计算穿越幅度
        breakthrough_margin = (current_price - avg_price) / avg_price
        
        # 综合计算强度
        strength = 0.0
        
        # 穿越幅度贡献 (40%)
        if breakthrough_margin > 0:
            strength += min(0.4, breakthrough_margin * 10)  # 4%穿越=满分
        
        # 价格变化贡献 (30%)
        if price_change > 0:
            strength += min(0.3, price_change * 15)  # 2%涨幅=满分
        
        # 持续性贡献 (30%)
        if current_price > avg_price and previous_price > avg_price * 0.98:
            strength += 0.3  # 连续接近或超过平均价格
        
        return min(1.0, strength)
    
    def _detect_breakthrough_trend(self, data: List[MarketData], avg_price: float) -> Dict:
        """检测穿越趋势
        
        Args:
            data: 市场数据列表
            avg_price: 平均价格
            
        Returns:
            Dict: 趋势分析结果
        """
        if len(data) < 5:
            return {'trend': 'insufficient_data', 'strength': 0.0}
        
        # 分析最近5天的价格趋势
        recent_data = data[-5:]
        prices = [d.close for d in recent_data]
        
        # 计算趋势方向
        above_avg_count = sum(1 for price in prices if price > avg_price)
        approaching_count = sum(1 for price in prices if avg_price * 0.98 <= price <= avg_price * 1.02)
        
        # 计算价格动量
        if len(prices) >= 2:
            momentum = (prices[-1] - prices[0]) / prices[0]
        else:
            momentum = 0.0
        
        # 判断趋势
        if above_avg_count >= 3:
            trend = "strong_upward"
            strength = 0.8 + min(0.2, momentum * 10)
        elif above_avg_count >= 2 or approaching_count >= 3:
            trend = "moderate_upward"
            strength = 0.5 + min(0.3, momentum * 15)
        elif momentum > 0.01:
            trend = "weak_upward"
            strength = 0.3 + min(0.2, momentum * 20)
        else:
            trend = "sideways_or_down"
            strength = max(0.0, 0.2 + momentum * 10)
        
        return {
            'trend': trend,
            'strength': min(1.0, max(0.0, strength)),
            'above_avg_count': above_avg_count,
            'approaching_count': approaching_count,
            'momentum': momentum
        }
    
    def _get_monitoring_status(self, breakthrough_result: Dict, price_position: Dict, 
                             breakthrough_strength: float) -> str:
        """获取监控状态描述
        
        Args:
            breakthrough_result: 穿越检测结果
            price_position: 价格位置信息
            breakthrough_strength: 穿越强度
            
        Returns:
            str: 监控状态描述
        """
        if breakthrough_result['has_breakthrough']:
            if breakthrough_strength > 0.7:
                return "强势穿越，优质入场机会"
            elif breakthrough_strength > 0.5:
                return "有效穿越，良好入场机会"
            else:
                return "弱势穿越，谨慎观察"
        
        elif price_position['position_level'] == "near_average":
            return "接近平均价格，等待穿越"
        
        elif price_position['above_average']:
            return "已在平均价格之上，监控回调"
        
        else:
            return "低于平均价格，等待上涨"
    
    def confirm_volume_breakthrough(self, current_data: MarketData, avg_volume_20d: float) -> Dict:
        """确认成交量突破
        
        检测当日成交量突破平均量m的情况，确认最佳入场时机。
        
        Args:
            current_data: 当前市场数据
            avg_volume_20d: 20日平均成交量m
            
        Returns:
            Dict: 成交量突破确认结果
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        if avg_volume_20d <= 0:
            raise CalculationException("20日平均成交量必须大于0")
        
        try:
            current_volume = current_data.volume
            
            # 检测成交量突破
            breakthrough_result = self._detect_volume_breakthrough(current_volume, avg_volume_20d)
            
            # 分析成交量质量
            volume_quality = self._analyze_volume_quality(current_volume, avg_volume_20d)
            
            # 计算突破强度
            breakthrough_intensity = self._calculate_volume_breakthrough_intensity(
                current_volume, avg_volume_20d
            )
            
            # 评估入场时机
            entry_timing_score = self._evaluate_volume_entry_timing(
                breakthrough_result, volume_quality, breakthrough_intensity
            )
            
            return {
                'has_breakthrough': breakthrough_result['has_breakthrough'],
                'volume_multiplier': breakthrough_result['volume_multiplier'],
                'breakthrough_level': breakthrough_result['breakthrough_level'],
                'current_volume': current_volume,
                'avg_volume_20d': avg_volume_20d,
                'volume_quality': volume_quality,
                'breakthrough_intensity': breakthrough_intensity,
                'entry_timing_score': entry_timing_score,
                'optimal_entry_timing': entry_timing_score > 0.6,
                'confirmation_status': self._get_volume_confirmation_status(
                    breakthrough_result, volume_quality, entry_timing_score
                )
            }
            
        except Exception as e:
            raise CalculationException(f"成交量突破确认失败: {str(e)}")
    
    def _detect_volume_breakthrough(self, current_volume: float, avg_volume: float) -> Dict:
        """检测成交量突破
        
        Args:
            current_volume: 当前成交量
            avg_volume: 平均成交量
            
        Returns:
            Dict: 成交量突破检测结果
        """
        volume_multiplier = current_volume / avg_volume
        
        # 判断突破级别
        if volume_multiplier >= 3.0:
            breakthrough_level = "exceptional"  # 异常突破
            has_breakthrough = True
        elif volume_multiplier >= 2.0:
            breakthrough_level = "strong"  # 强势突破
            has_breakthrough = True
        elif volume_multiplier >= self.volume_breakthrough_multiplier:
            breakthrough_level = "moderate"  # 适度突破
            has_breakthrough = True
        elif volume_multiplier >= 1.0:
            breakthrough_level = "weak"  # 弱势突破
            has_breakthrough = False
        else:
            breakthrough_level = "insufficient"  # 成交量不足
            has_breakthrough = False
        
        return {
            'has_breakthrough': has_breakthrough,
            'volume_multiplier': volume_multiplier,
            'breakthrough_level': breakthrough_level,
            'breakthrough_margin': volume_multiplier - 1.0
        }
    
    def _analyze_volume_quality(self, current_volume: float, avg_volume: float) -> Dict:
        """分析成交量质量
        
        Args:
            current_volume: 当前成交量
            avg_volume: 平均成交量
            
        Returns:
            Dict: 成交量质量分析结果
        """
        volume_ratio = current_volume / avg_volume
        
        # 质量评估标准
        if volume_ratio < 0.5:
            quality_level = "very_poor"
            quality_score = 0.1
        elif volume_ratio < 0.8:
            quality_level = "poor"
            quality_score = 0.3
        elif volume_ratio < 1.2:
            quality_level = "normal"
            quality_score = 0.5
        elif volume_ratio < 2.0:
            quality_level = "good"
            quality_score = 0.7
        elif volume_ratio < 5.0:
            quality_level = "excellent"
            quality_score = 0.9
        else:
            quality_level = "excessive"  # 可能异常
            quality_score = 0.6
        
        # 判断是否为健康的成交量
        is_healthy = 0.8 <= volume_ratio <= 5.0
        
        # 判断是否支持趋势
        supports_trend = volume_ratio >= 1.2
        
        return {
            'quality_level': quality_level,
            'quality_score': quality_score,
            'volume_ratio': volume_ratio,
            'is_healthy': is_healthy,
            'supports_trend': supports_trend,
            'is_excessive': volume_ratio > 5.0,
            'is_insufficient': volume_ratio < 0.8
        }
    
    def _calculate_volume_breakthrough_intensity(self, current_volume: float, 
                                               avg_volume: float) -> float:
        """计算成交量突破强度
        
        Args:
            current_volume: 当前成交量
            avg_volume: 平均成交量
            
        Returns:
            float: 突破强度 (0-1)
        """
        if avg_volume <= 0:
            return 0.0
        
        volume_ratio = current_volume / avg_volume
        
        # 基础强度计算
        if volume_ratio < 1.0:
            # 成交量不足
            intensity = volume_ratio * 0.3  # 最高0.3
        elif volume_ratio <= 2.0:
            # 正常到良好范围
            intensity = 0.3 + (volume_ratio - 1.0) * 0.4  # 0.3-0.7
        elif volume_ratio <= 3.0:
            # 强势突破范围
            intensity = 0.7 + (volume_ratio - 2.0) * 0.2  # 0.7-0.9
        elif volume_ratio <= 5.0:
            # 异常突破但仍可接受
            intensity = 0.9 + (volume_ratio - 3.0) * 0.05  # 0.9-1.0
        else:
            # 过度异常，降低评分
            intensity = max(0.5, 1.0 - (volume_ratio - 5.0) * 0.1)
        
        return min(1.0, max(0.0, intensity))
    
    def _evaluate_volume_entry_timing(self, breakthrough_result: Dict, 
                                    volume_quality: Dict, breakthrough_intensity: float) -> float:
        """评估基于成交量的入场时机
        
        Args:
            breakthrough_result: 突破检测结果
            volume_quality: 成交量质量
            breakthrough_intensity: 突破强度
            
        Returns:
            float: 入场时机评分 (0-1)
        """
        score = 0.0
        
        # 突破存在性 (30%)
        if breakthrough_result['has_breakthrough']:
            score += 0.3
        
        # 突破级别 (25%)
        level_scores = {
            'moderate': 0.15,
            'strong': 0.20,
            'exceptional': 0.25
        }
        score += level_scores.get(breakthrough_result['breakthrough_level'], 0.0)
        
        # 成交量质量 (25%)
        score += volume_quality['quality_score'] * 0.25
        
        # 突破强度 (20%)
        score += breakthrough_intensity * 0.20
        
        return min(1.0, score)
    
    def _get_volume_confirmation_status(self, breakthrough_result: Dict, 
                                      volume_quality: Dict, entry_timing_score: float) -> str:
        """获取成交量确认状态描述
        
        Args:
            breakthrough_result: 突破检测结果
            volume_quality: 成交量质量
            entry_timing_score: 入场时机评分
            
        Returns:
            str: 确认状态描述
        """
        if not breakthrough_result['has_breakthrough']:
            if volume_quality['is_insufficient']:
                return "成交量不足，等待放量"
            else:
                return "成交量正常，等待突破"
        
        level = breakthrough_result['breakthrough_level']
        
        if entry_timing_score > 0.8:
            return f"优质{level}突破，最佳入场时机"
        elif entry_timing_score > 0.6:
            return f"良好{level}突破，适合入场"
        elif entry_timing_score > 0.4:
            return f"一般{level}突破，谨慎入场"
        else:
            if volume_quality['is_excessive']:
                return f"{level}突破但成交量异常，观察后续"
            else:
                return f"{level}突破但质量一般，等待确认"
    
    def calculate_amplitude_coefficient(self, macro_displacement: float, avg_price_20d: float) -> Dict:
        """计算幅度校验系数
        
        计算Δ₂₀/d系数，验证系数有效性并实现等待机制。
        
        Args:
            macro_displacement: 宏观位移指标Δ₂₀ = d₂₀ - d₁
            avg_price_20d: 20日平均价格d
            
        Returns:
            Dict: 幅度校验系数计算结果
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        if avg_price_20d <= 0:
            raise CalculationException("20日平均价格必须大于0")
        
        try:
            # 计算幅度校验系数
            amplitude_coefficient = macro_displacement / avg_price_20d
            
            # 验证系数有效性
            validation_result = self._validate_amplitude_coefficient(amplitude_coefficient)
            
            # 分析系数质量
            coefficient_quality = self._analyze_coefficient_quality(amplitude_coefficient)
            
            # 评估等待必要性
            waiting_assessment = self._assess_waiting_necessity(
                amplitude_coefficient, validation_result, coefficient_quality
            )
            
            # 计算波幅显著性
            amplitude_significance = self._calculate_amplitude_significance(amplitude_coefficient)
            
            return {
                'amplitude_coefficient': amplitude_coefficient,
                'coefficient_percentage': amplitude_coefficient * 100,
                'is_valid': validation_result['is_valid'],
                'validation_status': validation_result['status'],
                'validation_issues': validation_result['issues'],
                'coefficient_quality': coefficient_quality,
                'amplitude_significance': amplitude_significance,
                'waiting_assessment': waiting_assessment,
                'should_wait': waiting_assessment['should_wait'],
                'wait_reason': waiting_assessment['reason'],
                'entry_readiness': self._evaluate_entry_readiness(
                    validation_result, coefficient_quality, waiting_assessment
                )
            }
            
        except Exception as e:
            raise CalculationException(f"幅度校验系数计算失败: {str(e)}")
    
    def _validate_amplitude_coefficient(self, coefficient: float) -> Dict:
        """验证幅度校验系数有效性
        
        Args:
            coefficient: 幅度校验系数
            
        Returns:
            Dict: 验证结果
        """
        issues = []
        
        # 检查系数范围
        if coefficient < self.min_amplitude_coefficient:
            issues.append(f"系数过小({coefficient:.3f} < {self.min_amplitude_coefficient})")
        
        if coefficient > self.max_amplitude_coefficient:
            issues.append(f"系数过大({coefficient:.3f} > {self.max_amplitude_coefficient})")
        
        # 检查系数为负（价格下跌）
        if coefficient < 0:
            issues.append("系数为负，价格整体下跌")
        
        # 检查系数为零（无变化）
        if abs(coefficient) < 0.001:
            issues.append("系数接近零，价格变化微小")
        
        # 判断整体有效性
        is_valid = len(issues) == 0
        
        # 确定状态
        if is_valid:
            status = "valid"
        elif coefficient < 0:
            status = "negative"
        elif coefficient < self.min_amplitude_coefficient:
            status = "insufficient"
        elif coefficient > self.max_amplitude_coefficient:
            status = "excessive"
        else:
            status = "invalid"
        
        return {
            'is_valid': is_valid,
            'status': status,
            'issues': issues,
            'coefficient': coefficient
        }
    
    def _analyze_coefficient_quality(self, coefficient: float) -> Dict:
        """分析系数质量
        
        Args:
            coefficient: 幅度校验系数
            
        Returns:
            Dict: 系数质量分析结果
        """
        # 质量等级划分
        if coefficient < 0:
            quality_level = "negative"
            quality_score = 0.0
        elif coefficient < 0.005:
            quality_level = "very_low"
            quality_score = 0.1
        elif coefficient < 0.01:
            quality_level = "low"
            quality_score = 0.3
        elif coefficient < 0.03:
            quality_level = "moderate"
            quality_score = 0.5
        elif coefficient < 0.08:
            quality_level = "good"
            quality_score = 0.7
        elif coefficient < 0.15:
            quality_level = "high"
            quality_score = 0.9
        elif coefficient <= 0.30:
            quality_level = "excellent"
            quality_score = 1.0
        else:
            quality_level = "excessive"
            quality_score = 0.6  # 过度波动降低质量
        
        # 判断是否为理想范围
        ideal_range = 0.02 <= coefficient <= 0.12  # 2%-12%为理想范围
        
        # 判断趋势强度
        if coefficient >= 0.05:
            trend_strength = "strong"
        elif coefficient >= 0.02:
            trend_strength = "moderate"
        elif coefficient >= 0.01:
            trend_strength = "weak"
        else:
            trend_strength = "very_weak"
        
        return {
            'quality_level': quality_level,
            'quality_score': quality_score,
            'coefficient': coefficient,
            'ideal_range': ideal_range,
            'trend_strength': trend_strength,
            'percentage': coefficient * 100
        }
    
    def _assess_waiting_necessity(self, coefficient: float, validation_result: Dict, 
                                coefficient_quality: Dict) -> Dict:
        """评估等待必要性
        
        Args:
            coefficient: 幅度校验系数
            validation_result: 验证结果
            coefficient_quality: 系数质量
            
        Returns:
            Dict: 等待评估结果
        """
        should_wait = False
        reasons = []
        wait_type = "none"
        
        # 系数为负需要等待转正（优先级最高）
        if coefficient < 0:
            should_wait = True
            reasons.append("价格整体下跌，等待趋势转正")
            wait_type = "trend_reversal"
        
        # 系数过小需要等待
        elif coefficient < self.min_amplitude_coefficient:
            should_wait = True
            reasons.append("幅度系数过小，等待波幅显著放大")
            wait_type = "amplitude_expansion"
        
        # 系数过大需要等待回调
        elif coefficient > self.max_amplitude_coefficient:
            should_wait = True
            reasons.append("幅度系数过大，等待适度回调")
            wait_type = "amplitude_moderation"
        
        # 质量过低需要等待改善
        elif coefficient_quality['quality_score'] < 0.3:
            should_wait = True
            reasons.append("系数质量过低，等待质量改善")
            wait_type = "quality_improvement"
        
        # 计算等待优先级
        if should_wait:
            if coefficient < 0:
                priority = "high"  # 负系数优先级最高
            elif coefficient < 0.005:
                priority = "high"  # 极小系数优先级高
            elif coefficient > 0.20:
                priority = "medium"  # 过大系数优先级中等
            else:
                priority = "low"  # 其他情况优先级低
        else:
            priority = "none"
        
        return {
            'should_wait': should_wait,
            'wait_type': wait_type,
            'priority': priority,
            'reasons': reasons,
            'reason': '; '.join(reasons) if reasons else "系数有效，无需等待"
        }
    
    def _calculate_amplitude_significance(self, coefficient: float) -> Dict:
        """计算波幅显著性
        
        Args:
            coefficient: 幅度校验系数
            
        Returns:
            Dict: 波幅显著性分析结果
        """
        # 显著性等级
        if abs(coefficient) < 0.005:
            significance_level = "negligible"  # 可忽略
            significance_score = 0.1
        elif abs(coefficient) < 0.01:
            significance_level = "minimal"  # 最小
            significance_score = 0.2
        elif abs(coefficient) < 0.02:
            significance_level = "low"  # 低
            significance_score = 0.4
        elif abs(coefficient) < 0.05:
            significance_level = "moderate"  # 中等
            significance_score = 0.6
        elif abs(coefficient) < 0.10:
            significance_level = "high"  # 高
            significance_score = 0.8
        else:
            significance_level = "very_high"  # 很高
            significance_score = 1.0
        
        # 判断是否显著
        is_significant = abs(coefficient) >= 0.01  # 1%以上认为显著
        
        # 判断方向
        if coefficient > 0:
            direction = "positive"
        elif coefficient < 0:
            direction = "negative"
        else:
            direction = "neutral"
        
        return {
            'significance_level': significance_level,
            'significance_score': significance_score,
            'is_significant': is_significant,
            'direction': direction,
            'absolute_value': abs(coefficient),
            'percentage': abs(coefficient) * 100
        }
    
    def _evaluate_entry_readiness(self, validation_result: Dict, coefficient_quality: Dict, 
                                waiting_assessment: Dict) -> Dict:
        """评估入场准备度
        
        Args:
            validation_result: 验证结果
            coefficient_quality: 系数质量
            waiting_assessment: 等待评估
            
        Returns:
            Dict: 入场准备度评估结果
        """
        # 基础准备度评分
        readiness_score = 0.0
        
        # 验证有效性 (40%)
        if validation_result['is_valid']:
            readiness_score += 0.4
        
        # 系数质量 (35%)
        readiness_score += coefficient_quality['quality_score'] * 0.35
        
        # 等待评估 (25%)
        if not waiting_assessment['should_wait']:
            readiness_score += 0.25
        elif waiting_assessment['priority'] == 'low':
            readiness_score += 0.15  # 低优先级等待仍有部分分数
        
        # 确定准备度等级
        if readiness_score >= 0.8:
            readiness_level = "excellent"
        elif readiness_score >= 0.6:
            readiness_level = "good"
        elif readiness_score >= 0.4:
            readiness_level = "moderate"
        elif readiness_score >= 0.2:
            readiness_level = "poor"
        else:
            readiness_level = "very_poor"
        
        # 判断是否可以入场
        ready_for_entry = (
            validation_result['is_valid'] and 
            not waiting_assessment['should_wait'] and 
            coefficient_quality['quality_score'] >= 0.3
        )
        
        return {
            'readiness_score': readiness_score,
            'readiness_level': readiness_level,
            'ready_for_entry': ready_for_entry,
            'recommendation': self._get_entry_recommendation(
                readiness_level, ready_for_entry, waiting_assessment
            )
        }
    
    def _get_entry_recommendation(self, readiness_level: str, ready_for_entry: bool, 
                                waiting_assessment: Dict) -> str:
        """获取入场建议
        
        Args:
            readiness_level: 准备度等级
            ready_for_entry: 是否可以入场
            waiting_assessment: 等待评估
            
        Returns:
            str: 入场建议
        """
        if ready_for_entry:
            if readiness_level == "excellent":
                return "幅度系数优秀，强烈建议入场"
            elif readiness_level == "good":
                return "幅度系数良好，建议入场"
            else:
                return "幅度系数合格，可以入场"
        
        else:
            if waiting_assessment['should_wait']:
                return f"建议等待：{waiting_assessment['reason']}"
            else:
                return f"准备度{readiness_level}，建议观察"
    
    def optimize_entry_timing_comprehensive(self, data: List[MarketData], 
                                          indicators: PVFRSIndicators) -> Dict:
        """综合优化入场时机
        
        整合价格穿越、成交量突破和幅度校验的综合分析。
        
        Args:
            data: 市场数据列表
            indicators: PVFRS指标
            
        Returns:
            Dict: 综合入场时机优化结果
            
        Raises:
            DataInsufficientException: 数据不足时抛出
            CalculationException: 计算异常时抛出
        """
        if len(data) < 2:
            raise DataInsufficientException("综合入场时机优化需要至少2天数据")
        
        try:
            # 价格穿越监控
            price_analysis = self.monitor_price_breakthrough(data, indicators.avg_price_20d)
            
            # 增强：价格位置评分
            price_position_score = self._calculate_price_position_score(data, indicators.avg_price_20d)
            price_analysis['position_score'] = price_position_score
            
            # 成交量突破确认
            volume_analysis = self.confirm_volume_breakthrough(data[-1], indicators.avg_volume_20d)
            
            # 增强：成交量突破强度分析（检查最近3天）
            volume_breakthrough_strength = self._analyze_volume_breakthrough_strength(data, indicators.avg_volume_20d)
            volume_analysis['breakthrough_strength'] = volume_breakthrough_strength
            
            # 幅度校验系数计算
            amplitude_analysis = self.calculate_amplitude_coefficient(
                indicators.macro_displacement, indicators.avg_price_20d
            )
            
            # 综合评估（优化权重：价格位置40% + 成交量突破40% + 幅度系数20%）
            comprehensive_score = self._calculate_comprehensive_score_enhanced(
                price_analysis, volume_analysis, amplitude_analysis, 
                price_position_score, volume_breakthrough_strength
            )
            
            # 生成综合建议
            comprehensive_recommendation = self._generate_comprehensive_recommendation(
                price_analysis, volume_analysis, amplitude_analysis, comprehensive_score
            )
            
            return {
                'price_analysis': price_analysis,
                'volume_analysis': volume_analysis,
                'amplitude_analysis': amplitude_analysis,
                'price_position_score': price_position_score,
                'volume_breakthrough_strength': volume_breakthrough_strength,
                'comprehensive_score': comprehensive_score,
                'optimal_entry_timing': comprehensive_score > 0.7,
                'good_entry_timing': comprehensive_score > 0.5,
                'recommendation': comprehensive_recommendation,
                'timing_summary': self._create_timing_summary(
                    price_analysis, volume_analysis, amplitude_analysis
                )
            }
            
        except Exception as e:
            raise CalculationException(f"综合入场时机优化失败: {str(e)}")
    
    def _calculate_price_position_score(self, data: List[MarketData], avg_price_20d: float) -> float:
        """计算价格位置评分（增强版）
        
        当前价格在20天价格区间中的位置评分
        评分标准：
        - 价格在区间上半部分（50%-100%）：高分
        - 价格在区间下半部分（0%-50%）：低分
        
        Args:
            data: 市场数据列表
            avg_price_20d: 20日平均价格
            
        Returns:
            float: 价格位置评分 (0-1)
        """
        try:
            if len(data) < 20:
                return 0.5  # 数据不足，返回中等评分
            
            recent_data = data[-20:]
            prices = [day.close for day in recent_data]
            
            min_price = min(prices)
            max_price = max(prices)
            current_price = prices[-1]
            
            if max_price == min_price:
                return 0.5  # 价格无波动，返回中等评分
            
            # 计算当前价格在区间中的位置（0-1）
            position_ratio = (current_price - min_price) / (max_price - min_price)
            
            # 计算相对于平均价格的位置
            if avg_price_20d > 0:
                relative_to_avg = (current_price - avg_price_20d) / avg_price_20d
            else:
                relative_to_avg = 0.0
            
            # 综合评分：位置占比60% + 相对平均价格40%
            position_score = position_ratio * 0.6 + max(0, min(1, (relative_to_avg + 0.1) * 5)) * 0.4
            
            return max(0.0, min(1.0, position_score))
            
        except Exception as e:
            raise CalculationException(f"价格位置评分计算失败: {str(e)}")
    
    def _analyze_volume_breakthrough_strength(self, data: List[MarketData], avg_volume_20d: float) -> Dict:
        """分析成交量突破强度（增强版：检查最近3天）
        
        分析突破幅度和持续性
        
        Args:
            data: 市场数据列表
            avg_volume_20d: 20日平均成交量
            
        Returns:
            Dict: 突破强度分析结果
        """
        try:
            if len(data) < 3:
                return {
                    'strength': 0.0,
                    'breakthrough_magnitude': 0.0,
                    'persistence_days': 0,
                    'is_strong': False
                }
            
            recent_data = data[-3:]
            volumes = [day.volume for day in recent_data]
            
            # 计算突破幅度（最近3天平均成交量/20日均量）
            avg_recent_volume = sum(volumes) / len(volumes)
            breakthrough_magnitude = avg_recent_volume / avg_volume_20d if avg_volume_20d > 0 else 0.0
            
            # 计算持续性（连续放量天数）
            persistence_days = sum(1 for vol in volumes if vol > avg_volume_20d)
            
            # 计算强度评分
            strength = 0.0
            if breakthrough_magnitude >= 2.0:
                strength += 0.5  # 突破幅度大
            elif breakthrough_magnitude >= 1.5:
                strength += 0.3
            elif breakthrough_magnitude >= 1.2:
                strength += 0.1
            
            if persistence_days >= 3:
                strength += 0.5  # 持续性强
            elif persistence_days >= 2:
                strength += 0.3
            elif persistence_days >= 1:
                strength += 0.1
            
            is_strong = strength >= 0.7
            
            return {
                'strength': min(1.0, strength),
                'breakthrough_magnitude': breakthrough_magnitude,
                'persistence_days': persistence_days,
                'is_strong': is_strong
            }
            
        except Exception as e:
            raise CalculationException(f"成交量突破强度分析失败: {str(e)}")
    
    def _calculate_comprehensive_score_enhanced(self, price_analysis: Dict, volume_analysis: Dict, 
                                               amplitude_analysis: Dict, price_position_score: float,
                                               volume_breakthrough_strength: Dict) -> float:
        """计算综合评分（增强版：价格位置40% + 成交量突破40% + 幅度系数20%）
        
        Args:
            price_analysis: 价格分析结果
            volume_analysis: 成交量分析结果
            amplitude_analysis: 幅度分析结果
            price_position_score: 价格位置评分
            volume_breakthrough_strength: 成交量突破强度
            
        Returns:
            float: 综合评分 (0-1)
        """
        score = 0.0
        
        # 价格位置贡献 (40%)
        score += price_position_score * 0.4
        
        # 成交量突破贡献 (40%)
        volume_strength = volume_breakthrough_strength.get('strength', 0.0)
        if volume_analysis.get('has_breakthrough', False):
            volume_strength = max(volume_strength, 0.5)  # 至少0.5分
        score += volume_strength * 0.4
        
        # 幅度系数贡献 (20%)
        if amplitude_analysis.get('is_valid', False):
            readiness_score = amplitude_analysis.get('entry_readiness', {}).get('readiness_score', 0.0)
            score += readiness_score * 0.20
        
        return min(1.0, score)
    
    def _generate_comprehensive_recommendation(self, price_analysis: Dict, volume_analysis: Dict, 
                                            amplitude_analysis: Dict, comprehensive_score: float) -> str:
        """生成综合建议
        
        Args:
            price_analysis: 价格分析结果
            volume_analysis: 成交量分析结果
            amplitude_analysis: 幅度分析结果
            comprehensive_score: 综合评分
            
        Returns:
            str: 综合建议
        """
        if comprehensive_score > 0.8:
            return "三维条件优秀，强烈建议立即入场"
        elif comprehensive_score > 0.6:
            return "三维条件良好，建议入场"
        elif comprehensive_score > 0.4:
            return "三维条件一般，谨慎入场"
        else:
            # 分析主要问题
            issues = []
            
            if not price_analysis['has_breakthrough']:
                issues.append("价格未穿越")
            if not volume_analysis['has_breakthrough']:
                issues.append("成交量未突破")
            if not amplitude_analysis['is_valid']:
                issues.append("幅度系数无效")
            
            if issues:
                return f"不建议入场：{', '.join(issues)}"
            else:
                return "条件不够理想，建议等待更好时机"
    
    def _create_timing_summary(self, price_analysis: Dict, volume_analysis: Dict, 
                             amplitude_analysis: Dict) -> Dict:
        """创建时机总结
        
        Args:
            price_analysis: 价格分析结果
            volume_analysis: 成交量分析结果
            amplitude_analysis: 幅度分析结果
            
        Returns:
            Dict: 时机总结
        """
        return {
            'price_status': price_analysis['monitoring_status'],
            'volume_status': volume_analysis['confirmation_status'],
            'amplitude_status': amplitude_analysis['entry_readiness']['recommendation'],
            'key_conditions': {
                'price_breakthrough': price_analysis['has_breakthrough'],
                'volume_breakthrough': volume_analysis['has_breakthrough'],
                'amplitude_valid': amplitude_analysis['is_valid']
            },
            'waiting_required': amplitude_analysis['should_wait'],
            'wait_reason': amplitude_analysis['wait_reason'] if amplitude_analysis['should_wait'] else None
        }