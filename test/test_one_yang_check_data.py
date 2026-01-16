"""
检查数据库中的历史数据
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend_core.database.db import get_db
from sqlalchemy import text

def check_database_data():
    """检查数据库中的数据"""
    print("=" * 60)
    print("检查数据库中的历史数据")
    print("=" * 60)
    
    # 获取数据库会话
    db = next(get_db())
    
    try:
        # 1. 检查股票基本信息表
        print("\n1. 检查股票基本信息表")
        result = db.execute(text("""
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN name NOT LIKE '%ST%' THEN 1 END) as non_st
            FROM stock_basic_info
            WHERE LENGTH(code) = 6
        """))
        row = result.fetchone()
        print(f"   总股票数: {row[0]}")
        print(f"   非ST股票数: {row[1]}")
        
        # 2. 检查历史行情表
        print("\n2. 检查历史行情表")
        result = db.execute(text("""
            SELECT COUNT(DISTINCT code) as stock_count,
                   COUNT(*) as total_records,
                   MIN(date) as min_date,
                   MAX(date) as max_date
            FROM historical_quotes
        """))
        row = result.fetchone()
        print(f"   有数据的股票数: {row[0]}")
        print(f"   总记录数: {row[1]}")
        print(f"   最早日期: {row[2]}")
        print(f"   最新日期: {row[3]}")
        
        # 3. 随机选择一只有数据的股票
        print("\n3. 随机选择一只有数据的股票")
        result = db.execute(text("""
            SELECT h.code, s.name, COUNT(*) as record_count
            FROM historical_quotes h
            LEFT JOIN stock_basic_info s ON h.code = s.code
            WHERE s.name NOT LIKE '%ST%'
            GROUP BY h.code, s.name
            HAVING COUNT(*) >= 120
            ORDER BY record_count DESC
            LIMIT 5
        """))
        rows = result.fetchall()
        
        if rows:
            print(f"   找到 {len(rows)} 只有足够数据的股票:")
            for row in rows:
                print(f"   - {row[0]} {row[1]}: {row[2]} 条记录")
            
            # 选择第一只股票查看详细数据
            test_code = rows[0][0]
            test_name = rows[0][1]
            
            print(f"\n4. 查看股票 {test_code} {test_name} 的最近数据")
            result = db.execute(text("""
                SELECT date, open, close, high, low, volume, turnover_rate
                FROM historical_quotes
                WHERE code = :code
                ORDER BY date DESC
                LIMIT 5
            """), {'code': test_code})
            
            print("   最近5个交易日:")
            for row in result.fetchall():
                print(f"   {row[0]}: 开={row[1]}, 收={row[2]}, 高={row[3]}, 低={row[4]}, 量={row[5]}, 换手率={row[6]}")
        else:
            print("   未找到有足够数据的股票")
        
        print("\n" + "=" * 60)
        print("检查完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n检查失败: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    check_database_data()
