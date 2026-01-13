"""
PVFRS策略主回测执行脚本
提供命令行接口，支持批量回测和参数优化
"""

import argparse
import sys
import os
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend_core.strategies.pvfrs_strategy import (
    PVFRSStrategy, PVFRSBacktestEngine, SignalType
)
from backend_core.strategies.pvfrs_data_loader import (
    PVFRSDataLoader, load_pvfrs_data, get_pvfrs_stocks
)
from backend_core.strategies.pvfrs_performance_analyzer import (
    PVFRSPerformanceAnalyzer, PVFRSReportGenerator,
    analyze_pvfrs_performance, generate_pvfrs_report
)
from backend_api.database import get_db

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PVFRSBacktestRunner:
    """PVFRS策略回测运行器"""
    
    def __init__(self):
        self.results = []
    
    def run_single_backtest(
        self, 
        code: str, 
        market_type: str, 
        start_date: str, 
        end_date: str,
        params: Dict = None,
        initial_capital: float = 100000
    ) -> Dict:
        """运行单个股票的回测"""
        logger.info(f"开始回测股票: {code} ({market_type})")
        
        try:
            # 加载数据
            data = load_pvfrs_data(code, market_type, start_date, end_date)
            
            if data.empty:
                logger.warning(f"股票 {code} 没有足够的数据，跳过回测")
                return None
            
            # 创建策略
            strategy = PVFRSStrategy(params)
            
            # 创建回测引擎
            engine = PVFRSBacktestEngine(strategy, initial_capital)
            
            # 运行回测
            result = engine.run_backtest(data)
            
            # 添加股票信息
            result.stock_code = code
            result.market_type = market_type
            result.data_range = f"{start_date} 到 {end_date}"
            
            logger.info(f"股票 {code} 回测完成，总收益率: {result.total_return:.2%}")
            
            return result
            
        except Exception as e:
            logger.error(f"回测股票 {code} 失败: {e}")
            return None
    
    def run_batch_backtest(
        self, 
        stock_codes: List[str], 
        market_type: str, 
        start_date: str, 
        end_date: str,
        params: Dict = None,
        initial_capital: float = 100000
    ) -> List[Dict]:
        """批量回测多个股票"""
        logger.info(f"开始批量回测，股票数量: {len(stock_codes)}")
        
        results = []
        
        for i, code in enumerate(stock_codes, 1):
            logger.info(f"处理进度: {i}/{len(stock_codes)} - {code}")
            
            result = self.run_single_backtest(
                code, market_type, start_date, end_date, params, initial_capital
            )
            
            if result:
                results.append(result)
            
            # 添加延迟避免请求过于频繁
            if i % 10 == 0:
                logger.info(f"已处理 {i} 只股票，暂停1秒...")
                import time
                time.sleep(1)
        
        logger.info(f"批量回测完成，有效结果: {len(results)} 个")
        return results
    
    def run_parameter_optimization(
        self,
        code: str,
        market_type: str,
        start_date: str,
        end_date: str,
        param_grid: Dict = None
    ) -> Dict:
        """参数优化"""
        logger.info(f"开始参数优化: {code}")
        
        if param_grid is None:
            param_grid = self._get_default_param_grid()
        
        best_result = None
        best_score = -float('inf')
        optimization_log = []
        
        total_combinations = 1
        for key, values in param_grid.items():
            total_combinations *= len(values)
        
        logger.info(f"参数组合总数: {total_combinations}")
        
        combination_count = 0
        for buy_bias in param_grid.get('buy_bias_min', [0.02]):
            for sell_bias in param_grid.get('sell_bias_max', [0.08]):
                for stop_loss in param_grid.get('stop_loss', [-0.10]):
                    for take_profit in param_grid.get('take_profit', [0.20]):
                        
                        combination_count += 1
                        logger.info(f"测试参数组合 {combination_count}/{total_combinations}")
                        
                        # 构建参数
                        test_params = {
                            'buy_bias_min': buy_bias,
                            'sell_bias_max': sell_bias,
                            'stop_loss': stop_loss,
                            'take_profit': take_profit
                        }
                        
                        # 运行回测
                        result = self.run_single_backtest(
                            code, market_type, start_date, end_date, test_params
                        )
                        
                        if result:
                            # 计算综合评分
                            analyzer = PVFRSPerformanceAnalyzer()
                            metrics = analyzer.calculate_comprehensive_metrics(result)
                            score = metrics.get('composite_score', 0)
                            
                            optimization_log.append({
                                'params': test_params.copy(),
                                'score': score,
                                'total_return': result.total_return,
                                'sharpe_ratio': metrics.get('sharpe_ratio', 0),
                                'max_drawdown': metrics.get('max_drawdown', 0)
                            })
                            
                            if score > best_score:
                                best_score = score
                                best_result = result
                                best_params = test_params.copy()
        
        optimization_result = {
            'best_result': best_result,
            'best_params': best_params,
            'best_score': best_score,
            'optimization_log': optimization_log
        }
        
        logger.info(f"参数优化完成，最佳评分: {best_score:.2f}")
        
        return optimization_result
    
    def _get_default_param_grid(self) -> Dict:
        """获取默认参数网格"""
        return {
            'buy_bias_min': [0.01, 0.02, 0.03],
            'sell_bias_max': [0.06, 0.08, 0.10],
            'stop_loss': [-0.05, -0.10, -0.15],
            'take_profit': [0.15, 0.20, 0.25]
        }
    
    def generate_batch_report(self, results: List[Dict], output_path: str = None) -> str:
        """生成批量回测报告"""
        if not results:
            return "没有有效的回测结果"
        
        # 统计信息
        total_stocks = len(results)
        profitable_stocks = len([r for r in results if r.total_return > 0])
        avg_return = sum([r.total_return for r in results]) / total_stocks
        max_return = max([r.total_return for r in results])
        min_return = min([r.total_return for r in results])
        
        # 按收益率排序
        sorted_results = sorted(results, key=lambda x: x.total_return, reverse=True)
        
        report = f"""
# PVFRS策略批量回测报告

## 总体统计
- 测试股票数量: {total_stocks}
- 盈利股票数量: {profitable_stocks}
- 盈利率: {profitable_stocks/total_stocks:.2%}
- 平均收益率: {avg_return:.2%}
- 最高收益率: {max_return:.2%}
- 最低收益率: {min_return:.2%}

## 收益分布
- 前10%平均收益率: {sum([r.total_return for r in sorted_results[:int(total_stocks*0.1)]]) / min(int(total_stocks*0.1), total_stocks):.2%}
- 前25%平均收益率: {sum([r.total_return for r in sorted_results[:int(total_stocks*0.25)]]) / min(int(total_stocks*0.25), total_stocks):.2%}
- 后25%平均收益率: {sum([r.total_return for r in sorted_results[-int(total_stocks*0.25):]]) / max(int(total_stocks*0.25), 1):.2%}

## 详细结果
| 排名 | 股票代码 | 市场类型 | 总收益率 | 年化收益率 | 最大回撤 | 夏普比率 | 交易次数 | 胜率 |
|------|----------|----------|----------|----------|----------|----------|----------|----------|
"""
        
        for i, result in enumerate(sorted_results, 1):
            analyzer = PVFRSPerformanceAnalyzer()
            metrics = analyzer.calculate_comprehensive_metrics(result)
            
            report += f"| {i} | {result.stock_code} | {result.market_type} | {result.total_return:.2%} | {metrics.get('annual_return', 0):.2%} | {metrics.get('max_drawdown', 0):.2%} | {metrics.get('sharpe_ratio', 0):.2f} | {metrics.get('total_trades', 0)} | {metrics.get('win_rate', 0):.2%} |\n"
        
        # 添加策略建议
        report += f"""
## 策略建议
{self._generate_batch_recommendations(results)}
"""
        
        # 保存报告
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"批量报告已保存到: {output_path}")
        
        return report
    
    def _generate_batch_recommendations(self, results: List[Dict]) -> str:
        """生成批量回测建议"""
        if not results:
            return "- 无有效结果"
        
        recommendations = []
        
        # 分析整体表现
        avg_return = sum([r.total_return for r in results]) / len(results)
        profitable_rate = len([r for r in results if r.total_return > 0]) / len(results)
        
        if avg_return < 0:
            recommendations.append("- 整体平均收益为负，建议重新评估策略逻辑")
        elif profitable_rate < 0.5:
            recommendations.append("- 盈利率低于50%，建议增加过滤条件")
        
        # 分析风险
        avg_drawdown = sum([abs(r.max_drawdown or 0) for r in results]) / len(results)
        if avg_drawdown > 0.15:
            recommendations.append("- 平均回撤较大，建议加强风险控制")
        
        # 分析交易频率
        avg_trades = sum([r.total_trades for r in results]) / len(results)
        if avg_trades < 5:
            recommendations.append("- 交易频率偏低，可能错过机会")
        elif avg_trades > 50:
            recommendations.append("- 交易频率偏高，建议增加信号过滤")
        
        return "\n".join(recommendations) if recommendations else "- 策略整体表现良好"

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='PVFRS策略回测系统')
    parser.add_argument('--mode', choices=['single', 'batch', 'optimize'], 
                       required=True, help='运行模式')
    parser.add_argument('--code', type=str, help='股票代码（single模式）')
    parser.add_argument('--market', type=str, choices=['CN', 'HK'], 
                       default='CN', help='市场类型')
    parser.add_argument('--start-date', type=str, required=True, 
                       help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, required=True, 
                       help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--initial-capital', type=float, default=None, 
                       help='初始资金')
    parser.add_argument('--output', type=str, help='输出文件路径')
    parser.add_argument('--stocks-file', type=str, help='股票列表文件路径')
    parser.add_argument('--params-file', type=str, help='参数配置文件路径')
    
    args = parser.parse_args()
    
    # 创建回测运行器
    runner = PVFRSBacktestRunner()
    
    # 加载自定义参数
    custom_params = {}
    backtest_config = {}
    if args.params_file and os.path.exists(args.params_file):
        with open(args.params_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 兼容两种格式：
        # 1) 分层结构（推荐）：{"strategy_params": {...}, ...}
        # 2) 扁平结构：{"buy_bias_min": 0.02, ...}
        if isinstance(config, dict) and isinstance(config.get('strategy_params'), dict):
            custom_params = config.get('strategy_params', {})
            backtest_config = config.get('backtest_config', {}) if isinstance(config.get('backtest_config'), dict) else {}
        elif isinstance(config, dict):
            custom_params = config
            backtest_config = {}
        else:
            custom_params = {}
            backtest_config = {}
        logger.info(f"加载自定义参数: {custom_params}")

    # 初始资金优先级：命令行 > 配置文件 backtest_config.initial_capital > 默认值 100000
    initial_capital = args.initial_capital
    if initial_capital is None:
        config_initial = backtest_config.get('initial_capital') if isinstance(backtest_config, dict) else None
        initial_capital = float(config_initial) if config_initial is not None else 100000.0
    
    try:
        if args.mode == 'single':
            # 单股票回测
            if not args.code:
                logger.error("single模式需要指定--code参数")
                return
            
            result = runner.run_single_backtest(
                args.code, args.market, args.start_date, args.end_date,
                custom_params, initial_capital
            )
            
            if result:
                # 生成详细报告
                report = generate_pvfrs_report(result, args.output)
                print(report)
            else:
                logger.error("回测失败，没有有效结果")
        
        elif args.mode == 'batch':
            # 批量回测
            stock_codes = []
            
            if args.stocks_file and os.path.exists(args.stocks_file):
                # 从文件读取股票列表
                with open(args.stocks_file, 'r', encoding='utf-8') as f:
                    stock_codes = [line.strip() for line in f if line.strip()]
            else:
                # 从数据库获取股票列表
                stock_codes = get_pvfrs_stocks(args.market)
            
            if not stock_codes:
                logger.error("没有找到股票代码")
                return
            
            logger.info(f"批量回测股票数量: {len(stock_codes)}")
            
            results = runner.run_batch_backtest(
                stock_codes, args.market, args.start_date, args.end_date,
                custom_params, initial_capital
            )
            
            # 生成批量报告
            report = runner.generate_batch_report(results, args.output)
            print(report)
        
        elif args.mode == 'optimize':
            # 参数优化
            if not args.code:
                logger.error("optimize模式需要指定--code参数")
                return
            
            optimization_result = runner.run_parameter_optimization(
                args.code, args.market, args.start_date, args.end_date
            )
            
            if optimization_result['best_result']:
                # 生成优化报告
                report = f"""
# PVFRS策略参数优化报告

## 最佳参数
```json
{json.dumps(optimization_result['best_params'], indent=2, ensure_ascii=False)}
```

## 最佳结果
- 总收益率: {optimization_result['best_result'].total_return:.2%}
- 年化收益率: {optimization_result['best_result'].annual_return:.2%}
- 最大回撤: {optimization_result['best_result'].max_drawdown:.2%}
- 夏普比率: {optimization_result['best_result'].sharpe_ratio:.2f}
- 综合评分: {optimization_result['best_score']:.2f}

## 优化日志
{pd.DataFrame(optimization_result['optimization_log']).to_string(index=False)}
"""
                
                if args.output:
                    with open(args.output, 'w', encoding='utf-8') as f:
                        f.write(report)
                    logger.info(f"优化报告已保存到: {args.output}")
                
                print(report)
            else:
                logger.error("参数优化失败")
    
    except Exception as e:
        logger.error(f"回测执行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
