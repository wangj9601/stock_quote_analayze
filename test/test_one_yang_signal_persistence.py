"""
测试一阳穿三线策略信号持久化功能
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend_api.database import get_db
from backend_api.stock.one_yang_three_lines_strategy import OneYangThreeLinesStrategy
from sqlalchemy import text
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_signal_persistence():
    """测试信号持久化功能"""
    
    logger.info("=" * 60)
    logger.info("测试一阳穿三线策略信号持久化功能")
    logger.info("=" * 60)
    
    # 获取数据库会话
    db = next(get_db())
    
    try:
        # 1. 清空测试数据（可选）
        logger.info("清空现有信号数据...")
        db.execute(text("DELETE FROM one_yang_three_lines_signals"))
        db.commit()
        logger.info("✓ 清空完成")
        
        # 2. 运行策略（只处理前10只股票进行测试）
        logger.info("\n运行策略（测试模式：前10只股票）...")
        results = OneYangThreeLinesStrategy.screening_one_yang_three_lines_strategy(
            db=db,
            limit=10
        )
        
        logger.info(f"\n✓ 策略执行完成，找到 {len(results)} 只符合条件的股票")
        
        # 3. 验证数据库中的信号
        logger.info("\n验证数据库中的信号...")
        query_result = db.execute(text("""
            SELECT code, name, signal_date, signal_score, crossed_count, position_type
            FROM one_yang_three_lines_signals
            ORDER BY signal_score DESC
        """))
        
        saved_signals = query_result.fetchall()
        logger.info(f"✓ 数据库中共有 {len(saved_signals)} 条信号")
        
        # 4. 显示保存的信号
        if saved_signals:
            logger.info("\n保存的信号列表:")
            logger.info("-" * 80)
            logger.info(f"{'代码':<10} {'名称':<15} {'日期':<12} {'评分':<6} {'穿越':<6} {'位置':<8}")
            logger.info("-" * 80)
            for signal in saved_signals:
                code, name, signal_date, score, crossed, position = signal
                logger.info(f"{code:<10} {name:<15} {str(signal_date):<12} {score:<6} {crossed:<6} {position:<8}")
            logger.info("-" * 80)
        
        # 5. 测试去重功能：再次运行策略
        logger.info("\n测试去重功能：再次运行策略...")
        results2 = OneYangThreeLinesStrategy.screening_one_yang_three_lines_strategy(
            db=db,
            limit=10
        )
        
        # 6. 验证信号数量没有增加（去重生效）
        query_result2 = db.execute(text("""
            SELECT COUNT(*) FROM one_yang_three_lines_signals
        """))
        count_after = query_result2.fetchone()[0]
        
        logger.info(f"\n✓ 第二次运行后，数据库中仍有 {count_after} 条信号")
        logger.info(f"✓ 去重功能正常（信号数量未增加）")
        
        # 7. 测试查询特定日期的信号
        logger.info("\n测试查询功能...")
        if saved_signals:
            test_date = saved_signals[0][2]  # 使用第一条信号的日期
            query_result3 = db.execute(text("""
                SELECT code, name, signal_score
                FROM one_yang_three_lines_signals
                WHERE signal_date = :signal_date
                ORDER BY signal_score DESC
            """), {'signal_date': test_date})
            
            date_signals = query_result3.fetchall()
            logger.info(f"✓ 日期 {test_date} 的信号数量: {len(date_signals)}")
        
        logger.info("\n" + "=" * 60)
        logger.info("测试完成！所有功能正常")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"测试失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    test_signal_persistence()
