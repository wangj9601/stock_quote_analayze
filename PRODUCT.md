# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

公司内部投研与员工。在工作场景下使用本系统做行情跟踪、策略选股、个股/板块分析、复盘与交易辅助决策；对外个人投资者不是第一受众。

## Product Purpose

「股票分析」是冰枫堂面向内部用户的 Web 股票分析与辅助决策平台。用户通过行情中心、自选股、多策略选股、智能分析、资讯与报告推送完成日常投研与交易准备；产品提供分析辅助与交易辅助能力，不以券商实盘撮合为目标。成功标准是内部用户能稳定依赖自研策略与分析闭环完成选股、观察与复盘。

## Positioning

差异化在于自研多策略体系，而非通用行情终端。核心策略与能力包括但不限于：GMS、RPE、URT、做小做底、通道突破，以及仓库中已落地的其他策略（如 PVFRS、一阳穿三线、SBBR、VSB、CSB、CAN SLIM 等）。板块「龙头 / 中军」、策略信号追溯与复盘报告是产品机制的一部分。

## Operating Context

- 双端：用户站（原生 HTML/CSS/JS MPA）与管理端（Vue）；可同域部署（如 `/` 与 `/admin/`）。
- 主导航工作流：首页 → 自选股 → 行情 → 选股 → 分析 → 资讯 → 我的。
- 市场覆盖：A 股、港股、ETF（部分港股能力仍在演进）。
- 内部推送：企业微信 / 邮件报告（偏公司内部）。
- 生产域名线索：`www.icemaplecity.com` / `icemaplecity.com`。

## Capabilities and Constraints

- 能力：行情与排行、自选股、多策略选股、个股详情（K 线/资金/资讯）、板块详情、策略信号追溯、智能分析与复盘报告、管理端用户/数据/回测/推送运营。
- 约束：产品定位为分析辅助与交易辅助；不将「真实券商下单撮合」写成已交付能力。
- 术语需保持稳定：GMS、RPE、URT、做小做底、通道突破、龙头、中军、RS Rating、前复权，以及权限前缀 `channel.*`。
- 权限：JWT；角色含 `standard` / `admin`；频道/Tab/按钮级权限。
- 技术栈既有事实：FastAPI（`backend_api`）、`backend_core` 采集与策略、PostgreSQL；用户前端 MPA + ECharts；管理端 Vue 3 + TypeScript + Vite + Element Plus。

## Brand Commitments

- 产品称呼：「股票分析」。
- 必须保留品牌署名：**冰枫堂** / **北京冰枫堂商贸有限公司**。
- 登录与首页等入口以公司品牌为可见署名；语气偏专业投研工具，而非 C 端消费营销站。

## Evidence on Hand

- 需求与设计：`docs/design/需求分析.md`、`docs/design/latest_system_design.md` 等。
- 用户/管理手册：`docs/admin/用户使用手册.md`、`docs/admin/管理后台说明与使用指南.md`。
- 品牌资产：`frontend/img/logo.svg`；登录/首页 title 与「冰枫堂」文案。
- 策略与运维文档：`docs/README.md` 索引下的策略/推送/部署说明。
- 不得虚构：客户证言、对外付费套餐、未实现的原生 App、未确认的合规认证。

## Product Principles

1. 内部投研优先：界面与信息架构服务公司内部日常选股、观察与复盘，而非对外营销转化。
2. 策略即产品：自研策略体系（GMS、RPE、URT、做小做底、通道突破等）是核心差异，命名与追溯链路应可发现、可复核。
3. 辅助而非撮合：明确提供分析辅助与交易辅助，不暗示已具备券商级实盘下单。
4. 品牌署名不可丢：冰枫堂 / 北京冰枫堂商贸有限公司在关键入口保持可见。
5. 术语与权限稳定：策略短码、板块角色词与 `channel.*` 权限模型不因界面改版随意改名。
