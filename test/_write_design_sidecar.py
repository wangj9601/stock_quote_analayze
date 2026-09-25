# -*- coding: utf-8 -*-
"""One-shot: write .impeccable/design.json and sync brief/token comments."""
from pathlib import Path
import json
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]

sidecar = {
  "schemaVersion": 2,
  "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
  "title": "Design System: 股票分析 · 冰枫堂",
  "extensions": {
    "colorMeta": {
      "ops-ground": {
        "role": "neutral",
        "displayName": "作战底",
        "canonical": "#0f1419",
        "tonalRamp": ["#070a0d", "#0f1419", "#161c24", "#1e2630", "#2a3440", "#3d4a58", "#5a6a7a", "#8b9aab"]
      },
      "ops-ground-elevated": {
        "role": "neutral",
        "displayName": "抬升面",
        "canonical": "#161c24",
        "tonalRamp": ["#0f1419", "#121820", "#161c24", "#1c2430", "#243040", "#344050", "#4a5a6a", "#6b7a8a"]
      },
      "ops-territory-a": {
        "role": "neutral",
        "displayName": "A股领地",
        "canonical": "#121820",
        "tonalRamp": ["#0c1016", "#121820", "#161c24", "#1a222c", "#243040", "#344050", "#4a5a6a", "#6b7a8a"]
      },
      "ops-territory-hk": {
        "role": "neutral",
        "displayName": "港股领地",
        "canonical": "#14161f",
        "tonalRamp": ["#0c0e14", "#14161f", "#1a1c28", "#222630", "#2e3440", "#404858", "#5a6474", "#7a8494"]
      },
      "ops-ink": {
        "role": "neutral",
        "displayName": "标图墨",
        "canonical": "#d9e2ec",
        "tonalRamp": ["#6b7a8a", "#8b9aab", "#a8b4c0", "#c0cad4", "#d0dae4", "#d9e2ec", "#e8eef4", "#f4f7fa"]
      },
      "ops-ink-muted": {
        "role": "neutral",
        "displayName": "次级墨",
        "canonical": "#8b9aab",
        "tonalRamp": ["#3d4a58", "#5a6a7a", "#6b7a8a", "#7a8a9a", "#8b9aab", "#a0aebc", "#b8c4d0", "#d0dae4"]
      },
      "ops-gold": {
        "role": "primary",
        "displayName": "叠层金",
        "canonical": "#c9a227",
        "tonalRamp": ["#3d3010", "#5c4818", "#7a6020", "#9a7a20", "#c9a227", "#d4b84a", "#e0cc70", "#efe0a8"]
      },
      "ops-route": {
        "role": "secondary",
        "displayName": "航线蓝",
        "canonical": "#2f6fed",
        "tonalRamp": ["#0e1f4a", "#163070", "#1e48a8", "#2f6fed", "#4a85f0", "#6a9ef4", "#94baf8", "#c4d6fb"]
      },
      "ops-alert": {
        "role": "secondary",
        "displayName": "警戒红",
        "canonical": "#c23b3b",
        "tonalRamp": ["#3a1010", "#5c1818", "#8a2828", "#c23b3b", "#d05555", "#dc7878", "#e8a0a0", "#f2c8c8"]
      },
      "color-rise": {
        "role": "secondary",
        "displayName": "涨色",
        "canonical": "#c23b3b",
        "tonalRamp": ["#3a1010", "#5c1818", "#8a2828", "#c23b3b", "#d05555", "#dc7878", "#e8a0a0", "#f2c8c8"]
      },
      "color-fall": {
        "role": "secondary",
        "displayName": "跌色绿",
        "canonical": "#2f9e6b",
        "tonalRamp": ["#0e2e1e", "#164830", "#1e6a48", "#2f9e6b", "#4ab080", "#6ac498", "#94d8b8", "#c4ead8"]
      },
      "color-border": {
        "role": "neutral",
        "displayName": "标图细线",
        "canonical": "rgba(217, 226, 236, 0.14)",
        "tonalRamp": [
          "rgba(217,226,236,0.06)", "rgba(217,226,236,0.10)", "rgba(217,226,236,0.14)",
          "rgba(217,226,236,0.20)", "rgba(217,226,236,0.28)", "rgba(217,226,236,0.40)",
          "rgba(217,226,236,0.55)", "rgba(217,226,236,0.72)"
        ]
      },
      "ops-overlay-film": {
        "role": "primary",
        "displayName": "金膜叠层",
        "canonical": "rgba(201, 162, 39, 0.12)",
        "tonalRamp": [
          "rgba(201,162,39,0.04)", "rgba(201,162,39,0.08)", "rgba(201,162,39,0.12)",
          "rgba(201,162,39,0.16)", "rgba(201,162,39,0.20)", "rgba(201,162,39,0.28)",
          "rgba(201,162,39,0.40)", "rgba(201,162,39,0.55)"
        ]
      }
    },
    "typographyMeta": {
      "display": {"displayName": "Display", "purpose": "页面主标（如「选股策略」）；常配 2px 金色底边。"},
      "headline": {"displayName": "Headline", "purpose": "A股/港股领地 Tab、关键区组标题。"},
      "title": {"displayName": "Title", "purpose": "卡片/面板 h3。"},
      "body": {"displayName": "Body", "purpose": "默认正文与表格字号。"},
      "label": {"displayName": "Label", "purpose": "策略芯片、频道、图例。"}
    },
    "shadows": [
      {"name": "none-default", "value": "none", "purpose": "默认抬升面：靠色阶与细线，不用阴影。"},
      {"name": "legacy-ops-map-panel", "value": "0 8px 24px rgba(0,0,0,0.28)", "purpose": "历史 ops-map-panel 残留；勿作为新默认。"}
    ],
    "motion": [
      {"name": "ease-standard", "value": "cubic-bezier(0.4, 0, 0.2, 1)", "purpose": "Tab/芯片状态切换默认缓动。"},
      {"name": "duration-fast", "value": "150ms", "purpose": "hover/active 短反馈。"},
      {"name": "duration-normal", "value": "220ms", "purpose": "频道/策略叠层切换。"}
    ],
    "breakpoints": [
      {"name": "bp-sm", "value": "480px"},
      {"name": "bp-md", "value": "768px"}
    ]
  },
  "components": [
    {
      "name": "Primary Overlay Button",
      "kind": "button",
      "refersTo": "button-primary",
      "description": "金膜叠层主按钮：稀缺使用，标示关键操作。",
      "html": "<button type=\"button\" class=\"ds-btn-primary\">执行筛选</button>",
      "css": ".ds-btn-primary{font-family:Barlow Condensed,Noto Sans SC,sans-serif;font-weight:600;letter-spacing:.06em;background:rgba(201,162,39,.12);color:#c9a227;border:1px solid rgba(201,162,39,.45);border-radius:1px;padding:8px 16px;cursor:pointer;transition:background 150ms cubic-bezier(.4,0,.2,1),border-color 150ms}.ds-btn-primary:hover{background:rgba(201,162,39,.2);border-color:rgba(201,162,39,.65)}.ds-btn-primary:focus-visible{outline:2px solid #2f6fed;outline-offset:2px}"
    },
    {
      "name": "Ghost Button",
      "kind": "button",
      "refersTo": "button-ghost",
      "description": "透明幽灵按钮，用于次要操作。",
      "html": "<button type=\"button\" class=\"ds-btn-ghost\">取消</button>",
      "css": ".ds-btn-ghost{font-family:Noto Sans SC,sans-serif;background:transparent;color:#d9e2ec;border:1px solid rgba(217,226,236,.14);border-radius:1px;padding:8px 16px;cursor:pointer;transition:background 150ms,border-color 150ms}.ds-btn-ghost:hover{background:rgba(217,226,236,.06);border-color:rgba(217,226,236,.28)}.ds-btn-ghost:focus-visible{outline:2px solid #2f6fed;outline-offset:2px}"
    },
    {
      "name": "Strategy Overlay Chip",
      "kind": "chip",
      "refersTo": "chip-strategy",
      "description": "策略叠层开关芯片（GMS/RPE/URT 等）。",
      "html": "<button type=\"button\" class=\"ds-chip-strategy\" aria-pressed=\"false\">GMS</button> <button type=\"button\" class=\"ds-chip-strategy is-active\" aria-pressed=\"true\">RPE</button>",
      "css": ".ds-chip-strategy{font-family:Barlow Condensed,Noto Sans SC,sans-serif;font-size:.8125rem;font-weight:600;letter-spacing:.08em;background:transparent;color:#8b9aab;border:1px solid rgba(217,226,236,.14);border-radius:1px;padding:3px 9px;cursor:pointer;transition:background 150ms,color 150ms,border-color 150ms}.ds-chip-strategy:hover{color:#d9e2ec;border-color:rgba(217,226,236,.28)}.ds-chip-strategy.is-active,.ds-chip-strategy[aria-pressed=true]{background:rgba(201,162,39,.12);color:#c9a227;border-color:rgba(201,162,39,.45)}.ds-chip-strategy:focus-visible{outline:2px solid #2f6fed;outline-offset:2px}"
    },
    {
      "name": "Elevated Panel",
      "kind": "card",
      "refersTo": "panel-elevated",
      "description": "不透明抬升面板；禁止白底上盖浅墨。",
      "html": "<section class=\"ds-panel\"><h3 class=\"ds-panel-title\">板块强度</h3><p class=\"ds-panel-body\">主区信号叠层可读，不依赖阴影。</p></section>",
      "css": ".ds-panel{background:#161c24;color:#d9e2ec;border:1px solid rgba(217,226,236,.14);border-radius:2px;padding:16px 18px;box-shadow:none}.ds-panel-title{margin:0 0 8px;font-family:Noto Sans SC,sans-serif;font-size:1.05rem;font-weight:600}.ds-panel-body{margin:0;font-size:14px;line-height:1.5;color:#8b9aab}"
    },
    {
      "name": "Ops Input",
      "kind": "input",
      "refersTo": "input-field",
      "description": "深底输入框，焦点用航线蓝双环。",
      "html": "<label class=\"ds-field\"><span class=\"ds-field-label\">股票代码</span><input class=\"ds-input\" type=\"text\" placeholder=\"600519\" value=\"\"></label>",
      "css": ".ds-field{display:flex;flex-direction:column;gap:6px;font-family:Noto Sans SC,sans-serif}.ds-field-label{font-family:Barlow Condensed,Noto Sans SC,sans-serif;font-size:.8125rem;font-weight:600;letter-spacing:.08em;color:#8b9aab}.ds-input{background:rgba(0,0,0,.28);color:#d9e2ec;border:1px solid rgba(217,226,236,.14);border-radius:2px;padding:6px 10px;font-size:14px}.ds-input::placeholder{color:#6b7a8a}.ds-input:focus{outline:none;border-color:#2f6fed;box-shadow:0 0 0 2px rgba(47,111,237,.35)}"
    },
    {
      "name": "Territory Tab Active",
      "kind": "nav",
      "refersTo": "tab-territory-active",
      "description": "A股/港股领地 Tab：金膜激活态。",
      "html": "<nav class=\"ds-territory\" role=\"tablist\"><button class=\"ds-tab\" role=\"tab\">港股</button><button class=\"ds-tab is-active\" role=\"tab\" aria-selected=\"true\">A股</button></nav>",
      "css": ".ds-territory{display:inline-flex;gap:4px}.ds-tab{font-family:Barlow Condensed,Noto Sans SC,sans-serif;font-size:1.125rem;font-weight:600;letter-spacing:.06em;background:transparent;color:#8b9aab;border:1px solid transparent;border-radius:1px;padding:6px 12px;cursor:pointer}.ds-tab:hover{color:#d9e2ec}.ds-tab.is-active{background:rgba(201,162,39,.12);color:#c9a227;border-color:rgba(201,162,39,.45)}.ds-tab:focus-visible{outline:2px solid #2f6fed;outline-offset:2px}"
    },
    {
      "name": "Channel Wordmark Nav",
      "kind": "nav",
      "refersTo": None,
      "description": "顶栏频道：跨房可读大字号；当前频道金色强调。",
      "html": "<header class=\"ds-chrome\"><a class=\"ds-brand\" href=\"#\">冰枫堂</a><nav class=\"ds-channels\"><a class=\"ds-ch\" href=\"#\">自选</a><a class=\"ds-ch is-current\" href=\"#\">行情</a><a class=\"ds-ch\" href=\"#\">选股</a></nav></header>",
      "css": ".ds-chrome{display:flex;align-items:baseline;gap:24px;padding:12px 16px;background:#0f1419;border-bottom:1px solid rgba(217,226,236,.14)}.ds-brand{font-family:Barlow Condensed,Noto Sans SC,sans-serif;font-weight:700;font-size:1.25rem;letter-spacing:.04em;color:#d9e2ec;text-decoration:none}.ds-channels{display:flex;gap:16px}.ds-ch{font-family:Barlow Condensed,Noto Sans SC,sans-serif;font-size:1.125rem;font-weight:600;letter-spacing:.06em;color:#8b9aab;text-decoration:none}.ds-ch:hover{color:#d9e2ec}.ds-ch.is-current{color:#c9a227;border-bottom:2px solid #c9a227}"
    },
    {
      "name": "Dragon / Mid-Army Badge",
      "kind": "custom",
      "refersTo": None,
      "description": "龙头/中军对向力标签：不做成装饰贴纸。",
      "html": "<span class=\"ds-badge ds-badge-dragon\">龙头</span> <span class=\"ds-badge ds-badge-army\">中军</span>",
      "css": ".ds-badge{display:inline-block;font-family:Barlow Condensed,Noto Sans SC,sans-serif;font-size:.75rem;font-weight:600;letter-spacing:.08em;border-radius:1px;padding:2px 8px;border:1px solid transparent}.ds-badge-dragon{background:rgba(194,59,59,.18);color:#c23b3b;border-color:rgba(194,59,59,.4)}.ds-badge-army{background:rgba(47,111,237,.16);color:#6a9ef4;border-color:rgba(47,111,237,.4)}"
    }
  ],
  "narrative": {
    "northStar": "作战标图台",
    "overview": (
      "内部投研工作台把市场当作一张活地图：行情底色是哑光作战底，"
      "GMS / RPE / URT / 大小资金 / 通道突破等自研策略是可开关的战略叠层。"
      "气质贴近作战室标图，而不是深色霓虹金融终端或营销落地页——"
      "无玻璃拟态、无卡片堆砌、无游戏化战体。\n\n"
      "密度服务于扫读与切策略，刻意远离宽松杂志编辑房或电商货架。"
      "叠层金色是装置色而非装饰色。底图已收敛为极淡暗角、无满屏方格；"
      "多页共享同一套抬升面语法。品牌「冰枫堂」是壳层定位信号，不是口号眉题。"
    ),
    "keyCharacteristics": [
      "哑光深作战底 + 标图灰墨；叠层金与航线蓝作稀缺激活与焦点",
      "策略叠层芯片/Tab 作为开关出场，而非游戏 HUD",
      "不透明抬升面盖住底图，杜绝浅墨压白底的反模式",
      "A 股涨红跌绿与龙头/中军用对向力色系，不作装饰墙",
      "管理端（Vue/Element）不在本文件约束范围内；本系统面向用户站 MPA body.ops-map"
    ],
    "rules": [
      {"name": "The Overlay Gold Rule", "body": "金色只服务激活/开关/关键叠层，不作大面积色块或正文替代墨色。", "section": "colors"},
      {"name": "The No White Paste Rule", "body": "用户站禁止保留业务 CSS 的白底卡片；一律抬升到 --ops-ground-elevated 与可控可读墨色。", "section": "colors"},
      {"name": "The A-Share Ink Rule", "body": "涨用 #c23b3b，跌用 #2f9e6b；不随西式反转市场习惯。", "section": "colors"},
      {"name": "The Mark Ladder Rule", "body": "频道与关键标题用 Barlow Condensed 字号阶梯可读，不用大色块吼叫。", "section": "typography"},
      {"name": "The Gutter Map Rule", "body": "周围只留给页边呼吸；可读内容落在实色抬升面。", "section": "layout"},
      {"name": "The Flat Acetate Rule", "body": "叠层靠细线与色阶辨认「醋酸片」层次，不靠动态模糊或投影。", "section": "elevation"},
      {"name": "The Hairline Rule", "body": "控件圆角 ≤ 2px；全圆角也不是默认语法。", "section": "shapes"}
    ],
    "dos": [
      "Do 新页面挂 body.ops-map，并按序加载 design-tokens → ops-shell → ops-data → 业务 CSS → *-ops → ops-surfaces（最后覆盖层）。",
      "Do 用 --ops-ink / --ops-ink-muted 写字；涨跌只用 --color-rise / --color-fall。",
      "Do 面板用 --ops-ground-elevated 实色；标签/芯片可用金膜半透明底，禁止浅业务底浅字。",
      "Do 策略名可读优先；叠层金稀缺，留给可开关策略。"
    ],
    "donts": [
      "Don't 再引入满屏装饰网格或白卡片糊底。",
      "Don't 做成 FPS/电竞 HUD、霓虹描边、金色无限发光皮肤。",
      "Don't 把管理端 Element 默认皮肤当作用户站规范。",
      "Don't 为装饰堆大圆角卡片；卡片不是默认布局。",
      "Don't 用 PowerShell 默认编码写含中文的 HTML（乱码）；前端以 UTF-8 文件操作为准。"
    ]
  }
}

