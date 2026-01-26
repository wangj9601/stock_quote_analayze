/**
 * 系统监控API服务
 */

import { request } from '@/utils/request'

export const systemMonitoringApi = {
  // 获取监控概览
  getOverview() {
    return request.get('/system/monitoring/overview')
  },

  // 获取系统健康状态
  getSystemHealth() {
    return request.get('/system/monitoring/system-health')
  },

  // 获取性能指标
  getMetrics(timeRange: string = '1h', interval: string = '1m') {
    return request.get('/system/monitoring/metrics', {
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
    return request.get('/system/monitoring/alerts', { params })
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
    return request.post('/system/monitoring/alerts', data)
  },

  // 确认告警
  acknowledgeAlert(alertId: number, data: { acknowledged_by?: string }) {
    return request.post(`/system/monitoring/alerts/${alertId}/acknowledge`, data)
  },

  // 解决告警
  resolveAlert(alertId: number, resolvedBy: string = 'admin') {
    return request.post(`/system/monitoring/alerts/${alertId}/resolve`, { resolved_by: resolvedBy })
  },

  // 获取告警统计
  getAlertStatistics(days: number = 7) {
    return request.get('/system/monitoring/alerts/statistics', {
      params: { days }
    })
  },

  // 获取服务状态
  getServices() {
    return request.get('/system/monitoring/services')
  },

  // 获取告警规则
  getAlertRules() {
    return request.get('/system/monitoring/rules')
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
    return request.post('/system/monitoring/rules', data)
  },

  // 删除告警规则
  deleteAlertRule(ruleName: string) {
    return request.delete(`/system/monitoring/rules/${ruleName}`)
  },

  // 获取通知配置
  getNotificationConfigs() {
    return request.get('/system/monitoring/notifications/configs')
  },

  // 创建通知配置
  createNotificationConfig(data: {
    name: string
    channel: string
    enabled?: boolean
    config: Record<string, any>
    filters?: Record<string, any>
  }) {
    return request.post('/system/monitoring/notifications/configs', data)
  },

  // 删除通知配置
  deleteNotificationConfig(configName: string) {
    return request.delete(`/system/monitoring/notifications/configs/${configName}`)
  },

  // 清理旧告警
  cleanupOldAlerts(days: number = 30) {
    return request.post('/system/monitoring/maintenance/cleanup-alerts', null, {
      params: { days }
    })
  },

  // 启动监控
  startMonitoring() {
    return request.post('/system/monitoring/monitoring/start')
  },

  // 停止监控
  stopMonitoring() {
    return request.post('/system/monitoring/monitoring/stop')
  },

  // 获取监控状态
  getMonitoringStatus() {
    return request.get('/system/monitoring/monitoring/status')
  }
}
