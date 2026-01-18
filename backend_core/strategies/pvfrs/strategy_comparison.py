"""
PVFRS策略对比功能模块
负责多个回测结果的对比分析和策略性能指标的横向比较
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import logging
import json
import math
import uuid
from dataclasses import dataclass, asdict

from .models import PVFRSException

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class ComparisonMetric:
    """对比指标数据结构"""
    metric_name: str
    values: List[float]
    best_index: int
    worst_index: int
    average: float
    std_deviation: float
    description: str


@dataclass
class StrategyRanking:
    """策略排名数据结构"""
    report_id: str
    strategy_name: str
    overall_score: float
    rank: int
    strengths: List[str]
    weaknesses: List[str]
    recommendation: str


class StrategyComparator:
    """策略对比器
    
    负责多个策略回测结果的对比分析：
    - 性能指标横向对比
    - 风险指标对比分析
    - 策略排名和评分
    - 对比可视化数据生成
    - 投资建议生成
    """
    
    def __init__(self):
        """初始化策略对比器"""
        # 定义对比指标权重
        self.metric_weights = {
            'total_return': 0.20,
            'annual_return': 0.20,
            'sharpe_ratio': 0.15,
            'max_drawdown': 0.15,
            'win_rate': 0.10,
            'profit_factor': 0.10,
            'volatility': 0.05,
            'calmar_ratio': 0.05
        }
        
        # 指标优化方向（True表示越大越好，False表示越小越好）
        self.metric_directions = {
            'total_return': True,
            'annual_return': True,
            'sharpe_ratio': True,
            'max_drawdown': False,
            'win_rate': True,
            'profit_factor': True,
            'volatility': False,
            'calmar_ratio': True
        }
        
        logger.info("策略对比器初始化完成")
    
    def compare_strategies(self, reports: List[Dict]) -> Dict:
        """对比多个策略
        
        Args:
            reports: 回测报告列表
            
        Returns:
            Dict: 策略对比结果
            
        Raises:
            PVFRSException: 对比失败时抛出
        """
        try:
            if len(reports) < 2:
                raise PVFRSException("至少需要2个报告进行对比")
            
            logger.info(f"开始对比 {len(reports)} 个策略")
            
            # 1. 提取和标准化指标数据
            metrics_data = self._extract_metrics_data(reports)
            
            # 2. 计算对比指标
            comparison_metrics = self._calculate_comparison_metrics(metrics_data)
            
            # 3. 计算策略评分和排名
            strategy_rankings = self._calculate_strategy_rankings(reports, metrics_data)
            
            # 4. 生成对比分析
            comparison_analysis = self._generate_comparison_analysis(comparison_metrics, strategy_rankings)
            
            # 5. 生成可视化数据
            visualization_data = self._prepare_comparison_visualization(reports, comparison_metrics)
            
            # 6. 生成投资建议
            investment_recommendations = self._generate_investment_recommendations(strategy_rankings)
            
            # 7. 构建完整对比结果
            comparison_result = {
                'comparison_id': f"comparison_{uuid.uuid4().hex[:8]}",
                'created_at': datetime.now().isoformat(),
                'report_count': len(reports),
                'reports_info': [
                    {
                        'report_id': report.get('report_id', 'unknown'),
                        'strategy_name': self._get_strategy_name(report),
                        'period': f"{report.get('config', {}).get('start_date', 'N/A')} - {report.get('config', {}).get('end_date', 'N/A')}"
                    }
                    for report in reports
                ],
                'comparison_metrics': {name: asdict(metric) for name, metric in comparison_metrics.items()},
                'strategy_rankings': [asdict(ranking) for ranking in strategy_rankings],
                'comparison_analysis': comparison_analysis,
                'visualization_data': visualization_data,
                'investment_recommendations': investment_recommendations,
                'summary': self._generate_comparison_summary(strategy_rankings, comparison_metrics)
            }
            
            logger.info("策略对比完成")
            return comparison_result
            
        except Exception as e:
            logger.error(f"策略对比失败: {str(e)}")
            raise PVFRSException(f"策略对比失败: {str(e)}")
    
    def compare_two_strategies(self, report1: Dict, report2: Dict) -> Dict:
        """对比两个策略（简化版）
        
        Args:
            report1: 第一个回测报告
            report2: 第二个回测报告
            
        Returns:
            Dict: 两策略对比结果
        """
        try:
            # 使用通用对比方法
            comparison_result = self.compare_strategies([report1, report2])
            
            # 添加专门的两策略对比分析
            two_strategy_analysis = self._analyze_two_strategies(report1, report2)
            comparison_result['two_strategy_analysis'] = two_strategy_analysis
            
            return comparison_result
            
        except Exception as e:
            logger.error(f"两策略对比失败: {str(e)}")
            raise PVFRSException(f"两策略对比失败: {str(e)}")
    
    def rank_strategies_by_metric(self, reports: List[Dict], metric_name: str) -> List[Dict]:
        """按指定指标对策略排名
        
        Args:
            reports: 回测报告列表
            metric_name: 指标名称
            
        Returns:
            List[Dict]: 按指标排名的策略列表
        """
        try:
            # 提取指标值
            strategy_metrics = []
            for i, report in enumerate(reports):
                metric_value = self._extract_metric_value(report, metric_name)
                strategy_metrics.append({
                    'index': i,
                    'report_id': report.get('report_id', f'report_{i}'),
                    'strategy_name': self._get_strategy_name(report),
                    'metric_value': metric_value,
                    'report': report
                })
            
            # 排序（根据指标优化方向）
            is_ascending = not self.metric_directions.get(metric_name, True)
            sorted_strategies = sorted(
                strategy_metrics, 
                key=lambda x: x['metric_value'] if x['metric_value'] is not None else float('-inf'),
                reverse=not is_ascending
            )
            
            # 添加排名
            for rank, strategy in enumerate(sorted_strategies, 1):
                strategy['rank'] = rank
            
            return sorted_strategies
            
        except Exception as e:
            logger.error(f"按指标排名失败: {str(e)}")
            raise PVFRSException(f"按指标排名失败: {str(e)}")
    
    def generate_comparison_report(self, comparison_result: Dict) -> str:
        """生成对比报告文本
        
        Args:
            comparison_result: 对比结果
            
        Returns:
            str: 对比报告文本
        """
        try:
            report_lines = []
            
            # 标题
            report_lines.append("PVFRS策略对比分析报告")
            report_lines.append("=" * 50)
            report_lines.append(f"生成时间: {comparison_result['created_at']}")
            report_lines.append(f"对比策略数量: {comparison_result['report_count']}")
            report_lines.append("")
            
            # 策略概览
            report_lines.append("策略概览:")
            report_lines.append("-" * 30)
            for i, report_info in enumerate(comparison_result['reports_info'], 1):
                report_lines.append(f"{i}. {report_info['strategy_name']} ({report_info['report_id']})")
                report_lines.append(f"   回测期间: {report_info['period']}")
            report_lines.append("")
            
            # 策略排名
            report_lines.append("策略排名:")
            report_lines.append("-" * 30)
            for ranking in comparison_result['strategy_rankings']:
                report_lines.append(f"{ranking['rank']}. {ranking['strategy_name']}")
                report_lines.append(f"   综合评分: {ranking['overall_score']:.2f}")
                report_lines.append(f"   优势: {', '.join(ranking['strengths'])}")
                if ranking['weaknesses']:
                    report_lines.append(f"   劣势: {', '.join(ranking['weaknesses'])}")
                report_lines.append(f"   建议: {ranking['recommendation']}")
                report_lines.append("")
            
            # 关键指标对比
            report_lines.append("关键指标对比:")
            report_lines.append("-" * 30)
            key_metrics = ['total_return', 'annual_return', 'sharpe_ratio', 'max_drawdown', 'win_rate']
            for metric_name in key_metrics:
                if metric_name in comparison_result['comparison_metrics']:
                    metric = comparison_result['comparison_metrics'][metric_name]
                    report_lines.append(f"{metric['description']}:")
                    for i, value in enumerate(metric['values']):
                        strategy_name = comparison_result['reports_info'][i]['strategy_name']
                        marker = " ★" if i == metric['best_index'] else ""
                        report_lines.append(f"  {strategy_name}: {value:.4f}{marker}")
                    report_lines.append("")
            
            # 投资建议
            report_lines.append("投资建议:")
            report_lines.append("-" * 30)
            for recommendation in comparison_result['investment_recommendations']:
                report_lines.append(f"• {recommendation}")
            report_lines.append("")
            
            # 总结
            report_lines.append("总结:")
            report_lines.append("-" * 30)
            report_lines.append(comparison_result['summary'])
            
            return "\n".join(report_lines)
            
        except Exception as e:
            logger.error(f"生成对比报告文本失败: {str(e)}")
            raise PVFRSException(f"生成对比报告文本失败: {str(e)}")
    
    def _extract_metrics_data(self, reports: List[Dict]) -> Dict[str, List[float]]:
        """提取指标数据
        
        Args:
            reports: 回测报告列表
            
        Returns:
            Dict[str, List[float]]: 指标数据字典
        """
        metrics_data = {}
        
        # 定义要提取的指标
        metric_names = [
            'total_return', 'annual_return', 'sharpe_ratio', 'max_drawdown',
            'win_rate', 'volatility'
        ]
        
        for metric_name in metric_names:
            metrics_data[metric_name] = []
            for report in reports:
                value = self._extract_metric_value(report, metric_name)
                metrics_data[metric_name].append(value if value is not None else 0.0)
        
        # 计算衍生指标
        metrics_data['profit_factor'] = []
        metrics_data['calmar_ratio'] = []
        
        for report in reports:
            # 盈亏比（处理 None 值）
            trades = report.get('trades', [])
            if trades:
                wins = [t.get('pnl') for t in trades if t.get('pnl') is not None and t.get('pnl', 0) > 0]
                losses = [t.get('pnl') for t in trades if t.get('pnl') is not None and t.get('pnl', 0) < 0]
                avg_win = sum(wins) / len(wins) if wins else 0
                avg_loss = sum(losses) / len(losses) if losses else 0
                profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            else:
                profit_factor = 0
            metrics_data['profit_factor'].append(profit_factor)
            
            # 卡玛比率
            annual_return = self._extract_metric_value(report, 'annual_return') or 0
            max_drawdown = self._extract_metric_value(report, 'max_drawdown') or 0
            calmar_ratio = annual_return / max_drawdown if max_drawdown > 0 else 0
            metrics_data['calmar_ratio'].append(calmar_ratio)
        
        return metrics_data
    
    def _extract_metric_value(self, report: Dict, metric_name: str) -> Optional[float]:
        """从报告中提取指标值
        
        Args:
            report: 回测报告
            metric_name: 指标名称
            
        Returns:
            Optional[float]: 指标值
        """
        # 直接从报告根级别获取
        if metric_name in report:
            return report[metric_name]
        
        # 从performance_metrics获取
        if 'performance_metrics' in report:
            perf_metrics = report['performance_metrics']
            if metric_name in perf_metrics:
                return perf_metrics[metric_name]
        
        # 从comprehensive_data获取
        if 'comprehensive_data' in report:
            comp_data = report['comprehensive_data']
            if 'performance_metrics' in comp_data:
                perf_metrics = comp_data['performance_metrics']
                if metric_name in perf_metrics:
                    return perf_metrics[metric_name]
        
        # 特殊处理一些指标
        if metric_name == 'volatility':
            # 尝试从风险指标获取
            if 'risk_metrics' in report:
                return report['risk_metrics'].get('volatility')
            if 'comprehensive_data' in report and 'risk_metrics' in report['comprehensive_data']:
                return report['comprehensive_data']['risk_metrics'].get('volatility')
        
        return None
    
    def _calculate_comparison_metrics(self, metrics_data: Dict[str, List[float]]) -> Dict[str, ComparisonMetric]:
        """计算对比指标
        
        Args:
            metrics_data: 指标数据
            
        Returns:
            Dict[str, ComparisonMetric]: 对比指标字典
        """
        comparison_metrics = {}
        
        metric_descriptions = {
            'total_return': '总收益率',
            'annual_return': '年化收益率',
            'sharpe_ratio': '夏普比率',
            'max_drawdown': '最大回撤',
            'win_rate': '胜率',
            'profit_factor': '盈亏比',
            'volatility': '波动率',
            'calmar_ratio': '卡玛比率'
        }
        
        for metric_name, values in metrics_data.items():
            if not values:
                continue
            
            # 找出最佳和最差（过滤 None 值）
            valid_values = [v for v in values if v is not None]
            if not valid_values:
                continue
            
            is_higher_better = self.metric_directions.get(metric_name, True)
            if is_higher_better:
                best_index = values.index(max(valid_values))
                worst_index = values.index(min(valid_values))
            else:
                best_index = values.index(min(valid_values))
                worst_index = values.index(max(valid_values))
            
            # 计算统计指标（过滤 None 值）
            valid_values = [v for v in values if v is not None]
            if not valid_values:
                continue
            average = sum(valid_values) / len(valid_values)
            variance = sum((v - average) ** 2 for v in valid_values) / len(valid_values)
            std_deviation = math.sqrt(variance)
            
            comparison_metric = ComparisonMetric(
                metric_name=metric_name,
                values=values,
                best_index=best_index,
                worst_index=worst_index,
                average=average,
                std_deviation=std_deviation,
                description=metric_descriptions.get(metric_name, metric_name)
            )
            
            comparison_metrics[metric_name] = comparison_metric
        
        return comparison_metrics
    
    def _calculate_strategy_rankings(self, reports: List[Dict], 
                                   metrics_data: Dict[str, List[float]]) -> List[StrategyRanking]:
        """计算策略排名
        
        Args:
            reports: 回测报告列表
            metrics_data: 指标数据
            
        Returns:
            List[StrategyRanking]: 策略排名列表
        """
        strategy_scores = []
        
        for i, report in enumerate(reports):
            # 计算综合评分
            total_score = 0
            valid_metrics = 0
            
            for metric_name, weight in self.metric_weights.items():
                if metric_name in metrics_data and i < len(metrics_data[metric_name]):
                    metric_value = metrics_data[metric_name][i]
                    metric_values = metrics_data[metric_name]
                    
                    # 标准化分数 (0-100)（过滤 None 值）
                    valid_metric_values = [v for v in metric_values if v is not None]
                    if len(valid_metric_values) > 1:
                        min_val = min(valid_metric_values)
                        max_val = max(valid_metric_values)
                        if max_val != min_val and metric_value is not None:
                            if self.metric_directions.get(metric_name, True):
                                # 越大越好
                                normalized_score = (metric_value - min_val) / (max_val - min_val) * 100
                            else:
                                # 越小越好
                                normalized_score = (max_val - metric_value) / (max_val - min_val) * 100
                        else:
                            normalized_score = 50  # 所有值相同时给中等分数
                    else:
                        normalized_score = 50
                    
                    total_score += normalized_score * weight
                    valid_metrics += weight
            
            # 计算最终评分
            overall_score = total_score / valid_metrics if valid_metrics > 0 else 0
            
            # 分析优势和劣势
            strengths, weaknesses = self._analyze_strategy_strengths_weaknesses(
                i, metrics_data, overall_score
            )
            
            # 生成建议
            recommendation = self._generate_strategy_recommendation(overall_score, strengths, weaknesses)
            
            strategy_ranking = StrategyRanking(
                report_id=report.get('report_id', f'report_{i}'),
                strategy_name=self._get_strategy_name(report),
                overall_score=overall_score,
                rank=0,  # 稍后设置
                strengths=strengths,
                weaknesses=weaknesses,
                recommendation=recommendation
            )
            
            strategy_scores.append(strategy_ranking)
        
        # 按评分排序并设置排名
        strategy_scores.sort(key=lambda x: x.overall_score, reverse=True)
        for rank, strategy in enumerate(strategy_scores, 1):
            strategy.rank = rank
        
        return strategy_scores
    
    def _analyze_strategy_strengths_weaknesses(self, strategy_index: int, 
                                             metrics_data: Dict[str, List[float]],
                                             overall_score: float) -> Tuple[List[str], List[str]]:
        """分析策略优势和劣势
        
        Args:
            strategy_index: 策略索引
            metrics_data: 指标数据
            overall_score: 综合评分
            
        Returns:
            Tuple[List[str], List[str]]: (优势列表, 劣势列表)
        """
        strengths = []
        weaknesses = []
        
        metric_names_cn = {
            'total_return': '总收益率',
            'annual_return': '年化收益率',
            'sharpe_ratio': '夏普比率',
            'max_drawdown': '最大回撤',
            'win_rate': '胜率',
            'profit_factor': '盈亏比',
            'volatility': '波动率',
            'calmar_ratio': '卡玛比率'
        }
        
        for metric_name, values in metrics_data.items():
            if strategy_index >= len(values):
                continue
            
            strategy_value = values[strategy_index]
            avg_value = sum(values) / len(values)
            
            is_higher_better = self.metric_directions.get(metric_name, True)
            metric_name_cn = metric_names_cn.get(metric_name, metric_name)
            
            # 判断是否为优势或劣势
            if is_higher_better:
                if strategy_value > avg_value * 1.1:  # 超过平均值10%
                    strengths.append(f"{metric_name_cn}表现优秀")
                elif strategy_value < avg_value * 0.9:  # 低于平均值10%
                    weaknesses.append(f"{metric_name_cn}表现不佳")
            else:
                if strategy_value < avg_value * 0.9:  # 低于平均值10%（对于越小越好的指标）
                    strengths.append(f"{metric_name_cn}控制良好")
                elif strategy_value > avg_value * 1.1:  # 超过平均值10%
                    weaknesses.append(f"{metric_name_cn}偏高")
        
        # 如果没有明显优势或劣势，给出通用评价
        if not strengths and overall_score > 70:
            strengths.append("综合表现均衡")
        if not weaknesses and overall_score < 50:
            weaknesses.append("整体表现有待提升")
        
        return strengths, weaknesses
    
    def _generate_strategy_recommendation(self, overall_score: float, 
                                        strengths: List[str], weaknesses: List[str]) -> str:
        """生成策略建议
        
        Args:
            overall_score: 综合评分
            strengths: 优势列表
            weaknesses: 劣势列表
            
        Returns:
            str: 策略建议
        """
        if overall_score >= 80:
            return "表现优秀，建议优先考虑实盘应用"
        elif overall_score >= 60:
            return "表现良好，可考虑小仓位试验"
        elif overall_score >= 40:
            return "表现一般，建议进一步优化参数"
        else:
            return "表现不佳，需要重新审视策略逻辑"
    
    def _generate_comparison_analysis(self, comparison_metrics: Dict[str, ComparisonMetric],
                                    strategy_rankings: List[StrategyRanking]) -> Dict:
        """生成对比分析
        
        Args:
            comparison_metrics: 对比指标
            strategy_rankings: 策略排名
            
        Returns:
            Dict: 对比分析结果
        """
        analysis = {
            'best_overall_strategy': strategy_rankings[0].strategy_name if strategy_rankings else None,
            'metric_leaders': {},
            'performance_spread': {},
            'risk_analysis': {},
            'consistency_analysis': {}
        }
        
        # 各指标领先者
        for metric_name, metric in comparison_metrics.items():
            best_strategy_index = metric.best_index
            if best_strategy_index < len(strategy_rankings):
                analysis['metric_leaders'][metric.description] = {
                    'strategy': strategy_rankings[best_strategy_index].strategy_name,
                    'value': metric.values[best_strategy_index]
                }
        
        # 性能分散度分析
        for metric_name, metric in comparison_metrics.items():
            if metric.std_deviation > 0:
                cv = metric.std_deviation / abs(metric.average) if metric.average != 0 else 0
                analysis['performance_spread'][metric.description] = {
                    'coefficient_of_variation': cv,
                    'interpretation': '高分散' if cv > 0.5 else '中等分散' if cv > 0.2 else '低分散'
                }
        
        return analysis
    
    def _prepare_comparison_visualization(self, reports: List[Dict], 
                                        comparison_metrics: Dict[str, ComparisonMetric]) -> Dict:
        """准备对比可视化数据
        
        Args:
            reports: 回测报告列表
            comparison_metrics: 对比指标
            
        Returns:
            Dict: 可视化数据
        """
        viz_data = {
            'radar_chart': self._prepare_radar_chart_data(reports, comparison_metrics),
            'bar_chart': self._prepare_bar_chart_data(comparison_metrics),
            'scatter_plot': self._prepare_scatter_plot_data(reports, comparison_metrics),
            'equity_curves': self._prepare_equity_curves_data(reports)
        }
        
        return viz_data
    
    def _prepare_radar_chart_data(self, reports: List[Dict], 
                                 comparison_metrics: Dict[str, ComparisonMetric]) -> Dict:
        """准备雷达图数据"""
        # 选择关键指标
        key_metrics = ['total_return', 'sharpe_ratio', 'win_rate', 'max_drawdown', 'volatility']
        
        radar_data = {
            'metrics': [],
            'strategies': []
        }
        
        # 指标名称
        for metric_name in key_metrics:
            if metric_name in comparison_metrics:
                radar_data['metrics'].append(comparison_metrics[metric_name].description)
        
        # 策略数据
        for i, report in enumerate(reports):
            strategy_data = {
                'name': self._get_strategy_name(report),
                'values': []
            }
            
            for metric_name in key_metrics:
                if metric_name in comparison_metrics:
                    metric = comparison_metrics[metric_name]
                    if i < len(metric.values):
                        # 标准化到0-100（过滤 None 值）
                        value = metric.values[i]
                        if value is None:
                            continue
                        valid_values = [v for v in metric.values if v is not None]
                        if not valid_values:
                            continue
                        min_val = min(valid_values)
                        max_val = max(valid_values)
                        
                        if max_val != min_val:
                            if self.metric_directions.get(metric_name, True):
                                normalized = (value - min_val) / (max_val - min_val) * 100
                            else:
                                normalized = (max_val - value) / (max_val - min_val) * 100
                        else:
                            normalized = 50
                        
                        strategy_data['values'].append(normalized)
                    else:
                        strategy_data['values'].append(0)
            
            radar_data['strategies'].append(strategy_data)
        
        return radar_data
    
    def _prepare_bar_chart_data(self, comparison_metrics: Dict[str, ComparisonMetric]) -> Dict:
        """准备柱状图数据"""
        bar_data = {}
        
        for metric_name, metric in comparison_metrics.items():
            bar_data[metric.description] = {
                'values': metric.values,
                'best_index': metric.best_index,
                'average': metric.average
            }
        
        return bar_data
    
    def _prepare_scatter_plot_data(self, reports: List[Dict], 
                                  comparison_metrics: Dict[str, ComparisonMetric]) -> Dict:
        """准备散点图数据（风险-收益）"""
        scatter_data = {
            'risk_return': {
                'x_values': [],  # 风险（最大回撤或波动率）
                'y_values': [],  # 收益（年化收益率）
                'labels': []
            }
        }
        
        # 提取风险和收益数据
        if 'annual_return' in comparison_metrics and 'max_drawdown' in comparison_metrics:
            annual_returns = comparison_metrics['annual_return'].values
            max_drawdowns = comparison_metrics['max_drawdown'].values
            
            for i, report in enumerate(reports):
                if i < len(annual_returns) and i < len(max_drawdowns):
                    scatter_data['risk_return']['x_values'].append(max_drawdowns[i])
                    scatter_data['risk_return']['y_values'].append(annual_returns[i])
                    scatter_data['risk_return']['labels'].append(self._get_strategy_name(report))
        
        return scatter_data
    
    def _prepare_equity_curves_data(self, reports: List[Dict]) -> Dict:
        """准备资金曲线对比数据"""
        equity_curves_data = {
            'dates': [],
            'curves': []
        }
        
        # 找到共同的日期范围
        all_dates = set()
        for report in reports:
            equity_curve = report.get('equity_curve', [])
            for point in equity_curve:
                all_dates.add(point.get('date'))
        
        if all_dates:
            sorted_dates = sorted(all_dates)
            equity_curves_data['dates'] = sorted_dates
            
            # 为每个策略生成曲线数据
            for report in reports:
                strategy_name = self._get_strategy_name(report)
                equity_curve = report.get('equity_curve', [])
                
                # 创建日期到权益的映射
                date_to_equity = {}
                for point in equity_curve:
                    date_to_equity[point.get('date')] = point.get('return_rate', 0)
                
                # 生成完整的曲线数据
                curve_values = []
                for date in sorted_dates:
                    if date in date_to_equity:
                        curve_values.append(date_to_equity[date])
                    else:
                        # 使用前一个值或0
                        curve_values.append(curve_values[-1] if curve_values else 0)
                
                equity_curves_data['curves'].append({
                    'name': strategy_name,
                    'values': curve_values
                })
        
        return equity_curves_data
    
    def _analyze_two_strategies(self, report1: Dict, report2: Dict) -> Dict:
        """分析两个策略的详细对比
        
        Args:
            report1: 第一个报告
            report2: 第二个报告
            
        Returns:
            Dict: 两策略详细对比分析
        """
        analysis = {
            'winner_by_metric': {},
            'improvement_suggestions': {},
            'risk_reward_comparison': {},
            'trading_behavior_comparison': {}
        }
        
        # 按指标对比
        metrics_to_compare = ['total_return', 'annual_return', 'sharpe_ratio', 'max_drawdown', 'win_rate']
        
        for metric_name in metrics_to_compare:
            value1 = self._extract_metric_value(report1, metric_name)
            value2 = self._extract_metric_value(report2, metric_name)
            
            if value1 is not None and value2 is not None:
                is_higher_better = self.metric_directions.get(metric_name, True)
                
                if is_higher_better:
                    winner = 1 if value1 > value2 else 2
                    improvement = abs(value1 - value2) / max(abs(value2), 0.0001) * 100
                else:
                    winner = 1 if value1 < value2 else 2
                    improvement = abs(value2 - value1) / max(abs(value1), 0.0001) * 100
                
                analysis['winner_by_metric'][metric_name] = {
                    'winner': winner,
                    'value1': value1,
                    'value2': value2,
                    'improvement_percentage': improvement
                }
        
        return analysis
    
    def _generate_investment_recommendations(self, strategy_rankings: List[StrategyRanking]) -> List[str]:
        """生成投资建议
        
        Args:
            strategy_rankings: 策略排名列表
            
        Returns:
            List[str]: 投资建议列表
        """
        recommendations = []
        
        if not strategy_rankings:
            return recommendations
        
        # 最佳策略建议
        best_strategy = strategy_rankings[0]
        recommendations.append(f"推荐使用 {best_strategy.strategy_name}，综合评分最高（{best_strategy.overall_score:.1f}分）")
        
        # 风险提示
        if best_strategy.overall_score < 70:
            recommendations.append("注意：即使是最佳策略的评分也不高，建议谨慎使用")
        
        # 分散化建议
        if len(strategy_rankings) > 1:
            top_strategies = [s for s in strategy_rankings if s.overall_score > 60]
            if len(top_strategies) > 1:
                recommendations.append(f"可考虑组合使用前{len(top_strategies)}个策略以分散风险")
        
        # 改进建议
        common_weaknesses = {}
        for strategy in strategy_rankings:
            for weakness in strategy.weaknesses:
                common_weaknesses[weakness] = common_weaknesses.get(weakness, 0) + 1
        
        if common_weaknesses:
            most_common_weakness = max(common_weaknesses.items(), key=lambda x: x[1])
            if most_common_weakness[1] > len(strategy_rankings) / 2:
                recommendations.append(f"所有策略都需要改进：{most_common_weakness[0]}")
        
        return recommendations
    
    def _generate_comparison_summary(self, strategy_rankings: List[StrategyRanking],
                                   comparison_metrics: Dict[str, ComparisonMetric]) -> str:
        """生成对比总结
        
        Args:
            strategy_rankings: 策略排名
            comparison_metrics: 对比指标
            
        Returns:
            str: 对比总结
        """
        if not strategy_rankings:
            return "无有效策略进行对比"
        
        best_strategy = strategy_rankings[0]
        worst_strategy = strategy_rankings[-1]
        
        summary_parts = []
        
        # 最佳策略
        summary_parts.append(f"最佳策略为 {best_strategy.strategy_name}（评分：{best_strategy.overall_score:.1f}）")
        
        # 性能差异
        score_diff = best_strategy.overall_score - worst_strategy.overall_score
        summary_parts.append(f"策略间性能差异为 {score_diff:.1f} 分")
        
        # 关键指标表现（过滤 None 值）
        if 'annual_return' in comparison_metrics:
            annual_returns = comparison_metrics['annual_return']
            valid_returns = [v for v in annual_returns.values if v is not None]
            if valid_returns:
                best_return = max(valid_returns)
                summary_parts.append(f"最高年化收益率为 {best_return:.2%}")
        
        if 'max_drawdown' in comparison_metrics:
            drawdowns = comparison_metrics['max_drawdown']
            valid_drawdowns = [v for v in drawdowns.values if v is not None]
            if valid_drawdowns:
                min_drawdown = min(valid_drawdowns)
                summary_parts.append(f"最小最大回撤为 {min_drawdown:.2%}")
        
        return "，".join(summary_parts) + "。"
    
    def _get_strategy_name(self, report: Dict) -> str:
        """获取策略名称
        
        Args:
            report: 回测报告
            
        Returns:
            str: 策略名称
        """
        # 尝试从多个位置获取策略名称
        if 'strategy_name' in report:
            return report['strategy_name']
        
        if 'config' in report and 'strategy_name' in report['config']:
            return report['config']['strategy_name']
        
        # 使用报告ID作为默认名称
        report_id = report.get('report_id', 'unknown')
        return f"PVFRS策略_{report_id[-8:]}"


# 便捷函数
def create_strategy_comparator() -> StrategyComparator:
    """创建策略对比器实例
    
    Returns:
        StrategyComparator: 策略对比器实例
    """
    return StrategyComparator()


def compare_strategies_quick(reports: List[Dict]) -> Dict:
    """快速对比策略
    
    Args:
        reports: 回测报告列表
        
    Returns:
        Dict: 对比结果
    """
    comparator = StrategyComparator()
    return comparator.compare_strategies(reports)