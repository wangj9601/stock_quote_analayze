<template>
  <div class="stock-basic-view">
    <div class="page-header">
      <h1>股票基本信息</h1>
    </div>

    <el-radio-group v-model="mainTab" class="mb-4" @change="onMainTabChange">
      <el-radio-button label="CN">A股</el-radio-button>
      <el-radio-button label="HK">港股</el-radio-button>
    </el-radio-group>

    <el-tabs v-model="subTab" type="card">
      <el-tab-pane label="基本信息查询" name="query">
        <el-card>
          <el-row :gutter="12" class="mb-4">
            <el-col :xs="24" :sm="12" :md="7">
              <el-input v-model="currentQuery.keyword" placeholder="代码/名称" clearable />
            </el-col>
            <el-col :xs="24" :sm="12" :md="5">
              <el-checkbox v-model="currentQuery.empty_shares">仅缺股本</el-checkbox>
            </el-col>
            <el-col :xs="24" :sm="12" :md="4">
              <el-select v-model="currentQuery.delisted_filter" style="width: 100%" placeholder="退市筛选">
                <el-option label="全部股票" value="all" />
                <el-option label="仅退市" value="only" />
                <el-option label="排除退市" value="exclude" />
              </el-select>
            </el-col>
            <el-col :xs="24" :sm="12" :md="4">
              <el-select v-model="currentCollectFilter" style="width: 100%" placeholder="采集标志">
                <el-option label="全部" value="all" />
                <el-option label="启用" value="enabled" />
                <el-option label="停用" value="disabled" />
              </el-select>
            </el-col>
            <el-col :xs="24" :sm="24" :md="8">
              <el-button type="primary" :loading="loading" @click="loadList">查询</el-button>
              <el-button
                v-if="mainTab === 'CN'"
                type="success"
                plain
                :loading="syncingIndustry"
                @click="syncIndustry"
              >
                同步行业
              </el-button>
            </el-col>
          </el-row>

          <div class="mb-3 flex gap-2 flex-wrap">
            <el-button :disabled="!selectedRows.length" @click="batchSetCollect(true)">批量启用采集</el-button>
            <el-button :disabled="!selectedRows.length" @click="batchSetCollect(false)">批量停用采集</el-button>
          </div>

          <div class="table-scroll">
            <el-table ref="tableRef" :data="rows" :loading="loading" stripe @selection-change="onSelectionChange">
              <el-table-column type="selection" width="42" />
              <el-table-column prop="code" label="代码" width="100" />
              <el-table-column prop="name" label="名称" min-width="120" />
              <el-table-column prop="total_shares" label="总股本" min-width="110" />
              <el-table-column prop="free_float_shares" label="流通股本" min-width="110" />
              <el-table-column prop="industry" label="行业" min-width="110">
                <template #default="scope">
                  {{ displayOptionalText(scope.row.industry) }}
                </template>
              </el-table-column>
              <el-table-column prop="listing_date" label="上市日期" min-width="100">
                <template #default="scope">
                  {{ displayOptionalText(scope.row.listing_date) }}
                </template>
              </el-table-column>
              <el-table-column prop="shares_updated_at" label="更新时间" min-width="170" />
              <el-table-column label="采集/处理" min-width="120">
                <template #default="scope">
                  <el-switch
                    :model-value="scope.row.collect_enabled"
                    @change="(v: boolean) => toggleCollectFlag(scope.row, v)"
                  />
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div class="mt-4 flex justify-end">
            <el-pagination
              v-model:current-page="currentQuery.page"
              v-model:page-size="currentQuery.page_size"
              :total="total"
              :page-sizes="[20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              @current-change="loadList"
              @size-change="loadList"
            />
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="股本导入" name="import">
        <el-card>
          <el-alert
            v-if="pipelineStatus"
            class="mb-4"
            type="warning"
            :closable="false"
            show-icon
            :title="`缺少股本：A股 ${pipelineStatus.missing_shares?.CN || 0}，港股 ${pipelineStatus.missing_shares?.HK || 0}`"
          />

          <div class="mb-4">
            <el-button @click="downloadTemplate('csv')">下载CSV模板</el-button>
            <el-button @click="downloadTemplate('xlsx')">下载XLSX模板</el-button>
            <el-button @click="loadPipelineStatus">刷新链路状态</el-button>
          </div>

          <el-alert class="mb-4" type="info" :closable="false" show-icon
            :title="`当前为【${mainTab === 'CN' ? 'A股' : '港股'}】导入。支持 CSV/XLS/XLSX，以及华泰/东财 Table.xls（制表符文本）。若文件含「流通值+现价」会自动反算流通股；「总市值+现价」反算总股本。`"
          />

          <el-form inline class="mb-4">
            <el-form-item label="写入策略">
              <el-select v-model="importMode" style="width: 280px">
                <el-option label="覆盖已有股本（推荐，刷新旧数据）" value="overwrite_shares" />
                <el-option label="仅补空（已有股本不改）" value="only_fill_empty" />
              </el-select>
            </el-form-item>
          </el-form>

          <el-upload
            :auto-upload="false"
            :show-file-list="true"
            :on-change="onFileChange"
            :limit="1"
            accept=".csv,.xlsx,.xls"
          >
            <template #trigger>
              <el-button type="primary">选择导入文件</el-button>
            </template>
          </el-upload>

          <div class="mt-4">
            <el-button :disabled="!currentImportFile" :loading="validating" @click="validateFile">预校验</el-button>
            <el-button :disabled="!currentImportFile" :loading="executing" @click="executeImport(false)">执行导入</el-button>
            <el-button :disabled="!currentImportFile" :loading="executing" @click="executeImport(true)">Dry Run</el-button>
          </div>

          <el-card v-if="currentValidateResult" class="mt-4">
            <template #header>预校验结果</template>
            <div>有效行：{{ currentValidateResult.valid_rows }}，无效行：{{ currentValidateResult.invalid_rows }}</div>
            <div>市场分布：A股 {{ currentValidateResult.market_count?.CN || 0 }}，港股 {{ currentValidateResult.market_count?.HK || 0 }}</div>
            <div>
              含股本数据行：{{ currentValidateResult.rows_with_shares ?? '--' }}
              （其中市值反算：{{ currentValidateResult.derived_from_mv ?? 0 }}）
            </div>
            <div class="table-scroll">
              <el-table :data="currentValidateResult.issues || []" size="small" class="mt-3">
                <el-table-column prop="row_no" label="行号" width="80" />
                <el-table-column prop="code" label="代码" width="120" />
                <el-table-column prop="message" label="错误信息" min-width="220" />
              </el-table>
            </div>
          </el-card>

          <el-card v-if="currentExecuteResult" class="mt-4">
            <template #header>导入结果</template>
            <div>
              模式 {{ currentExecuteResult.mode }}，总行数 {{ currentExecuteResult.total_rows }}，
              成功 {{ currentExecuteResult.success }}，跳过 {{ currentExecuteResult.skipped }}，
              失败 {{ currentExecuteResult.failed }}
              <span v-if="currentExecuteResult.derived_from_mv">
                ，市值反算 {{ currentExecuteResult.derived_from_mv }}
              </span>
              <span v-if="currentExecuteResult.no_shares_in_row">
                ，无股本字段跳过 {{ currentExecuteResult.no_shares_in_row }}
              </span>
            </div>
            <div class="table-scroll">
              <el-table :data="currentExecuteResult.failed_sample || []" size="small" class="mt-3">
                <el-table-column prop="row_no" label="行号" width="80" />
                <el-table-column prop="code" label="代码" width="120" />
                <el-table-column prop="message" label="错误信息" min-width="220" />
              </el-table>
            </div>
          </el-card>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="股本导出" name="export">
        <el-card>
          <el-alert
            class="mb-4"
            type="info"
            :closable="false"
            show-icon
            title="导出列含：code、name、market、total_shares、free_float_shares、listing_date、industry、shares_updated_at、collect_enabled。可按下方条件筛选后导出全部匹配行（不分页）。"
          />
          <el-row :gutter="12" class="mb-4">
            <el-col :xs="24" :sm="12" :md="8">
              <el-input v-model="currentExportFilters.keyword" placeholder="代码/名称（可选）" clearable />
            </el-col>
            <el-col :xs="24" :sm="12" :md="5">
              <el-checkbox v-model="currentExportFilters.empty_shares">仅缺股本</el-checkbox>
            </el-col>
            <el-col :xs="24" :sm="12" :md="6">
              <el-select v-model="currentExportFilters.delisted_filter" style="width: 100%" placeholder="退市筛选">
                <el-option label="全部股票" value="all" />
                <el-option label="仅退市" value="only" />
                <el-option label="排除退市" value="exclude" />
              </el-select>
            </el-col>
            <el-col :xs="24" :sm="12" :md="6">
              <el-select v-model="currentExportCollectFilter" style="width: 100%" placeholder="采集标志">
                <el-option label="全部" value="all" />
                <el-option label="启用" value="enabled" />
                <el-option label="停用" value="disabled" />
              </el-select>
            </el-col>
          </el-row>
          <div class="mb-2">
            <el-button type="primary" :loading="exporting" @click="doExport('csv')">导出 CSV</el-button>
            <el-button type="primary" :loading="exporting" @click="doExport('xlsx')">导出 XLSX</el-button>
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="股价相对强度" name="rs">
        <el-card>
          <el-alert
            class="mb-4"
            type="info"
            :closable="false"
            show-icon
            :title="`仅 A 股，按前复权收盘计算。默认最新预计算日，RS 从高到低。${rsAsof ? `当前基准日：${rsAsof}` : '尚未预计算'}`"
          />
          <el-row :gutter="12" class="mb-4">
            <el-col :xs="24" :sm="12" :md="6">
              <el-input v-model="rsQuery.keyword" placeholder="代码/名称" clearable />
            </el-col>
            <el-col :xs="24" :sm="12" :md="5">
              <el-date-picker
                v-model="rsQuery.date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="基准日（可选）"
                style="width: 100%"
                clearable
              />
            </el-col>
            <el-col :xs="24" :sm="12" :md="5">
              <el-select v-model="rsQuery.min_rating" style="width: 100%" clearable placeholder="最低评级（清空=全部）">
                <el-option label="≥90 很强" :value="90" />
                <el-option label="≥70 偏强" :value="70" />
                <el-option label="≥50 中性+" :value="50" />
              </el-select>
            </el-col>
            <el-col :xs="24" :sm="12" :md="8">
              <el-button type="primary" :loading="rsLoading" @click="searchRsList">查询</el-button>
              <el-button @click="openRsTrace()">历史追溯</el-button>
            </el-col>
          </el-row>
          <el-row :gutter="12" class="mb-4">
            <el-col :xs="24" :sm="12" :md="10">
              <el-date-picker
                v-model="rsForceRange"
                type="daterange"
                value-format="YYYY-MM-DD"
                start-placeholder="重算起"
                end-placeholder="重算止"
                style="width: 100%"
                clearable
              />
            </el-col>
            <el-col :xs="24" :sm="12" :md="14">
              <el-button
                type="warning"
                :loading="rsForceLoading"
                @click="forceRsPrecompute"
              >强制重算区间（全市场）</el-button>
              <span v-if="rsForceStatus" class="rs-force-status inline">{{ rsForceStatus }}</span>
            </el-col>
          </el-row>

          <div class="table-scroll">
            <el-table :data="rsRows" :loading="rsLoading" stripe>
              <el-table-column prop="rs_rating" label="RS" width="80" sortable>
                <template #default="scope">
                  <span :class="rsToneClass(scope.row.rs_rating)">
                    {{ scope.row.rs_rating ?? '--' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="strength_label" label="强弱" width="80" />
              <el-table-column prop="code" label="代码" width="100" />
              <el-table-column prop="name" label="名称" min-width="120" />
              <el-table-column prop="date" label="基准日" width="110" />
              <el-table-column label="近63日" min-width="100">
                <template #default="scope">{{ formatRoc(scope.row.roc_63) }}</template>
              </el-table-column>
              <el-table-column label="近126日" min-width="100">
                <template #default="scope">{{ formatRoc(scope.row.roc_126) }}</template>
              </el-table-column>
              <el-table-column label="近189日" min-width="100">
                <template #default="scope">{{ formatRoc(scope.row.roc_189) }}</template>
              </el-table-column>
              <el-table-column label="近252日" min-width="100">
                <template #default="scope">{{ formatRoc(scope.row.roc_252) }}</template>
              </el-table-column>
              <el-table-column prop="rs_raw" label="RS_Raw" min-width="100">
                <template #default="scope">
                  {{ scope.row.rs_raw == null ? '--' : Number(scope.row.rs_raw).toFixed(4) }}
                </template>
              </el-table-column>
              <el-table-column prop="universe_size" label="宇宙" width="90" />
              <el-table-column label="操作" width="100" fixed="right">
                <template #default="scope">
                  <el-button link type="primary" @click="openRsTrace(scope.row)">追溯</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div class="mt-4 flex justify-end">
            <el-pagination
              v-model:current-page="rsQuery.page"
              v-model:page-size="rsQuery.page_size"
              :total="rsTotal"
              :page-sizes="[20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              @current-change="loadRsList"
              @size-change="loadRsList"
            />
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog
      v-model="rsTraceVisible"
      :title="`RS 历史追溯${rsTraceMeta ? ' · ' + rsTraceMeta : ''}`"
      width="920px"
      destroy-on-close
    >
      <el-row :gutter="12" class="mb-3">
        <el-col :span="6">
          <el-input v-model="rsTraceForm.code" placeholder="6位代码" clearable />
        </el-col>
        <el-col :span="6">
          <el-date-picker
            v-model="rsTraceForm.start_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="起始日"
            style="width: 100%"
            clearable
          />
        </el-col>
        <el-col :span="6">
          <el-date-picker
            v-model="rsTraceForm.end_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="结束日"
            style="width: 100%"
            clearable
          />
        </el-col>
        <el-col :span="6">
          <el-button type="primary" :loading="rsTraceLoading" @click="loadRsTrace">查询</el-button>
          <el-button
            :disabled="!rsTraceForm.code"
            @click="openPublicRsTrace"
          >站外追溯页</el-button>
        </el-col>
      </el-row>
      <el-row :gutter="12" class="mb-3">
        <el-col :span="10">
          <el-date-picker
            v-model="rsForceRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            start-placeholder="强制重算起"
            end-placeholder="强制重算止"
            style="width: 100%"
            clearable
          />
        </el-col>
        <el-col :span="14">
          <el-button
            type="warning"
            :loading="rsForceLoading"
            @click="forceRsPrecomputeFromTrace"
          >强制重算区间（全市场）</el-button>
          <span v-if="rsForceStatus" class="rs-force-status inline">{{ rsForceStatus }}</span>
        </el-col>
      </el-row>
      <div class="table-scroll">
        <el-table :data="rsTraceRows" :loading="rsTraceLoading" stripe max-height="480" size="small">
          <el-table-column prop="date" label="日期" width="110" />
          <el-table-column prop="rs_rating" label="RS" width="70">
            <template #default="scope">
              <span :class="rsToneClass(scope.row.rs_rating)">{{ scope.row.rs_rating ?? '--' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="strength_label" label="强弱" width="70" />
          <el-table-column prop="rs_raw" label="RS_Raw" min-width="90">
            <template #default="scope">
              {{ scope.row.rs_raw == null ? '--' : Number(scope.row.rs_raw).toFixed(4) }}
            </template>
          </el-table-column>
          <el-table-column label="近63日" min-width="90">
            <template #default="scope">{{ formatRoc(scope.row.roc_63) }}</template>
          </el-table-column>
          <el-table-column label="近126日" min-width="90">
            <template #default="scope">{{ formatRoc(scope.row.roc_126) }}</template>
          </el-table-column>
          <el-table-column label="近189日" min-width="90">
            <template #default="scope">{{ formatRoc(scope.row.roc_189) }}</template>
          </el-table-column>
          <el-table-column label="近252日" min-width="90">
            <template #default="scope">{{ formatRoc(scope.row.roc_252) }}</template>
          </el-table-column>
          <el-table-column prop="universe_size" label="宇宙" width="80" />
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { stockBasicService, type DelistedFilter, type StockBasicMarket } from '@/services/stockBasic.service'
import { stockRsTraceUrl } from '@/utils/publicStockLinks'

const mainTab = ref<StockBasicMarket>('CN')
const subTab = ref('query')
const loading = ref(false)
const syncingIndustry = ref(false)
const validating = ref(false)
const importMode = ref<'only_fill_empty' | 'overwrite_shares'>('overwrite_shares')
const executing = ref(false)
const exporting = ref(false)
const rows = ref<any[]>([])
const total = ref(0)
const selectedRows = ref<any[]>([])
const tableRef = ref()
const pipelineStatus = ref<any>(null)

type CollectFilter = 'all' | 'enabled' | 'disabled'

const queryCN = reactive({
  keyword: '',
  empty_shares: false,
  delisted_filter: 'all' as DelistedFilter,
  page: 1,
  page_size: 20
})
const queryHK = reactive({
  keyword: '',
  empty_shares: false,
  delisted_filter: 'all' as DelistedFilter,
  page: 1,
  page_size: 20
})
const collectFilterCN = ref<CollectFilter>('all')
const collectFilterHK = ref<CollectFilter>('all')

const currentQuery = computed(() => (mainTab.value === 'CN' ? queryCN : queryHK))
const currentCollectFilter = computed({
  get: () => (mainTab.value === 'CN' ? collectFilterCN.value : collectFilterHK.value),
  set: (v: CollectFilter) => {
    if (mainTab.value === 'CN') collectFilterCN.value = v
    else collectFilterHK.value = v
  }
})

const fileCN = ref<File | null>(null)
const fileHK = ref<File | null>(null)
const validateCN = ref<any>(null)
const validateHK = ref<any>(null)
const executeCN = ref<any>(null)
const executeHK = ref<any>(null)

const currentImportFile = computed(() => (mainTab.value === 'CN' ? fileCN.value : fileHK.value))
const currentValidateResult = computed(() => (mainTab.value === 'CN' ? validateCN.value : validateHK.value))
const currentExecuteResult = computed(() => (mainTab.value === 'CN' ? executeCN.value : executeHK.value))

const exportFiltersCN = reactive({ keyword: '', empty_shares: false, delisted_filter: 'all' as DelistedFilter })
const exportFiltersHK = reactive({ keyword: '', empty_shares: false, delisted_filter: 'all' as DelistedFilter })
const exportCollectFilterCN = ref<CollectFilter>('all')
const exportCollectFilterHK = ref<CollectFilter>('all')

const currentExportFilters = computed(() => (mainTab.value === 'CN' ? exportFiltersCN : exportFiltersHK))
const currentExportCollectFilter = computed({
  get: () => (mainTab.value === 'CN' ? exportCollectFilterCN.value : exportCollectFilterHK.value),
  set: (v: CollectFilter) => {
    if (mainTab.value === 'CN') exportCollectFilterCN.value = v
    else exportCollectFilterHK.value = v
  }
})

function collectEnabledFromFilter(cf: CollectFilter): boolean | null {
  if (cf === 'all') return null
  return cf === 'enabled'
}

/** 行业、上市日期：不展示 nan / 无效占位 */
function displayOptionalText(v: unknown): string {
  if (v === null || v === undefined) return ''
  const s = String(v).trim()
  if (!s) return ''
  const low = s.toLowerCase()
  if (low === 'nan' || low === 'none' || low === 'null' || low === '<na>' || low === 'nat') return ''
  return s
}

const loadList = async () => {
  loading.value = true
  try {
    const m = mainTab.value
    const q = m === 'CN' ? queryCN : queryHK
    const cf = m === 'CN' ? collectFilterCN.value : collectFilterHK.value
    const res = await stockBasicService.getList({
      market: m,
      keyword: q.keyword,
      empty_shares: q.empty_shares,
      delisted_filter: q.delisted_filter,
      collect_enabled: collectEnabledFromFilter(cf),
      page: q.page,
      page_size: q.page_size
    })
    rows.value = res.data || []
    total.value = res.total || 0
  } catch (e: any) {
    ElMessage.error(e?.message || '查询失败')
  } finally {
    loading.value = false
  }
}

const syncIndustry = async () => {
  syncingIndustry.value = true
  try {
    const res = await stockBasicService.syncIndustryFromBoards({ only_empty: true })
    const updated = res.data?.updated ?? 0
    ElMessage.success(`已同步 ${updated} 条 A 股行业`)
    await loadList()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '同步行业失败')
  } finally {
    syncingIndustry.value = false
  }
}

const toggleCollectFlag = async (row: any, value: boolean) => {
  try {
    await stockBasicService.updateCollectFlag(row.market, row.code, value)
    row.collect_enabled = value
    ElMessage.success('采集/处理标志已更新')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '更新失败')
    loadList()
  }
}

const onSelectionChange = (selection: any[]) => {
  selectedRows.value = selection
}

const batchSetCollect = async (enabled: boolean) => {
  if (!selectedRows.value.length) return
  const label = enabled ? '启用' : '停用'
  try {
    await ElMessageBox.confirm(
      `确定对选中的 ${selectedRows.value.length} 只股票批量${label}采集/处理吗？`,
      `批量${label}采集`,
      { type: 'warning' }
    )
    const codes = selectedRows.value.map((r) => r.code)
    const res = await stockBasicService.batchUpdateCollectFlag(mainTab.value, codes, enabled)
    const affected = res.data?.affected ?? 0
    ElMessage.success(`已${label} ${affected} 条`)
    selectedRows.value = []
    tableRef.value?.clearSelection?.()
    await loadList()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.detail || e?.message || '批量更新失败')
    }
  }
}

