import { API_BASE } from '@/config/api'

const PREFIX = '/api/admin/gms'

/** GET /api/screening/gms-strategy 响应（与网站端一致） */
export interface GmsStrategyScreeningResult {
  success: boolean
  data: any[]
  total?: number
  search_date?: string
  strategy_name?: string
  message?: string
  gms_trace_meta?: Record<string, unknown>
  trace_only?: boolean
  paging?: {
    enabled: boolean
    page: number
    page_size: number
    total: number
    total_pages: number
  }
}

export interface GMSScoringMechanism {
  id: string
  label: string
  description?: string
  version?: string
  supports_penalties?: boolean
}

export interface GMSPenaltyRuleType {
  id: string
  label: string
  description?: string
  default_points?: number
  default_amplitude_threshold_pct?: number
}

export interface GMSPenaltyRule {
  id: string
  enabled: boolean
  points: number
  label?: string
  amplitude_threshold_pct?: number
  half_when_ma60_flat?: boolean
}

export interface GMSStrategyVersion {
  id: number
  strategy_code: string
  version_name: string
  version_no: number
  description?: string
  config_id?: number | null
  is_active: boolean
  created_by?: string
  created_at?: string
  updated_at?: string
  scoring_mechanism?: string
  scoring_mechanism_label?: string
  penalty_rules?: GMSPenaltyRule[]
}

export interface GMSStrategyVersionFull {
  version: GMSStrategyVersion
  stock_count: number
  config: GMSStrategyConfig | null
}

