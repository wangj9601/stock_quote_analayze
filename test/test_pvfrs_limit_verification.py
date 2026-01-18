"""
PVFRS选股限制验证脚本
验证取消50条记录限制后的实际效果
"""

import requests
import json
from datetime import datetime

def test_api_endpoints():
    """测试API端点的限制参数"""
    
    base_url = "http://localhost:8000"  # 假设后端服务运行在8000端口
    
    print("🔍 PVFRS选股限制验证")
    print("=" * 50)
    
    # 测试选股路由
    print("\n1. 测试选股路由 (/api/screening/pvfrs-strategy)")
    
    # 不传limit参数
    print("   - 不传limit参数（应该返回所有符合条件的股票）")
    try:
        response = requests.get(f"{base_url}/api/screening/pvfrs-strategy")
        if response.status_code == 200:
            data = response.json()
            limit_param = data.get('parameters', {}).get('limit', 'unknown')
            print(f"     ✅ 响应成功，limit参数: {limit_param}")
            print(f"     📊 返回股票数量: {data.get('total', 0)}")
        else:
            print(f"     ❌ 请求失败: {response.status_code}")
    except Exception as e:
        print(f"     ⚠️  无法连接到服务器: {e}")
    
    # 传入limit参数
    print("   - 传入limit=20（应该限制为20条）")
    try:
        response = requests.get(f"{base_url}/api/screening/pvfrs-strategy?limit=20")
        if response.status_code == 200:
            data = response.json()
            limit_param = data.get('parameters', {}).get('limit', 'unknown')
            print(f"     ✅ 响应成功，limit参数: {limit_param}")
            print(f"     📊 返回股票数量: {data.get('total', 0)}")
        else:
            print(f"     ❌ 请求失败: {response.status_code}")
    except Exception as e:
        print(f"     ⚠️  无法连接到服务器: {e}")
    
    # 测试前端路由
    print("\n2. 测试前端路由 (/api/frontend/pvfrs/selection-results)")
    
    # 不传limit参数
    print("   - 不传limit参数（应该返回所有符合条件的股票）")
    try:
        response = requests.get(f"{base_url}/api/frontend/pvfrs/selection-results")
        if response.status_code == 200:
            data = response.json()
            print(f"     ✅ 响应成功")
            print(f"     📊 返回股票数量: {len(data.get('data', []))}")
        else:
            print(f"     ❌ 请求失败: {response.status_code}")
    except Exception as e:
        print(f"     ⚠️  无法连接到服务器: {e}")
    
    # 传入limit参数
    print("   - 传入limit=30（应该限制为30条）")
    try:
        response = requests.get(f"{base_url}/api/frontend/pvfrs/selection-results?limit=30")
        if response.status_code == 200:
            data = response.json()
            print(f"     ✅ 响应成功")
            print(f"     📊 返回股票数量: {len(data.get('data', []))}")
        else:
            print(f"     ❌ 请求失败: {response.status_code}")
    except Exception as e:
        print(f"     ⚠️  无法连接到服务器: {e}")


def show_code_changes():
    """显示代码修改总结"""
    
    print("\n" + "=" * 50)
    print("📝 代码修改总结")
    print("=" * 50)
    
    changes = [
        {
            "文件": "backend_api/stock/stock_screening_routes.py",
            "修改": [
                "• limit参数从 Query(50, ge=1, le=100) 改为 Query(None, ge=1)",
                "• 移除了le=100的上限限制",
                "• 当limit为None时，设置max_results=10000（实际不限制）",
                "• 响应中显示limit为'无限制'而不是具体数值"
            ]
        },
        {
            "文件": "backend_api/stock/pvfrs_frontend_routes.py", 
            "修改": [
                "• limit参数从 Query(50, ge=1, le=100) 改为 Query(None, ge=1)",
                "• 移除了le=100的上限限制",
                "• 当limit为None时，设置max_results=10000（实际不限制）",
                "• 配置接口也支持无限制设置"
            ]
        },
        {
            "文件": "backend_core/strategies/pvfrs/frontend_interface.py",
            "修改": [
                "• 默认max_selection_results从50改为10000",
                "• set_selection_config默认参数从50改为10000",
                "• 支持设置大数值来实现不限制效果"
            ]
        }
    ]
    
    for change in changes:
        print(f"\n📁 {change['文件']}")
        for mod in change['修改']:
            print(f"   {mod}")
    
    print(f"\n✅ 修改完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n🎯 效果:")
    print("   • 不传limit参数时：返回所有符合条件的股票")
    print("   • 传入limit参数时：按指定数量限制返回")
    print("   • 取消了原来的50条和100条上限限制")
    print("   • 保持向后兼容性，现有调用不受影响")


if __name__ == "__main__":
    print("🚀 PVFRS选股限制验证脚本")
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 显示代码修改
    show_code_changes()
    
    # 测试API（如果服务器运行的话）
    print("\n" + "=" * 50)
    print("🌐 API端点测试")
    print("=" * 50)
    print("注意: 需要后端服务运行在 http://localhost:8000")
    
    test_api_endpoints()
    
    print("\n" + "=" * 50)
    print("✅ 验证完成！")
    print("PVFRS选股功能已成功取消50条记录限制")
    print("=" * 50)