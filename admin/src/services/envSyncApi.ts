import { API_BASE } from '@/config/api'

const PREFIX = '/api/admin/env-sync'

export type EnvSyncModuleCode = string

export type SyncDateRange = {
  start_date?: string | null
  end_date?: string | null
}

class EnvSyncApiService {
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
      const msg =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map((d: any) => d.msg || d).join('; ')
            : JSON.stringify(detail)
      throw new Error(msg || `HTTP ${response.status}`)
    }
    return response.json()
  }

  getServerConfig() {
    return this.request(`${PREFIX}/server-config`)
  }

  updateServerConfig(body: { enabled?: boolean; sync_key?: string; rotate?: boolean }) {
    return this.request(`${PREFIX}/server-config`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
  }

  getClientConfig() {
    return this.request(`${PREFIX}/client-config`)
  }

  updateClientConfig(body: {
    enabled?: boolean
    prod_base_url?: string
    sync_key?: string
  }) {
    return this.request(`${PREFIX}/client-config`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
  }

  testConnection() {
    return this.request(`${PREFIX}/test-connection`, { method: 'POST', body: '{}' })
  }

  listModules() {
    return this.request<{
      groups: Array<{
        group: string
        group_name: string
        name?: string
        requires_date_range?: boolean
        date_range_optional?: boolean
        items: Array<{
          code: string
          name: string
          desc?: string
          requires_date_range?: boolean
          date_range_optional?: boolean
        }>
      }>
      legacy_modules?: Array<{ code: string; name: string; desc?: string }>
      all_resources?: string[]
      default_resources?: string[]
      date_range_required?: string[]
      date_range_optional?: string[]
    }>(`${PREFIX}/modules`)
  }

  pull(modules?: EnvSyncModuleCode[], range?: SyncDateRange) {
    return this.request(`${PREFIX}/pull`, {
      method: 'POST',
      body: JSON.stringify({
        modules: modules || null,
        start_date: range?.start_date || null,
        end_date: range?.end_date || null,
      }),
    })
  }

  push(modules?: EnvSyncModuleCode[], range?: SyncDateRange) {
    return this.request(`${PREFIX}/push`, {
      method: 'POST',
      body: JSON.stringify({
        modules: modules || null,
        start_date: range?.start_date || null,
        end_date: range?.end_date || null,
      }),
    })
  }
}

export const envSyncApi = new EnvSyncApiService()
