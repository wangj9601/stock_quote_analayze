"""
PVFRS策略管理端回测功能测试
测试管理端接口的回测功能实现
"""

import pytest
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend_core.strategies.pvfrs.admin_interface import AdminInterface, BacktestConfig
from backend_core.strategies.pvfrs.backtest_config_validator import BacktestConfigValidator
from backend_core.strategies.pvfrs.backtest_storage import QueryFilter
from backend_core.strategies.pvfrs.models import BacktestResult, Trade


class TestAdminBacktestFunctionality:
    """管理端回测功能测试类"""
    
    def setup_method(self):
        """测试前设置"""
        self.admin_interface = AdminInterface()
        
        # 创建测试配置
        self.test_config = BacktestConfig(
            start_date="2023-01-01",
            end_date="2023-12-31",
            stock_pool=["000001", "000002", "600000"],
            initial_capital=100000.0,
            strategy_params={
                "observation_period": 20,
                "min_volume_ratio": 1.0,
                "amplitude_threshold": 0.05
            },
            risk_params={
                "stop_loss_rate": 0.1,
                "take_profit_rate": 0.2,
                "max_holding_days": 30
            }
        )
    
    def test_config_validation(self):
        """测试配置验证功能"""
        # 测试有效配置
        config_dict = {
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "stock_pool": ["000001", "000002"],
            "initial_capital": 100000.0,
            "strategy_params": {
                "observation_period": 20,
                "min_volume_ratio": 1.0
            },
            "risk_params": {
                "stop_loss_rate": 0.1,
                "take_profit_rate": 0.2
            }
        }
        
        is_valid, errors = self.admin_interface.validate_config(config_dict)
        assert is_valid, f"配置验证失败: {errors}"
        
        # 测试无效配置
        invalid_config = config_dict.copy()
        invalid_config["start_date"] = "2023-12-31"  # 开始日期晚于结束日期
        invalid_config["end_date"] = "2023-01-01"
        
        is_valid, errors = self.admin_interface.validate_config(invalid_config)
        assert not is_valid, "应该检测到无效配置"
        assert len(errors) > 0, "应该有错误信息"
    
    def test_default_config_generation(self):
        """测试默认配置生成"""
        default_config = self.admin_interface.get_default_backtest_config()
        
        assert "start_date" in default_config
        assert "end_date" in default_config
        assert "stock_pool" in default_config
        assert "initial_capital" in default_config
        assert "strategy_params" in default_config
        assert "risk_params" in default_config
        
        # 验证默认配置是有效的
        is_valid, errors = self.admin_interface.validate_config(default_config)
        assert is_valid, f"默认配置应该是有效的: {errors}"
    
    def test_config_schema_generation(self):
        """测试配置模式生成"""
        schema = self.admin_interface.get_config_schema()
        
        assert "basic_config" in schema
        assert "stock_pool_config" in schema
        assert "strategy_params" in schema
        assert "risk_params" in schema
        
        # 检查基本配置字段
        basic_config = schema["basic_config"]
        assert "fields" in basic_config
        assert "start_date" in basic_config["fields"]
        assert "end_date" in basic_config["fields"]
        assert "initial_capital" in basic_config["fields"]
    
    def test_task_creation(self):
        """测试回测任务创建"""
        # 创建任务
        task_id = self.admin_interface.create_backtest(self.test_config)
        
        assert task_id is not None
        assert task_id in self.admin_interface.active_tasks
        
        # 检查任务状态
        task = self.admin_interface.active_tasks[task_id]
        assert task.status == "pending"
        assert task.config == self.test_config
        assert task.progress == 0
    
    def test_task_progress_monitoring(self):
        """测试任务进度监控"""
        # 创建任务
        task_id = self.admin_interface.create_backtest(self.test_config)
        
        # 获取进度信息
        progress_info = self.admin_interface.get_backtest_progress(task_id)
        
        assert progress_info["task_id"] == task_id
        assert progress_info["status"] == "pending"
        assert progress_info["progress"] == 0
        assert "config_summary" in progress_info
        
        # 测试不存在的任务
        with pytest.raises(Exception):
            self.admin_interface.get_backtest_progress("nonexistent_task")
    
    def test_task_cancellation(self):
        """测试任务取消"""
        # 创建任务
        task_id = self.admin_interface.create_backtest(self.test_config)
        
        # 取消任务
        success = self.admin_interface.cancel_backtest(task_id)
        assert success
        
        # 检查任务状态
        assert task_id not in self.admin_interface.active_tasks
        assert task_id in self.admin_interface.completed_tasks
        
        task = self.admin_interface.completed_tasks[task_id]
        assert task.status == "cancelled"
    
    def test_config_suggestions(self):
        """测试配置改进建议"""
        # 测试短期回测的建议
        short_config = {
            "start_date": "2023-01-01",
            "end_date": "2023-01-31",  # 只有1个月
            "stock_pool": ["000001"],
            "initial_capital": 10000.0,  # 资金较少
            "strategy_params": {},
            "risk_params": {
                "stop_loss_rate": 0.25,  # 止损比例较高
                "take_profit_rate": 0.05   # 止盈比例较低
            }
        }
        
        suggestions = self.admin_interface.suggest_config_improvements(short_config)
        
        assert len(suggestions) > 0
        # 应该包含关于回测期间、资金、止损止盈比例的建议
        suggestion_text = " ".join(suggestions)
        assert any(keyword in suggestion_text for keyword in ["回测期间", "资金", "止损", "止盈"])
    
    def test_execution_statistics(self):
        """测试执行统计信息"""
        stats = self.admin_interface.get_execution_statistics()
        
        assert "monitor_statistics" in stats
        assert "local_statistics" in stats
        assert "system_status" in stats
        
        local_stats = stats["local_statistics"]
        assert "local_active_tasks" in local_stats
        assert "local_completed_tasks" in local_stats
        assert "total_reports" in local_stats
    
    def test_task_cleanup(self):
        """测试任务清理"""
        # 创建并取消一些任务
        task_ids = []
        for i in range(3):
            task_id = self.admin_interface.create_backtest(self.test_config)
            self.admin_interface.cancel_backtest(task_id)
            task_ids.append(task_id)
        
        # 执行清理
        cleanup_result = self.admin_interface.cleanup_old_tasks(keep_recent_hours=0)
        
        assert "total_cleaned_count" in cleanup_result
        assert cleanup_result["total_cleaned_count"] >= 0
    
    def test_comparison_metrics_availability(self):
        """测试对比指标可用性"""
        metrics = self.admin_interface.get_available_comparison_metrics()
        
        assert len(metrics) > 0
        
        # 检查必要的指标
        metric_names = [m["name"] for m in metrics]
        required_metrics = ["total_return", "annual_return", "sharpe_ratio", "max_drawdown", "win_rate"]
        
        for required_metric in required_metrics:
            assert required_metric in metric_names
        
        # 检查指标结构
        for metric in metrics:
            assert "name" in metric
            assert "display_name" in metric
            assert "description" in metric
            assert "higher_better" in metric
            assert "format" in metric
    
    def test_storage_statistics(self):
        """测试存储统计信息"""
        try:
            stats = self.admin_interface.get_storage_statistics()
            
            assert "total_reports" in stats
            assert "strategy_distribution" in stats
            assert "recent_reports_30d" in stats
            assert "performance_statistics" in stats
            assert "storage_info" in stats
            
            # 检查性能统计
            perf_stats = stats["performance_statistics"]
            assert "average_return" in perf_stats
            assert "max_return" in perf_stats
            assert "min_return" in perf_stats
            
            # 检查存储信息
            storage_info = stats["storage_info"]
            assert "database_size_bytes" in storage_info
            assert "compression_enabled" in storage_info
            
        except Exception as e:
            # 如果存储未初始化，这是正常的
            assert "存储" in str(e) or "数据库" in str(e)
    
    def test_system_status(self):
        """测试系统状态获取"""
        status = self.admin_interface.get_system_status()
        
        assert "admin_interface_status" in status
        assert "pvfrs_system_status" in status
        assert "active_tasks_count" in status
        assert "completed_tasks_count" in status
        assert "total_reports_count" in status
        
        assert status["admin_interface_status"] == "active"
    
    def test_config_from_dict_creation(self):
        """测试从字典创建配置对象"""
        config_dict = {
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "stock_pool": ["000001", "000002"],
            "initial_capital": 100000.0,
            "strategy_params": {
                "observation_period": 20
            },
            "risk_params": {
                "stop_loss_rate": 0.1,
                "take_profit_rate": 0.2
            }
        }
        
        config = self.admin_interface.create_config_from_dict(config_dict)
        
        assert config.start_date == "2023-01-01"
        assert config.end_date == "2023-12-31"
        assert config.stock_pool == ["000001", "000002"]
        assert config.initial_capital == 100000.0
        assert config.strategy_params["observation_period"] == 20
        assert config.risk_params["stop_loss_rate"] == 0.1
    
    def test_task_creation_from_dict(self):
        """测试从字典创建回测任务"""
        config_dict = {
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "stock_pool": ["000001"],
            "initial_capital": 100000.0,
            "strategy_params": {},
            "risk_params": {}
        }
        
        task_id = self.admin_interface.create_backtest_from_dict(config_dict)
        
        assert task_id is not None
        assert task_id in self.admin_interface.active_tasks
        
        task = self.admin_interface.active_tasks[task_id]
        assert task.config.start_date == "2023-01-01"
        assert task.config.stock_pool == ["000001"]


def test_config_validator_standalone():
    """测试配置验证器独立功能"""
    validator = BacktestConfigValidator()
    
    # 测试默认配置
    default_config = validator.get_default_config()
    is_valid, errors = validator.validate_backtest_config(default_config)
    assert is_valid, f"默认配置应该有效: {errors}"
    
    # 测试参数模式
    schema = validator.get_parameter_schema()
    assert "basic_config" in schema
    assert "strategy_params" in schema
    assert "risk_params" in schema


def test_query_filter_creation():
    """测试查询过滤器创建"""
    from backend_core.strategies.pvfrs.backtest_storage import create_query_filter
    
    # 测试默认过滤器
    filter_obj = create_query_filter()
    assert filter_obj.limit == 50
    assert filter_obj.offset == 0
    assert filter_obj.order_by == "created_at"
    assert filter_obj.order_desc == True
    
    # 测试自定义过滤器
    custom_filter = create_query_filter(
        start_date="2023-01-01",
        end_date="2023-12-31",
        strategy_name="PVFRS",
        limit=100
    )
    
    assert custom_filter.start_date == "2023-01-01"
    assert custom_filter.end_date == "2023-12-31"
    assert custom_filter.strategy_name == "PVFRS"
    assert custom_filter.limit == 100


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])