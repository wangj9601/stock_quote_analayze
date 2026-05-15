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
  wechat_notify_userids?: string[] | null
  wechat_app_profile?: string | null
  created_at: string
  updated_at: string
}

export interface ConfigUpdateRequest {
  enabled?: boolean
  channels?: string[]
  push_times?: string[]
  report_type?: string
  stock_codes?: string[] | null
  wechat_notify_userids?: string[] | null
  wechat_app_profile?: string | null
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
    // 使用 POST 避免生产环境对 PUT 返回 405 (Method Not Allowed)；后端同时支持 PUT 与 POST
    return apiService.post<EmailSenderConfigResponse>(`${this.base}/email-sender-config`, data)
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
    options?: {
      enabled?: boolean
      channels?: string[]
      push_times?: string[]
      report_type?: string
      wechat_notify_userids?: string[] | null
      wechat_app_profile?: string | null
    }
  ): Promise<UserPushConfigResponse> {
    const body: {
      user_id: number
      enabled?: boolean
      channels?: string[]
      push_times?: string[]
      report_type?: string
      wechat_notify_userids?: string[] | null
      wechat_app_profile?: string | null
    } = {
      user_id: userId
    }
    if (options?.enabled !== undefined) body.enabled = options.enabled
    if (options?.channels !== undefined) body.channels = options.channels
    if (options?.push_times !== undefined) body.push_times = options.push_times
    if (options?.report_type !== undefined) body.report_type = options.report_type
    if (options?.wechat_notify_userids !== undefined) body.wechat_notify_userids = options.wechat_notify_userids
    if (options?.wechat_app_profile !== undefined) body.wechat_app_profile = options.wechat_app_profile
    return apiService.post<UserPushConfigResponse>(`${this.base}/configs`, body)
  }

  /** 管理员按任务 id 更新一条推送配置（同一用户可有多条任务） */
  async adminUpdatePushConfigByConfigId(
    configId: number,
    data: ConfigUpdateRequest
  ): Promise<UserPushConfigResponse> {
    // 使用 POST 避免生产环境对 PUT/PATCH 返回 405；后端支持 PUT/POST/PATCH
    return apiService.post<UserPushConfigResponse>(`${this.base}/configs/${configId}`, data)
  }

  /** 管理员按任务 id 删除一条推送配置 */
  async deletePushConfigByConfigId(
    configId: number
  ): Promise<{ success: boolean; deleted: boolean; message: string }> {
    // 使用 POST 避免生产环境对 DELETE 返回 405；后端提供 POST /configs/{id}/delete 兼容接口
    return apiService.post<{ success: boolean; deleted: boolean; message: string }>(
      `${this.base}/configs/${configId}/delete`
    )
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
