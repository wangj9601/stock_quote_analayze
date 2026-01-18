"""
PVFRS策略三维共振检测器集成模块
整合价格、频率、成交量三个维度分析器和信号生成器
"""

from typing import Dict, List, Optional
from .models import MarketData, Signal, PVFRSIndicators, CalculationException
from .analyzers import PriceDimensionAnalyzer, FrequencyDimensionAnalyzer, VolumeDimensionAnalyzer
from .resonance_detector import ResonanceDetector
from .signal_generator import SignalGenerator


class ThreeDimensionResonanceEngine:
    """三维共振检测引擎
    
    整合所有维度分析器，实现完整的三维共振检测和信号生成流程。
    """
    
    def __init__(self):
        """初始化三维共振检测引擎"""
        self.price_analyzer = PriceDimensionAnalyzer()
        self.frequency_analyzer = FrequencyDimensionAnalyzer()
        self.volume_analyzer = VolumeDimensionAnalyzer()
        self.resonance_detector = ResonanceDetector()
        self.signal_generator = SignalGenerator()
    
    def analyze_and_generate_signal(self, symbol: str, data: List[MarketData]) -> Optional[Signal]:
        """分析股票数据并生成信号
        
        完整的三维共振分析和信号生成流程：
        1. 分析三个维度的指标
        2. 检测三维共振状态
        3. 应用信号过滤逻辑
        4. 生成买入信号（如果满足条件）
        
        Args:
            symbol: 股票代码
            data: 市场数据列表
            
        Returns:
            Optional[Signal]: 生成的信号，如果不满足条件则返回None
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            if len(data) < 20:
                return None  # 数据不足，无法分析
            
            # 第一步：分析三个维度的指标
            price_indicators = self.price_analyzer.analyze(data)
            frequency_indicators = self.frequency_analyzer.analyze(data)
            volume_indicators = self.volume_analyzer.analyze(data)
            
            # 第二步：应用信号过滤逻辑（严格的条件验证）
            should_generate_signal = self.signal_generator.filter_signals(
                price_indicators, frequency_indicators, volume_indicators
            )
            
            if not should_generate_signal:
                return None  # 不满足过滤条件，不生成信号
            
            # 第三步：检测三维共振状态
            resonance_result = self.resonance_detector.detect_resonance(
                price_indicators, frequency_indicators, volume_indicators
            )
            
            # 第四步：确认高效率演化轨道
            if not resonance_result.get('high_efficiency_trajectory', False):
                return None  # 未确认进入高效率演化轨道
            
            # 第五步：构建PVFRS指标对象
            pvfrs_indicators = self._build_pvfrs_indicators(
                price_indicators, frequency_indicators, volume_indicators, resonance_result
            )
            
            # 第六步：生成买入信号
            current_data = data[-1]
            buy_signal = self.signal_generator.generate_buy_signal(
                symbol=symbol,
                date=current_data.date,
                price=current_data.close,
                indicators=pvfrs_indicators,
                conditions_met=resonance_result['conditions_met']
            )
            
            # 第七步：优化入场时机
            optimized_signal = self.signal_generator.optimize_entry_timing(data, buy_signal)
            
            return optimized_signal
            
        except Exception as e:
            raise CalculationException(f"三维共振分析失败 ({symbol}): {str(e)}")
    
    def get_analysis_details(self, symbol: str, data: List[MarketData]) -> Dict:
        """获取详细的分析结果
        
        返回完整的分析过程和结果，用于调试和分析。
        
        Args:
            symbol: 股票代码
            data: 市场数据列表
            
        Returns:
            Dict: 详细的分析结果
        """
        try:
            if len(data) < 20:
                return {
                    'symbol': symbol,
                    'error': '数据不足，需要至少20天数据',
                    'data_length': len(data)
                }
            
            # 分析三个维度
            price_indicators = self.price_analyzer.analyze(data)
            frequency_indicators = self.frequency_analyzer.analyze(data)
            volume_indicators = self.volume_analyzer.analyze(data)
            
            # 检测共振状态
            resonance_result = self.resonance_detector.detect_resonance(
                price_indicators, frequency_indicators, volume_indicators
            )
            
            # 应用过滤逻辑
            should_generate_signal = self.signal_generator.filter_signals(
                price_indicators, frequency_indicators, volume_indicators
            )
            
            # 获取过滤拒绝原因（如果被拒绝）
            filter_reason = ""
            if not should_generate_signal:
                filter_reason = self.signal_generator.get_filter_rejection_reason(
                    price_indicators, frequency_indicators, volume_indicators
                )
            
            return {
                'symbol': symbol,
                'data_length': len(data),
                'price_indicators': price_indicators,
                'frequency_indicators': frequency_indicators,
                'volume_indicators': volume_indicators,
                'resonance_result': resonance_result,
                'should_generate_signal': should_generate_signal,
                'filter_reason': filter_reason,
                'analysis_date': data[-1].date if data else None
            }
            
        except Exception as e:
            return {
                'symbol': symbol,
                'error': f'分析失败: {str(e)}',
                'data_length': len(data) if data else 0
            }
    
    def batch_analyze_stocks(self, stock_data: Dict[str, List[MarketData]]) -> Dict[str, Dict]:
        """批量分析股票
        
        Args:
            stock_data: 股票数据字典，键为股票代码，值为市场数据列表
            
        Returns:
            Dict[str, Dict]: 分析结果字典
        """
        results = {}
        
        for symbol, data in stock_data.items():
            try:
                # 尝试生成信号
                signal = self.analyze_and_generate_signal(symbol, data)
                
                # 获取详细分析结果
                analysis_details = self.get_analysis_details(symbol, data)
                
                results[symbol] = {
                    'signal': signal,
                    'analysis': analysis_details,
                    'has_signal': signal is not None
                }
                
            except Exception as e:
                results[symbol] = {
                    'signal': None,
                    'analysis': {'error': str(e)},
                    'has_signal': False
                }
        
        return results
    
    def _build_pvfrs_indicators(self, price_indicators: Dict, 
                               frequency_indicators: Dict, 
                               volume_indicators: Dict, 
                               resonance_result: Dict) -> PVFRSIndicators:
        """构建PVFRS指标对象
        
        Args:
            price_indicators: 价格维度指标
            frequency_indicators: 频率维度指标
            volume_indicators: 成交量维度指标
            resonance_result: 共振检测结果
            
        Returns:
            PVFRSIndicators: PVFRS指标对象
        """
        # 计算幅度系数
        macro_displacement = price_indicators.get('macro_displacement', 0)
        avg_price_20d = price_indicators.get('avg_price_20d', 1)
        amplitude_ratio = macro_displacement / avg_price_20d if avg_price_20d > 0 else 0
        
        return PVFRSIndicators(
            # 价格维度指标
            macro_displacement=macro_displacement,
            instant_deviation=price_indicators.get('instant_deviation', 0),
            avg_price_20d=avg_price_20d,
            
            # 频率维度指标
            rising_days=frequency_indicators.get('rising_days', 0),
            falling_days=frequency_indicators.get('falling_days', 0),
            frequency_advantage=frequency_indicators.get('frequency_advantage', False),
            
            # 成交量维度指标
            avg_volume_20d=volume_indicators.get('avg_volume_20d', 0),
            current_volume=volume_indicators.get('current_volume', 0),
            efficiency_ratio=volume_indicators.get('efficiency_ratio', 0),
            
            # 综合指标
            amplitude_ratio=amplitude_ratio,
            resonance_strength=resonance_result.get('resonance_strength', 0)
        )
    
    def get_dimension_summary(self, analysis_results: Dict[str, Dict]) -> Dict:
        """获取维度分析汇总
        
        Args:
            analysis_results: 批量分析结果
            
        Returns:
            Dict: 维度分析汇总统计
        """
        total_stocks = len(analysis_results)
        stocks_with_signals = sum(1 for result in analysis_results.values() if result['has_signal'])
        
        # 统计各维度通过情况
        price_pass = 0
        frequency_pass = 0
        volume_pass = 0
        three_dimension_pass = 0
        
        for result in analysis_results.values():
            analysis = result.get('analysis', {})
            if 'price_indicators' in analysis:
                if analysis['price_indicators'].get('price_dimension_valid', False):
                    price_pass += 1
            if 'frequency_indicators' in analysis:
                if analysis['frequency_indicators'].get('frequency_dimension_valid', False):
                    frequency_pass += 1
            if 'volume_indicators' in analysis:
                if analysis['volume_indicators'].get('volume_dimension_valid', False):
                    volume_pass += 1
            if 'resonance_result' in analysis:
                if analysis['resonance_result'].get('three_dimension_resonance', False):
                    three_dimension_pass += 1
        
        return {
            'total_stocks': total_stocks,
            'stocks_with_signals': stocks_with_signals,
            'signal_rate': stocks_with_signals / total_stocks if total_stocks > 0 else 0,
            'dimension_pass_rates': {
                'price': price_pass / total_stocks if total_stocks > 0 else 0,
                'frequency': frequency_pass / total_stocks if total_stocks > 0 else 0,
                'volume': volume_pass / total_stocks if total_stocks > 0 else 0,
                'three_dimension': three_dimension_pass / total_stocks if total_stocks > 0 else 0
            },
            'dimension_pass_counts': {
                'price': price_pass,
                'frequency': frequency_pass,
                'volume': volume_pass,
                'three_dimension': three_dimension_pass
            }
        }