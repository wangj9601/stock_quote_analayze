import { API_BASE } from '@/config/api'

const PREFIX = '/api/admin/gms'

export interface GMSStrategyVersion {
  id: number
  strategy_code: string
  version_name: string
  version_no: number
  description?: string
  is_active: boolean
  created_by?: string
  created_at?: string
  updated_at?: string
}

export interface GMSStrategyVersionStock {
  id: number
  version_id: number
  market: 'A' | 'HK'
  stock_code: string
  stock_name?: string
  sort_order: number
  status: string
  remark?: string
  created_at?: string
  updated_at?: string
}

class GMSApiService {
  private getAuthHeaders(): Record<string, string> {
    const token = localStorage.getItem('admin_token')
    return token ? { Authorization: `Bearer ${token}` } : {}
  }

  private async request<T = any>(url: string, options: RequestInit = {}): Promise<T> {
    const response = await fetch(`${API_BASE}${url}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
        ...(options.headers as Record<string, string>),
      },
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Request failed' }))
      throw new Error(err.detail || err.message || 'Request failed')
    }
    return response.json()
  }

  /** 系统状态 */
  async getSystemStatus(): Promise<{ runningBacktests: number; totalReports: number; systemHealth: string }> {
    const res = await this.request<{ success: boolean; data: any }>(`${PREFIX}/system/status`)
    return res.data
  }

  /** 创建回测任务 */
  async createBacktest(body: {
    task_name?: string
    market?: string
    start_date: string
    end_date: string
    target_pct?: number
    horizon_days?: number
    min_score?: number
    backtest_type?: 'signal_hit_rate' | 'trade_simulation'
    stop_loss_pct?: number
    commission_bps?: number
    slippage_bps?: number
    atr_period?: number
    init_stop_atr_k?: number
    trail_stop_mode?: 'atr' | 'percent'
    trail_atr_k?: number
    trail_pct?: number
    breakeven_trigger_r?: number
    profit_lock_trigger_r?: number
    profit_lock_r?: number
    partial_take_profit_r?: number
    partial_take_ratio?: number
    time_stop_bars?: number
    stock_pool_mode?: string
    stock_code?: string
    stock_pool?: string[]
    watchlist_user_id?: number
  }) {
    const res = await this.request<{ success: boolean; data: { task_id: string } }>(`${PREFIX}/backtests`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
    return res.data.task_id
  }

  /** 有自选股的用户列表（GMS 回测创建页用于按用户筛选） */
  async getWatchlistUsers(): Promise<Array<{ user_id: number; username: string; watchlist_count: number }>> {
    const res = await this.request<{ success: boolean; data: { users: Array<{ user_id: number; username: string; watchlist_count: number }> } }>(
      `${PREFIX}/watchlist-users`
    )
    return res.data?.users || []
  }

  /** 任务列表 */
  async getBacktestTasks(params?: { status?: string; limit?: number; offset?: number }) {
    const q = new URLSearchParams()
    if (params?.status) q.set('status', params.status)
    if (params?.limit != null) q.set('limit', String(params.limit))
    if (params?.offset != null) q.set('offset', String(params.offset))
    const res = await this.request<{ success: boolean; data: { tasks: any[] } }>(`${PREFIX}/backtests?${q}`)
    return res.data.tasks
  }

  /** 任务详情 */
  async getBacktestTask(taskId: string) {
    const res = await this.request<{ success: boolean; data: any }>(`${PREFIX}/backtests/${taskId}`)
    return res.data
  }

  /** 任务日志 */
  async getBacktestLogs(taskId: string) {
    const res = await this.request<{ success: boolean; data: { logs: any[] } }>(`${PREFIX}/backtests/${taskId}/logs`)
    return res.data.logs
  }

  /** 取消任务 */
  async cancelBacktestTask(taskId: string) {
    await this.request(`${PREFIX}/backtests/${taskId}/cancel`, { method: 'POST' })
  }

  /** 重新执行：相同参数创建新任务 */
  async rerunBacktestTask(taskId: string): Promise<string> {
    const res = await this.request<{ success: boolean; data: { task_id: string } }>(
      `${PREFIX}/backtests/${taskId}/rerun`,
      { method: 'POST' }
    )
    return res.data.task_id
  }

  /** 删除任务 */
  async deleteBacktestTask(taskId: string) {
    await this.request(`${PREFIX}/backtests/${taskId}`, { method: 'DELETE' })
  }

  /** 报告列表 */
  async getReports(params?: { limit?: number; offset?: number }) {
    const q = new URLSearchParams()
    if (params?.limit != null) q.set('limit', String(params.limit))
    if (params?.offset != null) q.set('offset', String(params.offset))
    const res = await this.request<{ success: boolean; data: { reports: any[] } }>(`${PREFIX}/reports?${q}`)
    return res.data.reports
  }

  /** 报告详情 */
  async getReport(reportId: string) {
    const res = await this.request<{ success: boolean; data: any }>(`${PREFIX}/reports/${reportId}`)
    return res.data
  }

  /**
   * 下载报告明细
   * @param variant 不传：与报告记录一致（新任务多为 xlsx）；csv / xlsx 强制格式（CSV 为 UTF-8 中文表头，与 Excel 列一致）
   */
  async downloadReport(
    reportId: string,
    variant?: 'csv' | 'xlsx'
  ): Promise<{ blob: Blob; filename: string }> {
    const q =
      variant === 'csv' || variant === 'xlsx'
        ? `?variant=${encodeURIComponent(variant)}`
        : ''
    const response = await fetch(`${API_BASE}${PREFIX}/reports/${reportId}/download${q}`, {
      headers: this.getAuthHeaders(),
    })
    if (!response.ok) throw new Error('Download failed')
    let filename = `gms_backtest_${reportId.slice(0, 8)}.xlsx`
    const cd = response.headers.get('Content-Disposition')
    if (cd) {
      const utf8 = /filename\*=UTF-8''([^;\s]+)/i.exec(cd)
      const quoted = /filename="([^"]+)"/i.exec(cd)
      const plain = /filename=([^;\s]+)/i.exec(cd)
      if (utf8) {
        try {
          filename = decodeURIComponent(utf8[1])
        } catch {
          /* keep default */
        }
      } else if (quoted) {
        filename = quoted[1]
      } else if (plain) {
        filename = plain[1].replace(/['"]/g, '')
      }
    }
    const blob = await response.blob()
    return { blob, filename }
  }

  /** 读取 GMS 策略配置 */
  async getConfig() {
    const res = await this.request<{ success: boolean; data: any }>(`${PREFIX}/config`)
    return res.data
  }

  /** 更新 GMS 策略配置 */
  async saveConfig(config: Record<string, any>) {
    const res = await this.request<{ success: boolean; data: any }>(`${PREFIX}/config`, {
      method: 'PUT',
      body: JSON.stringify({ config }),
    })
    return res.data
  }

  /** 策略版本列表 */
  async getStrategyVersions(params?: { strategy_code?: string; is_active?: boolean; page?: number; page_size?: number }) {
    const q = new URLSearchParams()
    if (params?.strategy_code) q.set('strategy_code', params.strategy_code)
    if (params?.is_active !== undefined) q.set('is_active', String(params.is_active))
    if (params?.page) q.set('page', String(params.page))
    if (params?.page_size) q.set('page_size', String(params.page_size))
    const res = await this.request<{ success: boolean; data: GMSStrategyVersion[]; total: number; page: number; page_size: number }>(
      `${PREFIX}/strategy-versions?${q.toString()}`
    )
    return res
  }

  async createStrategyVersion(body: {
    strategy_code: string
    version_name: string
    version_no: number
    description?: string
    is_active?: boolean
    created_by?: string
  }) {
    const res = await this.request<{ success: boolean; data: GMSStrategyVersion }>(`${PREFIX}/strategy-versions`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
    return res.data
  }

  async updateStrategyVersion(versionId: number, body: Partial<GMSStrategyVersion>) {
    const res = await this.request<{ success: boolean; data: GMSStrategyVersion }>(`${PREFIX}/strategy-versions/${versionId}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    })
    return res.data
  }

  async deleteStrategyVersion(versionId: number) {
    await this.request(`${PREFIX}/strategy-versions/${versionId}`, { method: 'DELETE' })
  }

  /** 观察股列表 */
  async getStrategyVersionStocks(params: {
    version_id: number
    market?: string
    keyword?: string
    status?: string
    page?: number
    page_size?: number
  }) {
    const q = new URLSearchParams()
    q.set('version_id', String(params.version_id))
    if (params.market) q.set('market', params.market)
    if (params.keyword) q.set('keyword', params.keyword)
    if (params.status) q.set('status', params.status)
    if (params.page) q.set('page', String(params.page))
    if (params.page_size) q.set('page_size', String(params.page_size))
    const res = await this.request<{
      success: boolean
      data: GMSStrategyVersionStock[]
      total: number
      page: number
      page_size: number
    }>(`${PREFIX}/strategy-version-stocks?${q.toString()}`)
    return res
  }

  async createStrategyVersionStock(body: {
    version_id: number
    market: string
    stock_code: string
    stock_name?: string
    sort_order?: number
    status?: string
    remark?: string
  }) {
    const safe = {
      ...body,
      // JSON 中必须为字符串，否则纯数字代码会变成 number，后端易与整型混淆
      stock_code: body.stock_code != null && body.stock_code !== '' ? String(body.stock_code).trim() : '',
    }
    const res = await this.request<{ success: boolean; data: GMSStrategyVersionStock }>(`${PREFIX}/strategy-version-stocks`, {
      method: 'POST',
      body: JSON.stringify(safe),
    })
    return res.data
  }

  async updateStrategyVersionStock(stockId: number, body: Partial<GMSStrategyVersionStock>) {
    const sc = body.stock_code
    const safe =
      sc !== undefined && sc !== null && sc !== ''
        ? { ...body, stock_code: String(sc).trim() }
        : body
    const res = await this.request<{ success: boolean; data: GMSStrategyVersionStock }>(`${PREFIX}/strategy-version-stocks/${stockId}`, {
      method: 'PUT',
      body: JSON.stringify(safe),
    })
    return res.data
  }

  async deleteStrategyVersionStock(stockId: number) {
    await this.request(`${PREFIX}/strategy-version-stocks/${stockId}`, { method: 'DELETE' })
  }

  async batchDeleteStrategyVersionStocks(payload: { ids?: number[]; stock_codes?: string[]; version_id?: number; market?: string }) {
    const res = await this.request<{ success: boolean; data: { deleted: number } }>(`${PREFIX}/strategy-version-stocks/batch-delete`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    return res.data
  }

  async batchImportStrategyVersionStocks(payload: {
    version_id: number
    items: Array<{
      market: string
      stock_code: string
      stock_name?: string
      sort_order?: number
      status?: string
      remark?: string
    }>
  }) {
    const res = await this.request<{
      success: boolean
      data: {
        success_count: number
        skip_count: number
        fail_count: number
        fail_details: Array<{ index: number; market: string; stock_code: string; reason: string }>
      }
    }>(`${PREFIX}/strategy-version-stocks/batch-import`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    return res.data
  }

  /**
   * 选股结果列表，数据来自 **gms_signal_trace**（与前端网站 GMS 选股同源缓存表）。
   */
  async getSelectionResults(params?: { date?: string; limit?: number; min_strength?: number }) {
    const q = new URLSearchParams()
    if (params?.date) q.set('date', params.date)
    if (params?.limit != null) q.set('limit', String(params.limit))
    if (params?.min_strength != null) q.set('min_strength', String(params.min_strength))
    const qs = q.toString()
    return this.request<{
      success: boolean
      data: any[]
      total: number
      search_date?: string
      timestamp?: string
      message?: string
      data_source?: string
      strategy_name?: string
    }>(`${PREFIX}/selection-results${qs ? `?${qs}` : ''}`)
  }
}

export const gmsApiService = new GMSApiService()
