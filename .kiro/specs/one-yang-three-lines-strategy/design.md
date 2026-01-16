# 设计文档 - 一阳穿三线选股策略

## 概述

本文档描述"一阳穿三线"（又称"出水芙蓉"）选股策略的技术设计。该策略用于识别股价在均线系统粘合或走平过程中,出现一根带量长阳线并一次性向上突破至少三根移动平均线的技术形态。

策略核心思想:
- 均线系统粘合/走平代表筹码分布集中,持仓成本趋于一致
- 长阳线带量突破代表多方力量强势介入
- 穿越多条均线代表突破的有效性和力度
- 位置判别和乖离率用于风险控制

## 架构

### 系统分层

```
┌─────────────────────────────────────────┐
│         前端展示层 (Frontend)            │
│   - 选股策略页面                         │
│   - 一阳穿三线选项卡                     │
│   - 结果表格展示                         │
└─────────────────────────────────────────┘
                    ↓ HTTP/REST
┌─────────────────────────────────────────┐
│         API路由层 (FastAPI)              │
│   - stock_screening_routes.py           │
│   - GET /api/screening/one-yang-three-  │
│     lines                                │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         策略执行层 (Strategy)            │
│   - OneYangThreeLinesStrategy类          │
│   - 形态识别算法                         │
│   - 信号质量评分                         │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         数据访问层 (Database)            │
│   - historical_quotes表                  │
│   - stock_basic_info表                   │
│   - SQLAlchemy ORM                       │
└─────────────────────────────────────────┘
```

### 模块划分

1. **OneYangThreeLinesStrategy类** (backend_api/stock/one_yang_three_lines_strategy.py)
   - 策略主函数: screening_one_yang_three_lines_strategy()
   - 均线计算: calculate_moving_averages()
   - 长阳线识别: check_long_yang_candle()
   - 穿线识别: check_cross_three_lines()
   - 成交量验证: check_volume_increase()
   - 位置判别: check_position_type()
   - 乖离率计算: calculate_bias()
   - 信号评分: calculate_signal_score()

2. **API路由** (backend_api/stock/stock_screening_routes.py)
   - 新增路由: GET /api/screening/one-yang-three-lines
   - 参数验证和错误处理
   - 返回JSON格式结果

3. **前端组件** (frontend/src/pages/Screening.tsx)
   - 新增"一阳穿三线"选项卡
   - 结果表格展示
   - 刷新筛选按钮

## 组件和接口

### 核心类: OneYangThreeLinesStrategy

