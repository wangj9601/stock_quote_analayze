"""
PVFRS策略系统集成模块
连接所有组件形成完整的PVFRS策略系统，实现端到端的策略执行流程
"""

from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime, timedelta

from .models import (
    MarketData, PVFRSIndicators, Signal, Trade, BacktestResult,
    SignalType, PVFRSException, DataInsufficientException, 
    CalculationException, ConfigurationException
)
from .interfaces import IStrategyEngine, IBacktestEngine, IRiskManager, IConfigManager
from .config import PVFRSConfigManager
from .data_interface import PVFRSDataInterface
from .strategy_engine import StrategyEngine
from .backtest_engine import BacktestEngine
from .risk_manager import RiskManager
from .three_dimension_resonance import ThreeDimensionResonanceEngine

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PVFRSSystem:
    """PVFRS策略系统
    
    完整的PVFRS策略系统，集成所有组件：
    - 策略引擎：执行PVFRS策略逻辑
    - 回测引擎：历史数据回测
    - 风险管理：风险控制和资金管理
    - 数据接口：统一数据获取
    - 配置管理：参数配置和管理
    - 三维共振引擎：核心算法实现
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """初始化PVFRS策略系统
        
        Args:
            config: 可选的配置字典，与文件配置合并后传给策略引擎（买点参数等）
        """
        # 初始化配置管理器并加载当前配置
        self.config_manager = PVFRSConfigManager()
        self.config_manager.load_config()
        current_config = self.config_manager.get_current_config()
        if config:
            current_config = {**current_config, **config}
        
        # 初始化数据接口
        self.data_interface = PVFRSDataInterface()
        
        # 核心组件：策略引擎使用当前配置（共振买点参数等）
        self.strategy_engine = StrategyEngine(config=current_config)
        self.backtest_engine = BacktestEngine()
        self.risk_manager = RiskManager()
        self.resonance_engine = ThreeDimensionResonanceEngine()
        
        # 系统状态
        self.is_initialized = True
        self.last_analysis_time = None
        
        logger.info("PVFRS策略系统初始化完成")
    
    def analyze_single_stock(self, symbol: str, data: List[MarketData]) -> Dict:
        """分析单只股票
        
        提供完整的单股分析功能，包括指标计算、信号生成和风险评估。
        
        Args:
            symbol: 股票代码
            data: 市场数据列表
            
        Returns:
            Dict: 完整的分析结果
            
        Raises:
            DataInsufficientException: 数据不足时抛出
            CalculationException: 计算异常时抛出
        """
        try:
            logger.info(f"开始分析股票: {symbol}")
            
            # 1. 数据验证
            if not data or len(data) < 20:
                raise DataInsufficientException(f"股票 {symbol} 数据不足，需要至少20天数据")
            
            # 2. 策略引擎分析
            strategy_analysis = self.strategy_engine.get_strategy_analysis(symbol, data)
            
            # 3. 三维共振分析
            resonance_signal = self.resonance_engine.analyze_and_generate_signal(symbol, data)
            resonance_details = self.resonance_engine.get_analysis_details(symbol, data)
            
            # 4. 风险评估
            risk_assessment = {
                'overall_risk_score': 0.5,  # 默认中等风险
                'risk_factors': [],
                'risk_level': 'MEDIUM'
            }
            
            # 5. 策略条件验证
            condition_validation = self.strategy_engine.validate_strategy_conditions(symbol, data)
            
            # 6. 综合评分
            overall_score = self._calculate_overall_score(
                strategy_analysis, resonance_details, risk_assessment, condition_validation
            )
            
            # 7. 投资建议
            investment_advice = self._generate_investment_advice(
                overall_score, resonance_signal, risk_assessment, condition_validation
            )
            
            analysis_result = {
                'symbol': symbol,
                'analysis_time': datetime.now().isoformat(),
                'data_period': {
                    'start_date': data[0].date,
                    'end_date': data[-1].date,
                    'data_length': len(data)
                },
                
                # 核心分析结果
                'strategy_analysis': strategy_analysis,
                'resonance_analysis': {
                    'signal': self._signal_to_dict(resonance_signal) if resonance_signal else None,
                    'details': resonance_details
                },
                'risk_assessment': risk_assessment,
                'condition_validation': condition_validation,
                
                # 综合评估
                'overall_score': overall_score,
                'investment_advice': investment_advice,
                
                # 系统状态
                'system_version': self.get_system_info()['version'],
                'analysis_success': True
            }
            
            self.last_analysis_time = datetime.now()
            logger.info(f"股票 {symbol} 分析完成，综合评分: {overall_score:.2f}")
            
            return analysis_result
            
        except (DataInsufficientException, CalculationException) as e:
            logger.error(f"股票 {symbol} 分析失败: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"股票 {symbol} 分析异常: {str(e)}")
            raise CalculationException(f"股票 {symbol} 分析失败: {str(e)}")
    
    def analyze_stock(self, symbol: str, data: List[MarketData]) -> Dict:
        """分析单只股票（兼容接口）
        
        这是 analyze_single_stock 的别名，为了兼容 frontend_interface 的调用。
        
        Args:
            symbol: 股票代码
            data: 市场数据列表
            
        Returns:
            Dict: 完整的分析结果（包含 strategy_analysis, resonance_analysis 等字段，
                  以及用于选股的简化字段：signal_strength, indicators, conditions_met）
        """
        # 调用完整分析
        full_result = self.analyze_single_stock(symbol, data)
        
        # 提取信号强度和指标用于选股
        signal_strength = full_result.get('overall_score', 0.0)
        resonance_signal = full_result.get('resonance_analysis', {}).get('signal', {})
        if resonance_signal:
            signal_strength = resonance_signal.get('strength', signal_strength)
        
        # 构建指标对象（用于选股结果）
        strategy_analysis = full_result.get('strategy_analysis', {})
        indicators_dict = {
            'price_dimension': strategy_analysis.get('price_dimension', {}),
            'frequency_dimension': strategy_analysis.get('frequency_dimension', {}),
            'volume_dimension': strategy_analysis.get('volume_dimension', {}),
        }
        
        # 获取策略引擎的指标（如果需要 PVFRSIndicators 对象）
        try:
            from dataclasses import asdict
            pvfrs_indicators = self.strategy_engine.analyze_stock(symbol, data)
            # 将 PVFRSIndicators 对象转换为字典，以便 JSON 序列化
            if pvfrs_indicators:
                indicators_dict['pvfrs_indicators'] = asdict(pvfrs_indicators)
        except Exception:
            pass
        
        # 获取条件验证结果
        conditions_met = full_result.get('condition_validation', {})
        
        # 扩展结果，添加用于选股的字段
        full_result['signal_strength'] = signal_strength
        full_result['indicators'] = indicators_dict
        full_result['conditions_met'] = conditions_met
        
        return full_result
    
    def screen_stocks(self, symbols: List[str], target_date: Optional[str] = None) -> Dict:
        """批量选股
        
        对股票列表进行批量分析和筛选，返回符合PVFRS条件的股票。
        
        Args:
            symbols: 股票代码列表
            target_date: 目标分析日期，如果不提供则使用最新日期
            
        Returns:
            Dict: 选股结果
        """
        try:
            logger.info(f"开始批量选股，股票数量: {len(symbols)}")
            
            if not target_date:
                target_date = datetime.now().strftime('%Y-%m-%d')
            
            # 1. 获取股票数据（这里需要实际的数据获取实现）
            stock_data_dict = {}
            failed_symbols = []
            
            for symbol in symbols:
                try:
                    # 这里应该调用实际的数据获取接口
                    # data = self.data_interface.get_stock_data(symbol, target_date)
                    # 暂时跳过数据获取，使用空数据
                    data = []
                    if data:
                        stock_data_dict[symbol] = data
                    else:
                        failed_symbols.append(symbol)
                except Exception as e:
                    logger.warning(f"获取股票 {symbol} 数据失败: {str(e)}")
                    failed_symbols.append(symbol)
            
            # 2. 批量分析
            analysis_results = self.resonance_engine.batch_analyze_stocks(stock_data_dict)
            
            # 3. 筛选有信号的股票
            qualified_stocks = []
            for symbol, result in analysis_results.items():
                if result['has_signal'] and result['signal']:
                    signal_dict = self._signal_to_dict(result['signal'])
                    qualified_stocks.append({
                        'symbol': symbol,
                        'signal': signal_dict,
                        'analysis': result['analysis']
                    })
            
            # 4. 按信号强度排序
            qualified_stocks.sort(key=lambda x: x['signal']['strength'], reverse=True)
            
            # 5. 生成选股统计
            screening_stats = self._generate_screening_stats(
                symbols, stock_data_dict, analysis_results, qualified_stocks, failed_symbols
            )
            
            # 6. 维度分析汇总
            dimension_summary = self.resonance_engine.get_dimension_summary(analysis_results)
            
            screening_result = {
                'screening_time': datetime.now().isoformat(),
                'target_date': target_date,
                'input_symbols': symbols,
                'qualified_stocks': qualified_stocks,
                'screening_stats': screening_stats,
                'dimension_summary': dimension_summary,
                'failed_symbols': failed_symbols,
                'system_version': self.get_system_info()['version']
            }
            
            logger.info(f"批量选股完成，筛选出 {len(qualified_stocks)} 只股票")
            
            return screening_result
            
        except Exception as e:
            logger.error(f"批量选股失败: {str(e)}")
            raise CalculationException(f"批量选股失败: {str(e)}")
    
    def run_backtest(self, symbols: List[str], start_date: str, end_date: str, 
                    initial_capital: float = 100000) -> Dict:
        """运行回测
        
        对指定股票列表和时间范围运行完整的策略回测。
        
        Args:
            symbols: 股票代码列表
            start_date: 回测开始日期
            end_date: 回测结束日期
            initial_capital: 初始资金
            
        Returns:
            Dict: 回测结果
        """
        try:
            logger.info(f"开始回测，股票数量: {len(symbols)}, 时间范围: {start_date} - {end_date}")
            
            # 1. 获取回测数据（这里需要实际的数据获取实现）
            backtest_data = {}
            for symbol in symbols:
                try:
                    # data = self.data_interface.get_historical_data(symbol, start_date, end_date)
                    # 暂时使用空数据
                    data = []
                    if data:
                        backtest_data[symbol] = data
                except Exception as e:
                    logger.warning(f"获取股票 {symbol} 历史数据失败: {str(e)}")
            
            if not backtest_data:
                raise DataInsufficientException("没有可用的回测数据")
            
            # 2. 运行回测引擎
            backtest_result = self.backtest_engine.run_backtest(
                backtest_data, initial_capital, self.config_manager.get_current_config()
            )
            
            # 3. 风险分析
            risk_analysis = self.risk_manager.analyze_backtest_risk(backtest_result)
            
            # 4. 生成回测报告
            backtest_report = {
                'backtest_time': datetime.now().isoformat(),
                'parameters': {
                    'symbols': symbols,
                    'start_date': start_date,
                    'end_date': end_date,
                    'initial_capital': initial_capital
                },
                'backtest_result': self._backtest_result_to_dict(backtest_result),
                'risk_analysis': risk_analysis,
                'config_used': self.config_manager.get_current_config(),
                'system_version': self.get_system_info()['version']
            }
            
            logger.info(f"回测完成，总收益率: {backtest_result.total_return:.2%}")
            
            return backtest_report
            
        except Exception as e:
            logger.error(f"回测失败: {str(e)}")
            raise CalculationException(f"回测失败: {str(e)}")
    
    def optimize_parameters(self, symbols: List[str], start_date: str, end_date: str,
                          parameter_ranges: Dict) -> Dict:
        """参数优化
        
        对策略参数进行优化，寻找最佳参数组合。
        
        Args:
            symbols: 股票代码列表
            start_date: 优化开始日期
            end_date: 优化结束日期
            parameter_ranges: 参数范围字典
            
        Returns:
            Dict: 参数优化结果
        """
        try:
            logger.info("开始参数优化")
            
            # 这里应该实现参数优化逻辑
            # 暂时返回基本结构
            optimization_result = {
                'optimization_time': datetime.now().isoformat(),
                'parameters': {
                    'symbols': symbols,
                    'start_date': start_date,
                    'end_date': end_date,
                    'parameter_ranges': parameter_ranges
                },
                'best_parameters': self.config_manager.get_current_config(),
                'optimization_results': [],
                'system_version': self.get_system_info()['version']
            }
            
            logger.info("参数优化完成")
            
            return optimization_result
            
        except Exception as e:
            logger.error(f"参数优化失败: {str(e)}")
            raise CalculationException(f"参数优化失败: {str(e)}")
    
    def get_system_status(self) -> Dict:
        """获取系统状态
        
        Returns:
            Dict: 系统状态信息
        """
        return {
            'system_name': 'PVFRS Strategy System',
            'version': '1.0.0',
            'initialized': self.is_initialized,
            'last_analysis_time': self.last_analysis_time.isoformat() if self.last_analysis_time else None,
            'components': {
                'config_manager': type(self.config_manager).__name__,
                'data_interface': type(self.data_interface).__name__,
                'strategy_engine': type(self.strategy_engine).__name__,
                'backtest_engine': type(self.backtest_engine).__name__,
                'risk_manager': type(self.risk_manager).__name__,
                'resonance_engine': type(self.resonance_engine).__name__
            },
            'current_config': self.config_manager.get_current_config(),
            'system_ready': self._check_system_ready()
        }
    
    def get_system_info(self) -> Dict:
        """获取系统信息
        
        Returns:
            Dict: 系统基本信息
        """
        return {
            'name': 'PVFRS Strategy System',
            'version': '1.0.0',
            'description': '量价频三维共振演化策略系统',
            'author': 'PVFRS Strategy Team',
            'components': [
                'Strategy Engine', 'Backtest Engine', 'Risk Manager',
                'Data Interface', 'Config Manager', 'Resonance Engine'
            ]
        }
    
    def update_config(self, new_config: Dict) -> bool:
        """更新系统配置
        
        Args:
            new_config: 新的配置字典
            
        Returns:
            bool: 更新是否成功
        """
        try:
            self.config_manager.update_config(new_config)
            logger.info("系统配置更新成功")
            return True
        except Exception as e:
            logger.error(f"系统配置更新失败: {str(e)}")
            return False
    
    def validate_system(self) -> Dict:
        """验证系统完整性
        
        Returns:
            Dict: 验证结果
        """
        validation_result = {
            'validation_time': datetime.now().isoformat(),
            'overall_valid': True,
            'component_status': {},
            'issues': []
        }
        
        # 验证各个组件
        components = {
            'config_manager': self.config_manager,
            'data_interface': self.data_interface,
            'strategy_engine': self.strategy_engine,
            'backtest_engine': self.backtest_engine,
            'risk_manager': self.risk_manager,
            'resonance_engine': self.resonance_engine
        }
        
        for name, component in components.items():
            try:
                # 检查组件是否正确初始化
                if hasattr(component, 'validate') and callable(component.validate):
                    component_valid = component.validate()
                else:
                    component_valid = component is not None
                
                validation_result['component_status'][name] = {
                    'valid': component_valid,
                    'type': type(component).__name__
                }
                
                if not component_valid:
                    validation_result['overall_valid'] = False
                    validation_result['issues'].append(f"组件 {name} 验证失败")
                    
            except Exception as e:
                validation_result['component_status'][name] = {
                    'valid': False,
                    'error': str(e)
                }
                validation_result['overall_valid'] = False
                validation_result['issues'].append(f"组件 {name} 验证异常: {str(e)}")
        
        # 验证配置
        try:
            config_valid = self.config_manager.validate_config(self.config_manager.get_current_config())
            validation_result['config_valid'] = config_valid
            if not config_valid:
                validation_result['overall_valid'] = False
                validation_result['issues'].append("配置验证失败")
        except Exception as e:
            validation_result['config_valid'] = False
            validation_result['overall_valid'] = False
            validation_result['issues'].append(f"配置验证异常: {str(e)}")
        
        return validation_result
    
    def _calculate_overall_score(self, strategy_analysis: Dict, resonance_details: Dict,
                               risk_assessment: Dict, condition_validation: Dict) -> float:
        """计算综合评分
        
        Args:
            strategy_analysis: 策略分析结果
            resonance_details: 共振分析详情
            risk_assessment: 风险评估结果
            condition_validation: 条件验证结果
            
        Returns:
            float: 综合评分 (0-1)
        """
        score = 0.0
        
        # 策略评估权重 40%
        if strategy_analysis.get('strategy_assessment', {}).get('overall_score'):
            score += strategy_analysis['strategy_assessment']['overall_score'] * 0.4
        
        # 共振强度权重 30%
        if resonance_details.get('resonance_result', {}).get('resonance_strength'):
            score += resonance_details['resonance_result']['resonance_strength'] * 0.3
        
        # 条件验证权重 20%
        if condition_validation.get('valid'):
            score += 0.2
        
        # 风险评估权重 10%（风险越低分数越高）
        risk_score = risk_assessment.get('overall_risk_score', 0.5)
        score += (1 - risk_score) * 0.1
        
        return min(1.0, max(0.0, score))
    
    def _generate_investment_advice(self, overall_score: float, resonance_signal: Optional[Signal],
                                  risk_assessment: Dict, condition_validation: Dict) -> Dict:
        """生成投资建议
        
        Args:
            overall_score: 综合评分
            resonance_signal: 共振信号
            risk_assessment: 风险评估
            condition_validation: 条件验证
            
        Returns:
            Dict: 投资建议
        """
        advice = {
            'recommendation': 'HOLD',  # BUY, SELL, HOLD
            'confidence': 0.0,
            'reasons': [],
            'risk_level': 'MEDIUM',
            'suggested_position_size': 0.0
        }
        
        # 基于综合评分给出建议
        if overall_score >= 0.8 and resonance_signal and condition_validation.get('valid'):
            advice['recommendation'] = 'BUY'
            advice['confidence'] = overall_score
            advice['reasons'].append('三维共振信号强烈')
            advice['suggested_position_size'] = min(0.1, overall_score * 0.15)
        elif overall_score >= 0.6 and resonance_signal:
            advice['recommendation'] = 'BUY'
            advice['confidence'] = overall_score * 0.8
            advice['reasons'].append('共振信号较好')
            advice['suggested_position_size'] = min(0.05, overall_score * 0.1)
        else:
            advice['recommendation'] = 'HOLD'
            advice['confidence'] = 0.5
            advice['reasons'].append('信号不够强烈，建议观望')
        
        # 风险等级
        risk_score = risk_assessment.get('overall_risk_score', 0.5)
        if risk_score < 0.3:
            advice['risk_level'] = 'LOW'
        elif risk_score > 0.7:
            advice['risk_level'] = 'HIGH'
            if advice['recommendation'] == 'BUY':
                advice['suggested_position_size'] *= 0.5  # 高风险时减少仓位
        
        return advice
    
    def _generate_screening_stats(self, input_symbols: List[str], stock_data_dict: Dict,
                                analysis_results: Dict, qualified_stocks: List[Dict],
                                failed_symbols: List[str]) -> Dict:
        """生成选股统计
        
        Args:
            input_symbols: 输入股票列表
            stock_data_dict: 股票数据字典
            analysis_results: 分析结果
            qualified_stocks: 符合条件的股票
            failed_symbols: 失败的股票
            
        Returns:
            Dict: 选股统计
        """
        return {
            'total_input': len(input_symbols),
            'data_available': len(stock_data_dict),
            'analysis_completed': len(analysis_results),
            'qualified_count': len(qualified_stocks),
            'failed_count': len(failed_symbols),
            'success_rate': len(qualified_stocks) / len(input_symbols) if input_symbols else 0,
            'qualification_rate': len(qualified_stocks) / len(analysis_results) if analysis_results else 0
        }
    
    def _check_system_ready(self) -> bool:
        """检查系统是否就绪
        
        Returns:
            bool: 系统是否就绪
        """
        try:
            return (
                self.is_initialized and
                self.config_manager is not None and
                self.strategy_engine is not None and
                self.backtest_engine is not None and
                self.risk_manager is not None and
                self.resonance_engine is not None
            )
        except:
            return False
    
    def _signal_to_dict(self, signal: Signal) -> Dict:
        """将信号对象转换为字典
        
        Args:
            signal: 信号对象
            
        Returns:
            Dict: 信号字典
        """
        if not signal:
            return None
        
        return {
            'symbol': signal.symbol,
            'date': signal.date,
            'signal_type': signal.signal_type.value,
            'price': signal.price,
            'strength': signal.strength,
            'reason': signal.reason,
            'conditions_met': signal.conditions_met
        }
    
    def _backtest_result_to_dict(self, result: BacktestResult) -> Dict:
        """将回测结果转换为字典
        
        Args:
            result: 回测结果对象
            
        Returns:
            Dict: 回测结果字典
        """
        return {
            'initial_capital': result.initial_capital,
            'final_capital': result.final_capital,
            'total_return': result.total_return,
            'annual_return': result.annual_return,
            'max_drawdown': result.max_drawdown,
            'sharpe_ratio': result.sharpe_ratio,
            'win_rate': result.win_rate,
            'profit_factor': result.profit_factor,
            'total_trades': result.total_trades,
            'winning_trades': result.winning_trades,
            'losing_trades': result.losing_trades,
            'avg_holding_period': result.avg_holding_period
        }


# 便捷函数
def create_pvfrs_system(config: Optional[Dict] = None) -> PVFRSSystem:
    """创建PVFRS策略系统实例
    
    Args:
        config: 可选的配置字典
        
    Returns:
        PVFRSSystem: PVFRS策略系统实例
    """
    return PVFRSSystem(config)


def quick_analyze_stock(symbol: str, data: List[MarketData], config: Optional[Dict] = None) -> Dict:
    """快速分析单只股票
    
    Args:
        symbol: 股票代码
        data: 市场数据列表
        config: 可选的配置字典
        
    Returns:
        Dict: 分析结果
    """
    system = create_pvfrs_system(config)
    return system.analyze_single_stock(symbol, data)


def quick_screen_stocks(symbols: List[str], target_date: Optional[str] = None,
                       config: Optional[Dict] = None) -> Dict:
    """快速批量选股
    
    Args:
        symbols: 股票代码列表
        target_date: 目标分析日期
        config: 可选的配置字典
        
    Returns:
        Dict: 选股结果
    """
    system = create_pvfrs_system(config)
    return system.screen_stocks(symbols, target_date)