from datetime import datetime
from sqlalchemy import Column, DateTime, String, Float
from backend_core.database.db import Base

class MAIndicators(Base):
    """MA移动平均线指标数据表（A股和港股共用）"""
    __tablename__ = 'ma_indicators'
    code = Column(String, primary_key=True)
    date = Column(String, primary_key=True)  # 使用String类型以兼容A股Date和港股String
    market_type = Column(String, primary_key=True)  # 'A股' 或 '港股'
    ma5 = Column(Float)  # 5日移动平均
    ma10 = Column(Float)  # 10日移动平均
    ma20 = Column(Float)  # 20日移动平均
    ma30 = Column(Float)  # 30日移动平均
    ma60 = Column(Float)  # 60日移动平均
    ma120 = Column(Float)  # 120日移动平均
    ma200 = Column(Float)  # 200日移动平均
    created_at = Column(DateTime, default=datetime.now)

