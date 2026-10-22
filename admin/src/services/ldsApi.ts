/**
 * LDS 龙头战法策略管理端 API
 */
import { apiService } from './api'

const PREFIX = '/lds'

export type LdsScopeBody = {
  trade_date?: string
  config_id?: number
  stock_pool_mode: 'industry_board' | 'concept_board' | 'stocks' | 'market'
  industry_board_codes?: string[]
  concept_board_codes?: string[]
  stock_codes?: string[]
  universe_limit?: number
  max_results?: number
  persist?: boolean
  force?: boolean
}

export const ldsApi = {
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
  trial(body: LdsScopeBody) {
    return apiService.post<{
      items: any[]
      hit_count?: number
      trade_date?: string
      [k: string]: unknown
    }>(`${PREFIX}/trial`, body)
  },
  triggerPrecompute(body: LdsScopeBody) {
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
    code?: string
    role?: string
    watch_ready?: boolean
    limit?: number
    offset?: number
  }) {
    return apiService.get<{ items: any[]; total?: number }>(`${PREFIX}/signals`, { params })
  },
}

export default ldsApi
