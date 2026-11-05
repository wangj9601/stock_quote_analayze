import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import dayjs from 'dayjs'
import { logsService } from '@/services/logs.service'
import type { AnyLogEntry, AppLogFileInfo, LogFilter, LogStats, LogTable } from '@/types/logs.types'

export type LogsTab = 'historical_collect' | 'realtime_collect' | 'operation' | 'app'

function defaultAppFilters(): LogFilter {
  return {
    type: 'app',
    level: 'WARNING,ERROR',
    startDate: dayjs().subtract(1, 'day').format('YYYY-MM-DD'),
    endDate: dayjs().format('YYYY-MM-DD'),
    collect_source: null,
    keyword: '',
    sourceFile: null,
  }
}

export const useLogsStore = defineStore('logs', () => {
  const historicalLogs = ref<AnyLogEntry[]>([])
  const realtimeLogs = ref<AnyLogEntry[]>([])
  const operationLogs = ref<AnyLogEntry[]>([])
  const appLogs = ref<AnyLogEntry[]>([])
  const appLogFiles = ref<AppLogFileInfo[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const filters = ref<LogFilter>({
    type: 'all',
    level: 'all',
    startDate: null,
    endDate: null,
    collect_source: null,
    keyword: '',
    sourceFile: null,
  })
  const pagination = ref({
    current: 1,
    pageSize: 20,
    total: 0
  })
  const stats = ref<LogStats | null>(null)
  const logTables = ref<LogTable[]>([])
  const currentTab = ref<LogsTab>('historical_collect')

  const filteredLogs = computed(() => {
    if (currentTab.value === 'historical_collect') {
      return historicalLogs.value
    }
    if (currentTab.value === 'realtime_collect') {
      return realtimeLogs.value
    }
    if (currentTab.value === 'app') {
      return appLogs.value
    }
    return operationLogs.value
  })

  const fetchLogs = async () => {
    loading.value = true
    error.value = null
    try {
      const response = await logsService.getLogs({
        ...filters.value,
        page: pagination.value.current,
        pageSize: pagination.value.pageSize
      })
      historicalLogs.value = response.data
      pagination.value.total = response.total
    } catch (err) {
      error.value = err instanceof Error ? err.message : '获取日志失败'
    } finally {
      loading.value = false
    }
  }

  const fetchRealtimeLogs = async () => {
    loading.value = true
    error.value = null
    try {
      const response = await logsService.getRealtimeLogs({
        ...filters.value,
        page: pagination.value.current,
        pageSize: pagination.value.pageSize
      })
      realtimeLogs.value = response.data
      pagination.value.total = response.total
    } catch (err) {
      error.value = err instanceof Error ? err.message : '获取实时行情采集日志失败'
    } finally {
      loading.value = false
    }
  }

  const fetchOperationLogs = async () => {
    loading.value = true
    error.value = null
    try {
      const response = await logsService.getOperationLogs({
        ...filters.value,
        page: pagination.value.current,
        pageSize: pagination.value.pageSize
      })
      operationLogs.value = response.data
      pagination.value.total = response.total
    } catch (err) {
      error.value = err instanceof Error ? err.message : '获取操作日志失败'
    } finally {
      loading.value = false
    }
  }

  const fetchAppLogs = async () => {
    loading.value = true
    error.value = null
    try {
      const response = await logsService.getAppLogs({
        ...filters.value,
        page: pagination.value.current,
        pageSize: pagination.value.pageSize
      })
      appLogs.value = response.data
      pagination.value.total = response.total
      if (response.files) {
        appLogFiles.value = response.files
      }
      if (response.stats) {
        stats.value = response.stats
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : '获取应用日志失败'
    } finally {
      loading.value = false
    }
  }

  const fetchStats = async () => {
    if (currentTab.value === 'app') {
      return
    }
    try {
      stats.value = await logsService.getLogStats()
    } catch (err) {
      error.value = err instanceof Error ? err.message : '获取统计失败'
    }
  }

  const fetchLogTables = async () => {
    try {
      logTables.value = await logsService.getLogTables()
    } catch (err) {
      error.value = err instanceof Error ? err.message : '获取日志表失败'
    }
  }

  const updateFilters = (newFilters: Partial<LogFilter>) => {
    filters.value = { ...filters.value, ...newFilters }
    pagination.value.current = 1
    loadLogs()
  }

  const updatePagination = (page: number, pageSize: number) => {
    pagination.value.current = page
    pagination.value.pageSize = pageSize
    loadLogs()
  }

  const switchTab = (tab: LogsTab) => {
    currentTab.value = tab
    pagination.value.current = 1
    if (tab === 'app') {
      filters.value = defaultAppFilters()
    } else {
      filters.value = {
        type: 'all',
        level: 'all',
        startDate: null,
        endDate: null,
        collect_source: null,
        keyword: '',
        sourceFile: null,
      }
    }
    loadLogs()
    fetchStats()
  }

  const loadLogs = () => {
    if (currentTab.value === 'historical_collect') {
      fetchLogs()
    } else if (currentTab.value === 'realtime_collect') {
      fetchRealtimeLogs()
    } else if (currentTab.value === 'app') {
      fetchAppLogs()
    } else {
      fetchOperationLogs()
    }
  }

  const refresh = () => {
    loadLogs()
    fetchStats()
  }

  const exportLogs = async () => {
    try {
      const blob = await logsService.exportLogs(filters.value)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `logs_${new Date().toISOString().split('T')[0]}.csv`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '导出失败'
    }
  }

  const clearError = () => {
    error.value = null
  }

  return {
    historicalLogs,
    realtimeLogs,
    operationLogs,
    appLogs,
    appLogFiles,
    loading,
    error,
    filters,
    pagination,
    stats,
    logTables,
    currentTab,
    filteredLogs,
    fetchLogs,
    fetchRealtimeLogs,
    fetchOperationLogs,
    fetchAppLogs,
    fetchStats,
    fetchLogTables,
    updateFilters,
    updatePagination,
    switchTab,
    loadLogs,
    refresh,
    exportLogs,
    clearError
  }
})
