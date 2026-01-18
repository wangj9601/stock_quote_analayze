"""
PVFRS策略系统集成测试
验证整个系统的端到端正确性和各组件之间的集成
"""

import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime, timedelta
from typing import List, Dict
import random

from backend_core.strategies.pvfrs import (
    MarketData, PVFRSIndicators, Signal, Trade, BacktestResult,
    SignalType, DataInsufficientException, CalculationException, ConfigurationException
)
from backend_core.strategies.pvfrs.pvfrs_system import (
    PVFRSSystem, create_pvfrs_system, quick_analyze_stock, quick_screen_stocks
)


class TestPVFRSSystemIntegration:
    """PVFRS策略系统集成测试类"""
    
    @pytest.fixture
    def sample_data(self) -> List[MarketData]:
        """生成测试用的市场数据"""
        data = []
        base_price = 10.0
        base_volume = 1000000
        
        for i in range(30):
            date = (datetime.now() - timedelta(days=30-i-1)).strftime('%Y-%m-%d')
            
            # 模拟上涨趋势数据
            price_change = random.uniform(-0.02, 0.06)  # 偏向上涨
            base_price *= (1 + price_change)
            
            volume_change = random.uniform(-0.2, 0.4)
            volume = int(base_volume * (1 + volume_change))
            
            open_price = base_price * random.uniform(0.99, 1.01)
            close_price = base_price
            high_price = max(open_price, close_price) * random.uniform(1.0, 1.02)
            low_price = min(open_price, close_price) * random.uniform(0.98, 1.0)
            
            market_data = MarketData(
                symbol="TEST001",
                date=date,
                open=round(open_price, 2),
                high=round(high_price, 2),
                low=round(low_price, 2),
                close=round(close_price, 2),
                volume=volume,
                amount=round(volume * close_price, 2)
            )
            
            data.append(market_data)
        
        return data
    
    @pytest.fixture
    def pvfrs_system(self) -> PVFRSSystem:
        """创建PVFRS系统实例"""
        return create_pvfrs_system()
    
    def test_system_initialization(self, pvfrs_system):
        """测试系统初始化"""
        # 验证系统基本属性
        assert pvfrs_system.is_initialized is True
        assert pvfrs_system.config_manager is not None
        assert pvfrs_system.data_interface is not None
        assert pvfrs_system.strategy_engine is not None
        assert pvfrs_system.backtest_engine is not None
        assert pvfrs_system.risk_manager is not None
        assert pvfrs_system.resonance_engine is not None
        
        # 验证系统状态
        status = pvfrs_system.get_system_status()
        assert status['initialized'] is True
        assert status['system_ready'] is True
        assert 'components' in status
        assert len(status['components']) == 6
        
        # 验证系统信息
        info = pvfrs_system.get_system_info()
        assert info['name'] == 'PVFRS Strategy System'
        assert info['version'] == '1.0.0'
        assert 'components' in info
    
    def test_system_validation(self, pvfrs_system):
        """测试系统验证功能"""
        validation_result = pvfrs_system.validate_system()
        
        # 验证基本结构
        assert 'validation_time' in validation_result
        assert 'overall_valid' in validation_result
        assert 'component_status' in validation_result
        assert 'issues' in validation_result
        
        # 验证组件状态
        components = validation_result['component_status']
        expected_components = [
            'config_manager', 'data_interface', 'strategy_engine',
            'backtest_engine', 'risk_manager', 'resonance_engine'
        ]
        
        for component in expected_components:
            assert component in components
            assert 'valid' in components[component]
    
    def test_single_stock_analysis_integration(self, pvfrs_system, sample_data):
        """测试单股分析集成功能"""
        symbol = "TEST001"
        
        # 执行分析
        result = pvfrs_system.analyze_single_stock(symbol, sample_data)
        
        # 验证结果结构
        assert 'symbol' in result
        assert result['symbol'] == symbol
        assert 'analysis_time' in result
        assert 'data_period' in result
        assert 'strategy_analysis' in result
        assert 'resonance_analysis' in result
        assert 'risk_assessment' in result
        assert 'condition_validation' in result
        assert 'overall_score' in result
        assert 'investment_advice' in result
        assert 'analysis_success' in result
        
        # 验证数据期间信息
        data_period = result['data_period']
        assert 'start_date' in data_period
        assert 'end_date' in data_period
        assert 'data_length' in data_period
        assert data_period['data_length'] == len(sample_data)
        
        # 验证策略分析结果
        strategy_analysis = result['strategy_analysis']
        assert 'strategy_assessment' in strategy_analysis
        
        strategy_assessment = strategy_analysis['strategy_assessment']
        assert 'has_buy_signal' in strategy_assessment
        assert 'max_signal_strength' in strategy_assessment
        assert 'three_dimension_resonance' in strategy_assessment
        assert 'overall_score' in strategy_assessment
        
        # 验证共振分析结果
        resonance_analysis = result['resonance_analysis']
        assert 'signal' in resonance_analysis
        assert 'details' in resonance_analysis
        
        # 验证风险评估结果
        risk_assessment = result['risk_assessment']
        assert isinstance(risk_assessment, dict)
        
        # 验证条件验证结果
        condition_validation = result['condition_validation']
        assert 'valid' in condition_validation
        assert 'data_sufficient' in condition_validation
        
        # 验证综合评分
        overall_score = result['overall_score']
        assert isinstance(overall_score, (int, float))
        assert 0 <= overall_score <= 1
        
        # 验证投资建议
        investment_advice = result['investment_advice']
        assert 'recommendation' in investment_advice
        assert 'confidence' in investment_advice
        assert 'reasons' in investment_advice
        assert 'risk_level' in investment_advice
        assert 'suggested_position_size' in investment_advice
        
        assert investment_advice['recommendation'] in ['BUY', 'SELL', 'HOLD']
        assert 0 <= investment_advice['confidence'] <= 1
        assert investment_advice['risk_level'] in ['LOW', 'MEDIUM', 'HIGH']
        assert 0 <= investment_advice['suggested_position_size'] <= 1
    
    def test_single_stock_analysis_with_insufficient_data(self, pvfrs_system):
        """测试数据不足时的单股分析"""
        symbol = "TEST002"
        insufficient_data = [
            MarketData(
                symbol=symbol,
                date="2024-01-01",
                open=10.0,
                high=10.5,
                low=9.5,
                close=10.2,
                volume=1000000,
                amount=10200000.0
            )
        ]
        
        # 应该抛出数据不足异常
        with pytest.raises(DataInsufficientException):
            pvfrs_system.analyze_single_stock(symbol, insufficient_data)
    
    def test_batch_screening_integration(self, pvfrs_system):
        """测试批量选股集成功能"""
        symbols = ["TEST001", "TEST002", "TEST003"]
        target_date = datetime.now().strftime('%Y-%m-%d')
        
        # 执行批量选股
        result = pvfrs_system.screen_stocks(symbols, target_date)
        
        # 验证结果结构
        assert 'screening_time' in result
        assert 'target_date' in result
        assert result['target_date'] == target_date
        assert 'input_symbols' in result
        assert result['input_symbols'] == symbols
        assert 'qualified_stocks' in result
        assert 'screening_stats' in result
        assert 'dimension_summary' in result
        assert 'failed_symbols' in result
        assert 'system_version' in result
        
        # 验证选股统计
        screening_stats = result['screening_stats']
        assert 'total_input' in screening_stats
        assert 'data_available' in screening_stats
        assert 'analysis_completed' in screening_stats
        assert 'qualified_count' in screening_stats
        assert 'failed_count' in screening_stats
        assert 'success_rate' in screening_stats
        assert 'qualification_rate' in screening_stats
        
        assert screening_stats['total_input'] == len(symbols)
        assert 0 <= screening_stats['success_rate'] <= 1
        assert 0 <= screening_stats['qualification_rate'] <= 1
        
        # 验证维度汇总
        dimension_summary = result['dimension_summary']
        assert 'total_stocks' in dimension_summary
        assert 'stocks_with_signals' in dimension_summary
        assert 'signal_rate' in dimension_summary
        assert 'dimension_pass_rates' in dimension_summary
        assert 'dimension_pass_counts' in dimension_summary
        
        pass_rates = dimension_summary['dimension_pass_rates']
        assert 'price' in pass_rates
        assert 'frequency' in pass_rates
        assert 'volume' in pass_rates
        assert 'three_dimension' in pass_rates
        
        for rate in pass_rates.values():
            assert 0 <= rate <= 1
    
    def test_backtest_integration(self, pvfrs_system):
        """测试回测集成功能"""
        symbols = ["TEST001", "TEST002"]
        start_date = "2024-01-01"
        end_date = "2024-12-31"
        initial_capital = 100000
        
        # 由于没有真实数据源，测试应该抛出CalculationException
        with pytest.raises(CalculationException) as exc_info:
            pvfrs_system.run_backtest(symbols, start_date, end_date, initial_capital)
        
        # 验证异常信息包含预期内容
        assert "没有可用的回测数据" in str(exc_info.value)
    
    def test_configuration_management_integration(self, pvfrs_system):
        """测试配置管理集成功能"""
        # 获取原始配置
        original_config = pvfrs_system.config_manager.get_current_config()
        assert isinstance(original_config, dict)
        
        # 更新配置
        new_config = {
            'stop_loss': -0.08,
            'take_profit': 0.25,
            'max_position_size': 0.12
        }
        
        success = pvfrs_system.update_config(new_config)
        assert success is True
        
        # 验证配置更新
        updated_config = pvfrs_system.config_manager.get_current_config()
        assert updated_config['stop_loss'] == -0.08
        assert updated_config['take_profit'] == 0.25
        assert updated_config['max_position_size'] == 0.12
        
        # 验证配置有效性
        is_valid = pvfrs_system.config_manager.validate_config(updated_config)
        assert is_valid is True
    
    def test_quick_functions_integration(self, sample_data):
        """测试快捷函数集成"""
        symbol = "TEST001"
        
        # 测试快速分析单股
        result = quick_analyze_stock(symbol, sample_data)
        
        # 验证结果结构
        assert 'symbol' in result
        assert result['symbol'] == symbol
        assert 'overall_score' in result
        assert 'investment_advice' in result
        
        # 测试快速批量选股
        symbols = ["TEST001", "TEST002"]
        target_date = datetime.now().strftime('%Y-%m-%d')
        
        screening_result = quick_screen_stocks(symbols, target_date)
        
        # 验证结果结构
        assert 'input_symbols' in screening_result
        assert screening_result['input_symbols'] == symbols
        assert 'qualified_stocks' in screening_result
        assert 'screening_stats' in screening_result
    
    def test_error_handling_integration(self, pvfrs_system):
        """测试错误处理集成"""
        # 测试空数据
        with pytest.raises(DataInsufficientException):
            pvfrs_system.analyze_single_stock("EMPTY", [])
        
        # 测试数据不足
        insufficient_data = [
            MarketData(
                symbol="INSUFFICIENT",
                date="2024-01-01",
                open=10.0,
                high=10.0,
                low=10.0,
                close=10.0,
                volume=1000,
                amount=10000.0
            )
        ]
        
        with pytest.raises(DataInsufficientException):
            pvfrs_system.analyze_single_stock("INSUFFICIENT", insufficient_data)
        
        # 测试无效配置
        invalid_config = {
            'stop_loss': 0.1,  # 应该是负数
            'take_profit': -0.2,  # 应该是正数
            'max_position_size': 1.5,  # 不应该超过1
            'max_holding_days': 10,  # 添加必需参数
            'observation_period': 20  # 添加必需参数
        }
        
        # 配置验证应该失败
        with pytest.raises(ConfigurationException):
            pvfrs_system.config_manager.validate_config(invalid_config)
    
    def test_end_to_end_workflow(self, pvfrs_system, sample_data):
        """测试端到端工作流程"""
        symbol = "TEST001"
        
        # 1. 系统验证
        validation = pvfrs_system.validate_system()
        assert validation['overall_valid'] is True
        
        # 2. 单股分析
        analysis_result = pvfrs_system.analyze_single_stock(symbol, sample_data)
        assert analysis_result['analysis_success'] is True
        
        # 3. 获取投资建议
        advice = analysis_result['investment_advice']
        recommendation = advice['recommendation']
        
        # 4. 根据建议进行后续操作
        if recommendation == 'BUY':
            # 如果建议买入，验证相关信息
            assert advice['confidence'] > 0
            assert advice['suggested_position_size'] >= 0
            
            # 可以进一步进行回测验证（但由于没有真实数据，会抛出异常）
            try:
                backtest_result = pvfrs_system.run_backtest([symbol], "2024-01-01", "2024-12-31")
                assert 'backtest_result' in backtest_result
            except CalculationException:
                # 预期的异常，因为没有真实数据
                pass
        
        # 5. 批量选股验证
        screening_result = pvfrs_system.screen_stocks([symbol], datetime.now().strftime('%Y-%m-%d'))
        assert 'qualified_stocks' in screening_result
        
        # 6. 配置管理验证
        config_update_success = pvfrs_system.update_config({'max_position_size': 0.1})
        assert config_update_success is True
        
        # 验证整个流程完成
        final_status = pvfrs_system.get_system_status()
        assert final_status['system_ready'] is True


