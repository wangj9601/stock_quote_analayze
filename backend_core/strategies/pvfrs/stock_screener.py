"""
PVFRS策略批量选股功能实现
对股票池中每只股票应用PVFRS条件，筛选满足三维共振条件的股票
"""

from typing import List, Dict, Optional, Callable
from datetime import datetime, timedelta
import concurrent.futures
from dataclasses import dataclass
from .models import MarketData, Signal, CalculationException, DataInsufficientException
from .strategy_engine import StrategyEngine


@dataclass
class SelectionResult:
    """选股结果"""
    symbol: str
    date: str
    signal_strength: float
    signal_reason: str
    conditions_met: Dict[str, bool]
    price: float
    volume: int
    market_cap: Optional[float] = None
    industry: Optional[str] = None
    name: Optional[str] = None  # 添加股票名称字段
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'symbol': self.symbol,
            'date': self.date,
            'signal_strength': self.signal_strength,
            'signal_reason': self.signal_reason,
            'conditions_met': self.conditions_met,
            'price': self.price,
            'volume': self.volume,
            'market_cap': self.market_cap,
            'industry': self.industry,
            'name': self.name  # 添加name字段到返回字典
        }


@dataclass
class ScreeningConfig:
    """选股配置"""
    min_signal_strength: float = 0.6  # 最小信号强度
    max_results: int = 50  # 最大结果数量
    enable_parallel_processing: bool = True  # 是否启用并行处理
    max_workers: int = 4  # 最大工作线程数
    min_price: float = 1.0  # 最小价格过滤
    max_price: float = 1000.0  # 最大价格过滤
    min_volume: int = 100000  # 最小成交量过滤
    exclude_st_stocks: bool = True  # 是否排除ST股票
    include_industries: Optional[List[str]] = None  # 包含的行业
    exclude_industries: Optional[List[str]] = None  # 排除的行业


