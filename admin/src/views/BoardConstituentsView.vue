<template>
  <div class="board-constituents-view space-y-4">
    <div class="page-header">
      <h1 class="text-xl font-semibold">板块成分股维护</h1>
      <p class="text-sm text-gray-500 mt-1">
        维护东财行业板块与概念板块的成分股映射；支持板块信息编辑、东财同步、全量/单板 Excel 导入导出、单个录入与手动增删；可按股票代码/名称反查所属板块。
      </p>
    </div>

    <el-radio-group v-model="boardType" class="mb-2" @change="onBoardTypeChange">
      <el-radio-button label="industry">行业板块</el-radio-button>
      <el-radio-button label="concept">概念板块</el-radio-button>
    </el-radio-group>

    <el-card shadow="never" class="stock-lookup-card">
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-sm text-gray-600 shrink-0">股票反查所属板块：</span>
        <el-input
          v-model="stockLookupKeyword"
          placeholder="股票代码或名称"
          clearable
          class="max-w-xs"
          @keyup.enter="lookupBoardsByStock"
        />
        <el-button type="primary" plain size="small" :loading="stockLookupLoading" @click="lookupBoardsByStock">
          查询
        </el-button>
        <span v-if="stockLookupHint" class="text-sm text-gray-500">{{ stockLookupHint }}</span>
      </div>
      <el-table
        v-if="stockLookupBoards.length"
        :data="stockLookupBoards"
        size="small"
        class="mt-3"
        highlight-current-row
        max-height="200"
        @row-click="onStockLookupBoardClick"
      >
        <el-table-column prop="board_code" label="板块代码" min-width="100" show-overflow-tooltip />
        <el-table-column prop="board_name" label="板块名称" min-width="120" show-overflow-tooltip />
        <el-table-column prop="last_updated" label="成分更新时间" width="170" />
        <el-table-column label="操作" width="72" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click.stop="onStockLookupBoardClick(row)">定位</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty
        v-else-if="stockLookupSearched && !stockLookupLoading"
        description="未找到所属板块"
        :image-size="56"
        class="mt-2 py-2"
      />
    </el-card>

    <el-row :gutter="16" class="board-panels-row">
      <el-col :span="9" class="board-panel-col">
        <el-card shadow="never" class="board-panel-card">
          <template #header>
            <div class="flex flex-wrap items-center justify-between gap-2">
              <span class="font-semibold">板块列表</span>
              <div class="flex gap-2">
                <el-button size="small" type="primary" @click="openBoardEditDialog()">新增板块</el-button>
                <el-button
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
            placeholder="板块代码/名称（BK 或中文/英文）"
            clearable
            class="mb-3"
            @keyup.enter="loadBoards"
          />
          <el-button type="primary" size="small" :loading="boardsLoading" @click="loadBoards">查询</el-button>
          <div class="board-panel-main mt-3">
            <el-table
              ref="boardTableRef"
              :data="boards"
              v-loading="boardsLoading"
              size="small"
              highlight-current-row
              height="100%"
              row-key="board_code"
              @current-change="onSelectBoard"
              @selection-change="onBoardSelectionChange"
              @select-all="onBoardSelectAll"
            >
            <!-- 不使用 reserve-selection：表头全选/取消仅作用于当前页，避免跨页累加误选 -->
            <el-table-column type="selection" width="42" />
            <el-table-column prop="board_code" label="代码" min-width="100" show-overflow-tooltip />
            <el-table-column prop="board_name" label="名称" min-width="100" show-overflow-tooltip />
            <el-table-column prop="board_code_source_label" label="代码来源" width="88" show-overflow-tooltip />
            <el-table-column prop="constituent_count" label="成分数" width="72" align="right" />
            <el-table-column label="交易观察" width="88" align="center">
              <template #default="{ row }">
                <el-switch
                  :model-value="!!row.trade_observe_flag"
                  size="small"
                  inline-prompt
                  active-text="是"
                  inactive-text="否"
                  @click.stop
                  @change="(val: boolean) => toggleBoardTradeObserve(row, val)"
                />
              </template>
            </el-table-column>
            <el-table-column label="前端显示" width="88" align="center">
              <template #default="{ row }">
                <el-switch
                  :model-value="row.frontend_visible_flag !== false"
                  size="small"
                  inline-prompt
                  active-text="是"
                  inactive-text="否"
                  @click.stop
                  @change="(val: boolean) => toggleBoardFrontendVisible(row, val)"
                />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="108" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click.stop="openBoardEditDialog(row)">编辑</el-button>
                <el-button link type="primary" size="small" @click.stop="syncOneBoard(row.board_code)">同步</el-button>
              </template>
            </el-table-column>
          </el-table>
          </div>
          <div class="mt-3 flex justify-end board-panel-footer">
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

      <el-col :span="15" class="board-panel-col">
        <el-card shadow="never" class="board-panel-card">
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

          <div v-if="!selectedBoard" class="board-panel-main board-panel-empty">
            <el-empty description="请从左侧选择板块" />
          </div>
          <template v-else>
            <el-input
              v-model="stockKeyword"
              placeholder="股票代码/名称"
              clearable
              class="mb-3 max-w-xs"
              @keyup.enter="loadConstituents"
            />
            <el-button size="small" :loading="stocksLoading" @click="loadConstituents">查询</el-button>
            <div class="board-panel-main mt-3">
              <el-table
                :data="constituents"
                v-loading="stocksLoading"
                size="small"
                height="100%"
                @selection-change="(rows: BoardConstituentRow[]) => (selectedRows = rows)"
              >
              <el-table-column type="selection" width="42" />
              <el-table-column prop="stock_code" label="代码" width="100" />
              <el-table-column prop="stock_name" label="名称" min-width="120" show-overflow-tooltip />
              <el-table-column prop="updated_at" label="更新时间" width="170" />
            </el-table>
            </div>
            <div class="mt-3 flex justify-end board-panel-footer">
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
        <el-form-item label="板块代码" :required="!isBoardCreateAutoCode">
          <div class="flex gap-2 w-full">
            <el-input
              v-model="boardEditForm.board_code"
              :placeholder="isBoardCreateAutoCode
                ? '保存时自动生成数字编码（不加 BK）'
                : (boardType === 'industry' ? '数字/BK/中文/英文' : '数字或 BK+数字，如 0428')"
              :readonly="isBoardCreateAutoCode"
              :clearable="!isBoardCreateAutoCode"
              class="flex-1"
            />
            <el-button
              v-if="isBoardCreateAutoCode"
              size="default"
              :loading="loadingNextBoardCode"
              @click="refreshBoardCode"
            >
              换一个
            </el-button>
          </div>
          <p v-if="isBoardCreateAutoCode" class="text-xs text-gray-500 mt-1">
            行业/概念板块新增时自动生成纯数字编码（不加 BK），且全局不可重复；也可点「换一个」预览。存量 BK 编码仍可继续使用。
          </p>
        </el-form-item>
        <el-form-item label="板块名称">
          <el-input
            ref="boardNameInputRef"
            v-model="boardEditForm.board_name"
            placeholder="展示名称（可与其它板块同名）"
            clearable
            @keyup.enter="submitBoardEdit"
          />
        </el-form-item>
        <el-form-item label="代码来源">
          <el-select v-model="boardEditForm.board_code_source" class="w-full" placeholder="选择板块代码来源">
            <el-option
              v-for="opt in boardCodeSourceOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
          <p class="text-xs text-gray-500 mt-1">
            标识板块代码取自哪家数据源；名称允许重复，用代码来源区分不同记录。东财同步一般为「东方财富」，手工/导入新建默认为「手动维护」。
          </p>
        </el-form-item>
        <el-form-item label="交易观察">
          <el-switch
            v-model="boardEditForm.trade_observe_flag"
            inline-prompt
            active-text="是"
            inactive-text="否"
          />
          <p class="text-xs text-gray-500 mt-1">标记后可在 GMS 等板块筛选中作为重点关注来源。</p>
        </el-form-item>
        <el-form-item label="前端显示">
          <el-switch
            v-model="boardEditForm.frontend_visible_flag"
            inline-prompt
            active-text="是"
            inactive-text="否"
          />
          <p class="text-xs text-gray-500 mt-1">关闭后网站 GMS 选股页的行业/概念板块选择器中不再展示该板块。</p>
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
          ? '请使用「导出全部」得到的 .xlsx（含 board_code 列），或下载全量模板。不支持东财单板 Table.xls（仅名称列）；单板文件请选中板块后用右侧「Excel 导入」。概念板块导入前将清空原有全部数据。'
          : '文件需含 board_code、stock_code/stock_name 列（与「导出全部」格式一致，见示意图）。板块代码须与列表中一致：若列表为 BK1028 等新编码，文件中 BK0420 等旧编码将导入到对应旧板块行，不会填充 BK1028。导入后可在列表搜索 board_code 核对成分数。'"
      />
      <el-checkbox
        v-if="boardType === 'industry'"
        v-model="importAllClearExisting"
        class="mb-3"
      >
        导入前清空全部行业板块数据（基础信息、成分股、实时行情）
      </el-checkbox>
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
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { TableInstance } from 'element-plus'
import {
  boardConstituentsService,
  type BoardType,
  type BoardSummary,
  type BoardConstituentRow,
  type BoardCodeSourceOption,
} from '@/services/boardConstituents.service'