```python
class OneYangThreeLinesStrategy:
    """一阳穿三线选股策略类"""

    
    @staticmethod
    def calculate_moving_averages(
        historical_data: List[Dict], 
        current_index: int = 0
    ) -> Dict[str, float]:
        """
        计算多条移动平均线
        
        Args:
            historical_data: 历史数据列表(倒序,最新在前)
            current_index: 当前日期索引
            
        Returns:
            均线字典: {'ma5': float, 'ma10': float, ...}
        """
        pass
    
    @staticmethod
    def check_long_yang_candle(candle_data: Dict) -> Tuple[bool, Dict]:
        """
        检查是否为长阳线
        
        条件:
        1. 收盘价 > 开盘价 (阳线)
        2. 实体长度占K线总长度 >= 70%
        3. 涨幅 >= 3%
        
        Args:
            candle_data: K线数据
            
        Returns:
            (是否为长阳线, 阳线信息)
        """
        pass
    
    @staticmethod
    def check_cross_three_lines(
        candle_data: Dict,
        ma_values: Dict[str, float]
    ) -> Tuple[bool, List[str], int]:
        """
        检查是否穿越至少三条均线
        
        条件:
        1. 收盘价 > 至少三条均线
        2. 开盘价 < 这三条均线中的至少两条
        3. 最低价 < 这三条均线中的至少一条
        
        Args:
            candle_data: K线数据
            ma_values: 均线值字典
            
        Returns:
            (是否穿越, 穿越的均线列表, 穿越数量)
        """
        pass
    
    @staticmethod
    def check_volume_increase(
        historical_data: List[Dict],
        current_index: int,
        days_before: int = 5
    ) -> Tuple[bool, float, float]:
        """
        检查成交量是否放大
        
        条件:
        1. 当日成交量 >= 前期平均成交量的2倍
        2. 换手率在3%-10%之间为理想
        
        Args:
            historical_data: 历史数据列表
            current_index: 当前日期索引
            days_before: 计算平均成交量的天数
            
        Returns:
            (是否放量, 成交量倍数, 换手率)
        """
        pass
    
    @staticmethod
    def check_position_type(
        historical_data: List[Dict],
        current_index: int
    ) -> Tuple[str, float]:
        """
        判断突破位置类型
        
        分类:
        - 低位: 距离60日最高价回撤 >= 30%
        - 中位: 回撤在10%-30%之间
        - 高位: 回撤 < 10%
        
        Args:
            historical_data: 历史数据列表
            current_index: 当前日期索引
            
        Returns:
            (位置类型, 回撤幅度)
        """
        pass
    
    @staticmethod
    def calculate_bias(
        current_price: float,
        ma_values: Dict[str, float]
    ) -> Dict[str, float]:
        """
        计算乖离率
        
        公式: BIAS = (收盘价 - MA) / MA × 100%
        
        Args:
            current_price: 当前价格
            ma_values: 均线值字典
            
        Returns:
            乖离率字典: {'bias5': float, 'bias10': float, ...}
        """
        pass
    
    @staticmethod
    def calculate_signal_score(
        crossed_lines_count: int,
        volume_ratio: float,
        turnover_rate: float,
        position_type: str,
        bias30: float
    ) -> int:
        """
        计算信号质量评分(0-100分)
        
        评分规则:
        - 穿越均线数量: 3条=20分, 4条=30分, 5条=40分, 6条=50分
        - 成交量倍数: >=2倍=20分, >=3倍=25分
        - 换手率: 3%-10%=15分, 其他=5分
        - 位置类型: 低位=15分, 中位=10分, 高位=0分
        - 乖离率: <5%=10分, 5%-10%=5分, >10%=0分
        
        Args:
            crossed_lines_count: 穿越的均线数量
            volume_ratio: 成交量倍数
            turnover_rate: 换手率
            position_type: 位置类型
            bias30: 30日乖离率
            
        Returns:
            信号质量评分
        """
        pass
    
    @staticmethod
    def screening_one_yang_three_lines_strategy(
        db: Session
    ) -> List[Dict]:
        """
        一阳穿三线选股策略主函数
        
        执行流程:
        1. 获取A股股票列表(排除ST)
        2. 获取最近20个交易日的历史数据
        3. 计算6条移动平均线(MA5/10/20/30/60/120)
        4. 检查最新K线是否为长阳线
        5. 检查是否穿越至少三条均线
        6. 验证成交量放大
        7. 判断位置类型
        8. 计算乖离率
        9. 计算信号质量评分
        10. 返回符合条件的股票列表
        
        Args:
            db: 数据库会话
            
        Returns:
            符合条件的股票列表
        """
        pass
```

### API接口

```python
@router.get("/one-yang-three-lines")
async def get_one_yang_three_lines_strategy(
    db: Session = Depends(get_db)
):
    """
    一阳穿三线选股策略API
    
    Returns:
        {
            "success": true,
            "data": [
                {
                    "code": "000001",
                    "name": "平安银行",
                    "signal_date": "2025-01-16",
                    "current_price": 12.50,
                    "ma5": 12.30,
                    "ma10": 12.10,
                    "ma20": 11.90,
                    "ma30": 11.70,
                    "ma60": 11.50,
                    "ma120": 11.30,
                    "crossed_lines": "MA5+MA10+MA20",
                    "crossed_count": 3,
                    "volume_ratio": 2.5,
                    "turnover_rate": 4.2,
                    "position_type": "低位",
                    "retracement": 35.5,
                    "bias5": 1.6,
                    "bias10": 3.3,
                    "bias30": 6.8,
                    "signal_score": 85,
                    "risk_warnings": []
                }
            ],
            "total": 1,
            "search_date": "2025-01-16",
            "strategy_name": "一阳穿三线"
        }
    """
    pass
```

## 数据模型

### 输入数据

从`historical_quotes`表获取:
```sql
SELECT code, name, date, open, close, high, low, 
       change_percent, volume, amount, turnover_rate
FROM historical_quotes 
WHERE code = :code 
AND date >= :start_date 
AND date <= :end_date
ORDER BY date DESC
```

### 输出数据结构

```python
{
    "code": str,              # 股票代码
    "name": str,              # 股票名称
    "signal_date": str,       # 信号日期
    "current_price": float,   # 当前价格
    "ma5": float,             # 5日均线
    "ma10": float,            # 10日均线
    "ma20": float,            # 20日均线
    "ma30": float,            # 30日均线
    "ma60": float,            # 60日均线
    "ma120": float,           # 120日均线
    "crossed_lines": str,     # 穿越的均线组合
    "crossed_count": int,     # 穿越数量
    "volume_ratio": float,    # 成交量倍数
    "turnover_rate": float,   # 换手率
    "position_type": str,     # 位置类型
    "retracement": float,     # 回撤幅度
    "bias5": float,           # 5日乖离率
    "bias10": float,          # 10日乖离率
    "bias30": float,          # 30日乖离率
    "signal_score": int,      # 信号质量评分
    "risk_warnings": List[str] # 风险提示
}
```

## 正确性属性

