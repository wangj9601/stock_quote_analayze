<template>
  <div class="stock-basic-view">
    <div class="page-header">
      <h1>股票基本信息管理</h1>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="基本信息查询" name="query">
        <el-card>
          <el-row :gutter="12" class="mb-4">
            <el-col :span="4">
              <el-select v-model="query.market" style="width: 100%">
                <el-option label="全部" value="ALL" />
                <el-option label="A股" value="CN" />
                <el-option label="港股" value="HK" />
              </el-select>
            </el-col>
            <el-col :span="6">
              <el-input v-model="query.keyword" placeholder="代码/名称" clearable />
            </el-col>
            <el-col :span="4">
              <el-checkbox v-model="query.empty_shares">仅缺股本</el-checkbox>
            </el-col>
            <el-col :span="4">
              <el-select v-model="collectEnabledFilter" style="width: 100%" placeholder="采集标志">
                <el-option label="全部" value="all" />
                <el-option label="启用" value="enabled" />
                <el-option label="停用" value="disabled" />
              </el-select>
            </el-col>
            <el-col :span="6">
              <el-button type="primary" :loading="loading" @click="loadList">查询</el-button>
            </el-col>
          </el-row>

          <el-table :data="rows" :loading="loading" stripe>
            <el-table-column prop="market" label="市场" width="70" />
            <el-table-column prop="code" label="代码" width="100" />
            <el-table-column prop="name" label="名称" min-width="120" />
            <el-table-column prop="total_shares" label="总股本" min-width="110" />
            <el-table-column prop="free_float_shares" label="流通股本" min-width="110" />
            <el-table-column prop="industry" label="行业" min-width="110" />
            <el-table-column prop="listing_date" label="上市日期" min-width="100" />
            <el-table-column prop="shares_updated_at" label="更新时间" min-width="170" />
            <el-table-column label="采集/处理" min-width="120">
              <template #default="scope">
                <el-switch
                  :model-value="scope.row.collect_enabled"
                  @change="(v:boolean)=>toggleCollectFlag(scope.row, v)"
                />
              </template>
            </el-table-column>
          </el-table>

          <div class="mt-4 flex justify-end">
            <el-pagination
              v-model:current-page="query.page"
              v-model:page-size="query.page_size"
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

          <el-upload
            :auto-upload="false"
            :show-file-list="true"
            :on-change="onFileChange"
            :limit="1"
            accept=".csv,.xlsx"
          >
            <template #trigger>
              <el-button type="primary">选择导入文件</el-button>
            </template>
          </el-upload>

          <div class="mt-4">
            <el-button :disabled="!selectedFile" :loading="validating" @click="validateFile">预校验</el-button>
            <el-button :disabled="!selectedFile" :loading="executing" @click="executeImport(false)">执行导入</el-button>
            <el-button :disabled="!selectedFile" :loading="executing" @click="executeImport(true)">Dry Run</el-button>
          </div>

          <el-alert class="mt-4" type="info" :closable="false" show-icon
            title="导入策略：仅补空值（默认不覆盖已有非空字段），支持 A股+港股，支持 CSV/XLSX。"
          />

          <el-card v-if="validateResult" class="mt-4">
            <template #header>预校验结果</template>
            <div>有效行：{{ validateResult.valid_rows }}，无效行：{{ validateResult.invalid_rows }}</div>
            <div>市场分布：A股 {{ validateResult.market_count?.CN || 0 }}，港股 {{ validateResult.market_count?.HK || 0 }}</div>
            <el-table :data="validateResult.issues || []" size="small" class="mt-3">
              <el-table-column prop="row_no" label="行号" width="80" />
              <el-table-column prop="code" label="代码" width="120" />
              <el-table-column prop="message" label="错误信息" min-width="220" />
            </el-table>
          </el-card>

          <el-card v-if="executeResult" class="mt-4">
            <template #header>导入结果</template>
            <div>
              总行数 {{ executeResult.total_rows }}，成功 {{ executeResult.success }}，
              跳过 {{ executeResult.skipped }}，失败 {{ executeResult.failed }}
            </div>
            <el-table :data="executeResult.failed_sample || []" size="small" class="mt-3">
              <el-table-column prop="row_no" label="行号" width="80" />
              <el-table-column prop="code" label="代码" width="120" />
              <el-table-column prop="message" label="错误信息" min-width="220" />
            </el-table>
          </el-card>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { stockBasicService } from '@/services/stockBasic.service'

const activeTab = ref('query')
const loading = ref(false)
const validating = ref(false)
const executing = ref(false)
const rows = ref<any[]>([])
const total = ref(0)
const selectedFile = ref<File | null>(null)
const validateResult = ref<any>(null)
const executeResult = ref<any>(null)
const pipelineStatus = ref<any>(null)
const collectEnabledFilter = ref<'all' | 'enabled' | 'disabled'>('all')

const query = reactive({
  market: 'ALL' as 'ALL' | 'CN' | 'HK',
  keyword: '',
  empty_shares: false,
  page: 1,
  page_size: 20
})

const loadList = async () => {
  loading.value = true
  try {
    const collectEnabled =
      collectEnabledFilter.value === 'all'
        ? null
        : collectEnabledFilter.value === 'enabled'
          ? true
          : false
    const res = await stockBasicService.getList({
      ...query,
      collect_enabled: collectEnabled
    })
    rows.value = res.data || []
    total.value = res.total || 0
  } catch (e: any) {
    ElMessage.error(e?.message || '查询失败')
  } finally {
    loading.value = false
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
  selectedFile.value = uploadFile.raw || null
  validateResult.value = null
  executeResult.value = null
}

const validateFile = async () => {
  if (!selectedFile.value) return
  validating.value = true
  try {
    const res = await stockBasicService.validateImport(selectedFile.value)
    validateResult.value = res.data
    ElMessage.success('预校验完成')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '预校验失败')
  } finally {
    validating.value = false
  }
}

const executeImport = async (dryRun: boolean) => {
  if (!selectedFile.value) return
  executing.value = true
  try {
    const res = await stockBasicService.executeImport(selectedFile.value, dryRun, 100)
    executeResult.value = res.data
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

onMounted(loadList)
onMounted(loadPipelineStatus)
</script>

<style scoped>
.page-header {
  margin-bottom: 12px;
}
</style>

