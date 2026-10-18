<template>
  <StrategyOpsShell
    ref="shellRef"
    v-model:tab="activeTab"
    code="CSB"
    title="低位通道突破"
    subtitle="参数配置、信号预计算、多数据源回测与报告分析"
    trace-name="csb_signal_trace"
    :api="csbApiService"
  >
    <el-tab-pane label="策略参数" name="config">
      <CsbStrategyConfiguration @need-precompute="onNeedPrecompute" />
    </el-tab-pane>
    <el-tab-pane label="回测管理" name="backtest">
      <CsbBacktestManagement />
    </el-tab-pane>
    <el-tab-pane label="报告与分析" name="reports">
      <CsbReportAnalysis ref="reportRef" />
    </el-tab-pane>
    <el-tab-pane label="操作记录" name="audit">
      <CsbAuditLogs ref="auditRef" />
    </el-tab-pane>
  </StrategyOpsShell>
</template>

<script setup lang="ts">
import { provide, ref, watch } from 'vue'
import { csbApiService } from '@/services/csbApi'
import StrategyOpsShell from '@/components/layout/StrategyOpsShell.vue'
import CsbStrategyConfiguration from '@/components/csb/StrategyConfiguration.vue'
import CsbBacktestManagement from '@/components/csb/BacktestManagement.vue'
import CsbReportAnalysis from '@/components/csb/ReportAnalysis.vue'
import CsbAuditLogs from '@/components/csb/CsbAuditLogs.vue'

provide('csbApi', csbApiService)

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
