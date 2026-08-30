/** 与网站 static 页一致：由 Vite / Nginx 提供 /stock.html、/stock_history.html */

export function stockDetailUrl(code: string, name?: string): string {
  const c = String(code || '').trim()
  const n = String(name || '').trim()
  return `/stock.html?code=${encodeURIComponent(c)}&name=${encodeURIComponent(n)}`
}

export function stockHistoryUrl(code: string): string {
  return `/stock_history.html?code=${encodeURIComponent(String(code || '').trim())}`
}

export function stockRsTraceUrl(code: string): string {
  return `/stock_rs_trace.html?code=${encodeURIComponent(String(code || '').trim())}`
}
