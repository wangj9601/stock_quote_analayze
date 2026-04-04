import { API_BASE } from '@/config/api'

const PREFIX = '/api/admin/gms'

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
    stock_pool_mode?: string
    stock_code?: string
    stock_pool?: string[]
  }) {
    const res = await this.request<{ success: boolean; data: { task_id: string } }>(`${PREFIX}/backtests`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
    return res.data.task_id
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
}

export const gmsApiService = new GMSApiService()
