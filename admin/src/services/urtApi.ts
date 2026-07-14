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
      throw new Error(err.detail || err.message || 'Request failed')
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

  async screenPreview(params?: { limit?: number; date?: string; config_id?: number }) {
    const q = new URLSearchParams()
    if (params?.limit) q.set('limit', String(params.limit))
    if (params?.date) q.set('date', params.date)
    if (params?.config_id) q.set('config_id', String(params.config_id))
    return this.request(`${PREFIX}/screen-preview?${q.toString()}`, { method: 'POST' })
  }

  async runPrecompute(params?: { date?: string; config_id?: number; limit?: number }) {
    const q = new URLSearchParams()
    if (params?.date) q.set('date', params.date)
    if (params?.config_id) q.set('config_id', String(params.config_id))
    if (params?.limit) q.set('limit', String(params.limit))
    return this.request(`${PREFIX}/precompute/run?${q.toString()}`, { method: 'POST' })
  }

  async createBacktest(body: Record<string, any>) {
    const res = await this.request<{ success: boolean; task_id: string; data: any }>(
      `${PREFIX}/backtests`,
      { method: 'POST', body: JSON.stringify(body) }
    )
    return res
  }

  async listBacktests(limit = 50) {
    const res = await this.request<{ success: boolean; data: any[] }>(
      `${PREFIX}/backtests?limit=${limit}`
    )
    return res.data || []
  }

  async getBacktest(taskId: string) {
    const res = await this.request<{ success: boolean; data: any }>(`${PREFIX}/backtests/${taskId}`)
    return res.data
  }

  async cancelBacktest(taskId: string) {
    return this.request(`${PREFIX}/backtests/${taskId}/cancel`, { method: 'POST' })
  }

  async deleteBacktest(taskId: string) {
    return this.request(`${PREFIX}/backtests/${taskId}/delete`, { method: 'POST' })
  }

  backtestExportUrl(taskId: string) {
    return `${API_BASE}${PREFIX}/backtests/${taskId}/export`
  }
}

export const urtApiService = new URTApiService()
