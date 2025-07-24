from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Float, Date
from backend_core.database.db import Base

class HistoricalQuotes(Base):
    __tablename__ = 'historical_quotes'
    # id = Column(Integer, primary_key=True, autoincrement=True)
    #code = Column(String(20), nullable=False)
    #date = Column(Date, nullable=False)
    code = Column(String, primary_key=True)
    ts_code = Column(String)
    name = Column(String)
    market = Column(String)
    date = Column(Date, primary_key=True)
    open = Column(Float)
    close = Column(Float)
    high = Column(Float)
    low = Column(Float)
    pre_close = Column(Float)
    volume = Column(Integer)
    amount = Column(Float)
    amplitude = Column(Float)
    change_percent = Column(Float)
    change = Column(Float)
    turnover_rate = Column(Float)
    collected_source = Column(String)
    #adjust = Column(String(10)) 
    collected_date = Column(DateTime, default=datetime.now) 