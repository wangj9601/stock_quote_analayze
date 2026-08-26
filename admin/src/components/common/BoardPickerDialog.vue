<template>
  <div class="board-picker-field">
    <div class="board-picker-row">
      <el-button type="primary" plain @click="openDialog">选择板块</el-button>
      <span class="board-picker-summary">{{ summaryText }}</span>
    </div>

    <el-dialog
      v-model="visible"
      :title="dialogTitle"
      width="720px"
      destroy-on-close
      class="board-picker-dialog"
      @open="onOpen"
    >
      <div class="board-picker-toolbar">
        <el-input
          v-model="keyword"
          clearable
          placeholder="搜索板块名称或代码"
          class="board-picker-search"
        />
        <span class="board-picker-count">{{ countText }}</span>
        <el-button size="small" @click="selectAllVisible">全选当前</el-button>
        <el-button size="small" @click="clearDraft">清空</el-button>
      </div>
      <div v-loading="loading" class="board-picker-list">
        <label
          v-for="b in visibleBoards"
          :key="b.board_code"
          class="board-picker-item"
        >
          <el-checkbox
            :model-value="draftSet.has(b.board_code)"
            @change="(v) => toggleDraft(b.board_code, v === true)"
          />
          <span class="board-picker-item-text">
            <span class="board-picker-name">{{ b.board_name || b.board_code }}</span>
            <span class="board-picker-code">{{ b.board_code }}</span>
            <span v-if="b.constituent_count" class="board-picker-meta">成分 {{ b.constituent_count }}</span>
          </span>
        </label>
        <div v-if="!loading && !visibleBoards.length" class="board-picker-empty">无匹配板块</div>
      </div>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="confirm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { boardConstituentsService, type BoardSummary, type BoardType } from '@/services/boardConstituents.service'

const BOARD_LIST_PAGE_SIZE = 200

const props = withDefaults(
  defineProps<{
    modelValue: string[]
    boardType: BoardType
    label?: string
  }>(),
  { label: '' }
)

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const visible = ref(false)
const loading = ref(false)
const keyword = ref('')
const catalog = ref<BoardSummary[]>([])
const draftSet = ref(new Set<string>())

const dialogTitle = computed(() =>
  props.boardType === 'concept' ? '选择概念板块（可多选）' : '选择行业板块（可多选）'
)

const boardMap = computed(() => {
  const m = new Map<string, BoardSummary>()
  for (const b of catalog.value) m.set(b.board_code, b)
  return m
})

const visibleBoards = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  let list = catalog.value
  if (q) {
    list = list.filter((b) => {
      const name = String(b.board_name || '').toLowerCase()
      const code = String(b.board_code || '').toLowerCase()
      return name.includes(q) || code.includes(q)
    })
  }
  return list
})

const countText = computed(() => {
  const total = catalog.value.length
  const filtered = visibleBoards.value.length
  if (keyword.value.trim()) return `当前 ${filtered} / 共 ${total}`
  return `共 ${total} 个可选`
})

const summaryText = computed(() => {
  const codes = props.modelValue || []
  if (!codes.length) return '未选择板块，点击「选择板块」'
  if (codes.length === 1) {
    const b = boardMap.value.get(codes[0])
    const name = b?.board_name || codes[0]
    return `已选 1 个：${name}（${codes[0]}）`
  }
  const names = codes.slice(0, 3).map((c) => boardMap.value.get(c)?.board_name || c)
  const more = codes.length > 3 ? ` 等 ${codes.length} 个` : ''
  return `已选 ${codes.length} 个：${names.join('、')}${more}`
})

async function loadCatalog() {
  loading.value = true
  try {
    const all: BoardSummary[] = []
    let page = 1
    let total = 0
    do {
      const res = await boardConstituentsService.listBoards({
        boardType: props.boardType,
        page,
        pageSize: BOARD_LIST_PAGE_SIZE,
      })
      const batch = res.data || []
      total = res.total ?? batch.length
      all.push(...batch)
      if (batch.length < BOARD_LIST_PAGE_SIZE) break
      page += 1
    } while (all.length < total)
    catalog.value = all
  } catch (e: any) {
    catalog.value = []
    ElMessage.error(e?.response?.data?.detail || e?.message || '加载板块列表失败')
  } finally {
    loading.value = false
  }
}

function openDialog() {
  visible.value = true
}

async function onOpen() {
  draftSet.value = new Set(props.modelValue || [])
  keyword.value = ''
  if (!catalog.value.length) await loadCatalog()
}

function toggleDraft(code: string, checked: boolean) {
  const next = new Set(draftSet.value)
  if (checked) next.add(code)
  else next.delete(code)
  draftSet.value = next
}

function selectAllVisible() {
  const next = new Set(draftSet.value)
  for (const b of visibleBoards.value) next.add(b.board_code)
  draftSet.value = next
}

function clearDraft() {
  draftSet.value = new Set()
}

function confirm() {
  emit('update:modelValue', [...draftSet.value])
  visible.value = false
}

watch(
  () => props.boardType,
  () => {
    catalog.value = []
  }
)
</script>

<style scoped>
.board-picker-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  width: 100%;
}
.board-picker-summary {
  flex: 1;
  min-width: 200px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.5;
}
.board-picker-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.board-picker-search {
  width: 260px;
}
.board-picker-count {
  color: #64748b;
  font-size: 12px;
  margin-right: auto;
}
.board-picker-list {
  max-height: 420px;
  overflow: auto;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px;
}
.board-picker-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
}
.board-picker-item:hover {
  background: #f8fafc;
}
.board-picker-item-text {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: baseline;
}
.board-picker-name {
  font-weight: 500;
  color: #111827;
}
.board-picker-code,
.board-picker-meta {
  color: #64748b;
  font-size: 12px;
}
.board-picker-empty {
  padding: 24px;
  text-align: center;
  color: #94a3b8;
}
</style>
