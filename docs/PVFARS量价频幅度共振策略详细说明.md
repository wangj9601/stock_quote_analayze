# PVFARS量价频幅度共振策略详细说明

## 1. 策略概述

PVFARS（Price, Volume, Frequency, Amplitude, Resonance Strategy）量价频幅度共振选股策略是一种基于价格、成交量、频率、幅度四个维度综合分析的量化选股模型。该策略通过检测股票在三个维度上的共振状态，并结合幅度分析、趋势持续性、乖离率分析等技术指标，识别进入高效率演化轨道的投资机会。

### 1.1 策略核心理念

- **三维共振**：价格维度、频率维度、成交量维度同时满足特定条件
- **高效率演化轨道**：股票进入持续上涨的良性循环状态
- **量化筛选**：基于明确的数学指标和逻辑条件进行选股
- **买点权重判定**：下跌天数多于上涨天数作为买入权重
- **趋势持续性验证**：确保上涨趋势的稳定性和持续性

### 1.2 策略架构

```
PVFARS策略架构
├── 价格维度分析器 (PriceDimensionAnalyzer)
│   ├── 宏观位移指标计算
│   ├── 即时强度指标计算
│   ├── 价格趋势持续性分析
│   ├── 价格波动率分析
│   ├── 乖离率计算与趋势分析
│   └── 价格维度条件验证
├── 频率维度分析器 (FrequencyDimensionAnalyzer)
│   ├── 上涨/下跌天数统计
│   ├── 频率权重判定 (F > Z)
│   ├── 虚假繁荣检测
│   ├── 上涨集中度分析
│   ├── 上涨持续性验证
│   └── 频率维度条件验证
├── 成交量维度分析器 (VolumeDimensionAnalyzer)
│   ├── 成交量效率指标计算
│   ├── 量价共振状态检测
│   ├── 资金支撑质量分析
│   ├── 连续放量验证
│   ├── 成交量趋势持续性分析
│   └── 成交量维度条件验证
├── 三维共振检测器 (ResonanceDetector)
│   ├── 三维条件综合验证
│   ├── 买点排除机制
│   ├── 共振强度计算
│   └── 高效率演化轨道确认
└── 信号生成器 (SignalGenerator)
    ├── 信号强度评估
    ├── 质量因子调整
    └── 投资建议生成
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

#### 2.1.4 幅度（Amplitude）

**计算公式**: `幅度 = |Δ| = |d₂₀ - d₁|`
**定义**: 宏观位移的数值大小
**业务含义**: 衡量20天价格变化的绝对幅度

#### 2.1.5 幅度比例（Amplitude Ratios）

**计算公式**: 
- `ratio_d20 = Δ / d₂₀`
- `ratio_d1 = Δ / d₁`
**定义**: 宏观位移相对于首尾价格的比率
**业务含义**: 判断整体趋势强度相对于价格水平

### 2.2 增强指标分析

#### 2.2.1 价格趋势持续性分析
- **5天趋势斜率**: 计算最近5天价格的线性回归斜率
- **10天趋势斜率**: 计算最近10天价格的线性回归斜率
- **上涨天数占比**: 计算最近N天中上涨天数的比例
- **最大回撤**: 计算观察期内的最大回撤幅度
- **持续性判定**: 趋势斜率为正且上涨天数占比≥50%且最大回撤<10%

#### 2.2.2 价格波动率分析
- **计算公式**: 标准差/均值
- **业务含义**: 衡量价格波动的剧烈程度
- **阈值**: 波动率<15%为正常，超过则为异常波动

#### 2.2.3 乖离率分析
- **计算公式**: BIAS = (当前价格 - 20日均价) / 20日均价
- **乖离率趋势**: 分析最近5天、10天的bias变化趋势
- **趋势类型**: 扩大(expanding)、收敛(converging)、稳定(stable)

### 2.3 价格维度条件判断（增强版）

#### 2.3.1 条件1: 宏观位移为正
- **判断逻辑**: Δ > 0
- **业务含义**: 股票在20天内整体上涨
- **权重**: 30%

#### 2.3.2 条件2: 即时强度为正
- **判断逻辑**: d₂₀ > d
- **业务含义**: 当前价格高于平均价格，显示强势
- **权重**: 25%

#### 2.3.3 条件3: 价格趋势持续性（新增）
- **判断逻辑**: 趋势持续性为真
- **业务含义**: 确保上涨趋势的稳定性和持续性
- **权重**: 25%

#### 2.3.4 条件4: 价格波动率控制（新增）
- **判断逻辑**: 价格波动率 < 15%
- **业务含义**: 排除异常波动的股票
- **权重**: 20%

#### 2.3.5 价格维度有效性
- **判断逻辑**: 条件1 AND 条件2 AND 条件3 AND 条件4
- **业务含义**: 价格维度同时满足趋势性、强势性、持续性和稳定性要求

## 3. 频率维度分析

### 3.1 核心指标

#### 3.1.0 日价格变化（Daily Price Change）

**定义**: `Δᵢ = dᵢ₊₁ - dᵢ`，表示相邻交易日之间的价格变化

**与Z/F的关系**:
- Z（上涨天数）= count(Δᵢ > 0)
- F（下跌天数）= count(Δᵢ < 0)
- 横盘日（Δᵢ = 0）不计入Z或F

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

#### 3.1.3 买点权重判定 (Frequency Advantage)
- **判断逻辑**: F > Z（下跌天数 > 上涨天数）
- **定义**: 下跌天数严格多于上涨天数
- **业务含义**: 买点侧权重，下跌较多时买入机会更佳
- **权重**: 30%

### 3.2 增强虚假繁荣检测

#### 3.2.1 多维度虚假繁荣检测
- **单日暴涨检测**: 单日涨幅 > 5%
- **连续异常涨幅**: 连续2-3天涨幅 > 3%
- **涨幅集中度检测**: 过度涨幅占总涨幅比例 > 30%
- **上涨分布验证**: 前期上涨天数占比 > 70%且后期上涨天数 < 3
- **整体趋势稳定性**: 排除趋势不够稳定的情况

#### 3.2.2 上涨集中度分析
- **计算公式**: 后期上涨天数 / 总上涨天数
- **业务含义**: 判断上涨是否集中在后期，避免集中在前期的情况
- **应用**: 集中度越高，上涨质量越好

#### 3.2.3 上涨持续性验证
- **计算内容**: 最近10天中的上涨天数
- **阈值**: ≥ 6天
- **业务含义**: 确保上涨具有持续性

### 3.3 频率维度条件判断（买点权重版）

#### 3.3.1 条件1: 频率权重优势
- **判断逻辑**: F > Z（下跌天数严格多于上涨天数）
- **业务含义**: 买点权重，下跌较多时买入机会更佳
- **权重**: 30%

#### 3.3.2 条件2: 持续买盘支撑
- **判断逻辑**: Z ≥ 10（上涨天数占据明显优势）
- **业务含义**: 确保趋势持续性，上涨天数至少占50%
- **权重**: 25%

#### 3.3.3 条件3: 排除虚假繁荣（已优化）
- **判断逻辑**: NOT has_false_prosperity（当前版本已注释，恒通过）
- **业务含义**: 确保上涨趋势由持续买盘推动
- **权重**: 20%

#### 3.3.4 条件4: 频率优势确认
- **判断逻辑**: F > Z（与条件1一致，确保买点权重）
- **业务含义**: 再次确认下跌天数多于上涨天数
- **权重**: 15%

#### 3.3.5 条件5: 上涨持续性验证
- **判断逻辑**: 最近10天中上涨天数 ≥ 6
- **业务含义**: 验证近期上涨的持续性
- **权重**: 10%

#### 3.3.6 频率维度有效性
- **判断逻辑**: 条件1 AND 条件2 AND 条件3 AND 条件4 AND 条件5
- **业务含义**: 频率维度同时满足买点权重、持续性和稳定性要求

#### 3.3.7 重点关注条件（风险预警）
**判断逻辑**: `F > Z 且 d₂₀ < d₁`
**业务含义**: 下跌频率占优且整体下跌，需要重点关注
**应用**: 可作为卖出信号或风险预警

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

### 4.2 增强量价共振分析

#### 4.2.1 量价共振状态检测（增强版）
- **单日量价共振**: 价格上涨 AND 成交量放大
- **连续量价配合**: 检查最近3天的量价配合情况
- **量价相关系数**: 计算价格变化与成交量变化的相关性
- **共振天数统计**: 统计最近3天中量价共振的天数

#### 4.2.2 资金支撑质量分析（增强版）
- **强资金支撑判定**: 
  - 当前成交量 ≥ 1.2倍平均成交量
  - 连续3天成交量放大
  - 成交量递增趋势
  - 成交量放大倍数在1.2-8.0倍之间
- **连续放量验证**: 最近3天都放量且成交量递增
- **成交量倍数**: 当前成交量/20日平均成交量

#### 4.2.3 成交量趋势持续性分析
- **持续性验证**: 
  - 最近5天中至少3天成交量>20日均量
  - 成交量放大天数占比≥60%
- **趋势稳定性**: 确保成交量放大的持续性

#### 4.2.4 低成色信号过滤
- **成交量不足**: 当前成交量 < 80%平均成交量
- **成交量过度放大**: 当前成交量 > 10倍平均成交量
- **异常交易识别**: 排除可能的异常交易行为

### 4.3 成交量维度条件判断（增强版）

#### 4.3.1 条件1: 成交量效率
- **判断逻辑**: m₂₀ > m（当前成交量高于平均水平）
- **业务含义**: 当前成交量高于平均水平
- **权重**: 20%

#### 4.3.2 条件2: 量价共振状态
- **判断逻辑**: 价格上涨 AND 成交量放大
- **业务含义**: 健康的量价配合
- **权重**: 25%

#### 4.3.3 条件3: 强劲资金支撑（增强版）
- **判断逻辑**: 强资金支撑 AND 连续放量
- **业务含义**: 充足且持续的资金流入
- **权重**: 30%

#### 4.3.4 条件4: 高质量信号
- **判断逻辑**: 排除低成色信号
- **业务含义**: 确保信号质量
- **权重**: 15%

#### 4.3.5 条件5: 成交量趋势持续性
- **判断逻辑**: 成交量趋势持续
- **业务含义**: 确保成交量放大的持续性
- **权重**: 10%

#### 4.3.6 成交量维度有效性
- **业务含义**: 成交量维度同时满足效率、共振、支撑和持续性要求

## 5. 三维共振检测

### 5.1 三维共振检测（增强版）

#### 5.1.1 基本共振条件
- **判断逻辑**: 价格维度有效 AND 频率维度有效 AND 成交量维度有效
- **业务含义**: 三个维度同时满足条件
- **维度权重**: 价格40%、频率30%、成交量30%

#### 5.1.2 买点排除机制（新增）
- **F≥Z且Δ<0排除**: 下跌频率占优且整体下跌时排除买点
- **横盘排除**: 横盘状态时排除买点（可配置）
- **Δ/d₂₀超限排除**: 幅度比例超过上限时排除（可配置）

#### 5.1.3 高效率演化轨道确认（增强版）
- **确认条件**: 
  - 三维共振为真
  - 买点排除机制通过
  - 共振强度达到阈值
- **业务含义**: 股票进入持续上涨的良性循环状态

#### 5.1.4 共振强度计算
- **计算方法**: 基于各维度满足条件的数量和质量
- **维度得分**: 
  - 价格维度得分：基于趋势性、强势性、持续性、稳定性
  - 频率维度得分：基于买点权重、持续性、稳定性
  - 成交量维度得分：基于效率、共振、支撑、持续性
- **综合得分**: 加权平均计算总体共振强度

### 5.2 信号强度评估
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

### 10.1 核心类结构（基于最新实现）

#### 10.1.1 StrategyEngine (策略引擎)
```python
class StrategyEngine:
    def __init__(self, config=None):
        # 初始化各个维度分析器
        self.price_analyzer = PriceDimensionAnalyzer()
        self.frequency_analyzer = FrequencyDimensionAnalyzer()
        self.volume_analyzer = VolumeDimensionAnalyzer()
        
        # 共振检测器：支持买点参数配置
        if config:
            buy_ratio_d20_max = config.get('buy_ratio_d20_max', 0.5)
            buy_exclude_sideways = config.get('buy_exclude_sideways', True)
            self.resonance_detector = ResonanceDetector(
                buy_ratio_d20_max=float(buy_ratio_d20_max),
                buy_exclude_sideways=bool(buy_exclude_sideways)
            )
        else:
            self.resonance_detector = ResonanceDetector()
        
        self.signal_generator = SignalGenerator()
        self.min_data_length = int(config.get('observation_period', 20)) if config else 20
    
    def analyze_stock(self, symbol, data):
        # 验证数据充足性
        if len(data) < self.min_data_length:
            raise DataInsufficientException(f"数据不足，需要至少{self.min_data_length}天数据")
        
        # 1. 价格维度分析（增强版）
        price_indicators = self.price_analyzer.analyze(data)
        
        # 2. 频率维度分析（买点权重版）
        frequency_indicators = self.frequency_analyzer.analyze(data)
        
        # 3. 成交量维度分析（增强版）
        volume_indicators = self.volume_analyzer.analyze(data)
        
        # 4. 三维共振检测（增强版）
        resonance_result = self.resonance_detector.detect_resonance(
            price_indicators, frequency_indicators, volume_indicators
        )
        
        # 5. 构建完整的PVFRS指标
        pvfrs_indicators = PVFRSIndicators(
            # 价格维度指标
            macro_displacement=price_indicators['macro_displacement'],
            instant_deviation=price_indicators['instant_deviation'],
            avg_price_20d=price_indicators['avg_price_20d'],
            
            # 频率维度指标
            rising_days=frequency_indicators['rising_days'],
            falling_days=frequency_indicators['falling_days'],
            frequency_advantage=frequency_indicators['frequency_advantage'],
            
            # 成交量维度指标
            avg_volume_20d=volume_indicators['avg_volume_20d'],
            current_volume=volume_indicators['current_volume'],
            efficiency_ratio=volume_indicators['efficiency_ratio'],
            
            # 共振检测结果
            three_dimension_resonance=resonance_result['three_dimension_resonance'],
            high_efficiency_trajectory=resonance_result['high_efficiency_trajectory'],
            resonance_strength=resonance_result['resonance_strength'],
            conditions_met=resonance_result['conditions_met']
        )
        
        # 6. 生成交易信号
        signal = self.signal_generator.generate_signal(
            symbol, data[-1].date, data[-1].close, pvfrs_indicators
        )
        
        return signal
