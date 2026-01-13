# PVFRS 策略与回测系统设计文档

## 1. 文档目的

本文档描述基于 **PVFRS（量价频三维共振演化 / 均值频率共振）** 理论的交易策略设计与回测系统实现方案，用于：

- 定义 PVFRS 指标的交易信号（买点/卖点/风控）
- 说明回测系统的数据依赖、模块结构、参数配置与运行方式
- 作为后续功能扩展（图表、佣金滑点、多标的组合等）的设计依据

> 理论依据参考：
> - `docs/均值频率共振指标设计文档.md`
> - `docs/量价频三维共振演化策略指南.md`

---

## 2. PVFRS 理论与指标字段

### 2.1 三维共振理论（PVFRS）

PVFRS 将“高效率上涨”定义为市场在以下三个维度同时达成向上共振：

- **价格维度（方向 + 强度）**
  - 宏观位移 Δ > 0
  - 即时强度 d20 > d（Close > MA20）
- **频率维度（微观一致性/共识）**
  - 上涨频率优势 Z > F（上涨天数多于下跌天数）
- **成交量维度（动力与进出效率）**
  - 进出效率 m20 > m（Vol > MAVOL20）

当三个维度同时满足时，认为进入“高效率演化轨道”，具备更高的趋势延续概率。

---

### 2.2 指标字段（数据库模型）

PVFRS 指标数据存储在：

- 表：`mean_frequency_resonance_indicators`
- 模型：`backend_api.models.MeanFrequencyResonanceIndicators`

字段（与策略/回测强相关）：

- `macro_displacement_delta`：宏观位移 Δ
- `instant_deviation`：即时偏离度（Close - MA20）
- `rising_days_z`：上涨天数 Z
- `falling_days_f`：下跌天数 F
- `efficiency_m20_minus_m`：进出效率（Vol - MAVOL20）
- `ma20_d`：MA20
- `mavol20_m`：MAVOL20
- `bias`：乖离率（Close - MA20）/ MA20

行情数据来源：

- A 股：`backend_api.models.HistoricalQuotes`（`date` 为 Date 类型）
- 港股：`backend_api.models.HistoricalQuotesHK`（`date` 为 String 类型）

---

## 3. 交易策略设计（买点/卖点/风控）

### 3.1 买入信号（高效率上涨确认）

本策略的买入逻辑严格遵循文档中的“高效率上涨”定义：

#### 3.1.1 严格条件（必须全部满足）

- **价格维度**
  - `macro_displacement_delta > 0`
  - `instant_deviation > 0`（Close > MA20）
- **频率维度**
  - `rising_days_z > falling_days_f`
- **成交量维度**
  - `efficiency_m20_minus_m > 0`（Vol > MAVOL20）

#### 3.1.2 增强条件（提高信号强度）

增强条件用于过滤“太平”的走势（幅度不足）与弱动能：

- 幅度校验
  - `bias > buy_bias_min`（默认 2%）
  - `macro_displacement_delta / ma20_d > buy_relative_displacement_min`（默认 5%）
- 连续确认
  - 连续 `buy_consecutive_days` 天满足“严格条件”（默认 3 天）

> 信号强度 `strength` 基于增强条件达成数量计算，并对连续确认做加权。

---

### 3.2 卖出信号（趋势反转/风险信号）

卖出信号分为“趋势反转”与“价涨量缩背离”。

#### 3.2.1 趋势反转（满足 >=2 条触发卖出）

候选反转条件：

- `instant_deviation < 0`（价格跌破 MA20）
- `macro_displacement_delta < 0`（宏观位移转负）
- `falling_days_f > rising_days_z`（下跌频率占优）
- `efficiency_m20_minus_m < 0`（成交量萎缩）
- `bias > sell_bias_max`（默认 8%，超买）
- `instant_deviation > sell_instant_deviation_max`（默认 5%，偏离过远）

当上述条件命中数量 >= 2 时，生成卖出信号。

#### 3.2.2 价涨量缩背离（单独触发卖出）

- `instant_deviation > 0` 且 `efficiency_m20_minus_m < 0`
- 连续 >=2 天出现背离则触发卖出（越久强度越高）

---

### 3.3 风控规则

回测引擎内置风控（持仓后自动检查）：

- **止损**：`stop_loss`（默认 -10%）
- **止盈**：`take_profit`（默认 +20%）
- **最大持有天数**：`max_holding_days`（默认 30 天）
- **最大仓位**：`max_position_size`（默认 10%）

---

## 4. 系统实现与模块设计

### 4.1 代码目录

实现位于：`backend_core/strategies/`

