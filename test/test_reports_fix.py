"""
测试报告数据查询修复
验证报告列表和概览数据是否能正确从数据库查询并返回
"""
import requests
import json

def test_reports_api():
    """测试报告API"""
    base_url = "http://localhost:8000"
    
    try:
        print("=" * 60)
        print("测试报告数据查询修复")
        print("=" * 60)
        
        # 1. 测试报告列表API
        print("\n1. 测试报告列表API...")
        reports_params = {
            "page": 1,
            "pageSize": 20
        }
        reports_response = requests.get(
            f"{base_url}/api/admin/pvfrs/reports",
            params=reports_params
        )
        
        if reports_response.status_code == 200:
            result = reports_response.json()
            print(f"✅ 报告列表API调用成功")
            print(f"响应结构: success={result.get('success')}")
            print(f"数据位置: {'result.data' if 'data' in result else 'result.reports'}")
            
            # 检查数据格式
            if 'data' in result:
                reports = result['data']
                print(f"报告数量: {len(reports)}")
                print(f"总数: {result.get('total', 0)}")
                if len(reports) > 0:
                    print(f"第一条报告示例:")
                    print(f"  - ID: {reports[0].get('id')}")
                    print(f"  - 标题: {reports[0].get('title')}")
                    print(f"  - 总收益率: {reports[0].get('totalReturn')}%")
                    print(f"  - 创建时间: {reports[0].get('createdAt')}")
            else:
                print("❌ 响应中没有 'data' 字段")
        else:
            print(f"❌ API调用失败，状态码: {reports_response.status_code}")
            print(f"响应内容: {reports_response.text}")
        
        # 2. 测试报告概览API
        print("\n2. 测试报告概览API...")
        overview_response = requests.get(f"{base_url}/api/admin/pvfrs/reports/overview")
        
        if overview_response.status_code == 200:
            result = overview_response.json()
            print(f"✅ 概览API调用成功")
            print(f"响应结构: success={result.get('success')}")
            
            if 'data' in result:
                overview = result['data']
                print(f"概览数据:")
                print(f"  - 总报告数: {overview.get('totalReports', 0)}")
                print(f"  - 平均收益率: {overview.get('avgReturn', 0)}%")
                print(f"  - 平均胜率: {overview.get('winRate', 0)}%")
                print(f"  - 最大回撤: {overview.get('maxDrawdown', 0)}%")
            else:
                print("❌ 响应中没有 'data' 字段")
        else:
            print(f"❌ 概览API调用失败，状态码: {overview_response.status_code}")
            print(f"响应内容: {overview_response.text}")
        
        print("\n" + "=" * 60)
        print("🎉 测试完成!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_reports_api()
