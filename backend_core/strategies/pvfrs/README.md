# PVFRS策略模块

量价频三维共振演化策略（PVFRS - Price-Volume-Frequency Resonance Strategy）的完整实现。

## 项目结构

```
backend_core/strategies/pvfrs/
├── __init__.py              # 模块初始化，导出核心类和接口
├── models.py                # 核心数据模型定义
├── interfaces.py            # 接口定义
├── config.py                # 配置管理
├── README.md                # 项目说明文档
└── pvfrs_config.json        # 默认配置文件（自动生成）
```

## 核心组件

### 数据模型 (models.py)

- **MarketData**: 市场数据结构，包含OHLCV数据
- **PVFRSIndicators**: PVFRS指标结构，包含三维分析结果
- **Signal**: 交易信号结构，包含买卖信号信息
- **Trade**: 交易记录结构，记录完整交易信息
- **BacktestResult**: 回测结果结构，包含绩效指标
- **异常类**: 各种业务异常定义

### 接口定义 (interfaces.py)

定义了各个组件的标准接口：

- **IDataInterface**: 数据接口
- **IDimensionAnalyzer**: 维度分析器基础接口
- **IPriceDimensionAnalyzer**: 价格维度分析器接口
- **IFrequencyDimensionAnalyzer**: 频率维度分析器接口
- **IVolumeDimensionAnalyzer**: 成交量维度分析器接口
- **IResonanceDetector**: 三维共振检测器接口
- **ISignalGenerator**: 信号生成器接口
- **IStrategyEngine**: 策略引擎接口
- **IBacktestEngine**: 回测引擎接口
- **IRiskManager**: 风险管理器接口
- **IConfigManager**: 配置管理器接口

### 配置管理 (config.py)

- **PVFRSConfigManager**: 配置管理器实现
- 提供默认配置、配置验证、加载保存等功能
- 支持参数验证和逻辑关系检查

## 使用示例

### 基本使用

```python
from backend_core.strategies.pvfrs import (
    MarketData, PVFRSIndicators, Signal, 
    PVFRSConfigManager, SignalType
)

# 创建市场数据
market_data = MarketData(
    symbol="000001",
    date="2024-01-15",
    open=10.0,
    high=11.0,
    low=9.5,
    close=10.5,
    volume=1000000,
    amount=10500000.0
)

# 配置管理
config_manager = PVFRSConfigManager()
config = config_manager.get_default_config()

# 创建交易信号
signal = Signal(
    symbol="000001",
    date="2024-01-15",
    signal_type=SignalType.BUY,
    price=10.5,
    strength=0.8,
    reason="三维共振买入信号"
)
```

### 配置管理

```python
# 加载配置
config = config_manager.load_config()

# 修改配置
config['stop_loss'] = -0.08
config['take_profit'] = 0.3

# 保存配置
config_manager.save_config(config)

# 验证配置
is_valid = config_manager.validate_config(config)
```

## 数据验证

所有数据模型都包含内置验证：

- **价格数据验证**: 确保价格逻辑正确（高>=开盘/收盘，低<=开盘/收盘）
- **成交量验证**: 确保成交量和成交额非负
- **指标验证**: 确保指标值在合理范围内
- **信号验证**: 确保信号强度在0-1之间
- **配置验证**: 确保配置参数有效且逻辑一致

## 异常处理

提供完整的异常体系：

- **PVFRSException**: 基础异常类
- **DataInsufficientException**: 数据不足异常
- **CalculationException**: 计算异常
- **ConfigurationException**: 配置异常
- **ValidationException**: 验证异常

## 测试

运行测试：

```bash
# 运行所有PVFRS相关测试
python -m pytest test/test_pvfrs_*.py -v

# 运行数据模型测试
python -m pytest test/test_pvfrs_models.py -v

# 运行配置管理测试
python -m pytest test/test_pvfrs_config.py -v
```

## 下一步开发

根据任务计划，接下来将实现：

1. 价格维度分析器
2. 频率维度分析器
3. 成交量维度分析器
4. 三维共振检测器
5. 信号生成器
6. 策略引擎
7. 回测引擎
8. 风险管理器

每个组件都将基于已定义的接口进行实现，确保模块化和可测试性。