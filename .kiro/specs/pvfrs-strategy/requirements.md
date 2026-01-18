# 需求文档

## 介绍

量价频三维共振演化策略（PVFRS）是一个基于价格、频率和成交量三个维度的量化股票选股和交易策略。该策略通过量化分析市场在价格方向、微观共识与资金动力三个维度的共振状态，识别处于"高效率上涨"阶段的股票，并提供完整的选股、信号生成、前端展示和回测功能。

## 术语表

- **PVFRS_System**: 完整的量价频三维共振演化策略系统
- **Strategy_Engine**: 策略引擎，负责执行选股和回测逻辑
- **Signal_Generator**: 信号生成器，负责生成买卖信号
- **Backtest_Engine**: 回测引擎，负责历史数据回测
- **Data_Interface**: 数据接口，用于标准化数据获取和处理
- **Config_Manager**: 配置管理器，负责参数验证和存储
- **Risk_Manager**: 风险管理模块，负责控制交易风险
- **Frontend_Interface**: 前端接口，负责选股频道页面展示
- **Admin_Interface**: 管理端接口，负责回测功能管理
- **High_Efficiency_Uptrend**: 高效率上涨，市场在价格方向、微观共识与资金动力三个维度达成向上共振的状态
- **Macro_Displacement_Indicator**: 宏观位移指标，Δ = d₂₀ - d₁，观察周期末位价格与起始价格的差值
- **Instant_Strength_Indicator**: 即时强度指标，d₂₀ > d，末位价格高于周期内平均价格
- **Rising_Frequency_Advantage**: 上涨频率优势，Z > F，上涨天数严格多于下跌天数
- **Efficiency_Indicator**: 进出效率指标，m₂₀ > m，即时成交量高于周期平均成交量

## 需求

### 需求 1: 价格维度分析

**用户故事**: 作为量化交易员，我希望系统能够分析价格维度的方向与强度，以便确认市场的盈亏状态和即时强弱。

#### 验收标准

1. WHEN THE PVFRS_System 计算宏观位移指标 THEN THE Strategy_Engine SHALL 计算 Δ = d₂₀ - d₁ 并验证 Δ > 0
2. WHEN THE PVFRS_System 计算即时强度指标 THEN THE Strategy_Engine SHALL 验证 d₂₀ > d（末位价格高于平均价格）
3. WHEN 价格维度条件满足 THEN THE Strategy_Engine SHALL 标记价格维度为"强势演化阶段"
4. WHEN 价格维度条件不满足 THEN THE Strategy_Engine SHALL 排除该股票的选股候选

### 需求 2: 频率维度分析

**用户故事**: 作为量化交易员，我希望系统能够分析频率维度的微观一致性，以便验证趋势的稳定性和市场共识。

#### 验收标准

1. WHEN THE PVFRS_System 统计观察周期内的涨跌分布 THEN THE Strategy_Engine SHALL 计算上涨天数Z和下跌天数F
2. WHEN THE PVFRS_System 验证上涨频率优势 THEN THE Strategy_Engine SHALL 确认 Z > F（上涨天数严格多于下跌天数）
3. WHEN 频率维度条件满足 THEN THE Strategy_Engine SHALL 确认趋势由持续买盘推动
4. WHEN 频率维度条件不满足 THEN THE Strategy_Engine SHALL 排除"虚假繁荣"的单日暴涨情况

### 需求 3: 成交量维度分析

**用户故事**: 作为量化交易员，我希望系统能够分析成交量维度的动力与效率，以便评估趋势的"成色"和资金支撑。

#### 验收标准

1. WHEN THE PVFRS_System 计算进出效率指标 THEN THE Strategy_Engine SHALL 验证 m₂₀ > m（即时成交量高于平均成交量）
2. WHEN 价格上涨且成交量放大 THEN THE Strategy_Engine SHALL 识别为"量价共振"状态
3. WHEN 成交量维度条件满足 THEN THE Strategy_Engine SHALL 确认趋势具有强劲资金支撑
4. WHEN 价格上涨但成交量不足 THEN THE Strategy_Engine SHALL 标记为"低成色"信号并排除

### 需求 4: 三维共振判定

**用户故事**: 作为量化交易员，我希望系统能够综合判定三个维度的共振状态，以便识别高效率上涨的股票。

#### 验收标准

1. WHEN 价格、频率、成交量三个维度条件同时满足 THEN THE Strategy_Engine SHALL 确认进入高效率演化轨道
2. WHEN THE PVFRS_System 检测到三维共振 THEN THE Signal_Generator SHALL 生成买入信号
3. WHEN 任一维度条件不满足 THEN THE Strategy_Engine SHALL 不生成买入信号
4. WHEN 生成买入信号 THEN THE Signal_Generator SHALL 记录满足的具体条件和信号强度

### 需求 5: 入场时机优化

**用户故事**: 作为量化交易员，我希望系统能够优化入场时机，以便在最佳点位介入交易。

#### 验收标准

1. WHEN 价格向上穿越平均价格d THEN THE Signal_Generator SHALL 监控入场机会
2. WHEN 当日成交量突破平均量m THEN THE Signal_Generator SHALL 确认入场时机
3. WHEN THE PVFRS_System 计算幅度校验系数 THEN THE Strategy_Engine SHALL 验证 Δ₂₀/d 系数的有效性
4. WHEN 幅度校验系数过小 THEN THE Strategy_Engine SHALL 等待波幅显著放大