function formatApiError(e: unknown, fallback: string): string {
  if (e === 'cancel') return ''
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === 'object' && 'msg' in item) return String((item as { msg: string }).msg)
        return String(item)
      })
      .join('；')
  }
  if (e instanceof Error && e.message) return e.message
  return fallback
}

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

const stockLookupKeyword = ref('')
const stockLookupLoading = ref(false)
const stockLookupBoards = ref<BoardSummary[]>([])
const stockLookupHint = ref('')
const stockLookupSearched = ref(false)

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
const importAllClearExisting = ref(false)
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
const boardCodeSourceOptions = ref<BoardCodeSourceOption[]>([])
const boardEditForm = reactive({
  board_code: '',
  board_name: '',
  trade_observe_flag: false,
  frontend_visible_flag: true,
  board_code_source: 'manual',
  original_board_code: '' as string,
})
const togglingTradeObserve = ref<string | null>(null)
const togglingFrontendVisible = ref<string | null>(null)

const isBoardCreateAutoCode = computed(() => !boardEditForm.original_board_code)

function isValidBoardCode(type: BoardType, code: string): boolean {
  const c = code.trim()
  if (!c) return false
  if (/^BK\d+$/i.test(c)) return true
  if (/^\d{1,20}$/.test(c)) return true
  if (type === 'industry') {
    return /^[\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9._\-·]{0,19}$/.test(c)
  }
  return false
}

