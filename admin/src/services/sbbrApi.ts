/**
 * SBBR 管理端 API（走 apiService，自动带 admin_token）
 */
import { apiService } from './api'

/** apiService baseURL 已是 /api/admin，此处只需相对路径 */
const PREFIX = '/sbbr'

export const sbbrApi = {
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
  triggerPrecompute(params?: { config_id?: number; trade_date?: string }) {
    return apiService.post(`${PREFIX}/precompute/trigger`, null, { params })
  },
}

export default sbbrApi
