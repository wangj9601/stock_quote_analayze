import { apiService } from './api'

/** 与 backend_api triple_volume_observe_routes.admin_router 前缀一致（baseURL 已为 /api/admin） */
const TVO = '/triple-volume-observe'

export interface ObserveRow {
  id: number
  market: string
  code: string
  name?: string | null
  observe_trade_date: string
  prev_trade_date?: string | null
  prev_volume?: number | null
  curr_volume?: number | null
  volume_ratio_actual?: number | null
  status: string
  vsb_evaluated_at?: string | null
  created_at: string
  updated_at: string
}

export interface ObserveListResponse {
  total: number
  page: number
  page_size: number
  items: ObserveRow[]
}

export async function listTripleVolumeObserve(params: {
  market?: string
  status?: string
  page?: number
  page_size?: number
}): Promise<ObserveListResponse> {
  return apiService.get<ObserveListResponse>(`${TVO}/list`, { params })
}

export async function exportTripleVolumeObserveBlob(params: {
  market?: string
  status?: string
}): Promise<Blob> {
  const { default: axios } = await import('axios')
  const { getResolvedApiBaseUrl } = await import('@/config/environment')
  const base = (getResolvedApiBaseUrl() || '/api/admin').replace(/\/$/, '')
  const token = localStorage.getItem('admin_token')
  const res = await axios.get(`${base}${TVO}/export`, {
    params,
    responseType: 'blob',
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  })
  return res.data as Blob
}

export async function adminRunScan(): Promise<unknown> {
  return apiService.post(`${TVO}/run-scan`, {})
}

export async function adminRunEval(): Promise<unknown> {
  return apiService.post(`${TVO}/run-eval`, {})
}
