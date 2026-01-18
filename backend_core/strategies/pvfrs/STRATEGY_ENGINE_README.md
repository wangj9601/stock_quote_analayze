# PVFRS策略引擎和选股功能使用指南

## 概述

PVFRS策略引擎是一个完整的量价频三维共振演化策略实现，提供了股票分析、信号生成、批量选股和报告生成等功能。

## 核心组件

### 1. StrategyEngine（策略引擎）

策略引擎是PVFRS策略的核心组件，负责协调各个维度分析器并生成交易信号。

#### 主要功能

- **analyze_stock()**: 分析单只股票的PVFRS指标
- **generate_signals()**: 生成交易信号
- **get_strategy_analysis()**: 获取完整的策略分析结果
- **validate_strategy_conditions()**: 验证策略条件

#### 使用示例

```python
from backend_core.strategies.pvfrs.strategy_engine import StrategyEngine
from backend_core.strategies.pvfrs.models import MarketData

# 创建策略引擎
engine = StrategyEngine()

# 准备市场数据（至少20天）
market_data = [
    MarketData(
        symbol="000001",
        date="2026-01-01",
        open=10.0,
        high=10.5,
        low=9.8,
        close=10.2,
        volume=1000000,
        amount=10200000.0
    ),
    # ... 更多数据
]

# 分析股票
indicators = engine.analyze_stock("000001", market_data)
print(f"共振强度: {indicators.resonance_strength}")

# 生成信号
signals = engine.generate_signals("000001", market_data)
for signal in signals:
    print(f"信号类型: {signal.signal_type.value}, 强度: {signal.strength}")
```

### 2. StockScreener（股票筛选器）

股票筛选器提供批量选股功能，可以对多只股票同时应用PVFRS策略条件。

#### 主要功能

- **screen_stocks()**: 批量选股主函数
- **screen_stocks_with_callback()**: 带进度回调的批量选股
- **get_screening_statistics()**: 获取筛选统计信息

#### 使用示例

```python
from backend_core.strategies.pvfrs.stock_screener import StockScreener, ScreeningConfig

# 创建筛选器
screener = StockScreener()

# 配置筛选参数
config = ScreeningConfig(
    min_signal_strength=0.7,  # 最小信号强度
    max_results=20,           # 最大结果数
    min_price=5.0,           # 最小价格
    max_price=200.0,         # 最大价格
    min_volume=1000000       # 最小成交量
)

# 准备股票数据字典
stock_data_dict = {
    "000001": market_data_1,
    "000002": market_data_2,
    # ... 更多股票数据
}

# 执行选股
target_date = "2026-01-17"
results = screener.screen_stocks(stock_data_dict, target_date, config)

# 查看结果
for result in results:
    print(f"{result.symbol}: 强度={result.signal_strength:.4f}, 价格={result.price}")
```

### 3. ScreeningReportGenerator（报告生成器）

报告生成器负责对选股结果进行排序、格式化和输出。

#### 主要功能

- **generate_comprehensive_report()**: 生成综合报告
- **generate_json_report()**: 生成JSON格式报告
- **generate_csv_report()**: 生成CSV格式报告
- **generate_text_report()**: 生成文本格式报告

#### 使用示例

```python
from backend_core.strategies.pvfrs.screening_report import ScreeningReportGenerator, ReportConfig

# 创建报告生成器
generator = ScreeningReportGenerator()

# 配置报告参数
config = ReportConfig(
    include_detailed_conditions=True,
    include_statistics=True,
    sort_by='signal_strength',
    sort_ascending=False
)
generator.set_config(config)

# 生成文本报告
screening_stats = screener.get_screening_statistics()
text_report = generator.generate_text_report(
    results, screening_config, screening_stats, target_date
)
print(text_report)

# 生成CSV报告
csv_report = generator.generate_csv_report(results)
with open('screening_results.csv', 'w', encoding='utf-8') as f:
    f.write(csv_report)
```

## 完整工作流程示例

