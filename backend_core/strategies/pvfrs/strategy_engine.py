"""
PVFRS策略引擎实现
协调各个维度分析器，实现完整的PVFRS策略执行流程
"""

from typing import List, Dict, Optional
from .models import MarketData, PVFRSIndicators, Signal, CalculationException, DataInsufficientException
from .interfaces import IStrategyEngine
from .analyzers import PriceDimensionAnalyzer, FrequencyDimensionAnalyzer, VolumeDimensionAnalyzer
from .resonance_detector import ResonanceDetector
from .signal_generator import SignalGenerator


class StrategyEngine(IStrategyEngine):
    """PVFRS策略引擎
    
    协调各个维度分析器，实现完整的PVFRS策略执行流程：
    - 协调价格、频率、成交量三个维度分析器
    - 整合分析结果进行三维共振检测
    - 生成交易信号
    - 提供完整的策略执行流程
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """初始化策略引擎
        
        Args:
            config: 可选配置字典，用于共振检测器等（如 buy_ratio_d20_max, buy_exclude_sideways）
        """
        # 初始化各个维度分析器
        self.price_analyzer = PriceDimensionAnalyzer()
        self.frequency_analyzer = FrequencyDimensionAnalyzer()
        self.volume_analyzer = VolumeDimensionAnalyzer()
        
        # 共振检测器：若提供配置则使用买点参数
        if config:
            buy_ratio_d20_max = config.get('buy_ratio_d20_max', 0.5)
            buy_exclude_sideways = config.get('buy_exclude_sideways', True)
            self.resonance_detector = ResonanceDetector(
                buy_ratio_d20_max=float(buy_ratio_d20_max),
                buy_exclude_sideways=bool(buy_exclude_sideways)
            )
        else:
            self.resonance_detector = ResonanceDetector()
        self.signal_generator = SignalGenerator()
        
        # 策略配置
        self.min_data_length = int(config.get('observation_period', 20)) if config else 20
        self.enable_entry_timing_optimization = True  # 是否启用入场时机优化
    
    def analyze_stock(self, symbol: str, data: List[MarketData]) -> PVFRSIndicators:
        """分析单只股票的PVFRS指标
        
        协调各个维度分析器，计算完整的PVFRS指标。
        
        Args:
            symbol: 股票代码
            data: 市场数据列表，按时间顺序排列
            
        Returns:
            PVFRSIndicators: 完整的PVFRS指标
            
        Raises:
            DataInsufficientException: 数据不足时抛出
            CalculationException: 计算异常时抛出
        """
        try:
            # 验证数据充足性
            if len(data) < self.min_data_length:
                raise DataInsufficientException(
                    f"股票 {symbol} 数据不足，需要至少{self.min_data_length}天数据，实际{len(data)}天"
                )
            
            # 1. 价格维度分析
            price_indicators = self.price_analyzer.analyze(data)
            
            # 2. 频率维度分析
            frequency_indicators = self.frequency_analyzer.analyze(data)
            
            # 3. 成交量维度分析
            volume_indicators = self.volume_analyzer.analyze(data)
            
            # 4. 三维共振检测
            resonance_result = self.resonance_detector.detect_resonance(
                price_indicators, frequency_indicators, volume_indicators
            )
            
            # 5. 构建完整的PVFRS指标
            pvfrs_indicators = PVFRSIndicators(
                # 价格维度指标
                macro_displacement=price_indicators['macro_displacement'],
                instant_deviation=price_indicators['instant_deviation'],
                avg_price_20d=price_indicators['avg_price_20d'],
                
                # 频率维度指标
                rising_days=frequency_indicators['rising_days'],
                falling_days=frequency_indicators['falling_days'],
                frequency_advantage=frequency_indicators['frequency_advantage'],
                
                # 成交量维度指标
                avg_volume_20d=volume_indicators['avg_volume_20d'],
                current_volume=volume_indicators['current_volume'],
                efficiency_ratio=volume_indicators['efficiency_ratio'],
                
                # 综合指标
                amplitude_ratio=self._calculate_amplitude_ratio(
                    price_indicators['macro_displacement'],
                    price_indicators['avg_price_20d']
                ),
                resonance_strength=resonance_result['resonance_strength'],
                # 幅度指标
                amplitude=price_indicators.get('amplitude'),
                ratio_d20=price_indicators.get('ratio_d20'),
                ratio_d1=price_indicators.get('ratio_d1'),
                is_sideways=price_indicators.get('is_sideways')
            )
            
            return pvfrs_indicators
            
        except (DataInsufficientException, CalculationException):
            # 重新抛出已知异常
            raise
        except Exception as e:
            raise CalculationException(f"股票 {symbol} PVFRS指标分析失败: {str(e)}")
    
    def screen_stocks(self, symbols: List[str], date: str) -> List[str]:
        """选股：筛选符合PVFRS条件的股票
        
        对股票池中的每只股票应用PVFRS条件，筛选满足三维共振条件的股票。
        注意：此方法需要外部提供数据获取接口，这里提供接口定义。
        
        Args:
            symbols: 股票代码列表
            date: 分析日期
            
        Returns:
            List[str]: 符合PVFRS条件的股票代码列表
            
        Raises:
            NotImplementedError: 需要外部实现数据获取接口
        """
        # 这个方法需要数据接口支持，在实际使用时需要注入数据获取器
        raise NotImplementedError(
            "选股功能需要数据接口支持。请使用 screen_stocks_with_data 方法，"
            "或者实现 IDataInterface 接口并通过 set_data_interface 方法注入。"
        )
    
    def screen_stocks_with_data(self, stock_data_dict: Dict[str, List[MarketData]], 
                               target_date: str) -> List[Dict]:
        """使用提供的数据进行选股
        
        对提供的股票数据应用PVFRS条件，筛选满足三维共振条件的股票。
        
        Args:
            stock_data_dict: 股票数据字典，键为股票代码，值为市场数据列表
            target_date: 目标分析日期
            
        Returns:
            List[Dict]: 符合条件的股票信息列表，包含股票代码、指标和信号强度
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            qualified_stocks = []
            
            for symbol, data in stock_data_dict.items():
                try:
                    # 过滤到目标日期的数据
                    filtered_data = self._filter_data_to_date(data, target_date)
                    
                    if len(filtered_data) < self.min_data_length:
                        continue  # 数据不足，跳过
                    
                    # 分析股票指标
                    indicators = self.analyze_stock(symbol, filtered_data)
                    
                    # 生成信号进行筛选
                    signals = self.generate_signals(symbol, filtered_data)
                    
                    # 检查是否有买入信号
                    buy_signals = [s for s in signals if s.signal_type.value == 'buy']
                    
                    if buy_signals:
                        # 取最强的买入信号
                        strongest_signal = max(buy_signals, key=lambda x: x.strength)
                        
                        qualified_stocks.append({
                            'symbol': symbol,
                            'date': target_date,
                            'signal_strength': strongest_signal.strength,
                            'signal_reason': strongest_signal.reason,
                            'conditions_met': strongest_signal.conditions_met,
                            'indicators': indicators,
                            'price': filtered_data[-1].close if filtered_data else 0
                        })
                        
                except (DataInsufficientException, CalculationException) as e:
                    # 记录但不中断整个选股过程
                    print(f"股票 {symbol} 分析失败: {str(e)}")
                    continue
                except Exception as e:
                    print(f"股票 {symbol} 处理异常: {str(e)}")
                    continue
            
            # 按信号强度排序
            qualified_stocks.sort(key=lambda x: x['signal_strength'], reverse=True)
            
            return qualified_stocks
            
        except Exception as e:
            raise CalculationException(f"批量选股失败: {str(e)}")
    
    def generate_signals(self, symbol: str, data: List[MarketData]) -> List[Signal]:
        """生成交易信号
        
        基于PVFRS分析结果生成买入和卖出信号。
        
        Args:
            symbol: 股票代码
            data: 市场数据列表，按时间顺序排列
            
        Returns:
            List[Signal]: 交易信号列表
            
        Raises:
            DataInsufficientException: 数据不足时抛出
            CalculationException: 计算异常时抛出
        """
        try:
            # 验证数据充足性
            if len(data) < self.min_data_length:
                raise DataInsufficientException(
                    f"生成信号需要至少{self.min_data_length}天数据，实际{len(data)}天"
                )
            
            signals = []
            
            # 1. 进行维度分析
            price_indicators = self.price_analyzer.analyze(data)
            frequency_indicators = self.frequency_analyzer.analyze(data)
            volume_indicators = self.volume_analyzer.analyze(data)
            
            # 2. 信号过滤检查
            if not self.signal_generator.filter_signals(
                price_indicators, frequency_indicators, volume_indicators
            ):
                # 不满足信号生成条件，返回空列表
                return signals
            
            # 3. 三维共振检测
            resonance_result = self.resonance_detector.detect_resonance(
                price_indicators, frequency_indicators, volume_indicators
            )
            
            # 4. 检查是否满足三维共振条件
            if resonance_result['three_dimension_resonance']:
                # 构建PVFRS指标
                pvfrs_indicators = PVFRSIndicators(
                    macro_displacement=price_indicators['macro_displacement'],
                    instant_deviation=price_indicators['instant_deviation'],
                    avg_price_20d=price_indicators['avg_price_20d'],
                    rising_days=frequency_indicators['rising_days'],
                    falling_days=frequency_indicators['falling_days'],
                    frequency_advantage=frequency_indicators['frequency_advantage'],
                    avg_volume_20d=volume_indicators['avg_volume_20d'],
                    current_volume=volume_indicators['current_volume'],
                    efficiency_ratio=volume_indicators['efficiency_ratio'],
                    amplitude_ratio=self._calculate_amplitude_ratio(
                        price_indicators['macro_displacement'],
                        price_indicators['avg_price_20d']
                    ),
                    resonance_strength=resonance_result['resonance_strength'],
                    amplitude=price_indicators.get('amplitude'),
                    ratio_d20=price_indicators.get('ratio_d20'),
                    ratio_d1=price_indicators.get('ratio_d1'),
                    is_sideways=price_indicators.get('is_sideways')
                )
                
                # 5. 生成买入信号
                current_date = data[-1].date
                current_price = data[-1].close
                
                buy_signal = self.signal_generator.generate_buy_signal(
                    symbol=symbol,
                    date=current_date,
                    price=current_price,
                    indicators=pvfrs_indicators,
                    conditions_met=resonance_result['conditions_met']
                )
                
                # 6. 入场时机优化（如果启用）
                if self.enable_entry_timing_optimization:
                    optimized_signal = self.signal_generator.optimize_entry_timing(data, buy_signal)
                    if optimized_signal:
                        signals.append(optimized_signal)
                    # 如果优化后返回None，说明时机不佳，不添加信号
                else:
                    signals.append(buy_signal)
            
            return signals
            
        except (DataInsufficientException, CalculationException):
            # 重新抛出已知异常
            raise
        except Exception as e:
            raise CalculationException(f"股票 {symbol} 信号生成失败: {str(e)}")
    
    def get_strategy_analysis(self, symbol: str, data: List[MarketData]) -> Dict:
        """获取完整的策略分析结果
        
        提供详细的分析结果，包括各维度指标、共振检测和信号生成。
        
        Args:
            symbol: 股票代码
            data: 市场数据列表
            
        Returns:
            Dict: 完整的策略分析结果
            
        Raises:
            DataInsufficientException: 数据不足时抛出
            CalculationException: 计算异常时抛出
        """
        try:
            # 验证数据充足性
            if len(data) < self.min_data_length:
                raise DataInsufficientException(
                    f"策略分析需要至少{self.min_data_length}天数据，实际{len(data)}天"
                )
            
            # 1. 各维度分析
            price_indicators = self.price_analyzer.analyze(data)
            frequency_indicators = self.frequency_analyzer.analyze(data)
            volume_indicators = self.volume_analyzer.analyze(data)
            
            # 2. 三维共振检测
            resonance_result = self.resonance_detector.detect_resonance(
                price_indicators, frequency_indicators, volume_indicators
            )
            
            # 3. 信号生成
            signals = self.generate_signals(symbol, data)
            
            # 4. 入场时机分析（如果有指标）
            entry_timing_analysis = None
            if resonance_result['three_dimension_resonance']:
                pvfrs_indicators = PVFRSIndicators(
                    macro_displacement=price_indicators['macro_displacement'],
                    instant_deviation=price_indicators['instant_deviation'],
                    avg_price_20d=price_indicators['avg_price_20d'],
                    rising_days=frequency_indicators['rising_days'],
                    falling_days=frequency_indicators['falling_days'],
                    frequency_advantage=frequency_indicators['frequency_advantage'],
                    avg_volume_20d=volume_indicators['avg_volume_20d'],
                    current_volume=volume_indicators['current_volume'],
                    efficiency_ratio=volume_indicators['efficiency_ratio'],
                    amplitude_ratio=self._calculate_amplitude_ratio(
                        price_indicators['macro_displacement'],
                        price_indicators['avg_price_20d']
                    ),
                    resonance_strength=resonance_result['resonance_strength'],
                    amplitude=price_indicators.get('amplitude'),
                    ratio_d20=price_indicators.get('ratio_d20'),
                    ratio_d1=price_indicators.get('ratio_d1'),
                    is_sideways=price_indicators.get('is_sideways')
                )
                
                entry_timing_analysis = self.signal_generator.get_entry_timing_analysis(
                    data, pvfrs_indicators
                )
            
            # 5. 信号汇总统计
            signal_summary = self.signal_generator.generate_signal_summary(signals)
            
            return {
                'symbol': symbol,
                'analysis_date': data[-1].date if data else None,
                'data_length': len(data),
                
                # 维度分析结果
                'price_dimension': price_indicators,
                'frequency_dimension': frequency_indicators,
                'volume_dimension': volume_indicators,
                
                # 共振检测结果
                'resonance_detection': resonance_result,
                
                # 信号生成结果
                'signals': [self._signal_to_dict(s) for s in signals],
                'signal_summary': signal_summary,
                
                # 入场时机分析
                'entry_timing_analysis': entry_timing_analysis,
                
                # 策略评估
                'strategy_assessment': {
                    'has_buy_signal': any(s.signal_type.value == 'buy' for s in signals),
                    'max_signal_strength': max([s.strength for s in signals], default=0),
                    'three_dimension_resonance': resonance_result['three_dimension_resonance'],
                    'high_efficiency_trajectory': resonance_result['high_efficiency_trajectory'],
                    'overall_score': resonance_result['resonance_strength']
                }
            }
            
        except (DataInsufficientException, CalculationException):
            # 重新抛出已知异常
            raise
        except Exception as e:
            raise CalculationException(f"股票 {symbol} 策略分析失败: {str(e)}")
    
    def validate_strategy_conditions(self, symbol: str, data: List[MarketData]) -> Dict:
        """验证策略条件
        
        检查股票是否满足PVFRS策略的各项条件，提供详细的验证结果。
        
        Args:
            symbol: 股票代码
            data: 市场数据列表
            
        Returns:
            Dict: 策略条件验证结果
            
        Raises:
            DataInsufficientException: 数据不足时抛出
            CalculationException: 计算异常时抛出
        """
        try:
            # 验证数据充足性
            if len(data) < self.min_data_length:
                return {
                    'valid': False,
                    'reason': f'数据不足，需要至少{self.min_data_length}天数据，实际{len(data)}天',
                    'data_sufficient': False
                }
            
            # 1. 各维度条件验证
            price_indicators = self.price_analyzer.analyze(data)
            frequency_indicators = self.frequency_analyzer.analyze(data)
            volume_indicators = self.volume_analyzer.analyze(data)
            
            # 2. 详细条件检查
            validation_result = {
                'valid': False,
                'data_sufficient': True,
                'symbol': symbol,
                'analysis_date': data[-1].date,
                
                # 各维度验证结果
                'price_dimension_valid': price_indicators.get('price_dimension_valid', False),
                'frequency_dimension_valid': frequency_indicators.get('frequency_dimension_valid', False),
                'volume_dimension_valid': volume_indicators.get('volume_dimension_valid', False),
                
                # 详细条件检查
                'detailed_conditions': {
                    'price_conditions': {
                        'macro_displacement_positive': price_indicators.get('macro_displacement', 0) > 0,
                        'instant_deviation_positive': price_indicators.get('instant_deviation', 0) > 0,
                        'amplitude_ratio_valid': self._validate_amplitude_ratio(
                            price_indicators.get('macro_displacement', 0),
                            price_indicators.get('avg_price_20d', 1)
                        )
                    },
                    'frequency_conditions': {
                        'frequency_advantage': frequency_indicators.get('frequency_advantage', False),
                        'no_false_prosperity': not frequency_indicators.get('has_false_prosperity', True),
                        'sufficient_rising_days': frequency_indicators.get('rising_days', 0) >= 8
                    },
                    'volume_conditions': {
                        'volume_efficiency': volume_indicators.get('current_volume', 0) > volume_indicators.get('avg_volume_20d', 0),
                        'volume_price_resonance': volume_indicators.get('volume_price_resonance', False),
                        'strong_fund_support': volume_indicators.get('strong_fund_support', False)
                    }
                },
                
                # 过滤检查
                'passes_signal_filter': self.signal_generator.filter_signals(
                    price_indicators, frequency_indicators, volume_indicators
                )
            }
            
            # 3. 三维共振检测
            resonance_result = self.resonance_detector.detect_resonance(
                price_indicators, frequency_indicators, volume_indicators
            )
            
            validation_result['three_dimension_resonance'] = resonance_result['three_dimension_resonance']
            validation_result['resonance_strength'] = resonance_result['resonance_strength']
            
            # 4. 综合验证结果
            validation_result['valid'] = (
                validation_result['price_dimension_valid'] and
                validation_result['frequency_dimension_valid'] and
                validation_result['volume_dimension_valid'] and
                validation_result['passes_signal_filter'] and
                validation_result['three_dimension_resonance']
            )
            
            # 5. 生成验证说明
            if validation_result['valid']:
                validation_result['reason'] = '满足所有PVFRS策略条件'
            else:
                failed_conditions = []
                if not validation_result['price_dimension_valid']:
                    failed_conditions.append('价格维度条件')
                if not validation_result['frequency_dimension_valid']:
                    failed_conditions.append('频率维度条件')
                if not validation_result['volume_dimension_valid']:
                    failed_conditions.append('成交量维度条件')
                if not validation_result['passes_signal_filter']:
                    failed_conditions.append('信号过滤条件')
                
                validation_result['reason'] = f'不满足: {", ".join(failed_conditions)}'
            
            return validation_result
            
        except (DataInsufficientException, CalculationException):
            # 重新抛出已知异常
            raise
        except Exception as e:
            raise CalculationException(f"股票 {symbol} 策略条件验证失败: {str(e)}")
    
    def _calculate_amplitude_ratio(self, macro_displacement: float, avg_price_20d: float) -> float:
        """计算幅度系数 Δ₂₀ / d
        
        Args:
            macro_displacement: 宏观位移
            avg_price_20d: 20日平均价格
            
        Returns:
            float: 幅度系数
        """
        if avg_price_20d <= 0:
            return 0.0
        return macro_displacement / avg_price_20d
    
    def _validate_amplitude_ratio(self, macro_displacement: float, avg_price_20d: float) -> bool:
        """验证幅度系数有效性
        
        Args:
            macro_displacement: 宏观位移
            avg_price_20d: 20日平均价格
            
        Returns:
            bool: 幅度系数是否有效
        """
        if avg_price_20d <= 0:
            return False
        
        amplitude_ratio = macro_displacement / avg_price_20d
        # 幅度系数应该在合理范围内（0.5% - 50%）
        return 0.005 <= amplitude_ratio <= 0.5
    
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
    
    def _signal_to_dict(self, signal: Signal) -> Dict:
        """将信号对象转换为字典
        
        Args:
            signal: 信号对象
            
        Returns:
            Dict: 信号字典
        """
        return {
            'symbol': signal.symbol,
            'date': signal.date,
            'signal_type': signal.signal_type.value,
            'price': signal.price,
            'strength': signal.strength,
            'reason': signal.reason,
            'conditions_met': signal.conditions_met
        }
    
    def set_configuration(self, config: Dict) -> None:
        """设置策略配置
        
        Args:
            config: 配置字典
        """
        if 'min_data_length' in config:
            self.min_data_length = max(20, config['min_data_length'])  # 最少20天
        
        if 'enable_entry_timing_optimization' in config:
            self.enable_entry_timing_optimization = config['enable_entry_timing_optimization']
    
    def get_configuration(self) -> Dict:
        """获取当前策略配置
        
        Returns:
            Dict: 当前配置
        """
        return {
            'min_data_length': self.min_data_length,
            'enable_entry_timing_optimization': self.enable_entry_timing_optimization
        }
    
    def get_engine_status(self) -> Dict:
        """获取引擎状态
        
        Returns:
            Dict: 引擎状态信息
        """
        return {
            'engine_name': 'PVFRS Strategy Engine',
            'version': '1.0.0',
            'components': {
                'price_analyzer': type(self.price_analyzer).__name__,
                'frequency_analyzer': type(self.frequency_analyzer).__name__,
                'volume_analyzer': type(self.volume_analyzer).__name__,
                'resonance_detector': type(self.resonance_detector).__name__,
                'signal_generator': type(self.signal_generator).__name__
            },
            'configuration': self.get_configuration(),
            'ready': True
        }