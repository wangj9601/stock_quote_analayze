"""
数据库模型定义
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Float, Date, Text, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

# SQLAlchemy 模型
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user")
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.now)
    last_login = Column(DateTime, nullable=True)
    
    watchlists = relationship("Watchlist", back_populates="user")
    watchlist_groups = relationship("WatchlistGroup", back_populates="user")

class Admin(Base):
    __tablename__ = "admins"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="admin")
    created_at = Column(DateTime, default=datetime.now)
    last_login = Column(DateTime, nullable=True)

class Watchlist(Base):
    __tablename__ = "watchlist"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stock_code = Column(String, nullable=False)
    stock_name = Column(String, nullable=False)
    group_name = Column(String, default="default")
    created_at = Column(DateTime, default=datetime.now)
    
    user = relationship("User", back_populates="watchlists")

class WatchlistGroup(Base):
    __tablename__ = "watchlist_groups"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    group_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    
    user = relationship("User", back_populates="watchlist_groups")

class StockBasicInfo(Base):
    __tablename__ = "stock_basic_info"
    
    #id = Column(Integer, primary_key=True, index=True)
    #code = Column(String, unique=True, nullable=False)
    code = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    #industry = Column(String, nullable=True)
    #market = Column(String, nullable=True)
    #created_at = Column(DateTime, default=datetime.now)
    #updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class StockBasicInfoHK(Base):
    __tablename__ = "stock_basic_info_hk"
    
    code = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    create_date = Column(DateTime)

# Pydantic 模型（用于API请求和响应）
class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str
    role: Optional[str] = "user"

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    status: Optional[str] = None

class UserInDB(UserBase):
    id: int
    role: str
    status: str
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True

class AdminBase(BaseModel):
    username: str

class AdminCreate(AdminBase):
    password: str

class AdminInDB(AdminBase):
    id: int
    role: str
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True

class WatchlistBase(BaseModel):
    stock_code: str
    stock_name: str
    group_name: str = "default"

class WatchlistCreate(WatchlistBase):
    pass

class WatchlistInDB(WatchlistBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class WatchlistGroupBase(BaseModel):
    group_name: str

class WatchlistGroupCreate(WatchlistGroupBase):
    user_id: int

class WatchlistGroupInDB(WatchlistGroupBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class StockBasicInfoBase(BaseModel):
    code: str
    name: str
    industry: Optional[str] = None
    market: Optional[str] = None

class StockBasicInfoInDB(StockBasicInfoBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Optional[UserInDB] = None

    class Config:
        from_attributes = True

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None
    is_admin: bool = False

class QuoteData(Base):
    """行情数据模型"""
    __tablename__ = "quote_data"
    
    id = Column(Integer, primary_key=True, index=True)
    stock_code = Column(String(10), nullable=False, index=True)
    stock_name = Column(String(50), nullable=False)
    trade_date = Column(Date, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    last_price = Column(Float, nullable=False)
    pre_close = Column(Float, nullable=False)
    change_percent = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    __table_args__ = (
        # 添加联合唯一索引
        {'sqlite_autoincrement': True},
    )

class QuoteDataCreate(BaseModel):
    """行情数据创建模型"""
    stock_code: str
    stock_name: str
    trade_date: datetime
    open: float
    high: float
    low: float
    last_price: float
    pre_close: float
    change_percent: float
    volume: float
    amount: float

class QuoteDataInDB(QuoteDataCreate):
    """行情数据数据库模型"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class QuoteSyncTask(Base):
    """行情数据同步任务模型"""
    __tablename__ = "quote_sync_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    task_type = Column(String(20), nullable=False)  # 'realtime' 或 'historical'
    status = Column(String(20), nullable=False)  # 'pending', 'running', 'completed', 'failed'
    progress = Column(Float, default=0.0)
    error_message = Column(String(200), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class QuoteSyncTaskCreate(BaseModel):
    """行情数据同步任务创建模型"""
    task_type: str
    status: str = "pending"
    progress: float = 0.0
    error_message: Optional[str] = None

class QuoteSyncTaskInDB(QuoteSyncTaskCreate):
    """行情数据同步任务数据库模型"""
    id: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class StockRealtimeQuote(Base):
    __tablename__ = "stock_realtime_quote"
    code = Column(String, primary_key=True)
    trade_date = Column(String, primary_key=True)
    name = Column(String)
    current_price = Column(Float)
    change_percent = Column(Float)
    volume = Column(Float)
    amount = Column(Float)
    high = Column(Float)
    low = Column(Float)
    open = Column(Float)
    pre_close = Column(Float)
    turnover_rate = Column(Float)
    pe_dynamic = Column(Float)
    total_market_value = Column(Float)
    pb_ratio = Column(Float)
    circulating_market_value = Column(Float)
    update_time = Column(DateTime)
    
    __table_args__ = (
        UniqueConstraint('code', 'trade_date', name='uq_stock_realtime_quote_code_date'),
    )

class StockRealtimeQuoteHK(Base):
    __tablename__ = "stock_realtime_quote_hk"
    code = Column(String, primary_key=True)
    trade_date = Column(String, primary_key=True)
    name = Column(String)
    english_name = Column(String)
    current_price = Column(Float)
    change_percent = Column(Float)
    change_amount = Column(Float)
    volume = Column(Float)
    amount = Column(Float)
    high = Column(Float)
    low = Column(Float)
    open = Column(Float)
    pre_close = Column(Float)
    update_time = Column(DateTime)
    
    __table_args__ = (
        UniqueConstraint('code', 'trade_date', name='uq_stock_realtime_quote_hk_code_date'),
    )

class StockNoticeReport(Base):
    __tablename__ = "stock_notice_report"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), index=True)
    name = Column(String(50))
    notice_title = Column(String(200))
    notice_type = Column(String(50))
    publish_date = Column(DateTime)
    url = Column(String(300))
    created_at = Column(DateTime)

