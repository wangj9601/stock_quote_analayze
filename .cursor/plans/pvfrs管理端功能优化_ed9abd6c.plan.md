---
name: PVFRS管理端功能优化
overview: 根据策略优化逻辑（包括乖离率优化等），优化管理端PVFRS策略管理中的回测任务管理、策略回测、报告分析、策略配置相关功能
todos:
  - id: config-bias-optimization
    content: 策略配置：添加乖离率动态调整配置（市场波动率、价格区间、历史分布）
    status: completed
  - id: config-dimension-enhancement
    content: 策略配置：添加价格/频率/成交量维度增强配置项
    status: completed
  - id: config-signal-quality
    content: 策略配置：添加信号质量分级配置（阈值、权重）
    status: completed
  - id: backtest-param-optimization
    content: 回测任务管理：增强参数优化模式（支持乖离率参数网格搜索）
    status: completed
  - id: backtest-strategy-comparison
    content: 回测任务管理：增加策略对比功能（多配置同时回测）
    status: completed
  - id: report-bias-metrics
    content: 报告分析：增加乖离率相关指标展示（bias得分、趋势、协同）
    status: completed
  - id: report-dimension-analysis
    content: 报告分析：增加维度分析展示（各维度得分、均衡性）
    status: completed
  - id: report-signal-quality
    content: 报告分析：增强信号质量分析（分级统计、分布图、过滤原因）
    status: completed
  - id: api-dynamic-params
    content: 后端API：支持动态参数配置和应用
    status: completed
  - id: api-param-optimization
    content: 后端API：支持参数网格搜索和多目标优化
    status: completed
isProject: false
---

# PVFRS管理端功能优化计划

## 一、优化目标

根据策略改进计划（包括价格维度、频率维度、成交量维度、乖离率优化等），优化管理端PVFRS策略管理功能，使其能够：

1. 支持新的策略参数配置（包括动态乖离率阈值）
2. 提供更完善的回测任务管理（支持参数优化）
3. 增强报告分析功能（展示新指标）
4. 优化策略配置界面（支持改进后的参数）

## 二、优化内容

### 2.1 策略配置优化

**文件**: `admin/src/components/pvfrs/StrategyConfiguration.vue`

**优化点1：增加乖离率动态调整配置**

- 添加"动态乖离率调整"开关
- 配置市场波动率阈值（高/中/低波动）
- 配置价格区间调整规则（低价股/高价股）
- 配置bias历史分布分位数范围

**优化点2：增加价格维度增强配置**

- 价格趋势持续性验证开关
- 价格波动率阈值配置
- 幅度系数范围调整（1%-30%）

**优化点3：增加频率维度增强配置**

- 上涨天数要求（Z >= 10, Z > F+3）
- 上涨集中度分析开关
- 虚假繁荣检测增强开关

**优化点4：增加成交量维度增强配置**

- 连续放量天数要求（默认3天）
- 成交量趋势持续性验证开关
- 量价相关系数阈值（默认0.5）

**优化点5：增加信号质量分级配置**

- 高质量/中等质量/低质量信号阈值
- 信号强度权重配置（包括bias权重10%）

### 2.2 回测任务管理优化

**文件**: `admin/src/components/pvfrs/BacktestManagement.vue`

**优化点1：增强参数优化模式**

- 支持乖离率参数网格搜索（buy_bias_min, sell_bias_max）
- 支持多参数组合优化
- 显示优化进度和最佳参数

**优化点2：增加策略对比功能**

- 支持多个策略配置同时回测
- 对比不同参数组合的效果
- 展示参数敏感性分析

**优化点3：增强任务详情展示**

- 显示使用的策略参数（包括动态调整后的值）
- 展示信号质量分布
- 显示各维度得分

### 2.3 报告分析优化

**文件**: `admin/src/components/pvfrs/ReportAnalysis.vue`, `ReportDetail.vue`

**优化点1：增加乖离率相关指标**

- bias质量得分
- bias趋势分析（5天/10天趋势）
- bias与价格位置/成交量的协同指标

**优化点2：增加维度分析展示**

- 价格维度得分（包括趋势持续性、波动率）
- 频率维度得分（包括上涨集中度、虚假繁荣检测）
- 成交量维度得分（包括连续放量、趋势持续性）
- 各维度均衡性指标

**优化点3：增强信号质量分析**

- 信号质量分级统计（高质量/中等质量/低质量）
- 信号强度分布图
- 信号过滤原因统计

**优化点4：增加策略改进效果对比**

- 对比改进前后的回测结果
- 展示改进带来的收益提升
- 参数优化建议

### 2.4 后端API优化

**文件**: `backend_api/admin/pvfrs_admin_routes.py`, `backend_core/strategies/pvfrs/admin_interface_enhanced.py`

**优化点1：支持动态参数配置**

- 策略配置API支持动态调整参数
- 回测时应用动态参数（根据市场环境、股票特性）

**优化点2：增强报告数据**

- 报告数据包含新指标（bias得分、维度得分等）
- 支持信号质量分级数据
- 支持维度均衡性数据

**优化点3：参数优化API**

- 支持参数网格搜索
- 支持多目标优化（收益、夏普、回撤）
- 返回最佳参数组合

## 三、实施步骤

### 阶段1：策略配置优化（高优先级）

1. 更新StrategyConfiguration.vue，添加新参数配置项
2. 更新后端配置API，支持新参数保存和加载
3. 添加参数验证逻辑

### 阶段2：回测任务管理优化（高优先级）

1. 增强BacktestManagement.vue，支持参数优化模式
2. 更新后端回测API，支持参数网格搜索
3. 优化任务详情展示

### 阶段3：报告分析优化（中优先级）

1. 更新ReportDetail.vue，展示新指标
2. 更新ReportAnalysis.vue，增加对比分析功能
3. 更新后端报告生成逻辑，包含新指标

### 阶段4：后端API优化（中优先级）

1. 更新admin_interface_enhanced.py，支持动态参数
2. 更新pvfrs_admin_routes.py，添加新API端点
3. 优化数据序列化，包含新字段

## 四、预期效果

1. **配置更灵活**：支持动态参数调整，适应不同市场环境
2. **回测更强大**：支持参数优化，找到最佳参数组合
3. **分析更深入**：展示更多维度指标，帮助理解策略表现
4. **使用更便捷**：界面优化，操作更直观

## 五、技术要点

1. **前端**：使用Vue 3 + Element Plus，保持现有代码风格
2. **后端**：保持现有API结构，扩展功能而非重构
3. **数据**：确保向后兼容，新字段可选
4. **性能**：参数优化可能耗时，需要异步处理和进度反馈