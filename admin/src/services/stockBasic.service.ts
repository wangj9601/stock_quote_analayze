import { apiService } from './api'

export type StockBasicMarket = 'CN' | 'HK'

export interface StockBasicQueryParams {
  market: 'ALL' | StockBasicMarket
  keyword?: string
  empty_shares?: boolean
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
    scopeMarket?: StockBasicMarket
  ): Promise<any> {
    const fd = new FormData()
    fd.append('file', file)
    const q = new URLSearchParams()
    q.set('mode', 'only_fill_empty')
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
    opts?: { keyword?: string; empty_shares?: boolean; collect_enabled?: boolean | null }
  ): Promise<Blob> {
    const q = new URLSearchParams()
    q.set('market', market)
    q.set('format', format)
    if (opts?.keyword) q.set('keyword', opts.keyword)
    if (opts?.empty_shares) q.set('empty_shares', 'true')
    if (opts?.collect_enabled !== undefined && opts?.collect_enabled !== null) {
      q.set('collect_enabled', String(opts.collect_enabled))
    }
    return apiService.get(`/stock-basic/export/shares?${q.toString()}`, {
      responseType: 'blob'
    })
  }
}

export const stockBasicService = new StockBasicService()
