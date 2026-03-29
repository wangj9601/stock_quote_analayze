import { apiService } from './api'
import { getCurrentEnvConfig } from '@/config/environment'

export interface StockQuoteParams {
  page: number
  pageSize: number
  keyword?: string
  market?: string
  sortBy?: string
}

export interface IndexQuoteParams {
  page: number
  pageSize: number
  keyword?: string
  sortBy?: string
}

export interface IndustryQuoteParams {
  page: number
  pageSize: number
  keyword?: string
  sortBy?: string
}

export interface HistoricalQuoteParams {
  code?: string
  keyword?: string
  page: number
  pageSize: number
  startDate?: string
  endDate?: string
  includeNotes?: boolean
}

export interface HistoricalQuoteUpdateParams {
  code: string
  date: string
  open?: number
  close?: number
  high?: number
  low?: number
  volume?: number
  amount?: number
  change_percent?: number
  change?: number
  turnover_rate?: number
  remarks?: string
}

export interface MultiPeriodQuoteParams {
  period: string
  page: number
  pageSize: number
  keyword?: string
  startDate?: string
  endDate?: string
}

export interface QuotesResponse<T> {
  success: boolean
  data: T[]
  total: number
  page: number
  pageSize: number
  message?: string
}

export interface QuotesStats {
  totalStocks: number
  totalIndices: number
  totalIndustries: number
  lastUpdateTime: string
}

class QuotesService {
  private getQuotesApiUrl(endpoint: string): string {
    // 使用独立的API基础URL来访问行情数据
    const config = getCurrentEnvConfig()
    const baseUrl = config.apiBaseUrl.replace('/api/admin', '/api')
    return `${baseUrl}/quotes${endpoint}`
  }

  /**
   * 获取股票实时行情数据
   */
  async getStockQuotes(params: StockQuoteParams): Promise<QuotesResponse<any>> {
    const queryParams = new URLSearchParams()
    queryParams.append('page', params.page.toString())
    queryParams.append('page_size', params.pageSize.toString())

    if (params.keyword) {
      queryParams.append('keyword', params.keyword)
    }
    if (params.market) {
      queryParams.append('market', params.market)
    }
    if (params.sortBy) {
      queryParams.append('sort_by', params.sortBy)
    }

    return apiService.get<QuotesResponse<any>>(this.getQuotesApiUrl(`/stocks?${queryParams}`))
  }

  /**
   * 获取指数实时行情数据
   */
  async getIndexQuotes(params: IndexQuoteParams): Promise<QuotesResponse<any>> {
    const queryParams = new URLSearchParams()
    queryParams.append('page', params.page.toString())
    queryParams.append('page_size', params.pageSize.toString())

    if (params.keyword) {
      queryParams.append('keyword', params.keyword)
    }
    if (params.sortBy) {
      queryParams.append('sort_by', params.sortBy)
    }

    return apiService.get<QuotesResponse<any>>(this.getQuotesApiUrl(`/indices?${queryParams}`))
  }

  /**
   * 获取行业板块实时行情数据
   */
  async getIndustryQuotes(params: IndustryQuoteParams): Promise<QuotesResponse<any>> {
    const queryParams = new URLSearchParams()
    queryParams.append('page', params.page.toString())
    queryParams.append('page_size', params.pageSize.toString())

    if (params.keyword) {
      queryParams.append('keyword', params.keyword)
    }
    if (params.sortBy) {
      queryParams.append('sort_by', params.sortBy)
    }

    return apiService.get<QuotesResponse<any>>(this.getQuotesApiUrl(`/industries?${queryParams}`))
  }

  /**
   * 获取行情数据统计信息
   */
  async getQuotesStats(): Promise<{ success: boolean; data: QuotesStats }> {
    return apiService.get<{ success: boolean; data: QuotesStats }>(this.getQuotesApiUrl('/stats'))
  }

