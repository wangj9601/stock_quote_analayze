import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { test } from '../src/fixtures/auth.fixture'
import { parseExcelCases, type WebCase } from '../src/data/excel-case-parser'
import { runCase } from '../src/runner/case-runner'

const currentDir = path.dirname(fileURLToPath(import.meta.url))
const excelPath = path.resolve(currentDir, '../data/excel/web_cases.xlsx')
let cases: WebCase[] = []

try {
  cases = parseExcelCases(excelPath)
} catch {
  cases = []
}

test.describe('Excel 用例执行 @case', () => {
  test.skip(cases.length === 0, '未找到可执行的 Excel 用例，请先准备 web_cases.xlsx')

  for (const c of cases) {
    test(`${c.caseId} ${c.title} @case`, async ({ authenticatedPage }) => {
      await runCase(authenticatedPage, c)
    })
  }
})
