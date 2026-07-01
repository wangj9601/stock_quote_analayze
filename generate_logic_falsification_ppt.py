from pathlib import Path

import win32com.client


OUT = Path(__file__).with_name("逻辑证伪应对系统_方法论.pptx").resolve()


def rgb(r, g, b):
    return r + g * 256 + b * 65536


BG = rgb(7, 22, 42)
PANEL = rgb(15, 39, 72)
PANEL_2 = rgb(18, 49, 88)
ACCENT = rgb(87, 245, 215)
TEXT = rgb(222, 232, 246)
MUTED = rgb(145, 160, 184)
WARN = rgb(255, 94, 102)
YELLOW = rgb(255, 205, 92)


def add_bg(slide):
    slide.FollowMasterBackground = False
    slide.Background.Fill.ForeColor.RGB = BG
    for x in range(0, 961, 40):
        line = slide.Shapes.AddLine(x, 0, x, 540)
        line.Line.ForeColor.RGB = rgb(18, 42, 76)
        line.Line.Transparency = 0.72
        line.Line.Weight = 0.5
    for y in range(0, 541, 40):
        line = slide.Shapes.AddLine(0, y, 960, y)
        line.Line.ForeColor.RGB = rgb(18, 42, 76)
        line.Line.Transparency = 0.72
        line.Line.Weight = 0.5


def set_text(shape, text, size=22, color=TEXT, bold=False):
    tf = shape.TextFrame
    tf.MarginLeft = 0
    tf.MarginRight = 0
    tf.MarginTop = 0
    tf.MarginBottom = 0
    tf.WordWrap = True
    tr = tf.TextRange
    tr.Text = text
    tr.Font.Name = "Microsoft YaHei"
    tr.Font.Size = size
    tr.Font.Color.RGB = color
    tr.Font.Bold = -1 if bold else 0
    return tr


def add_text(slide, text, x, y, w, h, size=22, color=TEXT, bold=False, align=None):
    shape = slide.Shapes.AddTextbox(1, x, y, w, h)
    tr = set_text(shape, text, size, color, bold)
    if align is not None:
        tr.ParagraphFormat.Alignment = align
    return shape


def add_rect(slide, x, y, w, h, fill=PANEL, line=rgb(39, 73, 116), radius=True):
    shape_type = 5 if radius else 1
    shape = slide.Shapes.AddShape(shape_type, x, y, w, h)
    shape.Fill.ForeColor.RGB = fill
    shape.Line.ForeColor.RGB = line
    shape.Line.Transparency = 0.25
    return shape


def add_header(slide, title, subtitle=None):
    bar = slide.Shapes.AddShape(1, 48, 48, 7, 58)
    bar.Fill.ForeColor.RGB = ACCENT
    bar.Line.Visible = 0
    add_text(slide, title, 72, 46, 780, 64, 34, ACCENT, True)
    if subtitle:
        add_text(slide, subtitle, 74, 108, 780, 28, 14, MUTED)


def add_footer(slide, n):
    add_text(slide, f"{n:02d}", 892, 500, 40, 18, 10, rgb(78, 100, 130))


def add_card(slide, title, body, x, y, w, h, mark=None, mark_color=ACCENT):
    add_rect(slide, x, y, w, h, PANEL, rgb(40, 74, 118))
    if mark:
        add_text(slide, mark, x + 22, y + 20, 42, 34, 24, mark_color, True)
    add_text(slide, title, x + 22, y + 70, w - 44, 30, 21, ACCENT, True)
    add_text(slide, body, x + 22, y + 116, w - 44, h - 130, 16, MUTED)


def add_bullets(slide, items, x, y, w, gap=56):
    for i, (head, body, color) in enumerate(items):
        yy = y + i * gap
        add_text(slide, "✓", x, yy, 28, 26, 22, color, True)
        add_text(slide, head, x + 38, yy + 2, 132, 26, 17, TEXT, True)
        add_text(slide, body, x + 168, yy + 2, w - 168, 28, 16, MUTED)


def add_arrow(slide, x1, y1, x2, y2, color=ACCENT):
    line = slide.Shapes.AddLine(x1, y1, x2, y2)
    line.Line.ForeColor.RGB = color
    line.Line.Weight = 2.5
    line.Line.EndArrowheadStyle = 3
    return line


