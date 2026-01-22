# PVFRS三维共振选股策略详细说明

## 1. 策略概述

PVFRS（Price, Volume, Frequency, Resonance, Strength）三维共振选股策略是一种基于价格、成交量、频率三个维度综合分析的量化选股模型。该策略通过检测股票在三个维度上的共振状态，识别进入高效率演化轨道的投资机会。

### 1.1 策略核心理念

- **三维共振**：价格维度、频率维度、成交量维度同时满足特定条件
- **高效率演化轨道**：股票进入持续上涨的良性循环状态
- **量化筛选**：基于明确的数学指标和逻辑条件进行选股

### 1.2 策略架构

```
PVFRS策略架构
├── 价格维度分析器 (PriceDimensionAnalyzer)
├── 频率维度分析器 (FrequencyDimensionAnalyzer)  
├── 成交量维度分析器 (VolumeDimensionAnalyzer)
├── 三维共振检测器 (ResonanceDetector)
└── 信号生成器 (SignalGenerator)
```

## 2. 价格维度分析

### 2.1 核心指标

#### 2.1.1 宏观位移指标 (Macro Displacement)
- **计算公式**: Δ = d₂₀ - d₁
- **定义**: 20天观察期内，期末价格与期初价格的差值
- **业务含义**: 衡量股票在观察期内的整体价格趋势
- **数据来源**: 最近20天收盘价数据

```python
def calculate_macro_displacement(data):
    d1 = recent_data[0].close      # 第1天收盘价
    d20 = recent_data[-1].close   # 第20天收盘价
    macro_displacement = d20 - d1
    return macro_displacement
```

#### 2.1.2 即时强度指标 (Instant Deviation)
- **计算公式**: d₂₀ - d
- **定义**: 当前价格相对于20日平均价格的偏离程度
- **业务含义**: 反映当前价格的强势程度
- **数据来源**: 最新收盘价和20日均价

```python
def calculate_instant_deviation(data):
    d20 = recent_data[-1].close
    avg_price = calculate_avg_price_20d(data)
    instant_deviation = d20 - avg_price
    return instant_deviation
```

#### 2.1.3 20日平均价格 (20-day Average Price)
- **计算公式**: d = (d₁ + d₂ + ... + d₂₀) / 20
- **定义**: 20天观察期内的平均收盘价
- **业务含义**: 价格波动的基准线

### 2.2 价格维度条件判断

#### 2.2.1 条件1: 宏观位移为正
- **判断逻辑**: Δ > 0
- **业务含义**: 股票在20天内整体上涨
- **权重**: 40%

#### 2.2.2 条件2: 即时强度为正
- **判断逻辑**: d₂₀ > d
- **业务含义**: 当前价格高于平均价格，显示强势
- **权重**: 30%

#### 2.2.3 价格维度有效性
- **判断逻辑**: 条件1 AND 条件2
- **业务含义**: 价格维度同时满足趋势性和强势性要求

## 3. 频率维度分析

### 3.1 核心指标

#### 3.1.1 上涨天数 (Rising Days)
- **计算公式**: Z = count(dᵢ > dᵢ₋₁) for i in [2, 20]
- **定义**: 20天内收盘价高于前一日的天数
- **业务含义**: 上涨频率的量化指标

```python
def count_rising_days(data):
    rising_days = 0
    for i in range(1, len(recent_data)):
        if recent_data[i].close > recent_data[i-1].close:
            rising_days += 1
    return rising_days
```

#### 3.1.2 下跌天数 (Falling Days)
- **计算公式**: F = count(dᵢ < dᵢ₋₁) for i in [2, 20]
- **定义**: 20天内收盘价低于前一日的天数
- **业务含义**: 下跌频率的量化指标

#### 3.1.3 频率优势 (Frequency Advantage)
- **判断逻辑**: Z > F
- **定义**: 上涨天数严格多于下跌天数
- **业务含义**: 上涨频率占优

### 3.2 虚假繁荣检测

#### 3.2.1 单日暴涨检测
- **检测阈值**: 单日涨幅 > 5%
- **业务含义**: 识别异常的短期波动

#### 3.2.2 虚假繁荣判定
- **判断逻辑**: 
  1. 存在单日涨幅 > 5%
  2. 过度涨幅占总涨幅比例 > 30%
- **业务含义**: 排除由单日异常涨幅造成的虚假繁荣

