"""
成交量维度分析器测试
测试VolumeDimensionAnalyzer的各项功能
"""

import pytest
from backend_core.strategies.pvfrs.models import MarketData, DataInsufficientException, CalculationException
from backend_core.strategies.pvfrs.analyzers import VolumeDimensionAnalyzer


class TestVolumeDimensionAnalyzer:
    """成交量维度分析器测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.analyzer = VolumeDimensionAnalyzer()
        
        # 创建测试数据 - 20天的市场数据
        self.test_data = []
        base_price = 10.0
        base_volume = 1000000
        
        for i in range(20):
            # 模拟价格上涨趋势
            price = base_price + i * 0.1
            # 模拟成交量变化
            volume = base_volume + i * 50000
            
            data = MarketData(
                symbol="000001",
                date=f"2024-01-{i+1:02d}",
                open=price - 0.05,
                high=price + 0.1,
                low=price - 0.1,
                close=price,
                volume=volume,
                amount=volume * price
            )
            self.test_data.append(data)
    
    def test_calculate_avg_volume_20d(self):
        """测试20日平均成交量计算"""
        avg_volume = self.analyzer.calculate_avg_volume_20d(self.test_data)
        
        # 验证计算结果
        expected_avg = sum(data.volume for data in self.test_data) / 20
        assert abs(avg_volume - expected_avg) < 0.01
        assert avg_volume > 0
    
    def test_calculate_avg_volume_insufficient_data(self):
        """测试数据不足时的平均成交量计算"""
        insufficient_data = self.test_data[:10]  # 只有10天数据
        
        with pytest.raises(DataInsufficientException, match="计算20日平均成交量需要至少20天数据"):
            self.analyzer.calculate_avg_volume_20d(insufficient_data)
    
    def test_calculate_efficiency_ratio(self):
        """测试效率比计算"""
        current_volume = 1500000.0
        avg_volume = 1000000.0
        
        ratio = self.analyzer.calculate_efficiency_ratio(current_volume, avg_volume)
        
        assert ratio == 1.5
        assert ratio > 0
    
    def test_calculate_efficiency_ratio_zero_avg(self):
        """测试平均成交量为零时的效率比计算"""
        current_volume = 1500000.0
        avg_volume = 0.0
        
        with pytest.raises(CalculationException, match="平均成交量不能为零或负数"):
            self.analyzer.calculate_efficiency_ratio(current_volume, avg_volume)
    
    def test_calculate_efficiency_indicator(self):
        """测试进出效率指标计算"""
        current_volume = 1500000.0
        avg_volume = 1000000.0
        
        indicator = self.analyzer.calculate_efficiency_indicator(current_volume, avg_volume)
        
        assert indicator == 500000.0
    
    def test_check_volume_efficiency(self):
        """测试成交量效率条件检查"""
        # 测试成交量高于平均水平
        assert self.analyzer.check_volume_efficiency(1500000.0, 1000000.0) is True
        
        # 测试成交量等于平均水平
        assert self.analyzer.check_volume_efficiency(1000000.0, 1000000.0) is False
        
        # 测试成交量低于平均水平
        assert self.analyzer.check_volume_efficiency(800000.0, 1000000.0) is False
    
    def test_check_volume_efficiency_negative_volume(self):
        """测试负成交量的效率条件检查"""
        with pytest.raises(CalculationException, match="成交量不能为负数"):
            self.analyzer.check_volume_efficiency(-1000000.0, 1000000.0)
    
    def test_check_price_rising(self):
        """测试价格上涨检查"""
        # 测试价格上涨
        rising_data = [
            MarketData("000001", "2024-01-01", 10.0, 10.2, 9.8, 10.0, 1000000, 10000000.0),
            MarketData("000001", "2024-01-02", 10.1, 10.3, 9.9, 10.2, 1100000, 11220000.0)
        ]
        assert self.analyzer.check_price_rising(rising_data) is True
        
        # 测试价格下跌
        falling_data = [
            MarketData("000001", "2024-01-01", 10.0, 10.2, 9.8, 10.2, 1000000, 10200000.0),
            MarketData("000001", "2024-01-02", 10.1, 10.3, 9.9, 10.0, 1100000, 11000000.0)
        ]
        assert self.analyzer.check_price_rising(falling_data) is False
    
    def test_check_price_rising_insufficient_data(self):
        """测试数据不足时的价格上涨检查"""
        insufficient_data = [self.test_data[0]]  # 只有1天数据
        
        with pytest.raises(DataInsufficientException, match="检查价格上涨需要至少2天数据"):
            self.analyzer.check_price_rising(insufficient_data)
    
    def test_detect_volume_price_resonance(self):
        """测试量价共振状态检测"""
        # 测试量价共振（价格上涨且成交量放大）
        assert self.analyzer.detect_volume_price_resonance(True, True) is True
        
        # 测试价格上涨但成交量未放大
        assert self.analyzer.detect_volume_price_resonance(True, False) is False
        
        # 测试价格未上涨但成交量放大
        assert self.analyzer.detect_volume_price_resonance(False, True) is False
        
        # 测试价格未上涨且成交量未放大
        assert self.analyzer.detect_volume_price_resonance(False, False) is False
    
    def test_analyze_volume_price_resonance(self):
        """测试量价共振分析"""
        result = self.analyzer.analyze_volume_price_resonance(self.test_data)
        
        # 验证返回结果包含必要字段
        assert 'price_rising' in result
        assert 'volume_increasing' in result
        assert 'volume_price_resonance' in result
        assert 'current_price' in result
        assert 'previous_price' in result
        assert 'current_volume' in result
        assert 'avg_volume_20d' in result
        
        # 验证数据类型
        assert isinstance(result['price_rising'], bool)
        assert isinstance(result['volume_increasing'], bool)
        assert isinstance(result['volume_price_resonance'], bool)
        assert isinstance(result['current_price'], (int, float))
        assert isinstance(result['current_volume'], (int, float))
    
    def test_confirm_strong_fund_support(self):
        """测试强劲资金支撑确认"""
        # 测试强劲资金支撑（1.2-8倍范围内）
        assert self.analyzer.confirm_strong_fund_support(1200000.0, 1000000.0) is True  # 1.2倍
        assert self.analyzer.confirm_strong_fund_support(3000000.0, 1000000.0) is True  # 3倍
        assert self.analyzer.confirm_strong_fund_support(8000000.0, 1000000.0) is True  # 8倍
        
        # 测试资金支撑不足（低于1.2倍）
        assert self.analyzer.confirm_strong_fund_support(1100000.0, 1000000.0) is False  # 1.1倍
        
        # 测试过度放量（超过8倍）
        assert self.analyzer.confirm_strong_fund_support(9000000.0, 1000000.0) is False  # 9倍
    
    def test_confirm_strong_fund_support_zero_avg(self):
        """测试平均成交量为零时的资金支撑确认"""
        with pytest.raises(CalculationException, match="平均成交量不能为零或负数"):
            self.analyzer.confirm_strong_fund_support(1500000.0, 0.0)
    
    def test_filter_low_quality_signals(self):
        """测试低成色信号过滤"""
        # 测试高质量信号（0.8-10倍范围内）
        assert self.analyzer.filter_low_quality_signals(1000000.0, 1000000.0) is True  # 1倍
        assert self.analyzer.filter_low_quality_signals(2000000.0, 1000000.0) is True  # 2倍
        assert self.analyzer.filter_low_quality_signals(5000000.0, 1000000.0) is True  # 5倍
        
        # 测试成交量不足（低于0.8倍）
        assert self.analyzer.filter_low_quality_signals(700000.0, 1000000.0) is False  # 0.7倍
        
        # 测试过度放量（超过10倍）
        assert self.analyzer.filter_low_quality_signals(11000000.0, 1000000.0) is False  # 11倍
    
    def test_analyze_fund_support_quality(self):
        """测试资金支撑质量分析"""
        result = self.analyzer.analyze_fund_support_quality(self.test_data)
        
        # 验证返回结果包含必要字段
        assert 'strong_fund_support' in result
        assert 'is_high_quality_signal' in result
        assert 'volume_multiplier' in result
        assert 'current_volume' in result
        assert 'avg_volume_20d' in result
        assert 'fund_support_quality' in result
        
        # 验证数据类型
        assert isinstance(result['strong_fund_support'], bool)
        assert isinstance(result['is_high_quality_signal'], bool)
        assert isinstance(result['volume_multiplier'], (int, float))
        assert isinstance(result['fund_support_quality'], bool)
    
    def test_analyze_complete(self):
        """测试完整的成交量维度分析"""
        result = self.analyzer.analyze(self.test_data)
        
        # 验证返回结果包含所有必要字段
        expected_fields = [
            'avg_volume_20d', 'current_volume', 'efficiency_ratio',
            'efficiency_indicator', 'volume_efficiency', 'price_rising',
            'volume_increasing', 'volume_price_resonance', 'strong_fund_support',
            'is_high_quality_signal', 'volume_multiplier', 'fund_support_quality',
            'volume_dimension_valid'
        ]
        
        for field in expected_fields:
            assert field in result, f"缺少字段: {field}"
        
        # 验证关键指标的数据类型
        assert isinstance(result['avg_volume_20d'], (int, float))
        assert isinstance(result['current_volume'], (int, float))
        assert isinstance(result['efficiency_ratio'], (int, float))
        assert isinstance(result['volume_dimension_valid'], bool)
    
    def test_analyze_insufficient_data(self):
        """测试数据不足时的分析"""
        insufficient_data = self.test_data[:10]  # 只有10天数据
        
        with pytest.raises(DataInsufficientException, match="数据不足，需要至少20天数据"):
            self.analyzer.analyze(insufficient_data)
    
    def test_validate_conditions(self):
        """测试成交量维度条件验证"""
        # 测试所有条件都满足的情况
        indicators = {
            'current_volume': 2000000.0,
            'avg_volume_20d': 1000000.0,
            'volume_price_resonance': True
        }
        
        result = self.analyzer.validate_conditions(indicators)
        
        # 由于我们的测试数据设计，应该满足大部分条件
        assert isinstance(result, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])