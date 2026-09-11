/**
 * 板块资金流向：业务接口 `/api/board_fund_flow/*`（非 /api/admin 前缀）。
 * 与 screeningPublicApi 一样走同源绝对路径，避免 apiService baseURL=/api/admin 拼接错误。
 */

export interface BoardFundFlowTodayItem {
  board_kind: string
  board_code: string
  board_name: string | null
  trade_date: string
  change_percent: number | null
  inflow_amount: number | null
  outflow_amount: number | null
  main_net_inflow: number | null
  source: string | null
}

export interface BoardFundFlowTodayData {
  trade_date: string | null
  items: BoardFundFlowTodayItem[]
  count: number
}

export interface BoardFundFlowTodayResponse {
  success: boolean
  data?: BoardFundFlowTodayData
  message?: string
}

export interface BoardFundFlowTodayParams {
  board_kind: 'industry' | 'concept'
  board_code_source?: string
  trade_date?: string
}

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('admin_token')
  const h: Record<string, string> = {}
  if (token) h.Authorization = `Bearer ${token}`
  return h
}

export async function getBoardFundFlowToday(
  params: BoardFundFlowTodayParams
): Promise<BoardFundFlowTodayResponse> {
  const q = new URLSearchParams()
  q.set('board_kind', params.board_kind)
  q.set('board_code_source', params.board_code_source || 'tonghuashun')
  if (params.trade_date) q.set('trade_date', params.trade_date)

  const url = `/api/board_fund_flow/today?${q.toString()}`
  const res = await fetch(url, { headers: authHeaders() })
  const text = await res.text()
  let body: BoardFundFlowTodayResponse = { success: false }
  try {
    body = text ? (JSON.parse(text) as BoardFundFlowTodayResponse) : body
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

const boardFundFlowService = {
  getToday: getBoardFundFlowToday,
}

export default boardFundFlowService
