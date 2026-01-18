"""
PVFRS策略回测结果持久化存储模块
负责回测报告的数据库存储和历史查询功能
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import logging
import json
import sqlite3
import os
from dataclasses import dataclass, asdict

from .models import PVFRSException

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class StorageConfig:
    """存储配置"""
    db_path: str = "pvfrs_backtest_storage.db"
    max_reports_per_strategy: int = 100
    auto_cleanup_days: int = 365
    enable_compression: bool = True
    backup_enabled: bool = True
    backup_interval_hours: int = 24


@dataclass
class QueryFilter:
    """查询过滤器"""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    strategy_name: Optional[str] = None
    min_return: Optional[float] = None
    max_drawdown: Optional[float] = None
    min_sharpe_ratio: Optional[float] = None
    task_ids: Optional[List[str]] = None
    report_ids: Optional[List[str]] = None
    limit: int = 50
    offset: int = 0
    order_by: str = "created_at"
    order_desc: bool = True


class BacktestStorage:
    """回测结果存储管理器
    
    负责回测报告的持久化存储和查询：
    - 数据库表结构管理
    - 报告数据存储和检索
    - 历史查询和过滤
    - 数据清理和维护
    - 备份和恢复功能
    """
    
    def __init__(self, config: Optional[StorageConfig] = None):
        """初始化存储管理器
        
        Args:
            config: 存储配置，如果不提供则使用默认配置
        """
        self.config = config or StorageConfig()
        self.db_path = self.config.db_path
        
        # 确保数据库目录存在
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
        
        # 初始化数据库
        self._init_database()
        
        # 最后备份时间
        self.last_backup_time = None
        
        logger.info(f"回测存储管理器初始化完成，数据库路径: {self.db_path}")
    
    def save_report(self, report_data: Dict) -> str:
        """保存回测报告
        
        Args:
            report_data: 报告数据字典
            
        Returns:
            str: 存储记录ID
            
        Raises:
            PVFRSException: 保存失败时抛出
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 准备数据
                report_id = report_data.get('report_id')
                task_id = report_data.get('task_id')
                strategy_name = self._extract_strategy_name(report_data)
                
                # 基本性能指标
                total_return = report_data.get('total_return', 0.0)
                annual_return = report_data.get('annual_return', 0.0)
                win_rate = report_data.get('win_rate', 0.0)
                max_drawdown = report_data.get('max_drawdown', 0.0)
                sharpe_ratio = report_data.get('sharpe_ratio', 0.0)
                
                # 配置信息
                config_data = report_data.get('config', {})
                start_date = config_data.get('start_date')
                end_date = config_data.get('end_date')
                initial_capital = config_data.get('initial_capital', 0.0)
                stock_count = len(config_data.get('stock_pool', []))
                
                # 交易统计（处理 None 值）
                trades = report_data.get('trades', [])
                total_trades = len(trades)
                winning_trades = len([t for t in trades if t.get('pnl') is not None and t.get('pnl', 0) > 0])
                
                # 序列化完整数据
                full_data_json = json.dumps(report_data, ensure_ascii=False)
                
                # 压缩数据（如果启用）
                if self.config.enable_compression:
                    full_data_json = self._compress_data(full_data_json)
                
                # 插入数据
                cursor.execute("""
                    INSERT OR REPLACE INTO backtest_reports (
                        report_id, task_id, strategy_name, created_at,
                        start_date, end_date, initial_capital, stock_count,
                        total_return, annual_return, win_rate, max_drawdown, sharpe_ratio,
                        total_trades, winning_trades, full_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    report_id, task_id, strategy_name, datetime.now().isoformat(),
                    start_date, end_date, initial_capital, stock_count,
                    total_return, annual_return, win_rate, max_drawdown, sharpe_ratio,
                    total_trades, winning_trades, full_data_json
                ))
                
                storage_id = cursor.lastrowid
                
                # 检查是否需要清理旧数据
                self._cleanup_old_reports_if_needed(cursor, strategy_name)
                
                conn.commit()
                
                # 检查是否需要备份
                self._backup_if_needed()
                
                logger.info(f"回测报告保存成功: {report_id} (存储ID: {storage_id})")
                return str(storage_id)
                
        except Exception as e:
            logger.error(f"保存回测报告失败: {str(e)}")
            raise PVFRSException(f"保存回测报告失败: {str(e)}")
    
    def get_report(self, report_id: str) -> Optional[Dict]:
        """获取回测报告
        
        Args:
            report_id: 报告ID
            
        Returns:
            Optional[Dict]: 报告数据，如果不存在则返回None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT full_data FROM backtest_reports 
                    WHERE report_id = ?
                """, (report_id,))
                
                result = cursor.fetchone()
                
                if result:
                    full_data_json = result[0]
                    
                    # 解压缩数据（如果需要）
                    if self.config.enable_compression:
                        full_data_json = self._decompress_data(full_data_json)
                    
                    report_data = json.loads(full_data_json)
                    
                    logger.debug(f"获取回测报告成功: {report_id}")
                    return report_data
                
                return None
                
        except Exception as e:
            logger.error(f"获取回测报告失败: {str(e)}")
            raise PVFRSException(f"获取回测报告失败: {str(e)}")
    
    def query_reports(self, filter_obj: Optional[QueryFilter] = None) -> List[Dict]:
        """查询回测报告
        
        Args:
            filter_obj: 查询过滤器
            
        Returns:
            List[Dict]: 报告列表
        """
        try:
            filter_obj = filter_obj or QueryFilter()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 构建查询条件
                where_conditions = []
                params = []
                
                if filter_obj.start_date:
                    where_conditions.append("created_at >= ?")
                    params.append(filter_obj.start_date)
                
                if filter_obj.end_date:
                    where_conditions.append("created_at <= ?")
                    params.append(filter_obj.end_date)
                
                if filter_obj.strategy_name:
                    where_conditions.append("strategy_name LIKE ?")
                    params.append(f"%{filter_obj.strategy_name}%")
                
                if filter_obj.min_return is not None:
                    where_conditions.append("total_return >= ?")
                    params.append(filter_obj.min_return)
                
                if filter_obj.max_drawdown is not None:
                    where_conditions.append("max_drawdown <= ?")
                    params.append(filter_obj.max_drawdown)
                
                if filter_obj.min_sharpe_ratio is not None:
                    where_conditions.append("sharpe_ratio >= ?")
                    params.append(filter_obj.min_sharpe_ratio)
                
                if filter_obj.task_ids:
                    placeholders = ",".join("?" * len(filter_obj.task_ids))
                    where_conditions.append(f"task_id IN ({placeholders})")
                    params.extend(filter_obj.task_ids)
                
                if filter_obj.report_ids:
                    placeholders = ",".join("?" * len(filter_obj.report_ids))
                    where_conditions.append(f"report_id IN ({placeholders})")
                    params.extend(filter_obj.report_ids)
                
                # 构建完整查询
                where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
                order_direction = "DESC" if filter_obj.order_desc else "ASC"
                
                query = f"""
                    SELECT * FROM backtest_reports 
                    WHERE {where_clause}
                    ORDER BY {filter_obj.order_by} {order_direction}
                    LIMIT ? OFFSET ?
                """
                
                params.extend([filter_obj.limit, filter_obj.offset])
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # 转换为字典列表
                columns = [desc[0] for desc in cursor.description]
                reports = []
                
                for row in rows:
                    report_dict = dict(zip(columns, row))
                    
                    # 解析完整数据（如果需要）
                    if 'full_data' in report_dict and report_dict['full_data']:
                        try:
                            full_data_json = report_dict['full_data']
                            if self.config.enable_compression:
                                full_data_json = self._decompress_data(full_data_json)
                            
                            full_data = json.loads(full_data_json)
                            report_dict.update(full_data)
                        except Exception as e:
                            logger.warning(f"解析报告完整数据失败: {str(e)}")
                    
                    # 移除原始JSON数据以减少传输量
                    if 'full_data' in report_dict:
                        del report_dict['full_data']
                    
                    reports.append(report_dict)
                
                logger.info(f"查询回测报告完成，返回 {len(reports)} 条记录")
                return reports
                
        except Exception as e:
            logger.error(f"查询回测报告失败: {str(e)}")
            raise PVFRSException(f"查询回测报告失败: {str(e)}")
    
    def get_report_summary(self, report_id: str) -> Optional[Dict]:
        """获取报告摘要信息
        
        Args:
            report_id: 报告ID
            
        Returns:
            Optional[Dict]: 报告摘要，如果不存在则返回None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT report_id, task_id, strategy_name, created_at,
                           start_date, end_date, initial_capital, stock_count,
                           total_return, annual_return, win_rate, max_drawdown, sharpe_ratio,
                           total_trades, winning_trades
                    FROM backtest_reports 
                    WHERE report_id = ?
                """, (report_id,))
                
                result = cursor.fetchone()
                
                if result:
                    columns = [desc[0] for desc in cursor.description]
                    summary = dict(zip(columns, result))
                    
                    # 计算衍生指标
                    summary['losing_trades'] = summary['total_trades'] - summary['winning_trades']
                    summary['win_rate_percentage'] = summary['win_rate'] * 100
                    
                    return summary
                
                return None
                
        except Exception as e:
            logger.error(f"获取报告摘要失败: {str(e)}")
            raise PVFRSException(f"获取报告摘要失败: {str(e)}")
    
    def delete_report(self, report_id: str) -> bool:
        """删除回测报告
        
        Args:
            report_id: 报告ID
            
        Returns:
            bool: 是否成功删除
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("DELETE FROM backtest_reports WHERE report_id = ?", (report_id,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logger.info(f"删除回测报告成功: {report_id}")
                    return True
                else:
                    logger.warning(f"报告不存在，无法删除: {report_id}")
                    return False
                
        except Exception as e:
            logger.error(f"删除回测报告失败: {str(e)}")
            raise PVFRSException(f"删除回测报告失败: {str(e)}")
    
    def get_statistics(self) -> Dict:
        """获取存储统计信息
        
        Returns:
            Dict: 统计信息
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 总报告数
                cursor.execute("SELECT COUNT(*) FROM backtest_reports")
                total_reports = cursor.fetchone()[0]
                
                # 按策略分组统计
                cursor.execute("""
                    SELECT strategy_name, COUNT(*) as count
                    FROM backtest_reports 
                    GROUP BY strategy_name
                    ORDER BY count DESC
                """)
                strategy_counts = dict(cursor.fetchall())
                
                # 最近30天的报告数
                thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
                cursor.execute("""
                    SELECT COUNT(*) FROM backtest_reports 
                    WHERE created_at >= ?
                """, (thirty_days_ago,))
                recent_reports = cursor.fetchone()[0]
                
                # 性能统计
                cursor.execute("""
                    SELECT 
                        AVG(total_return) as avg_return,
                        MAX(total_return) as max_return,
                        MIN(total_return) as min_return,
                        AVG(sharpe_ratio) as avg_sharpe,
                        AVG(max_drawdown) as avg_drawdown
                    FROM backtest_reports
                """)
                perf_stats = cursor.fetchone()
                
                # 数据库大小
                db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
                
                statistics = {
                    'total_reports': total_reports,
                    'strategy_distribution': strategy_counts,
                    'recent_reports_30d': recent_reports,
                    'performance_statistics': {
                        'average_return': perf_stats[0] or 0,
                        'max_return': perf_stats[1] or 0,
                        'min_return': perf_stats[2] or 0,
                        'average_sharpe_ratio': perf_stats[3] or 0,
                        'average_max_drawdown': perf_stats[4] or 0
                    },
                    'storage_info': {
                        'database_size_bytes': db_size,
                        'database_size_mb': db_size / (1024 * 1024),
                        'compression_enabled': self.config.enable_compression,
                        'auto_cleanup_days': self.config.auto_cleanup_days
                    }
                }
                
                return statistics
                
        except Exception as e:
            logger.error(f"获取存储统计信息失败: {str(e)}")
            raise PVFRSException(f"获取存储统计信息失败: {str(e)}")
    
    def cleanup_old_reports(self, days: Optional[int] = None) -> int:
        """清理旧的回测报告
        
        Args:
            days: 保留天数，如果不指定则使用配置中的值
            
        Returns:
            int: 清理的报告数量
        """
        try:
            cleanup_days = days or self.config.auto_cleanup_days
            cutoff_date = (datetime.now() - timedelta(days=cleanup_days)).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 删除旧报告
                cursor.execute("""
                    DELETE FROM backtest_reports 
                    WHERE created_at < ?
                """, (cutoff_date,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"清理旧报告完成，删除了 {deleted_count} 个报告")
                return deleted_count
                
        except Exception as e:
            logger.error(f"清理旧报告失败: {str(e)}")
            raise PVFRSException(f"清理旧报告失败: {str(e)}")
    
    def backup_database(self, backup_path: Optional[str] = None) -> str:
        """备份数据库
        
        Args:
            backup_path: 备份文件路径，如果不指定则自动生成
            
        Returns:
            str: 备份文件路径
        """
        try:
            if not backup_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"{self.db_path}.backup_{timestamp}"
            
            # 复制数据库文件
            import shutil
            shutil.copy2(self.db_path, backup_path)
            
            self.last_backup_time = datetime.now()
            
            logger.info(f"数据库备份完成: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"数据库备份失败: {str(e)}")
            raise PVFRSException(f"数据库备份失败: {str(e)}")
    
    def restore_database(self, backup_path: str) -> bool:
        """恢复数据库
        
        Args:
            backup_path: 备份文件路径
            
        Returns:
            bool: 是否成功恢复
        """
        try:
            if not os.path.exists(backup_path):
                raise PVFRSException(f"备份文件不存在: {backup_path}")
            
            # 备份当前数据库
            current_backup = f"{self.db_path}.before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            import shutil
            shutil.copy2(self.db_path, current_backup)
            
            # 恢复数据库
            shutil.copy2(backup_path, self.db_path)
            
            logger.info(f"数据库恢复完成，当前数据库已备份到: {current_backup}")
            return True
            
        except Exception as e:
            logger.error(f"数据库恢复失败: {str(e)}")
            raise PVFRSException(f"数据库恢复失败: {str(e)}")
    
    def _init_database(self) -> None:
        """初始化数据库表结构"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 创建回测报告表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS backtest_reports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        report_id TEXT UNIQUE NOT NULL,
                        task_id TEXT,
                        strategy_name TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        start_date TEXT,
                        end_date TEXT,
                        initial_capital REAL,
                        stock_count INTEGER,
                        total_return REAL,
                        annual_return REAL,
                        win_rate REAL,
                        max_drawdown REAL,
                        sharpe_ratio REAL,
                        total_trades INTEGER,
                        winning_trades INTEGER,
                        full_data TEXT,
                        UNIQUE(report_id)
                    )
                """)
                
                # 创建索引
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_report_id 
                    ON backtest_reports(report_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_strategy_name 
                    ON backtest_reports(strategy_name)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_created_at 
                    ON backtest_reports(created_at)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_performance 
                    ON backtest_reports(total_return, sharpe_ratio, max_drawdown)
                """)
                
                conn.commit()
                
                logger.debug("数据库表结构初始化完成")
                
        except Exception as e:
            logger.error(f"初始化数据库失败: {str(e)}")
            raise PVFRSException(f"初始化数据库失败: {str(e)}")
    
    def _extract_strategy_name(self, report_data: Dict) -> str:
        """提取策略名称"""
        # 尝试从多个位置获取策略名称
        if 'strategy_name' in report_data:
            return report_data['strategy_name']
        
        config = report_data.get('config', {})
        if 'strategy_name' in config:
            return config['strategy_name']
        
        # 默认使用PVFRS
        return "PVFRS"
    
    def _cleanup_old_reports_if_needed(self, cursor, strategy_name: str) -> None:
        """如果需要，清理该策略的旧报告"""
        try:
            # 检查该策略的报告数量
            cursor.execute("""
                SELECT COUNT(*) FROM backtest_reports 
                WHERE strategy_name = ?
            """, (strategy_name,))
            
            count = cursor.fetchone()[0]
            
            if count > self.config.max_reports_per_strategy:
                # 删除最旧的报告
                excess_count = count - self.config.max_reports_per_strategy
                cursor.execute("""
                    DELETE FROM backtest_reports 
                    WHERE strategy_name = ? 
                    ORDER BY created_at ASC 
                    LIMIT ?
                """, (strategy_name, excess_count))
                
                logger.info(f"清理策略 {strategy_name} 的 {excess_count} 个旧报告")
                
        except Exception as e:
            logger.warning(f"清理旧报告时发生异常: {str(e)}")
    
    def _backup_if_needed(self) -> None:
        """如果需要，执行自动备份"""
        if not self.config.backup_enabled:
            return
        
        try:
            now = datetime.now()
            
            if (self.last_backup_time is None or 
                (now - self.last_backup_time).total_seconds() > self.config.backup_interval_hours * 3600):
                
                self.backup_database()
                
        except Exception as e:
            logger.warning(f"自动备份失败: {str(e)}")
    
    def _compress_data(self, data: str) -> str:
        """压缩数据"""
        try:
            import gzip
            import base64
            
            compressed = gzip.compress(data.encode('utf-8'))
            return base64.b64encode(compressed).decode('ascii')
            
        except Exception as e:
            logger.warning(f"数据压缩失败，使用原始数据: {str(e)}")
            return data
    
    def _decompress_data(self, compressed_data: str) -> str:
        """解压缩数据"""
        try:
            import gzip
            import base64
            
            # 尝试解压缩
            compressed_bytes = base64.b64decode(compressed_data.encode('ascii'))
            decompressed = gzip.decompress(compressed_bytes)
            return decompressed.decode('utf-8')
            
        except Exception:
            # 如果解压缩失败，可能是未压缩的数据
            return compressed_data


# 便捷函数
def create_backtest_storage(config: Optional[StorageConfig] = None) -> BacktestStorage:
    """创建回测存储管理器实例
    
    Args:
        config: 存储配置
        
    Returns:
        BacktestStorage: 存储管理器实例
    """
    return BacktestStorage(config)


def create_query_filter(**kwargs) -> QueryFilter:
    """创建查询过滤器
    
    Args:
        **kwargs: 过滤器参数
        
    Returns:
        QueryFilter: 查询过滤器实例
    """
    return QueryFilter(**kwargs)