import { apiService } from './api'

export interface LoginLogItem {
  id: number
  channel: string
  user_id?: number | null
  username: string
  success: boolean
  failure_reason?: string | null
  ip?: string | null
  user_agent?: string | null
  created_at?: string | null
}

export interface LoginLogListResponse {
  items: LoginLogItem[]
  total: number
  page: number
  page_size: number
}

export interface LoginLogQuery {
  channel?: string
  username?: string
  success?: boolean
  start_date?: string
  end_date?: string
  page?: number
  page_size?: number
}

export const loginLogsService = {
  async query(params: LoginLogQuery): Promise<LoginLogListResponse> {
    return apiService.get<LoginLogListResponse>('/login-logs', { params })
  },
}
