<template>
  <div class="urt-management">
    <div class="page-header">
      <div class="header-row">
        <div>
          <h2>URT 上升趋势策略</h2>
          <p class="subtitle">参数配置、信号预计算、多数据源回测与报告分析</p>
        </div>
        <div class="header-actions">
          <el-button type="warning" size="small" @click="openPrecompute">
            信号预计算
          </el-button>
          <el-button type="success" size="small" @click="refreshSystemStatus">
            <el-icon><Refresh /></el-icon>
            刷新状态
          </el-button>
        </div>
      </div>
    </div>

    <div class="status-cards">
      <el-row :gutter="16">
        <el-col :span="6">
          <el-card shadow="never" class="status-card">
            <div class="status-value">{{ systemStatus.runningBacktests }}</div>
            <div class="status-label">运行中回测</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="status-card">
            <div class="status-value">{{ systemStatus.pendingBacktests }}</div>
            <div class="status-label">待执行</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="status-card">
            <div class="status-value">{{ systemStatus.failedBacktests }}</div>
            <div class="status-label">失败任务</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="status-card">
            <div class="status-value">{{ systemStatus.totalReports }}</div>
            <div class="status-label">历史报告</div>
          </el-card>
        </el-col>
      </el-row>
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
      <el-tab-pane label="操作记录" name="audit">
        <UrtAuditLogs ref="auditRef" />
      </el-tab-pane>
    </el-tabs>

    <el-dialog
      v-model="precomputeVisible"
      title="URT 信号预计算"
      width="480px"
      @open="loadPrecomputeConfigs"
    >
      <el-form label-width="100px">
        <el-form-item label="交易日" required>
          <el-date-picker
            v-model="precomputeForm.date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择交易日"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="市场">
          <el-radio-group v-model="precomputeForm.market">
            <el-radio-button label="CN">A股</el-radio-button>
            <el-radio-button label="HK">港股</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="参数版本">
          <el-select
            v-model="precomputeForm.config_id"
            clearable
            filterable
            placeholder="空=全部预计算启用版本"
            style="width: 100%"
          >
            <el-option
              v-for="c in precomputeConfigs"
              :key="c.id"
              :label="`${c.name}${c.is_default ? ' (默认)' : ''}`"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="候选上限">
          <el-input-number
            v-model="precomputeForm.limit"
            :min="1"
            :max="10000"
            controls-position="right"
            placeholder="可选，调试用"
            style="width: 100%"
          />
        </el-form-item>
        <p class="precompute-hint">
          将扫描全市场硬筛命中并写入 urt_signal_trace；任务在后台执行，完成后选股/推送可读缓存。
        </p>
      </el-form>
      <template #footer>
        <el-button @click="precomputeVisible = false">取消</el-button>
        <el-button type="primary" :loading="precomputing" @click="submitPrecompute">启动预计算</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { provide, reactive, ref, watch } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { urtApiService, type URTStrategyConfig } from '@/services/urtApi'
import UrtStrategyConfiguration from '@/components/urt/StrategyConfiguration.vue'
import UrtBacktestManagement from '@/components/urt/BacktestManagement.vue'
import UrtReportAnalysis from '@/components/urt/ReportAnalysis.vue'
import UrtAuditLogs from '@/components/urt/UrtAuditLogs.vue'

provide('urtApi', urtApiService)

const activeTab = ref('backtest')
const reportRef = ref<{ refresh?: () => void } | null>(null)
const auditRef = ref<{ refresh?: () => void } | null>(null)

const systemStatus = ref({
  runningBacktests: 0,
  pendingBacktests: 0,
  failedBacktests: 0,
  totalReports: 0,
  systemHealth: 'ok',
})

const precomputeVisible = ref(false)
const precomputing = ref(false)
const precomputeConfigs = ref<URTStrategyConfig[]>([])
const precomputeForm = reactive({
  date: new Date().toISOString().slice(0, 10),
  market: 'CN' as 'CN' | 'HK',
  config_id: undefined as number | undefined,
  limit: undefined as number | undefined,
})

function openPrecompute() {
  if (!precomputeForm.date) {
    precomputeForm.date = new Date().toISOString().slice(0, 10)
  }
  precomputeVisible.value = true
}

async function loadPrecomputeConfigs() {
  try {
    precomputeConfigs.value = await urtApiService.listStrategyConfigs(true)
  } catch {
    precomputeConfigs.value = []
  }
}

async function submitPrecompute() {
  if (!precomputeForm.date) {
    ElMessage.warning('请选择交易日')
    return
  }
  precomputing.value = true
  try {
    const res = await urtApiService.runPrecompute({
      date: precomputeForm.date,
      market: precomputeForm.market,
      config_id: precomputeForm.config_id,
      limit: precomputeForm.limit,
    })
    const msg =
      (res as { message?: string })?.message ||
      `预计算已启动（${precomputeForm.market} / ${precomputeForm.date}）`
    ElMessage.success(msg)
    precomputeVisible.value = false
  } catch (e: any) {
    ElMessage.error(e?.message || '启动预计算失败')
  } finally {
    precomputing.value = false
  }
}

async function refreshSystemStatus() {
  try {
    const data = await urtApiService.getSystemStatus()
    systemStatus.value = { ...systemStatus.value, ...data }
    ElMessage.success('系统状态已刷新')
  } catch {
    ElMessage.error('获取系统状态失败')
  }
}

watch(activeTab, (tab) => {
  if (tab === 'reports') reportRef.value?.refresh?.()
  if (tab === 'audit') auditRef.value?.refresh?.()
})

refreshSystemStatus()
</script>

<style scoped>
.urt-management {
  padding: 16px 20px;
}
.header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.header-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.page-header h2 {
  margin: 0 0 4px;
  font-size: 20px;
}
.subtitle {
  margin: 0;
  color: #6b7280;
  font-size: 13px;
}
.status-cards {
  margin-bottom: 16px;
}
.status-card {
  text-align: center;
}
.status-value {
  font-size: 22px;
  font-weight: 600;
  color: #1f2937;
}
.status-label {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}
.precompute-hint {
  margin: 0 0 0 100px;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.5;
}
</style>
