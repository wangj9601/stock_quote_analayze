<template>
  <div class="board-constituents-view space-y-4">
    <div class="page-header">
      <h1 class="text-xl font-semibold">板块成分股维护</h1>
      <p class="text-sm text-gray-500 mt-1">
        维护东财行业板块与概念板块的成分股映射；支持板块信息编辑、东财同步、全量/单板 Excel 导入导出、单个录入与手动增删。
      </p>
    </div>

    <el-radio-group v-model="boardType" class="mb-2" @change="onBoardTypeChange">
      <el-radio-button label="industry">行业板块</el-radio-button>
      <el-radio-button label="concept">概念板块</el-radio-button>
    </el-radio-group>

    <el-row :gutter="16">
      <el-col :span="9">
        <el-card shadow="never">
          <template #header>
            <div class="flex flex-wrap items-center justify-between gap-2">
              <span class="font-semibold">板块列表</span>
              <div class="flex gap-2">
                <el-button size="small" type="primary" @click="openBoardEditDialog()">新增板块</el-button>
                <el-button
                  v-if="boardType === 'concept'"
                  size="small"
                  type="danger"
                  plain
                  :disabled="!selectedBoardRows.length"
                  :loading="deletingBoardsBatch"
                  @click="removeSelectedBoards"
                >
                  删除选中
                </el-button>
                <el-button size="small" :loading="exportingAll" @click="exportAllConstituents">
                  导出全部
                </el-button>
                <el-button size="small" type="primary" plain @click="openImportAllDialog">
                  导入全部
                </el-button>
                <el-button size="small" :loading="syncingBoards" @click="syncAllBoards">
                  {{ boardType === 'concept' ? '同步列表+成分' : '同步全部成分' }}
                </el-button>
              </div>
            </div>
          </template>
          <el-input
            v-model="boardKeyword"
            placeholder="板块代码/名称"
            clearable
            class="mb-3"
            @keyup.enter="loadBoards"
          />
          <el-button type="primary" size="small" :loading="boardsLoading" @click="loadBoards">查询</el-button>
          <el-table
            ref="boardTableRef"
            :data="boards"
            v-loading="boardsLoading"
            size="small"
            highlight-current-row
            class="mt-3"
            max-height="520"
            row-key="board_code"
            @current-change="onSelectBoard"
            @selection-change="onBoardSelectionChange"
          >
            <el-table-column
              v-if="boardType === 'concept'"
              type="selection"
              width="42"
              reserve-selection
            />
            <el-table-column prop="board_code" label="代码" width="88" />
            <el-table-column prop="board_name" label="名称" min-width="100" show-overflow-tooltip />
            <el-table-column prop="constituent_count" label="成分数" width="72" align="right" />
            <el-table-column label="操作" width="108" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click.stop="openBoardEditDialog(row)">编辑</el-button>
                <el-button link type="primary" size="small" @click.stop="syncOneBoard(row.board_code)">同步</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="mt-3 flex justify-end">
            <el-pagination
              v-model:current-page="boardPage"
              v-model:page-size="boardPageSize"
              :total="boardTotal"
              layout="total, prev, pager, next"
              small
              @current-change="loadBoards"
            />
          </div>
        </el-card>
      </el-col>

      <el-col :span="15">
        <el-card shadow="never">
          <template #header>
            <div class="flex flex-wrap items-center justify-between gap-2">
              <span class="font-semibold">
                成分股
                <template v-if="selectedBoard">
                  — {{ selectedBoard.board_name || selectedBoard.board_code }}
                  <span class="text-gray-400 text-sm">({{ selectedBoard.board_code }})</span>
                </template>
              </span>
              <div v-if="selectedBoard" class="flex flex-wrap gap-2">
                <el-button size="small" type="primary" @click="openSingleAddDialog">单个录入</el-button>
                <el-button size="small" type="primary" plain @click="openImportDialog">Excel 导入</el-button>
                <el-button size="small" :disabled="!selectedRows.length" @click="removeSelected">删除选中</el-button>
                <el-button size="small" type="danger" plain @click="clearBoard">清空本板</el-button>
                <el-button size="small" :loading="syncingBoard" @click="syncOneBoard(selectedBoard.board_code)">
                  东财同步
                </el-button>
              </div>
            </div>
          </template>

          <el-empty v-if="!selectedBoard" description="请从左侧选择板块" />
          <template v-else>
            <el-input
              v-model="stockKeyword"
              placeholder="股票代码/名称"
              clearable
              class="mb-3 max-w-xs"
              @keyup.enter="loadConstituents"
            />
            <el-button size="small" :loading="stocksLoading" @click="loadConstituents">查询</el-button>
            <el-table
              :data="constituents"
              v-loading="stocksLoading"
              size="small"
              class="mt-3"
              max-height="480"
              @selection-change="(rows: BoardConstituentRow[]) => (selectedRows = rows)"
            >
              <el-table-column type="selection" width="42" />
              <el-table-column prop="stock_code" label="代码" width="100" />
              <el-table-column prop="stock_name" label="名称" min-width="120" show-overflow-tooltip />
              <el-table-column prop="updated_at" label="更新时间" width="170" />
            </el-table>
            <div class="mt-3 flex justify-end">
              <el-pagination
                v-model:current-page="stockPage"
                v-model:page-size="stockPageSize"
                :total="stockTotal"
                :page-sizes="[50, 100, 200]"
                layout="total, sizes, prev, pager, next"
                small
                @current-change="loadConstituents"
                @size-change="loadConstituents"
              />
            </div>
          </template>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog
      v-model="boardEditVisible"
      :title="boardEditForm.original_board_code ? '编辑板块' : '新增板块'"
      width="460px"
      @closed="resetBoardEditForm"
      @opened="onBoardEditDialogOpened"
    >
      <el-form label-width="88px" @submit.prevent>
        <el-form-item label="板块代码" :required="!isConceptBoardCreate">
          <div class="flex gap-2 w-full">
            <el-input
              v-model="boardEditForm.board_code"
              :placeholder="isConceptBoardCreate ? '保存时自动生成' : '如 BK0428 或 IT服务'"
              :readonly="isConceptBoardCreate"
              :clearable="!isConceptBoardCreate"
              class="flex-1"
            />
            <el-button
              v-if="isConceptBoardCreate"
              size="default"
              :loading="loadingNextBoardCode"
              @click="refreshConceptBoardCode"
            >
              换一个
            </el-button>
          </div>
          <p v-if="isConceptBoardCreate" class="text-xs text-gray-500 mt-1">
            概念板块将按 BK+数字 规则自动生成，也可点「换一个」预览下一编码。
          </p>
        </el-form-item>
        <el-form-item label="板块名称">
          <el-input
            ref="boardNameInputRef"
            v-model="boardEditForm.board_name"
            placeholder="展示名称"
            clearable
            @keyup.enter="submitBoardEdit"
          />
        </el-form-item>
        <p v-if="boardEditForm.original_board_code" class="text-xs text-gray-500">
          修改代码将同步更新该板块下全部成分股的 board_code。
        </p>
      </el-form>
      <template #footer>
        <el-button
          v-if="boardEditForm.original_board_code"
          type="danger"
          plain
          :loading="deletingBoard"
          @click="deleteBoardInfo"
        >
          删除板块
        </el-button>
        <el-button @click="boardEditVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingBoard" @click="submitBoardEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="singleAddVisible" title="单个录入成分股" width="420px" @closed="resetSingleAddForm">
      <el-form label-width="88px" @submit.prevent>
        <el-form-item label="股票代码" required>
          <el-input v-model="singleAddForm.stock_code" placeholder="6位A股代码，如 000001" clearable />
        </el-form-item>
        <el-form-item label="股票名称">
          <el-input v-model="singleAddForm.stock_name" placeholder="可选，便于展示" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="singleAddVisible = false">取消</el-button>
        <el-button type="primary" :loading="adding" @click="submitSingleAdd">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="importAllVisible" title="全量导入成分股" width="560px" @closed="resetImportAllForm">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="mb-4"
        :title="boardType === 'concept'
          ? '文件需含「板块代码」列及「股票代码」或「名称」列；概念板块导入前将清空原有全部板块与成分股，再写入本次数据。可先导出全部再编辑后回导。'
          : '文件需含「板块代码」列及「股票代码」或「名称」列；可先导出全部再编辑后回导。'"
      />
      <div class="mb-3 flex flex-wrap gap-2">
        <el-button size="small" @click="downloadAllTemplate('xlsx')">下载 XLSX 模板</el-button>
        <el-button size="small" @click="downloadAllTemplate('csv')">下载 CSV 模板</el-button>
      </div>
      <el-upload
        :auto-upload="false"
        :limit="1"
        accept=".xlsx,.xls,.csv"
        :on-change="onImportAllFileChange"
        :on-remove="() => (importAllFile = null)"
      >
        <template #trigger>
          <el-button type="primary" plain>选择文件</el-button>
        </template>
      </el-upload>
      <el-card v-if="importAllResult" class="mt-4" shadow="never">
        <div class="text-sm">{{ importAllResult.message }}</div>
        <div v-if="importAllResult.board_stats?.length" class="mt-2 text-xs text-gray-500">
          <div v-for="(bs, i) in importAllResult.board_stats.slice(0, 8)" :key="i">
            {{ bs.board_code }}：有效 {{ bs.processed }}，新增 {{ bs.added }}
          </div>
        </div>
        <div v-if="importAllResult.issues?.length" class="mt-2 text-xs text-amber-600">
          <div v-for="(it, i) in importAllResult.issues.slice(0, 5)" :key="i">
            第 {{ it.row_no }} 行：{{ it.message }}
          </div>
        </div>
      </el-card>
      <template #footer>
        <el-button @click="importAllVisible = false">关闭</el-button>
        <el-button
          type="primary"
          :loading="importingAll"
          :disabled="!importAllFile"
          @click="submitImportAll"
        >
          开始导入
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="importVisible" title="Excel / CSV 导入成分股" width="520px" @closed="resetImportForm">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="mb-4"
        title="请先选择左侧板块。文件需含「股票代码」列，可选「股票名称」列；支持 .xlsx / .csv。"
      />
      <div class="mb-3 flex flex-wrap gap-2">
        <el-button size="small" @click="downloadTemplate('xlsx')">下载 XLSX 模板</el-button>
        <el-button size="small" @click="downloadTemplate('csv')">下载 CSV 模板</el-button>
      </div>
      <el-upload
        :auto-upload="false"
        :limit="1"
        accept=".xlsx,.xls,.csv"
        :on-change="onImportFileChange"
        :on-remove="() => (importFile = null)"
      >
        <template #trigger>
          <el-button type="primary" plain>选择文件</el-button>
        </template>
      </el-upload>
      <el-card v-if="importResult" class="mt-4" shadow="never">
        <div class="text-sm">{{ importResult.message }}</div>
        <div v-if="importResult.issues?.length" class="mt-2 text-xs text-amber-600">
          <div v-for="(it, i) in importResult.issues.slice(0, 5)" :key="i">
            第 {{ it.row_no }} 行：{{ it.message }}
          </div>
        </div>
      </el-card>
      <template #footer>
        <el-button @click="importVisible = false">关闭</el-button>
        <el-button type="primary" :loading="importing" :disabled="!importFile" @click="submitImport">
          开始导入
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { TableInstance } from 'element-plus'
import {
  boardConstituentsService,
  type BoardType,
  type BoardSummary,
  type BoardConstituentRow,
} from '@/services/boardConstituents.service'

