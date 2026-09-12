/**
 * 板块趋势（多窗口斜率）：业务接口 `/api/market/*_board/list`
 * 与 boardFundFlow 一样走同源绝对路径，避免 apiService baseURL=/api/admin 拼接错误。
 */

export type SectorSlopeWindow = 5 | 10 | 20 | 60 | 120

export interface BoardSectorTrendItem {
  board_code: string
  board_name: string
  /** 默认中线 60 日 */
  sector_slope: number | null
  sector_slope_window?: number | null
  slope_asof_date?: string | null
  slope_source?: string | null
  slope_r2?: number | null
  board_env?: string | null
  board_env_label?: string | null
  /** 其它窗口：120 / 20 / 5；10 日用 short 后缀 */
  sector_slope_120?: number | null
  sector_slope_120_window?: number | null
  slope_120_asof_date?: string | null
  slope_120_source?: string | null
  slope_120_r2?: number | null
  board_env_120?: string | null
  board_env_120_label?: string | null
  sector_slope_20?: number | null
  sector_slope_20_window?: number | null
  slope_20_asof_date?: string | null
  slope_20_source?: string | null
  slope_20_r2?: number | null
  board_env_20?: string | null
  board_env_20_label?: string | null
  sector_slope_short?: number | null
  sector_slope_short_window?: number | null
  slope_short_asof_date?: string | null
  slope_short_source?: string | null
  slope_short_r2?: number | null
  board_env_short?: string | null
  board_env_short_label?: string | null
  sector_slope_5?: number | null
  sector_slope_5_window?: number | null
  slope_5_asof_date?: string | null
  slope_5_source?: string | null
  slope_5_r2?: number | null
  board_env_5?: string | null
  board_env_5_label?: string | null
  change_percent?: number | null
  member_count?: number | null
}

/** 归一化后的单窗口斜率行，供图表直接使用 */
export interface BoardSectorTrendNormalized {
  board_code: string
  board_name: string
  sector_slope: number | null
  sector_slope_window: number
  slope_asof_date: string | null
  slope_source: string | null
  slope_r2: number | null
  board_env: string | null
  board_env_label: string | null
}

export interface BoardSectorTrendListResponse {
  success: boolean
  data?: BoardSectorTrendItem[]
  message?: string
}

export interface BoardSectorTrendListParams {
  board_kind: 'industry' | 'concept'
  board_code_source?: string
}

export const SECTOR_SLOPE_WINDOWS: SectorSlopeWindow[] = [5, 10, 20, 60, 120]

function asNumber(v: unknown): number | null {
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function asText(v: unknown): string | null {
  if (v == null || v === '') return null
  return String(v)
}

/**
 * 从列表行取出指定窗口的斜率/环境字段（与行情页字段命名一致）。
 */
export function normalizeTrendItemForWindow(
  item: BoardSectorTrendItem,
  window: SectorSlopeWindow
): BoardSectorTrendNormalized {
  const code = String(item.board_code || '')
  const name = String(item.board_name || item.board_code || '--')
  if (window === 60) {
    return {
      board_code: code,
      board_name: name,
      sector_slope: asNumber(item.sector_slope),
      sector_slope_window: asNumber(item.sector_slope_window) ?? 60,
      slope_asof_date: asText(item.slope_asof_date),
      slope_source: asText(item.slope_source),
      slope_r2: asNumber(item.slope_r2),
      board_env: asText(item.board_env),
      board_env_label: asText(item.board_env_label),
    }
  }
  if (window === 10) {
    return {
      board_code: code,
      board_name: name,
      sector_slope: asNumber(item.sector_slope_short),
      sector_slope_window: asNumber(item.sector_slope_short_window) ?? 10,
      slope_asof_date: asText(item.slope_short_asof_date),
      slope_source: asText(item.slope_short_source),
      slope_r2: asNumber(item.slope_short_r2),
      board_env: asText(item.board_env_short),
      board_env_label: asText(item.board_env_short_label),
    }
  }
  const suffix = String(window) as '5' | '20' | '120'
  const row = item as BoardSectorTrendItem & Record<string, unknown>
  return {
    board_code: code,
    board_name: name,
    sector_slope: asNumber(row[`sector_slope_${suffix}`]),
    sector_slope_window: asNumber(row[`sector_slope_${suffix}_window`]) ?? window,
    slope_asof_date: asText(row[`slope_${suffix}_asof_date`]),
    slope_source: asText(row[`slope_${suffix}_source`]),
    slope_r2: asNumber(row[`slope_${suffix}_r2`]),
    board_env: asText(row[`board_env_${suffix}`]),
    board_env_label: asText(row[`board_env_${suffix}_label`]),
  }
}

export function normalizeTrendListForWindow(
  items: BoardSectorTrendItem[],
  window: SectorSlopeWindow
): BoardSectorTrendNormalized[] {
  return items.map((x) => normalizeTrendItemForWindow(x, window))
}

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('admin_token')
  const h: Record<string, string> = {}
  if (token) h.Authorization = `Bearer ${token}`
  return h
}

function listUrl(kind: 'industry' | 'concept', source: string): string {
  const path =
    kind === 'concept'
      ? '/api/market/concept_board/list'
      : '/api/market/industry_board/list'
  const q = new URLSearchParams()
  q.set('board_code_source', source)
  return `${path}?${q.toString()}`
}

export async function getBoardSectorTrendList(
  params: BoardSectorTrendListParams
): Promise<BoardSectorTrendListResponse> {
  const source = params.board_code_source || 'tonghuashun'
  const url = listUrl(params.board_kind, source)
  const res = await fetch(url, { headers: authHeaders() })
  const text = await res.text()
  let body: BoardSectorTrendListResponse = { success: false }
  try {
    body = text ? (JSON.parse(text) as BoardSectorTrendListResponse) : body
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

const boardSectorTrendService = {
  getList: getBoardSectorTrendList,
  normalizeForWindow: normalizeTrendListForWindow,
  windows: SECTOR_SLOPE_WINDOWS,
}

export default boardSectorTrendService