```python
def detect_false_prosperity(data):
    # 计算每日涨跌幅
    daily_changes = []
    for i in range(1, len(recent_data)):
        change_pct = (recent_data[i].close - recent_data[i-1].close) / recent_data[i-1].close * 100
        daily_changes.append(change_pct)
    
    # 检测过度涨幅
    excessive_gains = [change for change in daily_changes if change > 5.0]
    if excessive_gains:
        total_positive_change = sum([change for change in daily_changes if change > 0])
        excessive_gain_ratio = sum(excessive_gains) / total_positive_change
        return excessive_gain_ratio > 0.3
    
    return False
```

### 3.3 频率维度条件判断

#### 3.3.1 条件1: 频率优势
- **判断逻辑**: Z > F
- **业务含义**: 上涨天数严格多于下跌天数
- **权重**: 30%

#### 3.3.2 条件2: 持续买盘支撑
- **判断逻辑**: Z >= (20-1)//2 = 9
- **业务含义**: 上涨天数占据明显优势，确保趋势持续性
- **权重**: 20%

#### 3.3.3 条件3: 排除虚假繁荣
- **判断逻辑**: NOT has_false_prosperity
- **业务含义**: 确保上涨趋势由持续买盘推动
- **权重**: 25%

## 4. 成交量维度分析

### 4.1 核心指标

#### 4.1.1 20日平均成交量 (20-day Average Volume)
- **计算公式**: m = (m₁ + m₂ + ... + m₂₀) / 20
- **定义**: 20天观察期内的平均成交量
- **业务含义**: 成交量波动的基准线

#### 4.1.2 当前成交量 (Current Volume)
- **定义**: 最新交易日的成交量
- **业务含义**: 当前市场参与度

#### 4.1.3 效率比 (Efficiency Ratio)
- **计算公式**: m₂₀ / m
- **定义**: 当前成交量与平均成交量的比值
- **业务含义**: 成交量放大的程度

### 4.2 量价共振分析

#### 4.2.1 价格上涨检测
- **判断逻辑**: 当前价格 > 前一日价格
- **业务含义**: 价格处于上涨状态

#### 4.2.2 成交量增长检测
- **判断逻辑**: 当前成交量 > 平均成交量
- **业务含义**: 成交量放大

#### 4.2.3 量价共振状态
- **判断逻辑**: 价格上涨 AND 成交量放大
- **业务含义**: 健康的量价配合关系

### 4.3 资金支撑质量分析

#### 4.3.1 强资金支撑判定
- **判断逻辑**: 
  1. 效率比 > 1.5 (成交量放大50%以上)
  2. 连续3天成交量放大
- **业务含义**: 强资金流入支撑

#### 4.3.2 高质量信号识别
- **判断逻辑**: 
  1. 强资金支撑
  2. 量价共振状态
  3. 成交量倍数 > 2.0
- **业务含义**: 高质量的买入信号

### 4.4 成交量维度条件判断

#### 4.4.1 条件1: 成交量效率
- **判断逻辑**: m₂₀ > m
- **业务含义**: 当前成交量高于平均水平
- **权重**: 25%

#### 4.4.2 条件2: 量价共振
- **判断逻辑**: 价格上涨 AND 成交量放大
- **业务含义**: 健康的量价配合
- **权重**: 30%

#### 4.4.3 条件3: 资金支撑
- **判断逻辑**: 强资金支撑
- **业务含义**: 充足的资金流入
- **权重**: 20%

## 5. 三维共振检测

### 5.1 共振条件

#### 5.1.1 基本共振条件
- **判断逻辑**: 价格维度有效 AND 频率维度有效 AND 成交量维度有效
- **业务含义**: 三个维度同时满足条件

#### 5.1.2 高效率演化轨道确认
- **判断逻辑**: 
  1. 三维共振成立
  2. 共振强度 > 0.6
  3. 各维度得分均衡
- **业务含义**: 股票进入持续上涨的良性循环

### 5.2 共振强度计算

#### 5.2.1 维度权重分配
- **价格维度**: 40%
- **频率维度**: 30%
- **成交量维度**: 30%

#### 5.2.2 共振强度公式
```python
def calculate_resonance_strength(conditions_met):
    dimension_weights = {
        'price': 0.4,
        'frequency': 0.3,
        'volume': 0.3
    }
    
    # 计算各维度得分
    price_score = calculate_price_score(conditions_met)
    frequency_score = calculate_frequency_score(conditions_met)
    volume_score = calculate_volume_score(conditions_met)
    
    # 加权计算共振强度
    resonance_strength = (
        price_score * dimension_weights['price'] +
        frequency_score * dimension_weights['frequency'] +
        volume_score * dimension_weights['volume']
    )
    
    return resonance_strength
```

### 5.3 共振状态分类