const boardType = ref<BoardType>('industry')
const boardKeyword = ref('')
const boardPage = ref(1)
const boardPageSize = ref(30)
const boardTotal = ref(0)
const boards = ref<BoardSummary[]>([])
const boardsLoading = ref(false)
const selectedBoard = ref<BoardSummary | null>(null)
const selectedBoardRows = ref<BoardSummary[]>([])
const deletingBoardsBatch = ref(false)
const boardTableRef = ref<TableInstance | null>(null)

const stockKeyword = ref('')
const stockPage = ref(1)
const stockPageSize = ref(50)
const stockTotal = ref(0)
const constituents = ref<BoardConstituentRow[]>([])
const stocksLoading = ref(false)
const selectedRows = ref<BoardConstituentRow[]>([])

const syncingBoards = ref(false)
const syncingBoard = ref(false)
const exportingAll = ref(false)
const singleAddVisible = ref(false)
const importVisible = ref(false)
const importAllVisible = ref(false)
const adding = ref(false)
const importing = ref(false)
const importingAll = ref(false)
const singleAddForm = reactive({ stock_code: '', stock_name: '' })
const importFile = ref<File | null>(null)
const importAllFile = ref<File | null>(null)
const importResult = ref<{
  message: string
  issues?: Array<{ row_no: number; message: string }>
} | null>(null)
const importAllResult = ref<{
  message: string
  issues?: Array<{ row_no: number; message: string }>
  board_stats?: Array<{ board_code: string; processed: number; added: number }>
} | null>(null)