```

#### 10.1.2 StockScreener (股票筛选器)
```python
class StockScreener:
    def __init__(self, strategy_engine=None):
        self.strategy_engine = strategy_engine or StrategyEngine()
        self.screening_config = ScreeningConfig()
    
    def screen_stocks(self, stock_data_dict, target_date, config=None):
        results = []
        config = config or self.screening_config
        
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
                        volume=data[-1].volume,
                        name=get_stock_name(symbol)  # 获取股票名称
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

### 10.2 关键算法实现（基于最新代码）

#### 10.2.1 价格趋势持续性分析算法
```python
def analyze_price_trend_persistence(self, data):
    """分析价格趋势持续性"""
    recent_data = data[-self.observation_period:]
    
    # 计算最近5天趋势斜率
    trend_5d = self._calculate_trend_slope(recent_data[-5:])
    
    # 计算最近10天趋势斜率
    trend_10d = self._calculate_trend_slope(recent_data[-10:])
    
    # 计算上涨天数占比
    recent_5d_rising_ratio = self._calculate_rising_ratio(recent_data[-5:])
    recent_10d_rising_ratio = self._calculate_rising_ratio(recent_data[-10:])
    
    # 计算最大回撤
    max_drawdown = self._calculate_max_drawdown(recent_data)
    
    # 持续性判定
    is_persistent = (trend_5d > 0 and trend_10d > 0 and 
                    recent_10d_rising_ratio >= 0.5 and max_drawdown < 0.10)
    
    return {
        'trend_5d_slope': trend_5d,
        'trend_10d_slope': trend_10d,
        'recent_5d_rising_ratio': recent_5d_rising_ratio,
        'recent_10d_rising_ratio': recent_10d_rising_ratio,
        'max_drawdown': max_drawdown,
        'is_persistent': is_persistent
    }
```

