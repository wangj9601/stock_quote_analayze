---
name: 股票分析 · 冰枫堂
description: 作战标图台 — 自研策略叠层的内部投研工作台
colors:
  ops-ground: "#0f1419"
  ops-ground-elevated: "#161c24"
  ops-territory-a: "#121820"
  ops-territory-hk: "#14161f"
  ops-ink: "#d9e2ec"
  ops-ink-muted: "#8b9aab"
  ops-gold: "#c9a227"
  ops-route: "#2f6fed"
  ops-alert: "#c23b3b"
  color-rise: "#c23b3b"
  color-fall: "#2f9e6b"
  color-border: "rgba(217, 226, 236, 0.14)"
  ops-overlay-film: "rgba(201, 162, 39, 0.12)"
typography:
  display:
    fontFamily: "Barlow Condensed, Noto Sans SC, sans-serif"
    fontSize: "clamp(1.75rem, 3vw, 2.5rem)"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.04em"
  headline:
    fontFamily: "Barlow Condensed, Noto Sans SC, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.06em"
  title:
    fontFamily: "Noto Sans SC, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "1.05rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "normal"
  body:
    fontFamily: "Noto Sans SC, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "Barlow Condensed, Noto Sans SC, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.08em"
rounded:
  hairline: "1px"
  panel: "2px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.ops-overlay-film}"
    textColor: "{colors.ops-gold}"
    rounded: "{rounded.hairline}"
    padding: "8px 16px"
  button-primary-hover:
    backgroundColor: "rgba(201, 162, 39, 0.2)"
    textColor: "{colors.ops-gold}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ops-ink}"
    rounded: "{rounded.hairline}"
    padding: "8px 16px"
  chip-strategy:
    backgroundColor: "{colors.ops-overlay-film}"
    textColor: "{colors.ops-gold}"
    rounded: "{rounded.hairline}"
    padding: "3px 9px"
  chip-strategy-active:
    backgroundColor: "{colors.ops-overlay-film}"
    textColor: "{colors.ops-gold}"
  panel-elevated:
    backgroundColor: "{colors.ops-ground-elevated}"
    textColor: "{colors.ops-ink}"
    rounded: "{rounded.panel}"
    padding: "16px 18px"
  input-field:
    backgroundColor: "rgba(0, 0, 0, 0.28)"
    textColor: "{colors.ops-ink}"
    rounded: "{rounded.panel}"
    padding: "6px 10px"
  date-picker-indicator:
    filter: "invert(1) brightness(1.4)"
    filterHover: "invert(1) brightness(1.65)"
    note: "原生 type=date 日历按钮；深底强制 color-scheme:dark + filter 提亮"
  tab-territory-active:
    backgroundColor: "{colors.ops-overlay-film}"
    textColor: "{colors.ops-gold}"
    rounded: "{rounded.hairline}"
---

# Design System: 股票分析 · 冰枫堂

## Overview

**Creative North Star: "作战标图台"**

内部投研工作台把市场当作一张活地图：板块与个股是哑光底图，GMS / RPE / URT / 做小做底 / 通道突破等自研策略是可开关的战术叠层。气质来自作战室标图与研判地图，而不是霓虹交易终端或营销落地页。材料语汇是半透明醋酸叠片、标图色铅笔线、哑光作战板。

密度服务于扫读：频道与策略短码靠字号阶梯跨房可读；涨跌与命中用语义色，不用装饰色喊话。底图已收敛为极淡暗角、无满屏方格，阅读页与数据页共用同一套抬升面语法。品牌署名「冰枫堂」是壳层恒定信号，不是可删眉题。

**Key Characteristics:**
- 哑光深作战板 + 地图灰墨字色，金色仅作叠层激活与焦点
- 策略以芯片/Tab 叠层开关出现，不做成游戏 HUD
- 不透明抬升面板盖住底图；白卡贴深底是反模式
- A 股涨红跌绿语义固定；龙头/中军用对向力关系呈现
- 上文只约束用户站 MPA `body.ops-map`。管理端浅色壳层见文末「管理端：浅色值班台」，不进入本文件色板与组件令牌

## Colors

哑光深底上的克制标图色：金是叠层与焦点，蓝是航线/链接，红是警戒与涨，绿仅用于跌。

### Primary
- **叠层金** (`#c9a227`): 激活 Tab、策略芯片描边、页标题下划线、主按钮字色；稀缺使用。
- **航线蓝** (`#2f6fed`): 链接、航线强调、部分中军/信息态；`--ops-route`。

