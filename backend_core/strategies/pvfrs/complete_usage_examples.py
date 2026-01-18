#!/usr/bin/env python3
"""
PVFRS策略系统完整使用示例
展示在实际投资场景中如何使用PVFRS系统进行股票分析、选股和投资决策
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from datetime import datetime, timedelta
from typing import List, Dict, Optional
import random
import json
import pandas as pd

from backend_core.strategies.pvfrs import MarketData, SignalType
from backend_core.strategies.pvfrs.pvfrs_system import (
    PVFRSSystem, create_pvfrs_system, quick_analyze_stock, quick_screen_stocks
)


class PVFRSUsageExamples:
    """PVFRS策略系统使用示例类"""
    
    def __init__(self):
        """初始化示例系统"""
        self.system = create_pvfrs_system()
        self.sample_stocks = [
            "000001", "000002", "000858", "002415", "300059",
            "600036", "600519", "000858", "002304", "300750"
        ]
    
    def example_1_quick_stock_analysis(self):
        """示例1: 快速单股分析"""
        print("=" * 60)
        print("示例1: 快速单股分析")
        print("=" * 60)
        
        # 1. 准备股票数据
        symbol = "000001"
        print(f"分析股票: {symbol} (平安银行)")
        
        # 生成示例数据（实际使用中应该从数据源获取）
        market_data = self._generate_realistic_data(symbol, 30)
        
        try:
            # 2. 执行快速分析
            print("正在执行PVFRS分析...")
            result = quick_analyze_stock(symbol, market_data)
            
            # 3. 解读分析结果
            print(f"\n📊 分析结果:")
            print(f"   综合评分: {result['overall_score']:.2f}/1.00")
            
            advice = result['investment_advice']
            print(f"   投资建议: {advice['recommendation']}")
            print(f"   信心度: {advice['confidence']:.1%}")
            print(f"   风险等级: {advice['risk_level']}")
            print(f"   建议仓位: {advice['suggested_position_size']:.1%}")
            
            # 4. 详细分析解读
            if 'strategy_analysis' in result:
                strategy = result['strategy_analysis']['strategy_assessment']
                print(f"\n🔍 策略分析:")
                print(f"   三维共振: {'✓' if strategy['three_dimension_resonance'] else '✗'}")
                print(f"   买入信号: {'✓' if strategy['has_buy_signal'] else '✗'}")
                print(f"   高效轨道: {'✓' if strategy['high_efficiency_trajectory'] else '✗'}")
                print(f"   信号强度: {strategy['max_signal_strength']:.2f}")
            
            # 5. 投资建议解读
            print(f"\n💡 投资建议解读:")
            if advice['recommendation'] == 'BUY':
                print("   🟢 建议买入")
                print(f"   理由: {', '.join(advice['reasons'])}")
                print(f"   建议在价格 {market_data[-1].close:.2f} 附近分批买入")
            elif advice['recommendation'] == 'HOLD':
                print("   🟡 建议持有观望")
                print(f"   理由: {', '.join(advice['reasons'])}")
            else:
                print("   🔴 建议回避或卖出")
                print(f"   理由: {', '.join(advice['reasons'])}")
            
            return True
            
        except Exception as e:
            print(f"❌ 分析失败: {str(e)}")
            return False
    
    def example_2_batch_stock_screening(self):
        """示例2: 批量股票筛选"""
        print("\n" + "=" * 60)
        print("示例2: 批量股票筛选")
        print("=" * 60)
        
        print(f"筛选股票池: {self.sample_stocks}")
        target_date = datetime.now().strftime('%Y-%m-%d')
        print(f"筛选日期: {target_date}")
        
        try:
            # 1. 执行批量筛选
            print("\n正在执行批量筛选...")
            result = quick_screen_stocks(self.sample_stocks, target_date)
            
            # 2. 显示筛选统计
            stats = result['screening_stats']
            print(f"\n📈 筛选统计:")
            print(f"   输入股票: {stats['total_input']} 只")
            print(f"   数据可用: {stats['data_available']} 只")
            print(f"   分析完成: {stats['analysis_completed']} 只")
            print(f"   符合条件: {stats['qualified_count']} 只")
            print(f"   成功率: {stats['success_rate']:.1%}")
            print(f"   通过率: {stats['qualification_rate']:.1%}")
            
            # 3. 显示符合条件的股票
            qualified_stocks = result['qualified_stocks']
            if qualified_stocks:
                print(f"\n🎯 符合条件的股票 (前5只):")
                for i, stock in enumerate(qualified_stocks[:5], 1):
                    signal = stock['signal']
                    print(f"   {i}. {stock['symbol']}")
                    print(f"      信号强度: {signal['strength']:.2f}")
                    print(f"      当前价格: {signal['price']:.2f}")
                    print(f"      信号原因: {signal['reason']}")
                    print()
            else:
                print(f"\n⚠️  当前没有股票符合PVFRS条件")
                print("   建议:")
                print("   - 扩大股票池范围")
                print("   - 调整筛选参数")
                print("   - 等待更好的市场时机")
            
            # 4. 维度分析
            dimension_summary = result['dimension_summary']
            print(f"📊 各维度通过情况:")
            rates = dimension_summary['dimension_pass_rates']
            print(f"   价格维度通过率: {rates['price']:.1%}")
            print(f"   频率维度通过率: {rates['frequency']:.1%}")
            print(f"   成交量维度通过率: {rates['volume']:.1%}")
            print(f"   三维共振通过率: {rates['three_dimension']:.1%}")
            
            return qualified_stocks
            
        except Exception as e:
            print(f"❌ 筛选失败: {str(e)}")
            return []
    
    def example_3_portfolio_construction(self, qualified_stocks: List[Dict]):
        """示例3: 投资组合构建"""
        print("\n" + "=" * 60)
        print("示例3: 投资组合构建")
        print("=" * 60)
        
        if not qualified_stocks:
            print("⚠️  没有符合条件的股票，无法构建投资组合")
            return None
        
        # 1. 设定投资参数
        total_capital = 100000  # 总资金10万
        max_positions = 5       # 最多持有5只股票
        max_single_position = 0.3  # 单只股票最大仓位30%
        
        print(f"💰 投资参数:")
        print(f"   总资金: {total_capital:,} 元")
        print(f"   最大持仓数: {max_positions} 只")
        print(f"   单只最大仓位: {max_single_position:.0%}")
        
        # 2. 选择投资标的
        selected_stocks = qualified_stocks[:max_positions]
        print(f"\n🎯 选择投资标的:")
        
        portfolio = []
        remaining_capital = total_capital
        
        for i, stock in enumerate(selected_stocks):
            signal = stock['signal']
            
            # 根据信号强度分配仓位
            base_weight = 1.0 / len(selected_stocks)  # 基础权重
            strength_multiplier = signal['strength']   # 信号强度调整
            
            # 计算调整后权重
            adjusted_weight = base_weight * (0.5 + 0.5 * strength_multiplier)
            position_size = min(adjusted_weight, max_single_position)
            
            # 计算投资金额
            investment_amount = total_capital * position_size
            shares = int(investment_amount / signal['price'] / 100) * 100  # 按手数计算
            actual_investment = shares * signal['price']
            
            if actual_investment <= remaining_capital and shares > 0:
                portfolio_item = {
                    'symbol': stock['symbol'],
                    'price': signal['price'],
                    'shares': shares,
                    'investment': actual_investment,
                    'weight': actual_investment / total_capital,
                    'signal_strength': signal['strength'],
                    'reason': signal['reason']
                }
                portfolio.append(portfolio_item)
                remaining_capital -= actual_investment
                
                print(f"   {i+1}. {stock['symbol']}")
                print(f"      买入价格: {signal['price']:.2f}")
                print(f"      买入股数: {shares:,} 股")
                print(f"      投资金额: {actual_investment:,.0f} 元")
                print(f"      仓位占比: {portfolio_item['weight']:.1%}")
                print(f"      信号强度: {signal['strength']:.2f}")
                print()
        
        # 3. 投资组合总结
        total_invested = sum(item['investment'] for item in portfolio)
        cash_remaining = total_capital - total_invested
        
        print(f"📋 投资组合总结:")
        print(f"   总投资金额: {total_invested:,.0f} 元")
        print(f"   剩余现金: {cash_remaining:,.0f} 元")
        print(f"   资金使用率: {total_invested/total_capital:.1%}")
        print(f"   持仓股票数: {len(portfolio)} 只")
        
        return portfolio
    
    def example_4_risk_management_setup(self, portfolio: List[Dict]):
        """示例4: 风险管理设置"""
        print("\n" + "=" * 60)
        print("示例4: 风险管理设置")
        print("=" * 60)
        
        if not portfolio:
            print("⚠️  没有投资组合，无法设置风险管理")
            return None
        
        # 1. 获取当前风险管理配置
        config = self.system.config_manager.get_current_config()
        
        print(f"🛡️  当前风险管理配置:")
        print(f"   止损线: {config['stop_loss']:.1%}")
        print(f"   止盈线: {config['take_profit']:.1%}")
        print(f"   最大持有期: {config['max_holding_days']} 天")
        print(f"   最大仓位: {config['max_position_size']:.1%}")
        
        # 2. 为每只股票设置具体的风险管理参数
        print(f"\n📊 各股票风险管理参数:")
        
        risk_management_plan = []
        
        for item in portfolio:
            symbol = item['symbol']
            buy_price = item['price']
            signal_strength = item['signal_strength']
            
            # 根据信号强度调整风险参数
            if signal_strength >= 0.8:
                # 高信号强度：相对宽松的止损，较高的止盈
                stop_loss_pct = -0.08
                take_profit_pct = 0.25
                max_holding = 30
            elif signal_strength >= 0.6:
                # 中等信号强度：标准风险参数
                stop_loss_pct = -0.06
                take_profit_pct = 0.20
                max_holding = 20
            else:
                # 低信号强度：较严格的止损
                stop_loss_pct = -0.05
                take_profit_pct = 0.15
                max_holding = 15
            
            stop_loss_price = buy_price * (1 + stop_loss_pct)
            take_profit_price = buy_price * (1 + take_profit_pct)
            
            risk_item = {
                'symbol': symbol,
                'buy_price': buy_price,
                'stop_loss_price': stop_loss_price,
                'take_profit_price': take_profit_price,
                'stop_loss_pct': stop_loss_pct,
                'take_profit_pct': take_profit_pct,
                'max_holding_days': max_holding,
                'signal_strength': signal_strength
            }
            
            risk_management_plan.append(risk_item)
            
            print(f"   {symbol}:")
            print(f"      买入价格: {buy_price:.2f}")
            print(f"      止损价格: {stop_loss_price:.2f} ({stop_loss_pct:.1%})")
            print(f"      止盈价格: {take_profit_price:.2f} ({take_profit_pct:.1%})")
            print(f"      最大持有: {max_holding} 天")
            print(f"      信号强度: {signal_strength:.2f}")
            print()
        
        # 3. 整体风险控制建议
        print(f"🎯 整体风险控制建议:")
        print(f"   1. 严格执行止损止盈纪律")
        print(f"   2. 定期检查持仓股票的PVFRS信号变化")
        print(f"   3. 市场环境恶化时及时减仓")
        print(f"   4. 单日最大亏损不超过总资金的2%")
        print(f"   5. 连续亏损3次后暂停交易，重新评估策略")
        
        return risk_management_plan
    
    def example_5_backtest_validation(self):
        """示例5: 回测验证"""
        print("\n" + "=" * 60)
        print("示例5: 回测验证")
        print("=" * 60)
        
        # 1. 设置回测参数
        symbols = self.sample_stocks[:3]  # 选择3只股票进行回测
        start_date = "2024-01-01"
        end_date = "2024-12-31"
        initial_capital = 100000
        
        print(f"📈 回测参数:")
        print(f"   回测股票: {symbols}")
        print(f"   回测期间: {start_date} - {end_date}")
        print(f"   初始资金: {initial_capital:,} 元")
        
        try:
            # 2. 执行回测
            print(f"\n正在执行回测...")
            backtest_result = self.system.run_backtest(symbols, start_date, end_date, initial_capital)
            
            # 3. 显示回测结果
            result = backtest_result['backtest_result']
            
            print(f"\n📊 回测结果:")
            print(f"   最终资金: {result['final_capital']:,.0f} 元")
            print(f"   总收益: {result['final_capital'] - result['initial_capital']:+,.0f} 元")
            print(f"   总收益率: {result['total_return']:+.1%}")
            print(f"   年化收益率: {result['annual_return']:+.1%}")
            print(f"   最大回撤: {result['max_drawdown']:.1%}")
            print(f"   夏普比率: {result['sharpe_ratio']:.2f}")
            
            # 4. 交易统计
            print(f"\n📋 交易统计:")
            print(f"   总交易次数: {result['total_trades']}")
            print(f"   盈利交易: {result['winning_trades']}")
            print(f"   亏损交易: {result['losing_trades']}")
            print(f"   胜率: {result['win_rate']:.1%}")
            print(f"   盈亏比: {result['profit_factor']:.2f}")
            print(f"   平均持有期: {result['avg_holding_period']:.1f} 天")
            
            # 5. 回测结果评价
            print(f"\n💡 回测结果评价:")
            
            if result['total_return'] > 0.15:  # 年化收益率超过15%
                print("   🟢 策略表现优秀")
            elif result['total_return'] > 0.08:  # 年化收益率超过8%
                print("   🟡 策略表现良好")
            else:
                print("   🔴 策略表现需要改进")
            
            if result['max_drawdown'] > -0.20:  # 最大回撤小于20%
                print("   🟢 风险控制良好")
            elif result['max_drawdown'] > -0.35:
                print("   🟡 风险控制一般")
            else:
                print("   🔴 风险控制需要加强")
            
            if result['sharpe_ratio'] > 1.0:
                print("   🟢 风险调整收益优秀")
            elif result['sharpe_ratio'] > 0.5:
                print("   🟡 风险调整收益良好")
            else:
                print("   🔴 风险调整收益需要改进")
            
            return backtest_result
            
        except Exception as e:
            print(f"❌ 回测失败: {str(e)}")
            return None
    
    def example_6_parameter_optimization(self):
        """示例6: 参数优化"""
        print("\n" + "=" * 60)
        print("示例6: 参数优化")
        print("=" * 60)
        
        # 1. 定义参数优化范围
        param_ranges = {
            'stop_loss': [-0.05, -0.08, -0.10, -0.12],
            'take_profit': [0.15, 0.20, 0.25, 0.30],
            'max_position_size': [0.10, 0.15, 0.20, 0.25]
        }
        
        print(f"🔧 参数优化范围:")
        for param, values in param_ranges.items():
            print(f"   {param}: {values}")
        
        # 2. 执行参数优化
        print(f"\n正在执行参数优化...")
        
        best_config = None
        best_score = -float('inf')
        optimization_results = []
        
        original_config = self.system.config_manager.get_current_config()
        
        try:
            # 简化的网格搜索
            for stop_loss in param_ranges['stop_loss']:
                for take_profit in param_ranges['take_profit']:
                    for max_pos in param_ranges['max_position_size']:
                        
                        # 更新配置
                        test_config = {
                            'stop_loss': stop_loss,
                            'take_profit': take_profit,
                            'max_position_size': max_pos
                        }
                        
                        self.system.update_config(test_config)
                        
                        # 执行简化回测
                        try:
                            backtest_result = self.system.run_backtest(
                                self.sample_stocks[:2], 
                                "2024-06-01", 
                                "2024-12-31", 
                                50000
                            )
                            
                            result = backtest_result['backtest_result']
                            
                            # 计算综合评分 (收益率 - 回撤惩罚)
                            score = result['total_return'] - abs(result['max_drawdown']) * 0.5
                            
                            optimization_results.append({
                                'config': test_config.copy(),
                                'score': score,
                                'return': result['total_return'],
                                'drawdown': result['max_drawdown'],
                                'sharpe': result['sharpe_ratio']
                            })
                            
                            if score > best_score:
                                best_score = score
                                best_config = test_config.copy()
                        
                        except Exception as e:
                            print(f"   配置 {test_config} 测试失败: {str(e)}")
            
            # 3. 显示优化结果
            if optimization_results:
                # 排序结果
                optimization_results.sort(key=lambda x: x['score'], reverse=True)
                
                print(f"\n🏆 参数优化结果 (前5名):")
                for i, result in enumerate(optimization_results[:5], 1):
                    config = result['config']
                    print(f"   {i}. 评分: {result['score']:.3f}")
                    print(f"      止损: {config['stop_loss']:.1%}")
                    print(f"      止盈: {config['take_profit']:.1%}")
                    print(f"      仓位: {config['max_position_size']:.1%}")
                    print(f"      收益率: {result['return']:+.1%}")
                    print(f"      回撤: {result['drawdown']:.1%}")
                    print(f"      夏普: {result['sharpe']:.2f}")
                    print()
                
                # 4. 应用最佳配置
                if best_config:
                    print(f"🎯 建议使用最佳配置:")
                    print(f"   止损线: {best_config['stop_loss']:.1%}")
                    print(f"   止盈线: {best_config['take_profit']:.1%}")
                    print(f"   最大仓位: {best_config['max_position_size']:.1%}")
                    
                    # 应用最佳配置
                    self.system.update_config(best_config)
                    print(f"   ✓ 已应用最佳配置")
            
            else:
                print(f"❌ 参数优化失败，没有有效结果")
        
        finally:
            # 如果没有找到更好的配置，恢复原始配置
            if not best_config:
                self.system.config_manager.config = original_config
        
        return optimization_results
    
    def example_7_monitoring_and_alerts(self):
        """示例7: 监控和预警"""
        print("\n" + "=" * 60)
        print("示例7: 监控和预警")
        print("=" * 60)
        
        # 1. 设置监控股票池
        monitor_symbols = self.sample_stocks[:5]
        print(f"📡 监控股票池: {monitor_symbols}")
        
        # 2. 执行实时监控
        print(f"\n正在执行实时监控...")
        
        alerts = []
        
        for symbol in monitor_symbols:
            try:
                # 生成最新数据
                latest_data = self._generate_realistic_data(symbol, 25)
                
                # 执行分析
                result = self.system.analyze_single_stock(symbol, latest_data)
                
                # 检查预警条件
                advice = result['investment_advice']
                score = result['overall_score']
                
                # 买入信号预警
                if advice['recommendation'] == 'BUY' and advice['confidence'] >= 0.7:
                    alerts.append({
                        'type': 'BUY_SIGNAL',
                        'symbol': symbol,
                        'message': f'{symbol} 出现强烈买入信号',
                        'score': score,
                        'confidence': advice['confidence'],
                        'price': latest_data[-1].close
                    })
                
                # 高分股票预警
                elif score >= 0.8:
                    alerts.append({
                        'type': 'HIGH_SCORE',
                        'symbol': symbol,
                        'message': f'{symbol} 获得高评分',
                        'score': score,
                        'confidence': advice['confidence'],
                        'price': latest_data[-1].close
                    })
                
                # 风险预警
                elif advice['recommendation'] == 'SELL':
                    alerts.append({
                        'type': 'RISK_WARNING',
                        'symbol': symbol,
                        'message': f'{symbol} 出现风险信号',
                        'score': score,
                        'confidence': advice['confidence'],
                        'price': latest_data[-1].close
                    })
            
            except Exception as e:
                alerts.append({
                    'type': 'ERROR',
                    'symbol': symbol,
                    'message': f'{symbol} 分析失败: {str(e)}',
                    'score': 0,
                    'confidence': 0,
                    'price': 0
                })
        
        # 3. 显示预警信息
        if alerts:
            print(f"\n🚨 预警信息:")
            
            for alert in alerts:
                if alert['type'] == 'BUY_SIGNAL':
                    print(f"   🟢 {alert['message']}")
                    print(f"      评分: {alert['score']:.2f}")
                    print(f"      信心度: {alert['confidence']:.1%}")
                    print(f"      当前价格: {alert['price']:.2f}")
                    print(f"      建议: 考虑买入")
                
                elif alert['type'] == 'HIGH_SCORE':
                    print(f"   🟡 {alert['message']}")
                    print(f"      评分: {alert['score']:.2f}")
                    print(f"      当前价格: {alert['price']:.2f}")
                    print(f"      建议: 密切关注")
                
                elif alert['type'] == 'RISK_WARNING':
                    print(f"   🔴 {alert['message']}")
                    print(f"      评分: {alert['score']:.2f}")
                    print(f"      当前价格: {alert['price']:.2f}")
                    print(f"      建议: 考虑减仓或卖出")
                
                elif alert['type'] == 'ERROR':
                    print(f"   ⚠️  {alert['message']}")
                
                print()
        else:
            print(f"\n✅ 当前没有预警信息")
        
        # 4. 监控建议
        print(f"📋 监控建议:")
        print(f"   1. 每日收盘后执行监控分析")
        print(f"   2. 关注买入信号的及时性")
        print(f"   3. 重视风险预警，及时止损")
        print(f"   4. 定期更新监控股票池")
        print(f"   5. 结合市场环境调整预警阈值")
        
        return alerts
    
    def _generate_realistic_data(self, symbol: str, days: int) -> List[MarketData]:
        """生成逼真的市场数据"""
        data = []
        
        # 根据股票代码设置不同的基础参数
        if symbol.startswith('000'):
            base_price = random.uniform(8, 15)
            base_volume = random.randint(800000, 1500000)
            volatility = 0.03
        elif symbol.startswith('002'):
            base_price = random.uniform(15, 30)
            base_volume = random.randint(600000, 1200000)
            volatility = 0.04
        elif symbol.startswith('300'):
            base_price = random.uniform(20, 50)
            base_volume = random.randint(400000, 800000)
            volatility = 0.05
        else:
            base_price = random.uniform(10, 25)
            base_volume = random.randint(1000000, 2000000)
            volatility = 0.035
        
        # 生成趋势方向
        trend_direction = random.choice(['up', 'down', 'sideways'])
        
        for i in range(days):
            date = (datetime.now() - timedelta(days=days-i-1)).strftime('%Y-%m-%d')
            
            # 根据趋势生成价格变化
            if trend_direction == 'up':
                base_change = random.uniform(0.005, 0.025)
            elif trend_direction == 'down':
                base_change = random.uniform(-0.025, -0.005)
            else:
                base_change = random.uniform(-0.015, 0.015)
            
            # 添加随机波动
            price_change = base_change + random.uniform(-volatility, volatility)
            base_price *= (1 + price_change)
            
            # 生成成交量
            volume_change = random.uniform(-0.3, 0.4)
            volume = int(base_volume * (1 + volume_change))
            
            # 生成OHLC
            open_price = base_price * random.uniform(0.995, 1.005)
            close_price = base_price
            high_price = max(open_price, close_price) * random.uniform(1.0, 1.02)
            low_price = min(open_price, close_price) * random.uniform(0.98, 1.0)
            
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


def main():
    """主函数：运行所有使用示例"""
    print("PVFRS策略系统完整使用示例")
    print("=" * 80)
    print("本示例将展示PVFRS系统在实际投资场景中的完整应用流程")
    print("包括：股票分析、批量筛选、组合构建、风险管理、回测验证等")
    print("=" * 80)
    
    try:
        # 创建示例实例
        examples = PVFRSUsageExamples()
        
        # 运行所有示例
        print("\n🚀 开始运行使用示例...")
        
        # 示例1: 快速单股分析
        success1 = examples.example_1_quick_stock_analysis()
        
        # 示例2: 批量股票筛选
        qualified_stocks = examples.example_2_batch_stock_screening()
        
        # 示例3: 投资组合构建
        portfolio = examples.example_3_portfolio_construction(qualified_stocks)
        
        # 示例4: 风险管理设置
        risk_plan = examples.example_4_risk_management_setup(portfolio)
        
        # 示例5: 回测验证
        backtest_result = examples.example_5_backtest_validation()
        
        # 示例6: 参数优化
        optimization_results = examples.example_6_parameter_optimization()
        
        # 示例7: 监控和预警
        alerts = examples.example_7_monitoring_and_alerts()
        
        # 总结
        print("\n" + "=" * 80)
        print("🎉 PVFRS策略系统使用示例完成！")
        print("=" * 80)
        
        print(f"✅ 完成的示例:")
        print(f"   1. 快速单股分析: {'成功' if success1 else '失败'}")
        print(f"   2. 批量股票筛选: {'成功' if qualified_stocks else '失败'}")
        print(f"   3. 投资组合构建: {'成功' if portfolio else '失败'}")
        print(f"   4. 风险管理设置: {'成功' if risk_plan else '失败'}")
        print(f"   5. 回测验证: {'成功' if backtest_result else '失败'}")
        print(f"   6. 参数优化: {'成功' if optimization_results else '失败'}")
        print(f"   7. 监控和预警: {'成功' if alerts is not None else '失败'}")
        
        print(f"\n💡 使用建议:")
        print(f"   1. 在实际使用中，请连接真实的数据源")
        print(f"   2. 根据个人风险偏好调整参数配置")
        print(f"   3. 定期进行回测验证和参数优化")
        print(f"   4. 严格执行风险管理纪律")
        print(f"   5. 结合基本面分析进行最终决策")
        
        print(f"\n🔗 相关文档:")
        print(f"   - 系统设计文档: design.md")
        print(f"   - 需求规格文档: requirements.md")
        print(f"   - 配置说明文档: CONFIG_DATA_README.md")
        print(f"   - 策略引擎文档: STRATEGY_ENGINE_README.md")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 示例运行失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)