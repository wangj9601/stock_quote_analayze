<template>
  <div class="urt-management">
    <div class="page-header">
      <h2>URT 上升趋势策略</h2>
      <p class="subtitle">参数配置、多数据源回测、任务详情与统计分析报告</p>
    </div>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="策略参数" name="config">
        <UrtStrategyConfiguration />
      </el-tab-pane>
      <el-tab-pane label="回测管理" name="backtest">
        <UrtBacktestManagement />
      </el-tab-pane>
      <el-tab-pane label="报告与分析" name="reports">
        <UrtReportAnalysis ref="reportRef" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { provide, ref, watch } from 'vue'
import { urtApiService } from '@/services/urtApi'
import UrtStrategyConfiguration from '@/components/urt/StrategyConfiguration.vue'
import UrtBacktestManagement from '@/components/urt/BacktestManagement.vue'
import UrtReportAnalysis from '@/components/urt/ReportAnalysis.vue'

provide('urtApi', urtApiService)

const activeTab = ref('backtest')
const reportRef = ref<{ refresh?: () => void } | null>(null)

watch(activeTab, (tab) => {
  if (tab === 'reports') reportRef.value?.refresh?.()
})
</script>

<style scoped>
.urt-management {
  padding: 16px 20px;
}
.page-header h2 {
  margin: 0 0 4px;
  font-size: 20px;
}
.subtitle {
  margin: 0 0 16px;
  color: #6b7280;
  font-size: 13px;
}
</style>
