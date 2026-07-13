# URT 上升趋势策略实现设计

## 1. 策略定义

产品名：**上升趋势策略**；短码：**urt**（Upward Right-side Trend）。

来源：会议纪要《股票交易策略会议纪要》《20260710 A股交易策略讨论》。

| 规则 | 说明 |
|------|------|
| 站上 MA20 | 收盘价 ≥ 20 日简单均线 |
| 连阳 | 4 日内 ≥3 阳 **或** 5 日内 ≥4 阳（阳线：`close > open`） |
| 量能 | 当日量 ≥ 近 20 日均量（不含当日）× `volume_multiple`（默认 2.5） |
| 得分 | 默认 `min_score=70` |
| 换手/量比 | 默认关闭；管理端可启用硬筛 |

交易纪律（写入配置，供回测扩展）：价格止损 5%–10%、连跌 3 日离场、涨 25%–30% 后高点回撤 5% 止盈。

与 GMS 差异：不做左侧吸附；数据源为 `historical_quotes`（现算 MA），不依赖 `mean_frequency_resonance_indicators`。

## 2. 模块结构（对齐 GMS/VSB 垂直切片）

```
backend_core/strategies/urt/
  config.py / urt_config.json
  data_loader.py
  indicators.py / scoring.py / signal_detector.py
  strategy_engine.py
  frontend_interface.py

backend_api/
  models.py                 # URTStrategyConfig → urt_strategy_configs
  admin/urt_admin_routes.py # /api/admin/urt
  stock/stock_screening_routes.py  # GET /api/screening/urt-strategy

frontend/screening.html + js/screening.js  # Tab data-strategy="urt"
admin/  # /urt-management 参数配置页
```

## 3. API

### 选股

`GET /api/screening/urt-strategy`

主要 Query：`scope`(all|watchlist)、`limit`、`date`、`config_id`、`volume_multiple`、`min_score`、`boards`、`use_turnover`、`use_volume_ratio`。

响应：

```json
{
  "success": true,
  "data": [{ "code", "name", "signal_date", "close", "ma20", "yang_count_4", "yang_count_5", "volume_multiple", "score", ... }],
  "total": 0,
  "strategy_name": "上升趋势策略",
  "search_date": "YYYY-MM-DD",
  "parameters": {}
}
```

### 管理端

- `GET/POST /api/admin/urt/strategy-configs`
- `GET/PUT /api/admin/urt/strategy-configs/{id}`
- `GET /api/admin/urt/default-params`
- `POST /api/admin/urt/screen-preview`

## 4. 权限

权限码：

- `channel.screening.tab.urt` — 选股页「上升趋势」Tab
- `channel.screening.tab.urt.btn.refresh` — 刷新筛选
- `channel.screening.tab.urt.btn.export` — 导出 CSV

注册表：`frontend/js/permission-registry.js`、`backend_api/permission_registry_data.py`（`PERMISSION_TAB_MAP.urt`）。

行为：

- 前端 `PermissionEngine.decorateStrategyTabs` 为 Tab/内容区/刷新/导出挂载 `data-perm`，无权限则隐藏
- `ScreeningPage.switchStrategy` 无 Tab 权限时拒绝切换
- 后端启动时 `ensure_permissions_from_registry`：把注册表缺失项写入 DB，并给 **admin / standard** 补齐缺少的注册表权限（不影响其他自定义角色）
- 自定义角色：管理端「权限资源」同步后，在角色权限中勾选上述 URT 码

## 5. 与 GMS 对照

| 能力 | GMS | URT（本期） |
|------|-----|-------------|
| 选股引擎 | 有 | 有 |
| 参数多版本 | 有 | 有（`urt_strategy_configs`） |
| 前台 Tab | 有 | 有 |
| Admin 配置 | 有 | 有（精简） |
| 信号 trace / 观察股 / 回测中心 | 有 | 预留（纪律函数已在 `signal_detector.evaluate_exit_rules`） |

## 6. 默认配置

见 `backend_core/strategies/urt/urt_config.json`。

## 7. 测试

`test/test_urt_strategy.py`：连阳计数、量能、硬筛、得分、止损/止盈路径。
