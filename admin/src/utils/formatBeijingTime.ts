/**
 * ISO 时间 → 北京时间（Asia/Shanghai）展示，24 小时制 YYYY-MM-DD HH:mm:ss
 */
export function formatDateTimeBeijing(iso: string | undefined | null): string {
  if (iso == null || String(iso).trim() === '') return '-'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '-'
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  })
  const parts = formatter.formatToParts(d)
  const get = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((p) => p.type === type)?.value ?? ''
  return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}:${get('second')}`
}
