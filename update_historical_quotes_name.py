from backend_core.database.db import SessionLocal
from sqlalchemy import text

def update_historical_quotes_name():
    session = SessionLocal()
    try:
        # 读取所有股票基本信息
        stock_list = session.execute(text('SELECT code, name FROM stock_basic_info')).fetchall()
        print(f"共读取到 {len(stock_list)} 条股票基本信息")
        update_count = 0
        for code, name in stock_list:
            # 更新 historical_quotes 表中对应 code 的 name 字段
            result = session.execute(
                text('UPDATE historical_quotes SET name = :name WHERE code = :code'),
                {'name': name, 'code': code}
            )
            update_count += result.rowcount
        session.commit()
        print(f"已更新 historical_quotes 表 name 字段 {update_count} 条记录")
    except Exception as e:
        session.rollback()
        print(f"更新失败: {e}")
    finally:
        session.close()

if __name__ == '__main__':
    update_historical_quotes_name() 