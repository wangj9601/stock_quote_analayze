<template>
  <div class="sbbr-management">
    <div class="page-header">
      <h1 class="page-title">做小做底（SBBR）管理</h1>
      <p class="page-subtitle">参数版本 · 历史回测 · 手动预计算</p>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="策略配置" name="config">
        <div class="toolbar">
          <el-button type="primary" @click="loadConfigs">刷新</el-button>
          <el-button @click="showCreate = true">新建版本</el-button>
          <el-button type="warning" :loading="precomputing" @click="openPrecompute">手动预计算</el-button>
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

      <el-tab-pane label="回测任务" name="backtest">
        <el-card shadow="never" class="history-card">
          <template #header>
            <div class="card-header">
              <span>历史回测</span>
              <div class="toolbar inline">
                <el-button type="primary" @click="loadBacktests">刷新</el-button>
                <el-button type="success" @click="openBtDialog">创建历史回测</el-button>
              </div>
            </div>
          </template>
          <el-table :data="backtests" stripe v-loading="loadingBt">
            <el-table-column prop="task_id" label="任务ID" min-width="200" show-overflow-tooltip />
            <el-table-column prop="name" label="名称" width="140" show-overflow-tooltip />
            <el-table-column label="数据范围" min-width="140">
              <template #default="{ row }">
                {{ formatScope(row) }}
              </template>
            </el-table-column>
            <el-table-column prop="backtest_type" label="类型" width="130" />
            <el-table-column label="入场次数" width="90" align="right">
              <template #default="{ row }">
                {{ formatNum(row.summary?.entry_count) }}
              </template>
            </el-table-column>
            <el-table-column label="命中次数" width="90" align="right">
              <template #default="{ row }">
                <template v-if="row.backtest_type === 'trade_simulation'">
                  {{ formatNum(row.summary?.total_trades) }}
                  <span class="sub-hint">交易</span>
                </template>
                <template v-else>
                  {{ formatNum(row.summary?.hit_count) }}
                </template>
              </template>
            </el-table-column>
            <el-table-column label="命中率" width="90" align="right">
              <template #default="{ row }">
                <template v-if="row.backtest_type === 'trade_simulation'">
                  {{ formatPct(row.summary?.win_rate) }}
                  <span class="sub-hint">胜率</span>
                </template>
                <template v-else>
                  {{ formatPct(row.summary?.hit_rate) }}
                </template>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="90" />
            <el-table-column prop="progress" label="进度" width="70" />
            <el-table-column prop="created_at" label="创建时间" width="170" />
            <el-table-column label="操作" width="90" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="viewBt(row.task_id)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
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

    <el-dialog v-model="showBt" title="创建历史回测" width="640px">
      <el-form label-width="120px">
        <el-form-item label="任务名"><el-input v-model="btForm.task_name" /></el-form-item>
        <el-form-item label="开始日"><el-input v-model="btForm.start_date" placeholder="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="结束日"><el-input v-model="btForm.end_date" placeholder="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="btForm.backtest_type" style="width: 100%">
            <el-option label="命中率 signal_hit_rate" value="signal_hit_rate" />
            <el-option label="交易模拟 trade_simulation" value="trade_simulation" />
          </el-select>
        </el-form-item>
        <el-form-item label="数据范围" required>
          <el-select v-model="btForm.stock_pool_mode" style="width: 100%" @change="onPoolModeChange">
            <el-option label="全市场（做小宇宙）" value="market" />
            <el-option label="行业板块" value="industry_board" />
            <el-option label="概念板块" value="concept_board" />
            <el-option label="个股" value="stocks" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="btForm.stock_pool_mode === 'industry_board'" label="行业板块" required>
          <BoardPickerDialog v-model="selectedIndustryBoardCodes" board-type="industry" />
        </el-form-item>
        <el-form-item v-if="btForm.stock_pool_mode === 'concept_board'" label="概念板块" required>
          <BoardPickerDialog v-model="selectedConceptBoardCodes" board-type="concept" />
        </el-form-item>
        <el-form-item v-if="btForm.stock_pool_mode === 'stocks'" label="个股代码" required>
          <el-input
            v-model="stockCodesText"
            type="textarea"
            :rows="3"
            placeholder="多个代码用逗号、空格或换行分隔，如 600519,000001"
          />
        </el-form-item>
        <el-form-item v-if="btForm.stock_pool_mode === 'market'" label="宇宙上限">
          <el-input-number v-model="btForm.universe_limit" :min="10" :max="500" />
          <span class="form-hint">按做小宇宙筛选后取前 N 只</span>
        </el-form-item>
        <el-form-item label="目标涨幅"><el-input-number v-model="btForm.target_pct" :min="0.1" :max="2" :step="0.1" /></el-form-item>
        <el-form-item label="持有天数"><el-input-number v-model="btForm.horizon_days" :min="5" :max="120" /></el-form-item>
        <el-form-item label="采样步长"><el-input-number v-model="btForm.date_step" :min="1" :max="20" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBt = false">取消</el-button>
        <el-button type="primary" @click="onCreateBt">提交</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showDetail" title="回测详情" width="720px">
      <pre class="json-pre">{{ detailText }}</pre>
    </el-dialog>

    <el-dialog v-model="showPrecompute" title="SBBR 信号预计算" width="440px">
      <el-form label-width="100px">
        <el-form-item label="基准日">
          <el-date-picker
            v-model="precomputeForm.trade_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="留空=最新交易日"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="配置 ID">
          <el-input-number v-model="precomputeForm.config_id" :min="1" controls-position="right" />
          <span class="precompute-hint">可选；不填用默认配置</span>
        </el-form-item>
        <p class="precompute-hint">
          按指定交易日（含当日及之前行情）全市场筛选并写入 sbbr_signal_trace；非交易日会自动对齐到 ≤该日 的最近有行情日。
        </p>
      </el-form>
      <template #footer>
        <el-button @click="showPrecompute = false">取消</el-button>
        <el-button type="primary" :loading="precomputing" @click="onPrecompute">开始预计算</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import BoardPickerDialog from '@/components/common/BoardPickerDialog.vue'
