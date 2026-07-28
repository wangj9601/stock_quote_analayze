"""
数据库模型定义
"""

from datetime import datetime, date
import numbers
from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Float, Date, Text, UniqueConstraint, Index, JSON, TypeDecorator, cast, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import operators as sa_operators
from sqlalchemy.sql.elements import ClauseElement, BindParameter

Base = declarative_base()


class _StockCodeTextPKComparator(TypeDecorator.Comparator):
    """对比较右侧生成 CAST(... AS VARCHAR)，避免 PostgreSQL 报 text = integer。

    纯标量（如 2709）会先变成 BindParameter；若仅处理「非 ClauseElement」会漏掉 BindParameter，
    仍会按 integer 绑定，故 BindParameter 也需包一层 CAST。
    """

    def operate(self, op, *other, **kwargs):
        if other and op in (sa_operators.eq, sa_operators.ne):
            o = other[0]
            impl = self.expr.type
            length = 32
            inner = getattr(impl, "impl", None)
            if inner is not None and getattr(inner, "length", None):
                length = inner.length
            elif getattr(impl, "length", None):
                length = impl.length
            str_type = String(length)
            if isinstance(o, BindParameter):
                return super().operate(op, cast(o, str_type), **kwargs)
            if not isinstance(o, ClauseElement):
                return super().operate(op, cast(o, str_type), **kwargs)
        return super().operate(op, *other, **kwargs)


class StockCodeTextPK(TypeDecorator):
    """
    stock_basic_info / stock_basic_info_hk 主键 code 在库中为文本。
    ORM 比较 `StockBasicInfo.code == 688114` 时，底层 String 的 TypeEngine.coerce_compared_value
    会把右侧推断成 Integer，导致 PostgreSQL 出现 text = integer。
    此处显式固定比较类型为本装饰器（字符串语义），并统一 bind/result 为 str。
    """

    impl = String(32)
    cache_ok = True
    comparator_factory = _StockCodeTextPKComparator

    def coerce_compared_value(self, op, value: Any):
        """保证与 int/float/numpy 标量比较时右侧类型为本装饰器，不委托为 Integer。

        SQLAlchemy 2.x 中若将 ``coerce_compared_value`` 完全交给 ``String.impl``，
        对 Python ``int`` 可能解析为 ``Integer()``，绑定参数按整数下发，触发 PG ``text = integer``。
        """
        if value is None:
            return self.impl.coerce_compared_value(op, value)
        if isinstance(value, bool):
            return self.impl.coerce_compared_value(op, value)
        if isinstance(value, (int, float, numbers.Integral, numbers.Real)):
            return self
        try:
            import numpy as np

            if isinstance(value, np.generic):
                return self
        except ImportError:
            pass
        return self.impl.coerce_compared_value(op, value)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        # 统一转为字符串，并移除首尾空格
        return str(value).strip()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return str(value).strip()

# SQLAlchemy 模型
class FrontendRole(Base):
    __tablename__ = "frontend_roles"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)

    permissions = relationship(
        "FrontendPermission",
        secondary="role_permissions",
        back_populates="roles",
    )
    users = relationship("User", back_populates="frontend_role")


