---
name: PVFRS价格幅度对照说明
overview: PVFRS 三维共振策略已考虑图片中的价格幅度（Δ = d₂₀ - d₁、幅度、相对比例及 Δ=0 横盘）。本计划对照笔记与实现，说明对应关系及唯一差异点。
todos: []
isProject: false
---

# PVFRS 价格幅度对照说明

## 结论

**PVFRS 三维共振策略已经考虑图片中的价格幅度。** 实现与设计文档在 Δ、幅度、相对比例及 Δ=0 横盘判断上均与笔记一致；唯一差异为比例分母：策略统一使用 **Δ/d**（d = 20 日均价），而笔记中另外给出 **Δ/d₁、Δ/d₂₀**。

---

## 图片定义与策略实现的对应关系

### 1. Δ = d₂₀ - d₁（宏观位移）

| 项目 | 图片 | PVFRS 实现 |
|------|------|------------|
| 公式 | Δ = d₂₀ - d₁ | 一致 |
| d₁ | 观察周期起始价格 | [analyzers.py](backend_core/strategies/pvfrs/analyzers.py) 第 75 行：`d1 = recent_data[0].close`（第 1 天收盘价） |
| d₂₀ | 观察周期末位价格 | 第 78 行：`d20 = recent_data[-1].close`（第 20 天收盘价） |
| Δ | 宏观位移 | 第 81 行：`macro_displacement = d20 - d1` |

设计文档 [均值频率共振指标设计文档.md](docs/均值频率共振指标设计文档.md) 第 32–44 行同样定义 Δ = d₂₀ - d₁，并说明 Δ>0 / Δ<0 / Δ=0 的含义。

---

### 2. 「Δ 的数值大小」→ 幅度（amplitude）

| 项目 | 图片 | PVFRS 实现 |
|------|------|------------|
| 含义 | Δ 的数值大小表示幅度 | 通过 **幅度系数** 使用 Δ 的相对大小 |
| 比例 | Δ/d₂₀、Δ/d₁ | 策略采用 **Δ/d**（d = 20 日平均价格） |

**幅度在策略中的用法：**

- [models.py](backend_core/strategies/pvfrs/models.py) 第 59 行：`amplitude_ratio: float  # 幅度系数 Δ₂₀/d`
- [strategy_engine.py](backend_core/strategies/pvfrs/strategy_engine.py) 第 502–514 行：`_calculate_amplitude_ratio(macro_displacement, avg_price_20d)` → `macro_displacement / avg_price_20d`
- [entry_timing_optimizer.py](backend_core/strategies/pvfrs/entry_timing_optimizer.py) 第 527–565 行：`calculate_amplitude_coefficient` 计算 Δ/d，并做幅度校验、等待判断（系数过小→等波幅放大，过大→等回调）
- [signal_generator.py](backend_core/strategies/pvfrs/signal_generator.py) 第 611–637 行：`_validate_amplitude_coefficient` 约束幅度系数在 1%–30%

[量价频三维共振演化策略指南.md](docs/量价频三维共振演化策略指南.md) 与 [均值频率共振指标设计文档.md](docs/均值频率共振指标设计文档.md) 第 223–225 行均写明：**幅度校验** 使用 **Δ/d**，系数过小表示「平」、需等待波幅放大。因此，**「幅度」在策略中已被显式考虑**。

---

### 3. Δ = 0 → 横盘

| 项目 | 图片 | PVFRS 实现 |
|------|------|------------|
| 判断 | ① Δ = 0 则为横盘 | 设计文档第 49 行：**Δ = 0：市场横盘整理** |
| 买入 | - | 买入要求 **Δ > 0**（[resonance_detector.py](backend_core/strategies/pvfrs/resonance_detector.py) 等处的 `macro_displacement_positive`） |
| 卖出 | - | Δ < 0 视为反转：[risk_manager.py](backend_core/strategies/pvfrs/risk_manager.py) 第 585 行 `macro_reversal = macro_displacement < 0` |

因此，**Δ = 0 在逻辑上被当作横盘**：既不满足买入条件（Δ>0），也不触发 Δ<0 的卖出反转；代码通过 Δ≤0 不买入、Δ<0 反转卖出实现了与「Δ=0 横盘」一致的处理。

---

### 4. 比例 Δ/d₂₀、Δ/d₁ 与策略中的 Δ/d

- **图片**：给出 **Δ/d₂₀**、**Δ/d₁** 两个比例。
- **策略**：统一使用 **Δ/d**，d = 20 日平均价格（即 MA20）。

设计文档与代码中幅度校验、入场时机均基于 **Δ/d**。未单独实现 Δ/d₁、Δ/d₂₀，但 **Δ/d** 同样刻画「相对幅度」，与笔记思路一致，只是分母选取不同。

---

## 小结

- **Δ = d₂₀ - d₁**：与图片、设计文档完全一致，且直接用于买卖逻辑。  
- **幅度**：通过 **幅度系数 Δ/d** 及 1%–30% 的校验、入场时机优化（波幅不足则等待）体现。  
- **Δ = 0 横盘**：在设计文档中明文写出；代码通过 Δ>0 才买、Δ<0 反转卖， implicitly 将 Δ=0 视为横盘。

若希望与笔记在形式上完全对齐，可考虑：

- 在策略或报告中**显式**输出「Δ=0 → 横盘」的说明；和/或  
- 新增 **Δ/d₁、Δ/d₂₀** 作为可选指标，与现有 **Δ/d** 一并展示或用于后续扩展。  

这些属于增强项，不影响当前「已考虑价格幅度」的结论。