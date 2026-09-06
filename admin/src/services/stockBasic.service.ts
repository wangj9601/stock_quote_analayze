import { apiService } from './api'

export type StockBasicMarket = 'CN' | 'HK'

export type DelistedFilter = 'all' | 'only' | 'exclude'

export interface StockBasicQueryParams {
  market: 'ALL' | StockBasicMarket
  keyword?: string
  empty_shares?: boolean
  delisted_filter?: DelistedFilter
  collect_enabled?: boolean | null
  page: number
  page_size: number
}

export interface StockBasicListItem {
  market: 'CN' | 'HK'
  code: string
  name: string
  total_shares: number | null
  free_float_shares: number | null
  industry: string | null
  listing_date: string | null
  shares_updated_at: string | null
  collect_enabled: boolean
}

class StockBasicService {
  async getPipelineStatus(): Promise<any> {
    return apiService.get('/stock-basic/pipeline-status')
  }

  async getList(params: StockBasicQueryParams): Promise<{
    success: boolean
    data: StockBasicListItem[]
    total: number
    page: number
    page_size: number
  }> {
    const q = new URLSearchParams()
    q.set('market', params.market)
    q.set('page', String(params.page))
    q.set('page_size', String(params.page_size))
    if (params.keyword) q.set('keyword', params.keyword)
    if (params.empty_shares) q.set('empty_shares', 'true')
    if (params.delisted_filter && params.delisted_filter !== 'all') {
      q.set('delisted_filter', params.delisted_filter)
    }
    if (params.collect_enabled !== undefined && params.collect_enabled !== null) {
      q.set('collect_enabled', String(params.collect_enabled))
    }
    return apiService.get(`/stock-basic/list?${q.toString()}`)
  }

  async updateCollectFlag(market: StockBasicMarket, code: string, collectEnabled: boolean): Promise<any> {
    const q = new URLSearchParams()
    q.set('market', market)
    q.set('code', code)
    q.set('collect_enabled', String(collectEnabled))
    return apiService.post(`/stock-basic/collect-flag?${q.toString()}`)
  }

  async batchUpdateCollectFlag(
    market: StockBasicMarket,
    codes: string[],
    collectEnabled: boolean
  ): Promise<{ success: boolean; data: { affected: number } }> {
    return apiService.post('/stock-basic/collect-flag/batch', {
      market,
      codes,
      collect_enabled: collectEnabled,
    })
  }

  async downloadTemplate(format: 'csv' | 'xlsx'): Promise<Blob> {
    return apiService.get(`/stock-basic/import/template?format=${format}`, {
      responseType: 'blob'
    })
  }

