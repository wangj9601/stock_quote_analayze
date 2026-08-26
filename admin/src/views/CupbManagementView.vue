<template>
  <div class="cupb-management">
    <div class="page-header">
      <h1 class="page-title">杯底形态策略（CUPB）管理</h1>
      <p class="page-subtitle">参数版本 · 按行业/概念/个股试算与预计算 · 信号结果</p>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="策略配置" name="config">
        <div class="toolbar">
          <el-button type="primary" @click="loadConfigs">刷新</el-button>
          <el-button @click="showCreate = true">新建版本</el-button>
        </div>
        <el-table :data="configs" stripe v-loading="loadingConfigs">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="name" label="名称" width="160" />
          <el-table-column prop="description" label="说明" />
          <el-table-column label="默认" width="80">
            <template #default="{ row }">
              <el-tag v-if="row.is_default" type="success">是</el-tag>
              <el-button v-else link type="primary" @click="onSetDefault(row.id)">设为默认</el-button>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="80">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '是' : '否' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEdit(row)">编辑 JSON</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="分析试算 / 预计算" name="analyze">
        <el-form label-width="110px" class="scope-form">
          <el-form-item label="基准日">
            <el-date-picker
              v-model="scopeForm.trade_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="留空=最新交易日"
              style="width: 220px"
            />
          </el-form-item>
          <el-form-item label="配置版本">
            <el-select v-model="scopeForm.config_id" clearable placeholder="默认配置" style="width: 280px">
              <el-option
                v-for="c in configs"
                :key="c.id"
                :label="`${c.name} (#${c.id})${c.is_default ? ' · 默认' : ''}`"
                :value="c.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="状态过滤">
            <el-select v-model="scopeForm.status_filter" style="width: 220px">
              <el-option label="全部（forming+confirmed）" value="both" />
              <el-option label="仅形成中 forming" value="forming" />
              <el-option label="仅已确认 confirmed" value="confirmed" />
            </el-select>
          </el-form-item>
          <el-form-item label="价格口径">
            <el-switch
              v-model="scopeForm.use_qfq"
              active-text="前复权"
              inactive-text="不复权"
            />
            <span class="hint">前复权与形态识别工具默认口径一致；与不复权结果分别缓存</span>
          </el-form-item>
          <el-form-item label="股票池">
            <el-select v-model="scopeForm.stock_pool_mode" style="width: 220px" @change="onPoolModeChange">
              <el-option label="行业板块" value="industry_board" />
              <el-option label="概念板块" value="concept_board" />
              <el-option label="个股" value="stocks" />
              <el-option label="全市场" value="market" />
            </el-select>
          </el-form-item>

          <el-form-item v-if="scopeForm.stock_pool_mode === 'industry_board'" label="行业板块" required>
            <BoardPickerDialog v-model="selectedIndustryBoardCodes" board-type="industry" />
          </el-form-item>

          <el-form-item v-if="scopeForm.stock_pool_mode === 'concept_board'" label="概念板块" required>
            <BoardPickerDialog v-model="selectedConceptBoardCodes" board-type="concept" />
          </el-form-item>

          <el-form-item v-if="scopeForm.stock_pool_mode === 'stocks'" label="个股代码" required>
            <el-input
              v-model="stockCodesText"
              type="textarea"
              :rows="3"
              placeholder="多个代码用逗号、空格或换行分隔，如 600519,000001"
            />
          </el-form-item>

          <el-form-item
            v-if="showCnBoardSegments"
            label="A股板块"
          >
            <el-checkbox-group v-model="selectedCnBoardSegments" class="cn-board-group">
              <el-checkbox label="MAIN">主板</el-checkbox>
              <el-checkbox label="CYB">创业板</el-checkbox>
              <el-checkbox label="SZ_SME">中小板</el-checkbox>
              <el-checkbox label="KCB">科创板</el-checkbox>
              <el-checkbox label="BJ">北证</el-checkbox>
            </el-checkbox-group>
            <div class="hint block-hint">可多选；不选时默认沪深主板/创业/科创/中小板，自动排除 4/8 打头无效代码及北证</div>
          </el-form-item>

          <el-form-item v-if="scopeForm.stock_pool_mode === 'market'" label="市场范围">
            <el-checkbox-group v-model="selectedMarketScopes">
              <el-checkbox label="CN">A股</el-checkbox>
              <el-checkbox label="HK">港股</el-checkbox>
            </el-checkbox-group>
          </el-form-item>

          <el-form-item v-if="scopeForm.stock_pool_mode === 'market'" label="提示">
            <span class="hint">全市场扫描较慢，建议先用板块/个股试算；A股默认过滤 4/8 打头无效代码</span>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" :loading="trialing" @click="onTrial">试算（利旧入库）</el-button>
            <el-button type="danger" :loading="forcing" @click="onForce">强制计算</el-button>
            <el-button type="warning" :loading="precomputing" @click="onPrecompute">写入预计算</el-button>
            <span class="hint">试算优先复用已入库信号；强制计算忽略缓存并全量重算入库</span>
          </el-form-item>
        </el-form>

        <div v-if="trialMeta" class="meta-line">
          日期 {{ trialMeta.trade_date }} · 扫描 {{ trialMeta.screened }} · 命中 {{ trialMeta.hit_count }}
          <span v-if="trialMeta.reused != null"> · 利旧 {{ trialMeta.reused }}</span>
          <span v-if="trialMeta.computed != null"> · 新算 {{ trialMeta.computed }}</span>
          <span v-if="trialMeta.saved != null"> · 入库 {{ trialMeta.saved }}</span>
          <span v-if="trialMeta.force"> · 强制</span>
          <span v-if="trialMeta.price_adjust"> · {{ trialMeta.price_adjust === 'qfq' ? '前复权' : '不复权' }}</span>
          <span v-if="trialMeta.scope_meta"> · 模式 {{ trialMeta.scope_meta.stock_pool_mode }}</span>
        </div>
        <CupbGradeVolumeRulesPanel />
        <div class="cupb-table-wrap">
          <el-table
            class="cupb-table"
            :data="trialItems"
            stripe
            border
            v-loading="trialing"
            max-height="480"
            style="width: 100%"
            table-layout="fixed"
          >
            <el-table-column prop="code" label="代码" width="88" />
            <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="104">
              <template #default="{ row }">
                <el-tag :type="row.status === 'confirmed' ? 'success' : 'warning'" size="small">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="曾确认" width="80" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.ever_confirmed" type="success" size="small">是</el-tag>
                <el-tag v-else type="info" size="small">否</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="first_confirm_date" label="历史确认日" width="112" />
            <el-table-column prop="grade" width="88" align="center">
              <template #header>
                <span class="col-header">
                  等级
                  <el-tooltip placement="top" effect="light" :show-after="200">
                    <template #content>
                      <div class="col-tip">A：量价≥3 且非延长/深杯受限<br />B：量价 1～2<br />C：延长/深杯或量价 0<br />详见上方判定规则</div>
                    </template>
                    <el-icon class="col-help"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <template #default="{ row }">
                <el-tag v-if="row.grade" :type="gradeTagType(row.grade)" size="small">{{ row.grade }}</el-tag>
                <span v-else>—</span>
              </template>
            </el-table-column>
            <el-table-column prop="volume_score" width="88" align="center">
              <template #header>
                <span class="col-header">
                  量价
                  <el-tooltip placement="top" effect="light" :show-after="200">
                    <template #content>
                      <div class="col-tip">0～4：四项量价检查通过数<br />悬停单元格可看各项明细</div>
                    </template>
                    <el-icon class="col-help"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <template #default="{ row }">
                <el-tooltip
                  v-if="volumeFlagSummary(row)"
                  placement="top"
                  effect="light"
                  :show-after="200"
                >
                  <template #content>
                    <div class="col-tip col-tip-pre">{{ volumeFlagSummary(row) }}</div>
                  </template>
                  <span class="metric-val">{{ formatVolumeScore(row.volume_score) }}</span>
                </el-tooltip>
                <span v-else>{{ formatVolumeScore(row.volume_score) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="board_labels" label="所属板块" width="108" show-overflow-tooltip />
            <el-table-column prop="last_close" label="收盘" width="80" align="right" />
            <el-table-column prop="left_rim_price" label="左沿" width="80" align="right" />
            <el-table-column prop="cup_bottom_price" label="杯底" width="80" align="right" />
            <el-table-column prop="right_rim_price" label="右沿" width="80" align="right" />
            <el-table-column prop="handle_low_price" label="柄低" width="80" align="right" />
            <el-table-column prop="rim" label="杯口" width="80" align="right" />
            <el-table-column prop="cup_depth_pct" label="杯深%" width="80" align="right" />
            <el-table-column prop="handle_retrace_pct" label="柄回撤%" width="88" align="right" />
            <el-table-column prop="left_rim_date" label="左沿日" width="112" />
            <el-table-column prop="cup_bottom_date" label="杯底日" width="112" />
            <el-table-column prop="right_rim_date" label="右沿日" width="112" />
            <el-table-column prop="handle_low_date" label="柄低日" width="112" />
            <el-table-column prop="confirm_date" label="确认日" min-width="112" />
          </el-table>
        </div>
        <div class="toolbar" style="margin-top: 8px">
          <el-button :disabled="!trialItems.length" @click="exportTrialCsv">导出试算 CSV</el-button>
        </div>
      </el-tab-pane>

      <el-tab-pane label="信号结果" name="signals">
        <div class="toolbar">
          <el-date-picker
            v-model="signalQuery.trade_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="交易日"
          />
          <el-select v-model="signalQuery.config_id" clearable placeholder="配置" style="width: 200px">
            <el-option
              v-for="c in configs"
              :key="c.id"
              :label="`${c.name} (#${c.id})`"
              :value="c.id"
            />
          </el-select>
          <el-select v-model="signalQuery.status" clearable placeholder="状态" style="width: 140px">
            <el-option label="forming" value="forming" />
            <el-option label="confirmed" value="confirmed" />
          </el-select>
          <el-input v-model="signalQuery.code" clearable placeholder="代码" style="width: 120px" />
          <el-button type="primary" :loading="loadingSignals" @click="loadSignals">查询</el-button>
          <el-button :disabled="!signalItems.length" @click="exportSignalsCsv">导出 CSV</el-button>
        </div>
        <div class="meta-line">共 {{ signalTotal }} 条</div>
        <CupbGradeVolumeRulesPanel />
        <div class="cupb-table-wrap">
          <el-table
            class="cupb-table"
            :data="signalItems"
            stripe
            border
            v-loading="loadingSignals"
            max-height="520"
            style="width: 100%"
            table-layout="fixed"
          >
            <el-table-column prop="code" label="代码" width="88" />
            <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="104" />
            <el-table-column label="曾确认" width="80" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.ever_confirmed" type="success" size="small">是</el-tag>
                <el-tag v-else type="info" size="small">否</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="first_confirm_date" label="历史确认日" width="112" />
            <el-table-column prop="grade" width="88" align="center">
              <template #header>
                <span class="col-header">
                  等级
                  <el-tooltip placement="top" effect="light" :show-after="200">
                    <template #content>
                      <div class="col-tip">A：量价≥3 且非延长/深杯受限<br />B：量价 1～2<br />C：延长/深杯或量价 0<br />详见上方判定规则</div>
                    </template>
                    <el-icon class="col-help"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <template #default="{ row }">
                <el-tag v-if="row.grade" :type="gradeTagType(row.grade)" size="small">{{ row.grade }}</el-tag>
                <span v-else>—</span>
              </template>
            </el-table-column>
            <el-table-column prop="volume_score" width="88" align="center">
              <template #header>
                <span class="col-header">
                  量价
                  <el-tooltip placement="top" effect="light" :show-after="200">
                    <template #content>
                      <div class="col-tip">0～4：四项量价检查通过数<br />悬停单元格可看各项明细</div>
                    </template>
                    <el-icon class="col-help"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <template #default="{ row }">
                <el-tooltip
                  v-if="volumeFlagSummary(row)"
                  placement="top"
                  effect="light"
                  :show-after="200"
                >
                  <template #content>
                    <div class="col-tip col-tip-pre">{{ volumeFlagSummary(row) }}</div>
                  </template>
                  <span class="metric-val">{{ formatVolumeScore(row.volume_score) }}</span>
                </el-tooltip>
                <span v-else>{{ formatVolumeScore(row.volume_score) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="board_labels" label="所属板块" width="108" show-overflow-tooltip />
            <el-table-column prop="last_close" label="收盘" width="80" align="right" />
            <el-table-column prop="left_rim_price" label="左沿" width="80" align="right" />
            <el-table-column prop="cup_bottom_price" label="杯底" width="80" align="right" />
            <el-table-column prop="right_rim_price" label="右沿" width="80" align="right" />
            <el-table-column prop="handle_low_price" label="柄低" width="80" align="right" />
            <el-table-column prop="rim" label="杯口" width="80" align="right" />
            <el-table-column prop="cup_depth_pct" label="杯深%" width="80" align="right" />
            <el-table-column prop="handle_retrace_pct" label="柄回撤%" width="88" align="right" />
            <el-table-column prop="left_rim_date" label="左沿日" width="112" />
            <el-table-column prop="cup_bottom_date" label="杯底日" width="112" />
            <el-table-column prop="right_rim_date" label="右沿日" width="112" />
            <el-table-column prop="handle_low_date" label="柄低日" width="112" />
            <el-table-column prop="confirm_date" label="确认日" min-width="112" />
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="showCreate" title="新建配置版本" width="640px">
      <el-form label-width="100px">
        <el-form-item label="名称"><el-input v-model="createForm.name" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="createForm.description" /></el-form-item>
        <el-form-item label="设为默认"><el-switch v-model="createForm.set_default" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="onCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showEdit" title="编辑 config_params" width="720px">
      <el-input v-model="editJson" type="textarea" :rows="18" />
      <template #footer>
        <el-button @click="showEdit = false">取消</el-button>
        <el-button type="primary" @click="onSaveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import cupbApi, { type CupbScopeBody } from '@/services/cupbApi'
import BoardPickerDialog from '@/components/common/BoardPickerDialog.vue'
import CupbGradeVolumeRulesPanel from '@/components/cupb/CupbGradeVolumeRulesPanel.vue'

const VOLUME_FLAG_LABELS: Record<string, string> = {
  bottom_shrink: '杯底缩量',
  right_expand: '右侧放量',
  handle_shrink: '柄部缩量',
  breakout_expand: '突破放量',
}

function gradeTagType(grade: string): 'success' | 'primary' | 'warning' | 'info' | 'danger' {
  const g = String(grade || '').toUpperCase()
  if (g === 'A') return 'success'
  if (g === 'B') return 'primary'
  if (g === 'C') return 'warning'
  return 'info'
}

function formatVolumeScore(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—'
  return String(v)
}

function volumeFlagSummary(row: any): string {
  const flags = row?.detail?.volume_flags
  if (!flags || typeof flags !== 'object') return ''
  return Object.entries(VOLUME_FLAG_LABELS)
    .map(([key, label]) => `${label}：${flags[key] ? '通过' : '未过'}`)
    .join('\n')
}

const activeTab = ref('config')
const configs = ref<any[]>([])
const loadingConfigs = ref(false)
const showCreate = ref(false)
const showEdit = ref(false)
const editId = ref<number | null>(null)
const editJson = ref('')
const createForm = reactive({ name: '', description: '', set_default: false })

const scopeForm = reactive({
  trade_date: '',
  config_id: undefined as number | undefined,
  status_filter: 'both',
  use_qfq: false,
  stock_pool_mode: 'stocks' as CupbScopeBody['stock_pool_mode'],
})
const stockCodesText = ref('')
const selectedIndustryBoardCodes = ref<string[]>([])
const selectedConceptBoardCodes = ref<string[]>([])
const selectedMarketScopes = ref<Array<'CN' | 'HK'>>(['CN'])
const selectedCnBoardSegments = ref<string[]>([])

const showCnBoardSegments = computed(() => {
  const mode = scopeForm.stock_pool_mode
  if (mode === 'market') return selectedMarketScopes.value.includes('CN')
  return mode === 'industry_board' || mode === 'concept_board' || mode === 'stocks'
})

const trialing = ref(false)
const forcing = ref(false)
const precomputing = ref(false)
const trialItems = ref<any[]>([])
const trialMeta = ref<any>(null)

const signalQuery = reactive({
  trade_date: new Date().toISOString().slice(0, 10),
  config_id: undefined as number | undefined,
  status: '' as string,
  code: '',
})
const signalItems = ref<any[]>([])
const signalTotal = ref(0)
const loadingSignals = ref(false)

function parseStockCodes(text: string): string[] {
  return text
    .split(/[\s,，;；\n]+/)
    .map((s) => s.trim())
    .filter(Boolean)
}

function sortByConfirmDateDesc(rows: any[]): any[] {
  return [...rows].sort((a, b) => {
    const sa = a?.status === 'confirmed' ? 0 : 1
    const sb = b?.status === 'confirmed' ? 0 : 1
    if (sa !== sb) return sa - sb
    const da = String(a?.confirm_date || a?.right_rim_date || '')
    const db = String(b?.confirm_date || b?.right_rim_date || '')
    if (da !== db) return db.localeCompare(da)
    return String(a?.code || '').localeCompare(String(b?.code || ''))
  })
}

function buildScopeBody(): CupbScopeBody {
  const body: CupbScopeBody = {
    stock_pool_mode: scopeForm.stock_pool_mode,
    status_filter: scopeForm.status_filter,
  }
  if (scopeForm.trade_date) body.trade_date = scopeForm.trade_date
  if (scopeForm.config_id) body.config_id = scopeForm.config_id
  if (scopeForm.stock_pool_mode === 'industry_board') {
    body.industry_board_codes = [...selectedIndustryBoardCodes.value]
  } else if (scopeForm.stock_pool_mode === 'concept_board') {
    body.concept_board_codes = [...selectedConceptBoardCodes.value]
  } else if (scopeForm.stock_pool_mode === 'stocks') {
    body.stock_codes = parseStockCodes(stockCodesText.value)
  } else if (scopeForm.stock_pool_mode === 'market') {
    body.market_scopes = [...selectedMarketScopes.value]
  }
  if (showCnBoardSegments.value && selectedCnBoardSegments.value.length) {
    body.cn_board_segments = [...selectedCnBoardSegments.value]
  }
  body.price_adjust = scopeForm.use_qfq ? 'qfq' : 'none'
  return body
}

function onPoolModeChange() {
  if (scopeForm.stock_pool_mode === 'market' && !selectedMarketScopes.value.length) {
    selectedMarketScopes.value = ['CN']
  }
}

async function loadConfigs() {
  loadingConfigs.value = true
  try {
    const data = await cupbApi.listConfigs()
    configs.value = data.items || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e.message || '加载配置失败')
  } finally {
    loadingConfigs.value = false
  }
}

async function onCreate() {
  try {
    await cupbApi.createConfig({ ...createForm })
    showCreate.value = false
    createForm.name = ''
    createForm.description = ''
    createForm.set_default = false
    ElMessage.success('已创建')
    await loadConfigs()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e.message)
  }
}

function openEdit(row: any) {
  editId.value = row.id
  editJson.value = JSON.stringify(row.config_params || {}, null, 2)
  showEdit.value = true
}

async function onSaveEdit() {
  if (editId.value == null) return
  try {
    const params = JSON.parse(editJson.value)
    await cupbApi.updateConfig(editId.value, { config_params: params })
    showEdit.value = false
    ElMessage.success('已保存')
    await loadConfigs()
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  }
}

async function onSetDefault(id: number) {
  await cupbApi.setDefault(id)
  ElMessage.success('已设为默认')
  await loadConfigs()
}

async function runTrial(force: boolean) {
  if (scopeForm.stock_pool_mode === 'market' && !selectedMarketScopes.value.length) {
    ElMessage.warning('全市场请至少选择 A股 或 港股')
    return
  }
  const loading = force ? forcing : trialing
  loading.value = true
  try {
    const data = await cupbApi.trial({ ...buildScopeBody(), persist: true, force })
    trialItems.value = sortByConfirmDateDesc(data.items || [])
    trialMeta.value = data
    const reused = data.reused ?? 0
    const saved = data.saved ?? 0
    ElMessage.success(
      force
        ? `强制计算完成，命中 ${data.hit_count ?? trialItems.value.length}，入库 ${saved}`
        : `试算完成，命中 ${data.hit_count ?? trialItems.value.length}（利旧 ${reused}，入库 ${saved}）`
    )
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e.message || (force ? '强制计算失败' : '试算失败'))
  } finally {
    loading.value = false
  }
}

async function onTrial() {
  await runTrial(false)
}

async function onForce() {
  await runTrial(true)
}

async function onPrecompute() {
  precomputing.value = true
  try {
    const data = await cupbApi.triggerPrecompute({ ...buildScopeBody(), force: true })
    ElMessage.success(
      `预计算完成 date=${data.trade_date ?? '-'} screened=${data.screened ?? '-'} hit=${data.hit_count ?? '-'} saved=${data.saved ?? '-'}`
    )
    if (data.trade_date) signalQuery.trade_date = data.trade_date
    activeTab.value = 'signals'
    await loadSignals()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e.message || '预计算失败')
  } finally {
    precomputing.value = false
  }
}

