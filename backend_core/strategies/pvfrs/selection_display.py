"""
PVFRS策略选股结果展示功能
实现选股结果列表的数据处理和格式化
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
import logging
from dataclasses import dataclass, asdict

from .models import PVFRSIndicators, SignalType
from .frontend_interface import SelectionResult, FrontendInterface

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class SelectionDisplayItem:
    """选股展示项数据结构"""
    # 基本信息
    symbol: str                    # 股票代码
    name: str                     # 股票名称
    current_price: float          # 当前价格
    price_change: float           # 价格变化
    price_change_pct: float       # 价格变化百分比
    
    # PVFRS信号信息
    signal_strength: float        # 信号强度 (0-1)
    signal_level: str            # 信号等级 (强/中/弱)
    signal_reason: str           # 信号原因
    
    # 满足条件信息
    conditions_met: Dict[str, bool]  # 满足的条件
    conditions_summary: str          # 条件汇总描述
    
    # 关键指标
    resonance_strength: float     # 共振强度
    amplitude_ratio: float        # 幅度系数
    efficiency_ratio: float       # 效率比
    frequency_advantage: bool     # 频率优势
    
    # 维度评分
    price_dimension_score: float  # 价格维度评分
    frequency_dimension_score: float  # 频率维度评分
    volume_dimension_score: float     # 成交量维度评分
    
    # 展示辅助信息
    rank: int                     # 排名
    timestamp: str               # 时间戳
    recommendation: str          # 推荐等级
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return asdict(self)


class SelectionDisplayFormatter:
    """选股结果展示格式化器
    
    负责将选股结果转换为适合前端展示的格式，
    包含股票代码、名称、信号强度、满足条件等信息。
    """
    
    def __init__(self):
        """初始化格式化器"""
        # 信号强度等级阈值
        self.strength_thresholds = {
            'strong': 0.8,    # 强信号
            'medium': 0.5,    # 中等信号
            'weak': 0.0       # 弱信号
        }
        
        # 推荐等级映射
        self.recommendation_mapping = {
            'strong': '强烈推荐',
            'medium': '一般推荐', 
            'weak': '谨慎关注'
        }
        
        # 条件描述映射
        self.condition_descriptions = {
            'price_dimension_valid': '价格维度',
            'frequency_dimension_valid': '频率维度',
            'volume_dimension_valid': '成交量维度',
            'three_dimension_resonance': '三维共振',
            'high_efficiency_trajectory': '高效率轨道',
            'macro_displacement_positive': '宏观位移向上',
            'instant_deviation_positive': '即时强度向上',
            'frequency_advantage': '频率权重(F>Z)',
            'volume_efficiency': '成交量效率',
            'volume_price_resonance': '量价共振',
            'amplitude_ratio_valid': '幅度系数有效'
        }
    
    def format_selection_results(self, selection_results: List[SelectionResult]) -> List[SelectionDisplayItem]:
        """格式化选股结果列表
        
        Args:
            selection_results: 原始选股结果列表
            
        Returns:
            List[SelectionDisplayItem]: 格式化后的展示项列表
        """
        try:
            display_items = []
            
            for rank, result in enumerate(selection_results, 1):
                try:
                    display_item = self._format_single_result(result, rank)
                    display_items.append(display_item)
                except Exception as e:
                    logger.warning(f"格式化股票 {result.symbol} 结果失败: {str(e)}")
                    continue
            
            logger.info(f"成功格式化 {len(display_items)} 个选股结果")
            return display_items
            
        except Exception as e:
            logger.error(f"格式化选股结果失败: {str(e)}")
            return []
    
    def _format_single_result(self, result: SelectionResult, rank: int) -> SelectionDisplayItem:
        """格式化单个选股结果
        
        Args:
            result: 选股结果
            rank: 排名
            
        Returns:
            SelectionDisplayItem: 格式化后的展示项
        """
        # 计算信号等级
        signal_level = self._calculate_signal_level(result.signal_strength)
        
        # 生成条件汇总
        conditions_summary = self._generate_conditions_summary(result.conditions_met)
        
        # 计算维度评分
        dimension_scores = self._calculate_dimension_scores(result.indicators, result.conditions_met)
        
        # 计算价格变化（这里需要历史价格数据，暂时设为0）
        price_change = 0.0
        price_change_pct = 0.0
        
        # 生成推荐等级
        recommendation = self.recommendation_mapping.get(signal_level, '观望')
        
        # 提取关键指标（兼容字典和对象格式）
        if isinstance(result.indicators, dict):
            resonance_strength = result.indicators.get('resonance_strength', 0.0)
            amplitude_ratio = result.indicators.get('amplitude_ratio', 0.0)
            efficiency_ratio = result.indicators.get('efficiency_ratio', 0.0)
            frequency_advantage = result.indicators.get('frequency_dimension', {}).get('frequency_advantage', False)
        else:
            # PVFRSIndicators对象
            resonance_strength = getattr(result.indicators, 'resonance_strength', 0.0)
            amplitude_ratio = getattr(result.indicators, 'amplitude_ratio', 0.0)
            efficiency_ratio = getattr(result.indicators, 'efficiency_ratio', 0.0)
            frequency_advantage = getattr(result.indicators, 'frequency_advantage', False)
        
        return SelectionDisplayItem(
            # 基本信息
            symbol=result.symbol,
            name=result.name,
            current_price=result.price,
            price_change=price_change,
            price_change_pct=price_change_pct,
            
            # PVFRS信号信息
            signal_strength=result.signal_strength,
            signal_level=signal_level,
            signal_reason=getattr(result, 'signal_reason', '三维共振信号'),
            
            # 满足条件信息
            conditions_met=result.conditions_met,
            conditions_summary=conditions_summary,
            
            # 关键指标
            resonance_strength=resonance_strength,
            amplitude_ratio=amplitude_ratio,
            efficiency_ratio=efficiency_ratio,
            frequency_advantage=frequency_advantage,
            
            # 维度评分
            price_dimension_score=dimension_scores['price'],
            frequency_dimension_score=dimension_scores['frequency'],
            volume_dimension_score=dimension_scores['volume'],
            
            # 展示辅助信息
            rank=rank,
            timestamp=getattr(result, 'timestamp', datetime.now().isoformat()),
            recommendation=recommendation
        )
    
    def _calculate_signal_level(self, signal_strength: float) -> str:
        """计算信号等级
        
        Args:
            signal_strength: 信号强度
            
        Returns:
            str: 信号等级
        """
        if signal_strength >= self.strength_thresholds['strong']:
            return 'strong'
        elif signal_strength >= self.strength_thresholds['medium']:
            return 'medium'
        else:
            return 'weak'
    
    def _generate_conditions_summary(self, conditions_met: Dict[str, bool]) -> str:
        """生成条件汇总描述
        
        Args:
            conditions_met: 满足的条件字典
            
        Returns:
            str: 条件汇总描述
        """
        met_conditions = []
        
        for condition, is_met in conditions_met.items():
            if is_met and condition in self.condition_descriptions:
                met_conditions.append(self.condition_descriptions[condition])
        
        if not met_conditions:
            return "无满足条件"
        
        if len(met_conditions) <= 3:
            return "、".join(met_conditions)
        else:
            return f"{met_conditions[0]}、{met_conditions[1]}等{len(met_conditions)}项"
    
    def _calculate_dimension_scores(self, indicators: PVFRSIndicators, 
                                  conditions_met: Dict[str, bool]) -> Dict[str, float]:
        """计算各维度评分
        
        Args:
            indicators: PVFRS指标
            conditions_met: 满足的条件
            
        Returns:
            Dict[str, float]: 各维度评分
        """
        # 如果indicators是字典类型，直接使用
        if isinstance(indicators, dict):
            price_dim = indicators.get('price_dimension', {})
            frequency_dim = indicators.get('frequency_dimension', {})
            volume_dim = indicators.get('volume_dimension', {})
            
            # 价格维度评分
            price_score = 0.0
            if price_dim.get('macro_displacement', 0) > 0:
                price_score += 0.4
            if price_dim.get('instant_deviation', 0) > 0:
                price_score += 0.4
            if price_dim.get('price_dimension_valid', False):
                price_score += 0.2
            
            # 频率维度评分
            frequency_score = 0.0
            if frequency_dim.get('frequency_advantage', False):
                frequency_score += 0.6
            if frequency_dim.get('frequency_dimension_valid', False):
                frequency_score += 0.4
            
            # 成交量维度评分
            volume_score = 0.0
            if volume_dim.get('volume_efficiency', False):
                volume_score += 0.4
            if volume_dim.get('volume_price_resonance', False):
                volume_score += 0.4
            if volume_dim.get('efficiency_ratio', 0) > 1.0:
                volume_score += 0.2
            
            return {
                'price': min(1.0, price_score),
                'frequency': min(1.0, frequency_score),
                'volume': min(1.0, volume_score)
            }
        
        # 原有逻辑（兼容PVFRSIndicators对象）
        # 价格维度评分
        price_score = 0.0
        if conditions_met.get('macro_displacement_positive', False):
            price_score += 0.4
        if conditions_met.get('instant_deviation_positive', False):
            price_score += 0.4
        if conditions_met.get('amplitude_ratio_valid', False):
            price_score += 0.2
        
        # 频率维度评分
        frequency_score = 0.0
        if hasattr(indicators, 'frequency_advantage') and indicators.frequency_advantage:
            frequency_score += 0.6
        if conditions_met.get('frequency_dimension_valid', False):
            frequency_score += 0.4
        
        # 成交量维度评分
        volume_score = 0.0
        if conditions_met.get('volume_efficiency', False):
            volume_score += 0.4
        if conditions_met.get('volume_price_resonance', False):
            volume_score += 0.4
        if hasattr(indicators, 'efficiency_ratio') and indicators.efficiency_ratio > 1.0:
            volume_score += 0.2
        
        return {
            'price': min(1.0, price_score),
            'frequency': min(1.0, frequency_score),
            'volume': min(1.0, volume_score)
        }


class SelectionDisplayManager:
    """选股结果展示管理器
    
    管理选股结果的展示逻辑，包括数据获取、格式化、排序、分页等功能。
    """
    
    def __init__(self, frontend_interface: FrontendInterface):
        """初始化展示管理器
        
        Args:
            frontend_interface: 前端接口实例
        """
        self.frontend_interface = frontend_interface
        self.formatter = SelectionDisplayFormatter()
        
        # 展示配置
        self.page_size = 20           # 每页显示数量
        self.sort_by = 'signal_strength'  # 默认排序字段
        self.sort_order = 'desc'      # 排序顺序
        self.filter_min_strength = 0.3  # 最低信号强度过滤
        
        logger.info("选股结果展示管理器初始化完成")
    
    def get_display_results(self, page: int = 1, page_size: Optional[int] = None,
                          sort_by: Optional[str] = None, sort_order: Optional[str] = None,
                          filter_conditions: Optional[Dict] = None) -> Dict:
        """获取展示结果
        
        Args:
            page: 页码（从1开始）
            page_size: 每页大小
            sort_by: 排序字段
            sort_order: 排序顺序 ('asc' 或 'desc')
            filter_conditions: 过滤条件
            
        Returns:
            Dict: 包含展示结果和分页信息的字典
        """
        try:
            # 使用默认值
            page_size = page_size or self.page_size
            sort_by = sort_by or self.sort_by
            sort_order = sort_order or self.sort_order
            filter_conditions = filter_conditions or {}
            
            # 获取原始选股结果
            selection_results = self.frontend_interface.get_selection_results()
            
            # 格式化结果
            display_items = self.formatter.format_selection_results(selection_results)
            
            # 应用过滤
            filtered_items = self._apply_filters(display_items, filter_conditions)
            
            # 应用排序
            sorted_items = self._apply_sorting(filtered_items, sort_by, sort_order)
            
            # 应用分页
            total_count = len(sorted_items)
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            page_items = sorted_items[start_index:end_index]
            
            # 计算分页信息
            total_pages = (total_count + page_size - 1) // page_size
            
            result = {
                'items': [item.to_dict() for item in page_items],
                'pagination': {
                    'current_page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': total_pages,
                    'has_previous': page > 1,
                    'has_next': page < total_pages
                },
                'sorting': {
                    'sort_by': sort_by,
                    'sort_order': sort_order
                },
                'filtering': {
                    'applied_filters': filter_conditions,
                    'filtered_count': len(filtered_items),
                    'original_count': len(display_items)
                },
                'summary': self._generate_page_summary(page_items),
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"获取展示结果成功，页码: {page}, 数量: {len(page_items)}")
            return result
            
        except Exception as e:
            logger.error(f"获取展示结果失败: {str(e)}")
            return {
                'error': f"获取展示结果失败: {str(e)}",
                'items': [],
                'pagination': {'current_page': 1, 'page_size': page_size, 'total_count': 0, 'total_pages': 0},
                'timestamp': datetime.now().isoformat()
            }
    
    def get_strength_distribution(self) -> Dict:
        """获取信号强度分布统计
        
        Returns:
            Dict: 信号强度分布信息
        """
        try:
            selection_results = self.frontend_interface.get_selection_results()
            display_items = self.formatter.format_selection_results(selection_results)
            
            # 统计各强度等级数量
            distribution = {'strong': 0, 'medium': 0, 'weak': 0}
            strength_values = []
            
            for item in display_items:
                distribution[item.signal_level] += 1
                strength_values.append(item.signal_strength)
            
            # 计算统计指标
            total_count = len(display_items)
            avg_strength = sum(strength_values) / total_count if total_count > 0 else 0
            max_strength = max(strength_values) if strength_values else 0
            min_strength = min(strength_values) if strength_values else 0
            
            return {
                'distribution': {
                    'strong': {'count': distribution['strong'], 'percentage': distribution['strong'] / total_count * 100 if total_count > 0 else 0},
                    'medium': {'count': distribution['medium'], 'percentage': distribution['medium'] / total_count * 100 if total_count > 0 else 0},
                    'weak': {'count': distribution['weak'], 'percentage': distribution['weak'] / total_count * 100 if total_count > 0 else 0}
                },
                'statistics': {
                    'total_count': total_count,
                    'average_strength': avg_strength,
                    'max_strength': max_strength,
                    'min_strength': min_strength
                },
                'thresholds': self.formatter.strength_thresholds,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取信号强度分布失败: {str(e)}")
            return {'error': f"获取信号强度分布失败: {str(e)}"}
    
    def get_condition_statistics(self) -> Dict:
        """获取条件满足统计
        
        Returns:
            Dict: 条件满足统计信息
        """
        try:
            selection_results = self.frontend_interface.get_selection_results()
            display_items = self.formatter.format_selection_results(selection_results)
            
            # 统计各条件满足情况
            condition_stats = {}
            total_count = len(display_items)
            
            if total_count > 0:
                # 收集所有条件
                all_conditions = set()
                for item in display_items:
                    all_conditions.update(item.conditions_met.keys())
                
                # 统计每个条件
                for condition in all_conditions:
                    met_count = sum(1 for item in display_items if item.conditions_met.get(condition, False))
                    condition_stats[condition] = {
                        'name': self.formatter.condition_descriptions.get(condition, condition),
                        'met_count': met_count,
                        'total_count': total_count,
                        'percentage': met_count / total_count * 100,
                        'not_met_count': total_count - met_count
                    }
            
            return {
                'condition_statistics': condition_stats,
                'total_stocks': total_count,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取条件统计失败: {str(e)}")
            return {'error': f"获取条件统计失败: {str(e)}"}
    
    def _apply_filters(self, items: List[SelectionDisplayItem], 
                      filter_conditions: Dict) -> List[SelectionDisplayItem]:
        """应用过滤条件
        
        Args:
            items: 原始项目列表
            filter_conditions: 过滤条件
            
        Returns:
            List[SelectionDisplayItem]: 过滤后的项目列表
        """
        filtered_items = items
        
        # 信号强度过滤
        min_strength = filter_conditions.get('min_strength', self.filter_min_strength)
        if min_strength > 0:
            filtered_items = [item for item in filtered_items if item.signal_strength >= min_strength]
        
        # 信号等级过滤
        signal_levels = filter_conditions.get('signal_levels', [])
        if signal_levels:
            filtered_items = [item for item in filtered_items if item.signal_level in signal_levels]
        
        # 条件过滤
        required_conditions = filter_conditions.get('required_conditions', [])
        if required_conditions:
            filtered_items = [
                item for item in filtered_items 
                if all(item.conditions_met.get(cond, False) for cond in required_conditions)
            ]
        
        # 股票代码过滤
        symbols = filter_conditions.get('symbols', [])
        if symbols:
            filtered_items = [item for item in filtered_items if item.symbol in symbols]
        
        return filtered_items
    
    def _apply_sorting(self, items: List[SelectionDisplayItem], 
                      sort_by: str, sort_order: str) -> List[SelectionDisplayItem]:
        """应用排序
        
        Args:
            items: 项目列表
            sort_by: 排序字段
            sort_order: 排序顺序
            
        Returns:
            List[SelectionDisplayItem]: 排序后的项目列表
        """
        reverse = (sort_order.lower() == 'desc')
        
        try:
            if sort_by == 'signal_strength':
                return sorted(items, key=lambda x: x.signal_strength, reverse=reverse)
            elif sort_by == 'resonance_strength':
                return sorted(items, key=lambda x: x.resonance_strength, reverse=reverse)
            elif sort_by == 'amplitude_ratio':
                return sorted(items, key=lambda x: x.amplitude_ratio, reverse=reverse)
            elif sort_by == 'efficiency_ratio':
                return sorted(items, key=lambda x: x.efficiency_ratio, reverse=reverse)
            elif sort_by == 'symbol':
                return sorted(items, key=lambda x: x.symbol, reverse=reverse)
            elif sort_by == 'name':
                return sorted(items, key=lambda x: x.name, reverse=reverse)
            elif sort_by == 'current_price':
                return sorted(items, key=lambda x: x.current_price, reverse=reverse)
            else:
                # 默认按信号强度排序
                return sorted(items, key=lambda x: x.signal_strength, reverse=True)
        except Exception as e:
            logger.warning(f"排序失败，使用默认排序: {str(e)}")
            return sorted(items, key=lambda x: x.signal_strength, reverse=True)
    
    def _generate_page_summary(self, items: List[SelectionDisplayItem]) -> Dict:
        """生成页面汇总信息
        
        Args:
            items: 当前页面项目列表
            
        Returns:
            Dict: 页面汇总信息
        """
        if not items:
            return {
                'count': 0,
                'avg_signal_strength': 0,
                'strength_distribution': {'strong': 0, 'medium': 0, 'weak': 0}
            }
        
        # 统计信号强度分布
        distribution = {'strong': 0, 'medium': 0, 'weak': 0}
        total_strength = 0
        
        for item in items:
            distribution[item.signal_level] += 1
            total_strength += item.signal_strength
        
        return {
            'count': len(items),
            'avg_signal_strength': total_strength / len(items),
            'strength_distribution': distribution,
            'top_stock': {
                'symbol': items[0].symbol,
                'name': items[0].name,
                'signal_strength': items[0].signal_strength
            } if items else None
        }
    
    def set_display_config(self, page_size: Optional[int] = None, 
                          sort_by: Optional[str] = None, sort_order: Optional[str] = None,
                          filter_min_strength: Optional[float] = None) -> None:
        """设置展示配置
        
        Args:
            page_size: 每页大小
            sort_by: 默认排序字段
            sort_order: 默认排序顺序
            filter_min_strength: 最低信号强度过滤
        """
        if page_size is not None:
            self.page_size = page_size
        if sort_by is not None:
            self.sort_by = sort_by
        if sort_order is not None:
            self.sort_order = sort_order
        if filter_min_strength is not None:
            self.filter_min_strength = filter_min_strength
        
        logger.info(f"展示配置更新: page_size={self.page_size}, sort_by={self.sort_by}")


# 便捷函数
def create_selection_display_manager(frontend_interface: FrontendInterface) -> SelectionDisplayManager:
    """创建选股结果展示管理器
    
    Args:
        frontend_interface: 前端接口实例
        
    Returns:
        SelectionDisplayManager: 展示管理器实例
    """
    return SelectionDisplayManager(frontend_interface)