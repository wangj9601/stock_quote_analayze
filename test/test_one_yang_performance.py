"""
一阳穿三线策略性能测试

测试目标:
1. 测试处理5000只股票的执行时间
2. 如果超过5分钟，记录性能瓶颈
3. 记录详细的性能指标

性能要求:
- 处理5000只股票应在5分钟内完成
- 如果超时，需要进行优化（批量查询、索引优化等）
"""

import pytest
import time
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from backend_core.database.db import get_db
from backend_api.stock.one_yang_three_lines_strategy import OneYangThreeLinesStrategy

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestOneYangPerformance:
    """一阳穿三线策略性能测试类"""
    
    def test_performance_5000_stocks(self):
        """
        测试处理5000只股票的性能
        
        性能指标:
        - 总执行时间
        - 平均每只股票处理时间
        - 数据库查询时间
        - 策略计算时间
        """
        logger.info("=" * 80)
        logger.info("开始性能测试: 处理5000只股票")
        logger.info("=" * 80)
        
        # 获取数据库会话
        db = next(get_db())
        
        try:
            # 记录开始时间
            start_time = time.time()
            start_datetime = datetime.now()
            
            logger.info(f"测试开始时间: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"目标: 处理5000只股票")
            logger.info(f"性能要求: 5分钟内完成 (300秒)")
            logger.info("-" * 80)
            
            # 执行策略（限制处理5000只股票）
            results = OneYangThreeLinesStrategy.screening_one_yang_three_lines_strategy(
                db=db,
                limit=5000
            )
            
            # 记录结束时间
            end_time = time.time()
            end_datetime = datetime.now()
            
            # 计算性能指标
            total_time = end_time - start_time
            total_minutes = total_time / 60
            avg_time_per_stock = total_time / 5000
            
            logger.info("=" * 80)
            logger.info("性能测试完成!")
            logger.info("=" * 80)
            logger.info(f"测试结束时间: {end_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"总执行时间: {total_time:.2f} 秒 ({total_minutes:.2f} 分钟)")
            logger.info(f"平均每只股票处理时间: {avg_time_per_stock:.4f} 秒")
            logger.info(f"找到符合条件的股票: {len(results)} 只")
            logger.info("-" * 80)
            
            # 性能评估
            if total_time <= 300:  # 5分钟 = 300秒
                logger.info("✓ 性能测试通过: 在5分钟内完成")
                logger.info(f"  剩余时间: {300 - total_time:.2f} 秒")
            else:
                logger.warning("✗ 性能测试未通过: 超过5分钟")
                logger.warning(f"  超时: {total_time - 300:.2f} 秒")
                logger.warning("  建议优化:")
                logger.warning("  1. 批量查询历史数据")
                logger.warning("  2. 添加数据库索引")
                logger.warning("  3. 优化SQL查询")
                logger.warning("  4. 使用缓存机制")
            
            logger.info("=" * 80)
            
            # 断言：性能要求
            assert total_time <= 300, f"性能测试失败: 处理5000只股票耗时{total_time:.2f}秒，超过5分钟限制"
            
        finally:
            db.close()
    
    def test_performance_1000_stocks_baseline(self):
        """
        测试处理1000只股票的基准性能
        
        用于评估系统基准性能，为优化提供参考
        """
        logger.info("=" * 80)
        logger.info("开始基准性能测试: 处理1000只股票")
        logger.info("=" * 80)
        
        # 获取数据库会话
        db = next(get_db())
        
        try:
            # 记录开始时间
            start_time = time.time()
            start_datetime = datetime.now()
            
            logger.info(f"测试开始时间: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"目标: 处理1000只股票")
            logger.info("-" * 80)
            
            # 执行策略（限制处理1000只股票）
            results = OneYangThreeLinesStrategy.screening_one_yang_three_lines_strategy(
                db=db,
                limit=1000
            )
            
            # 记录结束时间
            end_time = time.time()
            end_datetime = datetime.now()
            
            # 计算性能指标
            total_time = end_time - start_time
            total_minutes = total_time / 60
            avg_time_per_stock = total_time / 1000
            
            # 预估5000只股票的时间
            estimated_5000_time = avg_time_per_stock * 5000
            estimated_5000_minutes = estimated_5000_time / 60
            
            logger.info("=" * 80)
            logger.info("基准性能测试完成!")
            logger.info("=" * 80)
            logger.info(f"测试结束时间: {end_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"总执行时间: {total_time:.2f} 秒 ({total_minutes:.2f} 分钟)")
            logger.info(f"平均每只股票处理时间: {avg_time_per_stock:.4f} 秒")
            logger.info(f"找到符合条件的股票: {len(results)} 只")
            logger.info("-" * 80)
            logger.info(f"预估处理5000只股票时间: {estimated_5000_time:.2f} 秒 ({estimated_5000_minutes:.2f} 分钟)")
            
            if estimated_5000_time <= 300:
                logger.info("✓ 预估可以在5分钟内完成5000只股票的处理")
            else:
                logger.warning("✗ 预估无法在5分钟内完成5000只股票的处理")
                logger.warning(f"  预计超时: {estimated_5000_time - 300:.2f} 秒")
            
            logger.info("=" * 80)
            
        finally:
            db.close()
    
    def test_performance_100_stocks_detailed(self):
        """
        测试处理100只股票的详细性能分析
        
        分析各个环节的耗时，找出性能瓶颈
        """
        logger.info("=" * 80)
        logger.info("开始详细性能分析: 处理100只股票")
        logger.info("=" * 80)
        
        # 获取数据库会话
        db = next(get_db())
        
        try:
            # 记录开始时间
            start_time = time.time()
            start_datetime = datetime.now()
            
            logger.info(f"测试开始时间: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"目标: 处理100只股票并分析各环节耗时")
            logger.info("-" * 80)
            
            # 执行策略（限制处理100只股票）
            results = OneYangThreeLinesStrategy.screening_one_yang_three_lines_strategy(
                db=db,
                limit=100
            )
            
            # 记录结束时间
            end_time = time.time()
            end_datetime = datetime.now()
            
            # 计算性能指标
            total_time = end_time - start_time
            avg_time_per_stock = total_time / 100
            
            logger.info("=" * 80)
            logger.info("详细性能分析完成!")
            logger.info("=" * 80)
            logger.info(f"测试结束时间: {end_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"总执行时间: {total_time:.2f} 秒")
            logger.info(f"平均每只股票处理时间: {avg_time_per_stock:.4f} 秒")
            logger.info(f"找到符合条件的股票: {len(results)} 只")
            logger.info("-" * 80)
            
            # 性能分析建议
            logger.info("性能优化建议:")
            logger.info("1. 数据库查询优化:")
            logger.info("   - 为 historical_quotes 表的 (code, date) 添加复合索引")
            logger.info("   - 为 stock_basic_info 表的 name 字段添加索引（用于ST股票过滤）")
            logger.info("2. 批量查询优化:")
            logger.info("   - 考虑批量获取多只股票的历史数据")
            logger.info("   - 减少数据库往返次数")
            logger.info("3. 计算优化:")
            logger.info("   - 使用NumPy向量化计算加速均线计算")
            logger.info("   - 缓存重复计算的结果")
            logger.info("4. 并行处理:")
            logger.info("   - 考虑使用多进程或多线程并行处理股票")
            logger.info("=" * 80)
            
        finally:
            db.close()


if __name__ == '__main__':
    # 运行性能测试
    pytest.main([__file__, '-v', '-s'])
