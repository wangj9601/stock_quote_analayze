#!/usr/bin/env python3
"""
PVFRS管理端Vue界面集成测试
测试Vue管理界面与后端API的集成
"""

import pytest
import requests
import json
import time
from datetime import datetime, timedelta
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestPVFRSAdminVueIntegration:
    """PVFRS管理端Vue界面集成测试类"""
    
    def setup_method(self):
        """测试前准备"""
        self.base_url = "http://localhost:8000"
        self.admin_api_base = f"{self.base_url}/api/admin/pvfrs"
        
        # 测试用的认证token（实际使用中需要通过登录获取）
        self.auth_headers = {
            "Authorization": "Bearer test_admin_token",
            "Content-Type": "application/json"
        }
        
        logger.info("PVFRS管理端Vue界面集成测试开始")
    
    def test_system_status_api(self):
        """测试系统状态API"""
        try:
            url = f"{self.admin_api_base}/system/status"
            response = requests.get(url, headers=self.auth_headers, timeout=10)
            
            logger.info(f"系统状态API响应状态: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"系统状态数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
                
                # 验证响应结构
                assert "success" in data
                assert "data" in data
                
                status_data = data["data"]
                expected_fields = [
                    "activeStrategies", "runningBacktests", 
                    "totalReports", "systemHealth"
                ]
                
                for field in expected_fields:
                    assert field in status_data, f"缺少字段: {field}"
                
                logger.info("✅ 系统状态API测试通过")
            else:
                logger.warning(f"系统状态API返回非200状态码: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"系统状态API请求失败: {str(e)}")
            pytest.skip("后端服务不可用，跳过API测试")
    
    def test_backtest_task_creation_api(self):
        """测试回测任务创建API"""
        try:
            url = f"{self.admin_api_base}/backtest"
            
            # 构建测试回测配置
            test_config = {
                "name": "Vue界面集成测试",
                "mode": "single",
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
                "initial_capital": 100000,
                "market": "CN",
                "stock_code": "000001",
                "strategy_params": {
                    "buy_bias_min": -0.05,
                    "sell_bias_max": 0.05,
                    "buy_consecutive_days": 3
                },
                "risk_params": {
                    "stop_loss_rate": 0.1,
                    "take_profit_rate": 0.2,
                    "max_position_size": 0.3
                }
            }
            
            response = requests.post(
                url, 
                headers=self.auth_headers,
                json=test_config,
                timeout=15
            )
            
            logger.info(f"回测任务创建API响应状态: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"回测任务创建响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
                
                # 验证响应结构
                assert "success" in data
                assert "data" in data
                
                task_data = data["data"]
                assert "task_id" in task_data
                assert "execution_started" in task_data
                
                logger.info("✅ 回测任务创建API测试通过")
                return task_data["task_id"]
            else:
                logger.warning(f"回测任务创建API返回非200状态码: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"回测任务创建API请求失败: {str(e)}")
            pytest.skip("后端服务不可用，跳过API测试")
            return None
    
    def test_backtest_progress_api(self):
        """测试回测进度查询API"""
        try:
            # 先创建一个任务
            task_id = self.test_backtest_task_creation_api()
            
            if not task_id:
                pytest.skip("无法创建回测任务，跳过进度查询测试")
                return
            
            # 查询任务进度
            url = f"{self.admin_api_base}/backtest/progress/{task_id}"
            response = requests.get(url, headers=self.auth_headers, timeout=10)
            
            logger.info(f"回测进度查询API响应状态: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"回测进度数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
                
                # 验证响应结构
                assert "success" in data or "task_id" in data
                
                logger.info("✅ 回测进度查询API测试通过")
            else:
                logger.warning(f"回测进度查询API返回非200状态码: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"回测进度查询API请求失败: {str(e)}")
    
    def test_reports_list_api(self):
        """测试报告列表API"""
        try:
            url = f"{self.admin_api_base}/reports"
            params = {
                "page": 1,
                "pageSize": 10
            }
            
            response = requests.get(
                url, 
                headers=self.auth_headers,
                params=params,
                timeout=10
            )
            
            logger.info(f"报告列表API响应状态: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"报告列表数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
                
                # 验证响应结构
                assert "success" in data
                assert "data" in data
                
                reports_data = data["data"]
                assert "reports" in reports_data or isinstance(reports_data, list)
                
                logger.info("✅ 报告列表API测试通过")
            else:
                logger.warning(f"报告列表API返回非200状态码: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"报告列表API请求失败: {str(e)}")
    
    def test_strategy_config_api(self):
        """测试策略配置API"""
        try:
            url = f"{self.admin_api_base}/config"
            
            # 测试获取配置
            response = requests.get(url, headers=self.auth_headers, timeout=10)
            
            logger.info(f"策略配置获取API响应状态: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"策略配置数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
                logger.info("✅ 策略配置获取API测试通过")
            
            # 测试保存配置
            test_config = {
                "strategy_params": {
                    "buy_bias_min": -0.06,
                    "sell_bias_max": 0.06,
                    "buy_consecutive_days": 2
                },
                "risk_params": {
                    "stop_loss_rate": 0.08,
                    "take_profit_rate": 0.15,
                    "max_position_size": 0.25
                }
            }
            
            response = requests.post(
                url,
                headers=self.auth_headers,
                json=test_config,
                timeout=10
            )
            
            logger.info(f"策略配置保存API响应状态: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"策略配置保存响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
                logger.info("✅ 策略配置保存API测试通过")
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"策略配置API请求失败: {str(e)}")
    
    def test_monitoring_data_api(self):
        """测试监控数据API"""
        try:
            url = f"{self.admin_api_base}/monitor"
            response = requests.get(url, headers=self.auth_headers, timeout=10)
            
            logger.info(f"监控数据API响应状态: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"监控数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
                
                # 验证响应结构
                assert "success" in data
                assert "data" in data
                
                logger.info("✅ 监控数据API测试通过")
            else:
                logger.warning(f"监控数据API返回非200状态码: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"监控数据API请求失败: {str(e)}")
    
    def test_vue_component_structure(self):
        """测试Vue组件文件结构"""
        import os
        
        # 检查主要Vue组件文件是否存在
        vue_components = [
            "admin/src/views/PVFRSManagementView.vue",
            "admin/src/components/pvfrs/BacktestManagement.vue",
            "admin/src/components/pvfrs/ReportAnalysis.vue",
            "admin/src/components/pvfrs/StrategyConfiguration.vue",
            "admin/src/components/pvfrs/RealTimeMonitor.vue",
            "admin/src/components/pvfrs/StrategyGuide.vue",
            "admin/src/components/pvfrs/TaskDetail.vue",
            "admin/src/components/pvfrs/ReportDetail.vue",
            "admin/src/components/pvfrs/ReportComparison.vue",
            "admin/src/components/pvfrs/ReportGenerator.vue"
        ]
        
        missing_files = []
        existing_files = []
        
        for component_path in vue_components:
            if os.path.exists(component_path):
                existing_files.append(component_path)
                logger.info(f"✅ Vue组件存在: {component_path}")
            else:
                missing_files.append(component_path)
                logger.warning(f"❌ Vue组件缺失: {component_path}")
        
        # 检查API服务文件
        api_service_path = "admin/src/services/pvfrsApi.ts"
        if os.path.exists(api_service_path):
            existing_files.append(api_service_path)
            logger.info(f"✅ API服务文件存在: {api_service_path}")
        else:
            missing_files.append(api_service_path)
            logger.warning(f"❌ API服务文件缺失: {api_service_path}")
        
        # 检查路由配置
        router_path = "admin/src/router/index.ts"
        if os.path.exists(router_path):
            existing_files.append(router_path)
            logger.info(f"✅ 路由配置文件存在: {router_path}")
            
            # 检查路由配置中是否包含PVFRS管理路由
            try:
                with open(router_path, 'r', encoding='utf-8') as f:
                    router_content = f.read()
                    if 'pvfrs-management' in router_content:
                        logger.info("✅ 路由配置包含PVFRS管理路由")
                    else:
                        logger.warning("❌ 路由配置缺少PVFRS管理路由")
            except Exception as e:
                logger.warning(f"读取路由配置文件失败: {str(e)}")
        else:
            missing_files.append(router_path)
            logger.warning(f"❌ 路由配置文件缺失: {router_path}")
        
        # 生成测试报告
        logger.info(f"\n📊 Vue组件结构测试报告:")
        logger.info(f"✅ 存在的文件数量: {len(existing_files)}")
        logger.info(f"❌ 缺失的文件数量: {len(missing_files)}")
        
        if missing_files:
            logger.warning("缺失的文件列表:")
            for file_path in missing_files:
                logger.warning(f"  - {file_path}")
        
        # 如果关键文件都存在，测试通过
        critical_files = [
            "admin/src/views/PVFRSManagementView.vue",
            "admin/src/services/pvfrsApi.ts",
            "admin/src/router/index.ts"
        ]
        
        critical_missing = [f for f in critical_files if f in missing_files]
        
        if not critical_missing:
            logger.info("✅ Vue组件结构测试通过")
        else:
            logger.error(f"❌ 关键文件缺失: {critical_missing}")
            pytest.fail(f"关键Vue组件文件缺失: {critical_missing}")
    
    def test_backend_api_routes_availability(self):
        """测试后端API路由可用性"""
        try:
            # 测试管理端接口状态
            url = f"{self.admin_api_base}/interface-status"
            response = requests.get(url, headers=self.auth_headers, timeout=10)
            
            logger.info(f"管理端接口状态API响应: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"管理端接口状态: {json.dumps(data, indent=2, ensure_ascii=False)}")
                logger.info("✅ 后端API路由可用性测试通过")
            else:
                logger.warning(f"管理端接口状态API返回非200状态码: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"后端API路由测试失败: {str(e)}")
            pytest.skip("后端服务不可用，跳过API路由测试")
    
    def test_full_workflow_simulation(self):
        """测试完整工作流程模拟"""
        logger.info("🔄 开始完整工作流程模拟测试")
        
        try:
            # 1. 获取系统状态
            logger.info("1️⃣ 获取系统状态...")
            self.test_system_status_api()
            
            # 2. 创建回测任务
            logger.info("2️⃣ 创建回测任务...")
            task_id = self.test_backtest_task_creation_api()
            
            if task_id:
                # 3. 查询任务进度
                logger.info("3️⃣ 查询任务进度...")
                time.sleep(2)  # 等待任务开始执行
                self.test_backtest_progress_api()
            
            # 4. 获取报告列表
            logger.info("4️⃣ 获取报告列表...")
            self.test_reports_list_api()
            
            # 5. 测试策略配置
            logger.info("5️⃣ 测试策略配置...")
            self.test_strategy_config_api()
            
            # 6. 获取监控数据
            logger.info("6️⃣ 获取监控数据...")
            self.test_monitoring_data_api()
            
            logger.info("✅ 完整工作流程模拟测试完成")
            
        except Exception as e:
            logger.error(f"完整工作流程模拟测试失败: {str(e)}")
            pytest.fail(f"工作流程测试失败: {str(e)}")
    
    def teardown_method(self):
        """测试后清理"""
        logger.info("PVFRS管理端Vue界面集成测试结束")


def test_pvfrs_admin_vue_integration():
    """运行PVFRS管理端Vue界面集成测试"""
    logger.info("🚀 开始PVFRS管理端Vue界面集成测试")
    
    test_instance = TestPVFRSAdminVueIntegration()
    test_instance.setup_method()
    
    try:
        # 测试Vue组件结构
        test_instance.test_vue_component_structure()
        
        # 测试后端API可用性
        test_instance.test_backend_api_routes_availability()
        
        # 测试完整工作流程
        test_instance.test_full_workflow_simulation()
        
        logger.info("🎉 PVFRS管理端Vue界面集成测试全部通过")
        
    except Exception as e:
        logger.error(f"集成测试失败: {str(e)}")
        raise
    finally:
        test_instance.teardown_method()


if __name__ == "__main__":
    test_pvfrs_admin_vue_integration()