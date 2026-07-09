<template>
  <div class="strategy-configuration">
    <el-row :gutter="16">
      <el-col :span="7">
        <el-card header="共享参数版本">
          <p class="text-xs text-gray-500 mb-3">
            仅维护 <strong>default</strong>（标准版）与 <strong>gms_penalty</strong>（减分版）；修改原地保存，不新建版本。
          </p>
          <div class="mb-3 flex flex-wrap gap-2">
            <el-button size="small" @click="loadVersions">刷新</el-button>
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
                <el-tag v-if="row.precompute_enabled" size="small" type="info" class="ml-1">预计算</el-tag>
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
                <el-switch v-model="editMeta.precompute_enabled" active-text="预计算" />
                <el-button type="primary" :loading="saving" @click="saveVersion">保存</el-button>
                <el-button @click="showJson = !showJson">{{ showJson ? '表单' : 'JSON' }}</el-button>
              </div>
            </div>
          </template>

          <el-form v-if="!showJson" label-width="160px" class="param-form">
            <el-divider content-position="left">左侧买点</el-divider>
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="|Δ/d₂₀| 上限">
                  <el-input-number v-model="form.left_buy.ratio_d20_abs_max" :step="0.001" :precision="4" class="w-full" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="地量 m₂₀/m 上限">
                  <el-input-number v-model="form.left_buy.volume_ratio_max" :step="0.05" :precision="2" class="w-full" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-divider content-position="left">右侧买点</el-divider>
            <el-form-item label="放量 m₂₀/m 下限">
              <el-input-number v-model="form.right_buy.volume_ratio_min" :step="0.1" :precision="2" class="w-full" />
            </el-form-item>

            <el-divider content-position="left">评分阈值</el-divider>
            <el-row :gutter="12">
              <el-col :span="8">
                <el-form-item label="F/Z 下限">
                  <el-input-number v-model="form.scoring.accumulation_fz_min" :step="0.1" class="w-full" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="平衡 |Δ/d| 上限">
                  <el-input-number v-model="form.scoring.balance_ratio_max" :step="0.001" :precision="4" class="w-full" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="左侧蓄势分下限">
                  <el-input-number v-model="form.left_buy.min_accumulation_score" :min="0" :max="100" class="w-full" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="12">
              <el-col :span="8">
                <el-form-item label="关注分">
                  <el-input-number v-model="form.scoring.watch_threshold" :step="1" class="w-full" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="预警分">
                  <el-input-number v-model="form.scoring.alert_threshold" :step="1" class="w-full" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="观察周期(天)">
                  <el-input-number v-model="form.observation_period" :min="10" :max="60" class="w-full" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="12">
              <el-col :span="6">
                <el-form-item label="收敛 S 级">
                  <el-input-number v-model="form.scoring.accumulation_s_threshold" class="w-full" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="收敛 A 级">
                  <el-input-number v-model="form.scoring.accumulation_a_threshold" class="w-full" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="动量全速">
                  <el-input-number v-model="form.scoring.momentum_full_threshold" class="w-full" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="动量分批">
                  <el-input-number v-model="form.scoring.momentum_batch_threshold" class="w-full" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="推力支撑站稳天数">
              <el-input-number v-model="form.scoring.instant_deviation_stable_days" :min="1" :max="30" class="w-full" />
            </el-form-item>

            <el-divider content-position="left">评分权重</el-divider>
            <el-row :gutter="12">
              <el-col :span="8"><el-form-item label="F/Z 权重"><el-input-number v-model="form.scoring.weight_acc_fz" class="w-full" /></el-form-item></el-col>
              <el-col :span="8"><el-form-item label="|Δ/d| 权重"><el-input-number v-model="form.scoring.weight_acc_balance" class="w-full" /></el-form-item></el-col>
              <el-col :span="8"><el-form-item label="缩量权重"><el-input-number v-model="form.scoring.weight_acc_volume" class="w-full" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="12">
              <el-col :span="8"><el-form-item label="Δ/d₁ 权重"><el-input-number v-model="form.scoring.weight_mom_ratio_d1" class="w-full" /></el-form-item></el-col>
              <el-col :span="8"><el-form-item label="推力支撑权重"><el-input-number v-model="form.scoring.weight_mom_deviation" class="w-full" /></el-form-item></el-col>
              <el-col :span="8"><el-form-item label="攻击强度权重"><el-input-number v-model="form.scoring.weight_mom_volume" class="w-full" /></el-form-item></el-col>
            </el-row>

            <el-divider content-position="left">退出</el-divider>
            <el-form-item label="乖离过大阈值">
              <el-input-number v-model="form.exit.overbought_ratio" :step="0.01" :precision="3" class="w-full" />
            </el-form-item>

            <template v-if="showPenaltyEditor">
              <el-divider content-position="left">减分规则（减分版）</el-divider>
              <el-table :data="penaltyRules" border size="small" class="mb-2">
                <el-table-column prop="label" label="规则" min-width="140">
                  <template #default="{ row }">
                    <div>{{ row.label }}</div>
                    <div class="text-xs text-gray-500">{{ row.description }}</div>
                  </template>
                </el-table-column>
                <el-table-column label="启用" width="72">
                  <template #default="{ row }">
                    <el-switch v-model="row.enabled" />
                  </template>
                </el-table-column>
                <el-table-column label="扣分" width="120">
                  <template #default="{ row }">
                    <el-input-number v-model="row.points" :min="0" :max="50" size="small" />
                  </template>
                </el-table-column>
                <el-table-column label="参数" min-width="200">
                  <template #default="{ row }">
                    <div v-if="row.id === 'observation_range_amplitude'" class="flex items-center gap-2 flex-wrap">
                      <span class="text-xs text-gray-500 whitespace-nowrap">振幅阈值</span>
                      <el-input-number
                        v-model="row.amplitude_threshold_pct"
                        :min="0.01"
                        :max="2"
                        :step="0.01"
                        :precision="2"
                        size="small"
                        controls-position="right"
                        style="width: 132px"
                      />
                      <span class="text-xs text-gray-400">（0.30=30%）</span>
                    </div>
                    <span v-else class="text-xs text-gray-400">—</span>
                  </template>
                </el-table-column>
              </el-table>
              <el-divider content-position="left">MA60 走平判定（低于 MA60 减分减半）</el-divider>
              <el-row :gutter="12">
                <el-col :span="12">
                  <el-form-item label="回看周期(天)">
                    <el-input-number v-model="form.scoring.ma60_flat_lookback_days" :min="1" :max="120" class="w-full" />
                    <div class="text-xs text-gray-500">默认与观察周期一致（{{ form.observation_period }} 天）</div>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="变化率阈值">
                    <el-input-number v-model="form.scoring.ma60_flat_tol" :min="0.001" :max="0.1" :step="0.001" :precision="4" class="w-full" />
                    <div class="text-xs text-gray-500">|MA60今-MA60_N日前|/MA60_N日前 &lt; 阈值视为走平，默认 1.5%</div>
                  </el-form-item>
                </el-col>
              </el-row>
            </template>
          </el-form>

          <el-input v-else v-model="configJson" type="textarea" :rows="22" class="font-mono text-sm" />
        </el-card>
        <el-empty v-else description="请选择参数版本" />
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, inject } from 'vue'
import { ElMessage } from 'element-plus'
import type { GMSStrategyConfig } from '@/services/gmsApi'

