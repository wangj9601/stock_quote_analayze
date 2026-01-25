---
name: 幅度计算及指标与图片对齐
overview: 对照手写笔记中的幅度定义（Δ = d₂₀−d₁、幅度 = Δ的数值大小、Δ/d₂₀ 与 Δ/d₁、Δ=0→横盘），梳理 PVFRS 现状与差异，并给出具体调整方案。
todos:
  - id: todo-1769313579085-0k0ad770d
    content: ""
    status: completed
  - id: todo-1769313640469-0iwqtaf5y
    content: ""
    status: completed
  - id: todo-1769313609938-xnw9wdyuw
    content: ""
    status: completed
isProject: false
---

# 图片中幅度计算及指标 — 调整方案

## 一、图片中的定义（摘要）

| 项 | 定义 |
|----|------|
| 公式 | Δ = d₂₀ - d₁ |
| 幅度 | **Δ 的数值大小** → 幅度 |
| 比例 | **Δ/d₂₀**、**Δ/d₁** |
| 判断 | **① Δ = 0 → 横盘** |

---

## 二、PVFRS 当前实现 vs 图片

| 图片 | PVFRS 现状 | 是否一致 |
|------|------------|----------|
| Δ = d₂₀ - d₁ | [analyzers.py](backend_core/strategies/pvfrs/analyzers.py) 第 74–81 行：d₁、d₂₀ 取首尾收盘价，`macro_displacement = d20 - d1` | 一致 |
| 幅度 = Δ 的数值大小 | 仅有 **幅度系数** Δ/d（d=20 日均价），无单独的「幅度」标量 | 不一致 |
| Δ/d₂₀、Δ/d₁ | 仅实现 **Δ/d**（d=20 日均价），未实现 Δ/d₂₀、Δ/d₁ | 不一致 |
| Δ = 0 → 横盘 | 通过 Δ>0 才买、Δ<0 反转卖隐式处理；**无显式横盘状态** | 逻辑等效，未显式 |

---

## 三、建议新增 / 调整的指标

为与图片保持一致，建议在价格维度中**新增**下列计算与指标，并**保留**现有 Δ、Δ/d 等逻辑（不删除）。

### 3.1 幅度（标量）

- **定义**：幅度 = Δ 的数值大小。
- **实现**：`amplitude = abs(macro_displacement)`（即 |Δ|）；若希望带符号则可取 Δ 本身，但通常「数值大小」指绝对值。
- **放置**：在 [PriceDimensionAnalyzer.analyze](backend_core/strategies/pvfrs/analyzers.py) 的返回字典中增加 `amplitude`；若 [PVFRSIndicators](backend_core/strategies/pvfrs/models.py) 需向下游传递，可增加可选字段 `amplitude`。

### 3.2 Δ/d₂₀、Δ/d₁

- **定义**：  
- `ratio_d20` = Δ / d₂₀  
- `ratio_d1` = Δ / d₁  
- **数据来源**：d₁、d₂₀ 在 `calculate_macro_displacement` 内已计算，但未向外暴露。
- **实现**：  
- 在 [analyzers.py](backend_core/strategies/pvfrs/analyzers.py) 中，让 `calculate_macro_displacement` 返回 `(Δ, d1, d20)`，或在 `analyze` 内复用近期 data 自行算 d₁、d₂₀；  
- 在 `analyze` 的返回中增加 `d1`、`d20`、`ratio_d20`、`ratio_d1`；  
- 若 d₂₀=0 或 d₁=0，则对应比例置为 `None` 或跳过，避免除零。
- **下游**：若 [StrategyEngine](backend_core/strategies/pvfrs/strategy_engine.py) 或 [PVFRSIndicators](backend_core/strategies/pvfrs/models.py) 需要，可增加 `ratio_d20`、`ratio_d1` 字段；序列化、前展示按需带出。

### 3.3 Δ = 0 → 横盘（显式判断）

- **定义**：当 Δ ≈ 0 时，显式标记为**横盘**。
- **实现**：  
- 设阈值 `ε`（例如 `1e-6` 或可配置如 `amplitude_flat_threshold`）；  
- 若 `|Δ| < ε`，则 `is_sideways = True`（横盘），否则 `False`。  
- **放置**：在 `analyze` 的返回中增加 `is_sideways`（或 `market_state: 'sideways' | 'up' | 'down'`）；若用枚举，可先简化为布尔 `is_sideways`。
- **使用**：  
- 报告、前端展示中可显式展示「横盘」；  
- 可选：在信号或风控逻辑中引用 `is_sideways`（例如横盘时更保守），与现有 Δ>0 / Δ<0 逻辑兼容。

---

## 四、涉及文件与修改点

| 文件 | 修改内容 |
|------|----------|
| [backend_core/strategies/pvfrs/analyzers.py](backend_core/strategies/pvfrs/analyzers.py) | ① `calculate_macro_displacement` 返回 `(Δ, d1, d20)` 或在 `analyze` 中取得 d₁、d₂₀；② 在 `analyze` 中计算 `amplitude`、`ratio_d20`、`ratio_d1`、`is_sideways` 并加入返回字典 |
| [backend_core/strategies/pvfrs/models.py](backend_core/strategies/pvfrs/models.py) | 在 `PVFRSIndicators` 中**可选**增加 `amplitude`、`ratio_d20`、`ratio_d1`、`is_sideways`（若下游或序列化需要） |
| [backend_core/strategies/pvfrs/strategy_engine.py](backend_core/strategies/pvfrs/strategy_engine.py) | 构建 `PVFRSIndicators` 时传入上述新字段（若 models 已扩展） |
| [backend_core/strategies/pvfrs/config.py](backend_core/strategies/pvfrs/config.py) 或策略配置 | 可选：`amplitude_flat_threshold`（横盘判定阈值） |

不影响现有幅度系数 Δ/d、入场时机、信号过滤等逻辑；仅**新增与图片对应的指标与横盘判断**。

---

## 五、可选扩展（非必需）

- **配置化**：`amplitude_flat_threshold`、`ratio_d20` / `ratio_d1` 的合理区间（若有过滤或告警）。  
- **报告与前端**：在报告详情、选股结果等展示「幅度」、Δ/d₂₀、Δ/d₁、横盘状态，便于与笔记对照。  
- **文档**：在 [均值频率共振指标设计文档](docs/均值频率共振指标设计文档.md) 或 [PVFRS 策略说明](docs/PVFRS三维共振选股策略详细说明.md) 中补充上述定义与实现说明。

---

## 六、小结

- **Δ = d₂₀ - d₁**：已实现，无需改。  
- **幅度**：新增 `amplitude = |Δ|`。  
- **Δ/d₂₀、Δ/d₁**：新增 `ratio_d20`、`ratio_d1`；需在价格分析中暴露 d₁、d₂₀。  
- **Δ = 0 → 横盘**：新增 `is_sideways`（|Δ| < ε），并可选在展示与逻辑中使用。

按上述调整后，PVFRS 的幅度计算及指标即可与图片中的定义对齐，同时保留现有 Δ/d 等逻辑不变。