#!/usr/bin/env python3
"""
PVFRS策略系统性能验证测试
测试系统在各种负载条件下的性能表现
"""

import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime, timedelta
from typing import List, Dict
import time
import threading
import multiprocessing
import psutil
import random
import gc

from backend_core.strategies.pvfrs import (
    MarketData, PVFRSIndicators, Signal, Trade, BacktestResult,
    SignalType, DataInsufficientException, CalculationException
)
from backend_core.strategies.pvfrs.pvfrs_system import (
    PVFRSSystem, create_pvfrs_system, quick_analyze_stock, quick_screen_stocks
)


class TestPVFRSPerformanceValidation:
    """PVFRS策略系统性能验证测试类"""
    
    @pytest.fixture
    def performance_system(self) -> PVFRSSystem:
        """创建性能测试用的PVFRS系统"""
        return create_pvfrs_system()
    
    def test_single_stock_analysis_performance(self, performance_system):
        """测试单股分析性能"""
        print("\n=== 单股分析性能测试 ===")
        
        # 测试不同数据量的分析性能
        data_sizes = [20, 50, 100, 200, 500]
        performance_results = []
        
        for size in data_sizes:
            # 生成测试数据
            test_data = self._generate_performance_data("PERF_TEST", size)
            
            # 执行性能测试
            start_time = time.time()
            
            try:
                result = performance_system.analyze_single_stock("PERF_TEST", test_data)
                end_time = time.time()
                
                analysis_time = end_time - start_time
                
                performance_results.append({
                    'data_size': size,
                    'analysis_time': analysis_time,
                    'success': True,
                    'throughput': size / analysis_time if analysis_time > 0 else 0
                })
                
                print(f"数据量 {size:3d} 天: {analysis_time:.4f}秒 (吞吐量: {size/analysis_time:.1f} 天/秒)")
                
                # 性能要求验证
                if size <= 100:
                    assert analysis_time < 2.0, f"小数据集分析耗时过长: {analysis_time:.4f}秒"
                elif size <= 200:
                    assert analysis_time < 5.0, f"中等数据集分析耗时过长: {analysis_time:.4f}秒"
                else:
                    assert analysis_time < 10.0, f"大数据集分析耗时过长: {analysis_time:.4f}秒"
                
            except Exception as e:
                performance_results.append({
                    'data_size': size,
                    'analysis_time': 0,
                    'success': False,
                    'error': str(e)
                })
                print(f"数据量 {size:3d} 天: 分析失败 - {str(e)}")
        
        # 验证性能趋势
        successful_results = [r for r in performance_results if r['success']]
        assert len(successful_results) >= len(data_sizes) * 0.8, "性能测试成功率过低"
        
        # 验证时间复杂度合理性（应该接近线性）
        if len(successful_results) >= 3:
            time_ratios = []
            for i in range(1, len(successful_results)):
                prev = successful_results[i-1]
                curr = successful_results[i]
                
                size_ratio = curr['data_size'] / prev['data_size']
                time_ratio = curr['analysis_time'] / prev['analysis_time']
                
                time_ratios.append(time_ratio / size_ratio)
            
            # 时间复杂度应该接近线性（比值接近1）
            avg_complexity_ratio = sum(time_ratios) / len(time_ratios)
            assert avg_complexity_ratio < 3.0, f"时间复杂度过高: {avg_complexity_ratio:.2f}"
        
        return performance_results
    
    def test_batch_screening_performance(self, performance_system):
        """测试批量选股性能"""
        print("\n=== 批量选股性能测试 ===")
        
        # 测试不同股票数量的选股性能
        stock_counts = [10, 25, 50, 100, 200]
        performance_results = []
        
        for count in stock_counts:
            # 生成股票列表
            symbols = [f"BATCH_TEST_{i:04d}" for i in range(count)]
            target_date = datetime.now().strftime('%Y-%m-%d')
            
            # 执行性能测试
            start_time = time.time()
            
            try:
                result = performance_system.screen_stocks(symbols, target_date)
                end_time = time.time()
                
                screening_time = end_time - start_time
                
                performance_results.append({
                    'stock_count': count,
                    'screening_time': screening_time,
                    'success': True,
                    'throughput': count / screening_time if screening_time > 0 else 0,
                    'qualified_count': len(result.get('qualified_stocks', []))
                })
                
                print(f"股票数量 {count:3d}: {screening_time:.4f}秒 "
                      f"(吞吐量: {count/screening_time:.1f} 股票/秒, "
                      f"符合条件: {len(result.get('qualified_stocks', []))})")
                
                # 性能要求验证
                if count <= 50:
                    assert screening_time < 30.0, f"小批量选股耗时过长: {screening_time:.4f}秒"
                elif count <= 100:
                    assert screening_time < 60.0, f"中等批量选股耗时过长: {screening_time:.4f}秒"
                else:
                    assert screening_time < 120.0, f"大批量选股耗时过长: {screening_time:.4f}秒"
                
            except Exception as e:
                performance_results.append({
                    'stock_count': count,
                    'screening_time': 0,
                    'success': False,
                    'error': str(e)
                })
                print(f"股票数量 {count:3d}: 选股失败 - {str(e)}")
        
        # 验证批量处理效率
        successful_results = [r for r in performance_results if r['success']]
        assert len(successful_results) >= len(stock_counts) * 0.8, "批量选股成功率过低"
        
        # 验证吞吐量合理性
        if successful_results:
            avg_throughput = sum(r['throughput'] for r in successful_results) / len(successful_results)
            assert avg_throughput >= 1.0, f"批量选股吞吐量过低: {avg_throughput:.2f} 股票/秒"
        
        return performance_results
    
    def test_concurrent_analysis_performance(self, performance_system):
        """测试并发分析性能"""
        print("\n=== 并发分析性能测试 ===")
        
        # 测试不同并发数的性能
        thread_counts = [1, 2, 4, 8]
        performance_results = []
        
        for thread_count in thread_counts:
            print(f"测试 {thread_count} 线程并发...")
            
            # 准备测试数据
            test_symbols = [f"CONCURRENT_{i:03d}" for i in range(thread_count * 5)]
            results_queue = []
            threads = []
            
            def worker_function(symbol_batch):
                """工作线程函数"""
                worker_results = []
                for symbol in symbol_batch:
                    try:
                        data = self._generate_performance_data(symbol, 30)
                        start_time = time.time()
                        result = performance_system.analyze_single_stock(symbol, data)
                        end_time = time.time()
                        
                        worker_results.append({
                            'symbol': symbol,
                            'success': True,
                            'time': end_time - start_time
                        })
                    except Exception as e:
                        worker_results.append({
                            'symbol': symbol,
                            'success': False,
                            'error': str(e)
                        })
                
                results_queue.extend(worker_results)
            
            # 分配任务到线程
            symbols_per_thread = len(test_symbols) // thread_count
            
            start_time = time.time()
            
            for i in range(thread_count):
                start_idx = i * symbols_per_thread
                end_idx = start_idx + symbols_per_thread
                symbol_batch = test_symbols[start_idx:end_idx]
                
                thread = threading.Thread(target=worker_function, args=(symbol_batch,))
                threads.append(thread)
                thread.start()
            
            # 等待所有线程完成
            for thread in threads:
                thread.join(timeout=60)  # 60秒超时
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # 统计结果
            successful_analyses = [r for r in results_queue if r['success']]
            failed_analyses = [r for r in results_queue if not r['success']]
            
            if successful_analyses:
                avg_analysis_time = sum(r['time'] for r in successful_analyses) / len(successful_analyses)
                total_throughput = len(successful_analyses) / total_time
            else:
                avg_analysis_time = 0
                total_throughput = 0
            
            performance_results.append({
                'thread_count': thread_count,
                'total_time': total_time,
                'successful_count': len(successful_analyses),
                'failed_count': len(failed_analyses),
                'avg_analysis_time': avg_analysis_time,
                'total_throughput': total_throughput,
                'success_rate': len(successful_analyses) / len(test_symbols) if test_symbols else 0
            })
            
            print(f"  总耗时: {total_time:.2f}秒")
            print(f"  成功分析: {len(successful_analyses)}/{len(test_symbols)}")
            print(f"  平均分析时间: {avg_analysis_time:.4f}秒")
            print(f"  总吞吐量: {total_throughput:.2f} 分析/秒")
            print(f"  成功率: {len(successful_analyses)/len(test_symbols):.1%}")
        
        # 验证并发性能
        assert len(performance_results) > 0, "并发测试没有结果"
        
        # 验证成功率
        for result in performance_results:
            assert result['success_rate'] >= 0.8, f"{result['thread_count']} 线程并发成功率过低: {result['success_rate']:.1%}"
        
        # 验证并发效率（多线程应该有性能提升）
        if len(performance_results) >= 2:
            single_thread_throughput = performance_results[0]['total_throughput']
            multi_thread_throughput = performance_results[-1]['total_throughput']
            
            if single_thread_throughput > 0:
                speedup_ratio = multi_thread_throughput / single_thread_throughput
                print(f"并发加速比: {speedup_ratio:.2f}x")
                
                # 多线程应该有一定的性能提升
                assert speedup_ratio >= 1.2, f"并发性能提升不明显: {speedup_ratio:.2f}x"
        
        return performance_results
    
    def test_memory_usage_performance(self, performance_system):
        """测试内存使用性能"""
        print("\n=== 内存使用性能测试 ===")
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        print(f"初始内存使用: {initial_memory:.2f} MB")
        
        memory_measurements = []
        
        # 执行大量分析操作
        for i in range(100):
            symbol = f"MEMORY_TEST_{i:03d}"
            
            # 生成较大的数据集
            data = self._generate_performance_data(symbol, 100)
            
            try:
                result = performance_system.analyze_single_stock(symbol, data)
                
                # 每10次操作测量一次内存
                if i % 10 == 9:
                    gc.collect()  # 强制垃圾回收
                    current_memory = process.memory_info().rss / 1024 / 1024  # MB
                    memory_growth = current_memory - initial_memory
                    
                    memory_measurements.append({
                        'iteration': i + 1,
                        'memory_mb': current_memory,
                        'growth_mb': memory_growth
                    })
                    
                    print(f"第 {i+1:3d} 次: 内存 {current_memory:.2f} MB (增长 {memory_growth:+.2f} MB)")
                    
                    # 内存增长检查
                    assert memory_growth < 200, f"内存增长过大: {memory_growth:.2f} MB"
            
            except Exception as e:
                print(f"第 {i+1} 次分析失败: {str(e)}")
        
        # 最终内存检查
        gc.collect()
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_growth = final_memory - initial_memory
        
        print(f"最终内存使用: {final_memory:.2f} MB")
        print(f"总内存增长: {total_growth:+.2f} MB")
        
        # 验证内存使用合理性
        assert total_growth < 300, f"总内存增长过大: {total_growth:.2f} MB"
        
        # 验证内存增长趋势
        if len(memory_measurements) >= 3:
            # 计算内存增长率
            growth_rates = []
            for i in range(1, len(memory_measurements)):
                prev = memory_measurements[i-1]
                curr = memory_measurements[i]
                
                iteration_diff = curr['iteration'] - prev['iteration']
                memory_diff = curr['growth_mb'] - prev['growth_mb']
                
                growth_rate = memory_diff / iteration_diff if iteration_diff > 0 else 0
                growth_rates.append(growth_rate)
            
            avg_growth_rate = sum(growth_rates) / len(growth_rates)
            print(f"平均内存增长率: {avg_growth_rate:.4f} MB/次")
            
            # 内存增长率应该很小（接近0表示没有内存泄漏）
            assert avg_growth_rate < 0.5, f"内存增长率过高，可能存在内存泄漏: {avg_growth_rate:.4f} MB/次"
        
        return memory_measurements
    
    def test_backtest_performance(self, performance_system):
        """测试回测性能"""
        print("\n=== 回测性能测试 ===")
        
        # 测试不同规模的回测性能
        test_scenarios = [
            {'symbols': 2, 'days': 90, 'name': '小规模'},
            {'symbols': 5, 'days': 180, 'name': '中等规模'},
            {'symbols': 10, 'days': 365, 'name': '大规模'}
        ]
        
        performance_results = []
        
        for scenario in test_scenarios:
            print(f"测试 {scenario['name']} 回测...")
            
            # 准备回测参数
            symbols = [f"BT_TEST_{i:03d}" for i in range(scenario['symbols'])]
            start_date = (datetime.now() - timedelta(days=scenario['days'])).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')
            initial_capital = 100000
            
            # 执行回测性能测试
            start_time = time.time()
            
            try:
                result = performance_system.run_backtest(symbols, start_date, end_date, initial_capital)
                end_time = time.time()
                
                backtest_time = end_time - start_time
                
                performance_results.append({
                    'scenario': scenario['name'],
                    'symbols': scenario['symbols'],
                    'days': scenario['days'],
                    'backtest_time': backtest_time,
                    'success': True,
                    'throughput': (scenario['symbols'] * scenario['days']) / backtest_time if backtest_time > 0 else 0
                })
                
                print(f"  耗时: {backtest_time:.2f}秒")
                print(f"  吞吐量: {(scenario['symbols'] * scenario['days']) / backtest_time:.1f} 股票·天/秒")
                
                # 性能要求验证
                if scenario['name'] == '小规模':
                    assert backtest_time < 30.0, f"小规模回测耗时过长: {backtest_time:.2f}秒"
                elif scenario['name'] == '中等规模':
                    assert backtest_time < 90.0, f"中等规模回测耗时过长: {backtest_time:.2f}秒"
                else:
                    assert backtest_time < 300.0, f"大规模回测耗时过长: {backtest_time:.2f}秒"
                
            except Exception as e:
                performance_results.append({
                    'scenario': scenario['name'],
                    'symbols': scenario['symbols'],
                    'days': scenario['days'],
                    'backtest_time': 0,
                    'success': False,
                    'error': str(e)
                })
                print(f"  回测失败: {str(e)}")
        
        # 验证回测性能
        successful_results = [r for r in performance_results if r['success']]
        assert len(successful_results) >= len(test_scenarios) * 0.8, "回测性能测试成功率过低"
        
        return performance_results
    
    def test_stress_testing(self, performance_system):
        """压力测试"""
        print("\n=== 系统压力测试 ===")
        
        # 高强度连续操作测试
        stress_duration = 30  # 30秒压力测试
        operations_count = 0
        errors_count = 0
        
        start_time = time.time()
        end_time = start_time + stress_duration
        
        print(f"开始 {stress_duration} 秒压力测试...")
        
        while time.time() < end_time:
            try:
                # 随机选择操作类型
                operation_type = random.choice(['analyze', 'screen', 'quick_analyze'])
                
                if operation_type == 'analyze':
                    # 单股分析
                    symbol = f"STRESS_{random.randint(1, 1000):04d}"
                    data = self._generate_performance_data(symbol, random.randint(20, 50))
                    result = performance_system.analyze_single_stock(symbol, data)
                
                elif operation_type == 'screen':
                    # 批量选股
                    symbols = [f"STRESS_{i:04d}" for i in range(random.randint(5, 15))]
                    target_date = datetime.now().strftime('%Y-%m-%d')
                    result = performance_system.screen_stocks(symbols, target_date)
                
                elif operation_type == 'quick_analyze':
                    # 快速分析
                    symbol = f"STRESS_{random.randint(1, 1000):04d}"
                    data = self._generate_performance_data(symbol, 25)
                    result = quick_analyze_stock(symbol, data)
                
                operations_count += 1
                
                # 每100次操作输出一次进度
                if operations_count % 100 == 0:
                    elapsed = time.time() - start_time
                    rate = operations_count / elapsed
                    print(f"  已完成 {operations_count} 次操作 (速率: {rate:.1f} 操作/秒)")
            
            except Exception as e:
                errors_count += 1
                if errors_count <= 5:  # 只打印前5个错误
                    print(f"  压力测试错误: {str(e)}")
        
        total_time = time.time() - start_time
        success_rate = (operations_count - errors_count) / operations_count if operations_count > 0 else 0
        operations_per_second = operations_count / total_time
        
        print(f"压力测试完成:")
        print(f"  总操作数: {operations_count}")
        print(f"  错误数: {errors_count}")
        print(f"  成功率: {success_rate:.1%}")
        print(f"  操作速率: {operations_per_second:.1f} 操作/秒")
        
        # 验证压力测试结果
        assert operations_count > 0, "压力测试没有完成任何操作"
        assert success_rate >= 0.9, f"压力测试成功率过低: {success_rate:.1%}"
        assert operations_per_second >= 1.0, f"压力测试操作速率过低: {operations_per_second:.1f} 操作/秒"
        
        return {
            'total_operations': operations_count,
            'errors': errors_count,
            'success_rate': success_rate,
            'operations_per_second': operations_per_second,
            'duration': total_time
        }
    
    def test_resource_cleanup_performance(self, performance_system):
        """测试资源清理性能"""
        print("\n=== 资源清理性能测试 ===")
        
        initial_threads = threading.active_count()
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        print(f"初始线程数: {initial_threads}")
        print(f"初始内存: {initial_memory:.2f} MB")
        
        # 执行大量操作
        for i in range(50):
            symbol = f"CLEANUP_TEST_{i:03d}"
            data = self._generate_performance_data(symbol, 30)
            
            try:
                result = performance_system.analyze_single_stock(symbol, data)
            except Exception as e:
                print(f"清理测试第 {i+1} 次失败: {str(e)}")
        
        # 强制垃圾回收
        gc.collect()
        
        # 等待资源清理
        time.sleep(2)
        
        final_threads = threading.active_count()
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        print(f"最终线程数: {final_threads}")
        print(f"最终内存: {final_memory:.2f} MB")
        
        thread_growth = final_threads - initial_threads
        memory_growth = final_memory - initial_memory
        
        print(f"线程增长: {thread_growth:+d}")
        print(f"内存增长: {memory_growth:+.2f} MB")
        
        # 验证资源清理
        assert thread_growth <= 2, f"线程泄漏: 增长了 {thread_growth} 个线程"
        assert memory_growth < 50, f"内存增长过大: {memory_growth:.2f} MB"
        
        return {
            'thread_growth': thread_growth,
            'memory_growth': memory_growth,
            'cleanup_effective': thread_growth <= 2 and memory_growth < 50
        }
    
    def _generate_performance_data(self, symbol: str, days: int) -> List[MarketData]:
        """生成性能测试用的市场数据"""
        data = []
        base_price = random.uniform(8, 25)
        base_volume = random.randint(500000, 2000000)
        
        for i in range(days):
            date = (datetime.now() - timedelta(days=days-i-1)).strftime('%Y-%m-%d')
            
            # 模拟价格变化
            price_change = random.uniform(-0.08, 0.10)
            base_price *= (1 + price_change)
            
            # 模拟成交量变化
            volume_change = random.uniform(-0.4, 0.6)
            volume = int(base_volume * (1 + volume_change))
            
            # 生成OHLC数据
            open_price = base_price * random.uniform(0.97, 1.03)
            close_price = base_price
            high_price = max(open_price, close_price) * random.uniform(1.0, 1.05)
            low_price = min(open_price, close_price) * random.uniform(0.95, 1.0)
            
            market_data = MarketData(
                symbol=symbol,
                date=date,
                open=round(open_price, 2),
                high=round(high_price, 2),
                low=round(low_price, 2),
                close=round(close_price, 2),
                volume=volume,
                amount=round(close_price * volume, 2)
            )
            
            data.append(market_data)
        
        return data


