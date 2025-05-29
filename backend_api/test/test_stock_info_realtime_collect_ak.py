"""
实时行情数据采集测试
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend_api.config import DB_PATH
from ..config import DB_PATH

def test_collect_realtime_quotes():
    """测试实时行情数据采集"""
    from backend.stock_info_realtime_collect_ak import collect_realtime_quotes
    db_file = DB_PATH
    # 运行采集
    collect_realtime_quotes(db_file=db_file)
    # 检查数据库文件是否存在
    assert os.path.exists(db_file), "数据库文件应存在"
    # 检查表和数据
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    # 检查基础信息表
    cursor.execute("SELECT COUNT(*) FROM stock_basic_info")
    basic_count = cursor.fetchone()[0]
    assert basic_count > 0, "stock_basic_info 表应有数据"
    # 检查实时行情表
    cursor.execute("SELECT COUNT(*) FROM stock_realtime_quote")
    realtime_count = cursor.fetchone()[0]
    assert realtime_count > 0, "stock_realtime_quote 表应有数据"
    # 检查部分字段
    cursor.execute("SELECT code, name FROM stock_basic_info LIMIT 1")
    code, name = cursor.fetchone()
    assert code and name, "股票代码和名称应存在"
    cursor.execute("SELECT code, current_price FROM stock_realtime_quote WHERE code=?", (code,))
    row = cursor.fetchone()
    assert row is not None, "实时行情表应有对应股票"
    conn.close()