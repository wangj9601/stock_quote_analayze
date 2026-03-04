import { apiService } from './api'

export interface EmailSenderConfigResponse {
  id: number
  host: string
  port: number
  username: string
  password_masked?: string
  from_email: string
  from_name: string
  use_tls: boolean
  updated_at?: string
}

export interface EmailSenderConfigUpdateRequest {
  host?: string
  port?: number
  username?: string
  password?: string
  from_email?: string
  from_name?: string
  use_tls?: boolean
}

export interface UserPushConfigResponse {
  id: number
  user_id: number
  enabled: boolean
  channels: string[]
  push_times: string[]
  report_type: string
  stock_codes?: string[] | null
  created_at: string
  updated_at: string
}

export interface ConfigUpdateRequest {
  enabled?: boolean
  channels?: string[]
  push_times?: string[]
  report_type?: string
  stock_codes?: string[] | null
}

export interface EmailSendLogResponse {
  id: number
  user_id: number
  username?: string
  to_email: string
  subject: string
  report_type: string
  push_record_id?: number
  sent_at: string
  success: boolean
  error_message?: string | null
  created_at?: string
}

export class PushService {
  private base = '/push'

  async getEmailSenderConfig(): Promise<EmailSenderConfigResponse> {
    return apiService.get<EmailSenderConfigResponse>(`${this.base}/email-sender-config`)
  }

  async updateEmailSenderConfig(data: EmailSenderConfigUpdateRequest): Promise<EmailSenderConfigResponse> {
    return apiService.put<EmailSenderConfigResponse>(`${this.base}/email-sender-config`, data)
  }

  async testEmailSenderConfig(to_email: string): Promise<{ success: boolean; message: string }> {
    return apiService.post<{ success: boolean; message: string }>(`${this.base}/email-sender-config/test`, {
      to_email
    })
  }

  async getAllPushConfigs(limit = 100, offset = 0): Promise<UserPushConfigResponse[]> {
    return apiService.get<UserPushConfigResponse[]>(`${this.base}/configs`, {
      params: { limit, offset }
    })
  }

  /** 管理员为指定用户新建推送配置（用户来源于 user 表，配置写入 user_push_configs 表） */
  async createPushConfig(
    userId: number,
    options?: { enabled?: boolean; channels?: string[]; push_times?: string[]; report_type?: string }
  ): Promise<UserPushConfigResponse> {
    const body: { user_id: number; enabled?: boolean; channels?: string[]; push_times?: string[]; report_type?: string } = {
      user_id: userId
    }
    if (options?.enabled !== undefined) body.enabled = options.enabled
    if (options?.channels !== undefined) body.channels = options.channels
    if (options?.push_times !== undefined) body.push_times = options.push_times
    if (options?.report_type !== undefined) body.report_type = options.report_type
    return apiService.post<UserPushConfigResponse>(`${this.base}/configs`, body)
  }

  async adminUpdatePushConfig(userId: number, data: ConfigUpdateRequest): Promise<UserPushConfigResponse> {
    return apiService.put<UserPushConfigResponse>(`${this.base}/configs/${userId}`, data)
  }

  /** 管理员删除指定用户的邮件推送配置 */
  async deletePushConfig(userId: number): Promise<{ success: boolean; deleted: boolean; message: string }> {
    return apiService.delete<{ success: boolean; deleted: boolean; message: string }>(`${this.base}/configs/${userId}`)
  }

  async getEmailLogs(params: {
    user_id?: number
    start_date?: string
    end_date?: string
    success?: boolean
    limit?: number
    offset?: number
  }): Promise<EmailSendLogResponse[]> {
    return apiService.get<EmailSendLogResponse[]>(`${this.base}/email-logs`, { params })
  }
}

export const pushService = new PushService()
