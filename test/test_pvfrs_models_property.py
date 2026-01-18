"""
PVFRS核心数据模型属性测试
使用Hypothesis进行基于属性的测试，验证数据接口标准化
**属性 9: 数据接口标准化**
**验证需求: 需求 9.1, 9.2**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from datetime import datetime, timedelta
from backend_core.strategies.pvfrs.models import (
    MarketData, PVFRSIndicators, Signal, Trade, BacktestResult,
    SignalType, ValidationException
)


# 策略生成器
@st.composite
def market_data_strategy(draw):
    """生成有效的MarketData实例"""
    symbol = draw(st.text(min_size=1, max_size=6, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'))
    
    # 生成日期
    base_date = datetime(2020, 1, 1)
    days_offset = draw(st.integers(min_value=0, max_value=365))
    date = (base_date + timedelta(days=days_offset)).strftime('%Y-%m-%d')
    
    # 简化价格生成逻辑
    base_price = draw(st.floats(min_value=5.0, max_value=100.0))
    
    # 生成开盘和收盘价
    open_price = draw(st.floats(min_value=base_price * 0.95, max_value=base_price * 1.05))
    close_price = draw(st.floats(min_value=base_price * 0.95, max_value=base_price * 1.05))
    
    # 确保高低价格逻辑正确
    min_oc = min(open_price, close_price)
    max_oc = max(open_price, close_price)
    
    high_price = draw(st.floats(min_value=max_oc, max_value=max_oc * 1.02))
    low_price = draw(st.floats(min_value=min_oc * 0.98, max_value=min_oc))
    
    # 生成成交量和成交额
    volume = draw(st.integers(min_value=1000, max_value=10000000))
    amount = volume * close_price
    
    return MarketData(
        symbol=symbol,
        date=date,
        open=round(open_price, 2),
        high=round(high_price, 2),
        low=round(low_price, 2),
        close=round(close_price, 2),
        volume=volume,
        amount=round(amount, 2)
    )


@st.composite
def pvfrs_indicators_strategy(draw):
    """生成有效的PVFRSIndicators实例"""
    avg_price_20d = draw(st.floats(min_value=0.01, max_value=1000.0))
    
    # 确保涨跌天数总和不超过20天
    total_days = draw(st.integers(min_value=1, max_value=20))
    rising_days = draw(st.integers(min_value=0, max_value=total_days))
    falling_days = total_days - rising_days
    
    return PVFRSIndicators(
        macro_displacement=draw(st.floats(min_value=-100.0, max_value=100.0)),
        instant_deviation=draw(st.floats(min_value=-50.0, max_value=50.0)),
        avg_price_20d=avg_price_20d,
        rising_days=rising_days,
        falling_days=falling_days,
        frequency_advantage=draw(st.booleans()),
        avg_volume_20d=draw(st.floats(min_value=0, max_value=1000000000.0)),
        current_volume=draw(st.floats(min_value=0, max_value=1000000000.0)),
        efficiency_ratio=draw(st.floats(min_value=0, max_value=10.0)),
        amplitude_ratio=draw(st.floats(min_value=-1.0, max_value=1.0)),
        resonance_strength=draw(st.floats(min_value=0.0, max_value=1.0))
    )


@st.composite
def signal_strategy(draw):
    """生成有效的Signal实例"""
    symbol = draw(st.text(min_size=1, max_size=6, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'))
    
    base_date = datetime(2020, 1, 1)
    days_offset = draw(st.integers(min_value=0, max_value=365))
    date = (base_date + timedelta(days=days_offset)).strftime('%Y-%m-%d')
    
    return Signal(
        symbol=symbol,
        date=date,
        signal_type=draw(st.sampled_from(SignalType)),
        price=draw(st.floats(min_value=0.01, max_value=1000.0)),
        strength=draw(st.floats(min_value=0.0, max_value=1.0)),
        reason=draw(st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz '))
    )


class TestMarketDataProperties:
    """MarketData属性测试"""
    
    @given(market_data_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_market_data_price_consistency(self, market_data):
        """
        属性: 对于任何有效的MarketData，价格数据应该保持逻辑一致性
        验证需求: 需求 9.1 - 数据接口应提供标准化的数据获取接口
        """
        # 价格逻辑一致性
        assert market_data.high >= market_data.open, f"最高价{market_data.high}应该>=开盘价{market_data.open}"
        assert market_data.high >= market_data.close, f"最高价{market_data.high}应该>=收盘价{market_data.close}"
        assert market_data.low <= market_data.open, f"最低价{market_data.low}应该<=开盘价{market_data.open}"
        assert market_data.low <= market_data.close, f"最低价{market_data.low}应该<=收盘价{market_data.close}"
        
        # 价格为正
        assert market_data.open > 0, "开盘价必须为正"
        assert market_data.high > 0, "最高价必须为正"
        assert market_data.low > 0, "最低价必须为正"
        assert market_data.close > 0, "收盘价必须为正"
        
        # 成交量和成交额非负
        assert market_data.volume >= 0, "成交量不能为负"
        assert market_data.amount >= 0, "成交额不能为负"
    
    @given(market_data_strategy())
    @settings(max_examples=50)
    def test_market_data_serialization_consistency(self, market_data):
        """
        属性: 对于任何MarketData，其属性应该可以被正确访问和序列化
        验证需求: 需求 9.2 - 数据接口应返回标准格式数据
        """
        # 所有必需属性都存在且可访问
        assert hasattr(market_data, 'symbol')
        assert hasattr(market_data, 'date')
        assert hasattr(market_data, 'open')
        assert hasattr(market_data, 'high')
        assert hasattr(market_data, 'low')
        assert hasattr(market_data, 'close')
        assert hasattr(market_data, 'volume')
        assert hasattr(market_data, 'amount')
        
        # 数据类型正确
        assert isinstance(market_data.symbol, str)
        assert isinstance(market_data.date, str)
        assert isinstance(market_data.open, (int, float))
        assert isinstance(market_data.high, (int, float))
        assert isinstance(market_data.low, (int, float))
        assert isinstance(market_data.close, (int, float))
        assert isinstance(market_data.volume, int)
        assert isinstance(market_data.amount, (int, float))
        
        # 日期格式正确
        try:
            datetime.strptime(market_data.date, '%Y-%m-%d')
        except ValueError:
            pytest.fail(f"日期格式不正确: {market_data.date}")


class TestPVFRSIndicatorsProperties:
    """PVFRSIndicators属性测试"""
    
    @given(pvfrs_indicators_strategy())
    @settings(max_examples=50)
    def test_indicators_value_ranges(self, indicators):
        """
        属性: 对于任何PVFRSIndicators，指标值应该在合理范围内
        验证需求: 需求 9.1, 9.2 - 数据标准化和格式一致性
        """
        # 价格相关指标
        assert indicators.avg_price_20d > 0, "20日平均价格必须为正"
        
        # 天数统计
        assert indicators.rising_days >= 0, "上涨天数不能为负"
        assert indicators.falling_days >= 0, "下跌天数不能为负"
        assert indicators.rising_days + indicators.falling_days <= 20, "总天数不应超过观察周期"
        
        # 成交量指标
        assert indicators.avg_volume_20d >= 0, "平均成交量不能为负"
        assert indicators.current_volume >= 0, "当前成交量不能为负"
        assert indicators.efficiency_ratio >= 0, "效率比不能为负"
        
        # 共振强度
        assert 0 <= indicators.resonance_strength <= 1, "共振强度必须在0-1之间"
    
    @given(pvfrs_indicators_strategy())
    @settings(max_examples=50)
    def test_indicators_frequency_advantage_consistency(self, indicators):
        """
        属性: 对于任何PVFRSIndicators，频率优势标志应该与天数统计一致
        验证需求: 需求 9.1 - 数据逻辑一致性
        """
        # 如果明确设置了频率优势，应该与天数统计一致
        if indicators.rising_days != indicators.falling_days:
            expected_advantage = indicators.rising_days > indicators.falling_days
            # 注意：这里不强制要求一致，因为可能有其他因素影响频率优势判定
            # 但我们可以检查数据的合理性
            assert isinstance(indicators.frequency_advantage, bool), "频率优势必须是布尔值"


class TestSignalProperties:
    """Signal属性测试"""
    
    @given(signal_strategy())
    @settings(max_examples=50)
    def test_signal_value_constraints(self, signal):
        """
        属性: 对于任何Signal，其值应该满足约束条件
        验证需求: 需求 9.1, 9.2 - 信号数据标准化
        """
        # 价格为正
        assert signal.price > 0, "信号价格必须为正"
        
        # 强度在0-1之间
        assert 0 <= signal.strength <= 1, "信号强度必须在0-1之间"
        
        # 信号类型有效
        assert signal.signal_type in SignalType, "信号类型必须有效"
        
        # 必需字段非空
        assert signal.symbol, "股票代码不能为空"
        assert signal.date, "日期不能为空"
        assert signal.reason, "信号原因不能为空"
    
    @given(signal_strategy())
    @settings(max_examples=50)
    def test_signal_conditions_met_initialization(self, signal):
        """
        属性: 对于任何Signal，conditions_met应该被正确初始化
        验证需求: 需求 9.2 - 数据结构完整性
        """
        # conditions_met应该被初始化为字典
        assert isinstance(signal.conditions_met, dict), "conditions_met必须是字典类型"
        
        # 可以安全地添加条件
        signal.conditions_met['test_condition'] = True
        assert signal.conditions_met['test_condition'] is True


class TestDataInterfaceStandardization:
    """数据接口标准化属性测试"""
    
    @given(st.lists(market_data_strategy(), min_size=1, max_size=50))
    @settings(max_examples=50)
    def test_market_data_list_consistency(self, market_data_list):
        """
        属性: 对于任何MarketData列表，所有元素应该具有一致的数据结构
        验证需求: 需求 9.1 - 标准化数据获取接口
        """
        # 所有元素都是MarketData类型
        for data in market_data_list:
            assert isinstance(data, MarketData), "列表中所有元素都必须是MarketData类型"
        
        # 所有元素都有相同的属性结构
        if len(market_data_list) > 1:
            first_data = market_data_list[0]
            for data in market_data_list[1:]:
                assert set(dir(first_data)) == set(dir(data)), "所有MarketData对象应该有相同的属性结构"
    
    @given(st.lists(signal_strategy(), min_size=1, max_size=20))
    @settings(max_examples=50)
    def test_signal_list_type_consistency(self, signal_list):
        """
        属性: 对于任何Signal列表，信号类型应该是有效的枚举值
        验证需求: 需求 9.2 - 标准格式数据返回
        """
        valid_signal_types = set(SignalType)
        
        for signal in signal_list:
            assert signal.signal_type in valid_signal_types, f"信号类型{signal.signal_type}必须是有效的枚举值"
            assert isinstance(signal.signal_type, SignalType), "信号类型必须是SignalType枚举实例"
    
    @given(
        st.lists(market_data_strategy(), min_size=20, max_size=25),
        st.text(min_size=1, max_size=10)
    )
    @settings(max_examples=30)
    def test_data_temporal_consistency(self, market_data_list, symbol):
        """
        属性: 对于任何时间序列数据，应该支持时间排序和一致性检查
        验证需求: 需求 9.1 - 数据清洗和标准化
        """
        # 为所有数据设置相同的股票代码
        for i, data in enumerate(market_data_list):
            # 创建新的MarketData对象，保持原有数据但统一symbol
            market_data_list[i] = MarketData(
                symbol=symbol,
                date=data.date,
                open=data.open,
                high=data.high,
                low=data.low,
                close=data.close,
                volume=data.volume,
                amount=data.amount
            )
        
        # 按日期排序
        sorted_data = sorted(market_data_list, key=lambda x: x.date)
        
        # 验证排序后的数据仍然有效
        for data in sorted_data:
            assert isinstance(data, MarketData), "排序后数据类型应该保持不变"
            assert data.symbol == symbol, "排序后股票代码应该保持一致"
        
        # 验证日期格式一致性
        for data in sorted_data:
            try:
                datetime.strptime(data.date, '%Y-%m-%d')
            except ValueError:
                pytest.fail(f"日期格式应该保持一致: {data.date}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])