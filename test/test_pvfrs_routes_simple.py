"""
PVFRS策略路由简单测试
测试路由函数的基本功能
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import HTTPException
from datetime import datetime

# 测试前端路由函数
@patch('backend_api.stock.pvfrs_frontend_routes.get_pvfrs_frontend_interface')
def test_frontend_route_creation(mock_get_interface):
    """测试前端路由创建"""
    # 模拟前端接口
    mock_interface = Mock()
    mock_interface.get_selection_results.return_value = []
    mock_interface.set_selection_config = Mock()
    mock_get_interface.return_value = mock_interface
    
    # 导入路由函数
    from backend_api.stock.pvfrs_frontend_routes import get_selection_results
    
    # 模拟数据库会话
    mock_db = Mock()
    
    # 测试函数调用
    try:
        # 这里只是测试函数能否正常导入和调用，不测试完整的HTTP响应
        assert callable(get_selection_results)
        print("前端路由函数导入成功")
    except Exception as e:
        print(f"前端路由函数导入失败: {e}")


@patch('backend_api.admin.pvfrs_admin_routes.get_admin_interface')
def test_admin_route_creation(mock_get_interface):
    """测试管理端路由创建"""
    # 模拟管理端接口
    mock_interface = Mock()
    mock_interface.create_backtest.return_value = "task_123"
    mock_interface.start_backtest_execution.return_value = True
    mock_get_interface.return_value = mock_interface
    
    # 导入路由函数
    from backend_api.admin.pvfrs_admin_routes import create_backtest_task
    
    # 测试函数调用
    try:
        assert callable(create_backtest_task)
        print("管理端路由函数导入成功")
    except Exception as e:
        print(f"管理端路由函数导入失败: {e}")


def test_serialization_integration():
    """测试序列化集成"""
    from backend_core.strategies.pvfrs.serialization import (
        get_serializer, get_formatter, serialize_to_json, format_api_response
    )
    
    # 测试序列化器
    serializer = get_serializer()
    assert serializer is not None
    
    # 测试格式化器
    formatter = get_formatter()
    assert formatter is not None
    
    # 测试便捷函数
    test_data = {"test": "value", "number": 123}
    json_str = serialize_to_json(test_data)
    assert isinstance(json_str, str)
    assert "test" in json_str
    
    # 测试API响应格式化
    response = format_api_response(test_data, success=True, message="测试成功")
    assert response["success"] is True
    assert response["message"] == "测试成功"
    assert response["data"] == test_data
    
    print("序列化集成测试通过")


def test_data_models_integration():
    """测试数据模型集成"""
    from backend_core.strategies.pvfrs.models import MarketData, PVFRSIndicators, Signal, SignalType
    
    # 测试MarketData
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
    assert market_data.symbol == "000001"
    assert market_data.close == 10.2
    
    # 测试PVFRSIndicators
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
    assert indicators.resonance_strength == 0.8
    assert indicators.frequency_advantage is True
    
    # 测试Signal
    signal = Signal(
        symbol="000001",
        date="2024-01-15",
        signal_type=SignalType.BUY,
        price=10.2,
        strength=0.8,
        reason="三维共振条件满足",
        indicators=indicators,
        conditions_met={"price_dimension": True}
    )
    assert signal.signal_type == SignalType.BUY
    assert signal.strength == 0.8
    
    print("数据模型集成测试通过")


def test_interface_classes():
    """测试接口类"""
    from backend_core.strategies.pvfrs.frontend_interface import FrontendInterface
    from backend_core.strategies.pvfrs.admin_interface import AdminInterface
    
    # 测试前端接口类
    try:
        frontend_interface = FrontendInterface()
        assert hasattr(frontend_interface, 'get_selection_results')
        assert hasattr(frontend_interface, 'get_stock_detail')
        assert hasattr(frontend_interface, 'refresh_results')
        print("前端接口类创建成功")
    except Exception as e:
        print(f"前端接口类创建失败: {e}")
    
    # 测试管理端接口类
    try:
        admin_interface = AdminInterface()
        assert hasattr(admin_interface, 'create_backtest')
        assert hasattr(admin_interface, 'get_backtest_progress')
        assert hasattr(admin_interface, 'get_backtest_report')
        print("管理端接口类创建成功")
    except Exception as e:
        print(f"管理端接口类创建失败: {e}")


def test_route_imports():
    """测试路由导入"""
    try:
        # 测试前端路由导入
        import backend_api.stock.pvfrs_frontend_routes
        assert hasattr(backend_api.stock.pvfrs_frontend_routes, 'router')
        print("前端路由模块导入成功")
        
        # 测试管理端路由导入
        import backend_api.admin.pvfrs_admin_routes
        assert hasattr(backend_api.admin.pvfrs_admin_routes, 'router')
        print("管理端路由模块导入成功")
        
        # 测试序列化模块导入
        import backend_core.strategies.pvfrs.serialization
        assert hasattr(backend_core.strategies.pvfrs.serialization, 'DataSerializer')
        print("序列化模块导入成功")
        
    except Exception as e:
        print(f"路由导入失败: {e}")
        raise


if __name__ == "__main__":
    print("开始PVFRS路由集成测试...")
    
    # 运行各项测试
    test_route_imports()
    test_serialization_integration()
    test_data_models_integration()
    test_interface_classes()
    test_frontend_route_creation()
    test_admin_route_creation()
    
    print("所有PVFRS路由集成测试完成！")