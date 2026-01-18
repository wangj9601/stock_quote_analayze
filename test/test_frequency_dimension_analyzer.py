"""
频率维度分析器测试
测试频率维度分析器的各项功能
"""

import pytest
from backend_core.strategies.pvfrs.analyzers import FrequencyDimensionAnalyzer
from backend_core.strategies.pvfrs.models import MarketData, DataInsufficientException, CalculationException


class TestFrequencyDimensionAnalyzer:
    """频率维度分析器测试类"""
    
    def setup_method(self):
        """测试前准备"""
        self.analyzer = FrequencyDimensionAnalyzer()
    
    def create_test_data(self, prices):
        """创建测试数据"""
        data = []
        for i, price in enumerate(prices):
            data.append(MarketData(
                symbol="TEST",
                date=f"2024-01-{i+1:02d}",
                open=price,
                high=price * 1.02,
                low=price * 0.98,
                close=price,
                volume=1000000,
                amount=price * 1000000
            ))
        return data
    
    def test_count_rising_days_basic(self):
        """测试基本上涨天数统计"""
        # 创建20天数据，前10天上涨，后10天下跌
        prices = list(range(100, 110)) + list(range(109, 99, -1))
        data = self.create_test_data(prices)
        
        rising_days = self.analyzer.count_rising_days(data)
        assert rising_days == 9  # 前9天上涨（从第2天开始比较）
    
    def test_count_falling_days_basic(self):
        """测试基本下跌天数统计"""
        # 创建20天数据，前10天上涨，后10天下跌
        prices = list(range(100, 110)) + list(range(108, 98, -1))  # 修正：避免重复价格
        data = self.create_test_data(prices)
        
        falling_days = self.analyzer.count_falling_days(data)
        assert falling_days == 10  # 后10天下跌
    
    def test_count_days_insufficient_data(self):
        """测试数据不足的情况"""
        # 只有10天数据，不足20天
        prices = list(range(100, 110))
        data = self.create_test_data(prices)
        
        with pytest.raises(DataInsufficientException):
            self.analyzer.count_rising_days(data)
        
        with pytest.raises(DataInsufficientException):
            self.analyzer.count_falling_days(data)
    
    def test_check_frequency_advantage_true(self):
        """测试频率优势为真的情况"""
        result = self.analyzer.check_frequency_advantage(12, 7)
        assert result is True
    
    def test_check_frequency_advantage_false(self):
        """测试频率优势为假的情况"""
        result = self.analyzer.check_frequency_advantage(7, 12)
        assert result is False
    
    def test_check_frequency_advantage_equal(self):
        """测试上涨下跌天数相等的情况"""
        result = self.analyzer.check_frequency_advantage(10, 10)
        assert result is False  # 必须严格大于
    
    def test_check_frequency_advantage_invalid_input(self):
        """测试无效输入"""
        with pytest.raises(CalculationException):
            self.analyzer.check_frequency_advantage(-1, 5)
        
        with pytest.raises(CalculationException):
            self.analyzer.check_frequency_advantage(5, -1)
    
    def test_detect_false_prosperity_normal_trend(self):
        """测试正常趋势（无虚假繁荣）"""
        # 创建稳定上涨的价格序列
        prices = [100 + i * 0.5 for i in range(20)]  # 每天涨0.5%
        data = self.create_test_data(prices)
        
        has_false_prosperity = self.analyzer.detect_false_prosperity(data)
        assert has_false_prosperity is False
    
    def test_detect_false_prosperity_single_spike(self):
        """测试单日暴涨情况"""
        # 创建包含单日暴涨的价格序列
        prices = [100] * 10 + [120] + [121] * 9  # 第11天暴涨20%
        data = self.create_test_data(prices)
        
        has_false_prosperity = self.analyzer.detect_false_prosperity(data)
        assert has_false_prosperity is True
    
    def test_analyze_complete_valid_case(self):
        """测试完整分析 - 有效情况"""
        # 创建符合条件的价格序列：稳定上涨，无暴涨
        prices = [100 + i * 0.3 for i in range(20)]  # 稳定上涨
        data = self.create_test_data(prices)
        
        result = self.analyzer.analyze(data)
        
        assert 'rising_days' in result
        assert 'falling_days' in result
        assert 'frequency_advantage' in result
        assert 'has_false_prosperity' in result
        assert 'frequency_dimension_valid' in result
        
        # 应该有19天上涨，0天下跌
        assert result['rising_days'] == 19
        assert result['falling_days'] == 0
        assert result['frequency_advantage'] is True
        assert result['has_false_prosperity'] is False
        assert result['frequency_dimension_valid'] is True
    
    def test_analyze_complete_invalid_case(self):
        """测试完整分析 - 无效情况（虚假繁荣）"""
        # 创建包含暴涨的价格序列
        prices = [100] * 10 + [130] + [131] * 9  # 第11天暴涨30%
        data = self.create_test_data(prices)
        
        result = self.analyzer.analyze(data)
        
        assert result['has_false_prosperity'] is True
        assert result['frequency_dimension_valid'] is False  # 因为有虚假繁荣
    
    def test_validate_conditions_all_met(self):
        """测试所有条件都满足的情况"""
        indicators = {
            'rising_days': 15,
            'falling_days': 4,
            'has_false_prosperity': False
        }
        
        result = self.analyzer.validate_conditions(indicators)
        assert result is True
    
    def test_validate_conditions_false_prosperity(self):
        """测试存在虚假繁荣的情况"""
        indicators = {
            'rising_days': 15,
            'falling_days': 4,
            'has_false_prosperity': True
        }
        
        result = self.analyzer.validate_conditions(indicators)
        assert result is False
    
    def test_validate_conditions_insufficient_rising_days(self):
        """测试上涨天数不足的情况"""
        indicators = {
            'rising_days': 8,  # 少于(20-1)//2 = 9
            'falling_days': 4,
            'has_false_prosperity': False
        }
        
        result = self.analyzer.validate_conditions(indicators)
        assert result is False