#### 5.3.1 三维共振 (Three-Dimension Resonance)
- **条件**: 所有维度条件都满足
- **共振强度**: > 0.8
- **投资建议**: BUY (买入)

#### 5.3.2 部分共振 (Partial Resonance)
- **条件**: 2个维度条件满足
- **共振强度**: 0.6 - 0.8
- **投资建议**: HOLD (持有)

#### 5.3.3 无共振 (No Resonance)
- **条件**: 少于2个维度条件满足
- **共振强度**: < 0.6
- **投资建议**: WAIT (等待)

## 6. 信号强度评估

### 6.1 信号强度计算

#### 6.1.1 基础强度
- **来源**: 三维共振强度
- **范围**: 0-1
- **阈值**: 0.6 (最小信号强度)

#### 6.1.2 质量调整因子
- **高质量信号**: +0.1
- **虚假繁荣**: -0.2
- **量价背离**: -0.1

#### 6.1.3 最终信号强度
```python
def calculate_final_signal_strength(base_strength, quality_factors):
    final_strength = base_strength
    
    # 应用质量调整
    if quality_factors['is_high_quality']:
        final_strength += 0.1
    if quality_factors['has_false_prosperity']:
        final_strength -= 0.2
    if quality_factors['volume_price_divergence']:
        final_strength -= 0.1
    
    # 确保在0-1范围内
    final_strength = max(0, min(1, final_strength))
    
    return final_strength
```

### 6.2 信号强度分级

#### 6.2.1 高强度信号 (High Strength)
- **范围**: 0.8 - 1.0
- **颜色标识**: 红色 (strength-high)
- **投资建议**: 强烈买入

#### 6.2.2 中强度信号 (Medium Strength)
- **范围**: 0.6 - 0.8
- **颜色标识**: 橙色 (strength-mid)
- **投资建议**: 谨慎买入

#### 6.2.3 低强度信号 (Low Strength)
- **范围**: 0.0 - 0.6
- **颜色标识**: 灰色 (strength-low)
- **投资建议**: 观察等待

## 7. 入场时机优化

### 7.1 入场时机评估

#### 7.1.1 技术位置分析
- **相对位置**: 当前价格在20日价格区间中的位置
- **突破确认**: 是否突破关键阻力位
- **回调机会**: 是否出现健康的回调

#### 7.1.2 市场环境评估
- **大盘走势**: 整体市场趋势
- **行业轮动**: 所属行业的资金流向
- **风险偏好**: 市场风险偏好水平

### 7.2 入场时机状态

#### 7.2.1 最佳入场 (Optimal Entry)
- **条件**: 
  1. 三维共振 + 高信号强度
  2. 技术位置良好
  3. 市场环境配合
- **操作建议**: 立即买入

#### 7.2.2 良好入场 (Good Entry)
- **条件**: 
  1. 三维共振 + 中信号强度
  2. 技术位置一般
  3. 市场环境中性
- **操作建议**: 分批买入

#### 7.2.3 等待入场 (Wait Entry)
- **条件**: 
  1. 部分共振
  2. 技术位置不佳
  3. 市场环境不利
- **操作建议**: 等待机会

## 8. 投资建议生成

### 8.1 建议等级

#### 8.1.1 买入 (BUY)
- **触发条件**: 
  - 三维共振
  - 信号强度 >= 0.8
  - 高质量信号
- **颜色标识**: 绿色 (advice-buy)
- **仓位建议**: 5-8%

#### 8.1.2 持有 (HOLD)
- **触发条件**: 
  - 部分共振
  - 信号强度 0.6-0.8
  - 中等质量信号
- **颜色标识**: 黄色 (advice-hold)
- **仓位建议**: 2-5%

#### 8.1.3 等待 (WAIT)
- **触发条件**: 
  - 无共振
  - 信号强度 < 0.6
  - 低质量信号
- **颜色标识**: 灰色 (advice-wait)
- **仓位建议**: 0%

### 8.2 风险提示

#### 8.2.1 主要风险
- **市场风险**: 大盘系统性下跌
- **个股风险**: 公司基本面恶化
- **技术风险**: 技术形态破坏

#### 8.2.2 风险控制建议
- **止损设置**: 8-10%止损
- **仓位控制**: 单股不超过8%
- **分散投资**: 持股数量不超过10只

## 9. 业务流程

### 9.1 选股流程

