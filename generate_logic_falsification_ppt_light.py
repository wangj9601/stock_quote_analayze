from pathlib import Path

import win32com.client


OUT = Path(__file__).with_name("逻辑证伪应对系统_现代简约浅色版.pptx").resolve()


def rgb(r, g, b):
    return r + g * 256 + b * 65536


BG = rgb(248, 251, 253)
INK = rgb(28, 42, 58)
MUTED = rgb(101, 116, 135)
FAINT = rgb(229, 238, 244)
CARD = rgb(255, 255, 255)
ACCENT = rgb(22, 177, 166)
ACCENT_2 = rgb(49, 109, 221)
WARN = rgb(228, 82, 92)
AMBER = rgb(230, 162, 45)


def set_text(shape, text, size=22, color=INK, bold=False):
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


def add_text(slide, text, x, y, w, h, size=22, color=INK, bold=False, align=None):
    shape = slide.Shapes.AddTextbox(1, x, y, w, h)
    tr = set_text(shape, text, size, color, bold)
    if align is not None:
        tr.ParagraphFormat.Alignment = align
    return shape


def add_rect(slide, x, y, w, h, fill=CARD, line=FAINT, radius=True):
    shape_type = 5 if radius else 1
    shape = slide.Shapes.AddShape(shape_type, x, y, w, h)
    shape.Fill.ForeColor.RGB = fill
    shape.Line.ForeColor.RGB = line
    shape.Line.Weight = 1
    return shape


def add_bg(slide):
    slide.FollowMasterBackground = False
    slide.Background.Fill.ForeColor.RGB = BG
    band = slide.Shapes.AddShape(1, 0, 0, 960, 8)
    band.Fill.ForeColor.RGB = ACCENT
    band.Line.Visible = 0


def add_header(slide, title, subtitle=None):
    add_text(slide, title, 66, 48, 760, 50, 31, INK, True)
    line = slide.Shapes.AddShape(1, 66, 104, 54, 4)
    line.Fill.ForeColor.RGB = ACCENT
    line.Line.Visible = 0
    if subtitle:
        add_text(slide, subtitle, 66, 122, 760, 26, 14, MUTED)


def add_footer(slide, n):
    add_text(slide, f"{n:02d}", 884, 500, 40, 18, 10, rgb(160, 174, 192))


def add_card(slide, title, body, x, y, w, h, tag=None, tag_color=ACCENT):
    add_rect(slide, x, y, w, h, CARD, FAINT)
    if tag:
        chip = slide.Shapes.AddShape(5, x + 24, y + 22, 38, 30)
        chip.Fill.ForeColor.RGB = rgb(233, 250, 247)
        chip.Line.Visible = 0
        add_text(slide, tag, x + 24, y + 27, 38, 18, 12, tag_color, True, 2)
    add_text(slide, title, x + 24, y + 70, w - 48, 28, 20, INK, True)
    add_text(slide, body, x + 24, y + 112, w - 48, h - 126, 15, MUTED)


def add_check_row(slide, idx, title, body, x, y, w, color=ACCENT):
    dot = slide.Shapes.AddShape(9, x, y + 2, 24, 24)
    dot.Fill.ForeColor.RGB = color
    dot.Line.Visible = 0
    add_text(slide, str(idx), x, y + 6, 24, 14, 9, rgb(255, 255, 255), True, 2)
    add_text(slide, title, x + 40, y, 150, 24, 17, INK, True)
    add_text(slide, body, x + 190, y + 1, w - 190, 24, 15, MUTED)


def add_arrow(slide, x1, y1, x2, y2, color=ACCENT):
    line = slide.Shapes.AddLine(x1, y1, x2, y2)
    line.Line.ForeColor.RGB = color
    line.Line.Weight = 2.25
    line.Line.EndArrowheadStyle = 3
    return line


