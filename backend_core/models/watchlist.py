from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String
from backend_core.database.db import Base

class Watchlist(Base):
    __tablename__ = 'watchlist'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    stock_code = Column(String, nullable=False)
    stock_name = Column(String, nullable=False)
    group_name = Column(String, default="default")
    created_at = Column(DateTime, default=datetime.now)