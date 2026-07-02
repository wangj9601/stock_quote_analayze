<template>
  <div class="gms-screening-results space-y-4">
    <el-card class="info-card" shadow="never">
      <template #header><span class="font-semibold">策略说明</span></template>
      <ul class="strategy-conditions text-sm text-gray-700 list-disc pl-5 space-y-1">
        <li>
          <strong>数据来源：</strong>【GMS观察股】为管理端「GMS策略版本」中启用版本下的股票；【我的自选】支持指定用户（管理员）；【全部港股】【全部A股】【全部ETF】与网站端一致；【全部A股】可进一步限定主板、创业板、中小板、科创板或北证。
        </li>
        <li><strong>时间范围：</strong>最近 20 个交易日</li>
        <li><strong>双模块阶梯式评分：</strong></li>
        <li class="ml-2">
          <strong>【均值收敛态】</strong>
          F/Z、|Δ/d|、m₂₀/m 加权；总分≥85 S 级，[70,85) A 级
        </li>
        <li class="ml-2">
          <strong>【动量溢出态】</strong>
          Δ/d₁、d₂₀-d、m₂₀/m 加权；≥90 全速切入，[80,90) 分批买入
        </li>
        <li class="ml-2">左侧买点：均值收敛态 S/A + 粘合 + 地量；右侧买点：动量溢出 + 放量</li>
        <li class="ml-2"><strong>退出：</strong>d₂₀ 跌破 d 或乖离过大（Δ/d₂₀&gt;15%）</li>
      </ul>
    </el-card>

    <el-card shadow="never">
      <template #header><span class="font-semibold">数据来源</span></template>
      <el-radio-group v-model="scope" class="flex flex-wrap gap-4" @change="onScopeChange">
        <el-radio label="cn">全部A股</el-radio>
        <el-radio label="hk">全部港股</el-radio>
        <el-radio label="etf">全部ETF</el-radio>
        <el-radio label="watchlist">我的自选</el-radio>
        <el-radio label="gms_watchlist">GMS观察股</el-radio>
      </el-radio-group>
      <div v-if="scope === 'cn'" class="mt-3">
        <div class="text-xs text-gray-500 mb-1">A股板块（在当日有行情的股票池内按代码段筛选）</div>
        <el-radio-group v-model="cnBoardSegment" class="flex flex-wrap gap-3">
          <el-radio label="ALL">全部A股</el-radio>
          <el-radio label="MAIN">主板</el-radio>
          <el-radio label="CYB">创业板</el-radio>
          <el-radio label="SZ_SME">中小板</el-radio>
          <el-radio label="KCB">科创板</el-radio>
          <el-radio label="BJ">北证</el-radio>
        </el-radio-group>
      </div>
      <div v-if="scope === 'gms_watchlist'" class="mt-3">
        <div class="text-xs text-gray-500 mb-1">观察股市场（来自启用策略版本且状态为 active 的观察股）</div>
        <el-radio-group v-model="gmsWatchlistMarket" class="flex flex-wrap gap-3" @change="onGmsWatchlistMarketChange">
          <el-radio label="all">全部</el-radio>
          <el-radio label="cn">仅A股</el-radio>
          <el-radio label="hk">仅港股</el-radio>
        </el-radio-group>
      </div>
      <div v-if="scope === 'watchlist'" class="mt-3 max-w-md">
        <div class="text-xs text-gray-500 mb-1">自选用户（管理员指定，留空则用当前登录用户对应网站账号）</div>
        <el-select
          v-model="watchlistUserId"
          filterable
          clearable
          placeholder="选择用户（可选）"
          class="w-full"
          @change="onWatchlistUserChange"
        >
          <el-option
            v-for="u in watchlistUsers"
            :key="u.user_id"
            :label="`${u.username} (${u.watchlist_count}只)`"
            :value="u.user_id"
          />
        </el-select>
      </div>
    </el-card>

    <el-card shadow="never">
      <template #header><span class="font-semibold">GMS 策略参数版本</span></template>
      <p class="text-xs text-gray-500 mb-2">仅 <strong>default</strong>（标准版）与 <strong>gms_penalty</strong>（减分版）两个共享版本。</p>
      <el-select v-model="selectedConfigId" placeholder="选择参数版本" class="max-w-md" @change="onConfigChange">
        <el-option
          v-for="c in strategyConfigs"
          :key="c.id"
          :label="configOptionLabel(c)"
          :value="c.id"
        />
      </el-select>
      <div class="mt-2 flex flex-wrap items-center gap-3">
        <el-button size="small" :disabled="!selectedConfigId" @click="() => syncParamsFromServer()">从服务端同步参数</el-button>
        <el-checkbox v-model="paramOverride">临时用下方表单覆盖服务端参数</el-checkbox>
      </div>
      <p class="text-xs text-gray-500 mt-2">默认仅传 <code>config_id</code>，与网站选股页一致；勾选覆盖后才附加下方各字段。</p>
    </el-card>

    <el-card shadow="never">
      <template #header><span class="font-semibold">GMS 策略参数（临时覆盖，可选）</span></template>
      <div class="params-grid">
        <div v-for="row in primaryParamRows" :key="row.k" class="param-row">
          <label class="param-label">{{ row.label }}</label>
          <el-input-number
            v-if="row.type === 'num'"
            :model-value="Number(gmsFormDyn[row.k] ?? 0)"
            class="w-full"
            @update:model-value="(v: number | undefined) => (gmsFormDyn[row.k] = v ?? 0)"
          />
          <el-input
            v-else-if="row.type === 'text'"
            :model-value="String(gmsFormDyn[row.k] ?? '')"
            clearable
            placeholder="留空则按下方数据来源范围"
            class="w-full"
            @update:model-value="(v: string) => (gmsFormDyn[row.k] = v)"
          />
          <el-input
            v-else
            :model-value="String(gmsFormDyn[row.k] ?? '')"
            type="date"
            class="w-full"
            @update:model-value="(v: string) => (gmsFormDyn[row.k] = v)"
          />
          <span v-if="row.hint" class="param-hint">{{ row.hint }}</span>
        </div>
      </div>
      <el-divider />
      <div class="text-sm font-medium mb-2">评分权重（每模块合计建议 100）</div>
      <div class="params-grid">
        <div v-for="row in weightParamRows" :key="row.k" class="param-row">
          <label class="param-label">{{ row.label }}</label>
          <el-input-number
            :model-value="Number(gmsFormDyn[row.k] ?? 0)"
            :min="0"
            :max="100"
            :step="1"
            class="w-full"
            @update:model-value="(v: number | undefined) => (gmsFormDyn[row.k] = v ?? 0)"
          />
          <span v-if="row.hint" class="param-hint">{{ row.hint }}</span>
        </div>
      </div>
      <div class="mt-3 flex items-center gap-2">
        <el-button type="primary" plain @click="saveParams">保存筛选偏好</el-button>
        <span class="text-sm text-gray-500">{{ saveStatus }}</span>
      </div>
    </el-card>

    <el-alert
      v-if="showClickRefreshHint"
      type="info"
      :closable="false"
      show-icon
      class="mb-0"
      title="进入本页不会自动计算信号。设置好数据来源与参数后，请点击「刷新筛选」再执行选股与计算。"
    />

    <div class="flex flex-wrap items-center gap-2">
      <el-button type="primary" :loading="loading" @click="refresh">
        <el-icon class="mr-1"><Refresh /></el-icon>
        刷新筛选
      </el-button>
      <el-button :disabled="!tableRows.length || loading" @click="exportCsv">导出CSV</el-button>
      <el-button :disabled="!tableRows.length || loading" @click="exportExcel">导出Excel</el-button>
      <span v-if="searchDateStr" class="text-sm text-gray-600">筛选时间：{{ searchDateStr }}</span>
    </div>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon closable @close="errorMsg = ''" />

    <div v-loading="loading" class="min-h-[120px]">
      <div class="mb-2 text-sm text-gray-700">
        <template v-if="showClickRefreshHint">
          尚未执行筛选，结果将在点击「刷新筛选」后显示。
        </template>
        <template v-else>
          共找到 <strong>{{ paging?.total ?? tableRows.length }}</strong> 只符合条件的股票
          <span v-if="traceHint" class="text-amber-700 ml-2">{{ traceHint }}</span>
        </template>
      </div>
      <el-pagination
        v-if="paging && paging.enabled && (paging.total_pages ?? 0) > 1"
        v-model:current-page="gmsPage"
        :page-size="GMS_PAGE_SIZE"
        :total="paging.total"
        layout="prev, pager, next, total"
        class="mb-3"
        @current-change="onPageChange"
      />
      <el-table :data="tableRows" stripe border class="gms-table" style="width: 100%" row-key="symbol">
        <template #empty>
          <span class="text-gray-500 text-sm">
            {{ showClickRefreshHint ? '请点击上方「刷新筛选」执行计算' : '暂无数据' }}
          </span>
        </template>
        <el-table-column type="expand">
          <template #default="{ row }">
            <GmsScoreDetailBlock :stock="row" />
          </template>
        </el-table-column>
        <el-table-column label="股票代码" width="100" fixed>
          <template #default="{ row }">
            <el-link type="primary" :href="stockDetailHref(row)" target="_blank" :underline="false">
              {{ row.symbol || row.code }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="股票名称" width="110" show-overflow-tooltip />
        <el-table-column label="信号强度" width="88">
          <template #default="{ row }">
            <span :class="strengthClass(row)">{{ (signalStrength(row) * 100).toFixed(1) }}%</span>
          </template>
        </el-table-column>
        <el-table-column label="买点类型" width="100">
          <template #default="{ row }">
            <span :class="buyTypeClass(row)">{{ row.buy_type || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="风险" width="120">
          <template #default="{ row }">
            <template v-if="riskTags(row).length">
              <el-tooltip v-for="t in riskTags(row)" :key="t.id" :content="t.reason || t.label" placement="top">
                <el-tag :type="riskTagType(t.level)" size="small" class="mr-1 mb-1">{{ t.label || t.id }}</el-tag>
              </el-tooltip>
            </template>
            <span v-else class="text-gray-400">—</span>
          </template>
        </el-table-column>
        <el-table-column label="当前价格" width="92">
          <template #default="{ row }">
            {{ row.current_price != null ? Number(row.current_price).toFixed(2) : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="Δ" width="96">
          <template #default="{ row }">
            {{ row.delta != null ? Number(row.delta).toFixed(4) : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="F" width="72">
          <template #default="{ row }">{{ row.falling_days ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="Z" width="72">
          <template #default="{ row }">{{ row.rising_days ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="d" width="96">
          <template #default="{ row }">
            {{ row.d_ma20 != null ? Number(row.d_ma20).toFixed(2) : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="Δ/d" width="88">
          <template #default="{ row }">
            {{ fmtRatioRelative(row) }}
          </template>
        </el-table-column>
        <el-table-column label="Δ/d₂₀" width="88">
          <template #default="{ row }">{{ fmtPct(row.ratio_d20) }}</template>
        </el-table-column>
        <el-table-column label="Δ/d₁" width="88">
          <template #default="{ row }">{{ fmtPct(row.ratio_d1) }}</template>
        </el-table-column>
        <el-table-column label="F/Z" width="72">
          <template #default="{ row }">
            {{ row.fz_ratio != null ? Number(row.fz_ratio).toFixed(2) : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="当前涨跌幅" width="100">
          <template #default="{ row }">
            <span :class="changeClass(row)">{{ fmtChange(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-link type="primary" :href="gmsTraceHref(row)" target="_blank" :underline="false">信号历史</el-link>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as XLSX from 'xlsx'
import { gmsApiService, type GmsStrategyScreeningResult, type GMSStrategyConfig } from '@/services/gmsApi'
import GmsScoreDetailBlock from './GmsScoreDetailBlock.vue'
import {
  mergeGmsScoreDetail,
  gmsSignalStrength,
  buildGmsScoreDetailCommentText,
  gmsCsvScoreDetailStr,
  type GmsStockRow,
} from '@/utils/gmsScreeningFormat'
import { configParamsToFlatForm } from '@/utils/gmsFlatFormParams'

const PREF_SESSION_KEY = 'adminGmsScreeningPrefs'
const GMS_PAGE_SIZE = 100

const scope = ref<'cn' | 'hk' | 'etf' | 'watchlist' | 'gms_watchlist'>('cn')
/** scope=cn 时传给后端的 cn_board_segment */
const cnBoardSegment = ref<'ALL' | 'MAIN' | 'CYB' | 'SZ_SME' | 'KCB' | 'BJ'>('ALL')
/** scope=gms_watchlist 时传给后端的 gms_watchlist_market */
const gmsWatchlistMarket = ref<'all' | 'cn' | 'hk'>('all')
const watchlistUserId = ref<number | undefined>(undefined)
const watchlistUsers = ref<Array<{ user_id: number; username: string; watchlist_count: number }>>([])
const strategyConfigs = ref<GMSStrategyConfig[]>([])
const selectedConfigId = ref<number | undefined>(undefined)

function configOptionLabel(c: GMSStrategyConfig) {
  const nameLabels: Record<string, string> = { default: '标准版', gms_penalty: '减分版' }
  let label = nameLabels[c.name] || c.name
  const mech = (c as GMSStrategyConfig & { scoring_mechanism_label?: string }).scoring_mechanism_label
  if (mech) label += ` · ${mech}`
  if (c.is_default) label += ' [默认]'
  return label
}
/** 为 true 时请求附带下方表单参数覆盖服务端版本 */
const paramOverride = ref(false)

const gmsForm = reactive({
  /** 非空时请求带 code=，后端仅计算该股（忽略数据来源 scope） */
  single_stock_code: '' as string,
  start_date: '' as string,
  observation_period: 20,
  ratio_d20_max: 0.015,
  volume_ratio_max: 0.8,
  left_buy_min_accumulation: 0,
  volume_ratio_min: 1.5,
  accumulation_fz_min: 1.5,
  balance_ratio_max: 0.01,
  watch_threshold: 60,
  alert_threshold: 90,
  overbought_ratio: 0.15,
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
})
/** 模板内动态 key 绑定用，避免 TS 索引类型报错 */
const gmsFormDyn = gmsForm as Record<string, string | number | undefined>

const primaryParamRows = [
  {
    k: 'single_stock_code' as const,
    label: '限定股票代码（可选）',
    type: 'text' as const,
    hint: '填写则仅对该股选股（请求参数 code），忽略下方「数据来源」范围',
  },
  { k: 'start_date' as const, label: '策略起始交易日期', type: 'date' as const, hint: '留空则取历史行情最近一日' },
  { k: 'observation_period' as const, label: '观察周期（天）', type: 'num' as const, hint: '默认 20（仅本地记录）' },
  { k: 'ratio_d20_max' as const, label: '左侧买点 Δ/d₂₀ 上限', type: 'num' as const, hint: '如 0.015 = 1.5%' },
  { k: 'volume_ratio_max' as const, label: '左侧买点 量比上限', type: 'num' as const, hint: '地量 m₂₀/m 阈值' },
  {
    k: 'left_buy_min_accumulation' as const,
    label: '左侧 蓄势分下限',
    type: 'num' as const,
    hint: '0=关闭；>0 时「左侧」需均值收敛态得分≥此值',
  },
  { k: 'volume_ratio_min' as const, label: '右侧买点 量比下限', type: 'num' as const, hint: '放量' },
  { k: 'accumulation_fz_min' as const, label: '蓄势 F/Z 下限', type: 'num' as const, hint: '' },
  { k: 'balance_ratio_max' as const, label: '平衡 |Δ/d₂₀| 上限', type: 'num' as const, hint: '' },
  { k: 'watch_threshold' as const, label: '重点关注分数', type: 'num' as const, hint: '' },
  { k: 'alert_threshold' as const, label: '动量突变预警分数', type: 'num' as const, hint: '' },
  { k: 'overbought_ratio' as const, label: '乖离过大阈值', type: 'num' as const, hint: '' },
  { k: 'accumulation_s_threshold' as const, label: '均值收敛态 S 级阈值', type: 'num' as const, hint: '' },
  { k: 'accumulation_a_threshold' as const, label: '均值收敛态 A 级阈值', type: 'num' as const, hint: '' },
  { k: 'momentum_full_threshold' as const, label: '动量溢出态全速切入阈值', type: 'num' as const, hint: '' },
  { k: 'momentum_batch_threshold' as const, label: '动量溢出态分批买入阈值', type: 'num' as const, hint: '' },
  { k: 'instant_deviation_stable_days' as const, label: '推力支撑站稳天数', type: 'num' as const, hint: '' },
]

const weightParamRows = [
  { k: 'weight_acc_fz' as const, label: '均值收敛态 时间耗散 F/Z 权重', hint: '默认 30' },
  { k: 'weight_acc_balance' as const, label: '均值收敛态 引力粘合 |Δ/d| 权重', hint: '默认 40' },
  { k: 'weight_acc_volume' as const, label: '均值收敛态 成交量缩 权重', hint: '默认 30' },
  { k: 'weight_mom_ratio_d1' as const, label: '动量溢出态 盈亏反转 Δ/d₁ 权重', hint: '默认 40' },
  { k: 'weight_mom_deviation' as const, label: '动量溢出态 推力支撑 d₂₀-d 权重', hint: '默认 30' },
  { k: 'weight_mom_volume' as const, label: '动量溢出态 攻击强度 m₂₀/m 权重', hint: '默认 30' },
]

/** 为 true 时提示用户须手动点「刷新筛选」；数据来源/自选用户变更后也会重新置为 true 并清空结果 */
const showClickRefreshHint = ref(true)

const loading = ref(false)
const errorMsg = ref('')
const saveStatus = ref('')
const tableRows = ref<any[]>([])
const paging = ref<{ enabled: boolean; page: number; page_size: number; total: number; total_pages: number } | null>(
  null
)
const searchDateStr = ref('')
const traceHint = ref('')
const gmsPage = ref(1)

function riskTags(row: any) {
  const tags = row.risk_tags
  return Array.isArray(tags) ? tags : []
}

function riskTagType(level?: string) {
  if (level === 'danger') return 'danger'
  if (level === 'warn') return 'warning'
  return 'info'
}

async function loadParams() {
  try {
    const pref = await gmsApiService.getGmsScreeningPreferences()
    if (pref.config_id != null) selectedConfigId.value = Number(pref.config_id)
    if (pref.scope) scope.value = pref.scope as typeof scope.value
    if (pref.cn_board_segment) cnBoardSegment.value = pref.cn_board_segment as typeof cnBoardSegment.value
  } catch {
    try {
      const raw = sessionStorage.getItem(PREF_SESSION_KEY)
      if (!raw) return
      const data = JSON.parse(raw) as Record<string, unknown>
      if (data.config_id != null) selectedConfigId.value = Number(data.config_id)
      if (data.scope) scope.value = data.scope as typeof scope.value
    } catch {
      /* ignore */
    }
  }
}

async function saveParams() {
  const prefs = {
    config_id: selectedConfigId.value ?? null,
    scope: scope.value,
    cn_board_segment: cnBoardSegment.value,
    page_size: GMS_PAGE_SIZE,
  }
  try {
    await gmsApiService.putGmsScreeningPreferences(prefs)
    saveStatus.value = '筛选偏好已保存'
    ElMessage.success('GMS 筛选偏好已保存')
  } catch {
    sessionStorage.setItem(PREF_SESSION_KEY, JSON.stringify(prefs))
    saveStatus.value = '已保存到本会话'
    ElMessage.success('筛选偏好已保存（本会话）')
  }
}

function buildSearchParams(includePagination: boolean): URLSearchParams {
  const q = new URLSearchParams()
  q.set('scope', scope.value)
  if (scope.value === 'cn' && cnBoardSegment.value && cnBoardSegment.value !== 'ALL') {
    q.set('cn_board_segment', cnBoardSegment.value)
  }
  if (scope.value === 'watchlist' && watchlistUserId.value != null) {
    q.set('watchlist_user_id', String(watchlistUserId.value))
  }
  if (scope.value === 'gms_watchlist') {
    q.set('gms_watchlist_market', gmsWatchlistMarket.value)
  }
  if (selectedConfigId.value) {
    q.set('config_id', String(selectedConfigId.value))
  }
  const f = gmsForm
  const singleCode = String(f.single_stock_code ?? '').trim()
  if (singleCode) q.set('code', singleCode)
  if (f.start_date) q.set('date', f.start_date)
  if (paramOverride.value) {
    if (f.ratio_d20_max != null) q.set('ratio_d20_max', String(f.ratio_d20_max))
    if (f.volume_ratio_max != null) q.set('volume_ratio_max', String(f.volume_ratio_max))
    if (f.left_buy_min_accumulation != null) q.set('left_buy_min_accumulation', String(f.left_buy_min_accumulation))
    if (f.volume_ratio_min != null) q.set('volume_ratio_min', String(f.volume_ratio_min))
    if (f.accumulation_fz_min != null) q.set('accumulation_fz_min', String(f.accumulation_fz_min))
    if (f.balance_ratio_max != null) q.set('balance_ratio_max', String(f.balance_ratio_max))
    if (f.watch_threshold != null) q.set('watch_threshold', String(f.watch_threshold))
    if (f.alert_threshold != null) q.set('alert_threshold', String(f.alert_threshold))
    if (f.overbought_ratio != null) q.set('overbought_ratio', String(f.overbought_ratio))
    if (f.accumulation_s_threshold != null) q.set('accumulation_s_threshold', String(f.accumulation_s_threshold))
    if (f.accumulation_a_threshold != null) q.set('accumulation_a_threshold', String(f.accumulation_a_threshold))
    if (f.momentum_full_threshold != null) q.set('momentum_full_threshold', String(f.momentum_full_threshold))
    if (f.momentum_batch_threshold != null) q.set('momentum_batch_threshold', String(f.momentum_batch_threshold))
    if (f.instant_deviation_stable_days != null) {
      q.set('instant_deviation_stable_days', String(f.instant_deviation_stable_days))
    }
    if (f.weight_acc_fz != null) q.set('weight_acc_fz', String(f.weight_acc_fz))
    if (f.weight_acc_balance != null) q.set('weight_acc_balance', String(f.weight_acc_balance))
    if (f.weight_acc_volume != null) q.set('weight_acc_volume', String(f.weight_acc_volume))
    if (f.weight_mom_ratio_d1 != null) q.set('weight_mom_ratio_d1', String(f.weight_mom_ratio_d1))
    if (f.weight_mom_deviation != null) q.set('weight_mom_deviation', String(f.weight_mom_deviation))
    if (f.weight_mom_volume != null) q.set('weight_mom_volume', String(f.weight_mom_volume))
  }
  q.set('min_score', '0')
  if (includePagination) {
    q.set('use_pagination', 'true')
    q.set('page', String(gmsPage.value))
    q.set('page_size', String(GMS_PAGE_SIZE))
  } else {
    q.set('use_pagination', 'false')
  }
  return q
}

async function fetchGmsOnce(traceOnly: boolean): Promise<GmsStrategyScreeningResult> {
  const base = buildSearchParams(true)
  base.set('trace_only', traceOnly ? 'true' : 'false')
  return gmsApiService.getGmsStrategyScreening(base)
}

function clearScreeningResults() {
  tableRows.value = []
  paging.value = null
  searchDateStr.value = ''
  traceHint.value = ''
  errorMsg.value = ''
  gmsPage.value = 1
  showClickRefreshHint.value = true
}

async function refresh() {
  loading.value = true
  errorMsg.value = ''
  traceHint.value = ''
  try {
    let res = await fetchGmsOnce(true)
    const meta = res.gms_trace_meta || {}
    if (meta.trace_complete !== true) {
      traceHint.value = '缓存不完整，正在全量计算…'
      res = await fetchGmsOnce(false)
    }
    if (!res.success) {
      errorMsg.value = res.message || '请求失败'
      tableRows.value = []
      paging.value = null
      return
    }
    tableRows.value = Array.isArray(res.data) ? res.data : []
    paging.value = res.paging || null
    if (res.paging?.page != null) gmsPage.value = res.paging.page
    searchDateStr.value = res.search_date || ''
    if (res.message) traceHint.value = res.message
    else traceHint.value = ''
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    errorMsg.value = msg
    tableRows.value = []
    paging.value = null
  } finally {
    loading.value = false
    showClickRefreshHint.value = false
  }
}

function onPageChange() {
  void refresh()
}

function onScopeChange() {
  clearScreeningResults()
}

function onWatchlistUserChange() {
  clearScreeningResults()
}

function onGmsWatchlistMarketChange() {
  clearScreeningResults()
}

function onConfigChange() {
  void syncParamsFromServer(false)
  saveParams()
  clearScreeningResults()
}

async function syncParamsFromServer(showToast = true) {
  const cid = selectedConfigId.value
  if (!cid) return
  try {
    const data = await gmsApiService.getStrategyConfig(cid)
    const flat = configParamsToFlatForm((data.config_params || {}) as Record<string, unknown>)
    Object.assign(gmsForm, flat)
    if (showToast) ElMessage.success(`已同步参数：${data.name || cid}`)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '同步失败')
  }
}

function signalStrength(row: GmsStockRow) {
  const sd = mergeGmsScoreDetail(row)
  return gmsSignalStrength(row, sd)
}

function strengthClass(row: GmsStockRow) {
  const s = signalStrength(row)
  if (s >= 0.8) return 'text-red-600 font-semibold'
  if (s >= 0.6) return 'text-amber-600 font-semibold'
  return 'text-gray-800'
}

function buyTypeClass(row: GmsStockRow) {
  if (row.left_buy_signal) return 'text-blue-600'
  if (row.right_buy_signal) return 'text-emerald-600'
  return ''
}

function fmtPct(v: unknown) {
  if (v != null && typeof v === 'number' && !isNaN(v)) return (v * 100).toFixed(1) + '%'
  return '—'
}

function fmtRatioRelative(row: GmsStockRow) {
  if (row.ratio_relative != null && typeof row.ratio_relative === 'number') {
    return (row.ratio_relative * 100).toFixed(2) + '%'
  }
  return '—'
}

function fmtChange(row: GmsStockRow) {
  const p = row.current_change_percent
  if (p == null || typeof p !== 'number') return '0%'
  const sym = p > 0 ? '+' : ''
  return sym + p.toFixed(2) + '%'
}

function changeClass(row: GmsStockRow) {
  const p = row.current_change_percent
  if (p == null || typeof p !== 'number') return ''
  if (p > 0) return 'text-red-500'
  if (p < 0) return 'text-emerald-600'
  return ''
}

function stockDetailHref(row: any) {
  const c = encodeURIComponent(String(row.symbol || row.code || ''))
  const n = encodeURIComponent(String(row.name || ''))
  return `/stock.html?code=${c}&name=${n}`
}

function gmsTraceHref(row: any) {
  const c = encodeURIComponent(String(row.symbol || row.code || ''))
  const n = encodeURIComponent(String(row.name || ''))
  return `/stock_gms_trace.html?code=${c}&name=${n}`
}

async function loadFullForExport() {
  const q = buildSearchParams(false)
  q.set('trace_only', 'false')
  const res = await gmsApiService.getGmsStrategyScreening(q)
  if (!res.success || !res.data?.length) {
    throw new Error(res.message || '没有可导出的数据')
  }
  return res.data as GmsStockRow[]
}

async function exportCsv() {
  try {
    loading.value = true
    const data = await loadFullForExport()
    const headers = [
      '股票代码',
      '股票名称',
      '信号强度',
      '买点类型',
      '当前价格',
      'Δ (20日位移)',
      'F (下跌天)',
      'Z (上涨天)',
      'd (20日均价)',
      'Δ/d (位移/均价)',
      'Δ/d₂₀',
      'Δ/d₁',
      'F/Z',
      '当前涨跌幅',
      '得分明细',
    ]
    const lines = [headers.join(',')]
    for (const stock of data) {
      const sig = gmsSignalStrength(stock, mergeGmsScoreDetail(stock))
      const row = [
        '\u2060' + String(stock.symbol || stock.code || ''),
        String(stock.name || ''),
        (sig * 100).toFixed(1) + '%',
        String(stock.buy_type || ''),
        stock.current_price != null ? Number(stock.current_price).toFixed(2) : '',
        stock.delta != null ? Number(stock.delta).toFixed(4) : '',
        stock.falling_days != null ? String(stock.falling_days) : '',
        stock.rising_days != null ? String(stock.rising_days) : '',
        stock.d_ma20 != null ? Number(stock.d_ma20).toFixed(2) : '',
        stock.ratio_relative != null ? (Number(stock.ratio_relative) * 100).toFixed(2) + '%' : '',
        stock.ratio_d20 != null ? (Number(stock.ratio_d20) * 100).toFixed(2) + '%' : '',
        stock.ratio_d1 != null ? (Number(stock.ratio_d1) * 100).toFixed(2) + '%' : '',
        stock.fz_ratio != null ? Number(stock.fz_ratio).toFixed(2) : '',
        stock.current_change_percent != null ? Number(stock.current_change_percent).toFixed(2) + '%' : '0%',
        gmsCsvScoreDetailStr(stock),
      ]
      lines.push(row.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(','))
    }
    const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `GMS均值引力动量筛选结果_${new Date().toISOString().split('T')[0]}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
    ElMessage.success('CSV 已导出')
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '导出失败')
  } finally {
    loading.value = false
  }
}

async function exportExcel() {
  try {
    loading.value = true
    const data = await loadFullForExport()
    const headers = [
      '股票代码',
      '股票名称',
      '信号强度',
      '买点类型',
      '当前价格',
      'Δ (20日位移)',
      'F (下跌天)',
      'Z (上涨天)',
      'd (20日均价)',
      'Δ/d (位移/均价)',
      'Δ/d₂₀',
      'Δ/d₁',
      'F/Z',
      '当前涨跌幅',
      '得分明细',
    ]
    const aoa: (string | number)[][] = [headers]
    for (const stock of data) {
      const sig = gmsSignalStrength(stock, mergeGmsScoreDetail(stock))
      const sd = mergeGmsScoreDetail(stock)
      aoa.push([
        '\u2060' + String(stock.symbol || stock.code || ''),
        String(stock.name || ''),
        (sig * 100).toFixed(1) + '%',
        String(stock.buy_type || ''),
        stock.current_price != null ? Number(stock.current_price).toFixed(2) : '',
        stock.delta != null ? Number(stock.delta).toFixed(4) : '',
        stock.falling_days != null ? String(stock.falling_days) : '',
        stock.rising_days != null ? String(stock.rising_days) : '',
        stock.d_ma20 != null ? Number(stock.d_ma20).toFixed(2) : '',
        stock.ratio_relative != null ? (Number(stock.ratio_relative) * 100).toFixed(2) + '%' : '',
        stock.ratio_d20 != null ? (Number(stock.ratio_d20) * 100).toFixed(2) + '%' : '',
        stock.ratio_d1 != null ? (Number(stock.ratio_d1) * 100).toFixed(2) + '%' : '',
        stock.fz_ratio != null ? Number(stock.fz_ratio).toFixed(2) : '',
        stock.current_change_percent != null ? Number(stock.current_change_percent).toFixed(2) + '%' : '0%',
        '点击行首 + 展开',
      ])
      const detailText = buildGmsScoreDetailCommentText(sd)
      const detailRow: string[] = [detailText]
      for (let c = 1; c < headers.length; c++) detailRow.push('')
      aoa.push(detailRow)
    }
    const ws = XLSX.utils.aoa_to_sheet(aoa)
    if (!ws['!rows']) ws['!rows'] = []
    const merges: NonNullable<XLSX.WorkSheet['!merges']> = [...(ws['!merges'] || [])]
    data.forEach((_stock, i) => {
      const dataRowIdx = 1 + i * 2
      const detailRowIdx = 2 + i * 2
      ws['!rows']![dataRowIdx] = { level: 0 }
      ws['!rows']![detailRowIdx] = { level: 1, hidden: true }
      merges.push({ s: { r: detailRowIdx, c: 0 }, e: { r: detailRowIdx, c: 14 } })
    })
    ws['!merges'] = merges
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'GMS选股结果')
    XLSX.writeFile(wb, `GMS均值引力动量筛选结果_${new Date().toISOString().split('T')[0]}.xlsx`)
    ElMessage.success('Excel 已导出（与网站端一致：明细行可展开）')
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '导出失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadParams()
  try {
    strategyConfigs.value = await gmsApiService.listStrategyConfigs(true)
    if (selectedConfigId.value == null) {
      const def = strategyConfigs.value.find((c) => c.is_default)
      if (def) selectedConfigId.value = def.id
    }
    if (selectedConfigId.value) {
      await syncParamsFromServer(false)
    }
  } catch {
    strategyConfigs.value = []
  }
  try {
    watchlistUsers.value = await gmsApiService.getWatchlistUsers()
  } catch {
    watchlistUsers.value = []
  }
})
</script>

<style scoped lang="postcss">
.params-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px 16px;
}
.param-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.param-label {
  font-size: 13px;
  color: #374151;
}
.param-hint {
  font-size: 12px;
  color: #9ca3af;
}
.gms-table :deep(.el-table__cell) {
  font-size: 12px;
}
.info-card :deep(.el-card__body) {
  padding-top: 8px;
}
</style>
