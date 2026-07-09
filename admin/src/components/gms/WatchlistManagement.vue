<template>
  <div class="watchlist-management">
    <el-card class="toolbar">
      <el-row :gutter="12" align="middle">
        <el-col :span="6">
          <el-select v-model="selectedVersionId" placeholder="选择 GMS 策略版本" filterable @change="handleVersionChange">
            <el-option
              v-for="v in versions"
              :key="v.id"
              :label="versionOptionLabel(v)"
              :value="v.id"
            />
          </el-select>
        </el-col>
        <el-col :span="3" v-if="activeTab === 'stocks'">
          <el-select v-model="marketFilter" placeholder="市场" clearable @change="refresh">
            <el-option label="A股" value="A" />
            <el-option label="港股" value="HK" />
          </el-select>
        </el-col>
        <el-col :span="5" v-if="activeTab === 'stocks'">
          <el-input v-model="keyword" placeholder="代码/名称" clearable @keyup.enter="refresh" />
        </el-col>
        <el-col :span="activeTab === 'stocks' ? 10 : 15" class="actions">
          <el-button type="primary" @click="openVersionDialog()">新增版本</el-button>
          <template v-if="activeTab === 'stocks'">
            <el-button type="success" :disabled="!selectedVersionId" @click="openStockDialog()">新增观察股</el-button>
            <el-button :disabled="!selectedIds.length" @click="batchDelete">批量删除</el-button>
            <el-button :disabled="!selectedVersionId" @click="openImportDialog">批量导入</el-button>
            <el-button :disabled="!selectedVersionId" @click="handleExport">批量导出</el-button>
            <el-button @click="refresh">刷新</el-button>
          </template>
          <template v-else>
            <el-button type="primary" :disabled="!selectedVersionId || scoringSaving" :loading="scoringSaving" @click="saveScoring">
              保存打分配置
            </el-button>
            <el-button :disabled="!selectedVersionId" @click="loadScoringPanel">刷新</el-button>
          </template>
        </el-col>
      </el-row>
    </el-card>

    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <el-tab-pane label="观察股" name="stocks">
        <el-table v-loading="loading" :data="stocks" @selection-change="onSelectionChange">
          <el-table-column type="selection" width="42" />
          <el-table-column prop="market" label="市场" width="80" />
          <el-table-column prop="stock_code" label="代码" width="120" />
          <el-table-column prop="stock_name" label="名称" min-width="120" />
          <el-table-column prop="industry" label="行业" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.industry">{{ row.industry }}</span>
              <span v-else class="text-gray-400">-</span>
            </template>
          </el-table-column>
          <el-table-column label="当前价格" width="100">
            <template #default="scope">
              <span v-if="scope.row.current_price != null">
                {{ scope.row.market === 'HK' ? '$' : '¥' }}{{ scope.row.current_price.toFixed(2) }}
              </span>
              <span v-else class="text-gray-400">-</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="88" align="center">
            <template #default="{ row }">
              <el-switch
                :model-value="row.status === 'active'"
                size="small"
                inline-prompt
                active-text="启用"
                inactive-text="停用"
                @change="(val: boolean) => toggleStatus(row, val)"
              />
            </template>
          </el-table-column>
          <el-table-column label="审核" width="80">
            <template #default="{ row }">
              <el-switch v-model="row.is_verified" size="small" @change="(val: boolean) => toggleVerified(row, val)" />
            </template>
          </el-table-column>
          <el-table-column prop="sort_order" label="排序" width="90" />
          <el-table-column prop="remark" label="备注" min-width="140" />
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openStockDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="removeStock(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next, sizes"
          :page-sizes="[20, 50, 100]"
          @current-change="refresh"
          @size-change="refresh"
        />
      </el-tab-pane>

      <el-tab-pane label="打分与参数" name="scoring">
        <div v-loading="scoringLoading" class="scoring-panel">
          <el-empty v-if="!selectedVersionId" description="请先选择 GMS 策略版本" />
          <template v-else>
            <el-alert
              type="info"
              :closable="false"
              class="mb-4"
              :title="`保存目标：共享参数「${canonicalTargetLabel}」${currentVersion?.config_id ? ` (config_id=${currentVersion.config_id})` : ''}`"
              description="全系统仅两个 GMS 参数版本：default（标准版）与 gms_penalty（减分版）。修改会原地更新对应共享配置，不会新建 auto_gms_* 版本。"
            />

            <el-form label-width="140px" class="max-w-3xl">
              <el-form-item label="打分机制">
                <el-select v-model="scoringForm.scoring_mechanism" class="w-full" @change="onMechanismChange">
                  <el-option
                    v-for="m in scoringMechanisms"
                    :key="m.id"
                    :label="m.label"
                    :value="m.id"
                  />
                </el-select>
                <p v-if="selectedMechanismMeta?.description" class="text-xs text-gray-500 mt-1">
                  {{ selectedMechanismMeta.description }}
                </p>
              </el-form-item>

              <template v-if="scoringForm.scoring_mechanism === 'tiered_dual_penalty'">
                <el-divider content-position="left">减分规则</el-divider>
                <p class="text-xs text-gray-500 mb-3">
                  增强版在基础分上按规则扣分；勾选启用并设置每条规则的扣分分值（1～100），保存后选股明细即时生效。
                </p>
                <div class="penalty-rules-list">
                  <div
                    v-for="rule in scoringForm.penalty_rules"
                    :key="rule.id"
                    class="penalty-rule-item"
                  >
                    <div class="penalty-rule-head">
                      <el-checkbox v-model="rule.enabled" class="penalty-rule-check">
                        {{ rule.label || rule.id }}
                      </el-checkbox>
                      <div class="penalty-rule-controls">
                        <div class="penalty-field">
                          <span class="penalty-field-label">扣分</span>
                          <el-input-number
                            v-model="rule.points"
                            :min="1"
                            :max="100"
                            :step="1"
                            controls-position="right"
                            class="penalty-input-num"
                          />
                          <span class="penalty-field-suffix">分</span>
                        </div>
                        <div
                          v-if="rule.id === 'observation_range_amplitude'"
                          class="penalty-field penalty-field-threshold"
                        >
                          <span class="penalty-field-label">振幅阈值</span>
                          <el-input-number
                            v-model="rule.amplitude_threshold_pct"
                            :min="0.01"
                            :max="2"
                            :step="0.01"
                            :precision="2"
                            controls-position="right"
                            class="penalty-input-num penalty-input-threshold"
                          />
                          <span class="penalty-field-suffix">（0.30 = 30%）</span>
                        </div>
                      </div>
                    </div>
                    <p v-if="penaltyRuleHint(rule.id)" class="penalty-rule-desc">
                      {{ penaltyRuleHint(rule.id) }}
                    </p>
                  </div>
                </div>
                <el-button size="small" class="mt-2" @click="addPenaltyRule">添加规则</el-button>
                <el-divider content-position="left">MA60 走平判定</el-divider>
                <p class="text-xs text-gray-500 mb-2">
                  收盘低于 MA60 时，若 MA60 在回看周期内变化率低于阈值，减分取半。回看周期默认与策略<strong>观察周期</strong>（observation_period，默认 20 个交易日）一致，可在下方单独修改。
                </p>
                <el-row :gutter="16">
                  <el-col :span="12">
                    <el-form-item label="回看周期(天)">
                      <el-input-number
                        v-model="scoringForm.config.scoring.ma60_flat_lookback_days"
                        :min="1"
                        :max="120"
                        class="w-full"
                      />
                    </el-form-item>
                  </el-col>
                  <el-col :span="12">
                    <el-form-item label="变化率阈值">
                      <el-input-number
                        v-model="scoringForm.config.scoring.ma60_flat_tol"
                        :min="0.001"
                        :max="0.1"
                        :step="0.001"
                        :precision="4"
                        class="w-full"
                      />
                    </el-form-item>
                  </el-col>
                </el-row>
              </template>

              <el-divider content-position="left">核心阈值</el-divider>
              <el-row :gutter="16">
                <el-col :span="12">
                  <el-form-item label="关注阈值">
                    <el-input-number v-model="scoringForm.config.scoring.watch_threshold" :min="0" :max="100" class="w-full" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="预警阈值">
                    <el-input-number v-model="scoringForm.config.scoring.alert_threshold" :min="0" :max="100" class="w-full" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="F/Z 下限">
                    <el-input-number v-model="scoringForm.config.scoring.accumulation_fz_min" :step="0.1" class="w-full" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="平衡 |Δ/d| 上限">
                    <el-input-number v-model="scoringForm.config.scoring.balance_ratio_max" :step="0.001" :precision="4" class="w-full" />
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
          </template>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="versionDialogVisible" title="GMS 策略版本" @opened="() => versionStrategyCodeRef?.focus()">
      <el-form :model="versionForm" label-width="120px">
        <el-form-item label="策略编码"><el-input ref="versionStrategyCodeRef" v-model="versionForm.strategy_code" @keyup.enter="saveVersion" /></el-form-item>
        <el-form-item label="版本名称"><el-input v-model="versionForm.version_name" @keyup.enter="saveVersion" /></el-form-item>
        <el-form-item label="版本序号"><el-input-number v-model="versionForm.version_no" :min="1" @keyup.enter="saveVersion" /></el-form-item>
        <el-form-item label="打分机制">
          <el-select v-model="versionForm.scoring_mechanism" class="w-full" @change="onVersionDialogMechanismChange">
            <el-option v-for="m in scoringMechanisms" :key="m.id" :label="m.label" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="versionForm.scoring_mechanism === 'tiered_dual_penalty'" label="减分规则">
          <div v-for="(rule, idx) in versionForm.penalty_rules" :key="idx" class="penalty-row">
            <el-checkbox v-model="rule.enabled">{{ rule.label || rule.id }}</el-checkbox>
            <span class="text-sm text-gray-600">扣分</span>
            <el-input-number v-model="rule.points" :min="1" :max="100" />
            <span class="text-sm text-gray-500">分</span>
          </div>
        </el-form-item>
        <el-form-item label="启用"><el-switch v-model="versionForm.is_active" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="versionForm.description" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="versionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveVersion">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="stockDialogVisible" title="观察股" @opened="() => stockCodeRef?.focus()">
      <el-form :model="stockForm" label-width="90px">
        <el-form-item label="市场">
          <el-select v-model="stockForm.market"><el-option label="A股" value="A" /><el-option label="港股" value="HK" /></el-select>
        </el-form-item>
        <el-form-item label="代码"><el-input ref="stockCodeRef" v-model="stockForm.stock_code" @keyup.enter="saveStock" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="stockForm.stock_name" @keyup.enter="saveStock" /></el-form-item>
        <el-form-item label="状态"><el-select v-model="stockForm.status"><el-option label="active" value="active" /><el-option label="inactive" value="inactive" /></el-select></el-form-item>
        <el-form-item label="审核"><el-switch v-model="stockForm.is_verified" /></el-form-item>
        <el-form-item label="排序"><el-input-number v-model="stockForm.sort_order" @keyup.enter="saveStock" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="stockForm.remark" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stockDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveStock">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="importDialogVisible" title="批量导入观察股" @closed="resetImportForm">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="mb-3"
        title="每行一个，格式：市场,代码,名称（名称可省略），例如：A,000001,平安银行"
      />
      <el-checkbox v-model="importClearExisting" class="mb-3">
        导入前清空当前策略版本下全部观察股
      </el-checkbox>
      <el-input
        ref="importInputRef"
        v-model="importText"
        type="textarea"
        :rows="10"
        placeholder="每行一个，格式：市场,代码,名称（名称可省略） 例如：A,000001,平安银行"
      />
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitImport">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  gmsApiService,
  type GMSScoringMechanism,
  type GMSPenaltyRule,
  type GMSPenaltyRuleType,
  type GMSStrategyVersionStock,
  type GMSStrategyVersion,
} from '@/services/gmsApi'

