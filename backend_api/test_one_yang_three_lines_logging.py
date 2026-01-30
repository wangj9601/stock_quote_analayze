#!/usr/bin/env python3
"""
测试一阳穿三线策略日志功能
"""

import sys
import os
import logging
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_logging():
    """测试日志功能"""
    try:
        # 导入策略模块
        from stock.one_yang_three_lines_strategy import OneYangThreeLinesStrategy, setup_strategy_logger
        
        print("=" * 60)
        print("🧪 测试一阳穿三线策略日志功能")
        print("=" * 60)
        
        # 测试日志配置
        logger = setup_strategy_logger()
        
        # 测试各种级别的日志
        logger.info("🚀 开始测试日志功能")
        logger.debug("🔍 这是一条调试信息")
        logger.warning("⚠️ 这是一条警告信息")
        logger.error("❌ 这是一条错误信息")
        
        # 测试策略方法日志
        print("\n📊 测试策略方法日志:")
        
        # 测试长阳线检测
        test_candle = {
            'open': 10.0,
            'close': 10.5,
            'high': 10.8,
            'low': 9.8
        }
        
        is_long_yang, candle_info = OneYangThreeLinesStrategy.check_long_yang_candle(test_candle)
        logger.info(f"📈 长阳线检测结果: {is_long_yang}, 涨幅: {candle_info['change_percent']*100:.2f}%")
        
        # 测试均线计算
        test_data = [
            {'close': 10.1}, {'close': 10.2}, {'close': 10.3},
            {'close': 10.4}, {'close': 10.5}, {'close': 10.6},
            {'close': 10.7}, {'close': 10.8}, {'close': 10.9},
            {'close': 11.0}, {'close': 11.1}, {'close': 11.2}
        ]
        
        ma_values = OneYangThreeLinesStrategy.calculate_moving_averages(test_data, 0, [5, 10])
        logger.info(f"📊 均线计算结果: MA5={ma_values.get('ma5')}, MA10={ma_values.get('ma10')}")
        
        # 测试成交量检测
        test_volume_data = [
            {'volume': 1000000}, {'volume': 1200000}, {'volume': 1100000},
            {'volume': 1300000}, {'volume': 1150000}, {'volume': 2500000}
        ]
        
        is_volume_increase, volume_ratio, turnover_rate = OneYangThreeLinesStrategy.check_volume_increase(
            test_volume_data, 0
        )
        logger.info(f"📈 成交量检测结果: 放量={is_volume_increase}, 倍数={volume_ratio}, 换手率={turnover_rate:.2f}%")
        
        print("\n✅ 日志功能测试完成!")
        print("📁 请检查 backend_api/logs/ 目录下的日志文件")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_logging()
    sys.exit(0 if success else 1)