class TestPVFRSScalabilityValidation:
    """PVFRS策略系统可扩展性验证测试类"""
    
    def test_horizontal_scaling_simulation(self):
        """测试水平扩展模拟"""
        print("\n=== 水平扩展模拟测试 ===")
        
        # 模拟多个系统实例
        instance_counts = [1, 2, 4]
        workload_size = 100  # 总工作负载
        
        scaling_results = []
        
        for instance_count in instance_counts:
            print(f"测试 {instance_count} 个系统实例...")
            
            # 分配工作负载
            workload_per_instance = workload_size // instance_count
            
            start_time = time.time()
            
            # 模拟多实例并行处理
            def instance_worker(instance_id, workload):
                """模拟系统实例工作"""
                system = create_pvfrs_system()
                results = []
                
                for i in range(workload):
                    symbol = f"SCALE_{instance_id}_{i:03d}"
                    data = self._generate_test_data(symbol, 30)
                    
                    try:
                        result = system.analyze_single_stock(symbol, data)
                        results.append({'success': True, 'symbol': symbol})
                    except Exception as e:
                        results.append({'success': False, 'symbol': symbol, 'error': str(e)})
                
                return results
            
            # 启动多个工作进程
            with multiprocessing.Pool(processes=instance_count) as pool:
                tasks = []
                for i in range(instance_count):
                    task = pool.apply_async(instance_worker, (i, workload_per_instance))
                    tasks.append(task)
                
                # 收集结果
                all_results = []
                for task in tasks:
                    try:
                        instance_results = task.get(timeout=120)  # 2分钟超时
                        all_results.extend(instance_results)
                    except Exception as e:
                        print(f"实例任务失败: {str(e)}")
            
            end_time = time.time()
            total_time = end_time - start_time
            
            successful_count = sum(1 for r in all_results if r['success'])
            total_processed = len(all_results)
            
            scaling_results.append({
                'instance_count': instance_count,
                'total_time': total_time,
                'processed_count': total_processed,
                'successful_count': successful_count,
                'throughput': successful_count / total_time if total_time > 0 else 0,
                'success_rate': successful_count / total_processed if total_processed > 0 else 0
            })
            
            print(f"  处理时间: {total_time:.2f}秒")
            print(f"  处理数量: {successful_count}/{total_processed}")
            print(f"  吞吐量: {successful_count/total_time:.1f} 任务/秒")
            print(f"  成功率: {successful_count/total_processed:.1%}")
        
        # 验证扩展效果
        if len(scaling_results) >= 2:
            single_instance_throughput = scaling_results[0]['throughput']
            multi_instance_throughput = scaling_results[-1]['throughput']
            
            if single_instance_throughput > 0:
                scaling_efficiency = multi_instance_throughput / (single_instance_throughput * scaling_results[-1]['instance_count'])
                print(f"扩展效率: {scaling_efficiency:.1%}")
                
                # 扩展效率应该合理（考虑到开销，60%以上是可接受的）
                assert scaling_efficiency >= 0.6, f"水平扩展效率过低: {scaling_efficiency:.1%}"
        
        return scaling_results
    
    def _generate_test_data(self, symbol: str, days: int) -> List[MarketData]:
        """生成测试数据"""
        data = []
        base_price = 10.0
        
        for i in range(days):
            date = (datetime.now() - timedelta(days=days-i-1)).strftime('%Y-%m-%d')
            
            market_data = MarketData(
                symbol=symbol,
                date=date,
                open=base_price,
                high=base_price * 1.02,
                low=base_price * 0.98,
                close=base_price,
                volume=1000000,
                amount=base_price * 1000000
            )
            data.append(market_data)
        
        return data


if __name__ == "__main__":
    # 运行性能验证测试
    pytest.main([__file__, "-v", "--tb=short", "-s"])