out = ROOT / ".impeccable" / "design.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("wrote", out, "bytes", out.stat().st_size)

brief = ROOT / ".impeccable" / "decision" / "surface-brief-shell.md"
t = brief.read_text(encoding="utf-8")
t2 = t.replace(
  "半透明叠层芯片、标图式细线网格、字号阶梯导航；无玻璃拟态、无霓虹描边。",
  "半透明叠层芯片、极淡暗角底图（无满屏方格）、字号阶梯导航；无玻璃拟态、无霓虹描边。"
).replace(
  "主区为板块/行情底图网格，右侧信号/龙头中军对向力侧栏。",
  "主区为板块/行情抬升工作面，右侧信号/龙头中军对向力侧栏。"
)
if t2 != t:
  brief.write_text(t2, encoding="utf-8")
  print("updated surface brief")
else:
  print("brief unchanged")

tok = ROOT / "frontend" / "css" / "design-tokens.css"
tt = tok.read_text(encoding="utf-8")
old = (
  "/* 作战标图台 — design tokens (Impeccable direction a802e0ce)\n"
  " * 底图策略：稀疏主网格 + 暗角大气；行情/首页略强，选股/分析等阅读页几乎无网；\n"
  " * 内容抬升面不透明，网格只在卡缝/页边露出。\n"
  " */"
)
new = (
  "/* 作战标图台 — design tokens (Impeccable direction a802e0ce)\n"
  " * 底图策略：无满屏方格；仅极淡暗角大气。抬升面不透明，靠色阶与细线分层。\n"
  " */"
)
if old in tt:
  tok.write_text(tt.replace(old, new), encoding="utf-8")
  print("updated design-tokens comment")
else:
  print("tokens comment skip")
