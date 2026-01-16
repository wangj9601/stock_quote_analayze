import pandas as pd
import numpy as np

class MeanFrequencyResonanceCalculator:
    """
    均值频率共振量化交易指标计算器
    指标包括：
    1. 宏观位移 Delta (d20 - d1)
    2. 即时偏离度 (d20 - d) (Close - MA20)
    3. 上涨的天数 (Z)
    4. 下跌的天数 (F)
    5. 进出效率指标 (m20 - m) (Volume - MAVOL20)
    
    其中：
    d = MA20 (20日移动平均线)
    m = MAVOL20 (20日移动平均成交量)
    d20 = 当前收盘价
    d1 = 20天前的收盘价 (或者说窗口起始价格)
    m20 = 当前成交量
    """
    
    def calculate(self, closes, volumes, window=20):
        """
        计算均值频率共振指标
        
        Args:
            closes: 收盘价列表或数组
            volumes: 成交量列表或数组
            window: 计算窗口，默认为20
            
        Returns:
            List[Dict]: 指标结果列表
        """
        if len(closes) < window or len(volumes) < window:
            return []
            
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
        df['is_rising'] = (df['close'] > df['close'].shift(1)).astype(int)
        df['is_falling'] = (df['close'] < df['close'].shift(1)).astype(int)
        
        # 滚动求和
        df['z'] = df['is_rising'].rolling(window=window).sum()
        df['f'] = df['is_falling'].rolling(window=window).sum()
        
        results = []
        for i in range(len(df)):
            if pd.isna(df['ma20'].iloc[i]):
                results.append(None)
            else:
                results.append({
                    'ma20_d': float(df['ma20'].iloc[i]),
                    'mavol20_m': float(df['mavol20'].iloc[i]),
                    'macro_displacement_delta': float(df['delta'].iloc[i]) if not pd.isna(df['delta'].iloc[i]) else 0.0,
                    'instant_deviation': float(df['instant_deviation'].iloc[i]),
                    'efficiency_m20_minus_m': float(df['efficiency'].iloc[i]),
                    'rising_days_z': int(df['z'].iloc[i]),
                    'falling_days_f': int(df['f'].iloc[i]),
                    'bias': float((df['close'].iloc[i] - df['ma20'].iloc[i]) / df['ma20'].iloc[i]) if df['ma20'].iloc[i] != 0 else 0.0
                })
                
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
        if len(history_rows) < window:
            return pd.DataFrame()
        
        # 从 ORM 对象提取数据
        dates = []
        closes = []
        volumes = []
        
        for row in history_rows:
            dates.append(row.date)
            closes.append(float(row.close))
            volumes.append(float(row.volume))
        
        # 使用现有的 calculate 方法计算指标
        results = self.calculate(closes, volumes, window)
        
        # 构建 DataFrame
        data = []
        for i, result in enumerate(results):
            if result is not None:
                data.append({
                    'date': dates[i],
                    'ma20_d': result['ma20_d'],
                    'mavol20_m': result['mavol20_m'],
                    'macro_displacement_delta': result['macro_displacement_delta'],
                    'instant_deviation': result['instant_deviation'],
                    'efficiency_m20_minus_m': result['efficiency_m20_minus_m'],
                    'rising_days_z': result['rising_days_z'],
                    'falling_days_f': result['falling_days_f'],
                    'bias': result['bias']
                })
        
        return pd.DataFrame(data)
