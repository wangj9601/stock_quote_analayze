/**
 * 前端权限资源注册表（与 backend_api/permission_registry_data.py 保持同步）
 */
window.PERMISSION_REGISTRY = [
  { code: 'channel.home', name: '首页', level: 1, parent_code: null, channel_code: 'home', sort_order: 10 },
  { code: 'channel.watchlist', name: '自选股', level: 1, parent_code: null, channel_code: 'watchlist', sort_order: 20 },
  { code: 'channel.quotes', name: '行情', level: 1, parent_code: null, channel_code: 'quotes', sort_order: 30 },
  { code: 'channel.screening', name: '选股', level: 1, parent_code: null, channel_code: 'screening', sort_order: 40 },
  { code: 'channel.analyze', name: '分析', level: 1, parent_code: null, channel_code: 'analyze', sort_order: 50 },
  { code: 'channel.news', name: '资讯', level: 1, parent_code: null, channel_code: 'news', sort_order: 60 },
  { code: 'channel.profile', name: '我的', level: 1, parent_code: null, channel_code: 'profile', sort_order: 70 },

  { code: 'channel.screening.tab.cyb_midline', name: '创业板中线选股', level: 2, parent_code: 'channel.screening', channel_code: 'screening', sort_order: 10 },
  { code: 'channel.screening.tab.parking_apron', name: '停机坪', level: 2, parent_code: 'channel.screening', channel_code: 'screening', sort_order: 20 },
  { code: 'channel.screening.tab.backtrace_ma250', name: '回踩年线', level: 2, parent_code: 'channel.screening', channel_code: 'screening', sort_order: 30 },
  { code: 'channel.screening.tab.high_tight_flag', name: '高而窄的旗形', level: 2, parent_code: 'channel.screening', channel_code: 'screening', sort_order: 40 },
  { code: 'channel.screening.tab.one_yang_three_lines', name: '一阳穿三线', level: 2, parent_code: 'channel.screening', channel_code: 'screening', sort_order: 50 },
  { code: 'channel.screening.tab.gms', name: 'GMS均值引力动量', level: 2, parent_code: 'channel.screening', channel_code: 'screening', sort_order: 60 },
  { code: 'channel.screening.tab.pvfrs', name: 'PVFRS量价频幅度共振', level: 2, parent_code: 'channel.screening', channel_code: 'screening', sort_order: 70 },
  { code: 'channel.screening.tab.vsb', name: '3倍量缩量突破', level: 2, parent_code: 'channel.screening', channel_code: 'screening', sort_order: 80 },
  { code: 'channel.screening.tab.urt', name: '上升趋势', level: 2, parent_code: 'channel.screening', channel_code: 'screening', sort_order: 90 },
  { code: 'channel.screening.tab.sbbr', name: '做小做底', level: 2, parent_code: 'channel.screening', channel_code: 'screening', sort_order: 100 },
  { code: 'channel.screening.tab.rpe', name: '比价效应', level: 2, parent_code: 'channel.screening', channel_code: 'screening', sort_order: 110 },

  { code: 'channel.screening.tab.cyb_midline.btn.refresh', name: '刷新筛选', level: 3, parent_code: 'channel.screening.tab.cyb_midline', channel_code: 'screening', sort_order: 10 },
  { code: 'channel.screening.tab.gms.btn.refresh', name: 'GMS刷新', level: 3, parent_code: 'channel.screening.tab.gms', channel_code: 'screening', sort_order: 10 },
  { code: 'channel.screening.tab.gms.btn.export', name: 'GMS导出', level: 3, parent_code: 'channel.screening.tab.gms', channel_code: 'screening', sort_order: 20 },
  { code: 'channel.screening.tab.pvfrs.btn.refresh', name: 'PVFRS刷新', level: 3, parent_code: 'channel.screening.tab.pvfrs', channel_code: 'screening', sort_order: 10 },
  { code: 'channel.screening.tab.vsb.btn.refresh', name: 'VSB刷新', level: 3, parent_code: 'channel.screening.tab.vsb', channel_code: 'screening', sort_order: 10 },
  { code: 'channel.screening.tab.vsb.btn.add_observe', name: '加入观察', level: 3, parent_code: 'channel.screening.tab.vsb', channel_code: 'screening', sort_order: 20 },
  { code: 'channel.screening.tab.urt.btn.refresh', name: 'URT刷新', level: 3, parent_code: 'channel.screening.tab.urt', channel_code: 'screening', sort_order: 10 },
  { code: 'channel.screening.tab.urt.btn.export', name: 'URT导出', level: 3, parent_code: 'channel.screening.tab.urt', channel_code: 'screening', sort_order: 20 },
  { code: 'channel.screening.tab.urt.btn.calc_qfq', name: 'URT按前复权计算支撑阻力', level: 3, parent_code: 'channel.screening.tab.urt', channel_code: 'screening', sort_order: 25 },
  { code: 'channel.screening.tab.urt.btn.observe', name: 'URT交易观察', level: 3, parent_code: 'channel.screening.tab.urt', channel_code: 'screening', sort_order: 30 },
  { code: 'channel.screening.tab.urt.btn.formal', name: 'URT正式交易', level: 3, parent_code: 'channel.screening.tab.urt', channel_code: 'screening', sort_order: 40 },
  { code: 'channel.screening.tab.vsb.btn.add_observe', name: '加入观察', level: 3, parent_code: 'channel.screening.tab.vsb', channel_code: 'screening', sort_order: 20 },
  { code: 'channel.screening.tab.sbbr.btn.refresh', name: 'SBBR刷新', level: 3, parent_code: 'channel.screening.tab.sbbr', channel_code: 'screening', sort_order: 10 },
  { code: 'channel.screening.tab.sbbr.btn.add_observe', name: '加入观察', level: 3, parent_code: 'channel.screening.tab.sbbr', channel_code: 'screening', sort_order: 20 },
  { code: 'channel.screening.tab.sbbr.btn.add_reserve', name: '加入储备', level: 3, parent_code: 'channel.screening.tab.sbbr', channel_code: 'screening', sort_order: 30 },
  { code: 'channel.screening.tab.rpe.btn.refresh', name: 'RPE刷新', level: 3, parent_code: 'channel.screening.tab.rpe', channel_code: 'screening', sort_order: 10 },
  { code: 'channel.screening.tab.rpe.btn.calc_qfq', name: 'RPE按前复权重算策略信号', level: 3, parent_code: 'channel.screening.tab.rpe', channel_code: 'screening', sort_order: 20 },

  { code: 'channel.analyze.tab.market', name: '市场分析', level: 2, parent_code: 'channel.analyze', channel_code: 'analyze', sort_order: 10 },
  { code: 'channel.analyze.tab.technical', name: '技术工具', level: 2, parent_code: 'channel.analyze', channel_code: 'analyze', sort_order: 20 },
  { code: 'channel.analyze.tab.strategy', name: '投资策略', level: 2, parent_code: 'channel.analyze', channel_code: 'analyze', sort_order: 30 },
  { code: 'channel.analyze.tab.report', name: '分析报告', level: 2, parent_code: 'channel.analyze', channel_code: 'analyze', sort_order: 40 },
  { code: 'channel.analyze.tab.technical.btn.analyze', name: '开始分析', level: 3, parent_code: 'channel.analyze.tab.technical', channel_code: 'analyze', sort_order: 10 },
  { code: 'channel.analyze.tab.report.btn.export', name: '导出报告', level: 3, parent_code: 'channel.analyze.tab.report', channel_code: 'analyze', sort_order: 10 },

  { code: 'channel.profile.tab.overview', name: '投资概况', level: 2, parent_code: 'channel.profile', channel_code: 'profile', sort_order: 10 },
  { code: 'channel.profile.tab.portfolio', name: '投资组合', level: 2, parent_code: 'channel.profile', channel_code: 'profile', sort_order: 20 },
  { code: 'channel.profile.tab.transactions', name: '交易记录', level: 2, parent_code: 'channel.profile', channel_code: 'profile', sort_order: 30 },
  { code: 'channel.profile.tab.trading_logs', name: '交易日志', level: 2, parent_code: 'channel.profile', channel_code: 'profile', sort_order: 40 },
  { code: 'channel.profile.tab.analysis', name: '投资分析', level: 2, parent_code: 'channel.profile', channel_code: 'profile', sort_order: 50 },
  { code: 'channel.profile.tab.kde_levels', name: '支撑压力', level: 2, parent_code: 'channel.profile', channel_code: 'profile', sort_order: 55 },
  { code: 'channel.profile.tab.settings', name: '账户设置', level: 2, parent_code: 'channel.profile', channel_code: 'profile', sort_order: 60 },
  { code: 'channel.profile.tab.kde_levels.btn.calc', name: '计算支撑压力', level: 3, parent_code: 'channel.profile.tab.kde_levels', channel_code: 'profile', sort_order: 10 },
  { code: 'channel.profile.tab.kde_levels.btn.calc_qfq', name: '按前复权计算支撑压力', level: 3, parent_code: 'channel.profile.tab.kde_levels', channel_code: 'profile', sort_order: 20 },
  { code: 'channel.profile.tab.settings.btn.change_password', name: '修改密码', level: 3, parent_code: 'channel.profile.tab.settings', channel_code: 'profile', sort_order: 10 },

  { code: 'channel.watchlist.tab.default', name: '自选股列表', level: 2, parent_code: 'channel.watchlist', channel_code: 'watchlist', sort_order: 10 },
  { code: 'channel.watchlist.tab.default.btn.add', name: '添加自选股', level: 3, parent_code: 'channel.watchlist.tab.default', channel_code: 'watchlist', sort_order: 10 },
  { code: 'channel.watchlist.tab.default.btn.delete', name: '删除自选股', level: 3, parent_code: 'channel.watchlist.tab.default', channel_code: 'watchlist', sort_order: 20 },
  { code: 'channel.watchlist.tab.default.btn.import', name: '导入自选股', level: 3, parent_code: 'channel.watchlist.tab.default', channel_code: 'watchlist', sort_order: 30 }
];

/** 策略 tab data-strategy → 权限码映射 */
window.PERMISSION_TAB_MAP = {
  'cyb-midline': 'channel.screening.tab.cyb_midline',
  'parking-apron': 'channel.screening.tab.parking_apron',
  'backtrace-ma250': 'channel.screening.tab.backtrace_ma250',
  'high-tight-flag': 'channel.screening.tab.high_tight_flag',
  'one-yang-three-lines': 'channel.screening.tab.one_yang_three_lines',
  gms: 'channel.screening.tab.gms',
  pvfrs: 'channel.screening.tab.pvfrs',
  'volume-shrink-breakout': 'channel.screening.tab.vsb',
  urt: 'channel.screening.tab.urt',
  sbbr: 'channel.screening.tab.sbbr',
  rpe: 'channel.screening.tab.rpe'
};
