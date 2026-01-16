"""
测试一阳穿三线策略API路由
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend_api')))

from fastapi.testclient import TestClient
from backend_api.main import app

client = TestClient(app)


def test_one_yang_three_lines_api_basic():
    """测试一阳穿三线API基本功能"""
    response = client.get("/api/screening/one-yang-three-lines")
    
    print(f"状态码: {response.status_code}")
    
    # 检查响应状态码
    assert response.status_code == 200, f"期望状态码200，实际: {response.status_code}"
    
    # 检查响应格式
    data = response.json()
    print(f"响应数据: {data}")
    
    assert "success" in data, "响应中应包含success字段"
    assert "data" in data, "响应中应包含data字段"
    assert "total" in data, "响应中应包含total字段"
    assert "strategy_name" in data, "响应中应包含strategy_name字段"
    
    assert data["success"] is True, "success字段应为True"
    assert isinstance(data["data"], list), "data字段应为列表"
    assert isinstance(data["total"], int), "total字段应为整数"
    assert data["strategy_name"] == "一阳穿三线", "策略名称应为'一阳穿三线'"
    
    print(f"✓ API基本功能测试通过，找到 {data['total']} 只符合条件的股票")


def test_one_yang_three_lines_api_pagination():
    """测试分页功能"""
    response = client.get("/api/screening/one-yang-three-lines?page=1&page_size=10")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "page" in data, "响应中应包含page字段"
    assert "page_size" in data, "响应中应包含page_size字段"
    assert "total_pages" in data, "响应中应包含total_pages字段"
    
    assert data["page"] == 1, "页码应为1"
    assert data["page_size"] == 10, "每页数量应为10"
    assert len(data["data"]) <= 10, "返回的数据不应超过每页数量"
    
    print(f"✓ 分页功能测试通过，第1页返回 {len(data['data'])} 条数据")


def test_one_yang_three_lines_api_date_filter():
    """测试日期过滤功能"""
    response = client.get("/api/screening/one-yang-three-lines?start_date=2025-01-01&end_date=2025-01-31")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "date_range" in data, "响应中应包含date_range字段"
    assert data["date_range"]["start_date"] == "2025-01-01"
    assert data["date_range"]["end_date"] == "2025-01-31"
    
    print(f"✓ 日期过滤功能测试通过，找到 {data['total']} 只符合条件的股票")


def test_one_yang_three_lines_api_invalid_date():
    """测试无效日期格式"""
    response = client.get("/api/screening/one-yang-three-lines?start_date=2025/01/01")
    
    assert response.status_code == 400, "无效日期格式应返回400错误"
    data = response.json()
    assert "detail" in data, "错误响应应包含detail字段"
    
    print(f"✓ 无效日期格式测试通过，返回错误: {data['detail']}")


def test_one_yang_three_lines_api_response_structure():
    """测试响应数据结构"""
    response = client.get("/api/screening/one-yang-three-lines?page_size=1")
    
    assert response.status_code == 200
    data = response.json()
    
    if data["total"] > 0:
        # 检查第一条数据的结构
        first_result = data["data"][0]
        
        required_fields = [
            "code", "name", "signal_date", "current_price",
            "ma5", "ma10", "ma20", "ma30", "ma60", "ma120",
            "crossed_lines", "crossed_count", "volume_ratio", "turnover_rate",
            "position_type", "retracement", "bias5", "bias10", "bias30",
            "signal_score", "risk_warnings"
        ]
        
        for field in required_fields:
            assert field in first_result, f"结果中应包含{field}字段"
        
        print(f"✓ 响应数据结构测试通过，包含所有必需字段")
        print(f"  示例股票: {first_result['code']} {first_result['name']}")
        print(f"  信号评分: {first_result['signal_score']}")
        print(f"  穿越均线: {first_result['crossed_lines']}")
    else:
        print("⚠ 当前没有符合条件的股票，跳过数据结构测试")


if __name__ == "__main__":
    print("=" * 60)
    print("测试一阳穿三线策略API路由")
    print("=" * 60)
    
    try:
        test_one_yang_three_lines_api_basic()
        print()
        test_one_yang_three_lines_api_pagination()
        print()
        test_one_yang_three_lines_api_date_filter()
        print()
        test_one_yang_three_lines_api_invalid_date()
        print()
        test_one_yang_three_lines_api_response_structure()
        print()
        print("=" * 60)
        print("✓ 所有API路由测试通过！")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
