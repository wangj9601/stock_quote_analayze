import time
from datetime import datetime, timedelta
import akshare as ak
from sqlalchemy.orm import Session
from sqlalchemy import exists
from backend_core.database.db import get_db

# 假设有自选股表 watchlist，字段 code
from backend_core.models.watchlist import Watchlist  # 需根据实际路径调整
from backend_core.models.historical_quotes import HistoricalQuotes  # 需根据实际路径调整
from backend_core.models.watchlist_history_collection_logs import WatchlistHistoryCollectionLogs  # 需根据实际路径调整

def get_watchlist_codes(db: Session):
    """获取自选股股票代码列表，去重。"""
    codes = db.query(Watchlist.stock_code).distinct().all()
    return [c[0] for c in codes]

def has_collected(db: Session, stock_code: str) -> bool:
    """判断该股票是否已采集过历史数据。"""
    return db.query(
        exists().where(
            (WatchlistHistoryCollectionLogs.stock_code == stock_code) &
            (WatchlistHistoryCollectionLogs.status == 'success')
        )
    ).scalar()

def log_collection(db: Session, stock_code: str, affected_rows: int, status: str, error_message: str = None):
    """写入采集日志。"""
    log = WatchlistHistoryCollectionLogs(
        stock_code=stock_code,
        affected_rows=affected_rows,
        status=status,
        error_message=error_message,
        created_at=datetime.now()
    )
    db.add(log)
    db.commit()

def insert_historical_quotes(db: Session, stock_code: str, df):
    """批量插入历史行情数据，避免重复插入。"""
    rows = []
    # 根据code从watchlist表获取股票名称
    stock_name = None
    result = db.query(Watchlist.stock_name).filter(Watchlist.stock_code == stock_code).first()
    if result and len(result) > 0:
        stock_name = result[0]
    print(f"stock_name: {stock_name}")

    for _, row in df.iterrows():
        hq = HistoricalQuotes(
            code=stock_code,
            name=stock_name,
            date=row.get('日期'),
            open=row.get('开盘'),
            close=row.get('收盘'),
            high=row.get('最高'),
            low=row.get('最低'),
            volume=row.get('成交量'),
            amount=row.get('成交额'),
            amplitude=row.get('振幅'),
            change_percent=row.get('涨跌幅'),
            change=row.get('涨跌额'),
            turnover_rate=row.get('换手率')
            #adjust='qfq'
        )
        rows.append(hq)
    if rows:
        # 执行upsert操作，避免重复插入
        # 这里只能用原生SQL或SQLAlchemy的merge/on_conflict等方式，以下为通用实现（以PostgreSQL为例，其他数据库需调整语法）
        from sqlalchemy.dialects.postgresql import insert

        for hq in rows:
            stmt = insert(HistoricalQuotes).values(
                code=hq.code,
                name=hq.name,    # 新增股票名称字段      
                date=hq.date,
                open=hq.open,
                close=hq.close,
                high=hq.high,
                low=hq.low,
                volume=hq.volume,
                amount=hq.amount,
                #amplitude=hq.amplitude,
                change_percent=hq.change_percent,
                #change=hq.change,
                #turnover_rate=hq.turnover_rate,
                #adjust=hq.adjust
            ).on_conflict_do_update(
                index_elements=['code', 'date'],
                set_={
                    'name': hq.name,
                    'open': hq.open,
                    'close': hq.close,
                    'high': hq.high,
                    'low': hq.low,
                    'volume': hq.volume,
                    'amount': hq.amount,
                    #'amplitude': hq.amplitude,
                    'change_percent': hq.change_percent
                    #   'change': hq.change,
                    #'turnover_rate': hq.turnover_rate,
                    #'adjust': hq.adjust
                }
            )
            db.execute(stmt)
        db.commit()
    return len(rows)

def collect_watchlist_history():
    """
    自选股历史行情采集主函数。
    返回采集成功的股票数量和失败的股票数量。
    """
    db = next(get_db())
    codes = get_watchlist_codes(db)
    success_count = 0
    fail_count = 0
    for stock_code in set(codes):
        if has_collected(db, stock_code):
            continue
        try:
            end_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
            df = ak.stock_zh_a_hist(symbol=stock_code, period='daily', start_date='19940101', end_date=end_date, adjust='qfq')
            # 批量插入前，先删除该stock_code的历史数据
            db.query(HistoricalQuotes).filter(HistoricalQuotes.code == stock_code).delete()
            affected_rows = insert_historical_quotes(db, stock_code, df)
            log_collection(db, stock_code, affected_rows, 'success')
            success_count += 1
        except Exception as e:
            db.rollback()
            log_collection(db, stock_code, 0, 'fail', str(e))
            fail_count += 1
        time.sleep(10)
    return {"success": success_count, "fail": fail_count}
