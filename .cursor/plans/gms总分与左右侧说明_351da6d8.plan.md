---
name: GMS总分与左右侧说明
overview: 基于仓库内 `GMSIndicatorsCalculator`、`GMSSignalDetector` 与 `GMSStrategyEngine` 的实现：**总分 35 且标为「左侧」在当前逻辑下可以同时成立**；总分由双模块取 **max** 而非相加；左右侧由独立的布尔信号决定，且 **左侧优先于右侧**。
todos: []
isProject: false
---

# GMS：35 分 +「左侧」是否正常、判定条件与可优化点

## 1. 「35 分还判定左侧」是否正常？

**正常**，原因有两层：

### 1.1 总分不是两模块相加

[`indicators_calculator.py`](e:/wangxw/股票分析软件/编码/stock_quote_analayze/backend_core/strategies/gms/indicators_calculator.py) 中明确：

```136:137:e:/wangxw/股票分析软件/编码/stock_quote_analayze/backend_core/strategies/gms/indicators_calculator.py
            # 综合总分：取两模块较高者，用于排序
            score_total = max(score_accumulation, score_momentum)
```

因此你截图里「均值收敛 35 + 动量溢出 -10」时，界面上的 **总分 = max(35, -10) = 35**，而不是 25。动量模块为负 **不会拉低** 展示用的总分（但仍会体现在「动量溢出态」明细里）。

### 1.2 「左侧/右侧」与总分是两条线

[`strategy_engine.py`](e:/wangxw/股票分析软件/编码/stock_quote_analayze/backend_core/strategies/gms/strategy_engine.py) 里先算 `detect_left_buy` / `detect_right_buy`，再写 `buy_type`：

```111:123:e:/wangxw/股票分析软件/编码/stock_quote_analayze/backend_core/strategies/gms/strategy_engine.py
                left = self.detector.detect_left_buy(ind)
                right = self.detector.detect_right_buy(ind)
                ...
                buy_type = ""
                if left:
                    buy_type = "左侧"
                elif right:
                    buy_type = "右侧"
```

也就是说：**买点类型不由「总分是否高」决定**，而由检测器规则决定；总分只用于排序/过滤（如 `min_score`）。因此 **35 分可以同时对应「左侧」**，只要左侧条件满足且 `left==True`。

---

## 2. 当前代码里「左/右侧」的实际条件

实现位于 [`signal_detector.py`](e:/wangxw/股票分析软件/编码/stock_quote_analayze/backend_core/strategies/gms/signal_detector.py)。

### 2.1 左侧 `detect_left_buy`

- **若** `accumulation_grade` 为 **`S` 或 `A`**（由均值收敛态子分与阈值 85/70 决定，见计算器），则 **跳过** 下列「前置 F/Z、delta」检查，但仍要满足后面的粘合与地量条件。
- **否则**（无 S/A）需同时：
  - `rising_days > 0`
  - **F > Z**（`falling_days > rising_days`）
  - **delta < 0**（注释：d20 相对窗口起点下跌）
- **共通硬条件**：
  - `abs(ratio_d20) < ratio_d20_abs_max`（默认 **0.015**，即 \|Δ/d₂₀\| < 1.5%）
  - `volume_ratio < volume_ratio_max`（默认 **0.8**）

其中 **`ratio_d20` = Δ/d₂₀**（宏观位移除以**当日收盘价**），定义见 [`mean_frequency_calculator.py`](e:/wangxw/股票分析软件/编码/stock_quote_analayze/backend_core/utils/mean_frequency_calculator.py) 与 PVFRS 注释；**与界面上的 Δ₂₀/d（价格相对均线的乖离，常记作 bias）不是同一指标**。

`volume_ratio` 在 [`data_loader.py`](e:/wangxw/股票分析软件/编码/stock_quote_analayze/backend_core/strategies/gms/data_loader.py) 为 **当日量 / 20 日均量**（缩量时 < 1）。

### 2.2 右侧 `detect_right_buy`

- **若** `momentum_grade` 为 **`全速切入` 或 `分批买入`**（动量子分阈值 90/80），则跳过部分价格条件，但仍需 **量比**。
- **否则**需：
  - `instant_deviation > 0`（**d₂₀ > d**，站在均线上方）
  - `delta > 0`（窗口内宏观位移向上）
  - `volume_ratio >= volume_ratio_min`（默认 **1.5**，放量）

### 2.3 二者同时满足时

代码 **先判左侧**，左侧为真则 **`buy_type` 永远是「左侧」**（右侧被覆盖）。

---

## 3. 与你截图案例（广信股份类）的一致性

典型状态：价格在均线下方（`instant_deviation < 0`）、动量子分为负 → **右侧条件不成立**；若同时 \|Δ/d₂₀\| 仍在 1.5% 内、量比 < 0.8、且无 S/A 时 F>Z 且 delta<0，则 **左侧可成立**。  
界面若同时展示 **Δ₂₀/d 较大（如约 -5%）** 与 **「左侧」**，并不一定矛盾：左侧用的是 **Δ/d₂₀**，不是 **(d₂₀−d)/d**。

---

## 4. 可优化空间（产品与逻辑层面，非本次改代码）

| 方向 | 说明 |
|------|------|
| **概念对齐** | 避免用户把「总分」理解成「两模块之和」；可在 UI 标注「总分 = max(蓄势, 动量)」或显示「主导模块」。 |
| **指标命名** | 详情里同时展示 **Δ/d₂₀** 与 **(d₂₀−d)/d** 并注明符号，减少与「粘合」直觉的冲突。 |
| **低分左侧** | 总分 35 低于配置里常见的 `watch_threshold`（默认 60，见 [`gms_config.json`](e:/wangxw/股票分析软件/编码/stock_quote_analayze/backend_core/strategies/gms/gms_config.json)），若仍出现在列表里，多半是 **min_score=0** 或未按关注线过滤；可按产品要求收紧「展示左侧」与「入选列表」的规则。 |
| **若将来要改公式** | 可选：总分改为加权/求和、或要求「左侧」时 `score_accumulation` 至少达到某阈值；均属**策略变更**，需回测验证。 |

---

## 5. 文档对照

[`docs/GMS策略买点判定标准说明文档.md`](e:/wangxw/股票分析软件/编码/stock_quote_analayze/docs/GMS策略买点判定标准说明文档.md) 第 2.3 / 3.3 节与上述代码一致；第 4 节说明选股与追溯共用同一套检测器。
