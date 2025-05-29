"""
数据库模型定义
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Float, Date
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

# Pydantic 模型（用于API请求和响应）
class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[str] = None

class UserInDB(UserBase):
    id: int
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
    user_id: int

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