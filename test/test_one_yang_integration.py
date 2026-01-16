"""
一阳穿三线策略集成测试
测试完整的端到端流程：API调用 -> 策略执行 -> 数据库查询 -> 结果返回
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'backend_api'))

from fastapi.testclient import TestClient
from backend_api.main import app
from backend_core.database.db import get_db
from sqlalchemy import text
import time

client = TestClient(app)


def test_end_to_end_flow():
    """
    测试完整的端到端流程
    1. 验证数据库中有足够的测试数据
    2. 调用API接口
    3. 验证响应格式和数据完整性
    4. 验证业务逻辑正确性
    """
    print("=" * 80)
    print("一阳穿三线策略 - 端到端集成测试")
    print("=" * 80)
    
    # 步骤1: 验证数据库连接和数据
    print("\n步骤1: 验证数据库连接和数据...")
    db = next(get_db())
    
    try:
        # 检查是否有足够的历史数据
        result = db.execute(text("""
            SELECT COUNT(DISTINCT code) as stock_count
            FROM historical_quotes
        """))
        stock_count = result.fetchone()[0]
        print(f"   ✓ 数据库连接成功")
        print(f"   ✓ 找到 {stock_count} 只有历史数据的股票")
        
        if stock_count < 10:
            print("   ⚠ 警告: 数据量较少，可能影响测试结果")
        
        # 检查stock_basic_info表
        result = db.execute(text("""
            SELECT COUNT(*) as count
            FROM stock_basic_info
            WHERE name NOT LIKE '%ST%'
        """))
        non_st_count = result.fetchone()[0]
        print(f"   ✓ 找到 {non_st_count} 只非ST股票")
        
    except Exception as e:
        print(f"   ✗ 数据库验证失败: {str(e)}")
        return False
    finally:
        db.close()
    
    # 步骤2: 调用API接口
    print("\n步骤2: 调用API接口...")
    start_time = time.time()
    
    try:
        response = client.get("/api/screening/one-yang-three-lines")
        elapsed_time = time.time() - start_time
        
        print(f"   ✓ API调用成功")
        print(f"   ✓ 响应时间: {elapsed_time:.2f}秒")
        print(f"   ✓ 状态码: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ✗ 期望状态码200，实际: {response.status_code}")
            print(f"   响应内容: {response.text}")
            return False
        
    except Exception as e:
        print(f"   ✗ API调用失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # 步骤3: 验证响应格式
    print("\n步骤3: 验证响应格式...")
    
    try:
        data = response.json()
        
        # 检查必需字段
        required_fields = ["success", "data", "total", "page", "page_size", 
                          "total_pages", "search_date", "strategy_name"]
        for field in required_fields:
            if field not in data:
                print(f"   ✗ 缺少必需字段: {field}")
                return False
        print(f"   ✓ 包含所有必需字段")
        
        # 检查字段类型
        if not isinstance(data["success"], bool):
            print(f"   ✗ success字段类型错误")
            return False
        if not isinstance(data["data"], list):
            print(f"   ✗ data字段类型错误")
            return False
        if not isinstance(data["total"], int):
            print(f"   ✗ total字段类型错误")
            return False
        print(f"   ✓ 字段类型正确")
        
        # 检查success值
        if data["success"] is not True:
            print(f"   ✗ success应为True")
            return False
        print(f"   ✓ success字段值正确")
        
        # 检查策略名称
        if data["strategy_name"] != "一阳穿三线":
            print(f"   ✗ 策略名称错误: {data['strategy_name']}")
            return False
        print(f"   ✓ 策略名称正确")
        
        print(f"   ✓ 找到 {data['total']} 只符合条件的股票")
        
    except Exception as e:
        print(f"   ✗ 响应格式验证失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # 步骤4: 验证数据完整性
    print("\n步骤4: 验证数据完整性...")
    
    if data["total"] > 0:
        try:
            # 检查第一条数据的结构
            first_result = data["data"][0]
            
            required_result_fields = [
                "code", "name", "signal_date", "current_price",
                "ma5", "ma10", "ma20", "ma30", "ma60", "ma120",
                "crossed_lines", "crossed_count", "volume_ratio", "turnover_rate",
                "position_type", "retracement", "bias5", "bias10", "bias30",
                "signal_score", "risk_warnings"
            ]
            
            for field in required_result_fields:
                if field not in first_result:
                    print(f"   ✗ 结果数据缺少字段: {field}")
                    return False
            print(f"   ✓ 结果数据包含所有必需字段")
            
            # 检查数据类型
            if not isinstance(first_result["code"], str):
                print(f"   ✗ code字段应为字符串")
                return False
            if not isinstance(first_result["crossed_count"], int):
                print(f"   ✗ crossed_count字段应为整数")
                return False
            if not isinstance(first_result["signal_score"], int):
                print(f"   ✗ signal_score字段应为整数")
                return False
            if not isinstance(first_result["risk_warnings"], list):
                print(f"   ✗ risk_warnings字段应为列表")
                return False
            print(f"   ✓ 数据类型正确")
            
            # 显示示例数据
            print(f"\n   示例股票:")
            print(f"   - 代码: {first_result['code']}")
            print(f"   - 名称: {first_result['name']}")
            print(f"   - 信号日期: {first_result['signal_date']}")
            print(f"   - 当前价格: {first_result['current_price']}")
            print(f"   - 穿越均线: {first_result['crossed_lines']} (共{first_result['crossed_count']}条)")
            print(f"   - 成交量倍数: {first_result['volume_ratio']}x")
            print(f"   - 换手率: {first_result['turnover_rate']}%")
            print(f"   - 位置类型: {first_result['position_type']}")
            print(f"   - 信号评分: {first_result['signal_score']}分")
            if first_result['risk_warnings']:
                print(f"   - 风险提示: {', '.join(first_result['risk_warnings'])}")
            
        except Exception as e:
            print(f"   ✗ 数据完整性验证失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    else:
        print(f"   ⚠ 当前没有符合条件的股票，跳过数据完整性验证")
    
    # 步骤5: 验证业务逻辑
    print("\n步骤5: 验证业务逻辑...")
    
    if data["total"] > 0:
        try:
            # 验证穿线数量
            for result in data["data"]:
                if result["crossed_count"] < 3:
                    print(f"   ✗ 股票 {result['code']} 穿线数量 {result['crossed_count']} < 3")
                    return False
            print(f"   ✓ 所有股票穿线数量 >= 3")
            
            # 验证ST股票排除
            for result in data["data"]:
                if "ST" in result["name"]:
                    print(f"   ✗ 结果中包含ST股票: {result['code']} {result['name']}")
                    return False
            print(f"   ✓ 已排除所有ST股票")
            
            # 验证评分排序
            scores = [result["signal_score"] for result in data["data"]]
            if scores != sorted(scores, reverse=True):
                print(f"   ✗ 结果未按评分降序排列")
                return False
            print(f"   ✓ 结果按评分降序排列")
            
            # 验证位置类型
            valid_positions = ["低位", "中位", "高位"]
            for result in data["data"]:
                if result["position_type"] not in valid_positions:
                    print(f"   ✗ 无效的位置类型: {result['position_type']}")
                    return False
            print(f"   ✓ 位置类型有效")
            
        except Exception as e:
            print(f"   ✗ 业务逻辑验证失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    else:
        print(f"   ⚠ 当前没有符合条件的股票，跳过业务逻辑验证")
        print(f"   ℹ 这是正常情况，策略条件较严格，不是每天都有符合条件的股票")
    
    print("\n" + "=" * 80)
    print("✓ 端到端集成测试通过！")
    print("=" * 80)
    return True


def test_api_pagination():
    """测试API分页功能"""
    print("\n" + "=" * 80)
    print("测试API分页功能")
    print("=" * 80)
    
    try:
        # 获取第一页
        response1 = client.get("/api/screening/one-yang-three-lines?page=1&page_size=5")
        assert response1.status_code == 200
        data1 = response1.json()
        
        print(f"✓ 第1页请求成功")
        print(f"  总数: {data1['total']}")
        print(f"  当前页: {data1['page']}")
        print(f"  每页数量: {data1['page_size']}")
        print(f"  总页数: {data1['total_pages']}")
        print(f"  返回数量: {len(data1['data'])}")
        
        # 验证分页参数
        assert data1["page"] == 1
        assert data1["page_size"] == 5
        assert len(data1["data"]) <= 5
        
        if data1["total"] > 5:
            # 获取第二页
            response2 = client.get("/api/screening/one-yang-three-lines?page=2&page_size=5")
            assert response2.status_code == 200
            data2 = response2.json()
            
            print(f"✓ 第2页请求成功")
            print(f"  返回数量: {len(data2['data'])}")
            
            # 验证两页数据不同
            if len(data1["data"]) > 0 and len(data2["data"]) > 0:
                assert data1["data"][0]["code"] != data2["data"][0]["code"]
                print(f"✓ 两页数据不同")
        
        print("✓ 分页功能测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 分页功能测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_api_date_filter():
    """测试API日期过滤功能"""
    print("\n" + "=" * 80)
    print("测试API日期过滤功能")
    print("=" * 80)
    
    try:
        # 测试日期范围过滤
        response = client.get("/api/screening/one-yang-three-lines?start_date=2025-01-01&end_date=2025-01-31")
        assert response.status_code == 200
        data = response.json()
        
        print(f"✓ 日期过滤请求成功")
        print(f"  日期范围: {data['date_range']['start_date']} 至 {data['date_range']['end_date']}")
        print(f"  找到 {data['total']} 只符合条件的股票")
        
        # 验证日期范围
        if data["total"] > 0:
            for result in data["data"]:
                signal_date = result["signal_date"]
                assert signal_date >= "2025-01-01"
                assert signal_date <= "2025-01-31"
            print(f"✓ 所有结果在指定日期范围内")
        
        print("✓ 日期过滤功能测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 日期过滤功能测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_api_error_handling():
    """测试API错误处理"""
    print("\n" + "=" * 80)
    print("测试API错误处理")
    print("=" * 80)
    
    try:
        # 测试无效日期格式
        response = client.get("/api/screening/one-yang-three-lines?start_date=2025/01/01")
        assert response.status_code == 400
        print(f"✓ 无效日期格式返回400错误")
        
        # 测试日期范围错误
        response = client.get("/api/screening/one-yang-three-lines?start_date=2025-12-31&end_date=2025-01-01")
        assert response.status_code == 400
        print(f"✓ 日期范围错误返回400错误")
        
        # 测试无效页码
        response = client.get("/api/screening/one-yang-three-lines?page=0")
        assert response.status_code == 422  # FastAPI参数验证错误
        print(f"✓ 无效页码返回422错误")
        
        # 测试无效每页数量
        response = client.get("/api/screening/one-yang-three-lines?page_size=1000")
        assert response.status_code == 422  # 超过最大值500
        print(f"✓ 无效每页数量返回422错误")
        
        print("✓ 错误处理测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 错误处理测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_database_query_performance():
    """测试数据库查询性能"""
    print("\n" + "=" * 80)
    print("测试数据库查询性能")
    print("=" * 80)
    
    db = next(get_db())
    
    try:
        # 测试单只股票查询性能
        start_time = time.time()
        result = db.execute(text("""
            SELECT code, name, date, open, close, high, low, 
                   change_percent, volume, amount, turnover_rate
            FROM historical_quotes 
            WHERE code = '000001'
            ORDER BY date DESC
            LIMIT 250
        """))
        rows = result.fetchall()
        elapsed_time = time.time() - start_time
        
        print(f"✓ 单只股票查询: {len(rows)} 条记录，耗时 {elapsed_time:.3f}秒")
        
        if elapsed_time > 1.0:
            print(f"  ⚠ 警告: 查询时间较长，建议优化索引")
        
        # 测试批量股票列表查询性能
        start_time = time.time()
        result = db.execute(text("""
            SELECT code, name
            FROM stock_basic_info
            WHERE name NOT LIKE '%ST%'
            LIMIT 100
        """))
        rows = result.fetchall()
        elapsed_time = time.time() - start_time
        
        print(f"✓ 股票列表查询: {len(rows)} 条记录，耗时 {elapsed_time:.3f}秒")
        
        if elapsed_time > 0.5:
            print(f"  ⚠ 警告: 查询时间较长，建议优化索引")
        
        print("✓ 数据库查询性能测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 数据库查询性能测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "一阳穿三线策略 - 集成测试套件" + " " * 20 + "║")
    print("╚" + "=" * 78 + "╝")
    
    all_passed = True
    
    # 运行所有测试
    tests = [
        ("端到端流程测试", test_end_to_end_flow),
        ("API分页功能测试", test_api_pagination),
        ("API日期过滤测试", test_api_date_filter),
        ("API错误处理测试", test_api_error_handling),
        ("数据库查询性能测试", test_database_query_performance),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
            if not passed:
                all_passed = False
        except Exception as e:
            print(f"\n✗ {test_name} 执行异常: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
            all_passed = False
    
    # 输出测试总结
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 30 + "测试总结" + " " * 30 + "║")
    print("╠" + "=" * 78 + "╣")
    
    for test_name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"║  {test_name:<50} {status:>20}  ║")
    
    print("╠" + "=" * 78 + "╣")
    
    if all_passed:
        print("║" + " " * 25 + "✓ 所有集成测试通过！" + " " * 25 + "║")
        print("╚" + "=" * 78 + "╝")
        sys.exit(0)
    else:
        print("║" + " " * 25 + "✗ 部分测试失败" + " " * 28 + "║")
        print("╚" + "=" * 78 + "╝")
        sys.exit(1)
