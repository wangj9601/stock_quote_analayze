/**
 * 网站端同源公开选股接口 `/api/screening/*`（与 frontend/js/screening.js 一致）。
 * 管理端使用 Bearer（admin_token），行为与网站登录用户一致。
 */

export interface ScreeningJsonResponse {
  success: boolean
  data?: unknown[]
  message?: string
  search_date?: string
  total?: number
  strategy_name?: string
  paging?: {
    enabled: boolean
    page: number
    page_size: number
    total: number
    total_pages: number
  }
}

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('admin_token')
  const h: Record<string, string> = {}
  if (token) h.Authorization = `Bearer ${token}`
  return h
}

/** path 不含前缀，如 `cyb-midline-strategy?months=4` */
export async function screeningGet(pathWithoutPrefix: string): Promise<ScreeningJsonResponse> {
  const path = pathWithoutPrefix.replace(/^\/+/, '')
  const url = `/api/screening/${path}`
  const res = await fetch(url, { headers: authHeaders() })
  const text = await res.text()
  const ct = res.headers.get('Content-Type') || ''

  if (!res.ok) {
    let msg = `请求失败(${res.status})`
    if (ct.includes('application/json') && text?.trim().startsWith('{')) {
      try {
        const j = JSON.parse(text) as { detail?: unknown; message?: string }
        const d = j.detail
        msg =
          typeof d === 'string'
            ? d
            : Array.isArray(d)
              ? (d as { msg?: string }[])
                  .map((x) => x.msg || '')
                  .join('; ') || msg
              : j.message || msg
      } catch {
        if (text.length < 400) msg = text
      }
    } else if (text && text.length < 400) {
      msg = text
    }
    throw new Error(msg)
  }

  if (!ct.includes('application/json') || !text?.trim().startsWith('{')) {
    throw new Error('服务器返回了非 JSON 数据')
  }

  try {
    return JSON.parse(text) as ScreeningJsonResponse
  } catch {
    throw new Error('解析响应失败')
  }
}

export async function pvfrsParamsGet(): Promise<{ success: boolean; data?: Record<string, unknown>; message?: string }> {
  const res = await fetch('/api/screening/pvfrs-params', { headers: authHeaders() })
  const json = (await res.json().catch(() => ({}))) as {
    success: boolean
    data?: Record<string, unknown>
    message?: string
  }
  if (!res.ok) {
    throw new Error(json.message || `加载参数失败(${res.status})`)
  }
  return json
}

export async function pvfrsParamsPost(body: Record<string, unknown>): Promise<{ success: boolean; message?: string }> {
  const res = await fetch('/api/screening/pvfrs-params', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  const json = (await res.json().catch(() => ({}))) as { success: boolean; message?: string }
  if (!res.ok) {
    throw new Error(json.message || `保存失败(${res.status})`)
  }
  return json
}
