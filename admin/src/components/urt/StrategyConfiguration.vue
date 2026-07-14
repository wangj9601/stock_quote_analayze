<template>
  <div class="urt-strategy-configuration">
    <el-row :gutter="16">
      <el-col :span="7">
        <el-card header="URT 参数版本">
          <div class="mb-3 flex flex-wrap gap-2">
            <el-button size="small" @click="loadVersions">刷新</el-button>
            <el-button size="small" type="primary" @click="createVersion">新建</el-button>
          </div>
          <el-table
            :data="versions"
            v-loading="listLoading"
            highlight-current-row
            size="small"
            @current-change="onSelectVersion"
          >
            <el-table-column prop="name" label="名称" min-width="100">
              <template #default="{ row }">
                <span>{{ row.name }}</span>
                <el-tag v-if="row.is_default" size="small" type="success" class="ml-1">默认</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="version_label" label="版本" width="70" />
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="17">
        <el-card v-if="selectedId">
          <template #header>
            <div class="flex items-center justify-between">
              <span>编辑：{{ selected?.name }}</span>
              <div class="flex gap-2">
                <el-switch v-model="editMeta.is_default" active-text="默认" />
                <el-switch v-model="editMeta.is_active" active-text="启用" />
                <el-switch v-model="editMeta.precompute_enabled" active-text="预计算" />
                <el-button type="primary" :loading="saving" @click="saveVersion">保存</el-button>
                <el-button @click="showJson = !showJson">{{ showJson ? '表单' : 'JSON' }}</el-button>
                <el-button :loading="previewing" @click="runPreview">试跑选股</el-button>
              </div>
            </div>
          </template>

          <el-form v-if="!showJson" label-width="140px" class="param-form">
            <el-form-item label="版本标签">
              <el-input v-model="editMeta.version_label" placeholder="如 v1" />
            </el-form-item>
            <el-form-item label="说明">
              <el-input v-model="editMeta.description" type="textarea" :rows="2" />
            </el-form-item>

            <el-divider content-position="left">硬筛条件</el-divider>
            <el-row :gutter="12">
              <el-col :span="8">
                <el-form-item label="MA 周期">
                  <el-input-number v-model="form.ma_period" :min="5" :max="60" class="w-full" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="量能均量窗口">
                  <el-input-number v-model="form.volume_lookback" :min="5" :max="60" class="w-full" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="量能倍数">
                  <el-input-number v-model="form.volume_multiple" :min="1" :max="30" :step="0.1" :precision="2" class="w-full" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="12">
              <el-col :span="8">
                <el-form-item label="最低得分">
                  <el-input-number v-model="form.min_score" :min="0" :max="100" class="w-full" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="4日最少阳线">
                  <el-input-number v-model="form.yang_rule_a.min_up_days" :min="1" :max="4" class="w-full" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="5日最少阳线">
                  <el-input-number v-model="form.yang_rule_b.min_up_days" :min="1" :max="5" class="w-full" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-divider content-position="left">精细化（可选）</el-divider>
            <el-row :gutter="12">
              <el-col :span="8">
                <el-form-item label="启用换手率">
                  <el-switch v-model="form.use_turnover" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="最低换手%">
                  <el-input-number v-model="form.min_turnover" :min="0" :step="0.1" :precision="2" class="w-full" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="启用量比">
                  <el-switch v-model="form.use_volume_ratio" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="最低量比">
              <el-input-number v-model="form.min_volume_ratio" :min="0" :step="0.1" :precision="2" />
            </el-form-item>

            <el-divider content-position="left">交易纪律（回测用）</el-divider>
            <el-row :gutter="12">
              <el-col :span="8">
                <el-form-item label="止损%上限">
                  <el-input-number v-model="form.risk.stop_loss_pct_max" :min="1" :max="30" class="w-full" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="连跌离场天数">
                  <el-input-number v-model="form.risk.time_stop_down_days" :min="1" :max="10" class="w-full" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="回撤止盈%">
                  <el-input-number v-model="form.risk.trailing_drawdown_pct" :min="1" :max="20" class="w-full" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>

          <el-input
            v-else
            v-model="jsonText"
            type="textarea"
            :rows="22"
            class="json-editor"
          />

          <el-alert
            v-if="previewHint"
            :title="previewHint"
            type="info"
            show-icon
            class="mt-3"
            :closable="true"
            @close="previewHint = ''"
          />
        </el-card>
        <el-empty v-else description="请选择左侧参数版本" />
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { urtApiService, type URTStrategyConfig } from '@/services/urtApi'

const versions = ref<URTStrategyConfig[]>([])
const listLoading = ref(false)
const selectedId = ref<number | null>(null)
const selected = ref<URTStrategyConfig | null>(null)
const saving = ref(false)
const previewing = ref(false)
const showJson = ref(false)
const jsonText = ref('')
const previewHint = ref('')

const editMeta = reactive({
  version_label: '',
  description: '',
  is_default: false,
  is_active: true,
  precompute_enabled: false,
})

