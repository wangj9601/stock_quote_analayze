import pandas as pd
import numpy as np


def _fmt_date(d):
    """将日期转为 YYYY-MM-DD 字符串"""
    if d is None:
        return None
    if hasattr(d, 'strftime'):
        return d.strftime('%Y-%m-%d')
    s = str(d)
    return s[:10] if len(s) >= 10 else s


class MeanFrequencyResonanceCalculator:
    """
    均值频率共振量化交易指标计算器
    指标包括：
    1. 宏观位移 Delta (d20 - d1)，利旧
    2. 幅度比例 ratio_d20 = Δ/d₂₀、ratio_d1 = Δ/d₁
    3. 即时偏离度 (d20 - d) (Close - MA20)
    4. 上涨的天数 (Z)
    5. 下跌的天数 (F)
    6. 进出效率指标 (m20 - m) (Volume - MAVOL20)
    
    其中：
    d = MA20 (20日移动平均线)
    m = MAVOL20 (20日移动平均成交量)
    d20 = 当前收盘价
    d1 = 20天前的收盘价 (或者说窗口起始价格)
    m20 = 当前成交量
    """
    
    def calculate(self, closes, volumes, dates=None, window=20):
        """
        计算均值频率共振指标

        Args:
            closes: 收盘价列表或数组
            volumes: 成交量列表或数组
            dates: 可选，与 closes 一一对应的交易日期列表（用于输出 d1_date、d20_date）
            window: 计算窗口，默认为20

        Returns:
            List[Dict]: 指标结果列表，每项含 d1、d1_date、d20、d20_date（当 dates 传入时）
        """
        # PVFRS 指标计算通常需要 window + 1 的数据来计算上涨/下跌天数
        # 因为计算上涨/下跌需要比较 T 和 T-1 的价格
        if len(closes) < window + 1 or len(volumes) < window + 1:
            return []
        if dates is not None and len(dates) != len(closes):
            dates = None

        df = pd.DataFrame({
            'close': closes,
            'volume': volumes
        })
        
        # 1. 计算 MA20 (d)
        df['ma20'] = df['close'].rolling(window=window).mean()
        
        # 2. 计算 MAVOL20 (m)
        df['mavol20'] = df['volume'].rolling(window=window).mean()
        
        # 3. 计算 Delta (d20 - d1)
        # d20 是当前价格 (t), d1 是窗口起始价格 (t-19)
        # 实际上是价格在20天内的位移
        # shift(window-1) 取到的是窗口第一个值
        df['delta'] = df['close'] - df['close'].shift(window - 1)
        
        # 4. 计算 即时偏离度 (d20 - d)
        df['instant_deviation'] = df['close'] - df['ma20']
        
        # 5. 计算 进出效率 (m20 - m)
        df['efficiency'] = df['volume'] - df['mavol20']
        
        # 6. 计算 Z (上涨天数) 和 F (下跌天数)
        # 定义上涨为 Close > Prev Close
        # 注意：这里需要 T 和 T-1，所以第一个 is_rising 是从索引 1 开始的
        df['is_rising'] = (df['close'] > df['close'].shift(1)).astype(float)
        df['is_falling'] = (df['close'] < df['close'].shift(1)).astype(float)
        
        # 滚动求和
        # 如果 window=20，第 20 个点 (index 19) 的 z 将是 NaN，因为 is_rising[0] 是 NaN
        # 第 21 个点 (index 20) 的 z 才是有效的（涵盖了 20 个完整的变动判断）
        df['z'] = df['is_rising'].rolling(window=window).sum()
        df['f'] = df['is_falling'].rolling(window=window).sum()
        
        # d1 = 窗口起始价 (shift window-1)
        df['d1'] = df['close'].shift(window - 1)

        results = []
        for i in range(len(df)):
            # 只有当 ma20, z, f 都不为 NaN 时，才返回结果
            if pd.isna(df['ma20'].iloc[i]) or pd.isna(df['z'].iloc[i]):
                results.append(None)
            else:
                delta = float(df['delta'].iloc[i]) if not pd.isna(df['delta'].iloc[i]) else 0.0
                d20 = df['close'].iloc[i]
                d1 = df['d1'].iloc[i]
                ratio_d20 = None
                ratio_d1 = None
                if d20 != 0 and not pd.isna(d20):
                    ratio_d20 = float(delta / d20)
                if d1 != 0 and not pd.isna(d1):
                    ratio_d1 = float(delta / d1)
                
                item = {
                    'ma20_d': float(df['ma20'].iloc[i]),
                    'mavol20_m': float(df['mavol20'].iloc[i]),
                    'macro_displacement_delta': delta,
                    'amplitude': abs(delta),
                    'ratio_d20': ratio_d20,
                    'ratio_d1': ratio_d1,
                    'instant_deviation': float(df['instant_deviation'].iloc[i]),
                    'efficiency_m20_minus_m': float(df['efficiency'].iloc[i]),
                    'rising_days_z': int(df['z'].iloc[i]),
                    'falling_days_f': int(df['f'].iloc[i]),
                    'bias': float((df['close'].iloc[i] - df['ma20'].iloc[i]) / df['ma20'].iloc[i]) if df['ma20'].iloc[i] != 0 else 0.0
                }
                item['d20'] = float(d20)
                item['d1'] = float(d1) if d1 is not None and not pd.isna(d1) else None
                if dates is not None:
                    item['d20_date'] = _fmt_date(dates[i])
                    d1_idx = i - (window - 1)
                    item['d1_date'] = _fmt_date(dates[d1_idx]) if d1_idx >= 0 else None
                else:
                    item['d20_date'] = None
                    item['d1_date'] = None
                results.append(item)
                
        return results
    
    def calculate_for_dataframe(self, history_rows, window=20):
        """
        从数据库查询结果计算均值频率共振指标，返回 DataFrame
        
        Args:
            history_rows: 数据库查询结果列表（ORM 对象）
            window: 计算窗口，默认为20
            
        Returns:
            pd.DataFrame: 包含日期和所有指标的 DataFrame
        """
        if len(history_rows) < window + 1:
            return pd.DataFrame()
        
        # 从 ORM 对象提取数据
        dates = []
        closes = []
        volumes = []
        
        for row in history_rows:
            dates.append(row.date)
            closes.append(float(row.close))
            volumes.append(float(row.volume))
        
        # 使用现有的 calculate 方法计算指标（传入 dates 以输出 d1_date、d20_date）
        results = self.calculate(closes, volumes, dates=dates, window=window)

        # 构建 DataFrame
        data = []
        for i, result in enumerate(results):
            if result is not None:
                row = {
                    'date': dates[i],
                    'ma20_d': result['ma20_d'],
                    'mavol20_m': result['mavol20_m'],
                    'macro_displacement_delta': result['macro_displacement_delta'],
                    'amplitude': result.get('amplitude'),
                    'ratio_d20': result.get('ratio_d20'),
                    'ratio_d1': result.get('ratio_d1'),
                    'instant_deviation': result['instant_deviation'],
                    'efficiency_m20_minus_m': result['efficiency_m20_minus_m'],
                    'rising_days_z': result['rising_days_z'],
                    'falling_days_f': result['falling_days_f'],
                    'bias': result['bias']
                }
                for k in ('d1', 'd1_date', 'd20', 'd20_date'):
                    if k in result:
                        row[k] = result[k]
                data.append(row)
        
        return pd.DataFrame(data)