const loadPipelineStatus = async () => {
  try {
    const res = await stockBasicService.getPipelineStatus()
    pipelineStatus.value = res.data
  } catch {
    // ignore
  }
}

const downloadTemplate = async (format: 'csv' | 'xlsx') => {
  try {
    const blob = await stockBasicService.downloadTemplate(format)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `stock_basic_import_template.${format}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('模板下载失败')
  }
}

const onFileChange = (uploadFile: any) => {
  const f = uploadFile.raw || null
  if (mainTab.value === 'CN') {
    fileCN.value = f
    validateCN.value = null
    executeCN.value = null
  } else {
    fileHK.value = f
    validateHK.value = null
    executeHK.value = null
  }
}

const validateFile = async () => {
  const f = currentImportFile.value
  if (!f) return
  validating.value = true
  try {
    const res = await stockBasicService.validateImport(f, mainTab.value)
    if (mainTab.value === 'CN') validateCN.value = res.data
    else validateHK.value = res.data
    ElMessage.success('预校验完成')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '预校验失败')
  } finally {
    validating.value = false
  }
}

const executeImport = async (dryRun: boolean) => {
  const f = currentImportFile.value
  if (!f) return
  executing.value = true
  try {
    const res = await stockBasicService.executeImport(
      f,
      dryRun,
      100,
      mainTab.value,
      importMode.value
    )
    if (mainTab.value === 'CN') executeCN.value = res.data
    else executeHK.value = res.data
    if (res.success) {
      ElMessage.success(dryRun ? 'Dry Run完成' : '导入完成')
      if (!dryRun) loadList()
    } else {
      ElMessage.warning('导入完成，但存在失败项')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '导入失败')
  } finally {
    executing.value = false
  }
}

const doExport = async (format: 'csv' | 'xlsx') => {
  exporting.value = true
  try {
    const ef = mainTab.value === 'CN' ? exportFiltersCN : exportFiltersHK
    const ecf = mainTab.value === 'CN' ? exportCollectFilterCN.value : exportCollectFilterHK.value
    const blob = await stockBasicService.exportShares(mainTab.value, format, {
      keyword: ef.keyword || undefined,
      empty_shares: ef.empty_shares,
      delisted_filter: ef.delisted_filter,
      collect_enabled: collectEnabledFromFilter(ecf)
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `stock_basic_shares_${mainTab.value.toLowerCase()}.${format}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success('导出已开始')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

function onMainTabChange() {
  if (subTab.value === 'query') loadList()
}

const rsLoading = ref(false)
const rsRows = ref<any[]>([])
const rsTotal = ref(0)
const rsAsof = ref<string | null>(null)
const rsQuery = reactive({
  keyword: '',
  date: '' as string | '',
  min_rating: null as number | null,
  page: 1,
  page_size: 20
})
const rsForceLoading = ref(false)
const rsForceStatus = ref('')
const rsForceRange = ref<[string, string] | null>(null)
let rsForcePollTimer: ReturnType<typeof setTimeout> | null = null

function formatRoc(v: unknown): string {
  if (v == null || Number.isNaN(Number(v))) return '--'
  return `${(Number(v) * 100).toFixed(2)}%`
}

function rsToneClass(rating: unknown): string {
  const r = rating == null ? null : Number(rating)
  if (r == null || Number.isNaN(r)) return 'rs-na'
  if (r >= 70) return 'rs-strong'
  if (r >= 50) return 'rs-mid'
  return 'rs-weak'
}

const loadRsList = async () => {
  rsLoading.value = true
  try {
    const res = await stockBasicService.getRsRatings({
      keyword: rsQuery.keyword || undefined,
      date: rsQuery.date || undefined,
      min_rating: rsQuery.min_rating,
      page: rsQuery.page,
      page_size: rsQuery.page_size
    })
    rsRows.value = res.data || []
    rsTotal.value = res.total || 0
    rsAsof.value = res.asof || null
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || 'RS 列表加载失败')
  } finally {
    rsLoading.value = false
  }
}

const searchRsList = () => {
  rsQuery.page = 1
  loadRsList()
}

const rsTraceVisible = ref(false)
const rsTraceLoading = ref(false)
const rsTraceRows = ref<any[]>([])
const rsTraceMeta = ref('')
const rsTraceForm = reactive({
  code: '',
  start_date: '' as string | '',
  end_date: '' as string | ''
})

function openRsTrace(row?: { code?: string; name?: string | null }) {
  rsTraceForm.code = String(row?.code || rsTraceForm.code || '').trim()
  rsTraceVisible.value = true
  rsTraceMeta.value = ''
  rsTraceRows.value = []
  if (rsTraceForm.code) {
    void loadRsTrace()
  }
}

async function loadRsTrace() {
  const code = String(rsTraceForm.code || '').trim()
  if (!code) {
    ElMessage.warning('请输入股票代码')
    return
  }
  rsTraceLoading.value = true
  try {
    const res = await stockBasicService.getRsRatingHistory({
      code,
      start_date: rsTraceForm.start_date || undefined,
      end_date: rsTraceForm.end_date || undefined,
      limit: 200
    })
    rsTraceRows.value = res.data || []
    rsTraceMeta.value = `${res.code}${res.name ? ' ' + res.name : ''} · ${res.count || 0} 条`
    if (!rsTraceRows.value.length) {
      ElMessage.info(res.message || '暂无历史记录')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '历史追溯失败')
  } finally {
    rsTraceLoading.value = false
  }
}

function openPublicRsTrace() {
  const code = String(rsTraceForm.code || '').trim()
  if (!code) return
  window.open(stockRsTraceUrl(code), '_blank')
}

async function pollRsForceTask(taskId: string, reloadList: boolean, reloadTrace: boolean) {
  try {
    const res = await stockBasicService.getRsForcePrecomputeTask(taskId)
    const t = res.data || ({} as any)
    rsForceStatus.value = `${t.message || t.status || ''}${t.progress != null ? ` ${t.progress}%` : ''}`.trim()
    if (t.status === 'completed') {
      rsForcePollTimer = null
      rsForceLoading.value = false
      ElMessage.success(t.message || '强制预计算完成')
      if (reloadList) await loadRsList()
      if (reloadTrace && rsTraceForm.code) await loadRsTrace()
      return
    }
    if (t.status === 'failed') {
      rsForcePollTimer = null
      rsForceLoading.value = false
      ElMessage.error(t.message || t.error || '强制预计算失败')
      return
    }
    rsForcePollTimer = setTimeout(() => {
      void pollRsForceTask(taskId, reloadList, reloadTrace)
    }, 2000)
  } catch (e: any) {
    rsForcePollTimer = null
    rsForceLoading.value = false
    rsForceStatus.value = e?.response?.data?.detail || e?.message || '轮询失败'
  }
}

async function runRsForcePrecompute(
  range: { start_date?: string; end_date?: string; trade_date?: string },
  opts: { reloadList: boolean; reloadTrace: boolean }
) {
  const start = (range.start_date || '').trim()
  const end = (range.end_date || '').trim()
  const single = (range.trade_date || '').trim()
  let tip = '将对行情最新交易日执行全市场 RS 截面重算（可能耗时数分钟）。确认？'
  if (start && end) {
    tip = `将对 ${start} ~ ${end} 区间内各交易日执行全市场 RS 截面重算（单次最多 10 个交易日，可能较久）。确认？`
  } else if (single) {
    tip = `将对交易日 ${single} 执行全市场 RS 截面重算（可能耗时数分钟）。确认？`
  }
  try {
    await ElMessageBox.confirm(tip, '强制重算 RS', { type: 'warning' })
  } catch {
    return
  }
  if (rsForcePollTimer) {
    clearTimeout(rsForcePollTimer)
    rsForcePollTimer = null
  }
  rsForceLoading.value = true
  rsForceStatus.value = '启动中…'
  try {
    const body: { trade_date?: string; start_date?: string; end_date?: string } = {}
    if (start && end) {
      body.start_date = start
      body.end_date = end
    } else if (single) {
      body.trade_date = single
    }
    const res = await stockBasicService.startRsForcePrecompute(body)
    rsForceStatus.value = res.message || '已启动'
    await pollRsForceTask(res.task_id, opts.reloadList, opts.reloadTrace)
  } catch (e: any) {
    rsForceLoading.value = false
    const msg = e?.response?.data?.detail || e?.message || '启动失败'
    rsForceStatus.value = msg
    ElMessage.error(msg)
  }
}

function resolveForceRange(): { start_date?: string; end_date?: string; trade_date?: string } | null {
  const r = rsForceRange.value
  if (r && r[0] && r[1]) {
    if (r[0] > r[1]) {
      ElMessage.warning('重算起始日不能晚于结束日')
      return null
    }
    return { start_date: r[0], end_date: r[1] }
  }
  const asof = String(rsQuery.date || rsAsof.value || '').trim()
  if (asof) return { trade_date: asof }
  return {}
}

function forceRsPrecompute() {
  const range = resolveForceRange()
  if (range == null) return
  void runRsForcePrecompute(range, { reloadList: true, reloadTrace: false })
}

function forceRsPrecomputeFromTrace() {
  const r = rsForceRange.value
  if (r && r[0] && r[1]) {
    if (r[0] > r[1]) {
      ElMessage.warning('重算起始日不能晚于结束日')
      return
    }
    void runRsForcePrecompute(
      { start_date: r[0], end_date: r[1] },
      { reloadList: true, reloadTrace: true }
    )
    return
  }
  const start = String(rsTraceForm.start_date || '').trim()
  const end = String(rsTraceForm.end_date || '').trim()
  if (start && end) {
    void runRsForcePrecompute(
      { start_date: start, end_date: end },
      { reloadList: true, reloadTrace: true }
    )
    return
  }
  if ((start && !end) || (!start && end)) {
    ElMessage.warning('请选择完整的强制重算区间，或在追溯查询中同时填写起止日')
    return
  }
  const asof = String(rsQuery.date || rsAsof.value || '').trim()
  void runRsForcePrecompute(
    asof ? { trade_date: asof } : {},
    { reloadList: true, reloadTrace: true }
  )
}

watch(subTab, (t) => {
  if (t === 'query') loadList()
  if (t === 'rs') loadRsList()
})

onMounted(() => {
  loadList()
  loadPipelineStatus()
})
</script>

<style scoped>
.page-header {
  margin-bottom: 12px;
}
.rs-strong {
  color: #b91c1c;
  font-weight: 700;
}
.rs-mid {
  color: #c2410c;
  font-weight: 600;
}
.rs-weak {
  color: #166534;
  font-weight: 600;
}
.rs-na {
  color: #94a3b8;
}
.rs-force-status {
  margin: 0 0 12px;
  color: #64748b;
  font-size: 13px;
}
.rs-force-status.inline {
  margin-left: 12px;
}
</style>