const form = reactive<any>({
  ma_period: 20,
  volume_lookback: 20,
  volume_multiple: 2.5,
  min_score: 70,
  yang_rule_a: { window: 4, min_up_days: 3 },
  yang_rule_b: { window: 5, min_up_days: 4 },
  use_turnover: false,
  use_volume_ratio: false,
  min_turnover: 0,
  min_volume_ratio: 0,
  history_calendar_days: 120,
  risk: {
    stop_loss_pct_min: 5,
    stop_loss_pct_max: 10,
    time_stop_down_days: 3,
    take_profit_alert_pct_min: 25,
    take_profit_alert_pct_max: 30,
    trailing_drawdown_pct: 5,
  },
})

function applyParams(params: Record<string, any> = {}) {
  form.ma_period = params.ma_period ?? 20
  form.volume_lookback = params.volume_lookback ?? 20
  form.volume_multiple = params.volume_multiple ?? 2.5
  form.min_score = params.min_score ?? 70
  form.yang_rule_a = { window: 4, min_up_days: 3, ...(params.yang_rule_a || {}) }
  form.yang_rule_b = { window: 5, min_up_days: 4, ...(params.yang_rule_b || {}) }
  form.use_turnover = !!params.use_turnover
  form.use_volume_ratio = !!params.use_volume_ratio
  form.min_turnover = params.min_turnover ?? 0
  form.min_volume_ratio = params.min_volume_ratio ?? 0
  form.history_calendar_days = params.history_calendar_days ?? 120
  form.risk = {
    stop_loss_pct_min: 5,
    stop_loss_pct_max: 10,
    time_stop_down_days: 3,
    take_profit_alert_pct_min: 25,
    take_profit_alert_pct_max: 30,
    trailing_drawdown_pct: 5,
    ...(params.risk || {}),
  }
  jsonText.value = JSON.stringify(params, null, 2)
}

async function loadVersions() {
  listLoading.value = true
  try {
    versions.value = await urtApiService.listStrategyConfigs()
    if (!selectedId.value && versions.value.length) {
      await onSelectVersion(versions.value[0])
    }
  } catch (e: any) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    listLoading.value = false
  }
}

async function onSelectVersion(row: URTStrategyConfig | null) {
  if (!row) return
  selectedId.value = row.id
  selected.value = row
  try {
    const data = await urtApiService.getStrategyConfig(row.id)
    selected.value = data
    editMeta.version_label = data.version_label || ''
    editMeta.description = data.description || ''
    editMeta.is_default = !!data.is_default
    editMeta.is_active = data.is_active !== false
    editMeta.precompute_enabled = !!data.precompute_enabled
    applyParams(data.config_params || {})
  } catch (e: any) {
    ElMessage.error(e.message || '加载版本失败')
  }
}

async function saveVersion() {
  if (!selectedId.value) return
  saving.value = true
  try {
    let params = { ...form }
    if (showJson.value) {
      params = JSON.parse(jsonText.value)
    }
    await urtApiService.updateStrategyConfig(selectedId.value, {
      version_label: editMeta.version_label,
      description: editMeta.description,
      is_default: editMeta.is_default,
      is_active: editMeta.is_active,
      precompute_enabled: editMeta.precompute_enabled,
      config_params: params,
    })
    ElMessage.success('已保存')
    await loadVersions()
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function createVersion() {
  try {
    const { value } = await ElMessageBox.prompt('请输入版本名称', '新建 URT 参数版本', {
      inputValue: `urt_${Date.now()}`,
      confirmButtonText: '创建',
      cancelButtonText: '取消',
    })
    const defaults = await urtApiService.getDefaultParams()
    const created = await urtApiService.createStrategyConfig({
      name: value,
      version_label: 'v1',
      config_params: defaults,
      is_active: true,
      is_default: false,
    })
    ElMessage.success('已创建')
    await loadVersions()
    await onSelectVersion(created)
  } catch (e: any) {
    if (e === 'cancel' || e?.toString?.().includes('cancel')) return
    ElMessage.error(e.message || '创建失败')
  }
}

async function runPreview() {
  if (!selectedId.value) return
  previewing.value = true
  try {
    const res = await urtApiService.screenPreview({ limit: 50, config_id: selectedId.value })
    previewHint.value = `试跑完成：命中 ${res.total ?? (res.data || []).length} 只，基准日 ${res.search_date || '-'}`
  } catch (e: any) {
    ElMessage.error(e.message || '试跑失败')
  } finally {
    previewing.value = false
  }
}

onMounted(loadVersions)
</script>

<style scoped>
.urt-strategy-configuration {
  padding: 4px;
}
.mb-3 {
  margin-bottom: 12px;
}
.ml-1 {
  margin-left: 4px;
}
.mt-3 {
  margin-top: 12px;
}
.flex {
  display: flex;
}
.items-center {
  align-items: center;
}
.justify-between {
  justify-content: space-between;
}
.gap-2 {
  gap: 8px;
}
.w-full {
  width: 100%;
}
.json-editor {
  font-family: ui-monospace, monospace;
}
</style>