const boardEditVisible = ref(false)
const boardNameInputRef = ref<{ focus: () => void } | null>(null)
const savingBoard = ref(false)
const deletingBoard = ref(false)
const loadingNextBoardCode = ref(false)
const boardEditForm = reactive({
  board_code: '',
  board_name: '',
  original_board_code: '' as string,
})

const isConceptBoardCreate = computed(
  () => boardType.value === 'concept' && !boardEditForm.original_board_code,
)

function onBoardTypeChange() {
  selectedBoard.value = null
  selectedBoardRows.value = []
  constituents.value = []
  boardPage.value = 1
  void loadBoards()
}

function onBoardSelectionChange(rows: BoardSummary[]) {
  selectedBoardRows.value = rows
}

async function loadBoards() {
  boardsLoading.value = true
  try {
    const res = await boardConstituentsService.listBoards({
      boardType: boardType.value,
      keyword: boardKeyword.value.trim() || undefined,
      page: boardPage.value,
      pageSize: boardPageSize.value,
    })
    boards.value = res.data || []
    boardTotal.value = res.total || 0
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载板块列表失败')
  } finally {
    boardsLoading.value = false
  }
}

function onSelectBoard(row: BoardSummary | null) {
  if (!row) return
  selectedBoard.value = row
  stockPage.value = 1
  selectedRows.value = []
  void loadConstituents()
}