#### 10.2.2 虚假繁荣检测算法
```python
def detect_false_prosperity(self, data):
    """检测虚假繁荣（多维度）"""
    recent_data = data[-self.observation_period:]
    
    # 计算每日涨跌幅
    daily_changes = []
    for i in range(1, len(recent_data)):
        change_pct = (recent_data[i].close - recent_data[i-1].close) / recent_data[i-1].close * 100
        daily_changes.append(change_pct)
    
    positive_changes = [change for change in daily_changes if change > 0]
    
    if not positive_changes:
        return False
    
    # 检测1: 单日异常涨幅（超过5%）
    excessive_gains = [change for change in positive_changes if change > 5.0]
    if excessive_gains:
        total_positive_change = sum(positive_changes)
        excessive_gain_ratio = sum(excessive_gains) / total_positive_change
        if excessive_gain_ratio > 0.3:
            return True
    
    # 检测2: 连续异常涨幅（连续2-3天涨幅>3%）
    consecutive_days = 0
    for change in daily_changes:
        if change > 3.0:
            consecutive_days += 1
            if consecutive_days >= 2:
                return True
        else:
            consecutive_days = 0
    
    # 检测3: 上涨分布验证
    rising_days_indices = [i for i, change in enumerate(daily_changes) if change > 0]
    if rising_days_indices:
        early_rising = sum(1 for idx in rising_days_indices if idx < 10)
        late_rising = len(rising_days_indices) - early_rising
        
        if len(rising_days_indices) > 0:
            early_ratio = early_rising / len(rising_days_indices)
            if early_ratio > 0.7 and late_rising < 3:
                return True
    
    return False
```

