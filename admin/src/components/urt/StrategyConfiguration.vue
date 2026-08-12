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
                <el-form-item label="量能满分倍数">
                  <el-input-number v-model="form.volume_score_full_multiple" :min="1" :max="30" :step="0.1" :precision="2" class="w-full" />
                </el-form-item>
              </el-col>
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
            </el-row>
            <el-row :gutter="12">
              <el-col :span="8">
                <el-form-item label="5日最少阳线">
                  <el-input-number v-model="form.yang_rule_b.min_up_days" :min="1" :max="5" class="w-full" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-divider content-position="left">中期阳线（默认开启硬筛）</el-divider>
            <el-alert
              type="info"
              :closable="false"
              show-icon
              class="mb-3"
              title="开启「中期阳线硬筛」后，须同时满足 10/15/20 日最低阳线数，买点会明显变少。"
            />
            <el-form-item label="中期阳线硬筛">
              <el-switch v-model="form.use_yang_medium" active-text="开启" inactive-text="关闭" />
            </el-form-item>
            <el-row :gutter="12">
              <el-col :span="8">
                <el-form-item label="10日最少阳线">
                  <el-input-number v-model="form.yang_medium_rules[0].min_up_days" :min="1" :max="10" class="w-full" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="15日最少阳线">
                  <el-input-number v-model="form.yang_medium_rules[1].min_up_days" :min="1" :max="15" class="w-full" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="20日最少阳线">
                  <el-input-number v-model="form.yang_medium_rules[2].min_up_days" :min="1" :max="20" class="w-full" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-divider content-position="left">均线多头（默认开启硬筛）</el-divider>
            <el-alert
              type="info"
              :closable="false"
              show-icon
              class="mb-3"
              title="多头排列默认 MA5>MA10>MA20。关闭硬筛时仍可打分：多头+6、空头-8。"
            />
            <el-form-item label="多头排列硬筛">
              <el-switch v-model="form.require_ma_bull" active-text="开启" inactive-text="关闭" />
            </el-form-item>

            <el-divider content-position="left">结构盈亏比 / KDE（混合）</el-divider>
            <el-alert
              type="info"
              :closable="false"
              show-icon
              class="mb-3"
              title="RR 偏低仅风险提示；破位支撑、贴/超阻力、悬空离支撑在硬闸开启时否决正式买点。KDE 无效不硬闸。"
            />
            <el-row :gutter="12">
              <el-col :span="8">
                <el-form-item label="结构风险提示">
                  <el-switch v-model="form.structure_rr_warn_enabled" active-text="开" inactive-text="关" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="结构硬闸">
                  <el-switch v-model="form.structure_rr_hard_gate_enabled" active-text="开" inactive-text="关" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="最低 RR">
                  <el-input-number v-model="form.structure_rr_min_rr" :min="0.5" :max="10" :step="0.1" :precision="2" class="w-full" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="12">
              <el-col :span="8">
                <el-form-item label="最小上行%">
                  <el-input-number
                    v-model="form.structure_rr_min_upside_pct_ui"
                    :min="0"
                    :max="20"
                    :step="0.5"
                    :precision="1"
                    @change="onMinUpsidePctUiChange"
                  />
                  <span class="hang-hint">距阻力相对现价低于此%视为上行不足（硬闸）</span>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="悬空阈值%">
                  <el-input-number
                    v-model="form.structure_hang_min_upside_pct_ui"
                    :min="1"
                    :max="50"
                    :step="0.5"
                    :precision="1"
                    @change="onHangPctUiChange"
                  />
                  <span class="hang-hint">相对支撑距离 ≥ 此% 视为悬空</span>
                </el-form-item>
              </el-col>
            </el-row>

            <el-divider content-position="left">近期涨幅过大</el-divider>
            <el-alert
              type="info"
              :closable="false"
              show-icon
              class="mb-3"
              title="近 N 日相对最低价涨幅：≥软阈值仅提示，≥硬阈值否决买点；相对 MA20 乖离同理。"
            />
            <el-row :gutter="12">
              <el-col :span="8">
                <el-form-item label="过热提示">
                  <el-switch v-model="form.overheat_warn_enabled" active-text="开" inactive-text="关" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="过热硬闸">
                  <el-switch v-model="form.overheat_hard_gate_enabled" active-text="开" inactive-text="关" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="回看天数">
                  <el-input-number v-model="form.overheat_lookback_days" :min="3" :max="60" class="w-full" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="12">
              <el-col :span="6">
                <el-form-item label="涨幅提示%">
                  <el-input-number v-model="form.overheat_soft_pct_ui" :min="1" :max="80" :step="1" :precision="0" @change="syncOverheatPctUi" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="涨幅硬闸%">
                  <el-input-number v-model="form.overheat_hard_pct_ui" :min="1" :max="100" :step="1" :precision="0" @change="syncOverheatPctUi" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="乖离提示%">
                  <el-input-number v-model="form.overheat_bias_soft_pct_ui" :min="1" :max="80" :step="1" :precision="0" @change="syncOverheatPctUi" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="乖离硬闸%">
                  <el-input-number v-model="form.overheat_bias_hard_pct_ui" :min="1" :max="100" :step="1" :precision="0" @change="syncOverheatPctUi" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-divider content-position="left">精细化（换手默认开）</el-divider>
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
  volume_multiple: 3.0,
  volume_score_full_multiple: 4.0,
  min_score: 70,
  yang_rule_a: { window: 4, min_up_days: 3 },
  yang_rule_b: { window: 5, min_up_days: 4 },
  yang_medium_rules: [
    { window: 10, min_up_days: 6 },
    { window: 15, min_up_days: 8 },
    { window: 20, min_up_days: 10 },
  ],
  use_yang_medium: true,
  require_ma_bull: true,
  ma_bull_periods: [5, 10, 20],
  use_turnover: true,
  use_volume_ratio: false,
  min_turnover: 3.0,
  min_volume_ratio: 0,
  history_calendar_days: 120,
  structure_rr_warn_enabled: true,
  structure_rr_hard_gate_enabled: true,
  structure_rr_min_rr: 2.0,
  structure_rr_min_upside_pct: 0.03,
  structure_rr_min_upside_pct_ui: 3.0,
  structure_hang_min_upside_pct: 0.08,
  structure_hang_min_upside_pct_ui: 8.0,
  overheat_warn_enabled: true,
  overheat_hard_gate_enabled: true,
  overheat_lookback_days: 10,
  overheat_soft_pct: 0.15,
  overheat_hard_pct: 0.25,
  overheat_bias_soft_pct: 0.15,
  overheat_bias_hard_pct: 0.20,
  overheat_soft_pct_ui: 15,
  overheat_hard_pct_ui: 25,
  overheat_bias_soft_pct_ui: 15,
  overheat_bias_hard_pct_ui: 20,
  risk: {
    stop_loss_pct_min: 5,
    stop_loss_pct_max: 10,
    time_stop_down_days: 3,
    take_profit_alert_pct_min: 25,
    take_profit_alert_pct_max: 30,
    trailing_drawdown_pct: 5,
  },
})