const stockCodeRef = ref<any>(null)
const versionStrategyCodeRef = ref<any>(null)
const importInputRef = ref<any>(null)

const activeTab = ref<'stocks' | 'scoring'>('stocks')
const loading = ref(false)
const versions = ref<GMSStrategyVersion[]>([])
const scoringMechanisms = ref<GMSScoringMechanism[]>([])
const penaltyRuleTypes = ref<GMSPenaltyRuleType[]>([])
const selectedVersionId = ref<number>()
const stocks = ref<GMSStrategyVersionStock[]>([])
const selectedIds = ref<number[]>([])
const keyword = ref('')
const marketFilter = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const scoringLoading = ref(false)
const scoringSaving = ref(false)
const scoringForm = ref({
  scoring_mechanism: 'tiered_dual_max',
  penalty_rules: [] as GMSPenaltyRule[],
  config: {
    scoring: {
      watch_threshold: 60,
      alert_threshold: 80,
      accumulation_fz_min: 1,
      balance_ratio_max: 0.02,
      ma60_flat_lookback_days: 20,
      ma60_flat_tol: 0.015,
    },
  } as Record<string, any>,
})

const versionDialogVisible = ref(false)
const editingVersionId = ref<number | null>(null)
const versionForm = ref({
  strategy_code: 'GMS',
  version_name: '',
  version_no: 1,
  description: '',
  is_active: true,
  created_by: 'admin',
  auto_create_config: true,
  scoring_mechanism: 'tiered_dual_max',
  penalty_rules: [] as GMSPenaltyRule[],
})