class StockNews(Base):
    __tablename__ = "stock_news"
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), index=True)
    title = Column(String(200))
    content = Column(Text)
    keywords = Column(String(100))
    publish_time = Column(DateTime)
    source = Column(String(100))
    url = Column(String(300))
    summary = Column(Text)
    type = Column(String(20))
    rating = Column(String(50))
    target_price = Column(String(50))
    created_at = Column(DateTime)
    
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )

class StockResearchReport(Base):
    __tablename__ = "stock_research_reports"
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), index=True)
    stock_name = Column(String(50))
    report_name = Column(String(200))
    dongcai_rating = Column(String(50))
    institution = Column(String(100))
    monthly_report_count = Column(Integer)
    profit_2024 = Column(Float)
    pe_2024 = Column(Float)
    profit_2025 = Column(Float)
    pe_2025 = Column(Float)
    profit_2026 = Column(Float)
    pe_2026 = Column(Float)
    industry = Column(String(100))
    report_date = Column(DateTime)
    pdf_url = Column(String(300))
    updated_at = Column(DateTime)
    
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )

class IndexRealtimeQuotes(Base):
    __tablename__ = "index_realtime_quotes"
    code = Column(String(10), primary_key=True)
    name = Column(String(50), nullable=False)
    price = Column(Float)
    change = Column(Float)
    pct_chg = Column(Float)
    high = Column(Float)
    low = Column(Float)
    open = Column(Float)
    pre_close = Column(Float)
    volume = Column(Float)
    amount = Column(Float)
    amplitude = Column(Float)
    turnover = Column(Float)
    pe = Column(Float)
    volume_ratio = Column(Float)
    update_time = Column(String, index=True)  # 改为String类型匹配数据库
    collect_time = Column(String)  # 添加缺失的字段
    index_spot_type = Column(Integer)  # 添加缺失的字段

