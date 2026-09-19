/**
 * 龙虎榜：`GET /api/market/dragon-tiger`。
 * 同源绝对路径，避免管理端 apiService baseURL=/api/admin 拼接错误。
 */

export type DragonTigerBoardType = 'all' | 'org' | 'hot_money'

export interface DragonTigerStockItem {
  code: string
  name: string | null
  change_percent: number | null
  close: number | null
  buy_value: number | null
  sell_value: number | null
  net_value: number | null
  net_rate: number | null
  org_net_value: number | null
  hot_money_net_value: number | null
  reason: string | null
  interpretation: string | null
}

export interface DragonTigerSeat {
  name: string
  buy_value: number | null
  sell_value: number | null
  net_value: number | null
  stocks: DragonTigerStockItem[]
}

export interface DragonTigerData {
  source: string
  source_label: string
  board_type: DragonTigerBoardType | string
  trade_date: string | null
  stock_count: number
  count: number
  amount_unit: string
  items: DragonTigerStockItem[]
  hot_money_items: DragonTigerSeat[]
  fallback_reason: string | null
  board_type_note: string | null
}

export interface DragonTigerResponse {
  success: boolean
  data?: DragonTigerData
  message?: string
}

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('admin_token')
  const h: Record<string, string> = {}
  if (token) h.Authorization = `Bearer ${token}`
  return h
}

export async function getDragonTiger(params: {
  board_type?: DragonTigerBoardType
  date?: string
}): Promise<DragonTigerResponse> {
  const q = new URLSearchParams()
  q.set('board_type', params.board_type || 'all')
  if (params.date) q.set('date', params.date)
  const url = `/api/market/dragon-tiger?${q.toString()}`
  const res = await fetch(url, { headers: authHeaders() })
  const text = await res.text()
  let body: DragonTigerResponse = { success: false }
  try {
    body = text ? (JSON.parse(text) as DragonTigerResponse) : body
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