async function loadSignals() {
  if (!signalQuery.trade_date) {
    ElMessage.warning('请选择交易日')
    return
  }
  loadingSignals.value = true
  try {
    const data = await cupbApi.listSignals({
      trade_date: signalQuery.trade_date,
      config_id: signalQuery.config_id,
      status: signalQuery.status || undefined,
      code: signalQuery.code || undefined,
      limit: 500,
    })
    signalItems.value = sortByConfirmDateDesc(data.items || [])
    signalTotal.value = data.total ?? signalItems.value.length
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e.message || '查询失败')
  } finally {
    loadingSignals.value = false
  }
}

const CSV_COLS = [
  'code',
  'name',
  'status',
  'ever_confirmed',
  'first_confirm_date',
  'grade',
  'volume_score',
  'board_labels',
  'price_adjust',
  'last_close',
  'left_rim_price',
  'cup_bottom_price',
  'right_rim_price',
  'handle_low_price',
  'rim',
  'cup_depth_pct',
  'handle_retrace_pct',
  'left_rim_date',
  'cup_bottom_date',
  'right_rim_date',
  'handle_low_date',
  'confirm_date',
]

function exportCsv(filename: string, rows: any[]) {
  if (!rows.length) return
  const lines = [CSV_COLS.join(',')]
  for (const r of rows) {
    lines.push(
      CSV_COLS.map((c) => {
        const v = r[c] == null ? '' : String(r[c])
        return `"${v.replace(/"/g, '""')}"`
      }).join(',')
    )
  }
  const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function exportTrialCsv() {
  exportCsv(`cupb_trial_${trialMeta.value?.trade_date || 'export'}.csv`, trialItems.value)
}

function exportSignalsCsv() {
  exportCsv(`cupb_signals_${signalQuery.trade_date}.csv`, signalItems.value)
}

onMounted(() => {
  loadConfigs()
})
</script>

<style scoped>
.cupb-management { padding: 16px; width: 100%; box-sizing: border-box; }
.page-header { margin-bottom: 16px; }
.page-title { margin: 0; font-size: 22px; }
.page-subtitle { margin: 4px 0 0; color: #666; }
.toolbar { margin-bottom: 12px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.scope-form { max-width: 960px; margin-bottom: 12px; }
.hint { margin-left: 8px; color: #64748b; font-size: 12px; }
.block-hint { display: block; margin: 6px 0 0; margin-left: 0; }
.cn-board-group { display: flex; flex-wrap: wrap; gap: 8px 16px; }
.meta-line { margin: 0 0 8px; color: #64748b; font-size: 13px; }
.w-full { width: 100%; }
.cupb-table-wrap { width: 100%; min-width: 0; }
.cupb-table { width: 100% !important; }
.cupb-table :deep(.el-table__header),
.cupb-table :deep(.el-table__body) { width: 100% !important; }
.cupb-table :deep(.cell) { padding-left: 8px; padding-right: 8px; }
.col-header {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.col-help {
  font-size: 14px;
  color: #94a3b8;
  cursor: help;
  vertical-align: middle;
}
.col-help:hover {
  color: #3b82f6;
}
.col-tip {
  font-size: 12px;
  line-height: 1.5;
  max-width: 280px;
}
.col-tip-pre {
  white-space: pre-line;
}
.metric-val {
  cursor: help;
  border-bottom: 1px dashed #cbd5e1;
}
</style>