*属性是一个特征或行为,应该在系统的所有有效执行中保持为真——本质上是关于系统应该做什么的形式化陈述。属性作为人类可读规范和机器可验证正确性保证之间的桥梁。*


### 属性1: 移动平均线计算正确性
*对于任意*股票的历史价格数据和任意周期N(5,10,20,30,60,120),计算的N日移动平均线应该等于最近N个交易日收盘价的算术平均值
**验证: 需求 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7**

### 属性2: ST股票排除
*对于任意*股票列表,筛选结果中不应包含任何名称包含"ST"、"*ST"或"S*ST"的股票
**验证: 需求 1.2**

### 属性3: 长阳线识别
*对于任意*K线数据,当且仅当满足以下条件时应被识别为长阳线: (1)收盘价>开盘价, (2)实体长度/(最高价-最低价)>=0.7, (3)(收盘价-开盘价)/开盘价>=0.03
**验证: 需求 4.1, 4.2, 4.3, 4.4, 4.5**

### 属性4: 穿线数量单调性
*对于任意*两个信号,如果信号A穿越的均线数量大于信号B,则信号A的质量评分应该大于信号B的评分(其他条件相同时)
**验证: 需求 5.7**

### 属性5: 穿越有效性
*对于任意*被判定为"一阳穿三线"的K线,必须同时满足: (1)收盘价大于至少3条均线, (2)开盘价小于这些均线中的至少2条, (3)最低价低于这些均线中的至少1条
**验证: 需求 5.1, 5.2, 5.3, 5.4, 5.6**

### 属性6: 放量突破判断
*对于任意*交易日,当且仅当该日成交量>=前5日平均成交量的2倍时,应被判定为放量突破
**验证: 需求 6.1, 6.2**

### 属性7: 换手率警告一致性
*对于任意*交易日,当换手率<3%时应包含"动能不足"警告,当换手率>10%时应包含"可能存在对倒"警告,当换手率在3%-10%之间时不应包含这两个警告
**验证: 需求 6.4, 6.5, 6.6**

### 属性8: 位置类型判断
*对于任意*股票,当回撤幅度>=30%时应判定为"低位",当回撤幅度<10%时应判定为"高位",当回撤幅度在10%-30%之间时应判定为"中位"
**验证: 需求 7.2, 7.3, 7.4**

### 属性9: 乖离率计算正确性
*对于任意*股票价格和均线值,乖离率BIAS应该等于(价格-均线)/均线×100%
**验证: 需求 8.1, 8.2, 8.3**

### 属性10: 高乖离率风险提示
*对于任意*信号,当BIAS30>10%时,风险提示列表中应包含"乖离过大,注意回调风险"
**验证: 需求 8.4**

### 属性11: 结果排序单调性
*对于任意*筛选结果列表,列表中任意相邻两个元素,前一个元素的信号质量评分应该大于等于后一个元素的评分
**验证: 需求 10.7**

### 属性12: 输出完整性
*对于任意*符合条件的股票,输出结果应包含所有必需字段:代码、名称、日期、价格、6条均线值、穿越均线组合、成交量倍数、换手率、3个乖离率、位置类型、评分
**验证: 需求 10.1, 10.2, 10.3, 10.4, 10.5, 10.6**

### 属性13: 数据去重
*对于任意*股票和日期组合,在数据库中最多只应存在一条该股票该日期的信号记录
**验证: 需求 11.4**

### 属性14: API响应格式
*对于任意*成功的API请求,响应应该是有效的JSON格式,包含success字段(true)、data数组、total数字和strategy_name字符串
**验证: 需求 12.4**

## 错误处理

### 数据异常处理

1. **数据不足**: 当股票历史数据少于120个交易日时,跳过该股票并记录警告日志
2. **数据缺失**: 当关键字段(open, close, high, low, volume)为空或0时,跳过该K线
3. **计算异常**: 当除数为0或计算结果为NaN时,使用默认值0并记录错误日志

### API错误处理

1. **数据库连接失败**: 返回HTTP 500,错误信息"数据库连接失败"
2. **查询超时**: 返回HTTP 504,错误信息"查询超时,请稍后重试"
3. **参数验证失败**: 返回HTTP 400,错误信息说明具体参数错误

### 日志记录

```python
logger.info(f"开始执行一阳穿三线选股策略")
logger.info(f"找到 {len(stocks)} 只A股股票")
logger.info(f"处理进度: {idx}/{len(stocks)}")
logger.info(f"✓ 找到符合条件的股票: {code} {name}")
logger.warning(f"股票 {code} 数据不足,跳过")
logger.error(f"✗ 处理股票 {code} 时出错: {str(e)}")
logger.info(f"策略执行完成,找到 {len(results)} 只符合条件的股票")
```

## 测试策略

### 单元测试

使用pytest框架编写单元测试,测试文件: `test/test_one_yang_three_lines_strategy.py`