#### 10.2.3 连续放量验证算法
```python
def analyze_fund_support_quality(self, data):
    """分析资金支撑质量（增强版）"""
    avg_volume_20d = self.calculate_avg_volume_20d(data)
    current_volume = data[-1].volume
    
    # 强资金支撑判定
    volume_multiplier = current_volume / avg_volume_20d
    strong_fund_support = (1.2 <= volume_multiplier <= 8.0)
    
    # 连续放量验证
    continuous_volume_increase = False
    if len(data) >= 3:
        recent_data = data[-3:]
        consecutive_days = sum(1 for day in recent_data if day.volume > avg_volume_20d)
        
        # 检查成交量是否递增
        volumes_increasing = all(
            recent_data[i].volume >= recent_data[i-1].volume 
            for i in range(1, len(recent_data))
        )
        continuous_volume_increase = consecutive_days >= 3 and volumes_increasing
    
    return {
        'strong_fund_support': strong_fund_support,
        'continuous_volume_increase': continuous_volume_increase,
        'volume_multiplier': volume_multiplier,
        'fund_support_quality': strong_fund_support and continuous_volume_increase
    }
```

#### 10.2.4 三维共振检测算法
```python
def detect_resonance(self, price_indicators, frequency_indicators, volume_indicators):
    """检测三维共振状态（增强版）"""
    # 获取各维度的条件满足情况
    price_valid = price_indicators.get('price_dimension_valid', False)
    frequency_valid = frequency_indicators.get('frequency_dimension_valid', False)
    volume_valid = volume_indicators.get('volume_dimension_valid', False)
    
    # 记录满足的具体条件
    conditions_met = self._analyze_detailed_conditions(
        price_indicators, frequency_indicators, volume_indicators
    )
    
    # 三维共振判定
    three_dimension_resonance = price_valid and frequency_valid and volume_valid
    
    # 买点排除机制
    if conditions_met.get('buy_excluded_fz_delta', False):
        three_dimension_resonance = False
    if conditions_met.get('buy_excluded_sideways', False):
        three_dimension_resonance = False
    if not conditions_met.get('ratio_d20_ok', True):
        three_dimension_resonance = False
    
    # 计算共振强度
    resonance_strength = self.calculate_resonance_strength(conditions_met)
    
    # 确认高效率演化轨道
    high_efficiency_trajectory = self._confirm_high_efficiency_trajectory(
        three_dimension_resonance, resonance_strength, conditions_met
    )
    
    return {
        'price_dimension_valid': price_valid,
        'frequency_dimension_valid': frequency_valid,
        'volume_dimension_valid': volume_valid,
        'three_dimension_resonance': three_dimension_resonance,
        'high_efficiency_trajectory': high_efficiency_trajectory,
        'resonance_strength': resonance_strength,
        'conditions_met': conditions_met,
        'dimension_scores': {
            'price_score': self._calculate_dimension_score(price_indicators, 'price'),
            'frequency_score': self._calculate_dimension_score(frequency_indicators, 'frequency'),
            'volume_score': self._calculate_dimension_score(volume_indicators, 'volume'),
            'resonance_score': self._calculate_resonance_score(resonance_indicators)
        }
    }
```
### 10.3 前端展示

