"""
PVFRS策略管理模块增强数据模型
重构后的数据库表结构，支持更完善的策略管理功能
"""

from sqlalchemy import Column, Integer, String, DateTime, Date, Float, Boolean, Text, DECIMAL, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class PVFRSStrategyConfig(Base):
    """PVFRS策略配置表"""
    __tablename__ = "pvfrs_strategy_configs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text)
    config_params = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关联关系
    tasks = relationship("PVFRSBacktestTaskEnhanced", back_populates="strategy_config")
    results = relationship("PVFRSBacktestResultEnhanced", back_populates="strategy_config")
    
    __table_args__ = (
        Index('idx_pvfrs_strategy_configs_name', 'name'),
        Index('idx_pvfrs_strategy_configs_active', 'is_active'),
    )

class PVFRSBacktestTaskEnhanced(Base):
    """PVFRS回测任务表（增强版）"""
    __tablename__ = "pvfrs_backtest_tasks_enhanced"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(50), unique=True, nullable=False, index=True)
    strategy_config_id = Column(Integer, ForeignKey("pvfrs_strategy_configs.id"), nullable=False, index=True)
    mode = Column(String(20), nullable=False)  # single, batch, optimize
    stock_codes = Column(JSON, nullable=False)
    market = Column(String(10), nullable=False)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    initial_capital = Column(DECIMAL(15,2), nullable=False)
    status = Column(String(20), default="pending", index=True)  # pending, running, completed, failed, cancelled
    progress = Column(Integer, default=0)
    current_step = Column(Text)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    estimated_duration = Column(Integer)  # 预估执行时间（秒）
    priority = Column(Integer, default=5)  # 优先级：1-10
    processing_speed = Column(DECIMAL(8,2), default=0.0)  # 处理速度（股票/秒）
    worker_id = Column(String(50))  # 执行的工作进程ID
    
    # 关联关系
    strategy_config = relationship("PVFRSStrategyConfig", back_populates="tasks")
    results = relationship("PVFRSBacktestResultEnhanced", back_populates="task")
    
    __table_args__ = (
        Index('idx_pvfrs_tasks_task_id', 'task_id'),
        Index('idx_pvfrs_tasks_status', 'status'),
        Index('idx_pvfrs_tasks_created_at', 'created_at'),
        Index('idx_pvfrs_tasks_strategy_config', 'strategy_config_id'),
        Index('idx_pvfrs_tasks_date_range', 'start_date', 'end_date'),
    )