class IndustryBoardRealtimeQuotes(Base):
    __tablename__ = "industry_board_realtime_quotes"
    board_code = Column(String(20), primary_key=True)
    board_name = Column(String(100))
    latest_price = Column(Float)
    change_amount = Column(Float)
    change_percent = Column(Float)
    total_market_value = Column(Float)
    volume = Column(Float)
    amount = Column(Float)
    turnover_rate = Column(Float)
    leading_stock_name = Column(String(100))
    leading_stock_code = Column(String(20))
    leading_stock_change_percent = Column(Float)
    update_time = Column(String)  # 改为String类型匹配数据库

class HKIndexBasicInfo(Base):
    """港股指数基础信息表"""
    __tablename__ = "hk_index_basic_info"
    code = Column(String(10), primary_key=True)
    name = Column(String(50), nullable=False)
    english_name = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class HKIndexRealtimeQuotes(Base):
    """港股指数实时行情表"""
    __tablename__ = "hk_index_realtime_quotes"
    code = Column(String(10), primary_key=True)
    trade_date = Column(String, primary_key=True)  # 交易日期，格式：YYYY-MM-DD
    name = Column(String(50), nullable=False)
    price = Column(Float)
    change = Column(Float)
    pct_chg = Column(Float)
    high = Column(Float)
    low = Column(Float)
    open = Column(Float)
    pre_close = Column(Float)
    volume = Column(Float)
    amount = Column(Float)
    update_time = Column(String, index=True)
    collect_time = Column(String)

class HKIndexHistoricalQuotes(Base):
    """港股指数历史行情表"""
    __tablename__ = "hk_index_historical_quotes"
    code = Column(String(10), primary_key=True)
    name = Column(String(50), nullable=False)
    date = Column(String, primary_key=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    amount = Column(Float)
    change = Column(Float)
    pct_chg = Column(Float)
    collected_source = Column(String)
    collected_date = Column(DateTime, default=datetime.now)

class HistoricalQuotes(Base):
    __tablename__ = 'historical_quotes'
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
    collected_date = Column(DateTime, default=datetime.now) 
    # 新增字段
    cumulative_change_percent = Column(Float)  # 累计升跌%
    five_day_change_percent = Column(Float)    # 5天升跌%
    ten_day_change_percent = Column(Float)     # 10天升跌%
    thirty_day_change_percent = Column(Float)  # 30天升跌%
    sixty_day_change_percent = Column(Float)   # 60天升跌%
    remarks = Column(String)                   # 备注

class HistoricalQuotesHK(Base):
    __tablename__ = 'historical_quotes_hk'
    code = Column(String, primary_key=True)
    ts_code = Column(String)
    name = Column(String)
    english_name = Column(String)
    date = Column(String, primary_key=True)  # 港股使用TEXT类型
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    pre_close = Column(Float)
    volume = Column(Float)
    amount = Column(Float)
    change_amount = Column(Float)  # 港股使用change_amount
    amplitude = Column(Float)
    turnover_rate = Column(Float)
    change_percent = Column(Float)
    five_day_change_percent = Column(Float)
    ten_day_change_percent = Column(Float)
    sixty_day_change_percent = Column(Float)
    thirty_day_change_percent = Column(Float)
    collected_source = Column(String)
    collected_date = Column(DateTime, default=datetime.now)

class MACDIndicators(Base):
    """MACD指标数据表（A股和港股共用）"""
    __tablename__ = 'macd_indicators'
    code = Column(String, primary_key=True)
    date = Column(String, primary_key=True)  # 使用String类型以兼容A股Date和港股String
    market_type = Column(String, primary_key=True)  # 'A股' 或 '港股'
    dif = Column(Float)  # DIF值（快线EMA12 - 慢线EMA26）
    dea = Column(Float)  # DEA值（DIF的9日EMA）
    macd = Column(Float)  # MACD柱状图值（DIF - DEA）
    ema12 = Column(Float)  # 12日指数移动平均
    ema26 = Column(Float)  # 26日指数移动平均
    created_at = Column(DateTime, default=datetime.now)


class KDJIndicators(Base):
    """KDJ指标数据表（A股和港股共用）"""
    __tablename__ = 'kdj_indicators'
    code = Column(String, primary_key=True)
    date = Column(String, primary_key=True)  # 使用String类型以兼容A股Date和港股String
    market_type = Column(String, primary_key=True)  # 'CN' 或 'HK'
    k = Column(Float)
    d = Column(Float)
    j = Column(Float)
    rsv = Column(Float)
    created_at = Column(DateTime, default=datetime.now)

class RSIIndicators(Base):
    """RSI指标数据表（A股和港股共用）"""
    __tablename__ = 'rsi_indicators'
    code = Column(String, primary_key=True)
    date = Column(String, primary_key=True)  # 使用String类型以兼容A股Date和港股String
    market_type = Column(String, primary_key=True)  # 'CN' 或 'HK'
    rsi6 = Column(Float)
    rsi12 = Column(Float)
    rsi24 = Column(Float)
    created_at = Column(DateTime, default=datetime.now)


class TradingNotes(Base):
    __tablename__ = 'trading_notes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False)
    trade_date = Column(Date, nullable=False)
    notes = Column(Text)
    strategy_type = Column(String(50))  # 策略类型：如"买入信号"、"卖出信号"、"观察"等
    risk_level = Column(String(20))     # 风险等级：如"低"、"中"、"高"
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_by = Column(String(50))     # 创建用户
    

class SimTradeAccount(Base):
    """模拟交易账户"""
    __tablename__ = "sim_trade_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    initial_capital = Column(Float, default=0.0)
    cash_balance = Column(Float, default=0.0)
    total_market_value = Column(Float, default=0.0)
    total_profit = Column(Float, default=0.0)
    total_profit_rate = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class SimTradePosition(Base):
    """模拟交易持仓"""
    __tablename__ = "sim_trade_positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stock_code = Column(String(20), nullable=False)
    stock_name = Column(String(50))
    quantity = Column(Integer, nullable=False, default=0)
    avg_price = Column(Float, default=0.0)
    last_price = Column(Float, default=0.0)
    market_value = Column(Float, default=0.0)
    unrealized_profit = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint('user_id', 'stock_code', name='uq_sim_trade_position_user_code'),
    )