#### 10.3.1 结果表格展示
```javascript
// PVFARS策略结果表格
function renderPVFARSResults(results) {
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

## 11. 策略优化建议

### 11.1 参数调优

#### 11.1.1 价格维度参数
- **观察周期**: 可调整为10天、30天等不同周期
- **波动率阈值**: 可根据市场波动性调整15%的阈值
- **趋势持续性权重**: 可调整趋势斜率和上涨天数占比的权重

#### 11.1.2 频率维度参数
- **买点权重**: F>Z的差值阈值可调整
- **虚假繁荣检测**: 单日涨幅阈值和连续涨幅阈值可调整
- **上涨持续性**: 最近10天上涨天数阈值可调整

#### 11.1.3 成交量维度参数
- **资金支撑倍数**: 1.2-8.0倍的范围可调整
- **连续放量天数**: 3天可调整为2天或4天
- **成交量趋势持续性**: 5天中3天的标准可调整

### 11.2 策略增强

#### 11.2.1 市场环境适应
- **牛市模式**: 降低筛选标准，增加选股数量
- **熊市模式**: 提高筛选标准，减少选股数量
- **震荡市模式**: 适中的筛选标准

#### 11.2.2 行业轮动
- **行业权重**: 根据行业热点调整不同行业的权重
- **资金流向**: 结合大单资金流向数据
- **政策影响**: 考虑政策对不同行业的影响

#### 11.2.3 风险控制
- **止损机制**: 动态止损位设置
- **仓位管理**: 根据信号强度动态调整仓位
- **分散投资**: 行业分散和市值分散

### 11.3 回测验证

#### 11.3.1 历史回测
- **时间跨度**: 至少2年的历史数据回测
- **市场环境**: 牛市、熊市、震荡市的不同表现
- **基准比较**: 与沪深300、创业板指等基准比较

#### 11.3.2 实盘验证
- **模拟交易**: 小资金模拟交易验证
- **实盘跟踪**: 实盘表现跟踪和分析
- **策略优化**: 根据实盘结果持续优化

## 12. 总结

PVFARS量价频幅度共振策略是一个基于多维度分析的量化选股模型，具有以下特点：

### 12.1 策略优势
- **多维度分析**: 价格、频率、成交量三个维度综合分析
- **买点权重**: 独特的F>Z买点权重判定机制
- **趋势持续性**: 强调趋势的稳定性和持续性
- **量价配合**: 重视成交量与价格的配合关系
- **风险控制**: 多层次的风险识别和控制机制

### 12.2 适用场景
- **中长期投资**: 适合10-20个交易日的投资周期
- **趋势跟踪**: 适合趋势明显的市场环境
- **价值发现**: 能够发现被低估的投资机会
- **风险控制**: 适合风险偏好较低的投资者

### 12.3 使用建议
- **参数调整**: 根据市场环境调整策略参数
- **风险控制**: 严格执行止损和仓位管理
- **持续优化**: 根据回测和实盘结果持续优化
- **组合投资**: 建议采用组合投资降低风险

PVFARS策略通过科学的量化分析，为投资者提供了一个系统化的选股工具，能够有效识别进入高效率演化轨道的投资机会，是实现稳健投资的重要工具。
