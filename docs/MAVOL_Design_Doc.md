# MAVOL 指标集成设计文档

## 1. 项目概述
本项目旨在为股票分析系统的详情页（针对 A 股和港股）集成 **MAVOL (成交量均线)** 指标。MAVOL 指标能帮助用户更清晰地观察成交量的变化趋势，识别放量或缩量的技术形态。

## 2. 核心功能
*   在副图成交量图表中增加 **MAVOL20**（20日成交量均线）曲线。
*   支持 A 股（`stock.js`）与港股（`stock_hk.js`）的同步显示。
*   完善指标切换逻辑：仅在显示“成交量”时展示 MAVOL20，切换至 MACD、KDJ、RSI 时自动隐藏。
*   优化 Tooltip（提示框）显示，悬浮时可看精确的均线数值。

## 3. 技术实现细节

### 3.1 图表配置 (ECharts)
在 K 线图的 `series` 配置中新增 MAVOL20 系列：
*   **类型**: `line` (折线图)
*   **坐标轴**: 关联副图坐标系 (`xAxisIndex: 1`, `yAxisIndex: 1`)。
*   **样式**: 
    *   颜色: 紫色 (`#a855f7`)，以便与红绿成交量柱状图区分。
    *   宽度: `1.5`。
    *   平滑度: `smooth: true`。

### 3.2 数据加载逻辑
在 `loadKlineData` 函数中，解析后端 API 返回的 K 线数据列表：
*   **字段映射**: 从每条 K 线数据中提取 `mavol20` 字段。
*   **异常处理**: 转换 `parseFloat` 并处理 `null` 或 `undefined` 值为 `null`，确保图表不会因脏数据断裂或报错。
*   **系列更新**: 根据不同市场对应的系列索引（A 股索引 18，港股索引 13）动态更新 `option.series[i].data`。

### 3.3 显示与控制逻辑
*   **初始化**: 默认选中成交量指标，并激活 MAVOL20。
*   **图例 (Legend) 管理**: 
    *   在 `updateLegendForIndicator` 中，当 `indicator === 'vol'` 时，将 `MAVOL20` 加入图例数组，引导用户识别曲线含义。
*   **可见性切换**:
    *   `showVolumeChart`: 将 MAVOL20 系列的 `show` 设为 `true`。
    *   `showMACDChart` / `showKDJChart` / `showRSIChart`: 将 MAVOL20 系列的 `show` 设为 `false`，确保副图区域不会出现指标重叠。

### 3.4 交互优化
*   **提示框 (Tooltip)**: 更新 `formatter` 函数。当 `currentIndicator === 'vol'` 时，遍历参数并提取 `MAVOL20` 的数值，以“MAVOL20: XXX”的形式展示在成交量数值下方。

## 4. 文件变更
*   `frontend/js/stock.js`: 完善 A 股详情页 logic，修正了 RSI 系列的索引偏差。
*   `frontend/js/stock_hk.js`: 同步移植 MAVOL logic 至港股详情页，确保 UI/UX 一致性。

## 5. 测试要点
1.  **数据准确性**: 验证均线值是否与成交量趋势吻合。
2.  **联动切换**: 反复切换成交量、MACD、RSI，确认 MAVOL20 只在成交量模式下出现。
3.  **市场适配**: 分别进入 A 股和港股详情页，确认样式和数据加载均正常。
4.  **无数据处理**: 针对无 `mavol20` 历史数据的旧股票，确认页面不崩溃且不显示脏线。
