# -*- coding: utf-8 -*-
"""Polish markets.html: replace light-theme inline styles with ops classes."""
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "frontend" / "markets.html"
text = path.read_text(encoding="utf-8")
orig = text

replacements = [
    (
        '<div style="display: flex; align-items: center; justify-content: space-between;">',
        '<div class="ops-page-head">',
    ),
    (
        '<div class="market-filter" style="display:flex;align-items:center;gap:12px;">',
        '<div class="market-filter">',
    ),
    (
        '<div id="volumeAberrationToolbar" class="volume-aberration-toolbar" style="display:none; align-items:center; gap:12px;">',
        '<div id="volumeAberrationToolbar" class="volume-aberration-toolbar" style="display:none;">',
    ),
    (
        '<label style="margin-left:8px;">导出范围</label>',
        '<label class="ops-export-scope-label">导出范围</label>',
    ),
    (
        '<select id="volumeAberrationExportScope" style="padding:6px 10px;border:1px solid #ccc;border-radius:4px;">',
        '<select id="volumeAberrationExportScope" class="filter-select">',
    ),
    (
        '<input type="text" id="marketSearchInput" placeholder="输入股票代码或名称" style="padding:6px 12px; font-size:1em; border:1px solid #ccc; border-radius:4px;">',
        '<input type="text" id="marketSearchInput" class="ops-search-input" placeholder="输入股票代码或名称">',
    ),
    (
        '<button id="marketSearchBtn" style="padding:6px 16px; margin-left:8px; font-size:1em; border:none; background:#1976d2; color:#fff; border-radius:4px; cursor:pointer;">查询</button>',
        '<button type="button" id="marketSearchBtn" class="ops-search-btn">查询</button>',
    ),
    (
        '<input type="text" id="hkMarketSearchInput" placeholder="输入股票代码或名称" style="padding:6px 12px; font-size:1em; border:1px solid #ccc; border-radius:4px;">',
        '<input type="text" id="hkMarketSearchInput" class="ops-search-input" placeholder="输入股票代码或名称">',
    ),
    (
        '<button id="hkMarketSearchBtn" style="padding:6px 16px; margin-left:8px; font-size:1em; border:none; background:#1976d2; color:#fff; border-radius:4px; cursor:pointer;">查询</button>',
        '<button type="button" id="hkMarketSearchBtn" class="ops-search-btn">查询</button>',
    ),
    (
        '<input type="text" id="auctionKeyword" placeholder="代码/名称关键字" style="padding:6px 10px;border:1px solid #ccc;border-radius:4px;">',
        '<input type="text" id="auctionKeyword" class="ops-search-input" placeholder="代码/名称关键字">',
    ),
    (
        '<tr><td colspan="11" style="text-align:center;color:#888;">加载中...</td></tr>',
        '<tr><td colspan="11" class="ops-empty-cell">加载中...</td></tr>',
    ),
    (
        '<tr><td colspan="11" style="text-align:center;color:#888;">切换到本页后加载</td></tr>',
        '<tr><td colspan="11" class="ops-empty-cell">切换到本页后加载</td></tr>',
    ),
    (
        '<tr><td colspan="12" style="text-align:center;color:#888;">切换到本页后加载</td></tr>',
        '<tr><td colspan="12" class="ops-empty-cell">切换到本页后加载</td></tr>',
    ),
    (
        '<p style="text-align:center;padding:40px;color:#666;">港股行业板块功能开发中...</p>',
        '<p class="ops-placeholder-msg">港股行业板块功能开发中...</p>',
    ),
    (
        '<p style="text-align:center;padding:40px;color:#666;">港股热门关注功能开发中...</p>',
        '<p class="ops-placeholder-msg">港股热门关注功能开发中...</p>',
    ),
    (
        '<p style="text-align:center;padding:40px;color:#666;">港股市场统计功能开发中...</p>',
        '<p class="ops-placeholder-msg">港股市场统计功能开发中...</p>',
    ),
]

for old, new in replacements:
    if old not in text:
        print("MISS:", old[:80])
    else:
        text = text.replace(old, new)
        print("OK:", new[:60])

# bump markets-ops cache if linked with query — markets.html has no ?v on markets-ops; bump ops-surfaces already has v
# add cache buster on markets-ops
if 'href="css/markets-ops.css"' in text and 'markets-ops.css?v=' not in text:
    text = text.replace(
        'href="css/markets-ops.css"',
        'href="css/markets-ops.css?v=20260925polish"',
    )
    print("OK: cache bust markets-ops")

if text == orig:
    print("NO CHANGES")
else:
    path.write_text(text, encoding="utf-8")
    print("wrote", path)

# sync surface brief grid language for markets surface
brief = Path(__file__).resolve().parents[1] / ".impeccable" / "surfaces" / "frontend-markets-html.md"
if brief.exists():
    bt = brief.read_text(encoding="utf-8")
    bt2 = bt.replace(
        "半透明叠层芯片、标图式细线网格、字号阶梯导航；无玻璃拟态、无霓虹描边。",
        "半透明叠层芯片、极淡暗角底图（无满屏方格）、字号阶梯导航；无玻璃拟态、无霓虹描边。"
    ).replace(
        "主区为板块/行情底图网格，右侧信号/龙头中军对向力侧栏。",
        "主区为板块/行情抬升工作面，右侧信号/龙头中军对向力侧栏。"
    )
    if bt2 != bt:
        brief.write_text(bt2, encoding="utf-8")
        print("updated markets surface brief")
