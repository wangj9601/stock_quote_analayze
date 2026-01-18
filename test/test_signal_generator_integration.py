"""
信号生成器与入场时机优化器集成测试
"""

import pytest
from datetime import datetime, timedelta
from backend_core.strategies.pvfrs.signal_generator import SignalGenerator
from backend_core.strategies.pvfrs.models import MarketData, PVFRSIndicators, SignalType


class TestSignalGeneratorIntegration:
    """信号生成器集成测试类"""
    
    def setup_method(self):
        """测试前设置"""
        self.signal_generator = SignalGenerator()
        
        # 创建测试数据
        self.base_date = datetime(2024, 1, 1)
        self.test_data = self._create_test_market_data()
        self.test_indicators = self._create_test_indicators()
    
    def _create_test_market_data(self):
        """创建测试市场数据"""
        data = []
        
        # 创建价格穿越场景：前一天低于平均价格，当天高于平均价格
        data.append(MarketData(
            symbol='TEST001',
            date='2024-01-01',
            open=9.8,
            high=10.0,
            low=9.7,
            close=9.9,  # 低于平均价格10.0
            volume=1000000,
            amount=9900000
        ))
        
        data.append(MarketData(
            symbol='TEST001',
            date='2024-01-02',
            open=10.1,
            high=10.3,
            low=10.0,
            close=10.2,  # 高于平均价格10.0，发生穿越
            volume=1300000,  # 成交量突破
            amount=13260000
        ))
        
        return data
    
    def _create_test_indicators(self):
        """创建测试PVFRS指标"""
        return PVFRSIndicators(
            macro_displacement=0.3,  # 3%的宏观位移
            instant_deviation=0.2,   # 即时强度为正
            avg_price_20d=10.0,      # 平均价格
            rising_days=12,
            falling_days=7,
            frequency_advantage=True,
            avg_volume_20d=1000000,  # 平均成交量
            current_volume=1300000,  # 当前成交量突破
            efficiency_ratio=1.3,
            amplitude_ratio=0.03,    # 3%的幅度系数
            resonance_strength=0.8
        )
    
    def test_optimize_entry_timing_with_optimal_conditions(self):
        """测试最佳条件下的入场时机优化"""
        # 创建基础信号
        base_signal = self.signal_generator.generate_buy_signal(
            symbol='TEST001',
            date='2024-01-02',
            price=10.2,
            indicators=self.test_indicators,
            conditions_met={
                'macro_displacement_positive': True,
                'instant_strength_positive': True,
                'frequency_advantage': True,
                'volume_efficiency': True,
                'volume_price_resonance': True,
                'strong_fund_support': True
            }
        )
        
        # 优化入场时机
        optimized_signal = self.signal_generator.optimize_entry_timing(
            self.test_data, base_signal
        )
        
        # 验证优化结果
        assert optimized_signal is not None
        assert optimized_signal.strength >= base_signal.strength  # 强度应该提升或保持
        assert 'entry_timing_optimized' in optimized_signal.conditions_met or \
               'entry_timing_good' in optimized_signal.conditions_met
        assert optimized_signal.signal_type == SignalType.BUY
    
    def test_optimize_entry_timing_with_poor_conditions(self):
        """测试较差条件下的入场时机优化"""
        # 创建较差的指标
        poor_indicators = PVFRSIndicators(
            macro_displacement=-0.1,  # 负宏观位移
            instant_deviation=-0.05,
            avg_price_20d=10.0,
            rising_days=8,
            falling_days=11,
            frequency_advantage=False,
            avg_volume_20d=1000000,
            current_volume=800000,   # 成交量不足
            efficiency_ratio=0.8,
            amplitude_ratio=-0.01,   # 负幅度系数
            resonance_strength=0.3
        )
        
        # 创建基础信号
        base_signal = self.signal_generator.generate_buy_signal(
            symbol='TEST001',
            date='2024-01-02',
            price=10.2,
            indicators=poor_indicators,
            conditions_met={
                'macro_displacement_positive': False,
                'instant_strength_positive': False,
                'frequency_advantage': False,
                'volume_efficiency': False
            }
        )
        
        # 优化入场时机
        optimized_signal = self.signal_generator.optimize_entry_timing(
            self.test_data, base_signal
        )
        
        # 验证优化结果
        assert optimized_signal is not None  # 应该返回信号，但可能质量较低
        
        # 检查是否有等待建议或时机不佳的标记
        conditions = optimized_signal.conditions_met
        
        # 在较差条件下，应该有相应的标记
        if conditions.get('entry_timing_suboptimal') or conditions.get('wait_recommended'):
            # 如果标记为次优时机，强度应该被降低
            assert optimized_signal.strength <= base_signal.strength * 1.1  # 允许小幅提升
        else:
            # 如果没有次优标记，说明某些条件仍然良好，允许适度提升
            assert optimized_signal.strength >= base_signal.strength
    
    def test_get_entry_timing_analysis(self):
        """测试入场时机分析功能"""
        analysis = self.signal_generator.get_entry_timing_analysis(
            self.test_data, self.test_indicators
        )
        
        assert analysis['analysis_available'] is True
        assert 'price_breakthrough' in analysis
        assert 'volume_breakthrough' in analysis
        assert 'amplitude_validation' in analysis
        assert 'comprehensive_assessment' in analysis
        assert 'timing_summary' in analysis
        
        # 验证分析结果结构
        price_analysis = analysis['price_breakthrough']
        assert 'detected' in price_analysis
        assert 'strength' in price_analysis
        assert 'status' in price_analysis
        
        volume_analysis = analysis['volume_breakthrough']
        assert 'detected' in volume_analysis
        assert 'timing_score' in volume_analysis
        assert 'status' in volume_analysis
        
        amplitude_analysis = analysis['amplitude_validation']
        assert 'valid' in amplitude_analysis
        assert 'coefficient' in amplitude_analysis
        assert 'should_wait' in amplitude_analysis
        assert 'recommendation' in amplitude_analysis
        
        comprehensive = analysis['comprehensive_assessment']
        assert 'score' in comprehensive
        assert 'optimal_timing' in comprehensive
        assert 'good_timing' in comprehensive
        assert 'recommendation' in comprehensive
    
    def test_entry_timing_analysis_insufficient_data(self):
        """测试数据不足时的入场时机分析"""
        # 只提供一天数据
        insufficient_data = [self.test_data[0]]
        
        analysis = self.signal_generator.get_entry_timing_analysis(
            insufficient_data, self.test_indicators
        )
        
        assert analysis['analysis_available'] is False
        assert 'reason' in analysis
        assert '数据不足' in analysis['reason']
    
    def test_signal_strength_enhancement(self):
        """测试信号强度提升机制"""
        # 创建中等强度的基础信号
        base_signal = self.signal_generator.generate_buy_signal(
            symbol='TEST001',
            date='2024-01-02',
            price=10.2,
            indicators=self.test_indicators,
            conditions_met={
                'macro_displacement_positive': True,
                'frequency_advantage': True,
                'volume_efficiency': True
            }
        )
        
        original_strength = base_signal.strength
        
        # 优化入场时机
        optimized_signal = self.signal_generator.optimize_entry_timing(
            self.test_data, base_signal
        )
        
        # 在良好条件下，信号强度应该得到提升
        if optimized_signal and optimized_signal.conditions_met.get('entry_timing_optimized'):
            assert optimized_signal.strength > original_strength
            # 提升幅度应该在合理范围内
            enhancement_ratio = optimized_signal.strength / original_strength
            assert 1.0 < enhancement_ratio <= 1.15  # 最多提升15%
    
    def test_comprehensive_conditions_tracking(self):
        """测试综合条件跟踪"""
        base_signal = self.signal_generator.generate_buy_signal(
            symbol='TEST001',
            date='2024-01-02',
            price=10.2,
            indicators=self.test_indicators,
            conditions_met={
                'macro_displacement_positive': True,
                'instant_strength_positive': True,
                'frequency_advantage': True,
                'volume_efficiency': True,
                'volume_price_resonance': True
            }
        )
        
        optimized_signal = self.signal_generator.optimize_entry_timing(
            self.test_data, base_signal
        )
        
        # 验证条件跟踪
        if optimized_signal:
            conditions = optimized_signal.conditions_met
            
            # 应该包含原始条件
            assert conditions.get('macro_displacement_positive') is True
            assert conditions.get('frequency_advantage') is True
            
            # 应该包含优化相关的条件
            if conditions.get('entry_timing_optimized'):
                assert 'price_breakthrough' in conditions
                assert 'volume_breakthrough' in conditions
                assert 'amplitude_validation' in conditions
                assert 'comprehensive_score' in conditions
                assert 'timing_recommendation' in conditions


if __name__ == '__main__':
    pytest.main([__file__])