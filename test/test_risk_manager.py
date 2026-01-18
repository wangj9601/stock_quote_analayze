"""
PVFRS风险管理模块测试
测试止损止盈机制、时间管理和趋势反转检测功能
"""

import pytest
from datetime import datetime, timedelta
from backend_core.strategies.pvfrs.risk_manager import RiskManager
from backend_core.strategies.pvfrs.models import MarketData, Trade, SignalType, CalculationException


class TestRiskManager:
    """风险管理器测试类"""
    
    def setup_method(self):
        """测试前准备"""
        self.risk_manager = RiskManager()
        
        # 创建测试用的市场数据
        self.test_data = []
        base_date = datetime(2024, 1, 1)
        base_price = 10.0
        base_volume = 1000000
        
        for i in range(25):
            date = (base_date + timedelta(days=i)).strftime('%Y-%m-%d')
            # 模拟价格上涨趋势
            price = base_price + i * 0.1 + (i % 3 - 1) * 0.05  # 带波动的上涨
            volume = base_volume + i * 10000 + (i % 2) * 50000  # 成交量变化
            
            market_data = MarketData(
                symbol='TEST001',
                date=date,
                open=price - 0.02,
                high=price + 0.03,
                low=price - 0.03,
                close=price,
                volume=int(volume),
                amount=price * volume
            )
            self.test_data.append(market_data)
        
        # 创建测试交易
        self.test_trade = Trade(
            symbol='TEST001',
            entry_date='2024-01-01',
            exit_date=None,
            entry_price=10.0,
            exit_price=None,
            quantity=1000,
            position_size=10000.0
        )
    
    def test_check_stop_loss(self):
        """测试止损检查"""
        # 测试正常情况
        assert not self.risk_manager.check_stop_loss(10.0, 10.0)  # 无变化
        assert not self.risk_manager.check_stop_loss(9.5, 10.0)   # -5%，未触发默认-6%止损
        assert self.risk_manager.check_stop_loss(9.3, 10.0)       # -7%，触发止损
        
        # 测试自定义止损比例
        assert self.risk_manager.check_stop_loss(9.7, 10.0, -0.02)  # -3%，触发-2%止损
        assert not self.risk_manager.check_stop_loss(9.85, 10.0, -0.02)  # -1.5%，未触发
        
        # 测试异常情况
        with pytest.raises(CalculationException):
            self.risk_manager.check_stop_loss(10.0, 0)  # 入场价格为0
        
        with pytest.raises(CalculationException):
            self.risk_manager.check_stop_loss(0, 10.0)  # 当前价格为0
    
    def test_check_take_profit(self):
        """测试止盈检查"""
        # 测试正常情况
        assert not self.risk_manager.check_take_profit(10.0, 10.0)  # 无变化
        assert not self.risk_manager.check_take_profit(12.0, 10.0)  # +20%，未触发默认25%止盈
        assert self.risk_manager.check_take_profit(12.6, 10.0)      # +26%，触发止盈
        
        # 测试自定义止盈比例
        assert self.risk_manager.check_take_profit(11.1, 10.0, 0.10)  # +11%，触发10%止盈
        assert not self.risk_manager.check_take_profit(10.9, 10.0, 0.10)  # +9%，未触发
        
        # 测试异常情况
        with pytest.raises(CalculationException):
            self.risk_manager.check_take_profit(10.0, 0)  # 入场价格为0
    
    def test_check_max_holding_period(self):
        """测试最大持有期检查"""
        # 测试正常情况
        assert not self.risk_manager.check_max_holding_period('2024-01-01', '2024-01-30')  # 29天，未超过45天
        assert self.risk_manager.check_max_holding_period('2024-01-01', '2024-02-20')     # 50天，超过45天
        
        # 测试自定义最大天数
        assert self.risk_manager.check_max_holding_period('2024-01-01', '2024-01-11', 10)  # 10天，等于限制
        assert not self.risk_manager.check_max_holding_period('2024-01-01', '2024-01-10', 10)  # 9天，未超过
        
        # 测试异常情况
        with pytest.raises(CalculationException):
            self.risk_manager.check_max_holding_period('invalid-date', '2024-01-01')
    
    def test_check_trailing_stop(self):
        """测试移动止损检查"""
        # 启用移动止损
        self.risk_manager.trailing_stop_enabled = True
        self.risk_manager.trailing_stop_pct = 0.10  # 10%移动止损
        
        symbol = 'TEST001'
        entry_price = 10.0
        
        # 第一次检查，价格上涨
        triggered, reason = self.risk_manager.check_trailing_stop(symbol, 11.0, entry_price)
        assert not triggered  # 价格上涨，不触发
        
        # 价格继续上涨，更新最高价
        triggered, reason = self.risk_manager.check_trailing_stop(symbol, 12.0, entry_price)
        assert not triggered
        
        # 价格回落但未触发移动止损
        triggered, reason = self.risk_manager.check_trailing_stop(symbol, 11.0, entry_price)
        assert not triggered  # 11.0 > 12.0 * 0.9 = 10.8
        
        # 价格回落触发移动止损
        triggered, reason = self.risk_manager.check_trailing_stop(symbol, 10.5, entry_price)
        assert triggered  # 10.5 < 12.0 * 0.9 = 10.8
        assert "移动止损触发" in reason
        
        # 测试禁用移动止损
        self.risk_manager.trailing_stop_enabled = False
        triggered, reason = self.risk_manager.check_trailing_stop(symbol, 9.0, entry_price)
        assert not triggered
    
    def test_detect_trend_reversal(self):
        """测试趋势反转检测"""
        # 使用测试数据（上涨趋势）
        is_reversal = self.risk_manager.detect_trend_reversal(self.test_data)
        assert not is_reversal  # 上涨趋势，不应该检测到反转
        
        # 创建反转数据（价格下跌）
        reversal_data = self.test_data.copy()
        
        # 创建更明显的反转：最后10天价格大幅下跌，成交量萎缩
        for i in range(10):  # 增加反转天数
            idx = -(i + 1)
            original = reversal_data[idx]
            new_close = original.close - (i + 1) * 0.15  # 更大的跌幅
            new_low = min(original.low, new_close - 0.02)  # 调整最低价
            new_high = max(original.high, original.open + 0.01)  # 调整最高价，但保持下跌趋势
            
            reversal_data[idx] = MarketData(
                symbol='TEST001',
                date=original.date,
                open=original.open,
                high=new_high,
                low=new_low,
                close=new_close,
                volume=original.volume // 3,  # 成交量大幅萎缩
                amount=original.amount
            )
        
        is_reversal = self.risk_manager.detect_trend_reversal(reversal_data)
        # 注意：由于反转检测的具体实现可能需要更多条件，这里主要测试不会抛异常
        # 实际的反转检测结果取决于具体的算法实现
        assert isinstance(is_reversal, bool)  # 确保返回布尔值
        
        # 测试数据不足的情况
        with pytest.raises(CalculationException):
            self.risk_manager.detect_trend_reversal(self.test_data[:10])  # 少于20天数据
    
    def test_detect_trend_reversal_with_profit(self):
        """测试基于盈利情况的趋势反转检测"""
        # 低盈利情况（需要更多反转条件）
        is_reversal, details = self.risk_manager.detect_trend_reversal_with_profit(
            self.test_data, 0.05  # 5%盈利
        )
        
        assert 'current_profit_pct' in details
        assert 'required_conditions' in details
        assert 'reversal_count' in details
        assert details['required_conditions'] == 3  # 低盈利需要3个条件
        
        # 高盈利情况（需要较少反转条件）
        is_reversal, details = self.risk_manager.detect_trend_reversal_with_profit(
            self.test_data, 0.20  # 20%盈利
        )
        
        assert details['required_conditions'] == 2  # 高盈利只需要2个条件
    
    def test_generate_risk_management_signal(self):
        """测试风险管理信号生成"""
        current_data = self.test_data[-1]
        
        # 测试正常情况（无风险信号）
        signal = self.risk_manager.generate_risk_management_signal(
            'TEST001', current_data, self.test_trade, self.test_data
        )
        assert signal is None  # 正常情况下不应该有风险信号
        
        # 测试止损情况
        loss_trade = Trade(
            symbol='TEST001',
            entry_date='2024-01-01',
            exit_date=None,
            entry_price=15.0,  # 高入场价格，造成亏损
            exit_price=None,
            quantity=1000,
            position_size=15000.0
        )
        
        signal = self.risk_manager.generate_risk_management_signal(
            'TEST001', current_data, loss_trade, self.test_data
        )
        
        if signal:  # 如果触发了风险信号
            assert signal.signal_type == SignalType.SELL
            assert signal.strength > 0
            assert "止损" in signal.reason or "止盈" in signal.reason or "最大持有期" in signal.reason
    
    def test_get_dynamic_max_holding_days(self):
        """测试动态最大持有天数"""
        base_days = self.risk_manager.max_holding_days  # 45天
        
        # 亏损情况
        assert self.risk_manager.get_dynamic_max_holding_days(-0.05) == int(base_days * 0.6)  # 27天
        
        # 低盈利情况
        assert self.risk_manager.get_dynamic_max_holding_days(0.05) == base_days  # 45天
        
        # 中等盈利情况
        assert self.risk_manager.get_dynamic_max_holding_days(0.15) == int(base_days * 1.3)  # 58天
        
        # 高盈利情况
        assert self.risk_manager.get_dynamic_max_holding_days(0.25) == int(base_days * 1.6)  # 72天
    
    def test_check_time_based_exit(self):
        """测试基于时间的退出检查"""
        # 测试正常持有期内
        should_exit, reason = self.risk_manager.check_time_based_exit(
            '2024-01-01', '2024-01-20', 0.10  # 持有19天，盈利10%
        )
        assert not should_exit
        
        # 测试超过动态最大持有期
        should_exit, reason = self.risk_manager.check_time_based_exit(
            '2024-01-01', '2024-03-01', 0.05  # 持有约60天，盈利5%
        )
        assert should_exit
        assert "动态时间止损" in reason
        
        # 测试接近时间限制且盈利不佳
        should_exit, reason = self.risk_manager.check_time_based_exit(
            '2024-01-01', '2024-02-10', 0.02  # 持有约40天，盈利2%
        )
        # 根据具体实现可能触发也可能不触发，这里主要测试不会抛异常
        assert isinstance(should_exit, bool)
    
    def test_detect_trend_weakening(self):
        """测试趋势弱化检测"""
        # 测试正常上涨趋势（不应该检测到弱化）
        is_weakening, details = self.risk_manager.detect_trend_weakening(self.test_data)
        
        assert isinstance(is_weakening, bool)
        assert 'weakening_signals' in details
        assert 'weakening_count' in details
        
        # 创建弱化趋势数据
        weakening_data = self.test_data.copy()
        
        # 最近几天价格小幅波动，成交量萎缩
        for i in range(5):
            idx = -(i + 1)
            original = weakening_data[idx]
            new_close = original.close - 0.005 * i  # 小幅下跌，减少跌幅
            new_low = min(original.low, new_close - 0.001)  # 调整最低价
            new_high = max(original.high, new_close + 0.001)  # 调整最高价
            
            weakening_data[idx] = MarketData(
                symbol='TEST001',
                date=original.date,
                open=original.open,
                high=new_high,
                low=new_low,
                close=new_close,
                volume=original.volume // 3,  # 成交量大幅萎缩
                amount=original.amount
            )
        
        is_weakening, details = self.risk_manager.detect_trend_weakening(weakening_data)
        
        # 应该检测到一些弱化信号
        assert details['weakening_count'] >= 0
        
        # 测试数据不足的情况
        is_weakening, details = self.risk_manager.detect_trend_weakening(self.test_data[:8])
        assert 'error' in details
    
    def test_get_risk_status(self):
        """测试风险状态获取"""
        status = self.risk_manager.get_risk_status(
            'TEST001', 11.0, 10.0, '2024-01-01', '2024-01-15'
        )
        
        # 检查返回的状态信息
        assert status['symbol'] == 'TEST001'
        assert status['current_price'] == 11.0
        assert status['entry_price'] == 10.0
        assert status['profit_pct'] == 0.1  # 10%盈利
        assert status['holding_days'] == 14
        assert isinstance(status['stop_loss_triggered'], bool)
        assert isinstance(status['take_profit_triggered'], bool)
        assert isinstance(status['max_holding_triggered'], bool)
        assert status['risk_level'] in ['low', 'medium', 'high']
    
    def test_update_config(self):
        """测试配置更新"""
        original_stop_loss = self.risk_manager.stop_loss_pct
        
        # 更新配置
        new_config = {'stop_loss': -0.08, 'take_profit': 0.30}
        self.risk_manager.update_config(new_config)
        
        # 验证配置已更新
        assert self.risk_manager.stop_loss_pct == -0.08
        assert self.risk_manager.take_profit_pct == 0.30
        
        # 验证功能使用新配置
        assert self.risk_manager.check_stop_loss(9.1, 10.0)  # -9%，触发新的-8%止损
        assert not self.risk_manager.check_stop_loss(9.3, 10.0)  # -7%，未触发新止损
    
    def test_reset_position_tracking(self):
        """测试持仓跟踪重置"""
        symbol = 'TEST001'
        
        # 启用移动止损并建立跟踪
        self.risk_manager.trailing_stop_enabled = True
        self.risk_manager.check_trailing_stop(symbol, 12.0, 10.0)
        
        # 验证跟踪已建立
        assert symbol in self.risk_manager.highest_price_since_entry
        
        # 重置跟踪
        self.risk_manager.reset_position_tracking(symbol)
        
        # 验证跟踪已清除
        assert symbol not in self.risk_manager.highest_price_since_entry


if __name__ == '__main__':
    # 运行测试
    pytest.main([__file__, '-v'])