import sbbrApi, { type SbbrBacktestCreateBody, type SbbrStockPoolMode } from '@/services/sbbrApi'

const MODE_LABELS: Record<string, string> = {
  market: '全市场',
  industry_board: '行业',
  concept_board: '概念',
  stocks: '个股',
}

const activeTab = ref('config')
const configs = ref<any[]>([])
const backtests = ref<any[]>([])
const loadingConfigs = ref(false)
const loadingBt = ref(false)
const precomputing = ref(false)
const showCreate = ref(false)
const showEdit = ref(false)
const showBt = ref(false)
const showDetail = ref(false)
const showPrecompute = ref(false)
const editId = ref<number | null>(null)
const editJson = ref('')
const detailText = ref('')
const selectedIndustryBoardCodes = ref<string[]>([])
const selectedConceptBoardCodes = ref<string[]>([])
const stockCodesText = ref('')

const createForm = reactive({ name: '', description: '', set_default: false })
const precomputeForm = reactive<{ trade_date: string; config_id: number | undefined }>({
  trade_date: '',
  config_id: undefined,
})
const btForm = reactive({
  task_name: 'sbbr-bt',
  start_date: '',
  end_date: '',
  backtest_type: 'signal_hit_rate',
  target_pct: 0.5,
  horizon_days: 60,
  universe_limit: 50,
  date_step: 5,
  stock_pool_mode: 'market' as SbbrStockPoolMode,
})

function parseStockCodes(text: string): string[] {
  return text
    .split(/[\s,;，；\n\r]+/)
    .map((s) => s.trim())
    .filter(Boolean)
}

function formatNum(v: unknown): string {
  if (v === null || v === undefined || v === '') return '-'
  const n = Number(v)
  return Number.isFinite(n) ? String(n) : '-'
}

function formatPct(v: unknown): string {
  if (v === null || v === undefined || v === '') return '-'
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  return `${(n * 100).toFixed(1)}%`
}

function formatScope(row: any): string {
  const mode = row.stock_pool_mode || row.scope_meta?.stock_pool_mode || '-'
  const label = MODE_LABELS[mode] || mode
  const meta = row.scope_meta || {}
  const count = meta.stock_count
  if (mode === 'market') {
    const lim = meta.universe_limit
    return lim != null ? `${label}(上限${lim})` : label
  }
  if (count != null) return `${label}(${count}只)`
  const boards = meta.board_codes
  if (Array.isArray(boards) && boards.length) return `${label}(${boards.length}板)`
  return label
}

function onPoolModeChange() {
  selectedIndustryBoardCodes.value = []
  selectedConceptBoardCodes.value = []
  stockCodesText.value = ''
}

function openBtDialog() {
  if (!btForm.start_date || !btForm.end_date) {
    const end = new Date()
    const start = new Date()
    start.setMonth(start.getMonth() - 6)
    btForm.end_date = end.toISOString().slice(0, 10)
    btForm.start_date = start.toISOString().slice(0, 10)
  }
  showBt.value = true
}

