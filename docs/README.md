# 文档索引

本目录按功能模块归档。入口见下表；策略类文档在 `strategies/<短码>/` 下。

## 目录一览

| 目录 | 内容 |
|------|------|
| [strategies/](strategies/) | 选股/交易策略设计、规则、回测与运维说明 |
| [prod/](prod/) | 环境说明、部署运维、Nginx 模板与迁机手册 |
| [design/](design/) | 系统需求、总体设计与实现总览 |
| [admin/](admin/) | 管理后台与用户使用手册 |
| [data/](data/) | 数据采集、AKShare/ETF/港股、相关 API 说明 |
| [notifications/](notifications/) | 推送通知、报表服务 |
| [indicators/](indicators/) | 技术指标与无穷成本均线等 |
| [features/](features/) | 成交量异动榜、行业板块等功能说明 |
| [fixed/](fixed/) | 历史问题修复记录与专项说明（归档） |
| [specs/](specs/) | 规格/任务文档（如一阳穿三线） |
| [sql/](sql/) | SQL 脚本 |
| [images/](images/)、[image/](image/) | 架构图与文档配图 |
| [notes/](notes/) | 草稿、流程图、提示词等杂项 |
| [chat_history/](chat_history/) | 本地导出对话（默认 gitignore，不入仓） |

## 策略入口（strategies/）

| 子目录 | 策略 | 主要入口 |
|--------|------|----------|
| [gms/](strategies/gms/) | GMS 均值引力 / 动量 | `GMS_STRATEGY_IMPLEMENTATION_DESIGN.md`、`GMS_STATE_DETECTION_RULES.md`、回测手册 |
| [urt/](strategies/urt/) | URT 上升趋势 | 业务简化版、`URT_STRATEGY_IMPLEMENTATION_DESIGN.md`、回测说明、与 GMS 对比方案 |
| [rpe/](strategies/rpe/) | RPE 比价效应 | 业务简化版、信号计算规则、实现设计 |
| [sbbr/](strategies/sbbr/) | SBBR 做小做底 | 业务简化版、信号计算规则 |
| [vsb/](strategies/vsb/) | VSB 3 倍量缩量突破 | 设计与使用手册 |
| [pvfars/](strategies/pvfars/) | PVFRS/PVFARS 量价频共振 | 指标设计、演化指南、重构说明 |
| [specs/one-yang-three-lines-strategy/](specs/one-yang-three-lines-strategy/) | 一阳穿三线 | requirements / design / tasks |

## 运维与环境（prod/）

- `环境说明.md` — 端口、环境变量、同步与敏感配置说明  
- `系统维护手册.md` — 部署、备份、故障排查总册  
- `windows-cvm-one-click-deploy.md` / `centos-migration-runbook.md` — 部署与迁机  
- `nginx.conf` — 生产 Nginx 模板（与仓库根 `nginx.conf` 同步）；`nginx.legacy.conf` 为根目录旧版归档  
- `Nginx配置与修复指南.md`、`新版服务启动脚本.txt`、`triple_volume_observe_ops.md` 等  

## 其它常用入口

- 系统设计/需求：`design/系统设计.md`、`design/需求分析.md`、`design/系统实现.md`  
- 管理端 / 用户：`admin/管理后台说明与使用指南.md`、`admin/用户使用手册.md`  
- 推送：`notifications/公司内部用户_企业微信与邮件推送配置指南.md`  
- 采集：`data/AKShare使用与连接问题指南.md`、`data/ETF历史迁移脚本使用说明.md`  

## 说明

- 目录命名沿用既有英文风格（`prod` / `fixed` / `design` / `specs`）。  
- 支撑位/阻力位等历史修复文档仍在 `fixed/`，未拆散。  
- 引用文档时请使用新路径；`.cursor/plans/` 内旧链接未批量改动。  
