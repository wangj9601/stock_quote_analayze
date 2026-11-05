/**
 * RPE 管理端 API（走 apiService，自动带 admin_token）
 */
import { apiService } from './api'

/** apiService baseURL 已是 /api/admin，此处只需相对路径 */
const PREFIX = '/rpe'

export const rpeApi = {
  listConfigs() {
    return apiService.get<{ items: any[] }>(`${PREFIX}/strategy-configs`)
  },
  createConfig(body: Record<string, unknown>) {
    return apiService.post(`${PREFIX}/strategy-configs`, body)
  },
  updateConfig(id: number, body: Record<string, unknown>) {
    return apiService.put(`${PREFIX}/strategy-configs/${id}/update`, body)
  },
  setDefault(id: number) {
    return apiService.patch(`${PREFIX}/strategy-configs/${id}/default`, {})
  },
  listBacktests(limit = 50) {
    return apiService.get<{ items: any[] }>(`${PREFIX}/backtests`, { params: { limit } })
  },
  getBacktest(taskId: string) {
    return apiService.get(`${PREFIX}/backtests/${taskId}`)
  },
  createBacktest(body: Record<string, unknown>) {
    return apiService.post<{ task_id: string; status: string }>(`${PREFIX}/backtests`, body)
  },
  triggerPrecompute(params?: { config_id?: number; trade_date?: string; max_boards?: number }) {
    return apiService.post(`${PREFIX}/precompute/trigger`, null, { params })
  },
  /**
   * 预计算入场信号。必须走 GET /rpe/signals（即 /api/admin/rpe/signals），
   * 不要用 selection-results。响应为顶层 JSON，鉴权与其它 rpeApi 相同（admin JWT）。
   * 省略 trade_date / config_id 时由后端解析。
   */
  listSignals(params: {
    trade_date?: string
    config_id?: number
    code?: string
    limit?: number
    offset?: number
  }) {
    const query: Record<string, string | number> = {
      limit: params.limit ?? 50,
      offset: params.offset ?? 0,
    }
    if (params.trade_date) query.trade_date = params.trade_date
    if (params.config_id != null) query.config_id = params.config_id
    if (params.code) query.code = params.code
    return apiService.get<{
      items: any[]
      total: number
      trade_date: string
      config_id: number
      last_written_at: string | null
      has_any_trace: boolean
    }>(`${PREFIX}/signals`, { params: query })
  },
  selectionResults(params?: Record<string, unknown>) {
    return apiService.get(`${PREFIX}/selection-results`, { params })
  },
}

export default rpeApi
