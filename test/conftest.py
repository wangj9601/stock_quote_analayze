"""
pytest配置文件
为PVFRS策略测试提供共享的fixtures和配置
"""

import pytest
import sys
import os
from datetime import datetime, timedelta
from typing import List

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend_core.strategies.pvfrs.models import MarketData, PVFRSIndicators, Signal, SignalType


@pytest.fixture
def sample_market_data() -> List[MarketData]:
    """提供样本市场数据"""
    base_date = datetime(2024, 1, 1)
    data = []
    
    for i in range(25):  # 25天数据，满足20天观察周期需求
        date = (base_date + timedelta(days=i)).strftime('%Y-%m-%d')
        
        # 模拟价格数据，整体上涨趋势
        base_price = 10.0 + i * 0.1
        open_price = base_price + (i % 3 - 1) * 0.05
        high_price = base_price + 0.2
        low_price = base_price - 0.1
        close_price = base_price + (i % 2) * 0.1
        
        # 确保价格逻辑正确
        high_price = max(high_price, open_price, close_price)
        low_price = min(low_price, open_price, close_price)
        
        # 模拟成交量数据
        volume = 1000000 + i * 50000 + (i % 5) * 100000
        amount = volume * close_price
        
        data.append(MarketData(
            symbol="000001",
            date=date,
            open=round(open_price, 2),
            high=round(high_price, 2),
            low=round(low_price, 2),
            close=round(close_price, 2),
            volume=int(volume),
            amount=round(amount, 2)
        ))
    
    return data


@pytest.fixture
def sample_pvfrs_indicators() -> PVFRSIndicators:
    """提供样本PVFRS指标"""
    return PVFRSIndicators(
        macro_displacement=0.5,
        instant_deviation=0.3,
        avg_price_20d=10.5,
        rising_days=12,
        falling_days=8,
        frequency_advantage=True,
        avg_volume_20d=1200000.0,
        current_volume=1400000.0,
        efficiency_ratio=1.17,
        amplitude_ratio=0.048,
        resonance_strength=0.75
    )


@pytest.fixture
def sample_buy_signal() -> Signal:
    """提供样本买入信号"""
    return Signal(
        symbol="000001",
        date="2024-01-20",
        signal_type=SignalType.BUY,
        price=11.5,
        strength=0.8,
        reason="三维共振买入信号",
        conditions_met={
            'macro_displacement_positive': True,
            'instant_deviation_sufficient': True,
            'rising_days_advantage': True,
            'efficiency_positive': True
        }
    )


@pytest.fixture
def sample_sell_signal() -> Signal:
    """提供样本卖出信号"""
    return Signal(
        symbol="000001",
        date="2024-01-25",
        signal_type=SignalType.SELL,
        price=12.0,
        strength=0.6,
        reason="止盈卖出",
        conditions_met={
            'take_profit_reached': True
        }
    )


@pytest.fixture
def rising_price_data() -> List[MarketData]:
    """提供上涨趋势的价格数据"""
    base_date = datetime(2024, 1, 1)
    data = []
    
    for i in range(25):
        date = (base_date + timedelta(days=i)).strftime('%Y-%m-%d')
        
        # 持续上涨的价格
        base_price = 10.0 + i * 0.2
        open_price = base_price
        close_price = base_price + 0.15
        high_price = close_price + 0.05
        low_price = open_price - 0.05
        
        volume = 1000000 + i * 20000
        amount = volume * close_price
        
        data.append(MarketData(
            symbol="000001",
            date=date,
            open=round(open_price, 2),
            high=round(high_price, 2),
            low=round(low_price, 2),
            close=round(close_price, 2),
            volume=int(volume),
            amount=round(amount, 2)
        ))
    
    return data


@pytest.fixture
def falling_price_data() -> List[MarketData]:
    """提供下跌趋势的价格数据"""
    base_date = datetime(2024, 1, 1)
    data = []
    
    for i in range(25):
        date = (base_date + timedelta(days=i)).strftime('%Y-%m-%d')
        
        # 持续下跌的价格
        base_price = 15.0 - i * 0.2
        open_price = base_price
        close_price = base_price - 0.15
        high_price = open_price + 0.05
        low_price = close_price - 0.05
        
        volume = 1500000 - i * 20000
        amount = volume * close_price
        
        data.append(MarketData(
            symbol="000001",
            date=date,
            open=round(open_price, 2),
            high=round(high_price, 2),
            low=round(low_price, 2),
            close=round(close_price, 2),
            volume=int(volume),
            amount=round(amount, 2)
        ))
    
    return data


@pytest.fixture
def sideways_price_data() -> List[MarketData]:
    """提供横盘震荡的价格数据"""
    base_date = datetime(2024, 1, 1)
    data = []
    
    for i in range(25):
        date = (base_date + timedelta(days=i)).strftime('%Y-%m-%d')
        
        # 横盘震荡的价格
        base_price = 10.0 + (i % 4 - 2) * 0.1
        open_price = base_price
        close_price = base_price + (i % 3 - 1) * 0.05
        high_price = max(open_price, close_price) + 0.05
        low_price = min(open_price, close_price) - 0.05
        
        volume = 1200000 + (i % 5 - 2) * 50000
        amount = volume * close_price
        
        data.append(MarketData(
            symbol="000001",
            date=date,
            open=round(open_price, 2),
            high=round(high_price, 2),
            low=round(low_price, 2),
            close=round(close_price, 2),
            volume=int(volume),
            amount=round(amount, 2)
        ))
    
    return data


# 测试标记
def pytest_configure(config):
    """配置pytest标记"""
    config.addinivalue_line(
        "markers", "unit: 单元测试"
    )
    config.addinivalue_line(
        "markers", "integration: 集成测试"
    )
    config.addinivalue_line(
        "markers", "property: 属性测试"
    )
    config.addinivalue_line(
        "markers", "slow: 慢速测试"
    )
    config.addinivalue_line(
        "markers", "data: 数据相关测试"
    )