const gmsApi = inject<any>('gmsApi')

const versions = ref<GMSStrategyConfig[]>([])
const selectedId = ref<number | null>(null)
const listLoading = ref(false)
const saving = ref(false)
const showJson = ref(false)
const configJson = ref('{}')

const editMeta = reactive({ precompute_enabled: false })

const defaultForm = () => ({
  observation_period: 20,
  left_buy: { ratio_d20_abs_max: 0.015, volume_ratio_max: 0.8, min_accumulation_score: 0 },
  right_buy: { volume_ratio_min: 1.5 },
  scoring: {
    accumulation_fz_min: 1.5,
    balance_ratio_max: 0.01,
    momentum_volume_ratio_min: 1.5,
    watch_threshold: 60,
    alert_threshold: 90,
    accumulation_s_threshold: 85,
    accumulation_a_threshold: 70,
    momentum_full_threshold: 90,
    momentum_batch_threshold: 80,
    instant_deviation_stable_days: 3,
    weight_acc_fz: 30,
    weight_acc_balance: 40,
    weight_acc_volume: 30,
    weight_mom_ratio_d1: 40,
    weight_mom_deviation: 30,
    weight_mom_volume: 30,
    ma60_flat_lookback_days: 20,
    ma60_flat_tol: 0.015,
  },
  exit: { trend_break_days: 3, overbought_ratio: 0.15 },
  ratio_indicators: { use_ratio_d: true, use_ratio_d_for_exit: false },
})

