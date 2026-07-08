# GSM 选股策略状态判定规则明细

## 目录

- [1. 概述](#1-概述)
- [2. 均值收敛态判定规则](#2-均值收敛态判定规则)
- [3. 动量溢出态判定规则](#3-动量溢出态判定规则)
- [4. 信号检测逻辑](#4-信号检测逻辑)
- [5. 配置参数说明](#5-配置参数说明)
- [6. 判定流程图](#6-判定流程图)
- [7. 实际应用示例](#7-实际应用示例)

------------------------------------------------------------------------

## 1. 概述

GMS（均值引力与动量突变策略）采用**双模块阶梯式评分**系统，将股票状态分为两种核心形态：

### 1.1 均值收敛态（左侧买点）

- **定义**：价格极度接近均线，成交量萎缩，处于均值吸附状态
- **特征**：F \> Z（下跌天数 \> 上涨天数），Δ \<
  0，价格粘合均线，地量洗盘
- **等级**：S级（优秀）、A级（良好）、无等级

### 1.2 动量溢出态（右侧买点）

- **定义**：价格突破均线，成交量放大，处于动量引爆状态
- **特征**：d₂₀ \> d，Δ \> 0，放量确认，攻击强度高
- **等级**：全速切入、分批买入、无等级

### 1.3 评分体系

- **均值收敛态总分**：0-100分（时间耗散 + 引力粘合 + 成交量缩）
- **动量溢出态总分**：0-100分（盈亏反转 + 推力支撑 +
  攻击强度，可含负分）
- **综合总分**：取两模块较高者，用于排序（**标准版** `tiered_dual_max`）
- **增强版综合总分**（`tiered_dual_penalty` / 配置名 `gms_penalty`）：`clamp(基础分 − 减分合计, 0, 100)`，其中基础分 = max(均值收敛态小计, 动量溢出态小计)；等级判定仍按**减分前**基础分

------------------------------------------------------------------------

## 2. 均值收敛态判定规则

### 2.1 均值收敛态等级判定

#### S级（优秀）判定

``` python
if score_accumulation >= 85:
    accumulation_grade = "S"
```

#### A级（良好）判定

``` python
elif score_accumulation >= 70:
    accumulation_grade = "A"
```

#### 无等级判定

``` python
else:
    accumulation_grade = ""
```

### 2.2 均值收敛态评分构成（满分100分）

#### 2.2.1 时间耗散维度（权重30分）

**指标**：F/Z 数方比（下跌天数/上涨天数）

**评分规则**：

``` python
def _score_accumulation_fz(fz_ratio):
    """F/Z ≥ 2.5 → 30分（满分）
       1.5 ≤ F/Z < 2.5 → 20分（2/3权重）
       F/Z < 1.5 → 0分
    """
    if fz_ratio >= 2.5:
        return 30.0
    elif fz_ratio >= 1.5:
        return 20.0
    else:
        return 0.0
```

**配置参数**： - `accumulation_fz_tiers`: \[2.5, 1.5\] - F/Z 分级阈值 -
`weight_acc_fz`: 30 - 时间耗散权重

#### 2.2.2 引力粘合维度（权重40分）

**指标**：\|Δ/d\| 相对偏离率

**评分规则**：

``` python
def _score_accumulation_balance(abs_ratio_d):
    """|Δ/d| ≤ 0.01 → 40分（满分）
       0.01 < |Δ/d| ≤ 0.015 → 20分（1/2权重）
       |Δ/d| > 0.015 → 0分
    """
    if abs_ratio_d <= 0.01:
        return 40.0
    elif abs_ratio_d <= 0.015:
        return 20.0
    else:
        return 0.0
```

**配置参数**： - `balance_ratio_d_tiers`: \[0.01, 0.015\] -
引力粘合分级阈值 - `weight_acc_balance`: 40 - 引力粘合权重

#### 2.2.3 成交量缩维度（权重30分）

**指标**：m₂₀/m 量比（当日成交量/20日平均成交量）

**评分规则**：

``` python
def _score_accumulation_volume(volume_ratio):
    """m₂₀/m ≤ 0.6 → 30分（满分）
       0.6 < m₂₀/m ≤ 0.8 → 15分（1/2权重）
       m₂₀/m > 0.8 → 0分
    """
    if volume_ratio <= 0.6:
        return 30.0
    elif volume_ratio <= 0.8:
        return 15.0
    else:
        return 0.0
```

**配置参数**： - `volume_ratio_shrink_tiers`: \[0.6, 0.8\] -
成交量缩分级阈值 - `weight_acc_volume`: 30 - 成交量缩权重

### 2.3 均值收敛态前置条件

#### 传统判定条件（无等级时使用）

``` python
# 1. 必须有上涨天数
if indicators.rising_days <= 0:
    return False

# 2. 下跌天数 > 上涨天数（充分蓄势）
if indicators.falling_days <= indicators.rising_days:
    return False

# 3. 宏观位移为负（d20 < d1）
if indicators.delta >= 0:
    return False
```

#### 等级优先判定

``` python
# 如果已有S/A等级，跳过前置条件检查
if getattr(indicators, "accumulation_grade", None) in ("S", "A"):
    pass  # 直接进入后续判定
```

------------------------------------------------------------------------

## 3. 动量溢出态判定规则

### 3.1 动量溢出态等级判定

#### 全速切入判定

``` python
if score_momentum >= 90:
    momentum_grade = "全速切入"
```

#### 分批买入判定

``` python
elif score_momentum >= 80:
    momentum_grade = "分批买入"
```

#### 无等级判定

``` python
else:
    momentum_grade = ""
```

### 3.2 动量溢出态评分构成（满分100分，可含负分）

#### 3.2.1 盈亏反转维度（权重40分）

**指标**：Δ/d₁ 突变率

**评分规则**：

``` python
def _score_momentum_ratio_d1(ratio_d1):
    """0 < Δ/d₁ ≤ 0.001 → 20分（1/2权重，刚过0轴）
       0.001 < Δ/d₁ ≤ 0.03 → 40分（满分，刚突破）
       Δ/d₁ > 0.03 → 0分（已涨太多，非买点）
       Δ/d₁ ≤ 0 → 0分（未突破）
    """
    if 0 < ratio_d1 <= 0.001:
        return 20.0
    elif 0.001 < ratio_d1 <= 0.03:
        return 40.0
    else:
        return 0.0
```

**配置参数**： - `ratio_d1_tiers`: \[0.001, 0.03\] - 盈亏反转分级阈值 -
`weight_mom_ratio_d1`: 40 - 盈亏反转权重

#### 3.2.2 推力支撑维度（权重30分）

**指标**：d₂₀ - d 瞬时偏离

**评分规则**：

``` python
def _score_momentum_deviation(instant_deviation, series):
    """d₂₀ - d ≤ 0 → -10分（固定负分，未突破均线）
       d₂₀ - d > 0 且站稳3日 → 30分（满分）
       d₂₀ - d > 0 且仅当日 → 15分（1/2权重）
    """
    if instant_deviation <= 0:
        return -10.0  # 未突破均线，固定负分
    
    # 检查是否站稳3日
    if series and len(series) >= 3 and all(x > 0 for x in series[-3:]):
        return 30.0
    else:
        return 15.0  # 仅当日突破
```

**配置参数**： - `instant_deviation_stable_days`: 3 - 站稳天数要求 -
`weight_mom_deviation`: 30 - 推力支撑权重

#### 3.2.3 攻击强度维度（权重30分）

**指标**：m₂₀/m 量比

**评分规则**：

``` python
def _score_momentum_volume(volume_ratio):
    """m₂₀/m ≥ 2.0 → 30分（满分）
       1.5 ≤ m₂₀/m < 2.0 → 20分（2/3权重）
       m₂₀/m < 1.5 → 0分
    """
    if volume_ratio >= 2.0:
        return 30.0
    elif volume_ratio >= 1.5:
        return 20.0
    else:
        return 0.0
```

**配置参数**： - `volume_ratio_attack_tiers`: \[2.0, 1.5\] -
攻击强度分级阈值 - `weight_mom_volume`: 30 - 攻击强度权重

### 3.3 动量溢出态前置条件

#### 传统判定条件（无等级时使用）

``` python
# 1. 价格突破均线
if indicators.instant_deviation <= 0:  # d20 > d
    return False

# 2. 宏观位移为正（上涨趋势）
if indicators.delta <= 0:  # Δ > 0
    return False
```

#### 等级优先判定

``` python
# 如果已有全速切入/分批买入等级，跳过前置条件检查
if getattr(indicators, "momentum_grade", None) in ("全速切入", "分批买入"):
    pass  # 直接进入后续判定
```

------------------------------------------------------------------------

## 4. 信号检测逻辑

### 4.1 左侧买点（均值吸附）检测

#### 完整判定逻辑

``` python
def detect_left_buy(self, indicators):
    """左侧买点检测"""
    
    # 1. 等级优先：S/A级直接通过前置条件
    if getattr(indicators, "accumulation_grade", None) in ("S", "A"):
        pass
    else:
        # 前置条件检查
        if indicators.rising_days <= 0:
            return False
        if indicators.falling_days <= indicators.rising_days:  # F > Z
            return False
        if indicators.delta >= 0:  # Δ < 0
            return False
    
    # 2. 引力粘合检查：|Δ/d₂₀| < 1.5%
    if indicators.ratio_d20 is None or abs(indicators.ratio_d20) >= 0.015:
        return False
    
    # 3. 地量洗盘检查：m₂₀ < 0.8m
    if indicators.volume_ratio is None or indicators.volume_ratio >= 0.8:
        return False
    
    return True
```

#### 配置参数

- `ratio_d20_abs_max`: 0.015 - 最大偏离率
- `volume_ratio_max`: 0.8 - 最大量比

### 4.2 右侧买点（动量引爆）检测

#### 完整判定逻辑

``` python
def detect_right_buy(self, indicators):
    """右侧买点检测"""
    
    # 1. 等级优先：全速切入/分批买入直接通过前置条件
    if getattr(indicators, "momentum_grade", None) in ("全速切入", "分批买入"):
        pass
    else:
        # 前置条件检查
        if indicators.instant_deviation <= 0:  # d20 > d
            return False
        if indicators.delta <= 0:  # Δ > 0
            return False
    
    # 2. 放量确认：m₂₀ > 1.5m
    if indicators.volume_ratio is None or indicators.volume_ratio < 1.5:
        return False
    
    return True
```

#### 配置参数

- `volume_ratio_min`: 1.5 - 最小量比

### 4.3 卖点检测

#### 判定逻辑

``` python
def detect_sell(self, indicators):
    """卖点检测：乖离过大"""
    
    # 优先使用Δ/d指标
    if self.use_ratio_d_for_exit and indicators.ratio_d is not None:
        if indicators.ratio_d > 0.15:  # Δ/d > 15%
            return True
    
    # 使用Δ/d₂₀指标
    if indicators.ratio_d20 is not None:
        if indicators.ratio_d20 > 0.15:  # Δ/d₂₀ > 15%
            return True
    
    return False
```

#### 配置参数

- `overbought_ratio`: 0.15 - 超买阈值
- `use_ratio_d_for_exit`: False - 是否使用Δ/d作为退出条件

------------------------------------------------------------------------

## 5. 配置参数说明

### 5.1 均值收敛态配置参数

``` json
{
  "scoring": {
    // 均值收敛态评分阈值
    "accumulation_s_threshold": 85,    // S级阈值
    "accumulation_a_threshold": 70,    // A级阈值
    
    // 均值收敛态分级阈值
    "accumulation_fz_tiers": [2.5, 1.5],        // F/Z 分级：[满分阈值, 2/3分阈值]
    "balance_ratio_d_tiers": [0.01, 0.015],     // |Δ/d| 分级：[满分阈值, 1/2分阈值]
    "volume_ratio_shrink_tiers": [0.6, 0.8],    // m₂₀/m 分级：[满分阈值, 1/2分阈值]
    
    // 均值收敛态权重分配
    "weight_acc_fz": 30,          // 时间耗散权重
    "weight_acc_balance": 40,     // 引力粘合权重
    "weight_acc_volume": 30       // 成交量缩权重
  }
}
```

### 5.2 动量溢出态配置参数

``` json
{
  "scoring": {
    // 动量溢出态评分阈值
    "momentum_full_threshold": 90,    // 全速切入阈值
    "momentum_batch_threshold": 80,   // 分批买入阈值
    
    // 动量溢出态分级阈值
    "ratio_d1_tiers": [0.001, 0.03],          // Δ/d₁ 分级：[1/2分阈值, 满分阈值]
    "volume_ratio_attack_tiers": [2.0, 1.5], // m₂₀/m 分级：[满分阈值, 2/3分阈值]
    "instant_deviation_stable_days": 3,       // 站稳天数要求
    
    // 动量溢出态权重分配
    "weight_mom_ratio_d1": 40,     // 盈亏反转权重
    "weight_mom_deviation": 30,    // 推力支撑权重
    "weight_mom_volume": 30        // 攻击强度权重
  }
}
```

### 5.3 信号检测配置参数

``` json
{
  "left_buy": {
    "ratio_d20_abs_max": 0.015,    // |Δ/d₂₀| < 1.5%
    "volume_ratio_max": 0.8        // m₂₀ < 0.8m
  },
  "right_buy": {
    "volume_ratio_min": 1.5        // m₂₀ > 1.5m
  },
  "exit": {
    "overbought_ratio": 0.15,      // Δ/d₂₀ > 15%
    "trend_break_days": 3          // 趋势破坏天数
  },
  "ratio_indicators": {
    "use_ratio_d": true,           // 是否使用Δ/d指标
    "use_ratio_d_for_exit": false  // 是否使用Δ/d作为退出条件
  }
}
```

### 5.4 打分机制与减分规则（多版本）

`scoring.mechanism` 决定综合分计算方式。全系统仅两个**共享**参数版本（`gms_strategy_configs`）：

| 配置名 | mechanism | 名称 |
|--------|-----------|------|
| `default` | `tiered_dual_max` | 标准版·双模块阶梯 |
| `gms_penalty` | `tiered_dual_penalty` | 增强版·阶梯+减分 |

| mechanism | 名称 | 说明 |
|-----------|------|------|
| `tiered_dual_max` | 标准版·双模块阶梯 | 现网默认：均值收敛态与动量溢出态独立阶梯评分，综合分取两者较高者；**不允许**配置减分规则 |
| `tiered_dual_penalty` | 增强版·阶梯+减分 | 在标准版基础分上按规则扣分，最终分限制在 0~100；**至少一条**启用的减分规则 |

管理端「打分与参数」与网站选股下拉均只展示以上两者；**修改扣分值等参数会原地更新对应 config，不会新建 `auto_gms_v*` 版本**。观察股策略版本（`gms_strategy_versions`）按所选机制绑定到上述共享 config。

**管理入口**：管理端「GMS策略版本」→「打分与参数」Tab，或「策略参数配置」页（`default` / `gms_penalty`）；网站选股参数版本下拉展示 `scoring_mechanism_label`。减分规则类型列表：`GET /api/admin/gms/penalty-rule-types`。

#### 5.4.1 配置示例

``` json
{
  "observation_period": 20,
  "scoring": {
    "mechanism": "tiered_dual_penalty",
    "penalty_rules": [
      {
        "id": "close_below_ma60",
        "enabled": true,
        "points": 10,
        "label": "收盘低于60日均线",
        "half_when_ma60_flat": true
      },
      {
        "id": "observation_range_amplitude",
        "enabled": true,
        "points": 10,
        "label": "观察周期振幅过大",
        "amplitude_threshold_pct": 0.30
      }
    ],
    "ma60_flat_lookback_days": 20,
    "ma60_flat_tol": 0.015
  }
}
```

新建 `gms_penalty` 共享配置时，系统默认启用上述两条减分规则；**已有库内配置不会自动追加**，需在管理端「添加规则」手动启用 `observation_range_amplitude`。

#### 5.4.2 减分规则 `close_below_ma60`

当 `d20 < ma60_d`（收盘价低于 60 日均线）时，从基础分扣除 `points` 分。若 MA60 处于**走平**状态，扣分取半（默认 `points × 0.5`）。

**MA60 走平判定**（默认，可在 `scoring` 中配置）：

```
ma60_flat = |ma60_d - ma60_d_lag| / ma60_d_lag < ma60_flat_tol
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `ma60_flat_lookback_days` | 20（与 `observation_period` 一致） | 回看 N 个**交易日**的 MA60（`ma60_d_lag`）；未配置时自动取观察周期 |
| `ma60_flat_tol` | 0.015 | 相对变化 &lt; 1.5% 视为走平 |
| `half_when_ma60_flat` | true | 减分规则级开关，走平时扣分减半 |

缺 lag 日 MA60 数据时视为**非走平**，扣满分。

**数据依赖**：GMS 使用的 MA60 以 **`ma_indicators.ma60`** 为唯一权威源（同 `code` + `date` + `market_type`）。指标写入时同步到 `mean_frequency_resonance_indicators.ma60_d`；读取时若 `ma60_d` 缺失，`data_loader` 会从 `ma_indicators` 补全，并批量计算 `ma60_d_lag` / `ma60_flat`。**不再**用行情表估算。若 MA 指标未生成则 `ma60_d` 为空，该规则减分不生效。

#### 5.4.3 减分规则 `observation_range_amplitude`（观察周期振幅过大）

当策略**观察周期内**（默认 `observation_period` = 20 个交易日，含信号日）最高价与最低价的区间振幅超过阈值时扣分，并自动生成风险提示标签（`penalty_observation_range_amplitude`）。

**振幅计算公式**（与行情软件常见的「振幅」分母不同，以周期内最高价为分母）：

```
observation_range_amplitude_pct = (period_high − period_low) / period_high
```

其中：

- `period_high`：观察周期内（信号日及向前 N−1 个交易日）行情 **high** 的最大值
- `period_low`：同一窗口内行情 **low** 的最小值
- N = `observation_period`（默认 20）

**触发条件**：`observation_range_amplitude_pct > amplitude_threshold_pct`（严格大于；等于阈值不扣分）。

| 参数 | 位置 | 默认值 | 说明 |
|------|------|--------|------|
| `points` | 规则级 | 10 | 命中后扣分 |
| `amplitude_threshold_pct` | 规则级 | 0.30 | 振幅阈值（0.30 = 30%） |
| `observation_range_amplitude_threshold` | `scoring` 全局（可选） | — | 未在规则上配置阈值时的兜底 |
| `observation_period` | 根配置 | 20 | 观察窗口交易日数 |

**注意**：`mean_frequency_resonance_indicators.amplitude` 字段表示的是 `|Δ|`（宏观位移绝对值），**不是**本规则的区间振幅；本规则在运行时从行情表实时计算，不依赖该字段。

**数据依赖与 enrich 链路**：

| 市场 | 行情表 |
|------|--------|
| A 股 `CN` | `historical_quotes` |
| 港股 `HK` | `historical_quotes_hk` |
| ETF / 基金 `ETF` | `fund_historical_quotes` |

实现模块：`backend_core/strategies/gms/observation_range.py`。在 `GMSDataLoader.load_indicators` 及选股单股兜底路径中，于 MA60 enrich 之后调用 `enrich_rows_observation_range`，向计算行写入：

- `observation_period_high` / `observation_period_low`
- `observation_range_amplitude_pct`
- `observation_range_period_days`

窗口内有效 K 线不足 N 根时，振幅为空，规则**不触发**（不扣分）。

**得分明细展示**（前端 `gms_score_detail.js`）：减分项表格条件列显示「观察周期振幅 X% &gt; 阈值 Y%」；指标细项区展示周期高低点与振幅。

#### 5.4.4 其他已注册减分规则（可选启用）

| 规则 ID | 说明 | 默认扣分 |
|---------|------|----------|
| `volume_shrink_after_breakout` | 突破后缩量回落 | 8 |
| `momentum_fade` | 动量衰减 | 6 |
| `excessive_deviation` | 乖离过大（Δ/d₂₀ 超 `overbought_ratio`） | 12 |

规则注册表：`backend_core/strategies/gms/scoring/penalties.py` → `PENALTY_RULE_TYPES`；校验：`validate_scoring_config`（`registry.py`）。

#### 5.4.5 增强版计算流程（概要）

```
TieredDualMaxScorer → 基础分 base_total
        ↓
enrich（ma60_d / ma60_flat / observation_range）
        ↓
PenaltyEngine.apply(row) → 减分合计 + penalty_details
        ↓
score_total = clamp(base_total − 减分合计, 0, 100)
        ↓
build_risk_tags → 每条命中的减分规则生成 penalty_* 风险提示
```

相关代码：`scoring/tiered_dual_penalty.py`、`scoring/penalties.py`、`risk_tags.py`、`strategy_engine.py`（`score_detail.penalties`）。

------------------------------------------------------------------------

## 6. 判定流程图

### 6.1 均值收敛态判定流程

    开始
      ↓
    计算F/Z数方比
      ↓
    F/Z ≥ 2.5? ──否──→ F/Z ≥ 1.5? ──否──→ 时间耗散0分
      │是                    │是
      ↓                      ↓
    时间耗散30分          时间耗散20分
      ↓                      ↓
    计算|Δ/d|偏离率        计算|Δ/d|偏离率
      ↓                      ↓
    |Δ/d| ≤ 0.01? ──否──→ |Δ/d| ≤ 0.015? ──否──→ 引力粘合0分
      │是                    │是
      ↓                      ↓
    引力粘合40分          引力粘合20分
      ↓                      ↓
    计算m₂₀/m量比          计算m₂₀/m量比
      ↓                      ↓
    m₂₀/m ≤ 0.6? ──否──→ m₂₀/m ≤ 0.8? ──否──→ 成交量缩0分
      │是                    │是
      ↓                      ↓
    成交量缩30分          成交量缩15分
      ↓                      ↓
    总分 = 三项得分之和    总分 = 三项得分之和
      ↓                      ↓
    总分 ≥ 85? ──否──→ 总分 ≥ 70? ──否──→ 无等级
      │是                    │是
      ↓                      ↓
    S级均值收敛态              A级均值收敛态

### 6.2 动量溢出态判定流程

    开始
      ↓
    计算Δ/d₁突变率
      ↓
    Δ/d₁ ≤ 0? ──是──→ 盈亏反转0分
      │否
      ↓
    Δ/d₁ ≤ 0.001? ──否──→ Δ/d₁ ≤ 0.03? ──否──→ 盈亏反转0分
      │是                    │是
      ↓                      ↓
    盈亏反转20分          盈亏反转40分
      ↓                      ↓
    计算d₂₀-d偏离          计算d₂₀-d偏离
      ↓                      ↓
    d₂₀-d ≤ 0? ──是──→ 推力支撑-10分
      │否
      ↓
    站稳3日? ──否──→ 推力支撑15分
      │是
      ↓
    推力支撑30分
      ↓
    计算m₂₀/m量比
      ↓
    m₂₀/m < 1.5? ──是──→ 攻击强度0分
      │否
      ↓
    m₂₀/m < 2.0? ──是──→ 攻击强度20分
      │否
      ↓
    攻击强度30分
      ↓
    总分 = 三项得分之和
      ↓
    总分 ≥ 90? ──否──→ 总分 ≥ 80? ──否──→ 无等级
      │是                    │是
      ↓                      ↓
    全速切入              分批买入

------------------------------------------------------------------------

## 7. 实际应用示例

### 7.1 均值收敛态S级判定示例

**股票数据**： - F/Z = 3.2（下跌8天，上涨2.5天） - \|Δ/d\| =
0.008（偏离率0.8%） - m₂₀/m = 0.5（量比0.5倍）

**评分计算**：

    时间耗散：F/Z = 3.2 ≥ 2.5 → 30分
    引力粘合：|Δ/d| = 0.008 ≤ 0.01 → 40分
    成交量缩：m₂₀/m = 0.5 ≤ 0.6 → 30分
    总分：30 + 40 + 30 = 100分

**等级判定**：

    100分 ≥ 85分 → S级均值收敛态

**信号检测**：

    前置条件：F > Z ✓, Δ < 0 ✓
    引力粘合：|Δ/d₂₀| = 0.008 < 0.015 ✓
    地量洗盘：m₂₀/m = 0.5 < 0.8 ✓
    → 左侧买点触发 ✓

### 7.2 动量溢出态全速切入判定示例

**股票数据**： - Δ/d₁ = 0.02（突变率2%） - d₂₀-d = 0.12（站稳3日） -
m₂₀/m = 2.5（量比2.5倍）

**评分计算**：

    盈亏反转：Δ/d₁ = 0.02 ∈ (0.001, 0.03] → 40分
    推力支撑：d₂₀-d = 0.12 > 0 且站稳3日 → 30分
    攻击强度：m₂₀/m = 2.5 ≥ 2.0 → 30分
    总分：40 + 30 + 30 = 100分

**等级判定**：

    100分 ≥ 90分 → 全速切入

**信号检测**：

    前置条件：d₂₀ > d ✓, Δ > 0 ✓
    放量确认：m₂₀/m = 2.5 > 1.5 ✓
    → 右侧买点触发 ✓

### 7.3 边界情况示例

#### 均值收敛态A级边界

**股票数据**： - F/Z = 2.0（刚好在1.5-2.5区间） - \|Δ/d\| =
0.012（刚好在0.01-0.015区间） - m₂₀/m = 0.7（刚好在0.6-0.8区间）

**评分计算**：

    时间耗散：F/Z = 2.0 → 20分
    引力粘合：|Δ/d| = 0.012 → 20分
    成交量缩：m₂₀/m = 0.7 → 15分
    总分：20 + 20 + 15 = 55分

**等级判定**：

    55分 < 70分 → 无等级（需要前置条件检查）

#### 动量溢出态分批买入边界

**股票数据**： - Δ/d₁ = 0.005（刚好在0.001-0.03区间） - d₂₀-d =
0.08（仅当日突破） - m₂₀/m = 1.8（刚好在1.5-2.0区间）

**评分计算**：

    盈亏反转：Δ/d₁ = 0.005 → 40分
    推力支撑：d₂₀-d = 0.08 > 0 但仅当日 → 15分
    攻击强度：m₂₀/m = 1.8 → 20分
    总分：40 + 15 + 20 = 75分

**等级判定**：

    75分 < 80分 → 无等级（需要前置条件检查）

------------------------------------------------------------------------

## 总结

GMS策略的状态判定系统通过**双模块阶梯式评分**实现了对股票状态的精确刻画：

### 核心特点

1.  **双重评分体系**：均值收敛态和动量溢出态独立评分，互不干扰
2.  **等级优先机制**：S/A级和全速切入/分批买入等级可跳过前置条件
3.  **阶梯式评分**：每个维度采用多级阈值，评分更精细
4.  **灵活配置**：所有阈值和权重均可配置
5.  **增强减分版**（`gms_penalty`）：在基础分上按规则扣分（如低于 MA60、观察周期振幅过大），并输出风险提示标签

### 判定逻辑

- **均值收敛态**：关注时间耗散、引力粘合、成交量缩三个维度
- **动量溢出态**：关注盈亏反转、推力支撑、攻击强度三个维度
- **信号检测**：结合等级和具体指标进行最终判定

### 应用价值

- **左侧买点**：识别极度粘合、地量洗盘的吸筹机会
- **右侧买点**：捕捉突破均线、放量确认的起涨机会
- **风险控制**：通过乖离过大检测及时止盈

该判定规则为量化选股提供了系统化、可操作的决策依据。
