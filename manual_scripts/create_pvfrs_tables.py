#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建 PVFRS 策略相关的数据库表
"""

import sys
import os

# 添加 backend_api 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend_api'))

from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Text, DateTime, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

# 从配置文件读取数据库连接
from backend_api.config import DATABASE_CONFIG

# 创建独立的 Base
Base = declarative_base()

# 定义 PVFRS 相关的表模型
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

def create_pvfrs_tables():
    """创建 PVFRS 相关表"""
    try:
        # 创建数据库引擎
        engine = create_engine(DATABASE_CONFIG["url"])
        
        print("🚀 开始创建 PVFRS 策略相关表...")
        print(f"📊 数据库: {DATABASE_CONFIG['url'].split('@')[-1]}")
        
        # 创建所有表
        Base.metadata.create_all(engine)
        
        print("✅ PVFRS 表创建成功!")
        print("📋 已创建以下表:")
        print("   - pvfrs_backtest_tasks (回测任务表)")
        print("   - pvfrs_backtest_results (回测结果表)")
        print("   - pvfrs_trade_records (交易记录表)")
        print("   - pvfrs_equity_curves (收益曲线表)")
        
        return True
        
    except Exception as e:
        print(f"❌ 创建表失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = create_pvfrs_tables()
    sys.exit(0 if success else 1)