```
选股流程
├── 1. 数据获取
│   ├── 股票基础信息
│   ├── 历史价格数据 (20天)
│   └── 成交量数据 (20天)
├── 2. 维度分析
│   ├── 价格维度分析
│   ├── 频率维度分析
│   └── 成交量维度分析
├── 3. 共振检测
│   ├── 三维条件验证
│   ├── 共振强度计算
│   └── 演化轨道确认
├── 4. 信号生成
│   ├── 信号强度评估
│   ├── 质量因子调整
│   └── 投资建议生成
└── 5. 结果输出
    ├── 选股结果列表
    ├── 详细指标数据
    └── 投资建议报告
```

### 9.2 数据处理流程

#### 9.2.1 数据预处理
- **数据清洗**: 去除异常值和缺失值
- **数据标准化**: 统一数据格式和单位
- **数据验证**: 确保数据完整性和准确性

#### 9.2.2 指标计算
- **价格指标**: 宏观位移、即时强度、平均价格
- **频率指标**: 上涨天数、下跌天数、频率优势
- **成交量指标**: 平均成交量、效率比、量价共振

#### 9.2.3 结果整合
- **条件汇总**: 各维度条件满足情况
- **强度计算**: 综合信号强度
- **建议生成**: 投资建议和风险提示

## 10. 技术实现

### 10.1 核心类结构

#### 10.1.1 StrategyEngine (策略引擎)
```python
class StrategyEngine:
    def __init__(self):
        self.price_analyzer = PriceDimensionAnalyzer()
        self.frequency_analyzer = FrequencyDimensionAnalyzer()
        self.volume_analyzer = VolumeDimensionAnalyzer()
        self.resonance_detector = ResonanceDetector()
        self.signal_generator = SignalGenerator()
    
    def analyze_stock(self, symbol, data):
        # 1. 价格维度分析
        price_indicators = self.price_analyzer.analyze(data)
        
        # 2. 频率维度分析
        frequency_indicators = self.frequency_analyzer.analyze(data)
        
        # 3. 成交量维度分析
        volume_indicators = self.volume_analyzer.analyze(data)
        
        # 4. 三维共振检测
        resonance_result = self.resonance_detector.detect_resonance(
            price_indicators, frequency_indicators, volume_indicators
        )
        
        # 5. 生成交易信号
        signal = self.signal_generator.generate_signal(
            symbol, data[-1].date, data[-1].close, 
            resonance_result
        )
        
        return signal
```

#### 10.1.2 StockScreener (股票筛选器)
```python
class StockScreener:
    def screen_stocks(self, stock_data_dict, target_date, config):
        results = []
        
        for symbol, data in stock_data_dict.items():
            try:
                # 分析单只股票
                signal = self.strategy_engine.analyze_stock(symbol, data)
                
                # 检查是否满足选股条件
                if signal.strength >= config.min_signal_strength:
                    result = SelectionResult(
                        symbol=symbol,
                        date=target_date,
                        signal_strength=signal.strength,
                        signal_reason=signal.reason,
                        conditions_met=signal.conditions_met,
                        price=data[-1].close,
                        volume=data[-1].volume
                    )
                    results.append(result)
                    
            except Exception as e:
                # 记录错误，继续处理其他股票
                continue
        
        # 按信号强度排序
        results.sort(key=lambda x: x.signal_strength, reverse=True)
        
        # 限制结果数量
        return results[:config.max_results]
```

### 10.2 前端展示

#### 10.2.1 结果表格展示
```javascript
// PVFRS策略结果表格
function renderPVFRSResults(results) {
    let html = '';
    results.forEach((stock, index) => {
        // 信号强度颜色
        let strengthClass = '';
        if (stock.signal_strength >= 0.8) {
            strengthClass = 'strength-high';
        } else if (stock.signal_strength >= 0.6) {
            strengthClass = 'strength-mid';
        } else {
            strengthClass = 'strength-low';
        }
        
        // 共振状态显示
        let resonanceClass = '';
        if (stock.resonance_status === '三维共振') {
            resonanceClass = 'resonance-active';
        } else if (stock.resonance_status === '部分共振') {
            resonanceClass = 'resonance-partial';
        } else {
            resonanceClass = 'resonance-none';
        }
        
        html += `
            <tr>
                <td>${stock.symbol}</td>
                <td>${stock.name}</td>
                <td class="${strengthClass}">${(stock.signal_strength * 100).toFixed(1)}%</td>
                <td>${stock.current_price.toFixed(2)}</td>
                <td>${stock.price_dimension_status}</td>
                <td>${stock.frequency_dimension_status}</td>
                <td>${stock.volume_dimension_status}</td>
                <td class="${resonanceClass}">${stock.resonance_status}</td>
                <td>${stock.entry_timing_status}</td>
                <td>${stock.investment_advice}</td>
            </tr>
        `;
    });
    
    return html;
}
```