function onBoardTypeChange() {
  selectedBoard.value = null
  selectedBoardRows.value = []
  constituents.value = []
  boardPage.value = 1
  stockLookupBoards.value = []
  stockLookupHint.value = ''
  stockLookupSearched.value = false
  void loadBoards()
}

function onBoardSelectionChange(rows: BoardSummary[]) {
  selectedBoardRows.value = rows
}

/** 表头全选/取消全选：仅当前页 boards，与 selectedBoardRows / 删除选中对齐 */
function onBoardSelectAll(rows: BoardSummary[]) {
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
    // 分页/查询刷新后清空勾选，保证「删除选中」只针对当前页可见选择
    selectedBoardRows.value = []
    await nextTick()
    boardTableRef.value?.clearSelection()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载板块列表失败')
  } finally {
    boardsLoading.value = false
  }
}

async function lookupBoardsByStock() {
  const kw = stockLookupKeyword.value.trim()
  if (!kw) {
    ElMessage.warning('请输入股票代码或名称')
    return
  }
  stockLookupLoading.value = true
  stockLookupSearched.value = true
  try {
    const res = await boardConstituentsService.listBoardsByStock({
      boardType: boardType.value,
      stock: kw,
    })
    const codes = res.data?.stock_codes || []
    const names = res.data?.stock_names || []
    const namePart = names.length ? names.join('、') : ''
    const codePart = codes.join('、')
    stockLookupHint.value = namePart
      ? `股票 ${codePart}（${namePart}）— ${res.message || ''}`
      : `股票 ${codePart} — ${res.message || ''}`
    stockLookupBoards.value = (res.data?.boards || []).map((b) => ({
      board_code: b.board_code,
      board_name: b.board_name,
      constituent_count: 0,
      last_updated: b.last_updated,
      trade_observe_flag: b.trade_observe_flag,
    }))
    if (!stockLookupBoards.value.length) {
      ElMessage.info(stockLookupHint.value || '未找到所属板块')
    }
  } catch (e: unknown) {
    stockLookupBoards.value = []
    stockLookupHint.value = ''
    ElMessage.error(formatApiError(e, '反查失败'))
  } finally {
    stockLookupLoading.value = false
  }
}

