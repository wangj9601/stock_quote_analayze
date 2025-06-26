 #!/usr/bin/env python3
"""
创建股票新闻公告表的数据库迁移脚本
"""

import sqlite3
import os
import sys

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from backend_api.config import DB_PATH
    print(f"使用数据库路径: {DB_PATH}")
except ImportError as e:
    print(f"导入配置失败: {e}")
    # 使用默认路径
    DB_PATH = "database/stock_analysis.db"
    print(f"使用默认数据库路径: {DB_PATH}")

def create_stock_news_table():
    """创建股票新闻公告表"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 创建股票新闻表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code VARCHAR(10) NOT NULL,
                title VARCHAR(500) NOT NULL,
                content TEXT,
                keywords VARCHAR(200),
                publish_time VARCHAR(50),
                source VARCHAR(100),
                url VARCHAR(500),
                summary TEXT,
                type VARCHAR(20) DEFAULT 'news' NOT NULL,
                rating VARCHAR(50),
                target_price VARCHAR(20),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_news_code ON stock_news(stock_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_news_type ON stock_news(type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_news_publish_time ON stock_news(publish_time)")
        
        conn.commit()
        conn.close()
        
        print("✅ 成功创建股票新闻公告表及索引")
        return True
        
    except Exception as e:
        print(f"❌ 创建股票新闻公告表失败: {e}")
        return False

if __name__ == "__main__":
    print("开始创建股票新闻公告表...")
    if create_stock_news_table():
        print("✅ 数据库表创建完成")
    else:
        print("❌ 数据库表创建失败")