#### 10.2.2 交互功能
- **股票详情**: 点击股票代码查看详细分析
- **历史数据**: 查看股票历史PVFRS指标变化
- **实时更新**: 定期更新选股结果
- **参数调整**: 动态调整选股参数

## 11. 参数配置

### 11.1 基础参数

#### 11.1.1 选股参数
- **最小信号强度**: 0.6 (可调整范围: 0.5-0.8)
- **最大结果数量**: 50 (可调整范围: 10-200)
- **观察周期**: 20天 (固定)

#### 11.1.2 过滤参数
- **最小价格**: 1.0元
- **最大价格**: 1000.0元
- **最小成交量**: 10万股
- **排除ST股**: 是

### 11.2 高级参数

#### 11.2.1 维度权重
- **价格维度权重**: 0.4 (可调整范围: 0.3-0.5)
- **频率维度权重**: 0.3 (可调整范围: 0.2-0.4)
- **成交量维度权重**: 0.3 (可调整范围: 0.2-0.4)

#### 11.2.2 风险控制参数
- **虚假繁荣阈值**: 5% (单日涨幅)
- **虚假繁荣比例**: 30% (占总涨幅比例)
- **成交量放大阈值**: 1.5倍
- **强资金支撑阈值**: 2.0倍

## 12. 性能优化

### 12.1 计算优化

#### 12.1.1 并行处理
- **多线程处理**: 同时分析多只股票
- **批量计算**: 批量获取和处理数据
- **缓存机制**: 缓存中间计算结果

#### 12.1.2 数据优化
- **数据预加载**: 提前加载所需数据
- **增量更新**: 只更新变化的数据
- **数据压缩**: 压缩存储历史数据

### 12.2 系统优化

#### 12.2.1 数据库优化
- **索引优化**: 为关键字段建立索引
- **查询优化**: 优化SQL查询语句
- **连接池**: 使用数据库连接池

#### 12.2.2 前端优化
- **分页加载**: 分页显示大量结果
- **异步加载**: 异步加载数据
- **缓存策略**: 缓存常用数据

## 13. 监控与维护

### 13.1 性能监控

#### 13.1.1 系统性能
- **响应时间**: API响应时间监控
- **并发处理**: 并发处理能力监控
- **错误率**: 系统错误率监控

#### 13.1.2 业务监控
- **选股效果**: 选股成功率监控
- **信号质量**: 信号质量分布监控
- **用户反馈**: 用户满意度监控

### 13.2 模型维护

#### 13.2.1 参数调优
- **定期回测**: 定期进行历史数据回测
- **参数优化**: 根据回测结果优化参数
- **A/B测试**: 对不同参数进行A/B测试

#### 13.2.2 模型更新
- **算法升级**: 根据市场变化升级算法
- **特征工程**: 添加新的分析特征
- **模型验证**: 验证模型有效性

## 14. 风险管理

### 14.1 策略风险

#### 14.1.1 模型风险
- **过拟合风险**: 模型过度拟合历史数据
- **参数漂移**: 参数随时间失效
- **黑天鹅事件**: 极端市场情况

#### 14.1.2 执行风险
- **数据质量**: 数据错误或缺失
- **系统故障**: 系统技术故障
- **人为错误**: 人为操作失误

### 14.2 风险控制

#### 14.2.1 技术控制
- **数据验证**: 严格的数据验证机制
- **异常检测**: 实时异常检测
- **容错机制**: 系统容错和恢复

#### 14.2.2 业务控制
- **仓位限制**: 严格的仓位控制
- **止损机制**: 自动止损机制
- **分散投资**: 投资组合分散化

## 15. 总结

PVFRS三维共振选股策略通过价格、频率、成交量三个维度的综合分析，实现了对股票投资机会的量化识别。该策略具有以下特点：

### 15.1 策略优势
- **多维分析**: 避免单一指标的局限性
- **量化客观**: 基于明确的数学模型
- **实时动态**: 能够实时反映市场变化
- **风险可控**: 具有完善的风险控制机制

### 15.2 适用场景
- **趋势行情**: 适用于趋势性上涨行情
- **成长股**: 适用于成长性较好的股票
- **中线投资**: 适用于中线投资策略
- **量化交易**: 适用于量化交易系统

### 15.3 使用建议
- **参数调优**: 根据市场环境调整参数
- **风险控制**: 严格执行风险控制措施
- **持续监控**: 持续监控策略效果
- **定期评估**: 定期评估和优化策略

通过深入理解和正确使用PVFRS三维共振选股策略，投资者可以提高选股的成功率和投资收益。
