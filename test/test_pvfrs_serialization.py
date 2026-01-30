"""
PVFRS策略数据序列化和传输功能测试
"""

import pytest
import json
from datetime import datetime, date
from decimal import Decimal

from backend_core.strategies.pvfrs.serialization import (
    DataSerializer, APIResponseFormatter, DataValidator,
    get_serializer, get_formatter, get_validator,
    serialize_to_json, deserialize_from_json, format_api_response, validate_data
)
from backend_core.strategies.pvfrs.models import (
    MarketData, PVFRSIndicators, Signal, SignalType
)


class TestDataSerializer:
    """测试数据序列化器"""
    
    def setup_method(self):
        """测试前设置"""
        self.serializer = DataSerializer()
    
    def test_serialize_basic_data(self):
        """测试基本数据序列化"""
        # 测试字典
        data = {"name": "test", "value": 123, "active": True}
        json_str = self.serializer.serialize_to_json(data)
        assert isinstance(json_str, str)
        
        # 反序列化验证
        deserialized = self.serializer.deserialize_from_json(json_str)
        assert deserialized == data
    
    def test_serialize_datetime(self):
        """测试日期时间序列化"""
        now = datetime.now()
        today = date.today()
        
        data = {
            "datetime": now,
            "date": today,
            "timestamp": now.isoformat()
        }
        
        json_str = self.serializer.serialize_to_json(data)
        deserialized = self.serializer.deserialize_from_json(json_str)
        
        # 验证日期时间被转换为ISO格式字符串
        assert deserialized["datetime"] == now.isoformat()
        assert deserialized["date"] == today.isoformat()
        assert deserialized["timestamp"] == now.isoformat()
    
    def test_serialize_decimal(self):
        """测试Decimal序列化"""
        data = {
            "price": Decimal("123.45"),
            "volume": Decimal("1000000")
        }
        
        json_str = self.serializer.serialize_to_json(data)
        deserialized = self.serializer.deserialize_from_json(json_str)
        
        # 验证Decimal被转换为float
        assert deserialized["price"] == 123.45
        assert deserialized["volume"] == 1000000.0
    
    def test_serialize_market_data(self):
        """测试市场数据序列化"""
        market_data = MarketData(
            symbol="000001",
            date="2024-01-15",
            open=10.0,
            high=10.5,
            low=9.8,
            close=10.2,
            volume=1000000,
            amount=10200000.0
        )
        
        json_str = self.serializer.serialize_market_data(market_data)
        assert isinstance(json_str, str)
        
        # 反序列化验证
        deserialized = self.serializer.deserialize_market_data(json_str)
        assert isinstance(deserialized, MarketData)
        assert deserialized.symbol == "000001"
        assert deserialized.close == 10.2
    
    def test_serialize_market_data_list(self):
        """测试市场数据列表序列化"""
        market_data_list = [
            MarketData(
                symbol="000001",
                date="2024-01-15",
                open=10.0,
                high=10.5,
                low=9.8,
                close=10.2,
                volume=1000000,
                amount=10200000.0
            ),
            MarketData(
                symbol="000002",
                date="2024-01-15",
                open=20.0,
                high=20.5,
                low=19.8,
                close=20.2,
                volume=2000000,
                amount=40400000.0
            )
        ]
        
        json_str = self.serializer.serialize_market_data(market_data_list)
        assert isinstance(json_str, str)
        
        # 反序列化验证
        deserialized = self.serializer.deserialize_market_data(json_str)
        assert isinstance(deserialized, list)
        assert len(deserialized) == 2
        assert all(isinstance(item, MarketData) for item in deserialized)
    
    def test_serialize_indicators(self):
        """测试PVFRS指标序列化"""
        indicators = PVFRSIndicators(
            macro_displacement=0.5,
            instant_deviation=0.3,
            avg_price_20d=10.0,
            rising_days=12,
            falling_days=8,
            frequency_advantage=True,
            avg_volume_20d=1000000.0,
            current_volume=1500000.0,
            efficiency_ratio=1.5,
            amplitude_ratio=0.05,
            resonance_strength=0.8
        )
        
        json_str = self.serializer.serialize_indicators(indicators)
        assert isinstance(json_str, str)
        
        # 反序列化验证
        deserialized = self.serializer.deserialize_indicators(json_str)
        assert isinstance(deserialized, PVFRSIndicators)
        assert deserialized.resonance_strength == 0.8
        assert deserialized.frequency_advantage == True  # 反序列化可能为 1/0
    
    def test_serialize_signals(self):
        """测试信号序列化"""
        signal = Signal(
            symbol="000001",
            date="2024-01-15",
            signal_type=SignalType.BUY,
            price=10.2,
            strength=0.8,
            reason="三维共振条件满足",
            indicators=PVFRSIndicators(
                macro_displacement=0.5,
                instant_deviation=0.3,
                avg_price_20d=10.0,
                rising_days=12,
                falling_days=8,
                frequency_advantage=True,
                avg_volume_20d=1000000.0,
                current_volume=1500000.0,
                efficiency_ratio=1.5,
                amplitude_ratio=0.05,
                resonance_strength=0.8
            ),
            conditions_met={"price_dimension": True, "frequency_dimension": True}
        )
        
        json_str = self.serializer.serialize_signals(signal)
        assert isinstance(json_str, str)
        
        # 反序列化验证
        deserialized = self.serializer.deserialize_signals(json_str)
        assert isinstance(deserialized, Signal)
        assert deserialized.signal_type == SignalType.BUY
        assert deserialized.strength == 0.8