function onHangPctUiChange(v: number | undefined) {
  const pct = Number(v)
  if (!Number.isFinite(pct)) return
  form.structure_hang_min_upside_pct = Math.max(0, pct) / 100
}

function onMinUpsidePctUiChange(v: number | undefined) {
  const pct = Number(v)
  if (!Number.isFinite(pct)) return
  form.structure_rr_min_upside_pct = Math.max(0, pct) / 100
}

function syncOverheatPctUi() {
  form.overheat_soft_pct = Math.max(0, Number(form.overheat_soft_pct_ui) || 0) / 100
  form.overheat_hard_pct = Math.max(0, Number(form.overheat_hard_pct_ui) || 0) / 100
  form.overheat_bias_soft_pct = Math.max(0, Number(form.overheat_bias_soft_pct_ui) || 0) / 100
  form.overheat_bias_hard_pct = Math.max(0, Number(form.overheat_bias_hard_pct_ui) || 0) / 100
}

function applyParams(params: Record<string, any> = {}) {
  form.ma_period = params.ma_period ?? 20
  form.volume_lookback = params.volume_lookback ?? 20
  form.volume_multiple = params.volume_multiple ?? 3.0
  form.volume_score_full_multiple = params.volume_score_full_multiple ?? 4.0
  form.min_score = params.min_score ?? 70
  form.yang_rule_a = { window: 4, min_up_days: 3, ...(params.yang_rule_a || {}) }
  form.yang_rule_b = { window: 5, min_up_days: 4, ...(params.yang_rule_b || {}) }
  const midDefault = [
    { window: 10, min_up_days: 6 },
    { window: 15, min_up_days: 8 },
    { window: 20, min_up_days: 10 },
  ]
  const midRaw = Array.isArray(params.yang_medium_rules) ? params.yang_medium_rules : []
  form.yang_medium_rules = midDefault.map((d, i) => {
    const hit = midRaw.find((r: any) => Number(r?.window) === d.window) || midRaw[i] || {}
    return {
      window: d.window,
      min_up_days: Number(hit.min_up_days ?? d.min_up_days),
    }
  })
  form.use_yang_medium = params.use_yang_medium !== false
  form.require_ma_bull = params.require_ma_bull !== false
  form.ma_bull_periods = Array.isArray(params.ma_bull_periods) && params.ma_bull_periods.length >= 2
    ? params.ma_bull_periods.map((x: any) => Number(x))
    : [5, 10, 20]
  form.use_turnover = params.use_turnover !== false
  form.use_volume_ratio = !!params.use_volume_ratio
  form.min_turnover = params.min_turnover ?? 3.0
  form.min_volume_ratio = params.min_volume_ratio ?? 0
  form.history_calendar_days = params.history_calendar_days ?? 120
  form.structure_rr_warn_enabled = params.structure_rr_warn_enabled !== false
  form.structure_rr_hard_gate_enabled = params.structure_rr_hard_gate_enabled !== false
  form.structure_rr_min_rr = params.structure_rr_min_rr ?? 2.0
  const minUp = Number(params.structure_rr_min_upside_pct)
  form.structure_rr_min_upside_pct = Number.isFinite(minUp) ? minUp : 0.03
  form.structure_rr_min_upside_pct_ui = Math.round(form.structure_rr_min_upside_pct * 1000) / 10
  const hang = Number(params.structure_hang_min_upside_pct)
  form.structure_hang_min_upside_pct = Number.isFinite(hang) ? hang : 0.08
  form.structure_hang_min_upside_pct_ui = Math.round(form.structure_hang_min_upside_pct * 1000) / 10
  form.overheat_warn_enabled = params.overheat_warn_enabled !== false
  form.overheat_hard_gate_enabled = params.overheat_hard_gate_enabled !== false
  form.overheat_lookback_days = params.overheat_lookback_days ?? 10
  const soft = Number(params.overheat_soft_pct)
  form.overheat_soft_pct = Number.isFinite(soft) ? soft : 0.15
  const hard = Number(params.overheat_hard_pct)
  form.overheat_hard_pct = Number.isFinite(hard) ? hard : 0.25
  const bsoft = Number(params.overheat_bias_soft_pct)
  form.overheat_bias_soft_pct = Number.isFinite(bsoft) ? bsoft : 0.15
  const bhard = Number(params.overheat_bias_hard_pct)
  form.overheat_bias_hard_pct = Number.isFinite(bhard) ? bhard : 0.20
  form.overheat_soft_pct_ui = Math.round(form.overheat_soft_pct * 100)
  form.overheat_hard_pct_ui = Math.round(form.overheat_hard_pct * 100)
  form.overheat_bias_soft_pct_ui = Math.round(form.overheat_bias_soft_pct * 100)
  form.overheat_bias_hard_pct_ui = Math.round(form.overheat_bias_hard_pct * 100)
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
    let params: Record<string, any>
    if (showJson.value) {
      params = JSON.parse(jsonText.value)
    } else {
      const {
        structure_hang_min_upside_pct_ui,
        structure_rr_min_upside_pct_ui,
        overheat_soft_pct_ui,
        overheat_hard_pct_ui,
        overheat_bias_soft_pct_ui,
        overheat_bias_hard_pct_ui,
        ...rest
      } = form
      onHangPctUiChange(structure_hang_min_upside_pct_ui)
      onMinUpsidePctUiChange(structure_rr_min_upside_pct_ui)
      syncOverheatPctUi()
      params = { ...rest }
      delete params.structure_hang_min_upside_pct_ui
      delete params.structure_rr_min_upside_pct_ui
      delete params.overheat_soft_pct_ui
      delete params.overheat_hard_pct_ui
      delete params.overheat_bias_soft_pct_ui
      delete params.overheat_bias_hard_pct_ui
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
.hang-hint {
  margin-left: 8px;
  color: #909399;
  font-size: 12px;
}
</style>