const stockDialogVisible = ref(false)
const editingStockId = ref<number | null>(null)
const stockForm = ref({
  market: 'A' as 'A' | 'HK',
  stock_code: '',
  stock_name: '',
  status: 'active',
  is_verified: false,
  sort_order: 0,
  remark: '',
})

const importDialogVisible = ref(false)
const importText = ref('')
const importClearExisting = ref(false)

const currentVersion = computed(() => versions.value.find((v) => v.id === selectedVersionId.value))
const selectedMechanismMeta = computed(() =>
  scoringMechanisms.value.find((m) => m.id === scoringForm.value.scoring_mechanism)
)

const canonicalTargetLabel = computed(() =>
  scoringForm.value.scoring_mechanism === 'tiered_dual_penalty'
    ? 'gms_penalty · 增强版·阶梯+减分'
    : 'default · 标准版·双模块阶梯'
)

function versionOptionLabel(v: GMSStrategyVersion) {
  const tag = v.scoring_mechanism_label ? ` [${v.scoring_mechanism_label}]` : ''
  return `${v.strategy_code}-V${v.version_no} ${v.version_name}${tag}`
}

function penaltyRuleMetaList(): GMSPenaltyRuleType[] {
  const fallback: GMSPenaltyRuleType[] = [
    { id: 'close_below_ma60', label: '收盘低于 MA60', default_points: 10 },
    {
      id: 'observation_range_amplitude',
      label: '观察周期振幅过大',
      default_points: 10,
      default_amplitude_threshold_pct: 0.3,
    },
  ]
  const base = penaltyRuleTypes.value.length ? [...penaltyRuleTypes.value] : fallback
  if (!base.some((t) => t.id === 'observation_range_amplitude')) {
    base.push(fallback[1])
  }
  return base
}

