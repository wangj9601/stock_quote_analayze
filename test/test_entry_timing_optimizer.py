"""
入场时机优化器测试
测试价格穿越监控、成交量突破确认和幅度校验系数计算功能
"""

import pytest
from datetime import datetime, timedelta
from backend_core.strategies.pvfrs.entry_timing_optimizer import EntryTimingOptimizer
from backend_core.strategies.pvfrs.models import MarketData, PVFRSIndicators, CalculationException, DataInsufficientException


class TestEntryTimingOptimizer:
    """入场时机优化器测试类"""
    
    def setup_method(self):
        """测试前设置"""
        self.optimizer = EntryTimingOptimizer()
        
        # 创建测试数据
        self.base_date = datetime(2024, 1, 1)
        self.test_data = self._create_test_market_data()
        self.test_indicators = self._create_test_indicators()
    
    def _create_test_market_data(self):
        """创建测试市场数据"""
        data = []
        base_price = 10.0
        base_volume = 1000000
        
        for i in range(25):  # 25天数据
            date = (self.base_date + timedelta(days=i)).strftime('%Y-%m-%d')
            
            # 模拟价格上涨趋势
            price_factor = 1 + (i * 0.01)  # 每天上涨1%
            close_price = base_price * price_factor
            
            # 模拟成交量变化
            volume_factor = 1 + (i * 0.02)  # 成交量逐渐增加
            volume = int(base_volume * volume_factor)
            
            market_data = MarketData(
                symbol='TEST001',
                date=date,
                open=close_price * 0.99,
                high=close_price * 1.01,
                low=close_price * 0.98,
                close=close_price,
                volume=volume,
                amount=close_price * volume
            )
            data.append(market_data)
        
        return data
    
    def _create_test_indicators(self):
        """创建测试PVFRS指标"""
        return PVFRSIndicators(
            macro_displacement=0.5,  # 5%的宏观位移
            instant_deviation=0.2,
            avg_price_20d=10.0,
            rising_days=12,
            falling_days=7,
            frequency_advantage=True,
            avg_volume_20d=1200000,
            current_volume=1500000,
            efficiency_ratio=1.25,
            amplitude_ratio=0.05,  # 5%的幅度系数
            resonance_strength=0.8
        )
    
    def test_monitor_price_breakthrough_success(self):
        """测试价格穿越监控成功案例"""
        # 创建穿越场景：前一天低于平均价格，当天高于平均价格
        data = [
            MarketData('TEST001', '2024-01-01', 9.8, 10.0, 9.7, 9.9, 1000000, 9900000),  # 低于平均价格
            MarketData('TEST001', '2024-01-02', 10.1, 10.3, 10.0, 10.2, 1200000, 12240000)  # 高于平均价格
        ]
        
        avg_price = 10.0
        result = self.optimizer.monitor_price_breakthrough(data, avg_price)
        
        assert result['has_breakthrough'] is True
        assert result['breakthrough_type'] == 'upward'
        assert result['current_price'] == 10.2
        assert result['avg_price_20d'] == 10.0
        assert result['entry_opportunity'] is True
        assert result['breakthrough_strength'] > 0
    
    def test_monitor_price_breakthrough_no_breakthrough(self):
        """测试价格穿越监控无穿越案例"""
        # 创建无穿越场景：两天都高于平均价格
        data = [
            MarketData('TEST001', '2024-01-01', 10.1, 10.3, 10.0, 10.2, 1000000, 10200000),
            MarketData('TEST001', '2024-01-02', 10.2, 10.4, 10.1, 10.3, 1200000, 12360000)
        ]
        
        avg_price = 10.0
        result = self.optimizer.monitor_price_breakthrough(data, avg_price)
        
        assert result['has_breakthrough'] is False
        assert result['breakthrough_type'] == 'none'
        assert result['entry_opportunity'] is False
    
    def test_monitor_price_breakthrough_insufficient_data(self):
        """测试价格穿越监控数据不足"""
        data = [
            MarketData('TEST001', '2024-01-01', 10.0, 10.2, 9.8, 10.1, 1000000, 10100000)
        ]
        
        with pytest.raises(DataInsufficientException):
            self.optimizer.monitor_price_breakthrough(data, 10.0)
    
    def test_confirm_volume_breakthrough_success(self):
        """测试成交量突破确认成功案例"""
        # 创建成交量突破场景
        current_data = MarketData(
            'TEST001', '2024-01-02', 10.0, 10.2, 9.8, 10.1, 
            1500000, 15150000  # 成交量是平均量的1.5倍
        )
        
        avg_volume = 1000000
        result = self.optimizer.confirm_volume_breakthrough(current_data, avg_volume)
        
        assert result['has_breakthrough'] is True
        assert result['volume_multiplier'] == 1.5
        assert result['breakthrough_level'] == 'moderate'
        assert result['optimal_entry_timing'] is True
        assert result['entry_timing_score'] > 0.6
    
    def test_confirm_volume_breakthrough_strong(self):
        """测试强势成交量突破"""
        current_data = MarketData(
            'TEST001', '2024-01-02', 10.0, 10.2, 9.8, 10.1,
            2500000, 25250000  # 成交量是平均量的2.5倍
        )
        
        avg_volume = 1000000
        result = self.optimizer.confirm_volume_breakthrough(current_data, avg_volume)
        
        assert result['has_breakthrough'] is True
        assert result['volume_multiplier'] == 2.5
        assert result['breakthrough_level'] == 'strong'
        assert result['optimal_entry_timing'] is True
    
    def test_confirm_volume_breakthrough_insufficient(self):
        """测试成交量不足案例"""
        current_data = MarketData(
            'TEST001', '2024-01-02', 10.0, 10.2, 9.8, 10.1,
            800000, 8080000  # 成交量低于平均量
        )
        
        avg_volume = 1000000
        result = self.optimizer.confirm_volume_breakthrough(current_data, avg_volume)
        
        assert result['has_breakthrough'] is False
        assert result['volume_multiplier'] == 0.8
        assert result['breakthrough_level'] == 'insufficient'
        assert result['optimal_entry_timing'] is False
    
    def test_calculate_amplitude_coefficient_valid(self):
        """测试有效幅度校验系数计算"""
        macro_displacement = 0.5  # 价格上涨0.5元
        avg_price = 10.0  # 平均价格10元
        
        result = self.optimizer.calculate_amplitude_coefficient(macro_displacement, avg_price)
        
        assert result['amplitude_coefficient'] == 0.05  # 5%
        assert result['is_valid'] is True
        assert result['validation_status'] == 'valid'
        assert result['should_wait'] is False
        assert result['entry_readiness']['ready_for_entry'] is True
    
    def test_calculate_amplitude_coefficient_too_small(self):
        """测试幅度系数过小"""
        macro_displacement = 0.05  # 价格上涨0.05元
        avg_price = 10.0  # 平均价格10元，系数为0.5%
        
        result = self.optimizer.calculate_amplitude_coefficient(macro_displacement, avg_price)
        
        assert result['amplitude_coefficient'] == 0.005
        assert result['is_valid'] is False
        assert result['validation_status'] == 'insufficient'
        assert result['should_wait'] is True
        assert result['wait_reason'] == '幅度系数过小，等待波幅显著放大'
    
    def test_calculate_amplitude_coefficient_too_large(self):
        """测试幅度系数过大"""
        macro_displacement = 4.0  # 价格上涨4元
        avg_price = 10.0  # 平均价格10元，系数为40%
        
        result = self.optimizer.calculate_amplitude_coefficient(macro_displacement, avg_price)
        
        assert result['amplitude_coefficient'] == 0.4
        assert result['is_valid'] is False
        assert result['validation_status'] == 'excessive'
        assert result['should_wait'] is True
        assert result['wait_reason'] == '幅度系数过大，等待适度回调'
    
    def test_calculate_amplitude_coefficient_negative(self):
        """测试负幅度系数"""
        macro_displacement = -0.5  # 价格下跌0.5元
        avg_price = 10.0
        
        result = self.optimizer.calculate_amplitude_coefficient(macro_displacement, avg_price)
        
        assert result['amplitude_coefficient'] == -0.05
        assert result['is_valid'] is False
        assert result['validation_status'] == 'negative'
        assert result['should_wait'] is True
        assert result['wait_reason'] == '价格整体下跌，等待趋势转正'
    
    def test_optimize_entry_timing_comprehensive_optimal(self):
        """测试综合入场时机优化 - 最佳时机"""
        # 创建理想的价格穿越场景
        data = [
            MarketData('TEST001', '2024-01-01', 10.8, 11.0, 10.7, 10.9, 1100000, 11990000),  # 低于平均价格
            MarketData('TEST001', '2024-01-02', 11.1, 11.3, 11.0, 11.2, 1400000, 15680000)   # 高于平均价格，成交量突破
        ]
        
        # 调整指标为理想状态
        indicators = PVFRSIndicators(
            macro_displacement=0.6,  # 6%宏观位移
            instant_deviation=0.3,
            avg_price_20d=11.0,  # 平均价格11.0，当前价格11.2高于平均价格
            rising_days=15,
            falling_days=4,
            frequency_advantage=True,
            avg_volume_20d=1100000,
            current_volume=1400000,  # 成交量突破
            efficiency_ratio=1.27,
            amplitude_ratio=0.055,  # 5.5%幅度系数
            resonance_strength=0.85
        )
        
        result = self.optimizer.optimize_entry_timing_comprehensive(data, indicators)
        
        assert result['optimal_entry_timing'] is True
        assert result['comprehensive_score'] > 0.7
        assert result['price_analysis']['has_breakthrough'] is True
        assert result['volume_analysis']['has_breakthrough'] is True
        assert result['amplitude_analysis']['is_valid'] is True
    
    def test_optimize_entry_timing_comprehensive_poor(self):
        """测试综合入场时机优化 - 较差时机"""
        # 创建不理想的市场条件
        data = [
            MarketData('TEST001', '2024-01-01', 9.8, 10.0, 9.7, 9.9, 800000, 7920000),
            MarketData('TEST001', '2024-01-02', 9.7, 9.9, 9.6, 9.8, 750000, 7350000)
        ]
        
        indicators = PVFRSIndicators(
            macro_displacement=-0.2,  # 负宏观位移
            instant_deviation=-0.1,
            avg_price_20d=10.0,
            rising_days=8,
            falling_days=11,
            frequency_advantage=False,
            avg_volume_20d=1000000,
            current_volume=750000,  # 成交量不足
            efficiency_ratio=0.75,
            amplitude_ratio=-0.02,  # 负幅度系数
            resonance_strength=0.3
        )
        
        result = self.optimizer.optimize_entry_timing_comprehensive(data, indicators)
        
        assert result['optimal_entry_timing'] is False
        assert result['comprehensive_score'] < 0.4
        assert result['price_analysis']['has_breakthrough'] is False
        assert result['volume_analysis']['has_breakthrough'] is False
        assert result['amplitude_analysis']['is_valid'] is False
    
    def test_amplitude_coefficient_edge_cases(self):
        """测试幅度系数边界情况"""
        # 测试零平均价格
        with pytest.raises(CalculationException):
            self.optimizer.calculate_amplitude_coefficient(0.5, 0.0)
        
        # 测试负平均价格
        with pytest.raises(CalculationException):
            self.optimizer.calculate_amplitude_coefficient(0.5, -10.0)
        
        # 测试边界值
        result = self.optimizer.calculate_amplitude_coefficient(0.1, 10.0)  # 正好1%
        assert result['amplitude_coefficient'] == 0.01
        assert result['is_valid'] is True
        
        result = self.optimizer.calculate_amplitude_coefficient(3.0, 10.0)  # 正好30%
        assert result['amplitude_coefficient'] == 0.30
        assert result['is_valid'] is True
    
    def test_volume_breakthrough_edge_cases(self):
        """测试成交量突破边界情况"""
        # 测试零平均成交量
        current_data = MarketData('TEST001', '2024-01-02', 10.0, 10.2, 9.8, 10.1, 1000000, 10100000)
        
        with pytest.raises(CalculationException):
            self.optimizer.confirm_volume_breakthrough(current_data, 0.0)
        
        # 测试负平均成交量
        with pytest.raises(CalculationException):
            self.optimizer.confirm_volume_breakthrough(current_data, -1000000)
        
        # 测试边界突破倍数
        result = self.optimizer.confirm_volume_breakthrough(current_data, 833333)  # 正好1.2倍
        assert abs(result['volume_multiplier'] - 1.2) < 0.01
        assert result['has_breakthrough'] is True
    
    def test_price_breakthrough_trend_analysis(self):
        """测试价格穿越趋势分析"""
        # 创建强势上涨趋势数据
        uptrend_data = []
        for i in range(5):
            price = 10.0 + i * 0.1  # 每天上涨0.1元
            data = MarketData(f'TEST001', f'2024-01-0{i+1}', price-0.05, price+0.05, price-0.1, price, 1000000, price*1000000)
            uptrend_data.append(data)
        
        result = self.optimizer.monitor_price_breakthrough(uptrend_data, 10.0)
        
        assert result['breakthrough_trend']['trend'] in ['strong_upward', 'moderate_upward']
        assert result['breakthrough_trend']['strength'] > 0.5
        assert result['breakthrough_trend']['momentum'] > 0
    
    def test_comprehensive_score_calculation(self):
        """测试综合评分计算"""
        # 创建各种质量的分析结果
        excellent_price = {
            'has_breakthrough': True,
            'breakthrough_strength': 0.9
        }
        
        excellent_volume = {
            'has_breakthrough': True,
            'entry_timing_score': 0.85
        }
        
        excellent_amplitude = {
            'is_valid': True,
            'entry_readiness': {'readiness_score': 0.9}
        }
        
        score = self.optimizer._calculate_comprehensive_score(
            excellent_price, excellent_volume, excellent_amplitude
        )
        
        assert score > 0.8  # 应该是高分
        
        # 测试较差条件
        poor_price = {
            'has_breakthrough': False,
            'breakthrough_strength': 0.2
        }
        
        poor_volume = {
            'has_breakthrough': False,
            'entry_timing_score': 0.3
        }
        
        poor_amplitude = {
            'is_valid': False,
            'entry_readiness': {'readiness_score': 0.2}
        }
        
        score = self.optimizer._calculate_comprehensive_score(
            poor_price, poor_volume, poor_amplitude
        )
        
        assert score < 0.4  # 应该是低分


if __name__ == '__main__':
    pytest.main([__file__])