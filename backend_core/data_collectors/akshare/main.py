"""
AKShare数据采集器入口文件
用于运行各种数据采集任务
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 直接导入当前目录下的模块
from realtime import RealtimeQuoteCollector
from historical import HistoricalQuoteCollector
from index import IndexQuoteCollector

def run_realtime_collector():
    """运行实时行情采集器"""
    collector = RealtimeQuoteCollector()
    success = collector.collect_quotes()
    if success:
        print("实时行情数据采集成功")
    else:
        print("实时行情数据采集失败")

def run_historical_collector(date_str: str):
    """运行历史行情采集器"""
    collector = HistoricalQuoteCollector()
    success_count, error_count = collector.collect_quotes(date_str)
    print(f"历史行情数据采集完成。成功: {success_count}, 失败: {error_count}")

def run_index_collector():
    """运行指数行情采集器"""
    collector = IndexQuoteCollector()
    try:
        # 获取指数列表
        index_list = collector.get_index_list()
        print(f"获取到 {len(index_list)} 个指数")
        
        # 获取指数行情
        index_quotes = collector.get_index_quotes()
        print(f"获取到 {len(index_quotes)} 条指数行情数据")
        
        # 获取上证指数成分股
        components = collector.get_index_components('000001')
        print(f"获取到 {len(components)} 只上证指数成分股")
        
    except Exception as e:
        print(f"指数数据采集失败: {str(e)}")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='AKShare数据采集工具')
    parser.add_argument('--type', type=str, required=True,
                      choices=['realtime', 'historical', 'index'],
                      help='采集类型：realtime(实时行情), historical(历史行情), index(指数行情)')
    parser.add_argument('--date', type=str,
                      help='历史行情采集的日期，格式：YYYYMMDD')
    
    args = parser.parse_args()
    
    if args.type == 'realtime':
        run_realtime_collector()
    elif args.type == 'historical':
        if not args.date:
            print("历史行情采集需要指定日期参数 --date")
            sys.exit(1)
        run_historical_collector(args.date)
    elif args.type == 'index':
        run_index_collector() 