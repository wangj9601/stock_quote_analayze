<template>
  <div class="lds-management">
    <div class="page-header">
      <h1 class="page-title">龙头战法（LDS）管理</h1>
      <p class="page-subtitle">市场总龙头 + 板块龙头 · 带动性三维 · 右侧 watch_ready · 按行业/概念/个股试算与预计算</p>
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
          <el-form-item label="股票池">
            <el-select v-model="scopeForm.stock_pool_mode" style="width: 220px" @change="onPoolModeChange">
              <el-option label="行业板块" value="industry_board" />
              <el-option label="概念板块" value="concept_board" />
              <el-option label="个股" value="stocks" />
              <el-option label="全市场" value="market" />
            </el-select>
          </el-form-item>

          <el-form-item v-if="scopeForm.stock_pool_mode === 'industry_board'" label="行业板块" required>
            <el-select
              v-model="selectedIndustryBoardCodes"
              multiple
              filterable
              remote
              :remote-method="searchIndustryBoards"
              :loading="industryBoardLoading"
              placeholder="搜索并选择行业板块"
              class="w-full"
            >
              <el-option
                v-for="b in industryBoardOptions"
                :key="b.board_code"
                :label="`${b.board_name}（${b.board_code}）`"
                :value="b.board_code"
              />
            </el-select>
          </el-form-item>

          <el-form-item v-if="scopeForm.stock_pool_mode === 'concept_board'" label="概念板块" required>
            <el-select
              v-model="selectedConceptBoardCodes"
              multiple
              filterable
              remote
              :remote-method="searchConceptBoards"
              :loading="conceptBoardLoading"
              placeholder="搜索并选择概念板块"
              class="w-full"
            >
              <el-option
                v-for="b in conceptBoardOptions"
                :key="b.board_code"
                :label="`${b.board_name}（${b.board_code}）`"
                :value="b.board_code"
              />
            </el-select>
          </el-form-item>

          <el-form-item v-if="scopeForm.stock_pool_mode === 'stocks'" label="个股代码" required>
            <el-input
              v-model="stockCodesText"
              type="textarea"
              :rows="3"
              placeholder="多个代码用逗号、空格或换行分隔，如 600519,000001"
            />
          </el-form-item>

          <el-form-item v-if="scopeForm.stock_pool_mode === 'market'" label="提示">
            <span class="hint">全市场无上限，扫描较慢，建议先用板块/个股试算</span>
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
        </div>
        <div class="lds-table-wrap">
          <el-table
            class="lds-table"
            :data="trialItems"
            stripe
            border
            v-loading="trialing"
            style="width: 100%"
            table-layout="fixed"
          >
            <el-table-column prop="code" label="代码" width="88" />
            <el-table-column prop="name" label="名称" min-width="100" show-overflow-tooltip />
            <el-table-column prop="role" label="角色" width="120" />
            <el-table-column prop="board_name" label="板块" min-width="100" show-overflow-tooltip />
            <el-table-column prop="identity_score" label="身份分" width="88" align="right">
              <template #default="{ row }">{{ fmtNum(row.identity_score) }}</template>
            </el-table-column>
            <el-table-column prop="drive_score" label="带动分" width="88" align="right">
              <template #default="{ row }">{{ fmtNum(row.drive_score) }}</template>
            </el-table-column>
            <el-table-column prop="watch_ready" label="右侧" width="72">
              <template #default="{ row }">{{ row.watch_ready ? '是' : '否' }}</template>
            </el-table-column>
            <el-table-column prop="board_count" label="连板" width="64" align="right" />
            <el-table-column prop="same_as_height" label="最高板" width="72">
              <template #default="{ row }">{{ row.same_as_height ? '是' : '' }}</template>
            </el-table-column>
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
          <el-input v-model="signalQuery.code" clearable placeholder="代码" style="width: 120px" />
          <el-button type="primary" :loading="loadingSignals" @click="loadSignals">查询</el-button>
          <el-button :disabled="!signalItems.length" @click="exportSignalsCsv">导出 CSV</el-button>
        </div>
        <div class="meta-line">共 {{ signalTotal }} 条</div>
        <div class="lds-table-wrap">
          <el-table
            class="lds-table"
            :data="signalItems"
            stripe
            border
            v-loading="loadingSignals"
            style="width: 100%"
            table-layout="fixed"
          >
            <el-table-column prop="code" label="代码" width="88" />
            <el-table-column prop="name" label="名称" min-width="100" show-overflow-tooltip />
            <el-table-column prop="role" label="角色" width="120" />
            <el-table-column prop="board_name" label="板块" min-width="100" show-overflow-tooltip />
            <el-table-column prop="identity_score" label="身份分" width="88" align="right">
              <template #default="{ row }">{{ fmtNum(row.identity_score) }}</template>
            </el-table-column>
            <el-table-column prop="drive_score" label="带动分" width="88" align="right">
              <template #default="{ row }">{{ fmtNum(row.drive_score) }}</template>
            </el-table-column>
            <el-table-column prop="watch_ready" label="右侧" width="72">
              <template #default="{ row }">{{ row.watch_ready ? '是' : '否' }}</template>
            </el-table-column>
            <el-table-column prop="board_count" label="连板" width="64" align="right" />
            <el-table-column prop="same_as_height" label="最高板" width="72">
              <template #default="{ row }">{{ row.same_as_height ? '是' : '' }}</template>
            </el-table-column>
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
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { confirmStrategyJob } from '@/utils/confirmDanger'
import ldsApi, { type LdsScopeBody } from '@/services/ldsApi'
import { boardConstituentsService, type BoardSummary } from '@/services/boardConstituents.service'

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
  stock_pool_mode: 'stocks' as LdsScopeBody['stock_pool_mode'],
})
const stockCodesText = ref('')
const selectedIndustryBoardCodes = ref<string[]>([])
const selectedConceptBoardCodes = ref<string[]>([])
const industryBoardOptions = ref<BoardSummary[]>([])
const conceptBoardOptions = ref<BoardSummary[]>([])
const industryBoardLoading = ref(false)
const conceptBoardLoading = ref(false)

