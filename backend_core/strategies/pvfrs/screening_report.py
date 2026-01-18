"""
PVFRS策略选股结果排序和输出功能实现
按信号强度对选股结果排序，生成包含完整信息的选股报告
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
import json
import csv
from io import StringIO
from .stock_screener import ScreeningResult, ScreeningConfig


@dataclass
class ReportConfig:
    """报告配置"""
    include_detailed_conditions: bool = True  # 是否包含详细条件信息
    include_statistics: bool = True  # 是否包含统计信息
    include_market_info: bool = True  # 是否包含市场信息
    sort_by: str = 'signal_strength'  # 排序字段
    sort_ascending: bool = False  # 是否升序排列
    max_results_in_summary: int = 10  # 摘要中最大结果数
    decimal_places: int = 4  # 小数位数
    
    # 输出格式配置
    format_numbers: bool = True  # 是否格式化数字
    include_rank: bool = True  # 是否包含排名
    include_score_analysis: bool = True  # 是否包含评分分析


class ScreeningReportGenerator:
    """选股报告生成器
    
    负责选股结果的排序、格式化和输出：
    - 按信号强度对选股结果排序
    - 生成包含完整信息的选股报告
    - 支持多种输出格式（JSON、CSV、文本等）
    - 提供详细的统计分析
    """
    
    def __init__(self, config: Optional[ReportConfig] = None):
        """初始化报告生成器
        
        Args:
            config: 报告配置，如果为None则使用默认配置
        """
        self.config = config or ReportConfig()
    
    def generate_comprehensive_report(self, results: List[ScreeningResult], 
                                    screening_config: ScreeningConfig,
                                    screening_stats: Dict,
                                    target_date: str) -> Dict:
        """生成综合选股报告
        
        Args:
            results: 选股结果列表
            screening_config: 选股配置
            screening_stats: 选股统计信息
            target_date: 目标日期
            
        Returns:
            Dict: 综合报告
        """
        # 1. 排序结果
        sorted_results = self.sort_results(results)
        
        # 2. 生成报告各部分
        report = {
            'report_metadata': self._generate_report_metadata(target_date, screening_config, screening_stats),
            'executive_summary': self._generate_executive_summary(sorted_results, screening_stats),
            'detailed_results': self._generate_detailed_results(sorted_results),
            'statistical_analysis': self._generate_statistical_analysis(sorted_results),
            'market_analysis': self._generate_market_analysis(sorted_results),
            'risk_assessment': self._generate_risk_assessment(sorted_results),
            'recommendations': self._generate_recommendations(sorted_results, screening_stats)
        }
        
        return report
    
    def sort_results(self, results: List[ScreeningResult], 
                    sort_by: Optional[str] = None, 
                    ascending: Optional[bool] = None) -> List[ScreeningResult]:
        """对选股结果进行排序
        
        Args:
            results: 原始结果列表
            sort_by: 排序字段，如果为None则使用配置中的字段
            ascending: 是否升序，如果为None则使用配置中的设置
            
        Returns:
            List[ScreeningResult]: 排序后的结果列表
        """
        if not results:
            return results
        
        sort_field = sort_by or self.config.sort_by
        is_ascending = ascending if ascending is not None else self.config.sort_ascending
        
        # 定义排序键函数
        def get_sort_key(result: ScreeningResult) -> Any:
            if sort_field == 'signal_strength':
                return result.signal_strength
            elif sort_field == 'price':
                return result.price
            elif sort_field == 'volume':
                return result.volume
            elif sort_field == 'market_cap':
                return result.market_cap or 0
            elif sort_field == 'symbol':
                return result.symbol
            else:
                # 默认按信号强度排序
                return result.signal_strength
        
        try:
            sorted_results = sorted(results, key=get_sort_key, reverse=not is_ascending)
            
            # 如果启用了排名，添加排名信息
            if self.config.include_rank:
                for i, result in enumerate(sorted_results):
                    # 由于ScreeningResult是dataclass，我们需要通过其他方式添加排名
                    # 这里我们将排名信息添加到conditions_met中
                    result.conditions_met['rank'] = i + 1
            
            return sorted_results
            
        except Exception as e:
            # 如果排序失败，返回原始结果并记录错误
            print(f"排序失败，使用原始顺序: {str(e)}")
            return results
    
    def generate_json_report(self, results: List[ScreeningResult], 
                           screening_config: ScreeningConfig,
                           screening_stats: Dict,
                           target_date: str,
                           indent: int = 2) -> str:
        """生成JSON格式报告
        
        Args:
            results: 选股结果列表
            screening_config: 选股配置
            screening_stats: 选股统计信息
            target_date: 目标日期
            indent: JSON缩进
            
        Returns:
            str: JSON格式的报告
        """
        comprehensive_report = self.generate_comprehensive_report(
            results, screening_config, screening_stats, target_date
        )
        
        return json.dumps(comprehensive_report, indent=indent, ensure_ascii=False, default=str)
    
    def generate_csv_report(self, results: List[ScreeningResult]) -> str:
        """生成CSV格式报告
        
        Args:
            results: 选股结果列表
            
        Returns:
            str: CSV格式的报告
        """
        if not results:
            return "股票代码,日期,信号强度,价格,成交量,信号原因\n"
        
        # 排序结果
        sorted_results = self.sort_results(results)
        
        # 创建CSV内容
        output = StringIO()
        writer = csv.writer(output)
        
        # 写入表头
        headers = [
            '排名', '股票代码', '日期', '信号强度', '价格', '成交量', 
            '市值', '行业', '信号原因'
        ]
        
        if self.config.include_detailed_conditions:
            # 获取所有可能的条件
            all_conditions = set()
            for result in sorted_results:
                all_conditions.update(result.conditions_met.keys())
            
            # 排除排名条件（如果存在）
            all_conditions.discard('rank')
            
            headers.extend(sorted(all_conditions))
        
        writer.writerow(headers)
        
        # 写入数据行
        for i, result in enumerate(sorted_results):
            row = [
                i + 1,  # 排名
                result.symbol,
                result.date,
                self._format_number(result.signal_strength),
                self._format_number(result.price),
                result.volume,
                self._format_number(result.market_cap) if result.market_cap else '',
                result.industry or '',
                result.signal_reason
            ]
            
            if self.config.include_detailed_conditions:
                # 添加条件列
                for condition in sorted(all_conditions):
                    row.append('是' if result.conditions_met.get(condition, False) else '否')
            
            writer.writerow(row)
        
        return output.getvalue()
    
    def generate_text_report(self, results: List[ScreeningResult], 
                           screening_config: ScreeningConfig,
                           screening_stats: Dict,
                           target_date: str) -> str:
        """生成文本格式报告
        
        Args:
            results: 选股结果列表
            screening_config: 选股配置
            screening_stats: 选股统计信息
            target_date: 目标日期
            
        Returns:
            str: 文本格式的报告
        """
        lines = []
        
        # 报告标题
        lines.append("=" * 80)
        lines.append("PVFRS策略选股报告")
        lines.append("=" * 80)
        lines.append("")
        
        # 基本信息
        lines.append(f"分析日期: {target_date}")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"最小信号强度: {screening_config.min_signal_strength}")
        lines.append(f"最大结果数量: {screening_config.max_results}")
        lines.append("")
        
        # 统计摘要
        lines.append("统计摘要")
        lines.append("-" * 40)
        lines.append(f"总分析股票数: {screening_stats.get('total_stocks', 0)}")
        lines.append(f"成功分析数: {screening_stats.get('analyzed_stocks', 0)}")
        lines.append(f"符合条件数: {screening_stats.get('qualified_stocks', 0)}")
        lines.append(f"处理时间: {screening_stats.get('processing_time', 0):.2f}秒")
        lines.append(f"成功率: {screening_stats.get('success_rate', 0):.2%}")
        lines.append(f"入选率: {screening_stats.get('qualification_rate', 0):.2%}")
        lines.append("")
        
        # 选股结果
        if results:
            sorted_results = self.sort_results(results)
            
            lines.append("选股结果")
            lines.append("-" * 40)
            
            # 表头
            lines.append(f"{'排名':<4} {'股票代码':<10} {'信号强度':<8} {'价格':<8} {'成交量':<12} {'信号原因'}")
            lines.append("-" * 80)
            
            # 数据行（限制显示数量）
            display_count = min(len(sorted_results), self.config.max_results_in_summary)
            
            for i, result in enumerate(sorted_results[:display_count]):
                lines.append(
                    f"{i+1:<4} {result.symbol:<10} "
                    f"{self._format_number(result.signal_strength):<8} "
                    f"{self._format_number(result.price):<8} "
                    f"{result.volume:<12} "
                    f"{result.signal_reason[:40]}..."
                )
            
            if len(sorted_results) > display_count:
                lines.append(f"... 还有 {len(sorted_results) - display_count} 个结果")
            
            lines.append("")
            
            # 详细分析（前几名）
            if self.config.include_detailed_conditions and sorted_results:
                lines.append("详细分析（前5名）")
                lines.append("-" * 40)
                
                for i, result in enumerate(sorted_results[:5]):
                    lines.append(f"{i+1}. {result.symbol} - 信号强度: {self._format_number(result.signal_strength)}")
                    lines.append(f"   价格: {self._format_number(result.price)}, 成交量: {result.volume:,}")
                    lines.append(f"   原因: {result.signal_reason}")
                    
                    # 满足的条件
                    met_conditions = [k for k, v in result.conditions_met.items() if v and k != 'rank']
                    if met_conditions:
                        lines.append(f"   满足条件: {', '.join(met_conditions)}")
                    
                    lines.append("")
        else:
            lines.append("未找到符合条件的股票")
            lines.append("")
        
        # 风险提示
        lines.append("风险提示")
        lines.append("-" * 40)
        lines.append("1. 本报告仅供参考，不构成投资建议")
        lines.append("2. 股票投资存在风险，请谨慎决策")
        lines.append("3. 历史表现不代表未来收益")
        lines.append("4. 建议结合其他分析方法综合判断")
        lines.append("")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def _generate_report_metadata(self, target_date: str, 
                                 screening_config: ScreeningConfig,
                                 screening_stats: Dict) -> Dict:
        """生成报告元数据"""
        return {
            'report_type': 'PVFRS策略选股报告',
            'version': '1.0.0',
            'generated_at': datetime.now().isoformat(),
            'target_date': target_date,
            'screening_parameters': {
                'min_signal_strength': screening_config.min_signal_strength,
                'max_results': screening_config.max_results,
                'min_price': screening_config.min_price,
                'max_price': screening_config.max_price,
                'min_volume': screening_config.min_volume,
                'exclude_st_stocks': screening_config.exclude_st_stocks,
                'parallel_processing': screening_config.enable_parallel_processing
            },
            'processing_statistics': screening_stats
        }
    
    def _generate_executive_summary(self, results: List[ScreeningResult], 
                                   screening_stats: Dict) -> Dict:
        """生成执行摘要"""
        if not results:
            return {
                'total_qualified_stocks': 0,
                'summary': '未找到符合PVFRS策略条件的股票',
                'key_findings': [],
                'top_performers': []
            }
        
        # 基本统计
        signal_strengths = [r.signal_strength for r in results]
        avg_strength = sum(signal_strengths) / len(signal_strengths)
        
        # 关键发现
        key_findings = []
        
        if avg_strength >= 0.8:
            key_findings.append("整体信号质量较高，平均信号强度超过0.8")
        elif avg_strength >= 0.7:
            key_findings.append("整体信号质量良好，平均信号强度在0.7以上")
        else:
            key_findings.append("整体信号质量一般，建议谨慎选择")
        
        # 统计高质量信号数量
        high_quality_count = len([r for r in results if r.signal_strength >= 0.8])
        if high_quality_count > 0:
            key_findings.append(f"发现{high_quality_count}只高质量信号股票（强度≥0.8）")
        
        # 前几名表现者
        top_performers = []
        for i, result in enumerate(results[:5]):
            top_performers.append({
                'rank': i + 1,
                'symbol': result.symbol,
                'signal_strength': result.signal_strength,
                'price': result.price,
                'brief_reason': result.signal_reason[:50] + "..." if len(result.signal_reason) > 50 else result.signal_reason
            })
        
        return {
            'total_qualified_stocks': len(results),
            'average_signal_strength': avg_strength,
            'max_signal_strength': max(signal_strengths),
            'min_signal_strength': min(signal_strengths),
            'high_quality_signals': high_quality_count,
            'summary': f'共发现{len(results)}只符合PVFRS策略条件的股票，平均信号强度{avg_strength:.3f}',
            'key_findings': key_findings,
            'top_performers': top_performers,
            'processing_efficiency': {
                'success_rate': screening_stats.get('success_rate', 0),
                'qualification_rate': screening_stats.get('qualification_rate', 0),
                'processing_time': screening_stats.get('processing_time', 0)
            }
        }
    
    def _generate_detailed_results(self, results: List[ScreeningResult]) -> List[Dict]:
        """生成详细结果"""
        detailed_results = []
        
        for i, result in enumerate(results):
            detailed_result = {
                'rank': i + 1,
                'basic_info': {
                    'symbol': result.symbol,
                    'date': result.date,
                    'price': result.price,
                    'volume': result.volume,
                    'market_cap': result.market_cap,
                    'industry': result.industry
                },
                'signal_info': {
                    'strength': result.signal_strength,
                    'reason': result.signal_reason,
                    'quality_level': self._get_quality_level(result.signal_strength)
                },
                'conditions_analysis': self._analyze_conditions(result.conditions_met),
                'risk_indicators': self._assess_individual_risk(result)
            }
            
            detailed_results.append(detailed_result)
        
        return detailed_results
    
    def _generate_statistical_analysis(self, results: List[ScreeningResult]) -> Dict:
        """生成统计分析"""
        if not results:
            return {'message': '无数据进行统计分析'}
        
        signal_strengths = [r.signal_strength for r in results]
        prices = [r.price for r in results]
        volumes = [r.volume for r in results]
        
        # 信号强度分布
        strength_distribution = {
            '0.6-0.7': len([s for s in signal_strengths if 0.6 <= s < 0.7]),
            '0.7-0.8': len([s for s in signal_strengths if 0.7 <= s < 0.8]),
            '0.8-0.9': len([s for s in signal_strengths if 0.8 <= s < 0.9]),
            '0.9-1.0': len([s for s in signal_strengths if 0.9 <= s <= 1.0])
        }
        
        # 价格分布
        price_ranges = {
            '0-10': len([p for p in prices if 0 <= p < 10]),
            '10-50': len([p for p in prices if 10 <= p < 50]),
            '50-100': len([p for p in prices if 50 <= p < 100]),
            '100+': len([p for p in prices if p >= 100])
        }
        
        # 条件统计
        condition_stats = {}
        for result in results:
            for condition, met in result.conditions_met.items():
                if condition != 'rank' and met:
                    condition_stats[condition] = condition_stats.get(condition, 0) + 1
        
        return {
            'signal_strength_analysis': {
                'mean': sum(signal_strengths) / len(signal_strengths),
                'median': sorted(signal_strengths)[len(signal_strengths) // 2],
                'std_dev': self._calculate_std_dev(signal_strengths),
                'distribution': strength_distribution
            },
            'price_analysis': {
                'mean': sum(prices) / len(prices),
                'median': sorted(prices)[len(prices) // 2],
                'min': min(prices),
                'max': max(prices),
                'distribution': price_ranges
            },
            'volume_analysis': {
                'mean': sum(volumes) / len(volumes),
                'median': sorted(volumes)[len(volumes) // 2],
                'min': min(volumes),
                'max': max(volumes)
            },
            'condition_frequency': dict(sorted(condition_stats.items(), key=lambda x: x[1], reverse=True)),
            'quality_distribution': {
                'high_quality': len([r for r in results if r.signal_strength >= 0.8]),
                'medium_quality': len([r for r in results if 0.7 <= r.signal_strength < 0.8]),
                'acceptable_quality': len([r for r in results if 0.6 <= r.signal_strength < 0.7])
            }
        }
    
    def _generate_market_analysis(self, results: List[ScreeningResult]) -> Dict:
        """生成市场分析"""
        if not results:
            return {'message': '无数据进行市场分析'}
        
        # 行业分布
        industry_distribution = {}
        for result in results:
            industry = result.industry or '未知'
            industry_distribution[industry] = industry_distribution.get(industry, 0) + 1
        
        # 价格区间分析
        price_analysis = {
            'low_price_stocks': len([r for r in results if r.price < 10]),
            'mid_price_stocks': len([r for r in results if 10 <= r.price < 50]),
            'high_price_stocks': len([r for r in results if r.price >= 50])
        }
        
        # 成交量活跃度分析
        volumes = [r.volume for r in results]
        avg_volume = sum(volumes) / len(volumes)
        
        volume_activity = {
            'high_activity': len([r for r in results if r.volume > avg_volume * 1.5]),
            'normal_activity': len([r for r in results if avg_volume * 0.5 <= r.volume <= avg_volume * 1.5]),
            'low_activity': len([r for r in results if r.volume < avg_volume * 0.5])
        }
        
        return {
            'industry_distribution': dict(sorted(industry_distribution.items(), key=lambda x: x[1], reverse=True)),
            'price_segment_analysis': price_analysis,
            'volume_activity_analysis': volume_activity,
            'market_characteristics': self._analyze_market_characteristics(results)
        }
    
    def _generate_risk_assessment(self, results: List[ScreeningResult]) -> Dict:
        """生成风险评估"""
        if not results:
            return {'message': '无数据进行风险评估'}
        
        # 信号强度风险评估
        low_strength_count = len([r for r in results if r.signal_strength < 0.7])
        risk_level = 'low'
        
        if low_strength_count > len(results) * 0.5:
            risk_level = 'high'
        elif low_strength_count > len(results) * 0.3:
            risk_level = 'medium'
        
        # 价格风险评估
        high_price_count = len([r for r in results if r.price > 100])
        price_risk = 'low'
        
        if high_price_count > len(results) * 0.3:
            price_risk = 'medium'
        if high_price_count > len(results) * 0.5:
            price_risk = 'high'
        
        return {
            'overall_risk_level': risk_level,
            'signal_quality_risk': {
                'level': 'high' if low_strength_count > len(results) * 0.5 else 'medium' if low_strength_count > len(results) * 0.3 else 'low',
                'low_quality_count': low_strength_count,
                'percentage': low_strength_count / len(results)
            },
            'price_risk': {
                'level': price_risk,
                'high_price_count': high_price_count,
                'percentage': high_price_count / len(results)
            },
            'diversification_risk': self._assess_diversification_risk(results),
            'recommendations': self._generate_risk_recommendations(results)
        }
    
    def _generate_recommendations(self, results: List[ScreeningResult], 
                                 screening_stats: Dict) -> Dict:
        """生成投资建议"""
        if not results:
            return {
                'primary_recommendation': '当前市场条件下未发现符合PVFRS策略的投资机会',
                'suggestions': ['等待更好的市场时机', '调整筛选参数', '考虑其他投资策略']
            }
        
        recommendations = []
        
        # 基于信号质量的建议
        high_quality_count = len([r for r in results if r.signal_strength >= 0.8])
        
        if high_quality_count >= 5:
            recommendations.append('发现多只高质量信号股票，建议重点关注前5名')
        elif high_quality_count >= 1:
            recommendations.append('发现少量高质量信号股票，建议谨慎选择')
        else:
            recommendations.append('当前信号质量一般，建议等待更好机会')
        
        # 基于处理效率的建议
        success_rate = screening_stats.get('success_rate', 0)
        if success_rate < 0.8:
            recommendations.append('数据质量有待提升，建议检查数据源')
        
        # 基于入选率的建议
        qualification_rate = screening_stats.get('qualification_rate', 0)
        if qualification_rate < 0.05:
            recommendations.append('入选率较低，可考虑适当放宽筛选条件')
        elif qualification_rate > 0.2:
            recommendations.append('入选率较高，可考虑提高筛选标准')
        
        return {
            'primary_recommendation': self._get_primary_recommendation(results),
            'detailed_suggestions': recommendations,
            'top_picks': [r.symbol for r in results[:3]],
            'risk_management': [
                '建议分散投资，不要集中持有',
                '设置合理的止损位',
                '定期回顾和调整投资组合',
                '关注市场整体趋势变化'
            ],
            'follow_up_actions': [
                '持续监控选中股票的表现',
                '定期更新PVFRS分析',
                '结合基本面分析进行验证',
                '关注相关行业和市场动态'
            ]
        }
    
    def _format_number(self, value: Optional[float], decimal_places: Optional[int] = None) -> str:
        """格式化数字"""
        if value is None:
            return ''
        
        if not self.config.format_numbers:
            return str(value)
        
        places = decimal_places or self.config.decimal_places
        
        if isinstance(value, float):
            return f"{value:.{places}f}"
        else:
            return str(value)
    
    def _get_quality_level(self, signal_strength: float) -> str:
        """获取信号质量等级"""
        if signal_strength >= 0.9:
            return '优秀'
        elif signal_strength >= 0.8:
            return '良好'
        elif signal_strength >= 0.7:
            return '中等'
        else:
            return '一般'
    
    def _analyze_conditions(self, conditions_met: Dict[str, bool]) -> Dict:
        """分析满足的条件"""
        met_conditions = [k for k, v in conditions_met.items() if v and k != 'rank']
        total_conditions = len([k for k in conditions_met.keys() if k != 'rank'])
        
        return {
            'met_conditions': met_conditions,
            'total_conditions': total_conditions,
            'completion_rate': len(met_conditions) / total_conditions if total_conditions > 0 else 0,
            'key_strengths': self._identify_key_strengths(conditions_met)
        }
    
    def _identify_key_strengths(self, conditions_met: Dict[str, bool]) -> List[str]:
        """识别关键优势"""
        strengths = []
        
        if conditions_met.get('three_dimension_resonance', False):
            strengths.append('三维共振确认')
        if conditions_met.get('high_efficiency_trajectory', False):
            strengths.append('高效率演化轨道')
        if conditions_met.get('volume_price_resonance', False):
            strengths.append('量价共振')
        if conditions_met.get('strong_fund_support', False):
            strengths.append('强劲资金支撑')
        
        return strengths
    
    def _assess_individual_risk(self, result: ScreeningResult) -> Dict:
        """评估个股风险"""
        risk_factors = []
        risk_score = 0
        
        # 信号强度风险
        if result.signal_strength < 0.7:
            risk_factors.append('信号强度偏低')
            risk_score += 1
        
        # 价格风险
        if result.price > 100:
            risk_factors.append('价格较高')
            risk_score += 1
        elif result.price < 5:
            risk_factors.append('价格较低')
            risk_score += 1
        
        # 成交量风险
        if result.volume < 1000000:  # 100万
            risk_factors.append('成交量偏低')
            risk_score += 1
        
        risk_level = 'low'
        if risk_score >= 3:
            risk_level = 'high'
        elif risk_score >= 2:
            risk_level = 'medium'
        
        return {
            'risk_level': risk_level,
            'risk_score': risk_score,
            'risk_factors': risk_factors
        }
    
    def _calculate_std_dev(self, values: List[float]) -> float:
        """计算标准差"""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance ** 0.5
    
    def _analyze_market_characteristics(self, results: List[ScreeningResult]) -> List[str]:
        """分析市场特征"""
        characteristics = []
        
        # 价格特征
        prices = [r.price for r in results]
        avg_price = sum(prices) / len(prices)
        
        if avg_price > 50:
            characteristics.append('整体价格水平较高')
        elif avg_price < 20:
            characteristics.append('整体价格水平较低')
        else:
            characteristics.append('价格水平适中')
        
        # 信号强度特征
        strengths = [r.signal_strength for r in results]
        avg_strength = sum(strengths) / len(strengths)
        
        if avg_strength > 0.8:
            characteristics.append('信号质量整体较高')
        elif avg_strength < 0.7:
            characteristics.append('信号质量有待提升')
        
        return characteristics
    
    def _assess_diversification_risk(self, results: List[ScreeningResult]) -> Dict:
        """评估分散化风险"""
        # 行业集中度
        industries = [r.industry for r in results if r.industry]
        industry_concentration = len(set(industries)) / len(industries) if industries else 0
        
        # 价格集中度
        price_ranges = {
            'low': len([r for r in results if r.price < 20]),
            'mid': len([r for r in results if 20 <= r.price < 100]),
            'high': len([r for r in results if r.price >= 100])
        }
        
        max_price_concentration = max(price_ranges.values()) / len(results)
        
        return {
            'industry_diversification': 'good' if industry_concentration > 0.7 else 'poor',
            'price_diversification': 'good' if max_price_concentration < 0.6 else 'poor',
            'overall_diversification': 'good' if industry_concentration > 0.7 and max_price_concentration < 0.6 else 'needs_improvement'
        }
    
    def _generate_risk_recommendations(self, results: List[ScreeningResult]) -> List[str]:
        """生成风险管理建议"""
        recommendations = []
        
        # 基于信号强度的建议
        low_strength_count = len([r for r in results if r.signal_strength < 0.7])
        if low_strength_count > len(results) * 0.3:
            recommendations.append('部分股票信号强度偏低，建议重点关注高强度信号股票')
        
        # 基于价格的建议
        high_price_count = len([r for r in results if r.price > 100])
        if high_price_count > 0:
            recommendations.append('包含高价股票，注意价格波动风险')
        
        # 基于成交量的建议
        low_volume_count = len([r for r in results if r.volume < 1000000])
        if low_volume_count > 0:
            recommendations.append('部分股票成交量较低，注意流动性风险')
        
        return recommendations
    
    def _get_primary_recommendation(self, results: List[ScreeningResult]) -> str:
        """获取主要投资建议"""
        if not results:
            return '当前未发现符合条件的投资机会'
        
        high_quality_count = len([r for r in results if r.signal_strength >= 0.8])
        
        if high_quality_count >= 3:
            return f'发现{high_quality_count}只高质量信号股票，建议重点关注并适度配置'
        elif high_quality_count >= 1:
            return f'发现{high_quality_count}只高质量信号股票，建议谨慎选择并控制仓位'
        else:
            return '当前信号质量一般，建议等待更好的投资机会或降低预期收益'
    
    def set_config(self, config: ReportConfig) -> None:
        """设置报告配置"""
        self.config = config
    
    def get_config(self) -> ReportConfig:
        """获取当前报告配置"""
        return self.config