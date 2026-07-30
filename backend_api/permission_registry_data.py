"""
前端权限资源注册表（权威数据源，供 sync API 与 seed 使用）
权限码独立勾选，无父子继承。
"""

from typing import List, Dict, Any

PERMISSION_REGISTRY: List[Dict[str, Any]] = [
    # ── 一级：频道 ──
    {"code": "channel.home", "name": "首页", "level": 1, "parent_code": None, "channel_code": "home", "sort_order": 10},
    {"code": "channel.watchlist", "name": "自选股", "level": 1, "parent_code": None, "channel_code": "watchlist", "sort_order": 20},
    {"code": "channel.quotes", "name": "行情", "level": 1, "parent_code": None, "channel_code": "quotes", "sort_order": 30},
    {"code": "channel.screening", "name": "选股", "level": 1, "parent_code": None, "channel_code": "screening", "sort_order": 40},
    {"code": "channel.analyze", "name": "分析", "level": 1, "parent_code": None, "channel_code": "analyze", "sort_order": 50},
    {"code": "channel.news", "name": "资讯", "level": 1, "parent_code": None, "channel_code": "news", "sort_order": 60},
    {"code": "channel.profile", "name": "我的", "level": 1, "parent_code": None, "channel_code": "profile", "sort_order": 70},

    # ── 二级：选股标签页 ──
    {"code": "channel.screening.tab.cyb_midline", "name": "创业板中线选股", "level": 2, "parent_code": "channel.screening", "channel_code": "screening", "sort_order": 10},
    {"code": "channel.screening.tab.parking_apron", "name": "停机坪", "level": 2, "parent_code": "channel.screening", "channel_code": "screening", "sort_order": 20},
    {"code": "channel.screening.tab.backtrace_ma250", "name": "回踩年线", "level": 2, "parent_code": "channel.screening", "channel_code": "screening", "sort_order": 30},
    {"code": "channel.screening.tab.high_tight_flag", "name": "高而窄的旗形", "level": 2, "parent_code": "channel.screening", "channel_code": "screening", "sort_order": 40},
    {"code": "channel.screening.tab.one_yang_three_lines", "name": "一阳穿三线", "level": 2, "parent_code": "channel.screening", "channel_code": "screening", "sort_order": 50},
    {"code": "channel.screening.tab.gms", "name": "GMS均值引力动量", "level": 2, "parent_code": "channel.screening", "channel_code": "screening", "sort_order": 60},
    {"code": "channel.screening.tab.pvfrs", "name": "PVFRS量价频幅度共振", "level": 2, "parent_code": "channel.screening", "channel_code": "screening", "sort_order": 70},
    {"code": "channel.screening.tab.vsb", "name": "3倍量缩量突破", "level": 2, "parent_code": "channel.screening", "channel_code": "screening", "sort_order": 80},
    {"code": "channel.screening.tab.urt", "name": "上升趋势", "level": 2, "parent_code": "channel.screening", "channel_code": "screening", "sort_order": 90},
    {"code": "channel.screening.tab.sbbr", "name": "做小做底", "level": 2, "parent_code": "channel.screening", "channel_code": "screening", "sort_order": 100},
    {"code": "channel.screening.tab.rpe", "name": "比价效应", "level": 2, "parent_code": "channel.screening", "channel_code": "screening", "sort_order": 110},

    # ── 三级：选股按钮 ──
    {"code": "channel.screening.tab.cyb_midline.btn.refresh", "name": "刷新筛选", "level": 3, "parent_code": "channel.screening.tab.cyb_midline", "channel_code": "screening", "sort_order": 10},
    {"code": "channel.screening.tab.gms.btn.refresh", "name": "GMS刷新", "level": 3, "parent_code": "channel.screening.tab.gms", "channel_code": "screening", "sort_order": 10},
    {"code": "channel.screening.tab.gms.btn.export", "name": "GMS导出", "level": 3, "parent_code": "channel.screening.tab.gms", "channel_code": "screening", "sort_order": 20},
    {"code": "channel.screening.tab.pvfrs.btn.refresh", "name": "PVFRS刷新", "level": 3, "parent_code": "channel.screening.tab.pvfrs", "channel_code": "screening", "sort_order": 10},
    {"code": "channel.screening.tab.vsb.btn.refresh", "name": "VSB刷新", "level": 3, "parent_code": "channel.screening.tab.vsb", "channel_code": "screening", "sort_order": 10},
    {"code": "channel.screening.tab.vsb.btn.add_observe", "name": "加入观察", "level": 3, "parent_code": "channel.screening.tab.vsb", "channel_code": "screening", "sort_order": 20},
    {"code": "channel.screening.tab.urt.btn.refresh", "name": "URT刷新", "level": 3, "parent_code": "channel.screening.tab.urt", "channel_code": "screening", "sort_order": 10},
    {"code": "channel.screening.tab.urt.btn.export", "name": "URT导出", "level": 3, "parent_code": "channel.screening.tab.urt", "channel_code": "screening", "sort_order": 20},
    {"code": "channel.screening.tab.urt.btn.observe", "name": "URT交易观察", "level": 3, "parent_code": "channel.screening.tab.urt", "channel_code": "screening", "sort_order": 30},
    {"code": "channel.screening.tab.urt.btn.formal", "name": "URT正式交易", "level": 3, "parent_code": "channel.screening.tab.urt", "channel_code": "screening", "sort_order": 40},
    {"code": "channel.screening.tab.sbbr.btn.refresh", "name": "SBBR刷新", "level": 3, "parent_code": "channel.screening.tab.sbbr", "channel_code": "screening", "sort_order": 10},
    {"code": "channel.screening.tab.rpe.btn.refresh", "name": "RPE刷新", "level": 3, "parent_code": "channel.screening.tab.rpe", "channel_code": "screening", "sort_order": 10},
    {"code": "channel.screening.tab.sbbr.btn.add_observe", "name": "加入观察", "level": 3, "parent_code": "channel.screening.tab.sbbr", "channel_code": "screening", "sort_order": 20},
    {"code": "channel.screening.tab.sbbr.btn.add_reserve", "name": "加入储备", "level": 3, "parent_code": "channel.screening.tab.sbbr", "channel_code": "screening", "sort_order": 30},

    # ── 二级：分析标签页 ──
    {"code": "channel.analyze.tab.market", "name": "市场分析", "level": 2, "parent_code": "channel.analyze", "channel_code": "analyze", "sort_order": 10},
    {"code": "channel.analyze.tab.technical", "name": "技术工具", "level": 2, "parent_code": "channel.analyze", "channel_code": "analyze", "sort_order": 20},
    {"code": "channel.analyze.tab.strategy", "name": "投资策略", "level": 2, "parent_code": "channel.analyze", "channel_code": "analyze", "sort_order": 30},
    {"code": "channel.analyze.tab.report", "name": "分析报告", "level": 2, "parent_code": "channel.analyze", "channel_code": "analyze", "sort_order": 40},

    # ── 三级：分析按钮 ──
    {"code": "channel.analyze.tab.technical.btn.analyze", "name": "开始分析", "level": 3, "parent_code": "channel.analyze.tab.technical", "channel_code": "analyze", "sort_order": 10},
    {"code": "channel.analyze.tab.report.btn.export", "name": "导出报告", "level": 3, "parent_code": "channel.analyze.tab.report", "channel_code": "analyze", "sort_order": 10},

    # ── 二级：个人中心标签页 ──
    {"code": "channel.profile.tab.overview", "name": "投资概况", "level": 2, "parent_code": "channel.profile", "channel_code": "profile", "sort_order": 10},
    {"code": "channel.profile.tab.portfolio", "name": "投资组合", "level": 2, "parent_code": "channel.profile", "channel_code": "profile", "sort_order": 20},
    {"code": "channel.profile.tab.transactions", "name": "交易记录", "level": 2, "parent_code": "channel.profile", "channel_code": "profile", "sort_order": 30},
    {"code": "channel.profile.tab.trading_logs", "name": "交易日志", "level": 2, "parent_code": "channel.profile", "channel_code": "profile", "sort_order": 40},
    {"code": "channel.profile.tab.analysis", "name": "投资分析", "level": 2, "parent_code": "channel.profile", "channel_code": "profile", "sort_order": 50},
    {"code": "channel.profile.tab.kde_levels", "name": "支撑压力", "level": 2, "parent_code": "channel.profile", "channel_code": "profile", "sort_order": 55},
    {"code": "channel.profile.tab.settings", "name": "账户设置", "level": 2, "parent_code": "channel.profile", "channel_code": "profile", "sort_order": 60},

    # ── 三级：个人中心按钮 ──
    {"code": "channel.profile.tab.kde_levels.btn.calc", "name": "计算支撑压力", "level": 3, "parent_code": "channel.profile.tab.kde_levels", "channel_code": "profile", "sort_order": 10},
    {"code": "channel.profile.tab.settings.btn.change_password", "name": "修改密码", "level": 3, "parent_code": "channel.profile.tab.settings", "channel_code": "profile", "sort_order": 10},

    # ── 二级：自选股标签页 ──
    {"code": "channel.watchlist.tab.default", "name": "自选股列表", "level": 2, "parent_code": "channel.watchlist", "channel_code": "watchlist", "sort_order": 10},

    # ── 三级：自选股按钮 ──
    {"code": "channel.watchlist.tab.default.btn.add", "name": "添加自选股", "level": 3, "parent_code": "channel.watchlist.tab.default", "channel_code": "watchlist", "sort_order": 10},
    {"code": "channel.watchlist.tab.default.btn.delete", "name": "删除自选股", "level": 3, "parent_code": "channel.watchlist.tab.default", "channel_code": "watchlist", "sort_order": 20},
    {"code": "channel.watchlist.tab.default.btn.import", "name": "导入自选股", "level": 3, "parent_code": "channel.watchlist.tab.default", "channel_code": "watchlist", "sort_order": 30},
]

DEFAULT_ROLES = [
    {"code": "standard", "name": "标准用户", "description": "默认角色，含全部已注册权限", "is_system": True},
    {"code": "admin", "name": "前台管理员", "description": "前台管理员，含全部权限", "is_system": True},
    {"code": "guest", "name": "访客", "description": "预留角色，本阶段不启用", "is_system": True},
]
