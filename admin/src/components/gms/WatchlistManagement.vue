<template>
  <div class="watchlist-management">
    <el-card class="toolbar">
      <el-row :gutter="12" align="middle">
        <el-col :span="6">
          <el-select v-model="selectedVersionId" placeholder="选择策略版本" filterable @change="handleVersionChange">
            <el-option v-for="v in versions" :key="v.id" :label="`${v.strategy_code}-V${v.version_no} ${v.version_name}`" :value="v.id" />
          </el-select>
        </el-col>
        <el-col :span="3">
          <el-select v-model="marketFilter" placeholder="市场" clearable @change="refresh">
            <el-option label="A股" value="A" />
            <el-option label="港股" value="HK" />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-input v-model="keyword" placeholder="代码/名称" clearable @keyup.enter="refresh" />
        </el-col>
        <el-col :span="10" class="actions">
          <el-button type="primary" @click="openVersionDialog()">新增版本</el-button>
          <el-button type="success" :disabled="!selectedVersionId" @click="openStockDialog()">新增观察股</el-button>
          <el-button :disabled="!selectedIds.length" @click="batchDelete">批量删除</el-button>
          <el-button :disabled="!selectedVersionId" @click="openImportDialog">批量导入</el-button>
          <el-button :disabled="!selectedVersionId" @click="handleExport">批量导出</el-button>
          <el-button @click="refresh">刷新</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-table v-loading="loading" :data="stocks" @selection-change="onSelectionChange">
      <el-table-column type="selection" width="42" />
      <el-table-column prop="market" label="市场" width="80" />
      <el-table-column prop="stock_code" label="代码" width="120" />
      <el-table-column prop="stock_name" label="名称" min-width="140" />
      <el-table-column label="当前价格" width="100">
        <template #default="scope">
          <span v-if="scope.row.current_price != null">
            {{ scope.row.market === 'HK' ? '$' : '¥' }}{{ scope.row.current_price.toFixed(2) }}
          </span>
          <span v-else class="text-gray-400">-</span>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100" />
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

    <el-dialog v-model="versionDialogVisible" title="策略版本" @opened="() => versionStrategyCodeRef?.focus()">
      <el-form :model="versionForm" label-width="90px">
        <el-form-item label="策略编码"><el-input ref="versionStrategyCodeRef" v-model="versionForm.strategy_code" @keyup.enter="saveVersion" /></el-form-item>
        <el-form-item label="版本名称"><el-input v-model="versionForm.version_name" @keyup.enter="saveVersion" /></el-form-item>
        <el-form-item label="版本号"><el-input-number v-model="versionForm.version_no" :min="1" @keyup.enter="saveVersion" /></el-form-item>
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

    <el-dialog v-model="importDialogVisible" title="批量导入观察股">
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
import { nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { gmsApiService, type GMSStrategyVersionStock, type GMSStrategyVersion } from '@/services/gmsApi'

const stockCodeRef = ref<any>(null)
const versionStrategyCodeRef = ref<any>(null)
const importInputRef = ref<any>(null)

const loading = ref(false)
const versions = ref<GMSStrategyVersion[]>([])
const selectedVersionId = ref<number>()
const stocks = ref<GMSStrategyVersionStock[]>([])
const selectedIds = ref<number[]>([])
const keyword = ref('')
const marketFilter = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const versionDialogVisible = ref(false)
const editingVersionId = ref<number | null>(null)
const versionForm = ref({ strategy_code: 'GMS', version_name: '', version_no: 1, description: '', is_active: true, created_by: 'admin' })

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

const loadVersions = async () => {
  const res = await gmsApiService.getStrategyVersions({ page: 1, page_size: 200 })
  versions.value = res.data || []
  if (!selectedVersionId.value && versions.value.length) {
    // 优先寻找版本号为 1 的版本
    const v1 = versions.value.find(v => v.version_no === 1)
    selectedVersionId.value = v1 ? v1.id : versions.value[0].id
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
  await refresh()
}

const onSelectionChange = (rows: GMSStrategyVersionStock[]) => {
  selectedIds.value = rows.map((v) => v.id)
}

const openVersionDialog = () => {
  editingVersionId.value = null
  versionForm.value = { strategy_code: 'GMS', version_name: '', version_no: 1, description: '', is_active: true, created_by: 'admin' }
  versionDialogVisible.value = true
}

const saveVersion = async () => {
  try {
    if (editingVersionId.value) {
      await gmsApiService.updateStrategyVersion(editingVersionId.value, versionForm.value)
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
    row.is_verified = !verified // 恢复原状态
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
  importText.value = ''
  importDialogVisible.value = true
}

const submitImport = async () => {
  if (!selectedVersionId.value) return
  const items = importText.value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [market, stock_code, stock_name] = line.split(',').map((x) => (x || '').trim())
      return { market, stock_code, stock_name }
    })
  try {
    const data = await gmsApiService.batchImportStrategyVersionStocks({ version_id: selectedVersionId.value, items })
    if (data.fail_count > 0) {
      const reasons = data.fail_details.map(f => `${f.stock_code}: ${f.reason}`).join('\n')
      await ElMessageBox.alert(`导入完成：成功${data.success_count}，失败${data.fail_count}，跳过${data.skip_count}\n失败详情：\n${reasons}`, '导入结果', { type: 'warning' })
      // 存在失败时不关闭弹窗，方便用户修改后重试
      await refresh()
    } else {
      ElMessage.success(`导入完成：成功${data.success_count}，跳过${data.skip_count}`)
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
    const size = 200 // 后端 le=200 限制
    
    // 循环获取所有数据
    while (true) {
      const res = await gmsApiService.getStrategyVersionStocks({
        version_id: selectedVersionId.value,
        page: currentPage,
        page_size: size
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

    // 生成文本内容
    const content = allStocks.map(s => `${s.market},${s.stock_code},${s.stock_name || ''}`).join('\n')
    
    // 下载文件
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    
    // 文件名包含版本信息
    const version = versions.value.find(v => v.id === selectedVersionId.value)
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
  await loadVersions()
  await refresh()
})
</script>

<style scoped>
.toolbar { margin-bottom: 12px; }
.actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