async function loadConstituents() {
  if (!selectedBoard.value) return
  stocksLoading.value = true
  try {
    const res = await boardConstituentsService.listConstituents({
      boardType: boardType.value,
      boardCode: selectedBoard.value.board_code,
      keyword: stockKeyword.value.trim() || undefined,
      page: stockPage.value,
      pageSize: stockPageSize.value,
    })
    constituents.value = res.data || []
    stockTotal.value = res.total || 0
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载成分股失败')
  } finally {
    stocksLoading.value = false
  }
}

function openBoardEditDialog(row?: BoardSummary) {
  if (row) {
    boardEditForm.board_code = row.board_code
    boardEditForm.board_name = row.board_name || ''
    boardEditForm.original_board_code = row.board_code
  } else {
    boardEditForm.board_code = ''
    boardEditForm.board_name = ''
    boardEditForm.original_board_code = ''
  }
  boardEditVisible.value = true
  if (!row && boardType.value === 'concept') {
    void refreshConceptBoardCode()
  }
}

function onBoardEditDialogOpened() {
  if (boardEditForm.original_board_code) return
  setTimeout(() => boardNameInputRef.value?.focus(), 50)
}

async function refreshConceptBoardCode() {
  loadingNextBoardCode.value = true
  try {
    const after = boardEditForm.board_code.trim() || undefined
    const res = await boardConstituentsService.getNextBoardCode('concept', after)
    const next = res.data?.board_code || ''
    if (next && next === after) {
      ElMessage.info('暂无更大的可用编码，已保留当前预览')
      return
    }
    boardEditForm.board_code = next
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '获取编码失败')
  } finally {
    loadingNextBoardCode.value = false
  }
}

function resetBoardEditForm() {
  boardEditForm.board_code = ''
  boardEditForm.board_name = ''
  boardEditForm.original_board_code = ''
}

async function submitBoardEdit() {
  if (savingBoard.value) return
  const code = boardEditForm.board_code.trim()
  if (!isConceptBoardCreate.value && !code) {
    ElMessage.warning('请填写板块代码')
    return
  }
  savingBoard.value = true
  try {
    const res = await boardConstituentsService.saveBoard({
      boardType: boardType.value,
      boardCode: code || undefined,
      boardName: boardEditForm.board_name.trim() || undefined,
      originalBoardCode: boardEditForm.original_board_code || undefined,
    })
    ElMessage.success(res.message || '已保存')
    boardEditVisible.value = false
    const isCreate = !boardEditForm.original_board_code || res.data?.action === 'create'
    const prevSelected = selectedBoard.value?.board_code
    if (isCreate) {
      boardPage.value = 1
    }
    await loadBoards()
    const newCode = res.data?.board_code || code
    if (isCreate) {
      const hit = boards.value.find((b) => b.board_code === newCode)
      if (hit) {
        selectedBoard.value = hit
        stockPage.value = 1
        selectedRows.value = []
        await loadConstituents()
      }
    } else if (
      prevSelected &&
      (prevSelected === boardEditForm.original_board_code || prevSelected === code)
    ) {
      const hit = boards.value.find((b) => b.board_code === newCode)
      if (hit) {
        selectedBoard.value = hit
        await loadConstituents()
      } else {
        selectedBoard.value = null
        constituents.value = []
      }
    }
  } catch (e: unknown) {
    const msg =
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
      (e instanceof Error ? e.message : '保存失败')
    ElMessage.error(msg)
  } finally {
    savingBoard.value = false
  }
}

