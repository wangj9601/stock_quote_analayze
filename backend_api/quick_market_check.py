#!/usr/bin/env python3
"""
快速市场检查 - 分析当前市场情况
"""

import sys
import os
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def quick_market_check(db: Session):
    """快速检查市场情况"""
    print("=" * 60)
    print("📊 快速市场检查")
    print("=" * 60)
    
    # 1. 检查最新交易日数据
    print("\n1. 📅 最新交易日数据:")
    latest_query = db.execute(text("""
        SELECT MAX(date) as latest_date, COUNT(*) as stock_count
        FROM historical_quotes 
        WHERE date >= CURRENT_DATE - INTERVAL '7 days'
    """))
    latest_result = latest_query.fetchone()
    
    if latest_result:
        print(f"   最新交易日: {latest_result[0]}")
        print(f"   近7天数据股票数: {latest_result[1]}")
    
    # 2. 检查今日涨跌分布
    print("\n2. 📈 今日涨跌分布:")
    change_query = db.execute(text("""
        SELECT 
            CASE 
                WHEN change_percent >= 3 THEN '大涨(>=3%)'
                WHEN change_percent >= 1 THEN '上涨(1-3%)'
                WHEN change_percent >= 0 THEN '微涨(0-1%)'
                WHEN change_percent >= -1 THEN '微跌(-1-0%)'
                WHEN change_percent >= -3 THEN '下跌(-3--1%)'
                ELSE '大跌(<-3%)'
            END as change_range,
            COUNT(*) as stock_count,
            AVG(change_percent) as avg_change
        FROM historical_quotes 
        WHERE date = (SELECT MAX(date) FROM historical_quotes)
        AND change_percent IS NOT NULL
        GROUP BY change_range
        ORDER BY AVG(change_percent) DESC
    """))
    
    change_results = change_query.fetchall()
    for row in change_results:
        print(f"   {row[0]}: {row[1]}只股票 (平均{row[2]:.2f}%)")
    
    # 3. 检查长阳线情况
    print("\n3. 🕯️ 长阳线统计:")
    yang_query = db.execute(text("""
        SELECT 
            COUNT(*) as total_count,
            AVG(change_percent) as avg_change,
            MAX(change_percent) as max_change
        FROM historical_quotes 
        WHERE date = (SELECT MAX(date) FROM historical_quotes)
        AND change_percent >= 3.0
        AND close > open
        AND close > 0 AND open > 0
    """))
    
    yang_result = yang_query.fetchone()
    if yang_result and yang_result[0] > 0:
        print(f"   涨幅>=3%的阳线: {yang_result[0]}只")
        print(f"   平均涨幅: {yang_result[1]:.2f}%")
        print(f"   最大涨幅: {yang_result[2]:.2f}%")
    else:
        print("   ❌ 没有找到涨幅>=3%的阳线")
    
    # 4. 检查成交量放大情况
    print("\n4. 📊 成交量放大统计:")
    volume_query = db.execute(text("""
        SELECT 
            COUNT(*) as total_count,
            AVG(volume_ratio) as avg_ratio
        FROM (
            SELECT 
                h1.code,
                h1.volume / NULLIF(AVG(h2.volume), 0) as volume_ratio
            FROM historical_quotes h1
            LEFT JOIN historical_quotes h2 ON h1.code = h2.code 
                AND h2.date >= h1.date - INTERVAL '10 days' 
                AND h2.date < h1.date
            WHERE h1.date = (SELECT MAX(date) FROM historical_quotes)
            AND h1.volume > 0
            GROUP BY h1.code, h1.volume
            HAVING AVG(h2.volume) > 0
        ) t
        WHERE volume_ratio >= 2.0
    """))
    
    volume_result = volume_query.fetchone()
    if volume_result and volume_result[0] > 0:
        print(f"   成交量放大>=2倍: {volume_result[0]}只股票")
        print(f"   平均放大倍数: {volume_result[1]:.2f}")
    else:
        print("   ❌ 没有找到成交量放大>=2倍的股票")
    
    # 5. 检查均线穿越情况（简化版）
    print("\n5. 📈 均线穿越情况:")
    ma_query = db.execute(text("""
        SELECT COUNT(*) as stock_count
        FROM (
            SELECT 
                h.code,
                h.close,
                h.open,
                h.low,
                ma5.ma5,
                ma10.ma10,
                ma20.ma20
            FROM historical_quotes h
            LEFT JOIN ma_indicators ma5 ON h.code = ma5.code AND h.date = ma5.date AND ma5.market_type = 'CN'
            LEFT JOIN ma_indicators ma10 ON h.code = ma10.code AND h.date = ma10.date AND ma10.market_type = 'CN'
            LEFT JOIN ma_indicators ma20 ON h.code = ma20.code AND h.date = ma20.date AND ma20.market_type = 'CN'
            WHERE h.date = (SELECT MAX(date) FROM historical_quotes)
            AND h.change_percent >= 3.0
            AND h.close > h.open
            AND ma5.ma5 IS NOT NULL AND ma10.ma10 IS NOT NULL AND ma20.ma20 IS NOT NULL
        ) t
        WHERE close > ma5 AND close > ma10 AND close > ma20
        AND (open < ma5 OR open < ma10 OR open < ma20)
        AND (low < ma5 OR low < ma10 OR low < ma20)
    """))
    
    ma_result = ma_query.fetchone()
    if ma_result and ma_result[0] > 0:
        print(f"   穿越3条均线的股票: {ma_result[0]}只")
    else:
        print("   ❌ 没有找到穿越3条均线的股票")
    
    # 6. 检查换手率分布
    print("\n6. 🔄 换手率分布:")
    turnover_query = db.execute(text("""
        SELECT 
            CASE 
                WHEN turnover_rate >= 10 THEN '高换手(>=10%)'
                WHEN turnover_rate >= 5 THEN '中换手(5-10%)'
                WHEN turnover_rate >= 3 THEN '低换手(3-5%)'
                WHEN turnover_rate > 0 THEN '微换手(0-3%)'
                ELSE '无数据'
            END as turnover_range,
            COUNT(*) as stock_count
        FROM historical_quotes 
        WHERE date = (SELECT MAX(date) FROM historical_quotes)
        GROUP BY turnover_range
        ORDER BY stock_count DESC
    """))
    
    turnover_results = turnover_query.fetchall()
    for row in turnover_results:
        print(f"   {row[0]}: {row[1]}只股票")
    
    print("\n" + "=" * 60)
    print("💡 分析建议:")
    print("1. 如果大涨股票很少，说明市场整体表现平淡")
    print("2. 如果长阳线很少，可能需要降低涨幅要求")
    print("3. 如果成交量放大股票少，可能需要降低成交量倍数要求")
    print("4. 如果均线穿越股票少，可能需要减少穿越均线数量")
    print("=" * 60)

def main():
    """主函数"""
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        # 数据库连接配置（请根据实际情况修改）
        DATABASE_URL = "postgresql://username:password@localhost:5432/stock_db"
        
        # 创建数据库连接
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        db = Session()
        
        try:
            quick_market_check(db)
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ 检查失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
