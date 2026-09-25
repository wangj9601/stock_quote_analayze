---
version: 1
slug: "frontend-markets-html"
primary_target: "frontend/markets.html"
related_targets: ["frontend/index.html","frontend/login.html","frontend/screening.html","frontend/stock.html","frontend/components/header.html"]
---

# Surface: 用户站壳 + 首批工作台

## Scope and visitor mode
- Mode: Operate
- Targets: login.html, index.html, markets.html, screening.html, stock.html（共享顶栏壳）；admin 二期
- Preserve: API / JWT / channel.* / 策略逻辑 / 数据字段 / 品牌「冰枫堂」

## Audience and job
内部投研在交易时段扫读行情、切策略选股、进个股看信号；成功 = 3 秒内找到自选/行情/选股，策略名与信号可读性不降。

## Direction contract

THESIS: 市场是活地图，自研策略是可开关叠层；拒绝深色霓虹金融终端与卡片堆砌仪表盘。

OWN-WORLD: 哑光深底 `#0f1419` + 地图灰墨 `#d9e2ec`；叠层金 `#c9a227`、航线蓝 `#2f6fed`、警戒红 `#c23b3b`。半透明叠层芯片、标图式细线网格、字号阶梯导航；无玻璃拟态、无霓虹描边。

STORY: 进站即认冰枫堂与三大频道；打开策略叠层看 GMS/RPE/URT 等印在底图上的信号；进选股/个股仍是同一套叠层语法。

FIRST VIEWPORT: 顶栏左冰枫堂字标，频道名（自选/行情/选股）用跨房可读大字号；其下一条策略叠层开关条；主区为板块/行情底图网格，右侧信号/龙头中军对向力侧栏。登录页为同一地图的图例入口，不另起营销站。

FORM: 作战标图台（seed a802e0ce；THE ROLL assigned）。Raises：字号层级；领地底色分区；交易辅助试条预览；龙头/中军对向力标注。

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Constraints
- code-first；不改后端契约
- 禁区：游戏化 HUD、FPS 准星、营销落地页第一屏
- Signature interaction: 策略叠层芯片开关，激活层改写底图行/格的信号着色与标注
