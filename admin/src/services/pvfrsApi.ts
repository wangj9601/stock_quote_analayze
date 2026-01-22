import { API_BASE } from '@/config/api'

class PVFRSApiService {
  private getAuthHeaders(): Record<string, string> {
    const token = localStorage.getItem('admin_token')
    return token ? { Authorization: `Bearer ${token}` } : {}
  }

  private async request(url: string, options: RequestInit = {}) {
    const response = await fetch(`${API_BASE}${url}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
        ...options.headers,
      },
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Request failed' }))
      throw new Error(error.message || error.detail || 'Request failed')
    }

    return response.json()
  }

  // 系统状态
  async getSystemStatus() {
    return this.request('/api/frontend/pvfrs/system/status')
  }

  // 回测任务管理
  async createBacktestTask(taskData: any) {
    // 转换前端格式到后端期望的格式
    const backendData: any = {
      name: taskData.name,
      start_date: taskData.startDate || taskData.start_date,
      end_date: taskData.endDate || taskData.end_date,
      initial_capital: taskData.initialCapital || taskData.initial_capital || 100000,
      strategy_params: taskData.strategy_params || {},
      risk_params: taskData.risk_params || {}
    }

    // 处理股票池
    if (taskData.mode === 'single' && taskData.stockCode) {
      backendData.code = taskData.stockCode
    } else if (taskData.mode === 'batch' && taskData.stockList) {
      backendData.stockList = taskData.stockList
    } else if (taskData.stock_pool) {
      backendData.stock_pool = taskData.stock_pool
    } else if (taskData.code) {
      backendData.code = taskData.code
    } else if (taskData.stock_codes) {
      backendData.stock_codes = taskData.stock_codes
    }

    return this.request('/api/admin/pvfrs/backtest/create', {
      method: 'POST',
      body: JSON.stringify(backendData),
    })
  }

  async getBacktestTrades(taskId: string) {
    return this.request(`/api/admin/pvfrs/backtest/trades/${taskId}`)
  }

  async getBacktestTasks(params: any = {}) {
    const queryString = new URLSearchParams(params).toString()
    return this.request(`/api/admin/pvfrs/backtest/tasks?${queryString}`)
  }

  async getBacktestTask(taskId: string) {
    return this.request(`/api/admin/pvfrs/backtest/tasks/${taskId}`)
  }

  async getTaskLogs(taskId: string) {
    return this.request(`/api/admin/pvfrs/backtest/logs/${taskId}`)
  }

  async pauseBacktestTask(taskId: string) {
    return this.request(`/api/admin/pvfrs/backtest/tasks/${taskId}/pause`, {
      method: 'POST',
    })
  }

  async cancelBacktestTask(taskId: string) {
    return this.request(`/api/admin/pvfrs/backtest/tasks/${taskId}/cancel`, {
      method: 'POST',
    })
  }

  async clearCompletedTasks() {
    return this.request('/api/admin/pvfrs/backtest/tasks/completed', {
      method: 'DELETE',
    })
  }

  // 报告管理
  async getReports(params: any = {}) {
    const queryString = new URLSearchParams(params).toString()
    return this.request(`/api/admin/pvfrs/reports?${queryString}`)
  }

  async getReport(reportId: string) {
    return this.request(`/api/admin/pvfrs/reports/${reportId}`)
  }

  async generateReport(reportData: any) {
    return this.request('/api/admin/pvfrs/reports', {
      method: 'POST',
      body: JSON.stringify(reportData),
    })
  }

  async downloadReport(reportId: string) {
    const response = await fetch(`${API_BASE}/api/admin/pvfrs/reports/${reportId}/download`, {
      headers: this.getAuthHeaders(),
    })

    if (!response.ok) {
      throw new Error('Download failed')
    }

    return response.blob()
  }

  async deleteReport(reportId: string) {
    return this.request(`/api/admin/pvfrs/reports/${reportId}`, {
      method: 'DELETE',
    })
  }

  async compareReports(reportIds: string[]) {
    return this.request('/api/admin/pvfrs/reports/compare', {
      method: 'POST',
      body: JSON.stringify({ report_ids: reportIds }),
    })
  }

  async getReportOverview() {
    return this.request('/api/admin/pvfrs/reports/overview')
  }

  // 策略配置
  async getStrategyConfig() {
    return this.request('/api/admin/pvfrs/config')
  }

  async saveStrategyConfig(configData: any) {
    return this.request('/api/admin/pvfrs/config', {
      method: 'POST',
      body: JSON.stringify(configData),
    })
  }

  async testStrategyConfig(configData: any) {
    return this.request('/api/admin/pvfrs/config/test', {
      method: 'POST',
      body: JSON.stringify(configData),
    })
  }

  async getConfigHistory() {
    return this.request('/api/admin/pvfrs/config/history')
  }

  async deleteConfigHistory(historyId: string) {
    return this.request(`/api/admin/pvfrs/config/history/${historyId}`, {
      method: 'DELETE',
    })
  }

  // 实时监控
  async getMonitoringData() {
    return this.request('/api/frontend/pvfrs/monitor')
  }

  async getMonitoringAlerts() {
    return this.request('/api/frontend/pvfrs/monitor/alerts')
  }

  async acknowledgeAlert(alertId: string) {
    return this.request(`/api/frontend/pvfrs/monitor/alerts/${alertId}/acknowledge`, {
      method: 'POST',
    })
  }

  async getPerformanceMetrics(params: any = {}) {
    const queryString = new URLSearchParams(params).toString()
    return this.request(`/api/frontend/pvfrs/monitor/performance?${queryString}`)
  }

  // 选股结果
  async getSelectionResults(params: any = {}) {
    const queryString = new URLSearchParams(params).toString()
    return this.request(`/api/frontend/pvfrs/selection-results?${queryString}`)
  }

  async getSelectionSummary() {
    return this.request('/api/frontend/pvfrs/selection-summary')
  }

  // 数据分析
  async getAnalysisData(analysisType: string, params: any = {}) {
    const queryString = new URLSearchParams(params).toString()
    return this.request(`/api/admin/pvfrs/analysis/${analysisType}?${queryString}`)
  }

  async exportAnalysisData(analysisType: string, params: any = {}) {
    const queryString = new URLSearchParams(params).toString()
    const response = await fetch(`${API_BASE}/api/admin/pvfrs/analysis/${analysisType}/export?${queryString}`, {
      headers: this.getAuthHeaders(),
    })

    if (!response.ok) {
      throw new Error('Export failed')
    }

    return response.blob()
  }

  // 策略优化
  async optimizeStrategy(optimizationData: any) {
    return this.request('/api/admin/pvfrs/optimize', {
      method: 'POST',
      body: JSON.stringify(optimizationData),
    })
  }

  async getOptimizationResults(optimizationId: string) {
    return this.request(`/api/admin/pvfrs/optimize/${optimizationId}`)
  }

  async getOptimizationHistory() {
    return this.request('/api/admin/pvfrs/optimize/history')
  }

  // 风险管理
  async getRiskMetrics() {
    return this.request('/api/admin/pvfrs/risk/metrics')
  }

  async updateRiskLimits(riskLimits: any) {
    return this.request('/api/admin/pvfrs/risk/limits', {
      method: 'POST',
      body: JSON.stringify(riskLimits),
    })
  }

  async getRiskAlerts() {
    return this.request('/api/admin/pvfrs/risk/alerts')
  }

  // 数据管理
  async getDataStatus() {
    return this.request('/api/admin/pvfrs/data/status')
  }

  async refreshData(dataType: string) {
    return this.request(`/api/admin/pvfrs/data/refresh/${dataType}`, {
      method: 'POST',
    })
  }

  async validateData(dataType: string) {
    return this.request(`/api/admin/pvfrs/data/validate/${dataType}`, {
      method: 'POST',
    })
  }

  // 用户管理
  async getUsers() {
    return this.request('/api/admin/pvfrs/users')
  }

  async updateUserPermissions(userId: string, permissions: any) {
    return this.request(`/api/admin/pvfrs/users/${userId}/permissions`, {
      method: 'POST',
      body: JSON.stringify(permissions),
    })
  }

  // 日志管理
  async getLogs(params: any = {}) {
    const queryString = new URLSearchParams(params).toString()
    return this.request(`/api/admin/pvfrs/logs?${queryString}`)
  }

  async exportLogs(params: any = {}) {
    const queryString = new URLSearchParams(params).toString()
    const response = await fetch(`${API_BASE}/api/admin/pvfrs/logs/export?${queryString}`, {
      headers: this.getAuthHeaders(),
    })

    if (!response.ok) {
      throw new Error('Export failed')
    }

    return response.blob()
  }

  // 系统维护
  async performMaintenance(maintenanceType: string) {
    return this.request(`/api/admin/pvfrs/maintenance/${maintenanceType}`, {
      method: 'POST',
    })
  }

  async getMaintenanceStatus() {
    return this.request('/api/admin/pvfrs/maintenance/status')
  }

  async scheduleMaintenanceTask(taskData: any) {
    return this.request('/api/admin/pvfrs/maintenance/schedule', {
      method: 'POST',
      body: JSON.stringify(taskData),
    })
  }

  // 下载任务结果（通过任务ID）
  async downloadTaskResults(taskId: string, reportId?: string) {
    // 如果提供了 reportId，直接使用；否则尝试通过任务ID获取报告
    let finalReportId = reportId

    if (!finalReportId) {
      try {
        // 尝试通过任务ID获取报告
        const response = await fetch(`${API_BASE}/api/admin/pvfrs/backtest/report/${taskId}`, {
          headers: this.getAuthHeaders(),
        })

        if (response.ok) {
          const reportData = await response.json()
          if (reportData && reportData.data && reportData.data.report_id) {
            finalReportId = reportData.data.report_id
          } else if (reportData && reportData.report_id) {
            finalReportId = reportData.report_id
          }
        }
      } catch (error) {
        console.error('获取报告ID失败:', error)
      }
    }

    if (!finalReportId) {
      throw new Error('任务没有关联的报告ID')
    }

    // 使用报告下载端点
    const response = await fetch(`${API_BASE}/api/admin/pvfrs/reports/${finalReportId}/download`, {
      headers: this.getAuthHeaders(),
    })

    if (!response.ok) {
      throw new Error('Download failed')
    }

    return response.blob()
  }
}

export const pvfrsApiService = new PVFRSApiService()