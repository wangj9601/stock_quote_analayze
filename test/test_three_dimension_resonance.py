"""
三维共振检测器测试
测试三维共振检测器的核心功能
"""

import pytest
from datetime import datetime, timedelta
from backend_core.strategies.pvfrs import (
    MarketData, ThreeDimensionResonanceEngine, SignalType,
    DataInsufficientException, CalculationException
)


class TestThreeDimensionResonanceEngine:
    """三维共振检测引擎测试类"""
    
    def setup_method(self):
        """测试前准备"""
        self.engine = ThreeDimensionResonanceEngine()
    
    def create_test_data(self, days=20, trend='up', volume_trend='up'):
        """创建测试数据
        
        Args:
            days: 数据天数
            trend: 价格趋势 ('up', 'down', 'sideways')
            volume_trend: 成交量趋势 ('up', 'down', 'stable')
        """
        data = []
        base_date = datetime(2024, 1, 1)
        base_price = 10.0
        base_volume = 1000000
        
        for i in range(days):
            date = base_date + timedelta(days=i)
            
            # 价格趋势
            if trend == 'up':
                # 上涨趋势，有波动
                price_change = 0.02 + (i * 0.01) + (0.005 if i % 3 == 0 else -0.002)
                current_price = base_price * (1 + price_change * (i + 1) / 10)  # 缩小变化幅度
            elif trend == 'down':
                # 下跌趋势，但确保价格不会变为负数
                price_change = -0.005 * (i + 1)  # 每天下跌0.5%
                current_price = base_price * (1 + price_change)
                current_price = max(current_price, base_price * 0.5)  # 最低不低于基础价格的50%
            else:  # sideways
                price_change = 0.005 if i % 2 == 0 else -0.005
                current_price = base_price * (1 + price_change)
            
            # 成交量趋势
            if volume_trend == 'up':
                volume_multiplier = 1.0 + (i * 0.05)
            elif volume_trend == 'down':
                volume_multiplier = max(0.5, 1.0 - (i * 0.02))  # 最低不低于50%
            else:  # stable
                volume_multiplier = 1.0 + (0.1 if i % 2 == 0 else -0.1)
            
            current_volume = int(base_volume * volume_multiplier)
            
            # 创建OHLC数据
            open_price = current_price * 0.99
            high_price = current_price * 1.01
            low_price = current_price * 0.98
            close_price = current_price
            
            data.append(MarketData(
                symbol="TEST001",
                date=date.strftime("%Y-%m-%d"),
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=current_volume,
                amount=current_volume * current_price
            ))
        
        return data
    
    def test_analyze_insufficient_data(self):
        """测试数据不足的情况"""
        # 只有10天数据，不足20天
        data = self.create_test_data(days=10)
        
        signal = self.engine.analyze_and_generate_signal("TEST001", data)
        assert signal is None  # 数据不足，不应生成信号
    
    def test_analyze_strong_uptrend_with_volume(self):
        """测试强势上涨趋势配合成交量放大"""
        # 创建理想的上涨数据：价格上涨 + 成交量放大
        data = self.create_test_data(days=20, trend='up', volume_trend='up')
        
        signal = self.engine.analyze_and_generate_signal("TEST001", data)
        
        # 应该生成买入信号
        if signal:
            assert signal.signal_type == SignalType.BUY
            assert signal.symbol == "TEST001"
            assert signal.strength > 0
            assert "三维共振" in signal.reason
    
    def test_analyze_downtrend(self):
        """测试下跌趋势"""
        # 创建下跌数据
        data = self.create_test_data(days=20, trend='down', volume_trend='down')
        
        signal = self.engine.analyze_and_generate_signal("TEST001", data)
        
        # 下跌趋势不应生成买入信号
        assert signal is None
    
    def test_get_analysis_details(self):
        """测试获取详细分析结果"""
        data = self.create_test_data(days=20, trend='up', volume_trend='up')
        
        details = self.engine.get_analysis_details("TEST001", data)
        
        assert details['symbol'] == "TEST001"
        assert details['data_length'] == 20
        assert 'price_indicators' in details
        assert 'frequency_indicators' in details
        assert 'volume_indicators' in details
        assert 'resonance_result' in details
    
    def test_batch_analyze_stocks(self):
        """测试批量分析股票"""
        stock_data = {
            'STOCK001': self.create_test_data(days=20, trend='up', volume_trend='up'),
            'STOCK002': self.create_test_data(days=20, trend='down', volume_trend='down'),
            'STOCK003': self.create_test_data(days=15)  # 数据不足
        }
        
        results = self.engine.batch_analyze_stocks(stock_data)
        
        assert len(results) == 3
        assert 'STOCK001' in results
        assert 'STOCK002' in results
        assert 'STOCK003' in results
        
        # STOCK003数据不足，不应有信号
        assert not results['STOCK003']['has_signal']
    
    def test_get_dimension_summary(self):
        """测试维度分析汇总"""
        stock_data = {
            'STOCK001': self.create_test_data(days=20, trend='up', volume_trend='up'),
            'STOCK002': self.create_test_data(days=20, trend='down', volume_trend='down')
        }
        
        results = self.engine.batch_analyze_stocks(stock_data)
        summary = self.engine.get_dimension_summary(results)
        
        assert summary['total_stocks'] == 2
        assert 'signal_rate' in summary
        assert 'dimension_pass_rates' in summary
        assert 'dimension_pass_counts' in summary
    
    def test_price_dimension_validation(self):
        """测试价格维度验证"""
        # 创建价格横盘的数据（不满足价格维度条件）
        data = self.create_test_data(days=20, trend='sideways', volume_trend='up')
        
        signal = self.engine.analyze_and_generate_signal("TEST001", data)
        
        # 价格维度不满足，不应生成信号
        assert signal is None
    
    def test_volume_dimension_validation(self):
        """测试成交量维度验证"""
        # 创建价格上涨但成交量萎缩的数据
        data = self.create_test_data(days=20, trend='up', volume_trend='down')
        
        signal = self.engine.analyze_and_generate_signal("TEST001", data)
        
        # 成交量维度不满足，不应生成信号
        assert signal is None


if __name__ == "__main__":
    pytest.main([__file__])