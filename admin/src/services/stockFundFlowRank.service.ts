/**
 * 个股资金流向趋势（日/周/月净流入排名）：`/api/stock_fund_flow/rank`
 * 走同源绝对路径，避免 apiService baseURL=/api/admin 拼接错误。
 */

export type StockFundFlowRankPeriod = 'day' | 'week' | 'month'

export interface StockFundFlowRankItem {
  code: string
  name: string | null
  net_amount: number | null
  inflow_amount: number | null
  outflow_amount: number | null
  turnover_amount: number | null
  days_count?: number | null
}

export interface StockFundFlowRankData {
  period: StockFundFlowRankPeriod
  period_label: string
  trade_days: number
  start_date: string | null
  end_date: string | null
  items: StockFundFlowRankItem[]
  count: number
  total_universe?: number
  sides?: number
}

export interface StockFundFlowRankResponse {
  success: boolean
  data?: StockFundFlowRankData
  message?: string
}

export interface StockFundFlowRankParams {
  period?: StockFundFlowRankPeriod
  sides?: number
  trade_date?: string
}

export interface StockFundFlowTrendEntity {
  code: string
  name: string | null
  window_net: number | null
  net_amount: Array<number | null>
}

export interface StockFundFlowTrendSeriesData {
  period: StockFundFlowRankPeriod
  period_label: string
  trend_days: number
  start_date: string | null
  end_date: string | null
  dates: string[]
  aggregate: {
    net_amount: Array<number | null>
    inflow_amount: Array<number | null>
    outflow_amount: Array<number | null>
  }
  top_entities: StockFundFlowTrendEntity[]
}

export interface StockFundFlowTrendSeriesResponse {
  success: boolean
  data?: StockFundFlowTrendSeriesData
  message?: string
}

export interface StockFundFlowTrendSeriesParams {
  period?: StockFundFlowRankPeriod
  trade_date?: string
  top_n?: number
}

export const STOCK_FUND_FLOW_RANK_PERIODS: {
  value: StockFundFlowRankPeriod
  label: string
}[] = [
  { value: 'day', label: '日' },
  { value: 'week', label: '周' },
  { value: 'month', label: '月' },
]

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('admin_token')
  const h: Record<string, string> = {}
  if (token) h.Authorization = `Bearer ${token}`
  return h
}

export async function getStockFundFlowRank(
  params: StockFundFlowRankParams = {}
): Promise<StockFundFlowRankResponse> {
  const q = new URLSearchParams()
  q.set('period', params.period || 'day')
  if (params.sides != null) q.set('sides', String(params.sides))
  if (params.trade_date) q.set('trade_date', params.trade_date)

  const url = `/api/stock_fund_flow/rank?${q.toString()}`
  const res = await fetch(url, { headers: authHeaders() })
  const text = await res.text()
  let body: StockFundFlowRankResponse = { success: false }
  try {
    body = text ? (JSON.parse(text) as StockFundFlowRankResponse) : body
  } catch {
    body = { success: false, message: text?.slice(0, 200) || `HTTP ${res.status}` }
  }
  if (!res.ok) {
    return {
      success: false,
      message: body.message || `请求失败(${res.status})`,
    }
  }
  return body
}

export async function getStockFundFlowTrendSeries(
  params: StockFundFlowTrendSeriesParams = {}
): Promise<StockFundFlowTrendSeriesResponse> {
  const q = new URLSearchParams()
  q.set('period', params.period || 'day')
  if (params.trade_date) q.set('trade_date', params.trade_date)
  if (params.top_n != null) q.set('top_n', String(params.top_n))

  const url = `/api/stock_fund_flow/trend_series?${q.toString()}`
  const res = await fetch(url, { headers: authHeaders() })
  const text = await res.text()
  let body: StockFundFlowTrendSeriesResponse = { success: false }
  try {
    body = text ? (JSON.parse(text) as StockFundFlowTrendSeriesResponse) : body
  } catch {
    body = { success: false, message: text?.slice(0, 200) || `HTTP ${res.status}` }
  }
  if (!res.ok) {
    return {
      success: false,
      message: body.message || `请求失败(${res.status})`,
    }
  }
  return body
}

const stockFundFlowRankService = {
  getRank: getStockFundFlowRank,
  getTrendSeries: getStockFundFlowTrendSeries,
  periods: STOCK_FUND_FLOW_RANK_PERIODS,
}

export default stockFundFlowRankService
