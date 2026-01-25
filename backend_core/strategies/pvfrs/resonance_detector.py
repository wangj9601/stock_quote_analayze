"""
PVFRS策略三维共振检测器实现
负责整合价格、频率、成交量三个维度的分析结果，实现高效率演化轨道确认
"""

from typing import Dict, List
from .models import MarketData, CalculationException
from .interfaces import IResonanceDetector


class ResonanceDetector(IResonanceDetector):
    """三维共振检测器
    
    负责整合价格、频率、成交量三个维度的分析结果：
    - 综合判定三维条件是否同时满足
    - 确认进入高效率演化轨道
    - 计算共振强度
    """
    
    def __init__(self):
        """初始化三维共振检测器"""
        self.dimension_weights = {
            'price': 0.4,      # 价格维度权重
            'frequency': 0.3,  # 频率维度权重
            'volume': 0.3      # 成交量维度权重
        }
    
    def detect_resonance(self, price_indicators: Dict, frequency_indicators: Dict, 
                        volume_indicators: Dict) -> Dict:
        """检测三维共振状态
        
        整合价格、频率、成交量三个维度的分析结果，判定是否进入高效率演化轨道。
        
        Args:
            price_indicators: 价格维度分析结果
            frequency_indicators: 频率维度分析结果  
            volume_indicators: 成交量维度分析结果
            
        Returns:
            Dict: 包含共振检测结果的字典
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            # 获取各维度的条件满足情况
            price_valid = price_indicators.get('price_dimension_valid', False)
            frequency_valid = frequency_indicators.get('frequency_dimension_valid', False)
            volume_valid = volume_indicators.get('volume_dimension_valid', False)
            
            # 记录满足的具体条件
            conditions_met = self._analyze_detailed_conditions(
                price_indicators, frequency_indicators, volume_indicators
            )
            
            # 三维共振判定：所有维度条件都必须满足
            three_dimension_resonance = price_valid and frequency_valid and volume_valid
            
            # 计算共振强度
            resonance_strength = self.calculate_resonance_strength(conditions_met)
            
            # 确认高效率演化轨道
            high_efficiency_trajectory = self._confirm_high_efficiency_trajectory(
                three_dimension_resonance, resonance_strength, conditions_met
            )
            
            return {
                'price_dimension_valid': price_valid,
                'frequency_dimension_valid': frequency_valid,
                'volume_dimension_valid': volume_valid,
                'three_dimension_resonance': three_dimension_resonance,
                'high_efficiency_trajectory': high_efficiency_trajectory,
                'resonance_strength': resonance_strength,
                'conditions_met': conditions_met,
                'dimension_scores': {
                    'price_score': self._calculate_dimension_score(price_indicators, 'price'),
                    'frequency_score': self._calculate_dimension_score(frequency_indicators, 'frequency'),
                    'volume_score': self._calculate_dimension_score(volume_indicators, 'volume')
                }
            }
            
        except Exception as e:
            raise CalculationException(f"三维共振检测失败: {str(e)}")
    
    def calculate_resonance_strength(self, conditions_met: Dict[str, bool]) -> float:
        """计算共振强度
        
        基于满足的条件数量和重要性计算共振强度，范围为0-1。
        
        Args:
            conditions_met: 满足的条件字典
            
        Returns:
            float: 共振强度 (0-1)
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            # 定义各条件的权重（优化版：提高量价共振和频率优势权重）
            condition_weights = {
                # 价格维度条件
                'macro_displacement_positive': 0.14,  # 宏观位移为正（从0.15降低）
                'instant_strength_positive': 0.14,   # 即时强度为正（从0.15降低）
                'price_above_average': 0.10,         # 价格高于平均
                
                # 频率维度条件
                'frequency_advantage': 0.15,         # 频率优势（从0.12提高到0.15）
                'continuous_buying_support': 0.10,   # 持续买盘支撑
                'no_false_prosperity': 0.08,         # 无虚假繁荣
                
                # 成交量维度条件
                'volume_efficiency': 0.10,           # 成交量效率
                'volume_price_resonance': 0.15,      # 量价共振（从0.12提高到0.15）
                'strong_fund_support': 0.04          # 强劲资金支撑（从0.08降低，因为已有连续放量验证）
            }
            
            # 计算加权得分
            total_weight = 0.0
            achieved_weight = 0.0
            
            for condition, weight in condition_weights.items():
                total_weight += weight
                if conditions_met.get(condition, False):
                    achieved_weight += weight
            
            # 计算共振强度
            if total_weight > 0:
                resonance_strength = achieved_weight / total_weight
            else:
                resonance_strength = 0.0
            
            # 确保结果在0-1范围内
            resonance_strength = max(0.0, min(1.0, resonance_strength))
            
            return resonance_strength
            
        except Exception as e:
            raise CalculationException(f"共振强度计算失败: {str(e)}")
    
    def _analyze_detailed_conditions(self, price_indicators: Dict, 
                                   frequency_indicators: Dict, 
                                   volume_indicators: Dict) -> Dict[str, bool]:
        """分析详细的条件满足情况
        
        Args:
            price_indicators: 价格维度指标
            frequency_indicators: 频率维度指标
            volume_indicators: 成交量维度指标
            
        Returns:
            Dict[str, bool]: 详细的条件满足情况
        """
        conditions_met = {}
        
        # 价格维度条件
        conditions_met['macro_displacement_positive'] = (
            price_indicators.get('macro_displacement', 0) > 0
        )
        conditions_met['instant_strength_positive'] = (
            price_indicators.get('instant_deviation', 0) > 0
        )
        conditions_met['price_above_average'] = (
            price_indicators.get('instant_deviation', 0) > 0
        )
        
        # 频率维度条件
        rising_days = frequency_indicators.get('rising_days', 0)
        falling_days = frequency_indicators.get('falling_days', 0)
        conditions_met['frequency_advantage'] = rising_days > falling_days
        conditions_met['continuous_buying_support'] = rising_days >= 10  # 20天中至少10天上涨
        conditions_met['no_false_prosperity'] = not frequency_indicators.get('has_false_prosperity', True)
        
        # 成交量维度条件
        current_volume = volume_indicators.get('current_volume', 0)
        avg_volume = volume_indicators.get('avg_volume_20d', 1)
        conditions_met['volume_efficiency'] = current_volume > avg_volume
        conditions_met['volume_price_resonance'] = volume_indicators.get('volume_price_resonance', False)
        conditions_met['strong_fund_support'] = volume_indicators.get('strong_fund_support', False)
        
        # 乖离率条件（新增）
        bias = price_indicators.get('bias', 0.0)
        bias_trend = price_indicators.get('bias_trend', {})
        conditions_met['bias'] = bias  # 保存bias值供后续使用
        conditions_met['bias_reasonable'] = 0.005 <= bias <= 0.08  # bias在合理范围（0.5%-8%）
        if isinstance(bias_trend, dict):
            conditions_met['bias_trend_favorable'] = (
                bias_trend.get('trend_5d', 'stable') in ['expanding', 'stable'] and
                not bias_trend.get('is_converging', False)
            )
        else:
            conditions_met['bias_trend_favorable'] = True
        
        return conditions_met
    
    def _confirm_high_efficiency_trajectory(self, three_dimension_resonance: bool, 
                                          resonance_strength: float, 
                                          conditions_met: Dict[str, bool]) -> bool:
        """确认高效率演化轨道
        
        高效率演化轨道的确认标准：
        1. 三维共振条件必须满足
        2. 共振强度达到一定阈值
        3. 关键条件必须满足
        
        Args:
            three_dimension_resonance: 三维共振是否满足
            resonance_strength: 共振强度
            conditions_met: 满足的条件
            
        Returns:
            bool: 是否确认进入高效率演化轨道
        """
        # 基础条件：三维共振必须满足
        if not three_dimension_resonance:
            return False
        
        # 共振强度阈值：至少达到0.7
        min_resonance_strength = 0.7
        if resonance_strength < min_resonance_strength:
            return False
        
        # 关键条件检查：核心条件必须满足
        critical_conditions = [
            'macro_displacement_positive',  # 价格整体上涨
            'frequency_advantage',          # 频率优势
            'volume_efficiency',            # 成交量效率
            'volume_price_resonance'        # 量价共振（新增）
        ]
        
        for condition in critical_conditions:
            if not conditions_met.get(condition, False):
                return False
        
        # 维度均衡性检查（新增）
        dimension_scores = self._calculate_dimension_scores_from_conditions(conditions_met)
        if not self._check_dimension_balance(dimension_scores):
            return False
        
        return True
    
    def _calculate_dimension_scores_from_conditions(self, conditions_met: Dict[str, bool]) -> Dict[str, float]:
        """从条件计算各维度得分
        
        Args:
            conditions_met: 满足的条件
            
        Returns:
            Dict: 各维度得分
        """
        price_score = 0.0
        if conditions_met.get('macro_displacement_positive', False):
            price_score += 0.5
        if conditions_met.get('instant_strength_positive', False):
            price_score += 0.5
        
        frequency_score = 0.0
        if conditions_met.get('frequency_advantage', False):
            frequency_score += 0.4
        if conditions_met.get('continuous_buying_support', False):
            frequency_score += 0.3
        if conditions_met.get('no_false_prosperity', False):
            frequency_score += 0.3
        
        volume_score = 0.0
        if conditions_met.get('volume_efficiency', False):
            volume_score += 0.3
        if conditions_met.get('volume_price_resonance', False):
            volume_score += 0.4
        if conditions_met.get('strong_fund_support', False):
            volume_score += 0.3
        
        return {
            'price': price_score,
            'frequency': frequency_score,
            'volume': volume_score
        }
    
    def _check_dimension_balance(self, dimension_scores: Dict[str, float]) -> bool:
        """检查维度均衡性
        
        验证内容：
        1. 各维度得分差异<0.3（避免单一维度过高）
        2. 最低维度得分>0.5（确保各维度都达标）
        
        Args:
            dimension_scores: 各维度得分
            
        Returns:
            bool: 是否均衡
        """
        scores = list(dimension_scores.values())
        if len(scores) < 3:
            return True
        
        min_score = min(scores)
        max_score = max(scores)
        
        # 最低维度得分>0.5
        if min_score < 0.5:
            return False
        
        # 各维度得分差异<0.3
        if max_score - min_score > 0.3:
            return False
        
        return True
    
    def _calculate_dimension_score(self, indicators: Dict, dimension_type: str) -> float:
        """计算单个维度的得分
        
        Args:
            indicators: 维度指标
            dimension_type: 维度类型 ('price', 'frequency', 'volume')
            
        Returns:
            float: 维度得分 (0-1)
        """
        if dimension_type == 'price':
            return self._calculate_price_dimension_score(indicators)
        elif dimension_type == 'frequency':
            return self._calculate_frequency_dimension_score(indicators)
        elif dimension_type == 'volume':
            return self._calculate_volume_dimension_score(indicators)
        else:
            return 0.0
    
    def _calculate_price_dimension_score(self, indicators: Dict) -> float:
        """计算价格维度得分"""
        score = 0.0
        
        # 宏观位移得分
        macro_displacement = indicators.get('macro_displacement', 0)
        if macro_displacement > 0:
            score += 0.5
        
        # 即时强度得分
        instant_deviation = indicators.get('instant_deviation', 0)
        if instant_deviation > 0:
            score += 0.5
        
        return score
    
    def _calculate_frequency_dimension_score(self, indicators: Dict) -> float:
        """计算频率维度得分"""
        score = 0.0
        
        rising_days = indicators.get('rising_days', 0)
        falling_days = indicators.get('falling_days', 0)
        has_false_prosperity = indicators.get('has_false_prosperity', True)
        
        # 频率优势得分
        if rising_days > falling_days:
            score += 0.4
        
        # 持续买盘支撑得分
        if rising_days >= 10:  # 20天中至少10天上涨
            score += 0.3
        
        # 无虚假繁荣得分
        if not has_false_prosperity:
            score += 0.3
        
        return score
    
    def _calculate_volume_dimension_score(self, indicators: Dict) -> float:
        """计算成交量维度得分"""
        score = 0.0
        
        # 成交量效率得分
        current_volume = indicators.get('current_volume', 0)
        avg_volume = indicators.get('avg_volume_20d', 1)
        if current_volume > avg_volume:
            score += 0.3
        
        # 量价共振得分
        if indicators.get('volume_price_resonance', False):
            score += 0.4
        
        # 强劲资金支撑得分
        if indicators.get('strong_fund_support', False):
            score += 0.3
        
        return score
    
    def validate_input_indicators(self, price_indicators: Dict, 
                                frequency_indicators: Dict, 
                                volume_indicators: Dict) -> bool:
        """验证输入指标的有效性
        
        Args:
            price_indicators: 价格维度指标
            frequency_indicators: 频率维度指标
            volume_indicators: 成交量维度指标
            
        Returns:
            bool: 输入是否有效
            
        Raises:
            CalculationException: 输入无效时抛出
        """
        try:
            # 检查价格维度指标
            required_price_keys = ['macro_displacement', 'instant_deviation', 'avg_price_20d']
            for key in required_price_keys:
                if key not in price_indicators:
                    raise CalculationException(f"价格维度缺少必需指标: {key}")
            
            # 检查频率维度指标
            required_frequency_keys = ['rising_days', 'falling_days', 'frequency_advantage']
            for key in required_frequency_keys:
                if key not in frequency_indicators:
                    raise CalculationException(f"频率维度缺少必需指标: {key}")
            
            # 检查成交量维度指标
            required_volume_keys = ['current_volume', 'avg_volume_20d', 'efficiency_ratio']
            for key in required_volume_keys:
                if key not in volume_indicators:
                    raise CalculationException(f"成交量维度缺少必需指标: {key}")
            
            return True
            
        except Exception as e:
            raise CalculationException(f"输入指标验证失败: {str(e)}")