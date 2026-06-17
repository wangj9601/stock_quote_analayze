<template>
  <div class="strategy-configuration">
    <el-row :gutter="16">
      <el-col :span="7">
        <el-card header="参数版本列表">
          <div class="mb-3 flex flex-wrap gap-2">
            <el-button type="primary" size="small" @click="openCreateDialog">新建</el-button>
            <el-button size="small" :disabled="!selectedId" @click="handleClone">克隆</el-button>
            <el-button size="small" :disabled="!selectedId || selected?.is_default" @click="handleSetDefault">设为默认</el-button>
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
          </el-form>

          <el-input v-else v-model="configJson" type="textarea" :rows="22" class="font-mono text-sm" />
        </el-card>
        <el-empty v-else description="请选择或新建参数版本" />
      </el-col>
    </el-row>

    <el-dialog v-model="createVisible" title="新建参数版本" width="480px">
      <el-form label-width="100px">
        <el-form-item label="名称" required><el-input v-model="createForm.name" /></el-form-item>
        <el-form-item label="版本号"><el-input v-model="createForm.version_label" placeholder="如 1.0.0" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="createForm.description" type="textarea" /></el-form-item>
        <el-form-item label="预计算"><el-switch v-model="createForm.precompute_enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, inject } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { GMSStrategyConfig } from '@/services/gmsApi'

const gmsApi = inject<any>('gmsApi')

const versions = ref<GMSStrategyConfig[]>([])
const selectedId = ref<number | null>(null)
const listLoading = ref(false)
const saving = ref(false)
const creating = ref(false)
const showJson = ref(false)
const configJson = ref('{}')
const createVisible = ref(false)
const createForm = reactive({
  name: '',
  version_label: '1.0.0',
  description: '',
  precompute_enabled: false,
})

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
  configJson.value = JSON.stringify(params, null, 2)
}

function onSelectVersion(row: GMSStrategyConfig | null) {
  if (!row) return
  selectedId.value = row.id
  void loadDetail(row.id)
}

function openCreateDialog() {
  createForm.name = ''
  createForm.version_label = '1.0.0'
  createForm.description = ''
  createForm.precompute_enabled = false
  createVisible.value = true
}

async function submitCreate() {
  if (!createForm.name.trim()) {
    ElMessage.warning('请填写名称')
    return
  }
  creating.value = true
  try {
    const data = await gmsApi.createStrategyConfig({
      name: createForm.name.trim(),
      version_label: createForm.version_label,
      description: createForm.description,
      config_params: defaultForm(),
      precompute_enabled: createForm.precompute_enabled,
    })
    createVisible.value = false
    await loadVersions()
    selectedId.value = data.id
    await loadDetail(data.id)
    ElMessage.success('已创建')
  } catch (e: any) {
    ElMessage.error(e?.message || '创建失败')
  } finally {
    creating.value = false
  }
}

async function handleClone() {
  if (!selectedId.value) return
  const { value } = await ElMessageBox.prompt('请输入新版本名称', '克隆参数版本', {
    inputValue: `${selected.value?.name || 'copy'}-clone`,
  })
  if (!value?.trim()) return
  try {
    const data = await gmsApi.cloneStrategyConfig(selectedId.value, value.trim())
    await loadVersions()
    selectedId.value = data.id
    await loadDetail(data.id)
    ElMessage.success('克隆成功')
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e?.message || '克隆失败')
  }
}

async function handleSetDefault() {
  if (!selectedId.value) return
  try {
    await gmsApi.setStrategyConfigDefault(selectedId.value)
    await loadVersions()
    ElMessage.success('已设为默认版本')
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  }
}

async function saveVersion() {
  if (!selectedId.value) return
  saving.value = true
  try {
    let partial: Record<string, unknown>
    if (showJson.value) {
      partial = JSON.parse(configJson.value)
    } else {
      partial = JSON.parse(JSON.stringify(form))
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
onMounted(() => loadVersions())
</script>

<style scoped>
.mb-3 { margin-bottom: 0.75rem; }
.ml-1 { margin-left: 0.25rem; }
.font-mono { font-family: ui-monospace, monospace; }
.param-form { max-width: 960px; }
</style>
