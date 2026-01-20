"""
PVFRS策略管理模块数据库重构迁移脚本
将现有的SQLite数据迁移到PostgreSQL，并创建新的表结构
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend_api.database import engine as main_engine
from backend_api.models import Base
import logging
import json
from datetime import datetime

# 配置日志
logger = logging.getLogger(__name__)

def create_pvfrs_enhanced_tables():
    """创建增强的PVFRS表结构"""
    logger.info("开始创建PVFRS增强表结构...")
    
    # 策略配置表
    create_strategy_configs_sql = """
    CREATE TABLE IF NOT EXISTS pvfrs_strategy_configs (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) UNIQUE NOT NULL,
        description TEXT,
        config_params JSONB NOT NULL,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    
    CREATE INDEX IF NOT EXISTS idx_pvfrs_strategy_configs_name ON pvfrs_strategy_configs(name);
    CREATE INDEX IF NOT EXISTS idx_pvfrs_strategy_configs_active ON pvfrs_strategy_configs(is_active);
    """
    
    # 增强任务表
    create_enhanced_tasks_sql = """
    CREATE TABLE IF NOT EXISTS pvfrs_backtest_tasks_enhanced (
        id SERIAL PRIMARY KEY,
        task_id VARCHAR(50) UNIQUE NOT NULL,
        strategy_config_id INTEGER REFERENCES pvfrs_strategy_configs(id),
        mode VARCHAR(20) NOT NULL,
        stock_codes JSONB NOT NULL,
        market VARCHAR(10) NOT NULL,
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        initial_capital DECIMAL(15,2) NOT NULL,
        status VARCHAR(20) DEFAULT 'pending',
        progress INTEGER DEFAULT 0,
        current_step TEXT,
        error_message TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        estimated_duration INTEGER,
        priority INTEGER DEFAULT 5,
        processing_speed DECIMAL(8,2) DEFAULT 0.0,
        worker_id VARCHAR(50)
    );
    
    CREATE INDEX IF NOT EXISTS idx_pvfrs_tasks_task_id ON pvfrs_backtest_tasks_enhanced(task_id);
    CREATE INDEX IF NOT EXISTS idx_pvfrs_tasks_status ON pvfrs_backtest_tasks_enhanced(status);
    CREATE INDEX IF NOT EXISTS idx_pvfrs_tasks_created_at ON pvfrs_backtest_tasks_enhanced(created_at);
    CREATE INDEX IF NOT EXISTS idx_pvfrs_tasks_strategy_config ON pvfrs_backtest_tasks_enhanced(strategy_config_id);
    """
    
    # 增强结果表
    create_enhanced_results_sql = """
    CREATE TABLE IF NOT EXISTS pvfrs_backtest_results_enhanced (
        id SERIAL PRIMARY KEY,
        task_id VARCHAR(50) REFERENCES pvfrs_backtest_tasks_enhanced(task_id),
        strategy_config_id INTEGER REFERENCES pvfrs_strategy_configs(id),
        stock_code VARCHAR(20) NOT NULL,
        market VARCHAR(10) NOT NULL,
        backtest_date DATE NOT NULL,
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        initial_capital DECIMAL(15,2) NOT NULL,
        final_capital DECIMAL(15,2) NOT NULL,
        total_return DECIMAL(10,6) NOT NULL,
        annual_return DECIMAL(10,6) NOT NULL,
        max_drawdown DECIMAL(10,6) NOT NULL,
        sharpe_ratio DECIMAL(10,6) NOT NULL,
        win_rate DECIMAL(5,4) NOT NULL,
        profit_factor DECIMAL(10,6) NOT NULL,
        total_trades INTEGER NOT NULL,
        winning_trades INTEGER NOT NULL,
        avg_holding_period DECIMAL(8,2) NOT NULL,
        volatility DECIMAL(10,6) NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    );
    
    CREATE INDEX IF NOT EXISTS idx_pvfrs_results_task_id ON pvfrs_backtest_results_enhanced(task_id);
    CREATE INDEX IF NOT EXISTS idx_pvfrs_results_stock_code ON pvfrs_backtest_results_enhanced(stock_code);
    CREATE INDEX IF NOT EXISTS idx_pvfrs_results_total_return ON pvfrs_backtest_results_enhanced(total_return);
    CREATE INDEX IF NOT EXISTS idx_pvfrs_results_created_at ON pvfrs_backtest_results_enhanced(created_at);
    """
    
    # 交易记录表（增强版）
    create_enhanced_trades_sql = """
    CREATE TABLE IF NOT EXISTS pvfrs_trade_records_enhanced (
        id SERIAL PRIMARY KEY,
        result_id INTEGER REFERENCES pvfrs_backtest_results_enhanced(id),
        stock_code VARCHAR(20) NOT NULL,
        market VARCHAR(10) NOT NULL,
        trade_date DATE NOT NULL,
        entry_time TIMESTAMP,
        exit_time TIMESTAMP,
        entry_price DECIMAL(10,4) NOT NULL,
        exit_price DECIMAL(10,4) NOT NULL,
        quantity INTEGER NOT NULL,
        pnl DECIMAL(15,2) NOT NULL,
        pnl_percent DECIMAL(8,4) NOT NULL,
        commission DECIMAL(10,4) DEFAULT 0.0,
        slippage DECIMAL(10,4) DEFAULT 0.0,
        exit_reason VARCHAR(50),
        trade_type VARCHAR(20) DEFAULT 'long',
        holding_period INTEGER,
        created_at TIMESTAMP DEFAULT NOW()
    );
    
    CREATE INDEX IF NOT EXISTS idx_pvfrs_trades_result_id ON pvfrs_trade_records_enhanced(result_id);
    CREATE INDEX IF NOT EXISTS idx_pvfrs_trades_stock_code ON pvfrs_trade_records_enhanced(stock_code);
    CREATE INDEX IF NOT EXISTS idx_pvfrs_trades_trade_date ON pvfrs_trade_records_enhanced(trade_date);
    """
    
    # 收益曲线表（增强版）
    create_enhanced_equity_sql = """
    CREATE TABLE IF NOT EXISTS pvfrs_equity_curves_enhanced (
        id SERIAL PRIMARY KEY,
        result_id INTEGER REFERENCES pvfrs_backtest_results_enhanced(id),
        stock_code VARCHAR(20) NOT NULL,
        market VARCHAR(10) NOT NULL,
        curve_date DATE NOT NULL,
        equity DECIMAL(15,2) NOT NULL,
        cash DECIMAL(15,2) NOT NULL,
        portfolio_value DECIMAL(15,2) NOT NULL,
        benchmark_value DECIMAL(15,2),
        daily_return DECIMAL(8,6),
        cumulative_return DECIMAL(8,6),
        drawdown DECIMAL(8,6),
        max_drawdown DECIMAL(8,6),
        created_at TIMESTAMP DEFAULT NOW()
    );
    
    CREATE INDEX IF NOT EXISTS idx_pvfrs_equity_result_id ON pvfrs_equity_curves_enhanced(result_id);
    CREATE INDEX IF NOT EXISTS idx_pvfrs_equity_curve_date ON pvfrs_equity_curves_enhanced(curve_date);
    """
    
    try:
        with main_engine.connect() as conn:
            # 创建策略配置表
            conn.execute(text(create_strategy_configs_sql))
            logger.info("✓ 策略配置表创建完成")
            
            # 创建增强任务表
            conn.execute(text(create_enhanced_tasks_sql))
            logger.info("✓ 增强任务表创建完成")
            
            # 创建增强结果表
            conn.execute(text(create_enhanced_results_sql))
            logger.info("✓ 增强结果表创建完成")
            
            # 创建增强交易记录表
            conn.execute(text(create_enhanced_trades_sql))
            logger.info("✓ 增强交易记录表创建完成")
            
            # 创建增强收益曲线表
            conn.execute(text(create_enhanced_equity_sql))
            logger.info("✓ 增强收益曲线表创建完成")
            
            conn.commit()
            
    except Exception as e:
        logger.error(f"创建PVFRS增强表失败: {str(e)}")
        raise

def insert_default_strategy_configs():
    """插入默认策略配置"""
    logger.info("插入默认PVFRS策略配置...")
    
    default_configs = [
        {
            'name': 'PVFRS默认策略',
            'description': 'PVFRS量价频三维共振演化策略的默认配置',
            'config_params': {
                'strategy_params': {
                    'buy_bias_min': -0.05,
                    'sell_bias_max': 0.15,
                    'buy_consecutive_days': 2,
                    'signal_threshold': 0.6
                },
                'risk_params': {
                    'stop_loss_rate': 0.1,
                    'take_profit_rate': 0.2,
                    'max_position_size': 0.1,
                    'commission_rate': 0.0003,
                    'slippage_rate': 0.001
                }
            },
            'is_active': True
        },
        {
            'name': 'PVFRS保守策略',
            'description': 'PVFRS策略的保守版本，适合风险厌恶投资者',
            'config_params': {
                'strategy_params': {
                    'buy_bias_min': -0.03,
                    'sell_bias_max': 0.12,
                    'buy_consecutive_days': 3,
                    'signal_threshold': 0.7
                },
                'risk_params': {
                    'stop_loss_rate': 0.08,
                    'take_profit_rate': 0.15,
                    'max_position_size': 0.08,
                    'commission_rate': 0.0003,
                    'slippage_rate': 0.001
                }
            },
            'is_active': True
        },
        {
            'name': 'PVFRS激进策略',
            'description': 'PVFRS策略的激进版本，适合风险偏好投资者',
            'config_params': {
                'strategy_params': {
                    'buy_bias_min': -0.08,
                    'sell_bias_max': 0.20,
                    'buy_consecutive_days': 1,
                    'signal_threshold': 0.5
                },
                'risk_params': {
                    'stop_loss_rate': 0.12,
                    'take_profit_rate': 0.25,
                    'max_position_size': 0.15,
                    'commission_rate': 0.0003,
                    'slippage_rate': 0.001
                }
            },
            'is_active': True
        }
    ]
    
    try:
        with main_engine.connect() as conn:
            for config in default_configs:
                # 检查是否已存在
                result = conn.execute(
                    text("SELECT id FROM pvfrs_strategy_configs WHERE name = :name"),
                    {'name': config['name']}
                ).fetchone()
                
                if not result:
                    conn.execute(
                        text("""
                        INSERT INTO pvfrs_strategy_configs 
                        (name, description, config_params, is_active, created_at, updated_at)
                        VALUES (:name, :description, :config_params, :is_active, NOW(), NOW())
                        """),
                        {
                            'name': config['name'],
                            'description': config['description'],
                            'config_params': json.dumps(config['config_params']),
                            'is_active': config['is_active']
                        }
                    )
                    logger.info(f"✓ 插入策略配置: {config['name']}")
                else:
                    logger.info(f"⚠ 策略配置已存在: {config['name']}")
            
            conn.commit()
            
    except Exception as e:
        logger.error(f"插入默认策略配置失败: {str(e)}")
        raise

def migrate_existing_data():
    """迁移现有SQLite数据到PostgreSQL"""
    logger.info("开始迁移现有PVFRS数据...")
    
    # 检查SQLite文件是否存在
    sqlite_db_path = "pvfrs_backtest_storage.db"
    if not os.path.exists(sqlite_db_path):
        logger.warning("SQLite数据库文件不存在，跳过数据迁移")
        return
    
    try:
        import sqlite3
        
        with sqlite3.connect(sqlite_db_path) as sqlite_conn:
            sqlite_cursor = sqlite_conn.cursor()
            
            # 读取现有报告数据
            sqlite_cursor.execute("SELECT * FROM backtest_reports")
            reports = sqlite_cursor.fetchall()
            
            if reports:
                logger.info(f"找到 {len(reports)} 条历史报告，开始迁移...")
                
                with main_engine.connect() as pg_conn:
                    for report in reports:
                        # 解析报告数据
                        full_data = report[0]  # full_data字段
                        if full_data:
                            try:
                                report_data = json.loads(full_data)
                            except:
                                # 如果JSON解析失败，跳过这条记录
                                continue
                        
                        # 迁移到增强表结构
                        try:
                            # 插入到增强任务表
                            task_data = {
                                'task_id': report_data.get('task_id', f"migrated_{report[1]}"),
                                'strategy_config_id': 1,  # 默认策略配置
                                'mode': 'single' if len(report_data.get('config', {}).get('stock_pool', [])) == 1 else 'batch',
                                'stock_codes': report_data.get('config', {}).get('stock_pool', []),
                                'market': 'CN',
                                'start_date': report_data.get('config', {}).get('start_date'),
                                'end_date': report_data.get('config', {}).get('end_date'),
                                'initial_capital': report_data.get('config', {}).get('initial_capital', 100000),
                                'status': 'completed',
                                'progress': 100,
                                'current_step': '数据迁移完成',
                                'created_at': report_data.get('created_at'),
                                'completed_at': report_data.get('created_at')
                            }
                            
                            pg_conn.execute(text("""
                                INSERT INTO pvfrs_backtest_tasks_enhanced 
                                (task_id, strategy_config_id, mode, stock_codes, market, 
                                 start_date, end_date, initial_capital, status, progress, 
                                 current_step, created_at, completed_at)
                                VALUES (:task_id, :strategy_config_id, :mode, :stock_codes, :market,
                                        :start_date, :end_date, :initial_capital, :status, :progress,
                                        :current_step, :created_at, :completed_at)
                            """), {
                                'task_id': task_data['task_id'],
                                'strategy_config_id': task_data['strategy_config_id'],
                                'mode': task_data['mode'],
                                'stock_codes': json.dumps(task_data['stock_codes']),
                                'market': task_data['market'],
                                'start_date': task_data['start_date'],
                                'end_date': task_data['end_date'],
                                'initial_capital': task_data['initial_capital'],
                                'status': task_data['status'],
                                'progress': task_data['progress'],
                                'current_step': task_data['current_step'],
                                'created_at': task_data['created_at'],
                                'completed_at': task_data['completed_at']
                            })
                            
                            # 获取插入的任务ID
                            task_result = pg_conn.execute(
                                text("SELECT id FROM pvfrs_backtest_tasks_enhanced WHERE task_id = :task_id"),
                                {'task_id': task_data['task_id']}
                            ).fetchone()
                            
                            if task_result:
                                task_id_db = task_result[0]
                                
                                # 插入到增强结果表
                                result_data = {
                                    'task_id': task_data['task_id'],
                                    'strategy_config_id': 1,
                                    'stock_code': report_data.get('config', {}).get('stock_pool', [''])[0] if report_data.get('config', {}).get('stock_pool') else 'UNKNOWN',
                                    'market': 'CN',
                                    'backtest_date': report_data.get('config', {}).get('start_date'),
                                    'start_date': report_data.get('config', {}).get('start_date'),
                                    'end_date': report_data.get('config', {}).get('end_date'),
                                    'initial_capital': report_data.get('config', {}).get('initial_capital', 100000),
                                    'final_capital': report_data.get('config', {}).get('initial_capital', 100000) * (1 + report_data.get('total_return', 0)),
                                    'total_return': report_data.get('total_return', 0),
                                    'annual_return': report_data.get('annual_return', 0),
                                    'max_drawdown': report_data.get('max_drawdown', 0),
                                    'sharpe_ratio': report_data.get('sharpe_ratio', 0),
                                    'win_rate': report_data.get('win_rate', 0),
                                    'profit_factor': report_data.get('total_return', 0) / abs(report_data.get('max_drawdown', 1)) if report_data.get('max_drawdown', 0) != 0 else 0,
                                    'total_trades': report_data.get('total_trades', 0),
                                    'winning_trades': report_data.get('winning_trades', 0),
                                    'avg_holding_period': 5.0,  # 默认值
                                    'volatility': 0.2  # 默认值
                                }
                                
                                pg_conn.execute(text("""
                                    INSERT INTO pvfrs_backtest_results_enhanced 
                                    (task_id, strategy_config_id, stock_code, market, backtest_date,
                                     start_date, end_date, initial_capital, final_capital, total_return,
                                     annual_return, max_drawdown, sharpe_ratio, win_rate, profit_factor,
                                     total_trades, winning_trades, avg_holding_period, volatility, created_at)
                                    VALUES (:task_id, :strategy_config_id, :stock_code, :market, :backtest_date,
                                            :start_date, :end_date, :initial_capital, :final_capital, :total_return,
                                            :annual_return, :max_drawdown, :sharpe_ratio, :win_rate, :profit_factor,
                                            :total_trades, :winning_trades, :avg_holding_period, :volatility, :created_at)
                                """), result_data)
                                
                                logger.info(f"✓ 迁移报告: {task_data['task_id']}")
                            
                        except Exception as e:
                            logger.error(f"迁移报告失败 {report[1]}: {str(e)}")
                            continue
                    
                    pg_conn.commit()
                    
            logger.info(f"数据迁移完成，共处理 {len(reports)} 条记录")
            
    except Exception as e:
        logger.error(f"数据迁移失败: {str(e)}")
        raise

def main():
    """主函数"""
    logger.info("开始PVFRS策略管理模块数据库重构...")
    
    try:
        # 1. 创建增强表结构
        create_pvfrs_enhanced_tables()
        
        # 2. 插入默认策略配置
        insert_default_strategy_configs()
        
        # 3. 迁移现有数据
        migrate_existing_data()
        
        logger.info("✅ PVFRS策略管理模块数据库重构完成！")
        
    except Exception as e:
        logger.error(f"❌ PVFRS策略管理模块数据库重构失败: {str(e)}")
        raise

if __name__ == "__main__":
    main()
