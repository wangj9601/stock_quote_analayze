<template>
  <div class="simple-strategy-pane space-y-4">
    <el-card shadow="never">
      <template #header><span class="font-semibold">策略说明</span></template>
      <ul class="list-disc pl-5 text-sm text-gray-700 space-y-1">
        <li v-for="(b, i) in bullets" :key="i">{{ b }}</li>
      </ul>
    </el-card>

    <div class="flex flex-wrap items-center gap-2">
      <el-button type="primary" :loading="loading" @click="run">
        <el-icon class="mr-1"><Refresh /></el-icon>
        刷新筛选
      </el-button>
      <el-button :disabled="!rows.length || loading" @click="exportCsv">导出CSV</el-button>
      <span v-if="searchDate" class="text-sm text-gray-600">筛选时间：{{ searchDate }}</span>
    </div>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon closable @close="errorMsg = ''" />

    <div v-loading="loading" class="min-h-[100px]">
      <div class="mb-2 text-sm text-gray-700">共找到 <strong>{{ rows.length }}</strong> 只符合条件的股票</div>
      <el-table :data="rows" stripe border size="small" style="width: 100%">
        <template #empty>
          <span class="text-gray-500 text-sm">点击「刷新筛选」开始</span>
        </template>
        <el-table-column
          v-for="(c, i) in columns"
          :key="i"
          :label="c.label"
          :width="c.width"
          :min-width="c.minWidth"
        >
          <template #default="{ row }">
            <template v-if="c.type === 'code'">
              <el-link
                type="primary"
                :href="stockDetailUrl(String(row.symbol || row.code), String(row.name))"
                target="_blank"
                :underline="false"
              >
                {{ row.symbol || row.code }}
              </el-link>
            </template>
            <span v-else-if="c.type === 'name'">{{ row.name }}</span>
            <span v-else-if="c.type === 'text'">{{ displayText(row, c.prop) }}</span>
            <span v-else-if="c.type === 'price'">{{ fmtPrice(row[c.prop!]) }}</span>
            <span
              v-else-if="c.type === 'pct'"
              :class="pctClass(row.current_change_percent ?? row[c.prop!])"
            >
              {{ fmtPct(row.current_change_percent ?? row[c.prop!]) }}
            </span>
            <span v-else-if="c.type === 'custom'">{{ c.render(row) }}</span>
            <div v-else-if="c.type === 'actions'" class="flex gap-2 flex-wrap">
              <el-link
                type="primary"
                :href="stockHistoryUrl(String(row.symbol || row.code))"
                target="_blank"
                :underline="false"
              >
                历史
              </el-link>
              <el-link
                type="primary"
                :href="stockDetailUrl(String(row.symbol || row.code), String(row.name))"
                target="_blank"
                :underline="false"
              >
                详情
              </el-link>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { screeningGet } from '@/services/screeningPublicApi'
import { stockDetailUrl, stockHistoryUrl } from '@/utils/publicStockLinks'

export type SimpleCol =
  | { type: 'code'; label: string; width?: number; minWidth?: number }
  | { type: 'name'; label: string; width?: number; minWidth?: number }
  | { type: 'text'; label: string; prop: string; width?: number; minWidth?: number }
  | { type: 'price'; label: string; prop: string; width?: number; minWidth?: number }
  | { type: 'pct'; label: string; prop?: string; width?: number; minWidth?: number }
  | { type: 'actions'; label: string; width?: number; minWidth?: number }
  | { type: 'custom'; label: string; width?: number; minWidth?: number; render: (row: Record<string, unknown>) => string }

const props = defineProps<{
  bullets: string[]
  /** 如 cyb-midline-strategy?months=4 */
  fetchPath: string
  columns: SimpleCol[]
  exportName: string
}>()

const loading = ref(false)
const errorMsg = ref('')
const rows = ref<Record<string, unknown>[]>([])
const searchDate = ref('')

function displayText(row: Record<string, unknown>, prop: string) {
  const v = row[prop]
  if (v == null || v === '') return '—'
  return String(v)
}

function fmtPrice(v: unknown) {
  if (v == null || (typeof v === 'number' && Number.isNaN(v))) return '—'
  return Number(v).toFixed(2)
}

function fmtPct(v: unknown) {
  if (v == null || (typeof v === 'number' && Number.isNaN(v))) return '—'
  const n = Number(v)
  const sym = n > 0 ? '+' : ''
  return `${sym}${n.toFixed(2)}%`
}

function pctClass(v: unknown) {
  if (v == null) return ''
  const n = Number(v)
  if (n > 0) return 'text-red-600'
  if (n < 0) return 'text-green-600'
  return 'text-gray-600'
}

async function run() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await screeningGet(props.fetchPath)
    if (!res.success || !Array.isArray(res.data)) {
      throw new Error(res.message || '无数据')
    }
    rows.value = res.data as Record<string, unknown>[]
    searchDate.value = res.search_date || ''
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    errorMsg.value = msg
    rows.value = []
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

function exportCsv() {
  if (!rows.value.length) {
    ElMessage.warning('没有可导出的数据')
    return
  }
  const header = props.columns
    .filter((c) => c.type !== 'actions')
    .map((c) => c.label)
  const lines: string[] = [header.join(',')]
  for (const row of rows.value) {
    const cells = props.columns
      .filter((c) => c.type !== 'actions')
      .map((c) => {
        if (c.type === 'code') return row.symbol || row.code
        if (c.type === 'name') return row.name
        if (c.type === 'text' || c.type === 'price') return row[c.prop!] ?? ''
        if (c.type === 'pct') return row.current_change_percent ?? (c.prop ? row[c.prop] : '')
        if (c.type === 'custom') return c.render(row)
        return ''
      })
    lines.push(
      cells
        .map((v) => {
          const s = v == null ? '' : String(v)
          if (s.includes(',') || s.includes('"') || s.includes('\n')) {
            return `"${s.replace(/"/g, '""')}"`
          }
          return s
        })
        .join(',')
    )
  }
  const blob = new Blob(['\uFEFF' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `${props.exportName}_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}
</script>