export interface GMSStrategyConfig {
  id: number
  name: string
  version_label?: string | null
  description?: string | null
  config_params?: Record<string, any>
  is_active: boolean
  is_default: boolean
  precompute_enabled: boolean
  scoring_mechanism?: string
  scoring_mechanism_label?: string
  parent_id?: number | null
  created_by?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface GMSStrategyVersionStock {
  id: number
  version_id: number
  market: 'A' | 'HK'
  stock_code: string
  stock_name?: string
  industry?: string | null
  sort_order: number
  status: string
  is_verified: boolean
  remark?: string
  current_price?: number
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
  async getSystemStatus(): Promise<{
    runningBacktests: number
    totalReports: number
    systemHealth: string
    pendingBacktests?: number
    failedBacktests?: number
    screeningStats?: Record<string, unknown>
    latestPrecomputeRuns?: Array<Record<string, unknown>>
    recentJobRuns?: Array<Record<string, unknown>>
    alertMessage?: string | null
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

  async getGmsScreeningPreferences(): Promise<Record<string, unknown>> {
    const res = await this.request<{ success: boolean; data: Record<string, unknown> }>(
      '/api/user/preferences/gms-screening'
    )
    return res.data || {}
  }

  async putGmsScreeningPreferences(body: Record<string, unknown>) {
    const res = await this.request<{ success: boolean; data: Record<string, unknown> }>(
      '/api/user/preferences/gms-screening',
      { method: 'PUT', body: JSON.stringify(body) }
    )
    return res.data
  }

  /** 创建回测任务 */
  async createBacktest(body: {
    task_name?: string
    market?: string
    cn_board_segment?: string
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
    /** 单笔仓位 0~1，仅 trade_simulation */
    position_fraction?: number
    stock_pool_mode?: string
    stock_code?: string
    stock_pool?: string[]
    watchlist_user_id?: number
    strategy_config_id?: number
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
    // 兼容生产环境，优先使用 POST /delete
    await this.request(`${PREFIX}/backtests/${taskId}/delete`, { method: 'POST' })
  }

  /** 批量删除任务 */
  async batchDeleteBacktestTasks(taskIds: string[]) {
    const res = await this.request<{ success: boolean; data: { deleted: number; failed?: string[]; failed_count?: number } }>(
      `${PREFIX}/backtests/batch-delete`,
      {
        method: 'POST',
        body: JSON.stringify({ task_ids: taskIds }),
      }
    )
    return res.data
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

  /** 删除历史报告 */
  async deleteReport(reportId: string) {
    await this.request(`${PREFIX}/reports/${reportId}/delete`, { method: 'POST' })
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

  /** 读取 GMS 默认策略配置（兼容旧接口） */
  async getConfig(): Promise<{ data: Record<string, any>; config_id?: number }> {
    const res = await this.request<{ success: boolean; data: any; config_id?: number }>(`${PREFIX}/config`)
    return { data: res.data, config_id: res.config_id }
  }

  /** 更新 GMS 默认策略配置 */
  async saveConfig(config: Record<string, any>) {
    const res = await this.request<{ success: boolean; data: any; config_id?: number }>(`${PREFIX}/config/update`, {
      method: 'POST',
      body: JSON.stringify({ config }),
    })
    return res.data
  }

  /** 策略参数版本列表（默认仅共享版本 default / gms_penalty） */
  async listStrategyConfigs(activeOnly = false, canonicalOnly = true): Promise<GMSStrategyConfig[]> {
    const params = new URLSearchParams()
    if (activeOnly) params.set('active_only', 'true')
    if (canonicalOnly) params.set('canonical_only', 'true')
    const q = params.toString() ? `?${params.toString()}` : ''
    const res = await this.request<{ success: boolean; data: GMSStrategyConfig[] }>(`${PREFIX}/strategy-configs${q}`)
    return res.data || []
  }

  async getStrategyConfig(configId: number): Promise<GMSStrategyConfig> {
    const res = await this.request<{ success: boolean; data: GMSStrategyConfig }>(`${PREFIX}/strategy-configs/${configId}`)
    return res.data
  }

  async createStrategyConfig(body: {
    name: string
    version_label?: string
    description?: string
    config_params?: Record<string, any>
    is_active?: boolean
    is_default?: boolean
    precompute_enabled?: boolean
    created_by?: string
  }) {
    const res = await this.request<{ success: boolean; data: GMSStrategyConfig }>(`${PREFIX}/strategy-configs`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
    return res.data
  }

  async updateStrategyConfig(
    configId: number,
    body: {
      name?: string
      version_label?: string
      description?: string
      config?: Record<string, any>
      is_active?: boolean
      precompute_enabled?: boolean
      change_note?: string
    }
  ) {
    const res = await this.request<{ success: boolean; data: GMSStrategyConfig }>(
      `${PREFIX}/strategy-configs/${configId}/update`,
      { method: 'POST', body: JSON.stringify(body) }
    )
    return res.data
  }

  async cloneStrategyConfig(configId: number, newName: string, precomputeEnabled = false) {
    const res = await this.request<{ success: boolean; data: GMSStrategyConfig }>(
      `${PREFIX}/strategy-configs/${configId}/clone`,
      { method: 'POST', body: JSON.stringify({ new_name: newName, precompute_enabled: precomputeEnabled }) }
    )
    return res.data
  }

  async setStrategyConfigDefault(configId: number) {
    const res = await this.request<{ success: boolean; data: GMSStrategyConfig }>(
      `${PREFIX}/strategy-configs/${configId}/default`,
      { method: 'PATCH' }
    )
    return res.data
  }

  async compareStrategyConfigs(configIdA: number, configIdB: number) {
    const q = new URLSearchParams({
      config_id_a: String(configIdA),
      config_id_b: String(configIdB),
    })
    const res = await this.request<{ success: boolean; data: any }>(`${PREFIX}/strategy-configs/compare?${q}`)
    return res.data
  }

  async deactivateStrategyConfig(configId: number) {
    const res = await this.request<{ success: boolean; data: GMSStrategyConfig }>(
      `${PREFIX}/strategy-configs/${configId}/deactivate`,
      { method: 'POST' }
    )
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

  async getScoringMechanisms(): Promise<GMSScoringMechanism[]> {
    const res = await this.request<{ success: boolean; data: GMSScoringMechanism[] }>(`${PREFIX}/scoring-mechanisms`)
    return res.data || []
  }

  async getPenaltyRuleTypes(): Promise<GMSPenaltyRuleType[]> {
    const res = await this.request<{ success: boolean; data: GMSPenaltyRuleType[] }>(`${PREFIX}/penalty-rule-types`)
    return res.data || []
  }

  async getStrategyVersionFull(versionId: number): Promise<GMSStrategyVersionFull> {
    const res = await this.request<{ success: boolean; data: GMSStrategyVersionFull }>(
      `${PREFIX}/strategy-versions/${versionId}/full`
    )
    return res.data
  }

  async updateStrategyVersionScoring(
    versionId: number,
    body: {
      scoring_mechanism?: string
      penalty_rules?: GMSPenaltyRule[]
      config?: Record<string, unknown>
    }
  ) {
    const res = await this.request<{ success: boolean; data: GMSStrategyVersion }>(
      `${PREFIX}/strategy-versions/${versionId}/scoring`,
      { method: 'PUT', body: JSON.stringify(body) }
    )
    return res.data
  }

  async createStrategyVersion(body: {
    strategy_code: string
    version_name: string
    version_no: number
    description?: string
    config_id?: number | null
    is_active?: boolean
    created_by?: string
    auto_create_config?: boolean
    scoring_mechanism?: string
    penalty_rules?: GMSPenaltyRule[]
    config_params?: Record<string, unknown>
  }) {
    const res = await this.request<{ success: boolean; data: GMSStrategyVersion }>(`${PREFIX}/strategy-versions`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
    return res.data
  }

  async updateStrategyVersion(versionId: number, body: Partial<GMSStrategyVersion>) {
    // 兼容生产环境，优先使用 POST /update
    const res = await this.request<{ success: boolean; data: GMSStrategyVersion }>(`${PREFIX}/strategy-versions/${versionId}/update`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
    return res.data
  }

  async deleteStrategyVersion(versionId: number) {
    // 兼容生产环境，优先使用 POST /delete
    await this.request(`${PREFIX}/strategy-versions/${versionId}/delete`, { method: 'POST' })
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
    is_verified?: boolean
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
    // 兼容生产环境，优先使用 POST /update
    const res = await this.request<{ success: boolean; data: GMSStrategyVersionStock }>(`${PREFIX}/strategy-version-stocks/${stockId}/update`, {
      method: 'POST',
      body: JSON.stringify(safe),
    })
    return res.data
  }

  async deleteStrategyVersionStock(stockId: number) {
    // 兼容生产环境，优先使用 POST /delete
    await this.request(`${PREFIX}/strategy-version-stocks/${stockId}/delete`, { method: 'POST' })
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
    clear_existing?: boolean
  }) {
    const res = await this.request<{
      success: boolean
      data: {
        cleared_count?: number
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

  /**
   * 与网站选股页相同：`GET /api/screening/gms-strategy`（实时计算 + trace 缓存，非仅读 trace 表）。
   * 使用管理端 Bearer Token；scope=watchlist 时可传 watchlist_user_id（需管理员 JWT）。
   */
  async getGmsStrategyScreening(params: URLSearchParams): Promise<GmsStrategyScreeningResult> {
    const qs = params.toString()
    const url = `${API_BASE}/api/screening/gms-strategy${qs ? `?${qs}` : ''}`
    const response = await fetch(url, {
      headers: {
        ...this.getAuthHeaders(),
      },
    })
    const text = await response.text()
    if (!response.ok) {
      let detail: string = `HTTP ${response.status}`
      try {
        const j = JSON.parse(text) as { detail?: unknown; message?: string }
        const d = j.detail
        detail =
          typeof d === 'string'
            ? d
            : Array.isArray(d)
              ? (d as { msg?: string }[]).map((x) => x.msg || '').join('; ') || detail
              : j.message || detail
      } catch {
        if (text && text.length < 300) detail = text
      }
      throw new Error(detail)
    }
    try {
      return JSON.parse(text) as GmsStrategyScreeningResult
    } catch {
      throw new Error('服务器返回非 JSON')
    }
  }
}

export const gmsApiService = new GMSApiService()
