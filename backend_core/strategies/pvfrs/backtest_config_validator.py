"""
PVFRS策略回测参数配置和验证模块
负责回测参数的配置界面逻辑和参数有效性验证
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date, timedelta
import logging
from dataclasses import dataclass, asdict

from .models import PVFRSException

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class ParameterConstraint:
    """参数约束定义"""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[List[Any]] = None
    required: bool = True
    data_type: type = str
    description: str = ""


class BacktestConfigValidator:
    """回测配置验证器
    
    负责验证回测参数的有效性，包括：
    - 日期范围验证
    - 股票池验证
    - 策略参数验证
    - 风险参数验证
    - 资金配置验证
    """
    
    def __init__(self):
        """初始化配置验证器"""
        # 定义参数约束
        self.constraints = self._define_parameter_constraints()
        
        # 验证规则
        self.validation_rules = self._define_validation_rules()
        
        logger.info("回测配置验证器初始化完成")
    
    def validate_backtest_config(self, config_dict: Dict) -> Tuple[bool, List[str]]:
        """验证完整的回测配置
        
        Args:
            config_dict: 配置字典
            
        Returns:
            Tuple[bool, List[str]]: (是否有效, 错误信息列表)
        """
        errors = []
        
        try:
            # 1. 基本字段验证
            basic_errors = self._validate_basic_fields(config_dict)
            errors.extend(basic_errors)
            
            # 2. 日期验证
            date_errors = self._validate_dates(config_dict)
            errors.extend(date_errors)
            
            # 3. 股票池验证
            stock_errors = self._validate_stock_pool(config_dict)
            errors.extend(stock_errors)
            
            # 4. 资金配置验证
            capital_errors = self._validate_capital_config(config_dict)
            errors.extend(capital_errors)
            
            # 5. 策略参数验证
            strategy_errors = self._validate_strategy_params(config_dict.get('strategy_params', {}))
            errors.extend(strategy_errors)
            
            # 6. 风险参数验证
            risk_errors = self._validate_risk_params(config_dict.get('risk_params', {}))
            errors.extend(risk_errors)
            
            # 7. 业务逻辑验证
            business_errors = self._validate_business_logic(config_dict)
            errors.extend(business_errors)
            
            is_valid = len(errors) == 0
            
            if is_valid:
                logger.info("回测配置验证通过")
            else:
                logger.warning(f"回测配置验证失败，发现 {len(errors)} 个错误")
            
            return is_valid, errors
            
        except Exception as e:
            logger.error(f"配置验证过程中发生异常: {str(e)}")
            errors.append(f"配置验证异常: {str(e)}")
            return False, errors
    
    def get_default_config(self) -> Dict:
        """获取默认配置
        
        Returns:
            Dict: 默认配置字典
        """
        return {
            'start_date': (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
            'end_date': datetime.now().strftime('%Y-%m-%d'),
            'stock_pool': ['000001', '000002', '600000'],  # 添加默认股票
            'initial_capital': 100000.0,
            'strategy_params': {
                'observation_period': 20,
                'min_volume_ratio': 1.0,
                'min_price_change': 0.0,
                'enable_frequency_filter': True,
                'enable_volume_filter': True,
                'amplitude_threshold': 0.05
            },
            'risk_params': {
                'stop_loss_rate': 0.1,
                'take_profit_rate': 0.2,
                'max_holding_days': 30,
                'max_position_size': 0.1,
                'enable_stop_loss': True,
                'enable_take_profit': True,
                'enable_time_stop': True
            }
        }
    
    def get_parameter_schema(self) -> Dict:
        """获取参数配置模式
        
        Returns:
            Dict: 参数配置模式，用于前端界面生成
        """
        return {
            'basic_config': {
                'title': '基本配置',
                'fields': {
                    'start_date': {
                        'label': '开始日期',
                        'type': 'date',
                        'required': True,
                        'description': '回测开始日期'
                    },
                    'end_date': {
                        'label': '结束日期',
                        'type': 'date',
                        'required': True,
                        'description': '回测结束日期'
                    },
                    'initial_capital': {
                        'label': '初始资金',
                        'type': 'number',
                        'required': True,
                        'min': 10000,
                        'max': 10000000,
                        'step': 1000,
                        'description': '回测初始资金（元）'
                    }
                }
            },
            'stock_pool_config': {
                'title': '股票池配置',
                'fields': {
                    'stock_pool': {
                        'label': '股票代码列表',
                        'type': 'textarea',
                        'required': True,
                        'placeholder': '请输入股票代码，每行一个，如：000001',
                        'description': '回测股票池，支持A股代码'
                    }
                }
            },
            'strategy_params': {
                'title': 'PVFRS策略参数',
                'fields': {
                    'observation_period': {
                        'label': '观察周期',
                        'type': 'number',
                        'required': True,
                        'min': 10,
                        'max': 60,
                        'default': 20,
                        'description': '价格和成交量分析的观察周期（天）'
                    },
                    'min_volume_ratio': {
                        'label': '最小成交量比率',
                        'type': 'number',
                        'required': True,
                        'min': 0.5,
                        'max': 5.0,
                        'step': 0.1,
                        'default': 1.0,
                        'description': '当前成交量与平均成交量的最小比率'
                    },
                    'amplitude_threshold': {
                        'label': '幅度阈值',
                        'type': 'number',
                        'required': True,
                        'min': 0.01,
                        'max': 0.5,
                        'step': 0.01,
                        'default': 0.05,
                        'description': '价格幅度变化的最小阈值'
                    },
                    'enable_frequency_filter': {
                        'label': '启用频率过滤',
                        'type': 'checkbox',
                        'default': True,
                        'description': '是否启用上涨频率优势过滤'
                    },
                    'enable_volume_filter': {
                        'label': '启用成交量过滤',
                        'type': 'checkbox',
                        'default': True,
                        'description': '是否启用成交量效率过滤'
                    }
                }
            },
            'risk_params': {
                'title': '风险管理参数',
                'fields': {
                    'stop_loss_rate': {
                        'label': '止损比例',
                        'type': 'number',
                        'required': True,
                        'min': 0.01,
                        'max': 0.5,
                        'step': 0.01,
                        'default': 0.1,
                        'description': '止损比例（如0.1表示10%）'
                    },
                    'take_profit_rate': {
                        'label': '止盈比例',
                        'type': 'number',
                        'required': True,
                        'min': 0.05,
                        'max': 1.0,
                        'step': 0.01,
                        'default': 0.2,
                        'description': '止盈比例（如0.2表示20%）'
                    },
                    'max_holding_days': {
                        'label': '最大持有天数',
                        'type': 'number',
                        'required': True,
                        'min': 1,
                        'max': 100,
                        'default': 30,
                        'description': '单只股票的最大持有天数'
                    },
                    'max_position_size': {
                        'label': '最大仓位比例',
                        'type': 'number',
                        'required': True,
                        'min': 0.01,
                        'max': 1.0,
                        'step': 0.01,
                        'default': 0.1,
                        'description': '单只股票的最大仓位比例'
                    },
                    'enable_stop_loss': {
                        'label': '启用止损',
                        'type': 'checkbox',
                        'default': True,
                        'description': '是否启用止损功能'
                    },
                    'enable_take_profit': {
                        'label': '启用止盈',
                        'type': 'checkbox',
                        'default': True,
                        'description': '是否启用止盈功能'
                    },
                    'enable_time_stop': {
                        'label': '启用时间止损',
                        'type': 'checkbox',
                        'default': True,
                        'description': '是否启用时间止损功能'
                    }
                }
            }
        }
    
    def validate_and_normalize_config(self, config_dict: Dict) -> Dict:
        """验证并标准化配置
        
        Args:
            config_dict: 原始配置字典
            
        Returns:
            Dict: 标准化后的配置字典
            
        Raises:
            PVFRSException: 配置无效时抛出
        """
        # 验证配置
        is_valid, errors = self.validate_backtest_config(config_dict)
        
        if not is_valid:
            error_msg = "配置验证失败:\n" + "\n".join(errors)
            raise PVFRSException(error_msg)
        
        # 标准化配置
        normalized_config = self._normalize_config(config_dict)
        
        logger.info("配置验证和标准化完成")
        return normalized_config
    
    def _define_parameter_constraints(self) -> Dict[str, ParameterConstraint]:
        """定义参数约束"""
        return {
            'start_date': ParameterConstraint(
                required=True,
                data_type=str,
                description="回测开始日期，格式：YYYY-MM-DD"
            ),
            'end_date': ParameterConstraint(
                required=True,
                data_type=str,
                description="回测结束日期，格式：YYYY-MM-DD"
            ),
            'initial_capital': ParameterConstraint(
                min_value=10000,
                max_value=10000000,
                required=True,
                data_type=float,
                description="初始资金，范围：10,000 - 10,000,000"
            ),
            'observation_period': ParameterConstraint(
                min_value=10,
                max_value=60,
                required=True,
                data_type=int,
                description="观察周期，范围：10-60天"
            ),
            'min_volume_ratio': ParameterConstraint(
                min_value=0.5,
                max_value=5.0,
                required=True,
                data_type=float,
                description="最小成交量比率，范围：0.5-5.0"
            ),
            'stop_loss_rate': ParameterConstraint(
                min_value=0.01,
                max_value=0.5,
                required=True,
                data_type=float,
                description="止损比例，范围：1%-50%"
            ),
            'take_profit_rate': ParameterConstraint(
                min_value=0.05,
                max_value=1.0,
                required=True,
                data_type=float,
                description="止盈比例，范围：5%-100%"
            ),
            'max_holding_days': ParameterConstraint(
                min_value=1,
                max_value=100,
                required=True,
                data_type=int,
                description="最大持有天数，范围：1-100天"
            ),
            'max_position_size': ParameterConstraint(
                min_value=0.01,
                max_value=1.0,
                required=True,
                data_type=float,
                description="最大仓位比例，范围：1%-100%"
            )
        }
    
    def _define_validation_rules(self) -> Dict[str, callable]:
        """定义验证规则"""
        return {
            'date_range_valid': self._validate_date_range,
            'stock_pool_not_empty': self._validate_stock_pool_not_empty,
            'profit_loss_ratio_valid': self._validate_profit_loss_ratio,
            'capital_sufficient': self._validate_capital_sufficient
        }
    
    def _validate_basic_fields(self, config: Dict) -> List[str]:
        """验证基本字段"""
        errors = []
        required_fields = ['start_date', 'end_date', 'stock_pool', 'initial_capital']
        
        for field in required_fields:
            if field not in config:
                errors.append(f"缺少必需字段: {field}")
            elif config[field] is None:
                errors.append(f"字段 {field} 不能为空")
        
        return errors
    
    def _validate_dates(self, config: Dict) -> List[str]:
        """验证日期配置"""
        errors = []
        
        try:
            start_date_str = config.get('start_date')
            end_date_str = config.get('end_date')
            
            if not start_date_str or not end_date_str:
                return errors  # 基本字段验证会处理
            
            # 验证日期格式
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            except ValueError:
                errors.append("日期格式错误，应为 YYYY-MM-DD")
                return errors
            
            # 验证日期逻辑
            if start_date >= end_date:
                errors.append("开始日期必须早于结束日期")
            
            # 验证日期范围
            min_date = datetime(2010, 1, 1)
            max_date = datetime.now()
            
            if start_date < min_date:
                errors.append(f"开始日期不能早于 {min_date.strftime('%Y-%m-%d')}")
            
            if end_date > max_date:
                errors.append(f"结束日期不能晚于 {max_date.strftime('%Y-%m-%d')}")
            
            # 验证回测期间长度
            period_days = (end_date - start_date).days
            if period_days < 30:
                errors.append("回测期间至少需要30天")
            elif period_days > 3650:  # 10年
                errors.append("回测期间不能超过10年")
        
        except Exception as e:
            errors.append(f"日期验证异常: {str(e)}")
        
        return errors
    
    def _validate_stock_pool(self, config: Dict) -> List[str]:
        """验证股票池配置"""
        errors = []
        
        try:
            stock_pool = config.get('stock_pool', [])
            
            if not stock_pool:
                errors.append("股票池不能为空")
                return errors
            
            if not isinstance(stock_pool, list):
                errors.append("股票池必须是列表格式")
                return errors
            
            # 验证股票代码格式
            valid_codes = []
            for symbol in stock_pool:
                if not isinstance(symbol, str):
                    errors.append(f"股票代码必须是字符串: {symbol}")
                    continue
                
                symbol = symbol.strip()
                if not symbol:
                    continue
                
                # 简单的A股代码格式验证
                if not (symbol.isdigit() and len(symbol) == 6):
                    errors.append(f"无效的股票代码格式: {symbol}")
                    continue
                
                valid_codes.append(symbol)
            
            if not valid_codes:
                errors.append("没有有效的股票代码")
            elif len(valid_codes) > 100:
                errors.append("股票池数量不能超过100只")
        
        except Exception as e:
            errors.append(f"股票池验证异常: {str(e)}")
        
        return errors
    
    def _validate_capital_config(self, config: Dict) -> List[str]:
        """验证资金配置"""
        errors = []
        
        try:
            initial_capital = config.get('initial_capital')
            
            if initial_capital is None:
                return errors  # 基本字段验证会处理
            
            # 类型验证
            if not isinstance(initial_capital, (int, float)):
                errors.append("初始资金必须是数字")
                return errors
            
            # 范围验证
            if initial_capital < 10000:
                errors.append("初始资金不能少于10,000元")
            elif initial_capital > 10000000:
                errors.append("初始资金不能超过10,000,000元")
        
        except Exception as e:
            errors.append(f"资金配置验证异常: {str(e)}")
        
        return errors
    
    def _validate_strategy_params(self, strategy_params: Dict) -> List[str]:
        """验证策略参数"""
        errors = []
        
        try:
            # 观察周期验证
            observation_period = strategy_params.get('observation_period', 20)
            if not isinstance(observation_period, int) or observation_period < 10 or observation_period > 60:
                errors.append("观察周期必须是10-60之间的整数")
            
            # 成交量比率验证
            min_volume_ratio = strategy_params.get('min_volume_ratio', 1.0)
            if not isinstance(min_volume_ratio, (int, float)) or min_volume_ratio < 0.5 or min_volume_ratio > 5.0:
                errors.append("最小成交量比率必须是0.5-5.0之间的数字")
            
            # 幅度阈值验证
            amplitude_threshold = strategy_params.get('amplitude_threshold', 0.05)
            if not isinstance(amplitude_threshold, (int, float)) or amplitude_threshold < 0.01 or amplitude_threshold > 0.5:
                errors.append("幅度阈值必须是0.01-0.5之间的数字")
        
        except Exception as e:
            errors.append(f"策略参数验证异常: {str(e)}")
        
        return errors
    
    def _validate_risk_params(self, risk_params: Dict) -> List[str]:
        """验证风险参数"""
        errors = []
        
        try:
            # 止损比例验证
            stop_loss_rate = risk_params.get('stop_loss_rate', 0.1)
            if not isinstance(stop_loss_rate, (int, float)) or stop_loss_rate < 0.01 or stop_loss_rate > 0.5:
                errors.append("止损比例必须是0.01-0.5之间的数字")
            
            # 止盈比例验证
            take_profit_rate = risk_params.get('take_profit_rate', 0.2)
            if not isinstance(take_profit_rate, (int, float)) or take_profit_rate < 0.05 or take_profit_rate > 1.0:
                errors.append("止盈比例必须是0.05-1.0之间的数字")
            
            # 最大持有天数验证
            max_holding_days = risk_params.get('max_holding_days', 30)
            if not isinstance(max_holding_days, int) or max_holding_days < 1 or max_holding_days > 100:
                errors.append("最大持有天数必须是1-100之间的整数")
            
            # 最大仓位比例验证
            max_position_size = risk_params.get('max_position_size', 0.1)
            if not isinstance(max_position_size, (int, float)) or max_position_size < 0.01 or max_position_size > 1.0:
                errors.append("最大仓位比例必须是0.01-1.0之间的数字")
            
            # 止盈止损比例逻辑验证
            if isinstance(stop_loss_rate, (int, float)) and isinstance(take_profit_rate, (int, float)):
                if take_profit_rate <= stop_loss_rate:
                    errors.append("止盈比例应该大于止损比例")
        
        except Exception as e:
            errors.append(f"风险参数验证异常: {str(e)}")
        
        return errors
    
    def _validate_business_logic(self, config: Dict) -> List[str]:
        """验证业务逻辑"""
        errors = []
        
        try:
            # 验证股票池与资金的匹配性
            stock_pool = config.get('stock_pool', [])
            initial_capital = config.get('initial_capital', 0)
            risk_params = config.get('risk_params', {})
            max_position_size = risk_params.get('max_position_size', 0.1)
            
            if stock_pool and initial_capital and max_position_size:
                # 调整最小资金要求，使其更合理
                min_capital_per_stock = 5000  # 降低每只股票最少需要的资金
                max_concurrent_positions = int(initial_capital / min_capital_per_stock)
                
                # 股票池可以比最大并发持仓数大，因为不会同时持有所有股票
                reasonable_pool_size = max(max_concurrent_positions * 5, 10)  # 至少允许10只股票
                
                if len(stock_pool) > reasonable_pool_size:
                    errors.append(f"根据当前资金设置，建议股票池不超过{reasonable_pool_size}只股票")
                
                # 检查单只股票的最小投资金额是否合理
                min_investment_per_stock = initial_capital * max_position_size
                if min_investment_per_stock < 1000:
                    errors.append(f"单只股票最大投资金额过小({min_investment_per_stock:.0f}元)，建议增加初始资金或调整仓位比例")
        
        except Exception as e:
            errors.append(f"业务逻辑验证异常: {str(e)}")
        
        return errors
    
    def _normalize_config(self, config: Dict) -> Dict:
        """标准化配置"""
        normalized = config.copy()
        
        # 标准化股票代码
        if 'stock_pool' in normalized:
            stock_pool = normalized['stock_pool']
            if isinstance(stock_pool, list):
                # 去重、去空、标准化格式
                normalized_stocks = []
                seen = set()
                for symbol in stock_pool:
                    if isinstance(symbol, str):
                        symbol = symbol.strip().upper()
                        if symbol and symbol not in seen:
                            normalized_stocks.append(symbol)
                            seen.add(symbol)
                normalized['stock_pool'] = normalized_stocks
        
        # 确保数值类型正确
        if 'initial_capital' in normalized:
            normalized['initial_capital'] = float(normalized['initial_capital'])
        
        # 标准化策略参数
        if 'strategy_params' in normalized:
            strategy_params = normalized['strategy_params']
            if 'observation_period' in strategy_params:
                strategy_params['observation_period'] = int(strategy_params['observation_period'])
            if 'min_volume_ratio' in strategy_params:
                strategy_params['min_volume_ratio'] = float(strategy_params['min_volume_ratio'])
            if 'amplitude_threshold' in strategy_params:
                strategy_params['amplitude_threshold'] = float(strategy_params['amplitude_threshold'])
        
        # 标准化风险参数
        if 'risk_params' in normalized:
            risk_params = normalized['risk_params']
            if 'stop_loss_rate' in risk_params:
                risk_params['stop_loss_rate'] = float(risk_params['stop_loss_rate'])
            if 'take_profit_rate' in risk_params:
                risk_params['take_profit_rate'] = float(risk_params['take_profit_rate'])
            if 'max_holding_days' in risk_params:
                risk_params['max_holding_days'] = int(risk_params['max_holding_days'])
            if 'max_position_size' in risk_params:
                risk_params['max_position_size'] = float(risk_params['max_position_size'])
        
        return normalized
    
    # 验证规则方法
    def _validate_date_range(self, config: Dict) -> bool:
        """验证日期范围"""
        try:
            start_date = datetime.strptime(config['start_date'], "%Y-%m-%d")
            end_date = datetime.strptime(config['end_date'], "%Y-%m-%d")
            return start_date < end_date
        except:
            return False
    
    def _validate_stock_pool_not_empty(self, config: Dict) -> bool:
        """验证股票池非空"""
        stock_pool = config.get('stock_pool', [])
        return isinstance(stock_pool, list) and len(stock_pool) > 0
    
    def _validate_profit_loss_ratio(self, config: Dict) -> bool:
        """验证止盈止损比例"""
        try:
            risk_params = config.get('risk_params', {})
            stop_loss = risk_params.get('stop_loss_rate', 0)
            take_profit = risk_params.get('take_profit_rate', 0)
            return take_profit > stop_loss
        except:
            return False
    
    def _validate_capital_sufficient(self, config: Dict) -> bool:
        """验证资金充足性"""
        try:
            initial_capital = config.get('initial_capital', 0)
            stock_count = len(config.get('stock_pool', []))
            return initial_capital >= stock_count * 5000  # 每只股票至少5000元
        except:
            return False


# 便捷函数
def create_config_validator() -> BacktestConfigValidator:
    """创建配置验证器实例
    
    Returns:
        BacktestConfigValidator: 配置验证器实例
    """
    return BacktestConfigValidator()


def validate_config_quick(config_dict: Dict) -> bool:
    """快速验证配置
    
    Args:
        config_dict: 配置字典
        
    Returns:
        bool: 是否有效
    """
    validator = BacktestConfigValidator()
    is_valid, _ = validator.validate_backtest_config(config_dict)
    return is_valid