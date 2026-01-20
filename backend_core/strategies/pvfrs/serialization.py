"""
PVFRS策略数据序列化和传输模块
确保前后端数据格式的一致性，实现JSON序列化和反序列化功能
"""

import json
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, date
from dataclasses import dataclass, asdict, is_dataclass
from decimal import Decimal
import math
import numpy as np

from .models import (
    MarketData, PVFRSIndicators, Signal, SignalType, 
    PVFRSException
)

# 配置日志
logger = logging.getLogger(__name__)


class PVFRSJSONEncoder(json.JSONEncoder):
    """PVFRS专用JSON编码器
    
    处理特殊数据类型的序列化：
    - datetime和date对象
    - Decimal对象
    - dataclass对象
    - 枚举类型
    """
    
    def default(self, obj):
        """自定义序列化逻辑"""
        try:
            # 处理datetime和date对象
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, date):
                return obj.isoformat()
            
            # 处理Decimal对象
            elif isinstance(obj, Decimal):
                return float(obj)
            
            # 处理dataclass对象
            elif is_dataclass(obj):
                return asdict(obj)
            
            # 处理枚举类型
            elif hasattr(obj, 'value'):
                return obj.value
            
            # 处理其他可序列化对象
            elif hasattr(obj, 'to_dict'):
                return obj.to_dict()
            
            # 处理numpy数据
            elif hasattr(obj, 'tolist'):
                return obj.tolist()
            
            # 默认处理
            return super().default(obj)
            
        except Exception as e:
            logger.warning(f"序列化对象失败: {type(obj).__name__}, 错误: {str(e)}")
            return str(obj)


