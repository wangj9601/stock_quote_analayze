# 3倍量观察股：运维说明

## 功能概要

- **任务1（爆量扫描）**：日 K 落库后由 `backend_core` 定时任务写入 `triple_volume_observe_stocks`，状态初始为「待观察」。
- **任务2（VSB 复核）**：对「待观察」「观察中」记录调用既有 `evaluate_stock`，命中则「交易触发」，否则「观察中」。
- **推送**：与 GMS 日报相同链路，使用 `user_push_configs` / `push_records`；`report_type` 为 `triple_volume_observe_scan`（扫描结果）与 `triple_volume_observe_eval`（复核结果）。可选字段 `wechat_notify_userids`（JSON 数组）按**单条推送任务**覆盖企业微信接收人；为空则使用 `users.wechat_userid` / `wechat_openid`。

## 环境变量（扫描范围，与订阅表解耦）

| 变量 | 说明 | 默认 |
|------|------|------|
| `TRIPLE_VOLUME_OBSERVE_ENABLED` | 是否执行扫描/复核任务内逻辑（采集进程内） | `false` |
| `TRIPLE_VOLUME_MARKETS` | 逗号分隔，`CN` / `HK` | `CN` |
| `TRIPLE_VOLUME_BOARDS` | 逗号分隔板块键，空=不限（仍排除 ST）；键与 VSB 一致如 `CYB`、`SZ_MAIN` 等 | 空 |
| `TRIPLE_VOLUME_RATIO` | 爆量倍数阈值 | `3` |

## 采集调度（APScheduler，`backend_core/data_collectors/main.py`）

| 变量 | 说明 | 默认 |
|------|------|------|
| `SCHED_TRIPLE_VOLUME_SCAN_DOW` | 扫描任务星期 | `mon-fri` |
| `SCHED_TRIPLE_VOLUME_SCAN_HOUR` / `MINUTE` | 扫描触发时刻 | `16` / `25` |
| `SCHED_TRIPLE_VOLUME_EVAL_DOW` | 复核任务星期 | `mon-fri` |
| `SCHED_TRIPLE_VOLUME_EVAL_HOUR` / `MINUTE` | 复核触发时刻 | `16` / `40` |

建议扫描略早于复核，且均在日 K 采集任务完成之后。

## 推送时间

由 `user_push_configs.push_times` 与 `PushScheduler` 驱动；为扫描与复核分别建两条配置，可设不同时间点（如 16:10 / 16:30）。

## HTTP 接口

- 用户或管理员 JWT：`GET /api/stock/triple-volume-observe/list`、`GET /api/stock/triple-volume-observe/export`
- 仅管理员：`POST /api/stock/triple-volume-observe/admin/run-scan`、`POST .../admin/run-eval`
- **用户前台**：观察股列表与导出已并入 `screening.html` → 策略「3倍量缩量突破」→ 子页「观察股池」；直达链接 `screening.html#vsb-observe`（旧 `triple_volume_observe.html` 会跳转至此）。
- **管理端**：请求走 `/api/admin/triple-volume-observe/list|export|run-scan|run-eval`（与用户站 `/api/stock/triple-volume-observe/...` 等价），便于与仅反代 `/api/admin` 的网关配置一致。

## 数据库迁移

执行仓库内迁移脚本创建 `triple_volume_observe_stocks` 及 `user_push_configs.wechat_notify_userids`，并扩展 `report_type` 字段长度（若尚未执行）。

## 企业微信

与现有推送一致：应用可信 IP、成员 `userid` 与 `PushService` 发送逻辑；本功能仅增加按任务覆盖接收人列表。
