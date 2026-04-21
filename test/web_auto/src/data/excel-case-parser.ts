import fs from 'node:fs'
import path from 'node:path'
import xlsx from 'xlsx'

export interface WebCaseStep {
  action: string
  target: string
  value?: string
  expect?: string
}

export interface WebCase {
  caseId: string
  title: string
  tags: string[]
  precondition?: string
  steps: WebCaseStep[]
}

interface RawCaseRow {
  caseId: string
  title: string
  tags?: string
  precondition?: string
  stepAction: string
  stepTarget: string
  stepValue?: string
  stepExpect?: string
}

function readRows(excelPath: string): RawCaseRow[] {
  const workbook = xlsx.readFile(excelPath)
  const firstSheet = workbook.Sheets[workbook.SheetNames[0]]
  const rows = xlsx.utils.sheet_to_json<RawCaseRow>(firstSheet, { defval: '' })
  return rows
}

export function parseExcelCases(excelPath: string): WebCase[] {
  if (!fs.existsSync(excelPath)) {
    throw new Error(`未找到 Excel 用例文件: ${excelPath}`)
  }

  const grouped = new Map<string, WebCase>()
  for (const row of readRows(excelPath)) {
    if (!row.caseId || !row.title || !row.stepAction || !row.stepTarget) {
      continue
    }

    if (!grouped.has(row.caseId)) {
      grouped.set(row.caseId, {
        caseId: row.caseId,
        title: row.title,
        tags: row.tags
          ? row.tags
              .split(',')
              .map((s) => s.trim())
              .filter(Boolean)
          : [],
        precondition: row.precondition || undefined,
        steps: []
      })
    }

    grouped.get(row.caseId)?.steps.push({
      action: row.stepAction.trim(),
      target: row.stepTarget.trim(),
      value: row.stepValue?.trim() || undefined,
      expect: row.stepExpect?.trim() || undefined
    })
  }

  return [...grouped.values()]
}

export function saveCasesAsJson(excelPath: string, outputPath: string): void {
  const cases = parseExcelCases(excelPath)
  const outputDir = path.dirname(outputPath)
  fs.mkdirSync(outputDir, { recursive: true })
  fs.writeFileSync(outputPath, JSON.stringify(cases, null, 2), 'utf8')
}