function normalizePenaltyRuleFields(rule: GMSPenaltyRule, meta?: GMSPenaltyRuleType): GMSPenaltyRule {
  const m = meta || penaltyRuleMetaList().find((t) => t.id === rule.id)
  const out: GMSPenaltyRule = {
    id: rule.id,
    label: rule.label || m?.label || rule.id,
    enabled: rule.enabled !== false,
    points: toPenaltyPoints(rule.points ?? m?.default_points),
  }
  if (rule.id === 'observation_range_amplitude') {
    out.amplitude_threshold_pct = toAmplitudeThreshold(
      rule.amplitude_threshold_pct ?? m?.default_amplitude_threshold_pct
    )
  }
  if (rule.id === 'close_below_ma60') {
    out.half_when_ma60_flat = rule.half_when_ma60_flat !== false
  }
  return out
}

function toPenaltyPoints(value: unknown, fallback = 10): number {
  const n = Number(value)
  return Number.isFinite(n) && n > 0 ? n : fallback
}

function toAmplitudeThreshold(value: unknown, fallback = 0.3): number {
  const n = Number(value)
  return Number.isFinite(n) && n > 0 ? n : fallback
}

/** 与 StrategyConfiguration 一致：按规则类型补全 points / amplitude_threshold_pct，避免 el-input-number 绑定 undefined */
function syncPenaltyRulesFromConfig(existing: GMSPenaltyRule[] = []): GMSPenaltyRule[] {
  const byId = Object.fromEntries(existing.map((r) => [r.id, r]))
  const synced = penaltyRuleMetaList().map((meta) => {
    const cur = byId[meta.id]
    return normalizePenaltyRuleFields(
      {
        id: meta.id,
        label: meta.label,
        enabled: cur != null ? cur.enabled !== false : false,
        points: cur?.points,
        amplitude_threshold_pct: cur?.amplitude_threshold_pct,
        half_when_ma60_flat: cur?.half_when_ma60_flat,
      },
      meta
    )
  })
  for (const r of existing) {
    if (!synced.some((s) => s.id === r.id)) {
      synced.push(normalizePenaltyRuleFields(r))
    }
  }
  return synced
}

