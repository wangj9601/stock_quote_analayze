<template>
  <div class="daily-review-panel" v-loading="loading">
    <div class="dr-toolbar">
      <el-date-picker
        v-model="tradeDate"
        type="date"
        value-format="YYYY-MM-DD"
        placeholder="交易日"
        size="small"
      />
      <el-button size="small" @click="load">加载</el-button>
      <el-button size="small" type="primary" @click="compute">重算</el-button>
      <el-button size="small" @click="collectZt">补采涨停池</el-button>
      <el-button size="small" type="success" @click="save">保存观点/建议</el-button>
      <el-button size="small" @click="exportMd">导出 MD</el-button>
      <el-button size="small" type="warning" @click="exportPdf">导出 PDF</el-button>
      <span class="dr-status">{{ status }}</span>
    </div>

    <el-row :gutter="12" class="dr-metrics" v-if="data">
      <el-col :xs="12" :sm="8" :md="4" v-for="m in metricCards" :key="m.label">
        <el-card shadow="never" class="dr-metric-card">
          <div class="label">{{ m.label }}</div>
          <div class="value">{{ m.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card v-if="data" class="dr-block" shadow="never">
      <template #header>大盘环境</template>
      <p>{{ envSummary }}</p>
      <el-table :data="indexRows" size="small" stripe border empty-text="暂无">
        <el-table-column prop="name" label="指数" min-width="100" />
        <el-table-column label="收盘" width="100">
          <template #default="{ row }">{{ fmt(row.close) }}</template>
        </el-table-column>
        <el-table-column label="涨跌幅%" width="90">
          <template #default="{ row }"><span :class="tone(row.pct_chg)">{{ fmt(row.pct_chg) }}</span></template>
        </el-table-column>
        <el-table-column label="距20日高点" width="110">
          <template #default="{ row }">{{ fmt(row.gap_to_high20, 0) }}</template>
        </el-table-column>
        <el-table-column prop="note" label="备注" min-width="120" />
      </el-table>
    </el-card>

    <el-card v-if="data" class="dr-block" shadow="never">
      <template #header>趋势摘要</template>
      <p>{{ (data.rules_json && data.rules_json.summary) || '—' }}</p>
      <p class="muted">季节：{{ data.season || '—' }} · 口径：{{ data.limit_source || '—' }}</p>
    </el-card>

    <el-card v-if="data" class="dr-block" shadow="never">
      <template #header>
        五项硬门槛
        <span class="muted">{{ (data.hard_gates && data.hard_gates.rate) || '' }}</span>
      </template>
      <el-table :data="gateRows" size="small" stripe border>
        <el-table-column prop="id" label="#" width="50" />
        <el-table-column prop="name" label="门槛" min-width="140" />
        <el-table-column prop="standard" label="标准" min-width="120" />
        <el-table-column label="今日" width="100">
          <template #default="{ row }">{{ fmt(row.value) }}</template>
        </el-table-column>
        <el-table-column label="结果" width="90">
          <template #default="{ row }">
            <el-tag :type="row.passed ? 'success' : 'danger'" size="small">
              {{ row.passed ? '达标' : '不达标' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="data" class="dr-block" shadow="never">
      <template #header>当日结构</template>
      <p>{{ mainSideText }}</p>
      <h4>领涨行业</h4>
      <el-table :data="sector.leaders || []" size="small" stripe border empty-text="暂无">
        <el-table-column prop="board_name" label="板块" min-width="120" />
        <el-table-column label="涨跌幅%" width="90">
          <template #default="{ row }"><span :class="tone(row.change_percent)">{{ fmt(row.change_percent) }}</span></template>
        </el-table-column>
        <el-table-column label="净流入(亿)" width="110">
          <template #default="{ row }"><span :class="tone(row.net_inflow_yi ?? row.net_inflow)">{{ fmtYi(row) }}</span></template>
        </el-table-column>
        <el-table-column label="上涨/下跌" width="110">
          <template #default="{ row }">{{ pair(row) }}</template>
        </el-table-column>
      </el-table>
      <h4>领跌行业</h4>
      <el-table :data="sector.laggards || []" size="small" stripe border empty-text="暂无">
        <el-table-column prop="board_name" label="板块" min-width="120" />
        <el-table-column label="涨跌幅%" width="90">
          <template #default="{ row }"><span :class="tone(row.change_percent)">{{ fmt(row.change_percent) }}</span></template>
        </el-table-column>
        <el-table-column label="净流入(亿)" width="110">
          <template #default="{ row }"><span :class="tone(row.net_inflow_yi ?? row.net_inflow)">{{ fmtYi(row) }}</span></template>
        </el-table-column>
        <el-table-column label="上涨/下跌" width="110">
          <template #default="{ row }">{{ pair(row) }}</template>
        </el-table-column>
      </el-table>
      <p class="muted">{{ rotationText }}</p>
      <h4>行业净流入前五</h4>
      <el-table :data="sector.capital_in || []" size="small" stripe border empty-text="暂无">
        <el-table-column prop="board_name" label="板块" min-width="120" />
        <el-table-column label="净流入(亿)" width="110">
          <template #default="{ row }"><span :class="tone(row.net_inflow_yi ?? row.net_inflow)">{{ fmtYi(row) }}</span></template>
        </el-table-column>
      </el-table>
      <h4>行业净流出前三</h4>
      <el-table :data="sector.capital_out || []" size="small" stripe border empty-text="暂无">
        <el-table-column prop="board_name" label="板块" min-width="120" />
        <el-table-column label="净流入(亿)" width="110">
          <template #default="{ row }"><span :class="tone(row.net_inflow_yi ?? row.net_inflow)">{{ fmtYi(row) }}</span></template>
        </el-table-column>
      </el-table>
      <p>{{ ladderText }}</p>
      <el-table :data="sector.seal_leaders || []" size="small" stripe border empty-text="暂无主线涨停">
        <el-table-column label="主线涨停" min-width="140">
          <template #default="{ row }">
            <a class="dr-stock-link" :href="stockDetailUrl(row.code, row.name)" target="_blank" rel="noopener noreferrer">{{ row.name }}</a>
            <span class="dr-code">{{ row.code }}</span>
          </template>
        </el-table-column>
        <el-table-column label="涨幅%" width="80">
          <template #default="{ row }"><span :class="tone(row.change_percent)">{{ fmt(row.change_percent) }}</span></template>
        </el-table-column>
        <el-table-column label="封单(亿)" width="90">
          <template #default="{ row }">{{ fmt(row.seal_yi) }}</template>
        </el-table-column>
        <el-table-column prop="board_count" label="连板" width="70" />
      </el-table>
      <div class="dr-pair">
        <el-table :data="sector.flow_top || []" size="small" stripe border empty-text="暂无">
          <el-table-column label="个股主力净流入前五" min-width="160">
            <template #default="{ row }">
              <a class="dr-stock-link" :href="stockDetailUrl(row.code, row.name)" target="_blank" rel="noopener noreferrer">{{ row.name }}</a>
              <span class="dr-code">{{ row.code }}</span>
            </template>
          </el-table-column>
          <el-table-column label="净流入(亿)" width="110">
            <template #default="{ row }"><span :class="tone(row.net_inflow_yi)">{{ fmt(row.net_inflow_yi) }}</span></template>
          </el-table-column>
        </el-table>
        <el-table :data="sector.main_flow_top || []" size="small" stripe border empty-text="暂无">
          <el-table-column label="主线内吸金前三" min-width="160">
            <template #default="{ row }">
              <a class="dr-stock-link" :href="stockDetailUrl(row.code, row.name)" target="_blank" rel="noopener noreferrer">{{ row.name }}</a>
              <span class="dr-code">{{ row.code }}</span>
            </template>
          </el-table-column>
          <el-table-column label="净流入(亿)" width="110">
            <template #default="{ row }"><span :class="tone(row.net_inflow_yi)">{{ fmt(row.net_inflow_yi) }}</span></template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <el-card v-if="data" class="dr-block" shadow="never">
      <template #header>主线板块（近10日·同花顺概念）</template>
      <p class="muted">{{ (data.mainline_json && data.mainline_json.summary) || '' }}</p>
      <el-table :data="mainlineRows" size="small" stripe border>
        <el-table-column label="概念板块" min-width="120">
          <template #default="{ row }">
            <a
              v-if="row.board_code"
              class="dr-board-link"
              :href="boardHref('concept', row)"
              target="_blank"
              rel="noopener noreferrer"
              title="打开板块详情"
            >{{ row.board_name || row.board_code }}</a>
            <span v-else>{{ row.board_name || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="hits_10d" label="上榜" width="70" />
        <el-table-column prop="tier_label" label="定性" min-width="110" />
        <el-table-column prop="today_status" label="今日" min-width="100" />
        <el-table-column prop="echelon" label="梯队" width="90" />
      </el-table>
    </el-card>

    <el-card v-if="data" class="dr-block" shadow="never">
      <template #header>当日行业赛道确认</template>
      <p class="muted">{{ industryConfirmSummary }}</p>
      <el-table :data="industryConfirmRows" size="small" stripe border>
        <el-table-column label="行业板块" min-width="120">
          <template #default="{ row }">
            <a
              v-if="row.board_code"
              class="dr-board-link"
              :href="boardHref('industry', row)"
              target="_blank"
              rel="noopener noreferrer"
              title="打开板块详情"
            >{{ row.board_name || row.board_code }}</a>
            <span v-else>{{ row.board_name || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="reason_text" label="上榜原因" min-width="140" />
        <el-table-column label="涨跌幅%" width="100">
          <template #default="{ row }"><span :class="tone(row.change_percent)">{{ fmt(row.change_percent) }}</span></template>
        </el-table-column>
        <el-table-column label="净流入(亿)" width="110">
          <template #default="{ row }"><span :class="tone(row.net_inflow_yi ?? row.net_inflow)">{{ fmtYi(row) }}</span></template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="data" class="dr-block" shadow="never">
      <template #header>情绪与次日观察</template>
      <p class="muted">{{ curveText }}</p>
      <p>当日事实</p>
      <ul>
        <li v-for="(t, i) in sentiment.facts || []" :key="'f' + i">{{ t }}</li>
        <li v-if="!(sentiment.facts || []).length">暂无</li>
      </ul>
      <p>次日观察</p>
      <ul>
        <li v-for="(t, i) in sentiment.watch || []" :key="'w' + i">{{ t }}</li>
        <li v-if="!(sentiment.watch || []).length">暂无</li>
      </ul>
    </el-card>

    <el-card v-if="data" class="dr-block" shadow="never">
      <template #header>明日个股</template>
      <p class="muted">{{ picks.disclaimer || '重算后生成明日个股。规则合成参考，非投资建议。' }}</p>
      <p v-if="picks.note">{{ picks.note }}</p>
      <p>不追</p>
      <el-table :data="picks.no_chase || []" size="small" empty-text="无">
        <el-table-column label="个股" min-width="140">
          <template #default="{ row }">{{ row.name }}({{ row.code }})</template>
        </el-table-column>
        <el-table-column prop="board_count" label="连板" width="70" />
        <el-table-column label="封单(亿)" width="90">
          <template #default="{ row }">{{ fmt(row.seal_yi) }}</template>
        </el-table-column>
        <el-table-column prop="break_count" label="炸板" width="70" />
        <el-table-column prop="limit_band" label="涨跌停" width="80" />
        <el-table-column prop="stance" label="立场" width="90" />
        <el-table-column prop="trigger" label="次日" min-width="180" />
      </el-table>
      <p>可跟踪</p>
      <el-table :data="picks.track || []" size="small" empty-text="无">
        <el-table-column label="个股" min-width="140">
          <template #default="{ row }">{{ row.name }}({{ row.code }})</template>
        </el-table-column>
        <el-table-column label="策略" min-width="100">
          <template #default="{ row }">{{ (row.strategies || []).join('、') || '—' }}</template>
        </el-table-column>
        <el-table-column label="立场" width="120">
          <template #default="{ row }">{{ row.brief_stance ? `${row.stance}（简报${row.brief_stance}）` : row.stance }}</template>
        </el-table-column>
        <el-table-column label="支撑" width="80">
          <template #default="{ row }">{{ fmt(row.p_sup) }}</template>
        </el-table-column>
        <el-table-column label="压力" width="80">
          <template #default="{ row }">{{ fmt(row.p_res) }}</template>
        </el-table-column>
        <el-table-column prop="trigger" label="明日触发" min-width="180" />
        <el-table-column prop="pattern" label="形态" width="110" />
        <el-table-column prop="macd" label="MACD" width="110" />
        <el-table-column label="RSI" width="70">
          <template #default="{ row }">{{ fmt(row.rsi) }}</template>
        </el-table-column>
        <el-table-column prop="kdj" label="KDJ" width="70" />
        <el-table-column prop="trend" label="趋势" width="70" />
      </el-table>
      <p>支线只观察</p>
      <el-table :data="picks.sideline || []" size="small" empty-text="无">
        <el-table-column label="个股" min-width="140">
          <template #default="{ row }">{{ row.name }}({{ row.code }})</template>
        </el-table-column>
        <el-table-column prop="industry" label="行业" min-width="100" />
        <el-table-column label="涨幅%" width="90">
          <template #default="{ row }"><span :class="tone(row.change_percent)">{{ fmt(row.change_percent) }}</span></template>
        </el-table-column>
        <el-table-column prop="stance" label="立场" width="90" />
      </el-table>
      <p>回避</p>
      <el-table :data="picks.avoid || []" size="small" empty-text="无">
        <el-table-column label="个股" min-width="140">
          <template #default="{ row }">{{ row.name }}({{ row.code }})</template>
        </el-table-column>
        <el-table-column prop="reason" label="原因" min-width="120" />
        <el-table-column label="立场" width="80">
          <template #default>回避</template>
        </el-table-column>
      </el-table>
      <p>涨停后高位蓄势（ZHAB）</p>
      <p class="muted">涨停后 1–6 日高位缩量蓄势；突破确认才可执行，蓄势阶段仅观察回踩支撑。</p>
      <el-table :data="zhabRows" size="small" empty-text="无">
        <el-table-column label="个股" min-width="140">
          <template #default="{ row }">{{ row.name }}({{ row.code }})</template>
        </el-table-column>
        <el-table-column label="阶段" width="100">
          <template #default="{ row }">{{ row.signal_type === 'breakout' ? '突破确认' : '蓄势观察' }}</template>
        </el-table-column>
        <el-table-column prop="zt_date" label="涨停日" width="110" />
        <el-table-column prop="consol_days" label="整理日" width="80" />
        <el-table-column label="支撑" width="90">
          <template #default="{ row }">{{ fmt(row.box_low != null ? row.box_low : row.zt_mid) }}</template>
        </el-table-column>
        <el-table-column label="上沿" width="90">
          <template #default="{ row }">{{ fmt(row.box_high) }}</template>
        </el-table-column>
        <el-table-column prop="stance" label="立场" width="90" />
        <el-table-column prop="trigger" label="触发" min-width="180" />
        <el-table-column label="得分" width="80">
          <template #default="{ row }">{{ fmt(row.score) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-row :gutter="16" v-if="data">
      <el-col :xs="24" :md="12">
        <el-card class="dr-block" shadow="never">
          <template #header>观点与盘面分析</template>
          <el-input v-model="viewpoint" type="textarea" :rows="6" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card class="dr-block" shadow="never">
          <template #header>操作建议</template>
          <el-input v-model="advice" type="textarea" :rows="6" />
        </el-card>
      </el-col>
    </el-row>

    <el-card v-if="markdown" class="dr-block" shadow="never">
      <template #header>
        <button type="button" class="dr-fold-btn" @click="mdOpen = !mdOpen">
          Markdown 预览
          <span>{{ mdOpen ? '收起' : '展开' }}</span>
        </button>
      </template>
      <div v-show="mdOpen" class="dr-md" v-html="markdownHtml"></div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  collectZtPool,
  computeDailyReview,
  exportDailyReviewMd,
  exportDailyReviewPdf,
  getDailyReview,
  saveDailyReviewText,
} from '@/services/marketReview.service'
import { boardDetailUrl, stockDetailUrl } from '@/utils/publicStockLinks'

const loading = ref(false)
const status = ref('')
const data = ref<any>(null)
const viewpoint = ref('')
const advice = ref('')
const markdown = ref('')
const mdOpen = ref(false)
const markdownHtml = computed(() => renderReviewMarkdown(markdown.value))

function yesterday(): string {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  return d.toISOString().slice(0, 10)
}

const tradeDate = ref(yesterday())

const gateRows = computed(() => (data.value?.hard_gates?.items as any[]) || [])
const mainlineRows = computed(() => (data.value?.mainline_json?.rows as any[]) || [])
const industryConfirmRows = computed(
  () => (data.value?.mainline_json?.industry_confirm?.rows as any[]) || []
)
const industryConfirmSummary = computed(
  () => data.value?.mainline_json?.industry_confirm?.summary || ''
)
const sector = computed(() => data.value?.mainline_json?.sector || {})
const sentiment = computed(() => data.value?.rules_json?.sentiment || {})
const picks = computed(() => data.value?.rules_json?.picks || {})
const zhabRows = computed(() => {
  const z = picks.value?.zhab || {}
  return [].concat(z.breakout || [], z.setup || [])
})
const indexRows = computed(() => data.value?.rules_json?.market_env?.indexes || [])

const envSummary = computed(() => {
  const d = data.value || {}
  const env = d.rules_json?.market_env || {}
  const b = env.breadth || {}
  let line = `成交额 ${fmt(env.vol_trillion ?? d.vol_trillion)} 万亿`
  if (env.vol_delta_yi != null && env.vol_delta_yi !== '') {
    const n = Number(env.vol_delta_yi)
    const verb = n > 0 ? '放量' : n < 0 ? '缩量' : '变化'
    line += `，较昨日${verb} ${fmt(Math.abs(n), 0)} 亿`
  }
  if (env.above_2t) line += '，站上 2 万亿'
  line += `。上涨 ${b.up_count ?? '—'}，下跌 ${b.down_count ?? '—'}，平盘 ${b.flat_count ?? '—'}；涨停 ${d.limit_up_count ?? '—'}，跌停 ${b.limit_down_count ?? '—'}。`
  return line
})

const mainSideText = computed(() => {
  const main = sector.value?.main
  const sides = (sector.value?.sidelines || []).map((s: any) => s?.board_name).filter(Boolean)
  if (!main?.board_name) return '当日主线不明确。'
  const side = sides.length ? `支线：${sides.join('、')}。` : ''
  return `当日主线：${main.board_name}，涨跌幅 ${fmt(main.change_percent)}%，净流入 ${fmtYi(main)} 亿。${side}`
})

const rotationText = computed(() => {
  const rot = sector.value?.rotation || {}
  const bits: string[] = []
  if ((rot.dropped || []).length) bits.push(`昨日上榜今日跌出：${rot.dropped.join('、')}。`)
  if ((rot.new_inflow || []).length) {
    bits.push(
      '今日新进且净流入居前：' +
        rot.new_inflow.map((r: any) => `${r.board_name}（${fmtYi(r)}亿）`).join('、') +
        '。'
    )
  }
  return bits.join('') || '暂无轮动对照。'
})

const ladderText = computed(() => {
  const ladder = sector.value?.ladder
  if (!ladder) return '暂无连板梯队。'
  const hs = sector.value?.height_stock || {}
  const heightBit = hs.name ? `最高板：${hs.name} ${hs.board_count} 板。` : ''
  return `2 板 ${ladder.b2 || 0}，3 板 ${ladder.b3 || 0}，4 板及以上 ${ladder.b4plus || 0}。${heightBit}`
})

const curveText = computed(() => {
  const d = data.value || {}
  const zones = d.rules_json?.curve_zones || {}
  const note = d.percentile_note || zones.percentile_note || ''
  const summary = zones.summary || (note === '样本不足' ? '阈值未校准' : '')
  if (!summary) return ''
  return `Lo/Hi/Spread 区间：${summary}${note ? `（${note}）` : ''}`
})

function pair(row: any): string {
  if (!row || (row.up_count == null && row.down_count == null)) return '—'
  return `${row.up_count ?? '—'}/${row.down_count ?? '—'}`
}

const metricCards = computed(() => {
  const d = data.value || {}
  return [
    { label: 'Vol(万亿)', value: fmt(d.vol_trillion) },
    { label: '较昨日(亿)', value: deltaText(d) },
    { label: '涨停', value: fmt(d.limit_up_count, 0) },
    { label: '跌停', value: limitDownText(d) },
    { label: '平盘', value: flatText(d) },
    { label: '上涨/下跌', value: breadthText(d) },
    { label: 'CB', value: fmt(d.cb_count, 0) },
    { label: '高度', value: fmt(d.height, 0) },
    { label: '昨连板%', value: fmt(d.prev_cb_return) },
    { label: 'Lo', value: curveCard(d, 'lo', d.lo_value) },
    { label: 'Hi', value: curveCard(d, 'hi', d.hi_value) },
    { label: 'Sp', value: curveCard(d, 'sp', d.sp_value) },
    { label: '盘面', value: (d.rules_json && d.rules_json.tape && d.rules_json.tape.label) || '—' },
  ]
})

function breadthText(d: any): string {
  const b = d?.rules_json?.market_env?.breadth
  if (!b || b.up_count == null) return '—'
  return `${b.up_count}/${b.down_count ?? '—'}`
}

function limitDownText(d: any): string {
  const n = d?.rules_json?.market_env?.breadth?.limit_down_count
  return n == null ? '—' : String(n)
}

function flatText(d: any): string {
  const n = d?.rules_json?.market_env?.breadth?.flat_count
  return n == null ? '—' : String(n)
}

function deltaText(d: any): string {
  const n = d?.rules_json?.market_env?.vol_delta_yi
  if (n == null || n === '') return '—'
  const v = Number(n)
  if (!Number.isFinite(v)) return '—'
  return `${v > 0 ? '+' : ''}${fmt(v, 0)}`
}

function curveCard(d: any, key: string, raw: any): string {
  const zones = d?.rules_json?.curve_zones || {}
  const note = d?.percentile_note || zones.percentile_note || ''
  const base = fmt(raw)
  if (note === '样本不足') return `${base}（样本不足 / 阈值未校准）`
  if (zones[key]) return `${base}（${zones[key]}）`
  return base
}

function fmtYi(row: any): string {
  if (row?.net_inflow_yi != null && row.net_inflow_yi !== '') {
    const n = Number(row.net_inflow_yi)
    return Number.isFinite(n) ? n.toFixed(1) : '—'
  }
  if (row?.net_inflow == null || row.net_inflow === '') return '—'
  const n = Number(row.net_inflow)
  if (!Number.isFinite(n)) return '—'
  return (n / 1e8).toFixed(1)
}

function fmt(v: any, digits = 2): string {
  if (v == null || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  if (digits === 0) return String(Math.round(n))
  return n.toFixed(digits)
}

function tone(v: any): string {
  if (v == null || v === '') return ''
  const n = Number(v)
  if (!Number.isFinite(n) || n === 0) return ''
  return n > 0 ? 'dr-up' : 'dr-down'
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function mdInline(s: string): string {
  return escapeHtml(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/`([^`]+)`/g, '<code>$1</code>')
}

function renderReviewMarkdown(src: string): string {
  const text = String(src || '').replace(/\r\n/g, '\n')
  if (!text.trim()) return '<p class="muted">暂无预览</p>'
  const lines = text.split('\n')
  const out: string[] = []
  let i = 0
  const special = (line: string) => /^(#{1,3}\s|\||>|---+\s*$|\d+\.\s|[-*]\s)/.test(line)
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) {
      i += 1
      continue
    }
    if (/^---+\s*$/.test(line.trim())) {
      out.push('<hr>')
      i += 1
      continue
    }
    const heading = /^(#{1,3})\s+(.*)$/.exec(line)
    if (heading) {
      out.push(`<h${heading[1].length}>${mdInline(heading[2])}</h${heading[1].length}>`)
      i += 1
      continue
    }
    if (line.trim().startsWith('|')) {
      const block: string[] = []
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        block.push(lines[i])
        i += 1
      }
      const rows = block
        .map((row) => row.replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim()))
        .filter((cells) => !(cells.length && cells.every((c) => /^:?-+:?$/.test(c))))
      if (rows.length) {
        const head = rows[0]
        const toneIdx = head.map((h, idx) => (/涨跌|涨幅|净流入/.test(h) ? idx : -1)).filter((idx) => idx >= 0)
        const cell = (c: string, tag: string, idx: number) => {
          let html = mdInline(c)
          const num = tag === 'td' && toneIdx.includes(idx)
          if (num) {
            const n = Number(String(c).replace(/[^\d.+-]/g, ''))
            if (Number.isFinite(n) && n !== 0) html = `<span class="${n > 0 ? 'dr-up' : 'dr-down'}">${html}</span>`
          }
          return `<${tag}${num ? ' class="num"' : ''}>${html}</${tag}>`
        }
        const tr = (cells: string[], tag: string) => `<tr>${cells.map((c, idx) => cell(c, tag, idx)).join('')}</tr>`
        out.push(`<table class="md-table"><thead>${tr(head, 'th')}</thead><tbody>${rows.slice(1).map((r) => tr(r, 'td')).join('')}</tbody></table>`)
      }
      continue
    }
    if (/^>\s?/.test(line)) {
      const bits: string[] = []
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        bits.push(lines[i].replace(/^>\s?/, ''))
        i += 1
      }
      out.push(`<blockquote>${mdInline(bits.join(' '))}</blockquote>`)
      continue
    }
    if (/^[-*]\s+/.test(line) || /^\d+\.\s+/.test(line)) {
      const ordered = /^\d+\.\s+/.test(line)
      const re = ordered ? /^\d+\.\s+(.*)$/ : /^[-*]\s+(.*)$/
      const items: string[] = []
      while (i < lines.length && re.test(lines[i])) {
        items.push(`<li>${mdInline((lines[i].match(re) || [])[1] || '')}</li>`)
        i += 1
      }
      out.push(ordered ? `<ol>${items.join('')}</ol>` : `<ul>${items.join('')}</ul>`)
      continue
    }
    const para = [line]
    i += 1
    while (i < lines.length && lines[i].trim() && !special(lines[i])) {
      para.push(lines[i])
      i += 1
    }
    out.push(`<p>${mdInline(para.join(' '))}</p>`)
  }
  return out.join('')
}

function boardHref(kind: 'industry' | 'concept', row: any): string {
  return boardDetailUrl({
    boardKind: kind,
    boardCode: String(row?.board_code || ''),
    boardName: String(row?.board_name || ''),
    boardCodeSource: 'tonghuashun',
  })
}

function applyData(d: any) {
  data.value = d
  viewpoint.value = d?.viewpoint_md || ''
  advice.value = d?.advice_md || ''
  markdown.value = d?.markdown || ''
}

async function load() {
  if (!tradeDate.value) return
  loading.value = true
  status.value = '加载中…'
  try {
    const res = await getDailyReview(tradeDate.value)
    if (!res.success || !res.data) {
      status.value = res.message || '暂无快照，请重算'
      data.value = null
      return
    }
    applyData(res.data)
    status.value = `已加载 ${tradeDate.value}`
  } catch (e: any) {
    status.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function compute() {
  if (!tradeDate.value) return
  loading.value = true
  status.value = '重算中…'
  try {
    const res = await computeDailyReview(tradeDate.value, true)
    if (!res.success) {
      ElMessage.error(res.message || '重算失败')
      status.value = res.message || '重算失败'
      return
    }
    applyData(res.data)
    status.value = `重算完成 · ${res.data?.limit_source || ''} · ${res.data?.season || ''}`
    ElMessage.success('复盘重算完成')
  } catch (e: any) {
    status.value = e?.message || '重算失败'
    ElMessage.error(status.value)
  } finally {
    loading.value = false
  }
}

async function collectZt() {
  if (!tradeDate.value) return
  loading.value = true
  try {
    const res = await collectZtPool(tradeDate.value)
    if (res.success) {
      ElMessage.success(`涨停池写入 ${res.written ?? 0} 条`)
      status.value = `涨停池 OK written=${res.written}`
    } else {
      ElMessage.warning(res.error || res.message || '采集失败（可回退代理口径）')
      status.value = res.error || res.message || '涨停池采集失败'
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '采集异常')
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!tradeDate.value) return
  loading.value = true
  try {
    const res = await saveDailyReviewText(tradeDate.value, {
      viewpoint_md: viewpoint.value,
      advice_md: advice.value,
    })
    if (!res.success) {
      ElMessage.error(res.message || '保存失败')
      return
    }
    applyData(res.data)
    ElMessage.success('已保存')
    status.value = '观点/建议已保存'
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    loading.value = false
  }
}

async function exportMd() {
  if (!tradeDate.value) return
  loading.value = true
  try {
    const res = await exportDailyReviewMd(tradeDate.value)
    if (!res.ok) {
      ElMessage.error(res.message || '导出失败')
      return
    }
    ElMessage.success(`已下载 ${res.filename}`)
    status.value = res.filename || '已下载'
  } catch (e: any) {
    ElMessage.error(e?.message || '导出失败')
  } finally {
    loading.value = false
  }
}

async function exportPdf() {
  if (!tradeDate.value) return
  loading.value = true
  status.value = '正在生成 PDF…'
  try {
    const res = await exportDailyReviewPdf(tradeDate.value)
    if (!res.ok) {
      ElMessage.error(res.message || 'PDF 导出失败')
      status.value = res.message || 'PDF 导出失败'
      return
    }
    ElMessage.success(`已下载 ${res.filename}`)
    status.value = res.filename || 'PDF 已下载'
  } catch (e: any) {
    ElMessage.error(e?.message || 'PDF 导出失败')
    status.value = e?.message || 'PDF 导出失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
})
</script>

<style scoped>
.daily-review-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.dr-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.dr-status {
  color: #64748b;
  font-size: 13px;
}
.dr-metrics {
  margin-top: 4px;
}
.dr-metric-card {
  margin-bottom: 8px;
}
.dr-metric-card .label {
  font-size: 12px;
  color: #64748b;
}
.dr-metric-card .value {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}
.dr-block {
  margin-top: 4px;
}
.muted {
  color: #64748b;
  font-size: 13px;
}
.dr-fold-btn {
  border: none;
  background: transparent;
  padding: 0;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
  color: inherit;
}
.dr-fold-btn span {
  margin-left: 8px;
  font-size: 12px;
  font-weight: 500;
  color: #64748b;
}
.dr-md {
  color: #0f172a;
  line-height: 1.65;
  font-size: 14px;
}
.dr-md h1 { font-size: 20px; margin: 0 0 10px; }
.dr-md h2 { font-size: 16px; margin: 16px 0 8px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; }
.dr-md h3 { font-size: 15px; margin: 12px 0 6px; }
.dr-md :deep(table.md-table) { width: 100%; border-collapse: collapse; margin: 8px 0 12px; font-size: 13px; }
.dr-md :deep(table.md-table th),
.dr-md :deep(table.md-table td) { border: 1px solid #e2e8f0; padding: 6px 8px; text-align: left; }
.dr-md :deep(table.md-table th) { background: #f8fafc; }
.dr-md :deep(.num) { text-align: right; font-variant-numeric: tabular-nums; }
.dr-md blockquote { margin: 8px 0; padding: 8px 12px; background: #f8fafc; border-left: 3px solid #cbd5e1; color: #475569; }
.dr-board-link,
.dr-stock-link {
  color: #1d4ed8;
  text-decoration: none;
  font-weight: 600;
}
.dr-board-link:hover,
.dr-stock-link:hover {
  text-decoration: underline;
  color: #1e40af;
}
.dr-up { color: #dc2626; font-weight: 600; }
.dr-down { color: #16a34a; font-weight: 600; }
.dr-code { margin-left: 6px; color: #94a3b8; font-size: 12px; }
.dr-pair { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
@media (max-width: 900px) {
  .dr-pair { grid-template-columns: 1fr; }
}
</style>
