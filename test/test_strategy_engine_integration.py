"""
PVFRS策略引擎集成测试
测试策略引擎和选股功能的集成
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import datetime, timedelta
from backend_core.strategies.pvfrs.models import MarketData
from backend_core.strategies.pvfrs.strategy_engine import StrategyEngine
from backend_core.strategies.pvfrs.stock_screener import StockScreener, ScreeningConfig
from backend_core.strategies.pvfrs.screening_report import ScreeningReportGenerator


def create_test_data_with_trend(symbol: str, trend: str = "up") -> list[MarketData]:
    """创建具有特定趋势的测试数据
    
    Args:
        symbol: 股票代码
        trend: 趋势类型 ("up", "down", "sideways")
        
    Returns:
        list[MarketData]: 测试数据
    """
    data = []
    base_price = 50.0
    base_volume = 2000000
    
    start_date = datetime.now() - timedelta(days=25)
    
    for i in range(25):
        date = start_date + timedelta(days=i)
        
        # 根据趋势调整价格
        if trend == "up":
            # 上涨趋势：大部分天数上涨
            if i < 20:  # 前20天
                if i % 3 != 0:  # 2/3的天数上涨
                    base_price *= 1.02  # 上涨2%
                else:
                    base_price *= 0.99  # 偶尔下跌1%
            else:  # 最后5天继续上涨
                base_price *= 1.015
        elif trend == "down":
            # 下跌趋势
            base_price *= 0.98
        else:
            # 横盘趋势
            base_price *= (1 + (i % 2 - 0.5) * 0.01)
        
        # 成交量：上涨趋势时放量
        if trend == "up":
            volume_multiplier = 1.5 if i % 3 != 0 else 0.8
        else:
            volume_multiplier = 1.0
        
        current_volume = int(base_volume * volume_multiplier)
        
        # 生成OHLC
        open_price = base_price * 0.995
        close_price = base_price
        high_price = base_price * 1.01
        low_price = base_price * 0.99
        
        market_data = MarketData(
            symbol=symbol,
            date=date.strftime('%Y-%m-%d'),
            open=round(open_price, 2),
            high=round(high_price, 2),
            low=round(low_price, 2),
            close=round(close_price, 2),
            volume=current_volume,
            amount=round(current_volume * close_price, 2)
        )
        
        data.append(market_data)
    
    return data


class TestStrategyEngineIntegration:
    """策略引擎集成测试类"""
    
    def test_strategy_engine_initialization(self):
        """测试策略引擎初始化"""
        engine = StrategyEngine()
        
        assert engine is not None
        assert engine.price_analyzer is not None
        assert engine.frequency_analyzer is not None
        assert engine.volume_analyzer is not None
        assert engine.resonance_detector is not None
        assert engine.signal_generator is not None
        
        status = engine.get_engine_status()
        assert status['ready'] is True
        assert status['engine_name'] == 'PVFRS Strategy Engine'
    
    def test_analyze_stock_with_sufficient_data(self):
        """测试有足够数据时的股票分析"""
        engine = StrategyEngine()
        test_data = create_test_data_with_trend("TEST001", "up")
        
        # 应该能够成功分析
        indicators = engine.analyze_stock("TEST001", test_data)
        
        assert indicators is not None
        assert indicators.macro_displacement > 0  # 上涨趋势应该有正的宏观位移
        assert indicators.avg_price_20d > 0
        assert indicators.rising_days >= 0
        assert indicators.falling_days >= 0
        assert indicators.avg_volume_20d > 0
        assert indicators.current_volume > 0
        assert 0 <= indicators.resonance_strength <= 1
    
    def test_analyze_stock_with_insufficient_data(self):
        """测试数据不足时的股票分析"""
        engine = StrategyEngine()
        insufficient_data = create_test_data_with_trend("TEST002", "up")[:10]  # 只有10天数据
        
        # 应该抛出数据不足异常
        with pytest.raises(Exception):  # DataInsufficientException
            engine.analyze_stock("TEST002", insufficient_data)
    
    def test_generate_signals(self):
        """测试信号生成"""
        engine = StrategyEngine()
        test_data = create_test_data_with_trend("TEST003", "up")
        
        # 生成信号（可能为空，这是正常的）
        signals = engine.generate_signals("TEST003", test_data)
        
        assert isinstance(signals, list)
        # 验证信号格式（如果有信号的话）
        for signal in signals:
            assert signal.symbol == "TEST003"
            assert signal.price > 0
            assert 0 <= signal.strength <= 1
            assert signal.reason is not None
    
    def test_get_strategy_analysis(self):
        """测试获取完整策略分析"""
        engine = StrategyEngine()
        test_data = create_test_data_with_trend("TEST004", "up")
        
        analysis = engine.get_strategy_analysis("TEST004", test_data)
        
        assert analysis is not None
        assert analysis['symbol'] == "TEST004"
        assert analysis['data_length'] == 25
        assert 'price_dimension' in analysis
        assert 'frequency_dimension' in analysis
        assert 'volume_dimension' in analysis
        assert 'resonance_detection' in analysis
        assert 'signals' in analysis
        assert 'strategy_assessment' in analysis
    
    def test_validate_strategy_conditions(self):
        """测试策略条件验证"""
        engine = StrategyEngine()
        test_data = create_test_data_with_trend("TEST005", "up")
        
        validation = engine.validate_strategy_conditions("TEST005", test_data)
        
        assert validation is not None
        assert 'valid' in validation
        assert 'data_sufficient' in validation
        assert validation['data_sufficient'] is True
        assert 'detailed_conditions' in validation
        assert 'price_conditions' in validation['detailed_conditions']
        assert 'frequency_conditions' in validation['detailed_conditions']
        assert 'volume_conditions' in validation['detailed_conditions']


class TestStockScreener:
    """股票筛选器测试类"""
    
    def test_stock_screener_initialization(self):
        """测试股票筛选器初始化"""
        screener = StockScreener()
        
        assert screener is not None
        assert screener.strategy_engine is not None
        assert screener.screening_config is not None
    
    def test_screen_stocks_with_data(self):
        """测试使用数据进行选股"""
        screener = StockScreener()
        
        # 创建多只股票的测试数据
        stock_data_dict = {
            "STOCK001": create_test_data_with_trend("STOCK001", "up"),
            "STOCK002": create_test_data_with_trend("STOCK002", "down"),
            "STOCK003": create_test_data_with_trend("STOCK003", "sideways")
        }
        
        target_date = datetime.now().strftime('%Y-%m-%d')
        config = ScreeningConfig(min_signal_strength=0.1)  # 降低门槛以便测试
        
        results = screener.screen_stocks(stock_data_dict, target_date, config)
        
        assert isinstance(results, list)
        # 验证结果格式
        for result in results:
            assert hasattr(result, 'symbol')
            assert hasattr(result, 'signal_strength')
            assert hasattr(result, 'price')
            assert result.signal_strength >= config.min_signal_strength
    
    def test_get_screening_statistics(self):
        """测试获取筛选统计信息"""
        screener = StockScreener()
        
        # 执行一次筛选以生成统计信息
        stock_data_dict = {
            "TEST001": create_test_data_with_trend("TEST001", "up")
        }
        target_date = datetime.now().strftime('%Y-%m-%d')
        
        screener.screen_stocks(stock_data_dict, target_date)
        stats = screener.get_screening_statistics()
        
        assert stats is not None
        assert 'total_stocks' in stats
        assert 'analyzed_stocks' in stats
        assert 'qualified_stocks' in stats
        assert 'processing_time' in stats
        assert stats['total_stocks'] == 1


class TestScreeningReportGenerator:
    """选股报告生成器测试类"""
    
    def test_report_generator_initialization(self):
        """测试报告生成器初始化"""
        generator = ScreeningReportGenerator()
        
        assert generator is not None
        assert generator.config is not None
    
    def test_sort_results(self):
        """测试结果排序"""
        from backend_core.strategies.pvfrs.stock_screener import ScreeningResult
        
        generator = ScreeningReportGenerator()
        
        # 创建测试结果
        results = [
            ScreeningResult(
                symbol="A", date="2026-01-17", signal_strength=0.8,
                signal_reason="test", conditions_met={}, price=10.0, volume=1000000
            ),
            ScreeningResult(
                symbol="B", date="2026-01-17", signal_strength=0.9,
                signal_reason="test", conditions_met={}, price=20.0, volume=2000000
            ),
            ScreeningResult(
                symbol="C", date="2026-01-17", signal_strength=0.7,
                signal_reason="test", conditions_met={}, price=15.0, volume=1500000
            )
        ]
        
        # 按信号强度降序排序
        sorted_results = generator.sort_results(results)
        
        assert len(sorted_results) == 3
        assert sorted_results[0].signal_strength == 0.9  # B
        assert sorted_results[1].signal_strength == 0.8  # A
        assert sorted_results[2].signal_strength == 0.7  # C
    
    def test_generate_text_report(self):
        """测试生成文本报告"""
        generator = ScreeningReportGenerator()
        
        # 使用空结果测试
        config = ScreeningConfig()
        stats = {'total_stocks': 0, 'analyzed_stocks': 0, 'qualified_stocks': 0, 'processing_time': 0.0}
        
        report = generator.generate_text_report([], config, stats, "2026-01-17")
        
        assert isinstance(report, str)
        assert "PVFRS策略选股报告" in report
        assert "未找到符合条件的股票" in report
    
    def test_generate_csv_report(self):
        """测试生成CSV报告"""
        generator = ScreeningReportGenerator()
        
        # 使用空结果测试
        csv_report = generator.generate_csv_report([])
        
        assert isinstance(csv_report, str)
        assert "股票代码" in csv_report  # 应该包含表头


def test_integration_workflow():
    """测试完整的集成工作流程"""
    # 1. 创建策略引擎
    engine = StrategyEngine()
    
    # 2. 创建测试数据
    test_data = create_test_data_with_trend("INTEGRATION_TEST", "up")
    
    # 3. 分析股票
    indicators = engine.analyze_stock("INTEGRATION_TEST", test_data)
    assert indicators is not None
    
    # 4. 生成信号
    signals = engine.generate_signals("INTEGRATION_TEST", test_data)
    assert isinstance(signals, list)
    
    # 5. 创建筛选器并执行选股
    screener = StockScreener(engine)
    stock_data_dict = {"INTEGRATION_TEST": test_data}
    target_date = datetime.now().strftime('%Y-%m-%d')
    
    results = screener.screen_stocks(stock_data_dict, target_date)
    assert isinstance(results, list)
    
    # 6. 生成报告
    generator = ScreeningReportGenerator()
    config = ScreeningConfig()
    stats = screener.get_screening_statistics()
    
    report = generator.generate_text_report(results, config, stats, target_date)
    assert isinstance(report, str)
    assert "PVFRS策略选股报告" in report


if __name__ == "__main__":
    # 运行基本测试
    print("运行PVFRS策略引擎集成测试...")
    
    # 测试策略引擎
    test_engine = TestStrategyEngineIntegration()
    test_engine.test_strategy_engine_initialization()
    test_engine.test_analyze_stock_with_sufficient_data()
    print("✓ 策略引擎测试通过")
    
    # 测试股票筛选器
    test_screener = TestStockScreener()
    test_screener.test_stock_screener_initialization()
    test_screener.test_screen_stocks_with_data()
    print("✓ 股票筛选器测试通过")
    
    # 测试报告生成器
    test_generator = TestScreeningReportGenerator()
    test_generator.test_report_generator_initialization()
    test_generator.test_sort_results()
    test_generator.test_generate_text_report()
    print("✓ 报告生成器测试通过")
    
    # 测试集成工作流程
    test_integration_workflow()
    print("✓ 集成工作流程测试通过")
    
    print("\n所有测试通过！策略引擎和选股功能实现正确。")