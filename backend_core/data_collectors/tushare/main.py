import argparse
from .realtime import RealtimeQuoteCollector
from .historical import HistoricalQuoteCollector
from .index import IndexQuoteCollector

def main():
    parser = argparse.ArgumentParser(description='Tushare数据采集工具')
    parser.add_argument('--type', choices=['realtime', 'historical', 'index'], required=True, help='采集类型')
    parser.add_argument('--date', type=str, help='历史行情采集日期，格式YYYYMMDD')
    args = parser.parse_args()
    if args.type == 'realtime':
        collector = RealtimeQuoteCollector()
        collector.collect_quotes()
    elif args.type == 'historical':
        if not args.date:
            print('请指定--date参数')
            return
        collector = HistoricalQuoteCollector()
        collector.collect_historical_quotes(args.date)
    elif args.type == 'index':
        collector = IndexQuoteCollector()
        collector.collect_index_quotes()

if __name__ == '__main__':
    main()
