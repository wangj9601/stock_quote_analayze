/**
 * RPE 管理端 API
 */
import axios from 'axios'

const PREFIX = '/api/admin/rpe'

function authHeaders() {
  const token = localStorage.getItem('token') || localStorage.getItem('admin_token') || ''
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export const rpeApi = {
  listConfigs() {
    return axios.get(`${PREFIX}/strategy-configs`, { headers: authHeaders() })
  },
  createConfig(body: Record<string, unknown>) {
    return axios.post(`${PREFIX}/strategy-configs`, body, { headers: authHeaders() })
  },
  updateConfig(id: number, body: Record<string, unknown>) {
    return axios.put(`${PREFIX}/strategy-configs/${id}/update`, body, { headers: authHeaders() })
  },
  setDefault(id: number) {
    return axios.patch(`${PREFIX}/strategy-configs/${id}/default`, {}, { headers: authHeaders() })
  },
  listBacktests(limit = 50) {
    return axios.get(`${PREFIX}/backtests`, { params: { limit }, headers: authHeaders() })
  },
  getBacktest(taskId: string) {
    return axios.get(`${PREFIX}/backtests/${taskId}`, { headers: authHeaders() })
  },
  createBacktest(body: Record<string, unknown>) {
    return axios.post(`${PREFIX}/backtests`, body, { headers: authHeaders() })
  },
  triggerPrecompute(params?: { config_id?: number; trade_date?: string; max_boards?: number }) {
    return axios.post(`${PREFIX}/precompute/trigger`, null, { params, headers: authHeaders() })
  },
  selectionResults(params?: Record<string, unknown>) {
    return axios.get(`${PREFIX}/selection-results`, { params, headers: authHeaders() })
  },
}

export default rpeApi
