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

/** 行情中心板块详情深链（同花顺口径） */
export function boardDetailUrl(opts: {
  boardKind: 'industry' | 'concept'
  boardCode: string
  boardName?: string
  boardCodeSource?: string
}): string {
  const code = String(opts.boardCode || '').trim()
  const q = new URLSearchParams({
    board_kind: opts.boardKind === 'concept' ? 'concept' : 'industry',
    board_code: code,
    board_code_source: opts.boardCodeSource || 'tonghuashun',
  })
  const name = String(opts.boardName || '').trim()
  if (name) q.set('board_name', name)
  return `/board_detail.html?${q.toString()}`
}
