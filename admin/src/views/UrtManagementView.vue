<template>
  <StrategyOpsShell
    ref="shellRef"
    v-model:tab="activeTab"
    code="URT"
    title="上升趋势策略"
    subtitle="参数配置、信号预计算、多数据源回测与报告分析"
    trace-name="urt_signal_trace"
    :api="urtApiService"
  >
    <el-tab-pane label="策略参数" name="config">
      <UrtStrategyConfiguration @need-precompute="onNeedPrecompute" />
    </el-tab-pane>
    <el-tab-pane label="回测管理" name="backtest">
      <UrtBacktestManagement />
    </el-tab-pane>
    <el-tab-pane label="报告与分析" name="reports">
      <UrtReportAnalysis ref="reportRef" />
    </el-tab-pane>
    <el-tab-pane label="操作记录" name="audit">
      <UrtAuditLogs ref="auditRef" />
    </el-tab-pane>
  </StrategyOpsShell>
</template>

<script setup lang="ts">
import { provide, ref, watch } from 'vue'
import { urtApiService } from '@/services/urtApi'
import StrategyOpsShell from '@/components/layout/StrategyOpsShell.vue'
import UrtStrategyConfiguration from '@/components/urt/StrategyConfiguration.vue'
import UrtBacktestManagement from '@/components/urt/BacktestManagement.vue'
import UrtReportAnalysis from '@/components/urt/ReportAnalysis.vue'
import UrtAuditLogs from '@/components/urt/UrtAuditLogs.vue'

provide('urtApi', urtApiService)

const shellRef = ref<{ openPrecompute: (configId?: number | null) => void } | null>(null)
const activeTab = ref('backtest')
const reportRef = ref<{ refresh?: () => void } | null>(null)
const auditRef = ref<{ refresh?: () => void } | null>(null)

function onNeedPrecompute(configId?: number | null) {
  shellRef.value?.openPrecompute(configId)
}

watch(activeTab, (tab) => {
  if (tab === 'reports') reportRef.value?.refresh?.()
  if (tab === 'audit') auditRef.value?.refresh?.()
})
</script>