- `pvfrs_strategy.py`
  - 策略信号生成器：`PVFRSStrategy`
  - 信号检测：`PVFRSSignalDetector`、`DivergenceDetector`、`MomentumConfirmator`
  - 回测引擎：`PVFRSBacktestEngine`
- `pvfrs_data_loader.py`
  - 数据加载：`PVFRSDataLoader`
  - 数据合并与质量检查
- `pvfrs_performance_analyzer.py`
  - 绩效指标计算：`PVFRSPerformanceAnalyzer`
  - 报告生成：`PVFRSReportGenerator`
- `pvfrs_backtest_runner.py`
  - 命令行入口（single / batch / optimize）
- `pvfrs_config.json`
  - 分层策略配置文件

---

### 4.2 数据流（回测主流程）

1. `pvfrs_backtest_runner.py` 解析命令行参数
2. 从 `pvfrs_config.json` 加载
   - `strategy_params`
   - `backtest_config.initial_capital`（命令行优先）
3. `pvfrs_data_loader.py` 从数据库读取
   - PVFRS 指标
   - 历史行情（价格/成交量）
4. 合并为一个 DataFrame（按 `date` 对齐）
5. `PVFRSStrategy.generate_signals()` 生成买/卖信号
6. `PVFRSBacktestEngine.run_backtest()` 逐日回放
   - 执行交易
   - 更新权益曲线
   - 风控检查
7. 生成报告与指标统计

---

## 5. 配置设计（pvfrs_config.json）

当前配置文件采用**分层结构**：

- `strategy_params`：策略参数（阈值、连续确认天数、风控参数等）
- `backtest_config`：回测环境参数（初始资金等）
- `optimization_config`：参数网格搜索范围（可用于后续扩展）

示例片段：

```json
{
  "strategy_params": {
    "buy_bias_min": 0.02,
    "buy_consecutive_days": 3,
    "stop_loss": -0.1,
    "take_profit": 0.2
  },
  "backtest_config": {
    "initial_capital": 100000
  }
}
```

---

## 6. 运行方式

### 6.1 单股回测

```powershell
python backend_core/strategies/pvfrs_backtest_runner.py \
  --mode single \
  --code 688256 \
  --market CN \
  --start-date 2023-01-01 \
  --end-date 2025-12-31 \
  --params-file backend_core/strategies/pvfrs_config.json
```

如需覆盖初始资金：

```powershell
python backend_core/strategies/pvfrs_backtest_runner.py --mode single --code 688256 --market CN --start-date 2023-01-01 --end-date 2025-12-31 --params-file backend_core/strategies/pvfrs_config.json --initial-capital 200000
```

### 6.2 批量回测

```powershell
python backend_core/strategies/pvfrs_backtest_runner.py --mode batch --market CN --start-date 2023-01-01 --end-date 2025-12-31 --output pvfrs_batch_report.md
```

### 6.3 参数优化（网格搜索）

```powershell
python backend_core/strategies/pvfrs_backtest_runner.py --mode optimize --code 688256 --market CN --start-date 2023-01-01 --end-date 2025-12-31 --output pvfrs_optimize_report.md
```

---

## 7. 关键实现说明与已修复问题

- **A股日期类型对齐问题**：`HistoricalQuotes.date` 为 `Date`，已在数据加载时统一输出为 `YYYY-MM-DD` 字符串，保证与 PVFRS 指标按 `date` 合并。
- **参数读取分层结构**：runner 已支持从配置文件读取 `strategy_params`，并兼容扁平结构。
- **初始资金读取**：runner 支持从 `backtest_config.initial_capital` 读取，命令行优先。
- **可选依赖**：`pvfrs_performance_analyzer.py` 对 `matplotlib/seaborn` 做了可选导入处理，避免环境缺包导致回测入口崩溃。

---

## 8. 可扩展点（后续演进建议）

- **交易成本**：加入手续费、滑点（目前配置文件已有字段，但回测引擎未实现扣费）
- **组合回测**：支持多标的资金分配、最大持仓数量
- **信号可视化**：绘制 equity curve、买卖点标注、月度收益热力图
- **样本外验证**：分训练区间/验证区间，防止过拟合
- **事件记录**：将回测交易写入数据库日志表，用于前端展示

---

## 9. 限制与免责声明

- 本策略属于研究用途，回测结果不代表未来收益。
- PVFRS 策略对数据完整性敏感，需确保历史行情与 PVFRS 指标按日期完整对齐。
- 如用于实盘，需要额外考虑：停牌、涨跌停、流动性、交易时间、资金容量与撮合滑点等因素。
