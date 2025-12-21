"""
测试历史行情查询问题
"""
import sys
import os
# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'backend_api'))

from backend_core.database.db import SessionLocal
from sqlalchemy import text

def test_history_query():
    """测试历史行情查询"""
    db = SessionLocal()
    
    code = "603667"
    
    # 1. 检查数据库中是否有该股票的数据
    print(f"\n=== 检查股票 {code} 的数据 ===")
    check_query = "SELECT COUNT(*) FROM historical_quotes WHERE code = :code"
    count = db.execute(text(check_query), {"code": code}).scalar()
    print(f"数据库中股票 {code} 的总记录数: {count}")
    
    if count > 0:
        # 2. 查看日期范围
        date_range_query = """
            SELECT MIN(date) as min_date, MAX(date) as max_date, 
                   COUNT(*) as total_count
            FROM historical_quotes 
            WHERE code = :code
        """
        result = db.execute(text(date_range_query), {"code": code}).fetchone()
        print(f"日期范围: {result[0]} 到 {result[1]}")
        print(f"总记录数: {result[2]}")
        
        # 3. 查看date字段的实际类型和格式
        sample_query = """
            SELECT date, code, name 
            FROM historical_quotes 
            WHERE code = :code 
            ORDER BY date DESC 
            LIMIT 5
        """
        samples = db.execute(text(sample_query), {"code": code}).fetchall()
        print(f"\n最近5条记录的日期格式:")
        for row in samples:
            print(f"  date={row[0]} (type={type(row[0])}), code={row[1]}, name={row[2]}")
        
        # 4. 测试查询逻辑（使用2025年的日期）
        test_query = """
            SELECT COUNT(*) 
            FROM historical_quotes 
            WHERE code = :code 
            AND date >= :start_date 
            AND date <= :end_date
        """
        test_count = db.execute(text(test_query), {
            "code": code,
            "start_date": "2025-05-01",
            "end_date": "2025-12-19"
        }).scalar()
        print(f"\n使用日期范围 2025-05-01 到 2025-12-19 查询到的记录数: {test_count}")
        
        # 5. 测试使用CAST转换的查询
        test_query_cast = """
            SELECT COUNT(*) 
            FROM historical_quotes 
            WHERE code = :code 
            AND CAST(date AS DATE) >= CAST(:start_date AS DATE)
            AND CAST(date AS DATE) <= CAST(:end_date AS DATE)
        """
        test_count_cast = db.execute(text(test_query_cast), {
            "code": code,
            "start_date": "2025-05-01",
            "end_date": "2025-12-19"
        }).scalar()
        print(f"使用CAST转换后查询到的记录数: {test_count_cast}")
        
        # 6. 测试查询所有数据（不限制日期）
        all_query = """
            SELECT COUNT(*) 
            FROM historical_quotes 
            WHERE code = :code
        """
        all_count = db.execute(text(all_query), {"code": code}).scalar()
        print(f"\n不限制日期范围查询到的记录数: {all_count}")
        
    db.close()

if __name__ == "__main__":
    test_history_query()