def build():
    app = win32com.client.Dispatch("PowerPoint.Application")
    app.Visible = True
    pres = app.Presentations.Add()
    pres.PageSetup.SlideWidth = 960
    pres.PageSetup.SlideHeight = 540

    # 1
    s = pres.Slides.Add(1, 12)
    add_bg(s)
    add_text(s, "逻辑证伪应对系统", 0, 132, 960, 72, 46, ACCENT, True, 2)
    add_text(s, "判断方向之后，真正决定盈亏的是：市场证明我错了，我怎么办？", 135, 226, 690, 40, 22, TEXT, False, 2)
    add_text(s, "把预测转化为预案，把情绪转化为规则", 0, 346, 960, 28, 16, MUTED, False, 2)
    add_footer(s, 1)

    # 2
    s = pres.Slides.Add(2, 12)
    add_bg(s)
    add_header(s, "核心定义", "逻辑证伪不是猜涨跌，而是提前定义逻辑失效。")
    add_rect(s, 92, 180, 330, 190, PANEL, rgb(40, 74, 118))
    add_text(s, "普通止损", 122, 216, 250, 32, 26, WARN, True)
    add_text(s, "亏到某个比例就卖，容易被价格波动牵着走。", 122, 284, 250, 60, 20, MUTED)
    add_rect(s, 538, 180, 330, 190, PANEL, rgb(40, 74, 118))
    add_text(s, "逻辑证伪", 568, 216, 250, 32, 26, ACCENT, True)
    add_text(s, "买入理由被市场推翻，就按预案退出或降级处理。", 568, 284, 250, 60, 20, TEXT)
    add_arrow(s, 442, 276, 516, 276)
    add_footer(s, 2)

    # 3
    s = pres.Slides.Add(3, 12)
    add_bg(s)
    add_header(s, "第一步：写清楚入场逻辑", "不要只写“看涨”，要写可以被检验的条件。")
    add_card(s, "周期条件", "月线趋势向上；周线回调到支撑位；日线出现放量确认。", 80, 185, 245, 190, "1")
    add_card(s, "结构条件", "价格站上关键均线、平台或趋势线，支撑与阻力位置清晰。", 357, 185, 245, 190, "2")
    add_card(s, "环境条件", "板块资金仍在流入，大盘环境没有明显系统性风险。", 634, 185, 245, 190, "3")
    add_text(s, "逻辑越具体，越容易知道什么时候错了。", 0, 430, 960, 30, 20, ACCENT, True, 2)
    add_footer(s, 3)

    # 4
    s = pres.Slides.Add(4, 12)
    add_bg(s)
    add_header(s, "第二步：给每条逻辑设置失效条件")
    add_bullets(s, [
        ("月线失效：", "跌破 20 月线且无法收回，长期趋势假设不再成立。", ACCENT),
        ("周线失效：", "周收盘跌破关键支撑，波段持有逻辑降级。", ACCENT),
        ("日线失效：", "放量突破后缩量跌回平台，突破真实性被证伪。", ACCENT),
        ("板块失效：", "板块指数持续走弱，个股相对强度消失。", ACCENT),
    ], 100, 174, 760, 66)
    add_footer(s, 4)

    # 5
    s = pres.Slides.Add(5, 12)
    add_bg(s)
    add_header(s, "第三步：分层应对", "不要把所有波动都当成卖出信号。")
    levels = [
        ("轻微异常", "减仓观察", "日线走弱，但周线结构还没有破坏。", YELLOW),
        ("关键位失守", "执行止损", "收盘跌破预设支撑，原交易逻辑被证伪。", WARN),
        ("逻辑完全反向", "清仓停手", "周期、结构、板块同时转弱，禁止补仓摊平。", WARN),
    ]
    for i, (title, action, body, color) in enumerate(levels):
        x = 88 + i * 292
        add_rect(s, x, 188, 245, 210, PANEL, rgb(40, 74, 118))
        add_text(s, title, x + 24, 222, 190, 30, 22, color, True)
        add_text(s, action, x + 24, 272, 190, 30, 26, TEXT, True)
        add_text(s, body, x + 24, 326, 190, 52, 16, MUTED)
    add_footer(s, 5)

    # 6
    s = pres.Slides.Add(6, 12)
    add_bg(s)
    add_header(s, "第四步：交易前预案", "买入前先回答四个问题。")
    questions = [
        ("我为什么买？", "明确方向、周期、结构和资金依据。"),
        ("我错在哪里会被证明？", "写出可观察、可执行的证伪条件。"),
        ("如果错了，在哪里退出？", "提前定好关键位和收盘确认规则。"),
        ("如果对了，如何处理？", "设计加仓、止盈和持有条件。"),
    ]
    for i, (q, a) in enumerate(questions):
        y = 168 + i * 72
        add_text(s, f"{i+1}", 104, y, 34, 34, 24, ACCENT, True)
        add_text(s, q, 158, y, 270, 28, 21, TEXT, True)
        add_text(s, a, 445, y + 2, 360, 28, 17, MUTED)
    add_footer(s, 6)

    # 7
    s = pres.Slides.Add(7, 12)
    add_bg(s)
    add_header(s, "用收盘确认减少噪音", "尤其在 A 股 T+1 环境中，盘中波动不能替代确认。")
    add_card(s, "日线级别", "看当日收盘是否收回关键位，避免被盘中假跌破带偏。", 92, 190, 235, 180, "D")
    add_card(s, "周线级别", "看周五收盘是否守住支撑，决定波段逻辑是否延续。", 363, 190, 235, 180, "W")
    add_card(s, "月线级别", "看月末是否维持趋势结构，用来判断长期生态是否改变。", 634, 190, 235, 180, "M")
    add_footer(s, 7)

    # 8
    s = pres.Slides.Add(8, 12)
    add_bg(s)
    add_header(s, "一页执行清单", "把系统落到每一笔交易。")
    checks = [
        "买入理由写成具体条件，而不是一句感觉",
        "每条理由都有对应的证伪条件",
        "轻微异常、关键失守、完全反向分层处理",
        "买入前写好退出位和确认周期",
        "看错时亏得可控，看对时拿得住",
    ]
    for i, item in enumerate(checks):
        y = 176 + i * 58
        add_text(s, "□", 150, y, 28, 28, 23, ACCENT, True)
        add_text(s, item, 190, y + 3, 610, 28, 19, TEXT)
    add_text(s, "成熟系统的目标不是每次看对，而是看错时有规则。", 0, 462, 960, 28, 18, ACCENT, True, 2)
    add_footer(s, 8)

    pres.SaveAs(str(OUT))
    pres.Close()
    app.Quit()
    print(OUT)


if __name__ == "__main__":
    build()