class DataSerializer:
    """数据序列化器
    
    提供PVFRS策略相关数据的序列化和反序列化功能。
    """
    
    def __init__(self):
        """初始化序列化器"""
        self.encoder = PVFRSJSONEncoder()
        logger.info("PVFRS数据序列化器初始化完成")
    
    def serialize_to_json(self, data: Any, ensure_ascii: bool = False, indent: Optional[int] = None) -> str:
        """将数据序列化为JSON字符串
        
        Args:
            data: 要序列化的数据
            ensure_ascii: 是否确保ASCII编码
            indent: 缩进空格数，None表示紧凑格式
            
        Returns:
            str: JSON字符串
            
        Raises:
            PVFRSException: 序列化失败时抛出
        """
        try:
            # 预处理数据，处理 inf 和 nan
            sanitized_data = self._sanitize_data(data)
            
            json_str = json.dumps(
                sanitized_data, 
                cls=PVFRSJSONEncoder,
                ensure_ascii=ensure_ascii,
                indent=indent,
                separators=(',', ':') if indent is None else None
            )
            
            logger.debug(f"数据序列化成功，类型: {type(data).__name__}")
            return json_str
            
        except Exception as e:
            logger.error(f"数据序列化失败: {str(e)}")
            raise PVFRSException(f"数据序列化失败: {str(e)}")
    
    def deserialize_from_json(self, json_str: str) -> Any:
        """从JSON字符串反序列化数据
        
        Args:
            json_str: JSON字符串
            
        Returns:
            Any: 反序列化后的数据
            
        Raises:
            PVFRSException: 反序列化失败时抛出
        """
        try:
            data = json.loads(json_str)
            logger.debug("数据反序列化成功")
            return data
            
        except Exception as e:
            logger.error(f"数据反序列化失败: {str(e)}")
            raise PVFRSException(f"数据反序列化失败: {str(e)}")
    
    def _sanitize_data(self, data: Any) -> Any:
        """递归清理数据，处理 inf 和 nan"""
        try:
            if isinstance(data, (float, np.float32, np.float64)):
                if math.isinf(data):
                    return 999.0 if data > 0 else -999.0
                elif math.isnan(data):
                    return 0.0
                return float(data)
            elif isinstance(data, (int, np.integer)):
                return int(data)
            elif isinstance(data, dict):
                return {k: self._sanitize_data(v) for k, v in data.items()}
            elif isinstance(data, (list, tuple, np.ndarray)):
                if hasattr(data, 'tolist'):
                    return self._sanitize_data(data.tolist())
                return [self._sanitize_data(i) for i in data]
            elif is_dataclass(data):
                return self._sanitize_data(asdict(data))
            elif hasattr(data, 'to_dict') and not isinstance(data, type): # Avoid class objects
                return self._sanitize_data(data.to_dict())
            return data
        except Exception as e:
            logger.warning(f"清理数据失败: {str(e)}")
            return data
    
    def serialize_market_data(self, market_data: Union[MarketData, List[MarketData]]) -> str:
        """序列化市场数据
        
        Args:
            market_data: 市场数据或市场数据列表
            
        Returns:
            str: JSON字符串
        """
        try:
            if isinstance(market_data, list):
                data_list = [asdict(item) for item in market_data]
                return self.serialize_to_json(data_list)
            else:
                return self.serialize_to_json(asdict(market_data))
                
        except Exception as e:
            logger.error(f"市场数据序列化失败: {str(e)}")
            raise PVFRSException(f"市场数据序列化失败: {str(e)}")
    
    def deserialize_market_data(self, json_str: str) -> Union[MarketData, List[MarketData]]:
        """反序列化市场数据
        
        Args:
            json_str: JSON字符串
            
        Returns:
            Union[MarketData, List[MarketData]]: 市场数据或市场数据列表
        """
        try:
            data = self.deserialize_from_json(json_str)
            
            if isinstance(data, list):
                return [MarketData(**item) for item in data]
            else:
                return MarketData(**data)
                
        except Exception as e:
            logger.error(f"市场数据反序列化失败: {str(e)}")
            raise PVFRSException(f"市场数据反序列化失败: {str(e)}")
    
    def serialize_indicators(self, indicators: Union[PVFRSIndicators, List[PVFRSIndicators]]) -> str:
        """序列化PVFRS指标
        
        Args:
            indicators: PVFRS指标或指标列表
            
        Returns:
            str: JSON字符串
        """
        try:
            if isinstance(indicators, list):
                data_list = [asdict(item) for item in indicators]
                return self.serialize_to_json(data_list)
            else:
                return self.serialize_to_json(asdict(indicators))
                
        except Exception as e:
            logger.error(f"PVFRS指标序列化失败: {str(e)}")
            raise PVFRSException(f"PVFRS指标序列化失败: {str(e)}")
    
    def deserialize_indicators(self, json_str: str) -> Union[PVFRSIndicators, List[PVFRSIndicators]]:
        """反序列化PVFRS指标
        
        Args:
            json_str: JSON字符串
            
        Returns:
            Union[PVFRSIndicators, List[PVFRSIndicators]]: PVFRS指标或指标列表
        """
        try:
            data = self.deserialize_from_json(json_str)
            
            if isinstance(data, list):
                return [PVFRSIndicators(**item) for item in data]
            else:
                return PVFRSIndicators(**data)
                
        except Exception as e:
            logger.error(f"PVFRS指标反序列化失败: {str(e)}")
            raise PVFRSException(f"PVFRS指标反序列化失败: {str(e)}")
    
    def serialize_signals(self, signals: Union[Signal, List[Signal]]) -> str:
        """序列化信号数据
        
        Args:
            signals: 信号或信号列表
            
        Returns:
            str: JSON字符串
        """
        try:
            if isinstance(signals, list):
                data_list = []
                for signal in signals:
                    signal_dict = asdict(signal)
                    # 处理SignalType枚举
                    if 'signal_type' in signal_dict:
                        signal_dict['signal_type'] = signal_dict['signal_type'].value
                    data_list.append(signal_dict)
                return self.serialize_to_json(data_list)
            else:
                signal_dict = asdict(signals)
                # 处理SignalType枚举
                if 'signal_type' in signal_dict:
                    signal_dict['signal_type'] = signal_dict['signal_type'].value
                return self.serialize_to_json(signal_dict)
                
        except Exception as e:
            logger.error(f"信号数据序列化失败: {str(e)}")
            raise PVFRSException(f"信号数据序列化失败: {str(e)}")
    
    def deserialize_signals(self, json_str: str) -> Union[Signal, List[Signal]]:
        """反序列化信号数据
        
        Args:
            json_str: JSON字符串
            
        Returns:
            Union[Signal, List[Signal]]: 信号或信号列表
        """
        try:
            data = self.deserialize_from_json(json_str)
            
            if isinstance(data, list):
                signals = []
                for item in data:
                    # 处理SignalType枚举
                    if 'signal_type' in item:
                        item['signal_type'] = SignalType(item['signal_type'])
                    signals.append(Signal(**item))
                return signals
            else:
                # 处理SignalType枚举
                if 'signal_type' in data:
                    data['signal_type'] = SignalType(data['signal_type'])
                return Signal(**data)
                
        except Exception as e:
            logger.error(f"信号数据反序列化失败: {str(e)}")
            raise PVFRSException(f"信号数据反序列化失败: {str(e)}")


