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
    <el-tab-pane label="信号结果" name="signals" lazy>
      <StrategySignalResultsPanel
        strategy-code="URT"
        :list-signals="listUrtSignals"
        :list-configs="listUrtConfigs"
        show-market-switcher
        :columns="urtSignalColumns"
      />
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
import StrategySignalResultsPanel, {
  type SignalColumn,
} from '@/components/strategy/StrategySignalResultsPanel.vue'
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

const listUrtSignals = (query: Parameters<typeof urtApiService.listSignals>[0]) =>
  urtApiService.listSignals(query)
const listUrtConfigs = () => urtApiService.listStrategyConfigs()

const urtSignalColumns: SignalColumn[] = [
  { prop: 'code', label: '代码', width: 96 },
  { prop: 'name', label: '名称', minWidth: 120, showOverflowTooltip: true },
  { prop: 'score', label: '分数', width: 88, align: 'right' },
  { prop: 'signal_strength', label: '信号强度', width: 100, align: 'right' },
  { prop: 'close', label: '收盘', width: 88, align: 'right' },
  { prop: 'ma20', label: 'MA20', width: 88, align: 'right' },
  { prop: 'volume_multiple', label: '放量倍数', width: 100, align: 'right' },
  { prop: 'yang_rule', label: '阳线规则', width: 110, showOverflowTooltip: true },
  { prop: 'created_at', label: '写入时间', minWidth: 168 },
]

watch(activeTab, (tab) => {
  if (tab === 'reports') reportRef.value?.refresh?.()
  if (tab === 'audit') auditRef.value?.refresh?.()
})
</script>
