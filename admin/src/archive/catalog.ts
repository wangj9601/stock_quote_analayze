export type ArchiveGroup = 'today' | 'strategy' | 'collect' | 'audit'

export type ArchiveRecord = {
  code: string
  group: ArchiveGroup
}

const byPath: Record<string, ArchiveRecord> = {
  '/dashboard': { code: '今-01', group: 'today' },
  '/recommend-brief': { code: '今-02', group: 'today' },
  '/gms-watchlist': { code: '策-GMS', group: 'strategy' },
  '/gms-management': { code: '策-回测', group: 'strategy' },
  '/selection-results': { code: '策-选股', group: 'strategy' },
  '/indicators': { code: '策-指标', group: 'strategy' },
  '/sbbr-management': { code: '策-SBBR', group: 'strategy' },
  '/dblb-management': { code: '策-DBLB', group: 'strategy' },
  '/cupb-management': { code: '策-CUPB', group: 'strategy' },
  '/kgt-management': { code: '策-KGT', group: 'strategy' },
  '/bvf-management': { code: '策-BVF', group: 'strategy' },
  '/lds-management': { code: '策-LDS', group: 'strategy' },
  '/rpe-management': { code: '策-RPE', group: 'strategy' },
  '/urt-management': { code: '策-URT', group: 'strategy' },
  '/csb-management': { code: '策-CSB', group: 'strategy' },
  '/pvfrs-strategy': { code: '策-PVFRS', group: 'strategy' },
  '/pvfrs-management': { code: '策-PVFRS管', group: 'strategy' },
  '/quotes': { code: '采-01', group: 'collect' },
  '/stock-basic': { code: '采-02', group: 'collect' },
  '/board-constituents': { code: '采-03', group: 'collect' },
  '/datasource': { code: '采-04', group: 'collect' },
  '/env-sync': { code: '采-05', group: 'collect' },
  '/datacollect': { code: '采-06', group: 'collect' },
  '/collection-workflows': { code: '采-07', group: 'collect' },
  '/access-management': { code: '审-01', group: 'audit' },
  '/users': { code: '审-01', group: 'audit' },
  '/roles': { code: '审-01', group: 'audit' },
  '/permissions': { code: '审-01', group: 'audit' },
  '/login-logs': { code: '审-01', group: 'audit' },
  '/monitoring': { code: '审-02', group: 'audit' },
  '/models': { code: '审-03', group: 'audit' },
  '/logs': { code: '审-04', group: 'audit' },
  '/report-management': { code: '审-05', group: 'audit' },
}

export function archiveForPath(path: string): ArchiveRecord {
  if (byPath[path]) return byPath[path]
  if (/^\/users\/\d+\/permissions$/.test(path) || /^\/roles\/\d+\/permissions$/.test(path)) {
    return { code: '审-01', group: 'audit' }
  }
  if (path.startsWith('/reports/')) return { code: '审-05', group: 'audit' }
  return { code: '未入档', group: 'audit' }
}

export const archiveDoors = [
  { group: 'today' as const, code: '今-01', name: '今日', to: '/dashboard', hint: '仪表板' },
  { group: 'strategy' as const, code: '策-GMS', name: '策略', to: '/gms-watchlist', hint: 'GMS 策略版本' },
  { group: 'collect' as const, code: '采-01', name: '采集', to: '/quotes', hint: '行情数据' },
]
