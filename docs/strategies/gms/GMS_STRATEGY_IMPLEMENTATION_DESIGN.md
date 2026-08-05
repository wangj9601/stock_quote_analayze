# GSM 选股策略详细设计文档

## 目录
- [1. 策略概述](#1-策略概述)
- [2. 核心架构](#2-核心架构)
- [3. 数据模型](#3-数据模型)
- [4. 模块设计](#4-模块设计)
  - [4.6 打分机制与减分引擎](#46-打分机制与减分引擎)
  - [4.7 观察周期振幅 enrich](#47-观察周期振幅-enrich)
- [5. 算法实现](#5-算法实现)
- [6. 配置管理](#6-配置管理)
- [7. API接口](#7-api接口)
- [8. 部署与使用](#8-部署与使用)
- [9. 性能优化](#9-性能优化)
- [10. 扩展性设计](#10-扩展性设计)

---

## 1. 策略概述

### 1.1 策略名称
**GMS (均值引力与动量突变策略)** - 基于均值引力和动量突变的量化选股策略

### 1.2 策略理念
GMS策略基于"均值引力"和"动量突变"两个核心概念：
- **均值引力**：价格长期围绕均值波动的统计特性
- **动量突变**：价格突破均值时的加速运动特征

### 1.3 核心指标
策略基于`mean_frequency_resonance_indicators`表的核心指标：
- `macro_displacement_delta` (Δ)：宏观位移 = d₂₀ - d₁
- `ma20_d` (d)：20日均价
- `instant_deviation`：价格与均线的瞬时偏离
- `rising_days_z` (Z)：连续上涨天数
- `falling_days_f` (F)：连续下跌天数
- `mavol20_m` (m)：20日平均成交量
- `efficiency_m20_minus_m` (m₂₀)：当日成交量相对于均值的增量

### 1.4 交易信号
- **左侧买点**：均值吸附 - 价格极度接近均线且成交量萎缩
- **右侧买点**：动量引爆 - 价格突破均线且成交量放大
- **卖点**：乖离过大 - 价格偏离均线过多

---

## 2. 核心架构

### 2.1 架构层次
```
┌─────────────────────────────────────────┐
│              API Layer                  │
│         (stock_screening_routes)        │
├─────────────────────────────────────────┤
│           Frontend Interface            │
│         (GMSFrontendInterface)          │
├─────────────────────────────────────────┤
│            Strategy Engine              │
│          (GMSStrategyEngine)            │
├─────────────────────────────────────────┤
│    Signal Detector    │  Indicators     │
│   (GMSSignalDetector) │ Calculator      │
│                       │(GMSIndicators)  │
├─────────────────────────────────────────┤
│  Scoring (tiered_dual_max / penalty)    │
│  PenaltyEngine │ observation_range      │
├─────────────────────────────────────────┤
│              Data Loader                │
│           (GMSDataLoader)               │
├─────────────────────────────────────────┤
│         Database Layer                  │
│  mean_frequency_resonance_indicators    │
│  ma_indicators │ historical_quotes*      │
└─────────────────────────────────────────┘
```

### 2.2 数据流
```
Stock Codes → DataLoader → IndicatorsCalculator → SignalDetector → StrategyEngine → FrontendInterface → API
```

### 2.3 核心组件关系
```python
# 组件依赖关系
GMSDataLoader → GMSIndicatorsCalculator → GMSSignalDetector → GMSStrategyEngine
GMSConfigManager → [所有组件]
GMSFrontendInterface → GMSStrategyEngine
```

---

## 3. 数据模型

### 3.1 核心数据结构

#### GMSIndicators
```python
@dataclass
class GMSIndicators:
    # 基础字段
    code: str                    # 股票代码
    date: str                    # 日期
    market_type: str             # 市场类型 (CN/HK)
    
    # 原始指标
    delta: float                 # 宏观位移 Δ = d₂₀ - d₁
    d: float                     # 20日均价
    ratio_d20: Optional[float]   # 偏离率 Δ/d₂₀
    ratio_d1: Optional[float]    # 突变率 Δ/d₁
    instant_deviation: float     # d₂₀ - d (价格vs均线)
    rising_days: int             # Z 上涨天数
    falling_days: int            # F 下跌天数
    avg_volume_20d: float        # m 20日平均成交量
    current_volume: float        # m₂₀ 当日成交量
    
    # 衍生指标
    ratio_d: Optional[float]     # Δ/d 相对位移
    volume_ratio: Optional[float]# m₂₀/m 量比
    fz_ratio: Optional[float]    # F/Z 数方比
    
    # 评分系统
    score_accumulation: float    # 蓄势评分 0-30
    score_balance: float         # 平衡评分 0-40
    score_momentum: float        # 动量评分 0-30
    score_total: float           # 总分 0-100
    
    # 交易信号
    left_buy_signal: bool        # 左侧买点
    right_buy_signal: bool       # 右侧买点
    sell_signal: bool            # 卖点
```

#### GMSSignal
```python
@dataclass
class GMSSignal:
    symbol: str                  # 股票代码
    date: str                    # 日期
    signal_type: GMSSignalType   # 信号类型
    price: float                 # 价格
    strength: float              # 信号强度 0-1
    reason: str                  # 信号原因
    indicators: Optional[GMSIndicators]   # 关联指标
    conditions_met: Dict[str, bool]       # 满足的条件
```

### 3.2 异常体系
```python
GMSException                    # 基础异常
├── DataInsufficientException   # 数据不足异常
└── CalculationException        # 计算异常
```

---

## 4. 模块设计

### 4.1 配置管理 (GMSConfigManager)

#### 功能职责
- 管理策略参数配置
- 支持JSON配置文件
- 提供默认配置
- 支持配置热更新

#### 配置结构
```json
{
  "observation_period": 20,          // 观察周期
  "ratio_indicators": {
    "use_ratio_d": true,             // 是否使用Δ/d指标
    "use_ratio_d_for_exit": false    // 是否使用Δ/d作为退出条件
  },
  "left_buy": {                      // 左侧买点参数
    "ratio_d20_abs_max": 0.015,      // |Δ/d₂₀| < 1.5%
    "volume_ratio_max": 0.8          // m₂₀ < 0.8m
  },
  "right_buy": {                     // 右侧买点参数
    "volume_ratio_min": 1.5          // m₂₀ > 1.5m
  },
  "scoring": {                       // 评分参数
    "mechanism": "tiered_dual_max",  // 或 tiered_dual_penalty（增强减分版）
    "accumulation_fz_min": 1.5,
    "balance_ratio_max": 0.01,
    "momentum_volume_ratio_min": 1.5,
    "watch_threshold": 60,
    "alert_threshold": 90,
    "ma60_flat_lookback_days": 20,   // MA60 走平回看（增强版 close_below_ma60）
    "ma60_flat_tol": 0.015,
    "penalty_rules": [               // 仅 mechanism=tiered_dual_penalty 时启用
      {
        "id": "close_below_ma60",
        "enabled": true,
        "points": 10,
        "half_when_ma60_flat": true
      },
      {
        "id": "observation_range_amplitude",
        "enabled": true,
        "points": 10,
        "amplitude_threshold_pct": 0.30
      }
    ]
  },
  "exit": {                          // 退出参数
    "trend_break_days": 3,           // 趋势破坏天数
    "overbought_ratio": 0.15         // Δ/d₂₀ > 15% 卖出
  }
}
```

### 4.2 数据加载器 (GMSDataLoader)

#### 功能职责
- 从`mean_frequency_resonance_indicators`表加载基础数据
- 计算衍生指标 (ratio_d, volume_ratio)
- 补全 MA60（`ma_indicators.ma60`）及 MA60 走平字段
- 补全观察周期高低点与区间振幅（行情表）
- 支持批量加载
- 数据清洗和验证

#### enrich 顺序（选股 / 回测加载后）

```
load_indicators
  → _enrich_ma60_missing      # ma60_d 从 ma_indicators 补全
  → _enrich_ma60_flat         # ma60_d_lag / ma60_flat
  → _enrich_observation_range # period_high/low、observation_range_amplitude_pct
```

#### 核心算法
```python
def load_indicators(codes, date, market_type):
    # 1. 查询基础指标数据
    query = db.query(MeanFrequencyResonanceIndicators).filter(
        MeanFrequencyResonanceIndicators.code.in_(codes),
        MeanFrequencyResonanceIndicators.date == date,
        MeanFrequencyResonanceIndicators.market_type == market_type
    )
    
    # 2. 计算衍生指标
    for item in rows:
        # Δ/d 从bias字段获取
        ratio_d = item.bias
        
        # 量比计算: m₂₀ = efficiency_m20_minus_m + mavol20_m
        current_volume = eff_m20_m + mavol20_m
        volume_ratio = current_volume / mavol20_m if mavol20_m > 0 else None
```

### 4.3 指标计算器 (GMSIndicatorsCalculator)

#### 功能职责
- 计算GMS衍生指标
- 实现评分算法
- 数据有效性验证

#### 评分算法
```python
def calculate(self, row):
    # 1. 蓄势评分 (0-30分)
    score_acc = 30.0 if (fz_ratio > accumulation_fz_min) else 0.0
    
    # 2. 平衡评分 (0-40分)  
    score_bal = 40.0 if (abs(ratio_d20) < balance_ratio_max) else 0.0
    
    # 3. 动量评分 (0-30分)
    score_mom = 30.0 if (delta > 0 and volume_ratio > momentum_volume_ratio_min) else 0.0
    
    # 4. 总分
    score_total = score_acc + score_bal + score_mom
```

### 4.4 信号检测器 (GMSSignalDetector)

#### 功能职责
- 检测左侧买点 (均值吸附)
- 检测右侧买点 (动量引爆)  
- 检测卖点 (乖离过大)

#### 信号检测算法

##### 左侧买点检测
```python
def detect_left_buy(self, indicators):
    """
    左侧买点条件：
    1. F > Z 且 d₂₀ < d₁ (delta < 0) - 前置条件
    2. |Δ/d₂₀| < 1.5% - 极度粘合
    3. m₂₀ < 0.8m - 地量洗盘
    """
    return (
        indicators.rising_days > 0 and
        indicators.falling_days > indicators.rising_days and  # F > Z
        indicators.delta < 0 and                              # d20 < d1
        abs(indicators.ratio_d20) < self.ratio_d20_abs_max and
        indicators.volume_ratio < self.volume_ratio_max
    )
```

##### 右侧买点检测
```python
def detect_right_buy(self, indicators):
    """
    右侧买点条件：
    1. d₂₀ > d (instant_deviation > 0) - 突破均线
    2. Δ > 0 - 动量向上
    3. m₂₀ > 1.5m - 放量确认
    """
    return (
        indicators.instant_deviation > 0 and
        indicators.delta > 0 and
        indicators.volume_ratio > self.volume_ratio_min
    )
```

##### 卖点检测
```python
def detect_sell(self, indicators):
    """
    卖点条件：
    Δ/d₂₀ > 15% 或 Δ/d > 15% (可选)
    """
    if self.use_ratio_d_for_exit and indicators.ratio_d:
        return indicators.ratio_d > self.overbought_ratio
    return indicators.ratio_d20 > self.overbought_ratio
```

### 4.5 策略引擎 (GMSStrategyEngine)

#### 功能职责
- 协调各组件工作
- 实现选股逻辑
- 结果排序和过滤

#### 选股流程
```python
def screen(self, codes, date, market, min_score=0, max_results=None):
    results = []
    
    # 1. 按市场分别处理
    markets = ["CN", "HK"] if market == "all" else [market]
    
    for market_type in markets:
        # 2. 加载数据
        rows = self.data_loader.load_indicators(codes, date, market_type)
        
        # 3. 计算指标和评分
        for row in rows:
            indicators = self.calculator.calculate(row)
            if indicators.score_total < min_score:
                continue
                
            # 4. 检测信号
            left_buy = self.detector.detect_left_buy(indicators)
            right_buy = self.detector.detect_right_buy(indicators)
            sell = self.detector.detect_sell(indicators)
            
            # 5. 构建结果
            results.append({
                "symbol": indicators.code,
                "score_total": indicators.score_total,
                "buy_type": "左侧" if left_buy else "右侧" if right_buy else "",
                "left_buy_signal": left_buy,
                "right_buy_signal": right_buy,
                "sell_signal": sell,
                # ... 其他字段
            })
    
    # 6. 排序和截取
    results.sort(key=lambda x: x["score_total"], reverse=True)
    if max_results:
        results = results[:max_results]
    
    return results
```

### 4.6 打分机制与减分引擎

#### 机制注册（`scoring/registry.py`）

| ID | 类 | 综合分 |
|----|-----|--------|
| `tiered_dual_max` | `TieredDualMaxScorer` | max(均值收敛态, 动量溢出态) |
| `tiered_dual_penalty` | `TieredDualPenaltyScorer` | clamp(基础分 − Σ减分, 0, 100) |

共享配置名：`default`（标准版）、`gms_penalty`（减分版）。业务规则与参数说明见 [GMS_STATE_DETECTION_RULES.md §5.4](./GMS_STATE_DETECTION_RULES.md#54-打分机制与减分规则多版本)。

#### PenaltyEngine（`scoring/penalties.py`）

按 `scoring.penalty_rules` 中启用的规则对单行指标依次判定；命中则累加扣分并写入 `penalty_details`。规则类型见 `PENALTY_RULE_TYPES`，管理端通过 `GET /api/admin/gms/penalty-rule-types` 拉取元数据。

| 规则 ID | 判定概要 |
|---------|----------|
| `close_below_ma60` | d₂₀ &lt; ma60_d；MA60 走平时扣分减半 |
| `observation_range_amplitude` | 观察周期内 (高−低)/高 &gt; 阈值（默认 30%，扣 10 分） |
| `poor_structure_rr` | KDE 结构盈亏比 RR=(阻力−价)/(价−支撑)；破位/贴阻力或 RR&lt;min_rr（默认 1.5）扣分；无阻力不扣 |

等级（S/A/全速/分批）仍按**减分前**基础分判定。`risk_tags.py` 对每条命中的减分规则生成 `penalty_{id}` 风险提示。

**结构盈亏比数据时机**：`strategy_engine.screen` 须在 `calculator.calculate` 之前完成 `structure_levels.compute_structure_levels`，并把 `nearest_support` / `nearest_resistance` 写入打分行；`score_detail.structure.rr` 供明细展示。业务细则见 [GMS_STATE_DETECTION_RULES.md §5.4.4](./GMS_STATE_DETECTION_RULES.md#544-减分规则-poor_structure_rr结构盈亏比偏低)。单测：`test/test_gms_structure_rr_penalty.py`。

### 4.7 观察周期振幅 enrich

模块：`observation_range.py`（由 `GMSDataLoader._enrich_observation_range` 调用）。

```python
# 观察窗口 = observation_period 个交易日（含信号日）
period_high = max(high)   # 窗口内
period_low  = min(low)
observation_range_amplitude_pct = (period_high - period_low) / period_high

# 触发：observation_range_amplitude_pct > amplitude_threshold_pct（默认 0.30）
```

行情来源：A 股 `historical_quotes`、港股 `historical_quotes_hk`、ETF `fund_historical_quotes`。与指标表 `amplitude`（\|Δ\|）无关。

单测：`test/test_gms_observation_range.py`；减分集成：`test/test_gms_scoring_mechanism.py`。

### 4.8 前端接口 (GMSFrontendInterface)

#### 功能职责
- 提供API调用入口
- 股票池管理
- 参数配置和验证

#### 股票池获取
```python
def _get_stock_pool(self, date, market):
    """
    股票池来源：
    - CN: stock_basic_info 表 (全部A股)
    - HK: stock_basic_info_hk 表 (全部港股)
    """
    if market == "cn":
        rows = self.db.query(StockBasicInfo.code).all()
        return [str(r[0]).zfill(6) for r in rows]
    elif market == "hk":
        rows = self.db.query(StockBasicInfoHK.code).all()
        return [str(r[0]).strip() for r in rows]
```

---

## 5. 算法实现

### 5.1 核心数学模型

#### 基础指标定义
```
Δ = d₂₀ - d₁                    # 宏观位移
d = ma20_d                      # 20日均价
ratio_d20 = Δ / d₂₀             # 偏离率  
ratio_d1 = Δ / d₁               # 突变率
ratio_d = Δ / d                  # 相对位移
instant_deviation = d₂₀ - d     # 瞬时偏离
volume_ratio = m₂₀ / m           # 量比
fz_ratio = F / Z                 # 数方比
```

#### 评分函数
```
score_accumulation = 30 * I(fz_ratio > 1.5)
score_balance = 40 * I(|ratio_d20| < 0.01)  
score_momentum = 30 * I(Δ > 0 ∧ volume_ratio > 1.5)
score_total = score_accumulation + score_balance + score_momentum
```

其中 I(condition) 是指示函数，条件为真时返回1，否则返回0。

### 5.2 信号检测逻辑

#### 左侧买点 (均值吸附)
```
LEFT_BUY = (F > Z) ∧ (Δ < 0) ∧ (|ratio_d20| < 0.015) ∧ (volume_ratio < 0.8)
```

#### 右侧买点 (动量引爆)  
```
RIGHT_BUY = (instant_deviation > 0) ∧ (Δ > 0) ∧ (volume_ratio > 1.5)
```

#### 卖点 (乖离过大)
```
SELL = ratio_d20 > 0.15 ∨ (use_ratio_d_for_exit ∧ ratio_d > 0.15)
```

### 5.3 风险控制

#### 数据质量检查
- 必要字段非空验证
- 数值合理性检查
- 异常值过滤

#### 参数边界限制
- 评分范围: 0-100
- 信号强度: 0-1
- 比率指标: 合理上下限

---

## 6. 配置管理

### 6.1 配置文件结构
```
backend_core/strategies/gms/
├── gms_config.json          # 默认配置文件
├── config.py                 # 配置管理器
└── __init__.py
```

### 6.2 配置加载策略
1. **默认配置**: 硬编码的基准参数
2. **文件配置**: `gms_config.json` 中的自定义参数
3. **运行时配置**: API调用时传入的临时参数
4. **合并策略**: 深度合并，运行时 > 文件 > 默认

### 6.3 配置验证
```python
def validate_config(self, config):
    """配置参数验证"""
    required_sections = ["left_buy", "right_buy", "scoring", "exit"]
    for section in required_sections:
        if section not in config:
            raise ValueError(f"缺少配置节: {section}")
    
    # 数值范围验证
    if config["scoring"]["watch_threshold"] < 0 or config["scoring"]["watch_threshold"] > 100:
        raise ValueError("watch_threshold必须在0-100之间")
```

---

## 7. API接口

### 7.1 选股接口

#### 端点
```
GET /api/stock/screening/gms-strategy
```

#### 请求参数
```python
date: str = Query(None, description="目标日期 YYYY-MM-DD")
limit: int = Query(None, ge=1, description="最大返回数量")  
min_score: float = Query(0, ge=0, le=100, description="最低总分阈值")
scope: str = Query("all", description="选股范围: all/watchlist")
token: Optional[str] = Depends(oauth2_scheme_optional)
```

#### 响应格式
```json
{
  "success": true,
  "data": [
    {
      "symbol": "000001",
      "code": "000001", 
      "date": "2024-01-15",
      "market_type": "CN",
      "score_total": 85.5,
      "score_accumulation": 30.0,
      "score_balance": 40.0,
      "score_momentum": 15.5,
      "buy_type": "右侧",
      "left_buy_signal": false,
      "right_buy_signal": true,
      "sell_signal": false,
      "ratio_d20": 0.008,
      "ratio_d1": 0.012,
      "ratio_d": 0.005,
      "fz_ratio": 2.1,
      "volume_ratio": 2.3,
      "delta": 0.15,
      "d": 12.5,
      "instant_deviation": 0.08,
      "rising_days": 5,
      "falling_days": 8
    }
  ],
  "total": 156,
  "search_date": "2024-01-15",
  "strategy_name": "GMS均值引力动量策略",
  "parameters": {
    "limit": 100,
    "min_score": 60,
    "scope": "all"
  }
}
```

### 7.2 错误处理

#### 错误响应格式
```json
{
  "success": false,
  "message": "GMS策略暂不可用",
  "data": []
}
```

#### 常见错误码
- `503`: 策略模块不可用
- `400`: 参数验证失败
- `500`: 内部计算错误

---

## 8. 部署与使用

### 8.1 环境要求

#### 依赖模块
```python
# 核心依赖
sqlalchemy>=1.4.0
fastapi>=0.68.0
pydantic>=1.8.0

# 数据处理
pandas>=1.3.0
numpy>=1.21.0

# 配置管理  
jsonschema>=4.0.0
```

#### 数据表依赖
- `mean_frequency_resonance_indicators` - 核心指标数据
- `stock_basic_info` - A股基础信息
- `stock_basic_info_hk` - 港股基础信息
- `watchlist` - 自选股列表

### 8.2 部署步骤

#### 1. 配置文件部署
```bash
# 确保配置文件存在
cp backend_core/strategies/gms/gms_config.json.example \
   backend_core/strategies/gms/gms_config.json

# 根据环境调整参数
vim gms_config.json
```

#### 2. 数据准备
```sql
-- 确保指标表有数据
SELECT COUNT(*) FROM mean_frequency_resonance_indicators 
WHERE date = '2024-01-15';

-- 检查股票基础信息
SELECT COUNT(*) FROM stock_basic_info;
SELECT COUNT(*) FROM stock_basic_info_hk;
```

#### 3. 服务启动
```bash
# 启动后端服务
cd backend_api
python main.py

# 验证GMS模块加载
curl http://localhost:5000/debug/routes | grep gms
```

### 8.3 使用示例

#### API调用示例
```bash
# 基础选股
curl "http://localhost:5000/api/stock/screening/gms-strategy?date=2024-01-15&min_score=60"

# 限制数量
curl "http://localhost:5000/api/stock/screening/gms-strategy?date=2024-01-15&limit=20"

# 自选股范围
curl "http://localhost:5000/api/stock/screening/gms-strategy?scope=watchlist"
```

#### Python SDK示例
```python
from backend_core.strategies.gms.frontend_interface import GMSFrontendInterface
from backend_core.strategies.gms.config import GMSConfigManager

# 初始化
config = GMSConfigManager().get_config()
gms = GMSFrontendInterface(db, config)

# 设置选股参数
gms.set_selection_config(min_score=60, max_results=100)

# 执行选股
results = gms.get_selection_results(
    date="2024-01-15",
    stock_pool=None,  # None表示全市场
    market="all"
)

print(f"选股结果: {len(results)} 只股票")
for stock in results[:5]:
    print(f"{stock['symbol']}: {stock['score_total']:.1f}分 {stock['buy_type']}")
```

---

## 9. 性能优化

### 9.1 数据库优化

#### 索引设计
```sql
-- 核心查询索引
CREATE INDEX idx_mfri_date_market ON mean_frequency_resonance_indicators(date, market_type);
CREATE INDEX idx_mfri_code_date ON mean_frequency_resonance_indicators(code, date);
CREATE INDEX idx_mfri_score ON mean_frequency_resonance_indicators(score_total);

-- 复合索引
CREATE INDEX idx_mfri_query ON mean_frequency_resonance_indicators(date, market_type, code);
```

#### 查询优化
```python
# 批量查询优化
def load_indicators_batch(self, codes, date, market_type):
    # 分批查询，避免IN子句过长
    batch_size = 1000
    results = []
    
    for i in range(0, len(codes), batch_size):
        batch_codes = codes[i:i+batch_size]
        batch_results = self._query_batch(batch_codes, date, market_type)
        results.extend(batch_results)
    
    return results
```

### 9.2 内存优化

#### 对象池
```python
class GMSIndicatorsPool:
    """指标对象池，减少内存分配"""
    def __init__(self, pool_size=1000):
        self.pool = [GMSIndicators() for _ in range(pool_size)]
        self.available = list(range(pool_size))
    
    def acquire(self):
        if self.available:
            return self.pool[self.available.pop()]
        return GMSIndicators()  # 池满时新建
    
    def release(self, obj):
        # 重置对象状态
        self._reset_object(obj)
        if len(self.available) < len(self.pool):
            idx = self.pool.index(obj)
            self.available.append(idx)
```

#### 延迟计算
```python
class LazyGMSIndicators:
    """延迟计算指标，只在需要时计算"""
    def __init__(self, raw_data):
        self.raw_data = raw_data
        self._score_total = None
    
    @property
    def score_total(self):
        if self._score_total is None:
            self._score_total = self._calculate_score_total()
        return self._score_total
```

### 9.3 并发优化

#### 异步处理
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

class AsyncGMSEngine:
    def __init__(self, max_workers=4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    async def screen_async(self, codes, date, market):
        """异步选股，支持并发处理"""
        tasks = []
        
        # 按市场分片
        markets = ["CN", "HK"] if market == "all" else [market]
        
        for market_type in markets:
            task = asyncio.create_task(
                self._screen_market(codes, date, market_type)
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        return [item for sublist in results for item in sublist]
```

---

## 10. 扩展性设计

### 10.1 策略接口扩展

#### 新策略集成
```python
# 实现标准接口
class NewStrategyEngine(IStrategyEngine):
    def screen(self, codes, date, market, config):
        # 实现新策略逻辑
        pass

# 注册到策略工厂
class StrategyFactory:
    strategies = {
        "gms": GMSStrategyEngine,
        "new_strategy": NewStrategyEngine,
    }
    
    @classmethod
    def create(cls, strategy_name, **kwargs):
        if strategy_name not in cls.strategies:
            raise ValueError(f"未知策略: {strategy_name}")
        return cls.strategies[strategy_name](**kwargs)
```

#### 多策略组合
```python
class MultiStrategyEngine:
    """多策略组合引擎"""
    def __init__(self, strategies, weights=None):
        self.strategies = strategies
        self.weights = weights or [1.0] * len(strategies)
    
    def screen(self, codes, date, market, config):
        """多策略综合评分"""
        all_results = {}
        
        for strategy, weight in zip(self.strategies, self.weights):
            results = strategy.screen(codes, date, market, config)
            
            for result in results:
                symbol = result["symbol"]
                if symbol not in all_results:
                    all_results[symbol] = {
                        "symbol": symbol,
                        "scores": {},
                        "weighted_score": 0.0
                    }
                
                score = result.get("score_total", 0)
                all_results[symbol]["scores"][strategy.name] = score
                all_results[symbol]["weighted_score"] += score * weight
        
        # 归一化处理
        return self._normalize_results(all_results)
```

### 10.2 指标扩展

#### 自定义指标
```python
class CustomIndicatorsCalculator(GMSIndicatorsCalculator):
    """扩展指标计算器"""
    
    def __init__(self, config):
        super().__init__(config)
        self.custom_indicators = config.get("custom_indicators", {})
    
    def calculate(self, row):
        # 基础指标计算
        indicators = super().calculate(row)
        
        # 自定义指标计算
        for name, formula in self.custom_indicators.items():
            value = self._evaluate_formula(formula, row)
            setattr(indicators, name, value)
        
        return indicators
    
    def _evaluate_formula(self, formula, row):
        """安全公式求值"""
        # 实现安全的数学表达式求值
        pass
```

#### 动态指标注册
```python
class IndicatorRegistry:
    """指标注册中心"""
    _indicators = {}
    
    @classmethod
    def register(cls, name, calculator_func):
        """注册自定义指标"""
        cls._indicators[name] = calculator_func
    
    @classmethod
    def calculate(cls, name, row):
        """计算指定指标"""
        if name not in cls._indicators:
            raise ValueError(f"未注册指标: {name}")
        return cls._indicators[name](row)

# 使用示例
@IndicatorRegistry.register("custom_momentum")
def calculate_custom_momentum(row):
    return (row["delta"] / row["d"]) * row["volume_ratio"]
```

### 10.3 数据源扩展

#### 多数据源适配
```python
class UniversalDataLoader(IDataLoader):
    """通用数据加载器，支持多数据源"""
    
    def __init__(self, data_sources):
        self.data_sources = data_sources
    
    def load_indicators(self, codes, date, market_type):
        """从多个数据源加载并合并数据"""
        all_data = {}
        
        for source in self.data_sources:
            try:
                data = source.load_indicators(codes, date, market_type)
                for item in data:
                    symbol = item["code"]
                    if symbol not in all_data:
                        all_data[symbol] = item
                    else:
                        # 数据合并策略
                        all_data[symbol] = self._merge_data(
                            all_data[symbol], item
                        )
            except Exception as e:
                logger.warning(f"数据源 {source.name} 加载失败: {e}")
        
        return list(all_data.values())
```

---

## 总结

GMS选股策略是一个完整的量化选股系统，具有以下特点：

### 核心优势
1. **理论基础扎实**: 基于均值回归和动量效应的金融学原理
2. **架构设计清晰**: 分层架构，职责明确，易于维护
3. **配置灵活**: 支持多层级配置，参数可调
4. **扩展性强**: 接口标准化，便于策略扩展和组合
5. **性能优化**: 支持批量处理、异步计算、对象池等优化

### 适用场景
- A股和港股市场的量化选股
- 中长期趋势跟踪策略
- 基于技术指标的选股系统
- 多策略组合投资

### 后续优化方向
1. **机器学习增强**: 引入ML模型优化信号判断
2. **实时数据支持**: 支持实时行情数据处理
3. **回测系统完善**: 增强历史回测和绩效分析
4. **风险管理**: 增加止损、仓位管理等风控机制
5. **可视化界面**: 开发专门的策略分析和配置界面

该文档为GMS策略的完整技术实现指南，可作为开发、部署和维护的参考依据。