### Secondary
- **警戒红 / 涨色** (`#c23b3b`): 涨、命中偏多、告警；与 A 股习惯一致。
- **跌色绿** (`#2f9e6b`): 仅跌/回流绿语义，不做大面积品牌绿。

### Neutral
- **作战板** (`#0f1419`): 页面底 `--ops-ground`。
- **抬升面** (`#161c24`): 卡片/工作台 `--ops-ground-elevated`；必须不透明。
- **A 股领地** (`#121820`) / **港股领地** (`#14161f`): 极淡领地差，不用描边 chrome 分区。
- **地图墨** (`#d9e2ec`): 主文字 `--ops-ink`。
- **次级墨** (`#8b9aab`): 说明、meta、未激活 Tab。
- **标图细线** (`rgba(217, 226, 236, 0.14)`): 边框与分割。

### Named Rules
**The Overlay Gold Rule.** 金色只服务激活/焦点/策略叠层，任意屏金色面积应明显少于正文墨色。

**The No White Paste Rule.** 深底上禁止遗留业务 CSS 的白底卡片；一律抬升到 `--ops-ground-elevated` 并强制可读墨色。

**The A-Share Ink Rule.** 涨用 `#c23b3b`，跌用 `#2f9e6b`；不随主题反转红绿习惯。

## Typography

**Display Font:** Barlow Condensed（频道、策略短码、页标题标记）
**Body Font:** Noto Sans SC（正文、表格、表单）

**Character:** 冷凝标记字扫策略短码，宋体感无衬线中文承载密表与说明；层级靠字号与字距，不靠描边霓虹。

### Hierarchy
- **Display** (700, `clamp(1.75rem, 3vw, 2.5rem)`, letter-spacing `0.04em`): 页标题（如「选股策略」「智能分析中心」）；标题下 2px 金线。
- **Headline** (600, `1.125rem`, letter-spacing `0.06em`): A股/港股领地 Tab、关键分区标题。
- **Title** (600, `~1.05rem`): 卡片/区块 h3。
- **Body** (400, `14px`, line-height `1.5`): 默认正文字号。
- **Label** (600, `0.8125rem`, letter-spacing `0.08em`): 策略芯片、短码、徽标。

### Named Rules
**The Mark Ladder Rule.** 频道与策略名优先用 Barlow Condensed 字号阶梯跨距离可读，不用大块色块喊话。

## Layout

Operate 模式：顶栏（冰枫堂 + 频道）→ 可选策略叠层条 → 主内容容器。用户站为 MPA；共享壳在 `header` + `design-tokens` + `ops-shell` / `ops-data` / `ops-responsive` / `ops-surfaces`。

- 主列常见 `max-width` 约 `1400–1600px` 居中；密表可横向滚动。
- 断点：`--bp-md: 768px`，`--bp-sm: 480px`；手机显示底栏 `.ops-bottom-nav`，策略叠层条需可横滑。
- 间距节奏：`4 / 8 / 16 / 24 / 32`；面板内边距约 `16–18px`。
- 底图：全站无满屏方格；仅极淡径向暗角。内容面板不透明，网格不穿字。

### Named Rules
**The Gutter Map Rule.** 氛围只留在页边与缝；可读表面必须是实色抬升面。

## Elevation & Depth

默认平坦：深度靠色阶（ground → elevated）与 1px 边框，不靠大阴影堆叠。近期已去掉面板重阴影，避免「白块浮在深底」的廉价感。

### Shadow Vocabulary
- **Default panels:** `box-shadow: none`（或等价无阴影）。
- **Legacy ops-map-panel（慎用）:** `0 8px 24px rgba(0,0,0,0.28)` — 仅历史壳类，新面板勿默认开启。

### Named Rules
**The Flat Acetate Rule.** 叠层靠边框与金色描边表达「醋酸片」，不靠玻璃拟态或多层投影。

## Shapes

直角偏多的标图几何：面板 `2px`，芯片/按钮 `1px`。避免大圆角 pill 作为默认控件（涨跌语义小标签除外可略圆，但仍克制）。

边框为细线 `1px solid var(--color-border)`；激活态金边或底边金条。

### Named Rules
**The Hairline Rule.** 控件圆角 ≤ `2px`；全圆胶囊不是默认语法。