测试用例:
1. **test_calculate_moving_averages**: 测试均线计算的正确性
2. **test_check_long_yang_candle**: 测试长阳线识别
3. **test_check_cross_three_lines**: 测试穿线识别
4. **test_check_volume_increase**: 测试成交量放大判断
5. **test_check_position_type**: 测试位置类型判断
6. **test_calculate_bias**: 测试乖离率计算
7. **test_calculate_signal_score**: 测试信号评分
8. **test_st_stock_exclusion**: 测试ST股票排除
9. **test_data_insufficient**: 测试数据不足处理
10. **test_api_response_format**: 测试API响应格式

### 属性测试

使用hypothesis框架编写属性测试,每个测试运行100次以上

测试用例:
1. **test_property_ma_calculation**: 属性1 - 均线计算正确性
2. **test_property_st_exclusion**: 属性2 - ST股票排除
3. **test_property_long_yang_identification**: 属性3 - 长阳线识别
4. **test_property_score_monotonicity**: 属性4 - 穿线数量单调性
5. **test_property_cross_validity**: 属性5 - 穿越有效性
6. **test_property_volume_increase**: 属性6 - 放量突破判断
7. **test_property_turnover_warnings**: 属性7 - 换手率警告一致性
8. **test_property_position_type**: 属性8 - 位置类型判断
9. **test_property_bias_calculation**: 属性9 - 乖离率计算正确性
10. **test_property_bias_warning**: 属性10 - 高乖离率风险提示
11. **test_property_result_sorting**: 属性11 - 结果排序单调性
12. **test_property_output_completeness**: 属性12 - 输出完整性
13. **test_property_data_deduplication**: 属性13 - 数据去重
14. **test_property_api_response**: 属性14 - API响应格式

### 测试数据生成

使用hypothesis的策略生成器:
- `st.floats()`: 生成价格、成交量等浮点数
- `st.integers()`: 生成交易日数量、评分等整数
- `st.lists()`: 生成历史数据列表
- `st.text()`: 生成股票代码、名称等字符串
- `st.dates()`: 生成交易日期

### 集成测试

1. **端到端测试**: 从API调用到数据库查询到结果返回的完整流程
2. **性能测试**: 测试处理5000只股票的执行时间(目标<5分钟)
3. **并发测试**: 测试多个用户同时调用API的情况

## 实现注意事项

### 性能优化

1. **批量查询**: 使用SQL的IN子句批量查询多只股票的数据
2. **索引优化**: 在historical_quotes表的(code, date)字段上建立复合索引
3. **缓存策略**: 对于当天已计算过的结果,可以缓存1小时
4. **并行处理**: 使用多进程处理不同股票的计算(可选)

### 代码复用

1. **复用现有工具**: 使用backend_core/utils/ma_calculator.py中的MA计算函数
2. **复用数据模型**: 使用backend_core/models/historical_quotes.py中的数据模型
3. **复用API模式**: 参考low_nine_strategy.py的实现模式

### 数据库设计

可选:创建新表存储策略信号

```sql
CREATE TABLE IF NOT EXISTS one_yang_three_lines_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    signal_date TEXT NOT NULL,
    current_price REAL,
    ma5 REAL,
    ma10 REAL,
    ma20 REAL,
    ma30 REAL,
    ma60 REAL,
    ma120 REAL,
    crossed_lines TEXT,
    crossed_count INTEGER,
    volume_ratio REAL,
    turnover_rate REAL,
    position_type TEXT,
    retracement REAL,
    bias5 REAL,
    bias10 REAL,
    bias30 REAL,
    signal_score INTEGER,
    risk_warnings TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(code, signal_date)
);
```

### 前端实现

参考现有选股策略页面的实现:
- 使用React + TypeScript
- 使用Ant Design的Table组件展示结果
- 使用Tag组件显示位置类型和风险提示
- 使用不同颜色标识不同位置类型

## 部署和监控

### 部署步骤

1. 后端代码部署到backend_api/stock/目录
2. 在stock_screening_routes.py中注册新路由
3. 前端代码部署到frontend/src/pages/目录
4. 运行数据库迁移(如果创建了新表)
5. 重启后端服务和前端服务

### 监控指标

1. **执行时间**: 记录策略执行的总时间
2. **成功率**: 记录成功处理的股票数量占比
3. **错误率**: 记录处理失败的股票数量占比
4. **信号数量**: 记录每天找到的符合条件的股票数量
5. **API调用量**: 记录API的调用次数和响应时间

### 日志监控

使用ELK(Elasticsearch + Logstash + Kibana)或类似工具监控日志:
- 错误日志: 及时发现和处理异常
- 性能日志: 监控执行时间,发现性能瓶颈
- 业务日志: 统计每天的信号数量,分析策略效果