def build():
    app = win32com.client.DispatchEx("PowerPoint.Application")
    app.DisplayAlerts = 1
    app.Visible = True
    pres = app.Presentations.Add()
    pres.PageSetup.SlideWidth = 960
    pres.PageSetup.SlideHeight = 540

    # 1 Cover
    s = pres.Slides.Add(1, 12)
    add_bg(s)
    add_text(s, "逻辑证伪", 86, 138, 520, 64, 48, INK, True)
    add_text(s, "应对系统", 86, 196, 520, 64, 48, ACCENT, True)
    add_text(s, "判断方向之后，真正决定盈亏的是：市场证明我错了，我怎么办？", 90, 294, 610, 34, 20, MUTED)
    add_rect(s, 690, 132, 150, 230, rgb(232, 249, 246), rgb(204, 239, 235))
    add_text(s, "RULES\nBEFORE\nTRADE", 718, 176, 94, 120, 24, ACCENT, True, 2)
    add_text(s, "把预测转化为预案，把情绪转化为规则", 90, 390, 520, 24, 15, ACCENT, True)
    add_footer(s, 1)

    # 2 Definition
    s = pres.Slides.Add(2, 12)
    add_bg(s)
    add_header(s, "核心定义", "逻辑证伪不是猜涨跌，而是提前定义逻辑失效。")
    add_rect(s, 88, 190, 330, 180, rgb(255, 247, 247), rgb(248, 219, 222))
    add_text(s, "普通止损", 120, 225, 240, 32, 25, WARN, True)
    add_text(s, "亏到某个比例就卖，容易被价格波动牵着走。", 120, 292, 235, 54, 18, MUTED)
    add_arrow(s, 448, 280, 512, 280, rgb(136, 153, 171))
    add_rect(s, 542, 190, 330, 180, rgb(240, 251, 249), rgb(207, 239, 234))
    add_text(s, "逻辑证伪", 574, 225, 240, 32, 25, ACCENT, True)
    add_text(s, "买入理由被市场推翻，就按预案退出或降级处理。", 574, 292, 235, 54, 18, INK)
    add_footer(s, 2)

    # 3 Entry logic
    s = pres.Slides.Add(3, 12)
    add_bg(s)
    add_header(s, "第一步：写清楚入场逻辑", "不要只写“看涨”，要写可以被检验的条件。")
    add_card(s, "周期条件", "月线趋势向上；周线回调到支撑位；日线出现放量确认。", 76, 190, 250, 182, "01")
    add_card(s, "结构条件", "价格站上关键均线、平台或趋势线，支撑与阻力位置清晰。", 355, 190, 250, 182, "02")
    add_card(s, "环境条件", "板块资金仍在流入，大盘环境没有明显系统性风险。", 634, 190, 250, 182, "03")
    add_text(s, "逻辑越具体，越容易知道什么时候错了。", 0, 426, 960, 28, 19, ACCENT, True, 2)
    add_footer(s, 3)

    # 4 Failure conditions
    s = pres.Slides.Add(4, 12)
    add_bg(s)
    add_header(s, "第二步：设置失效条件", "每条买入理由，都必须有对应的证伪条件。")
    rows = [
        ("月线失效", "跌破 20 月线且无法收回，长期趋势假设不再成立。"),
        ("周线失效", "周收盘跌破关键支撑，波段持有逻辑降级。"),
        ("日线失效", "放量突破后缩量跌回平台，突破真实性被证伪。"),
        ("板块失效", "板块指数持续走弱，个股相对强度消失。"),
    ]
    for i, (title, body) in enumerate(rows, 1):
        y = 174 + (i - 1) * 62
        add_rect(s, 92, y - 10, 770, 46, CARD, FAINT)
        add_check_row(s, i, title, body, 120, y, 700)
    add_footer(s, 4)

    # 5 Layered response
    s = pres.Slides.Add(5, 12)
    add_bg(s)
    add_header(s, "第三步：分层应对", "不要把所有波动都当成卖出信号。")
    levels = [
        ("轻微异常", "减仓观察", "日线走弱，但周线结构还没有破坏。", AMBER, rgb(255, 249, 238)),
        ("关键位失守", "执行止损", "收盘跌破预设支撑，原交易逻辑被证伪。", WARN, rgb(255, 247, 247)),
        ("逻辑完全反向", "清仓停手", "周期、结构、板块同时转弱，禁止补仓摊平。", ACCENT_2, rgb(242, 247, 255)),
    ]
    for i, (title, action, body, color, fill) in enumerate(levels):
        x = 88 + i * 292
        add_rect(s, x, 190, 245, 206, fill, FAINT)
        add_text(s, title, x + 26, 226, 180, 26, 20, color, True)
        add_text(s, action, x + 26, 278, 180, 30, 27, INK, True)
        add_text(s, body, x + 26, 336, 186, 44, 15, MUTED)
    add_footer(s, 5)

    # 6 Pre-trade plan
    s = pres.Slides.Add(6, 12)
    add_bg(s)
    add_header(s, "第四步：交易前预案", "买入前先回答四个问题。")
    qs = [
        ("我为什么买？", "明确方向、周期、结构和资金依据。"),
        ("我错在哪里会被证明？", "写出可观察、可执行的证伪条件。"),
        ("如果错了，在哪里退出？", "提前定好关键位和确认周期。"),
        ("如果对了，如何处理？", "设计加仓、止盈和持有条件。"),
    ]
    for i, (q, a) in enumerate(qs, 1):
        y = 168 + (i - 1) * 72
        add_text(s, f"0{i}", 112, y, 44, 26, 17, ACCENT, True)
        add_text(s, q, 182, y, 270, 26, 21, INK, True)
        add_text(s, a, 470, y + 2, 360, 24, 16, MUTED)
    add_footer(s, 6)

    # 7 Close confirmation
    s = pres.Slides.Add(7, 12)
    add_bg(s)
    add_header(s, "用收盘确认减少噪音", "A 股 T+1 环境中，盘中波动不能替代确认。")
    add_card(s, "日线级别", "看当日收盘是否收回关键位，避免被盘中假跌破带偏。", 90, 192, 230, 176, "D")
    add_card(s, "周线级别", "看周五收盘是否守住支撑，决定波段逻辑是否延续。", 365, 192, 230, 176, "W")
    add_card(s, "月线级别", "看月末是否维持趋势结构，用来判断长期生态是否改变。", 640, 192, 230, 176, "M")
    add_footer(s, 7)

    # 8 Checklist
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
    for i, item in enumerate(checks, 1):
        y = 174 + (i - 1) * 54
        box = slide_box = s.Shapes.AddShape(1, 152, y + 3, 18, 18)
        box.Fill.ForeColor.RGB = rgb(255, 255, 255)
        box.Line.ForeColor.RGB = ACCENT
        box.Line.Weight = 1.5
        add_text(s, item, 194, y, 610, 24, 18, INK)
    add_text(s, "成熟系统的目标不是每次看对，而是看错时有规则。", 0, 462, 960, 28, 18, ACCENT, True, 2)
    add_footer(s, 8)

    pres.SaveAs(str(OUT))
    pres.Close()
    app.Quit()
    print(OUT)


if __name__ == "__main__":
    build()