async function onStockLookupBoardClick(row: BoardSummary) {
  boardKeyword.value = row.board_code
  boardPage.value = 1
  await loadBoards()
  let found = boards.value.find((b) => b.board_code === row.board_code)
  if (!found) {
    found = row
    boards.value = [row, ...boards.value]
  }
  boardTableRef.value?.setCurrentRow(found)
  onSelectBoard(found)
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
    boardEditForm.trade_observe_flag = !!row.trade_observe_flag
    boardEditForm.frontend_visible_flag = row.frontend_visible_flag !== false
    boardEditForm.board_code_source = row.board_code_source || 'manual'
    boardEditForm.original_board_code = row.board_code
  } else {
    boardEditForm.board_code = ''
    boardEditForm.board_name = ''
    boardEditForm.trade_observe_flag = false
    boardEditForm.frontend_visible_flag = true
    boardEditForm.board_code_source = 'manual'
    boardEditForm.original_board_code = ''
  }
  boardEditVisible.value = true
  if (!row) {
    void refreshBoardCode()
  }
}

function onBoardEditDialogOpened() {
  if (boardEditForm.original_board_code) return
  setTimeout(() => boardNameInputRef.value?.focus(), 50)
}

async function refreshBoardCode() {
  loadingNextBoardCode.value = true
  try {
    const after = boardEditForm.board_code.trim() || undefined
    const res = await boardConstituentsService.getNextBoardCode(boardType.value, after)
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
  boardEditForm.trade_observe_flag = false
  boardEditForm.frontend_visible_flag = true
  boardEditForm.board_code_source = 'manual'
  boardEditForm.original_board_code = ''
}

async function toggleBoardTradeObserve(row: BoardSummary, val: boolean) {
  if (togglingTradeObserve.value === row.board_code) return
  const prev = !!row.trade_observe_flag
  row.trade_observe_flag = val
  togglingTradeObserve.value = row.board_code
  try {
    await boardConstituentsService.setBoardTradeObserve({
      boardType: boardType.value,
      boardCode: row.board_code,
      tradeObserveFlag: val,
    })
    if (selectedBoard.value?.board_code === row.board_code) {
      selectedBoard.value.trade_observe_flag = val
    }
  } catch (e: unknown) {
    row.trade_observe_flag = prev
    ElMessage.error(e instanceof Error ? e.message : '更新交易观察标志失败')
  } finally {
    togglingTradeObserve.value = null
  }
}

async function toggleBoardFrontendVisible(row: BoardSummary, val: boolean) {
  if (togglingFrontendVisible.value === row.board_code) return
  const prev = row.frontend_visible_flag !== false
  row.frontend_visible_flag = val
  togglingFrontendVisible.value = row.board_code
  try {
    await boardConstituentsService.setBoardFrontendVisible({
      boardType: boardType.value,
      boardCode: row.board_code,
      frontendVisibleFlag: val,
    })
    if (selectedBoard.value?.board_code === row.board_code) {
      selectedBoard.value.frontend_visible_flag = val
    }
  } catch (e: unknown) {
    row.frontend_visible_flag = prev
    ElMessage.error(e instanceof Error ? e.message : '更新前端显示标志失败')
  } finally {
    togglingFrontendVisible.value = null
  }
}

async function submitBoardEdit() {
  if (savingBoard.value) return
  const code = boardEditForm.board_code.trim()
  if (!isBoardCreateAutoCode && !code) {
    ElMessage.warning('请填写板块代码')
    return
  }
  if (code && !isBoardCreateAutoCode && !isValidBoardCode(boardType.value, code)) {
    ElMessage.warning(
      boardType.value === 'industry'
        ? '行业板块代码须为数字、BK+数字、中文或英文字符'
        : '板块代码须为数字或 BK+数字 格式',
    )
    return
  }
  savingBoard.value = true
  try {
    const res = await boardConstituentsService.saveBoard({
      boardType: boardType.value,
      boardCode: code || undefined,
      boardName: boardEditForm.board_name.trim() || undefined,
      originalBoardCode: boardEditForm.original_board_code || undefined,
      tradeObserveFlag: boardEditForm.trade_observe_flag,
      frontendVisibleFlag: boardEditForm.frontend_visible_flag,
      boardCodeSource: boardEditForm.board_code_source,
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
    const msg = formatApiError(e, '删除失败')
    if (msg) ElMessage.error(msg)
  } finally {
    deletingBoard.value = false
  }
}

async function removeSelectedBoards() {
  if (!selectedBoardRows.value.length) return
  const codes = selectedBoardRows.value.map((r) => r.board_code).filter(Boolean)
  if (!codes.length) return
  const label = boardType.value === 'industry' ? '行业板块' : '概念板块'
  const preview = codes.slice(0, 8).join('、')
  const suffix = codes.length > 8 ? ` 等 ${codes.length} 个` : ''
  try {
    await ElMessageBox.confirm(
      `确定删除${label} ${preview}${suffix} 及其全部成分股？不可恢复。`,
      '批量删除确认',
      { type: 'warning' },
    )
    deletingBoardsBatch.value = true
    const res = await boardConstituentsService.deleteBoardsBatch({
      boardType: boardType.value,
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
    const msg = formatApiError(e, '删除失败')
    if (msg) ElMessage.error(msg)
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
  importAllClearExisting.value = false
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
  if (boardType.value === 'industry' && importAllClearExisting.value) {
    try {
      await ElMessageBox.confirm(
        '将清空全部行业板块的基础信息、成分股与实时行情，再导入文件数据。此操作不可恢复，是否继续？',
        '清空并导入确认',
        { type: 'warning' },
      )
    } catch {
      return
    }
  }
  importingAll.value = true
  try {
    const res = await boardConstituentsService.importAllFromFile({
      boardType: boardType.value,
      file: importAllFile.value,
      clearExisting: boardType.value === 'industry' ? importAllClearExisting.value : undefined,
    })
    if (!res.success) {
      const detail = res.data?.issues?.[0]?.message
      ElMessage.warning(detail || res.message || '导入未完成')
      importAllResult.value = {
        message: detail || res.message || '导入失败',
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
  void boardConstituentsService.getBoardCodeSources().then((res) => {
    boardCodeSourceOptions.value = res.data || []
  }).catch(() => {
    boardCodeSourceOptions.value = [
      { value: 'eastmoney', label: '东方财富' },
      { value: 'tonghuashun', label: '同花顺' },
      { value: 'huatai', label: '华泰' },
      { value: 'manual', label: '手动维护' },
      { value: 'other', label: '其他' },
    ]
  })
})
</script>

<style scoped>
.page-header {
  margin-bottom: 0.5rem;
}

.board-panels-row {
  align-items: stretch;
}

.board-panel-col {
  display: flex;
}

.board-panel-card {
  flex: 1;
  width: 100%;
  display: flex;
  flex-direction: column;
}

.board-panel-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 280px);
}

.board-panel-main {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.board-panel-empty {
  display: flex;
  align-items: center;
  justify-content: center;
}

.board-panel-footer {
  flex-shrink: 0;
}
</style>