async function loadConfigs() {
  loadingConfigs.value = true
  try {
    const data = await sbbrApi.listConfigs()
    configs.value = data.items || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e.message || '加载配置失败')
  } finally {
    loadingConfigs.value = false
  }
}

async function loadBacktests() {
  loadingBt.value = true
  try {
    const data = await sbbrApi.listBacktests()
    backtests.value = data.items || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e.message || '加载回测失败')
  } finally {
    loadingBt.value = false
  }
}

async function onCreate() {
  try {
    await sbbrApi.createConfig({ ...createForm })
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
    await sbbrApi.updateConfig(editId.value, { config_params: params })
    showEdit.value = false
    ElMessage.success('已保存')
    await loadConfigs()
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  }
}

async function onSetDefault(id: number) {
  await sbbrApi.setDefault(id)
  ElMessage.success('已设为默认')
  await loadConfigs()
}

function openPrecompute() {
  if (!precomputeForm.trade_date) {
    precomputeForm.trade_date = new Date().toISOString().slice(0, 10)
  }
  showPrecompute.value = true
}

async function onPrecompute() {
  precomputing.value = true
  try {
    const params: { config_id?: number; trade_date?: string } = {}
    if (precomputeForm.config_id) params.config_id = precomputeForm.config_id
    if (precomputeForm.trade_date) params.trade_date = precomputeForm.trade_date
    const data: any = await sbbrApi.triggerPrecompute(params)
    ElMessage.success(
      `预计算完成 date=${data.trade_date ?? precomputeForm.trade_date ?? '-'} screened=${data.screened ?? '-'} entry=${data.entry_count ?? '-'}`
    )
    showPrecompute.value = false
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e.message)
  } finally {
    precomputing.value = false
  }
}

async function onCreateBt() {
  if (!btForm.start_date || !btForm.end_date) {
    ElMessage.warning('请填写开始日与结束日')
    return
  }
  const mode = btForm.stock_pool_mode
  const body: SbbrBacktestCreateBody = {
    task_name: btForm.task_name,
    start_date: btForm.start_date,
    end_date: btForm.end_date,
    backtest_type: btForm.backtest_type,
    target_pct: btForm.target_pct,
    horizon_days: btForm.horizon_days,
    universe_limit: btForm.universe_limit,
    date_step: btForm.date_step,
    stock_pool_mode: mode,
  }
  if (mode === 'industry_board') {
    if (!selectedIndustryBoardCodes.value.length) {
      ElMessage.warning('请选择行业板块')
      return
    }
    body.industry_board_codes = [...selectedIndustryBoardCodes.value]
  } else if (mode === 'concept_board') {
    if (!selectedConceptBoardCodes.value.length) {
      ElMessage.warning('请选择概念板块')
      return
    }
    body.concept_board_codes = [...selectedConceptBoardCodes.value]
  } else if (mode === 'stocks') {
    const codes = parseStockCodes(stockCodesText.value)
    if (!codes.length) {
      ElMessage.warning('请输入个股代码')
      return
    }
    body.stock_codes = codes
  }

  try {
    const data = await sbbrApi.createBacktest(body)
    showBt.value = false
    ElMessage.success(`已创建任务 ${data.task_id}`)
    activeTab.value = 'backtest'
    await loadBacktests()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e.message)
  }
}

async function viewBt(taskId: string) {
  const data = await sbbrApi.getBacktest(taskId)
  detailText.value = JSON.stringify(data, null, 2)
  showDetail.value = true
}

onMounted(() => {
  loadConfigs()
  loadBacktests()
})
</script>

<style scoped>
.sbbr-management { padding: 16px; }
.page-header { margin-bottom: 16px; }
.page-title { margin: 0; font-size: 22px; }
.page-subtitle { margin: 4px 0 0; color: #666; }
.toolbar { margin-bottom: 12px; display: flex; gap: 8px; }
.toolbar.inline { margin-bottom: 0; }
.card-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.history-card { border: 1px solid #e5e7eb; }
.form-hint { margin-left: 8px; color: #64748b; font-size: 12px; }
.sub-hint { display: block; font-size: 11px; color: #94a3b8; line-height: 1.2; }
.precompute-hint { margin: 4px 0 0; color: #64748b; font-size: 12px; }
.json-pre {
  max-height: 480px;
  overflow: auto;
  background: #0f172a;
  color: #e2e8f0;
  padding: 12px;
  border-radius: 8px;
  font-size: 12px;
}
</style>
