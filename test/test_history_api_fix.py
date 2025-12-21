"""
测试历史行情API修复后的查询
"""
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'backend_api'))

from backend_core.database.db import SessionLocal
from sqlalchemy import text

def test_fixed_query():
    """测试修复后的查询逻辑"""
    db = SessionLocal()
    
    code = "603667"
    start_date = "2025-05-01"
    end_date = "2025-12-19"
    
    print(f"\n=== 测试修复后的查询逻辑 ===")
    print(f"股票代码: {code}")
    print(f"日期范围: {start_date} 到 {end_date}")
    
    # 测试include_notes=false的查询（修复后的）
    query_a = """
        SELECT 
            h.code, h.name, h.date, h.open, h.close, h.high, h.low, 
            h.volume, h.amount, h.change_percent, h.change, h.turnover_rate,
            h.cumulative_change_percent, h.five_day_change_percent, h.ten_day_change_percent, h.thirty_day_change_percent, h.sixty_day_change_percent, h.remarks,
            kdj.k, kdj.d, kdj.j,
            rsi.rsi6, rsi.rsi12, rsi.rsi24
        FROM historical_quotes h
        LEFT JOIN kdj_indicators kdj ON h.code = kdj.code AND h.date = kdj.date AND kdj.market_type = 'CN'
        LEFT JOIN rsi_indicators rsi ON h.code = rsi.code AND h.date = rsi.date AND rsi.market_type = 'CN'
        WHERE h.code = :code
    """
    
    params_a = {"code": code}
    if start_date:
        query_a += " AND h.date >= :start_date"
        params_a["start_date"] = start_date
    if end_date:
        query_a += " AND h.date <= :end_date"
        params_a["end_date"] = end_date
    query_a += " ORDER BY h.date DESC"
    
    # 测试计数查询
    count_query_a = f"SELECT COUNT(*) FROM ({query_a})"
    total_a = db.execute(text(count_query_a), params_a).scalar()
    print(f"\n修复后的查询结果: {total_a} 条记录")
    
    # 测试实际数据查询（限制5条）
    query_a_limit = query_a + " LIMIT 5"
    result = db.execute(text(query_a_limit), params_a)
    rows = result.fetchall()
    
    print(f"\n前5条记录:")
    for i, row in enumerate(rows, 1):
        print(f"  {i}. date={row[2]}, code={row[0]}, name={row[1]}, close={row[4]}")
    
    db.close()
    
    if total_a > 0:
        print(f"\n✅ 修复成功！查询到 {total_a} 条记录")
    else:
        print(f"\n❌ 修复失败！未查询到记录")

if __name__ == "__main__":
    test_fixed_query()