class StockScreener:
    """PVFRS策略股票筛选器
    
    负责批量选股功能：
    - 对股票池中每只股票应用PVFRS条件
    - 筛选满足三维共振条件的股票
    - 支持并行处理提高效率
    - 提供灵活的过滤和排序选项
    """
    
    def __init__(self, strategy_engine: Optional[StrategyEngine] = None):
        """初始化股票筛选器
        
        Args:
            strategy_engine: PVFRS策略引擎实例，如果为None则创建新实例
        """
        self.strategy_engine = strategy_engine or StrategyEngine()
        self.screening_config = ScreeningConfig()
        
        # 统计信息
        self.last_screening_stats = {
            'total_stocks': 0,
            'analyzed_stocks': 0,
            'qualified_stocks': 0,
            'error_stocks': 0,
            'processing_time': 0.0
        }
    
    def screen_stocks(self, stock_data_dict: Dict[str, List[MarketData]], 
                     target_date: str,
                     config: Optional[ScreeningConfig] = None) -> List[ScreeningResult]:
        """批量选股主函数
        
        对股票池中每只股票应用PVFRS条件，筛选满足三维共振条件的股票。
        
        Args:
            stock_data_dict: 股票数据字典，键为股票代码，值为市场数据列表
            target_date: 目标分析日期
            config: 选股配置，如果为None则使用默认配置
            
        Returns:
            List[ScreeningResult]: 筛选结果列表，按信号强度降序排列
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        start_time = datetime.now()
        
        try:
            # 使用提供的配置或默认配置
            screening_config = config or self.screening_config
            
            # 初始化统计信息
            self.last_screening_stats = {
                'total_stocks': len(stock_data_dict),
                'analyzed_stocks': 0,
                'qualified_stocks': 0,
                'error_stocks': 0,
                'processing_time': 0.0
            }
            
            # 1. 预过滤股票
            filtered_stocks = self._pre_filter_stocks(stock_data_dict, target_date, screening_config)
            
            # 2. 批量分析股票
            if screening_config.enable_parallel_processing and len(filtered_stocks) > 1:
                screening_results = self._parallel_screen_stocks(filtered_stocks, target_date, screening_config)
            else:
                screening_results = self._sequential_screen_stocks(filtered_stocks, target_date, screening_config)
            
            # 3. 后处理和排序
            final_results = self._post_process_results(screening_results, screening_config)
            
            # 4. 更新统计信息
            end_time = datetime.now()
            self.last_screening_stats['processing_time'] = (end_time - start_time).total_seconds()
            self.last_screening_stats['qualified_stocks'] = len(final_results)
            
            return final_results
            
        except Exception as e:
            raise CalculationException(f"批量选股失败: {str(e)}")
    
    def screen_stocks_with_callback(self, stock_data_dict: Dict[str, List[MarketData]], 
                                   target_date: str,
                                   progress_callback: Optional[Callable[[str, int, int], None]] = None,
                                   config: Optional[ScreeningConfig] = None) -> List[ScreeningResult]:
        """带进度回调的批量选股
        
        Args:
            stock_data_dict: 股票数据字典
            target_date: 目标分析日期
            progress_callback: 进度回调函数，参数为(当前股票代码, 已处理数量, 总数量)
            config: 选股配置
            
        Returns:
            List[ScreeningResult]: 筛选结果列表
        """
        start_time = datetime.now()
        
        try:
            screening_config = config or self.screening_config
            
            # 初始化统计信息
            self.last_screening_stats = {
                'total_stocks': len(stock_data_dict),
                'analyzed_stocks': 0,
                'qualified_stocks': 0,
                'error_stocks': 0,
                'processing_time': 0.0
            }
            
            # 预过滤股票
            filtered_stocks = self._pre_filter_stocks(stock_data_dict, target_date, screening_config)
            
            screening_results = []
            total_stocks = len(filtered_stocks)
            
            for i, (symbol, data) in enumerate(filtered_stocks.items()):
                try:
                    # 调用进度回调
                    if progress_callback:
                        progress_callback(symbol, i + 1, total_stocks)
                    
                    # 分析单只股票
                    result = self._analyze_single_stock(symbol, data, target_date, screening_config)
                    if result:
                        screening_results.append(result)
                    
                    self.last_screening_stats['analyzed_stocks'] += 1
                    
                except Exception as e:
                    self.last_screening_stats['error_stocks'] += 1
                    print(f"股票 {symbol} 分析失败: {str(e)}")
                    continue
            
            # 后处理和排序
            final_results = self._post_process_results(screening_results, screening_config)
            
            # 更新统计信息
            end_time = datetime.now()
            self.last_screening_stats['processing_time'] = (end_time - start_time).total_seconds()
            self.last_screening_stats['qualified_stocks'] = len(final_results)
            
            return final_results
            
        except Exception as e:
            raise CalculationException(f"带回调的批量选股失败: {str(e)}")
    
    def get_screening_statistics(self) -> Dict:
        """获取最近一次选股的统计信息
        
        Returns:
            Dict: 统计信息
        """
        stats = self.last_screening_stats.copy()
        
        # 计算成功率和效率指标
        if stats['total_stocks'] > 0:
            stats['success_rate'] = stats['analyzed_stocks'] / stats['total_stocks']
            stats['qualification_rate'] = stats['qualified_stocks'] / stats['analyzed_stocks'] if stats['analyzed_stocks'] > 0 else 0
            stats['error_rate'] = stats['error_stocks'] / stats['total_stocks']
        else:
            stats['success_rate'] = 0
            stats['qualification_rate'] = 0
            stats['error_rate'] = 0
        
        # 计算处理速度
        if stats['processing_time'] > 0:
            stats['stocks_per_second'] = stats['analyzed_stocks'] / stats['processing_time']
        else:
            stats['stocks_per_second'] = 0
        
        return stats
    
    def _pre_filter_stocks(self, stock_data_dict: Dict[str, List[MarketData]], 
                          target_date: str, 
                          config: ScreeningConfig) -> Dict[str, List[MarketData]]:
        """预过滤股票
        
        根据基本条件过滤股票，提高后续分析效率。
        
        Args:
            stock_data_dict: 原始股票数据
            target_date: 目标日期
            config: 筛选配置
            
        Returns:
            Dict[str, List[MarketData]]: 过滤后的股票数据
        """
        filtered_stocks = {}
        
        for symbol, data in stock_data_dict.items():
            try:
                # 过滤到目标日期的数据
                filtered_data = self._filter_data_to_date(data, target_date)
                
                # 检查数据充足性
                if len(filtered_data) < self.strategy_engine.min_data_length:
                    continue
                
                # 获取最新数据进行基本过滤
                latest_data = filtered_data[-1]
                
                # 价格过滤
                if not (config.min_price <= latest_data.close <= config.max_price):
                    continue
                
                # 成交量过滤
                if latest_data.volume < config.min_volume:
                    continue
                
                # ST股票过滤
                if config.exclude_st_stocks and self._is_st_stock(symbol):
                    continue
                
                # 行业过滤（如果配置了行业信息）
                if config.include_industries or config.exclude_industries:
                    stock_industry = self._get_stock_industry(symbol)
                    
                    if config.include_industries and stock_industry not in config.include_industries:
                        continue
                    
                    if config.exclude_industries and stock_industry in config.exclude_industries:
                        continue
                
                filtered_stocks[symbol] = filtered_data
                
            except Exception as e:
                print(f"预过滤股票 {symbol} 失败: {str(e)}")
                continue
        
        return filtered_stocks
    
    def _parallel_screen_stocks(self, stock_data_dict: Dict[str, List[MarketData]], 
                               target_date: str, 
                               config: ScreeningConfig) -> List[ScreeningResult]:
        """并行处理股票筛选
        
        Args:
            stock_data_dict: 股票数据字典
            target_date: 目标日期
            config: 筛选配置
            
        Returns:
            List[ScreeningResult]: 筛选结果列表
        """
        screening_results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=config.max_workers) as executor:
            # 提交所有任务
            future_to_symbol = {
                executor.submit(self._analyze_single_stock, symbol, data, target_date, config): symbol
                for symbol, data in stock_data_dict.items()
            }
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    result = future.result()
                    if result:
                        screening_results.append(result)
                    
                    self.last_screening_stats['analyzed_stocks'] += 1
                    
                except Exception as e:
                    self.last_screening_stats['error_stocks'] += 1
                    print(f"并行处理股票 {symbol} 失败: {str(e)}")
        
        return screening_results
    
    def _sequential_screen_stocks(self, stock_data_dict: Dict[str, List[MarketData]], 
                                 target_date: str, 
                                 config: ScreeningConfig) -> List[ScreeningResult]:
        """顺序处理股票筛选
        
        Args:
            stock_data_dict: 股票数据字典
            target_date: 目标日期
            config: 筛选配置
            
        Returns:
            List[ScreeningResult]: 筛选结果列表
        """
        screening_results = []
        
        for symbol, data in stock_data_dict.items():
            try:
                result = self._analyze_single_stock(symbol, data, target_date, config)
                if result:
                    screening_results.append(result)
                
                self.last_screening_stats['analyzed_stocks'] += 1
                
            except Exception as e:
                self.last_screening_stats['error_stocks'] += 1
                print(f"顺序处理股票 {symbol} 失败: {str(e)}")
                continue
        
        return screening_results
    
    def _analyze_single_stock(self, symbol: str, data: List[MarketData], 
                             target_date: str, config: ScreeningConfig) -> Optional[ScreeningResult]:
        """分析单只股票
        
        Args:
            symbol: 股票代码
            data: 市场数据
            target_date: 目标日期
            config: 筛选配置
            
        Returns:
            Optional[ScreeningResult]: 如果符合条件则返回筛选结果，否则返回None
        """
        try:
            # 生成信号
            signals = self.strategy_engine.generate_signals(symbol, data)
            
            # 检查是否有买入信号
            buy_signals = [s for s in signals if s.signal_type.value == 'buy']
            
            if not buy_signals:
                return None
            
            # 取最强的买入信号
            strongest_signal = max(buy_signals, key=lambda x: x.strength)
            
            # 检查信号强度是否达到要求
            if strongest_signal.strength < config.min_signal_strength:
                return None
            
            # 获取最新市场数据
            latest_data = data[-1]
            
            # 创建筛选结果
            screening_result = ScreeningResult(
                symbol=symbol,
                date=target_date,
                signal_strength=strongest_signal.strength,
                signal_reason=strongest_signal.reason,
                conditions_met=strongest_signal.conditions_met,
                price=latest_data.close,
                volume=latest_data.volume,
                market_cap=self._get_market_cap(symbol, latest_data.close),
                industry=self._get_stock_industry(symbol),
                name=self._get_stock_name(symbol)  # 添加股票名称
            )
            
            return screening_result
            
        except (DataInsufficientException, CalculationException):
            # 数据不足或计算异常，跳过该股票
            return None
        except Exception as e:
            raise CalculationException(f"分析股票 {symbol} 失败: {str(e)}")
    
    def _post_process_results(self, results: List[ScreeningResult], 
                             config: ScreeningConfig) -> List[ScreeningResult]:
        """后处理筛选结果
        
        Args:
            results: 原始筛选结果
            config: 筛选配置
            
        Returns:
            List[ScreeningResult]: 处理后的结果
        """
        # 按信号强度降序排序
        sorted_results = sorted(results, key=lambda x: x.signal_strength, reverse=True)
        
        # 限制结果数量
        if config.max_results > 0:
            sorted_results = sorted_results[:config.max_results]
        
        return sorted_results
    
    def _filter_data_to_date(self, data: List[MarketData], target_date: str) -> List[MarketData]:
        """过滤数据到指定日期
        
        Args:
            data: 原始数据列表
            target_date: 目标日期
            
        Returns:
            List[MarketData]: 过滤后的数据列表
        """
        filtered_data = []
        for item in data:
            if item.date <= target_date:
                filtered_data.append(item)
            else:
                break  # 假设数据是按时间顺序排列的
        
        return filtered_data
    
    def _is_st_stock(self, symbol: str) -> bool:
        """判断是否为ST股票
        
        Args:
            symbol: 股票代码
            
        Returns:
            bool: 是否为ST股票
        """
        # 简单的ST股票判断逻辑，实际应用中可能需要更复杂的判断
        return 'ST' in symbol.upper()
    
    def _get_stock_industry(self, symbol: str) -> Optional[str]:
        """获取股票行业信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            Optional[str]: 行业信息，如果无法获取则返回None
        """
        # 这里应该连接到实际的股票信息数据库
        # 目前返回None，表示暂不支持行业过滤
        return None
    
    def _get_market_cap(self, symbol: str, price: float) -> Optional[float]:
        """获取市值信息
        
        Args:
            symbol: 股票代码
            price: 当前价格
            
        Returns:
            Optional[float]: 市值，如果无法计算则返回None
        """
        # 这里应该连接到实际的股票信息数据库获取股本信息
        # 目前返回None，表示暂不支持市值计算
        return None
    
    def set_screening_config(self, config: ScreeningConfig) -> None:
        """设置筛选配置
        
        Args:
            config: 新的筛选配置
        """
        self.screening_config = config
    
    def get_screening_config(self) -> ScreeningConfig:
        """获取当前筛选配置
        
        Returns:
            ScreeningConfig: 当前筛选配置
        """
        return self.screening_config
    
    def export_results_to_dict(self, results: List[ScreeningResult]) -> List[Dict]:
        """将筛选结果导出为字典列表
        
        Args:
            results: 筛选结果列表
            
        Returns:
            List[Dict]: 字典格式的结果列表
        """
        return [result.to_dict() for result in results]
    
    def _get_stock_name(self, symbol: str) -> Optional[str]:
        """获取股票名称
        
        Args:
            symbol: 股票代码
            
        Returns:
            Optional[str]: 股票名称，如果无法获取则返回None
        """
        try:
            # 这里应该连接到实际的股票信息数据库
            # 暂时返回一个基于代码的简单名称，实际应用中应该查询数据库
            if symbol.startswith('6'):
                return f"股票{symbol}"
            elif symbol.startswith('0'):
                return f"股票{symbol}"
            elif symbol.startswith('3'):
                return f"股票{symbol}"
            else:
                return f"股票{symbol}"
        except Exception:
            return None
    
    def get_screening_summary(self, results: List[ScreeningResult]) -> Dict:
        """获取筛选结果汇总
        
        Args:
            results: 筛选结果列表
            
        Returns:
            Dict: 筛选结果汇总信息
        """
        if not results:
            return {
                'total_results': 0,
                'avg_signal_strength': 0.0,
                'max_signal_strength': 0.0,
                'min_signal_strength': 0.0,
                'strength_distribution': {},
                'top_conditions': {}
            }
        
        # 基本统计
        signal_strengths = [r.signal_strength for r in results]
        
        # 信号强度分布
        strength_ranges = {
            '0.6-0.7': 0,
            '0.7-0.8': 0,
            '0.8-0.9': 0,
            '0.9-1.0': 0
        }
        
        for strength in signal_strengths:
            if 0.6 <= strength < 0.7:
                strength_ranges['0.6-0.7'] += 1
            elif 0.7 <= strength < 0.8:
                strength_ranges['0.7-0.8'] += 1
            elif 0.8 <= strength < 0.9:
                strength_ranges['0.8-0.9'] += 1
            elif 0.9 <= strength <= 1.0:
                strength_ranges['0.9-1.0'] += 1
        
        # 统计最常见的满足条件
        condition_counts = {}
        for result in results:
            for condition, met in result.conditions_met.items():
                if met:
                    condition_counts[condition] = condition_counts.get(condition, 0) + 1
        
        # 排序获取前5个最常见条件
        top_conditions = dict(sorted(condition_counts.items(), key=lambda x: x[1], reverse=True)[:5])
        
        return {
            'total_results': len(results),
            'avg_signal_strength': sum(signal_strengths) / len(signal_strengths),
            'max_signal_strength': max(signal_strengths),
            'min_signal_strength': min(signal_strengths),
            'strength_distribution': strength_ranges,
            'top_conditions': top_conditions,
            'statistics': self.get_screening_statistics()
        }