### 需求 6: 选股策略实现

**用户故事**: 作为量化交易员，我希望系统能够实现完整的选股策略，以便筛选出符合PVFRS条件的股票。

#### 验收标准

1. WHEN THE PVFRS_System 执行选股 THEN THE Strategy_Engine SHALL 对股票池中的每只股票应用PVFRS条件
2. WHEN 股票满足三维共振条件 THEN THE Strategy_Engine SHALL 将其加入选股结果
3. WHEN THE PVFRS_System 生成选股结果 THEN THE Strategy_Engine SHALL 按信号强度排序
4. WHEN 输出选股结果 THEN THE Strategy_Engine SHALL 包含股票代码、信号强度、满足条件详情

### 需求 7: 回测引擎实现

**用户故事**: 作为量化交易员，我希望系统能够提供回测功能，以便验证策略的历史表现。

#### 验收标准

1. WHEN THE PVFRS_System 执行回测 THEN THE Backtest_Engine SHALL 使用历史数据模拟交易
2. WHEN 生成买入信号 THEN THE Backtest_Engine SHALL 模拟买入操作并记录交易
3. WHEN 触发卖出条件 THEN THE Backtest_Engine SHALL 模拟卖出操作并计算盈亏
4. WHEN 回测完成 THEN THE Backtest_Engine SHALL 生成包含收益率、胜率、最大回撤等指标的报告

### 需求 8: 风险管理

**用户故事**: 作为量化交易员，我希望系统能够实现风险管理功能，以便控制交易风险。

#### 验收标准

1. WHEN 持仓亏损达到止损线 THEN THE Risk_Manager SHALL 生成止损卖出信号
2. WHEN 持仓盈利达到止盈线 THEN THE Risk_Manager SHALL 生成止盈卖出信号
3. WHEN 持仓时间超过最大持有期 THEN THE Risk_Manager SHALL 生成强制平仓信号
4. WHEN 检测到趋势反转信号 THEN THE Risk_Manager SHALL 生成趋势反转卖出信号

### 需求 9: 数据接口和序列化

**用户故事**: 作为系统开发者，我希望系统能够提供标准化的数据接口和序列化功能，以便与现有数据源集成并确保数据持久化。

#### 验收标准

1. WHEN THE PVFRS_System 需要股票数据 THEN THE Data_Interface SHALL 提供标准化的数据获取接口
2. WHEN 获取历史行情数据 THEN THE Data_Interface SHALL 返回包含开高低收量的标准格式数据
3. WHEN 数据格式不符合要求 THEN THE Data_Interface SHALL 进行数据清洗和标准化
4. WHEN 数据缺失或异常 THEN THE Data_Interface SHALL 提供错误处理和数据修复机制
5. WHEN 存储PVFRS指标到磁盘 THEN THE Data_Interface SHALL 使用JSON格式进行序列化
6. WHEN 从磁盘加载PVFRS指标 THEN THE Data_Interface SHALL 将JSON数据反序列化为指标对象

### 需求 10: 配置管理

**用户故事**: 作为量化交易员，我希望系统能够支持参数配置，以便根据市场情况调整策略参数。

#### 验收标准

1. WHEN 用户修改策略参数 THEN THE Config_Manager SHALL 验证参数的有效性
2. WHEN 参数配置更新 THEN THE Strategy_Engine SHALL 使用新参数执行策略逻辑
3. WHEN THE PVFRS_System 启动 THEN THE Config_Manager SHALL 加载默认或用户自定义的参数配置
4. WHEN 保存参数配置 THEN THE Config_Manager SHALL 将配置持久化存储

### 需求 11: 选股频道前端展示

**用户故事**: 作为用户，我希望在选股频道页面能够看到PVFRS策略的选项卡和结果，以便直观地查看和使用PVFRS选股功能。

#### 验收标准

1. WHEN 用户访问选股频道页面 THEN THE Frontend_Interface SHALL 显示PVFRS策略选项卡
2. WHEN 用户点击PVFRS选项卡 THEN THE Frontend_Interface SHALL 展示PVFRS选股结果列表
3. WHEN 显示选股结果 THEN THE Frontend_Interface SHALL 包含股票代码、股票名称、信号强度、满足条件等信息
4. WHEN 用户点击具体股票 THEN THE Frontend_Interface SHALL 显示该股票的详细PVFRS分析指标
5. WHEN PVFRS选股结果更新 THEN THE Frontend_Interface SHALL 实时刷新显示最新结果

### 需求 12: 管理端回测功能

**用户故事**: 作为管理员，我希望在管理端增加PVFRS策略回测功能，以便对PVFRS策略的回测效果进行分析和与其他策略进行比较。

#### 验收标准

1. WHEN 管理员访问管理端 THEN THE Admin_Interface SHALL 提供PVFRS策略回测功能入口
2. WHEN 管理员配置回测参数 THEN THE Admin_Interface SHALL 允许设置回测时间范围、股票池、策略参数等
3. WHEN 执行PVFRS回测 THEN THE Admin_Interface SHALL 调用Backtest_Engine并显示回测进度
4. WHEN 回测完成 THEN THE Admin_Interface SHALL 展示详细的回测报告，包括收益率曲线、交易记录、风险指标等
5. WHEN 查看回测结果 THEN THE Admin_Interface SHALL 提供与其他策略回测结果的对比功能
6. WHEN 保存回测结果 THEN THE Admin_Interface SHALL 将回测报告持久化存储并支持历史查询