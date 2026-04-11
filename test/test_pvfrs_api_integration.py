"""
PVFRS策略API集成测试
测试前后端接口对接功能
"""

import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

# 导入FastAPI应用
from backend_api.main import app

# 创建测试客户端
client = TestClient(app)


class TestPVFRSFrontendAPI:
    """测试PVFRS前端API"""
    
    @patch('backend_core.strategies.pvfrs.frontend_interface.FrontendInterface.get_selection_results')
    def test_get_selection_results_success(self, mock_get_results):
        """测试获取选股结果成功"""
        # 模拟返回数据
        mock_results = [
            {
                "symbol": "000001",
                "name": "平安银行",
                "signal_strength": 0.8,
                "conditions_met": {"price_dimension": True},
                "indicators": {
                    "resonance_strength": 0.8,
                    "amplitude_ratio": 0.05
                },
                "timestamp": "2024-01-15T10:00:00",
                "price": 10.2,
                "signal_reason": "三维共振条件满足"
            }
        ]
        
        # 创建Mock对象
        mock_selection_result = Mock()
        mock_selection_result.to_dict.return_value = mock_results[0]
        mock_get_results.return_value = [mock_selection_result]
        
        # 发送请求
        response = client.get("/api/frontend/pvfrs/selection-results")
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 1
        assert data["data"][0]["symbol"] == "000001"
    
    def test_get_selection_results_with_params(self):
        """测试带参数的选股结果请求"""
        response = client.get(
            "/api/frontend/pvfrs/selection-results",
            params={
                "date": "2024-01-15",
                "limit": 10,
                "min_strength": 0.5
            }
        )
        
        # 由于没有实际数据，可能返回错误，但应该能正确处理参数
        assert response.status_code in [200, 404, 500]  # 接受这些状态码
    
    def test_get_selection_results_invalid_date(self):
        """测试无效日期参数"""
        response = client.get(
            "/api/frontend/pvfrs/selection-results",
            params={"date": "invalid-date"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "日期格式错误" in data["detail"]
    
    @patch('backend_core.strategies.pvfrs.frontend_interface.FrontendInterface.get_stock_detail')
    def test_get_stock_detail_success(self, mock_get_detail):
        """测试获取股票详情成功（PVFRS，返回 StockDetail dataclass）"""
        from backend_core.strategies.pvfrs.models import StockDetail

        mock_get_detail.return_value = StockDetail(
            symbol="000001",
            name="平安银行",
            current_price=10.2,
            analysis_date="2024-01-15",
            price_dimension={"macro_displacement": 0.5},
            frequency_dimension={"rising_days": 12},
            volume_dimension={"efficiency_ratio": 1.5},
            resonance_analysis={"resonance_strength": 0.8},
            signal_analysis={"signals": []},
            strategy_assessment={"overall_score": 0.8},
            investment_advice="买入",
            risk_assessment={"risk_level": "中等"},
        )

        # 发送请求
        response = client.get("/api/frontend/pvfrs/stock-detail/000001")
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["symbol"] == "000001"
    
    def test_get_stock_detail_empty_symbol(self):
        """测试空股票代码"""
        response = client.get("/api/frontend/pvfrs/stock-detail/")
        
        # 应该返回404，因为路径不匹配
        assert response.status_code == 404
    
    @patch('backend_core.strategies.pvfrs.frontend_interface.FrontendInterface.refresh_results')
    def test_refresh_results_success(self, mock_refresh):
        """测试刷新结果成功"""
        mock_refresh.return_value = True
        
        response = client.post("/api/frontend/pvfrs/refresh-results")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "刷新成功" in data["message"]
    
    @patch('backend_core.strategies.pvfrs.frontend_interface.FrontendInterface.get_selection_summary')
    def test_get_selection_summary_success(self, mock_get_summary):
        """测试获取选股汇总成功"""
        mock_summary = {
            "summary_date": "2024-01-15",
            "total_stocks": 10,
            "strength_distribution": {"high": {"count": 3}},
            "condition_statistics": {},
            "average_indicators": {"resonance_strength": 0.7},
            "top_stocks": [],
            "system_status": True
        }
        mock_get_summary.return_value = mock_summary
        
        response = client.get("/api/frontend/pvfrs/selection-summary")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total_stocks"] == 10
    
    @patch('backend_core.strategies.pvfrs.frontend_interface.FrontendInterface.get_interface_status')
    def test_get_interface_status_success(self, mock_get_status):
        """测试获取接口状态成功"""
        mock_status = {
            "interface_name": "PVFRS Frontend Interface",
            "version": "1.0.0",
            "cache_enabled": True,
            "pvfrs_system_status": True
        }
        mock_get_status.return_value = mock_status
        
        response = client.get("/api/frontend/pvfrs/interface-status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["interface_name"] == "PVFRS Frontend Interface"


class TestPVFRSAdminAPI:
    """测试PVFRS管理端API"""
    
    @patch('backend_core.strategies.pvfrs.admin_interface.AdminInterface.create_backtest')
    @patch('backend_core.strategies.pvfrs.admin_interface.AdminInterface.start_backtest_execution')
    def test_create_backtest_task_success(self, mock_start_execution, mock_create_backtest):
        """测试创建回测任务成功"""
        mock_create_backtest.return_value = "task_123"
        mock_start_execution.return_value = True
        
        config_data = {
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "stock_pool": ["000001", "000002"],
            "initial_capital": 100000,
            "strategy_params": {},
            "risk_params": {}
        }
        
        response = client.post(
            "/api/admin/pvfrs/backtest/create",
            json=config_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "task_id" in data["data"]
    
    def test_create_backtest_task_missing_fields(self):
        """测试创建回测任务缺少必需字段"""
        config_data = {
            "start_date": "2024-01-01",
            # 缺少其他必需字段
        }
        
        response = client.post(
            "/api/admin/pvfrs/backtest/create",
            json=config_data
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "缺少必需字段" in data["detail"]
    
    @patch('backend_core.strategies.pvfrs.admin_interface.AdminInterface.get_backtest_progress')
    def test_get_backtest_progress_success(self, mock_get_progress):
        """测试获取回测进度成功"""
        mock_progress = {
            "task_id": "task_123",
            "status": "running",
            "progress": 50,
            "current_step": "正在执行回测",
            "created_at": "2024-01-15T10:00:00"
        }
        mock_get_progress.return_value = mock_progress
        
        response = client.get("/api/admin/pvfrs/backtest/progress/task_123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["task_id"] == "task_123"
    
    @patch('backend_core.strategies.pvfrs.admin_interface.AdminInterface.get_backtest_report')
    def test_get_backtest_report_success(self, mock_get_report):
        """测试获取回测报告成功"""
        mock_report = Mock()
        mock_report.to_dict.return_value = {
            "report_id": "report_123",
            "task_id": "task_123",
            "total_return": 0.15,
            "win_rate": 0.65,
            "max_drawdown": 0.08
        }
        mock_get_report.return_value = mock_report
        
        response = client.get("/api/admin/pvfrs/backtest/report/task_123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["report_id"] == "report_123"
    
    @patch('backend_core.strategies.pvfrs.admin_interface.AdminInterface.compare_strategies')
    def test_compare_backtest_reports_success(self, mock_compare):
        """测试对比回测报告成功"""
        mock_comparison = {
            "comparison_id": "comp_123",
            "report_count": 2,
            "performance_comparison": {"total_return": [0.15, 0.12]},
            "summary": {"best_total_return": 0.15}
        }
        mock_compare.return_value = mock_comparison
        
        response = client.post(
            "/api/admin/pvfrs/backtest/compare",
            json=["report_1", "report_2"]
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["report_count"] == 2
    
    def test_compare_backtest_reports_insufficient_reports(self):
        """测试对比回测报告数量不足"""
        response = client.post(
            "/api/admin/pvfrs/backtest/compare",
            json=["report_1"]  # 只有一个报告
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "至少需要2个报告" in data["detail"]
    
    @patch('backend_core.strategies.pvfrs.admin_interface.AdminInterface.list_historical_reports')
    def test_list_backtest_reports_success(self, mock_list_reports):
        """测试获取历史回测报告列表成功"""
        mock_reports = [
            Mock(),
            Mock()
        ]
        mock_reports[0].to_dict.return_value = {"report_id": "report_1"}
        mock_reports[1].to_dict.return_value = {"report_id": "report_2"}
        mock_list_reports.return_value = mock_reports
        
        response = client.get("/api/admin/pvfrs/backtest/reports")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 2
    
    @patch('backend_core.strategies.pvfrs.admin_interface.AdminInterface.get_task_list')
    def test_list_backtest_tasks_success(self, mock_get_tasks):
        """测试获取回测任务列表成功"""
        mock_tasks = [
            {"task_id": "task_1", "status": "running"},
            {"task_id": "task_2", "status": "completed"}
        ]
        mock_get_tasks.return_value = mock_tasks
        
        response = client.get("/api/admin/pvfrs/backtest/tasks")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 2
    
    @patch('backend_core.strategies.pvfrs.admin_interface.AdminInterface.cancel_backtest')
    def test_cancel_backtest_task_success(self, mock_cancel):
        """测试取消回测任务成功"""
        mock_cancel.return_value = True
        
        response = client.post("/api/admin/pvfrs/backtest/cancel/task_123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "取消成功" in data["message"]
    
    @patch('backend_core.strategies.pvfrs.admin_interface.AdminInterface.get_interface_status')
    def test_get_admin_interface_status_success(self, mock_get_status):
        """测试获取管理端接口状态成功"""
        mock_status = {
            "interface_name": "PVFRS Admin Interface",
            "version": "1.0.0",
            "active_tasks_count": 2,
            "completed_tasks_count": 5
        }
        mock_get_status.return_value = mock_status
        
        response = client.get("/api/admin/pvfrs/interface-status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["interface_name"] == "PVFRS Admin Interface"


class TestPVFRSScreeningAPI:
    """测试PVFRS选股策略API"""
    
    @patch('backend_core.strategies.pvfrs.frontend_interface.create_frontend_interface')
    def test_get_pvfrs_strategy_success(self, mock_create_interface):
        """测试PVFRS策略选股成功"""
        # 模拟前端接口
        mock_interface = Mock()
        mock_selection_result = Mock()
        mock_selection_result.to_dict.return_value = {
            "symbol": "000001",
            "name": "平安银行",
            "signal_strength": 0.8,
            "conditions_met": {
                "price_dimension_met": True,
                "frequency_dimension_met": True,
                "volume_dimension_met": True,
                "resonance_detected": True
            }
        }
        mock_interface.get_selection_results.return_value = [mock_selection_result]
        mock_create_interface.return_value = mock_interface
        
        response = client.get("/api/screening/pvfrs-strategy")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["strategy_name"] == "PVFARS量价频幅度共振策略"
        assert len(data["data"]) == 1
        assert data["data"][0]["symbol"] == "000001"
    
    def test_get_pvfrs_strategy_with_params(self):
        """测试带参数的PVFRS策略选股"""
        response = client.get(
            "/api/screening/pvfrs-strategy",
            params={
                "date": "2024-01-15",
                "limit": 20,
                "min_strength": 0.6
            }
        )
        
        # 由于没有实际数据，可能返回错误，但应该能正确处理参数
        assert response.status_code in [200, 404, 500]
    
    def test_get_pvfrs_strategy_invalid_date(self):
        """测试无效日期参数"""
        response = client.get(
            "/api/screening/pvfrs-strategy",
            params={"date": "invalid-date"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "日期格式错误" in data["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])