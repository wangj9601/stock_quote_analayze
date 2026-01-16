# 需求文档 - 一阳穿三线选股策略

## 简介

本文档定义了"一阳穿三线"（又称"出水芙蓉"）选股策略的功能需求。该策略用于识别股价在均线系统粘合或走平过程中,出现一根带量长阳线并一次性向上突破三根移动平均线的技术形态。

## 术语表

- **System**: 股票分析系统
- **Strategy_Engine**: 策略执行引擎
- **Stock_Screener**: 选股筛选器
- **MA**: 移动平均线(Moving Average)
- **Long_Yang_Candle**: 长阳线,实体较长的阳线K线
- **Volume**: 成交量
- **Turnover_Rate**: 换手率
- **BIAS**: 乖离率,股价与均线的偏离程度
- **ST_Stock**: 特别处理股票,需要排除的股票类型

## 需求

### 需求 1: 股票范围筛选

**用户故事:** 作为交易者,我希望策略只在符合条件的股票范围内执行,以避免高风险股票。

#### 验收标准

1. THE System SHALL 筛选全部A股市场的股票
2. WHEN 执行策略时, THE System SHALL 排除所有ST股票(包括*ST和S*ST)
3. THE System SHALL 仅处理最近20个交易日的数据

### 需求 2: 移动平均线计算

**用户故事:** 作为交易者,我希望系统能够准确计算多条移动平均线,以识别均线粘合状态。

#### 验收标准

1. THE System SHALL 计算MA5(5日移动平均线)
2. THE System SHALL 计算MA10(10日移动平均线)
3. THE System SHALL 计算MA20(20日移动平均线)
4. THE System SHALL 计算MA30(30日移动平均线)
5. THE System SHALL 计算MA60(60日移动平均线)
6. THE System SHALL 计算MA120(120日移动平均线,季线)
7. WHEN 计算移动平均线时, THE System SHALL 使用收盘价作为计算基础
8. WHEN 数据不足时, THE System SHALL 跳过该股票并记录日志

### 需求 3: 均线粘合状态识别

**用户故事:** 作为交易者,我希望系统能够识别均线粘合或走平状态,这代表筹码分布集中。

#### 验收标准

1. THE System SHALL 从六条均线(MA5, MA10, MA20, MA30, MA60, MA120)中选择任意三条进行粘合状态判断
2. WHEN 选定的三条均线的最大值与最小值之差小于等于最小值的5%时, THE System SHALL 判定为均线粘合状态
3. THE System SHALL 计算每条均线的斜率(最近5日的线性回归斜率)
4. WHEN 选定的三条均线的斜率绝对值均小于0.5度时, THE System SHALL 判定为均线走平状态
5. THE System SHALL 将均线粘合或走平状态作为信号触发的可选加分条件

### 需求 4: 长阳线识别

**用户故事:** 作为交易者,我希望系统能够识别符合标准的长阳线,确保突破的有效性。

#### 验收标准

1. WHEN K线的收盘价大于开盘价时, THE System SHALL 判定为阳线
2. THE System SHALL 计算阳线实体长度为(收盘价 - 开盘价)
3. THE System SHALL 计算K线总长度为(最高价 - 最低价)
4. WHEN 阳线实体长度占K线总长度的比例大于等于70%时, THE System SHALL 判定为长阳线
5. WHEN 阳线涨幅(收盘价相对开盘价的涨幅)大于等于3%时, THE System SHALL 判定为有效长阳线

### 需求 5: 一阳穿三线形态识别

**用户故事:** 作为交易者,我希望系统能够准确识别一阳穿三线形态,即一根阳线突破任意三条均线。

#### 验收标准

1. THE System SHALL 检查长阳线是否穿越六条均线(MA5, MA10, MA20, MA30, MA60, MA120)中的任意三条或更多
2. WHEN 长阳线的收盘价大于至少三条均线时, THE System SHALL 判定为突破三条均线
3. WHEN 长阳线的开盘价小于这三条均线中的至少两条时, THE System SHALL 判定为有效穿越
4. THE System SHALL 要求长阳线的最低价低于这三条均线中的至少一条
5. THE System SHALL 记录具体穿越了哪三条(或更多)均线
6. THE System SHALL 将同时满足长阳线和突破至少三线的情况判定为"一阳穿三线"形态
7. WHEN 穿越的均线数量越多时, THE System SHALL 给予更高的信号质量评分

### 需求 6: 成交量放大验证

**用户故事:** 作为交易者,我希望系统验证突破时的成交量是否放大,以确认突破的真实性。

#### 验收标准