class TestPVFRSSystemPerformance:
    """PVFRS策略系统性能测试类"""
    
    def test_large_dataset_analysis(self):
        """测试大数据集分析性能"""
        # 生成较大的数据集
        large_data = []
        base_price = 10.0
        
        for i in range(100):  # 100天数据
            date = (datetime.now() - timedelta(days=100-i-1)).strftime('%Y-%m-%d')
            price_change = random.uniform(-0.03, 0.05)
            base_price *= (1 + price_change)
            
            market_data = MarketData(
                symbol="LARGE_TEST",
                date=date,
                open=base_price * 0.99,
                high=base_price * 1.02,
                low=base_price * 0.98,
                close=base_price,
                volume=random.randint(800000, 1200000),
                amount=base_price * random.randint(800000, 1200000)
            )
            large_data.append(market_data)
        
        # 测试分析性能
        system = create_pvfrs_system()
        
        start_time = datetime.now()
        result = system.analyze_single_stock("LARGE_TEST", large_data)
        end_time = datetime.now()
        
        analysis_time = (end_time - start_time).total_seconds()
        
        # 验证分析完成且性能合理（应该在几秒内完成）
        assert result['analysis_success'] is True
        assert analysis_time < 10.0  # 应该在10秒内完成
    
    def test_batch_analysis_performance(self):
        """测试批量分析性能"""
        system = create_pvfrs_system()
        
        # 生成多只股票的数据
        symbols = [f"PERF_TEST_{i:03d}" for i in range(10)]
        
        start_time = datetime.now()
        result = system.screen_stocks(symbols, datetime.now().strftime('%Y-%m-%d'))
        end_time = datetime.now()
        
        analysis_time = (end_time - start_time).total_seconds()
        
        # 验证批量分析完成且性能合理
        assert 'screening_stats' in result
        assert analysis_time < 30.0  # 应该在30秒内完成


