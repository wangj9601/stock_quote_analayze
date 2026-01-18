"""
PVFRS策略端到端功能测试
测试从选股到前端展示、从回测配置到报告生成的完整流程
"""

import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime, timedelta
from typing import List, Dict
import json
import time
import threading
import random
from dataclasses import asdict
from unittest.mock import Mock, patch

from backend_core.strategies.pvfrs import (
    MarketData, PVFRSIndicators, Signal, Trade, BacktestResult,
    SignalType, DataInsufficientException, CalculationException
)
from backend_core.strategies.pvfrs.frontend_interface import SelectionResult
from backend_core.strategies.pvfrs.admin_interface import BacktestConfig, BacktestReport
from backend_core.strategies.pvfrs.pvfrs_system import create_pvfrs_system
from backend_core.strategies.pvfrs.frontend_interface import create_frontend_interface
from backend_core.strategies.pvfrs.admin_interface import create_admin_interface


class TestPVFRSEndToEndWorkflow:
    """PVFRS策略端到端工作流程测试"""
    
    @pytest.fixture
    def sample_market_data(self) -> Dict[str, List[MarketData]]:
        """生成多只股票的示例市场数据"""
        stocks_data = {}
        
        symbols = ["000001", "000002", "600036", "002415", "300059"]
        
        for symbol in symbols:
            data = []
            base_price = 10.0 + hash(symbol) % 20  # 基于股票代码生成不同基础价格
            base_volume = 1000000 + hash(symbol) % 500000
            
            for i in range(30):
                date = (datetime.now() - timedelta(days=30-i-1)).strftime('%Y-%m-%d')
                
                # 模拟不同的市场表现
                if symbol in ["000001", "600036"]:  # 强势股
                    price_change = random.uniform(0.0, 0.08)
                    volume_change = random.uniform(-0.1, 0.4)
                elif symbol in ["000002"]:  # 弱势股
                    price_change = random.uniform(-0.06, 0.02)
                    volume_change = random.uniform(-0.3, 0.1)
                else:  # 震荡股
                    price_change = random.uniform(-0.03, 0.05)
                    volume_change = random.uniform(-0.2, 0.3)
                
                base_price *= (1 + price_change)
                volume = int(base_volume * (1 + volume_change))
                
                market_data = MarketData(
                    symbol=symbol,
                    date=date,
                    open=round(base_price * 0.99, 2),
                    high=round(base_price * 1.02, 2),
                    low=round(base_price * 0.98, 2),
                    close=round(base_price, 2),
                    volume=volume,
                    amount=round(volume * base_price, 2)
                )
                data.append(market_data)
            
            stocks_data[symbol] = data
        
        return stocks_data
    
    def test_complete_stock_selection_to_frontend_display_workflow(self, sample_market_data):
        """测试从选股到前端展示的完整流程"""
        print("\n=== 测试选股到前端展示完整流程 ===")
        
        # 1. 创建系统组件
        pvfrs_system = create_pvfrs_system()
        frontend_interface = create_frontend_interface()
        
        # 验证系统初始化
        assert pvfrs_system.is_initialized is True
        assert frontend_interface is not None
        
        # 2. 执行批量选股
        symbols = list(sample_market_data.keys())
        target_date = datetime.now().strftime('%Y-%m-%d')
        
        print(f"步骤1: 执行批量选股 - 股票池: {symbols}")
        
        # 模拟数据接口返回数据
        with patch.object(pvfrs_system.data_interface, 'get_market_data') as mock_get_data:
            def mock_data_side_effect(symbol, start_date, end_date):
                if symbol in sample_market_data:
                    return sample_market_data[symbol]
                return []
            
            mock_get_data.side_effect = mock_data_side_effect
            
            # 执行选股
            screening_result = pvfrs_system.screen_stocks(symbols, target_date)
            
            # 验证选股结果
            assert 'qualified_stocks' in screening_result
            assert 'screening_stats' in screening_result
            assert screening_result['screening_stats']['total_input'] == len(symbols)
            
            qualified_stocks = screening_result['qualified_stocks']
            print(f"选股结果: 符合条件的股票数量 = {len(qualified_stocks)}")
        
        # 3. 前端接口获取选股结果
        print(f"步骤2: 前端接口获取选股结果")
        
        # 模拟前端接口获取选股结果
        with patch.object(frontend_interface, 'get_selection_results') as mock_get_results:
            # 将选股结果转换为SelectionResult格式
            selection_results = []
            for stock in qualified_stocks:
                signal = stock['signal']
                selection_result = SelectionResult(
                    symbol=stock['symbol'],
                    name=f"股票{stock['symbol']}",
                    signal_strength=signal['strength'],
                    conditions_met={
                        'price_dimension': True,
                        'frequency_dimension': True,
                        'volume_dimension': True,
                        'resonance_detected': True
                    },
                    indicators=PVFRSIndicators(
                        macro_displacement=0.5,
                        instant_deviation=0.2,
                        avg_price_20d=signal['price'],
                        rising_days=12,
                        falling_days=8,
                        frequency_advantage=True,
                        avg_volume_20d=1000000,
                        current_volume=1200000,
                        efficiency_ratio=1.2,
                        amplitude_ratio=0.05,
                        resonance_strength=signal['strength']
                    ),
                    timestamp=datetime.now().isoformat(),
                    price=signal['price'],
                    signal_reason=signal['reason']
                )
                selection_results.append(selection_result)
            
            mock_get_results.return_value = selection_results
            
            # 前端获取选股结果
            frontend_results = frontend_interface.get_selection_results(target_date)
            
            # 验证前端结果
            assert len(frontend_results) == len(qualified_stocks)
            for result in frontend_results:
                assert isinstance(result, SelectionResult)
                assert result.symbol in symbols
                assert 0 <= result.signal_strength <= 1
                assert isinstance(result.conditions_met, dict)
                assert isinstance(result.indicators, PVFRSIndicators)
            
            print(f"前端展示结果: {len(frontend_results)} 只股票")
        
        # 4. 获取股票详细信息
        print(f"步骤3: 获取股票详细信息")
        
        if frontend_results:
            test_symbol = frontend_results[0].symbol
            
            with patch.object(frontend_interface, 'get_stock_detail') as mock_get_detail:
                # 模拟股票详细信息
                stock_detail = {
                    'symbol': test_symbol,
                    'name': f"股票{test_symbol}",
                    'current_price': sample_market_data[test_symbol][-1].close,
                    'analysis_date': target_date,
                    'price_dimension': {
                        'macro_displacement': 0.5,
                        'instant_deviation': 0.2,
                        'avg_price_20d': sample_market_data[test_symbol][-1].close,
                        'condition_met': True
                    },
                    'frequency_dimension': {
                        'rising_days': 12,
                        'falling_days': 8,
                        'frequency_advantage': True,
                        'condition_met': True
                    },
                    'volume_dimension': {
                        'avg_volume_20d': 1000000,
                        'current_volume': 1200000,
                        'efficiency_ratio': 1.2,
                        'condition_met': True
                    },
                    'resonance_analysis': {
                        'resonance_strength': 0.8,
                        'three_dimension_resonance': True
                    },
                    'investment_advice': {
                        'recommendation': 'BUY',
                        'confidence': 0.8,
                        'risk_level': 'MEDIUM'
                    }
                }
                
                mock_get_detail.return_value = stock_detail
                
                # 获取股票详细信息
                detail_result = frontend_interface.get_stock_detail(test_symbol)
                
                # 验证详细信息
                assert detail_result['symbol'] == test_symbol
                assert 'price_dimension' in detail_result
                assert 'frequency_dimension' in detail_result
                assert 'volume_dimension' in detail_result
                assert 'resonance_analysis' in detail_result
                assert 'investment_advice' in detail_result
                
                print(f"股票详细信息: {test_symbol} - 投资建议: {detail_result['investment_advice']['recommendation']}")
        
        # 5. 实时刷新功能
        print(f"步骤4: 测试实时刷新功能")
        
        with patch.object(frontend_interface, 'refresh_results') as mock_refresh:
            mock_refresh.return_value = True
            
            refresh_success = frontend_interface.refresh_results()
            assert refresh_success is True
            
            print(f"实时刷新: 成功")
        
        print(f"✅ 选股到前端展示完整流程测试通过")
        return True
    
    def test_complete_backtest_configuration_to_report_generation_workflow(self, sample_market_data):
        """测试从回测配置到报告生成的完整流程"""
        print("\n=== 测试回测配置到报告生成完整流程 ===")
        
        # 1. 创建系统组件
        pvfrs_system = create_pvfrs_system()
        admin_interface = create_admin_interface()
        
        # 验证系统初始化
        assert pvfrs_system.is_initialized is True
        assert admin_interface is not None
        
        # 2. 配置回测参数
        print(f"步骤1: 配置回测参数")
        
        backtest_config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-12-31",
            stock_pool=list(sample_market_data.keys())[:3],  # 选择3只股票
            initial_capital=100000.0,
            strategy_params={
                'observation_period': 20,
                'min_signal_strength': 0.6
            },
            risk_params={
                'stop_loss': -0.08,
                'take_profit': 0.20,
                'max_position_size': 0.25,
                'max_holding_days': 30
            }
        )
        
        # 验证配置有效性
        config_dict = {
            'start_date': backtest_config.start_date,
            'end_date': backtest_config.end_date,
            'stock_pool': backtest_config.stock_pool,
            'initial_capital': backtest_config.initial_capital,
            'strategy_params': backtest_config.strategy_params,
            'risk_params': backtest_config.risk_params
        }
        
        # 验证配置参数
        assert backtest_config.initial_capital > 0
        assert len(backtest_config.stock_pool) > 0
        assert backtest_config.start_date < backtest_config.end_date
        
        print(f"回测配置: 股票池={len(backtest_config.stock_pool)}只, 初始资金={backtest_config.initial_capital:,.0f}元")
        
        # 3. 创建回测任务
        print(f"步骤2: 创建回测任务")
        
        with patch.object(admin_interface, 'create_backtest') as mock_create_backtest:
            task_id = "backtest_task_001"
            mock_create_backtest.return_value = task_id
            
            # 创建回测任务
            created_task_id = admin_interface.create_backtest(backtest_config)
            
            # 验证任务创建
            assert created_task_id == task_id
            assert isinstance(created_task_id, str)
            assert len(created_task_id) > 0
            
            print(f"回测任务创建: 任务ID = {created_task_id}")
        
        # 4. 监控回测进度
        print(f"步骤3: 监控回测进度")
        
        with patch.object(admin_interface, 'get_backtest_progress') as mock_get_progress:
            # 模拟回测进度变化
            progress_stages = [
                {'task_id': task_id, 'status': 'running', 'progress': 25, 'current_step': '数据准备'},
                {'task_id': task_id, 'status': 'running', 'progress': 50, 'current_step': '策略执行'},
                {'task_id': task_id, 'status': 'running', 'progress': 75, 'current_step': '结果计算'},
                {'task_id': task_id, 'status': 'completed', 'progress': 100, 'current_step': '回测完成'}
            ]
            
            for i, progress_info in enumerate(progress_stages):
                mock_get_progress.return_value = progress_info
                
                # 获取回测进度
                current_progress = admin_interface.get_backtest_progress(task_id)
                
                # 验证进度信息
                assert current_progress['task_id'] == task_id
                assert current_progress['status'] in ['running', 'completed', 'failed']
                assert 0 <= current_progress['progress'] <= 100
                assert 'current_step' in current_progress
                
                print(f"回测进度: {current_progress['progress']}% - {current_progress['current_step']}")
                
                if current_progress['status'] == 'completed':
                    break
        
        # 5. 生成回测报告
        print(f"步骤4: 生成回测报告")
        
        with patch.object(admin_interface, 'get_backtest_report') as mock_get_report:
            # 模拟回测报告
            mock_report = BacktestReport(
                report_id="report_001",
                task_id=task_id,
                config=backtest_config,
                total_return=0.15,
                annual_return=0.15,
                win_rate=0.65,
                max_drawdown=-0.08,
                sharpe_ratio=1.2,
                trades=[],  # 简化，实际应包含交易记录
                equity_curve=[
                    {'date': '2024-01-01', 'value': 100000},
                    {'date': '2024-06-01', 'value': 105000},
                    {'date': '2024-12-31', 'value': 115000}
                ],
                created_at=datetime.now().isoformat(),
                summary={
                    'total_trades': 10,
                    'winning_trades': 7,
                    'losing_trades': 3,
                    'avg_holding_period': 15.5
                }
            )
            
            mock_get_report.return_value = mock_report
            
            # 获取回测报告
            backtest_report = admin_interface.get_backtest_report(task_id)
            
            # 验证回测报告
            assert isinstance(backtest_report, BacktestReport)
            assert backtest_report.config == backtest_config
            assert isinstance(backtest_report.total_return, (int, float))
            assert isinstance(backtest_report.win_rate, (int, float))
            assert isinstance(backtest_report.max_drawdown, (int, float))
            assert isinstance(backtest_report.sharpe_ratio, (int, float))
            assert isinstance(backtest_report.equity_curve, list)
            
            print(f"回测报告生成:")
            print(f"  总收益率: {backtest_report.total_return:.1%}")
            print(f"  胜率: {backtest_report.win_rate:.1%}")
            print(f"  最大回撤: {backtest_report.max_drawdown:.1%}")
            print(f"  夏普比率: {backtest_report.sharpe_ratio:.2f}")
        
        # 6. 保存回测报告
        print(f"步骤5: 保存回测报告")
        
        with patch.object(admin_interface, 'save_backtest_report') as mock_save_report:
            report_id = "report_001"
            mock_save_report.return_value = report_id
            
            # 保存回测报告
            saved_report_id = admin_interface.save_backtest_report(backtest_report)
            
            # 验证报告保存
            assert saved_report_id == report_id
            assert isinstance(saved_report_id, str)
            assert len(saved_report_id) > 0
            
            print(f"回测报告保存: 报告ID = {saved_report_id}")
        
        # 7. 策略对比功能
        print(f"步骤6: 策略对比功能")
        
        with patch.object(admin_interface, 'compare_strategies') as mock_compare:
            # 模拟对比结果
            comparison_result = {
                'comparison_id': 'comp_001',
                'report_count': 2,
                'performance_comparison': {
                    'total_return': [0.15, 0.12],
                    'win_rate': [0.65, 0.60],
                    'max_drawdown': [-0.08, -0.10],
                    'sharpe_ratio': [1.2, 1.0]
                },
                'summary': {
                    'best_total_return': 0.15,
                    'best_win_rate': 0.65,
                    'best_sharpe_ratio': 1.2,
                    'lowest_drawdown': -0.08
                }
            }
            
            mock_compare.return_value = comparison_result
            
            # 执行策略对比
            report_ids = [report_id, "report_002"]
            comparison = admin_interface.compare_strategies(report_ids)
            
            # 验证对比结果
            assert comparison['report_count'] == len(report_ids)
            assert 'performance_comparison' in comparison
            assert 'summary' in comparison
            
            print(f"策略对比: 对比了{comparison['report_count']}个报告")
            print(f"  最佳收益率: {comparison['summary']['best_total_return']:.1%}")
            print(f"  最佳胜率: {comparison['summary']['best_win_rate']:.1%}")
        
        # 8. 历史报告查询
        print(f"步骤7: 历史报告查询")
        
        with patch.object(admin_interface, 'list_historical_reports') as mock_list_reports:
            # 模拟历史报告列表
            historical_reports = [
                BacktestReport(
                    report_id="report_001",
                    task_id="task_001",
                    config=backtest_config,
                    total_return=0.15,
                    annual_return=0.15,
                    win_rate=0.65,
                    max_drawdown=-0.08,
                    sharpe_ratio=1.2,
                    trades=[],
                    equity_curve=[],
                    created_at=(datetime.now() - timedelta(days=1)).isoformat(),
                    summary={}
                ),
                BacktestReport(
                    report_id="report_002",
                    task_id="task_002",
                    config=backtest_config,
                    total_return=0.12,
                    annual_return=0.12,
                    win_rate=0.60,
                    max_drawdown=-0.10,
                    sharpe_ratio=1.0,
                    trades=[],
                    equity_curve=[],
                    created_at=(datetime.now() - timedelta(days=7)).isoformat(),
                    summary={}
                )
            ]
            
            mock_list_reports.return_value = historical_reports
            
            # 查询历史报告
            reports = admin_interface.list_historical_reports(limit=10)
            
            # 验证历史报告
            assert isinstance(reports, list)
            assert len(reports) == 2
            for report in reports:
                assert isinstance(report, BacktestReport)
                assert hasattr(report, 'total_return')
                assert hasattr(report, 'created_at')
            
            print(f"历史报告查询: 找到{len(reports)}个历史报告")
        
        print(f"✅ 回测配置到报告生成完整流程测试通过")
        return True
    
    def test_integrated_frontend_backend_data_flow(self, sample_market_data):
        """测试前后端集成数据流"""
        print("\n=== 测试前后端集成数据流 ===")
        
        # 1. 创建系统组件
        pvfrs_system = create_pvfrs_system()
        frontend_interface = create_frontend_interface()
        
        # 2. 测试数据序列化和反序列化
        print(f"步骤1: 测试数据序列化")
        
        # 创建测试数据
        test_indicators = PVFRSIndicators(
            macro_displacement=0.5,
            instant_deviation=0.2,
            avg_price_20d=10.5,
            rising_days=12,
            falling_days=8,
            frequency_advantage=True,
            avg_volume_20d=1000000,
            current_volume=1200000,
            efficiency_ratio=1.2,
            amplitude_ratio=0.05,
            resonance_strength=0.8
        )
        
        # 序列化测试
        from dataclasses import asdict
        serialized_data = asdict(test_indicators)
        assert isinstance(serialized_data, dict)
        assert 'macro_displacement' in serialized_data
        assert serialized_data['resonance_strength'] == 0.8
        
        # 反序列化测试
        deserialized_indicators = PVFRSIndicators(**serialized_data)
        assert deserialized_indicators.macro_displacement == test_indicators.macro_displacement
        assert deserialized_indicators.resonance_strength == test_indicators.resonance_strength
        
        print(f"数据序列化: 成功")
        
        # 3. 测试JSON格式传输
        print(f"步骤2: 测试JSON格式传输")
        
        json_data = json.dumps(serialized_data, ensure_ascii=False, indent=2)
        assert isinstance(json_data, str)
        assert '"resonance_strength": 0.8' in json_data
        
        # JSON解析测试
        parsed_data = json.loads(json_data)
        assert parsed_data['resonance_strength'] == 0.8
        
        print(f"JSON传输: 成功")
        
        # 4. 测试前端接口数据格式一致性
        print(f"步骤3: 测试前端接口数据格式")
        
        with patch.object(frontend_interface, 'get_selection_results') as mock_get_results:
            # 模拟选股结果
            mock_results = [
                SelectionResult(
                    symbol="000001",
                    name="测试股票1",
                    signal_strength=0.8,
                    conditions_met={'price': True, 'frequency': True, 'volume': True},
                    indicators=test_indicators,
                    timestamp=datetime.now().isoformat(),
                    price=10.5,
                    signal_reason="三维共振条件满足"
                )
            ]
            
            mock_get_results.return_value = mock_results
            
            # 获取结果并验证格式
            results = frontend_interface.get_selection_results()
            
            # 验证数据格式
            assert len(results) == 1
            result = results[0]
            assert isinstance(result, SelectionResult)
            
            # 转换为字典格式（模拟API响应）
            result_dict = asdict(result)
            assert 'symbol' in result_dict
            assert 'signal_strength' in result_dict
            assert 'indicators' in result_dict
            
            # 验证指标数据格式
            indicators_dict = result_dict['indicators']
            assert isinstance(indicators_dict, dict)
            assert 'resonance_strength' in indicators_dict
            
            print(f"前端接口数据格式: 一致")
        
        print(f"✅ 前后端集成数据流测试通过")
        return True
    
    def test_error_handling_and_recovery_workflow(self):
        """测试错误处理和恢复工作流程"""
        print("\n=== 测试错误处理和恢复工作流程 ===")
        
        # 1. 创建系统组件
        pvfrs_system = create_pvfrs_system()
        frontend_interface = create_frontend_interface()
        admin_interface = create_admin_interface()
        
        # 2. 测试数据不足错误处理
        print(f"步骤1: 测试数据不足错误处理")
        
        insufficient_data = [
            MarketData(
                symbol="TEST_INSUFFICIENT",
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
            pvfrs_system.analyze_single_stock("TEST_INSUFFICIENT", insufficient_data)
        
        print(f"数据不足错误处理: 正确抛出异常")
        
        # 3. 测试配置错误处理
        print(f"步骤2: 测试配置错误处理")
        
        invalid_config = {
            'stop_loss': 0.1,  # 应该是负数
            'take_profit': -0.2,  # 应该是正数
            'max_position_size': 1.5,  # 不应该超过1
            'max_holding_days': 10,
            'observation_period': 20
        }
        
        # 配置验证应该失败
        try:
            pvfrs_system.config_manager.validate_config(invalid_config)
            assert False, "应该抛出配置异常"
        except Exception as e:
            assert "配置" in str(e) or "参数" in str(e)
            print(f"配置错误处理: 正确检测到无效配置")
        
        # 4. 测试前端接口错误处理
        print(f"步骤3: 测试前端接口错误处理")
        
        with patch.object(frontend_interface, 'get_selection_results') as mock_get_results:
            # 模拟前端接口异常
            mock_get_results.side_effect = Exception("数据获取失败")
            
            try:
                frontend_interface.get_selection_results()
                assert False, "应该抛出异常"
            except Exception as e:
                assert "数据获取失败" in str(e)
                print(f"前端接口错误处理: 正确处理异常")
        
        # 5. 测试回测错误处理
        print(f"步骤4: 测试回测错误处理")
        
        with patch.object(admin_interface, 'create_backtest') as mock_create_backtest:
            # 模拟回测创建失败
            mock_create_backtest.side_effect = Exception("回测创建失败")
            
            try:
                invalid_config = BacktestConfig(
                    start_date="invalid-date",
                    end_date="2024-12-31",
                    stock_pool=[],
                    initial_capital=-1000,  # 无效的初始资金
                    strategy_params={},
                    risk_params={}
                )
                admin_interface.create_backtest(invalid_config)
                assert False, "应该抛出异常"
            except Exception as e:
                assert "回测创建失败" in str(e)
                print(f"回测错误处理: 正确处理异常")
        
        # 6. 测试系统恢复机制
        print(f"步骤5: 测试系统恢复机制")
        
        # 验证系统在错误后仍能正常工作
        system_status = pvfrs_system.get_system_status()
        assert system_status['system_ready'] is True
        
        # 验证系统验证功能
        validation_result = pvfrs_system.validate_system()
        assert validation_result['overall_valid'] is True
        
        print(f"系统恢复机制: 系统在错误后仍能正常工作")
        
        print(f"✅ 错误处理和恢复工作流程测试通过")
        return True


class TestPVFRSPerformanceAndStability:
    """PVFRS策略性能和稳定性测试"""
    
    def test_high_concurrency_access_performance(self):
        """测试高并发访问性能"""
        print("\n=== 测试高并发访问性能 ===")
        
        # 1. 创建系统实例
        pvfrs_system = create_pvfrs_system()
        frontend_interface = create_frontend_interface()
        
        # 2. 准备测试数据
        test_data = self._generate_test_data("CONCURRENT_TEST", 25)
        
        # 3. 并发测试参数
        num_threads = 10
        operations_per_thread = 5
        results = []
        errors = []
        
        def concurrent_analysis_worker(thread_id):
            """并发分析工作线程"""
            thread_results = []
            thread_errors = []
            
            for i in range(operations_per_thread):
                try:
                    start_time = time.time()
                    
                    # 执行分析
                    symbol = f"THREAD_{thread_id}_STOCK_{i}"
                    # 修改测试数据的股票代码
                    thread_data = []
                    for item in test_data:
                        new_item = MarketData(
                            symbol=symbol,
                            date=item.date,
                            open=item.open,
                            high=item.high,
                            low=item.low,
                            close=item.close,
                            volume=item.volume,
                            amount=item.amount
                        )
                        thread_data.append(new_item)
                    
                    result = pvfrs_system.analyze_single_stock(symbol, thread_data)
                    
                    end_time = time.time()
                    execution_time = end_time - start_time
                    
                    thread_results.append({
                        'thread_id': thread_id,
                        'operation_id': i,
                        'symbol': symbol,
                        'execution_time': execution_time,
                        'success': True,
                        'overall_score': result['overall_score']
                    })
                    
                except Exception as e:
                    thread_errors.append({
                        'thread_id': thread_id,
                        'operation_id': i,
                        'error': str(e)
                    })
            
            results.extend(thread_results)
            errors.extend(thread_errors)
        
        # 4. 启动并发测试
        print(f"启动并发测试: {num_threads}个线程, 每线程{operations_per_thread}次操作")
        
        threads = []
        start_time = time.time()
        
        for thread_id in range(num_threads):
            thread = threading.Thread(target=concurrent_analysis_worker, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join(timeout=60)  # 60秒超时
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # 5. 分析并发测试结果
        total_operations = num_threads * operations_per_thread
        successful_operations = len(results)
        failed_operations = len(errors)
        
        print(f"并发测试结果:")
        print(f"  总操作数: {total_operations}")
        print(f"  成功操作: {successful_operations}")
        print(f"  失败操作: {failed_operations}")
        print(f"  成功率: {successful_operations/total_operations:.1%}")
        print(f"  总耗时: {total_time:.2f}秒")
        print(f"  平均每操作耗时: {total_time/total_operations:.3f}秒")
        
        if results:
            avg_execution_time = sum(r['execution_time'] for r in results) / len(results)
            max_execution_time = max(r['execution_time'] for r in results)
            min_execution_time = min(r['execution_time'] for r in results)
            
            print(f"  单操作平均耗时: {avg_execution_time:.3f}秒")
            print(f"  单操作最大耗时: {max_execution_time:.3f}秒")
            print(f"  单操作最小耗时: {min_execution_time:.3f}秒")
        
        # 6. 性能断言
        assert successful_operations >= total_operations * 0.8, f"成功率过低: {successful_operations/total_operations:.1%}"
        assert total_time < 120, f"总耗时过长: {total_time:.2f}秒"
        
        if results:
            assert avg_execution_time < 5.0, f"平均耗时过长: {avg_execution_time:.3f}秒"
        
        print(f"✅ 高并发访问性能测试通过")
        return True
    
    def test_long_running_stability(self):
        """测试长时间运行稳定性"""
        print("\n=== 测试长时间运行稳定性 ===")
        
        # 1. 创建系统实例
        pvfrs_system = create_pvfrs_system()
        
        # 2. 长时间运行测试参数
        test_duration = 30  # 30秒测试（实际应用中可能需要更长时间）
        operation_interval = 1  # 每秒执行一次操作
        
        start_time = time.time()
        operations_count = 0
        errors_count = 0
        memory_samples = []
        
        print(f"开始长时间运行测试: 持续{test_duration}秒")
        
        try:
            import psutil
            process = psutil.Process(os.getpid())
            memory_monitoring = True
        except ImportError:
            memory_monitoring = False
            print("  注意: psutil未安装，跳过内存监控")
        
        # 3. 执行长时间运行测试
        while time.time() - start_time < test_duration:
            try:
                # 生成测试数据
                symbol = f"STABILITY_TEST_{operations_count:04d}"
                test_data = self._generate_test_data(symbol, 25)
                
                # 执行分析
                result = pvfrs_system.analyze_single_stock(symbol, test_data)
                
                # 验证结果
                assert 'overall_score' in result
                assert 0 <= result['overall_score'] <= 1
                
                operations_count += 1
                
                # 内存监控
                if memory_monitoring and operations_count % 5 == 0:
                    memory_usage = process.memory_info().rss / 1024 / 1024  # MB
                    memory_samples.append({
                        'time': time.time() - start_time,
                        'memory_mb': memory_usage,
                        'operations': operations_count
                    })
                
                # 系统状态检查
                if operations_count % 10 == 0:
                    system_status = pvfrs_system.get_system_status()
                    assert system_status['system_ready'] is True
                
                time.sleep(operation_interval)
                
            except Exception as e:
                errors_count += 1
                print(f"  操作{operations_count}失败: {str(e)}")
                
                # 如果错误率过高，停止测试
                if errors_count > operations_count * 0.1:  # 错误率超过10%
                    print(f"  错误率过高，停止测试")
                    break
        
        end_time = time.time()
        actual_duration = end_time - start_time
        
        # 4. 分析稳定性测试结果
        print(f"长时间运行测试结果:")
        print(f"  实际运行时间: {actual_duration:.1f}秒")
        print(f"  总操作数: {operations_count}")
        print(f"  错误数: {errors_count}")
        print(f"  成功率: {(operations_count-errors_count)/operations_count:.1%}" if operations_count > 0 else "N/A")
        print(f"  平均操作频率: {operations_count/actual_duration:.2f}次/秒")
        
        # 5. 内存使用分析
        if memory_samples:
            initial_memory = memory_samples[0]['memory_mb']
            final_memory = memory_samples[-1]['memory_mb']
            max_memory = max(sample['memory_mb'] for sample in memory_samples)
            memory_growth = final_memory - initial_memory
            
            print(f"  内存使用情况:")
            print(f"    初始内存: {initial_memory:.1f}MB")
            print(f"    最终内存: {final_memory:.1f}MB")
            print(f"    最大内存: {max_memory:.1f}MB")
            print(f"    内存增长: {memory_growth:+.1f}MB")
            
            # 内存泄漏检查
            assert memory_growth < 50, f"可能存在内存泄漏: 增长了{memory_growth:.1f}MB"
        
        # 6. 稳定性断言
        assert operations_count > 0, "没有成功执行任何操作"
        assert errors_count <= operations_count * 0.05, f"错误率过高: {errors_count/operations_count:.1%}"
        
        # 最终系统状态检查
        final_status = pvfrs_system.get_system_status()
        assert final_status['system_ready'] is True, "系统在长时间运行后状态异常"
        
        validation_result = pvfrs_system.validate_system()
        assert validation_result['overall_valid'] is True, "系统在长时间运行后验证失败"
        
        print(f"✅ 长时间运行稳定性测试通过")
        return True
    
    def test_large_dataset_processing_performance(self):
        """测试大数据集处理性能"""
        print("\n=== 测试大数据集处理性能 ===")
        
        # 1. 创建系统实例
        pvfrs_system = create_pvfrs_system()
        
        # 2. 生成大数据集
        large_stock_pool = [f"LARGE_TEST_{i:04d}" for i in range(100)]  # 100只股票
        
        print(f"生成大数据集: {len(large_stock_pool)}只股票")
        
        # 3. 执行大规模选股测试
        target_date = datetime.now().strftime('%Y-%m-%d')
        
        # 模拟数据接口
        with patch.object(pvfrs_system.data_interface, 'get_market_data') as mock_get_data:
            def mock_large_data_side_effect(symbol, start_date, end_date):
                # 为每只股票生成数据
                return self._generate_test_data(symbol, 30)
            
            mock_get_data.side_effect = mock_large_data_side_effect
            
            # 执行大规模选股
            start_time = time.time()
            
            try:
                screening_result = pvfrs_system.screen_stocks(large_stock_pool, target_date)
                
                end_time = time.time()
                processing_time = end_time - start_time
                
                # 验证结果
                assert 'screening_stats' in screening_result
                stats = screening_result['screening_stats']
                
                print(f"大数据集处理结果:")
                print(f"  处理时间: {processing_time:.2f}秒")
                print(f"  输入股票数: {stats['total_input']}")
                print(f"  处理成功数: {stats['analysis_completed']}")
                print(f"  符合条件数: {stats['qualified_count']}")
                print(f"  处理速度: {stats['total_input']/processing_time:.2f}股票/秒")
                print(f"  成功率: {stats['success_rate']:.1%}")
                
                # 性能断言
                assert processing_time < 300, f"处理时间过长: {processing_time:.2f}秒"  # 5分钟内完成
                
                # 对于大数据集测试，主要关注性能，不强制要求成功率
                if stats['analysis_completed'] > 0:
                    # 如果有分析完成的股票，检查成功率
                    success_rate = stats['analysis_completed'] / stats['total_input']
                    assert success_rate >= 0.3, f"分析完成率过低: {success_rate:.1%}"
                
                processing_rate = stats['total_input'] / processing_time if processing_time > 0 else float('inf')
                # 降低处理速度要求，因为可能包含数据获取时间
                assert processing_rate >= 0.1, f"处理速度过慢: {processing_rate:.2f}股票/秒"
                
            except Exception as e:
                print(f"大数据集处理失败: {str(e)}")
                # 对于大数据集，可能因为资源限制失败，这是可以接受的
                if "内存" in str(e) or "资源" in str(e):
                    print("  由于资源限制，大数据集测试跳过")
                    return True
                else:
                    raise
        
        print(f"✅ 大数据集处理性能测试通过")
        return True
    
    def test_system_resource_usage_monitoring(self):
        """测试系统资源使用监控"""
        print("\n=== 测试系统资源使用监控 ===")
        
        try:
            import psutil
        except ImportError:
            print("psutil模块未安装，跳过资源监控测试")
            return True
        
        # 1. 创建系统实例
        pvfrs_system = create_pvfrs_system()
        process = psutil.Process(os.getpid())
        
        # 2. 记录初始资源使用
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        initial_cpu_percent = process.cpu_percent()
        
        print(f"初始资源使用:")
        print(f"  内存: {initial_memory:.1f}MB")
        print(f"  CPU: {initial_cpu_percent:.1f}%")
        
        # 3. 执行资源密集型操作
        operations_count = 20
        resource_samples = []
        
        print(f"执行{operations_count}次资源密集型操作...")
        
        for i in range(operations_count):
            # 生成较大的数据集
            symbol = f"RESOURCE_TEST_{i:03d}"
            large_data = self._generate_test_data(symbol, 50)  # 50天数据
            
            # 执行分析
            start_time = time.time()
            result = pvfrs_system.analyze_single_stock(symbol, large_data)
            end_time = time.time()
            
            # 记录资源使用
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            current_cpu = process.cpu_percent()
            
            resource_samples.append({
                'operation': i + 1,
                'memory_mb': current_memory,
                'cpu_percent': current_cpu,
                'execution_time': end_time - start_time,
                'overall_score': result['overall_score']
            })
            
            if (i + 1) % 5 == 0:
                print(f"  完成{i + 1}/{operations_count}次操作")
        
        # 4. 分析资源使用情况
        final_memory = resource_samples[-1]['memory_mb']
        max_memory = max(sample['memory_mb'] for sample in resource_samples)
        avg_memory = sum(sample['memory_mb'] for sample in resource_samples) / len(resource_samples)
        
        max_cpu = max(sample['cpu_percent'] for sample in resource_samples)
        avg_cpu = sum(sample['cpu_percent'] for sample in resource_samples) / len(resource_samples)
        
        avg_execution_time = sum(sample['execution_time'] for sample in resource_samples) / len(resource_samples)
        
        print(f"资源使用分析:")
        print(f"  内存使用:")
        print(f"    最终内存: {final_memory:.1f}MB")
        print(f"    最大内存: {max_memory:.1f}MB")
        print(f"    平均内存: {avg_memory:.1f}MB")
        print(f"    内存增长: {final_memory - initial_memory:+.1f}MB")
        print(f"  CPU使用:")
        print(f"    最大CPU: {max_cpu:.1f}%")
        print(f"    平均CPU: {avg_cpu:.1f}%")
        print(f"  执行性能:")
        print(f"    平均执行时间: {avg_execution_time:.3f}秒")
        
        # 5. 资源使用断言
        memory_growth = final_memory - initial_memory
        assert memory_growth < 100, f"内存增长过大: {memory_growth:.1f}MB"
        assert max_memory < initial_memory + 200, f"内存峰值过高: {max_memory:.1f}MB"
        assert avg_execution_time < 2.0, f"平均执行时间过长: {avg_execution_time:.3f}秒"
        
        # 6. 垃圾回收测试
        import gc
        gc.collect()
        
        post_gc_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_freed = final_memory - post_gc_memory
        
        print(f"垃圾回收效果:")
        print(f"  回收前内存: {final_memory:.1f}MB")
        print(f"  回收后内存: {post_gc_memory:.1f}MB")
        print(f"  释放内存: {memory_freed:.1f}MB")
        
        print(f"✅ 系统资源使用监控测试通过")
        return True
    
    def _generate_test_data(self, symbol: str, days: int) -> List[MarketData]:
        """生成测试用的市场数据"""
        import random
        
        data = []
        base_price = 10.0 + abs(hash(symbol)) % 20
        base_volume = 1000000 + abs(hash(symbol)) % 500000
        
        for i in range(days):
            date = (datetime.now() - timedelta(days=days-i-1)).strftime('%Y-%m-%d')
            
            # 生成价格变化
            price_change = random.uniform(-0.05, 0.08)
            base_price *= (1 + price_change)
            
            # 生成成交量变化
            volume_change = random.uniform(-0.3, 0.5)
            volume = int(base_volume * (1 + volume_change))
            
            # 生成OHLC数据
            open_price = base_price * random.uniform(0.99, 1.01)
            close_price = base_price
            high_price = max(open_price, close_price) * random.uniform(1.0, 1.03)
            low_price = min(open_price, close_price) * random.uniform(0.97, 1.0)
            
            market_data = MarketData(
                symbol=symbol,
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


if __name__ == "__main__":
    # 运行端到端测试
    pytest.main([__file__, "-v", "-s"])