class FrontendPermission(Base):
    __tablename__ = "frontend_permissions"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(200), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    level = Column(Integer, nullable=False)
    parent_code = Column(String(200), nullable=True)
    channel_code = Column(String(50), nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

    roles = relationship(
        "FrontendRole",
        secondary="role_permissions",
        back_populates="permissions",
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id = Column(Integer, ForeignKey("frontend_roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("frontend_permissions.id", ondelete="CASCADE"), primary_key=True)


class UserPermission(Base):
    """用户级权限覆盖：granted=True 额外授予，granted=False 相对角色撤销"""
    __tablename__ = "user_permissions"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("frontend_permissions.id", ondelete="CASCADE"), primary_key=True)
    granted = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", back_populates="permission_overrides")
    permission = relationship("FrontendPermission")


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user")
    role_id = Column(Integer, ForeignKey("frontend_roles.id"), nullable=True, index=True)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.now)
    last_login = Column(DateTime, nullable=True)
    
    # 微信推送相关字段
    wechat_openid = Column(String(100), nullable=True, index=True)  # 微信OpenID（公众号/个人）
    wechat_userid = Column(String(100), nullable=True, index=True)  # 企业微信成员UserID，通知发送时优先使用
    wechat_type = Column(String(20), nullable=True)  # 'personal' 或 'enterprise'
    
    frontend_role = relationship("FrontendRole", back_populates="users")
    permission_overrides = relationship("UserPermission", back_populates="user", cascade="all, delete-orphan")
    watchlists = relationship("Watchlist", back_populates="user")
    watchlist_groups = relationship("WatchlistGroup", back_populates="user")
    push_configs = relationship("UserPushConfig", back_populates="user", uselist=True)
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
    stock_code = Column(StockCodeTextPK(), nullable=False)
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
    # PostgreSQL 等库中 code 多为 text/varchar，与 Integer 绑定会导致 text=integer 比较错误
    code = Column(StockCodeTextPK(), primary_key=True, index=True)
    name = Column(String, nullable=False)
    industry = Column(Text, nullable=True)
    listing_date = Column(Text, nullable=True)
    total_shares = Column(Float, nullable=True)
    free_float_shares = Column(Float, nullable=True)
    shares_updated_at = Column(DateTime, nullable=True)
    collect_enabled = Column(Boolean, nullable=True, default=True)
    #market = Column(String, nullable=True)
    #created_at = Column(DateTime, default=datetime.now)
    #updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class StockBasicInfoHK(Base):
    __tablename__ = "stock_basic_info_hk"
    
    code = Column(StockCodeTextPK(), primary_key=True, index=True)
    name = Column(String, nullable=False)
    create_date = Column(DateTime)
    industry = Column(Text, nullable=True)
    listing_date = Column(Text, nullable=True)
    total_shares = Column(Float, nullable=True)
    free_float_shares = Column(Float, nullable=True)
    shares_updated_at = Column(DateTime, nullable=True)
    collect_enabled = Column(Boolean, nullable=True, default=True)

# Pydantic 模型（用于API请求和响应）
class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str
    role: Optional[str] = "user"
    role_id: Optional[int] = None

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    role_id: Optional[int] = None
    status: Optional[str] = None
    wechat_userid: Optional[str] = None  # 企业微信成员UserID，用于微信通知

class UserInDB(UserBase):
    id: int
    role: str
    role_id: Optional[int] = None
    status: str
    created_at: datetime
    last_login: Optional[datetime] = None
    wechat_userid: Optional[str] = None  # 企业微信成员UserID

    class Config:
        from_attributes = True


class FrontendRoleBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None


class FrontendRoleCreate(FrontendRoleBase):
    pass


class FrontendRoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class FrontendRoleInDB(FrontendRoleBase):
    id: int
    is_system: bool
    created_at: datetime

    class Config:
        from_attributes = True


class FrontendPermissionInDB(BaseModel):
    id: int
    code: str
    name: str
    level: int
    parent_code: Optional[str] = None
    channel_code: Optional[str] = None
    sort_order: int
    is_active: bool

    class Config:
        from_attributes = True


class PermissionTreeNode(BaseModel):
    id: int
    code: str
    name: str
    level: int
    parent_code: Optional[str] = None
    channel_code: Optional[str] = None
    sort_order: int
    children: List["PermissionTreeNode"] = []


class RolePermissionsUpdate(BaseModel):
    permission_codes: List[str]


class UserRoleInfo(BaseModel):
    code: str
    name: str


class PermissionsResponse(BaseModel):
    permissions: List[str]
    role: UserRoleInfo
    has_custom_permissions: bool = False


class UserPermissionsUpdate(BaseModel):
    permission_codes: List[str]


class UserPermissionsDetail(BaseModel):
    role: UserRoleInfo
    role_permission_codes: List[str]
    effective_permission_codes: List[str]
    override_count: int

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
    permissions: Optional[List[str]] = None
    role: Optional[UserRoleInfo] = None

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
    stock_code = Column(StockCodeTextPK(), nullable=False, index=True)
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
    code = Column(StockCodeTextPK(), primary_key=True)
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
    code = Column(StockCodeTextPK(), primary_key=True)
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

class IndustryBoardConstituent(Base):
    """东财行业板块成分股（board_code ↔ stock_code 多对多）。"""
    __tablename__ = "industry_board_constituents"
    board_code = Column(String(20), primary_key=True)
    stock_code = Column(String(20), primary_key=True)
    stock_name = Column(String(100))
    updated_at = Column(DateTime, default=datetime.now)


class ConceptBoardConstituent(Base):
    """东财概念板块成分股（board_code ↔ stock_code 多对多）。"""
    __tablename__ = "concept_board_constituents"
    board_code = Column(String(20), primary_key=True)
    stock_code = Column(String(20), primary_key=True)
    stock_name = Column(String(100))
    updated_at = Column(DateTime, default=datetime.now)


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
    up_count = Column(Integer)
    down_count = Column(Integer)
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
    code = Column(StockCodeTextPK(), primary_key=True)
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
    code = Column(StockCodeTextPK(), primary_key=True)
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
    code = Column(StockCodeTextPK(), primary_key=True)
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
    code = Column(StockCodeTextPK(), primary_key=True)
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
    code = Column(StockCodeTextPK(), primary_key=True)
    date = Column(String, primary_key=True)  # 使用String类型以兼容A股Date和港股String
    market_type = Column(String, primary_key=True)  # 'CN' 或 'HK'
    rsi6 = Column(Float)
    rsi12 = Column(Float)
    rsi24 = Column(Float)
    created_at = Column(DateTime, default=datetime.now)

class MAIndicators(Base):
    """MA移动平均线指标数据表（A股和港股共用）"""
    __tablename__ = 'ma_indicators'
    code = Column(StockCodeTextPK(), primary_key=True)
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
    code = Column(StockCodeTextPK(), primary_key=True)
    date = Column(String, primary_key=True)  # 使用String类型以兼容A股Date和港股String
    market_type = Column(String, primary_key=True)  # 'CN' 或 'HK'
    mid = Column(Float)  # 中轨线 (通常为20日收盘价简单平均线)
    upper = Column(Float)  # 上轨线 (中轨线 + K倍标准差)
    lower = Column(Float)  # 下轨线 (中轨线 - K倍标准差)
    created_at = Column(DateTime, default=datetime.now)



class MAVOLIndicators(Base):
    """MAVOL成交量移动平均线指标数据表（A股和港股共用）"""
    __tablename__ = 'mavol_indicators'
    code = Column(StockCodeTextPK(), primary_key=True)
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


class InfiniteCostIndicators(Base):
    """无穷成本均线 ic_price：有换手率时按文档 CYC∞ 递归；否则退化为累计成交额/累计成交量（全历史 VWAP）。
    cum_amount/cum_volume 为审计用累计额与股数；与通达信筹码 COST 不等价。行情 volume 为手时计算先×100。"""

    __tablename__ = "icost_indicators"
    code = Column(StockCodeTextPK(), primary_key=True)
    date = Column(String, primary_key=True)
    market_type = Column(String, primary_key=True)  # 'CN' 或 'HK'
    ic_price = Column(Float, nullable=True)
    cum_amount = Column(Float, nullable=True)
    cum_volume = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class MeanFrequencyResonanceIndicators(Base):
    """均值频率共振量化交易指标数据表（A股和港股共用）"""
    __tablename__ = 'mean_frequency_resonance_indicators'
    code = Column(StockCodeTextPK(), primary_key=True)
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
    ma60_d = Column(Float, nullable=True)     # 移动平均线 MA60（减分规则等）
    mavol20_m = Column(Float)                 # 移动平均成交量 MAVOL20 (m)
    bias = Column(Float)                      # 乖离率 (Bias) = (Pt - d) / d

    d1 = Column(Float, nullable=True)         # 周期起点收盘价 d₁
    d1_date = Column(String, nullable=True)   # d₁ 对应的交易日期 YYYY-MM-DD
    d20 = Column(Float, nullable=True)        # 周期末/当日收盘价 d₂₀
    d20_date = Column(String, nullable=True)  # d₂₀ 对应的交易日期 YYYY-MM-DD

    created_at = Column(DateTime, default=datetime.now)


class URTStrategyConfig(Base):
    """URT 上升趋势策略参数版本表：多版本 JSON 快照。"""

    __tablename__ = "urt_strategy_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    version_label = Column(String(32), nullable=True)
    description = Column(Text, nullable=True)
    config_params = Column(JSON, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    is_default = Column(Boolean, nullable=False, default=False, index=True)
    precompute_enabled = Column(Boolean, nullable=False, default=False, index=True)
    created_by = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class UrtTraceRecomputeTask(Base):
    """URT 信号历史强制重算任务（多 worker 共享进度）。"""

    __tablename__ = "urt_trace_recompute_tasks"

    task_id = Column(String(64), primary_key=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    progress = Column(Integer, nullable=False, default=0)
    message = Column(Text, nullable=True)
    code = Column(String(20), nullable=False, index=True)
    config_id = Column(Integer, nullable=False, index=True)
    config_name = Column(String(200), nullable=True)
    current = Column(Integer, nullable=False, default=0)
    total = Column(Integer, nullable=False, default=0)
    saved_count = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class URTSignalTrace(Base):
    """URT 信号预计算表：按 code + date + config_id 隔离。"""

    __tablename__ = "urt_signal_trace"

    code = Column(StockCodeTextPK(), primary_key=True)
    date = Column(String(20), primary_key=True)
    config_id = Column(
        Integer,
        ForeignKey("urt_strategy_configs.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    name = Column(String(100), nullable=True)
    buy_signal = Column(Boolean, nullable=True, index=True)
    score = Column(Float, nullable=True, index=True)
    signal_strength = Column(Float, nullable=True)
    close = Column(Float, nullable=True)
    open = Column(Float, nullable=True)
    ma20 = Column(Float, nullable=True)
    above_ma20 = Column(Boolean, nullable=True)
    yang_count_4 = Column(Integer, nullable=True)
    yang_count_5 = Column(Integer, nullable=True)
    yang_rule = Column(String(32), nullable=True)
    volume = Column(Float, nullable=True)
    avg_volume_20 = Column(Float, nullable=True)
    volume_multiple = Column(Float, nullable=True)
    volume_ratio = Column(Float, nullable=True)
    turnover_rate = Column(Float, nullable=True)
    score_detail = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (Index("idx_urt_trace_date_score", "date", "score"),)


class URTBacktestTask(Base):
    """URT 回测任务与报告摘要。"""

    __tablename__ = "urt_backtest_tasks"

    task_id = Column(String(64), primary_key=True)
    name = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False, index=True)
    progress = Column(Integer, default=0, nullable=False)
    message = Column(Text, nullable=True)
    config = Column(JSON, nullable=False)
    logs = Column(JSON, nullable=True)
    summary = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    details_path = Column(String(512), nullable=True)
    details_csv_bytes = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (Index("idx_urt_bt_status_created", "status", "created_at"),)


class GMSStrategyConfig(Base):
    """GMS 策略参数版本表：多版本 JSON 快照，支持默认版本与预计算标记。"""

    __tablename__ = "gms_strategy_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    version_label = Column(String(32), nullable=True)
    description = Column(Text, nullable=True)
    config_params = Column(JSON, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    is_default = Column(Boolean, nullable=False, default=False, index=True)
    precompute_enabled = Column(Boolean, nullable=False, default=False, index=True)
    parent_id = Column(Integer, ForeignKey("gms_strategy_configs.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class GMSSignalTrace(Base):
    """GMS 信号追溯记录表：存储每只股票每日的 GMS 策略指标与信号（按 config_id 隔离）"""
    __tablename__ = 'gms_signal_trace'
    code = Column(StockCodeTextPK(), primary_key=True)
    date = Column(String(20), primary_key=True)
    market_type = Column(String(10), primary_key=True)
    config_id = Column(
        Integer,
        ForeignKey("gms_strategy_configs.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        default=1,
    )

    score_total = Column(Float, nullable=True)
    score_accumulation = Column(Float, nullable=True)
    score_momentum = Column(Float, nullable=True)
    signal_strength = Column(Float, nullable=True)
    buy_type = Column(String(20), nullable=True)
    left_buy_signal = Column(Boolean, nullable=True)
    right_buy_signal = Column(Boolean, nullable=True)
    sell_signal = Column(Boolean, nullable=True)
    accumulation_grade = Column(String(5), nullable=True)
    momentum_grade = Column(String(20), nullable=True)
    delta = Column(Float, nullable=True)
    d = Column(Float, nullable=True)
    ratio_d20 = Column(Float, nullable=True)
    ratio_d1 = Column(Float, nullable=True)
    fz_ratio = Column(Float, nullable=True)
    volume_ratio = Column(Float, nullable=True)
    instant_deviation = Column(Float, nullable=True)
    rising_days = Column(Integer, nullable=True)
    falling_days = Column(Integer, nullable=True)
    score_acc_fz = Column(Float, nullable=True)
    score_acc_balance = Column(Float, nullable=True)
    score_acc_volume = Column(Float, nullable=True)
    score_mom_ratio_d1 = Column(Float, nullable=True)
    score_mom_deviation = Column(Float, nullable=True)
    score_mom_volume = Column(Float, nullable=True)
    acc_fz_judge = Column(String(50), nullable=True)
    acc_balance_judge = Column(String(50), nullable=True)
    acc_volume_judge = Column(String(50), nullable=True)
    mom_ratio_d1_judge = Column(String(50), nullable=True)
    mom_deviation_judge = Column(String(50), nullable=True)
    mom_volume_judge = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    risk_tags = Column(JSON, nullable=True)
    score_detail = Column(JSON, nullable=True)


class GmsTraceRecomputeTask(Base):
    """GMS 信号追溯强制重算任务（多 worker 共享进度）"""
    __tablename__ = "gms_trace_recompute_tasks"

    task_id = Column(String(64), primary_key=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    progress = Column(Integer, nullable=False, default=0)
    message = Column(Text, nullable=True)
    code = Column(String(20), nullable=False, index=True)
    market_type = Column(String(10), nullable=False, default="CN")
    config_id = Column(Integer, nullable=False, index=True)
    config_name = Column(String(200), nullable=True)
    current = Column(Integer, nullable=False, default=0)
    total = Column(Integer, nullable=False, default=0)
    saved_count = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class GMSStrategyVersion(Base):
    """GMS 观察股分组表（非参数版本）；可选绑定 gms_strategy_configs。"""
    __tablename__ = "gms_strategy_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_code = Column(String(50), nullable=False, index=True)
    version_name = Column(String(100), nullable=False)
    version_no = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    config_id = Column(Integer, ForeignKey("gms_strategy_configs.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    __table_args__ = (
        UniqueConstraint("strategy_code", "version_no", name="uq_gms_strategy_code_version_no"),
    )


class GMSStrategyVersionStock(Base):
    """GMS策略版本观察股关系表。"""
    __tablename__ = "gms_strategy_version_stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version_id = Column(Integer, ForeignKey("gms_strategy_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    market = Column(String(10), nullable=False, index=True)  # A/HK
    stock_code = Column(StockCodeTextPK(), nullable=False, index=True)
    stock_name = Column(String(100), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="active")
    is_verified = Column(Boolean, nullable=False, default=False)
    remark = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    __table_args__ = (
        UniqueConstraint("version_id", "market", "stock_code", name="uq_gms_version_market_code"),
        Index("idx_gms_version_status", "version_id", "status"),
    )


class GMSRuntimeConfig(Base):
    """GMS 运行时策略默认参数（原 gms_config.json），单行 name='default'。"""

    __tablename__ = "gms_runtime_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False, index=True, default="default")
    config_params = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class GMSBacktestTask(Base):
    """GMS 回测任务与报告明细（原 backtest_data 目录文件）。"""

    __tablename__ = "gms_backtest_tasks"

    task_id = Column(String(64), primary_key=True)
    name = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False, index=True)
    progress = Column(Integer, default=0, nullable=False)
    message = Column(Text, nullable=True)
    config = Column(JSON, nullable=False)
    logs = Column(JSON, nullable=True)
    summary = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    details_path = Column(String(512), nullable=True)
    details_csv_bytes = Column(LargeBinary, nullable=True)
    details_xlsx_bytes = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_gms_bt_status_created", "status", "created_at"),
    )


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
    sync_from_realtime: bool = False  # 是否从实时行情表同步到历史行情表（港股/A股共用）

class RealtimeHistoricalCollectionRequest(BaseModel):
    """从实时行情表同步历史数据请求模型（主要用于 A 股）"""
    start_date: str
    end_date: str
    indicators: Optional[List[str]] = None  # 可选：同步后生成的技术指标列表

class FileHistoricalCollectionRequest(BaseModel):
    """从本地文件采集A股历史数据请求模型"""
    start_date: str
    end_date: str
    force_update: bool = False
    indicators: Optional[List[str]] = None
    file_type: str = 'txt'

class HKFileHistoricalCollectionRequest(BaseModel):
    """从本地文件采集港股历史数据请求模型"""
    start_date: str
    end_date: str
    force_update: bool = False
    indicators: Optional[List[str]] = None
    file_type: str = 'txt'

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
    warning_message: Optional[str] = None
    failed_details: List[str] = []

class RealtimeCollectionRequest(BaseModel):
    """实时数据采集请求模型"""
    market: str = 'CN'  # CN: A股, HK: 港股
    stock_code: Optional[str] = None  # 单个股票采集时填写
    stock_codes: Optional[List[str]] = None  # 前端单股采集以数组形式传入，保持兼容
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
    stock_code = Column(StockCodeTextPK(), nullable=False, index=True)
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
    stock_code = Column(StockCodeTextPK(), nullable=False)
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
    code = Column(StockCodeTextPK(), nullable=False, index=True)
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


class VolumeShrinkBreakoutSignal(Base):
    """3倍量缩量突破策略信号表（选股命中落库，signal_date=突破日）"""

    __tablename__ = "volume_shrink_breakout_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(StockCodeTextPK(), nullable=False, index=True)
    name = Column(String(100), nullable=False, default="")
    signal_date = Column(Date, nullable=False, index=True)
    boom_date = Column(String(20), nullable=True)
    boom_close = Column(Float, nullable=True)
    boom_volume = Column(Float, nullable=True)
    boom_volume_ratio_vs_prev = Column(Float, nullable=True)
    ma5_at_boom = Column(Float, nullable=True)
    ma10_at_boom = Column(Float, nullable=True)
    ma20_at_boom = Column(Float, nullable=True)
    breakout_close = Column(Float, nullable=True)
    breakout_volume = Column(Float, nullable=True)
    current_change_percent = Column(Float, nullable=True)
    volume_ratio_param = Column(Float, nullable=True)
    boom_lookback_min = Column(Integer, nullable=True)
    boom_lookback_max = Column(Integer, nullable=True)
    boards_json = Column(Text, nullable=True)
    run_search_date = Column(String(20), nullable=True)
    signal_strength = Column(Integer, nullable=True)
    signal_strength_level = Column(String(10), nullable=True)
    buy_signal_text = Column(String(220), nullable=True)
    signal_reminders_json = Column(Text, nullable=True)
    phase_state_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint("code", "signal_date", name="uq_vsb_signal_code_signal_date"),
    )


class GmsTradeObserveStock(Base):
    """用户 GMS 交易观察股：网站选股页从 GMS 信号列表点击「交易观察」加入。"""

    __tablename__ = "gms_trade_observe_stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    market = Column(String(10), nullable=False, default="CN", index=True)
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    signal_snapshot_json = Column(JSON, nullable=True)
    signal_date = Column(Date, nullable=True, index=True)
    key_focus_flag = Column(Boolean, nullable=False, default=False, index=True)
    latest_close_price = Column(Float, nullable=True)
    latest_close_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    user = relationship("User", backref="gms_trade_observe_stocks")

    __table_args__ = (
        UniqueConstraint("user_id", "market", "code", name="uq_gms_trade_observe_user_market_code"),
    )


class GmsTradeObserveHistory(Base):
    """用户 GMS 交易观察股移除归档：从交易观察列表移除时写入。"""

    __tablename__ = "gms_trade_observe_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    market = Column(String(10), nullable=False, default="CN", index=True)
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    signal_snapshot_json = Column(JSON, nullable=True)
    signal_date = Column(Date, nullable=True, index=True)
    observe_created_at = Column(DateTime, nullable=True)
    observe_updated_at = Column(DateTime, nullable=True)
    source_observe_id = Column(Integer, nullable=True)
    removed_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    user = relationship("User", backref="gms_trade_observe_history")


class GmsFormalTrade(Base):
    """用户 GMS 正式交易记录：从交易观察转入，记录入场/仓位/出场等。"""

    __tablename__ = "gms_formal_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    market = Column(String(10), nullable=False, default="CN", index=True)
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    source_observe_id = Column(Integer, nullable=True, index=True)
    entry_price = Column(Float, nullable=False)
    position_lots = Column(Integer, nullable=False, default=0)
    exit_price = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default="open", index=True)
    signal_date = Column(Date, nullable=True, index=True)
    signal_snapshot_json = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    entry_at = Column(DateTime, default=datetime.now, nullable=False)
    exit_at = Column(DateTime, nullable=True)
    pnl_amount = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    user = relationship("User", backref="gms_formal_trades")


class UrtTradeObserveStock(Base):
    """用户 URT 交易观察股：网站选股页从 URT 信号列表点击「观察」加入。"""

    __tablename__ = "urt_trade_observe_stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    market = Column(String(10), nullable=False, default="CN", index=True)
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    signal_snapshot_json = Column(JSON, nullable=True)
    signal_date = Column(Date, nullable=True, index=True)
    config_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    user = relationship("User", backref="urt_trade_observe_stocks")

    __table_args__ = (
        UniqueConstraint("user_id", "market", "code", name="uq_urt_trade_observe_user_market_code"),
    )


class UrtTradeObserveHistory(Base):
    """用户 URT 交易观察股移除归档。"""

    __tablename__ = "urt_trade_observe_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    market = Column(String(10), nullable=False, default="CN", index=True)
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    signal_snapshot_json = Column(JSON, nullable=True)
    signal_date = Column(Date, nullable=True, index=True)
    config_id = Column(Integer, nullable=True, index=True)
    observe_created_at = Column(DateTime, nullable=True)
    observe_updated_at = Column(DateTime, nullable=True)
    source_observe_id = Column(Integer, nullable=True)
    removed_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    user = relationship("User", backref="urt_trade_observe_history")


class UrtFormalTrade(Base):
    """用户 URT 正式交易记录：从交易观察转入。"""

    __tablename__ = "urt_formal_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    market = Column(String(10), nullable=False, default="CN", index=True)
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    source_observe_id = Column(Integer, nullable=True, index=True)
    entry_price = Column(Float, nullable=False)
    position_lots = Column(Integer, nullable=False, default=0)
    exit_price = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default="open", index=True)
    signal_date = Column(Date, nullable=True, index=True)
    signal_snapshot_json = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    entry_at = Column(DateTime, default=datetime.now, nullable=False)
    exit_at = Column(DateTime, nullable=True)
    pnl_amount = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    user = relationship("User", backref="urt_formal_trades")


class TripleVolumeTradeObserveStock(Base):
    """用户 3倍量策略交易观察股：日终爆量列表点击「交易观察」加入。"""

    __tablename__ = "triple_volume_trade_observe_stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    market = Column(String(10), nullable=False, default="CN", index=True)
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    observe_trade_date = Column(Date, nullable=True, index=True)
    observe_snapshot_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    user = relationship("User", backref="triple_volume_trade_observe_stocks")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "market", "code", name="uq_tvo_trade_observe_user_market_code"
        ),
    )


class VsbObserveStock(Base):
    """VSB 选股观察股：策略筛选命中后写入（与 volume_shrink_breakout_signals 同源触发）"""

    __tablename__ = "vsb_observe_stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    market = Column(String(10), nullable=False, default="CN", index=True)
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    signal_date = Column(Date, nullable=False, index=True)
    boom_date = Column(String(20), nullable=True)
    run_search_date = Column(String(20), nullable=True)
    signal_strength = Column(Integer, nullable=True)
    signal_strength_level = Column(String(20), nullable=True)
    buy_signal_text = Column(String(220), nullable=True)
    screen_snapshot_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    __table_args__ = (
        UniqueConstraint("market", "code", "signal_date", name="uq_vsb_observe_market_code_signal_date"),
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


class TripleVolumeObserveStock(Base):
    """3倍量观察股：爆量侦测入库 + VSB 复核状态"""

    __tablename__ = "triple_volume_observe_stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    market = Column(String(10), nullable=False, index=True)  # CN / HK
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    observe_trade_date = Column(Date, nullable=False, index=True)
    prev_trade_date = Column(Date, nullable=True)
    prev_volume = Column(Float, nullable=True)
    curr_volume = Column(Float, nullable=True)
    volume_ratio_actual = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default="待观察", index=True)
    vsb_evaluated_at = Column(DateTime, nullable=True)
    vsb_detail_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    __table_args__ = (
        UniqueConstraint("market", "code", "observe_trade_date", name="uq_tvo_code_market_obdate"),
    )


# 微信每日报告推送相关模型
class UserPushConfig(Base):
    """用户推送配置表"""
    __tablename__ = "user_push_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # 推送开关
    enabled = Column(Boolean, default=True, nullable=False)
    
    # 推送渠道配置 (JSON格式: ["wechat", "email"])
    channels = Column(JSON, default=["wechat"], nullable=False)
    
    # 推送时间配置 (JSON格式: ["09:30", "15:30"])
    push_times = Column(JSON, default=["09:30", "15:30"], nullable=False)
    
    # 报告类型（含 triple_volume_observe_scan / triple_volume_observe_eval 等）
    report_type = Column(String(64), default="summary", nullable=False)
    
    # 股票范围配置 (JSON格式: null表示全部, 或["000001", "600000"])
    stock_codes = Column(JSON, nullable=True)

    # 可选：本推送任务企业微信接收人 userid 列表（覆盖 users.wechat_userid）；JSON 数组字符串
    wechat_notify_userids = Column(JSON, nullable=True)

    # 可选：企业微信应用配置档（仅大写字母数字下划线，最长 32）。非空则读 WECHAT_<PROFILE>_CORP_ID 等；空则读 WECHAT_CORP_ID 默认三套
    wechat_app_profile = Column(String(32), nullable=True)

    # 时间戳
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    user = relationship("User", back_populates="push_configs")


class PushRecord(Base):
    """推送记录表"""
    __tablename__ = "push_records"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # 推送信息
    push_date = Column(Date, nullable=False, index=True)
    push_time = Column(String(10), nullable=False)  # "09:30"
    report_type = Column(String(64), nullable=False)
    
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


class EmailSenderConfig(Base):
    """发件邮箱配置表（单行配置，id=1）"""
    __tablename__ = "email_sender_config"

    id = Column(Integer, primary_key=True, index=True, default=1)
    host = Column(String(255), nullable=False, default="smtp.example.com")
    port = Column(Integer, nullable=False, default=587)
    username = Column(String(255), nullable=False, default="")
    password = Column(String(500), nullable=True)  # 存储时可加密
    from_email = Column(String(255), nullable=False, default="")
    from_name = Column(String(100), nullable=False, default="股票分析系统")
    use_tls = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class EmailSendLog(Base):
    """邮件发送日志表"""
    __tablename__ = "email_send_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    to_email = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    report_type = Column(String(64), nullable=False)
    push_record_id = Column(Integer, ForeignKey("push_records.id"), nullable=True, index=True)
    sent_at = Column(DateTime, nullable=False, default=datetime.now)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", backref="email_send_logs")

# 采集日历模型
class TradingCalendar(Base):
    """
    采集日历表：存储 A 股和港股的节假日。
    如果在采集时，目标日期属于节假日，则跳过不采集。
    """
    __tablename__ = "trading_calendar"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    market = Column(String(10), nullable=False, index=True)  # 'CN' 或 'HK'
    holiday_date = Column(Date, nullable=False, index=True)
    description = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    __table_args__ = (
        UniqueConstraint('market', 'holiday_date', name='uq_trading_calendar_market_date'),
    )

class TradingCalendarBase(BaseModel):
    market: str
    holiday_date: date
    description: Optional[str] = None

class TradingCalendarCreate(TradingCalendarBase):
    pass

class TradingCalendarInDB(TradingCalendarBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========================= 基金/ETF 相关模型 =========================

class FundBasicInfo(Base):
    """基金/ETF 基础信息表"""
    __tablename__ = "fund_basic_info"

    code = Column(StockCodeTextPK(), primary_key=True, index=True)
    name = Column(String, nullable=False)
    fund_type = Column(String(20), nullable=True)           # 基金类型: ETF / LOF 等
    listing_date = Column(Text, nullable=True)              # 上市日期
    fund_company = Column(String(100), nullable=True)       # 基金公司
    industry = Column(Text, nullable=True)                  # 所属行业/板块
    total_shares = Column(Float, nullable=True)             # 总份额
    free_float_shares = Column(Float, nullable=True)        # 流通份额
    shares_updated_at = Column(DateTime, nullable=True)
    collect_enabled = Column(Boolean, nullable=True, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class FundRealtimeQuote(Base):
    """基金/ETF 实时行情表"""
    __tablename__ = "fund_realtime_quote"

    code = Column(StockCodeTextPK(), primary_key=True)
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
    total_market_value = Column(Float)
    circulating_market_value = Column(Float)
    update_time = Column(DateTime)

    __table_args__ = (
        UniqueConstraint('code', 'trade_date', name='uq_fund_realtime_quote_code_date'),
    )


class FundHistoricalQuotes(Base):
    """基金/ETF 历史行情表"""
    __tablename__ = 'fund_historical_quotes'

    code = Column(StockCodeTextPK(), primary_key=True)
    name = Column(String)
    date = Column(Date, primary_key=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    pre_close = Column(Float)
    volume = Column(Float)                  # 成交量
    amount = Column(Float)                  # 成交额
    change_percent = Column(Float)          # 涨跌幅
    change = Column(Float)                  # 涨跌额
    amplitude = Column(Float)              # 振幅
    turnover_rate = Column(Float)          # 换手率
    collected_source = Column(String)
    collected_date = Column(DateTime, default=datetime.now)

# ========== SBBR 做小做底策略 ==========

class SBBRStrategyConfig(Base):
    """SBBR 策略参数版本。"""
    __tablename__ = "sbbr_strategy_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    config_params = Column(JSON, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    is_default = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class SBBRSignalTrace(Base):
    """SBBR 日终信号追溯。"""
    __tablename__ = "sbbr_signal_trace"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False, index=True)
    trade_date = Column(Date, nullable=False, index=True)
    config_id = Column(Integer, ForeignKey("sbbr_strategy_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    market_type = Column(String(10), nullable=False, default="CN")
    total_mv = Column(Float, nullable=True)
    circ_mv = Column(Float, nullable=True)
    size_ok = Column(Boolean, nullable=True)
    bottom_mode = Column(String(40), nullable=True)
    bottom_matched = Column(Boolean, nullable=True)
    entry_signal = Column(Boolean, nullable=True)
    entry_low = Column(Float, nullable=True)
    defense_low = Column(Float, nullable=True)
    defense_high = Column(Float, nullable=True)
    defense_buffer_pct = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)
    ma20 = Column(Float, nullable=True)
    volume_ratio = Column(Float, nullable=True)
    exit_flags = Column(JSON, nullable=True)
    position_advice = Column(JSON, nullable=True)
    detail = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    __table_args__ = (
        UniqueConstraint("code", "trade_date", "config_id", name="uq_sbbr_signal_trace_code_date_cfg"),
    )


class SBBRReserveBox(Base):
    """SBBR 人工储备箱。"""
    __tablename__ = "sbbr_reserve_box"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    stock_code = Column(String(20), nullable=False, index=True)
    stock_name = Column(String(200), nullable=True)
    industry_note = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="watching")
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    user = relationship("User", backref="sbbr_reserve_box")

    __table_args__ = (
        UniqueConstraint("user_id", "stock_code", name="uq_sbbr_reserve_user_code"),
    )


class SBBRTradeObserveStock(Base):
    """SBBR 交易观察。"""
    __tablename__ = "sbbr_trade_observe_stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    market = Column(String(10), nullable=False, default="CN", index=True)
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    signal_snapshot_json = Column(JSON, nullable=True)
    signal_date = Column(Date, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    user = relationship("User", backref="sbbr_trade_observe_stocks")

    __table_args__ = (
        UniqueConstraint("user_id", "market", "code", name="uq_sbbr_trade_observe_user_market_code"),
    )


class SBBRFormalTrade(Base):
    """SBBR 正式交易（含五·三·二分仓）。"""
    __tablename__ = "sbbr_formal_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    market = Column(String(10), nullable=False, default="CN", index=True)
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    source_observe_id = Column(Integer, nullable=True, index=True)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default="open", index=True)
    signal_date = Column(Date, nullable=True, index=True)
    signal_snapshot_json = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    stage = Column(String(20), nullable=False, default="probe")
    budget_total = Column(Float, nullable=True)
    allocated_pct = Column(Float, nullable=False, default=50.0)
    defense_anchor_low = Column(Float, nullable=True)
    defense_buffer_pct = Column(Float, nullable=True)
    exit_reason = Column(String(100), nullable=True)
    last_eval_json = Column(JSON, nullable=True)
    pnl_amount = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)
    entry_at = Column(DateTime, default=datetime.now, nullable=False)
    exit_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    user = relationship("User", backref="sbbr_formal_trades")


class SBBRBacktestTask(Base):
    """SBBR 回测任务。"""
    __tablename__ = "sbbr_backtest_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=True)
    config = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    progress = Column(Integer, nullable=False, default=0)
    message = Column(Text, nullable=True)
    summary = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

# ========== RPE 比价效应策略 ==========

class RPEStrategyConfig(Base):
    """RPE 策略参数版本。"""
    __tablename__ = "rpe_strategy_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    config_params = Column(JSON, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    is_default = Column(Boolean, nullable=False, default=False, index=True)
    precompute_enabled = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class RPESignalTrace(Base):
    """RPE 日终信号追溯。"""
    __tablename__ = "rpe_signal_trace"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False, index=True)
    trade_date = Column(Date, nullable=False, index=True)
    market_type = Column(String(10), nullable=False, default="CN")
    config_id = Column(Integer, ForeignKey("rpe_strategy_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    sector_id = Column(String(40), nullable=True, index=True)
    sector_name = Column(String(100), nullable=True)
    z_score = Column(Float, nullable=True)
    ratio = Column(Float, nullable=True)
    signal_type = Column(String(20), nullable=True, index=True)
    entry_signal = Column(Boolean, nullable=True)
    watch_only = Column(Boolean, nullable=True)
    trend_veto = Column(Boolean, nullable=True)
    sector_slope = Column(Float, nullable=True)
    support_levels = Column(JSON, nullable=True)
    resistance_levels = Column(JSON, nullable=True)
    nearest_support = Column(Float, nullable=True)
    nearest_resistance = Column(Float, nullable=True)
    structure_valid = Column(Boolean, nullable=True)
    liquidity_ok = Column(Boolean, nullable=True)
    close_price = Column(Float, nullable=True)
    detail = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    __table_args__ = (
        UniqueConstraint("code", "trade_date", "market_type", "config_id", name="uq_rpe_signal_trace_code_date_mkt_cfg"),
    )


class RPETradeObserveStock(Base):
    """RPE 交易观察。"""
    __tablename__ = "rpe_trade_observe_stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    market = Column(String(10), nullable=False, default="CN", index=True)
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    signal_snapshot_json = Column(JSON, nullable=True)
    signal_date = Column(Date, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    user = relationship("User", backref="rpe_trade_observe_stocks")

    __table_args__ = (
        UniqueConstraint("user_id", "market", "code", name="uq_rpe_trade_observe_user_market_code"),
    )


class RPETradeObserveHistory(Base):
    """RPE 交易观察移除归档。"""
    __tablename__ = "rpe_trade_observe_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    market = Column(String(10), nullable=False, default="CN")
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    signal_snapshot_json = Column(JSON, nullable=True)
    signal_date = Column(Date, nullable=True)
    source_observe_id = Column(Integer, nullable=True)
    removed_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    user = relationship("User", backref="rpe_trade_observe_history")


class RPEFormalTrade(Base):
    """RPE 正式交易（结构破位离场）。"""
    __tablename__ = "rpe_formal_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    market = Column(String(10), nullable=False, default="CN", index=True)
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    source_observe_id = Column(Integer, nullable=True, index=True)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default="open", index=True)
    signal_date = Column(Date, nullable=True, index=True)
    signal_snapshot_json = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    structure_support = Column(Float, nullable=True)
    structure_resistance = Column(Float, nullable=True)
    exit_reason = Column(String(100), nullable=True)
    last_eval_json = Column(JSON, nullable=True)
    pnl_amount = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)
    entry_at = Column(DateTime, default=datetime.now, nullable=False)
    exit_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    user = relationship("User", backref="rpe_formal_trades")


class RPEBacktestTask(Base):
    """RPE 回测任务。"""
    __tablename__ = "rpe_backtest_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=True)
    config = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    progress = Column(Integer, nullable=False, default=0)
    message = Column(Text, nullable=True)
    summary = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class RPEPrecomputeRun(Base):
    """RPE 预计算运行记录。"""
    __tablename__ = "rpe_precompute_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_id = Column(Integer, nullable=False, index=True)
    trade_date = Column(Date, nullable=True, index=True)
    market = Column(String(10), nullable=False, default="CN")
    status = Column(String(20), nullable=False, default="completed")
    stock_count = Column(Integer, nullable=True)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)


class RPETraceRecomputeTask(Base):
    """RPE 信号追溯强制重算任务（多 worker 共享进度）。"""

    __tablename__ = "rpe_trace_recompute_tasks"

    task_id = Column(String(64), primary_key=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    progress = Column(Integer, nullable=False, default=0)
    message = Column(Text, nullable=True)
    code = Column(String(20), nullable=False, index=True)
    config_id = Column(Integer, nullable=False, index=True)
    config_name = Column(String(200), nullable=True)
    current = Column(Integer, nullable=False, default=0)
    total = Column(Integer, nullable=False, default=0)
    saved_count = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


# ========== 环境数据同步 ==========

class EnvSyncServerConfig(Base):
    """生产端 Sync Key（单行 id=1）：仅存哈希，用于校验对端请求。"""

    __tablename__ = "env_sync_server_config"

    id = Column(Integer, primary_key=True, default=1)
    enabled = Column(Boolean, nullable=False, default=False)
    sync_key_hash = Column(String(128), nullable=True)
    key_hint = Column(String(16), nullable=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class EnvSyncClientConfig(Base):
    """本地客户端：生产 Base URL + Sync Key（单行 id=1）。"""

    __tablename__ = "env_sync_client_config"

    id = Column(Integer, primary_key=True, default=1)
    enabled = Column(Boolean, nullable=False, default=False)
    prod_base_url = Column(String(500), nullable=False, default="")
    sync_key = Column(String(500), nullable=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class EnvSyncAuditLog(Base):
    """环境同步操作审计。"""

    __tablename__ = "env_sync_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    direction = Column(String(16), nullable=False)  # pull / push / import / export
    modules = Column(JSON, nullable=True)
    operator = Column(String(100), nullable=True)
    success = Column(Boolean, nullable=False, default=False)
    summary = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