```python
from datetime import datetime
from backend_core.strategies.pvfrs.strategy_engine import StrategyEngine
from backend_core.strategies.pvfrs.stock_screener import StockScreener, ScreeningConfig
from backend_core.strategies.pvfrs.screening_report import ScreeningReportGenerator

def complete_screening_workflow():
    """完整的选股工作流程"""
    
    # 1. 创建策略引擎
    engine = StrategyEngine()
    
    # 2. 创建股票筛选器
    screener = StockScreener(engine)
    
    # 3. 配置筛选参数
    screening_config = ScreeningConfig(
        min_signal_strength=0.6,
        max_results=50,
        enable_parallel_processing=True,
        max_workers=4
    )
    
    # 4. 准备股票数据（从数据源获取）
    stock_data_dict = load_stock_data()  # 自定义数据加载函数
    
    # 5. 执行选股
    target_date = datetime.now().strftime('%Y-%m-%d')
    results = screener.screen_stocks(stock_data_dict, target_date, screening_config)
    
    # 6. 生成报告
    generator = ScreeningReportGenerator()
    screening_stats = screener.get_screening_statistics()
    
    # 生成多种格式的报告
    text_report = generator.generate_text_report(
        results, screening_config, screening_stats, target_date
    )
    
    json_report = generator.generate_json_report(
        results, screening_config, screening_stats, target_date
    )
    
    csv_report = generator.generate_csv_report(results)
    
    # 7. 保存报告
    save_reports(text_report, json_report, csv_report)
    
    return results

def load_stock_data():
    """加载股票数据的示例函数"""
    # 这里应该连接到实际的数据源
    # 返回格式: Dict[str, List[MarketData]]
    pass

def save_reports(text_report, json_report, csv_report):
    """保存报告的示例函数"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    with open(f'pvfrs_report_{timestamp}.txt', 'w', encoding='utf-8') as f:
        f.write(text_report)
    
    with open(f'pvfrs_report_{timestamp}.json', 'w', encoding='utf-8') as f:
        f.write(json_report)
    
    with open(f'pvfrs_report_{timestamp}.csv', 'w', encoding='utf-8') as f:
        f.write(csv_report)
```

## 配置选项

### ScreeningConfig（筛选配置）

- `min_signal_strength`: 最小信号强度阈值（默认0.6）
- `max_results`: 最大结果数量（默认50）
- `enable_parallel_processing`: 是否启用并行处理（默认True）
- `max_workers`: 最大工作线程数（默认4）
- `min_price`: 最小价格过滤（默认1.0）
- `max_price`: 最大价格过滤（默认1000.0）
- `min_volume`: 最小成交量过滤（默认100000）
- `exclude_st_stocks`: 是否排除ST股票（默认True）

### ReportConfig（报告配置）

- `include_detailed_conditions`: 是否包含详细条件信息（默认True）
- `include_statistics`: 是否包含统计信息（默认True）
- `sort_by`: 排序字段（默认'signal_strength'）
- `sort_ascending`: 是否升序排列（默认False）
- `decimal_places`: 小数位数（默认4）

## 性能优化建议

1. **并行处理**: 对于大量股票，启用并行处理可以显著提高效率
2. **数据预过滤**: 使用价格、成交量等基本条件预过滤可以减少计算量
3. **批量处理**: 一次性处理多只股票比逐个处理更高效
4. **内存管理**: 对于超大数据集，考虑分批处理以控制内存使用

## 错误处理

系统提供了完善的错误处理机制：

- `DataInsufficientException`: 数据不足异常
- `CalculationException`: 计算异常
- `ConfigurationException`: 配置异常
- `ValidationException`: 数据验证异常

## 扩展性

策略引擎采用模块化设计，支持以下扩展：

1. **自定义分析器**: 实现相应的接口可以添加新的维度分析器
2. **自定义信号生成器**: 可以实现不同的信号生成逻辑
3. **自定义报告格式**: 可以添加新的报告输出格式
4. **数据源适配**: 可以适配不同的数据源接口

## 注意事项

1. **数据质量**: 确保输入数据的准确性和完整性
2. **参数调优**: 根据市场情况调整筛选参数
3. **风险控制**: 选股结果仅供参考，需要结合其他分析方法
4. **定期更新**: 定期更新数据和重新运行分析以获得最新结果

## 演示和测试

- 运行 `demo_strategy_engine.py` 查看完整演示
- 运行 `test_strategy_engine_integration.py` 执行集成测试

## 技术支持

如有问题或建议，请参考：
- 设计文档: `design.md`
- 需求文档: `requirements.md`
- 任务列表: `tasks.md`