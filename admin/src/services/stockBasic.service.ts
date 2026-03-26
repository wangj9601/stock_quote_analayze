import { apiService } from './api'

export interface StockBasicQueryParams {
  market: 'ALL' | 'CN' | 'HK'
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

  async updateCollectFlag(market: 'CN' | 'HK', code: string, collectEnabled: boolean): Promise<any> {
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

  async validateImport(file: File): Promise<any> {
    const fd = new FormData()
    fd.append('file', file)
    return apiService.post('/stock-basic/import/validate', fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }

  async executeImport(file: File, dryRun = false, maxErrors = 100): Promise<any> {
    const fd = new FormData()
    fd.append('file', file)
    const q = new URLSearchParams()
    q.set('mode', 'only_fill_empty')
    q.set('dry_run', String(dryRun))
    q.set('max_errors', String(maxErrors))
    return apiService.post(`/stock-basic/import/execute?${q.toString()}`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }
}

export const stockBasicService = new StockBasicService()