**The Control Indicator Rule.** 作战板上原生日期/时间控件的日历图标，以及 `<select>` / `.ops-select` 下拉箭头，必须与 `--ops-ink` 同级可读。不要用 `invert` 滤镜硬拧系统图标（`color-scheme: dark` 下会越拧越暗）；统一换成 `--ops-date-picker-icon` / `--ops-select-chevron`（静止墨色、hover/焦点金色）SVG。实现集中在 `design-tokens.css`，`ops-surfaces.css` 末级重申；后续样式用 `background-color` 而非 `background` 简写。勿在各页单独糊补丁。

## Components

实现落点：`frontend/css/design-tokens.css`、`ops-shell.css`、`ops-data.css`、`ops-surfaces.css`、各 `*-ops.css`。壳类名 `body.ops-map` + `data-channel`。

### Buttons
- **Shape:** 直角短倒角 (`1px`)
- **Primary:** 透明/金膜底 + 金边金字（`--ops-overlay-film`）
- **Ghost / Secondary:** 透明底 + 浅边 + 墨字；hover 金边
- **Focus:** `--ops-focus` 双环（深底 + 金）

### Chips（策略叠层 / 信号）
- **Style:** 金边 + 金膜底 + Barlow 短码；激活同色加强，不换成高饱和填充块
- **State:** 未激活墨灰边；激活金边；禁止霓虹外发光

### Cards / Containers
- **Corner:** `2px`
- **Background:** `#161c24` 不透明
- **Border:** `rgba(217,226,236,0.14)`
- **Shadow:** 默认无
- **Internal padding:** `~16–18px`

### Inputs / Fields
- **Style:** `rgba(0,0,0,0.28)` 底 + 浅边 + 墨字
- **Focus:** 金环 `--ops-focus`
- **Radius:** `2px`
- **Date / time:** `color-scheme: dark`；WebKit 日历弹出按钮用 `--ops-date-picker-indicator-filter`（`invert(1) brightness(1.4)`）提亮，禁止深底上残留近黑默认图标
- **实现:** `frontend/css/design-tokens.css`（令牌 + 全局 `::-webkit-calendar-picker-indicator`）；`ops-data.css` 同步输入底色

### Navigation
- **顶栏:** 冰枫堂署名恒定；频道字号大于正文；当前频道金色强调
- **领地 Tab（A股/港股）:** 底边金条 + 金膜底
- **策略 Tab / 分析 Tab:** 金边激活语法与芯片一致
- **手机:** 底栏频道切换；叠层条横滑

### Signature: 策略叠层开关
短码芯片条（GMS / RPE / URT…）作为可开关叠层；激活层改写底图表意着色与标注，而不是另开皮肤主题。

### Signature: 龙头 / 中军
用对向力/角色标签呈现关系（金/航线蓝区分角色），避免装饰性徽章墙。

## Do's and Don'ts

### Do:
- **Do** 新页面挂 `body.ops-map`，并按序加载 `design-tokens` → `ops-shell` → `ops-data` → 业务 CSS → `*-ops` → `ops-surfaces`（最后覆盖层）。
- **Do** 用 `--ops-ink` / `--ops-ink-muted` 写字；涨跌只用 `--color-rise` / `--color-fall`。
- **Do** 面板用 `--ops-ground-elevated` 实色；标签/芯片在深底上用暗半透明底，不用浅灰底浅字。
- **Do** 保留「冰枫堂」署名与策略短码可发现性。

### Don't:
- **Don't** 复活满屏方格底纹或白卡贴深底。
- **Don't** 做成 FPS/电竞 HUD、玻璃拟态、紫色霓虹金融皮肤。
- **Don't** 把管理端 Element 默认主题当成用户站规范，也不要把用户站深色作战板涂到管理端。
- **Don't** 在管理端用紫、靛装饰色标状态或当前项。
- **Don't** 为装饰引入大圆角卡片网格仪表盘作为默认布局。
- **Don't** 用 PowerShell 默认编码改含中文的 HTML（易乱码）；改前端文案用 UTF-8 工具链。

## 管理端：浅色值班台

这一节只描述 Vue 管理端壳层。上面的色板、字体、圆角和组件令牌仍然只属于用户站。管理端颜色写在壳层本地变量里，不提升进文首 frontmatter。

**Creative North Star: "浅色值班台"**

日间办公的密度：安静、密、可扫读。侧栏按工作分组，当前位置和危险操作要一眼能认。品牌「冰枫堂」只做署名和当前位置，不负责给整页上色。表格、表单、日期、标签页和确认框继续用 Element Plus。

