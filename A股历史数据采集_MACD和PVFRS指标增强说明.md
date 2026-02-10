# A股历史数据采集页面 - MACD和PVFRS指标生成功能增强

## 修改概述

本次修改为"管理端-数据采集-A股历史数据采集-历史数据采集-akshare"页面增加了以下功能:
1. **新增MACD指标数据生成选项**
2. **修复PVFRS指标数据生成逻辑**

这两个指标的生成逻辑与"管理端-指标管理"中的逻辑保持一致。

## 修改文件清单

### 1. 后端API文件
**文件**: `backend_api/stock/data_collection_api.py`

#### 修改内容:

**a) 添加MACD指标生成方法 (新增)**
- 位置: 第590-639行
- 方法名: `_generate_macd_indicators`
- 功能: 使用`MACDCalculator`计算MACD指标(DIF、DEA、MACD、EMA12、EMA26)并保存到数据库
- 逻辑与`backend_api/admin/indicators.py`中的MACD生成逻辑一致

**b) 完善PVFRS指标生成方法 (修改)**
- 位置: 第712-806行  
- 方法名: `_generate_pvfrs_indicators`
- 原状态: 仅为占位符实现
- 新状态: 完整实现,使用`MeanFrequencyResonanceCalculator`计算所有PVFRS指标并保存
- 包含的指标字段:
  - macro_displacement_delta (宏观位移Δ)
  - amplitude (幅度)
  - ratio_d20, ratio_d1 (比率)
  - instant_deviation (即时偏离度)
  - rising_days_z (上涨天数Z)
  - falling_days_f (下跌天数F)
  - efficiency_m20_minus_m (进出效率)
  - ma20_d (20日均价d)
  - mavol20_m (20日均量m)
  - bias (乖离率)

**c) 在指标生成调度中添加MACD (修改)**
- 位置: 第452-454行
- 在`_generate_indicators`方法中添加MACD指标的条件判断和调用

### 2. 前端页面文件
**文件**: `admin/datacollect.html`

#### 修改内容:

**a) 添加指标选择UI (新增)**
- 位置: 第240-301行
- 新增一个"指标数据生成(可选)"区域
- 包含7个复选框:
  - MA (移动平均线)
  - MAVOL (成交量均线)
  - **MACD指标** ⭐ 新增
  - KDJ指标
  - RSI指标
  - BOLL指标
  - **PVFRS指标** ⭐ 已修复
- 提示文字: "勾选后将在采集历史数据的同时生成相应的技术指标数据"

**b) 修改Vue数据模型 (修改)**
- 位置: 第364-387行
- 在`form`对象中添加`indicators`子对象
- 包含所有7个指标的布尔值状态

**c) 修改数据提交逻辑 (修改)**
- 位置: 第416-425行
- 在`startCollection`方法中添加指标收集逻辑
- 将选中的指标以数组形式添加到API请求的`indicators`字段

**d) 修改表单重置逻辑 (修改)**
- 位置: 第505-522行
- 在`resetForm`方法中添加indicators对象的重置

## 技术实现细节

### MACD指标生成逻辑
```python
# 使用MACDCalculator批量计算
macd_calc = MACDCalculator()
macd_data = macd_calc.calculate_macd_batch(df['close'].tolist())

# 保存到macd_indicators表
# 字段: code, date, market_type, dif, dea, macd, ema12, ema26
```

### PVFRS指标生成逻辑
```python
# 使用MeanFrequencyResonanceCalculator计算
calculator = MeanFrequencyResonanceCalculator()
pvfrs_df = calculator.calculate_for_dataframe(orm_rows)

# 保存到mean_frequency_resonance_indicators表
# 包含所有PVFRS相关字段
```

### 前端指标收集逻辑
```javascript
// 收集选中的指标
const selectedIndicators = [];
for (const [key, value] of Object.entries(this.form.indicators)) {
    if (value) {
        selectedIndicators.push(key);
    }
}
if (selectedIndicators.length > 0) {
    requestData.indicators = selectedIndicators;
}
```

## 使用说明

1. 打开"管理端-数据采集"页面
2. 设置日期范围和股票选择
3. 在"指标数据生成(可选)"区域勾选需要生成的指标:
   - **MACD指标** - 新增功能
   - **PVFRS指标** - 已修复,现在可以正常生成
4. 点击"开始采集"按钮
5. 系统将在采集历史数据的同时生成选中的技术指标数据

## 数据库表

### MACD指标表
- 表名: `macd_indicators`
- 主键: (code, date, market_type)
- 字段: dif, dea, macd, ema12, ema26

### PVFRS指标表
- 表名: `mean_frequency_resonance_indicators`
- 主键: (code, date, market_type)
- 字段: macro_displacement_delta, amplitude, ratio_d20, ratio_d1, instant_deviation, rising_days_z, falling_days_f, efficiency_m20_minus_m, ma20_d, mavol20_m, bias

## 注意事项

1. **PVFRS指标需要至少21天历史数据**才能计算(20天窗口+1天用于计算涨跌)
2. **MACD指标需要至少26天历史数据**才能计算(慢线EMA26周期)
3. 指标生成是可选的,不勾选则只采集历史行情数据
4. 所有指标的生成逻辑与"指标管理"模块保持一致
5. 使用ON CONFLICT DO UPDATE确保数据可以重复生成和更新

## 测试建议

1. 测试单只股票采集+MACD指标生成
2. 测试单只股票采集+PVFRS指标生成
3. 测试多只股票采集+多个指标同时生成
4. 验证生成的指标数据与"指标管理"模块生成的数据一致
5. 检查数据库中的指标数据是否正确保存
