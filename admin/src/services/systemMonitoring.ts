/**
 * 系统监控API服务
 */

import { apiService } from './api'

export const systemMonitoringApi = {
  // 获取监控概览
  getOverview() {
    return apiService.get('/system/monitoring/overview')
  },

  // 获取系统健康状态
  getSystemHealth() {
    return apiService.get('/system/monitoring/system-health')
  },

  // 获取性能指标
  getMetrics(timeRange: string = '1h', interval: string = '1m') {
    return apiService.get('/system/monitoring/metrics', {
      params: { time_range: timeRange, interval }
    })
  },

  // 获取告警列表
  getAlerts(params: {
    limit?: number
    level?: string
    alert_type?: string
    acknowledged?: boolean
    start_time?: string
    end_time?: string
  } = {}) {
    return apiService.get('/system/monitoring/alerts', { params })
  },

  // 创建告警
  createAlert(data: {
    level: string
    title: string
    message: string
    alert_type?: string
    source?: string
    metadata?: Record<string, any>
  }) {
    return apiService.post('/system/monitoring/alerts', data)
  },

  // 确认告警
  acknowledgeAlert(alertId: number, data: { acknowledged_by?: string }) {
    return apiService.post(`/system/monitoring/alerts/${alertId}/acknowledge`, data)
  },

  // 解决告警
  resolveAlert(alertId: number, resolvedBy: string = 'admin') {
    return apiService.post(`/system/monitoring/alerts/${alertId}/resolve`, { resolved_by: resolvedBy })
  },

  // 获取告警统计
  getAlertStatistics(days: number = 7) {
    return apiService.get('/system/monitoring/alerts/statistics', {
      params: { days }
    })
  },

  // 获取服务状态
  getServices() {
    return apiService.get('/system/monitoring/services')
  },

  // 获取告警规则
  getAlertRules() {
    return apiService.get('/system/monitoring/rules')
  },

  // 创建告警规则
  createAlertRule(data: {
    name: string
    metric_name: string
    condition: string
    threshold: number
    level: string
    alert_type: string
    message_template: string
    enabled?: boolean
    description?: string
  }) {
    return apiService.post('/system/monitoring/rules', data)
  },

  // 删除告警规则
  deleteAlertRule(ruleName: string) {
    return apiService.delete(`/system/monitoring/rules/${ruleName}`)
  },

  // 获取通知配置
  getNotificationConfigs() {
    return apiService.get('/system/monitoring/notifications/configs')
  },

  // 创建通知配置
  createNotificationConfig(data: {
    name: string
    channel: string
    enabled?: boolean
    config: Record<string, any>
    filters?: Record<string, any>
  }) {
    return apiService.post('/system/monitoring/notifications/configs', data)
  },

  // 删除通知配置
  deleteNotificationConfig(configName: string) {
    return apiService.delete(`/system/monitoring/notifications/configs/${configName}`)
  },

  // 清理旧告警
  cleanupOldAlerts(days: number = 30) {
    return apiService.post('/system/monitoring/maintenance/cleanup-alerts', null, {
      params: { days }
    })
  },

  // 启动监控
  startMonitoring() {
    return apiService.post('/system/monitoring/monitoring/start')
  },

  // 停止监控
  stopMonitoring() {
    return apiService.post('/system/monitoring/monitoring/stop')
  },

  // 获取监控状态
  getMonitoringStatus() {
    return apiService.get('/system/monitoring/monitoring/status')
  }
}