class TestPVFRSRealDataValidation:
    """PVFRS策略真实数据验证测试类"""
    
    def test_real_market_conditions_simulation(self):
        """测试真实市场条件模拟"""
        system = create_pvfrs_system()
        
        # 模拟不同市场条件的数据
        market_scenarios = {
            'bull_market': self._generate_bull_market_data(),
            'bear_market': self._generate_bear_market_data(),
            'sideways_market': self._generate_sideways_market_data(),
            'volatile_market': self._generate_volatile_market_data()
        }
        
        results = {}
        
        for scenario_name, data in market_scenarios.items():
            try:
                result = system.analyze_single_stock(f"TEST_{scenario_name.upper()}", data)
                results[scenario_name] = {
                    'success': True,
                    'overall_score': result['overall_score'],
                    'recommendation': result['investment_advice']['recommendation'],
                    'confidence': result['investment_advice']['confidence']
                }
            except Exception as e:
                results[scenario_name] = {
                    'success': False,
                    'error': str(e)
                }
        
        # 验证不同市场条件下的系统表现
        assert results['bull_market']['success'] is True
        assert results['bear_market']['success'] is True
        assert results['sideways_market']['success'] is True
        assert results['volatile_market']['success'] is True
        
        # 验证牛市中更容易产生买入信号
        bull_score = results['bull_market']['overall_score']
        bear_score = results['bear_market']['overall_score']
        assert bull_score >= bear_score, "牛市评分应该不低于熊市评分"
    
    def test_edge_case_data_handling(self):
        """测试边界情况数据处理"""
        system = create_pvfrs_system()
        
        # 测试各种边界情况
        edge_cases = {
            'all_same_price': self._generate_flat_price_data(),
            'extreme_volatility': self._generate_extreme_volatile_data(),
            'zero_volume_days': self._generate_zero_volume_data(),
            'price_gaps': self._generate_gap_data(),
            'minimal_data': self._generate_minimal_valid_data()
        }
        
        for case_name, data in edge_cases.items():
            try:
                if case_name == 'minimal_data':
                    # 最小数据应该能够分析
                    result = system.analyze_single_stock(f"EDGE_{case_name.upper()}", data)
                    assert result['analysis_success'] is True
                else:
                    # 其他边界情况应该能够处理或给出合理的错误
                    result = system.analyze_single_stock(f"EDGE_{case_name.upper()}", data)
                    # 如果能分析，结果应该是合理的
                    assert 0 <= result['overall_score'] <= 1
            except (DataInsufficientException, CalculationException) as e:
                # 这些异常是可以接受的
                assert case_name in ['zero_volume_days', 'extreme_volatility']
            except Exception as e:
                pytest.fail(f"边界情况 {case_name} 处理失败: {str(e)}")
    
    def test_large_scale_screening_performance(self):
        """测试大规模选股性能"""
        system = create_pvfrs_system()
        
        # 生成大量股票数据
        large_symbol_list = [f"TEST{i:06d}" for i in range(100)]
        target_date = datetime.now().strftime('%Y-%m-%d')
        
        start_time = datetime.now()
        result = system.screen_stocks(large_symbol_list, target_date)
        end_time = datetime.now()
        
        processing_time = (end_time - start_time).total_seconds()
        
        # 验证性能要求
        assert processing_time < 120.0, f"大规模选股耗时过长: {processing_time:.2f}秒"
        
        # 验证结果完整性
        assert 'screening_stats' in result
        assert result['screening_stats']['total_input'] == len(large_symbol_list)
        
        # 验证处理效率
        processing_rate = len(large_symbol_list) / processing_time
        assert processing_rate > 0.5, f"处理速度过慢: {processing_rate:.2f} 股票/秒"
    
    def test_concurrent_analysis_stability(self):
        """测试并发分析稳定性"""
        import threading
        import queue
        
        system = create_pvfrs_system()
        results_queue = queue.Queue()
        
        def analyze_worker(symbol_suffix):
            try:
                data = self._generate_bull_market_data()
                # 修改股票代码以避免冲突
                for item in data:
                    item.symbol = f"CONCURRENT_{symbol_suffix}"
                
                result = system.analyze_single_stock(f"CONCURRENT_{symbol_suffix}", data)
                results_queue.put(('success', symbol_suffix, result['overall_score']))
            except Exception as e:
                results_queue.put(('error', symbol_suffix, str(e)))
        
        # 启动多个并发分析线程
        threads = []
        for i in range(10):
            thread = threading.Thread(target=analyze_worker, args=(f"{i:03d}",))
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join(timeout=30)
        
        # 收集结果
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())
        
        # 验证并发处理结果
        assert len(results) == 10, "并发分析结果数量不正确"
        
        success_count = sum(1 for result in results if result[0] == 'success')
        assert success_count >= 8, f"并发分析成功率过低: {success_count}/10"
    
    def test_memory_usage_stability(self):
        """测试内存使用稳定性"""
        import gc
        
        try:
            import psutil
        except ImportError:
            pytest.skip("psutil模块未安装，跳过内存测试")
        
        import os
        
        system = create_pvfrs_system()
        process = psutil.Process(os.getpid())
        
        # 记录初始内存使用
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 执行大量分析操作
        for i in range(50):
            data = self._generate_bull_market_data()
            symbol = f"MEMORY_TEST_{i:03d}"
            
            try:
                result = system.analyze_single_stock(symbol, data)
                
                # 每10次操作检查一次内存
                if i % 10 == 9:
                    gc.collect()  # 强制垃圾回收
                    current_memory = process.memory_info().rss / 1024 / 1024  # MB
                    memory_growth = current_memory - initial_memory
                    
                    # 内存增长不应该超过100MB
                    assert memory_growth < 100, f"内存泄漏检测: 增长了 {memory_growth:.2f}MB"
            
            except Exception as e:
                # 记录但不中断测试
                print(f"内存测试中的分析错误 (第{i}次): {str(e)}")
        
        # 最终内存检查
        gc.collect()
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_growth = final_memory - initial_memory
        
        assert total_growth < 150, f"总内存增长过大: {total_growth:.2f}MB"
    
    def _generate_bull_market_data(self) -> List[MarketData]:
        """生成牛市数据"""
        data = []
        base_price = 10.0
        base_volume = 1000000
        
        for i in range(30):
            date = (datetime.now() - timedelta(days=30-i-1)).strftime('%Y-%m-%d')
            
            # 牛市特征：价格总体上涨，成交量逐步放大
            price_change = random.uniform(0.0, 0.08)  # 偏向上涨
            base_price *= (1 + price_change)
            
            volume_change = random.uniform(-0.1, 0.3)  # 成交量逐步放大
            volume = int(base_volume * (1 + volume_change))
            
            market_data = MarketData(
                symbol="BULL_TEST",
                date=date,
                open=base_price * 0.99,
                high=base_price * 1.03,
                low=base_price * 0.98,
                close=base_price,
                volume=volume,
                amount=volume * base_price
            )
            data.append(market_data)
        
        return data
    
    def _generate_bear_market_data(self) -> List[MarketData]:
        """生成熊市数据"""
        data = []
        base_price = 15.0  # 从较高价格开始下跌
        base_volume = 1200000
        
        for i in range(30):
            date = (datetime.now() - timedelta(days=30-i-1)).strftime('%Y-%m-%d')
            
            # 熊市特征：价格总体下跌，成交量萎缩
            price_change = random.uniform(-0.06, 0.02)  # 偏向下跌
            base_price *= (1 + price_change)
            
            volume_change = random.uniform(-0.3, 0.1)  # 成交量萎缩
            volume = int(base_volume * (1 + volume_change))
            
            market_data = MarketData(
                symbol="BEAR_TEST",
                date=date,
                open=base_price * 1.01,
                high=base_price * 1.02,
                low=base_price * 0.97,
                close=base_price,
                volume=volume,
                amount=volume * base_price
            )
            data.append(market_data)
        
        return data
    
    def _generate_sideways_market_data(self) -> List[MarketData]:
        """生成横盘市场数据"""
        data = []
        base_price = 12.0
        base_volume = 1000000
        
        for i in range(30):
            date = (datetime.now() - timedelta(days=30-i-1)).strftime('%Y-%m-%d')
            
            # 横盘特征：价格在小范围内波动
            price_change = random.uniform(-0.03, 0.03)  # 小幅波动
            current_price = base_price * (1 + price_change)
            
            volume_change = random.uniform(-0.2, 0.2)
            volume = int(base_volume * (1 + volume_change))
            
            market_data = MarketData(
                symbol="SIDEWAYS_TEST",
                date=date,
                open=current_price * 0.995,
                high=current_price * 1.015,
                low=current_price * 0.985,
                close=current_price,
                volume=volume,
                amount=volume * current_price
            )
            data.append(market_data)
        
        return data
    
    def _generate_volatile_market_data(self) -> List[MarketData]:
        """生成高波动市场数据"""
        data = []
        base_price = 10.0
        base_volume = 1000000
        
        for i in range(30):
            date = (datetime.now() - timedelta(days=30-i-1)).strftime('%Y-%m-%d')
            
            # 高波动特征：价格大幅波动，成交量不规律
            price_change = random.uniform(-0.15, 0.15)  # 大幅波动
            base_price *= (1 + price_change)
            
            volume_change = random.uniform(-0.5, 1.0)  # 成交量大幅波动
            volume = int(base_volume * (1 + volume_change))
            
            market_data = MarketData(
                symbol="VOLATILE_TEST",
                date=date,
                open=base_price * random.uniform(0.95, 1.05),
                high=base_price * random.uniform(1.05, 1.20),
                low=base_price * random.uniform(0.80, 0.95),
                close=base_price,
                volume=volume,
                amount=volume * base_price
            )
            data.append(market_data)
        
        return data
    
    def _generate_flat_price_data(self) -> List[MarketData]:
        """生成价格不变数据"""
        data = []
        price = 10.0
        
        for i in range(25):
            date = (datetime.now() - timedelta(days=25-i-1)).strftime('%Y-%m-%d')
            
            market_data = MarketData(
                symbol="FLAT_TEST",
                date=date,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=1000000,
                amount=price * 1000000
            )
            data.append(market_data)
        
        return data
    
    def _generate_extreme_volatile_data(self) -> List[MarketData]:
        """生成极端波动数据"""
        data = []
        base_price = 10.0
        
        for i in range(25):
            date = (datetime.now() - timedelta(days=25-i-1)).strftime('%Y-%m-%d')
            
            # 极端波动：每天涨跌幅超过20%
            price_change = random.choice([-0.25, 0.25])  # 极端涨跌
            base_price *= (1 + price_change)
            
            market_data = MarketData(
                symbol="EXTREME_TEST",
                date=date,
                open=base_price * 0.9,
                high=base_price * 1.3,
                low=base_price * 0.7,
                close=base_price,
                volume=random.randint(500000, 2000000),
                amount=base_price * random.randint(500000, 2000000)
            )
            data.append(market_data)
        
        return data
    
    def _generate_zero_volume_data(self) -> List[MarketData]:
        """生成零成交量数据"""
        data = []
        base_price = 10.0
        
        for i in range(25):
            date = (datetime.now() - timedelta(days=25-i-1)).strftime('%Y-%m-%d')
            
            # 部分天数成交量为0
            volume = 0 if i % 5 == 0 else random.randint(800000, 1200000)
            
            market_data = MarketData(
                symbol="ZERO_VOL_TEST",
                date=date,
                open=base_price,
                high=base_price * 1.01,
                low=base_price * 0.99,
                close=base_price,
                volume=volume,
                amount=base_price * volume
            )
            data.append(market_data)
        
        return data
    
    def _generate_gap_data(self) -> List[MarketData]:
        """生成跳空数据"""
        data = []
        base_price = 10.0
        
        for i in range(25):
            date = (datetime.now() - timedelta(days=25-i-1)).strftime('%Y-%m-%d')
            
            # 每5天一个跳空
            if i % 5 == 0 and i > 0:
                gap_ratio = random.choice([0.8, 1.2])  # 向上或向下跳空20%
                base_price *= gap_ratio
            
            market_data = MarketData(
                symbol="GAP_TEST",
                date=date,
                open=base_price,
                high=base_price * 1.02,
                low=base_price * 0.98,
                close=base_price,
                volume=random.randint(800000, 1200000),
                amount=base_price * random.randint(800000, 1200000)
            )
            data.append(market_data)
        
        return data
    
    def _generate_minimal_valid_data(self) -> List[MarketData]:
        """生成最小有效数据（刚好20天）"""
        data = []
        base_price = 10.0
        
        for i in range(20):  # 刚好20天
            date = (datetime.now() - timedelta(days=20-i-1)).strftime('%Y-%m-%d')
            
            price_change = random.uniform(-0.02, 0.04)
            base_price *= (1 + price_change)
            
            market_data = MarketData(
                symbol="MINIMAL_TEST",
                date=date,
                open=base_price * 0.99,
                high=base_price * 1.02,
                low=base_price * 0.98,
                close=base_price,
                volume=random.randint(800000, 1200000),
                amount=base_price * random.randint(800000, 1200000)
            )
            data.append(market_data)
        
        return data


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])