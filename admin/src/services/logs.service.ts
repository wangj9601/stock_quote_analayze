import { apiService } from './api'
import type { LogsResponse, LogFilter, LogStats, LogTable, AppLogFileInfo } from '@/types/logs.types'

export class LogsService {
  async getLogs(params: LogFilter & { page: number; pageSize: number }): Promise<LogsResponse> {
    const queryParams = new URLSearchParams()
    
    if (params.type !== 'all') {
      queryParams.append('type', params.type)
    }
    if (params.level !== 'all') {
      queryParams.append('level', params.level)
    }
    if (params.startDate) {
      queryParams.append('start_date', params.startDate)
    }
    if (params.endDate) {
      queryParams.append('end_date', params.endDate)
    }
    if (params.keyword) {
      queryParams.append('keyword', params.keyword)
    }
    queryParams.append('page', params.page.toString())
    queryParams.append('page_size', params.pageSize.toString())
    
    return apiService.get<LogsResponse>(`/logs/query/historical_collect?${queryParams}`)
  }

  async getRealtimeLogs(params: LogFilter & { page: number; pageSize: number }): Promise<LogsResponse> {
    const queryParams = new URLSearchParams()
    
    if (params.level !== 'all') {
      queryParams.append('level', params.level)
    }
    if (params.startDate) {
      queryParams.append('start_date', params.startDate)
    }
    if (params.endDate) {
      queryParams.append('end_date', params.endDate)
    }
    if (params.keyword) {
      queryParams.append('keyword', params.keyword)
    }
    queryParams.append('page', params.page.toString())
    queryParams.append('page_size', params.pageSize.toString())
    
    return apiService.get<LogsResponse>(`/logs/query/realtime_collect?${queryParams}`)
  }

  async getOperationLogs(params: LogFilter & { page: number; pageSize: number }): Promise<LogsResponse> {
    const queryParams = new URLSearchParams()
    
    if (params.level !== 'all') {
      queryParams.append('level', params.level)
    }
    if (params.startDate) {
      queryParams.append('start_date', params.startDate)
    }
    if (params.endDate) {
      queryParams.append('end_date', params.endDate)
    }
    if (params.keyword) {
      queryParams.append('keyword', params.keyword)
    }
    queryParams.append('page', params.page.toString())
    queryParams.append('page_size', params.pageSize.toString())
    
    return apiService.get<LogsResponse>(`/operation-logs/query?${queryParams}`)
  }

  async getAppLogs(params: LogFilter & { page: number; pageSize: number }): Promise<LogsResponse & {
    stats?: LogStats
    files?: AppLogFileInfo[]
  }> {
    const queryParams = new URLSearchParams()
    const levels = params.level && params.level !== 'all' ? params.level : 'all'
    queryParams.append('levels', levels)
    if (params.startDate) {
      queryParams.append('start_date', params.startDate)
    }
    if (params.endDate) {
      queryParams.append('end_date', params.endDate)
    }
    if (params.keyword) {
      queryParams.append('keyword', params.keyword)
    }
    if (params.sourceFile) {
      queryParams.append('source_file', params.sourceFile)
    }
    queryParams.append('page', params.page.toString())
    queryParams.append('page_size', params.pageSize.toString())

    const raw = await apiService.get<any>(`/app-logs/query?${queryParams}`)
    const s = raw?.stats || {}
    return {
      data: raw?.data || [],
      total: raw?.total || 0,
      page: raw?.page || params.page,
      pageSize: raw?.page_size || params.pageSize,
      files: raw?.files || [],
      stats: {
        total: s.total ?? raw?.total ?? 0,
        success: 0,
        error: s.error ?? 0,
        successRate: 0,
        todayCount: 0,
        weekCount: 0,
        warning: s.warning ?? 0,
        info: s.info ?? 0,
        unknown: s.unknown ?? 0,
        bytesRead: s.bytes_read,
        windowBytes: s.window_bytes,
      },
    }
  }

  async getAppLogFiles(): Promise<AppLogFileInfo[]> {
    const raw = await apiService.get<{ files: AppLogFileInfo[] }>('/app-logs/files')
    return raw?.files || []
  }

  async getLogStats(): Promise<LogStats> {
    return apiService.get<LogStats>('/logs/stats')
  }

  async getLogTables(): Promise<LogTable[]> {
    return apiService.get<LogTable[]>('/logs/tables')
  }

  async exportLogs(params: LogFilter): Promise<Blob> {
    const queryParams = new URLSearchParams()
    
    if (params.type !== 'all') {
      queryParams.append('type', params.type)
    }
    if (params.level !== 'all') {
      queryParams.append('level', params.level)
    }
    if (params.startDate) {
      queryParams.append('start_date', params.startDate)
    }
    if (params.endDate) {
      queryParams.append('end_date', params.endDate)
    }
    if (params.keyword) {
      queryParams.append('keyword', params.keyword)
    }
    
    const response = await apiService.get(`/logs/export?${queryParams}`, {
      responseType: 'blob'
    })
    return response as Blob
  }
}

export const logsService = new LogsService() 