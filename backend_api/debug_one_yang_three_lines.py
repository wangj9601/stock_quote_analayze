#!/usr/bin/env python3
"""
调试一阳穿三线策略 - 分析为什么没有筛选出股票
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
import json
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入策略类
from stock.one_yang_three_lines_strategy import OneYangThreeLinesStrategy

# 配置日志
def setup_debug_logger():
    """配置调试日志到项目根 logs/（.env 中 LOG_TO_FILE=true 时才写文件）"""
    from backend_core.logging_utils import should_log_to_file, resolve_log_file
    log_filename = f"debug_one_yang_three_lines_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_filepath = resolve_log_file(log_filename)

    logger = logging.getLogger('debug_one_yang_three_lines')
    logger.setLevel(logging.DEBUG)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    if should_log_to_file():
        file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

def debug_strategy(db: Session, limit: int = 100):
    """调试策略执行过程"""
    logger = setup_debug_logger()
    
    # 统计信息
    stats = {
        'total_stocks': 0,
        'processed_stocks': 0,
        'data_insufficient': 0,
        'not_long_yang': 0,
        'not_cross_lines': 0,
        'not_volume_increase': 0,
        'turnover_rate_invalid': 0,
        'found_signals': 0,
        'errors': 0,
        'long_yang_details': [],
        'cross_lines_details': [],
        'volume_details': []
    }
    
    try:
        logger.info("=" * 80)
        logger.info("🔍 开始调试一阳穿三线策略")
        logger.info("=" * 80)
        
        # 1. 获取股票列表
        stocks_query = db.execute(text("""
            SELECT DISTINCT code, name 
            FROM stock_basic_info 
            WHERE LENGTH(code) = 6
            AND name NOT LIKE '%ST%'
            ORDER BY code
            LIMIT :limit
        """), {'limit': limit})
        
        stocks = stocks_query.fetchall()
        stats['total_stocks'] = len(stocks)
        
        logger.info(f"📊 获取 {len(stocks)} 只股票进行调试")
        
        # 2. 设置参数
        min_increase_percent = 3.0
        min_body_ratio = 0.7
        min_cross_lines = 3
        min_volume_ratio = 2.0
        min_turnover_rate = 3.0
        max_turnover_rate = 10.0
        ma_periods = [5, 10, 20, 30, 60, 120]
        
        # 3. 计算日期范围
        max_ma_period = max(ma_periods)
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=max_ma_period * 2)
        
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        logger.info(f"📅 查询日期范围: {start_date_str} 至 {end_date_str}")
        
        # 4. 逐个分析股票
        for idx, (code, name) in enumerate(stocks):
            try:
                logger.debug(f"\n🔍 分析股票 {idx+1}/{len(stocks)}: {code} {name}")
                
                # 获取历史数据
                history_query = db.execute(text("""
                    SELECT code, name, date, open, close, high, low, 
                           change_percent, volume, amount, turnover_rate
                    FROM historical_quotes 
                    WHERE code = :code 
                    AND date >= :start_date 
                    AND date <= :end_date
                    ORDER BY date DESC
                """), {
                    'code': str(code),
                    'start_date': start_date_str,
                    'end_date': end_date_str
                })
                
                history_rows = history_query.fetchall()
                
                # 检查数据充足性
                if len(history_rows) < max_ma_period:
                    stats['data_insufficient'] += 1
                    logger.debug(f"  ❌ 数据不足: 需要{max_ma_period}天，实际{len(history_rows)}天")
                    continue
                
                # 转换数据格式
                historical_data = []
                for row in history_rows:
                    historical_data.append({
                        'code': row[0],
                        'name': row[1],
                        'date': str(row[2]),
                        'open': float(row[3]) if row[3] else 0.0,
                        'close': float(row[4]) if row[4] else 0.0,
                        'high': float(row[5]) if row[5] else 0.0,
                        'low': float(row[6]) if row[6] else 0.0,
                        'change_percent': float(row[7]) if row[7] else 0.0,
                        'volume': float(row[8]) if row[8] else 0.0,
                        'amount': float(row[9]) if row[9] else 0.0,
                        'turnover_rate': float(row[10]) if row[10] else 0.0
                    })
                
                current_candle = historical_data[0]
                stats['processed_stocks'] += 1
                
                # 检查1: 长阳线
                is_long_yang, candle_info = OneYangThreeLinesStrategy.check_long_yang_candle(
                    current_candle, min_increase_percent, min_body_ratio
                )
                
                if not is_long_yang:
                    stats['not_long_yang'] += 1
                    # 记录详细信息
                    stats['long_yang_details'].append({
                        'code': code,
                        'name': name,
                        'change_percent': candle_info['change_percent'] * 100,
                        'body_ratio': candle_info['body_ratio'],
                        'is_yang': candle_info['is_yang']
                    })
                    logger.debug(f"  ❌ 不是长阳线: 涨幅{candle_info['change_percent']*100:.2f}%, 实体占比{candle_info['body_ratio']:.2f}")
                    continue
                
                logger.debug(f"  ✅ 是长阳线: 涨幅{candle_info['change_percent']*100:.2f}%, 实体占比{candle_info['body_ratio']:.2f}")
                
                # 检查2: 均线计算
                ma_values = OneYangThreeLinesStrategy.calculate_moving_averages(
                    historical_data, current_index=0, periods=ma_periods
                )
                
                if any(v is None for v in ma_values.values()):
                    logger.debug(f"  ❌ 均线计算失败")
                    continue
                
                # 检查3: 穿越均线
                is_cross, crossed_lines, crossed_count = OneYangThreeLinesStrategy.check_cross_three_lines(
                    current_candle, ma_values, min_cross_lines
                )
                
                if not is_cross:
                    stats['not_cross_lines'] += 1
                    # 记录详细信息
                    stats['cross_lines_details'].append({
                        'code': code,
                        'name': name,
                        'close_price': current_candle['close'],
                        'ma_values': ma_values,
                        'crossed_count': crossed_count
                    })
                    logger.debug(f"  ❌ 未穿越足够均线: 只穿越{crossed_count}条，需要{min_cross_lines}条")
                    continue
                
                logger.debug(f"  ✅ 穿越{crossed_count}条均线: {', '.join(crossed_lines)}")
                
                # 检查4: 成交量
                is_volume_increase, volume_ratio, turnover_rate = OneYangThreeLinesStrategy.check_volume_increase(
                    historical_data, current_index=0, 
                    min_volume_ratio=min_volume_ratio,
                    min_turnover_rate=min_turnover_rate,
                    max_turnover_rate=max_turnover_rate
                )
                
                if not is_volume_increase:
                    stats['not_volume_increase'] += 1
                    # 记录详细信息
                    stats['volume_details'].append({
                        'code': code,
                        'name': name,
                        'volume_ratio': volume_ratio,
                        'turnover_rate': turnover_rate
                    })
                    logger.debug(f"  ❌ 成交量未放大: {volume_ratio}倍，需要{min_volume_ratio}倍")
                    continue
                
                # 检查5: 换手率
                if turnover_rate < min_turnover_rate or turnover_rate > max_turnover_rate:
                    stats['turnover_rate_invalid'] += 1
                    logger.debug(f"  ❌ 换手率不符合: {turnover_rate:.2f}%, 范围{min_turnover_rate}-{max_turnover_rate}%")
                    continue
                
                # 如果所有条件都满足
                stats['found_signals'] += 1
                logger.info(f"  🎯 找到信号: {code} {name}")
                
            except Exception as e:
                stats['errors'] += 1
                logger.error(f"  💥 处理股票 {code} 时出错: {str(e)}")
                continue
        
        # 5. 输出统计结果
        logger.info("\n" + "=" * 80)
        logger.info("📊 调试统计结果")
        logger.info("=" * 80)
        logger.info(f"总股票数: {stats['total_stocks']}")
        logger.info(f"成功处理: {stats['processed_stocks']}")
        logger.info(f"数据不足: {stats['data_insufficient']} ({stats['data_insufficient']/stats['total_stocks']*100:.1f}%)")
        logger.info(f"不是长阳线: {stats['not_long_yang']} ({stats['not_long_yang']/stats['processed_stocks']*100:.1f}%)")
        logger.info(f"未穿越均线: {stats['not_cross_lines']} ({stats['not_cross_lines']/stats['processed_stocks']*100:.1f}%)")
        logger.info(f"成交量不足: {stats['not_volume_increase']} ({stats['not_volume_increase']/stats['processed_stocks']*100:.1f}%)")
        logger.info(f"换手率异常: {stats['turnover_rate_invalid']} ({stats['turnover_rate_invalid']/stats['processed_stocks']*100:.1f}%)")
        logger.info(f"找到信号: {stats['found_signals']} ({stats['found_signals']/stats['processed_stocks']*100:.1f}%)")
        logger.info(f"处理错误: {stats['errors']}")
        
        # 6. 详细分析
        if stats['not_long_yang'] > 0:
            logger.info(f"\n📈 长阳线分析 (前10个):")
            for detail in stats['long_yang_details'][:10]:
                logger.info(f"  {detail['code']} {detail['name']}: 涨幅{detail['change_percent']:.2f}%, 实体占比{detail['body_ratio']:.2f}, 是阳线{detail['is_yang']}")
        
        if stats['not_cross_lines'] > 0:
            logger.info(f"\n📊 均线穿越分析 (前10个):")
            for detail in stats['cross_lines_details'][:10]:
                logger.info(f"  {detail['code']} {detail['name']}: 收盘价{detail['close_price']}, 穿越{detail['crossed_count']}条均线")
        
        if stats['not_volume_increase'] > 0:
            logger.info(f"\n📈 成交量分析 (前10个):")
            for detail in stats['volume_details'][:10]:
                logger.info(f"  {detail['code']} {detail['name']}: 成交量{detail['volume_ratio']:.2f}倍, 换手率{detail['turnover_rate']:.2f}%")
        
        # 7. 保存详细统计到项目根 logs/
        from backend_core.logging_utils import resolve_log_file
        stats_file = str(resolve_log_file(f"debug_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"))
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n📁 详细统计已保存到: {stats_file}")
        logger.info("=" * 80)
        
        return stats
        
    except Exception as e:
        logger.error(f"调试过程出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def main():
    """主函数"""
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        # 数据库连接配置（请根据实际情况修改）
        DATABASE_URL = "postgresql+psycopg2://postgres:qidianspacetime@localhost:5446/stock_analysis"
        
        # 创建数据库连接
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        db = Session()
        
        try:
            print("🔍 开始调试一阳穿三线策略...")
            print("📊 将分析前100只股票的详细情况")
            
            # 执行调试
            stats = debug_strategy(db, limit=100)
            
            if stats:
                print(f"\n✅ 调试完成！")
                print(f"📊 处理了 {stats['total_stocks']} 只股票")
                print(f"🎯 找到 {stats['found_signals']} 只符合条件的股票")
                
                if stats['found_signals'] == 0:
                    print("\n❌ 没有找到符合条件的股票，主要原因:")
                    if stats['not_long_yang'] > stats['processed_stocks'] * 0.5:
                        print("  • 大部分股票不是长阳线（涨幅<3%或实体占比<0.7）")
                    if stats['not_cross_lines'] > stats['processed_stocks'] * 0.3:
                        print("  • 很多股票未穿越足够数量的均线")
                    if stats['not_volume_increase'] > stats['processed_stocks'] * 0.2:
                        print("  • 成交量放大的股票较少")
                    
                    print("\n💡 建议:")
                    print("  1. 适当降低涨幅要求（如从3%降到2%）")
                    print("  2. 降低实体占比要求（如从0.7降到0.6）")
                    print("  3. 减少穿越均线数量（如从3条降到2条）")
                    print("  4. 降低成交量放大倍数（如从2.0降到1.5）")
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ 调试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
