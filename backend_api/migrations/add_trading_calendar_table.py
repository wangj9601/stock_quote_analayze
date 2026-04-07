"""
迁移脚本: 创建 trading_calendar 采集日历表
"""
from sqlalchemy import text, inspect

def run_migration(engine):
    inspector = inspect(engine)
    if 'trading_calendar' in inspector.get_table_names():
        print("trading_calendar 表已存在，跳过创建")
        return
    
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS trading_calendar (
                id SERIAL PRIMARY KEY,
                market VARCHAR(10) NOT NULL,
                holiday_date DATE NOT NULL,
                description VARCHAR(200),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                CONSTRAINT uq_trading_calendar_market_date UNIQUE (market, holiday_date)
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_trading_calendar_market ON trading_calendar (market)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_trading_calendar_holiday_date ON trading_calendar (holiday_date)
        """))
        conn.commit()
    print("✅ trading_calendar 表创建成功")


if __name__ == '__main__':
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from backend_api.database import engine
    run_migration(engine)