  async validateImport(file: File, scopeMarket?: StockBasicMarket): Promise<any> {
    const fd = new FormData()
    fd.append('file', file)
    const q = new URLSearchParams()
    if (scopeMarket) q.set('scope_market', scopeMarket)
    const qs = q.toString()
    return apiService.post(`/stock-basic/import/validate${qs ? `?${qs}` : ''}`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }

  async executeImport(
    file: File,
    dryRun = false,
    maxErrors = 100,
    scopeMarket?: StockBasicMarket,
    mode: 'only_fill_empty' | 'overwrite_shares' = 'overwrite_shares'
  ): Promise<any> {
    const fd = new FormData()
    fd.append('file', file)
    const q = new URLSearchParams()
    q.set('mode', mode)
    q.set('dry_run', String(dryRun))
    q.set('max_errors', String(maxErrors))
    if (scopeMarket) q.set('scope_market', scopeMarket)
    return apiService.post(`/stock-basic/import/execute?${q.toString()}`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }

  /** 股本导出（单市场） */
  async exportShares(
    market: StockBasicMarket,
    format: 'csv' | 'xlsx',
    opts?: {
      keyword?: string
      empty_shares?: boolean
      delisted_filter?: DelistedFilter
      collect_enabled?: boolean | null
    }
  ): Promise<Blob> {
    const q = new URLSearchParams()
    q.set('market', market)
    q.set('format', format)
    if (opts?.keyword) q.set('keyword', opts.keyword)
    if (opts?.empty_shares) q.set('empty_shares', 'true')
    if (opts?.delisted_filter && opts.delisted_filter !== 'all') {
      q.set('delisted_filter', opts.delisted_filter)
    }
    if (opts?.collect_enabled !== undefined && opts?.collect_enabled !== null) {
      q.set('collect_enabled', String(opts.collect_enabled))
    }
    return apiService.get(`/stock-basic/export/shares?${q.toString()}`, {
      responseType: 'blob'
    })
  }

  /** 从行业板块表同步 A 股 industry 到 stock_basic_info */
  async syncIndustryFromBoards(opts?: { only_empty?: boolean }): Promise<{
    success: boolean
    data: { updated: number; matched: number }
  }> {
    const q = new URLSearchParams()
    q.set('market', 'CN')
    if (opts?.only_empty === false) q.set('only_empty', 'false')
    return apiService.post(`/stock-basic/sync-industry?${q.toString()}`)
  }

  /** A 股相对强度 RS 列表（默认最高排最前） */
  async getRsRatings(params: {
    keyword?: string
    date?: string
    min_rating?: number | null
    page: number
    page_size: number
  }): Promise<{
    success: boolean
    data: Array<{
      code: string
      name: string | null
      date: string
      rs_rating: number | null
      rs_raw: number | null
      roc_63: number | null
      roc_126: number | null
      roc_189: number | null
      roc_252: number | null
      strength_label: string | null
      universe_size: number | null
      coverage_ratio: number | null
    }>
    total: number
    page: number
    page_size: number
    asof: string | null
  }> {
    const q = new URLSearchParams()
    q.set('page', String(params.page))
    q.set('page_size', String(params.page_size))
    if (params.keyword) q.set('keyword', params.keyword)
    if (params.date) q.set('date', params.date)
    if (params.min_rating != null) q.set('min_rating', String(params.min_rating))
    return apiService.get(`/stock-basic/rs-ratings?${q.toString()}`)
  }

  /** 单只股票 RS 历史追溯 */
  async getRsRatingHistory(params: {
    code: string
    start_date?: string
    end_date?: string
    limit?: number
  }): Promise<{
    success: boolean
    code: string
    name?: string | null
    count: number
    data: Array<{
      code: string
      date: string
      rs_rating: number | null
      rs_raw: number | null
      roc_63: number | null
      roc_126: number | null
      roc_189: number | null
      roc_252: number | null
      strength_label: string | null
      universe_size: number | null
      coverage_ratio: number | null
    }>
    message?: string
  }> {
    const q = new URLSearchParams()
    q.set('code', params.code)
    if (params.start_date) q.set('start_date', params.start_date)
    if (params.end_date) q.set('end_date', params.end_date)
    q.set('limit', String(params.limit ?? 120))
    return apiService.get(`/stock-basic/rs-ratings/history?${q.toString()}`)
  }

  /** 强制重算指定日/短区间的全市场 RS 截面 */
  async startRsForcePrecompute(body: {
    trade_date?: string
    start_date?: string
    end_date?: string
  }): Promise<{
    success: boolean
    task_id: string
    trade_dates: string[]
    message?: string
  }> {
    return apiService.post(`/stock-basic/rs-ratings/precompute`, body)
  }

  async getRsForcePrecomputeTask(taskId: string): Promise<{
    success: boolean
    data: {
      task_id: string
      status: string
      progress: number
      message?: string
      error?: string | null
      trade_dates?: string[]
      trade_date?: string | null
      summaries?: unknown[]
    }
  }> {
    return apiService.get(`/stock-basic/rs-ratings/precompute/${encodeURIComponent(taskId)}`)
  }
}

export const stockBasicService = new StockBasicService()