class TestAPIResponseFormatter:
    """测试API响应格式化器"""
    
    def setup_method(self):
        """测试前设置"""
        self.formatter = APIResponseFormatter()
    
    def test_format_success_response(self):
        """测试成功响应格式化"""
        data = {"result": "success", "count": 10}
        response = self.formatter.format_success_response(data, "操作成功")
        
        assert response["success"] is True
        assert response["message"] == "操作成功"
        assert response["data"] == data
        assert "timestamp" in response
    
    def test_format_error_response(self):
        """测试错误响应格式化"""
        response = self.formatter.format_error_response("操作失败", "E001")
        
        assert response["success"] is False
        assert response["error"] == "操作失败"
        assert response["error_code"] == "E001"
        assert "timestamp" in response
    
    def test_format_selection_results(self):
        """测试选股结果格式化"""
        selection_results = [
            {"symbol": "000001", "strength": 0.8},
            {"symbol": "000002", "strength": 0.7}
        ]
        
        response = self.formatter.format_selection_results(selection_results)
        
        assert response["success"] is True
        assert response["data"] == selection_results
        assert response["total"] == 2
        assert response["strategy_name"] == "PVFARS量价频幅度共振策略"
    
    def test_format_stock_detail(self):
        """测试股票详情格式化"""
        stock_detail = {
            "symbol": "000001",
            "name": "平安银行",
            "analysis": {"resonance_strength": 0.8}
        }
        
        response = self.formatter.format_stock_detail(stock_detail)
        
        assert response["success"] is True
        assert response["data"] == stock_detail
        assert response["strategy_name"] == "PVFARS量价频幅度共振策略"
    
    def test_format_backtest_report(self):
        """测试回测报告格式化"""
        backtest_report = {
            "report_id": "report_001",
            "total_return": 0.15,
            "win_rate": 0.65
        }
        
        response = self.formatter.format_backtest_report(backtest_report)
        
        assert response["success"] is True
        assert response["data"] == backtest_report
        assert response["report_type"] == "PVFARS回测报告"
    
    def test_format_task_progress(self):
        """测试任务进度格式化"""
        progress_info = {
            "task_id": "task_001",
            "progress": 50,
            "status": "running"
        }
        
        response = self.formatter.format_task_progress(progress_info)
        
        assert response["success"] is True
        assert response["data"] == progress_info
        assert response["task_type"] == "PVFRS回测任务"


