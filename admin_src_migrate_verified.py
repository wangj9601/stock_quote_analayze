import os
from sqlalchemy import text, create_engine
from dotenv import load_dotenv

load_dotenv()

def migrate():
    # 尝试从环境变量获取连接和配置
    db_user = os.getenv("DB_USER", "postgres")
    db_pass = os.getenv("DB_PASSWORD", "qidianspacetime")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5446")
    db_name = os.getenv("DB_NAME", "stock_analysis")
    
    db_url = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    print(f"Connecting to {db_host}:{db_port}/{db_name}...")
    
    engine = create_engine(db_url)
    
    try:
        with engine.begin() as conn:
            # PostgreSQL column name lookup
            check_sql = text("""
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='gms_strategy_version_stocks' AND column_name='is_verified'
            """)
            res = conn.execute(check_sql).fetchone()
            
            if not res:
                print("Adding column 'is_verified' to 'gms_strategy_version_stocks'...")
                conn.execute(text("ALTER TABLE gms_strategy_version_stocks ADD COLUMN is_verified BOOLEAN NOT NULL DEFAULT FALSE"))
                print("Column added successfully.")
            else:
                print("Column 'is_verified' already exists.")
    except Exception as e:
        print(f"Error during migration: {e}")

if __name__ == "__main__":
    migrate()
