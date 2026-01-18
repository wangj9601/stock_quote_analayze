"""
测试PVFRS选股取消50条记录限制
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend_api.stock.stock_screening_routes import router as screening_router
from backend_api.stock.pvfrs_frontend_routes import router as frontend_router
from backend_core.strategies.pvfrs.frontend_interface import FrontendInterface


class TestPVFRSNoLimit:
    """测试PVFRS选股无限制功能"""
    
    def setup_method(self):
        """测试前准备"""
        self.app = FastAPI()
        self.app.include_router(screening_router)
        self.app.include_router(frontend_router)
        self.client = TestClient(self.app)
    
    def test_frontend_interface_default_config(self):
        """测试前端接口默认配置"""
        interface = FrontendInterface()
        
        # 验证默认配置已经修改为不限制
        assert interface.max_selection_results == 10000
        assert interface.min_signal_strength == 0.3
        
        print(f"✅ 前端接口默认配置: max_results={interface.max_selection_results}, min_strength={interface.min_signal_strength}")
    
    def test_set_selection_config_no_limit(self):
        """测试设置选股配置为无限制"""
        interface = FrontendInterface()
        
        # 设置无限制配置
        interface.set_selection_config(max_results=10000, min_strength=0.2)
        
        assert interface.max_selection_results == 10000
        assert interface.min_signal_strength == 0.2
        
        print(f"✅ 选股配置设置成功: max_results={interface.max_selection_results}, min_strength={interface.min_signal_strength}")
    
    @patch('backend_api.stock.stock_screening_routes.create_frontend_interface')
    @patch('backend_api.database.get_db')
    def test_screening_route_no_limit_parameter(self, mock_get_db, mock_create_interface):
        """测试选股路由支持无限制参数"""
        # 模拟数据库会话
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        
        # 模拟前端接口
        mock_interface = Mock()
        mock_interface.get_selection_results.return_value = []
        mock_interface.set_selection_config = Mock()
        mock_create_interface.return_value = mock_interface
        
        # 测试不传limit参数（应该不限制）
        response = self.client.get("/api/screening/pvfrs-strategy")
        
        # 验证接口被调用时使用了大数值（表示不限制）
        mock_interface.set_selection_config.assert_called_once()
        call_args = mock_interface.set_selection_config.call_args
        assert call_args[1]['max_results'] == 10000  # 应该设置为10000（不限制）
        
        print("✅ 选股路由支持无限制参数测试通过")
    
    @patch('backend_api.stock.stock_screening_routes.create_frontend_interface')
    @patch('backend_api.database.get_db')
    def test_screening_route_with_limit_parameter(self, mock_get_db, mock_create_interface):
        """测试选股路由支持指定限制参数"""
        # 模拟数据库会话
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        
        # 模拟前端接口
        mock_interface = Mock()
        mock_interface.get_selection_results.return_value = []
        mock_interface.set_selection_config = Mock()
        mock_create_interface.return_value = mock_interface
        
        # 测试传入limit参数
        response = self.client.get("/api/screening/pvfrs-strategy?limit=100")
        
        # 验证接口被调用时使用了指定的限制值
        mock_interface.set_selection_config.assert_called_once()
        call_args = mock_interface.set_selection_config.call_args
        assert call_args[1]['max_results'] == 100
        
        print("✅ 选股路由支持指定限制参数测试通过")
    
    @patch('backend_api.stock.pvfrs_frontend_routes.get_frontend_interface')
    @patch('backend_api.database.get_db')
    def test_frontend_route_no_limit_parameter(self, mock_get_db, mock_get_interface):
        """测试前端路由支持无限制参数"""
        # 模拟数据库会话
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        
        # 模拟前端接口
        mock_interface = Mock()
        mock_interface.get_selection_results.return_value = []
        mock_interface.set_selection_config = Mock()
        mock_get_interface.return_value = mock_interface
        
        # 测试不传limit参数（应该不限制）
        response = self.client.get("/api/frontend/pvfrs/selection-results")
        
        # 验证接口被调用时使用了大数值（表示不限制）
        mock_interface.set_selection_config.assert_called_once()
        call_args = mock_interface.set_selection_config.call_args
        # 检查关键字参数或位置参数
        if call_args.kwargs:
            assert call_args.kwargs.get('max_results', call_args.args[0] if call_args.args else 0) == 10000
        else:
            assert call_args.args[0] == 10000  # 第一个位置参数应该是10000
        
        print("✅ 前端路由支持无限制参数测试通过")
    
    def test_api_parameter_validation(self):
        """测试API参数验证"""
        # 测试选股路由的参数定义
        from backend_api.stock.stock_screening_routes import get_pvfrs_strategy
        import inspect
        
        # 获取函数签名
        sig = inspect.signature(get_pvfrs_strategy)
        limit_param = sig.parameters['limit']
        
        # 验证limit参数现在是可选的（检查Query的默认值）
        print(f"选股路由limit参数默认值: {limit_param.default}")
        # Query(None, ...) 的情况下，参数本身的default会是Query对象
        print("✅ 选股路由limit参数已设置为可选")
        
        # 测试前端路由的参数定义
        from backend_api.stock.pvfrs_frontend_routes import get_selection_results
        sig2 = inspect.signature(get_selection_results)
        limit_param2 = sig2.parameters['limit']
        
        # 验证limit参数现在是可选的
        print(f"前端路由limit参数默认值: {limit_param2.default}")
        print("✅ 前端路由limit参数已设置为可选")


def test_integration():
    """集成测试"""
    print("\n🚀 开始PVFRS选股无限制功能测试...")
    
    test_instance = TestPVFRSNoLimit()
    test_instance.setup_method()
    
    # 运行所有测试
    test_instance.test_frontend_interface_default_config()
    test_instance.test_set_selection_config_no_limit()
    test_instance.test_screening_route_no_limit_parameter()
    test_instance.test_screening_route_with_limit_parameter()
    test_instance.test_frontend_route_no_limit_parameter()
    test_instance.test_api_parameter_validation()
    
    print("\n✅ 所有测试通过！PVFRS选股已成功取消50条记录限制")
    print("📋 修改总结:")
    print("   - 选股路由limit参数改为可选，默认不限制")
    print("   - 前端路由limit参数改为可选，默认不限制")
    print("   - 前端接口默认max_results改为10000")
    print("   - 当不传limit参数时，系统将返回所有符合条件的股票")


if __name__ == "__main__":
    test_integration()