**Key Characteristics:**
- 浅灰底、白侧栏；内容区平面，轻阴影只给侧栏、抽屉和展开条
- 品牌字是枫金墨，当前项底是暖纸；涨红跌绿沿用用户站语义色
- 四组菜单：今日看板、策略、行情与采集、访问与审计
- 窄屏用顶栏加抽屉；宽屏收起侧栏后，面包屑仍标出当前位置

### Colors
- **枫金墨** (`#6b5420`): 侧栏署名、面包屑品牌、当前菜单字色、焦点环。浅底上不用用户站叠层金 `#c9a227` 做正文。
- **暖纸** (`#f4efe3`): 当前子菜单底色。分组按钮在包含当前页时只加粗，不铺这块底色。
- **次级说明** (`#4b5563`): 侧栏副题、页脚备案。不用更浅的灰做正文。
- **涨 / 跌**: 沿用上文 `color-rise` / `color-fall`。壳层变量是 `--admin-rise`、`--admin-fall`，与 `--admin-brand`、`--admin-brand-soft` 一起挂在 `.admin-layout`。

**The Duty Desk Rule.** 管理端保持浅色操作密度。品牌只署名和标出当前位置，不把页面涂成作战标图台。

**The Maple Ink Rule.** 浅底上的品牌字用枫金墨，当前项用暖纸。用户站叠层金不作为管理端正文色。

### Typography
管理端不加载 Barlow Condensed。署名用系统无衬线：侧栏「冰枫堂」`22px` / `700` / 字距 `0.08em`；面包屑品牌字距 `0.06em`。菜单 `14px`，子项 `13px`，顶栏页名 `15px` / `600`。正文、表格和表单交给 Element Plus 默认字号。

### Layout
实现在 `admin/src/views/AdminLayout.vue` 与 `admin/src/components/layout/NavMenuGroup.vue`。

- 宽屏侧栏 `256px`；`≤1024px` 收到 `224px`。主区左边距与侧栏同宽。
- `≥769px` 可把侧栏收到屏外，左侧中部留展开条。面包屑「冰枫堂 / 当前页」留在内容区顶部。
- `≤768px` 侧栏改为抽屉，顶栏显示页名和用户，面包屑隐藏。遮罩 `rgba(0, 0, 0, 0.45)`。抽屉打开时主区不可操作；Esc 或点遮罩关闭，焦点回到菜单按钮。
- 内容区内边距：默认 `24px`，`≤1024px` 为 `20px`，`≤768px` 为 `12px`，`≤480px` 为 `8px`。

### Elevation & Depth
内容区不抬起。深度只出现在壳层边缘。

- **侧栏:** Tailwind 默认大阴影，`0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)`。
- **展开条:** `2px 0 8px rgba(0, 0, 0, 0.06)`。

**The Shell Shadow Rule.** 内容区保持平面。轻阴影只给侧栏、抽屉遮罩和展开条。

### Shapes
壳层按钮圆角 `8px`。展开条只圆右侧，`0 10px 10px 0`。菜单项圆角 `8px`。Element 控件保持 Element 自己的圆角，不套用户站 `1px` / `2px` 标图几何。

### Components
#### Navigation
- 分组按钮：透明底，悬停浅灰。组内有当前页时，字色改为枫金墨并加粗。
- 当前子项：暖纸底、枫金墨字、`600`。`aria-current="page"`。
- 焦点：`2px` 枫金墨描边，外扩 `2px`。收起、展开、菜单按钮和备案链接同样。
- 退出登录是普通按钮，确认框用警告，不用危险色。

#### 当前位置
桌面面包屑和窄屏顶栏使用同一页名。报告管理会带上当前标签名。未进侧栏的 PVFRS 策略、PVFRS 管理和报告详情也有页名，但不因此出现在菜单里。

### Do
- **Do** 新的管理端页放进现有四组菜单，并让面包屑能叫出页名。
- **Do** 表格、表单、日期、标签页和确认框用 Element Plus。
- **Do** 涨跌使用 `--admin-rise` / `--admin-fall`。

### Don't
- **Don't** 把管理端涂成深色作战板，或改用 Barlow Condensed 和 `1px` 标图圆角。
- **Don't** 用紫、靛装饰色标状态、图标或当前项。
- **Don't** 把退出登录做成危险按钮。危险色留给会覆盖数据的确认。
