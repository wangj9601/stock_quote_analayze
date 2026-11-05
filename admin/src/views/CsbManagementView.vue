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
    <el-tab-pane label="信号结果" name="signals" lazy>
      <StrategySignalResultsPanel
        strategy-code="CSB"
        :list-signals="listCsbSignals"
        :list-configs="listCsbConfigs"
        :columns="csbSignalColumns"
      />
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
import StrategySignalResultsPanel, {
  type SignalColumn,
} from '@/components/strategy/StrategySignalResultsPanel.vue'
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

const listCsbSignals = (query: Parameters<typeof csbApiService.listSignals>[0]) =>
  csbApiService.listSignals(query)
const listCsbConfigs = () => csbApiService.listStrategyConfigs()

const csbSignalColumns: SignalColumn[] = [
  { prop: 'code', label: '代码', width: 96 },
  { prop: 'name', label: '名称', minWidth: 120, showOverflowTooltip: true },
  { prop: 'signal_type', label: '信号类型', width: 110 },
  { prop: 'score', label: '分数', width: 88, align: 'right' },
  { prop: 'close', label: '收盘', width: 88, align: 'right' },
  { prop: 'channel_lower', label: '通道下轨', width: 100, align: 'right' },
  { prop: 'channel_upper', label: '通道上轨', width: 100, align: 'right' },
  { prop: 'squeeze_days', label: '挤压天数', width: 96, align: 'right' },
  { prop: 'entry_low', label: '入场低点', width: 100, align: 'right' },
  { prop: 'updated_at', label: '写入时间', minWidth: 168 },
]

watch(activeTab, (tab) => {
  if (tab === 'reports') reportRef.value?.refresh?.()
  if (tab === 'audit') auditRef.value?.refresh?.()
})
</script>
