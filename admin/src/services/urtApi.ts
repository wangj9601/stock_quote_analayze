import { API_BASE } from '@/config/api'

const PREFIX = '/api/admin/urt'

export interface URTStrategyConfig {
  id: number
  name: string
  version_label?: string | null
  description?: string | null
  config_params?: Record<string, any>
  is_active: boolean
  is_default: boolean
  precompute_enabled?: boolean
  created_by?: string | null
  created_at?: string | null
  updated_at?: string | null
}

class URTApiService {
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
      const detail = err.detail
      const msg = typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: any) => d.msg || d).join('; ')
          : (err.message || 'Request failed')
      throw new Error(msg)
    }
    return response.json()
  }

  async listStrategyConfigs(activeOnly = false): Promise<URTStrategyConfig[]> {
    const q = activeOnly ? '?active_only=true' : ''
    const res = await this.request<{ success: boolean; data: URTStrategyConfig[] }>(
      `${PREFIX}/strategy-configs${q}`
    )
    return res.data || []
  }

  async getStrategyConfig(id: number): Promise<URTStrategyConfig> {
    const res = await this.request<{ success: boolean; data: URTStrategyConfig }>(
      `${PREFIX}/strategy-configs/${id}`
    )
    return res.data
  }

  async createStrategyConfig(body: Partial<URTStrategyConfig> & { name: string }) {
    const res = await this.request<{ success: boolean; data: URTStrategyConfig }>(
      `${PREFIX}/strategy-configs`,
      { method: 'POST', body: JSON.stringify(body) }
    )
    return res.data
  }

  async updateStrategyConfig(id: number, body: Record<string, any>) {
    const res = await this.request<{ success: boolean; data: URTStrategyConfig }>(
      `${PREFIX}/strategy-configs/${id}`,
      { method: 'PUT', body: JSON.stringify(body) }
    )
    return res.data
  }

  async getDefaultParams(): Promise<Record<string, any>> {
    const res = await this.request<{ success: boolean; data: Record<string, any> }>(
      `${PREFIX}/default-params`
    )
    return res.data || {}
  }

  async getWatchlistUsers(): Promise<Array<{ user_id: number; username: string; watchlist_count: number }>> {
    const res = await this.request<{ success: boolean; data: any[] }>(`${PREFIX}/watchlist-users`)
    return res.data || []
  }

  async screenPreview(params?: { limit?: number; date?: string; config_id?: number }) {
    const q = new URLSearchParams()
    if (params?.limit) q.set('limit', String(params.limit))
    if (params?.date) q.set('date', params.date)
    if (params?.config_id) q.set('config_id', String(params.config_id))
    return this.request(`${PREFIX}/screen-preview?${q.toString()}`, { method: 'POST' })
  }

  async runPrecompute(params?: {
    date?: string
    config_id?: number
    limit?: number
    market?: 'CN' | 'HK' | string
  }) {
    const q = new URLSearchParams()
    if (params?.date) q.set('date', params.date)
    if (params?.config_id) q.set('config_id', String(params.config_id))
    if (params?.limit) q.set('limit', String(params.limit))
    if (params?.market) q.set('market', params.market)
    const qs = q.toString()
    return this.request(`${PREFIX}/precompute/run${qs ? `?${qs}` : ''}`, { method: 'POST' })
  }

  async createBacktest(body: Record<string, any>) {
    return this.request<{ success: boolean; task_id: string; data: any }>(
      `${PREFIX}/backtests`,
      { method: 'POST', body: JSON.stringify(body) }
    )
  }

  async listBacktests(limit = 50, status?: string) {
    const q = new URLSearchParams({ limit: String(limit) })
    if (status) q.set('status', status)
    const res = await this.request<{ success: boolean; data: any[] }>(
      `${PREFIX}/backtests?${q.toString()}`
    )
    return res.data || []
  }

  async getBacktest(taskId: string) {
    const res = await this.request<{ success: boolean; data: any }>(`${PREFIX}/backtests/${taskId}`)
    return res.data
  }

  async getBacktestLogs(taskId: string) {
    const res = await this.request<{ success: boolean; data: { logs: any[] } }>(
      `${PREFIX}/backtests/${taskId}/logs`
    )
    return res.data?.logs || []
  }

  async cancelBacktest(taskId: string) {
    return this.request(`${PREFIX}/backtests/${taskId}/cancel`, { method: 'POST' })
  }

  async rerunBacktest(taskId: string) {
    return this.request(`${PREFIX}/backtests/${taskId}/rerun`, { method: 'POST' })
  }

  async deleteBacktest(taskId: string) {
    return this.request(`${PREFIX}/backtests/${taskId}/delete`, { method: 'POST' })
  }

  async batchDeleteBacktests(taskIds: string[]) {
    return this.request(`${PREFIX}/backtests/batch-delete`, {
      method: 'POST',
      body: JSON.stringify({ task_ids: taskIds }),
    })
  }

  backtestExportUrl(taskId: string) {
    return `${API_BASE}${PREFIX}/backtests/${taskId}/export`
  }

  backtestExportPdfUrl(taskId: string) {
    return `${API_BASE}${PREFIX}/backtests/${taskId}/export-pdf`
  }

  async downloadBacktestPdf(taskId: string): Promise<Blob> {
    const response = await fetch(this.backtestExportPdfUrl(taskId), {
      headers: this.getAuthHeaders(),
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: '导出PDF失败' }))
      const detail = err.detail
      const msg =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map((d: any) => d.msg || d).join('; ')
            : err.message || '导出PDF失败'
      throw new Error(msg)
    }
    return response.blob()
  }

  async getReports(params?: { limit?: number; offset?: number }) {
    const q = new URLSearchParams()
    if (params?.limit) q.set('limit', String(params.limit))
    if (params?.offset) q.set('offset', String(params.offset))
    const res = await this.request<{ success: boolean; data: { reports: any[] } }>(
      `${PREFIX}/reports?${q.toString()}`
    )
    return res.data?.reports || []
  }

  async getReport(reportId: string) {
    const res = await this.request<{ success: boolean; data: any }>(`${PREFIX}/reports/${reportId}`)
    return res.data
  }

  async deleteReport(reportId: string) {
    return this.request(`${PREFIX}/reports/${reportId}/delete`, { method: 'POST' })
  }

  reportDownloadUrl(reportId: string) {
    return `${API_BASE}${PREFIX}/reports/${reportId}/download`
  }

  reportDownloadXlsxUrl(reportId: string) {
    return `${API_BASE}${PREFIX}/reports/${reportId}/download-xlsx`
  }

  backtestExportXlsxUrl(taskId: string) {
    return `${API_BASE}${PREFIX}/backtests/${taskId}/export-xlsx`
  }

  async getSystemStatus(): Promise<{
    runningBacktests: number
    totalReports: number
    pendingBacktests?: number
    failedBacktests?: number
    systemHealth?: string
  }> {
    const res = await this.request<{ success: boolean; data: any }>(`${PREFIX}/system/status`)
    return res.data
  }

  async getAuditLogs(params?: { limit?: number; offset?: number; log_type?: string }) {
    const q = new URLSearchParams()
    if (params?.limit) q.set('limit', String(params.limit))
    if (params?.offset) q.set('offset', String(params.offset))
    if (params?.log_type) q.set('log_type', params.log_type)
    const res = await this.request<{ success: boolean; data: { items: any[] } }>(
      `${PREFIX}/audit-logs?${q.toString()}`
    )
    return res.data?.items || []
  }
}

export const urtApiService = new URTApiService()