async function deleteBoardInfo() {
  if (!boardEditForm.original_board_code) return
  try {
    await ElMessageBox.confirm(
      `确定删除板块「${boardEditForm.original_board_code}」及其全部成分股？不可恢复。`,
      '删除确认',
      { type: 'warning' },
    )
    deletingBoard.value = true
    const res = await boardConstituentsService.deleteBoard({
      boardType: boardType.value,
      boardCode: boardEditForm.original_board_code,
    })
    ElMessage.success(res.message || '已删除')
    boardEditVisible.value = false
    if (selectedBoard.value?.board_code === boardEditForm.original_board_code) {
      selectedBoard.value = null
      constituents.value = []
    }
    await loadBoards()
  } catch (e: unknown) {
    if (e !== 'cancel') ElMessage.error(e instanceof Error ? e.message : '删除失败')
  } finally {
    deletingBoard.value = false
  }
}

async function removeSelectedBoards() {
  if (boardType.value !== 'concept' || !selectedBoardRows.value.length) return
  const codes = selectedBoardRows.value.map((r) => r.board_code).filter(Boolean)
  if (!codes.length) return
  const preview = codes.slice(0, 8).join('、')
  const suffix = codes.length > 8 ? ` 等 ${codes.length} 个` : ''
  try {
    await ElMessageBox.confirm(
      `确定删除概念板块 ${preview}${suffix} 及其全部成分股？不可恢复。`,
      '批量删除确认',
      { type: 'warning' },
    )
    deletingBoardsBatch.value = true
    const res = await boardConstituentsService.deleteBoardsBatch({
      boardType: 'concept',
      boardCodes: codes,
    })
    ElMessage.success(res.message || '已删除')
    const deletedSet = new Set(codes)
    if (selectedBoard.value && deletedSet.has(selectedBoard.value.board_code)) {
      selectedBoard.value = null
      constituents.value = []
    }
    selectedBoardRows.value = []
    boardTableRef.value?.clearSelection()
    await loadBoards()
  } catch (e: unknown) {
    const msg =
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
      (e instanceof Error ? e.message : '删除失败')
    if (e !== 'cancel') ElMessage.error(msg)
  } finally {
    deletingBoardsBatch.value = false
  }
}

function openSingleAddDialog() {
  singleAddVisible.value = true
}

function resetSingleAddForm() {
  singleAddForm.stock_code = ''
  singleAddForm.stock_name = ''
}

function openImportAllDialog() {
  importAllVisible.value = true
}

function resetImportAllForm() {
  importAllFile.value = null
  importAllResult.value = null
}

function onImportAllFileChange(uploadFile: { raw?: File }) {
  importAllFile.value = uploadFile.raw || null
  importAllResult.value = null
}

async function downloadAllTemplate(format: 'csv' | 'xlsx') {
  try {
    const blob = await boardConstituentsService.downloadAllImportTemplate(format)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `board_constituents_all_template.${format}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('模板下载失败')
  }
}

async function exportAllConstituents() {
  exportingAll.value = true
  try {
    const blob = await boardConstituentsService.exportAll({ boardType: boardType.value, format: 'xlsx' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const prefix = boardType.value === 'industry' ? 'industry' : 'concept'
    a.download = `${prefix}_board_constituents_all.xlsx`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success('导出完成')
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '导出失败')
  } finally {
    exportingAll.value = false
  }
}

async function submitImportAll() {
  if (!importAllFile.value) return
  importingAll.value = true
  try {
    const res = await boardConstituentsService.importAllFromFile({
      boardType: boardType.value,
      file: importAllFile.value,
    })
    if (!res.success) {
      ElMessage.warning(res.message || '导入未完成')
      importAllResult.value = {
        message: res.message || '导入失败',
        issues: res.data?.issues,
        board_stats: res.data?.board_stats,
      }
      return
    }
    importAllResult.value = {
      message: res.message || '导入完成',
      issues: res.data?.issues,
      board_stats: res.data?.board_stats,
    }
    ElMessage.success(res.message || '导入完成')
    await loadBoards()
    if (selectedBoard.value) await loadConstituents()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '导入失败')
  } finally {
    importingAll.value = false
  }
}

function openImportDialog() {
  if (!selectedBoard.value) {
    ElMessage.warning('请先从左侧选择板块')
    return
  }
  importVisible.value = true
}

function resetImportForm() {
  importFile.value = null
  importResult.value = null
}

function onImportFileChange(uploadFile: { raw?: File }) {
  importFile.value = uploadFile.raw || null
  importResult.value = null
}

async function downloadTemplate(format: 'csv' | 'xlsx') {
  try {
    const blob = await boardConstituentsService.downloadImportTemplate(format)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `board_constituents_template.${format}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('模板下载失败')
  }
}

