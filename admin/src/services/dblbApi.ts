/**
 * DBLB 双底策略管理端 API（走 apiService，自动带 admin_token）
 */
import { apiService } from './api'

/** apiService baseURL 已是 /api/admin，此处只需相对路径 */
const PREFIX = '/dblb'

export type DblbScopeBody = {
  trade_date?: string
  config_id?: number
  status_filter?: string
  stock_pool_mode: 'industry_board' | 'concept_board' | 'stocks' | 'market'
  industry_board_codes?: string[]
  concept_board_codes?: string[]
  stock_codes?: string[]
  universe_limit?: number
  max_results?: number
  /** 默认 true：新命中入库以便利旧 */
  persist?: boolean
  /** true：忽略利旧，强制重算并覆盖入库 */
  force?: boolean
}

export const dblbApi = {
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
  trial(body: DblbScopeBody) {
    return apiService.post<{
      items: any[]
      hit_count?: number
      trade_date?: string
      [k: string]: unknown
    }>(`${PREFIX}/trial`, body)
  },
  triggerPrecompute(body: DblbScopeBody) {
    return apiService.post<{
      trade_date?: string
      screened?: number
      hit_count?: number
      saved?: number
      [k: string]: unknown
    }>(`${PREFIX}/precompute/trigger`, body)
  },
  listSignals(params: {
    trade_date: string
    config_id?: number
    status?: string
    code?: string
    limit?: number
    offset?: number
  }) {
    return apiService.get<{ items: any[]; total?: number }>(`${PREFIX}/signals`, { params })
  },
}

export default dblbApi
