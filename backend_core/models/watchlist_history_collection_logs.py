from sqlalchemy import Column, Integer, String, DateTime, Text
from backend_core.database.db import Base
from datetime import datetime

class WatchlistHistoryCollectionLogs(Base):
    __tablename__ = 'watchlist_history_collection_logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False)
    affected_rows = Column(Integer)
    status = Column(String(20))
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.now) 