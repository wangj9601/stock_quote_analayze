<template>
  <div class="logs-view">
    <LogsStats :stats="stats" :mode="currentTab === 'app' ? 'app' : 'db'" />

    <el-tabs v-model="currentTab" @tab-change="onTabChange">
      <el-tab-pane label="历史采集日志" name="historical_collect">
        <LogsFilter
          :filters="filters"
          @update-filters="updateFilters"
        />
        <LogsTable
          :logs="filteredLogs"
          :loading="loading"
          :log-type="currentTab"
          @refresh="loadLogs"
        />
        <LogsPagination
          v-model:current="pagination.current"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          @change="handlePageChange"
        />
      </el-tab-pane>

      <el-tab-pane label="实时行情采集日志" name="realtime_collect">
        <LogsFilter
          :filters="filters"
          @update-filters="updateFilters"
        />
        <LogsTable
          :logs="filteredLogs"
          :loading="loading"
          :log-type="currentTab"
          @refresh="loadLogs"
        />
        <LogsPagination
          v-model:current="pagination.current"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          @change="handlePageChange"
        />
      </el-tab-pane>

      <el-tab-pane label="操作日志" name="operation">
        <LogsFilter
          :filters="filters"
          @update-filters="updateFilters"
        />
        <LogsTable
          :logs="filteredLogs"
          :loading="loading"
          :log-type="currentTab"
          @refresh="loadLogs"
        />
        <LogsPagination
          v-model:current="pagination.current"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          @change="handlePageChange"
        />
      </el-tab-pane>

      <el-tab-pane label="应用日志" name="app">
        <LogsFilter
          mode="app"
          :filters="filters"
          :source-files="appLogFiles"
          @update-filters="updateFilters"
        />
        <LogsTable
          :logs="filteredLogs"
          :loading="loading"
          log-type="app"
          @refresh="loadLogs"
        />
        <LogsPagination
          v-model:current="pagination.current"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          @change="handlePageChange"
        />
      </el-tab-pane>
    </el-tabs>

    <el-alert
      v-if="error"
      :title="error"
      type="error"
      show-icon
      closable
      @close="clearError"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'

import { useLogsStore, type LogsTab } from '@/stores/logs'
import LogsStats from '@/components/logs/LogsStats.vue'
import LogsFilter from '@/components/logs/LogsFilter.vue'
import LogsTable from '@/components/logs/LogsTable.vue'
import LogsPagination from '@/components/logs/LogsPagination.vue'

const logsStore = useLogsStore()

const {
  loading,
  error,
  filters,
  pagination,
  stats,
  filteredLogs,
  currentTab,
  appLogFiles,
} = storeToRefs(logsStore)

const {
  fetchStats,
  updateFilters,
  updatePagination,
  switchTab,
  loadLogs,
  clearError,
} = logsStore

const onTabChange = (name: string | number) => {
  switchTab(String(name) as LogsTab)
}

const handlePageChange = (page: number, pageSize: number) => {
  updatePagination(page, pageSize)
}

onMounted(() => {
  loadLogs()
  fetchStats()
})
</script>

<style scoped>
.logs-view {
  margin-top: 24px;
}
</style>