function applyParamsToForm(params: Record<string, any>) {
  const d = defaultForm()
  form.observation_period = params.observation_period ?? d.observation_period
  form.left_buy = { ...d.left_buy, ...(params.left_buy || {}) }
  form.right_buy = { ...d.right_buy, ...(params.right_buy || {}) }
  form.scoring = { ...d.scoring, ...(params.scoring || {}) }
  form.exit = { ...d.exit, ...(params.exit || {}) }
  form.ratio_indicators = { ...d.ratio_indicators, ...(params.ratio_indicators || {}) }
}

const form = reactive(defaultForm())

const selected = computed(() => versions.value.find((v) => v.id === selectedId.value) || null)

const penaltyRuleTypes = ref<any[]>([])
const penaltyRules = ref<any[]>([])

const showPenaltyEditor = computed(
  () =>
    selected.value?.name === 'gms_penalty' ||
    selected.value?.scoring_mechanism === 'tiered_dual_penalty' ||
    (form.scoring as any).mechanism === 'tiered_dual_penalty'
)

function syncPenaltyRulesFromForm(params: Record<string, any>) {
  const existing = (params.scoring?.penalty_rules || []) as any[]
  const byId = Object.fromEntries(existing.map((r) => [r.id, r]))
  penaltyRules.value = penaltyRuleTypes.value.map((meta) => {
    const cur = byId[meta.id] || {}
    const row: Record<string, unknown> = {
      id: meta.id,
      label: meta.label,
      description: meta.description,
      enabled: cur.enabled !== false,
      points: cur.points != null ? cur.points : meta.default_points ?? 10,
    }
    if (meta.id === 'observation_range_amplitude') {
      row.amplitude_threshold_pct =
        cur.amplitude_threshold_pct != null && !Number.isNaN(Number(cur.amplitude_threshold_pct))
          ? Number(cur.amplitude_threshold_pct)
          : Number(meta.default_amplitude_threshold_pct ?? 0.3)
    }
    return row
  })
}

function mergePenaltyRulesIntoForm(partial: Record<string, unknown>) {
  if (!showPenaltyEditor.value || !penaltyRules.value.length) return partial
  const scoring = { ...((partial.scoring as Record<string, unknown>) || {}) }
  scoring.mechanism = 'tiered_dual_penalty'
  scoring.penalty_rules = penaltyRules.value.map((r) => {
    const item: Record<string, unknown> = {
      id: r.id,
      enabled: r.enabled,
      points: r.points,
      label: r.label,
    }
    if (r.id === 'observation_range_amplitude' && r.amplitude_threshold_pct != null) {
      item.amplitude_threshold_pct = r.amplitude_threshold_pct
    }
    return item
  })
  return { ...partial, scoring }
}

async function loadVersions() {
  listLoading.value = true
  try {
    versions.value = await gmsApi.listStrategyConfigs()
    if (!selectedId.value && versions.value.length) {
      const def = versions.value.find((v) => v.is_default) || versions.value[0]
      selectedId.value = def.id
      await loadDetail(def.id)
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '加载版本列表失败')
  } finally {
    listLoading.value = false
  }
}

async function loadDetail(id: number) {
  const data = await gmsApi.getStrategyConfig(id)
  const params = data.config_params || {}
  applyParamsToForm(params)
  editMeta.precompute_enabled = !!data.precompute_enabled
  syncPenaltyRulesFromForm(params)
  configJson.value = JSON.stringify(params, null, 2)
}

function onSelectVersion(row: GMSStrategyConfig | null) {
  if (!row) return
  selectedId.value = row.id
  void loadDetail(row.id)
}

async function saveVersion() {
  if (!selectedId.value) return
  saving.value = true
  try {
    let partial: Record<string, unknown>
    if (showJson.value) {
      partial = JSON.parse(configJson.value)
    } else {
      partial = mergePenaltyRulesIntoForm(JSON.parse(JSON.stringify(form)))
    }
    await gmsApi.updateStrategyConfig(selectedId.value, {
      config: partial,
      precompute_enabled: editMeta.precompute_enabled,
      change_note: 'admin ui save',
    })
    await loadVersions()
    ElMessage.success('已保存')
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

defineExpose({ loadVersions })
onMounted(async () => {
  try {
    penaltyRuleTypes.value = await gmsApi.getPenaltyRuleTypes()
  } catch {
    penaltyRuleTypes.value = []
  }
  await loadVersions()
})
</script>

<style scoped>
.mb-3 { margin-bottom: 0.75rem; }
.ml-1 { margin-left: 0.25rem; }
.font-mono { font-family: ui-monospace, monospace; }
.param-form { max-width: 960px; }
</style>
