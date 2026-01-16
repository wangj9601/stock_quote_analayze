"""
测试一阳穿三线策略主函数
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend_api.stock.one_yang_three_lines_strategy import OneYangThreeLinesStrategy
from backend_core.database.db import get_db

def test_screening_main_function():
    """测试策略主函数"""
    print("=" * 60)
    print("测试一阳穿三线策略主函数")
    print("=" * 60)
    
    # 获取数据库会话
    db = next(get_db())
    
    try:
        # 测试模式：只处理前50只股票（增加数量以提高找到符合条件股票的概率）
        print("\n测试模式：处理前50只股票")
        results = OneYangThreeLinesStrategy.screening_one_yang_three_lines_strategy(
            db=db,
            limit=50
        )
        
        print(f"\n找到 {len(results)} 只符合条件的股票")
        
        # 显示结果
        if results:
            print("\n符合条件的股票列表:")
            print("-" * 60)
            for idx, stock in enumerate(results, 1):
                print(f"\n{idx}. {stock['code']} {stock['name']}")
                print(f"   信号日期: {stock['signal_date']}")
                print(f"   当前价格: {stock['current_price']}")
                print(f"   穿越均线: {stock['crossed_lines']} (共{stock['crossed_count']}条)")
                print(f"   成交量倍数: {stock['volume_ratio']}x")
                print(f"   换手率: {stock['turnover_rate']}%")
                print(f"   位置类型: {stock['position_type']} (回撤{stock['retracement']}%)")
                print(f"   乖离率: BIAS5={stock['bias5']}%, BIAS10={stock['bias10']}%, BIAS30={stock['bias30']}%")
                print(f"   信号评分: {stock['signal_score']}分")
                if stock['risk_warnings']:
                    print(f"   风险提示: {', '.join(stock['risk_warnings'])}")
        else:
            print("\n未找到符合条件的股票（这是正常的，因为一阳穿三线是较为严格的形态）")
        
        print("\n" + "=" * 60)
        print("测试完成 - 主函数执行成功")
        print("=" * 60)
        
        # 验证返回结果的格式
        if results:
            print("\n验证结果格式:")
            first_result = results[0]
            required_fields = [
                'code', 'name', 'signal_date', 'current_price',
                'ma5', 'ma10', 'ma20', 'ma30', 'ma60', 'ma120',
                'crossed_lines', 'crossed_count', 'volume_ratio', 'turnover_rate',
                'position_type', 'retracement', 'bias5', 'bias10', 'bias30',
                'signal_score', 'risk_warnings'
            ]
            
            missing_fields = [field for field in required_fields if field not in first_result]
            if missing_fields:
                print(f"   ✗ 缺少字段: {missing_fields}")
            else:
                print(f"   ✓ 所有必需字段都存在")
            
            # 验证结果是否按评分降序排列
            if len(results) > 1:
                is_sorted = all(results[i]['signal_score'] >= results[i+1]['signal_score'] 
                               for i in range(len(results)-1))
                if is_sorted:
                    print(f"   ✓ 结果已按评分降序排列")
                else:
                    print(f"   ✗ 结果未按评分降序排列")
        
    except Exception as e:
        print(f"\n测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_screening_main_function()
