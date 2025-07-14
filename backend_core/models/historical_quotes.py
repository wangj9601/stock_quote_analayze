from sqlalchemy import Column, Integer, String, Float, Date
from backend_core.database.db import Base

class HistoricalQuotes(Base):
    __tablename__ = 'historical_quotes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False)
    trade_date = Column(Date, nullable=False)
    open = Column(Float)
    close = Column(Float)
    high = Column(Float)
    low = Column(Float)
    volume = Column(Integer)
    amount = Column(Float)
    amplitude = Column(Float)
    change_percent = Column(Float)
    change = Column(Float)
    turnover_rate = Column(Float)
    adjust = Column(String(10)) 