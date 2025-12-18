from datetime import datetime
from sqlalchemy import Column, DateTime, String, Float
from backend_core.database.db import Base

class MACDIndicators(Base):
    """MACD指标数据表（A股和港股共用）"""
    __tablename__ = 'macd_indicators'
    code = Column(String, primary_key=True)
    date = Column(String, primary_key=True)  # 使用String类型以兼容A股Date和港股String
    market_type = Column(String, primary_key=True)  # 'CN' 或 'HK'
    dif = Column(Float)  # DIF值（快线EMA12 - 慢线EMA26）
    dea = Column(Float)  # DEA值（DIF的9日EMA）
    macd = Column(Float)  # MACD柱状图值（DIF - DEA）
    ema12 = Column(Float)  # 12日指数移动平均
    ema26 = Column(Float)  # 26日指数移动平均
    created_at = Column(DateTime, default=datetime.now)

