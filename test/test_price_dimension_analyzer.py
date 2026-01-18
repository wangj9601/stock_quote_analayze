"""
价格维度分析器测试
测试宏观位移指标、即时强度指标和20日平均价格的计算
"""

import pytest
from datetime import datetime, timedelta
from backend_core.strategies.pvfrs.models import MarketData, DataInsufficientException, CalculationException
from backend_core.strategies.pvfrs.analyzers import PriceDimensionAnalyzer


class TestPriceDimensionAnalyzer:
    """价格维度分析器测试类"""
    
    def setup_method(self):
        """测试前准备"""
        self.analyzer = PriceDimensionAnalyzer()
    
    def create_test_data(self, days: int, start_price: float = 10.0, trend: str = 'up') -> list:
        """创建测试数据
        
        Args:
            days: 天数
            start_price: 起始价格
            trend: 趋势 ('up', 'down', 'flat')
        """
        data = []
        base_date = datetime(2024, 1, 1)
        
        for i in range(days):
            date = base_date + timedelta(days=i)
            
            if trend == 'up':
                # 上涨趋势：每天涨0.1元
                price = start_price + i * 0.1
            elif trend == 'down':
                # 下跌趋势：每天跌0.1元
                price = start_price - i * 0.1
            else:
                # 平盘：价格不变
                price = start_price
            
            market_data = MarketData(
                symbol="000001",
                date=date.strftime('%Y-%m-%d'),
                open=price,
                high=price * 1.02,
                low=price * 0.98,
                close=price,
                volume=1000000,
                amount=price * 1000000
            )
            data.append(market_data)
        
        return data
    
    def test_calculate_macro_displacement_uptrend(self):
        """测试上涨趋势的宏观位移指标计算"""
        # 创建20天上涨数据，起始价格10.0，每天涨0.1
        data = self.create_test_data(20, start_price=10.0, trend='up')
        
        # 计算宏观位移
        result = self.analyzer.calculate_macro_displacement(data)
        
        # d₁ = 10.0, d₂₀ = 10.0 + 19*0.1 = 11.9
        # Δ = d₂₀ - d₁ = 11.9 - 10.0 = 1.9
        expected = 1.9
        assert abs(result - expected) < 0.001, f"期望{expected}，实际{result}"
    
    def test_calculate_macro_displacement_downtrend(self):
        """测试下跌趋势的宏观位移指标计算"""
        # 创建20天下跌数据
        data = self.create_test_data(20, start_price=10.0, trend='down')
        
        result = self.analyzer.calculate_macro_displacement(data)
        
        # d₁ = 10.0, d₂₀ = 10.0 - 19*0.1 = 8.1
        # Δ = d₂₀ - d₁ = 8.1 - 10.0 = -1.9
        expected = -1.9
        assert abs(result - expected) < 0.001, f"期望{expected}，实际{result}"
    
    def test_calculate_macro_displacement_flat(self):
        """测试平盘的宏观位移指标计算"""
        # 创建20天平盘数据
        data = self.create_test_data(20, start_price=10.0, trend='flat')
        
        result = self.analyzer.calculate_macro_displacement(data)
        
        # d₁ = d₂₀ = 10.0
        # Δ = d₂₀ - d₁ = 10.0 - 10.0 = 0.0
        expected = 0.0
        assert abs(result - expected) < 0.001, f"期望{expected}，实际{result}"
    
    def test_calculate_macro_displacement_insufficient_data(self):
        """测试数据不足时的异常处理"""
        # 只有19天数据
        data = self.create_test_data(19, start_price=10.0, trend='up')
        
        with pytest.raises(DataInsufficientException) as exc_info:
            self.analyzer.calculate_macro_displacement(data)
        
        assert "至少20天数据" in str(exc_info.value)
    
    def test_calculate_macro_displacement_more_than_20_days(self):
        """测试超过20天数据时只取最近20天"""
        # 创建30天数据，前10天平盘，后20天上涨
        data_flat = self.create_test_data(10, start_price=10.0, trend='flat')
        data_up = self.create_test_data(20, start_price=10.0, trend='up')
        
        # 调整后20天数据的日期
        base_date = datetime(2024, 1, 11)  # 从第11天开始
        for i, market_data in enumerate(data_up):
            date = base_date + timedelta(days=i)
            market_data.date = date.strftime('%Y-%m-%d')
        
        all_data = data_flat + data_up
        
        result = self.analyzer.calculate_macro_displacement(all_data)
        
        # 应该只计算最近20天（上涨趋势）
        # d₁ = 10.0, d₂₀ = 11.9, Δ = 1.9
        expected = 1.9
        assert abs(result - expected) < 0.001, f"期望{expected}，实际{result}"
    
    def test_calculate_avg_price_20d(self):
        """测试20日平均价格计算"""
        # 创建20天数据，价格从10.0到11.9（每天涨0.1）
        data = self.create_test_data(20, start_price=10.0, trend='up')
        
        result = self.analyzer.calculate_avg_price_20d(data)
        
        # 平均价格 = (10.0 + 10.1 + ... + 11.9) / 20
        # 等差数列求和：(首项 + 末项) * 项数 / 2
        # = (10.0 + 11.9) * 20 / 2 / 20 = 10.95
        expected = 10.95
        assert abs(result - expected) < 0.001, f"期望{expected}，实际{result}"
    
    def test_calculate_instant_deviation_positive(self):
        """测试即时强度指标计算（正值）"""
        # 创建20天上涨数据
        data = self.create_test_data(20, start_price=10.0, trend='up')
        
        result = self.analyzer.calculate_instant_deviation(data)
        
        # d₂₀ = 11.9, d = 10.95
        # 即时强度 = d₂₀ - d = 11.9 - 10.95 = 0.95
        expected = 0.95
        assert abs(result - expected) < 0.001, f"期望{expected}，实际{result}"
    
    def test_calculate_instant_deviation_negative(self):
        """测试即时强度指标计算（负值）"""
        # 创建20天下跌数据
        data = self.create_test_data(20, start_price=10.0, trend='down')
        
        result = self.analyzer.calculate_instant_deviation(data)
        
        # d₂₀ = 8.1, d = 9.05
        # 即时强度 = d₂₀ - d = 8.1 - 9.05 = -0.95
        expected = -0.95
        assert abs(result - expected) < 0.001, f"期望{expected}，实际{result}"
    
    def test_validate_conditions_both_positive(self):
        """测试价格维度条件验证（两个条件都满足）"""
        indicators = {
            'macro_displacement': 1.5,  # 正值
            'instant_deviation': 0.8    # 正值
        }
        
        result = self.analyzer.validate_conditions(indicators)
        assert result is True
    
    def test_validate_conditions_macro_negative(self):
        """测试价格维度条件验证（宏观位移为负）"""
        indicators = {
            'macro_displacement': -0.5,  # 负值
            'instant_deviation': 0.8     # 正值
        }
        
        result = self.analyzer.validate_conditions(indicators)
        assert result is False
    
    def test_validate_conditions_instant_negative(self):
        """测试价格维度条件验证（即时强度为负）"""
        indicators = {
            'macro_displacement': 1.5,   # 正值
            'instant_deviation': -0.3    # 负值
        }
        
        result = self.analyzer.validate_conditions(indicators)
        assert result is False
    
    def test_validate_conditions_both_negative(self):
        """测试价格维度条件验证（两个条件都不满足）"""
        indicators = {
            'macro_displacement': -1.2,  # 负值
            'instant_deviation': -0.8    # 负值
        }
        
        result = self.analyzer.validate_conditions(indicators)
        assert result is False
    
    def test_analyze_complete_flow(self):
        """测试完整的分析流程"""
        # 创建上涨趋势数据
        data = self.create_test_data(20, start_price=10.0, trend='up')
        
        result = self.analyzer.analyze(data)
        
        # 验证返回的字典包含所有必要字段
        assert 'macro_displacement' in result
        assert 'instant_deviation' in result
        assert 'avg_price_20d' in result
        assert 'price_dimension_valid' in result
        
        # 验证计算结果
        assert abs(result['macro_displacement'] - 1.9) < 0.001
        assert abs(result['instant_deviation'] - 0.95) < 0.001
        assert abs(result['avg_price_20d'] - 10.95) < 0.001
        assert result['price_dimension_valid'] is True
    
    def test_analyze_insufficient_data(self):
        """测试分析时数据不足的异常处理"""
        data = self.create_test_data(15, start_price=10.0, trend='up')
        
        with pytest.raises(DataInsufficientException):
            self.analyzer.analyze(data)