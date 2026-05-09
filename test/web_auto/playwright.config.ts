import { defineConfig, devices } from '@playwright/test'
import dotenv from 'dotenv'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const configDir = dirname(fileURLToPath(import.meta.url))
dotenv.config({ path: resolve(configDir, '.env.web-auto') })

export default defineConfig({
  testDir: './specs',
  testMatch: ['**/*.spec.ts'],
  // 排除会触发管理端「数据采集/AkShare」及后端东财等行情接口的用例，勿纳入 test:all
  testIgnore: ['**/*.test.ts', '**/node_modules/**', '**/data-collection.spec.ts'],
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [['html', { open: 'never' }], ['list']],
  timeout: 60_000,
  expect: {
    timeout: 10_000
  },
  workers: 1,
  use: {
    baseURL: process.env.WEB_BASE_URL ?? 'http://127.0.0.1:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    headless: process.env.HEADLESS !== 'false',
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] }
    }
  ]
})
