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
- 管理端（Vue/Element）不在本文件约束范围内；本系统描述用户站 MPA `body.ops-map`

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
- **Don't** 把管理端 Element 默认主题当成用户站规范。
- **Don't** 为装饰引入大圆角卡片网格仪表盘作为默认布局。
- **Don't** 用 PowerShell 默认编码改含中文的 HTML（易乱码）；改前端文案用 UTF-8 工具链。