function serializePenaltyRulesForSave(rules: GMSPenaltyRule[]): GMSPenaltyRule[] {
  return syncPenaltyRulesFromConfig(rules).map((r) => {
    const item: GMSPenaltyRule = {
      id: r.id,
      enabled: r.enabled,
      points: r.points,
      label: r.label,
    }
    if (r.id === 'observation_range_amplitude') {
      item.amplitude_threshold_pct = r.amplitude_threshold_pct
    }
    if (r.id === 'close_below_ma60') {
      item.half_when_ma60_flat = r.half_when_ma60_flat
    }
    return item
  })
}

function defaultPenaltyRules(enabledOnly = false): GMSPenaltyRule[] {
  const rules = syncPenaltyRulesFromConfig([])
  if (enabledOnly) {
    return rules.map((r) => ({ ...r, enabled: true }))
  }
  return rules
}

function penaltyRuleHint(ruleId?: string): string {
  if (!ruleId) return ''
  const meta = penaltyRuleTypes.value.find((t) => t.id === ruleId)
  if (meta?.description) return meta.description
  const fallbacks: Record<string, string> = {
    close_below_ma60:
      '条件：收盘价 d₂₀ < MA60；MA60 走平时扣分减半（回看周期默认与观察周期相同，通常 20 个交易日）。',
    excessive_deviation:
      'Δ/d₂₀ 超过乖离过大阈值时扣分（默认 15%，可在策略参数「退出·乖离过大阈值」overbought_ratio 中配置）。',
    observation_range_amplitude:
      '观察周期内 (高−低)/高 超过振幅阈值时扣分；观察周期（observation_period）默认 20 个交易日。',
  }
  return fallbacks[ruleId] || ''
}

function onMechanismChange(mid: string) {
  if (mid === 'tiered_dual_penalty' && !scoringForm.value.penalty_rules.length) {
    scoringForm.value.penalty_rules = defaultPenaltyRules(true)
  }
  if (mid === 'tiered_dual_max') {
    scoringForm.value.penalty_rules = []
  }
}

function onVersionDialogMechanismChange(mid: string) {
  if (mid === 'tiered_dual_penalty') {
    versionForm.value.penalty_rules = defaultPenaltyRules(true)
  } else {
    versionForm.value.penalty_rules = []
  }
}

function addPenaltyRule() {
  const existing = new Set(scoringForm.value.penalty_rules.map((r) => r.id))
  const next = penaltyRuleTypes.value.find((t) => !existing.has(t.id))
  if (!next) {
    ElMessage.info('已添加全部可用减分规则')
    return
  }
  scoringForm.value.penalty_rules = syncPenaltyRulesFromConfig([
    ...scoringForm.value.penalty_rules,
    {
      id: next.id,
      label: next.label,
      enabled: true,
      points: toPenaltyPoints(next.default_points),
      ...(next.id === 'observation_range_amplitude'
        ? { amplitude_threshold_pct: toAmplitudeThreshold(next.default_amplitude_threshold_pct) }
        : {}),
    },
  ])
}

const loadVersions = async () => {
  const res = await gmsApiService.getStrategyVersions({ page: 1, page_size: 200 })
  versions.value = res.data || []
  if (!selectedVersionId.value && versions.value.length) {
    const v1 = versions.value.find((v) => v.version_no === 1)
    selectedVersionId.value = v1 ? v1.id : versions.value[0].id
  }
}

