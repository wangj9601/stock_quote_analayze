from pathlib import Path

import win32com.client


OUT = Path(__file__).with_name("判断股票方向分析框架_汇报版.pptx").resolve()


def rgb(r, g, b):
    return r + g * 256 + b * 65536


BG = rgb(7, 22, 42)
PANEL = rgb(15, 39, 72)
PANEL_2 = rgb(19, 49, 88)
ACCENT = rgb(87, 245, 215)
TEXT = rgb(221, 232, 246)
MUTED = rgb(142, 157, 183)
RED = rgb(255, 78, 88)
GREEN = rgb(87, 245, 215)


def set_text(shape, text, size=24, color=TEXT, bold=False, name="Microsoft YaHei"):
    tf = shape.TextFrame
    tf.MarginLeft = 0
    tf.MarginRight = 0
    tf.MarginTop = 0
    tf.MarginBottom = 0
    tf.WordWrap = True
    tr = tf.TextRange
    tr.Text = text
    tr.Font.Name = name
    tr.Font.Size = size
    tr.Font.Color.RGB = color
    tr.Font.Bold = -1 if bold else 0
    return tr


def add_text(slide, text, x, y, w, h, size=24, color=TEXT, bold=False):
    shape = slide.Shapes.AddTextbox(1, x, y, w, h)
    set_text(shape, text, size, color, bold)
    return shape


def add_rect(slide, x, y, w, h, fill=PANEL, line=rgb(36, 66, 105), radius=True):
    shape_type = 5 if radius else 1
    shape = slide.Shapes.AddShape(shape_type, x, y, w, h)
    shape.Fill.ForeColor.RGB = fill
    shape.Line.ForeColor.RGB = line
    shape.Line.Transparency = 0.25
    return shape


def add_header(slide, title, subtitle=None):
    bar = slide.Shapes.AddShape(1, 44, 52, 7, 58)
    bar.Fill.ForeColor.RGB = ACCENT
    bar.Line.Visible = 0
    add_text(slide, title, 68, 50, 760, 72, 33, ACCENT, True)
    if subtitle:
        add_text(slide, subtitle, 70, 111, 760, 28, 13, MUTED, False)


def add_bg(slide):
    slide.FollowMasterBackground = False
    slide.Background.Fill.ForeColor.RGB = BG
    # Subtle grid.
    for x in range(0, 961, 32):
        ln = slide.Shapes.AddLine(x, 0, x, 540)
        ln.Line.ForeColor.RGB = rgb(20, 44, 77)
        ln.Line.Transparency = 0.7
        ln.Line.Weight = 0.5
    for y in range(0, 541, 32):
        ln = slide.Shapes.AddLine(0, y, 960, y)
        ln.Line.ForeColor.RGB = rgb(20, 44, 77)
        ln.Line.Transparency = 0.7
        ln.Line.Weight = 0.5


def add_card(slide, title, body, x, y, w, h, icon=None):
    add_rect(slide, x, y, w, h, PANEL, rgb(39, 73, 116))
    if icon:
        add_text(slide, icon, x + 22, y + 26, 50, 42, 28, ACCENT, True, )
    add_text(slide, title, x + 22, y + 84, w - 44, 34, 22, ACCENT, True)
    add_text(slide, body, x + 22, y + 132, w - 44, h - 150, 17, MUTED, False)


def add_footer(slide, n):
    add_text(slide, f"{n:02d}", 895, 500, 36, 18, 10, rgb(76, 98, 130), False)


def add_bullets(slide, items, x, y, w, gap=52):
    for idx, (head, body) in enumerate(items):
        yy = y + idx * gap
        add_text(slide, "✓", x, yy, 28, 26, 22, ACCENT, True)
        add_text(slide, head, x + 36, yy + 2, 120, 26, 18, TEXT, True)
        add_text(slide, body, x + 150, yy + 2, w - 150, 28, 17, MUTED, False)