class TestDataValidator:
    """测试数据验证器"""
    
    def setup_method(self):
        """测试前设置"""
        self.validator = DataValidator()
    
    def test_validate_market_data_valid(self):
        """测试有效市场数据验证"""
        valid_data = {
            "symbol": "000001",
            "date": "2024-01-15",
            "open": 10.0,
            "high": 10.5,
            "low": 9.8,
            "close": 10.2,
            "volume": 1000000
        }
        
        assert self.validator.validate_market_data(valid_data) is True
    
    def test_validate_market_data_invalid(self):
        """测试无效市场数据验证"""
        # 缺少必需字段
        invalid_data1 = {
            "symbol": "000001",
            "date": "2024-01-15",
            "open": 10.0
            # 缺少其他字段
        }
        assert self.validator.validate_market_data(invalid_data1) is False
        
        # 价格逻辑错误
        invalid_data2 = {
            "symbol": "000001",
            "date": "2024-01-15",
            "open": 10.0,
            "high": 9.5,  # 最高价低于开盘价
            "low": 9.8,
            "close": 10.2,
            "volume": 1000000
        }
        assert self.validator.validate_market_data(invalid_data2) is False
        
        # 负数价格
        invalid_data3 = {
            "symbol": "000001",
            "date": "2024-01-15",
            "open": -10.0,  # 负数价格
            "high": 10.5,
            "low": 9.8,
            "close": 10.2,
            "volume": 1000000
        }
        assert self.validator.validate_market_data(invalid_data3) is False
    
    def test_validate_indicators_valid(self):
        """测试有效PVFRS指标验证"""
        valid_data = {
            "macro_displacement": 0.5,
            "instant_deviation": 0.3,
            "avg_price_20d": 10.0,
            "rising_days": 12,
            "falling_days": 8,
            "frequency_advantage": True,
            "avg_volume_20d": 1000000.0,
            "current_volume": 1500000.0,
            "efficiency_ratio": 1.5,
            "amplitude_ratio": 0.05,
            "resonance_strength": 0.8
        }
        
        assert self.validator.validate_indicators(valid_data) is True
    
    def test_validate_indicators_invalid(self):
        """测试无效PVFRS指标验证"""
        # 共振强度超出范围
        invalid_data1 = {
            "macro_displacement": 0.5,
            "instant_deviation": 0.3,
            "avg_price_20d": 10.0,
            "rising_days": 12,
            "falling_days": 8,
            "frequency_advantage": True,
            "avg_volume_20d": 1000000.0,
            "current_volume": 1500000.0,
            "efficiency_ratio": 1.5,
            "amplitude_ratio": 0.05,
            "resonance_strength": 1.5  # 超出0-1范围
        }
        assert self.validator.validate_indicators(invalid_data1) is False
        
        # 天数为负数
        invalid_data2 = {
            "macro_displacement": 0.5,
            "instant_deviation": 0.3,
            "avg_price_20d": 10.0,
            "rising_days": -5,  # 负数天数
            "falling_days": 8,
            "frequency_advantage": True,
            "avg_volume_20d": 1000000.0,
            "current_volume": 1500000.0,
            "efficiency_ratio": 1.5,
            "amplitude_ratio": 0.05,
            "resonance_strength": 0.8
        }
        assert self.validator.validate_indicators(invalid_data2) is False
    
    def test_validate_signal_valid(self):
        """测试有效信号数据验证"""
        valid_data = {
            "symbol": "000001",
            "date": "2024-01-15",
            "signal_type": "BUY",
            "price": 10.2,
            "strength": 0.8,
            "reason": "三维共振条件满足"
        }
        
        assert self.validator.validate_signal(valid_data) is True
    
    def test_validate_signal_invalid(self):
        """测试无效信号数据验证"""
        # 无效信号类型
        invalid_data1 = {
            "symbol": "000001",
            "date": "2024-01-15",
            "signal_type": "INVALID",  # 无效信号类型
            "price": 10.2,
            "strength": 0.8,
            "reason": "三维共振条件满足"
        }
        assert self.validator.validate_signal(invalid_data1) is False
        
        # 信号强度超出范围
        invalid_data2 = {
            "symbol": "000001",
            "date": "2024-01-15",
            "signal_type": "BUY",
            "price": 10.2,
            "strength": 1.5,  # 超出0-1范围
            "reason": "三维共振条件满足"
        }
        assert self.validator.validate_signal(invalid_data2) is False
        
        # 负数价格
        invalid_data3 = {
            "symbol": "000001",
            "date": "2024-01-15",
            "signal_type": "BUY",
            "price": -10.2,  # 负数价格
            "strength": 0.8,
            "reason": "三维共振条件满足"
        }
        assert self.validator.validate_signal(invalid_data3) is False


class TestConvenienceFunctions:
    """测试便捷函数"""
    
    def test_serialize_to_json(self):
        """测试JSON序列化便捷函数"""
        data = {"test": "value", "number": 123}
        json_str = serialize_to_json(data)
        
        assert isinstance(json_str, str)
        assert "test" in json_str
        assert "123" in json_str
    
    def test_deserialize_from_json(self):
        """测试JSON反序列化便捷函数"""
        json_str = '{"test": "value", "number": 123}'
        data = deserialize_from_json(json_str)
        
        assert isinstance(data, dict)
        assert data["test"] == "value"
        assert data["number"] == 123
    
    def test_format_api_response_success(self):
        """测试成功API响应格式化便捷函数"""
        data = {"result": "success"}
        response = format_api_response(data, success=True, message="操作成功")
        
        assert response["success"] is True
        assert response["message"] == "操作成功"
        assert response["data"] == data
    
    def test_format_api_response_error(self):
        """测试错误API响应格式化便捷函数"""
        response = format_api_response(None, success=False, message="操作失败")
        
        assert response["success"] is False
        assert response["error"] == "操作失败"
    
    def test_validate_data(self):
        """测试数据验证便捷函数"""
        # 测试市场数据验证
        market_data = {
            "symbol": "000001",
            "date": "2024-01-15",
            "open": 10.0,
            "high": 10.5,
            "low": 9.8,
            "close": 10.2,
            "volume": 1000000
        }
        assert validate_data(market_data, "market_data") is True
        
        # 测试无效数据类型
        assert validate_data({}, "invalid_type") is False


class TestGlobalInstances:
    """测试全局实例"""
    
    def test_get_serializer(self):
        """测试获取序列化器实例"""
        serializer1 = get_serializer()
        serializer2 = get_serializer()
        
        assert isinstance(serializer1, DataSerializer)
        assert serializer1 is serializer2  # 应该是同一个实例
    
    def test_get_formatter(self):
        """测试获取格式化器实例"""
        formatter1 = get_formatter()
        formatter2 = get_formatter()
        
        assert isinstance(formatter1, APIResponseFormatter)
        assert formatter1 is formatter2  # 应该是同一个实例
    
    def test_get_validator(self):
        """测试获取验证器实例"""
        validator1 = get_validator()
        validator2 = get_validator()
        
        assert isinstance(validator1, DataValidator)
        assert validator1 is validator2  # 应该是同一个实例


if __name__ == "__main__":
    pytest.main([__file__])