const loadScoringPanel = async () => {
  if (!selectedVersionId.value) return
  scoringLoading.value = true
  try {
    if (!penaltyRuleTypes.value.length) {
      try {
        penaltyRuleTypes.value = await gmsApiService.getPenaltyRuleTypes()
      } catch {
        /* 使用 penaltyRuleMetaList 内置 fallback */
      }
    }
    const full = await gmsApiService.getStrategyVersionFull(selectedVersionId.value)
    const v = full.version
    const params = full.config?.config_params || {}
    const scoring = (params.scoring || {}) as Record<string, any>
    const rawRules = ((v.penalty_rules?.length ? v.penalty_rules : scoring.penalty_rules) || []) as GMSPenaltyRule[]
    const mergedRules = syncPenaltyRulesFromConfig(rawRules)
    scoringForm.value = {
      scoring_mechanism: v.scoring_mechanism || scoring.mechanism || 'tiered_dual_max',
      penalty_rules: mergedRules.map((r) => ({ ...r })),
      config: {
        scoring: {
          watch_threshold: scoring.watch_threshold ?? 60,
          alert_threshold: scoring.alert_threshold ?? 80,
          accumulation_fz_min: scoring.accumulation_fz_min ?? 1,
          balance_ratio_max: scoring.balance_ratio_max ?? 0.02,
          ma60_flat_lookback_days:
            scoring.ma60_flat_lookback_days ?? (params as Record<string, any>).observation_period ?? 20,
          ma60_flat_tol: scoring.ma60_flat_tol ?? 0.015,
        },
      },
    }
    if (
      scoringForm.value.scoring_mechanism === 'tiered_dual_penalty' &&
      !rawRules.length
    ) {
      scoringForm.value.penalty_rules = defaultPenaltyRules(true)
    }
  } catch (e: any) {
    ElMessage.error(e.message || '加载打分配置失败')
  } finally {
    scoringLoading.value = false
  }
}

const saveScoring = async () => {
  if (!selectedVersionId.value) return
  if (scoringForm.value.scoring_mechanism === 'tiered_dual_penalty') {
    const enabled = scoringForm.value.penalty_rules.filter((r) => r.enabled)
    if (!enabled.length) {
      await ElMessageBox.alert('增强版至少需一条启用的减分规则', '校验失败', { type: 'warning' })
      return
    }
  }
  scoringSaving.value = true
  try {
    await gmsApiService.updateStrategyVersionScoring(selectedVersionId.value, {
      scoring_mechanism: scoringForm.value.scoring_mechanism,
      penalty_rules:
        scoringForm.value.scoring_mechanism === 'tiered_dual_penalty'
          ? serializePenaltyRulesForSave(scoringForm.value.penalty_rules)
          : [],
      config: scoringForm.value.config,
    })
    ElMessage.success('打分配置已保存')
    await loadVersions()
    await loadScoringPanel()
  } catch (e: any) {
    await ElMessageBox.alert(e.message || '保存失败', '错误', { type: 'error' })
  } finally {
    scoringSaving.value = false
  }
}