1. THE System SHALL 计算前期平均成交量(突破前5个交易日的平均成交量)
2. WHEN 突破当天的成交量大于等于前期平均成交量的2倍时, THE System SHALL 判定为放量突破
3. THE System SHALL 计算突破当天的换手率
4. WHEN 换手率在3%到10%之间时, THE System SHALL 判定为理想换手率范围
5. IF 换手率小于3%, THEN THE System SHALL 标记为"动能不足"警告
6. IF 换手率大于10%, THEN THE System SHALL 标记为"可能存在对倒"警告

### 需求 7: 位置判别

**用户故事:** 作为交易者,我希望系统能够判断突破发生的位置,以区分低位启动和高位诱多。

#### 验收标准

1. THE System SHALL 计算股价相对60日最高价的回撤幅度
2. WHEN 当前股价距离60日最高价的回撤幅度大于等于30%时, THE System SHALL 判定为低位启动
3. WHEN 当前股价距离60日最高价的回撤幅度小于10%时, THE System SHALL 判定为高位突破
4. THE System SHALL 在结果中标注位置类型(低位/中位/高位)
5. THE System SHALL 对高位突破给予"警惕诱多"的风险提示

### 需求 8: 乖离率计算

**用户故事:** 作为交易者,我希望系统计算股价与均线的乖离率,以评估回调风险。

#### 验收标准

1. THE System SHALL 计算股价相对MA5的乖离率: BIAS5 = (收盘价 - MA5) / MA5 × 100%
2. THE System SHALL 计算股价相对MA10的乖离率: BIAS10 = (收盘价 - MA10) / MA10 × 100%
3. THE System SHALL 计算股价相对MA30的乖离率: BIAS30 = (收盘价 - MA30) / MA30 × 100%
4. WHEN BIAS30大于10%时, THE System SHALL 标记为"乖离过大,注意回调风险"
5. THE System SHALL 在筛选结果中显示所有乖离率数值

### 需求 9: 均线拐头确认

**用户故事:** 作为交易者,我希望系统确认短中期均线是否向上拐头,以验证趋势反转。

#### 验收标准

1. THE System SHALL 计算MA5和MA10的斜率(最近3日的线性回归斜率)
2. WHEN MA5和MA10的斜率均大于0时, THE System SHALL 判定为均线向上拐头
3. THE System SHALL 将均线拐头作为信号确认的加分项

### 需求 10: 筛选结果输出

**用户故事:** 作为交易者,我希望系统能够输出详细的筛选结果,包括关键指标和风险提示。

#### 验收标准

1. THE System SHALL 输出符合条件的股票代码和股票名称
2. THE System SHALL 输出形态发生日期
3. THE System SHALL 输出关键指标:收盘价、MA5、MA10、MA20、MA30、MA60、MA120、成交量倍数、换手率、BIAS5、BIAS10、BIAS30
4. THE System SHALL 输出穿越的具体均线组合(例如:"MA5+MA10+MA30")
5. THE System SHALL 输出位置类型(低位/中位/高位)
6. THE System SHALL 输出风险提示(如有)
7. THE System SHALL 按照信号质量评分降序排列结果

### 需求 11: 数据持久化

**用户故事:** 作为系统管理员,我希望策略结果能够保存到数据库,以便历史回溯和统计分析。

#### 验收标准

1. THE System SHALL 将筛选结果保存到数据库表中
2. THE System SHALL 记录策略名称、股票代码、信号日期、关键指标和风险提示
3. WHEN 保存失败时, THE System SHALL 记录错误日志并继续处理其他股票
4. THE System SHALL 避免重复保存同一股票同一日期的信号

### 需求 12: API接口提供

**用户故事:** 作为前端开发者,我希望有RESTful API接口可以获取一阳穿三线策略的筛选结果。

#### 验收标准

1. THE System SHALL 提供GET接口 `/api/screening/one-yang-three-lines` 获取筛选结果
2. WHEN 请求接口时, THE System SHALL 支持分页参数(page, page_size)
3. WHEN 请求接口时, THE System SHALL 支持日期范围筛选参数(start_date, end_date)
4. THE System SHALL 返回JSON格式的结果,包含股票列表和总数
5. WHEN 发生错误时, THE System SHALL 返回适当的HTTP状态码和错误信息

### 需求 13: 前端展示集成

**用户故事:** 作为用户,我希望在选股频道页面能够看到"一阳穿三线"策略的选项卡和结果。

#### 验收标准

1. THE System SHALL 在选股策略页面添加"一阳穿三线"选项卡
2. WHEN 用户点击"刷新筛选"按钮时, THE System SHALL 调用后端API获取最新结果
3. THE System SHALL 以表格形式展示筛选结果,包含所有关键指标
4. THE System SHALL 对不同位置类型使用不同的颜色标识(低位-绿色,中位-黄色,高位-红色)
5. THE System SHALL 显示风险提示信息(如有)
6. WHEN 用户点击股票代码时, THE System SHALL 跳转到该股票的详情页面
