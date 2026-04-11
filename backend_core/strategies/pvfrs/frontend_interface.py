"""
PVFRS策略前端接口

提供前端界面与PVFRS策略系统交互的接口。
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
import logging

from .pvfrs_system import PVFRSSystem
from .models import (
    StockSelectionResult, StockDetail, MarketData,
    PVFRSIndicators, PVFRSException
)

logger = logging.getLogger(__name__)


class FrontendInterface:
    """PVFRS策略前端接口类
    
    提供前端界面所需的全部功能接口，包括选股结果获取、
    股票详情查询、缓存管理等。
    """
    
    def __init__(self, 
                 pvfrs_system: Optional[PVFRSSystem] = None,
                 stock_name_mapping: Optional[Dict[str, str]] = None):
        """初始化前端接口
        
        Args:
            pvfrs_system: PVFRS策略系统实例
            stock_name_mapping: 股票代码到名称的映射
        """
        self.pvfrs_system = pvfrs_system or PVFRSSystem()
        self.stock_name_mapping = stock_name_mapping or {}
        
        # 缓存配置
        self.cache_enabled = True
        self.cache_duration_minutes = 5
        self._selection_cache = {}
        self._detail_cache = {}
        
        # 选股配置
        self.max_selection_results = 10000  # 默认不限制，设置一个很大的值
        self.min_signal_strength = 0.3
        
        logger.info("PVFRS前端接口初始化完成")
    
    def get_selection_results(self, date: Optional[str] = None, stock_pool: Optional[List[str]] = None, market: str = 'all') -> List[StockSelectionResult]:
        """获取选股结果
        
        Args:
            date: 查询日期，格式为YYYY-MM-DD，默认为当前日期
            stock_pool: 可选，指定股票代码列表。如果提供，将只从这些股票中筛选。
            market: 股票市场，可选 'cn' (A股), 'hk' (港股), 'all' (两者)
            
        Returns:
            List[StockSelectionResult]: 选股结果列表
        """
        try:
            if date is None:
                date = datetime.now().strftime('%Y-%m-%d')
            
            # 检查缓存 (注意：如果指定了stock_pool，则不使用常规缓存，或者需要通过stock_pool生成特定的cache_key)
            # 为简单起见，如果指定了stock_pool，暂时跳过缓存读取，以免返回全部股票的缓存结果
            cache_key = f"selection_{date}_{market}"
            if stock_pool is None and self.cache_enabled and self._is_cache_valid(cache_key):
                logger.info(f"从缓存获取选股结果: {date}")
                return self._selection_cache[cache_key]['data']
            
            # 获取股票池
            # 如果未提供stock_pool，则根据market参数获取对应市场的股票池
            if stock_pool is None:
                stock_pool = self._get_stock_pool(market=market)
            else:
                # 如果提供了 stock_pool（如自选股），也要确保唯一性
                stock_pool = list(dict.fromkeys(stock_pool))
                
            logger.info(f"开始选股分析，股票池大小: {len(stock_pool)}")
            
            # 执行选股
            selection_results = []
            for symbol in stock_pool:
                try:
                    # 获取股票数据
                    stock_data = self._get_stock_data(symbol)
                    if not stock_data:
                        continue
                    
                    # 执行策略分析
                    analysis_result = self.pvfrs_system.analyze_stock(symbol, stock_data)
                    
                    # 检查是否满足选股条件
                    if analysis_result['signal_strength'] >= self.min_signal_strength:
                        # 获取股票名称
                        stock_name = self._get_stock_name(symbol)
                        
                        # 提取和格式化维度分析结果
                        strategy_analysis = analysis_result.get('strategy_analysis', {})
                        
                        # 构建完整的indicators字典，包含维度分析结果
                        indicators = {
                            # 基础指标
                            'resonance_strength': analysis_result.get('overall_score', 0.0),
                            'amplitude_ratio': 0.0,  # 默认值，后续从维度分析中提取
                            'efficiency_ratio': 0.0,  # 默认值，后续从维度分析中提取
                            
                            # 维度分析结果
                            'price_dimension': strategy_analysis.get('price_dimension', {}),
                            'frequency_dimension': strategy_analysis.get('frequency_dimension', {}),
                            'volume_dimension': strategy_analysis.get('volume_dimension', {}),
                            
                            # 其他分析结果
                            'investment_advice': analysis_result.get('investment_advice', {}),
                            'strategy_analysis': strategy_analysis,
                            'resonance_analysis': analysis_result.get('resonance_analysis', {}),
                            'entry_timing_analysis': strategy_analysis.get('entry_timing_analysis', {})
                        }
                        
                        # 从维度分析中提取具体指标值
                        price_dim = strategy_analysis.get('price_dimension', {})
                        volume_dim = strategy_analysis.get('volume_dimension', {})
                        
                        # 提取幅度系数（从价格维度）
                        if 'macro_displacement' in price_dim and 'avg_price_20d' in price_dim:
                            avg_price = price_dim.get('avg_price_20d', 1.0)
                            if avg_price > 0:
                                indicators['amplitude_ratio'] = abs(price_dim.get('macro_displacement', 0.0)) / avg_price
                        
                        # 提取效率比（从成交量维度）
                        if 'efficiency_ratio' in volume_dim:
                            indicators['efficiency_ratio'] = volume_dim.get('efficiency_ratio', 0.0)
                        
                        # 得分明细（共振强度与各维度得分，供前端展示）
                        resonance_detection = strategy_analysis.get('resonance_detection', {})
                        dimension_scores = resonance_detection.get('dimension_scores', {})
                        indicators['score_detail'] = {
                            'resonance_strength': resonance_detection.get('resonance_strength'),
                            'price_score': dimension_scores.get('price_score'),
                            'frequency_score': dimension_scores.get('frequency_score'),
                            'volume_score': dimension_scores.get('volume_score'),
                        }
                        
                        # 创建选股结果
                        result = StockSelectionResult(
                            symbol=symbol,
                            name=stock_name,
                            price=stock_data[-1].close,
                            signal_strength=analysis_result['signal_strength'],
                            indicators=indicators,
                            conditions_met=analysis_result.get('conditions_met', {}),
                            analysis_time=analysis_result.get('analysis_time', datetime.now().isoformat())
                        )
                        
                        selection_results.append(result)
                
                except Exception as e:
                    logger.warning(f"分析股票 {symbol} 失败: {str(e)}")
                    continue
            
            # 按信号强度排序
            selection_results.sort(key=lambda x: x.signal_strength, reverse=True)
            
            # 限制结果数量
            if len(selection_results) > self.max_selection_results:
                selection_results = selection_results[:self.max_selection_results]
            
            # 更新缓存
            if self.cache_enabled:
                self._selection_cache[cache_key] = {
                    'data': selection_results,
                    'timestamp': datetime.now()
                }
            
            logger.info(f"选股完成，共筛选出 {len(selection_results)} 只股票")
            return selection_results
            
        except Exception as e:
            logger.error(f"获取选股结果失败: {str(e)}")
            raise PVFRSException(f"获取选股结果失败: {str(e)}")
    
    def get_stock_detail(self, symbol: str) -> StockDetail:
        """获取股票详细信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            StockDetail: 股票详细信息
        """
        try:
            # 检查缓存
            cache_key = f"detail_{symbol}"
            if self.cache_enabled and self._is_cache_valid(cache_key):
                logger.info(f"从缓存获取股票详情: {symbol}")
                return self._detail_cache[cache_key]['data']
            
            # 获取股票数据
            stock_data = self._get_stock_data(symbol)
            if not stock_data:
                raise PVFRSException(f"无法获取股票 {symbol} 的数据")
            
            # 执行策略分析
            analysis_result = self.pvfrs_system.analyze_stock(symbol, stock_data)
            
            # 获取股票名称
            stock_name = self._get_stock_name(symbol)
            
            # 构建StockDetail
            stock_detail = StockDetail(
                symbol=symbol,
                name=stock_name,
                current_price=stock_data[-1].close,
                analysis_date=analysis_result['analysis_time'],
                
                # 三维分析结果
                price_dimension=analysis_result['strategy_analysis']['price_dimension'],
                frequency_dimension=analysis_result['strategy_analysis']['frequency_dimension'],
                volume_dimension=analysis_result['strategy_analysis']['volume_dimension'],
                
                # 综合分析结果
                resonance_analysis=analysis_result['resonance_analysis'],
                signal_analysis={
                    'signals': analysis_result['strategy_analysis']['signals'],
                    'signal_summary': analysis_result['strategy_analysis']['signal_summary'],
                    'entry_timing_analysis': analysis_result['strategy_analysis']['entry_timing_analysis']
                },
                strategy_assessment=analysis_result['strategy_analysis']['strategy_assessment'],
                
                # 投资建议和风险评估
                investment_advice=analysis_result['investment_advice'],
                risk_assessment=analysis_result['risk_assessment']
            )
            
            # 更新缓存
            if self.cache_enabled:
                self._detail_cache[cache_key] = {
                    'data': stock_detail,
                    'timestamp': datetime.now()
                }
            
            logger.info(f"获取股票 {symbol} 详细信息成功")
            return stock_detail
            
        except Exception as e:
            logger.error(f"获取股票 {symbol} 详细信息失败: {str(e)}")
            raise PVFRSException(f"获取股票 {symbol} 详细信息失败: {str(e)}")
    
    def refresh_results(self) -> bool:
        """刷新选股结果
        
        清除缓存并重新获取最新的选股结果。
        
        Returns:
            bool: 刷新是否成功
        """
        try:
            logger.info("刷新PVFRS选股结果")
            
            # 清除缓存
            self._selection_cache.clear()
            self._detail_cache.clear()
            
            # 重新获取选股结果
            current_date = datetime.now().strftime('%Y-%m-%d')
            selection_results = self.get_selection_results(current_date)
            
            logger.info(f"刷新完成，获取到 {len(selection_results)} 只股票")
            return True
            
        except Exception as e:
            logger.error(f"刷新选股结果失败: {str(e)}")
            return False
    
    def get_selection_summary(self) -> Dict:
        """获取选股汇总信息
        
        提供选股结果的统计汇总信息。
        
        Returns:
            Dict: 选股汇总信息
        """
        try:
            current_date = datetime.now().strftime('%Y-%m-%d')
            selection_results = self.get_selection_results(current_date)
            
            # 统计信息
            total_count = len(selection_results)
            high_strength_count = len([r for r in selection_results if r.signal_strength >= 0.8])
            medium_strength_count = len([r for r in selection_results if 0.5 <= r.signal_strength < 0.8])
            low_strength_count = len([r for r in selection_results if r.signal_strength < 0.5])
            
            # 条件满足统计
            condition_stats = {}
            if selection_results:
                all_conditions = set()
                for result in selection_results:
                    all_conditions.update(result.conditions_met.keys())
                
                for condition in all_conditions:
                    met_count = sum(1 for r in selection_results if r.conditions_met.get(condition, False))
                    condition_stats[condition] = {
                        'met_count': met_count,
                        'total_count': total_count,
                        'percentage': (met_count / total_count * 100) if total_count > 0 else 0
                    }
            
            # 信号强度分布
            strength_distribution = {
                'high': {'count': high_strength_count, 'threshold': '≥0.8'},
                'medium': {'count': medium_strength_count, 'threshold': '0.5-0.8'},
                'low': {'count': low_strength_count, 'threshold': '<0.5'}
            }
            
            # 平均指标（indicators 可能为 dict 或 PVFRSIndicators 对象）
            avg_indicators = {}
            if selection_results:
                indicators_sum = {
                    'resonance_strength': 0,
                    'amplitude_ratio': 0,
                    'efficiency_ratio': 0
                }

                def _triple(ind: Any) -> tuple:
                    if isinstance(ind, dict):
                        return (
                            float(ind.get('resonance_strength') or 0),
                            float(ind.get('amplitude_ratio') or 0),
                            float(ind.get('efficiency_ratio') or 0),
                        )
                    return (
                        float(getattr(ind, 'resonance_strength', 0) or 0),
                        float(getattr(ind, 'amplitude_ratio', 0) or 0),
                        float(getattr(ind, 'efficiency_ratio', 0) or 0),
                    )

                for result in selection_results:
                    rs, ar, er = _triple(result.indicators)
                    indicators_sum['resonance_strength'] += rs
                    indicators_sum['amplitude_ratio'] += ar
                    indicators_sum['efficiency_ratio'] += er

                avg_indicators = {
                    key: value / total_count for key, value in indicators_sum.items()
                }
            
            summary = {
                'summary_date': current_date,
                'summary_time': datetime.now().isoformat(),
                'total_stocks': total_count,
                'strength_distribution': strength_distribution,
                'condition_statistics': condition_stats,
                'average_indicators': avg_indicators,
                'top_stocks': [
                    {
                        'symbol': r.symbol,
                        'name': r.name,
                        'signal_strength': r.signal_strength,
                        'price': r.price
                    }
                    for r in selection_results[:10]  # 前10只股票
                ],
                'system_status': self.pvfrs_system.get_system_status()
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"获取选股汇总信息失败: {str(e)}")
            return {
                'error': f"获取选股汇总信息失败: {str(e)}",
                'summary_time': datetime.now().isoformat()
            }
    
    def set_stock_name_mapping(self, mapping: Dict[str, str]) -> None:
        """设置股票代码到名称的映射
        
        Args:
            mapping: 股票代码到名称的映射字典
        """
        self.stock_name_mapping.update(mapping)
        logger.info(f"更新股票名称映射，共 {len(mapping)} 条记录")
    
    def set_cache_config(self, enabled: bool = True, duration_minutes: int = 5) -> None:
        """设置缓存配置
        
        Args:
            enabled: 是否启用缓存
            duration_minutes: 缓存持续时间（分钟）
        """
        self.cache_enabled = enabled
        self.cache_duration_minutes = duration_minutes
        
        if not enabled:
            self._selection_cache.clear()
            self._detail_cache.clear()
        
        logger.info(f"缓存配置更新: enabled={enabled}, duration={duration_minutes}分钟")
    
    def set_selection_config(self, max_results: int = 10000, min_strength: float = 0.3) -> None:
        """设置选股配置
        
        Args:
            max_results: 最大返回结果数量，默认10000（实际不限制）
            min_strength: 最低信号强度阈值
        """
        self.max_selection_results = max_results
        self.min_signal_strength = min_strength
        logger.info(f"选股配置更新: max_results={max_results}, min_strength={min_strength}")
    
    def get_interface_status(self) -> Dict:
        """获取前端接口状态
        
        Returns:
            Dict: 接口状态信息
        """
        return {
            'interface_name': 'PVFRS Frontend Interface',
            'version': '1.0.0',
            'cache_enabled': self.cache_enabled,
            'cache_duration_minutes': self.cache_duration_minutes,
            'max_selection_results': self.max_selection_results,
            'stock_name_mapping_count': len(self.stock_name_mapping),
            'selection_cache_count': len(self._selection_cache),
            'detail_cache_count': len(self._detail_cache),
            'pvfrs_system_status': self.pvfrs_system.get_system_status()['system_ready']
        }

    def _get_stock_pool(self, market: str = 'all') -> List[str]:
        """获取股票池
        
        从数据库获取指定市场的股票代码
        
        Args:
            market: 市场类型，'cn' (A股), 'hk' (港股), 'all' (两者)
            
        Returns:
            List[str]: 股票代码列表
        """
        try:
            # 导入数据库相关模块
            import sys
            import os
            # 添加项目根目录到路径
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            sys.path.insert(0, project_root)
            
            from backend_api.database import get_db
            from backend_api.models import StockBasicInfo, StockBasicInfoHK
            
            # 获取数据库会话
            db = next(get_db())
            
            try:
                symbols_set = set()
                
                # 获取A股
                if market in ['cn', 'all']:
                    stocks_cn = db.query(StockBasicInfo).all()
                    for stock in stocks_cn:
                        symbols_set.add(str(stock.code))
                    logger.info(f"从数据库获取到 {len(stocks_cn)} 只A股股票")
                
                # 获取港股
                if market in ['hk', 'all']:
                    stocks_hk = db.query(StockBasicInfoHK).all()
                    # 确保港股代码格式正确 (港股恒指/主板代码为5位)
                    count_hk = 0
                    for stock in stocks_hk:
                        raw_code = str(stock.code).strip()
                        # 如果已经是6位且像是A股代码，且当前是仅筛选港股模式，则跳过
                        if len(raw_code) == 6 and market == 'hk':
                            continue
                            
                        # 处理港股代码补齐（通常补齐到5位）
                        # 只有当原始代码是纯数字且长度小于等于5时才补齐
                        if raw_code.isdigit() and len(raw_code) <= 5:
                            code = raw_code.zfill(5)
                        else:
                            code = raw_code
                            
                        # 如果补齐后长度仍然不是5位且当前是筛选港股模式，跳过
                        if market == 'hk' and len(code) != 5:
                            continue
                            
                        symbols_set.add(code)
                        count_hk += 1
                    logger.info(f"从数据库获取到 {count_hk} 只港股股票 (去重前)")
                
                stock_symbols = list(symbols_set)
                logger.info(f"股票池获取完成，去重后共 {len(stock_symbols)} 只股票 (市场: {market})")
                return stock_symbols
            
            except Exception as db_error:
                logger.error(f"数据库查询失败: {str(db_error)}")
                return []
            
            finally:
                db.close()
        
        except Exception as e:
            logger.error(f"获取股票池失败: {str(e)}")
            # 如果数据库获取失败，返回示例股票池
            return [
                '000001', '000002', '000858', '000876', '002415',
                '600000', '600036', '600519', '600887', '002415'
            ]

    def _get_stock_data(self, symbol: str) -> List[MarketData]:
        """获取股票数据
        
        从数据库获取股票历史行情数据。
        
        Args:
            symbol: 股票代码
            
        Returns:
            List[MarketData]: 股票数据列表
        """
        try:
            # 导入数据库相关模块
            import sys
            import os
            # 添加项目根目录到路径
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            sys.path.insert(0, project_root)
            
            from backend_api.database import get_db
            from backend_api.models import HistoricalQuotes, HistoricalQuotesHK
            from sqlalchemy import desc
            
            # 获取数据库会话
            db = next(get_db())
            
            try:
                # 判断是A股还是港股（A股通常为6位，港股通常为5位或更短）
                is_hk = (len(symbol) <= 5 and symbol.isdigit()) or not (symbol.startswith('6') or symbol.startswith('0') or symbol.startswith('3'))
                # 特殊情况：如果以0开头且长度为5，肯定是港股，不应被 startswith('0') 误判为A股
                if symbol.startswith('0') and len(symbol) == 5:
                    is_hk = True
                # A股确定的前缀
                if symbol.startswith(('60', '68', '00', '30', '43', '83', '87')):
                    if len(symbol) == 6:
                        is_hk = False
                
                market_data_list = []
                
                if is_hk:
                    # 港股数据
                    quotes = db.query(HistoricalQuotesHK).filter(
                        HistoricalQuotesHK.code == symbol
                    ).order_by(desc(HistoricalQuotesHK.date)).limit(250).all()  # 获取最近250条数据
                    
                    for quote in quotes:
                        try:
                            market_data = MarketData(
                                symbol=symbol,
                                date=str(quote.date)[:10] if quote.date else "",
                                open=float(quote.open) if quote.open else 0.0,
                                high=float(quote.high) if quote.high else 0.0,
                                low=float(quote.low) if quote.low else 0.0,
                                close=float(quote.close) if quote.close else 0.0,
                                volume=int(quote.volume) if quote.volume else 0,
                                amount=float(quote.amount) if quote.amount else 0.0
                            )
                            market_data_list.append(market_data)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"跳过无效数据: {symbol} {quote.date} - {e}")
                            continue
                else:
                    # A股数据
                    quotes = db.query(HistoricalQuotes).filter(
                        HistoricalQuotes.code == symbol
                    ).order_by(desc(HistoricalQuotes.date)).limit(250).all()  # 获取最近250条数据
                    
                    for quote in quotes:
                        try:
                            market_data = MarketData(
                                symbol=symbol,
                                date=str(quote.date)[:10] if quote.date else "",
                                open=float(quote.open) if quote.open else 0.0,
                                high=float(quote.high) if quote.high else 0.0,
                                low=float(quote.low) if quote.low else 0.0,
                                close=float(quote.close) if quote.close else 0.0,
                                volume=int(quote.volume) if quote.volume else 0,
                                amount=float(quote.amount) if quote.amount else 0.0
                            )
                            market_data_list.append(market_data)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"跳过无效数据: {symbol} {quote.date} - {e}")
                            continue
                
                # 按日期正序排列（从早到晚）
                market_data_list.sort(key=lambda x: x.date)
                
                logger.info(f"成功获取股票 {symbol} 的 {len(market_data_list)} 条历史数据")
                return market_data_list
            
            except Exception as db_error:
                logger.error(f"数据库查询失败: {str(db_error)}")
                return []
            
            finally:
                db.close()
        
        except Exception as e:
            logger.error(f"获取股票 {symbol} 数据失败: {str(e)}")
            return []
    
    def _get_stock_name(self, symbol: str) -> str:
        """获取股票名称
        
        Args:
            symbol: 股票代码
            
        Returns:
            str: 股票名称
        """
        return self.stock_name_mapping.get(symbol, f"股票{symbol}")
    
    def _dict_to_indicators(self, indicators_dict: Dict) -> PVFRSIndicators:
        """将字典转换为PVFRSIndicators对象
        
        Args:
            indicators_dict: 指标字典
            
        Returns:
            PVFRSIndicators: 指标对象
        """
        try:
            return PVFRSIndicators(
                macro_displacement=indicators_dict.get('macro_displacement', 0.0),
                instant_deviation=indicators_dict.get('instant_deviation', 0.0),
                avg_price_20d=indicators_dict.get('avg_price_20d', 1.0),
                rising_days=indicators_dict.get('rising_days', 0),
                falling_days=indicators_dict.get('falling_days', 0),
                frequency_advantage=indicators_dict.get('frequency_advantage', False),
                avg_volume_20d=indicators_dict.get('avg_volume_20d', 0.0),
                current_volume=indicators_dict.get('current_volume', 0.0),
                efficiency_ratio=indicators_dict.get('efficiency_ratio', 0.0),
                amplitude_ratio=indicators_dict.get('amplitude_ratio', 0.0),
                resonance_strength=indicators_dict.get('resonance_strength', 0.0),
                amplitude=indicators_dict.get('amplitude'),
                ratio_d20=indicators_dict.get('ratio_d20'),
                ratio_d1=indicators_dict.get('ratio_d1'),
                is_sideways=indicators_dict.get('is_sideways')
            )
        except Exception as e:
            logger.warning(f"转换指标字典失败: {str(e)}")
            # 返回默认指标
            return PVFRSIndicators(
                macro_displacement=0.0, instant_deviation=0.0, avg_price_20d=1.0,
                rising_days=0, falling_days=0, frequency_advantage=False,
                avg_volume_20d=0.0, current_volume=0.0, efficiency_ratio=0.0,
                amplitude_ratio=0.0, resonance_strength=0.0
            )
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效
        
        Args:
            cache_key: 缓存键
            
        Returns:
            bool: 缓存是否有效
        """
        if cache_key in self._selection_cache:
            cache_time = self._selection_cache[cache_key]['timestamp']
            return (datetime.now() - cache_time).total_seconds() < (self.cache_duration_minutes * 60)
        
        if cache_key in self._detail_cache:
            cache_time = self._detail_cache[cache_key]['timestamp']
            return (datetime.now() - cache_time).total_seconds() < (self.cache_duration_minutes * 60)
        
        return False


# 便捷函数
def create_frontend_interface(pvfrs_system: Optional[PVFRSSystem] = None,
                            stock_name_mapping: Optional[Dict[str, str]] = None) -> FrontendInterface:
    """创建前端接口实例
    
    Args:
        pvfrs_system: PVFRS策略系统实例
        stock_name_mapping: 股票名称映射
        
    Returns:
        FrontendInterface: 前端接口实例
    """
    return FrontendInterface(pvfrs_system, stock_name_mapping)
