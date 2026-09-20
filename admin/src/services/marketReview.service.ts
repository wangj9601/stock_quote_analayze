/**
 * 每日复盘：业务接口 `/api/market_review/*`（非 /api/admin 前缀）。
 */

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('admin_token')
  const h: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) h.Authorization = `Bearer ${token}`
  return h
}

async function parseJson<T extends { success?: boolean; message?: string }>(
  res: Response
): Promise<T> {
  const text = await res.text()
  let body = { success: false } as T
  try {
    body = text ? (JSON.parse(text) as T) : body
  } catch {
    body = { success: false, message: text?.slice(0, 200) || `HTTP ${res.status}` } as T
  }
  if (!res.ok) {
    return {
      ...body,
      success: false,
      message: body.message || `请求失败(${res.status})`,
    }
  }
  return body
}

export async function getDailyReview(tradeDate: string) {
  const q = new URLSearchParams({ trade_date: tradeDate })
  const res = await fetch(`/api/market_review/daily?${q}`, { headers: authHeaders() })
  return parseJson<{ success: boolean; data?: any; message?: string }>(res)
}

export async function computeDailyReview(tradeDate: string, collectZt = true) {
  const q = new URLSearchParams({
    trade_date: tradeDate,
    collect_zt: collectZt ? 'true' : 'false',
    export_md: 'false',
    sync: 'true',
  })
  const res = await fetch(`/api/market_review/compute?${q}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return parseJson<{ success: boolean; data?: any; zt_pool?: any; message?: string }>(res)
}

export async function collectZtPool(tradeDate: string) {
  const q = new URLSearchParams({ trade_date: tradeDate, sync: 'true' })
  const res = await fetch(`/api/market_review/zt_pool/collect?${q}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return parseJson<{ success: boolean; written?: number; message?: string; error?: string }>(res)
}

export async function saveDailyReviewText(
  tradeDate: string,
  body: { viewpoint_md?: string; advice_md?: string }
) {
  const q = new URLSearchParams({ trade_date: tradeDate })
  const res = await fetch(`/api/market_review/daily?${q}`, {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify(body),
  })
  return parseJson<{ success: boolean; data?: any; message?: string }>(res)
}

export async function exportDailyReviewMd(tradeDate: string): Promise<{
  ok: boolean
  filename?: string
  message?: string
}> {
  const q = new URLSearchParams({ trade_date: tradeDate })
  const res = await fetch(`/api/market_review/export.md?${q}`, { headers: authHeaders() })
  const ct = (res.headers.get('Content-Type') || '').toLowerCase()
  if (!res.ok || ct.includes('application/json')) {
    const body = await parseJson<{ success?: boolean; message?: string }>(res)
    return { ok: false, message: body.message || `Markdown 导出失败(${res.status})` }
  }
  const blob = await res.blob()
  const filename = filenameFromDisposition(res, `daily_review_${tradeDate}.md`)
  triggerDownload(blob, filename)
  return { ok: true, filename }
}

/** 下载复盘 PDF 到浏览器默认下载目录，不写入工程目录。 */
export async function exportDailyReviewPdf(tradeDate: string): Promise<{
  ok: boolean
  filename?: string
  message?: string
}> {
  const q = new URLSearchParams({ trade_date: tradeDate })
  const res = await fetch(`/api/market_review/export.pdf?${q}`, { headers: authHeaders() })
  const ct = (res.headers.get('Content-Type') || '').toLowerCase()
  if (!res.ok || ct.includes('application/json')) {
    const body = await parseJson<{ success?: boolean; message?: string }>(res)
    return { ok: false, message: body.message || `PDF 导出失败(${res.status})` }
  }
  const blob = await res.blob()
  const filename = filenameFromDisposition(res, `daily_review_${tradeDate}.pdf`)
  triggerDownload(blob, filename)
  return { ok: true, filename }
}

function filenameFromDisposition(res: Response, fallback: string): string {
  const cd = res.headers.get('Content-Disposition') || ''
  const mStar = /filename\*=UTF-8''([^;]+)/i.exec(cd)
  const m = /filename="?([^";]+)"?/i.exec(cd)
  if (mStar) {
    try {
      return decodeURIComponent(mStar[1])
    } catch {
      return mStar[1]
    }
  }
  if (m) return m[1]
  return fallback
}

function triggerDownload(blob: Blob, filename: string) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}
