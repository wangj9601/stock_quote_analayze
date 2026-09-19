<template>
  <div class="lhb-panel" v-loading="loading">
    <div class="lhb-toolbar">
      <el-radio-group v-model="boardType" size="small" @change="load">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="org">机构</el-radio-button>
        <el-radio-button value="hot_money">游资</el-radio-button>
      </el-radio-group>
      <el-date-picker
        v-model="tradeDate"
        type="date"
        value-format="YYYY-MM-DD"
        placeholder="最新交易日"
        size="small"
        clearable
      />
      <el-button size="small" type="primary" @click="load">查询</el-button>
      <span class="lhb-meta" v-if="metaText">{{ metaText }}</span>
    </div>

    <el-alert
      v-if="hint"
      class="lhb-hint"
      type="warning"
      :closable="false"
      show-icon
      :title="hint"
    />
    <el-alert
      v-if="error"
      class="lhb-hint"
      type="error"
      :closable="false"
      show-icon
      :title="error"
    />

    <el-row :gutter="12" class="lhb-metrics" v-if="data">
      <el-col :xs="12" :sm="6">
        <el-card shadow="never" class="lhb-metric">
          <div class="label">上榜股票</div>
          <div class="value">{{ data.stock_count ?? 0 }}</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="never" class="lhb-metric">
          <div class="label">净额合计(亿)</div>
          <div class="value" :class="netClass(sumNet)">{{ formatYi(sumNet) }}</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="never" class="lhb-metric">
          <div class="label">机构净额(亿)</div>
          <div class="value" :class="netClass(sumOrg)">{{ hasOrg ? formatYi(sumOrg) : '--' }}</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="never" class="lhb-metric">
          <div class="label">游资净额(亿)</div>
          <div class="value" :class="netClass(sumHot)">{{ hasHot ? formatYi(sumHot) : '--' }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-table :data="items" size="small" stripe border max-height="560" empty-text="暂无龙虎榜数据">
      <el-table-column prop="code" label="代码" width="90" fixed>
        <template #default="{ row }">
          <a class="lhb-link" :href="stockHref(row)" target="_blank" rel="noopener noreferrer">{{ row.code }}</a>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" min-width="100" fixed>
        <template #default="{ row }">
          <a class="lhb-link" :href="stockHref(row)" target="_blank" rel="noopener noreferrer">{{ row.name || '—' }}</a>
        </template>
      </el-table-column>
      <el-table-column label="涨跌幅" width="90" align="right">
        <template #default="{ row }">
          <span :class="netClass(row.change_percent)">{{ formatPct(row.change_percent) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="收盘" width="80" align="right">
        <template #default="{ row }">{{ formatPrice(row.close) }}</template>
      </el-table-column>
      <el-table-column label="买入(亿)" width="100" align="right">
        <template #default="{ row }">{{ formatYi(row.buy_value) }}</template>
      </el-table-column>
      <el-table-column label="卖出(亿)" width="100" align="right">
        <template #default="{ row }">{{ formatYi(row.sell_value) }}</template>
      </el-table-column>
      <el-table-column label="净额(亿)" width="100" align="right">
        <template #default="{ row }">
          <span :class="netClass(row.net_value)">{{ formatYi(row.net_value) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="净占比" width="90" align="right">
        <template #default="{ row }">
          <span :class="netClass(row.net_rate)">{{ formatPct(row.net_rate) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="机构净额(亿)" width="120" align="right">
        <template #default="{ row }">
          <span :class="netClass(row.org_net_value)">{{ formatYi(row.org_net_value) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="游资净额(亿)" width="120" align="right">
        <template #default="{ row }">
          <span :class="netClass(row.hot_money_net_value)">{{ formatYi(row.hot_money_net_value) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="上榜原因" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">{{ row.reason || row.interpretation || '—' }}</template>
      </el-table-column>
    </el-table>

    <el-card v-if="seats.length" class="lhb-seats" shadow="never">
      <template #header>游资席位</template>
      <el-table :data="seats" size="small" stripe border max-height="360">
        <el-table-column prop="name" label="席位" min-width="140" />
        <el-table-column label="买入(亿)" width="110" align="right">
          <template #default="{ row }">{{ formatYi(row.buy_value) }}</template>
        </el-table-column>
        <el-table-column label="卖出(亿)" width="110" align="right">
          <template #default="{ row }">{{ formatYi(row.sell_value) }}</template>
        </el-table-column>
        <el-table-column label="净额(亿)" width="110" align="right">
          <template #default="{ row }">
            <span :class="netClass(row.net_value)">{{ formatYi(row.net_value) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="关联股票" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">{{ seatStocks(row) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { stockDetailUrl } from '@/utils/publicStockLinks'
import {
  getDragonTiger,
  type DragonTigerBoardType,
  type DragonTigerData,
  type DragonTigerSeat,
  type DragonTigerStockItem
} from '@/services/dragonTiger.service'

const loading = ref(false)
const error = ref('')
const boardType = ref<DragonTigerBoardType>('all')
const tradeDate = ref<string>('')
const data = ref<DragonTigerData | null>(null)

const items = computed(() => data.value?.items || [])
const seats = computed(() => data.value?.hot_money_items || [])

const sumNet = computed(() => sumField('net_value'))
const sumOrg = computed(() => sumField('org_net_value'))
const sumHot = computed(() => sumField('hot_money_net_value'))
const hasOrg = computed(() => items.value.some((r) => r.org_net_value != null))
const hasHot = computed(() => items.value.some((r) => r.hot_money_net_value != null))

const metaText = computed(() => {
  const d = data.value
  if (!d) return ''
  const parts = [d.trade_date || '', d.source_label ? `来源 ${d.source_label}` : ''].filter(Boolean)
  return parts.join(' · ')
})

const hint = computed(() => data.value?.fallback_reason || data.value?.board_type_note || '')

function sumField(key: 'net_value' | 'org_net_value' | 'hot_money_net_value') {
  let total = 0
  let any = false
  for (const row of items.value) {
    const v = row[key]
    if (v == null || !Number.isFinite(Number(v))) continue
    total += Number(v)
    any = true
  }
  return any ? total : null
}

function formatYi(yuan: number | null | undefined) {
  if (yuan == null || !Number.isFinite(Number(yuan))) return '--'
  const yi = Math.round((Number(yuan) / 1e8) * 100) / 100
  const sign = yi > 0 ? '+' : ''
  return `${sign}${yi.toFixed(2)}`
}

function formatPct(v: number | null | undefined) {
  if (v == null || !Number.isFinite(Number(v))) return '--'
  const n = Number(v)
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toFixed(2)}%`
}

function formatPrice(v: number | null | undefined) {
  if (v == null || !Number.isFinite(Number(v))) return '--'
  return Number(v).toFixed(2)
}

function netClass(v: number | null | undefined) {
  if (v == null || !Number.isFinite(Number(v))) return ''
  if (Number(v) > 0) return 'net-pos'
  if (Number(v) < 0) return 'net-neg'
  return ''
}

function stockHref(row: DragonTigerStockItem) {
  return stockDetailUrl(row.code, row.name || '')
}

function seatStocks(row: DragonTigerSeat) {
  const stocks = row.stocks || []
  if (!stocks.length) return '—'
  return stocks
    .map((s) => {
      const label = `${s.name || ''}${s.code ? `(${s.code})` : ''}`.trim()
      const net = formatYi(s.net_value)
      return net === '--' ? label : `${label} ${net}`
    })
    .filter(Boolean)
    .join('、')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await getDragonTiger({
      board_type: boardType.value,
      date: tradeDate.value || undefined
    })
    if (!res.success || !res.data) {
      data.value = null
      error.value = res.message || '龙虎榜加载失败'
      return
    }
    data.value = res.data
    if (res.data.trade_date && !tradeDate.value) {
      tradeDate.value = res.data.trade_date
    }
  } catch (e: unknown) {
    data.value = null
    error.value = e instanceof Error ? e.message : '龙虎榜请求异常'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<style scoped>
.lhb-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.lhb-meta {
  color: #666;
  font-size: 13px;
}

.lhb-hint {
  margin-bottom: 12px;
}

.lhb-metrics {
  margin-bottom: 12px;
}

.lhb-metric .label {
  color: #888;
  font-size: 12px;
}

.lhb-metric .value {
  margin-top: 4px;
  font-size: 18px;
  font-weight: 600;
}

.lhb-link {
  color: var(--el-color-primary);
  text-decoration: none;
}

.lhb-seats {
  margin-top: 16px;
}

.net-pos {
  color: #dc2626;
}

.net-neg {
  color: #16a34a;
}
</style>
