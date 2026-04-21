import path from 'node:path'
import { saveCasesAsJson } from '../src/data/excel-case-parser'

const excelPath = path.resolve(process.cwd(), 'data/excel/web_cases.xlsx')
const outputPath = path.resolve(process.cwd(), 'data/generated/web_cases.json')

saveCasesAsJson(excelPath, outputPath)
console.log(`已转换用例: ${excelPath}`)
console.log(`输出 JSON: ${outputPath}`)