class SimTradeOrder(Base):
    """模拟交易订单"""
    __tablename__ = "sim_trade_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stock_code = Column(String(20), nullable=False)
    stock_name = Column(String(50))
    side = Column(String(10), nullable=False)  # buy / sell
    price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    fee = Column(Float, default=0.0)
    status = Column(String(20), default="filled")
    remark = Column(String(200))
    realized_profit = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.now)

# 数据采集相关模型
class DataCollectionRequest(BaseModel):
    """数据采集请求模型"""
    start_date: str
    end_date: str
    stock_codes: Optional[List[str]] = None
    test_mode: bool = False
    full_collection_mode: bool = False  # 新增：全量采集模式
    market: str = 'CN'  # CN: A股, HK: 港股
    force_update: bool = False  # 强制更新：如果为True，即使数据已存在也会重新采集并更新

class DataCollectionResponse(BaseModel):
    """数据采集响应模型"""
    task_id: str
    status: str
    message: str
    start_date: str
    end_date: str
    stock_codes: Optional[List[str]] = None
    test_mode: bool = False
    full_collection_mode: bool = False  # 新增：全量采集模式
    market: str = 'CN'

class DataCollectionStatus(BaseModel):
    """数据采集状态模型"""
    task_id: str
    status: str  # running, completed, failed, cancelled
    progress: int  # 0-100
    total_stocks: int
    processed_stocks: int
    success_count: int
    failed_count: int
    collected_count: int
    skipped_count: int
    start_time: datetime
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    failed_details: List[str] = []

class TushareHistoricalCollectionRequest(BaseModel):
    """TuShare历史数据采集请求模型"""
    start_date: str
    end_date: str
    force_update: bool = False  # 强制更新：如果已存在数据，先删除后插入 