class APIResponseFormatter:
    """API响应格式化器
    
    确保前后端数据格式的一致性。
    """
    
    def __init__(self):
        """初始化响应格式化器"""
        self.serializer = DataSerializer()
        logger.info("API响应格式化器初始化完成")
    
    def format_success_response(self, data: Any, message: str = "操作成功", **kwargs) -> Dict:
        """格式化成功响应
        
        Args:
            data: 响应数据
            message: 响应消息
            **kwargs: 其他响应字段
            
        Returns:
            Dict: 格式化后的响应
        """
        response = {
            "success": True,
            "message": message,
            "data": data,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        
        return self._ensure_serializable(response)
    
    def format_error_response(self, error_message: str, error_code: Optional[str] = None, **kwargs) -> Dict:
        """格式化错误响应
        
        Args:
            error_message: 错误消息
            error_code: 错误代码
            **kwargs: 其他响应字段
            
        Returns:
            Dict: 格式化后的响应
        """
        response = {
            "success": False,
            "error": error_message,
            "error_code": error_code,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        
        return self._ensure_serializable(response)
    
    def format_selection_results(self, selection_results: List[Dict], **kwargs) -> Dict:
        """格式化选股结果响应
        
        Args:
            selection_results: 选股结果列表
            **kwargs: 其他响应字段
            
        Returns:
            Dict: 格式化后的响应
        """
        response = {
            "success": True,
            "data": selection_results,
            "total": len(selection_results),
            "strategy_name": "PVFRS量价频三维共振演化策略",
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        
        return self._ensure_serializable(response)
    
    def format_stock_detail(self, stock_detail: Dict, **kwargs) -> Dict:
        """格式化股票详情响应
        
        Args:
            stock_detail: 股票详情数据
            **kwargs: 其他响应字段
            
        Returns:
            Dict: 格式化后的响应
        """
        response = {
            "success": True,
            "data": stock_detail,
            "strategy_name": "PVFRS量价频三维共振演化策略",
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        
        return self._ensure_serializable(response)
    
    def format_backtest_report(self, backtest_report: Dict, **kwargs) -> Dict:
        """格式化回测报告响应
        
        Args:
            backtest_report: 回测报告数据
            **kwargs: 其他响应字段
            
        Returns:
            Dict: 格式化后的响应
        """
        response = {
            "success": True,
            "data": backtest_report,
            "report_type": "PVFRS回测报告",
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        
        return self._ensure_serializable(response)
    
    def format_task_progress(self, progress_info: Dict, **kwargs) -> Dict:
        """格式化任务进度响应
        
        Args:
            progress_info: 任务进度信息
            **kwargs: 其他响应字段
            
        Returns:
            Dict: 格式化后的响应
        """
        response = {
            "success": True,
            "data": progress_info,
            "task_type": "PVFRS回测任务",
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        
        return self._ensure_serializable(response)
    
    def _ensure_serializable(self, data: Any) -> Any:
        """确保数据可序列化
        
        Args:
            data: 要检查的数据
            
        Returns:
            Any: 可序列化的数据
        """
        try:
            # 尝试序列化然后反序列化，确保数据格式正确
            json_str = self.serializer.serialize_to_json(data)
            return self.serializer.deserialize_from_json(json_str)
            
        except Exception as e:
            logger.warning(f"数据序列化检查失败: {str(e)}")
            # 如果序列化失败，返回字符串表示
            return str(data)


class DataValidator:
    """数据验证器
    
    验证前后端传输数据的完整性和正确性。
    """
    
    def __init__(self):
        """初始化数据验证器"""
        logger.info("数据验证器初始化完成")
    
    def validate_market_data(self, data: Dict) -> bool:
        """验证市场数据格式
        
        Args:
            data: 市场数据字典
            
        Returns:
            bool: 验证是否通过
        """
        try:
            required_fields = ['symbol', 'date', 'open', 'high', 'low', 'close', 'volume']
            
            # 检查必需字段
            for field in required_fields:
                if field not in data:
                    logger.error(f"市场数据缺少必需字段: {field}")
                    return False
            
            # 检查数值字段
            numeric_fields = ['open', 'high', 'low', 'close', 'volume']
            for field in numeric_fields:
                if not isinstance(data[field], (int, float)) or data[field] < 0:
                    logger.error(f"市场数据字段 {field} 格式错误")
                    return False
            
            # 检查价格逻辑
            if not (data['low'] <= data['open'] <= data['high'] and 
                   data['low'] <= data['close'] <= data['high']):
                logger.error("市场数据价格逻辑错误")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"市场数据验证失败: {str(e)}")
            return False
    
    def validate_indicators(self, data: Dict) -> bool:
        """验证PVFRS指标格式
        
        Args:
            data: PVFRS指标字典
            
        Returns:
            bool: 验证是否通过
        """
        try:
            required_fields = [
                'macro_displacement', 'instant_deviation', 'avg_price_20d',
                'rising_days', 'falling_days', 'frequency_advantage',
                'avg_volume_20d', 'current_volume', 'efficiency_ratio',
                'amplitude_ratio', 'resonance_strength'
            ]
            
            # 检查必需字段
            for field in required_fields:
                if field not in data:
                    logger.error(f"PVFRS指标缺少必需字段: {field}")
                    return False
            
            # 检查数值字段范围
            if not (0.0 <= data['resonance_strength'] <= 1.0):
                logger.error("共振强度必须在0-1之间")
                return False
            
            # 检查整数字段
            if not (isinstance(data['rising_days'], int) and data['rising_days'] >= 0):
                logger.error("上涨天数必须是非负整数")
                return False
            
            if not (isinstance(data['falling_days'], int) and data['falling_days'] >= 0):
                logger.error("下跌天数必须是非负整数")
                return False
            
            # 检查布尔字段
            if not isinstance(data['frequency_advantage'], bool):
                logger.error("频率优势必须是布尔值")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"PVFRS指标验证失败: {str(e)}")
            return False
    
    def validate_signal(self, data: Dict) -> bool:
        """验证信号数据格式
        
        Args:
            data: 信号数据字典
            
        Returns:
            bool: 验证是否通过
        """
        try:
            required_fields = ['symbol', 'date', 'signal_type', 'price', 'strength', 'reason']
            
            # 检查必需字段
            for field in required_fields:
                if field not in data:
                    logger.error(f"信号数据缺少必需字段: {field}")
                    return False
            
            # 检查信号类型
            valid_signal_types = ['BUY', 'SELL', 'HOLD']
            if data['signal_type'] not in valid_signal_types:
                logger.error(f"信号类型无效: {data['signal_type']}")
                return False
            
            # 检查信号强度
            if not (0.0 <= data['strength'] <= 1.0):
                logger.error("信号强度必须在0-1之间")
                return False
            
            # 检查价格
            if not (isinstance(data['price'], (int, float)) and data['price'] > 0):
                logger.error("价格必须是正数")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"信号数据验证失败: {str(e)}")
            return False


# 全局实例
_serializer = None
_formatter = None
_validator = None


def get_serializer() -> DataSerializer:
    """获取数据序列化器实例"""
    global _serializer
    if _serializer is None:
        _serializer = DataSerializer()
    return _serializer


def get_formatter() -> APIResponseFormatter:
    """获取API响应格式化器实例"""
    global _formatter
    if _formatter is None:
        _formatter = APIResponseFormatter()
    return _formatter


def get_validator() -> DataValidator:
    """获取数据验证器实例"""
    global _validator
    if _validator is None:
        _validator = DataValidator()
    return _validator


# 便捷函数
def serialize_to_json(data: Any, **kwargs) -> str:
    """序列化数据为JSON字符串"""
    return get_serializer().serialize_to_json(data, **kwargs)


def deserialize_from_json(json_str: str) -> Any:
    """从JSON字符串反序列化数据"""
    return get_serializer().deserialize_from_json(json_str)


def format_api_response(data: Any, success: bool = True, message: str = "操作成功", **kwargs) -> Dict:
    """格式化API响应"""
    formatter = get_formatter()
    if success:
        return formatter.format_success_response(data, message, **kwargs)
    else:
        return formatter.format_error_response(message, **kwargs)


def validate_data(data: Dict, data_type: str) -> bool:
    """验证数据格式
    
    Args:
        data: 要验证的数据
        data_type: 数据类型，可选值：market_data, indicators, signal
        
    Returns:
        bool: 验证是否通过
    """
    validator = get_validator()
    
    if data_type == "market_data":
        return validator.validate_market_data(data)
    elif data_type == "indicators":
        return validator.validate_indicators(data)
    elif data_type == "signal":
        return validator.validate_signal(data)
    else:
        logger.error(f"未知的数据类型: {data_type}")
        return False