async function submitSingleAdd() {
  if (!selectedBoard.value) return
  const code = singleAddForm.stock_code.trim()
  if (!code) {
    ElMessage.warning('请填写股票代码')
    return
  }
  adding.value = true
  try {
    const res = await boardConstituentsService.addStocks({
      boardType: boardType.value,
      boardCode: selectedBoard.value.board_code,
      stocks: [
        {
          stock_code: code,
          stock_name: singleAddForm.stock_name.trim() || undefined,
        },
      ],
    })
    ElMessage.success(res.message || '已保存')
    singleAddVisible.value = false
    await loadConstituents()
    await loadBoards()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    adding.value = false
  }
}

async function submitImport() {
  if (!selectedBoard.value || !importFile.value) return
  importing.value = true
  try {
    const res = await boardConstituentsService.importFromFile({
      boardType: boardType.value,
      boardCode: selectedBoard.value.board_code,
      file: importFile.value,
    })
    if (!res.success) {
      ElMessage.warning(res.message || '导入未完成')
      importResult.value = {
        message: res.message || '导入失败',
        issues: res.data?.issues,
      }
      return
    }
    importResult.value = {
      message: res.message || '导入完成',
      issues: res.data?.issues,
    }
    ElMessage.success(res.message || '导入完成')
    await loadConstituents()
    await loadBoards()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '导入失败')
  } finally {
    importing.value = false
  }
}

async function removeSelected() {
  if (!selectedBoard.value || !selectedRows.value.length) return
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${selectedRows.value.length} 只成分股？`, '删除确认', {
      type: 'warning',
    })
    const res = await boardConstituentsService.removeStocks({
      boardType: boardType.value,
      boardCode: selectedBoard.value.board_code,
      scope: 'selected',
      stockCodes: selectedRows.value.map((r) => r.stock_code),
    })
    ElMessage.success(res.message || '已删除')
    selectedRows.value = []
    await loadConstituents()
    await loadBoards()
  } catch (e: unknown) {
    if (e !== 'cancel') ElMessage.error(e instanceof Error ? e.message : '删除失败')
  }
}

async function clearBoard() {
  if (!selectedBoard.value) return
  try {
    await ElMessageBox.confirm('确定清空该板块全部成分股？不可恢复。', '清空确认', { type: 'warning' })
    const res = await boardConstituentsService.removeStocks({
      boardType: boardType.value,
      boardCode: selectedBoard.value.board_code,
      scope: 'all',
    })
    ElMessage.success(res.message || '已清空')
    await loadConstituents()
    await loadBoards()
  } catch (e: unknown) {
    if (e !== 'cancel') ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}

async function syncOneBoard(boardCode: string) {
  syncingBoard.value = true
  try {
    const res = await boardConstituentsService.syncConstituents({
      boardType: boardType.value,
      boardCodes: [boardCode],
      syncBoardList: false,
    })
    ElMessage.success(res.message || '同步完成')
    if (selectedBoard.value?.board_code === boardCode) await loadConstituents()
    await loadBoards()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '同步失败')
  } finally {
    syncingBoard.value = false
  }
}

async function syncAllBoards() {
  const tip =
    boardType.value === 'concept'
      ? '将先从东财同步概念板块列表，再同步全部板块成分股（耗时较长），是否继续？'
      : '将同步全部行业板块成分股（耗时较长），是否继续？'
  try {
    await ElMessageBox.confirm(tip, '全量同步', { type: 'info' })
    syncingBoards.value = true
    const res = await boardConstituentsService.syncConstituents({
      boardType: boardType.value,
      syncBoardList: boardType.value === 'concept',
    })
    ElMessage.success(res.message || '同步完成')
    await loadBoards()
    if (selectedBoard.value) await loadConstituents()
  } catch (e: unknown) {
    if (e !== 'cancel') ElMessage.error(e instanceof Error ? e.message : '同步失败')
  } finally {
    syncingBoards.value = false
  }
}

onMounted(() => {
  void loadBoards()
})
</script>

<style scoped>
.page-header {
  margin-bottom: 0.5rem;
}
</style>
