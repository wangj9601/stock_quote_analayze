<template>
  <div class="stock-basic-view">
    <div class="page-header">
      <h1>股票基本信息管理</h1>
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
            :title="`当前为【${mainTab === 'CN' ? 'A股' : '港股'}】导入：仅处理文件中市场为 ${mainTab} 的行；策略为仅补空值。支持 CSV/XLS/XLSX（含东财 Table.xls 文本格式）。`"
          />

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
              总行数 {{ currentExecuteResult.total_rows }}，成功 {{ currentExecuteResult.success }}，
              跳过 {{ currentExecuteResult.skipped }}，失败 {{ currentExecuteResult.failed }}
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
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { stockBasicService, type DelistedFilter, type StockBasicMarket } from '@/services/stockBasic.service'

const mainTab = ref<StockBasicMarket>('CN')
const subTab = ref('query')
const loading = ref(false)
const syncingIndustry = ref(false)
const validating = ref(false)
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
    const res = await stockBasicService.executeImport(f, dryRun, 100, mainTab.value)
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

watch(subTab, (t) => {
  if (t === 'query') loadList()
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
</style>