def build():
    app = win32com.client.Dispatch("PowerPoint.Application")
    app.Visible = True
    pres = app.Presentations.Add()
    pres.PageSetup.SlideWidth = 960
    pres.PageSetup.SlideHeight = 540

    layouts = []

    # 1 Cover
    s = pres.Slides.Add(1, 12)
    add_bg(s)
    add_text(s, "判断股票方向", 0, 116, 960, 80, 48, ACCENT, True)
    s.Shapes(s.Shapes.Count).TextFrame.TextRange.ParagraphFormat.Alignment = 2
    add_text(s, "多维度技术分析与周期共振框架", 0, 206, 960, 36, 22, MUTED, False)
    s.Shapes(s.Shapes.Count).TextFrame.TextRange.ParagraphFormat.Alignment = 2
    add_text(s, "建立专业、稳健的投资决策逻辑", 0, 294, 960, 30, 18, ACCENT, False)
    s.Shapes(s.Shapes.Count).TextFrame.TextRange.ParagraphFormat.Alignment = 2
    add_footer(s, 1)

    # 2 Overview
    s = pres.Slides.Add(2, 12)
    add_bg(s)
    add_header(s, "多维度分析体系概览")
    add_card(s, "宏观与板块", "先判断市场风向，再寻找景气度高、资金关注度高的核心赛道。", 70, 170, 185, 220, "≋")
    add_card(s, "技术与结构", "用趋势线、水平位、均线与形态，构建股价运行地图。", 285, 170, 185, 220, "⌁")
    add_card(s, "量价博弈", "成交量验证价格运行的真实性，排除无量反弹和虚假突破。", 500, 170, 185, 220, "▥")
    add_card(s, "周期共振", "把月线、周线、日线组合起来，统一全局方向与局部时机。", 715, 170, 185, 220, "◷")
    add_footer(s, 2)

    # 3 Macro
    s = pres.Slides.Add(3, 12)
    add_bg(s)
    add_header(s, "宏观环境与板块效应", "先看大方向，再挑强赛道，最后落到个股。")
    add_card(s, "大盘趋势", "上证/深成指是否处于上升通道？若市场在下降趋势中，应降低交易频率和仓位。", 72, 190, 250, 190, "◎")
    add_card(s, "板块景气度", "所属行业是否处于政策风口或业绩释放期？板块向上是个股爆发的前提。", 355, 190, 250, 190, "▰")
    add_card(s, "资金共识", "观察市场热线是否向该板块集中。板块效应越强，个股胜率越高。", 638, 190, 250, 190, "↗")
    add_footer(s, 3)

    # 4 Structure
    s = pres.Slides.Add(4, 12)
    add_bg(s)
    add_header(s, "技术结构与趋势线", "寻找图表中的结构防线。")
    # Simple chart sketch
    chart = add_rect(s, 72, 170, 390, 255, rgb(246, 248, 251), rgb(62, 87, 125), False)
    for yy in [220, 270, 320, 370]:
        ln = s.Shapes.AddLine(82, yy, 452, yy); ln.Line.ForeColor.RGB = rgb(218, 224, 233); ln.Line.Weight = 1
    pts = [(88,330),(130,300),(172,318),(214,270),(256,285),(298,238),(340,252),(382,220),(430,232)]
    for a, b in zip(pts, pts[1:]):
        ln = s.Shapes.AddLine(a[0], a[1], b[0], b[1]); ln.Line.ForeColor.RGB = rgb(0, 155, 120); ln.Line.Weight = 2
    trend = s.Shapes.AddLine(92, 345, 430, 215); trend.Line.ForeColor.RGB = RED; trend.Line.Weight = 2
    add_bullets(s, [
        ("趋势线：", "连接阶段性低点，划定多头生命线。"),
        ("阻力/支撑：", "识别前期密集成交区、缺口和重要平台。"),
        ("关键均线：", "重点关注 20 日/60 日/120 日均线的回踩力度。"),
        ("右侧交易：", "价格确认突破结构后再考虑介入，不接飞刀。"),
    ], 520, 180, 380, 56)
    add_footer(s, 4)

    # 5 Fibonacci
    s = pres.Slides.Add(5, 12)
    add_bg(s)
    add_header(s, "黄金分割与支撑位量化", "用关键比例刻画回调深度。")
    add_text(s, "0.382", 135, 188, 260, 70, 54, ACCENT, True)
    add_text(s, "强势回调位", 158, 260, 240, 32, 20, MUTED, False)
    add_text(s, "0.618", 135, 330, 260, 70, 54, ACCENT, True)
    add_text(s, "核心支撑黄金位", 135, 402, 260, 32, 20, MUTED, False)
    add_rect(s, 520, 176, 360, 240, PANEL, rgb(40, 74, 118))
    add_text(s, "Fibonacci Retracement", 550, 205, 310, 32, 24, ACCENT, True)
    add_text(s, "测量前一波上涨的深度。若回调在 0.5 以下止跌并放量，说明趋势仍强。", 550, 270, 300, 58, 18, MUTED)
    add_text(s, "P支撑 = P高 - (P高 - P低) × Ratio", 550, 350, 300, 26, 16, TEXT)
    add_text(s, "依托黄金分割位建立防守，而非盲目用固定百分比止损。", 550, 390, 300, 28, 16, MUTED)
    add_footer(s, 5)

    # 6 Volume-price
    s = pres.Slides.Add(6, 12)
    add_bg(s)
    add_header(s, "量价关系辨别趋势真伪", "量在价先，成交量是验证方向的关键证据。")
    labels = [("缩量上涨", "风险", RED, 165), ("放量上涨", "确立", GREEN, 345), ("放量下跌", "转空", RED, 325), ("缩量回调", "洗盘", GREEN, 150)]
    y = 178
    for i, (lab, tag, col, width) in enumerate(labels):
        yy = y + i * 58
        add_text(s, f"{lab}（{tag}）", 105, yy + 5, 140, 24, 16, TEXT, True)
        base = add_rect(s, 245, yy, 420, 28, rgb(35, 61, 98), rgb(35, 61, 98), False)
        base.Line.Visible = 0
        bar = add_rect(s, 245, yy, width, 28, col, col, False)
        bar.Line.Visible = 0
    add_text(s, "量价判断", 710, 188, 150, 32, 24, ACCENT, True)
    add_text(s, "成交量放大并配合价格上行，代表资金共识形成；无量反弹通常只是离场机会。", 710, 238, 190, 90, 18, MUTED)
    add_text(s, "重点排除：缩量冲高、放量滞涨、关键位跌破后反抽无量。", 710, 344, 190, 70, 17, TEXT)
    add_footer(s, 6)

    # 7 Month
    s = pres.Slides.Add(7, 12)
    add_bg(s)
    add_header(s, "月线看格局：长线生态", "过滤日内杂波，先判断个股是否处于长期底部。")
    add_bullets(s, [
        ("宏观视野：", "月线决定大方向，是判断底部与上升周期的第一步。"),
        ("核心均线：", "20 月线是牛熊分界线，斜率向下时不轻易重仓。"),
        ("大周期背离：", "月线级别 MACD 底背离，反转确定性更高。"),
    ], 92, 190, 470, 70)
    # Decorative rising arrow
    for i, h in enumerate([48, 76, 110, 150]):
        add_rect(s, 650 + i * 55, 395 - h, 38, h, rgb(20, 126, 144), rgb(35, 185, 190), False).Line.Visible = 0
    arr = s.Shapes.AddLine(625, 330, 865, 190)
    arr.Line.ForeColor.RGB = ACCENT
    arr.Line.Weight = 5
    arr.Line.EndArrowheadStyle = 3
    add_footer(s, 7)

    # 8 Week
    s = pres.Slides.Add(8, 12)
    add_bg(s)
    add_header(s, "周线看波段：中期买卖", "在大方向正确时寻找更优的波段窗口。")
    add_card(s, "中期动能", "周线金叉或突破 30 周线，通常预示中级反弹启动；关注“周线二次金叉”。", 72, 190, 250, 195, "⌕")
    add_card(s, "波段防守", "周五收盘若不跌破周线支撑，则持有逻辑成立，避免被日内骗线震出。", 355, 190, 250, 195, "⚓")
    add_card(s, "介入时机", "周线级别找支撑位，日线级别用 KDJ 等指标完成精准打击。", 638, 190, 250, 195, "⚖")
    add_footer(s, 8)

    # 9 Resonance
    s = pres.Slides.Add(9, 12)
    add_bg(s)
    add_header(s, "多周期共振策略体系", "大周期看涨，小周期买跌。")
    add_rect(s, 72, 190, 390, 210, PANEL, rgb(39, 73, 116))
    add_text(s, "共振逻辑图", 105, 220, 260, 34, 24, TEXT, True)
    steps = [("1", "月线定势：", "均线多头，趋势向上。"), ("2", "周线寻机：", "缩量回调至支撑位。"), ("3", "日线出击：", "弱转强，放量站稳关键点。")]
    for i, (no, head, body) in enumerate(steps):
        yy = 280 + i * 42
        add_text(s, no, 105, yy, 26, 24, 20, ACCENT, True)
        add_text(s, head, 150, yy + 2, 110, 24, 17, TEXT, True)
        add_text(s, body, 260, yy + 2, 180, 24, 17, MUTED)
    add_rect(s, 520, 190, 368, 210, PANEL, rgb(39, 73, 116))
    add_text(s, "核心法则", 552, 228, 190, 32, 24, ACCENT, True)
    add_text(s, "通过高级周期的稳定性过滤低级周期噪音，只在共振点交易，盈亏比才最有优势。", 552, 300, 280, 70, 19, MUTED)
    add_footer(s, 9)

    # 10 T+1
    s = pres.Slides.Add(10, 12)
    add_bg(s)
    add_header(s, "A 股实战：T+1 机制应对", "买入前先设计隔日风险处理方案。")
    add_bullets(s, [
        ("尾盘决策法：", "14:30 以后趋势明朗再决定是否介入，规避次日低开风险。"),
        ("结构化止损：", "依托关键位而非固定百分比。逻辑证伪，果断离场。"),
        ("不接飞刀：", "宁愿错过底部第一根阳线，也要等待形态确认。"),
    ], 120, 182, 690, 76)
    add_rect(s, 98, 420, 760, 42, rgb(11, 55, 72), rgb(38, 93, 118), False)
    add_text(s, "实战口诀：先看能不能亏得明白，再看能不能赚得漂亮。", 128, 432, 700, 22, 18, ACCENT, True)
    add_footer(s, 10)

    # 11 Checklist
    s = pres.Slides.Add(11, 12)
    add_bg(s)
    add_header(s, "交易前检查清单", "把判断方向落实为可执行的流程。")
    checks = [
        "大盘处于上升通道或风险可控区间",
        "板块有政策、业绩或资金共识支撑",
        "个股趋势线、均线、支撑位清晰",
        "回调位置与黄金分割/平台支撑匹配",
        "成交量验证突破或止跌的真实性",
        "月线、周线、日线至少两个周期共振",
        "入场、止损、止盈方案在买入前写清楚",
    ]
    for i, item in enumerate(checks):
        x = 98 if i < 4 else 520
        y = 170 + (i % 4) * 62
        add_text(s, "□", x, y, 28, 28, 22, ACCENT, True)
        add_text(s, item, x + 38, y + 3, 330, 26, 17, TEXT, False)
    add_footer(s, 11)

    # 12 Closing
    s = pres.Slides.Add(12, 12)
    add_bg(s)
    add_text(s, "建立您的决策逻辑", 0, 132, 960, 68, 44, ACCENT, True)
    s.Shapes(s.Shapes.Count).TextFrame.TextRange.ParagraphFormat.Alignment = 2
    add_text(s, "判断方向只是第一步，建立基于“逻辑证伪”的应对系统才是生存之道。", 115, 236, 730, 38, 22, TEXT, False)
    s.Shapes(s.Shapes.Count).TextFrame.TextRange.ParagraphFormat.Alignment = 2
    add_text(s, "理性投资 | 稳健复利", 0, 352, 960, 24, 16, ACCENT, False)
    s.Shapes(s.Shapes.Count).TextFrame.TextRange.ParagraphFormat.Alignment = 2
    add_footer(s, 12)

    pres.SaveAs(str(OUT))
    pres.Close()
    app.Quit()
    print(OUT)


if __name__ == "__main__":
    build()
