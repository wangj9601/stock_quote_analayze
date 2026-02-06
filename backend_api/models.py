"""
数据库模型定义
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Float, Date, Text, UniqueConstraint, Index, JSON
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
    
    # 微信推送相关字段
    wechat_openid = Column(String(100), nullable=True, index=True)  # 微信OpenID
    wechat_type = Column(String(20), nullable=True)  # 'personal' 或 'enterprise'
    
    watchlists = relationship("Watchlist", back_populates="user")
    watchlist_groups = relationship("WatchlistGroup", back_populates="user")
    push_config = relationship("UserPushConfig", back_populates="user", uselist=False)
    push_records = relationship("PushRecord", back_populates="user")

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

class MAIndicators(Base):
    """MA移动平均线指标数据表（A股和港股共用）"""
    __tablename__ = 'ma_indicators'
    code = Column(String, primary_key=True)
    date = Column(String, primary_key=True)  # 使用String类型以兼容A股Date和港股String
    market_type = Column(String, primary_key=True)  # 'CN' 或 'HK'
    ma5 = Column(Float)  # 5日移动平均
    ma10 = Column(Float)  # 10日移动平均
    ma20 = Column(Float)  # 20日移动平均
    ma30 = Column(Float)  # 30日移动平均
    ma60 = Column(Float)  # 60日移动平均
    ma120 = Column(Float)  # 120日移动平均
    ma200 = Column(Float)  # 200日移动平均
    created_at = Column(DateTime, default=datetime.now)


class BOLLIndicators(Base):
    """BOLL指标数据表（A股和港股共用）"""
    __tablename__ = 'boll_indicators'
    code = Column(String, primary_key=True)
    date = Column(String, primary_key=True)  # 使用String类型以兼容A股Date和港股String
    market_type = Column(String, primary_key=True)  # 'CN' 或 'HK'
    mid = Column(Float)  # 中轨线 (通常为20日收盘价简单平均线)
    upper = Column(Float)  # 上轨线 (中轨线 + K倍标准差)
    lower = Column(Float)  # 下轨线 (中轨线 - K倍标准差)
    created_at = Column(DateTime, default=datetime.now)



class MAVOLIndicators(Base):
    """MAVOL成交量移动平均线指标数据表（A股和港股共用）"""
    __tablename__ = 'mavol_indicators'
    code = Column(String, primary_key=True)
    date = Column(String, primary_key=True)  # 使用String类型以兼容A股Date和港股String
    market_type = Column(String, primary_key=True)  # 'CN' 或 'HK'
    mavol5 = Column(Float)  # 5日成交量移动平均
    mavol10 = Column(Float)  # 10日成交量移动平均
    mavol20 = Column(Float)  # 20日成交量移动平均
    mavol30 = Column(Float)  # 30日成交量移动平均
    mavol60 = Column(Float)  # 60日成交量移动平均
    mavol120 = Column(Float)  # 120日成交量移动平均
    mavol200 = Column(Float)  # 200日成交量移动平均
    created_at = Column(DateTime, default=datetime.now)


class MeanFrequencyResonanceIndicators(Base):
    """均值频率共振量化交易指标数据表（A股和港股共用）"""
    __tablename__ = 'mean_frequency_resonance_indicators'
    code = Column(String, primary_key=True)
    date = Column(String, primary_key=True)  # 使用String类型以兼容A股Date和港股String
    market_type = Column(String, primary_key=True)  # 'CN' 或 'HK'
    
    macro_displacement_delta = Column(Float)  # 宏观位移 Delta (d20 - d1)
    amplitude = Column(Float, nullable=True)  # 行情振幅 |Δ|
    ratio_d20 = Column(Float, nullable=True)  # 幅度比例 Δ/d₂₀
    ratio_d1 = Column(Float, nullable=True)   # 幅度比例 Δ/d₁
    instant_deviation = Column(Float)         # 即时偏离度 (d20 - d) (Close - MA20)
    rising_days_z = Column(Integer)           # 上涨的天数 (Z)
    falling_days_f = Column(Integer)          # 下跌的天数 (F)
    efficiency_m20_minus_m = Column(Float)    # 进出效率指标 (m20 - m) (Vol - MAVOL20)
    
    ma20_d = Column(Float)                    # 移动平均线 MA20 (d)
    mavol20_m = Column(Float)                 # 移动平均成交量 MAVOL20 (m)
    bias = Column(Float)                      # 乖离率 (Bias) = (Pt - d) / d

    d1 = Column(Float, nullable=True)         # 周期起点收盘价 d₁
    d1_date = Column(String, nullable=True)   # d₁ 对应的交易日期 YYYY-MM-DD
    d20 = Column(Float, nullable=True)        # 周期末/当日收盘价 d₂₀
    d20_date = Column(String, nullable=True)  # d₂₀ 对应的交易日期 YYYY-MM-DD

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
    

class TradingJournalLog(Base):
    """交易日志（个人复盘）：支持每日、每周"""

    __tablename__ = 'trading_journal_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    log_type = Column(String(10), nullable=False, index=True)  # daily / weekly

    # daily: log_date；weekly: week_start
    log_date = Column(Date, nullable=True, index=True)
    week_start = Column(Date, nullable=True, index=True)

    mood = Column(String(20), nullable=True)
    score = Column(String(5), nullable=True)
    content = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint('user_id', 'log_type', 'log_date', 'week_start', name='uq_trading_journal_user_type_date'),
    )


class TradeExecutionLog(Base):
    """单笔交易执行日志"""
    __tablename__ = 'trade_execution_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    stock_code = Column(String(20), nullable=False)
    stock_name = Column(String(50))
    trade_date = Column(Date, nullable=False)
    
    # 交易前的思路
    entry_thinking = Column(Text)     # 进场理由 & 是否符合系统
    market_context = Column(Text)     # 市场环境
    
    # 交易参数
    buy_price = Column(Float)
    position_size = Column(String(50)) # 仓位
    stop_loss = Column(Float)
    take_profit = Column(Float)
    
    # 结果与盘后
    strictly_execute = Column(String(50)) # 是否严格执行 (e.g., "严格执行", "偏差较大")
    emotional_trading = Column(String(50)) # 是否情绪化 (e.g., "无", "轻微", "严重")
    content = Column(Text)                # 交易结果总结
    
    image_url = Column(String(500))       # 截图
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


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
    indicators: Optional[List[str]] = None  # 需要生成的技术指标列表
    sync_from_realtime: bool = False  # 新增：是否从实时行情表同步到历史行情表

class DataCollectionResponse(BaseModel):
    """数据采集响应模型"""
    task_id: str
    status: str
    message: str
    start_date: str
    end_date: str
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

class RealtimeCollectionRequest(BaseModel):
    """实时数据采集请求模型"""
    market: str = 'CN'  # CN: A股, HK: 港股
    stock_code: Optional[str] = None  # 单个股票采集时填写
    full_collection_mode: bool = False  # 全量采集

class RealtimeCollectionResponse(BaseModel):
    """实时数据采集响应模型"""
    task_id: str
    status: str
    message: str
    market: str = 'CN'
    stock_code: Optional[str] = None
    full_collection_mode: bool = False

class TushareHistoricalCollectionRequest(BaseModel):
    """TuShare历史数据采集请求模型"""
    start_date: str
    end_date: str
    force_update: bool = False  # 强制更新：如果已存在数据，先删除后插入
    indicators: Optional[List[str]] = None  # 需要生成的技术指标列表（参考AkShare）

# PVFRS回测相关模型
class PVFRSBacktestTask(Base):
    """PVFRS回测任务表"""
    __tablename__ = "pvfrs_backtest_tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(50), unique=True, nullable=False, index=True)
    mode = Column(String(20), nullable=False)  # single, batch, optimize
    stock_codes = Column(Text)  # JSON格式存储股票代码列表
    market = Column(String(10), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    initial_capital = Column(Float, nullable=False)
    status = Column(String(20), default="running")  # running, completed, failed, cancelled
    progress = Column(Integer, default=0)  # 0-100
    current_step = Column(String(50))  # 当前步骤描述
    error_message = Column(Text)  # 错误信息
    created_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime, nullable=True)

class PVFRSBacktestResult(Base):
    """PVFRS回测结果表"""
    __tablename__ = "pvfrs_backtest_results"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(50), ForeignKey("pvfrs_backtest_tasks.task_id"), nullable=False, index=True)
    stock_code = Column(String(20), nullable=False, index=True)
    market = Column(String(10), nullable=False)
    backtest_date = Column(Date, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    initial_capital = Column(Float, nullable=False)
    final_capital = Column(Float, nullable=False)
    total_return = Column(Float, nullable=False)
    annual_return = Column(Float, nullable=False)
    max_drawdown = Column(Float, nullable=False)
    sharpe_ratio = Column(Float, nullable=False)
    win_rate = Column(Float, nullable=False)
    profit_factor = Column(Float, nullable=False)
    total_trades = Column(Integer, nullable=False)
    avg_holding_period = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    
    # 关联任务
    task = relationship("PVFRSBacktestTask", backref="results")

class PVFRSTradeRecord(Base):
    """PVFRS交易记录表"""
    __tablename__ = "pvfrs_trade_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    result_id = Column(Integer, ForeignKey("pvfrs_backtest_results.id"), nullable=False)
    stock_code = Column(String(20), nullable=False)
    market = Column(String(10), nullable=False)
    entry_date = Column(Date, nullable=False)
    exit_date = Column(Date, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=False)
    pnl = Column(Float, nullable=False)
    pnl_percent = Column(Float, nullable=False)
    exit_reason = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    
    # 关联回测结果
    result = relationship("PVFRSBacktestResult", backref="trades")

class PVFRSEquityCurve(Base):
    """PVFRS收益曲线表"""
    __tablename__ = "pvfrs_equity_curves"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    result_id = Column(Integer, ForeignKey("pvfrs_backtest_results.id"), nullable=False)
    stock_code = Column(String(20), nullable=False)
    market = Column(String(10), nullable=False)
    curve_date = Column(Date, nullable=False)
    equity = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    
    # 关联回测结果
    result = relationship("PVFRSBacktestResult", backref="equity_curve")
    
    # 复合索引
    __table_args__ = (
        Index('idx_result_curve_date', 'result_id', 'curve_date'),
    )

class OneYangThreeLinesSignal(Base):
    """一阳穿三线策略信号表"""
    __tablename__ = "one_yang_three_lines_signals"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    signal_date = Column(Date, nullable=False, index=True)
    current_price = Column(Float)
    ma5 = Column(Float)
    ma10 = Column(Float)
    ma20 = Column(Float)
    ma30 = Column(Float)
    ma60 = Column(Float)
    ma120 = Column(Float)
    crossed_lines = Column(String(100))  # 穿越的均线组合，如"MA5+MA10+MA20"
    crossed_count = Column(Integer)  # 穿越数量
    volume_ratio = Column(Float)  # 成交量倍数
    turnover_rate = Column(Float)  # 换手率
    position_type = Column(String(20))  # 位置类型：低位/中位/高位
    retracement = Column(Float)  # 回撤幅度
    bias5 = Column(Float)  # 5日乖离率
    bias10 = Column(Float)  # 10日乖离率
    bias30 = Column(Float)  # 30日乖离率
    signal_score = Column(Integer)  # 信号质量评分
    risk_warnings = Column(Text)  # 风险提示，JSON格式存储列表
    created_at = Column(DateTime, default=datetime.now)
    
    # 唯一约束：同一股票同一日期只能有一条记录
    __table_args__ = (
        UniqueConstraint('code', 'signal_date', name='uq_one_yang_signal_code_date'),
    )

# 系统监控相关模型
class SystemMonitorMetric(Base):
    """系统监控指标表"""
    __tablename__ = "system_monitor_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(String(100), nullable=False, index=True)  # 指标名称
    metric_value = Column(Float, nullable=False)  # 指标值
    tags = Column(JSON, nullable=True)  # 标签（JSON格式）
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class SystemAlert(Base):
    """系统告警表"""
    __tablename__ = "system_alerts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(String(20), nullable=False, index=True)  # 告警级别：LOW, MEDIUM, HIGH, CRITICAL
    alert_type = Column(String(50), nullable=False, index=True)  # 告警类型：system, performance, business, security
    title = Column(String(200), nullable=False)  # 告警标题
    message = Column(Text, nullable=False)  # 告警消息
    source = Column(String(100), nullable=False, default="system")  # 告警来源
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    acknowledged = Column(Boolean, nullable=False, default=False)  # 是否已确认
    acknowledged_at = Column(DateTime, nullable=True)  # 确认时间
    acknowledged_by = Column(String(100), nullable=True)  # 确认人
    alert_metadata = Column(JSON, nullable=True)  # 额外元数据
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class SystemServiceStatus(Base):
    """系统服务状态表"""
    __tablename__ = "system_service_status"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    service_name = Column(String(100), nullable=False, unique=True, index=True)  # 服务名称
    status = Column(String(20), nullable=False)  # 服务状态：healthy, degraded, unhealthy, unknown
    last_check = Column(DateTime, nullable=False, default=datetime.utcnow)  # 最后检查时间
    response_time = Column(Float, nullable=True)  # 响应时间（毫秒）
    error_message = Column(Text, nullable=True)  # 错误消息
    service_metadata = Column(JSON, nullable=True)  # 额外信息
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class SystemAlertRule(Base):
    """系统告警规则表"""
    __tablename__ = "system_alert_rules"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, unique=True)  # 规则名称
    metric_name = Column(String(100), nullable=False)  # 监控指标名称
    condition = Column(String(10), nullable=False)  # 条件：>, <, >=, <=, ==
    threshold = Column(Float, nullable=False)  # 阈值
    level = Column(String(20), nullable=False)  # 告警级别
    alert_type = Column(String(50), nullable=False)  # 告警类型
    message_template = Column(Text, nullable=False)  # 消息模板
    enabled = Column(Boolean, nullable=False, default=True)  # 是否启用
    description = Column(Text, nullable=True)  # 规则描述
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class SystemPerformanceReport(Base):
    """系统性能报告表"""
    __tablename__ = "system_performance_reports"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    report_name = Column(String(200), nullable=False)  # 报告名称
    report_type = Column(String(50), nullable=False)  # 报告类型：daily, weekly, monthly
    period_start = Column(DateTime, nullable=False)  # 报告周期开始时间
    period_end = Column(DateTime, nullable=False)  # 报告周期结束时间
    
    # 性能指标汇总
    avg_cpu_usage = Column(Float, nullable=True)  # 平均CPU使用率
    max_cpu_usage = Column(Float, nullable=True)  # 最大CPU使用率
    avg_memory_usage = Column(Float, nullable=True)  # 平均内存使用率
    max_memory_usage = Column(Float, nullable=True)  # 最大内存使用率
    avg_disk_usage = Column(Float, nullable=True)  # 平均磁盘使用率
    
    # 告警统计
    total_alerts = Column(Integer, nullable=False, default=0)  # 总告警数
    critical_alerts = Column(Integer, nullable=False, default=0)  # 严重告警数
    high_alerts = Column(Integer, nullable=False, default=0)  # 高级告警数
    medium_alerts = Column(Integer, nullable=False, default=0)  # 中级告警数
    low_alerts = Column(Integer, nullable=False, default=0)  # 低级告警数
    
    # 服务可用性
    service_uptime = Column(Float, nullable=True)  # 服务可用性百分比
    
    report_data = Column(JSON, nullable=True)  # 详细报告数据
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# 微信每日报告推送相关模型
class UserPushConfig(Base):
    """用户推送配置表"""
    __tablename__ = "user_push_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    
    # 推送开关
    enabled = Column(Boolean, default=True, nullable=False)
    
    # 推送渠道配置 (JSON格式: ["wechat", "email"])
    channels = Column(JSON, default=["wechat"], nullable=False)
    
    # 推送时间配置 (JSON格式: ["09:30", "15:30"])
    push_times = Column(JSON, default=["09:30", "15:30"], nullable=False)
    
    # 报告类型: 'summary' 或 'detailed'
    report_type = Column(String(20), default="summary", nullable=False)
    
    # 股票范围配置 (JSON格式: null表示全部, 或["000001", "600000"])
    stock_codes = Column(JSON, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    user = relationship("User", back_populates="push_config")


class PushRecord(Base):
    """推送记录表"""
    __tablename__ = "push_records"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # 推送信息
    push_date = Column(Date, nullable=False, index=True)
    push_time = Column(String(10), nullable=False)  # "09:30"
    report_type = Column(String(20), nullable=False)  # 'summary' 或 'detailed'
    
    # 推送渠道和状态 (JSON格式)
    # {"wechat": "success", "email": "failed"}
    channel_status = Column(JSON, nullable=False)
    
    # 整体状态: 'pending', 'processing', 'success', 'partial_success', 'failed'
    status = Column(String(20), default="pending", nullable=False, index=True)
    
    # 报告文件路径
    report_file_path = Column(String(500), nullable=True)
    
    # 错误信息 (JSON格式: {"wechat": "error msg", "email": null})
    error_messages = Column(JSON, nullable=True)
    
    # 重试信息
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # 关系
    user = relationship("User", back_populates="push_records")
