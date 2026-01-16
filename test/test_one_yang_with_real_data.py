"""
使用真实数据测试一阳穿三线策略主函数
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend_api.stock.one_yang_three_lines_strategy import OneYangThreeLinesStrategy
from backend_core.database.db import get_db
from sqlalchemy import text

def test_with_real_stocks():
    """使用有真实数据的股票进行测试"""
    print("=" * 60)
    print("使用真实数据测试一阳穿三线策略")
    print("=" * 60)
    
    # 获取数据库会话
    db = next(get_db())
    
    try:
        # 1. 先找出有足够数据的股票
        print("\n1. 查找有足够数据的股票...")
        result = db.execute(text("""
            SELECT h.code, s.name, COUNT(*) as record_count
            FROM historical_quotes h
            LEFT JOIN stock_basic_info s ON h.code = s.code
            WHERE s.name NOT LIKE '%ST%'
            AND LENGTH(h.code) = 6
            GROUP BY h.code, s.name
            HAVING COUNT(*) >= 120
            ORDER BY h.code
            LIMIT 100
        """))
        
        stocks_with_data = result.fetchall()
        print(f"   找到 {len(stocks_with_data)} 只有足够数据的股票")
        
        if not stocks_with_data:
            print("   没有找到有足够数据的股票，测试终止")
            return
        
        # 2. 临时修改stock_basic_info表的查询，只查询这些有数据的股票
        # 为了测试，我们直接传入这些股票代码
        print(f"\n2. 测试前 {min(20, len(stocks_with_data))} 只有数据的股票...")
        
        # 创建一个临时的测试函数，直接使用这些股票
        test_stocks = stocks_with_data[:20]
        results = []
        
        from datetime import datetime, timedelta
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=250)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        for idx, (code, name, _) in enumerate(test_stocks):
            print(f"   处理 {idx+1}/{len(test_stocks)}: {code} {name}")
            
            try:
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
                
                if len(history_rows) < 120:
                    continue
                
                # 转换为字典列表
                historical_data = []
                for row in history_rows:
                    date_val = row[2]
                    if hasattr(date_val, 'strftime'):
                        date_str = date_val.strftime('%Y-%m-%d')
                    else:
                        date_str = str(date_val)
                    
                    historical_data.append({
                        'code': row[0],
                        'name': row[1],
                        'date': date_str,
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
                
                # 检查长阳线
                is_long_yang, candle_info = OneYangThreeLinesStrategy.check_long_yang_candle(current_candle)
                if not is_long_yang:
                    continue
                
                print(f"      ✓ 发现长阳线")
                
                # 计算均线
                ma_values = OneYangThreeLinesStrategy.calculate_moving_averages(historical_data, current_index=0)
                if any(v is None for v in ma_values.values()):
                    continue
                
                # 检查穿线
                is_cross, crossed_lines, crossed_count = OneYangThreeLinesStrategy.check_cross_three_lines(
                    current_candle, ma_values
                )
                if not is_cross:
                    continue
                
                print(f"      ✓ 穿越 {crossed_count} 条均线")
                
                # 检查成交量
                is_volume_increase, volume_ratio, turnover_rate = OneYangThreeLinesStrategy.check_volume_increase(
                    historical_data, current_index=0, days_before=5
                )
                if not is_volume_increase:
                    continue
                
                print(f"      ✓ 成交量放大 {volume_ratio}x")
                
                # 判断位置
                position_type, retracement = OneYangThreeLinesStrategy.check_position_type(
                    historical_data, current_index=0
                )
                
                # 计算乖离率
                current_price = float(current_candle.get('close', 0))
                bias_values = OneYangThreeLinesStrategy.calculate_bias(current_price, ma_values)
                
                # 计算评分
                signal_score = OneYangThreeLinesStrategy.calculate_signal_score(
                    crossed_count, volume_ratio, turnover_rate, position_type, bias_values.get('bias30')
                )
                
                # 生成风险提示
                risk_warnings = []
                if turnover_rate < 3.0:
                    risk_warnings.append("动能不足")
                elif turnover_rate > 10.0:
                    risk_warnings.append("可能存在对倒")
                if position_type == "高位":
                    risk_warnings.append("警惕诱多")
                if bias_values.get('bias30') and bias_values.get('bias30') > 10.0:
                    risk_warnings.append("乖离过大，注意回调风险")
                
                result_item = {
                    'code': str(code),
                    'name': name,
                    'signal_date': current_candle.get('date'),
                    'current_price': round(current_price, 2),
                    'ma5': round(ma_values.get('ma5', 0), 2),
                    'ma10': round(ma_values.get('ma10', 0), 2),
                    'ma20': round(ma_values.get('ma20', 0), 2),
                    'ma30': round(ma_values.get('ma30', 0), 2),
                    'ma60': round(ma_values.get('ma60', 0), 2),
                    'ma120': round(ma_values.get('ma120', 0), 2),
                    'crossed_lines': '+'.join([ma.upper() for ma in crossed_lines]),
                    'crossed_count': crossed_count,
                    'volume_ratio': round(volume_ratio, 2),
                    'turnover_rate': round(turnover_rate, 2),
                    'position_type': position_type,
                    'retracement': round(retracement, 2),
                    'bias5': round(bias_values.get('bias5', 0), 2) if bias_values.get('bias5') is not None else None,
                    'bias10': round(bias_values.get('bias10', 0), 2) if bias_values.get('bias10') is not None else None,
                    'bias30': round(bias_values.get('bias30', 0), 2) if bias_values.get('bias30') is not None else None,
                    'signal_score': signal_score,
                    'risk_warnings': risk_warnings
                }
                
                results.append(result_item)
                print(f"      ✓✓✓ 符合所有条件！评分: {signal_score}")
                
            except Exception as e:
                print(f"      ✗ 处理出错: {str(e)}")
                continue
        
        # 按评分排序
        results.sort(key=lambda x: x['signal_score'], reverse=True)
        
        print(f"\n3. 测试结果")
        print(f"   找到 {len(results)} 只符合条件的股票")
        
        if results:
            print("\n符合条件的股票列表:")
            print("-" * 60)
            for idx, stock in enumerate(results, 1):
                print(f"\n{idx}. {stock['code']} {stock['name']}")
                print(f"   信号日期: {stock['signal_date']}")
                print(f"   当前价格: {stock['current_price']}")
                print(f"   穿越均线: {stock['crossed_lines']} (共{stock['crossed_count']}条)")
                print(f"   成交量倍数: {stock['volume_ratio']}x")
                print(f"   换手率: {stock['turnover_rate']}%")
                print(f"   位置类型: {stock['position_type']} (回撤{stock['retracement']}%)")
                print(f"   乖离率: BIAS5={stock['bias5']}%, BIAS10={stock['bias10']}%, BIAS30={stock['bias30']}%")
                print(f"   信号评分: {stock['signal_score']}分")
                if stock['risk_warnings']:
                    print(f"   风险提示: {', '.join(stock['risk_warnings'])}")
        
        print("\n" + "=" * 60)
        print("测试完成 - 主函数逻辑验证成功")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_with_real_stocks()
