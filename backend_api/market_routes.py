# backend_api/market_routes.py

from fastapi import APIRouter
import akshare as ak
from datetime import datetime
from fastapi.responses import JSONResponse
import random
import traceback
import pandas as pd
import numpy as np



router = APIRouter(prefix="/api/market", tags=["market"])

def safe_float(value):
    """安全地将值转换为浮点数，处理 NaN 和无效值"""
    try:
        if pd.isna(value) or value in [None, '', '-']:
            return None
        return float(value)
    except (ValueError, TypeError):
        return None

@router.get("/indices")
def get_market_indices():
    """获取市场指数数据(akshare)"""
    try:
        print("📊 开始获取市场指数数据...")
        
        # 尝试从akshare获取数据
        try:
            print("正在从akshare获取沪深重要指数...")
            df1 = ak.stock_zh_index_spot_em(symbol="沪深重要指数")
            print("正在从akshare获取上证系列指数...")
            df2 = ak.stock_zh_index_spot_em(symbol="上证系列指数")
            print("正在从akshare获取深证系列指数...")
            df3 = ak.stock_zh_index_spot_em(symbol="深证系列指数")
            
            # 合并所有数据框
            df = pd.concat([df1, df2, df3], ignore_index=True)
            # 删除重复的行
            df = df.drop_duplicates(subset=['代码'], keep='first')
            # 将所有 NaN 值替换为 None
            df = df.replace({np.nan: None})
            print(f"成功获取 {len(df)} 条指数数据")
            
        except Exception as e:
            print(f"❌ 从akshare获取数据失败: {str(e)}")
            print("将使用模拟数据...")
            df = pd.DataFrame()  # 创建空DataFrame
        
        target_indices = {
            '000001': '上证指数',
            '399001': '深证成指',
            '399006': '创业板指',
            '000300': '沪深300'
        }
        
        indices_data = []
        for code, name in target_indices.items():
            try:
                if not df.empty:
                    index_row = df[df['代码'] == code]
                    if not index_row.empty:
                        row = index_row.iloc[0]
                        indices_data.append({
                            'code': code,
                            'name': name,
                            'current': safe_float(row['最新价']),
                            'change': safe_float(row['涨跌额']),
                            'change_percent': safe_float(row['涨跌幅']),
                            'high': safe_float(row['最高']),
                            'low': safe_float(row['最低']),
                            'open': safe_float(row['今开']),
                            'yesterday_close': safe_float(row['昨收']),
                            'volume': safe_float(row['成交量']),
                            'turnover': safe_float(row['成交额']),
                            'timestamp': datetime.now().isoformat()
                        })
                        continue
                
                # 如果获取失败或数据不存在，使用模拟数据
                print(f"为 {name}({code}) 生成模拟数据...")
                base_price = random.uniform(3300, 3400) if code == '000001' else \
                             random.uniform(10800, 11200) if code == '399001' else \
                             random.uniform(2300, 2600) if code == '399006' else \
                             random.uniform(3800, 4000)
                change_amount = random.uniform(-50, 50)
                change_percent = (change_amount / base_price) * 100
                
                indices_data.append({
                    'code': code,
                    'name': name,
                    'current': round(base_price, 2),
                    'change': round(change_amount, 2),
                    'change_percent': round(change_percent, 2),
                    'high': round(base_price * 1.02, 2),
                    'low': round(base_price * 0.98, 2),
                    'open': round(base_price - change_amount, 2),
                    'yesterday_close': round(base_price - change_amount, 2),
                    'volume': random.randint(100000000, 500000000),
                    'turnover': random.randint(100000000000, 800000000000),
                    'timestamp': datetime.now().isoformat(),
                    'is_mock': True
                })
                
            except Exception as e:
                print(f"❌ 处理指数 {name}({code}) 时出错: {str(e)}")
                # 使用最基本的模拟数据
                indices_data.append({
                    'code': code,
                    'name': name,
                    'current': 0,
                    'change': 0,
                    'change_percent': 0,
                    'high': 0,
                    'low': 0,
                    'open': 0,
                    'yesterday_close': 0,
                    'volume': 0,
                    'turnover': 0,
                    'timestamp': datetime.now().isoformat(),
                    'is_mock': True,
                    'error': str(e)
                })
        
        print(f"✅ 成功生成 {len(indices_data)} 条指数数据")
        return JSONResponse({'success': True, 'data': indices_data})
        
    except Exception as e:
        print(f"❌ 获取市场指数数据失败: {str(e)}")
        print("详细错误信息:")
        traceback.print_exc()
        # 返回最基本的错误响应
        return JSONResponse(
            content={
                'success': False,
                'message': '获取市场指数数据失败',
                'error': str(e)
            },
            status_code=500
        )   

@router.get("/industry_board")
def get_industry_board():
    """获取当日最新板块行情，按涨幅降序排序"""
    try:
        print("📈 开始获取板块行情数据...")
        df = ak.stock_board_industry_name_em()
        df = df.sort_values(by='涨跌幅', ascending=False)
        print("实际字段：", df.columns.tolist())
        expected_fields = ['板块名称', '最新价', '涨跌额', '涨跌幅', '总市值', '换手率', '成交额', '领涨股', '领涨股涨跌幅']
        actual_fields = [f for f in expected_fields if f in df.columns]
        # 统一将 NaN 转为 None
        df = df.replace({np.nan: None})
        # 字段名映射为英文
        field_map = {
            '板块名称': 'name',
            '最新价': 'price',
            '涨跌额': 'change_amount',
            '涨跌幅': 'change_percent',
            '总市值': 'market_cap',
            '换手率': 'turnover_rate',
            '成交额': 'turnover',
            '领涨股': 'leading_stock',
            '领涨股涨跌幅': 'leading_stock_change'
        }
        data = []
        for _, row in df[actual_fields].iterrows():
            item = {}
            for k in actual_fields:
                item[field_map.get(k, k)] = row[k]
            data.append(item)
        print(f"✅ 成功获取 {len(data)} 条板块数据")
        return JSONResponse({'success': True, 'data': data})
    except Exception as e:
        print(f"❌ 获取板块行情数据失败: {str(e)}")
        print("详细错误信息:")
        tb = traceback.format_exc()
        print(tb)
        return JSONResponse({
            'success': False,
            'message': '获取板块行情数据失败',
            'error': str(e),
            'traceback': tb
        }, status_code=500) 