class PVFRSBacktestResultEnhanced(Base):
    """PVFRS回测结果表（增强版）"""
    __tablename__ = "pvfrs_backtest_results_enhanced"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(50), ForeignKey("pvfrs_backtest_tasks_enhanced.task_id"), nullable=False, index=True)
    strategy_config_id = Column(Integer, ForeignKey("pvfrs_strategy_configs.id"), nullable=False, index=True)
    stock_code = Column(String(20), nullable=False, index=True)
    market = Column(String(10), nullable=False)
    backtest_date = Column(Date, nullable=False, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    initial_capital = Column(DECIMAL(15,2), nullable=False)
    final_capital = Column(DECIMAL(15,2), nullable=False)
    total_return = Column(DECIMAL(10,6), nullable=False, index=True)
    annual_return = Column(DECIMAL(10,6), nullable=False, index=True)
    max_drawdown = Column(DECIMAL(10,6), nullable=False, index=True)
    sharpe_ratio = Column(DECIMAL(10,6), nullable=False, index=True)
    win_rate = Column(DECIMAL(5,4), nullable=False, index=True)
    profit_factor = Column(DECIMAL(10,6), nullable=False)
    total_trades = Column(Integer, nullable=False)
    winning_trades = Column(Integer, nullable=False)
    avg_holding_period = Column(DECIMAL(8,2), nullable=False)
    volatility = Column(DECIMAL(10,6), nullable=False)
    created_at = Column(DateTime, default=datetime.now, index=True)
    
    # 关联关系
    task = relationship("PVFRSBacktestTaskEnhanced", back_populates="results")
    strategy_config = relationship("PVFRSStrategyConfig", back_populates="results")
    trades = relationship("PVFRSTradeRecordEnhanced", back_populates="result")
    equity_curve = relationship("PVFRSEquityCurveEnhanced", back_populates="result")
    
    __table_args__ = (
        Index('idx_pvfrs_results_task_id', 'task_id'),
        Index('idx_pvfrs_results_stock_code', 'stock_code'),
        Index('idx_pvfrs_results_total_return', 'total_return'),
        Index('idx_pvfrs_results_created_at', 'created_at'),
        Index('idx_pvfrs_results_performance', 'total_return', 'sharpe_ratio', 'max_drawdown'),
    )

class PVFRSTradeRecordEnhanced(Base):
    """PVFRS交易记录表（增强版）"""
    __tablename__ = "pvfrs_trade_records_enhanced"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    result_id = Column(Integer, ForeignKey("pvfrs_backtest_results_enhanced.id"), nullable=False, index=True)
    stock_code = Column(String(20), nullable=False, index=True)
    market = Column(String(10), nullable=False)
    trade_date = Column(Date, nullable=False, index=True)
    entry_time = Column(DateTime)
    exit_time = Column(DateTime)
    entry_price = Column(DECIMAL(10,4), nullable=False)
    exit_price = Column(DECIMAL(10,4), nullable=False)
    quantity = Column(Integer, nullable=False)
    pnl = Column(DECIMAL(15,2), nullable=False, index=True)
    pnl_percent = Column(DECIMAL(8,4), nullable=False)
    commission = Column(DECIMAL(10,4), default=0.0)
    slippage = Column(DECIMAL(10,4), default=0.0)
    exit_reason = Column(String(50))
    trade_type = Column(String(20), default="long")  # long, short
    holding_period = Column(Integer)  # 持有天数
    created_at = Column(DateTime, default=datetime.now)
    
    # 关联关系
    result = relationship("PVFRSBacktestResultEnhanced", back_populates="trades")
    
    __table_args__ = (
        Index('idx_pvfrs_trades_result_id', 'result_id'),
        Index('idx_pvfrs_trades_stock_code', 'stock_code'),
        Index('idx_pvfrs_trades_trade_date', 'trade_date'),
        Index('idx_pvfrs_trades_pnl', 'pnl'),
    )

class PVFRSEquityCurveEnhanced(Base):
    """PVFRS收益曲线表（增强版）"""
    __tablename__ = "pvfrs_equity_curves_enhanced"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    result_id = Column(Integer, ForeignKey("pvfrs_backtest_results_enhanced.id"), nullable=False, index=True)
    stock_code = Column(String(20), nullable=False, index=True)
    market = Column(String(10), nullable=False)
    curve_date = Column(Date, nullable=False, index=True)
    equity = Column(DECIMAL(15,2), nullable=False)
    cash = Column(DECIMAL(15,2), nullable=False)
    portfolio_value = Column(DECIMAL(15,2), nullable=False)
    benchmark_value = Column(DECIMAL(15,2))
    daily_return = Column(DECIMAL(8,6))
    cumulative_return = Column(DECIMAL(8,6))
    drawdown = Column(DECIMAL(8,6))
    max_drawdown = Column(DECIMAL(8,6))
    created_at = Column(DateTime, default=datetime.now)
    
    # 关联关系
    result = relationship("PVFRSBacktestResultEnhanced", back_populates="equity_curve")
    
    __table_args__ = (
        Index('idx_pvfrs_equity_result_id', 'result_id'),
        Index('idx_pvfrs_equity_curve_date', 'curve_date'),
        Index('idx_pvfrs_equity_stock_code', 'stock_code'),
    )

# 兼容性别名，保持与现有代码的兼容性
PVFRSBacktestTask = PVFRSBacktestTaskEnhanced
PVFRSBacktestResult = PVFRSBacktestResultEnhanced
PVFRSTradeRecord = PVFRSTradeRecordEnhanced
PVFRSEquityCurve = PVFRSEquityCurveEnhanced