const refresh = async () => {
  if (!selectedVersionId.value) return
  loading.value = true
  try {
    const res = await gmsApiService.getStrategyVersionStocks({
      version_id: selectedVersionId.value,
      market: marketFilter.value || undefined,
      keyword: keyword.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    stocks.value = res.data || []
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}

const handleVersionChange = async () => {
  page.value = 1
  if (activeTab.value === 'scoring') {
    await loadScoringPanel()
  } else {
    await refresh()
  }
}

const onTabChange = async (name: string | number) => {
  if (name === 'scoring') {
    await loadScoringPanel()
  }
}

const onSelectionChange = (rows: GMSStrategyVersionStock[]) => {
  selectedIds.value = rows.map((v) => v.id)
}

const openVersionDialog = () => {
  editingVersionId.value = null
  versionForm.value = {
    strategy_code: 'GMS',
    version_name: '',
    version_no: 1,
    description: '',
    is_active: true,
    created_by: 'admin',
    auto_create_config: true,
    scoring_mechanism: 'tiered_dual_max',
    penalty_rules: [],
  }
  versionDialogVisible.value = true
}

const saveVersion = async () => {
  try {
    if (editingVersionId.value) {
      const { strategy_code, version_name, version_no, description, is_active, created_by } = versionForm.value
      await gmsApiService.updateStrategyVersion(editingVersionId.value, {
        strategy_code,
        version_name,
        version_no,
        description,
        is_active,
        created_by,
      })
    } else {
      await gmsApiService.createStrategyVersion(versionForm.value)
    }
    ElMessage.success('版本保存成功')
    versionDialogVisible.value = false
    await loadVersions()
  } catch (e: any) {
    await ElMessageBox.alert(e.message || '保存失败', '错误', { type: 'error' })
    setTimeout(() => versionStrategyCodeRef.value?.focus(), 50)
  }
}

const openStockDialog = (row?: GMSStrategyVersionStock) => {
  editingStockId.value = row?.id ?? null
  stockForm.value = row
    ? {
        market: row.market as 'A' | 'HK',
        stock_code: row.stock_code != null && row.stock_code !== '' ? String(row.stock_code) : '',
        stock_name: row.stock_name || '',
        status: row.status,
        is_verified: !!row.is_verified,
        sort_order: row.sort_order,
        remark: row.remark || '',
      }
    : { market: 'A' as 'A' | 'HK', stock_code: '', stock_name: '', status: 'active', is_verified: false, sort_order: 0, remark: '' }
  stockDialogVisible.value = true
}

const saveStock = async () => {
  if (!selectedVersionId.value) return
  const codeStr = String(stockForm.value.stock_code ?? '').trim()
  const payload = { ...stockForm.value, stock_code: codeStr }
  try {
    if (editingStockId.value) {
      await gmsApiService.updateStrategyVersionStock(editingStockId.value, payload)
    } else {
      await gmsApiService.createStrategyVersionStock({ version_id: selectedVersionId.value, ...payload })
    }
    ElMessage.success('观察股保存成功')
    stockDialogVisible.value = false
    await refresh()
  } catch (e: any) {
    await ElMessageBox.alert(e.message || '保存失败', '录入错误', { type: 'error' })
    setTimeout(() => stockCodeRef.value?.focus(), 50)
  }
}

const toggleVerified = async (row: GMSStrategyVersionStock, verified: boolean) => {
  try {
    await gmsApiService.updateStrategyVersionStock(row.id, { is_verified: verified })
    ElMessage.success(`${row.stock_code} 审核状态已更新`)
  } catch (e: any) {
    row.is_verified = !verified
    ElMessage.error('更新失败: ' + (e.message || '未知错误'))
  }
}

const toggleStatus = async (row: GMSStrategyVersionStock, active: boolean) => {
  const next = active ? 'active' : 'inactive'
  const prev = row.status
  try {
    await gmsApiService.updateStrategyVersionStock(row.id, { status: next })
    row.status = next
    ElMessage.success(`${row.stock_code} 已${active ? '启用' : '停用'}`)
  } catch (e: any) {
    row.status = prev
    ElMessage.error('更新失败: ' + (e.message || '未知错误'))
  }
}

const removeStock = async (row: GMSStrategyVersionStock) => {
  await ElMessageBox.confirm(`确认删除 ${row.stock_code} 吗？`, '删除确认', { type: 'warning' })
  await gmsApiService.deleteStrategyVersionStock(row.id)
  ElMessage.success('已删除')
  await refresh()
}

const batchDelete = async () => {
  if (!selectedIds.value.length) return
  await ElMessageBox.confirm(`确认批量删除 ${selectedIds.value.length} 条记录吗？`, '批量删除确认', { type: 'warning' })
  const data = await gmsApiService.batchDeleteStrategyVersionStocks({ ids: selectedIds.value })
  ElMessage.success(`已删除 ${data.deleted} 条`)
  await refresh()
}

const openImportDialog = () => {
  resetImportForm()
  importDialogVisible.value = true
}

const resetImportForm = () => {
  importText.value = ''
  importClearExisting.value = false
}

const submitImport = async () => {
  if (!selectedVersionId.value) return
  if (importClearExisting.value) {
    const verLabel = currentVersion.value
      ? `${currentVersion.value.strategy_code}-V${currentVersion.value.version_no}`
      : `版本 ${selectedVersionId.value}`
    try {
      await ElMessageBox.confirm(
        `将清空「${verLabel}」下全部观察股后再导入，此操作不可恢复，是否继续？`,
        '清空并导入确认',
        { type: 'warning' },
      )
    } catch {
      return
    }
  }
  const items = importText.value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [market, stock_code, stock_name] = line.split(',').map((x) => (x || '').trim())
      return { market, stock_code, stock_name }
    })
  try {
    const data = await gmsApiService.batchImportStrategyVersionStocks({
      version_id: selectedVersionId.value,
      items,
      clear_existing: importClearExisting.value,
    })
    const clearedTip = data.cleared_count ? `，已清空 ${data.cleared_count} 条` : ''
    if (data.fail_count > 0) {
      const reasons = data.fail_details.map((f) => `${f.stock_code}: ${f.reason}`).join('\n')
      await ElMessageBox.alert(
        `导入完成：成功${data.success_count}，失败${data.fail_count}，跳过${data.skip_count}${clearedTip}\n失败详情：\n${reasons}`,
        '导入结果',
        { type: 'warning' }
      )
      await refresh()
    } else {
      ElMessage.success(`导入完成：成功${data.success_count}，跳过${data.skip_count}${clearedTip}`)
      importDialogVisible.value = false
      await refresh()
    }
  } catch (e: any) {
    await ElMessageBox.alert(e.message || '导入失败', '错误', { type: 'error' })
    setTimeout(() => importInputRef.value?.focus(), 50)
  }
}

const handleExport = async () => {
  if (!selectedVersionId.value) return

  try {
    loading.value = true
    let allStocks: GMSStrategyVersionStock[] = []
    let currentPage = 1
    const size = 200

    while (true) {
      const res = await gmsApiService.getStrategyVersionStocks({
        version_id: selectedVersionId.value,
        page: currentPage,
        page_size: size,
      })

      const data = res.data || []
      allStocks = allStocks.concat(data)

      if (allStocks.length >= (res.total || 0) || data.length < size) {
        break
      }
      currentPage++
    }

    if (allStocks.length === 0) {
      ElMessage.info('没有可导出的观察股')
      return
    }

    const content = allStocks.map((s) => `${s.market},${s.stock_code},${s.stock_name || ''}`).join('\n')

    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')

    const version = versions.value.find((v) => v.id === selectedVersionId.value)
    const fileName = version
      ? `watch_list_${version.strategy_code}_${version.version_no}.txt`
      : 'watch_list_export.txt'

    link.href = url
    link.download = fileName
    link.click()
    URL.revokeObjectURL(url)

    ElMessage.success(`成功导出 ${allStocks.length} 条记录`)
  } catch (e: any) {
    ElMessage.error('导出失败: ' + (e.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

defineExpose({ refresh })

onMounted(async () => {
  try {
    scoringMechanisms.value = await gmsApiService.getScoringMechanisms()
    penaltyRuleTypes.value = await gmsApiService.getPenaltyRuleTypes()
  } catch {
    scoringMechanisms.value = [
      { id: 'tiered_dual_max', label: '标准版·双模块阶梯', supports_penalties: false },
      { id: 'tiered_dual_penalty', label: '增强版·阶梯+减分', supports_penalties: true },
    ]
    penaltyRuleTypes.value = [{ id: 'close_below_ma60', label: '收盘低于 MA60', default_points: 10 }]
  }
  await loadVersions()
  await refresh()
})
</script>

<style scoped>
.toolbar {
  margin-bottom: 12px;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}
.scoring-panel {
  min-height: 280px;
  padding: 8px 0;
}
.penalty-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.penalty-rules-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.penalty-rule-item {
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
}
.penalty-rule-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 12px 20px;
}
.penalty-rule-check {
  min-width: 168px;
  flex-shrink: 0;
  margin-right: 4px;
}
.penalty-rule-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px 24px;
  flex: 1;
  min-width: 280px;
}
.penalty-field {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.penalty-field-label {
  font-size: 13px;
  color: var(--el-text-color-regular);
  white-space: nowrap;
}
.penalty-field-suffix {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}
.penalty-input-num {
  width: 120px;
}
.penalty-input-threshold {
  width: 132px;
}
.penalty-rule-desc {
  margin: 10px 0 0 0;
  padding-left: 24px;
  font-size: 12px;
  line-height: 1.55;
  color: var(--el-text-color-secondary);
  word-break: break-word;
}
</style>
