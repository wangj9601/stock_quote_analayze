"""
测试一阳穿三线策略信号保存功能（使用更大样本量）
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

def test_signal_save_with_larger_sample():
    """测试信号保存功能（使用更大样本量）"""
    
    logger.info("=" * 60)
    logger.info("测试一阳穿三线策略信号保存功能（100只股票）")
    logger.info("=" * 60)
    
    # 获取数据库会话
    db = next(get_db())
    
    try:
        # 1. 清空测试数据
        logger.info("清空现有信号数据...")
        db.execute(text("DELETE FROM one_yang_three_lines_signals"))
        db.commit()
        logger.info("✓ 清空完成")
        
        # 2. 运行策略（处理前100只股票）
        logger.info("\n运行策略（测试模式：前100只股票）...")
        results = OneYangThreeLinesStrategy.screening_one_yang_three_lines_strategy(
            db=db,
            limit=100
        )
        
        logger.info(f"\n✓ 策略执行完成，找到 {len(results)} 只符合条件的股票")
        
        # 3. 验证数据库中的信号
        logger.info("\n验证数据库中的信号...")
        query_result = db.execute(text("""
            SELECT code, name, signal_date, signal_score, crossed_count, position_type, risk_warnings
            FROM one_yang_three_lines_signals
            ORDER BY signal_score DESC
            LIMIT 10
        """))
        
        saved_signals = query_result.fetchall()
        logger.info(f"✓ 数据库中共有信号（显示前10条）")
        
        # 4. 显示保存的信号
        if saved_signals:
            logger.info("\n保存的信号列表（按评分排序）:")
            logger.info("-" * 100)
            logger.info(f"{'代码':<10} {'名称':<15} {'日期':<12} {'评分':<6} {'穿越':<6} {'位置':<8} {'风险提示':<30}")
            logger.info("-" * 100)
            for signal in saved_signals:
                code, name, signal_date, score, crossed, position, warnings = signal
                logger.info(f"{code:<10} {name:<15} {str(signal_date):<12} {score:<6} {crossed:<6} {position:<8} {warnings:<30}")
            logger.info("-" * 100)
        else:
            logger.info("未找到符合条件的信号")
        
        # 5. 统计信息
        stats_query = db.execute(text("""
            SELECT 
                COUNT(*) as total,
                AVG(signal_score) as avg_score,
                MAX(signal_score) as max_score,
                MIN(signal_score) as min_score,
                COUNT(CASE WHEN position_type = '低位' THEN 1 END) as low_position,
                COUNT(CASE WHEN position_type = '中位' THEN 1 END) as mid_position,
                COUNT(CASE WHEN position_type = '高位' THEN 1 END) as high_position
            FROM one_yang_three_lines_signals
        """))
        
        stats = stats_query.fetchone()
        if stats and stats[0] > 0:
            logger.info("\n信号统计:")
            logger.info(f"  总数: {stats[0]}")
            logger.info(f"  平均评分: {stats[1]:.2f}")
            logger.info(f"  最高评分: {stats[2]}")
            logger.info(f"  最低评分: {stats[3]}")
            logger.info(f"  低位突破: {stats[4]} 只")
            logger.info(f"  中位突破: {stats[5]} 只")
            logger.info(f"  高位突破: {stats[6]} 只")
        
        logger.info("\n" + "=" * 60)
        logger.info("测试完成！")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"测试失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    test_signal_save_with_larger_sample()
