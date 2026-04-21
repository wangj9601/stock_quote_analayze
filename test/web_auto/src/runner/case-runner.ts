import { expect, type Page } from '@playwright/test'
import type { WebCase, WebCaseStep } from '../data/excel-case-parser.js'

async function runStep(page: Page, step: WebCaseStep): Promise<void> {
  const target = page.locator(step.target)

  switch (step.action) {
    case 'click':
      await target.click()
      break
    case 'fill':
      await target.fill(step.value ?? '')
      break
    case 'press':
      await target.press(step.value ?? 'Enter')
      break
    case 'assertVisible':
      await expect(target).toBeVisible()
      break
    case 'assertText':
      await expect(target).toContainText(step.expect ?? '')
      break
    case 'goto':
      await page.goto(step.target)
      break
    default:
      throw new Error(`不支持的 action: ${step.action}`)
  }
}

export async function runCase(page: Page, testCase: WebCase): Promise<void> {
  for (const step of testCase.steps) {
    await runStep(page, step)
  }
}
