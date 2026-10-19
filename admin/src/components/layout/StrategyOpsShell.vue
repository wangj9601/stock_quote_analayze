<template>
  <div class="strategy-ops">
    <header class="ops-head">
      <div>
        <h2>
          <span class="ops-code">{{ code }}</span>
          {{ title }}
        </h2>
        <p v-if="subtitle" class="ops-sub">{{ subtitle }}</p>
      </div>
      <div class="ops-actions">
        <el-button type="warning" size="small" @click="openPrecompute()">信号预计算</el-button>
        <el-button size="small" :loading="refreshing" @click="refreshSystemStatus">刷新状态</el-button>
      </div>
    </header>

    <p class="ops-status" aria-live="polite">
      运行中 {{ systemStatus.runningBacktests }}
      <span>待执行 {{ systemStatus.pendingBacktests }}</span>
      <span>失败 {{ systemStatus.failedBacktests }}</span>
      <span>历史报告 {{ systemStatus.totalReports }}</span>
    </p>

    <el-alert
      v-if="lastJob"
      class="ops-job"
      :title="lastJob.text"
      :type="lastJob.ok ? 'success' : 'error'"
      show-icon
      closable
      @close="lastJob = null"
    />

    <el-tabs v-model="activeTab">
      <slot />
    </el-tabs>

    <el-dialog v-model="precomputeVisible" :title="`${code} 信号预计算`" width="480px" @open="loadConfigs">
      <el-form label-width="100px">
        <el-form-item label="交易日" required>
          <el-date-picker
            v-model="form.date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择交易日"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="市场">
          <el-radio-group v-model="form.market">
            <el-radio-button label="CN">A股</el-radio-button>
            <el-radio-button label="HK">港股</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="参数版本">
          <el-select
            v-model="form.config_id"
            clearable
            filterable
            placeholder="空=全部预计算启用版本"
            style="width: 100%"
          >
            <el-option
              v-for="c in configs"
              :key="c.id"
              :label="`${c.name}${c.is_default ? ' (默认)' : ''}`"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="候选上限">
          <el-input-number
            v-model="form.limit"
            :min="1"
            :max="10000"
            controls-position="right"
            placeholder="可选，调试用"
            style="width: 100%"
          />
        </el-form-item>
        <p class="ops-hint">
          将扫描全市场硬筛命中并写入 {{ traceName }}；任务在后台执行。
          日终预计算只覆盖命中行，收紧参数后旧买点可能残留。不会自动删除旧记录，也不会改写历史回测任务。
          未选版本时会跑全部启用版本，提交前需要输入策略短码。
        </p>
      </el-form>
      <template #footer>
        <el-button @click="precomputeVisible = false">取消</el-button>
        <el-button type="danger" :loading="precomputing" @click="submitPrecompute">启动预计算</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

type ConfigRow = { id: number; name: string; is_default?: boolean }
type OpsApi = {
  listStrategyConfigs: (activeOnly?: boolean) => Promise<ConfigRow[]>
  runPrecompute: (body: {
    date: string
    market: 'CN' | 'HK'
    config_id?: number
    limit?: number
  }) => Promise<{ message?: string }>
  getSystemStatus: () => Promise<Record<string, number | string>>
}

const props = defineProps<{
  code: string
  title: string
  subtitle?: string
  traceName: string
  api: OpsApi
}>()

const activeTab = defineModel<string>('tab', { default: 'backtest' })

const systemStatus = ref({
  runningBacktests: 0,
  pendingBacktests: 0,
  failedBacktests: 0,
  totalReports: 0,
})
const refreshing = ref(false)
const precomputeVisible = ref(false)
const precomputing = ref(false)
const configs = ref<ConfigRow[]>([])
const form = reactive({
  date: new Date().toISOString().slice(0, 10),
  market: 'CN' as 'CN' | 'HK',
  config_id: undefined as number | undefined,
  limit: undefined as number | undefined,
})
const lastJob = ref<{ ok: boolean; text: string } | null>(null)

function openPrecompute(configId?: number | null) {
  if (configId != null) form.config_id = Number(configId)
  if (!form.date) form.date = new Date().toISOString().slice(0, 10)
  precomputeVisible.value = true
}

async function loadConfigs() {
  try {
    configs.value = await props.api.listStrategyConfigs(true)
  } catch {
    configs.value = []
  }
}

async function submitPrecompute() {
  if (!form.date) {
    ElMessage.warning('请选择交易日')
    return
  }
  const version = form.config_id
    ? configs.value.find((c) => c.id === form.config_id)?.name || String(form.config_id)
    : '全部启用版本'
  const market = form.market === 'HK' ? '港股' : 'A股'
  const summary = `${props.code} / ${version} / ${market} / ${form.date}，写入 ${props.traceName}。旧买点不会自动删除。`
  try {
    if (!form.config_id) {
      await ElMessageBox.prompt(
        `${summary} 这是全市场范围。输入 ${props.code} 以继续。`,
        '全市场预计算',
        {
          confirmButtonText: '启动预计算',
          cancelButtonText: '取消',
          inputPattern: new RegExp(`^${props.code}$`),
          inputErrorMessage: `请输入 ${props.code}`,
          confirmButtonClass: 'el-button--danger',
        }
      )
    } else {
      await ElMessageBox.confirm(summary, '启动预计算', {
        type: 'warning',
        confirmButtonText: '启动预计算',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger',
      })
    }
  } catch {
    return
  }

  precomputing.value = true
  try {
    const res = await props.api.runPrecompute({
      date: form.date,
      market: form.market,
      config_id: form.config_id,
      limit: form.limit,
    })
    const msg = res?.message || `预计算已提交（${market} / ${form.date} / ${version}）`
    lastJob.value = {
      ok: true,
      text: `${msg}。状态数字不会自动变化，需要时点「刷新状态」。`,
    }
    precomputeVisible.value = false
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : '启动预计算失败'
    lastJob.value = { ok: false, text: `${message}。可核对交易日和参数版本后重试。` }
  } finally {
    precomputing.value = false
  }
}

async function refreshSystemStatus() {
  refreshing.value = true
  try {
    const data = await props.api.getSystemStatus()
    systemStatus.value = { ...systemStatus.value, ...data }
    lastJob.value = { ok: true, text: '系统状态已刷新。' }
  } catch {
    lastJob.value = { ok: false, text: '获取系统状态失败。请稍后点「刷新状态」再试。' }
  } finally {
    refreshing.value = false
  }
}

defineExpose({ openPrecompute })
refreshSystemStatus()
</script>

<style scoped>
.strategy-ops {
  padding: 4px 0 16px;
}
.ops-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.ops-head h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 650;
  color: #1a2332;
}
.ops-code {
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #234e70;
  margin-right: 8px;
}
.ops-sub {
  margin: 4px 0 0;
  color: #4b5563;
  font-size: 13px;
}
.ops-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.ops-status {
  margin: 12px 0;
  padding: 8px 12px;
  background: #fff;
  border: 1px solid #c9c3b8;
  border-radius: 2px;
  color: #1a2332;
  font-size: 13px;
}
.ops-status span {
  margin-left: 16px;
}
.ops-job {
  margin-bottom: 12px;
}
.ops-hint {
  margin: 0 0 0 100px;
  font-size: 12px;
  color: #4b5563;
  line-height: 1.5;
}
@media (max-width: 768px) {
  .ops-head {
    flex-direction: column;
  }
  .ops-hint {
    margin-left: 0;
  }
  .ops-status span {
    display: inline-block;
    margin: 4px 16px 0 0;
  }
}
</style>