  /**
   * 导入A股实时行情换手率（管理端）
   */
  async importTurnoverRate(file: File, tradeDate?: string, dryRun = false, maxErrors = 200): Promise<any> {
    const formData = new FormData()
    formData.append('file', file)
    const params = new URLSearchParams()
    if (tradeDate) params.append('trade_date', tradeDate)
    params.append('dry_run', String(dryRun))
    params.append('max_errors', String(maxErrors))
    return apiService.post(`/quotes/turnover/import?${params.toString()}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }

  /**
   * 下载换手率导入模板（CSV/XLSX）
   */
  async downloadTurnoverTemplate(format: 'csv' | 'xlsx'): Promise<Blob> {
    return apiService.get(`/quotes/turnover/import/template?format=${format}`, {
      responseType: 'blob'
    })
  }

  /**
   * 刷新所有行情数据
   */
  async refreshAllQuotes(): Promise<{ success: boolean; message: string }> {
    return apiService.post<{ success: boolean; message: string }>(this.getQuotesApiUrl('/refresh'))
  }

  /**
   * 获取历史行情数据
   */
  async getHistoricalQuotes(params: HistoricalQuoteParams): Promise<QuotesResponse<any>> {
    const queryParams = new URLSearchParams()

    // code 可以为空
    if (params.code) {
      queryParams.append('code', params.code)
    }
    if (params.keyword) {
      queryParams.append('keyword', params.keyword)
    }

    queryParams.append('page', params.page.toString())
    queryParams.append('size', params.pageSize.toString())

    if (params.startDate) {
      queryParams.append('start_date', params.startDate)
    }
    if (params.endDate) {
      queryParams.append('end_date', params.endDate)
    }
    if (params.includeNotes !== undefined) {
      queryParams.append('include_notes', params.includeNotes.toString())
    }

    const response = await apiService.get<any>(this.getQuotesApiUrl(`/history?${queryParams}`))

    // 转换响应格式以匹配 QuotesResponse 接口
    return {
      success: true,
      data: response.items || [],
      total: response.total || 0,
      page: params.page,
      pageSize: params.pageSize
    }
  }

  /**
   * 导出历史行情数据
   */
  async exportHistoricalQuotes(params: { date?: string, startDate?: string, endDate?: string, format: 'txt' | 'xlsx', market?: string }): Promise<Blob> {
    const queryParams = new URLSearchParams()
    if (params.date) {
      queryParams.append('target_date', params.date)
    }
    if (params.startDate) {
      queryParams.append('start_date', params.startDate)
    }
    if (params.endDate) {
      queryParams.append('end_date', params.endDate)
    }
    if (params.market) {
      queryParams.append('market', params.market)
    }
    queryParams.append('format', params.format)

    return apiService.get(this.getQuotesApiUrl(`/historical/export?${queryParams}`), {
      responseType: 'blob'
    })
  }

  /**
   * 更新历史行情数据
   */
  async updateHistoricalQuote(params: HistoricalQuoteUpdateParams): Promise<{ success: boolean; message: string }> {
    return apiService.put<{ success: boolean; message: string }>(
      this.getQuotesApiUrl(`/history/${params.code}/${params.date}`),
      params
    )
  }

  /**
   * 获取股票列表（用于历史行情查询）
   */
  async getStockList(): Promise<{ success: boolean; data: any[] }> {
    return apiService.get<{ success: boolean; data: any[] }>(this.getQuotesApiUrl('/stocks/list'))
  }
  /**
   * 获取港股实时行情数据
   */
  async getHKStockQuotes(params: StockQuoteParams): Promise<QuotesResponse<any>> {
    const queryParams = new URLSearchParams()
    queryParams.append('page', params.page.toString())
    queryParams.append('page_size', params.pageSize.toString())

    if (params.keyword) {
      queryParams.append('keyword', params.keyword)
    }

    return apiService.get<QuotesResponse<any>>(this.getQuotesApiUrl(`/hk-stocks?${queryParams}`))
  }

  /**
   * 获取港股历史行情数据
   */
  async getHKHistoricalQuotes(params: HistoricalQuoteParams): Promise<QuotesResponse<any>> {
    const queryParams = new URLSearchParams()

    if (params.code) {
      queryParams.append('code', params.code)
    }
    if (params.keyword) {
      queryParams.append('keyword', params.keyword)
    }

    queryParams.append('page', params.page.toString())
    queryParams.append('size', params.pageSize.toString())

    if (params.startDate) {
      queryParams.append('start_date', params.startDate)
    }
    if (params.endDate) {
      queryParams.append('end_date', params.endDate)
    }

    const response = await apiService.get<any>(this.getQuotesApiUrl(`/hk-history?${queryParams}`))

    return {
      success: true,
      data: response.items || [],
      total: response.total || 0,
      page: params.page,
      pageSize: params.pageSize
    }
  }

  /**
   * 获取港股指数实时行情数据
   */
  async getHKIndexQuotes(params: IndexQuoteParams): Promise<QuotesResponse<any>> {
    const queryParams = new URLSearchParams()
    queryParams.append('page', params.page.toString())
    queryParams.append('page_size', params.pageSize.toString())

    if (params.keyword) {
      queryParams.append('keyword', params.keyword)
    }

    return apiService.get<QuotesResponse<any>>(this.getQuotesApiUrl(`/hk-indices?${queryParams}`))
  }

  /**
   * 获取港股指数历史行情数据
   */
  async getHKIndexHistoricalQuotes(params: HistoricalQuoteParams): Promise<QuotesResponse<any>> {
    const queryParams = new URLSearchParams()

    if (params.code) {
      queryParams.append('code', params.code)
    }
    if (params.keyword) {
      queryParams.append('keyword', params.keyword)
    }

    queryParams.append('page', params.page.toString())
    queryParams.append('size', params.pageSize.toString())

    if (params.startDate) {
      queryParams.append('start_date', params.startDate)
    }
    if (params.endDate) {
      queryParams.append('end_date', params.endDate)
    }

    const response = await apiService.get<any>(this.getQuotesApiUrl(`/hk-index-history?${queryParams}`))

    return {
      success: true,
      data: response.items || [],
      total: response.total || 0,
      page: params.page,
      pageSize: params.pageSize
    }
  }

  /**
   * 获取多周期历史行情数据
   */
  async getMultiPeriodHistoricalQuotes(params: MultiPeriodQuoteParams): Promise<QuotesResponse<any>> {
    const queryParams = new URLSearchParams()
    queryParams.append('period', params.period)
    queryParams.append('page', params.page.toString())
    queryParams.append('page_size', params.pageSize.toString())

    if (params.keyword) {
      queryParams.append('keyword', params.keyword)
    }
    if (params.startDate) {
      queryParams.append('start_date', params.startDate)
    }
    if (params.endDate) {
      queryParams.append('end_date', params.endDate)
    }

    return apiService.get<QuotesResponse<any>>(this.getQuotesApiUrl(`/historical/multi-period?${queryParams}`))
  }
}

export const quotesService = new QuotesService()
