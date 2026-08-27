<template>
  <div class="tvo-admin">
    <el-card>
      <template #header>
        <span>3倍量观察股</span>
        <div style="float: right; display: flex; gap: 8px;">
          <el-button type="warning" :loading="scanning" @click="runScan">手动爆量扫描</el-button>
          <el-button type="primary" :loading="evaluating" @click="runEval">手动策略复核</el-button>
          <el-button :loading="loading" @click="load">刷新</el-button>
          <el-button type="success" :loading="exporting" @click="doExport">导出 Excel</el-button>
        </div>
      </template>
      <el-form :inline="true" class="filter-form">
        <el-form-item label="市场">
          <el-select v-model="filters.market" placeholder="全部" clearable style="width: 100px;">
            <el-option label="A股" value="CN" />
            <el-option label="港股" value="HK" />
          </el-select>
        </el-form-item>
        <el-form-item label="板块">
          <el-select
            v-model="filters.board"
            placeholder="全部"
            clearable
            style="width: 150px"
            :disabled="filters.market === 'HK'"
          >
            <el-option label="沪深主板" value="MAIN" />
            <el-option label="创业板" value="CYB" />
            <el-option label="中小板" value="SZ_SME" />
            <el-option label="科创板" value="KCB" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 120px;">
            <el-option label="待观察" value="待观察" />
            <el-option label="观察中" value="观察中" />
            <el-option label="交易触发" value="交易触发" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">查询</el-button>
        </el-form-item>
      </el-form>
      <el-table :data="rows" v-loading="loading" border stripe>
        <el-table-column prop="market" label="市场" width="72" />
        <el-table-column prop="code" label="代码" width="100" />
        <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip />
        <el-table-column prop="observe_trade_date" label="观察日" width="110" />
        <el-table-column label="量比" width="90">
          <template #default="{ row }">
            {{ row.volume_ratio_actual != null ? Number(row.volume_ratio_actual).toFixed(2) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="vsb_evaluated_at" label="复核时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.vsb_evaluated_at) }}
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-section">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next"
          @size-change="load"
          @current-change="load"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  listTripleVolumeObserve,
  exportTripleVolumeObserveBlob,
  adminRunScan,
  adminRunEval,
  type ObserveRow
} from '@/services/triple_volume_observe.service'

const loading = ref(false)
const exporting = ref(false)
const scanning = ref(false)
const evaluating = ref(false)
const rows = ref<ObserveRow[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)

const filters = reactive<{ market?: string; status?: string; board?: string }>({
  market: undefined,
  status: undefined,
  board: undefined
})

function formatTime(v: string | undefined | null) {
  if (!v) return '-'
  return String(v).replace('T', ' ').slice(0, 19)
}

async function load() {
  loading.value = true
  try {
    const board =
      filters.market === 'HK' ? undefined : filters.board || undefined
    const market =
      board && !filters.market ? 'CN' : filters.market || undefined
    const res = await listTripleVolumeObserve({
      market,
      board,
      status: filters.status,
      page: page.value,
      page_size: pageSize.value
    })
    rows.value = res.items || []
    total.value = res.total || 0
  } catch (e: unknown) {
    const msg =
      e && typeof e === 'object' && 'response' in e
        ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : String(e)
    ElMessage.error('加载失败：' + msg)
  } finally {
    loading.value = false
  }
}

async function doExport() {
  exporting.value = true
  try {
    const board =
      filters.market === 'HK' ? undefined : filters.board || undefined
    const market =
      board && !filters.market ? 'CN' : filters.market || undefined
    const blob = await exportTripleVolumeObserveBlob({
      market,
      board,
      status: filters.status
    })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'triple_volume_observe.xlsx'
    a.click()
    URL.revokeObjectURL(a.href)
    ElMessage.success('已开始下载')
  } catch (e: unknown) {
    const msg =
      e && typeof e === 'object' && 'response' in e
        ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : String(e)
    ElMessage.error('导出失败：' + msg)
  } finally {
    exporting.value = false
  }
}

async function runScan() {
  scanning.value = true
  try {
    const data = await adminRunScan()
    ElMessage.success('扫描完成：' + JSON.stringify(data).slice(0, 200))
    await load()
  } catch (e: unknown) {
    const msg =
      e && typeof e === 'object' && 'response' in e
        ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : String(e)
    ElMessage.error('扫描失败：' + msg)
  } finally {
    scanning.value = false
  }
}

async function runEval() {
  evaluating.value = true
  try {
    const data = await adminRunEval()
    ElMessage.success('复核完成：' + JSON.stringify(data).slice(0, 200))
    await load()
  } catch (e: unknown) {
    const msg =
      e && typeof e === 'object' && 'response' in e
        ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : String(e)
    ElMessage.error('复核失败：' + msg)
  } finally {
    evaluating.value = false
  }
}

onMounted(() => {
  load()
})
</script>

<style scoped>
.tvo-admin {
  padding: 0;
}
.filter-form {
  margin-bottom: 12px;
}
.pagination-section {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
