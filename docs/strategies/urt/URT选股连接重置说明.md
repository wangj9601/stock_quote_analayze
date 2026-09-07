# URT 选股生产环境「连接被重置」说明

## 现象

- 选股 → 上升趋势（URT）→ **全部 A 股**（`scope=cn`）或勾选主板/中小板后刷新。
- 浏览器：`502` 或 `ERR_CONNECTION_RESET`，前端「服务暂时不可用」或 `Failed to fetch`。

## 常见原因

1. **无预计算却走全量实时扫描**：耗时数分钟，Nginx/Gunicorn 超时 → **502**。
2. **当日已预计算但买点为 0**：旧逻辑把空结果当成「无缓存」再实时扫一遍 → 同样 502（已修）。
3. 网关超时过短 / worker 被杀 / 网络不通。

## 应用侧行为（当前）

- 带板块筛选也优先读 `urt_signal_trace`，再过滤。
- 当日已判定「全市场预计算就绪」时，即使买点为 0 也视为缓存命中，**不再实时扫**。
- 全市场且无预计算时，默认 **快速失败**（返回明确文案），避免拖到网关 502；需要旧行为时设环境变量 `URT_ALLOW_FULL_MARKET_REALTIME=1`。

## 运维核对

1. 管理端执行 **URT 预计算**（当日 `urt_signal_trace` 有数据或扫描占位）。
2. Nginx：`location ^~ /api/screening/urt-strategy` 且 `proxy_read_timeout 600s`，reload。
3. Gunicorn：`--timeout 600`。
4. 部署前端时更新 `screening.html` 中 `screening.js?v=` 缓存戳，避免浏览器仍用旧提示文案。

## 临时缓解

改用「自选股」，或缩小板块范围。