const trialing = ref(false)
const forcing = ref(false)
const precomputing = ref(false)
const trialItems = ref<any[]>([])
const trialMeta = ref<any>(null)

const signalQuery = reactive({
  trade_date: new Date().toISOString().slice(0, 10),
  config_id: undefined as number | undefined,
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

function sortByIdentityDesc(rows: any[]): any[] {
  return [...rows].sort((a, b) => {
    const sa = Number(a?.identity_score || 0)
    const sb = Number(b?.identity_score || 0)
    if (sa !== sb) return sb - sa
    return String(a?.code || '').localeCompare(String(b?.code || ''))
  })
}

function fmtNum(v: unknown): string {
  if (v == null || v === '') return '-'
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : '-'
}

function buildScopeBody(): LdsScopeBody {
  const body: LdsScopeBody = {
    stock_pool_mode: scopeForm.stock_pool_mode,
  }
  if (scopeForm.trade_date) body.trade_date = scopeForm.trade_date
  if (scopeForm.config_id) body.config_id = scopeForm.config_id
  if (scopeForm.stock_pool_mode === 'industry_board') {
    body.industry_board_codes = [...selectedIndustryBoardCodes.value]
  } else if (scopeForm.stock_pool_mode === 'concept_board') {
    body.concept_board_codes = [...selectedConceptBoardCodes.value]
  } else if (scopeForm.stock_pool_mode === 'stocks') {
    body.stock_codes = parseStockCodes(stockCodesText.value)
  }
  return body
}

function onPoolModeChange() {
  if (scopeForm.stock_pool_mode === 'industry_board') void searchIndustryBoards('')
  if (scopeForm.stock_pool_mode === 'concept_board') void searchConceptBoards('')
}

async function searchIndustryBoards(keyword = '') {
  industryBoardLoading.value = true
  try {
    const res = await boardConstituentsService.listBoards({
      boardType: 'industry',
      keyword: keyword.trim() || undefined,
      page: 1,
      pageSize: 80,
    })
    industryBoardOptions.value = res.data || []
  } catch {
    industryBoardOptions.value = []
  } finally {
    industryBoardLoading.value = false
  }
}

async function searchConceptBoards(keyword = '') {
  conceptBoardLoading.value = true
  try {
    const res = await boardConstituentsService.listBoards({
      boardType: 'concept',
      keyword: keyword.trim() || undefined,
      page: 1,
      pageSize: 80,
    })
    conceptBoardOptions.value = res.data || []
  } catch {
    conceptBoardOptions.value = []
  } finally {
    conceptBoardLoading.value = false
  }
}

async function loadConfigs() {
  loadingConfigs.value = true
  try {
    const data = await ldsApi.listConfigs()
    configs.value = data.items || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e.message || '加载配置失败')
  } finally {
    loadingConfigs.value = false
  }
}

async function onCreate() {
  try {
    await ldsApi.createConfig({ ...createForm })
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
    await ldsApi.updateConfig(editId.value, { config_params: params })
    showEdit.value = false
    ElMessage.success('已保存')
    await loadConfigs()
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  }
}

async function onSetDefault(id: number) {
  await ldsApi.setDefault(id)
  ElMessage.success('已设为默认')
  await loadConfigs()
}

async function runTrial(force: boolean) {
  const loading = force ? forcing : trialing
  loading.value = true
  try {
    const data = await ldsApi.trial({ ...buildScopeBody(), persist: true, force })
    trialItems.value = sortByIdentityDesc(data.items || [])
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
  try {
    await confirmStrategyJob('lds', '龙头战法将按当前范围写入预计算。')
  } catch {
    return
  }
  precomputing.value = true
  try {
    const data = await ldsApi.triggerPrecompute({ ...buildScopeBody(), force: true })
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
    const data = await ldsApi.listSignals({
      trade_date: signalQuery.trade_date,
      config_id: signalQuery.config_id,
      code: signalQuery.code || undefined,
      limit: 500,
    })
    signalItems.value = sortByIdentityDesc(data.items || [])
    signalTotal.value = data.total ?? signalItems.value.length
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e.message || '查询失败')
  } finally {
    loadingSignals.value = false
  }
}

function exportCsv(filename: string, rows: any[]) {
  if (!rows.length) return
  const cols = [
    'code',
    'name',
    'role',
    'board_code',
    'board_name',
    'identity_score',
    'drive_score',
    'watch_ready',
    'board_count',
    'same_as_height',
    'is_primary',
  ]
  const lines = [cols.join(',')]
  for (const r of rows) {
    lines.push(
      cols
        .map((c) => {
          const v = r[c] == null ? '' : String(r[c])
          return `"${v.replace(/"/g, '""')}"`
        })
        .join(',')
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
  exportCsv(`lds_trial_${trialMeta.value?.trade_date || 'export'}.csv`, trialItems.value)
}

function exportSignalsCsv() {
  exportCsv(`lds_signals_${signalQuery.trade_date}.csv`, signalItems.value)
}

onMounted(() => {
  loadConfigs()
})
</script>

<style scoped>
.lds-management { padding: 16px; width: 100%; box-sizing: border-box; }
.page-header { margin-bottom: 16px; }
.page-title { margin: 0; font-size: 22px; }
.page-subtitle { margin: 4px 0 0; color: #666; }
.toolbar { margin-bottom: 12px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.scope-form { max-width: 960px; margin-bottom: 12px; }
.hint { margin-left: 8px; color: #64748b; font-size: 12px; }
.meta-line { margin: 0 0 8px; color: #64748b; font-size: 13px; }
.w-full { width: 100%; }
.lds-table-wrap { width: 100%; min-width: 0; }
.lds-table { width: 100% !important; }
.lds-table :deep(.el-table__header),
.lds-table :deep(.el-table__body) { width: 100% !important; }
.lds-table :deep(.cell) { padding-left: 8px; padding-right: 8px; }
</style>
