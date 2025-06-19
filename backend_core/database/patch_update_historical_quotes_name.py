import sqlite3
from pathlib import Path

# 使用相对路径
DB_PATH = Path(__file__).parent.parent.parent / 'database' / 'stock_analysis.db'

UPDATE_SQL = '''
UPDATE historical_quotes
SET name = (
    SELECT name FROM stock_basic_info WHERE stock_basic_info.code = historical_quotes.code
)
WHERE (name IS NULL OR name = '')
  AND code IN (SELECT code FROM stock_basic_info)
'''

def patch_update_historical_quotes_name(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    print('正在更新 historical_quotes 表中 name 为空的记录...')
    cursor.execute(UPDATE_SQL)
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    print(f'更新完成，共更新 {affected} 条记录。')

if __name__ == '__main__':
    patch_update_historical_quotes_name() 